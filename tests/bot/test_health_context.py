import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.base import Base
import db.models  # register models


@pytest.fixture(scope="module")
def engine():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


def test_empty_returns_empty_string(session):
    from bot.health_context import build_health_context
    assert build_health_context(session) == ""


def test_sleep_section_present(session):
    from bot.health_context import build_health_context
    from db.models import Sleep
    today = datetime.date.today()
    session.add(Sleep(
        sleep_date=today,
        total_sleep_min=420,
        deep_sleep_min=90,
        hrv_avg=52,
    ))
    session.flush()
    result = build_health_context(session)
    assert "睡眠" in result
    assert "7.0h" in result


def test_activity_section_present(session):
    from bot.health_context import build_health_context
    from db.models import Activity
    today = datetime.date.today()
    session.add(Activity(
        activity_date=today,
        activity_type="跑步",
        duration_min=30,
    ))
    session.flush()
    result = build_health_context(session)
    assert "运动" in result
    assert "跑步" in result


def test_body_metric_section_present(session):
    from bot.health_context import build_health_context
    from db.models import BodyMetric
    session.add(BodyMetric(
        measured_at=datetime.datetime.now(datetime.timezone.utc),
        weight_kg=68.2,
    ))
    session.flush()
    result = build_health_context(session)
    assert "体重" in result
    assert "68.2" in result


def test_meal_section_present(session):
    from bot.health_context import build_health_context
    from db.models import Meal
    session.add(Meal(
        recorded_at=datetime.datetime.now(datetime.timezone.utc),
        meal_type="早餐",
        foods=[],
        total_calories=500,
        protein_g=30,
        confirmed=True,
    ))
    session.flush()
    result = build_health_context(session)
    assert "饮食" in result


def test_out_of_range_data_excluded(session):
    from bot.health_context import build_health_context
    from db.models import Sleep
    # 15 days ago — outside 7-day window
    old_date = datetime.date.today() - datetime.timedelta(days=15)
    # Clear previous sleep rows to isolate this test
    session.query(Sleep).delete()
    session.add(Sleep(
        sleep_date=old_date,
        total_sleep_min=480,
    ))
    session.flush()
    result = build_health_context(session)
    assert "睡眠" not in result
