import datetime
import logging
import pytz
import config
from apscheduler.schedulers.background import BackgroundScheduler
from db.base import SessionLocal
from garmin.client import GarminClient
from garmin.sync import fetch_yesterday_sleep, fetch_yesterday_hrv, fetch_yesterday_activities, parse_sleep, parse_activity
from garmin.db_sync import upsert_sleep, insert_activities
from renpho_sync.client import RenphoClientWrapper
from renpho_sync.sync import fetch_recent_measurements, parse_measurement
from renpho_sync.db_sync import insert_body_metrics
from analysis.daily import generate_daily_report
from analysis.weekly import generate_weekly_report
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
            raw_hrv = fetch_yesterday_hrv(client.garmin)
            raw_sleep["hrv_summary"] = raw_hrv.get("hrvSummary", {})
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


def daily_report_job() -> None:
    try:
        today = datetime.datetime.now(pytz.timezone(config.TIMEZONE)).date()
        with SessionLocal() as session:
            report = generate_daily_report(session, today)
        if report:
            send_alert(report)
        logger.info("Daily report job complete. Report sent: %s", bool(report))
    except Exception as exc:
        logger.error("Daily report job failed: %s", exc)
        send_alert(f"⚠️ 日报生成失败：{exc}")


def weekly_report_job() -> None:
    try:
        week_end = datetime.datetime.now(pytz.timezone(config.TIMEZONE)).date() - datetime.timedelta(days=1)
        with SessionLocal() as session:
            report = generate_weekly_report(session, week_end)
        if report:
            send_alert(report)
        logger.info("Weekly report job complete. Report sent: %s", bool(report))
    except Exception as exc:
        logger.error("Weekly report job failed: %s", exc)
        send_alert(f"⚠️ 周报生成失败：{exc}")


def create_scheduler() -> BackgroundScheduler:
    tz = pytz.timezone(config.TIMEZONE)
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(garmin_sync_job, "cron", hour=9, minute=0, max_instances=1)
    scheduler.add_job(renpho_sync_job, "cron", hour=9, minute=0, max_instances=1)
    scheduler.add_job(daily_report_job, "cron", hour=22, minute=0, max_instances=1)
    scheduler.add_job(weekly_report_job, "cron", day_of_week="mon", hour=8, minute=0, max_instances=1)
    return scheduler
