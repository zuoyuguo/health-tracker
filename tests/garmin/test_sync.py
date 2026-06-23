# tests/garmin/test_sync.py
import pytest
from unittest.mock import MagicMock
from garmin.sync import (
    fetch_yesterday_sleep,
    fetch_yesterday_activities,
    parse_sleep,
    parse_activity,
)

SLEEP_FIXTURE = {
    "dailySleepDTO": {
        "sleepTimeSeconds": 27000,       # 450 min = 7.5h
        "deepSleepSeconds": 5400,        # 90 min
        "lightSleepSeconds": 14400,      # 240 min
        "remSleepSeconds": 5400,         # 90 min
        "awakeSleepSeconds": 1800,       # 30 min
        "sleepScores": {"overall": {"value": 82}},
        "sleepStartTimestampGMT": 1750000000000,   # ms
        "sleepEndTimestampGMT": 1750027000000,     # ms
    },
    "restingHeartRate": 54,
}

ACTIVITY_FIXTURE = {
    "activityId": 12345678,
    "activityType": {"typeKey": "running"},
    "startTimeLocal": "2026-06-21 07:30:00",
    "duration": 3600.0,           # 60 min
    "calories": 550,
    "averageHR": 145,
    "maxHR": 172,
    "steps": 8500,
    "distance": 10000.0,          # 10 km (meters)
    "hrTimeInZone": [300, 600, 1200, 900, 600],  # seconds per zone
}


def test_parse_sleep_converts_seconds_to_minutes():
    result = parse_sleep(SLEEP_FIXTURE)
    assert result["total_sleep_min"] == 450
    assert result["deep_sleep_min"] == 90
    assert result["light_sleep_min"] == 240
    assert result["rem_sleep_min"] == 90
    assert result["awake_min"] == 30


def test_parse_sleep_extracts_score_and_hr():
    result = parse_sleep(SLEEP_FIXTURE)
    assert result["sleep_score"] == 82
    assert result["resting_hr"] == 54


def test_parse_sleep_extracts_timestamps():
    result = parse_sleep(SLEEP_FIXTURE)
    assert result["sleep_start"] is not None
    assert result["sleep_end"] is not None
    # 应为 ISO 格式字符串
    assert "T" in result["sleep_start"] or " " in result["sleep_start"]


def test_parse_sleep_missing_score_returns_none():
    raw = {
        "dailySleepDTO": {
            "sleepTimeSeconds": 27000,
            "deepSleepSeconds": 5400,
            "lightSleepSeconds": 14400,
            "remSleepSeconds": 5400,
            "awakeSleepSeconds": 1800,
            "sleepScores": {},
            "sleepStartTimestampGMT": 1750000000000,
            "sleepEndTimestampGMT": 1750027000000,
        },
        "restingHeartRate": None,
    }
    result = parse_sleep(raw)
    assert result["sleep_score"] is None
    assert result["resting_hr"] is None


def test_parse_activity_converts_fields():
    result = parse_activity(ACTIVITY_FIXTURE)
    assert result["garmin_activity_id"] == 12345678
    assert result["activity_type"] == "running"
    assert result["duration_min"] == 60
    assert result["calories_burned"] == 550
    assert result["avg_hr"] == 145
    assert result["max_hr"] == 172
    assert result["steps"] == 8500


def test_parse_activity_converts_distance_to_km():
    result = parse_activity(ACTIVITY_FIXTURE)
    assert result["distance_km"] == pytest.approx(10.0, rel=1e-3)


def test_parse_activity_converts_hr_zones_to_minutes():
    result = parse_activity(ACTIVITY_FIXTURE)
    assert result["hr_zone_1_min"] == 5    # 300s
    assert result["hr_zone_2_min"] == 10   # 600s
    assert result["hr_zone_3_min"] == 20   # 1200s
    assert result["hr_zone_4_min"] == 15   # 900s
    assert result["hr_zone_5_min"] == 10   # 600s


def test_parse_activity_missing_hr_zones_returns_none():
    raw = {**ACTIVITY_FIXTURE, "hrTimeInZone": None}
    result = parse_activity(raw)
    assert result["hr_zone_1_min"] is None


def test_fetch_yesterday_sleep_calls_api(monkeypatch):
    mock_garmin = MagicMock()
    mock_garmin.get_sleep_data.return_value = SLEEP_FIXTURE

    import datetime
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    result = fetch_yesterday_sleep(mock_garmin)

    mock_garmin.get_sleep_data.assert_called_once_with(yesterday)
    assert result == SLEEP_FIXTURE


def test_fetch_yesterday_activities_calls_api():
    mock_garmin = MagicMock()
    mock_garmin.get_activities_by_date.return_value = [ACTIVITY_FIXTURE]

    import datetime
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    result = fetch_yesterday_activities(mock_garmin)

    mock_garmin.get_activities_by_date.assert_called_once_with(yesterday, yesterday)
    assert result == [ACTIVITY_FIXTURE]
