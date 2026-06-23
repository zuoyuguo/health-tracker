import datetime
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.base import Base
from db.models import Meal, Sleep, Activity, BodyMetric

_WEEK_END = datetime.date(2026, 6, 23)
_WEEK_START = datetime.date(2026, 6, 17)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _add_meal(session, date=_WEEK_END, cal=500):
    dt = datetime.datetime.combine(date, datetime.time(12, 0), tzinfo=datetime.timezone.utc)
    m = Meal(
        meal_type="午餐",
        recorded_at=dt,
        total_calories=cal,
        protein_g=30,
        carbs_g=60,
        fat_g=15,
        foods=[{"name": "米饭"}],
        confirmed=True,
    )
    session.add(m)
    session.commit()
    return m


def _add_activity(session, date=_WEEK_END):
    a = Activity(
        activity_date=date,
        activity_type="running",
        duration_min=30,
        calories_burned=300,
        avg_hr=145,
    )
    session.add(a)
    session.commit()
    return a


def _add_sleep(session, date=_WEEK_END):
    s = Sleep(
        sleep_date=date - datetime.timedelta(days=1),
        total_sleep_min=420,
        deep_sleep_min=90,
        rem_sleep_min=75,
        sleep_score=78,
        resting_hr=56,
    )
    session.add(s)
    session.commit()
    return s


def _add_body_metric(session, date=_WEEK_END, weight=71.0):
    dt = datetime.datetime.combine(date, datetime.time(8, 0), tzinfo=datetime.timezone.utc)
    bm = BodyMetric(
        measured_at=dt,
        weight_kg=weight,
        body_fat_pct=18.5,
        bmi=22.3,
        renpho_record_id=f"rec-{dt.timestamp():.0f}-{weight}",
    )
    session.add(bm)
    session.commit()
    return bm


# --- collect_weekly_data ---

def test_collect_weekly_data_returns_7_entries(session):
    from analysis.weekly import collect_weekly_data
    result = collect_weekly_data(session, _WEEK_END)
    assert len(result) == 7


def test_collect_weekly_data_dates_span_week(session):
    from analysis.weekly import collect_weekly_data
    result = collect_weekly_data(session, _WEEK_END)
    assert result[0]["date"] == _WEEK_START
    assert result[-1]["date"] == _WEEK_END


def test_collect_weekly_data_includes_meals_for_day(session):
    from analysis.weekly import collect_weekly_data
    _add_meal(session, date=_WEEK_END, cal=500)
    result = collect_weekly_data(session, _WEEK_END)
    last_day = result[-1]
    assert len(last_day["meals"]) == 1
    assert last_day["meals"][0]["total_calories"] == 500.0


def test_collect_weekly_data_excludes_unconfirmed_meals(session):
    from analysis.weekly import collect_weekly_data
    dt = datetime.datetime.combine(_WEEK_END, datetime.time(12, 0), tzinfo=datetime.timezone.utc)
    m = Meal(meal_type="午餐", recorded_at=dt, foods=[], confirmed=False)
    session.add(m)
    session.commit()
    result = collect_weekly_data(session, _WEEK_END)
    assert result[-1]["meals"] == []


def test_collect_weekly_data_includes_sleep_for_day(session):
    from analysis.weekly import collect_weekly_data
    _add_sleep(session, date=_WEEK_END)
    result = collect_weekly_data(session, _WEEK_END)
    last_day = result[-1]
    assert last_day["sleep"] is not None
    assert last_day["sleep"]["total_sleep_min"] == 420


def test_collect_weekly_data_sleep_none_when_missing(session):
    from analysis.weekly import collect_weekly_data
    result = collect_weekly_data(session, _WEEK_END)
    assert result[-1]["sleep"] is None


def test_collect_weekly_data_includes_activities(session):
    from analysis.weekly import collect_weekly_data
    _add_activity(session, date=_WEEK_END)
    result = collect_weekly_data(session, _WEEK_END)
    last_day = result[-1]
    assert len(last_day["activities"]) == 1
    assert last_day["activities"][0]["activity_type"] == "running"


def test_collect_weekly_data_includes_body_metrics_for_day(session):
    from analysis.weekly import collect_weekly_data
    _add_body_metric(session, date=_WEEK_END, weight=71.0)
    result = collect_weekly_data(session, _WEEK_END)
    last_day = result[-1]
    assert len(last_day["body_metrics"]) == 1
    assert last_day["body_metrics"][0]["weight_kg"] == 71.0


def test_collect_weekly_data_excludes_metrics_outside_week(session):
    from analysis.weekly import collect_weekly_data
    outside_date = _WEEK_START - datetime.timedelta(days=1)
    dt = datetime.datetime.combine(outside_date, datetime.time(8, 0), tzinfo=datetime.timezone.utc)
    bm = BodyMetric(measured_at=dt, weight_kg=72.0, renpho_record_id="rec-outside")
    session.add(bm)
    session.commit()
    result = collect_weekly_data(session, _WEEK_END)
    for entry in result:
        assert entry["body_metrics"] == []


def test_collect_weekly_data_meals_on_correct_day(session):
    from analysis.weekly import collect_weekly_data
    _add_meal(session, date=_WEEK_START, cal=400)
    result = collect_weekly_data(session, _WEEK_END)
    assert len(result[0]["meals"]) == 1   # _WEEK_START is index 0
    assert result[-1]["meals"] == []      # _WEEK_END (index 6) has no meal


# --- has_weekly_data ---

def test_has_weekly_data_true_when_meals_exist(session):
    from analysis.weekly import collect_weekly_data, has_weekly_data
    _add_meal(session)
    data = collect_weekly_data(session, _WEEK_END)
    assert has_weekly_data(data) is True


def test_has_weekly_data_true_when_activities_exist(session):
    from analysis.weekly import collect_weekly_data, has_weekly_data
    _add_activity(session)
    data = collect_weekly_data(session, _WEEK_END)
    assert has_weekly_data(data) is True


def test_has_weekly_data_false_when_empty(session):
    from analysis.weekly import collect_weekly_data, has_weekly_data
    data = collect_weekly_data(session, _WEEK_END)
    assert has_weekly_data(data) is False


def test_has_weekly_data_false_when_only_sleep_and_body_metrics(session):
    from analysis.weekly import collect_weekly_data, has_weekly_data
    _add_sleep(session)
    _add_body_metric(session)
    data = collect_weekly_data(session, _WEEK_END)
    assert has_weekly_data(data) is False


# --- generate_weekly_report ---

def test_generate_weekly_report_returns_none_when_no_data(session):
    from analysis.weekly import generate_weekly_report
    result = generate_weekly_report(session, _WEEK_END)
    assert result is None


def test_generate_weekly_report_calls_claude_and_returns_text(session):
    from analysis.weekly import generate_weekly_report
    _add_meal(session)

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="📊 本周周报：热量摄入趋势稳定。")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("analysis.weekly.anthropic.Anthropic", return_value=mock_client):
        result = generate_weekly_report(session, _WEEK_END)

    assert result == "📊 本周周报：热量摄入趋势稳定。"
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-8"
    assert call_kwargs["max_tokens"] == 2048


def test_generate_weekly_report_prompt_contains_meal_calories(session):
    from analysis.weekly import generate_weekly_report
    _add_meal(session, cal=620)

    captured = []

    def fake_create(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        m = MagicMock()
        m.content = [MagicMock(text="周报内容")]
        return m

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = fake_create

    with patch("analysis.weekly.anthropic.Anthropic", return_value=mock_client):
        generate_weekly_report(session, _WEEK_END)

    assert "620" in captured[0]
