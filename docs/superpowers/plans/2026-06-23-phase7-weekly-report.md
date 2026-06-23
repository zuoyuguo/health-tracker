# Phase 7 周报 + Bot /week 指令 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现每周一 08:00 自动周报推送、`/week` Bot 指令按需查询，聚合过去 7 天全量数据交由 Claude 生成 500-800 字中文分析。

**Architecture:** 新增 `analysis/weekly.py`（数据收集 + 报告生成）和扩展 `analysis/prompts.py`（添加 `build_weekly_prompt`）。`scheduler.py` 新增 `weekly_report_job` 注册为周一 08:00 cron job；`bot/handlers.py` 中 `cmd_week` 从存根升级为真实实现，调用 `generate_weekly_report`。

**Tech Stack:** Python 3.11, SQLAlchemy ORM, anthropic SDK (claude-opus-4-8), python-telegram-bot v20+, APScheduler

## Global Constraints

- Python 3.11+；所有新文件遵循项目已有代码风格（无注释、无多余 docstring）
- 模型固定为 `claude-opus-4-8`，周报 `max_tokens=2048`
- 所有数据库查询使用 `with SessionLocal() as session:` 模式
- 凭据只从 `config.py` env var 读取，禁止硬编码
- 时区：数据库存 UTC，`week_end = today - 1 day`，`week_start = week_end - 6 days`（共 7 天）
- 周报字数要求：500-800 字（写入 prompt 指示中）
- 周报调度：每周一 08:00 Asia/Shanghai（`day_of_week="mon", hour=8, minute=0`）
- 测试必须用 SQLite in-memory（`create_engine("sqlite:///:memory:")`），不得连接真实 DB
- 不得修改已有测试

---

## File Structure

```
analysis/
  prompts.py          # 已有 build_daily_prompt；新增 build_weekly_prompt + _weekday_cn
  weekly.py           # 新建：collect_weekly_data / has_weekly_data / generate_weekly_report
scheduler.py          # 新增 weekly_report_job + 注册 + import
bot/handlers.py       # cmd_week 从存根升级为真实实现
tests/
  analysis/
    test_prompts.py   # 追加 build_weekly_prompt 的测试
    test_weekly.py    # 新建：weekly.py 全部函数测试
  test_scheduler.py   # 追加 weekly_report_job 测试
  bot/
    test_handlers.py  # 追加 cmd_week 测试
```

---

### Task 1: `analysis/prompts.py` — 添加 `build_weekly_prompt`

**Files:**
- Modify: `analysis/prompts.py`
- Modify: `tests/analysis/test_prompts.py`

**Interfaces:**
- Consumes: nothing from other tasks
- Produces: `build_weekly_prompt(daily_data: list[dict]) -> str`
  - `daily_data` 每项结构：
    ```python
    {
        "date": datetime.date,
        "meals": list[dict],       # 同 daily collect 返回的 meal dict
        "sleep": dict | None,      # 同 daily collect 返回的 sleep dict
        "activities": list[dict],  # 同 daily collect 返回的 activity dict
        "body_metrics": list[dict],# 同 daily _body_metric_to_dict 返回的 dict（列表）
    }
    ```

- [ ] **Step 1: 写失败测试**

在 `tests/analysis/test_prompts.py` 末尾追加（保留已有内容，只追加）：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/zuoyuguo/Projects/health-tracker
python -m pytest tests/analysis/test_prompts.py::test_build_weekly_prompt_includes_date -v
```

期望：`FAILED` with `ImportError` 或 `cannot import name 'build_weekly_prompt'`

- [ ] **Step 3: 实现 `build_weekly_prompt` 和 `_weekday_cn`**

在 `analysis/prompts.py` 末尾追加（保留已有 `build_daily_prompt`，只追加）：

```python

_WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _weekday_cn(date: datetime.date) -> str:
    return _WEEKDAY_CN[date.weekday()]


def build_weekly_prompt(daily_data: list[dict]) -> str:
    lines = ["你是一位健康分析师。请根据以下过去7天健康数据生成周报。\n"]

    for entry in daily_data:
        date = entry["date"]
        meals = entry["meals"]
        sleep = entry["sleep"]
        activities = entry["activities"]
        body_metrics = entry["body_metrics"]

        lines.append(f"【{date.strftime('%m/%d')}（{_weekday_cn(date)}）】")

        if meals:
            total_cal = sum(m.get("total_calories") or 0 for m in meals)
            lines.append(f"  饮食：{total_cal:.0f} kcal")
        else:
            lines.append("  饮食：无记录")

        if sleep:
            total_min = sleep.get("total_sleep_min") or 0
            deep_min = sleep.get("deep_sleep_min") or 0
            deep_pct = f"{deep_min / total_min * 100:.0f}%" if total_min > 0 else "—"
            total_h, total_m = divmod(total_min, 60)
            sleep_str = f"{total_h}h{total_m:02d}m，深睡{deep_pct}"
            if sleep.get("sleep_score") is not None:
                sleep_str += f"，评分{sleep['sleep_score']}"
            if sleep.get("resting_hr") is not None:
                sleep_str += f"，静息心率{sleep['resting_hr']}bpm"
            lines.append(f"  睡眠：{sleep_str}")
        else:
            lines.append("  睡眠：无数据")

        if activities:
            act_parts = []
            for a in activities:
                act_parts.append(
                    f"{a.get('activity_type', '运动')}"
                    f"({a.get('duration_min', 0)}min,"
                    f"{a.get('calories_burned', 0):.0f}kcal)"
                )
            lines.append(f"  运动：{'；'.join(act_parts)}")
        else:
            lines.append("  运动：无")

        if body_metrics:
            for bm in body_metrics:
                parts = []
                if bm.get("weight_kg") is not None:
                    parts.append(f"体重{bm['weight_kg']:.1f}kg")
                if bm.get("body_fat_pct") is not None:
                    parts.append(f"体脂{bm['body_fat_pct']:.1f}%")
                lines.append(f"  称重：{'、'.join(parts) if parts else '—'}")

        lines.append("")

    lines.append(
        "请用中文生成500-800字的周报，格式：纯文本+少量emoji，分析以下维度：\n"
        "1. 热量摄入趋势（每日数据+趋势描述）\n"
        "2. 睡眠质量趋势（平均时长、深睡比例变化）\n"
        "3. 静息心率趋势（是否随运动频率改善）\n"
        "4. 运动频率和总量统计\n"
        "5. 体重/体脂变化趋势（若本周有称重记录）\n"
        "6. 关联发现（如运动日的次日深睡比例更高；热量缺口与体重变化是否一致）\n"
        "7. 本周亮点+下周建议"
    )

    return "\n".join(lines)
```

- [ ] **Step 4: 运行所有新测试确认通过**

```bash
python -m pytest tests/analysis/test_prompts.py -v
```

期望：所有测试 PASSED（含已有的 7 个 daily 测试 + 新增的 11 个 weekly 测试）

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
python -m pytest --tb=short -q
```

期望：140 passed（原有），无 failed

- [ ] **Step 6: Commit**

```bash
git add analysis/prompts.py tests/analysis/test_prompts.py
git commit -m "feat(analysis): add build_weekly_prompt to prompts.py"
```

---

### Task 2: `analysis/weekly.py` — 数据收集 + 周报生成

**Files:**
- Create: `analysis/weekly.py`
- Create: `tests/analysis/test_weekly.py`

**Interfaces:**
- Consumes from Task 1: `build_weekly_prompt(daily_data: list[dict]) -> str`
- Consumes from `analysis.daily` (already exists):
  - `_meal_to_dict(meal) -> dict`
  - `_sleep_to_dict(sleep) -> dict | None`
  - `_activity_to_dict(activity) -> dict`
  - `_body_metric_to_dict(metric) -> dict | None`
- Produces:
  - `collect_weekly_data(session, week_end: datetime.date) -> list[dict]`
  - `has_weekly_data(daily_data: list[dict]) -> bool`
  - `generate_weekly_report(session, week_end: datetime.date) -> str | None`

- [ ] **Step 1: 写失败测试**

新建 `tests/analysis/test_weekly.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/analysis/test_weekly.py::test_collect_weekly_data_returns_7_entries -v
```

期望：`FAILED` with `ModuleNotFoundError: No module named 'analysis.weekly'`

- [ ] **Step 3: 实现 `analysis/weekly.py`**

新建 `analysis/weekly.py`：

```python
import datetime
import anthropic
import config
from analysis.prompts import build_weekly_prompt
from analysis.daily import _meal_to_dict, _sleep_to_dict, _activity_to_dict, _body_metric_to_dict
from db.models import Meal, Sleep, Activity, BodyMetric


def collect_weekly_data(session, week_end: datetime.date) -> list[dict]:
    week_start = week_end - datetime.timedelta(days=6)
    result = []
    for i in range(7):
        date = week_start + datetime.timedelta(days=i)
        start_dt = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.timezone.utc)
        end_dt = datetime.datetime.combine(date, datetime.time.max, tzinfo=datetime.timezone.utc)
        yesterday = date - datetime.timedelta(days=1)

        meal_rows = (
            session.query(Meal)
            .filter(
                Meal.confirmed == True,
                Meal.recorded_at >= start_dt,
                Meal.recorded_at <= end_dt,
            )
            .order_by(Meal.recorded_at)
            .all()
        )

        sleep_row = session.query(Sleep).filter_by(sleep_date=yesterday).first()

        activity_rows = session.query(Activity).filter_by(activity_date=date).all()

        metric_rows = (
            session.query(BodyMetric)
            .filter(
                BodyMetric.measured_at >= start_dt,
                BodyMetric.measured_at <= end_dt,
            )
            .order_by(BodyMetric.measured_at)
            .all()
        )

        result.append({
            "date": date,
            "meals": [_meal_to_dict(m) for m in meal_rows],
            "sleep": _sleep_to_dict(sleep_row),
            "activities": [_activity_to_dict(a) for a in activity_rows],
            "body_metrics": [_body_metric_to_dict(bm) for bm in metric_rows],
        })

    return result


def has_weekly_data(daily_data: list[dict]) -> bool:
    return any(entry["meals"] or entry["activities"] for entry in daily_data)


def generate_weekly_report(session, week_end: datetime.date) -> str | None:
    daily_data = collect_weekly_data(session, week_end)
    if not has_weekly_data(daily_data):
        return None

    prompt = build_weekly_prompt(daily_data)
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
```

- [ ] **Step 4: 运行新测试确认全部通过**

```bash
python -m pytest tests/analysis/test_weekly.py -v
```

期望：所有 23 个测试 PASSED

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
python -m pytest --tb=short -q
```

期望：>140 passed，无 failed

- [ ] **Step 6: Commit**

```bash
git add analysis/weekly.py tests/analysis/test_weekly.py
git commit -m "feat(analysis): add weekly data collection and report generation"
```

---

### Task 3: `scheduler.py` + `bot/handlers.py` — 接入周报任务与 /week 指令

**Files:**
- Modify: `scheduler.py`
- Modify: `bot/handlers.py`
- Modify: `tests/test_scheduler.py`
- Modify: `tests/bot/test_handlers.py`

**Interfaces:**
- Consumes from Task 2:
  - `generate_weekly_report(session, week_end: datetime.date) -> str | None`
- Scheduler 已有模式（参考 `daily_report_job`）：
  ```python
  def daily_report_job() -> None:
      try:
          with SessionLocal() as session:
              report = generate_daily_report(session, datetime.date.today())
          if report:
              send_alert(report)
          logger.info(...)
      except Exception as exc:
          logger.error(...)
          send_alert(f"⚠️ ...")
  ```
- `create_scheduler()` 已有的 `scheduler.add_job(...)` 调用，继续追加

- [ ] **Step 1: 写失败测试**

在 `tests/test_scheduler.py` 末尾追加：

```python
# --- weekly_report_job tests ---

def test_weekly_report_job_sends_alert_when_report_returned():
    mock_session = MagicMock()
    report_text = "📊 本周周报内容"

    with patch("scheduler.SessionLocal") as MockSession, \
         patch("scheduler.generate_weekly_report", return_value=report_text) as mock_report, \
         patch("scheduler.send_alert") as mock_alert:
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        sched_mod.weekly_report_job()

    mock_report.assert_called_once()
    mock_alert.assert_called_once_with(report_text)


def test_weekly_report_job_does_not_send_when_no_data():
    mock_session = MagicMock()

    with patch("scheduler.SessionLocal") as MockSession, \
         patch("scheduler.generate_weekly_report", return_value=None), \
         patch("scheduler.send_alert") as mock_alert:
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        sched_mod.weekly_report_job()

    mock_alert.assert_not_called()


def test_weekly_report_job_sends_alert_on_failure():
    with patch("scheduler.SessionLocal", side_effect=Exception("DB error")), \
         patch("scheduler.send_alert") as mock_alert:
        sched_mod.weekly_report_job()

    mock_alert.assert_called_once()
    assert "周报生成失败" in mock_alert.call_args[0][0]


def test_weekly_report_job_week_end_is_yesterday():
    """week_end passed to generate_weekly_report must be today - 1 day."""
    import datetime as dt_mod
    mock_session = MagicMock()
    captured = []

    def fake_generate(session, week_end):
        captured.append(week_end)
        return None

    with patch("scheduler.SessionLocal") as MockSession, \
         patch("scheduler.generate_weekly_report", side_effect=fake_generate), \
         patch("scheduler.send_alert"):
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        sched_mod.weekly_report_job()

    assert captured[0] == dt_mod.date.today() - dt_mod.timedelta(days=1)


def test_create_scheduler_includes_weekly_job():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = sched_mod.create_scheduler()
    job_fns = [job.func for job in scheduler.get_jobs()]
    assert sched_mod.weekly_report_job in job_fns
    scheduler.shutdown(wait=False)
```

在 `tests/bot/test_handlers.py` 末尾追加：

```python
# --- cmd_week tests ---

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock


def test_cmd_week_sends_report_when_data_available(session):
    from bot.handlers import cmd_week
    report_text = "📊 本周周报：运动两次，睡眠质量提升。"

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch("bot.handlers.generate_weekly_report", return_value=report_text), \
         patch("bot.handlers.SessionLocal") as MockSession:
        MockSession.return_value.__enter__ = MagicMock(return_value=session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        asyncio.get_event_loop().run_until_complete(cmd_week(update, context))

    update.message.reply_text.assert_called_once_with(report_text)


def test_cmd_week_sends_no_data_message_when_report_is_none(session):
    from bot.handlers import cmd_week

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch("bot.handlers.generate_weekly_report", return_value=None), \
         patch("bot.handlers.SessionLocal") as MockSession:
        MockSession.return_value.__enter__ = MagicMock(return_value=session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        asyncio.get_event_loop().run_until_complete(cmd_week(update, context))

    reply = update.message.reply_text.call_args[0][0]
    assert "无" in reply or "暂无" in reply
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_scheduler.py::test_weekly_report_job_sends_alert_when_report_returned tests/bot/test_handlers.py::test_cmd_week_sends_report_when_data_available -v
```

期望：`FAILED` — `scheduler` 没有 `weekly_report_job` 属性，`bot.handlers` 没有 `generate_weekly_report`

- [ ] **Step 3: 修改 `scheduler.py`**

在 `scheduler.py` 的 import 块末尾追加（`from analysis.daily import generate_daily_report` 那一行之后）：

```python
from analysis.weekly import generate_weekly_report
```

在 `daily_report_job` 函数之后、`create_scheduler` 之前插入：

```python
def weekly_report_job() -> None:
    try:
        week_end = datetime.date.today() - datetime.timedelta(days=1)
        with SessionLocal() as session:
            report = generate_weekly_report(session, week_end)
        if report:
            send_alert(report)
        logger.info("Weekly report job complete. Report sent: %s", bool(report))
    except Exception as exc:
        logger.error("Weekly report job failed: %s", exc)
        send_alert(f"⚠️ 周报生成失败：{exc}")
```

在 `create_scheduler` 函数的 `return scheduler` 之前追加一行：

```python
    scheduler.add_job(weekly_report_job, "cron", day_of_week="mon", hour=8, minute=0, max_instances=1)
```

- [ ] **Step 4: 修改 `bot/handlers.py`**

在 `bot/handlers.py` 的 import 块末尾追加（`from notifications.telegram import send_alert` 或任意已有 import 之后）：

```python
from analysis.weekly import generate_weekly_report
```

将现有的 `cmd_week` 函数完整替换为：

```python
async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    week_end = datetime.date.today() - datetime.timedelta(days=1)
    with SessionLocal() as session:
        report = generate_weekly_report(session, week_end)
    if report:
        await update.message.reply_text(report)
    else:
        await update.message.reply_text("📭 近7天暂无饮食或运动记录，无法生成周报")
```

- [ ] **Step 5: 运行新增测试确认通过**

```bash
python -m pytest tests/test_scheduler.py -v -k "weekly"
python -m pytest tests/bot/test_handlers.py -v -k "week"
```

期望：所有新增测试 PASSED

- [ ] **Step 6: 运行全量测试确认无回归**

```bash
python -m pytest --tb=short -q
```

期望：>160 passed，无 failed

- [ ] **Step 7: Commit**

```bash
git add scheduler.py bot/handlers.py tests/test_scheduler.py tests/bot/test_handlers.py
git commit -m "feat(scheduler,bot): add weekly_report_job and implement /week command"
```

---

## Self-Review

### 1. Spec 覆盖检查

| PRD 需求 | 对应 Task |
|---------|----------|
| §4.4.2 周报每周一 08:00 | Task 3 — weekly_report_job, day_of_week="mon", hour=8 |
| §4.4.2 过去 7 天全量数据 | Task 2 — collect_weekly_data (week_end - 6 days to week_end) |
| §4.4.2 热量/睡眠/心率/运动/体重分析 | Task 1 — build_weekly_prompt 的 7 个分析维度 |
| §4.4.2 关联发现 | Task 1 — prompt 第 6 条 |
| §4.4.3 500-800 字 | Task 1 — prompt 明确写入 |
| §4.1.2 /week 指令 | Task 3 — cmd_week 实现 |

无缺漏。

### 2. Placeholder 扫描

无 TBD / TODO / "handle edge cases" / "add validation" 等占位语。所有步骤均含完整代码。

### 3. 类型一致性

- `collect_weekly_data` 返回 `list[dict]`，每项含 `"date"`, `"meals"`, `"sleep"`, `"activities"`, `"body_metrics"` 键
- `build_weekly_prompt` 接受相同结构的 `list[dict]`
- `generate_weekly_report` 接受 `(session, week_end: datetime.date)`，返回 `str | None`
- `weekly_report_job` 和 `cmd_week` 都调用 `generate_weekly_report(session, week_end)` — 签名一致
- `_body_metric_to_dict` 从 `analysis.daily` 导入，handle None 返回 None；在 `collect_weekly_data` 中迭代非 None 的 ORM 对象，所以返回值为 `dict`（非 None）

一致，无矛盾。
