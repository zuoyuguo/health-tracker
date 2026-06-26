import datetime
import pytz
from collections import Counter

import config
from db.models import Activity, BodyMetric, Meal, Sleep


def build_health_context(session, days: int = 7) -> str:
    local_tz = pytz.timezone(config.TIMEZONE)
    now_local = datetime.datetime.now(local_tz)
    today = now_local.date()
    cutoff_date = (now_local - datetime.timedelta(days=days)).date()
    cutoff_dt = local_tz.localize(
        datetime.datetime.combine(cutoff_date, datetime.time.min)
    )
    today_start = local_tz.localize(
        datetime.datetime.combine(today, datetime.time.min)
    )
    today_end = local_tz.localize(
        datetime.datetime.combine(today, datetime.time.max)
    )

    parts_today: list[str] = []
    sections_7d: list[str] = []

    # Today's meals
    today_meals = (
        session.query(Meal)
        .filter(
            Meal.recorded_at >= today_start,
            Meal.recorded_at <= today_end,
            Meal.confirmed.is_(True),
        )
        .order_by(Meal.recorded_at)
        .all()
    )
    if today_meals:
        meal_lines: list[str] = []
        for m in today_meals:
            time_str = m.recorded_at.astimezone(local_tz).strftime("%H:%M")
            if m.user_note and not m.foods:
                meal_lines.append(f"• {time_str} [{m.meal_type}] {m.user_note}")
            else:
                food_names = "、".join(f["name"] for f in (m.foods or []))
                cal_str = f" {float(m.total_calories):.0f} kcal" if m.total_calories else ""
                meal_lines.append(f"• {time_str} [{m.meal_type}] {food_names}{cal_str}")
        total_cal = sum(float(m.total_calories or 0) for m in today_meals)
        total_prot = sum(float(m.protein_g or 0) for m in today_meals)
        meal_lines.append(
            f"合计：{total_cal:.0f} kcal，蛋白质 {total_prot:.0f}g"
        )
        parts_today.append("饮食：\n" + "\n".join(meal_lines))

    # Today's activity
    today_activities = (
        session.query(Activity)
        .filter(Activity.activity_date == today)
        .all()
    )
    if today_activities:
        act_lines = []
        for a in today_activities:
            parts = []
            if a.activity_type:
                parts.append(a.activity_type)
            if a.duration_min:
                parts.append(f"{a.duration_min}min")
            if a.calories_burned:
                parts.append(f"{float(a.calories_burned):.0f} kcal")
            act_lines.append("• " + " ".join(parts))
        parts_today.append("运动：\n" + "\n".join(act_lines))

    # Sleep last night (sleep_date == today, covers previous night)
    last_sleep = (
        session.query(Sleep)
        .filter(Sleep.sleep_date == today)
        .first()
    )
    if last_sleep and last_sleep.total_sleep_min:
        h = last_sleep.total_sleep_min / 60
        sleep_parts = [f"{h:.1f}h"]
        if last_sleep.deep_sleep_min and last_sleep.total_sleep_min:
            deep_pct = last_sleep.deep_sleep_min / last_sleep.total_sleep_min * 100
            sleep_parts.append(f"深睡 {deep_pct:.0f}%")
        if last_sleep.hrv_avg:
            sleep_parts.append(f"HRV {float(last_sleep.hrv_avg):.0f}ms")
        parts_today.append("睡眠（昨晚）：" + "，".join(sleep_parts))

    # 7-day averages
    sleep_rows = (
        session.query(Sleep)
        .filter(Sleep.sleep_date >= cutoff_date)
        .all()
    )
    if sleep_rows:
        durations_h = [(r.total_sleep_min or 0) / 60 for r in sleep_rows]
        avg_h = sum(durations_h) / len(durations_h)
        avg_parts = [f"均值 {avg_h:.1f}h"]
        deep_rows = [r for r in sleep_rows if r.deep_sleep_min and r.total_sleep_min]
        if deep_rows:
            avg_deep_pct = (
                sum(r.deep_sleep_min / r.total_sleep_min for r in deep_rows)
                / len(deep_rows) * 100
            )
            avg_parts.append(f"深睡均值 {avg_deep_pct:.0f}%")
        hrv_rows = [r for r in sleep_rows if r.hrv_avg is not None]
        if hrv_rows:
            avg_hrv = sum(float(r.hrv_avg) for r in hrv_rows) / len(hrv_rows)
            avg_parts.append(f"HRV均值 {avg_hrv:.0f}ms")
        sections_7d.append("睡眠：" + "，".join(avg_parts))

    activity_rows = (
        session.query(Activity)
        .filter(Activity.activity_date >= cutoff_date)
        .all()
    )
    if activity_rows:
        type_counts = Counter(r.activity_type for r in activity_rows if r.activity_type)
        type_str = "、".join(f"{t}×{n}" for t, n in type_counts.most_common())
        total_min = sum(r.duration_min or 0 for r in activity_rows)
        avg_parts = [f"共 {len(activity_rows)} 次"]
        if type_str:
            avg_parts.append(f"类型：{type_str}")
        if total_min:
            avg_parts.append(f"总时长 {total_min}min")
        sections_7d.append("运动：" + "，".join(avg_parts))

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
        avg_parts = [f"均值 {avg_cal:.0f} kcal/天"]
        protein_rows = [m for m in meal_rows if m.protein_g is not None]
        if protein_rows:
            avg_prot = sum(float(m.protein_g) for m in protein_rows) / days
            avg_parts.append(f"蛋白质均值 {avg_prot:.0f}g")
        sections_7d.append("饮食：" + "，".join(avg_parts))

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
        sections_7d.append(f"体重：{first_w:.1f}→{last_w:.1f} kg（{sign}{delta:.1f}kg）")

    if not parts_today and not sections_7d:
        return ""

    lines: list[str] = ["[用户健康数据摘要]", ""]
    if parts_today:
        lines.append(f"今日（{today}）：")
        lines.extend(parts_today)
    if sections_7d:
        if parts_today:
            lines.append("")
        lines.append(f"过去{days}天均值：")
        lines.extend(sections_7d)

    return "\n".join(lines)
