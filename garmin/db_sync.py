import datetime
from db.models import Sleep, Activity


def _to_date(value) -> datetime.date | None:
    if value is None:
        return None
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def _to_datetime(value) -> datetime.datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(str(value))


def upsert_sleep(session, parsed: dict) -> None:
    sleep_date = _to_date(parsed.get("sleep_date"))
    existing = session.query(Sleep).filter_by(sleep_date=sleep_date).first()
    fields = {
        "sleep_date": sleep_date,
        "total_sleep_min": parsed.get("total_sleep_min"),
        "deep_sleep_min": parsed.get("deep_sleep_min"),
        "light_sleep_min": parsed.get("light_sleep_min"),
        "rem_sleep_min": parsed.get("rem_sleep_min"),
        "awake_min": parsed.get("awake_min"),
        "sleep_score": parsed.get("sleep_score"),
        "hrv_avg": parsed.get("hrv_avg"),
        "resting_hr": parsed.get("resting_hr"),
        "sleep_start": _to_datetime(parsed.get("sleep_start")),
        "sleep_end": _to_datetime(parsed.get("sleep_end")),
    }
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        session.add(Sleep(**fields))


def insert_activities(session, parsed_list: list[dict]) -> int:
    inserted = 0
    for parsed in parsed_list:
        gid = parsed.get("garmin_activity_id")
        if gid is not None:
            exists = session.query(Activity).filter_by(
                garmin_activity_id=gid
            ).first()
            if exists:
                continue
        session.add(Activity(
            garmin_activity_id=gid,
            activity_type=parsed.get("activity_type"),
            activity_date=_to_date(parsed.get("activity_date")),
            duration_min=parsed.get("duration_min"),
            calories_burned=parsed.get("calories_burned"),
            avg_hr=parsed.get("avg_hr"),
            max_hr=parsed.get("max_hr"),
            steps=parsed.get("steps"),
            distance_km=parsed.get("distance_km"),
            hr_zone_1_min=parsed.get("hr_zone_1_min"),
            hr_zone_2_min=parsed.get("hr_zone_2_min"),
            hr_zone_3_min=parsed.get("hr_zone_3_min"),
            hr_zone_4_min=parsed.get("hr_zone_4_min"),
            hr_zone_5_min=parsed.get("hr_zone_5_min"),
        ))
        inserted += 1
    return inserted
