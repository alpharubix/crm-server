from typing import Optional, List, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from starlette.requests import Request

from src.database import get_db
from src.models.support_ticket import SupportTicket
from src.models.user import User
from src.schemas.support_tickets import (
    SupportTicketCreate,
    SupportTicketStatusUpdate,
    SupportTicketUpdate,
)

support_tickets_router = APIRouter(prefix="/v1/support-ticket", tags=["Support Tickets"])


def _normalize_links(links_raw: Optional[Union[List[str], str]], single_link_raw: Optional[Union[List[str], str]] = None) -> List[str]:
    result = []
    if links_raw:
        if isinstance(links_raw, list):
            result.extend([str(l).strip() for l in links_raw if str(l).strip()])
        elif isinstance(links_raw, str) and links_raw.strip():
            result.append(links_raw.strip())
    if single_link_raw:
        if isinstance(single_link_raw, list):
            result.extend([str(l).strip() for l in single_link_raw if str(l).strip()])
        elif isinstance(single_link_raw, str) and single_link_raw.strip():
            result.append(single_link_raw.strip())
    return list(dict.fromkeys(result))



@support_tickets_router.post("/create")
def create_support_ticket(
    request: Request,
    payload: SupportTicketCreate,
    db: Session = Depends(get_db)
):
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        max_id = db.query(func.max(SupportTicket.id)).scalar() or 0
        ticket_code = f"ST-{max_id + 1001}"

        links = _normalize_links(payload.attachment_links, payload.attachment_link)

        ticket = SupportTicket(
            ticket_id=ticket_code,
            user_id=user_id,
            title=payload.title,
            service=payload.service,
            priority=payload.priority,
            description=payload.description,
            status="OPEN",
            attachment_links=links,
            attachments=links,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        return {
            "message": "Support ticket created successfully",
            "data": {
                "ticket_id": ticket.ticket_id,
                "status": ticket.status,
                "attachment_links": ticket.attachment_links or [],
                "created_at": ticket.created_at.strftime("%Y-%m-%d %I:%M:%S %p") if ticket.created_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create support ticket: {str(e)}"
        )


@support_tickets_router.get("/history")
def get_support_ticket_history(
    request: Request,
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Ticket status filter"),
    priority: Optional[str] = Query(None, description="Ticket priority filter"),
    search: Optional[str] = Query(None, description="Search ticket ID or title"),
    db: Session = Depends(get_db)
):
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        user_role_str = str(getattr(request.state, "role", "user")).lower().replace(" ", "_")

        company_filter = or_(SupportTicket.company_id == 1, SupportTicket.company_id.is_(None))
        query = db.query(SupportTicket).options(
            joinedload(SupportTicket.user),
            joinedload(SupportTicket.updater)
        ).filter(company_filter)

        # Managers, Admins, Super Admins can see all tickets, regular users see their own
        if user_role_str not in ["admin", "superadmin", "super_admin", "manager"]:
            query = query.filter(SupportTicket.user_id == user_id)

        # Period / Date & Time filters
        if from_date:
            if len(from_date.strip()) > 10:
                query = query.filter(SupportTicket.created_at >= from_date.strip().replace("T", " "))
            else:
                query = query.filter(func.date(SupportTicket.created_at) >= from_date.strip())
        if to_date:
            if len(to_date.strip()) > 10:
                query = query.filter(SupportTicket.created_at <= to_date.strip().replace("T", " "))
            else:
                query = query.filter(func.date(SupportTicket.created_at) <= to_date.strip())

        # Status filter
        if status and status.upper() != "ALL":
            status_clean = status.upper().replace(" ", "_")
            if status_clean == "INPROGRESS":
                status_clean = "IN_PROGRESS"
            query = query.filter(func.upper(SupportTicket.status) == status_clean)

        # Priority filter
        if priority and priority.upper() != "ALL":
            query = query.filter(func.lower(SupportTicket.priority) == priority.lower())

        # Search filter
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SupportTicket.ticket_id.ilike(term),
                    SupportTicket.title.ilike(term),
                    SupportTicket.service.ilike(term),
                    SupportTicket.description.ilike(term),
                )
            )

        tickets = query.order_by(SupportTicket.id.desc()).all()

        formatted_tickets = []
        for t in tickets:
            links = t.attachment_links or t.attachments or []
            if not isinstance(links, list):
                links = [links] if links else []

            formatted_tickets.append({
                "ticket_id": t.ticket_id,
                "title": t.title,
                "service": t.service,
                "priority": t.priority,
                "description": t.description,
                "status": t.status,
                "attachment_links": links,
                "attachment_link": links[0] if links else None,
                "created_at": t.created_at.strftime("%Y-%m-%d %I:%M:%S %p") if t.created_at else None,
                "updated_at": t.updated_at.strftime("%Y-%m-%d %I:%M:%S %p") if t.updated_at else None,
                "user_id": str(t.user_id),
                "user_name": t.user.full_name if t.user else None,
                "user_email": t.user.email if t.user else None,
                "updated_by": str(t.updated_by) if t.updated_by else None,
                "updated_by_name": t.updater.full_name if t.updater else None,
                "updated_by_email": t.updater.email if t.updater else None,
            })

        return {
            "message": "Support ticket history fetched successfully",
            "data": formatted_tickets
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch support ticket history: {str(e)}"
        )


@support_tickets_router.put("/{ticket_id}/status")
@support_tickets_router.patch("/{ticket_id}/status")
def update_support_ticket_status(
    ticket_id: str,
    payload: SupportTicketStatusUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        user_id = getattr(request.state, "user_id", None)
        user_role_str = str(getattr(request.state, "role", "user")).lower().replace(" ", "_")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == ticket_id).first()
        if not ticket and ticket_id.isdigit():
            ticket = db.query(SupportTicket).filter(SupportTicket.id == int(ticket_id)).first()

        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Support ticket '{ticket_id}' not found in database"
            )

        # Deactivate status updates when ticket is CLOSED
        if ticket.status and ticket.status.upper() == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ticket is marked as CLOSED and cannot be updated."
            )

        is_admin = user_role_str in ["admin", "superadmin", "super_admin", "manager"]
        is_creator = str(ticket.user_id) == str(user_id)

        if not (is_admin or is_creator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied. Only admins or the ticket creator can update ticket status."
            )

        allowed_statuses = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
        new_status = payload.status.upper()
        if new_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}"
            )

        ticket.status = new_status
        ticket.updated_by = user_id
        db.commit()
        db.refresh(ticket)

        updater_name = None
        updater_email = None
        if ticket.updater:
            updater_name = ticket.updater.full_name
            updater_email = ticket.updater.email
        else:
            u = db.query(User).filter(User.id == user_id).first()
            if u:
                updater_name = u.full_name
                updater_email = u.email

        return {
            "message": f"Ticket status updated to {new_status}",
            "data": {
                "ticket_id": ticket.ticket_id,
                "status": ticket.status,
                "updated_by": str(ticket.updated_by) if ticket.updated_by else None,
                "updated_by_name": updater_name,
                "updated_by_email": updater_email,
                "updated_at": ticket.updated_at.strftime("%Y-%m-%d %I:%M:%S %p") if ticket.updated_at else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update ticket status: {str(e)}"
        )


@support_tickets_router.put("/{ticket_id}")
@support_tickets_router.patch("/{ticket_id}")
def update_support_ticket(
    ticket_id: str,
    payload: SupportTicketUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        user_id = getattr(request.state, "user_id", None)
        user_role_str = str(getattr(request.state, "role", "user")).lower().replace(" ", "_")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == ticket_id).first()
        if not ticket and ticket_id.isdigit():
            ticket = db.query(SupportTicket).filter(SupportTicket.id == int(ticket_id)).first()

        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Support ticket '{ticket_id}' not found in database"
            )

        # Deactivate updates when ticket is CLOSED
        if ticket.status and ticket.status.upper() == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ticket is marked as CLOSED and cannot be updated."
            )

        is_admin = user_role_str in ["admin", "superadmin", "super_admin", "manager"]
        is_creator = str(ticket.user_id) == str(user_id)

        if not (is_admin or is_creator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied. Only admins or the ticket creator can update this ticket."
            )

        if payload.status:
            allowed_statuses = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
            new_status = payload.status.upper()
            if new_status not in allowed_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}"
                )
            ticket.status = new_status

        if payload.title is not None and payload.title.strip():
            ticket.title = payload.title.strip()
        if payload.description is not None and payload.description.strip():
            ticket.description = payload.description.strip()
        if payload.service is not None and payload.service.strip():
            ticket.service = payload.service.strip()
        if payload.priority is not None and payload.priority.strip():
            ticket.priority = payload.priority.strip()
        if payload.attachment_links is not None or payload.attachment_link is not None:
            links = _normalize_links(payload.attachment_links, payload.attachment_link)
            ticket.attachment_links = links
            ticket.attachments = links

        ticket.updated_by = user_id
        db.commit()
        db.refresh(ticket)

        updater_name = None
        updater_email = None
        if ticket.updater:
            updater_name = ticket.updater.full_name
            updater_email = ticket.updater.email
        else:
            u = db.query(User).filter(User.id == user_id).first()
            if u:
                updater_name = u.full_name
                updater_email = u.email

        links = ticket.attachment_links or ticket.attachments or []
        if not isinstance(links, list):
            links = [links] if links else []

        return {
            "message": "Support ticket updated successfully",
            "data": {
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "service": ticket.service,
                "priority": ticket.priority,
                "description": ticket.description,
                "status": ticket.status,
                "attachment_links": links,
                "updated_by": str(ticket.updated_by) if ticket.updated_by else None,
                "updated_by_name": updater_name,
                "updated_by_email": updater_email,
                "updated_at": ticket.updated_at.strftime("%Y-%m-%d %I:%M:%S %p") if ticket.updated_at else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update support ticket: {str(e)}"
        )

