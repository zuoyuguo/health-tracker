import datetime
import anthropic
import config
from analysis.prompts import build_daily_prompt
from db.models import Meal, Sleep, Activity, BodyMetric


def collect_daily_data(session, date: datetime.date) -> dict:
    start = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end = datetime.datetime.combine(date, datetime.time.max, tzinfo=datetime.timezone.utc)
    yesterday = date - datetime.timedelta(days=1)

    meal_rows = session.query(Meal).filter(
        Meal.confirmed == True,
        Meal.recorded_at >= start,
        Meal.recorded_at <= end,
    ).order_by(Meal.recorded_at).all()

    sleep_row = session.query(Sleep).filter_by(sleep_date=yesterday).first()

    activity_rows = session.query(Activity).filter_by(activity_date=date).all()

    metric_row = session.query(BodyMetric).filter(
        BodyMetric.measured_at <= end,
    ).order_by(BodyMetric.measured_at.desc()).first()

    return {
        "meals": [_meal_to_dict(m) for m in meal_rows],
        "sleep": _sleep_to_dict(sleep_row),
        "activities": [_activity_to_dict(a) for a in activity_rows],
        "body_metric": _body_metric_to_dict(metric_row),
    }


def has_data(data: dict) -> bool:
    return bool(data["meals"] or data["activities"])


def generate_daily_report(session, date: datetime.date) -> str | None:
    data = collect_daily_data(session, date)
    if not has_data(data):
        return None

    prompt = build_daily_prompt(
        data["meals"],
        data["sleep"],
        data["activities"],
        data["body_metric"],
    )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _meal_to_dict(meal) -> dict:
    return {
        "meal_type": meal.meal_type,
        "recorded_at": meal.recorded_at,
        "total_calories": float(meal.total_calories or 0),
        "protein_g": float(meal.protein_g or 0),
        "carbs_g": float(meal.carbs_g or 0),
        "fat_g": float(meal.fat_g or 0),
        "foods": meal.foods or [],
    }


def _sleep_to_dict(sleep) -> dict | None:
    if sleep is None:
        return None
    return {
        "total_sleep_min": sleep.total_sleep_min,
        "deep_sleep_min": sleep.deep_sleep_min,
        "rem_sleep_min": sleep.rem_sleep_min,
        "sleep_score": sleep.sleep_score,
        "resting_hr": sleep.resting_hr,
        "hrv_avg": float(sleep.hrv_avg) if sleep.hrv_avg is not None else None,
    }


def _activity_to_dict(activity) -> dict:
    return {
        "activity_type": activity.activity_type,
        "duration_min": activity.duration_min,
        "calories_burned": float(activity.calories_burned or 0),
        "avg_hr": activity.avg_hr,
    }


def _body_metric_to_dict(metric) -> dict | None:
    if metric is None:
        return None
    return {
        "measured_at": metric.measured_at,
        "weight_kg": float(metric.weight_kg) if metric.weight_kg is not None else None,
        "body_fat_pct": float(metric.body_fat_pct) if metric.body_fat_pct is not None else None,
        "bmi": float(metric.bmi) if metric.bmi is not None else None,
    }
