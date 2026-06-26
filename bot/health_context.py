import datetime
import pytz
from collections import Counter

import config
from db.models import Activity, BodyMetric, Meal, Sleep


def build_health_context(session, days: int = 7) -> str:
    local_tz = pytz.timezone(config.TIMEZONE)
    now_local = datetime.datetime.now(local_tz)
    cutoff_date = (now_local - datetime.timedelta(days=days)).date()
    cutoff_dt = local_tz.localize(
        datetime.datetime.combine(cutoff_date, datetime.time.min)
    )

    sections: list[str] = []

    # Sleep
    sleep_rows = (
        session.query(Sleep)
        .filter(Sleep.sleep_date >= cutoff_date)
        .all()
    )
    if sleep_rows:
        durations_h = [
            (r.total_sleep_min or 0) / 60 for r in sleep_rows
        ]
        avg_h = sum(durations_h) / len(durations_h)
        min_h = min(durations_h)
        max_h = max(durations_h)
        parts = [f"平均 {avg_h:.1f}h，范围 {min_h:.1f}-{max_h:.1f}h"]

        deep_rows = [r for r in sleep_rows if r.deep_sleep_min and r.total_sleep_min]
        if deep_rows:
            avg_deep_pct = (
                sum(r.deep_sleep_min / r.total_sleep_min for r in deep_rows)
                / len(deep_rows)
                * 100
            )
            parts.append(f"深睡均值 {avg_deep_pct:.0f}%")

        hrv_rows = [r for r in sleep_rows if r.hrv_avg is not None]
        if hrv_rows:
            avg_hrv = sum(float(r.hrv_avg) for r in hrv_rows) / len(hrv_rows)
            parts.append(f"HRV均值 {avg_hrv:.0f}ms（{len(hrv_rows)}天数据）")

        sections.append("睡眠：" + "，".join(parts))

    # Activity
    activity_rows = (
        session.query(Activity)
        .filter(Activity.activity_date >= cutoff_date)
        .all()
    )
    if activity_rows:
        type_counts = Counter(r.activity_type for r in activity_rows if r.activity_type)
        type_str = "、".join(
            f"{t}×{n}" for t, n in type_counts.most_common()
        )
        total_min = sum(r.duration_min or 0 for r in activity_rows)
        parts = [f"共 {len(activity_rows)} 次"]
        if type_str:
            parts.append(f"类型：{type_str}")
        if total_min:
            parts.append(f"总时长 {total_min}min")
        sections.append("运动：" + "，".join(parts))

    # Meals (confirmed only)
    meal_rows = (
        session.query(Meal)
        .filter(
            Meal.recorded_at >= cutoff_dt,
            Meal.confirmed.is_(True),
            Meal.total_calories.isnot(None),
        )
        .all()
    )
    if meal_rows:
        avg_cal = sum(float(m.total_calories) for m in meal_rows) / days
        parts = [f"平均 {avg_cal:.0f} kcal/天"]
        protein_rows = [m for m in meal_rows if m.protein_g is not None]
        if protein_rows:
            avg_prot = sum(float(m.protein_g) for m in protein_rows) / days
            parts.append(f"蛋白质均值 {avg_prot:.0f}g")
        sections.append("饮食：" + "，".join(parts))

    # Body metrics
    metric_rows = (
        session.query(BodyMetric)
        .filter(
            BodyMetric.measured_at >= cutoff_dt,
            BodyMetric.weight_kg.isnot(None),
        )
        .order_by(BodyMetric.measured_at)
        .all()
    )
    if metric_rows:
        first_w = float(metric_rows[0].weight_kg)
        last_w = float(metric_rows[-1].weight_kg)
        delta = last_w - first_w
        sign = "+" if delta >= 0 else ""
        sections.append(
            f"体重：{first_w:.1f}→{last_w:.1f} kg（{sign}{delta:.1f}kg）"
        )

    if not sections:
        return ""

    header = f"[用户健康数据摘要 - 过去{days}天]"
    return header + "\n" + "\n".join(sections)
