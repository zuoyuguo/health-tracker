from sqlalchemy import func
from db.models import BodyMetric


def insert_body_metrics(session, parsed_list: list[dict]) -> int:
    inserted = 0
    affected_dates = set()
    for parsed in parsed_list:
        record_id = parsed.get("renpho_record_id", "")
        if not record_id:
            continue
        exists = session.query(BodyMetric).filter_by(
            renpho_record_id=record_id
        ).first()
        if exists:
            continue
        session.add(BodyMetric(
            renpho_record_id=record_id,
            measured_at=parsed["measured_at"],
            weight_kg=parsed.get("weight_kg"),
            bmi=parsed.get("bmi"),
            body_fat_pct=parsed.get("body_fat_pct"),
            fat_mass_kg=parsed.get("fat_mass_kg"),
            lean_mass_kg=parsed.get("lean_mass_kg"),
            muscle_mass_kg=parsed.get("muscle_mass_kg"),
            bone_mass_kg=parsed.get("bone_mass_kg"),
            water_pct=parsed.get("water_pct"),
            visceral_fat=parsed.get("visceral_fat"),
            bmr_kcal=parsed.get("bmr_kcal"),
        ))
        inserted += 1
        affected_dates.add(parsed["measured_at"].date())

    if affected_dates:
        session.flush()
        _dedupe_by_date(session, affected_dates)

    return inserted


def _dedupe_by_date(session, dates) -> None:
    """同一天体重相差 ≤1kg 时，只保留体重最低的一条。"""
    for d in dates:
        records = (
            session.query(BodyMetric)
            .filter(func.date(BodyMetric.measured_at) == d)
            .order_by(BodyMetric.weight_kg)
            .all()
        )
        if len(records) <= 1:
            continue
        weights = [float(r.weight_kg) for r in records if r.weight_kg is not None]
        if not weights:
            continue
        if max(weights) - min(weights) <= 1.0:
            # 保留最低体重那条，删除其余
            keep = records[0]
            for r in records[1:]:
                session.delete(r)
