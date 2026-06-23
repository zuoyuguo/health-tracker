# Phase 6 AI 分析与日报推送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每晚 22:00 自动聚合当日健康数据，调用 Claude API 生成中文日报，并通过 Telegram Bot 推送给用户。

**Architecture:** 新建 `analysis/` 包，分三层：`prompts.py` 构建 Claude Prompt，`daily.py` 负责数据收集 + 调用 Claude + 返回报告文本；`scheduler.py` 新增 `daily_report_job` 在 22:00 触发，报告通过已有的 `notifications.telegram.send_alert` 推送。

**Tech Stack:** Python 3.11+, anthropic SDK (claude-opus-4-8), SQLAlchemy ORM, APScheduler, python-telegram-bot

## Global Constraints

- Python 3.11+；凭证只从 env 读取，不硬编码
- Claude 模型固定为 `claude-opus-4-8`，max_tokens=1024
- 报告语言：中文；格式：纯文本 + 少量 emoji；目标字数 300-500
- Telegram 推送复用 `notifications.telegram.send_alert(text)`
- DB Session 模式：`with SessionLocal() as session: …`
- 测试用 SQLite in-memory；生产用 PostgreSQL
- 所有 import 放文件顶部（PEP 8）；YAGNI

---

## File Structure

**新建文件：**
- `analysis/__init__.py` — 空包标记
- `analysis/prompts.py` — `build_daily_prompt(meals, sleep, activities, body_metric) -> str`
- `analysis/daily.py` — `collect_daily_data(session, date)` + `has_data(data)` + `generate_daily_report(session, date)`
- `tests/analysis/__init__.py` — 空包标记
- `tests/analysis/test_prompts.py`
- `tests/analysis/test_daily.py`

**修改文件：**
- `scheduler.py` — 新增 `daily_report_job()`；更新 `create_scheduler()` 注册第 3 个 job（22:00）；新增 `import datetime`
- `tests/test_scheduler.py` — 新增 daily_report_job 测试；更新 scheduler job 数量断言为 3

---

### Task 1: analysis/prompts.py — Prompt 构建

**Files:**
- Create: `analysis/__init__.py`
- Create: `analysis/prompts.py`
- Create: `tests/analysis/__init__.py`
- Test: `tests/analysis/test_prompts.py`

**Interfaces:**
- Produces:
  - `build_daily_prompt(meals: list[dict], sleep: dict | None, activities: list[dict], body_metric: dict | None) -> str`

**meals 中每个 dict 的结构：**
```python
{
    "meal_type": str,           # "早餐"/"午餐"/"晚餐"/"加餐"
    "recorded_at": datetime,    # timezone-aware UTC datetime
    "total_calories": float,
    "protein_g": float,
    "carbs_g": float,
    "fat_g": float,
    "foods": list[dict],        # [{"name": "鸡蛋", ...}, ...]
}
```

**sleep dict 结构：**
```python
{
    "total_sleep_min": int | None,
    "deep_sleep_min": int | None,
    "rem_sleep_min": int | None,
    "sleep_score": int | None,
    "resting_hr": int | None,
    "hrv_avg": float | None,
}
```

**activities 中每个 dict 的结构：**
```python
{
    "activity_type": str,       # "running"/"cycling" 等
    "duration_min": int | None,
    "calories_burned": float,
    "avg_hr": int | None,
}
```

**body_metric dict 结构：**
```python
{
    "measured_at": datetime,    # timezone-aware UTC datetime
    "weight_kg": float | None,
    "body_fat_pct": float | None,
    "bmi": float | None,
}
```

- [ ] **Step 1: 创建空包文件**

创建 `analysis/__init__.py`（内容为空）。
创建 `tests/analysis/__init__.py`（内容为空）。

- [ ] **Step 2: 写失败测试**

创建 `tests/analysis/test_prompts.py`：

```python
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
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
cd /Users/zuoyuguo/Projects/health-tracker
pytest tests/analysis/test_prompts.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'analysis'`

- [ ] **Step 4: 实现 analysis/prompts.py**

```python
import datetime


def build_daily_prompt(
    meals: list[dict],
    sleep: dict | None,
    activities: list[dict],
    body_metric: dict | None,
) -> str:
    lines = ["你是一位健康分析师。请根据以下今日健康数据生成日报。\n"]

    # 饮食
    if meals:
        lines.append("【今日饮食】（已确认记录）")
        total_cal = sum(m.get("total_calories") or 0 for m in meals)
        total_protein = sum(m.get("protein_g") or 0 for m in meals)
        total_carbs = sum(m.get("carbs_g") or 0 for m in meals)
        total_fat = sum(m.get("fat_g") or 0 for m in meals)
        for m in meals:
            foods_str = "、".join(f["name"] for f in (m.get("foods") or []) if f.get("name"))
            recorded_at = m.get("recorded_at")
            time_str = recorded_at.strftime("%H:%M") if isinstance(recorded_at, datetime.datetime) else ""
            lines.append(
                f"- {m.get('meal_type', '进餐')}（{time_str}）：{foods_str or '未知食物'}"
                f" — {m.get('total_calories') or 0:.0f} kcal"
                f" | 蛋白质 {m.get('protein_g') or 0:.0f}g"
                f" | 碳水 {m.get('carbs_g') or 0:.0f}g"
                f" | 脂肪 {m.get('fat_g') or 0:.0f}g"
            )
        lines.append(
            f"合计：{total_cal:.0f} kcal"
            f" | 蛋白质 {total_protein:.0f}g"
            f" | 碳水 {total_carbs:.0f}g"
            f" | 脂肪 {total_fat:.0f}g"
        )
    else:
        lines.append("【今日饮食】无确认记录")

    lines.append("")

    # 睡眠
    if sleep:
        lines.append("【昨晚睡眠】")
        total_min = sleep.get("total_sleep_min") or 0
        deep_min = sleep.get("deep_sleep_min") or 0
        rem_min = sleep.get("rem_sleep_min") or 0
        total_h, total_m = divmod(total_min, 60)
        deep_h, deep_m = divmod(deep_min, 60)
        rem_h, rem_m = divmod(rem_min, 60)
        parts = [
            f"总时长：{total_h}h{total_m:02d}m",
            f"深睡：{deep_h}h{deep_m:02d}m",
            f"REM：{rem_h}h{rem_m:02d}m",
        ]
        if sleep.get("sleep_score") is not None:
            parts.append(f"睡眠评分：{sleep['sleep_score']}")
        if sleep.get("resting_hr") is not None:
            parts.append(f"静息心率：{sleep['resting_hr']} bpm")
        if sleep.get("hrv_avg") is not None:
            parts.append(f"HRV：{sleep['hrv_avg']:.1f} ms")
        lines.append(" | ".join(parts))
    else:
        lines.append("【昨晚睡眠】无数据")

    lines.append("")

    # 运动
    if activities:
        lines.append("【今日运动】")
        for a in activities:
            activity_line = (
                f"- {a.get('activity_type', '运动')}（{a.get('duration_min') or 0}分钟）："
                f"消耗 {a.get('calories_burned') or 0:.0f} kcal"
            )
            if a.get("avg_hr"):
                activity_line += f" | 平均心率 {a['avg_hr']} bpm"
            lines.append(activity_line)
    else:
        lines.append("【今日运动】无数据")

    lines.append("")

    # 体重体脂
    if body_metric:
        measured_at = body_metric.get("measured_at")
        date_str = measured_at.strftime("%Y-%m-%d") if isinstance(measured_at, datetime.datetime) else "未知"
        lines.append(f"【体重体脂】（记录于 {date_str}）")
        parts = []
        if body_metric.get("weight_kg") is not None:
            parts.append(f"体重：{body_metric['weight_kg']:.1f} kg")
        if body_metric.get("body_fat_pct") is not None:
            parts.append(f"体脂率：{body_metric['body_fat_pct']:.1f}%")
        if body_metric.get("bmi") is not None:
            parts.append(f"BMI：{body_metric['bmi']:.1f}")
        lines.append(" | ".join(parts) if parts else "无数值")
    else:
        lines.append("【体重体脂】无数据")

    lines.append("")
    lines.append(
        "请用中文生成 300-500 字的日报，格式：纯文本+少量emoji，分析以下维度：\n"
        "1. 热量摄入vs消耗（若有运动数据则计算净差值）\n"
        "2. 营养素比例评价\n"
        "3. 进餐时间分布（是否有深夜进食）\n"
        "4. 睡眠质量简评（若有数据）\n"
        "5. 运动评价（若有数据）\n"
        "6. 体重体脂评价（若有数据）\n"
        "7. 1-2条个性化建议"
    )

    return "\n".join(lines)
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/analysis/test_prompts.py -v
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add analysis/__init__.py analysis/prompts.py tests/analysis/__init__.py tests/analysis/test_prompts.py
git commit -m "feat(analysis): add build_daily_prompt"
```

---

### Task 2: analysis/daily.py — 数据收集 + 报告生成

**Files:**
- Create: `analysis/daily.py`
- Test: `tests/analysis/test_daily.py`

**Interfaces:**
- Consumes:
  - `build_daily_prompt` from `analysis.prompts` (Task 1)
  - `db.models.Meal`, `Sleep`, `Activity`, `BodyMetric` (已存在)
  - `config.ANTHROPIC_API_KEY`
  - `anthropic.Anthropic` (anthropic SDK)
- Produces:
  - `collect_daily_data(session, date: datetime.date) -> dict`
    — keys: `"meals"` (list[dict]), `"sleep"` (dict|None), `"activities"` (list[dict]), `"body_metric"` (dict|None)
  - `has_data(data: dict) -> bool`
    — True if `data["meals"]` or `data["activities"]` is non-empty
  - `generate_daily_report(session, date: datetime.date) -> str | None`
    — None if `not has_data(data)`; otherwise Claude API text

**collect_daily_data 查询逻辑：**
- `meals`：`Meal.confirmed == True` AND `Meal.recorded_at` 在 [date 00:00 UTC, date 23:59:59 UTC] 范围内，按 `recorded_at` 升序
- `sleep`：`Sleep.sleep_date == date - 1 day`（昨晚）
- `activities`：`Activity.activity_date == date`
- `body_metric`：`BodyMetric.measured_at <= date 23:59:59 UTC`，按 `measured_at` 降序取第一条

**ORM → dict 转换（在 collect_daily_data 内完成）：**

Meal → dict:
```python
{
    "meal_type": meal.meal_type,
    "recorded_at": meal.recorded_at,
    "total_calories": float(meal.total_calories or 0),
    "protein_g": float(meal.protein_g or 0),
    "carbs_g": float(meal.carbs_g or 0),
    "fat_g": float(meal.fat_g or 0),
    "foods": meal.foods or [],
}
```

Sleep → dict:
```python
{
    "total_sleep_min": sleep.total_sleep_min,
    "deep_sleep_min": sleep.deep_sleep_min,
    "rem_sleep_min": sleep.rem_sleep_min,
    "sleep_score": sleep.sleep_score,
    "resting_hr": sleep.resting_hr,
    "hrv_avg": float(sleep.hrv_avg) if sleep.hrv_avg else None,
}
```

Activity → dict:
```python
{
    "activity_type": activity.activity_type,
    "duration_min": activity.duration_min,
    "calories_burned": float(activity.calories_burned or 0),
    "avg_hr": activity.avg_hr,
}
```

BodyMetric → dict:
```python
{
    "measured_at": metric.measured_at,
    "weight_kg": float(metric.weight_kg) if metric.weight_kg is not None else None,
    "body_fat_pct": float(metric.body_fat_pct) if metric.body_fat_pct is not None else None,
    "bmi": float(metric.bmi) if metric.bmi is not None else None,
}
```

- [ ] **Step 1: 写失败测试**

创建 `tests/analysis/test_daily.py`：

```python
import datetime
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.base import Base
from db.models import Meal, Sleep, Activity, BodyMetric


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


_TODAY = datetime.date(2026, 6, 23)
_YESTERDAY = datetime.date(2026, 6, 22)
_NOW = datetime.datetime(2026, 6, 23, 12, 0, 0, tzinfo=datetime.timezone.utc)
_END_OF_TODAY = datetime.datetime(2026, 6, 23, 23, 59, 59, tzinfo=datetime.timezone.utc)


def _add_meal(session, meal_type="早餐", cal=350, confirmed=True,
              recorded_at=None):
    if recorded_at is None:
        recorded_at = _NOW
    m = Meal(
        meal_type=meal_type,
        recorded_at=recorded_at,
        total_calories=cal,
        protein_g=20,
        carbs_g=40,
        fat_g=12,
        foods=[{"name": "鸡蛋"}],
        confirmed=confirmed,
    )
    session.add(m)
    session.commit()
    return m


def _add_sleep(session, date=_YESTERDAY):
    s = Sleep(
        sleep_date=date,
        total_sleep_min=450,
        deep_sleep_min=105,
        rem_sleep_min=80,
        sleep_score=82,
        resting_hr=54,
    )
    session.add(s)
    session.commit()
    return s


def _add_activity(session, date=_TODAY):
    a = Activity(
        activity_date=date,
        activity_type="running",
        duration_min=45,
        calories_burned=380,
        avg_hr=152,
    )
    session.add(a)
    session.commit()
    return a


def _add_body_metric(session, measured_at=None):
    if measured_at is None:
        measured_at = datetime.datetime(2026, 6, 22, 10, 0, tzinfo=datetime.timezone.utc)
    bm = BodyMetric(
        measured_at=measured_at,
        weight_kg=70.5,
        body_fat_pct=18.3,
        bmi=22.1,
        renpho_record_id=f"rec-{measured_at.timestamp():.0f}",
    )
    session.add(bm)
    session.commit()
    return bm


# --- collect_daily_data ---

def test_collect_returns_confirmed_meals_only(session):
    from analysis.daily import collect_daily_data
    _add_meal(session, confirmed=True)
    _add_meal(session, confirmed=False)
    data = collect_daily_data(session, _TODAY)
    assert len(data["meals"]) == 1
    assert data["meals"][0]["meal_type"] == "早餐"


def test_collect_excludes_meals_from_other_days(session):
    from analysis.daily import collect_daily_data
    yesterday_dt = datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc)
    _add_meal(session, confirmed=True, recorded_at=yesterday_dt)
    data = collect_daily_data(session, _TODAY)
    assert data["meals"] == []


def test_collect_returns_yesterdays_sleep(session):
    from analysis.daily import collect_daily_data
    _add_sleep(session, date=_YESTERDAY)
    data = collect_daily_data(session, _TODAY)
    assert data["sleep"] is not None
    assert data["sleep"]["total_sleep_min"] == 450
    assert data["sleep"]["sleep_score"] == 82


def test_collect_sleep_is_none_when_missing(session):
    from analysis.daily import collect_daily_data
    data = collect_daily_data(session, _TODAY)
    assert data["sleep"] is None


def test_collect_returns_todays_activities(session):
    from analysis.daily import collect_daily_data
    _add_activity(session, date=_TODAY)
    data = collect_daily_data(session, _TODAY)
    assert len(data["activities"]) == 1
    assert data["activities"][0]["activity_type"] == "running"
    assert data["activities"][0]["calories_burned"] == 380.0


def test_collect_excludes_activities_from_other_days(session):
    from analysis.daily import collect_daily_data
    _add_activity(session, date=_YESTERDAY)
    data = collect_daily_data(session, _TODAY)
    assert data["activities"] == []


def test_collect_returns_most_recent_body_metric(session):
    from analysis.daily import collect_daily_data
    _add_body_metric(session, datetime.datetime(2026, 6, 20, 10, 0, tzinfo=datetime.timezone.utc))
    _add_body_metric(session, datetime.datetime(2026, 6, 22, 10, 0, tzinfo=datetime.timezone.utc))
    data = collect_daily_data(session, _TODAY)
    assert data["body_metric"] is not None
    assert data["body_metric"]["weight_kg"] == 70.5


def test_collect_body_metric_excludes_future_records(session):
    from analysis.daily import collect_daily_data
    future = datetime.datetime(2026, 6, 24, 10, 0, tzinfo=datetime.timezone.utc)
    _add_body_metric(session, future)
    data = collect_daily_data(session, _TODAY)
    assert data["body_metric"] is None


# --- has_data ---

def test_has_data_true_when_meals_present(session):
    from analysis.daily import collect_daily_data, has_data
    _add_meal(session, confirmed=True)
    data = collect_daily_data(session, _TODAY)
    assert has_data(data) is True


def test_has_data_true_when_activities_present(session):
    from analysis.daily import collect_daily_data, has_data
    _add_activity(session)
    data = collect_daily_data(session, _TODAY)
    assert has_data(data) is True


def test_has_data_false_when_only_sleep_and_body_metric(session):
    from analysis.daily import collect_daily_data, has_data
    _add_sleep(session)
    _add_body_metric(session)
    data = collect_daily_data(session, _TODAY)
    assert has_data(data) is False


def test_has_data_false_when_empty(session):
    from analysis.daily import collect_daily_data, has_data
    data = collect_daily_data(session, _TODAY)
    assert has_data(data) is False


# --- generate_daily_report ---

def test_generate_daily_report_returns_none_when_no_data(session):
    from analysis.daily import generate_daily_report
    result = generate_daily_report(session, _TODAY)
    assert result is None


def test_generate_daily_report_calls_claude_and_returns_text(session):
    from analysis.daily import generate_daily_report
    _add_meal(session, confirmed=True)

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="📊 今日日报：热量摄入 350 kcal，营养均衡，建议多喝水。")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("analysis.daily.anthropic.Anthropic", return_value=mock_client):
        result = generate_daily_report(session, _TODAY)

    assert result == "📊 今日日报：热量摄入 350 kcal，营养均衡，建议多喝水。"
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-8"
    assert call_kwargs["max_tokens"] == 1024


def test_generate_daily_report_prompt_contains_meal_data(session):
    from analysis.daily import generate_daily_report
    _add_meal(session, confirmed=True, cal=500)

    captured_prompt = []

    def fake_create(**kwargs):
        captured_prompt.append(kwargs["messages"][0]["content"])
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="日报内容")]
        return mock_msg

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = fake_create

    with patch("analysis.daily.anthropic.Anthropic", return_value=mock_client):
        generate_daily_report(session, _TODAY)

    assert "500" in captured_prompt[0]
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/zuoyuguo/Projects/health-tracker
pytest tests/analysis/test_daily.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.daily'`

- [ ] **Step 3: 实现 analysis/daily.py**

```python
import datetime
import anthropic
import config
from analysis.prompts import build_daily_prompt
from db.models import Meal, Sleep, Activity, BodyMetric


def collect_daily_data(session, date: datetime.date) -> dict:
    start = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end = datetime.datetime.combine(date, datetime.time.max, tzinfo=datetime.timezone.utc)
    yesterday = date - datetime.timedelta(days=1)

    meal_rows = session.query(Meal).filter(
        Meal.confirmed == True,
        Meal.recorded_at >= start,
        Meal.recorded_at <= end,
    ).order_by(Meal.recorded_at).all()

    sleep_row = session.query(Sleep).filter_by(sleep_date=yesterday).first()

    activity_rows = session.query(Activity).filter_by(activity_date=date).all()

    metric_row = session.query(BodyMetric).filter(
        BodyMetric.measured_at <= end,
    ).order_by(BodyMetric.measured_at.desc()).first()

    return {
        "meals": [_meal_to_dict(m) for m in meal_rows],
        "sleep": _sleep_to_dict(sleep_row),
        "activities": [_activity_to_dict(a) for a in activity_rows],
        "body_metric": _body_metric_to_dict(metric_row),
    }


def has_data(data: dict) -> bool:
    return bool(data["meals"] or data["activities"])


def generate_daily_report(session, date: datetime.date) -> str | None:
    data = collect_daily_data(session, date)
    if not has_data(data):
        return None

    prompt = build_daily_prompt(
        data["meals"],
        data["sleep"],
        data["activities"],
        data["body_metric"],
    )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _meal_to_dict(meal) -> dict:
    return {
        "meal_type": meal.meal_type,
        "recorded_at": meal.recorded_at,
        "total_calories": float(meal.total_calories or 0),
        "protein_g": float(meal.protein_g or 0),
        "carbs_g": float(meal.carbs_g or 0),
        "fat_g": float(meal.fat_g or 0),
        "foods": meal.foods or [],
    }


def _sleep_to_dict(sleep) -> dict | None:
    if sleep is None:
        return None
    return {
        "total_sleep_min": sleep.total_sleep_min,
        "deep_sleep_min": sleep.deep_sleep_min,
        "rem_sleep_min": sleep.rem_sleep_min,
        "sleep_score": sleep.sleep_score,
        "resting_hr": sleep.resting_hr,
        "hrv_avg": float(sleep.hrv_avg) if sleep.hrv_avg is not None else None,
    }


def _activity_to_dict(activity) -> dict:
    return {
        "activity_type": activity.activity_type,
        "duration_min": activity.duration_min,
        "calories_burned": float(activity.calories_burned or 0),
        "avg_hr": activity.avg_hr,
    }


def _body_metric_to_dict(metric) -> dict | None:
    if metric is None:
        return None
    return {
        "measured_at": metric.measured_at,
        "weight_kg": float(metric.weight_kg) if metric.weight_kg is not None else None,
        "body_fat_pct": float(metric.body_fat_pct) if metric.body_fat_pct is not None else None,
        "bmi": float(metric.bmi) if metric.bmi is not None else None,
    }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/analysis/test_daily.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: 运行全套测试确认无回归**

```bash
pytest --tb=short -q
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add analysis/daily.py tests/analysis/test_daily.py
git commit -m "feat(analysis): add collect_daily_data and generate_daily_report"
```

---

### Task 3: scheduler.py — daily_report_job + 更新测试

**Files:**
- Modify: `scheduler.py`
- Modify: `tests/test_scheduler.py`

**Interfaces:**
- Consumes:
  - `generate_daily_report(session, date)` from `analysis.daily` (Task 2)
  - `send_alert(text)` from `notifications.telegram` (已存在)
  - `SessionLocal` from `db.base` (已存在)
- Produces: `daily_report_job() -> None`；`create_scheduler()` 注册 3 个 job

**scheduler.py 变更：**
- 新增 `import datetime`（在现有 imports 后追加）
- 新增 `from analysis.daily import generate_daily_report`
- 新增 `daily_report_job()` 函数
- `create_scheduler()` 新增第 3 个 job：`daily_report_job` 在 `hour=22, minute=0, max_instances=1`

**daily_report_job 逻辑：**
- 用 try/except 包裹全部
- 成功路径：`generate_daily_report(session, today)` → 若返回文本则 `send_alert(report)` → log
- 失败路径：log error + `send_alert(f"⚠️ 日报生成失败：{exc}")`

**tests/test_scheduler.py 变更：**
- 将 `test_create_scheduler_returns_scheduler_with_two_jobs` 更新为 `test_create_scheduler_returns_scheduler_with_three_jobs`，断言 `len(jobs) == 3`
- 追加 3 个新测试

- [ ] **Step 1: 写失败测试**

在 `tests/test_scheduler.py` 末尾追加以下内容，并将现有 `test_create_scheduler_returns_scheduler_with_two_jobs` 改为断言 3 个 job：

```python
# 将原来的 test_create_scheduler_returns_scheduler_with_two_jobs 改为：
def test_create_scheduler_returns_scheduler_with_three_jobs():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = sched_mod.create_scheduler()
    assert isinstance(scheduler, BackgroundScheduler)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 3
    for job in jobs:
        assert job.trigger.__class__.__name__ == "CronTrigger"
```

在文件末尾追加：

```python
# --- daily_report_job tests ---

def test_daily_report_job_sends_alert_when_report_returned():
    mock_session = MagicMock()
    report_text = "📊 今日日报内容"

    with patch("scheduler.SessionLocal") as MockSession, \
         patch("scheduler.generate_daily_report", return_value=report_text) as mock_report, \
         patch("scheduler.send_alert") as mock_alert:
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        sched_mod.daily_report_job()

    mock_report.assert_called_once()
    mock_alert.assert_called_once_with(report_text)


def test_daily_report_job_does_not_send_when_no_data():
    mock_session = MagicMock()

    with patch("scheduler.SessionLocal") as MockSession, \
         patch("scheduler.generate_daily_report", return_value=None), \
         patch("scheduler.send_alert") as mock_alert:
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        sched_mod.daily_report_job()

    mock_alert.assert_not_called()


def test_daily_report_job_sends_alert_on_failure():
    with patch("scheduler.SessionLocal", side_effect=Exception("DB error")), \
         patch("scheduler.send_alert") as mock_alert:
        sched_mod.daily_report_job()

    mock_alert.assert_called_once()
    alert_text = mock_alert.call_args[0][0]
    assert "日报" in alert_text or "失败" in alert_text
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/zuoyuguo/Projects/health-tracker
pytest tests/test_scheduler.py -v
```

Expected: FAIL（新测试找不到 `sched_mod.daily_report_job`；job 数量断言失败）

- [ ] **Step 3: 更新 scheduler.py**

完整 `scheduler.py`：

```python
import datetime
import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from db.base import SessionLocal
from garmin.client import GarminClient
from garmin.sync import fetch_yesterday_sleep, fetch_yesterday_activities, parse_sleep, parse_activity
from garmin.db_sync import upsert_sleep, insert_activities
from renpho_sync.client import RenphoClientWrapper
from renpho_sync.sync import fetch_recent_measurements, parse_measurement
from renpho_sync.db_sync import insert_body_metrics
from analysis.daily import generate_daily_report
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


def daily_report_job() -> None:
    try:
        today = datetime.date.today()
        with SessionLocal() as session:
            report = generate_daily_report(session, today)
        if report:
            send_alert(report)
        logger.info("Daily report job complete. Report sent: %s", bool(report))
    except Exception as exc:
        logger.error("Daily report job failed: %s", exc)
        send_alert(f"⚠️ 日报生成失败：{exc}")


def create_scheduler() -> BackgroundScheduler:
    tz = pytz.timezone("Asia/Shanghai")
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(garmin_sync_job, "cron", hour=9, minute=0, max_instances=1)
    scheduler.add_job(renpho_sync_job, "cron", hour=9, minute=0, max_instances=1)
    scheduler.add_job(daily_report_job, "cron", hour=22, minute=0, max_instances=1)
    return scheduler
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_scheduler.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: 运行全套测试确认无回归**

```bash
pytest --tb=short -q
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add scheduler.py tests/test_scheduler.py
git commit -m "feat(analysis): add daily_report_job to scheduler at 22:00"
```
