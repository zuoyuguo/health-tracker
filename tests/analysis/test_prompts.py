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
