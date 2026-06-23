# Phase 5 Renpho 体重体脂数据同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每天 09:00 自动从 Renpho 云端拉取最新体重体脂数据并写入 `body_metrics` 表，连续失败 3 次时通过 Telegram 发送告警。

**Architecture:** 参照 Garmin 模块结构：`renpho/client.py` 封装 RenphoClient（读 env），`renpho/sync.py` 负责拉取 + 解析，`renpho/db_sync.py` 负责去重写库；`scheduler.py` 新增独立的 `renpho_sync_job`，与 `garmin_sync_job` 并列挂在同一个 09:00 cron 上。

**Tech Stack:** Python 3.11+, renpho-api==0.1.0 (from renpho import RenphoClient, RenphoAPIError), SQLAlchemy ORM, pytest, pytest-mock

## Global Constraints

- Python 3.11+；所有凭证只从环境变量读取，绝不硬编码
- 数据库 Session 模式：`with SessionLocal() as session: … session.commit()`
- 测试用 SQLite in-memory（`sqlite:///:memory:`），生产用 PostgreSQL
- 告警文本为中文；告警逻辑：`_renpho_consecutive_failures == 3` 时发一次告警（等于 3，不是大于等于）
- 所有 import 放在文件顶部（PEP 8）
- renpho-api 导入路径：`from renpho import RenphoClient, RenphoAPIError`
- `body_metrics` 表的 ORM 模型是 `db.models.BodyMetric`（已存在，无需迁移）
- 去重字段：`renpho_record_id`（VARCHAR 64 UNIQUE），值为 `str(raw.get("id") or raw.get("timeStamp", ""))[:64]`
- `measured_at` 必须是 timezone-aware datetime（UTC）
- 每次同步拉取过去 7 天内的测量记录（过滤 timeStamp），新记录插入，已存在的跳过
- 每个 scheduler job 有各自独立的 failure counter（`_garmin_consecutive_failures`、`_renpho_consecutive_failures`）
- `create_scheduler()` 注册两个 cron job（garmin + renpho），`get_jobs()` 返回 2 个

---

## File Structure

**新建文件：**
- `renpho/__init__.py` — 空包标记
- `renpho/client.py` — RenphoClient 封装，读 config.RENPHO_EMAIL / RENPHO_PASSWORD
- `renpho/sync.py` — `fetch_recent_measurements(client)` + `parse_measurement(raw)`
- `renpho/db_sync.py` — `insert_body_metrics(session, parsed_list) -> int`
- `tests/renpho/__init__.py` — 空包标记
- `tests/renpho/test_sync.py` — sync 层单元测试
- `tests/renpho/test_db_sync.py` — DB 写层单元测试

**修改文件：**
- `config.py` — 新增 `RENPHO_EMAIL`、`RENPHO_PASSWORD`
- `requirements.txt` — 新增 `renpho-api==0.1.0`
- `scheduler.py` — 重命名现有 `_consecutive_failures` → `_garmin_consecutive_failures`；新增 `_renpho_consecutive_failures` + `renpho_sync_job()`；更新 `create_scheduler()` 挂两个 job
- `tests/test_scheduler.py` — 适配 renamed counter，更新 `test_create_scheduler_returns_scheduler_with_job` 断言 2 个 job，新增 renpho_sync_job 测试

---

### Task 1: Config + Dependencies

**Files:**
- Modify: `config.py`
- Modify: `requirements.txt`
- Modify: `tests/db/test_config_db.py` (新增 renpho env var 测试)

**Interfaces:**
- Produces:
  - `config.RENPHO_EMAIL: str`
  - `config.RENPHO_PASSWORD: str`

- [ ] **Step 1: 写失败测试**

在 `tests/db/test_config_db.py` 末尾追加：

```python
def test_renpho_email_from_env(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "test@renpho.com")
    import importlib, config
    importlib.reload(config)
    assert config.RENPHO_EMAIL == "test@renpho.com"


def test_renpho_password_from_env(monkeypatch):
    monkeypatch.setenv("RENPHO_PASSWORD", "secret")
    import importlib, config
    importlib.reload(config)
    assert config.RENPHO_PASSWORD == "secret"


def test_renpho_email_default_empty(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "")
    import importlib, config
    importlib.reload(config)
    assert config.RENPHO_EMAIL == ""
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/zuoyuguo/Projects/health-tracker
pytest tests/db/test_config_db.py::test_renpho_email_from_env -v
```

Expected: FAIL with `AttributeError: module 'config' has no attribute 'RENPHO_EMAIL'`

- [ ] **Step 3: 更新 config.py**

在 `config.py` 现有内容后追加两行：

```python
RENPHO_EMAIL = os.getenv("RENPHO_EMAIL", "")
RENPHO_PASSWORD = os.getenv("RENPHO_PASSWORD", "")
```

完整 `config.py`：

```python
import os
from dotenv import load_dotenv

load_dotenv()

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")
GARMIN_TOKEN_PATH = os.getenv("GARMINTOKENS", os.path.expanduser("~/.garmin_tokens"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
RENPHO_EMAIL = os.getenv("RENPHO_EMAIL", "")
RENPHO_PASSWORD = os.getenv("RENPHO_PASSWORD", "")
```

- [ ] **Step 4: 更新 requirements.txt**

在 `requirements.txt` 末尾追加：

```
renpho-api==0.1.0
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/db/test_config_db.py -v
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add config.py requirements.txt tests/db/test_config_db.py
git commit -m "feat(renpho): add RENPHO_EMAIL/PASSWORD config and renpho-api dependency"
```

---

### Task 2: renpho/client.py

**Files:**
- Create: `renpho/__init__.py`
- Create: `renpho/client.py`

**Interfaces:**
- Consumes: `config.RENPHO_EMAIL`, `config.RENPHO_PASSWORD`
- Produces:
  - `class RenphoClientWrapper` with method `connect() -> None` and attribute `client: RenphoClient`

> Note: `RenphoClient` from renpho-api uses `client.login()` to authenticate and stores token internally. `get_all_measurements()` auto-calls login if no token.

- [ ] **Step 1: 创建 renpho/__init__.py**

创建空文件 `renpho/__init__.py`（内容为空）。

- [ ] **Step 2: 写失败测试**

创建 `tests/renpho/__init__.py`（空文件）。

创建 `tests/renpho/test_client.py`：

```python
import pytest
from unittest.mock import patch, MagicMock


def test_renpho_client_wrapper_connect_calls_login(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "user@test.com")
    monkeypatch.setenv("RENPHO_PASSWORD", "pw")
    import importlib, config
    importlib.reload(config)

    mock_renpho = MagicMock()
    with patch("renpho.client.RenphoClient", return_value=mock_renpho) as MockClass:
        import importlib
        import renpho.client as rc
        importlib.reload(rc)
        wrapper = rc.RenphoClientWrapper()
        wrapper.connect()

    MockClass.assert_called_once_with("user@test.com", "pw")
    mock_renpho.login.assert_called_once()
    assert wrapper.client is mock_renpho


def test_renpho_client_wrapper_raises_on_missing_email(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "")
    monkeypatch.setenv("RENPHO_PASSWORD", "pw")
    import importlib, config
    importlib.reload(config)

    import importlib
    import renpho.client as rc
    importlib.reload(rc)
    wrapper = rc.RenphoClientWrapper()
    with pytest.raises(ValueError, match="RENPHO_EMAIL"):
        wrapper.connect()


def test_renpho_client_wrapper_raises_on_missing_password(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "user@test.com")
    monkeypatch.setenv("RENPHO_PASSWORD", "")
    import importlib, config
    importlib.reload(config)

    import importlib
    import renpho.client as rc
    importlib.reload(rc)
    wrapper = rc.RenphoClientWrapper()
    with pytest.raises(ValueError, match="RENPHO_PASSWORD"):
        wrapper.connect()
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
pytest tests/renpho/test_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'renpho.client'`

- [ ] **Step 4: 实现 renpho/client.py**

```python
from renpho import RenphoClient
import config


class RenphoClientWrapper:
    def __init__(self):
        self.client = None

    def connect(self) -> None:
        if not config.RENPHO_EMAIL:
            raise ValueError("RENPHO_EMAIL is not set")
        if not config.RENPHO_PASSWORD:
            raise ValueError("RENPHO_PASSWORD is not set")
        self.client = RenphoClient(config.RENPHO_EMAIL, config.RENPHO_PASSWORD)
        self.client.login()
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/renpho/test_client.py -v
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add renpho/__init__.py renpho/client.py tests/renpho/__init__.py tests/renpho/test_client.py
git commit -m "feat(renpho): add RenphoClientWrapper"
```

---

### Task 3: renpho/sync.py — 拉取 + 解析

**Files:**
- Create: `renpho/sync.py`
- Test: `tests/renpho/test_sync.py`

**Interfaces:**
- Consumes:
  - `wrapper.client: RenphoClient` (from Task 2)
- Produces:
  - `fetch_recent_measurements(client: RenphoClient, days: int = 7) -> list[dict]`
    — 调用 `client.get_all_measurements()`，过滤 `timeStamp` 在最近 `days` 天内的记录，返回 list
  - `parse_measurement(raw: dict) -> dict`
    — 把一条 Renpho 原始 dict 转为 DB 字段 dict，字段见下方

**parse_measurement 输出字段：**

```python
{
    "renpho_record_id": str,       # str(raw.get("id") or raw.get("timeStamp", ""))[:64]
    "measured_at": datetime,       # timezone-aware UTC datetime
    "weight_kg": float | None,     # raw.get("weight")
    "bmi": float | None,           # raw.get("bmi")
    "body_fat_pct": float | None,  # raw.get("bodyfat")
    "fat_mass_kg": float | None,   # raw.get("bodyfat_mass")  # None if absent
    "lean_mass_kg": float | None,  # raw.get("sinew") or raw.get("lbm")
    "muscle_mass_kg": float | None,# raw.get("muscle_mass")  # None if absent
    "bone_mass_kg": float | None,  # raw.get("bone_mass")    # None if absent
    "water_pct": float | None,     # raw.get("water")
    "visceral_fat": float | None,  # raw.get("visfat")
    "bmr_kcal": int | None,        # int(raw["bmr"]) if raw.get("bmr") else None
}
```

**timeStamp 转换规则：**
- 如果 `timeStamp > 1e12`，则是毫秒，除以 1000 得秒
- `datetime.datetime.fromtimestamp(ts_seconds, tz=datetime.timezone.utc)`

- [ ] **Step 1: 写失败测试**

创建 `tests/renpho/test_sync.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/renpho/test_sync.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'renpho.sync'`

- [ ] **Step 3: 实现 renpho/sync.py**

```python
import datetime
from renpho import RenphoClient


def fetch_recent_measurements(client: RenphoClient, days: int = 7) -> list[dict]:
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    cutoff_ts = cutoff.timestamp()

    all_measurements = client.get_all_measurements()
    result = []
    for m in all_measurements:
        ts = m.get("timeStamp")
        if ts is None:
            continue
        ts_sec = ts / 1000 if ts > 1e12 else ts
        if ts_sec >= cutoff_ts:
            result.append(m)
    return result


def parse_measurement(raw: dict) -> dict:
    ts = raw.get("timeStamp", 0)
    ts_sec = ts / 1000 if ts > 1e12 else ts
    measured_at = datetime.datetime.fromtimestamp(ts_sec, tz=datetime.timezone.utc)

    record_id = raw.get("id") or raw.get("timeStamp", "")
    renpho_record_id = str(record_id)[:64]

    bmr_raw = raw.get("bmr")
    bmr_kcal = int(bmr_raw) if bmr_raw is not None else None

    return {
        "renpho_record_id": renpho_record_id,
        "measured_at": measured_at,
        "weight_kg": raw.get("weight"),
        "bmi": raw.get("bmi"),
        "body_fat_pct": raw.get("bodyfat"),
        "fat_mass_kg": raw.get("bodyfat_mass"),
        "lean_mass_kg": raw.get("sinew") or raw.get("lbm"),
        "muscle_mass_kg": raw.get("muscle_mass"),
        "bone_mass_kg": raw.get("bone_mass"),
        "water_pct": raw.get("water"),
        "visceral_fat": raw.get("visfat"),
        "bmr_kcal": bmr_kcal,
    }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/renpho/test_sync.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add renpho/sync.py tests/renpho/test_sync.py
git commit -m "feat(renpho): add fetch_recent_measurements and parse_measurement"
```

---

### Task 4: renpho/db_sync.py — DB 写层

**Files:**
- Create: `renpho/db_sync.py`
- Test: `tests/renpho/test_db_sync.py`

**Interfaces:**
- Consumes:
  - `parse_measurement` 输出的 dict（见 Task 3）
  - `db.models.BodyMetric` ORM 类（已存在）
- Produces:
  - `insert_body_metrics(session, parsed_list: list[dict]) -> int`
    — 遍历 parsed_list，按 `renpho_record_id` 去重，新记录插入，已存在跳过；返回插入条数

- [ ] **Step 1: 写失败测试**

创建 `tests/renpho/test_db_sync.py`：

```python
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.base import Base
from db.models import BodyMetric


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _parsed(record_id="rec1", ts=None):
    if ts is None:
        ts = datetime.datetime(2026, 6, 22, 12, 0, 0, tzinfo=datetime.timezone.utc)
    return {
        "renpho_record_id": record_id,
        "measured_at": ts,
        "weight_kg": 70.5,
        "bmi": 22.1,
        "body_fat_pct": 18.3,
        "fat_mass_kg": None,
        "lean_mass_kg": 57.6,
        "muscle_mass_kg": None,
        "bone_mass_kg": None,
        "water_pct": 55.0,
        "visceral_fat": 6.0,
        "bmr_kcal": 1650,
    }


def test_insert_body_metrics_inserts_new_record(session):
    from renpho.db_sync import insert_body_metrics

    count = insert_body_metrics(session, [_parsed("r1")])
    session.commit()

    assert count == 1
    row = session.query(BodyMetric).filter_by(renpho_record_id="r1").first()
    assert row is not None
    assert float(row.weight_kg) == 70.5
    assert float(row.bmi) == 22.1
    assert float(row.body_fat_pct) == 18.3
    assert float(row.lean_mass_kg) == 57.6
    assert float(row.water_pct) == 55.0
    assert float(row.visceral_fat) == 6.0
    assert row.bmr_kcal == 1650
    assert row.fat_mass_kg is None
    assert row.muscle_mass_kg is None
    assert row.bone_mass_kg is None


def test_insert_body_metrics_skips_existing_record(session):
    from renpho.db_sync import insert_body_metrics

    insert_body_metrics(session, [_parsed("r1")])
    session.commit()

    count2 = insert_body_metrics(session, [_parsed("r1")])
    session.commit()

    assert count2 == 0
    assert session.query(BodyMetric).count() == 1


def test_insert_body_metrics_inserts_multiple_new(session):
    from renpho.db_sync import insert_body_metrics

    records = [_parsed("r1"), _parsed("r2"), _parsed("r3")]
    count = insert_body_metrics(session, records)
    session.commit()

    assert count == 3
    assert session.query(BodyMetric).count() == 3


def test_insert_body_metrics_partial_new_and_existing(session):
    from renpho.db_sync import insert_body_metrics

    insert_body_metrics(session, [_parsed("r1")])
    session.commit()

    count = insert_body_metrics(session, [_parsed("r1"), _parsed("r2")])
    session.commit()

    assert count == 1
    assert session.query(BodyMetric).count() == 2


def test_insert_body_metrics_returns_zero_for_empty_list(session):
    from renpho.db_sync import insert_body_metrics

    count = insert_body_metrics(session, [])
    assert count == 0


def test_insert_body_metrics_skips_when_record_id_is_empty(session):
    from renpho.db_sync import insert_body_metrics

    parsed = _parsed("")
    count = insert_body_metrics(session, [parsed])
    session.commit()
    assert count == 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/renpho/test_db_sync.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'renpho.db_sync'`

- [ ] **Step 3: 实现 renpho/db_sync.py**

```python
from db.models import BodyMetric


def insert_body_metrics(session, parsed_list: list[dict]) -> int:
    inserted = 0
    for parsed in parsed_list:
        record_id = parsed.get("renpho_record_id", "")
        if not record_id:
            continue
        exists = session.query(BodyMetric).filter_by(
            renpho_record_id=record_id
        ).first()
        if exists:
            continue
        session.add(BodyMetric(
            renpho_record_id=record_id,
            measured_at=parsed["measured_at"],
            weight_kg=parsed.get("weight_kg"),
            bmi=parsed.get("bmi"),
            body_fat_pct=parsed.get("body_fat_pct"),
            fat_mass_kg=parsed.get("fat_mass_kg"),
            lean_mass_kg=parsed.get("lean_mass_kg"),
            muscle_mass_kg=parsed.get("muscle_mass_kg"),
            bone_mass_kg=parsed.get("bone_mass_kg"),
            water_pct=parsed.get("water_pct"),
            visceral_fat=parsed.get("visceral_fat"),
            bmr_kcal=parsed.get("bmr_kcal"),
        ))
        inserted += 1
    return inserted
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/renpho/test_db_sync.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add renpho/db_sync.py tests/renpho/test_db_sync.py
git commit -m "feat(renpho): add insert_body_metrics DB write layer"
```

---

### Task 5: scheduler.py — 新增 renpho_sync_job + 更新测试

**Files:**
- Modify: `scheduler.py`
- Modify: `tests/test_scheduler.py`

**Interfaces:**
- Consumes:
  - `renpho.client.RenphoClientWrapper` (Task 2)
  - `renpho.sync.fetch_recent_measurements`, `parse_measurement` (Task 3)
  - `renpho.db_sync.insert_body_metrics` (Task 4)
  - `notifications.telegram.send_alert` (已存在)
- Produces: `renpho_sync_job() -> None`（独立 failure counter，== 3 时发告警）；`create_scheduler()` 注册两个 job

> 注意：`scheduler.py` 中现有的 `_consecutive_failures` 变量需重命名为 `_garmin_consecutive_failures`，同时更新 `garmin_sync_job` 内的 `global` 声明和所有引用。

- [ ] **Step 1: 写失败测试**

在 `tests/test_scheduler.py` 中：

1. 将所有 `sched_mod._consecutive_failures` 替换为 `sched_mod._garmin_consecutive_failures`
2. 将 fixture `reset_failure_counter` 更新为同时重置两个 counter
3. 将 `test_create_scheduler_returns_scheduler_with_job` 更新为断言 2 个 job
4. 在文件末尾追加 renpho job 测试

**完整更新后的 `tests/test_scheduler.py`：**

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_scheduler.py -v
```

Expected: FAIL（多个失败：`_garmin_consecutive_failures` 不存在、`renpho_sync_job` 不存在、job 数量断言失败）

- [ ] **Step 3: 更新 scheduler.py**

```python
import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from db.base import SessionLocal
from garmin.client import GarminClient
from garmin.sync import fetch_yesterday_sleep, fetch_yesterday_activities, parse_sleep, parse_activity
from garmin.db_sync import upsert_sleep, insert_activities
from renpho.client import RenphoClientWrapper
from renpho.sync import fetch_recent_measurements, parse_measurement
from renpho.db_sync import insert_body_metrics
from notifications.telegram import send_alert

logger = logging.getLogger(__name__)

_garmin_consecutive_failures = 0
_renpho_consecutive_failures = 0


def garmin_sync_job() -> None:
    global _garmin_consecutive_failures
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

        _garmin_consecutive_failures = 0
        logger.info("Garmin sync complete. Activities inserted: %d", count)

    except Exception as exc:
        _garmin_consecutive_failures += 1
        logger.error("Garmin sync failed (attempt %d): %s", _garmin_consecutive_failures, exc)
        if _garmin_consecutive_failures == 3:
            send_alert(f"⚠️ Garmin 同步连续失败 {_garmin_consecutive_failures} 次：{exc}")


def renpho_sync_job() -> None:
    global _renpho_consecutive_failures
    try:
        wrapper = RenphoClientWrapper()
        wrapper.connect()

        with SessionLocal() as session:
            raw_list = fetch_recent_measurements(wrapper.client)
            parsed_list = [parse_measurement(m) for m in raw_list]
            count = insert_body_metrics(session, parsed_list)
            session.commit()

        _renpho_consecutive_failures = 0
        logger.info("Renpho sync complete. Body metrics inserted: %d", count)

    except Exception as exc:
        _renpho_consecutive_failures += 1
        logger.error("Renpho sync failed (attempt %d): %s", _renpho_consecutive_failures, exc)
        if _renpho_consecutive_failures == 3:
            send_alert(f"⚠️ Renpho 同步连续失败 {_renpho_consecutive_failures} 次：{exc}")


def create_scheduler() -> BackgroundScheduler:
    tz = pytz.timezone("Asia/Shanghai")
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(garmin_sync_job, "cron", hour=9, minute=0, max_instances=1)
    scheduler.add_job(renpho_sync_job, "cron", hour=9, minute=0, max_instances=1)
    return scheduler
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_scheduler.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: 运行全套测试，确认无回归**

```bash
pytest --tb=short -q
```

Expected: 全部 PASS（原有 89 条 + 新增测试）

- [ ] **Step 6: Commit**

```bash
git add scheduler.py tests/test_scheduler.py
git commit -m "feat(renpho): add renpho_sync_job to scheduler, rename garmin failure counter"
```
