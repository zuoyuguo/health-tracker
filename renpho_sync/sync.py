import datetime
from renpho import RenphoClient


def fetch_recent_measurements(client: RenphoClient, days: int = 7) -> list[dict]:
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    cutoff_ts = cutoff.timestamp()

    all_measurements = client.get_all_measurements()
    result = []
    for m in all_measurements:
        ts = m.get("timeStamp")
        if ts is None:
            continue
        ts_sec = ts / 1000 if ts > 1e12 else ts
        if ts_sec >= cutoff_ts:
            result.append(m)
    return result


def parse_measurement(raw: dict) -> dict:
    ts = raw.get("timeStamp", 0)
    ts_sec = ts / 1000 if ts > 1e12 else ts
    measured_at = datetime.datetime.fromtimestamp(ts_sec, tz=datetime.timezone.utc)

    record_id = raw.get("id") or raw.get("timeStamp", "")
    renpho_record_id = str(record_id)[:64]

    bmr_raw = raw.get("bmr")
    bmr_kcal = int(bmr_raw) if bmr_raw is not None else None

    _sinew = raw.get("sinew")

    return {
        "renpho_record_id": renpho_record_id,
        "measured_at": measured_at,
        "weight_kg": raw.get("weight"),
        "bmi": raw.get("bmi"),
        "body_fat_pct": raw.get("bodyfat"),
        "fat_mass_kg": raw.get("bodyfat_mass"),
        "lean_mass_kg": _sinew if _sinew is not None else raw.get("lbm"),
        "muscle_mass_kg": raw.get("muscle_mass"),
        "bone_mass_kg": raw.get("bone_mass"),
        "water_pct": raw.get("water"),
        "visceral_fat": raw.get("visfat"),
        "bmr_kcal": bmr_kcal,
    }
