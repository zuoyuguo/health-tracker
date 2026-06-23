import datetime
import pytest
from unittest.mock import MagicMock, patch


def test_fetch_recent_measurements_filters_by_days():
    from renpho.sync import fetch_recent_measurements

    now = datetime.datetime.now(datetime.timezone.utc)
    ts_yesterday = int((now - datetime.timedelta(days=1)).timestamp())
    ts_old = int((now - datetime.timedelta(days=10)).timestamp())

    mock_client = MagicMock()
    mock_client.get_all_measurements.return_value = [
        {"timeStamp": ts_yesterday, "weight": 70.0, "id": "abc"},
        {"timeStamp": ts_old, "weight": 71.0, "id": "def"},
    ]

    result = fetch_recent_measurements(mock_client, days=7)
    assert len(result) == 1
    assert result[0]["id"] == "abc"


def test_fetch_recent_measurements_returns_empty_if_none_recent():
    from renpho.sync import fetch_recent_measurements

    now = datetime.datetime.now(datetime.timezone.utc)
    ts_old = int((now - datetime.timedelta(days=30)).timestamp())

    mock_client = MagicMock()
    mock_client.get_all_measurements.return_value = [
        {"timeStamp": ts_old, "weight": 70.0, "id": "xyz"},
    ]

    result = fetch_recent_measurements(mock_client, days=7)
    assert result == []


def test_parse_measurement_basic_fields():
    from renpho.sync import parse_measurement

    now_ts = 1700000000  # seconds
    raw = {
        "id": "rec123",
        "timeStamp": now_ts,
        "weight": 70.5,
        "bmi": 22.1,
        "bodyfat": 18.3,
        "water": 55.0,
        "visfat": 6.0,
        "bmr": 1650,
        "sinew": 57.6,
    }
    result = parse_measurement(raw)

    assert result["renpho_record_id"] == "rec123"
    assert result["weight_kg"] == 70.5
    assert result["bmi"] == 22.1
    assert result["body_fat_pct"] == 18.3
    assert result["water_pct"] == 55.0
    assert result["visceral_fat"] == 6.0
    assert result["bmr_kcal"] == 1650
    assert result["lean_mass_kg"] == 57.6
    expected_dt = datetime.datetime.fromtimestamp(now_ts, tz=datetime.timezone.utc)
    assert result["measured_at"] == expected_dt


def test_parse_measurement_millisecond_timestamp():
    from renpho.sync import parse_measurement

    ts_ms = 1700000000 * 1000
    raw = {"timeStamp": ts_ms, "weight": 69.0}
    result = parse_measurement(raw)

    expected_dt = datetime.datetime.fromtimestamp(1700000000, tz=datetime.timezone.utc)
    assert result["measured_at"] == expected_dt


def test_parse_measurement_record_id_falls_back_to_timestamp():
    from renpho.sync import parse_measurement

    raw = {"timeStamp": 1700000000, "weight": 70.0}
    result = parse_measurement(raw)
    assert result["renpho_record_id"] == "1700000000"


def test_parse_measurement_nullable_fields_absent():
    from renpho.sync import parse_measurement

    raw = {"timeStamp": 1700000000, "weight": 70.0, "id": "x"}
    result = parse_measurement(raw)

    assert result["fat_mass_kg"] is None
    assert result["muscle_mass_kg"] is None
    assert result["bone_mass_kg"] is None
    assert result["lean_mass_kg"] is None
    assert result["bmi"] is None
    assert result["bmr_kcal"] is None


def test_parse_measurement_bmr_is_int():
    from renpho.sync import parse_measurement

    raw = {"timeStamp": 1700000000, "id": "x", "bmr": 1700.9}
    result = parse_measurement(raw)
    assert result["bmr_kcal"] == 1700
    assert isinstance(result["bmr_kcal"], int)
