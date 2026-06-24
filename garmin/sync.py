import datetime
import pytz
import config


def _yesterday_local() -> str:
    tz = pytz.timezone(config.TIMEZONE)
    return (datetime.datetime.now(tz).date() - datetime.timedelta(days=1)).isoformat()


def fetch_yesterday_sleep(garmin) -> dict:
    return garmin.get_sleep_data(_yesterday_local())


def fetch_yesterday_activities(garmin) -> list[dict]:
    yesterday = _yesterday_local()
    return garmin.get_activities_by_date(yesterday, yesterday)


def parse_sleep(raw: dict) -> dict:
    dto = raw.get("dailySleepDTO", {})
    scores = dto.get("sleepScores", {})
    overall = scores.get("overall", {}) if isinstance(scores, dict) else {}

    def ms_to_iso(ms):
        if ms is None:
            return None
        return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc).isoformat()

    return {
        "sleep_date": dto.get("calendarDate") or dto.get("sleepDate"),
        "total_sleep_min": _sec_to_min(dto.get("sleepTimeSeconds")),
        "deep_sleep_min": _sec_to_min(dto.get("deepSleepSeconds")),
        "light_sleep_min": _sec_to_min(dto.get("lightSleepSeconds")),
        "rem_sleep_min": _sec_to_min(dto.get("remSleepSeconds")),
        "awake_min": _sec_to_min(dto.get("awakeSleepSeconds")),
        "sleep_score": overall.get("value") if overall else None,
        "resting_hr": raw.get("restingHeartRate"),
        "sleep_start": ms_to_iso(dto.get("sleepStartTimestampGMT")),
        "sleep_end": ms_to_iso(dto.get("sleepEndTimestampGMT")),
    }


def parse_activity(raw: dict) -> dict:
    zones = raw.get("hrTimeInZone")

    def zone_min(i):
        if not zones or len(zones) <= i:
            return None
        return round(zones[i] / 60)

    distance_m = raw.get("distance")
    duration_s = raw.get("duration")
    start = raw.get("startTimeLocal", "")
    activity_date = start[:10] if start else None

    return {
        "garmin_activity_id": raw.get("activityId"),
        "activity_type": (raw.get("activityType") or {}).get("typeKey"),
        "activity_date": activity_date,
        "duration_min": round(duration_s / 60) if duration_s is not None else None,
        "calories_burned": raw.get("calories"),
        "avg_hr": raw.get("averageHR"),
        "max_hr": raw.get("maxHR"),
        "steps": raw.get("steps"),
        "distance_km": round(distance_m / 1000, 3) if distance_m is not None else None,
        "hr_zone_1_min": zone_min(0),
        "hr_zone_2_min": zone_min(1),
        "hr_zone_3_min": zone_min(2),
        "hr_zone_4_min": zone_min(3),
        "hr_zone_5_min": zone_min(4),
    }


def _sec_to_min(seconds) -> int | None:
    if seconds is None:
        return None
    return round(seconds / 60)
