import datetime


def build_daily_prompt(
    meals: list[dict],
    sleep: dict | None,
    activities: list[dict],
    body_metric: dict | None,
) -> str:
    lines = ["你是一位健康分析师。请根据以下今日健康数据生成日报。\n"]

    # 饮食
    if meals:
        lines.append("【今日饮食】（已确认记录）")
        total_cal = sum(m.get("total_calories") or 0 for m in meals)
        total_protein = sum(m.get("protein_g") or 0 for m in meals)
        total_carbs = sum(m.get("carbs_g") or 0 for m in meals)
        total_fat = sum(m.get("fat_g") or 0 for m in meals)
        for m in meals:
            foods_str = "、".join(f["name"] for f in (m.get("foods") or []) if f.get("name"))
            recorded_at = m.get("recorded_at")
            time_str = recorded_at.strftime("%H:%M") if isinstance(recorded_at, datetime.datetime) else ""
            lines.append(
                f"- {m.get('meal_type', '进餐')}（{time_str}）：{foods_str or '未知食物'}"
                f" — {m.get('total_calories') or 0:.0f} kcal"
                f" | 蛋白质 {m.get('protein_g') or 0:.0f}g"
                f" | 碳水 {m.get('carbs_g') or 0:.0f}g"
                f" | 脂肪 {m.get('fat_g') or 0:.0f}g"
            )
        lines.append(
            f"合计：{total_cal:.0f} kcal"
            f" | 蛋白质 {total_protein:.0f}g"
            f" | 碳水 {total_carbs:.0f}g"
            f" | 脂肪 {total_fat:.0f}g"
        )
    else:
        lines.append("【今日饮食】无确认记录")

    lines.append("")

    # 睡眠
    if sleep:
        lines.append("【昨晚睡眠】")
        total_min = sleep.get("total_sleep_min") or 0
        deep_min = sleep.get("deep_sleep_min") or 0
        rem_min = sleep.get("rem_sleep_min") or 0
        total_h, total_m = divmod(total_min, 60)
        deep_h, deep_m = divmod(deep_min, 60)
        rem_h, rem_m = divmod(rem_min, 60)
        parts = [
            f"总时长：{total_h}h{total_m:02d}m",
            f"深睡：{deep_h}h{deep_m:02d}m",
            f"REM：{rem_h}h{rem_m:02d}m",
        ]
        if sleep.get("sleep_score") is not None:
            parts.append(f"睡眠评分：{sleep['sleep_score']}")
        if sleep.get("resting_hr") is not None:
            parts.append(f"静息心率：{sleep['resting_hr']} bpm")
        if sleep.get("hrv_avg") is not None:
            parts.append(f"HRV：{sleep['hrv_avg']:.1f} ms")
        lines.append(" | ".join(parts))
    else:
        lines.append("【昨晚睡眠】无数据")

    lines.append("")

    # 运动
    if activities:
        lines.append("【今日运动】")
        for a in activities:
            activity_line = (
                f"- {a.get('activity_type', '运动')}（{a.get('duration_min') or 0}分钟）："
                f"消耗 {a.get('calories_burned') or 0:.0f} kcal"
            )
            if a.get("avg_hr"):
                activity_line += f" | 平均心率 {a['avg_hr']} bpm"
            lines.append(activity_line)
    else:
        lines.append("【今日运动】无数据")

    lines.append("")

    # 体重体脂
    if body_metric:
        measured_at = body_metric.get("measured_at")
        date_str = measured_at.strftime("%Y-%m-%d") if isinstance(measured_at, datetime.datetime) else "未知"
        lines.append(f"【体重体脂】（记录于 {date_str}）")
        parts = []
        if body_metric.get("weight_kg") is not None:
            parts.append(f"体重：{body_metric['weight_kg']:.1f} kg")
        if body_metric.get("body_fat_pct") is not None:
            parts.append(f"体脂率：{body_metric['body_fat_pct']:.1f}%")
        if body_metric.get("bmi") is not None:
            parts.append(f"BMI：{body_metric['bmi']:.1f}")
        lines.append(" | ".join(parts) if parts else "无数值")
    else:
        lines.append("【体重体脂】无数据")

    lines.append("")
    lines.append(
        "请用中文生成 300-500 字的日报，格式：纯文本+少量emoji，分析以下维度：\n"
        "1. 热量摄入vs消耗（若有运动数据则计算净差值）\n"
        "2. 营养素比例评价\n"
        "3. 进餐时间分布（是否有深夜进食）\n"
        "4. 睡眠质量简评（若有数据）\n"
        "5. 运动评价（若有数据）\n"
        "6. 体重体脂评价（若有数据）\n"
        "7. 1-2条个性化建议"
    )

    return "\n".join(lines)
