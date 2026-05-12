from datetime import date
import logging

from sqlalchemy.orm import Session

from src.models.project import Project, StatusEnum
from src.models.user import User
from src.controllers.mail import notify_project_overdue

logger = logging.getLogger(__name__)


def check_overdue_projects(db: Session):

    logger.info("Checking overdue projects...")

    projects = db.query(Project).all()

    for project in projects:

        # skip completed/cancelled/rejected/on_hold projects
        if project.status in [
            StatusEnum.completed,
            StatusEnum.cancelled,
            StatusEnum.rejected,
            StatusEnum.on_hold
        ]:
            continue

        # skip projects without end_date
        if not project.end_date:
            continue

        today = date.today()

        # overdue project
        if today > project.end_date:

            overdue_days = (today - project.end_date).days

            logger.info(
                f"Overdue project found: {project.name} "
                f"(Overdue by {overdue_days} days)"
            )

            actioners = db.query(User).filter(
                User.id.in_(project.actioner_ids)
            ).all()

            emails = [user.email for user in actioners if user.email]

            if not emails:
                logger.warning(
                    f"No emails found for project: {project.name}"
                )
                continue

            logger.info(f"Sending overdue mail to: {emails}")

            try:
                notify_project_overdue(
                    emails=emails,
                    project_name=project.name,
                    project_id=project.id,
                    overdue_days=overdue_days
                )

                logger.info(
                    f"Overdue mail sent successfully for project: {project.name}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to send overdue mail for "
                    f"project {project.name}: {str(e)}"
                )

    logger.info("Overdue project check completed")