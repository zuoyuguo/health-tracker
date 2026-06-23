import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from db.base import SessionLocal
from garmin.client import GarminClient
from garmin.sync import fetch_yesterday_sleep, fetch_yesterday_activities, parse_sleep, parse_activity
from garmin.db_sync import upsert_sleep, insert_activities
from notifications.telegram import send_alert

logger = logging.getLogger(__name__)

_consecutive_failures = 0


def garmin_sync_job() -> None:
    global _consecutive_failures
    try:
        client = GarminClient()
        client.connect()

        with SessionLocal() as session:
            raw_sleep = fetch_yesterday_sleep(client.garmin)
            parsed_sleep = parse_sleep(raw_sleep)
            if parsed_sleep.get("sleep_date"):
                upsert_sleep(session, parsed_sleep)

            raw_activities = fetch_yesterday_activities(client.garmin)
            parsed_activities = [parse_activity(a) for a in raw_activities]
            count = insert_activities(session, parsed_activities)
            session.commit()

        _consecutive_failures = 0
        logger.info("Garmin sync complete. Activities inserted: %d", count)

    except Exception as exc:
        _consecutive_failures += 1
        logger.error("Garmin sync failed (attempt %d): %s", _consecutive_failures, exc)
        if _consecutive_failures >= 3:
            send_alert(f"Garmin sync failed {_consecutive_failures} times in a row: {exc}")


def create_scheduler() -> BackgroundScheduler:
    tz = pytz.timezone("Asia/Shanghai")
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(garmin_sync_job, "cron", hour=9, minute=0)
    return scheduler
