import pytest
from unittest.mock import MagicMock, patch
import scheduler as sched_mod


@pytest.fixture(autouse=True)
def reset_failure_counters():
    sched_mod._garmin_consecutive_failures = 0
    sched_mod._renpho_consecutive_failures = 0
    yield
    sched_mod._garmin_consecutive_failures = 0
    sched_mod._renpho_consecutive_failures = 0


def _make_mock_garmin_client(sleep_raw=None, activities_raw=None):
    client = MagicMock()
    client.garmin = MagicMock()
    return client


def test_garmin_sync_job_resets_counter_on_success():
    sched_mod._garmin_consecutive_failures = 2
    mock_client = _make_mock_garmin_client()
    mock_session = MagicMock()

    with patch("scheduler.GarminClient", return_value=mock_client), \
         patch("scheduler.fetch_yesterday_sleep", return_value={"dailySleepDTO": {}}), \
         patch("scheduler.fetch_yesterday_activities", return_value=[]), \
         patch("scheduler.parse_sleep", return_value={"sleep_date": "2026-06-21"}), \
         patch("scheduler.upsert_sleep"), \
         patch("scheduler.insert_activities", return_value=0), \
         patch("scheduler.SessionLocal") as MockSession:
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        sched_mod.garmin_sync_job()

    assert sched_mod._garmin_consecutive_failures == 0


def test_garmin_sync_job_increments_counter_on_failure():
    with patch("scheduler.GarminClient", side_effect=Exception("Login failed")), \
         patch("scheduler.send_alert"):
        sched_mod.garmin_sync_job()

    assert sched_mod._garmin_consecutive_failures == 1


def test_garmin_sync_job_sends_alert_after_3_failures():
    with patch("scheduler.GarminClient", side_effect=Exception("Login failed")), \
         patch("scheduler.send_alert") as mock_alert:
        sched_mod.garmin_sync_job()
        sched_mod.garmin_sync_job()
        sched_mod.garmin_sync_job()

    assert sched_mod._garmin_consecutive_failures == 3
    mock_alert.assert_called_once()
    alert_text = mock_alert.call_args[0][0]
    assert "3" in alert_text or "三" in alert_text


def test_garmin_sync_job_no_alert_before_3_failures():
    with patch("scheduler.GarminClient", side_effect=Exception("fail")), \
         patch("scheduler.send_alert") as mock_alert:
        sched_mod.garmin_sync_job()
        sched_mod.garmin_sync_job()

    assert sched_mod._garmin_consecutive_failures == 2
    mock_alert.assert_not_called()


def test_garmin_sync_job_no_alert_after_3rd_failure():
    with patch("scheduler.GarminClient", side_effect=Exception("fail")), \
         patch("scheduler.send_alert") as mock_alert:
        for _ in range(4):
            sched_mod.garmin_sync_job()
    mock_alert.assert_called_once()


def test_garmin_sync_job_skips_upsert_when_sleep_date_missing():
    mock_client = _make_mock_garmin_client()
    mock_session = MagicMock()

    with patch("scheduler.GarminClient", return_value=mock_client), \
         patch("scheduler.fetch_yesterday_sleep", return_value={}), \
         patch("scheduler.fetch_yesterday_activities", return_value=[]), \
         patch("scheduler.parse_sleep", return_value={"sleep_date": None}), \
         patch("scheduler.upsert_sleep") as mock_upsert, \
         patch("scheduler.insert_activities", return_value=0), \
         patch("scheduler.SessionLocal") as MockSession:
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        sched_mod.garmin_sync_job()

    mock_upsert.assert_not_called()


def test_create_scheduler_returns_scheduler_with_two_jobs():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = sched_mod.create_scheduler()
    assert isinstance(scheduler, BackgroundScheduler)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 2
    for job in jobs:
        assert job.trigger.__class__.__name__ == "CronTrigger"


# --- renpho_sync_job tests ---

def test_renpho_sync_job_resets_counter_on_success():
    sched_mod._renpho_consecutive_failures = 2
    mock_wrapper = MagicMock()
    mock_session = MagicMock()

    with patch("scheduler.RenphoClientWrapper", return_value=mock_wrapper), \
         patch("scheduler.fetch_recent_measurements", return_value=[{"timeStamp": 1700000000, "weight": 70.0, "id": "r1"}]), \
         patch("scheduler.parse_measurement", return_value={"renpho_record_id": "r1", "measured_at": None}), \
         patch("scheduler.insert_body_metrics", return_value=1), \
         patch("scheduler.SessionLocal") as MockSession:
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        sched_mod.renpho_sync_job()

    mock_wrapper.connect.assert_called_once()
    assert sched_mod._renpho_consecutive_failures == 0


def test_renpho_sync_job_increments_counter_on_failure():
    with patch("scheduler.RenphoClientWrapper", side_effect=Exception("Login failed")), \
         patch("scheduler.send_alert"):
        sched_mod.renpho_sync_job()

    assert sched_mod._renpho_consecutive_failures == 1


def test_renpho_sync_job_sends_alert_after_3_failures():
    with patch("scheduler.RenphoClientWrapper", side_effect=Exception("API error")), \
         patch("scheduler.send_alert") as mock_alert:
        sched_mod.renpho_sync_job()
        sched_mod.renpho_sync_job()
        sched_mod.renpho_sync_job()

    assert sched_mod._renpho_consecutive_failures == 3
    mock_alert.assert_called_once()
    alert_text = mock_alert.call_args[0][0]
    assert "3" in alert_text or "三" in alert_text


def test_renpho_sync_job_no_alert_before_3_failures():
    with patch("scheduler.RenphoClientWrapper", side_effect=Exception("fail")), \
         patch("scheduler.send_alert") as mock_alert:
        sched_mod.renpho_sync_job()
        sched_mod.renpho_sync_job()

    assert sched_mod._renpho_consecutive_failures == 2
    mock_alert.assert_not_called()


def test_renpho_sync_job_no_alert_after_3rd_failure():
    with patch("scheduler.RenphoClientWrapper", side_effect=Exception("fail")), \
         patch("scheduler.send_alert") as mock_alert:
        for _ in range(4):
            sched_mod.renpho_sync_job()
    mock_alert.assert_called_once()


def test_renpho_sync_job_counters_are_independent():
    """Garmin and Renpho failure counters do not affect each other."""
    with patch("scheduler.RenphoClientWrapper", side_effect=Exception("fail")), \
         patch("scheduler.send_alert"):
        sched_mod.renpho_sync_job()
        sched_mod.renpho_sync_job()

    assert sched_mod._garmin_consecutive_failures == 0
    assert sched_mod._renpho_consecutive_failures == 2
