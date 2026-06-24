import datetime
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.base import Base
from db.models import Meal, Sleep, Activity, BodyMetric


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


_TODAY = datetime.date(2026, 6, 23)
_YESTERDAY = datetime.date(2026, 6, 22)
_NOW = datetime.datetime(2026, 6, 23, 12, 0, 0, tzinfo=datetime.timezone.utc)
_END_OF_TODAY = datetime.datetime(2026, 6, 23, 23, 59, 59, tzinfo=datetime.timezone.utc)


def _add_meal(session, meal_type="早餐", cal=350, confirmed=True,
              recorded_at=None):
    if recorded_at is None:
        recorded_at = _NOW
    m = Meal(
        meal_type=meal_type,
        recorded_at=recorded_at,
        total_calories=cal,
        protein_g=20,
        carbs_g=40,
        fat_g=12,
        foods=[{"name": "鸡蛋"}],
        confirmed=confirmed,
    )
    session.add(m)
    session.commit()
    return m


def _add_sleep(session, date=_YESTERDAY):
    s = Sleep(
        sleep_date=date,
        total_sleep_min=450,
        deep_sleep_min=105,
        rem_sleep_min=80,
        sleep_score=82,
        resting_hr=54,
    )
    session.add(s)
    session.commit()
    return s


def _add_activity(session, date=_TODAY):
    a = Activity(
        activity_date=date,
        activity_type="running",
        duration_min=45,
        calories_burned=380,
        avg_hr=152,
    )
    session.add(a)
    session.commit()
    return a


def _add_body_metric(session, measured_at=None):
    if measured_at is None:
        measured_at = datetime.datetime(2026, 6, 22, 10, 0, tzinfo=datetime.timezone.utc)
    bm = BodyMetric(
        measured_at=measured_at,
        weight_kg=70.5,
        body_fat_pct=18.3,
        bmi=22.1,
        renpho_record_id=f"rec-{measured_at.timestamp():.0f}",
    )
    session.add(bm)
    session.commit()
    return bm


# --- collect_daily_data ---

def test_collect_returns_confirmed_meals_only(session):
    from analysis.daily import collect_daily_data
    _add_meal(session, confirmed=True)
    _add_meal(session, confirmed=False)
    data = collect_daily_data(session, _TODAY)
    assert len(data["meals"]) == 1
    assert data["meals"][0]["meal_type"] == "早餐"


def test_collect_excludes_meals_from_other_days(session):
    from analysis.daily import collect_daily_data
    yesterday_dt = datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc)
    _add_meal(session, confirmed=True, recorded_at=yesterday_dt)
    data = collect_daily_data(session, _TODAY)
    assert data["meals"] == []


def test_collect_returns_todays_sleep(session):
    from analysis.daily import collect_daily_data
    _add_sleep(session, date=_TODAY)
    data = collect_daily_data(session, _TODAY)
    assert data["sleep"] is not None
    assert data["sleep"]["total_sleep_min"] == 450
    assert data["sleep"]["sleep_score"] == 82


def test_collect_sleep_is_none_when_missing(session):
    from analysis.daily import collect_daily_data
    data = collect_daily_data(session, _TODAY)
    assert data["sleep"] is None


def test_collect_returns_todays_activities(session):
    from analysis.daily import collect_daily_data
    _add_activity(session, date=_TODAY)
    data = collect_daily_data(session, _TODAY)
    assert len(data["activities"]) == 1
    assert data["activities"][0]["activity_type"] == "running"
    assert data["activities"][0]["calories_burned"] == 380.0


def test_collect_excludes_activities_from_other_days(session):
    from analysis.daily import collect_daily_data
    _add_activity(session, date=_YESTERDAY)
    data = collect_daily_data(session, _TODAY)
    assert data["activities"] == []


def test_collect_returns_most_recent_body_metric(session):
    from analysis.daily import collect_daily_data
    _add_body_metric(session, datetime.datetime(2026, 6, 20, 10, 0, tzinfo=datetime.timezone.utc))
    _add_body_metric(session, datetime.datetime(2026, 6, 22, 10, 0, tzinfo=datetime.timezone.utc))
    data = collect_daily_data(session, _TODAY)
    assert data["body_metric"] is not None
    assert data["body_metric"]["weight_kg"] == 70.5


def test_collect_body_metric_excludes_future_records(session):
    from analysis.daily import collect_daily_data
    future = datetime.datetime(2026, 6, 24, 10, 0, tzinfo=datetime.timezone.utc)
    _add_body_metric(session, future)
    data = collect_daily_data(session, _TODAY)
    assert data["body_metric"] is None


# --- has_data ---

def test_has_data_true_when_meals_present(session):
    from analysis.daily import collect_daily_data, has_data
    _add_meal(session, confirmed=True)
    data = collect_daily_data(session, _TODAY)
    assert has_data(data) is True


def test_has_data_true_when_activities_present(session):
    from analysis.daily import collect_daily_data, has_data
    _add_activity(session)
    data = collect_daily_data(session, _TODAY)
    assert has_data(data) is True


def test_has_data_false_when_only_sleep_and_body_metric(session):
    from analysis.daily import collect_daily_data, has_data
    _add_sleep(session)
    _add_body_metric(session)
    data = collect_daily_data(session, _TODAY)
    assert has_data(data) is False


def test_has_data_false_when_empty(session):
    from analysis.daily import collect_daily_data, has_data
    data = collect_daily_data(session, _TODAY)
    assert has_data(data) is False


# --- generate_daily_report ---

def test_generate_daily_report_returns_none_when_no_data(session):
    from analysis.daily import generate_daily_report
    result = generate_daily_report(session, _TODAY)
    assert result is None


def test_generate_daily_report_calls_claude_and_returns_text(session):
    from analysis.daily import generate_daily_report
    _add_meal(session, confirmed=True)

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="📊 今日日报：热量摄入 350 kcal，营养均衡，建议多喝水。")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("analysis.daily.anthropic.Anthropic", return_value=mock_client):
        result = generate_daily_report(session, _TODAY)

    assert result == "📊 今日日报：热量摄入 350 kcal，营养均衡，建议多喝水。"
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-8"
    assert call_kwargs["max_tokens"] == 1024


def test_generate_daily_report_prompt_contains_meal_data(session):
    from analysis.daily import generate_daily_report
    _add_meal(session, confirmed=True, cal=500)

    captured_prompt = []

    def fake_create(**kwargs):
        captured_prompt.append(kwargs["messages"][0]["content"])
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="日报内容")]
        return mock_msg

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = fake_create

    with patch("analysis.daily.anthropic.Anthropic", return_value=mock_client):
        generate_daily_report(session, _TODAY)

    assert "500" in captured_prompt[0]
