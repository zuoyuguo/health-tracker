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

    weight = raw.get("weight")
    bodyfat = raw.get("bodyfat")
    fat_mass = round(weight * bodyfat / 100, 2) if weight and bodyfat else None

    return {
        "renpho_record_id": renpho_record_id,
        "measured_at": measured_at,
        "weight_kg": weight,
        "bmi": raw.get("bmi"),
        "body_fat_pct": bodyfat,
        "fat_mass_kg": fat_mass,
        "lean_mass_kg": raw.get("fatFreeWeight"),
        "muscle_mass_kg": raw.get("muscle"),
        "bone_mass_kg": raw.get("bone"),
        "water_pct": raw.get("water"),
        "visceral_fat": raw.get("visfat"),
        "bmr_kcal": bmr_kcal,
    }
