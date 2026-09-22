import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from pymongo import UpdateOne
from pymongo.database import Database

from src.config import settings
from src.database import monogodb

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def _sync_telecrm_leads_with_payload(
    payload: dict,
    mongo_db: Database | None = None,
) -> dict:
    if mongo_db is None:
        mongo_db = monogodb["crm_dev"]

    collection = mongo_db["tele-crm-calls"]

    limit = 100
    skip = 0
    total_count = 0
    total_upserted = 0
    total_modified = 0

    headers = {
        "Authorization": f"Bearer {settings.TELECRM_TOKEN}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60.0) as client:
        while True:
            response = client.post(
                settings.TELECRM_URL,
                params={
                    "skip": skip,
                    "limit": limit,
                },
                json=payload,
                headers=headers,
            )

            if response.status_code != 200:
                raise Exception(
                    f"TeleCRM API returned {response.status_code}: {response.text}"
                )

            result = response.json()

            leads = result.get("data", [])
            total_count = result.get("total_count", 0)

            if not leads:
                break

            operations = []

            for lead in leads:
                # Only use phone to identify the MongoDB document
                phone = lead.get("fields", {}).get("phone")

                if not phone:
                    continue

                now = datetime.now(UTC)

                operations.append(
                    UpdateOne(
                        {"phone": phone},
                        {
                            # Store the COMPLETE TeleCRM response
                            "$set": {
                                "phone": phone,
                                "data": lead,
                                "updated_at": now,
                            },
                            "$setOnInsert": {
                                "created_at": now,
                            },
                        },
                        upsert=True,
                    )
                )

            if operations:
                bulk_result = collection.bulk_write(
                    operations,
                    ordered=False,
                )

                total_upserted += bulk_result.upserted_count
                total_modified += bulk_result.modified_count

            skip += limit

            print(f"TeleCRM sync: {min(skip, total_count)}/{total_count}")

            if skip >= total_count:
                break

    return {
        "success": True,
        "total_count": total_count,
        "upserted": total_upserted,
        "modified": total_modified,
    }


def sync_all_telecrm_leads(mongo_db: Database | None = None) -> dict:
    return _sync_telecrm_leads_with_payload(payload={"fields": {}}, mongo_db=mongo_db)


def get_yesterday_date_range(target_date: date | None = None) -> tuple[str, str]:
    if target_date is None:
        target_date = (datetime.now(IST) - timedelta(days=1)).date()

    from_date_str = target_date.strftime("%d/%m/%Y 00:00:00")
    to_date_str = target_date.strftime("%d/%m/%Y 23:59:59")
    return from_date_str, to_date_str


def sync_yesterday_telecrm_leads(
    target_date: date | None = None,
    mongo_db: Database | None = None,
) -> dict:
    from_date_str, to_date_str = get_yesterday_date_range(target_date)

    payload = {
        "actions": {
            "type": [
                "INCOMING_CALL",
                "OUTGOING_CALL",
                "MISSED_CALL",
                "CALL_ACTION",
            ],
            "performed_at": {
                "from": from_date_str,
                "to": to_date_str,
            },
        }
    }

    result = _sync_telecrm_leads_with_payload(payload=payload, mongo_db=mongo_db)
    result["performed_at"] = {"from": from_date_str, "to": to_date_str}
    return result


def scheduled_sync_yesterday_telecrm_leads():
    logger.info("Starting scheduled TeleCRM leads sync for yesterday...")
    try:
        result = sync_yesterday_telecrm_leads()
        logger.info(
            "Completed scheduled TeleCRM leads sync: %s",
            result,
        )
        return result
    except Exception as e:
        logger.exception("Error during scheduled TeleCRM leads sync: %s", e)
