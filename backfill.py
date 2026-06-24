"""
历史数据回填脚本
用法: python backfill.py --days 30
"""
import argparse
import datetime
import logging
import pytz

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def backfill_garmin(days: int) -> None:
    import config
    from garmin.client import GarminClient
    from garmin.sync import parse_sleep, parse_activity
    from garmin.db_sync import upsert_sleep, insert_activities
    from db.base import SessionLocal

    logger.info("开始同步 Garmin 过去 %d 天数据...", days)
    client = GarminClient()
    client.connect()

    local_tz = pytz.timezone(config.TIMEZONE)
    today = datetime.datetime.now(local_tz).date()
    sleep_ok = 0
    activity_ok = 0

    for i in range(1, days + 1):
        target_date = (today - datetime.timedelta(days=i)).isoformat()
        try:
            # 睡眠 + HRV
            raw_sleep = client.garmin.get_sleep_data(target_date)
            raw_hrv = client.garmin.get_hrv_data(target_date)
            raw_sleep["hrv_summary"] = raw_hrv.get("hrvSummary", {})
            parsed_sleep = parse_sleep(raw_sleep)
            if parsed_sleep.get("sleep_date"):
                with SessionLocal() as session:
                    upsert_sleep(session, parsed_sleep)
                    session.commit()
                sleep_ok += 1

            # 运动
            raw_activities = client.garmin.get_activities_by_date(target_date, target_date)
            parsed_activities = [parse_activity(a) for a in raw_activities]
            with SessionLocal() as session:
                count = insert_activities(session, parsed_activities)
                session.commit()
            activity_ok += count

            logger.info("✓ %s  睡眠=%s  运动=%d条", target_date,
                        "有" if parsed_sleep.get("sleep_date") else "无", len(parsed_activities))
        except Exception as e:
            logger.warning("✗ %s 失败: %s", target_date, e)

    logger.info("Garmin 完成：睡眠 %d 天，运动 %d 条", sleep_ok, activity_ok)


def backfill_renpho(days: int) -> None:
    from renpho_sync.client import RenphoClientWrapper
    from renpho_sync.sync import fetch_recent_measurements, parse_measurement
    from renpho_sync.db_sync import insert_body_metrics
    from db.base import SessionLocal

    logger.info("开始同步 Renpho 过去 %d 天数据...", days)
    wrapper = RenphoClientWrapper()
    wrapper.connect()

    raw_list = fetch_recent_measurements(wrapper.client, days=days)
    parsed_list = [parse_measurement(m) for m in raw_list]

    with SessionLocal() as session:
        count = insert_body_metrics(session, parsed_list)
        session.commit()

    logger.info("Renpho 完成：新增 %d 条体重记录（共获取 %d 条）", count, len(parsed_list))


def main():
    parser = argparse.ArgumentParser(description="历史数据回填")
    parser.add_argument("--days", type=int, default=30, help="回填天数（默认30）")
    parser.add_argument("--source", choices=["garmin", "renpho", "all"], default="all",
                        help="数据源（默认all）")
    args = parser.parse_args()

    if args.source in ("garmin", "all"):
        backfill_garmin(args.days)

    if args.source in ("renpho", "all"):
        backfill_renpho(args.days)

    logger.info("回填完成！")


if __name__ == "__main__":
    main()
