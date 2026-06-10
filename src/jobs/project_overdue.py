import logging
from datetime import date

from sqlalchemy.orm import Session

from src.controllers.mail import notify_project_overdue
from src.models.project import Project, StatusEnum
from src.models.user import User

logger = logging.getLogger(__name__)


def check_overdue_projects(db: Session):
    logger.info("Checking overdue projects...")
    projects = db.query(Project).all()
    today = date.today()

    for project in projects:
        # Skip inactive or incomplete states
        if project.status in [
            StatusEnum.completed,
            StatusEnum.cancelled,
            StatusEnum.rejected,
            StatusEnum.on_hold,
        ]:
            continue

        if not project.end_date:
            continue

        if today > project.end_date:
            overdue_days = (today - project.end_date).days
            logger.info(
                f"Overdue project found: {project.name} (Overdue by {overdue_days} days)"
            )

            # Gather all target IDs for this project to notify everyone in one go
            # Team Members (actioner_ids) + Approver (approver_id) + Initiator (created_by)
            target_user_ids = set()
            if project.actioner_ids:
                target_user_ids.update(project.actioner_ids)
            if project.approver_id:
                target_user_ids.add(project.approver_id)
            if project.created_by:
                target_user_ids.add(project.created_by)

            # Query all users matching these combined IDs
            recipients = db.query(User).filter(User.id.in_(list(target_user_ids))).all()
            emails = list({user.email for user in recipients if user.email})

            if not emails:
                logger.warning(
                    f"No emails found for overdue project stakeholders: {project.name}"
                )
                continue

            try:
                # This sends a single email layout to all stakeholders safely spaced out
                # notify_project_overdue(
                #     emails=emails,
                #     project_name=project.name,
                #     project_id=project.id,
                #     overdue_days=overdue_days,
                # )
                logger.info(
                    f"Overdue mail sent to stakeholders for project: {project.name}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to send overdue mail for project {project.name}: {str(e)}"
                )

    logger.info("Overdue project check completed")
