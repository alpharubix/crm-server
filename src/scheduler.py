import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.controllers.tele_crm import scheduled_sync_yesterday_telecrm_leads

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

scheduler = BackgroundScheduler(timezone=IST)


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            scheduled_sync_yesterday_telecrm_leads,
            trigger=CronTrigger(hour=2, minute=0, timezone=IST),
            id="sync_yesterday_telecrm_leads_job",
            name="Sync yesterday TeleCRM leads",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            "APScheduler started: 'sync_yesterday_telecrm_leads_job' scheduled daily at 2:00 AM IST."
        )


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
