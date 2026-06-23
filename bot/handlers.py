import datetime
from db.models import Meal


def infer_meal_type(dt: datetime.datetime) -> str:
    hour = dt.hour
    if 5 <= hour < 10:
        return "早餐"
    elif 10 <= hour < 14:
        return "午餐"
    elif 17 <= hour < 21:
        return "晚餐"
    return "加餐"


def format_meal_summary(data: dict) -> str:
    lines = ["🍽 已识别："]
    for food in data.get("foods", []):
        lines.append(f"• {food['name']} {food['weight_g']}g — {food['calories']} kcal")
    lines.append("")
    lines.append(
        f"合计：{data.get('total_calories', 0):.0f} kcal | "
        f"蛋白质 {data.get('total_protein_g', 0):.0f}g | "
        f"碳水 {data.get('total_carbs_g', 0):.0f}g | "
        f"脂肪 {data.get('total_fat_g', 0):.0f}g"
    )
    lines.append("")
    lines.append("回复「确认」保存，或直接告诉我需要修正的内容")
    return "\n".join(lines)


def save_meal(session, data: dict, recorded_at: datetime.datetime, confirmed: bool = False) -> Meal:
    meal = Meal(
        recorded_at=recorded_at,
        meal_type=infer_meal_type(recorded_at),
        foods=data.get("foods", []),
        total_calories=data.get("total_calories"),
        protein_g=data.get("total_protein_g"),
        carbs_g=data.get("total_carbs_g"),
        fat_g=data.get("total_fat_g"),
        confirmed=confirmed,
    )
    session.add(meal)
    session.flush()
    return meal


def get_today_summary(session, date: datetime.date) -> str:
    from sqlalchemy import func
    meals = (
        session.query(Meal)
        .filter(
            func.date(Meal.recorded_at) == date,
            Meal.confirmed.is_(True),
        )
        .order_by(Meal.recorded_at)
        .all()
    )
    if not meals:
        return f"📅 {date} 暂无饮食记录"

    total_cal = sum(float(m.total_calories or 0) for m in meals)
    lines = [f"📅 {date} 饮食汇总", ""]
    for meal in meals:
        time_str = meal.recorded_at.strftime("%H:%M")
        cal_str = f"{float(meal.total_calories):.0f} kcal" if meal.total_calories else "—"
        if meal.user_note and not meal.foods:
            lines.append(f"• {time_str} [{meal.meal_type}] {meal.user_note}")
        else:
            food_names = "、".join(f["name"] for f in (meal.foods or []))
            lines.append(f"• {time_str} [{meal.meal_type}] {food_names} {cal_str}")
    lines.append("")
    lines.append(f"合计摄入：{total_cal:.0f} kcal")
    return "\n".join(lines)
