# Phase 1: Garmin Data Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 Garmin 账号数据可访问性 — 能成功拉取昨日睡眠和活动数据并打印到控制台。

**Architecture:** 三层结构：`session.py` 管理 Token 文件路径，`client.py` 封装 garminconnect 登录逻辑（含 Token 持久化），`sync.py` 负责拉取原始数据并解析为干净的 Python dict（字段与 PRD DB 表对齐）。`verify_garmin.py` 是可执行的验证脚本。

**Tech Stack:** Python 3.12, garminconnect==0.3.6, python-dotenv, pytest, pytest-mock

## Global Constraints

- Python 3.11+（当前环境 3.12.4）
- garminconnect==0.3.6（已安装）
- 凭证必须从环境变量读取，禁止硬编码：`GARMIN_EMAIL`, `GARMIN_PASSWORD`
- Token 持久化路径：`GARMINTOKENS` 环境变量（默认 `~/.garmin_tokens`）
- 所有日期字符串格式：`YYYY-MM-DD`
- 时区：Garmin 返回 GMT，保留原始值（Phase 2 写库时再转 UTC）
- 不写数据库（Phase 2 才做），只解析打印

---

## File Map

| 文件 | 职责 |
|------|------|
| `requirements.txt` | 项目依赖 |
| `.env.example` | 环境变量模板 |
| `config.py` | 从环境变量读取配置，统一入口 |
| `garmin/__init__.py` | 空文件，使 garmin 成为 package |
| `garmin/session.py` | Token 文件路径解析，唯一职责 |
| `garmin/client.py` | 封装 garminconnect.Garmin，处理登录 + Token 持久化 |
| `garmin/sync.py` | 拉取昨日睡眠 + 活动数据，解析为 dict |
| `verify_garmin.py` | CLI 验证脚本，打印数据 |
| `tests/__init__.py` | 空文件 |
| `tests/garmin/test_session.py` | session.py 单元测试 |
| `tests/garmin/test_client.py` | client.py 单元测试（mock garminconnect） |
| `tests/garmin/test_sync.py` | sync.py 解析函数单元测试（mock client） |

---

## Task 1: 项目基础设施（依赖、配置、环境变量）

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.py`
- Create: `tests/__init__.py`
- Create: `garmin/__init__.py`
- Create: `tests/garmin/__init__.py`

**Interfaces:**
- Produces:
  - `config.GARMIN_EMAIL: str`
  - `config.GARMIN_PASSWORD: str`
  - `config.GARMIN_TOKEN_PATH: str`  （默认 `~/.garmin_tokens`）

- [ ] **Step 1: 创建 requirements.txt**

```text
garminconnect==0.3.6
python-dotenv==1.0.1
pytest==8.3.5
pytest-mock==3.14.0
```

- [ ] **Step 2: 安装依赖**

```bash
pip3 install -r requirements.txt
```

Expected: 全部安装成功，无报错。

- [ ] **Step 3: 创建 .env.example**

```env
GARMIN_EMAIL=your@email.com
GARMIN_PASSWORD=yourpassword
GARMINTOKENS=~/.garmin_tokens
```

- [ ] **Step 4: 写 config.py 的失败测试**

创建 `tests/__init__.py`（空文件），`tests/garmin/__init__.py`（空文件），然后创建：

```python
# tests/garmin/test_config.py
import os
import pytest


def test_garmin_email_from_env(monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret")
    # 重新 import 以读取新 env
    import importlib
    import config
    importlib.reload(config)
    assert config.GARMIN_EMAIL == "test@example.com"
    assert config.GARMIN_PASSWORD == "secret"


def test_garmin_token_path_default(monkeypatch):
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    import importlib
    import config
    importlib.reload(config)
    assert config.GARMIN_TOKEN_PATH.endswith(".garmin_tokens")


def test_garmin_token_path_from_env(monkeypatch):
    monkeypatch.setenv("GARMINTOKENS", "/tmp/my_tokens")
    import importlib
    import config
    importlib.reload(config)
    assert config.GARMIN_TOKEN_PATH == "/tmp/my_tokens"
```

- [ ] **Step 5: 运行测试，确认失败**

```bash
cd /Users/zuoyuguo/Projects/health-tracker
pytest tests/garmin/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 6: 实现 config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")
GARMIN_TOKEN_PATH = os.getenv("GARMINTOKENS", os.path.expanduser("~/.garmin_tokens"))
```

- [ ] **Step 7: 创建空 package 文件**

创建 `garmin/__init__.py`（空文件）。

- [ ] **Step 8: 运行测试，确认通过**

```bash
pytest tests/garmin/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 9: Commit**

```bash
git init
git add requirements.txt .env.example config.py garmin/__init__.py tests/__init__.py tests/garmin/__init__.py tests/garmin/test_config.py
git commit -m "feat: project bootstrap — deps, config, env"
```

---

## Task 2: garmin/session.py — Token 路径管理

**Files:**
- Create: `garmin/session.py`
- Test: `tests/garmin/test_session.py`

**Interfaces:**
- Consumes: `config.GARMIN_TOKEN_PATH: str`
- Produces:
  - `garmin.session.get_token_path() -> str`  （返回展开后的绝对路径）

- [ ] **Step 1: 写失败测试**

```python
# tests/garmin/test_session.py
import os
import pytest
from garmin.session import get_token_path


def test_get_token_path_returns_string():
    path = get_token_path()
    assert isinstance(path, str)
    assert len(path) > 0


def test_get_token_path_no_tilde(monkeypatch):
    monkeypatch.setenv("GARMINTOKENS", "~/custom_tokens")
    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)
    path = session.get_token_path()
    assert "~" not in path
    assert os.path.isabs(path)


def test_get_token_path_uses_config(monkeypatch):
    monkeypatch.setenv("GARMINTOKENS", "/tmp/test_tokens")
    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)
    assert session.get_token_path() == "/tmp/test_tokens"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/garmin/test_session.py -v
```

Expected: `ImportError: cannot import name 'get_token_path'`

- [ ] **Step 3: 实现 garmin/session.py**

```python
import os
import config


def get_token_path() -> str:
    return os.path.expanduser(config.GARMIN_TOKEN_PATH)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/garmin/test_session.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add garmin/session.py tests/garmin/test_session.py
git commit -m "feat: garmin session token path management"
```

---

## Task 3: garmin/client.py — 封装登录逻辑

**Files:**
- Create: `garmin/client.py`
- Test: `tests/garmin/test_client.py`

**Interfaces:**
- Consumes: `config.GARMIN_EMAIL`, `config.GARMIN_PASSWORD`, `garmin.session.get_token_path()`
- Produces:
  - `garmin.client.GarminClient` 类
  - `GarminClient.connect() -> None`  （登录，持久化 token）
  - `GarminClient.garmin: garminconnect.Garmin`  （可直接调用 API 的实例）

- [ ] **Step 1: 写失败测试**

```python
# tests/garmin/test_client.py
import pytest
from unittest.mock import MagicMock, patch, call


def make_mock_garmin():
    mock = MagicMock()
    mock.login.return_value = (None, None)  # 成功登录返回 (None, None)
    return mock


def test_connect_calls_login_with_token_path(tmp_path, monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret")
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))

    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)

    mock_garmin_instance = make_mock_garmin()

    with patch("garmin.client.garminconnect.Garmin", return_value=mock_garmin_instance):
        import garmin.client as client_mod
        importlib.reload(client_mod)
        client = client_mod.GarminClient()
        client.connect()

    mock_garmin_instance.login.assert_called_once_with(
        tokenstore=str(tmp_path / "tokens")
    )


def test_connect_passes_credentials_to_garmin(tmp_path, monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "user@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pass123")
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))

    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)

    mock_garmin_instance = make_mock_garmin()

    with patch("garmin.client.garminconnect.Garmin") as MockGarmin:
        MockGarmin.return_value = mock_garmin_instance
        import garmin.client as client_mod
        importlib.reload(client_mod)
        client = client_mod.GarminClient()
        client.connect()
        MockGarmin.assert_called_once_with(
            email="user@example.com",
            password="pass123",
        )


def test_garmin_attribute_is_accessible_after_connect(tmp_path, monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret")
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))

    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)

    mock_garmin_instance = make_mock_garmin()

    with patch("garmin.client.garminconnect.Garmin", return_value=mock_garmin_instance):
        import garmin.client as client_mod
        importlib.reload(client_mod)
        client = client_mod.GarminClient()
        client.connect()

    assert client.garmin is mock_garmin_instance


def test_connect_raises_on_login_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "wrong")
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))

    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)

    mock_garmin_instance = make_mock_garmin()
    mock_garmin_instance.login.side_effect = Exception("GarminConnectAuthenticationError")

    with patch("garmin.client.garminconnect.Garmin", return_value=mock_garmin_instance):
        import garmin.client as client_mod
        importlib.reload(client_mod)
        client = client_mod.GarminClient()
        with pytest.raises(Exception, match="GarminConnectAuthenticationError"):
            client.connect()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/garmin/test_client.py -v
```

Expected: `ImportError: cannot import name 'GarminClient'`

- [ ] **Step 3: 实现 garmin/client.py**

```python
import garminconnect
import config
from garmin.session import get_token_path


class GarminClient:
    def __init__(self):
        self.garmin = None

    def connect(self) -> None:
        self.garmin = garminconnect.Garmin(
            email=config.GARMIN_EMAIL,
            password=config.GARMIN_PASSWORD,
        )
        self.garmin.login(tokenstore=get_token_path())
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/garmin/test_client.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add garmin/client.py tests/garmin/test_client.py
git commit -m "feat: garmin client with token-persistent login"
```

---

## Task 4: garmin/sync.py — 数据拉取与解析

**Files:**
- Create: `garmin/sync.py`
- Test: `tests/garmin/test_sync.py`

**Interfaces:**
- Consumes: `garmin.client.GarminClient`（已 connect）
- Produces:
  - `garmin.sync.fetch_yesterday_sleep(garmin: garminconnect.Garmin) -> dict`
  - `garmin.sync.fetch_yesterday_activities(garmin: garminconnect.Garmin) -> list[dict]`
  - `garmin.sync.parse_sleep(raw: dict) -> dict`  — 解析为 PRD sleep 表字段
  - `garmin.sync.parse_activity(raw: dict) -> dict`  — 解析为 PRD activities 表字段

解析后的 sleep dict 字段：
```
sleep_date, total_sleep_min, deep_sleep_min, light_sleep_min,
rem_sleep_min, awake_min, sleep_score, resting_hr,
sleep_start, sleep_end
```

解析后的 activity dict 字段：
```
garmin_activity_id, activity_type, activity_date,
duration_min, calories_burned, avg_hr, max_hr,
steps, distance_km,
hr_zone_1_min, hr_zone_2_min, hr_zone_3_min, hr_zone_4_min, hr_zone_5_min
```

- [ ] **Step 1: 定义测试 fixture 数据**

创建 `tests/garmin/test_sync.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/garmin/test_sync.py -v
```

Expected: `ImportError: cannot import name 'fetch_yesterday_sleep'`

- [ ] **Step 3: 实现 garmin/sync.py**

```python
import datetime
from typing import Any


def fetch_yesterday_sleep(garmin) -> dict:
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    return garmin.get_sleep_data(yesterday)


def fetch_yesterday_activities(garmin) -> list[dict]:
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    return garmin.get_activities_by_date(yesterday, yesterday)


def parse_sleep(raw: dict) -> dict:
    dto = raw.get("dailySleepDTO", {})
    scores = dto.get("sleepScores", {})
    overall = scores.get("overall", {}) if isinstance(scores, dict) else {}

    def ms_to_iso(ms):
        if ms is None:
            return None
        return datetime.datetime.utcfromtimestamp(ms / 1000).isoformat()

    return {
        "total_sleep_min": _sec_to_min(dto.get("sleepTimeSeconds")),
        "deep_sleep_min": _sec_to_min(dto.get("deepSleepSeconds")),
        "light_sleep_min": _sec_to_min(dto.get("lightSleepSeconds")),
        "rem_sleep_min": _sec_to_min(dto.get("remSleepSeconds")),
        "awake_min": _sec_to_min(dto.get("awakeSleepSeconds")),
        "sleep_score": overall.get("value") if overall else None,
        "resting_hr": raw.get("restingHeartRate"),
        "sleep_start": ms_to_iso(dto.get("sleepStartTimestampGMT")),
        "sleep_end": ms_to_iso(dto.get("sleepEndTimestampGMT")),
    }


def parse_activity(raw: dict) -> dict:
    zones = raw.get("hrTimeInZone")
    def zone_min(i):
        if not zones or len(zones) <= i:
            return None
        return round(zones[i] / 60)

    distance_m = raw.get("distance")
    duration_s = raw.get("duration")
    start = raw.get("startTimeLocal", "")
    activity_date = start[:10] if start else None

    return {
        "garmin_activity_id": raw.get("activityId"),
        "activity_type": (raw.get("activityType") or {}).get("typeKey"),
        "activity_date": activity_date,
        "duration_min": round(duration_s / 60) if duration_s is not None else None,
        "calories_burned": raw.get("calories"),
        "avg_hr": raw.get("averageHR"),
        "max_hr": raw.get("maxHR"),
        "steps": raw.get("steps"),
        "distance_km": round(distance_m / 1000, 3) if distance_m is not None else None,
        "hr_zone_1_min": zone_min(0),
        "hr_zone_2_min": zone_min(1),
        "hr_zone_3_min": zone_min(2),
        "hr_zone_4_min": zone_min(3),
        "hr_zone_5_min": zone_min(4),
    }


def _sec_to_min(seconds) -> int | None:
    if seconds is None:
        return None
    return round(seconds / 60)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/garmin/test_sync.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add garmin/sync.py tests/garmin/test_sync.py
git commit -m "feat: garmin sync — fetch and parse sleep/activity data"
```

---

## Task 5: verify_garmin.py — 真实账号验证脚本

**Files:**
- Create: `verify_garmin.py`

**Interfaces:**
- Consumes: `GarminClient`, `fetch_yesterday_sleep`, `fetch_yesterday_activities`, `parse_sleep`, `parse_activity`
- Produces: 控制台输出（无测试，此脚本直接跑真实 API）

> 此 task 无单元测试，目的是真实登录验证数据可访问性。

- [ ] **Step 1: 创建 .env 文件（本地使用，不提交）**

复制 `.env.example` 为 `.env`，填入真实 Garmin 账号：

```bash
cp .env.example .env
# 编辑 .env，填入 GARMIN_EMAIL 和 GARMIN_PASSWORD
```

确保 `.env` 已在 `.gitignore` 中：

```bash
echo ".env" >> .gitignore
echo "*.tokens" >> .gitignore
```

- [ ] **Step 2: 实现 verify_garmin.py**

```python
#!/usr/bin/env python3
"""Phase 1 验证脚本：测试 Garmin 账号数据可访问性"""
import json
import sys
from garmin.client import GarminClient
from garmin.sync import (
    fetch_yesterday_sleep,
    fetch_yesterday_activities,
    parse_sleep,
    parse_activity,
)


def main():
    print("正在连接 Garmin Connect...")
    client = GarminClient()
    try:
        client.connect()
    except Exception as e:
        print(f"登录失败：{e}")
        sys.exit(1)
    print("登录成功 ✓\n")

    # 睡眠数据
    print("=" * 50)
    print("【昨日睡眠数据】")
    print("=" * 50)
    try:
        raw_sleep = fetch_yesterday_sleep(client.garmin)
        sleep = parse_sleep(raw_sleep)
        for key, val in sleep.items():
            print(f"  {key}: {val}")
    except Exception as e:
        print(f"睡眠数据获取失败：{e}")

    print()

    # 活动数据
    print("=" * 50)
    print("【昨日活动数据】")
    print("=" * 50)
    try:
        raw_activities = fetch_yesterday_activities(client.garmin)
        if not raw_activities:
            print("  昨日无活动记录")
        for raw in raw_activities:
            act = parse_activity(raw)
            print(f"\n  活动类型: {act['activity_type']}")
            for key, val in act.items():
                if key != "activity_type":
                    print(f"    {key}: {val}")
    except Exception as e:
        print(f"活动数据获取失败：{e}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行验证脚本**

```bash
python3 verify_garmin.py
```

Expected 成功输出示例：
```
正在连接 Garmin Connect...
登录成功 ✓

==================================================
【昨日睡眠数据】
==================================================
  total_sleep_min: 432
  deep_sleep_min: 78
  ...
  sleep_score: 74
  resting_hr: 55

==================================================
【昨日活动数据】
==================================================
  活动类型: running
    duration_min: 45
    calories_burned: 380
    ...
```

若遇到 MFA 二步验证，garminconnect 会通过 `prompt_mfa` 回调请求，但默认不传则会报错。如出现 MFA 提示，在 `GarminClient.connect()` 里补充：
```python
self.garmin = garminconnect.Garmin(
    email=config.GARMIN_EMAIL,
    password=config.GARMIN_PASSWORD,
    prompt_mfa=lambda: input("请输入 Garmin MFA 验证码: "),
)
```

- [ ] **Step 4: 确认 Token 已持久化**

```bash
ls ~/.garmin_tokens   # 或 GARMINTOKENS 指向的路径
```

Expected: 看到 token 文件存在，说明下次登录无需重新输入密码。

- [ ] **Step 5: 运行全量测试，确认无回归**

```bash
pytest tests/ -v
```

Expected: 全部通过，无 warning。

- [ ] **Step 6: Commit**

```bash
git add verify_garmin.py .gitignore
git commit -m "feat: verify_garmin.py — phase 1 validation script"
```

---

## Self-Review

**Spec coverage 检查：**

| PRD Phase 1 要求 | 计划覆盖情况 |
|-----------------|-------------|
| 能成功打印昨日睡眠数据 | ✅ Task 5 verify_garmin.py |
| 能成功打印昨日活动数据 | ✅ Task 5 verify_garmin.py |
| Session Token 持久化 | ✅ Task 3 GarminClient.connect(tokenstore=...) |
| 凭证从环境变量读取 | ✅ Task 1 config.py |
| garmin/client.py + garmin/sync.py 交付物 | ✅ Task 3 + Task 4 |

**Placeholder 扫描：** 无 TBD / TODO / "similar to Task N" 项。

**Type 一致性：** `fetch_yesterday_sleep` 返回 `dict`，传给 `parse_sleep(raw: dict)`；`fetch_yesterday_activities` 返回 `list[dict]`，每项传给 `parse_activity(raw: dict)`。全链路一致。
