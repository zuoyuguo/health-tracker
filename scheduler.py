import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from db.base import SessionLocal
from garmin.client import GarminClient
from garmin.sync import fetch_yesterday_sleep, fetch_yesterday_activities, parse_sleep, parse_activity
from garmin.db_sync import upsert_sleep, insert_activities
from renpho.client import RenphoClientWrapper
from renpho.sync import fetch_recent_measurements, parse_measurement
from renpho.db_sync import insert_body_metrics
from notifications.telegram import send_alert

logger = logging.getLogger(__name__)

_garmin_consecutive_failures = 0
_renpho_consecutive_failures = 0


def garmin_sync_job() -> None:
    global _garmin_consecutive_failures
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

        _garmin_consecutive_failures = 0
        logger.info("Garmin sync complete. Activities inserted: %d", count)

    except Exception as exc:
        _garmin_consecutive_failures += 1
        logger.error("Garmin sync failed (attempt %d): %s", _garmin_consecutive_failures, exc)
        if _garmin_consecutive_failures == 3:
            send_alert(f"⚠️ Garmin 同步连续失败 {_garmin_consecutive_failures} 次：{exc}")


def renpho_sync_job() -> None:
    global _renpho_consecutive_failures
    try:
        wrapper = RenphoClientWrapper()
        wrapper.connect()

        with SessionLocal() as session:
            raw_list = fetch_recent_measurements(wrapper.client)
            parsed_list = [parse_measurement(m) for m in raw_list]
            count = insert_body_metrics(session, parsed_list)
            session.commit()

        _renpho_consecutive_failures = 0
        logger.info("Renpho sync complete. Body metrics inserted: %d", count)

    except Exception as exc:
        _renpho_consecutive_failures += 1
        logger.error("Renpho sync failed (attempt %d): %s", _renpho_consecutive_failures, exc)
        if _renpho_consecutive_failures == 3:
            send_alert(f"⚠️ Renpho 同步连续失败 {_renpho_consecutive_failures} 次：{exc}")


def create_scheduler() -> BackgroundScheduler:
    tz = pytz.timezone("Asia/Shanghai")
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(garmin_sync_job, "cron", hour=9, minute=0, max_instances=1)
    scheduler.add_job(renpho_sync_job, "cron", hour=9, minute=0, max_instances=1)
    return scheduler
