import datetime
import pytest


_MEAL = {
    "meal_type": "早餐",
    "recorded_at": datetime.datetime(2026, 6, 23, 8, 30, tzinfo=datetime.timezone.utc),
    "total_calories": 350.0,
    "protein_g": 20.0,
    "carbs_g": 40.0,
    "fat_g": 12.0,
    "foods": [{"name": "鸡蛋"}, {"name": "全麦面包"}],
}

_SLEEP = {
    "total_sleep_min": 450,
    "deep_sleep_min": 105,
    "rem_sleep_min": 80,
    "sleep_score": 82,
    "resting_hr": 54,
    "hrv_avg": 42.5,
}

_ACTIVITY = {
    "activity_type": "running",
    "duration_min": 45,
    "calories_burned": 380.0,
    "avg_hr": 152,
}

_BODY = {
    "measured_at": datetime.datetime(2026, 6, 22, 10, 0, tzinfo=datetime.timezone.utc),
    "weight_kg": 70.5,
    "body_fat_pct": 18.3,
    "bmi": 22.1,
}


def test_build_daily_prompt_includes_meal_data():
    from analysis.prompts import build_daily_prompt
    result = build_daily_prompt([_MEAL], None, [], None)
    assert "早餐" in result
    assert "350" in result
    assert "鸡蛋" in result
    assert "全麦面包" in result


def test_build_daily_prompt_includes_sleep_data():
    from analysis.prompts import build_daily_prompt
    result = build_daily_prompt([], _SLEEP, [], None)
    assert "7" in result        # 450 min = 7h30m
    assert "82" in result       # sleep_score
    assert "54" in result       # resting_hr


def test_build_daily_prompt_includes_activity_data():
    from analysis.prompts import build_daily_prompt
    result = build_daily_prompt([], None, [_ACTIVITY], None)
    assert "45" in result       # duration_min
    assert "380" in result      # calories_burned
    assert "152" in result      # avg_hr


def test_build_daily_prompt_includes_body_metric_data():
    from analysis.prompts import build_daily_prompt
    result = build_daily_prompt([], None, [], _BODY)
    assert "70.5" in result
    assert "18.3" in result
    assert "22.1" in result


def test_build_daily_prompt_returns_nonempty_string_when_all_none():
    from analysis.prompts import build_daily_prompt
    result = build_daily_prompt([], None, [], None)
    assert isinstance(result, str)
    assert len(result) > 100


def test_build_daily_prompt_includes_analysis_request():
    from analysis.prompts import build_daily_prompt
    result = build_daily_prompt([_MEAL], _SLEEP, [_ACTIVITY], _BODY)
    # 必须包含对 Claude 的分析指示
    assert "300" in result or "500" in result
    assert "中文" in result or "日报" in result


def test_build_daily_prompt_meal_totals_summed():
    from analysis.prompts import build_daily_prompt
    meal2 = {**_MEAL, "meal_type": "午餐", "total_calories": 650.0,
              "protein_g": 45.0, "carbs_g": 80.0, "fat_g": 10.0,
              "foods": [{"name": "米饭"}]}
    result = build_daily_prompt([_MEAL, meal2], None, [], None)
    # 合计热量 350 + 650 = 1000
    assert "1000" in result


# --- build_weekly_prompt tests ---

_WEEK_ENTRY = {
    "date": datetime.date(2026, 6, 23),
    "meals": [_MEAL],
    "sleep": _SLEEP,
    "activities": [_ACTIVITY],
    "body_metrics": [_BODY],
}

_EMPTY_WEEK_ENTRY = {
    "date": datetime.date(2026, 6, 23),
    "meals": [],
    "sleep": None,
    "activities": [],
    "body_metrics": [],
}


def test_build_weekly_prompt_includes_date():
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_WEEK_ENTRY])
    assert "06/23" in result


def test_build_weekly_prompt_includes_weekday():
    # 2026-06-23 is Tuesday (weekday=1 → 周二)
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_WEEK_ENTRY])
    assert "周二" in result


def test_build_weekly_prompt_includes_calorie_total():
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_WEEK_ENTRY])
    assert "350" in result


def test_build_weekly_prompt_includes_sleep_duration():
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_WEEK_ENTRY])
    assert "7h" in result   # 450 min = 7h30m


def test_build_weekly_prompt_includes_sleep_score():
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_WEEK_ENTRY])
    assert "82" in result


def test_build_weekly_prompt_includes_activity_data():
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_WEEK_ENTRY])
    assert "45" in result    # duration_min
    assert "380" in result   # calories_burned


def test_build_weekly_prompt_includes_body_weight():
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_WEEK_ENTRY])
    assert "70.5" in result


def test_build_weekly_prompt_includes_analysis_request():
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_WEEK_ENTRY])
    assert "500" in result or "800" in result
    assert "周报" in result


def test_build_weekly_prompt_empty_day_shows_no_data():
    from analysis.prompts import build_weekly_prompt
    result = build_weekly_prompt([_EMPTY_WEEK_ENTRY])
    assert "无记录" in result
    assert "无数据" in result
    assert "无" in result


def test_build_weekly_prompt_multiple_days():
    from analysis.prompts import build_weekly_prompt
    entry2 = {**_EMPTY_WEEK_ENTRY, "date": datetime.date(2026, 6, 22)}
    result = build_weekly_prompt([_WEEK_ENTRY, entry2])
    assert "06/23" in result
    assert "06/22" in result
