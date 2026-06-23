import pytest
from unittest.mock import MagicMock, patch, call
import scheduler as sched_mod


@pytest.fixture(autouse=True)
def reset_failure_counter():
    sched_mod._consecutive_failures = 0
    yield
    sched_mod._consecutive_failures = 0


def _make_mock_garmin_client(sleep_raw=None, activities_raw=None):
    client = MagicMock()
    client.garmin = MagicMock()
    return client


def test_garmin_sync_job_resets_counter_on_success():
    sched_mod._consecutive_failures = 2
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

    assert sched_mod._consecutive_failures == 0


def test_garmin_sync_job_increments_counter_on_failure():
    with patch("scheduler.GarminClient", side_effect=Exception("Login failed")), \
         patch("scheduler.send_alert"):
        sched_mod.garmin_sync_job()

    assert sched_mod._consecutive_failures == 1


def test_garmin_sync_job_sends_alert_after_3_failures():
    with patch("scheduler.GarminClient", side_effect=Exception("Login failed")), \
         patch("scheduler.send_alert") as mock_alert:
        sched_mod.garmin_sync_job()
        sched_mod.garmin_sync_job()
        sched_mod.garmin_sync_job()

    assert sched_mod._consecutive_failures == 3
    mock_alert.assert_called_once()
    alert_text = mock_alert.call_args[0][0]
    assert "3" in alert_text or "三" in alert_text


def test_garmin_sync_job_no_alert_before_3_failures():
    with patch("scheduler.GarminClient", side_effect=Exception("fail")), \
         patch("scheduler.send_alert") as mock_alert:
        sched_mod.garmin_sync_job()
        sched_mod.garmin_sync_job()

    assert sched_mod._consecutive_failures == 2
    mock_alert.assert_not_called()


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


def test_create_scheduler_returns_scheduler_with_job():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = sched_mod.create_scheduler()
    assert isinstance(scheduler, BackgroundScheduler)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.trigger.__class__.__name__ == "CronTrigger"
