# Phase 4: Garmin 自动同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Garmin sync into a daily APScheduler job at 09:00 Asia/Shanghai that writes yesterday's sleep and activities to the database, with Telegram alerts after 3 consecutive failures.

**Architecture:** A new `garmin/db_sync.py` handles the DB write layer (UPSERT sleep, skip-duplicate activities). `notifications/telegram.py` sends async Telegram alerts via python-telegram-bot's Bot class. `scheduler.py` wires these together with APScheduler's `BackgroundScheduler`. `main.py` starts the scheduler alongside the bot.

**Tech Stack:** `APScheduler>=3.10`, `pytz`, existing `garmin/sync.py` + `garmin/client.py`, `db/base.py` (SessionLocal), `db/models.py` (Sleep, Activity), `config.py`

## Global Constraints

- Python 3.11+
- Credentials read exclusively from env vars via config.py — never hardcoded
- DB session pattern: `with SessionLocal() as session: … session.commit()`
- Test DB: SQLite in-memory (same pattern as tests/db/test_models.py)
- Sync cron: daily at 09:00 Asia/Shanghai (use pytz timezone)
- Alert threshold: 3 consecutive failures trigger Telegram notification
- Failure counter resets to 0 on successful sync
- `TELEGRAM_CHAT_ID` env var identifies who to alert
- Do NOT use PostgreSQL-specific SQL (e.g. `ON CONFLICT`) — use ORM-level check-then-upsert for cross-DB compatibility with test SQLite
- `garmin/sync.py` and its tests must NOT be modified — db_sync.py consumes their output as-is
- `parse_sleep` returns `sleep_date` as a string (`"YYYY-MM-DD"`), `sleep_start`/`sleep_end` as ISO strings — db_sync.py converts them to Python date/datetime before ORM insert
- `parse_activity` returns `activity_date` as a string (`"YYYY-MM-DD"`) — db_sync.py converts it

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add `APScheduler>=3.10`, `pytz` |
| `config.py` | Modify | Add `TELEGRAM_CHAT_ID` |
| `garmin/db_sync.py` | Create | `upsert_sleep`, `insert_activities` — DB write layer |
| `notifications/__init__.py` | Create | Package marker (empty) |
| `notifications/telegram.py` | Create | `send_alert(text)` — async Telegram message sender |
| `scheduler.py` | Create | `garmin_sync_job`, `_consecutive_failures` counter, `create_scheduler()` |
| `main.py` | Modify | Start scheduler alongside bot in `__main__` block |
| `tests/garmin/test_db_sync.py` | Create | Unit tests for upsert_sleep, insert_activities |
| `tests/test_scheduler.py` | Create | Unit tests for garmin_sync_job (mocked Garmin + DB) |

---

### Task 1: Dependencies + Config

**Files:**
- Modify: `requirements.txt`
- Modify: `config.py`

**Interfaces:**
- Produces: `config.TELEGRAM_CHAT_ID: str` — consumed by Tasks 3 and 4

- [ ] **Step 1: Write the failing test**

Create `tests/test_scheduler_config.py`:
```python
def test_telegram_chat_id_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    import importlib, config
    importlib.reload(config)
    assert config.TELEGRAM_CHAT_ID == "123456789"


def test_telegram_chat_id_default_empty(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    import importlib, config
    importlib.reload(config)
    assert config.TELEGRAM_CHAT_ID == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_scheduler_config.py -v
```
Expected: FAIL with `AssertionError` (TELEGRAM_CHAT_ID not in config)

- [ ] **Step 3: Add config var and dependencies**

Add to `config.py` (after ANTHROPIC_API_KEY):
```python
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
```

Add to `requirements.txt`:
```
APScheduler>=3.10,<4.0
pytz>=2024.1
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```
Expected: apscheduler and pytz importable

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_scheduler_config.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt config.py tests/test_scheduler_config.py
git commit -m "feat: add APScheduler/pytz deps and TELEGRAM_CHAT_ID config var"
```

---

### Task 2: garmin/db_sync.py — Database Write Layer

**Files:**
- Create: `garmin/db_sync.py`
- Create: `tests/garmin/test_db_sync.py`

**Interfaces:**
- Consumes:
  - `parse_sleep()` output: `{"sleep_date": "2026-06-21", "total_sleep_min": 450, "deep_sleep_min": 90, "light_sleep_min": 240, "rem_sleep_min": 90, "awake_min": 30, "sleep_score": 82, "resting_hr": 54, "sleep_start": "2026-06-21T23:00:00+00:00", "sleep_end": "2026-06-22T07:00:00+00:00"}`
  - `parse_activity()` output: `{"garmin_activity_id": 12345678, "activity_type": "running", "activity_date": "2026-06-21", "duration_min": 60, "calories_burned": 550, "avg_hr": 145, "max_hr": 175, "steps": 8200, "distance_km": 10.0, "hr_zone_1_min": 5, "hr_zone_2_min": 10, "hr_zone_3_min": 20, "hr_zone_4_min": 20, "hr_zone_5_min": 5}`
- Produces:
  - `upsert_sleep(session, parsed: dict) -> None` — UPSERT by sleep_date
  - `insert_activities(session, parsed_list: list[dict]) -> int` — skip existing garmin_activity_id, return count inserted

- [ ] **Step 1: Write failing tests**

Create `tests/garmin/test_db_sync.py`:
```python
import datetime
import pytest
from sqlalchemy.orm import sessionmaker
from db.base import get_engine, Base


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


PARSED_SLEEP = {
    "sleep_date": "2026-06-21",
    "total_sleep_min": 450,
    "deep_sleep_min": 90,
    "light_sleep_min": 240,
    "rem_sleep_min": 90,
    "awake_min": 30,
    "sleep_score": 82,
    "resting_hr": 54,
    "sleep_start": "2026-06-21T23:00:00+00:00",
    "sleep_end": "2026-06-22T07:00:00+00:00",
}

PARSED_ACTIVITY = {
    "garmin_activity_id": 11111111,
    "activity_type": "running",
    "activity_date": "2026-06-21",
    "duration_min": 60,
    "calories_burned": 550,
    "avg_hr": 145,
    "max_hr": 175,
    "steps": 8200,
    "distance_km": 10.0,
    "hr_zone_1_min": 5,
    "hr_zone_2_min": 10,
    "hr_zone_3_min": 20,
    "hr_zone_4_min": 20,
    "hr_zone_5_min": 5,
}


def test_upsert_sleep_inserts_new_record(session):
    from garmin.db_sync import upsert_sleep
    from db.models import Sleep
    upsert_sleep(session, PARSED_SLEEP)
    session.flush()
    result = session.query(Sleep).filter_by(
        sleep_date=datetime.date(2026, 6, 21)
    ).one()
    assert result.total_sleep_min == 450
    assert result.sleep_score == 82
    assert result.resting_hr == 54


def test_upsert_sleep_updates_existing_record(session):
    from garmin.db_sync import upsert_sleep
    from db.models import Sleep
    # Insert first
    upsert_sleep(session, PARSED_SLEEP)
    session.flush()
    # Update with new score
    updated = dict(PARSED_SLEEP, sleep_score=90, sleep_date="2026-06-21")
    upsert_sleep(session, updated)
    session.flush()
    results = session.query(Sleep).filter_by(
        sleep_date=datetime.date(2026, 6, 21)
    ).all()
    assert len(results) == 1  # no duplicate
    assert results[0].sleep_score == 90


def test_upsert_sleep_converts_string_dates(session):
    from garmin.db_sync import upsert_sleep
    from db.models import Sleep
    data = dict(PARSED_SLEEP, sleep_date="2026-06-20")
    upsert_sleep(session, data)
    session.flush()
    result = session.query(Sleep).filter_by(
        sleep_date=datetime.date(2026, 6, 20)
    ).one()
    assert isinstance(result.sleep_start, datetime.datetime)


def test_upsert_sleep_handles_none_timestamps(session):
    from garmin.db_sync import upsert_sleep
    from db.models import Sleep
    data = dict(PARSED_SLEEP, sleep_date="2026-06-19",
                sleep_start=None, sleep_end=None)
    upsert_sleep(session, data)
    session.flush()
    result = session.query(Sleep).filter_by(
        sleep_date=datetime.date(2026, 6, 19)
    ).one()
    assert result.sleep_start is None


def test_insert_activities_inserts_new(session):
    from garmin.db_sync import insert_activities
    count = insert_activities(session, [PARSED_ACTIVITY])
    session.flush()
    assert count == 1


def test_insert_activities_skips_existing(session):
    from garmin.db_sync import insert_activities
    from db.models import Activity
    # First insert
    insert_activities(session, [PARSED_ACTIVITY])
    session.flush()
    # Second insert — same garmin_activity_id
    count = insert_activities(session, [PARSED_ACTIVITY])
    session.flush()
    assert count == 0
    total = session.query(Activity).filter_by(
        garmin_activity_id=PARSED_ACTIVITY["garmin_activity_id"]
    ).count()
    assert total == 1  # still just one


def test_insert_activities_converts_date_string(session):
    from garmin.db_sync import insert_activities
    from db.models import Activity
    data = dict(PARSED_ACTIVITY, garmin_activity_id=22222222)
    insert_activities(session, [data])
    session.flush()
    result = session.query(Activity).filter_by(garmin_activity_id=22222222).one()
    assert isinstance(result.activity_date, datetime.date)


def test_insert_activities_returns_count_of_inserted(session):
    from garmin.db_sync import insert_activities
    activities = [
        dict(PARSED_ACTIVITY, garmin_activity_id=33333333),
        dict(PARSED_ACTIVITY, garmin_activity_id=44444444),
    ]
    count = insert_activities(session, activities)
    session.flush()
    assert count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/garmin/test_db_sync.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'garmin.db_sync'`

- [ ] **Step 3: Implement garmin/db_sync.py**

Create `garmin/db_sync.py`:
```python
import datetime
from db.models import Sleep, Activity


def _to_date(value) -> datetime.date | None:
    if value is None:
        return None
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def _to_datetime(value) -> datetime.datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(str(value))


def upsert_sleep(session, parsed: dict) -> None:
    sleep_date = _to_date(parsed.get("sleep_date"))
    existing = session.query(Sleep).filter_by(sleep_date=sleep_date).first()
    fields = {
        "sleep_date": sleep_date,
        "total_sleep_min": parsed.get("total_sleep_min"),
        "deep_sleep_min": parsed.get("deep_sleep_min"),
        "light_sleep_min": parsed.get("light_sleep_min"),
        "rem_sleep_min": parsed.get("rem_sleep_min"),
        "awake_min": parsed.get("awake_min"),
        "sleep_score": parsed.get("sleep_score"),
        "hrv_avg": parsed.get("hrv_avg"),
        "resting_hr": parsed.get("resting_hr"),
        "sleep_start": _to_datetime(parsed.get("sleep_start")),
        "sleep_end": _to_datetime(parsed.get("sleep_end")),
    }
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        session.add(Sleep(**fields))


def insert_activities(session, parsed_list: list[dict]) -> int:
    inserted = 0
    for parsed in parsed_list:
        gid = parsed.get("garmin_activity_id")
        if gid is not None:
            exists = session.query(Activity).filter_by(
                garmin_activity_id=gid
            ).first()
            if exists:
                continue
        session.add(Activity(
            garmin_activity_id=gid,
            activity_type=parsed.get("activity_type"),
            activity_date=_to_date(parsed.get("activity_date")),
            duration_min=parsed.get("duration_min"),
            calories_burned=parsed.get("calories_burned"),
            avg_hr=parsed.get("avg_hr"),
            max_hr=parsed.get("max_hr"),
            steps=parsed.get("steps"),
            distance_km=parsed.get("distance_km"),
            hr_zone_1_min=parsed.get("hr_zone_1_min"),
            hr_zone_2_min=parsed.get("hr_zone_2_min"),
            hr_zone_3_min=parsed.get("hr_zone_3_min"),
            hr_zone_4_min=parsed.get("hr_zone_4_min"),
            hr_zone_5_min=parsed.get("hr_zone_5_min"),
        ))
        inserted += 1
    return inserted
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/garmin/test_db_sync.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 5: Run full suite to check regressions**

```bash
pytest -v
```
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add garmin/db_sync.py tests/garmin/test_db_sync.py
git commit -m "feat: add garmin/db_sync.py with upsert_sleep and insert_activities"
```

---

### Task 3: notifications/telegram.py — Alert Sender

**Files:**
- Create: `notifications/__init__.py`
- Create: `notifications/telegram.py`

**Interfaces:**
- Consumes: `config.TELEGRAM_BOT_TOKEN`, `config.TELEGRAM_CHAT_ID`
- Produces: `send_alert(text: str) -> None` — sends Telegram message; no-ops silently if token/chat_id not set

- [ ] **Step 1: Write failing tests**

Create `tests/test_notifications.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_send_alert_calls_send_message(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    import importlib, config
    importlib.reload(config)

    mock_bot = MagicMock()
    mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
    mock_bot.__aexit__ = AsyncMock(return_value=False)
    mock_bot.send_message = AsyncMock()

    with patch("notifications.telegram.Bot", return_value=mock_bot):
        import importlib
        import notifications.telegram as notif
        importlib.reload(notif)
        notif.send_alert("⚠️ 测试告警")

    mock_bot.send_message.assert_called_once_with(
        chat_id="999", text="⚠️ 测试告警"
    )


def test_send_alert_noop_when_token_missing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    import importlib, config
    importlib.reload(config)

    with patch("notifications.telegram.Bot") as MockBot:
        import notifications.telegram as notif
        importlib.reload(notif)
        notif.send_alert("test")
        MockBot.assert_not_called()


def test_send_alert_noop_when_chat_id_missing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    import importlib, config
    importlib.reload(config)

    with patch("notifications.telegram.Bot") as MockBot:
        import notifications.telegram as notif
        importlib.reload(notif)
        notif.send_alert("test")
        MockBot.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_notifications.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'notifications'`

- [ ] **Step 3: Create notifications/__init__.py and notifications/telegram.py**

Create `notifications/__init__.py` (empty):
```python
```

Create `notifications/telegram.py`:
```python
import asyncio
from telegram import Bot
import config


async def _send(text: str) -> None:
    async with Bot(token=config.TELEGRAM_BOT_TOKEN) as bot:
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)


def send_alert(text: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    asyncio.run(_send(text))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_notifications.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Run full suite**

```bash
pytest -v
```
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add notifications/__init__.py notifications/telegram.py tests/test_notifications.py
git commit -m "feat: add notifications/telegram.py alert sender"
```

---

### Task 4: scheduler.py — Garmin Sync Job

**Files:**
- Create: `scheduler.py`
- Create: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `GarminClient`, `fetch_yesterday_sleep`, `fetch_yesterday_activities`, `parse_sleep`, `parse_activity`, `upsert_sleep`, `insert_activities`, `send_alert`, `SessionLocal`
- Produces:
  - `garmin_sync_job() -> None` — runs one sync cycle; increments `_consecutive_failures` on error; resets to 0 on success; calls `send_alert` after 3 failures
  - `create_scheduler() -> BackgroundScheduler` — cron job at 09:00 Asia/Shanghai
  - `_consecutive_failures: int` — module-level counter

- [ ] **Step 1: Write failing tests**

Create `tests/test_scheduler.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scheduler.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'scheduler'`

- [ ] **Step 3: Implement scheduler.py**

Create `scheduler.py`:
```python
import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from db.base import SessionLocal
from garmin.client import GarminClient
from garmin.sync import fetch_yesterday_sleep, fetch_yesterday_activities, parse_sleep, parse_activity
from garmin.db_sync import upsert_sleep, insert_activities
from notifications.telegram import send_alert

logger = logging.getLogger(__name__)

_consecutive_failures = 0


def garmin_sync_job() -> None:
    global _consecutive_failures
    try:
        client = GarminClient()
        client.connect()

        with SessionLocal() as session:
            raw_sleep = fetch_yesterday_sleep(client.garmin)
            parsed_sleep = parse_sleep(raw_sleep)
            if parsed_sleep.get("sleep_date"):
                upsert_sleep(session, parsed_sleep)

            raw_activities = fetch_yesterday_activities(client.garmin)
            parsed_activities = [parse_activity(a) for a in raw_activities]
            count = insert_activities(session, parsed_activities)
            session.commit()

        _consecutive_failures = 0
        logger.info("Garmin sync complete. Activities inserted: %d", count)

    except Exception as exc:
        _consecutive_failures += 1
        logger.error("Garmin sync failed (attempt %d): %s", _consecutive_failures, exc)
        if _consecutive_failures >= 3:
            send_alert(f"⚠️ Garmin 同步连续失败 {_consecutive_failures} 次：{exc}")


def create_scheduler() -> BackgroundScheduler:
    tz = pytz.timezone("Asia/Shanghai")
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(garmin_sync_job, "cron", hour=9, minute=0)
    return scheduler
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scheduler.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 5: Run full suite**

```bash
pytest -v
```
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add scheduler.py tests/test_scheduler.py
git commit -m "feat: add scheduler.py with garmin_sync_job and create_scheduler"
```

---

### Task 5: main.py — Integrate Scheduler

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `create_scheduler()` from `scheduler.py`
- Produces: updated `__main__` block that starts scheduler before `run_polling()`

- [ ] **Step 1: Write failing test**

Create `tests/test_main_scheduler.py`:
```python
def test_main_starts_scheduler(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import importlib, config
    importlib.reload(config)

    from unittest.mock import MagicMock, patch
    mock_scheduler = MagicMock()

    with patch("scheduler.create_scheduler", return_value=mock_scheduler) as mock_create, \
         patch("main.create_app") as mock_app:
        mock_app_instance = MagicMock()
        mock_app.return_value = mock_app_instance

        import main
        importlib.reload(main)
        # Simulate __main__ execution by calling the function directly
        main._run()

    mock_create.assert_called_once()
    mock_scheduler.start.assert_called_once()
    mock_app_instance.run_polling.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_main_scheduler.py -v
```
Expected: FAIL with `AttributeError: module 'main' has no attribute '_run'`

- [ ] **Step 3: Update main.py**

Modify `main.py` to extract the startup logic into `_run()` for testability:
```python
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import config
from bot.handlers import (
    handle_photo,
    handle_text,
    cmd_today,
    cmd_note,
    cmd_week,
    cmd_status,
)
from scheduler import create_scheduler


def create_app() -> Application:
    if not config.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set")
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("note", cmd_note))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("status", cmd_status))
    return app


def _run() -> None:
    scheduler = create_scheduler()
    scheduler.start()
    create_app().run_polling()


if __name__ == "__main__":
    _run()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main_scheduler.py -v && pytest tests/test_main.py -v
```
Expected: Both pass

- [ ] **Step 5: Run full suite**

```bash
pytest -v
```
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main_scheduler.py
git commit -m "feat: integrate scheduler into main.py startup"
```

---

## Self-Review

### Spec Coverage

| PRD Requirement | Covered by |
|----------------|------------|
| Railway Cron 09:00 Asia/Shanghai | Task 4 `create_scheduler` with CronTrigger |
| 拉取前一天睡眠 + 活动 | Task 4 `garmin_sync_job` → fetch_yesterday_* |
| sleep UPSERT (sleep_date UNIQUE) | Task 2 `upsert_sleep` |
| activity INSERT skip-duplicate (garmin_activity_id) | Task 2 `insert_activities` |
| 3次失败 → Telegram 告警 | Task 4 `_consecutive_failures` counter |
| 失败后重置计数器 | Task 4 success path resets to 0 |
| 登录凭证从环境变量 | Task 1 config; existing garmin/client.py |
| garmin/sync.py 未修改 | Only db_sync.py is new |
| TELEGRAM_CHAT_ID | Task 1 + Task 3 |

### Placeholder Scan
None found.

### Type Consistency
- `upsert_sleep(session, parsed: dict) -> None` — used in Task 2 and Task 4
- `insert_activities(session, parsed_list: list[dict]) -> int` — used in Task 2 and Task 4
- `send_alert(text: str) -> None` — Task 3 definition, Task 4 call
- `create_scheduler() -> BackgroundScheduler` — Task 4 definition, Task 5 call
- `garmin_sync_job() -> None` — Task 4 definition, tested in Task 4
