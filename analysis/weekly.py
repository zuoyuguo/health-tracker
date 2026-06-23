import datetime
import pytz
import anthropic
import config
from analysis.prompts import build_weekly_prompt
from analysis.daily import _meal_to_dict, _sleep_to_dict, _activity_to_dict, _body_metric_to_dict
from db.models import Meal, Sleep, Activity, BodyMetric


def collect_weekly_data(session, week_end: datetime.date) -> list[dict]:
    week_start = week_end - datetime.timedelta(days=6)
    result = []
    local_tz = pytz.timezone(config.TIMEZONE)
    for i in range(7):
        date = week_start + datetime.timedelta(days=i)
        start_dt = local_tz.localize(datetime.datetime.combine(date, datetime.time.min))
        end_dt = local_tz.localize(datetime.datetime.combine(date, datetime.time.max))
        yesterday = date - datetime.timedelta(days=1)

        meal_rows = (
            session.query(Meal)
            .filter(
                Meal.confirmed == True,
                Meal.recorded_at >= start_dt,
                Meal.recorded_at <= end_dt,
            )
            .order_by(Meal.recorded_at)
            .all()
        )

        sleep_row = session.query(Sleep).filter_by(sleep_date=yesterday).first()

        activity_rows = session.query(Activity).filter_by(activity_date=date).all()

        metric_rows = (
            session.query(BodyMetric)
            .filter(
                BodyMetric.measured_at >= start_dt,
                BodyMetric.measured_at <= end_dt,
            )
            .order_by(BodyMetric.measured_at)
            .all()
        )

        result.append({
            "date": date,
            "meals": [_meal_to_dict(m) for m in meal_rows],
            "sleep": _sleep_to_dict(sleep_row),
            "activities": [_activity_to_dict(a) for a in activity_rows],
            "body_metrics": [_body_metric_to_dict(bm) for bm in metric_rows],
        })

    return result


def has_weekly_data(daily_data: list[dict]) -> bool:
    return any(entry["meals"] or entry["activities"] for entry in daily_data)


def generate_weekly_report(session, week_end: datetime.date) -> str | None:
    daily_data = collect_weekly_data(session, week_end)
    if not has_weekly_data(daily_data):
        return None

    prompt = build_weekly_prompt(daily_data)
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
