from db.models import BodyMetric


def insert_body_metrics(session, parsed_list: list[dict]) -> int:
    inserted = 0
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
    return inserted
