import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from starlette.requests import Request

from src.controllers.auth import MANAGERID
# from src.controllers.Background_threads import BackgroundThreadPool
# from src.controllers.mail import send_general_email
from src.models.account import Account
from src.models.deal import Deal


def export_accounts_csv(
    request: Request,
    db: Session,
    account_name: Optional[str] = None,
    account_status: Optional[list[str]] = None,
    account_stage: Optional[str] = None,
    source: Optional[list[str]] = None,
    industry: Optional[list[str]] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    phone_number: Optional[str] = None,
    account_owner_id: Optional[list[int]] = None,
    call_back_date_time: Optional[str] = None,
):

    # --- . RBAC ---
    MANAGER_EXECUTIVES_MAP = MANAGERID().MANAGER_EXECUTIVES_MAP
    user_id = request.state.user_id
    role = request.state.role

    filters = []

    allowed_owner_ids = None
    if role in ("super_admin", "admin"):
        pass
    elif role == "manager":
        allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
        filters.append(Account.account_owner_id.in_(allowed_owner_ids))
    elif role == "executive":
        allowed_owner_ids = [user_id]
        filters.append(Account.account_owner_id.in_(allowed_owner_ids))

    # --- . Block bulk export FIRST, before anything else ---
    no_filters_applied = not any(
        [
            account_name,
            account_status,
            account_stage,
            source,
            industry,
            city,
            state,
            phone_number,
            account_owner_id,
            call_back_date_time,
        ]
    )
    # --- . Query filters ---
    if account_name:
        filters.append(Account.account_name.ilike(f"%{account_name.strip()}%"))
    if account_status:
        status_list = [s.strip() for s in (account_status if isinstance(account_status, list) else [account_status]) if s and s.strip()]
        if status_list:
            filters.append(
                or_(*[Account.account_status.ilike(f"{status}%") for status in status_list])
            )
    if account_stage:
        filters.append(Account.account_stage.ilike(f"{account_stage.strip()}%"))
    if source:
        source_list = [s.strip() for s in (source if isinstance(source, list) else [source]) if s and s.strip()]
        if source_list:
            filters.append(
                or_(*[Account.source.ilike(f"{src}%") for src in source_list])
            )
    # if type_of_business:
    #     pass  # Just in case we need it, but type_of_business is not in export_accounts_csv parameters
    if industry:
        industry_list = [ind.strip() for ind in (industry if isinstance(industry, list) else [industry]) if ind and ind.strip()]
        if industry_list:
            filters.append(
                or_(*[Account.industry.ilike(ind) for ind in industry_list])
            )
    if city:
        filters.append(Account.city.ilike(f"%{city.strip()}%"))
    if state:
        filters.append(Account.state.ilike(f"%{state.strip()}%"))
    if phone_number and phone_number.strip():
        filters.append(
            or_(
                Account.phone.like(f"%{phone_number}%"),
                Account.phone.like(f"%91{phone_number}%"),
                Account.phone.like(f"%+91{phone_number}%"),
            )
        )
    if account_owner_id:
        owner_ids = [int(oid) for oid in (account_owner_id if isinstance(account_owner_id, list) else [account_owner_id]) if oid is not None]
        if owner_ids:
            if role in ("super_admin", "admin"):
                filters.append(Account.account_owner_id.in_(owner_ids))
            else:
                allowed_set = {int(x) for x in (allowed_owner_ids or [])}
                if not all(oid in allowed_set for oid in owner_ids):
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "You do not have permission to access records for this owner",
                            "success": False,
                        },
                    )
                filters.append(Account.account_owner_id.in_(owner_ids))
    if call_back_date_time:
        try:
            dt = datetime.fromisoformat(call_back_date_time)
            filters.append(Account.call_back_date_time != None)
            filters.append(Account.call_back_date_time <= dt)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid call_back_date_time format. Use ISO format e.g. 2024-01-31T00:00:00",
            )

    count = db.query(Account.id).filter(and_(*filters) if filters else True).count()
    if count == 0:
        raise HTTPException(
            status_code=404, detail="No Accounts found for the applied filters."
        )
    # 5. Fetch rows — ALL columns except custom_fields (JSONB, useless in CSV)
    rows = (
        db.query(
            Account.id,
            Account.first_name,
            Account.last_name,
            Account.email,
            Account.phone,
            Account.account_name,
            Account.account_owner_id,
            Account.account_status,
            Account.account_stage,
            Account.source,
            Account.business_status,
            Account.distributor_code,
            Account.type_of_business,
            Account.industry,
            Account.city,
            Account.state,
            Account.pincode,
            Account.waba_interested,
            Account.call_back_date_time,
            Account.created_time,
            Account.modified_time,
            Account.assignment_date,
            Account.created_by_id,
        )
        .filter(and_(*filters) if filters else True)
        .all()
    )

    # 6. Stream
    filename = f"accounts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "ID",
                "First Name",
                "Last Name",
                "Email",
                "Phone",
                "Account Name",
                "Account Owner ID",
                "Account Status",
                "Account Stage",
                "Source",
                "Business Status",
                "Distributor Code",
                "Type of Business",
                "Industry",
                "City",
                "State",
                "Pincode",
                "WABA Interested",
                "Callback DateTime",
                "Created Time",
                "Modified Time",
                "Assignment Date",
                "Created By ID",
            ]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for row in rows:
            writer.writerow(
                [
                    str(row.id) if row.id else "",
                    row.first_name or "",
                    row.last_name or "",
                    row.email or "",
                    row.phone or "",
                    row.account_name or "",
                    str(row.account_owner_id) if row.account_owner_id else "",
                    row.account_status or "",
                    row.account_stage or "",
                    row.source or "",
                    row.business_status or "",
                    row.distributor_code or "",
                    row.type_of_business or "",
                    row.industry or "",
                    row.city or "",
                    row.state or "",
                    row.pincode or "",
                    str(row.waba_interested) if row.waba_interested is not None else "",
                    row.call_back_date_time.strftime("%Y-%m-%d %H:%M:%S")
                    if row.call_back_date_time
                    else "",
                    row.created_time.strftime("%Y-%m-%d %H:%M:%S")
                    if row.created_time
                    else "",
                    row.modified_time.strftime("%Y-%m-%d %H:%M:%S")
                    if row.modified_time
                    else "",
                    row.assignment_date.strftime("%Y-%m-%d %H:%M:%S")
                    if row.assignment_date
                    else "",
                    str(row.created_by_id) if row.created_by_id else "",
                ]
            )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    # start a background thread for sending a mail in the background
    # BackgroundThreadPool.execute_task(
    #     intimate_user_via_mail,
    #     to="prathap@r1xchange.com",
    #     body=f"""
    #             <p>Dear Super Admin,</p>
    #
    #             <p>This is an automated notification to inform you that a <strong>data export</strong> has been initiated on the system. Please find the details below:</p>
    #
    #             <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
    #                 <tr>
    #                     <td style="padding: 8px; border: 1px solid #ddd;"><strong>Module</strong></td>
    #                     <td style="padding: 8px; border: 1px solid #ddd;">{"Accounts"}</td>
    #                 </tr>
    #                 <tr>
    #                     <td style="padding: 8px; border: 1px solid #ddd;"><strong>Role</strong></td>
    #                     <td style="padding: 8px; border: 1px solid #ddd;">{role}</td>
    #                 </tr>
    #                  <tr>
    #                     <td style="padding: 8px; border: 1px solid #ddd;"><strong>user_id</strong></td>
    #                     <td style="padding: 8px; border: 1px solid #ddd;">{user_id}</td>
    #                 </tr>
    #                 <tr>
    #                     <td style="padding: 8px; border: 1px solid #ddd;"><strong>Date & Time</strong></td>
    #                     <td style="padding: 8px; border: 1px solid #ddd;">{datetime.now().strftime("%d %b %Y, %I:%M %p")}
    #  }}</td>
    #                 </tr>
    #
    #             </table>
    #
    #             <p>If this activity was expected and authorized, no action is required. However, if this export appears suspicious or unauthorized, please review the activity immediately and take appropriate action.</p>
    #
    #             <p>For audit purposes, this event has been logged in the system.</p>
    #
    #             <br/>
    #             <p>Regards,</p>
    #             <p><strong>System Notification Service</strong></p>
    #             <p style="color: gray; font-size: 12px;">This is an automated message. Please do not reply to this email.</p>
    #         """,
    #     subject="[Data Export Alert] Account Data Export Initiated – Action Log Notification",
    # )

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def export_deals_csv(
    request: Request,
    db: Session,
    account_name: Optional[str] = None,
    lender_name: Optional[list[str]] = None,
    case_status: Optional[list[str]] = None,
    ticket_login: Optional[list[str]] = None,
    loan_type: Optional[list[str]] = None,
    type_of_case_login: Optional[list[str]] = None,
    deal_owner_id: Optional[list[int]] = None,
):
    # 1. RBAC first
    MANAGER_EXECUTIVES_MAP = (
        MANAGERID.MANAGER_EXECUTIVES_MAP
    )  # class-level, matches deals controller
    user_id = int(request.state.user_id)
    role = request.state.role

    filters = []

    allowed_owner_ids = None
    if role in ("super_admin", "admin"):
        pass
    elif role == "manager":
        allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
        filters.append(Deal.deal_owner_id.in_(allowed_owner_ids))
    elif role == "executive":
        allowed_owner_ids = [user_id]
        filters.append(Deal.deal_owner_id.in_(allowed_owner_ids))

    # 2. Block bulk export
    no_filters_applied = not any(
        [
            account_name,
            lender_name,
            case_status,
            ticket_login,
            loan_type,
            type_of_case_login,
            deal_owner_id,
        ]
    )

    # 3. Query filters
    if account_name:
        filters.append(Deal.account_name.ilike(f"%{account_name.strip()}%"))
    if lender_name:
        lenders = [l.strip() for l in (lender_name if isinstance(lender_name, list) else [lender_name]) if l and l.strip()]
        if lenders:
            filters.append(
                or_(*[Deal.lender_name.ilike(f"%{l}%") for l in lenders])
            )
    if case_status:
        statuses = [s.strip() for s in (case_status if isinstance(case_status, list) else [case_status]) if s and s.strip()]
        if statuses:
            filters.append(
                or_(*[Deal.deal_status.ilike(f"%{s}%") for s in statuses])
            )
    if ticket_login:
        tickets = [t.strip() for t in (ticket_login if isinstance(ticket_login, list) else [ticket_login]) if t and t.strip()]
        if tickets:
            filters.append(
                or_(*[Deal.ticket_login.ilike(f"%{t}%") for t in tickets])
            )
    if loan_type:
        loan_types = [lt.strip() for lt in (loan_type if isinstance(loan_type, list) else [loan_type]) if lt and lt.strip()]
        if loan_types:
            filters.append(
                or_(*[Deal.loan_type.ilike(f"%{lt}%") for lt in loan_types])
            )
    if type_of_case_login:
        cases = [c.strip() for c in (type_of_case_login if isinstance(type_of_case_login, list) else [type_of_case_login]) if c and c.strip()]
        if cases:
            filters.append(
                or_(*[Deal.type_of_case_login.ilike(f"%{c}%") for c in cases])
            )
    if deal_owner_id:
        owner_ids = [int(oid) for oid in (deal_owner_id if isinstance(deal_owner_id, list) else [deal_owner_id]) if oid is not None]
        if owner_ids:
            if role in ("super_admin", "admin"):
                filters.append(Deal.deal_owner_id.in_(owner_ids))
            else:
                allowed_set = {int(x) for x in (allowed_owner_ids or [])}
                if not all(oid in allowed_set for oid in owner_ids):
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "You do not have permission to access records for this owner",
                            "success": False,
                        },
                    )
                filters.append(Deal.deal_owner_id.in_(owner_ids))

    # 4. Count gate
    count = db.query(Deal.id).filter(*filters).count()
    if count == 0:
        raise HTTPException(
            status_code=404, detail="No deals found for the applied filters."
        )
    if count > 5000:
        raise HTTPException(
            status_code=403,
            detail=f"Your filter matches {count} records. Maximum allowed is 5000. Apply more specific filters.",
        )

    # 5. Fetch rows — ALL columns except payment_receipt and sanction_letter
    rows = (
        db.query(
            Deal.id,
            Deal.account_id,
            Deal.account_name,
            Deal.ticket_id,
            Deal.ticket_number,
            Deal.deal_type,
            Deal.loan_type,
            Deal.type_of_login,
            Deal.type_of_case_login,
            Deal.ticket_login,
            Deal.deal_stage,
            Deal.deal_status,
            Deal.disbursed_amount,
            Deal.sanction_amount,
            Deal.approved_amount,
            Deal.amount_required,
            Deal.processing_fees,
            Deal.mm_charges,
            Deal.insurance_amount,
            Deal.pf_percentage,
            Deal.rate_of_interest,
            Deal.interest_type,
            Deal.deal_call_back_datetime,
            Deal.disbursement_date,
            Deal.lender_login_date,
            Deal.loan_start_date,
            Deal.loan_end_date,
            Deal.targeted_disbursement_date,
            Deal.tenure,
            Deal.lender_code,
            Deal.lender_name,
            Deal.customer_rejection_reason,
            Deal.customer_rejection_status_explanation,
            Deal.lender_rejection_reason,
            Deal.lender_rejection_status_explanation,
            Deal.potential,
            Deal.product,
            Deal.assignee_id,
            Deal.created_by,
            Deal.modified_by,
            Deal.deal_owner_id,
            Deal.crm_deal_id,
            Deal.created_at,
            Deal.updated_at,
        )
        .filter(*filters)
        .all()
    )

    # 6. Stream
    filename = f"deals_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "Account ID",
                "Account Name",
                "Ticket ID",
                "Ticket Number",
                "Deal Type",
                "Loan Type",
                "Type of Login",
                "Type of Case Login",
                "Ticket Login",
                "Case Stage",
                "Case Status",
                "Disbursed Amount",
                "Sanction Amount",
                "Approved Amount",
                "Amount Required",
                "Processing Fees",
                "MM Charges",
                "Insurance Amount",
                "PF Percentage",
                "Rate of Interest",
                "Interest Type",
                "Deal Callback Date",
                "Disbursement Date",
                "Lender Login Date",
                "Loan Start Date",
                "Loan End Date",
                "Targeted Disbursement Date",
                "Tenure",
                "Lender Code",
                "Lender Name",
                "Customer Rejection Reason",
                "Customer Rejection Explanation",
                "Lender Rejection Reason",
                "Lender Rejection Explanation",
                "Potential",
                "Product",
                "Assignee ID",
                "Created By",
                "Modified By",
                "Deal Owner ID",
                "CRM Deal ID",
                "Created At",
                "Updated At",
            ]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for row in rows:
            writer.writerow(
                [
                    str(row.id) if row.id else "",
                    str(row.account_id) if row.account_id else "",
                    row.account_name or "",
                    str(row.ticket_id) if row.ticket_id else "",
                    str(row.ticket_number) if row.ticket_number else "",
                    row.deal_type or "",
                    row.loan_type or "",
                    row.type_of_login or "",
                    row.type_of_case_login or "",
                    row.ticket_login or "",
                    row.case_stage or "",
                    row.case_status or "",
                    str(row.disbursed_amount)
                    if row.disbursed_amount is not None
                    else "",
                    str(row.sanction_amount) if row.sanction_amount is not None else "",
                    str(row.approved_amount) if row.approved_amount is not None else "",
                    str(row.amount_required) if row.amount_required is not None else "",
                    str(row.processing_fees) if row.processing_fees is not None else "",
                    str(row.mm_charges) if row.mm_charges is not None else "",
                    str(row.insurance_amount)
                    if row.insurance_amount is not None
                    else "",
                    str(row.pf_percentage) if row.pf_percentage is not None else "",
                    str(row.rate_of_interest)
                    if row.rate_of_interest is not None
                    else "",
                    row.interest_type or "",
                    row.deal_call_back_datetime.strftime("%Y-%m-%d")
                    if row.deal_call_back_datetime
                    else "",
                    row.disbursement_date.strftime("%Y-%m-%d")
                    if row.disbursement_date
                    else "",
                    row.lender_login_date.strftime("%Y-%m-%d")
                    if row.lender_login_date
                    else "",
                    row.loan_start_date.strftime("%Y-%m-%d")
                    if row.loan_start_date
                    else "",
                    row.loan_end_date.strftime("%Y-%m-%d") if row.loan_end_date else "",
                    row.targeted_disbursement_date.strftime("%Y-%m-%d")
                    if row.targeted_disbursement_date
                    else "",
                    str(row.tenure) if row.tenure is not None else "",
                    row.lender_code or "",
                    row.lender_name or "",
                    row.customer_rejection_reason or "",
                    row.customer_rejection_status_explanation or "",
                    row.lender_rejection_reason or "",
                    row.lender_rejection_status_explanation or "",
                    row.potential or "",
                    row.product or "",
                    str(row.assignee_id) if row.assignee_id else "",
                    str(row.created_by) if row.created_by else "",
                    str(row.modified_by) if row.modified_by else "",
                    str(row.deal_owner_id) if row.deal_owner_id else "",
                    str(row.crm_deal_id) if row.crm_deal_id else "",
                    row.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if row.created_at
                    else "",
                    row.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                    if row.updated_at
                    else "",
                ]
            )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    # BackgroundThreadPool.execute_task(
    #     intimate_user_via_mail,
    #     to="prathap@r1xchange.com",
    #     body=f"""
    #         <p>Dear Super Admin,</p>
    #
    #         <p>This is an automated notification to inform you that a <strong>data export</strong> has been initiated on the system. Please find the details below:</p>
    #
    #         <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
    #             <tr>
    #                 <td style="padding: 8px; border: 1px solid #ddd;"><strong>Module</strong></td>
    #                 <td style="padding: 8px; border: 1px solid #ddd;">{"deals"}</td>
    #             </tr>
    #             <tr>
    #                 <td style="padding: 8px; border: 1px solid #ddd;"><strong>Role</strong></td>
    #                 <td style="padding: 8px; border: 1px solid #ddd;">{role}</td>
    #             </tr>
    #              <tr>
    #                 <td style="padding: 8px; border: 1px solid #ddd;"><strong>user_id</strong></td>
    #                 <td style="padding: 8px; border: 1px solid #ddd;">{user_id}</td>
    #             </tr>
    #             <tr>
    #                 <td style="padding: 8px; border: 1px solid #ddd;"><strong>Date & Time</strong></td>
    #                 <td style="padding: 8px; border: 1px solid #ddd;">{datetime.now().strftime("%d %b %Y, %I:%M %p")}
    #  }}</td>
    #             </tr>
    #
    #         </table>
    #
    #         <p>If this activity was expected and authorized, no action is required. However, if this export appears suspicious or unauthorized, please review the activity immediately and take appropriate action.</p>
    #
    #         <p>For audit purposes, this event has been logged in the system.</p>
    #
    #         <br/>
    #         <p>Regards,</p>
    #         <p><strong>System Notification Service</strong></p>
    #         <p style="color: gray; font-size: 12px;">This is an automated message. Please do not reply to this email.</p>
    #     """,
    #     subject="[Data Export Alert] Deals Data Export Initiated – Action Log Notification",
    # )
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# def intimate_user_via_mail(to: str, body: str, subject: str):
#     try:
#         send_general_email(to, subject, body)
#         print("Email sent successfully")
#     except Exception as e:
#         print(e)
