# tests/db/test_models.py
import pytest
from sqlalchemy import inspect, text
from db.base import Base, get_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="module")
def engine():
    """SQLite in-memory engine，用于测试模型定义"""
    e = get_engine("sqlite:///:memory:")
    # 导入 models 触发 mapper 注册
    import db.models
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


def test_meal_table_exists(engine):
    assert inspect(engine).has_table("meals")


def test_sleep_table_exists(engine):
    assert inspect(engine).has_table("sleep")


def test_activity_table_exists(engine):
    assert inspect(engine).has_table("activities")


def test_body_metric_table_exists(engine):
    assert inspect(engine).has_table("body_metrics")


def test_meal_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("meals")}
    required = {
        "id", "recorded_at", "meal_type", "photo_url", "foods",
        "total_calories", "protein_g", "carbs_g", "fat_g",
        "user_note", "confirmed", "created_at",
    }
    assert required.issubset(cols)


def test_sleep_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("sleep")}
    required = {
        "id", "sleep_date", "total_sleep_min", "deep_sleep_min",
        "light_sleep_min", "rem_sleep_min", "awake_min",
        "sleep_score", "hrv_avg", "resting_hr",
        "sleep_start", "sleep_end", "created_at",
    }
    assert required.issubset(cols)


def test_activity_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("activities")}
    required = {
        "id", "activity_date", "activity_type", "duration_min",
        "calories_burned", "avg_hr", "max_hr", "steps", "distance_km",
        "hr_zone_1_min", "hr_zone_2_min", "hr_zone_3_min",
        "hr_zone_4_min", "hr_zone_5_min",
        "garmin_activity_id", "created_at",
    }
    assert required.issubset(cols)


def test_body_metric_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("body_metrics")}
    required = {
        "id", "measured_at", "weight_kg", "bmi", "body_fat_pct",
        "fat_mass_kg", "lean_mass_kg", "muscle_mass_kg", "bone_mass_kg",
        "water_pct", "visceral_fat", "bmr_kcal",
        "renpho_record_id", "created_at",
    }
    assert required.issubset(cols)


def test_meal_confirmed_defaults_false(session):
    from db.models import Meal
    import datetime
    meal = Meal(
        recorded_at=datetime.datetime.now(datetime.timezone.utc),
        foods=[{"name": "鸡蛋", "weight_g": 60, "calories": 90}],
        total_calories=90,
    )
    session.add(meal)
    session.flush()
    assert meal.confirmed is False


def test_sleep_date_unique_constraint(session):
    from db.models import Sleep
    import datetime
    from sqlalchemy.exc import IntegrityError
    today = datetime.date.today()
    s1 = Sleep(sleep_date=today, total_sleep_min=420)
    s2 = Sleep(sleep_date=today, total_sleep_min=360)
    session.add(s1)
    session.flush()
    session.add(s2)
    with pytest.raises(IntegrityError):
        session.flush()


def test_activity_garmin_id_unique_constraint(session):
    from db.models import Activity
    import datetime
    from sqlalchemy.exc import IntegrityError
    a1 = Activity(activity_date=datetime.date.today(), garmin_activity_id=99999)
    a2 = Activity(activity_date=datetime.date.today(), garmin_activity_id=99999)
    session.add(a1)
    session.flush()
    session.add(a2)
    with pytest.raises(IntegrityError):
        session.flush()


def test_body_metric_renpho_id_unique_constraint(session):
    from db.models import BodyMetric
    import datetime
    from sqlalchemy.exc import IntegrityError
    b1 = BodyMetric(measured_at=datetime.datetime.now(datetime.timezone.utc), renpho_record_id="abc123")
    b2 = BodyMetric(measured_at=datetime.datetime.now(datetime.timezone.utc), renpho_record_id="abc123")
    session.add(b1)
    session.flush()
    session.add(b2)
    with pytest.raises(IntegrityError):
        session.flush()
