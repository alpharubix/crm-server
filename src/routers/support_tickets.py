from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from starlette.requests import Request

from src.database import get_db
from src.models.support_ticket import SupportTicket
from src.schemas.support_tickets import SupportTicketCreate, SupportTicketStatusUpdate

support_tickets_router = APIRouter(prefix="/v1/support-ticket", tags=["Support Tickets"])



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

        ticket = SupportTicket(
            ticket_id=ticket_code,
            user_id=user_id,
            title=payload.title,
            service=payload.service,
            priority=payload.priority,
            description=payload.description,
            status="OPEN"
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        return {
            "message": "Support ticket created successfully",
            "data": {
                "ticket_id": ticket.ticket_id,
                "status": ticket.status,
                "created_at": ticket.created_at.strftime("%Y-%m-%d %H:%M:%S") if ticket.created_at else None
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
        # Managers, Admins, Super Admins can see all tickets, regular users see their own
        if user_role_str in ["admin", "superadmin", "super_admin", "manager"]:
            tickets = db.query(SupportTicket).filter(company_filter).order_by(SupportTicket.id.desc()).all()
        else:
            tickets = db.query(SupportTicket).filter(company_filter, SupportTicket.user_id == user_id).order_by(SupportTicket.id.desc()).all()


        formatted_tickets = []
        for t in tickets:
            formatted_tickets.append({
                "ticket_id": t.ticket_id,
                "title": t.title,
                "service": t.service,
                "priority": t.priority,
                "description": t.description,
                "status": t.status,
                "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else None,
                "user_id": t.user_id
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

        # Only admin and super_admin/superadmin can update ticket status
        is_admin = user_role_str in ["admin", "superadmin", "super_admin"]

        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied. Only admins and super_admins can update ticket status."
            )



        allowed_statuses = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
        new_status = payload.status.upper()
        if new_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}"
            )

        ticket.status = new_status
        db.commit()
        db.refresh(ticket)

        return {
            "message": f"Ticket status updated to {new_status}",
            "data": {
                "ticket_id": ticket.ticket_id,
                "status": ticket.status
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

