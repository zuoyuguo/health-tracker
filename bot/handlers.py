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


from telegram import Update
from telegram.ext import ContextTypes
from bot.vision import analyze_food_photo, apply_correction
from db.base import SessionLocal

PENDING_MEAL_KEY = "pending_meal"


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("识别中...")
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    data = analyze_food_photo(image_bytes)
    context.user_data[PENDING_MEAL_KEY] = {
        "data": data,
        "recorded_at": update.message.date,
    }
    await update.message.reply_text(format_meal_summary(data))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    pending = context.user_data.get(PENDING_MEAL_KEY)
    if not pending:
        return
    if text == "确认":
        with SessionLocal() as session:
            save_meal(session, pending["data"], pending["recorded_at"], confirmed=True)
            session.commit()
        del context.user_data[PENDING_MEAL_KEY]
        await update.message.reply_text("✅ 已保存")
    else:
        await update.message.reply_text("正在修正...")
        new_data = apply_correction(pending["data"], text)
        context.user_data[PENDING_MEAL_KEY]["data"] = new_data
        await update.message.reply_text(format_meal_summary(new_data))


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.date.today()
    with SessionLocal() as session:
        reply = get_today_summary(session, today)
    await update.message.reply_text(reply)


async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note = " ".join(context.args) if context.args else ""
    if not note:
        await update.message.reply_text("用法：/note <备注内容>，例如：/note 喝了一杯咖啡")
        return
    recorded_at = update.message.date
    with SessionLocal() as session:
        meal = Meal(
            recorded_at=recorded_at,
            meal_type=infer_meal_type(recorded_at),
            foods=[],
            user_note=note,
            confirmed=True,
        )
        session.add(meal)
        session.commit()
    await update.message.reply_text(f"✅ 备注已保存：{note}")


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("功能开发中，周报将在 Phase 7 上线")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✅ 系统运行中")


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
