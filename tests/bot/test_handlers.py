import datetime
import pytest
from db.base import get_engine, Base
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="module")
def engine():
    e = get_engine("sqlite:///:memory:")
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


def test_infer_meal_type_breakfast():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 8, 30, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "早餐"


def test_infer_meal_type_lunch():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "午餐"


def test_infer_meal_type_dinner():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 19, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "晚餐"


def test_infer_meal_type_late_night_snack():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 23, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "加餐"


def test_infer_meal_type_early_morning_snack():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 3, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "加餐"


def test_format_meal_summary_includes_food_names():
    from bot.handlers import format_meal_summary
    data = {
        "foods": [
            {"name": "牛排", "weight_g": 250, "calories": 600},
            {"name": "米饭", "weight_g": 150, "calories": 195},
        ],
        "total_calories": 795,
        "total_protein_g": 52,
        "total_carbs_g": 44,
        "total_fat_g": 28,
    }
    summary = format_meal_summary(data)
    assert "牛排" in summary
    assert "250" in summary
    assert "米饭" in summary
    assert "795" in summary
    assert "确认" in summary


def test_format_meal_summary_shows_macros():
    from bot.handlers import format_meal_summary
    data = {
        "foods": [{"name": "鸡胸肉", "weight_g": 200, "calories": 330}],
        "total_calories": 330,
        "total_protein_g": 62,
        "total_carbs_g": 0,
        "total_fat_g": 7,
    }
    summary = format_meal_summary(data)
    assert "62" in summary
    assert "蛋白质" in summary


def test_save_meal_sets_confirmed_and_meal_type(session):
    from bot.handlers import save_meal
    from db.models import Meal
    data = {
        "foods": [{"name": "米饭", "weight_g": 150, "calories": 195,
                   "protein_g": 4, "carbs_g": 44, "fat_g": 1}],
        "total_calories": 195,
        "total_protein_g": 4,
        "total_carbs_g": 44,
        "total_fat_g": 1,
    }
    recorded_at = datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc)
    meal = save_meal(session, data, recorded_at, confirmed=True)
    session.flush()

    result = session.query(Meal).filter_by(id=meal.id).one()
    assert result.confirmed is True
    assert result.meal_type == "午餐"
    assert float(result.total_calories) == 195.0
    assert float(result.protein_g) == 4.0


def test_save_meal_unconfirmed_by_default(session):
    from bot.handlers import save_meal
    data = {
        "foods": [],
        "total_calories": 0,
        "total_protein_g": 0,
        "total_carbs_g": 0,
        "total_fat_g": 0,
    }
    recorded_at = datetime.datetime(2026, 6, 22, 8, 0, tzinfo=datetime.timezone.utc)
    meal = save_meal(session, data, recorded_at)
    session.flush()
    assert meal.confirmed is False


def test_get_today_summary_no_meals(session):
    from bot.handlers import get_today_summary
    summary = get_today_summary(session, datetime.date(2025, 1, 1))
    assert "暂无" in summary


def test_get_today_summary_sums_calories(session):
    from bot.handlers import get_today_summary
    from db.models import Meal
    test_date = datetime.date(2026, 6, 23)
    meals = [
        Meal(
            recorded_at=datetime.datetime(2026, 6, 23, 8, 0, tzinfo=datetime.timezone.utc),
            meal_type="早餐",
            foods=[{"name": "面包", "weight_g": 80, "calories": 200}],
            total_calories=200,
            confirmed=True,
        ),
        Meal(
            recorded_at=datetime.datetime(2026, 6, 23, 12, 0, tzinfo=datetime.timezone.utc),
            meal_type="午餐",
            foods=[{"name": "米饭", "weight_g": 200, "calories": 260}],
            total_calories=260,
            confirmed=True,
        ),
    ]
    for m in meals:
        session.add(m)
    session.flush()

    summary = get_today_summary(session, test_date)
    assert "460" in summary
    assert "早餐" in summary
    assert "午餐" in summary


def test_get_today_summary_excludes_unconfirmed(session):
    from bot.handlers import get_today_summary
    from db.models import Meal
    test_date = datetime.date(2026, 6, 24)
    session.add(Meal(
        recorded_at=datetime.datetime(2026, 6, 24, 12, 0, tzinfo=datetime.timezone.utc),
        meal_type="午餐",
        foods=[],
        total_calories=500,
        confirmed=False,
    ))
    session.flush()
    summary = get_today_summary(session, test_date)
    assert "暂无" in summary
