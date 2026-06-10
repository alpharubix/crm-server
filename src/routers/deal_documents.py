from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.controllers.auth import MANAGERID
from src.database import get_db
from src.models.deal import Deal
from src.models.deal_document import DealDocument
from src.models.user import User

deal_docs_router = APIRouter(
    prefix="/deals/{deal_id}/documents", tags=["deal-documents"]
)


def format_doc(d: DealDocument) -> dict:
    return {
        "id": str(d.id),
        "deal_id": str(d.deal_id),
        "module": d.module,
        "description": d.description,
        "from_date": d.from_date,
        "to_date": d.to_date,
        "status": d.status,
        "link": d.link,
        "created_by": str(d.created_by) if d.created_by is not None else None,
        "modified_by": str(d.modified_by) if d.modified_by is not None else None,
        "created_at": d.created_at.isoformat() if d.created_at is not None else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at is not None else None,
    }


# def process_document_notifications(
#     doc: DealDocument, db: Session, trigger_user_role: str
# ):
#     """
#     Evaluates whether the document status changes hit our operational trigger conditions
#     and dispatches non-blocking async background tasks safely.
#     """
#     try:
#         # Fetch root deal to extract account context and assignees
#         deal_record = db.query(Deal).filter(Deal.id == int(doc.deal_id)).first()
#         if not deal_record:
#             return

#         # Core operational banking emails from your sheet matrix
#         banking_team_emails = [
#             "suraj.gupta@r1xchange.com",
#             "myisa.beiucy@r1xchange.com",
#         ]
        

#         # Pull deal owner and their respective supervisor mapping profiles
#         deal_owner_email = None
#         manager_email = None

#         if deal_record.deal_owner_id:
#             deal_owner = (
#                 db.query(User).filter(User.id == int(deal_record.deal_owner_id)).first()
#             )
#             if deal_owner:
#                 deal_owner_email = deal_owner.email

#                 reporting_manager_id = None
#                 for mgr_id, executive_ids in MANAGERID().MANAGER_EXECUTIVES_MAP.items():
#                     if deal_owner.id in executive_ids:
#                         reporting_manager_id = mgr_id
#                         break

#                 if reporting_manager_id:
#                     manager_user = (
#                         db.query(User)
#                         .filter(User.id == int(reporting_manager_id))
#                         .first()
#                     )
#                     if manager_user and manager_user.email:
#                         manager_email = manager_user.email

#         # from src.controllers.Background_threads import BackgroundThreadPool

#         # current_status = str(doc.status).strip().lower()

#         # WORKFLOW CONDITION 1: Status updated to 'Completed' (Document Submitted)
#         # if current_status == "completed":
#         #     recipients = list(
#         #         set([email for email in banking_team_emails + [manager_email] if email])
#         #     )
#         #     if recipients:
#                 # from src.controllers.mail import notify_document_submitted
#                 #
#                 # BackgroundThreadPool.execute_task(
#                 #     notify_document_submitted,
#                 #     recipients,
#                 #     deal_record.account_name or "Unknown Deal",
#                 #     doc.module,
#                 #     doc.id,
#                 # )

#         # WORKFLOW CONDITION 2: Status updated to 'Pending' (Document Required)
#         # elif current_status == "pending":
#         #     recipients = list(
#         #         set([email for email in [deal_owner_email, manager_email] if email])
#         #     )
#         #     if recipients:
#                 # from src.controllers.mail import notify_document_required
#                 #
#                 # BackgroundThreadPool.execute_task(
#                 #     notify_document_required,
#                 #     recipients,
#                 #     deal_record.account_name or "Unknown Deal",
#                 #     doc.module,
#                 #     doc.id,
#                 # )
#     except Exception as err:
#         print(f"Warning: Deal document notification processing skipped: {err}")


@deal_docs_router.get("")
@deal_docs_router.get("/")
def get_documents(deal_id: int, db: Session = Depends(get_db)):
    docs = db.query(DealDocument).filter(DealDocument.deal_id == deal_id).all()
    return {"data": [format_doc(d) for d in docs]}


@deal_docs_router.post("")
@deal_docs_router.post("/")
async def create_document(
    deal_id: int, request: Request, db: Session = Depends(get_db)
):
    body = await request.json()
    sanitized_body = {k: (v if v != "" else None) for k, v in body.items()}

    user_id = request.state.user_id
    user_role = request.state.role

    doc = DealDocument(
        deal_id=deal_id,
        module=body.get("module"),
        description=body.get("description"),
        from_date=sanitized_body.get("from_date"),
        to_date=sanitized_body.get("to_date"),
        status=body.get("status"),
        link=body.get("link"),
        created_by=user_id,
        modified_by=user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Evaluate notification rules instantly on creation
    # process_document_notifications(doc, db, user_role)

    return format_doc(doc)


@deal_docs_router.put("/{doc_id}")
@deal_docs_router.patch("/{doc_id}")
async def update_document(
    deal_id: int, doc_id: int, request: Request, db: Session = Depends(get_db)
):
    doc = (
        db.query(DealDocument)
        .filter(
            DealDocument.id == doc_id,
            DealDocument.deal_id == deal_id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    body = await request.json()

    # Track old status to avoid firing duplicate tracking emails on secondary row attribute edits
    old_status = doc.status

    for key in ("module", "description", "from_date", "to_date", "status", "link"):
        if key in body:
            setattr(doc, key, body[key])

    user_role = request.state.role
    doc.modified_by = request.state.user_id
    doc.updated_at = datetime.now(timezone.utc)  # type: ignore

    db.commit()
    db.refresh(doc)

    # Trigger evaluation only if the status state is explicitly updated
    # if (
    #     body.get("status") is not None
    #     and str(body.get("status")).strip().lower() != str(old_status).strip().lower()
    # ):
        # process_document_notifications(doc, db, user_role)

    return format_doc(doc)


# @deal_docs_router.delete("/{doc_id}")
# def delete_document(deal_id: int, doc_id: int, db: Session = Depends(get_db)):
#     doc = (
#         db.query(DealDocument)
#         .filter(
#             DealDocument.id == doc_id,
#             DealDocument.deal_id == deal_id,
#         )
#         .first()
#     )
#     if not doc:
#         raise HTTPException(status_code=404, detail="Document not found")
#     db.delete(doc)
#     db.commit()
#     return {"message": "deleted"}
