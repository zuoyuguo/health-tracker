import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.base import Base
from db.models import BodyMetric


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _parsed(record_id="rec1", ts=None):
    if ts is None:
        ts = datetime.datetime(2026, 6, 22, 12, 0, 0, tzinfo=datetime.timezone.utc)
    return {
        "renpho_record_id": record_id,
        "measured_at": ts,
        "weight_kg": 70.5,
        "bmi": 22.1,
        "body_fat_pct": 18.3,
        "fat_mass_kg": None,
        "lean_mass_kg": 57.6,
        "muscle_mass_kg": None,
        "bone_mass_kg": None,
        "water_pct": 55.0,
        "visceral_fat": 6.0,
        "bmr_kcal": 1650,
    }


def test_insert_body_metrics_inserts_new_record(session):
    from renpho_sync.db_sync import insert_body_metrics

    count = insert_body_metrics(session, [_parsed("r1")])
    session.commit()

    assert count == 1
    row = session.query(BodyMetric).filter_by(renpho_record_id="r1").first()
    assert row is not None
    assert float(row.weight_kg) == 70.5
    assert float(row.bmi) == 22.1
    assert float(row.body_fat_pct) == 18.3
    assert float(row.lean_mass_kg) == 57.6
    assert float(row.water_pct) == 55.0
    assert float(row.visceral_fat) == 6.0
    assert row.bmr_kcal == 1650
    assert row.fat_mass_kg is None
    assert row.muscle_mass_kg is None
    assert row.bone_mass_kg is None


def test_insert_body_metrics_skips_existing_record(session):
    from renpho_sync.db_sync import insert_body_metrics

    insert_body_metrics(session, [_parsed("r1")])
    session.commit()

    count2 = insert_body_metrics(session, [_parsed("r1")])
    session.commit()

    assert count2 == 0
    assert session.query(BodyMetric).count() == 1


def test_insert_body_metrics_inserts_multiple_new(session):
    from renpho_sync.db_sync import insert_body_metrics

    records = [_parsed("r1"), _parsed("r2"), _parsed("r3")]
    count = insert_body_metrics(session, records)
    session.commit()

    assert count == 3
    assert session.query(BodyMetric).count() == 3


def test_insert_body_metrics_partial_new_and_existing(session):
    from renpho_sync.db_sync import insert_body_metrics

    insert_body_metrics(session, [_parsed("r1")])
    session.commit()

    count = insert_body_metrics(session, [_parsed("r1"), _parsed("r2")])
    session.commit()

    assert count == 1
    assert session.query(BodyMetric).count() == 2


def test_insert_body_metrics_returns_zero_for_empty_list(session):
    from renpho_sync.db_sync import insert_body_metrics

    count = insert_body_metrics(session, [])
    assert count == 0


def test_insert_body_metrics_skips_when_record_id_is_empty(session):
    from renpho_sync.db_sync import insert_body_metrics

    parsed = _parsed("")
    count = insert_body_metrics(session, [parsed])
    session.commit()
    assert count == 0
