# Phase 3: Telegram Bot 基础版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram Bot that accepts food photos, calls Claude Vision API to recognize food and estimate nutrition, stores confirmed meals in the `meals` table, and supports basic commands (/today, /note, /status).

**Architecture:** A `python-telegram-bot` v20+ async bot receives photo messages, delegates image analysis to `bot/vision.py` which calls the Anthropic SDK, and maintains per-user pending-confirmation state in `context.user_data`. Confirmed meals are written to PostgreSQL via the existing SQLAlchemy models. No scheduler is needed yet — bot starts via `main.py`.

**Tech Stack:** `python-telegram-bot>=20.7`, `anthropic`, existing `db/models.py` + `db/base.py`, `config.py`

## Global Constraints

- Python 3.11+; all handlers are `async def`
- Credentials read exclusively from env vars via `config.py` — never hardcoded
- Use `claude-opus-4-8` for all Claude API calls
- DB session pattern: `with SessionLocal() as session: … session.commit()`
- Test DB: SQLite in-memory (same pattern as `tests/db/test_models.py`)
- Language: Chinese UI strings throughout; prompt template verbatim from PRD §4.1.3
- `python-telegram-bot` v20+ API only — no v13 sync patterns
- No `/week` implementation in Phase 3 (Garmin data required — reply "功能开发中")

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add `python-telegram-bot[http2]>=20.7`, `anthropic` |
| `config.py` | Modify | Add `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY` |
| `bot/__init__.py` | Create | Package marker (empty) |
| `bot/vision.py` | Create | Claude Vision API caller + response parser |
| `bot/handlers.py` | Create | Telegram handlers + meal utilities (infer type, format, save, query) |
| `main.py` | Create | Application factory + `run_polling()` entry point |
| `tests/bot/__init__.py` | Create | Package marker (empty) |
| `tests/bot/test_vision.py` | Create | Unit tests for `parse_vision_response`, `build_vision_prompt` |
| `tests/bot/test_handlers.py` | Create | Unit tests for `infer_meal_type`, `format_meal_summary`, `save_meal`, `get_today_summary` |

---

### Task 1: Dependencies + Config

**Files:**
- Modify: `requirements.txt`
- Modify: `config.py`

**Interfaces:**
- Produces: `config.TELEGRAM_BOT_TOKEN: str`, `config.ANTHROPIC_API_KEY: str` — consumed by Tasks 2 and 4

- [ ] **Step 1: Write the failing config test**

Create `tests/bot/__init__.py` (empty):
```
# empty
```

Create `tests/bot/test_config_bot.py`:
```python
def test_telegram_bot_token_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    import importlib, config
    importlib.reload(config)
    assert config.TELEGRAM_BOT_TOKEN == "test-token-123"


def test_anthropic_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import importlib, config
    importlib.reload(config)
    assert config.ANTHROPIC_API_KEY == "sk-ant-test"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_config_bot.py -v
```
Expected: FAIL with `AttributeError: module 'config' has no attribute 'TELEGRAM_BOT_TOKEN'`

- [ ] **Step 3: Add env vars to config.py**

```python
# config.py — add after existing vars:
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
```

- [ ] **Step 4: Add dependencies to requirements.txt**

```
python-telegram-bot[http2]>=20.7
anthropic>=0.40.0
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```
Expected: both `telegram` and `anthropic` importable with no errors

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/bot/test_config_bot.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt config.py tests/bot/__init__.py tests/bot/test_config_bot.py
git commit -m "feat: add Telegram and Anthropic config vars + dependencies"
```

---

### Task 2: bot/vision.py — Claude Vision API Integration

**Files:**
- Create: `bot/__init__.py`
- Create: `bot/vision.py`
- Create: `tests/bot/test_vision.py`

**Interfaces:**
- Consumes: `config.ANTHROPIC_API_KEY`
- Produces:
  - `build_vision_prompt() -> str`
  - `parse_vision_response(text: str) -> dict` — raises `json.JSONDecodeError` on bad JSON
  - `analyze_food_photo(image_bytes: bytes, media_type: str = "image/jpeg") -> dict`
  - `apply_correction(original_data: dict, correction: str) -> dict`

- [ ] **Step 1: Write failing tests for parse_vision_response and build_vision_prompt**

Create `tests/bot/test_vision.py`:
```python
import json
import pytest
from bot.vision import parse_vision_response, build_vision_prompt


def test_parse_vision_response_valid_json():
    raw = json.dumps({
        "foods": [{"name": "鸡蛋", "weight_g": 60, "calories": 90,
                   "protein_g": 8, "carbs_g": 0, "fat_g": 6}],
        "total_calories": 90,
        "total_protein_g": 8,
        "total_carbs_g": 0,
        "total_fat_g": 6,
        "confidence": "high",
    })
    result = parse_vision_response(raw)
    assert result["foods"][0]["name"] == "鸡蛋"
    assert result["total_calories"] == 90


def test_parse_vision_response_strips_markdown_code_block():
    raw = '```json\n{"foods": [], "total_calories": 0, "total_protein_g": 0, "total_carbs_g": 0, "total_fat_g": 0}\n```'
    result = parse_vision_response(raw)
    assert result["foods"] == []


def test_parse_vision_response_strips_plain_code_block():
    raw = '```\n{"foods": [], "total_calories": 0, "total_protein_g": 0, "total_carbs_g": 0, "total_fat_g": 0}\n```'
    result = parse_vision_response(raw)
    assert result["total_calories"] == 0


def test_parse_vision_response_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_vision_response("这不是 JSON")


def test_build_vision_prompt_contains_required_terms():
    prompt = build_vision_prompt()
    assert "JSON" in prompt
    assert "重量" in prompt
    assert "calories" in prompt or "热量" in prompt
    assert "foods" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_vision.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'bot'`

- [ ] **Step 3: Create bot/__init__.py**

Create `bot/__init__.py` (empty file):
```python
```

- [ ] **Step 4: Implement bot/vision.py**

Create `bot/vision.py`:
```python
import json
import base64
import anthropic
import config

_PROMPT = """\
你是一个专业的营养师助手。请分析这张食物照片，识别所有可见的食物，并以 JSON 格式返回结果。

要求：
- 尽可能准确估算每种食物的重量（克）
- 根据重量估算热量和三大营养素
- 如果无法确定，给出合理的中间估计值
- 只返回 JSON，不要其他文字

返回格式：
{
  "foods": [
    {
      "name": "食物名称（中文）",
      "weight_g": 数字,
      "calories": 数字,
      "protein_g": 数字,
      "carbs_g": 数字,
      "fat_g": 数字
    }
  ],
  "total_calories": 数字,
  "total_protein_g": 数字,
  "total_carbs_g": 数字,
  "total_fat_g": 数字,
  "confidence": "high/medium/low",
  "notes": "识别说明或不确定项（可选）"
}"""


def build_vision_prompt() -> str:
    return _PROMPT


def parse_vision_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] is the content inside the first ```...``` block
        inner = parts[1]
        if inner.startswith("json"):
            inner = inner[4:]
        text = inner.strip()
    return json.loads(text)


def analyze_food_photo(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    b64 = base64.standard_b64encode(image_bytes).decode()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {"type": "text", "text": build_vision_prompt()},
            ],
        }],
    )
    return parse_vision_response(msg.content[0].text)


def apply_correction(original_data: dict, correction: str) -> dict:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = (
        f"原始食物识别结果：\n"
        f"{json.dumps(original_data, ensure_ascii=False, indent=2)}\n\n"
        f"用户修正：{correction}\n\n"
        "请根据用户修正重新计算，以完全相同的 JSON 格式返回完整结果。只返回 JSON，不要其他文字。"
    )
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_vision_response(msg.content[0].text)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/bot/test_vision.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add bot/__init__.py bot/vision.py tests/bot/test_vision.py
git commit -m "feat: add bot/vision.py with Claude Vision food recognition"
```

---

### Task 3: bot/handlers.py — Meal Utilities

**Files:**
- Create: `bot/handlers.py` (utility functions only in this task)
- Create: `tests/bot/test_handlers.py`

**Interfaces:**
- Consumes: `db.base.SessionLocal`, `db.models.Meal`
- Produces:
  - `infer_meal_type(dt: datetime.datetime) -> str` — returns "早餐"/"午餐"/"晚餐"/"加餐"
  - `format_meal_summary(data: dict) -> str` — Telegram-ready message with food list + totals
  - `save_meal(session, data: dict, recorded_at: datetime.datetime, confirmed: bool = False) -> Meal`
  - `get_today_summary(session, date: datetime.date) -> str`

- [ ] **Step 1: Write failing tests for utility functions**

Create `tests/bot/test_handlers.py`:
```python
import datetime
import pytest
from db.base import get_engine, Base
from sqlalchemy.orm import sessionmaker


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


def test_infer_meal_type_breakfast():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 8, 30, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "早餐"


def test_infer_meal_type_lunch():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "午餐"


def test_infer_meal_type_dinner():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 19, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "晚餐"


def test_infer_meal_type_late_night_snack():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 23, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "加餐"


def test_infer_meal_type_early_morning_snack():
    from bot.handlers import infer_meal_type
    dt = datetime.datetime(2026, 6, 22, 3, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "加餐"


def test_format_meal_summary_includes_food_names():
    from bot.handlers import format_meal_summary
    data = {
        "foods": [
            {"name": "牛排", "weight_g": 250, "calories": 600},
            {"name": "米饭", "weight_g": 150, "calories": 195},
        ],
        "total_calories": 795,
        "total_protein_g": 52,
        "total_carbs_g": 44,
        "total_fat_g": 28,
    }
    summary = format_meal_summary(data)
    assert "牛排" in summary
    assert "250" in summary
    assert "米饭" in summary
    assert "795" in summary
    assert "确认" in summary


def test_format_meal_summary_shows_macros():
    from bot.handlers import format_meal_summary
    data = {
        "foods": [{"name": "鸡胸肉", "weight_g": 200, "calories": 330}],
        "total_calories": 330,
        "total_protein_g": 62,
        "total_carbs_g": 0,
        "total_fat_g": 7,
    }
    summary = format_meal_summary(data)
    assert "62" in summary
    assert "蛋白质" in summary


def test_save_meal_sets_confirmed_and_meal_type(session):
    from bot.handlers import save_meal
    from db.models import Meal
    data = {
        "foods": [{"name": "米饭", "weight_g": 150, "calories": 195,
                   "protein_g": 4, "carbs_g": 44, "fat_g": 1}],
        "total_calories": 195,
        "total_protein_g": 4,
        "total_carbs_g": 44,
        "total_fat_g": 1,
    }
    recorded_at = datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc)
    meal = save_meal(session, data, recorded_at, confirmed=True)
    session.flush()

    result = session.query(Meal).filter_by(id=meal.id).one()
    assert result.confirmed is True
    assert result.meal_type == "午餐"
    assert float(result.total_calories) == 195.0
    assert float(result.protein_g) == 4.0


def test_save_meal_unconfirmed_by_default(session):
    from bot.handlers import save_meal
    data = {
        "foods": [],
        "total_calories": 0,
        "total_protein_g": 0,
        "total_carbs_g": 0,
        "total_fat_g": 0,
    }
    recorded_at = datetime.datetime(2026, 6, 22, 8, 0, tzinfo=datetime.timezone.utc)
    meal = save_meal(session, data, recorded_at)
    session.flush()
    assert meal.confirmed is False


def test_get_today_summary_no_meals(session):
    from bot.handlers import get_today_summary
    summary = get_today_summary(session, datetime.date(2025, 1, 1))
    assert "暂无" in summary


def test_get_today_summary_sums_calories(session):
    from bot.handlers import get_today_summary
    from db.models import Meal
    test_date = datetime.date(2026, 6, 23)
    meals = [
        Meal(
            recorded_at=datetime.datetime(2026, 6, 23, 8, 0, tzinfo=datetime.timezone.utc),
            meal_type="早餐",
            foods=[{"name": "面包", "weight_g": 80, "calories": 200}],
            total_calories=200,
            confirmed=True,
        ),
        Meal(
            recorded_at=datetime.datetime(2026, 6, 23, 12, 0, tzinfo=datetime.timezone.utc),
            meal_type="午餐",
            foods=[{"name": "米饭", "weight_g": 200, "calories": 260}],
            total_calories=260,
            confirmed=True,
        ),
    ]
    for m in meals:
        session.add(m)
    session.flush()

    summary = get_today_summary(session, test_date)
    assert "460" in summary
    assert "早餐" in summary
    assert "午餐" in summary


def test_get_today_summary_excludes_unconfirmed(session):
    from bot.handlers import get_today_summary
    from db.models import Meal
    test_date = datetime.date(2026, 6, 24)
    session.add(Meal(
        recorded_at=datetime.datetime(2026, 6, 24, 12, 0, tzinfo=datetime.timezone.utc),
        meal_type="午餐",
        foods=[],
        total_calories=500,
        confirmed=False,
    ))
    session.flush()
    summary = get_today_summary(session, test_date)
    assert "暂无" in summary
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_handlers.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.handlers'`

- [ ] **Step 3: Implement utility functions in bot/handlers.py**

Create `bot/handlers.py`:
```python
import datetime
from db.models import Meal


def infer_meal_type(dt: datetime.datetime) -> str:
    hour = dt.hour
    if 5 <= hour < 10:
        return "早餐"
    elif 10 <= hour < 14:
        return "午餐"
    elif 17 <= hour < 21:
        return "晚餐"
    return "加餐"


def format_meal_summary(data: dict) -> str:
    lines = ["🍽 已识别："]
    for food in data.get("foods", []):
        lines.append(f"• {food['name']} {food['weight_g']}g — {food['calories']} kcal")
    lines.append("")
    lines.append(
        f"合计：{data.get('total_calories', 0):.0f} kcal | "
        f"蛋白质 {data.get('total_protein_g', 0):.0f}g | "
        f"碳水 {data.get('total_carbs_g', 0):.0f}g | "
        f"脂肪 {data.get('total_fat_g', 0):.0f}g"
    )
    lines.append("")
    lines.append("回复「确认」保存，或直接告诉我需要修正的内容")
    return "\n".join(lines)


def save_meal(session, data: dict, recorded_at: datetime.datetime, confirmed: bool = False) -> Meal:
    meal = Meal(
        recorded_at=recorded_at,
        meal_type=infer_meal_type(recorded_at),
        foods=data.get("foods", []),
        total_calories=data.get("total_calories"),
        protein_g=data.get("total_protein_g"),
        carbs_g=data.get("total_carbs_g"),
        fat_g=data.get("total_fat_g"),
        confirmed=confirmed,
    )
    session.add(meal)
    session.flush()
    return meal


def get_today_summary(session, date: datetime.date) -> str:
    from sqlalchemy import func
    meals = (
        session.query(Meal)
        .filter(
            func.date(Meal.recorded_at) == date,
            Meal.confirmed.is_(True),
        )
        .order_by(Meal.recorded_at)
        .all()
    )
    if not meals:
        return f"📅 {date} 暂无饮食记录"

    total_cal = sum(float(m.total_calories or 0) for m in meals)
    lines = [f"📅 {date} 饮食汇总", ""]
    for meal in meals:
        time_str = meal.recorded_at.strftime("%H:%M")
        cal_str = f"{float(meal.total_calories):.0f} kcal" if meal.total_calories else "—"
        if meal.user_note and not meal.foods:
            lines.append(f"• {time_str} [{meal.meal_type}] {meal.user_note}")
        else:
            food_names = "、".join(f["name"] for f in (meal.foods or []))
            lines.append(f"• {time_str} [{meal.meal_type}] {food_names} {cal_str}")
    lines.append("")
    lines.append(f"合计摄入：{total_cal:.0f} kcal")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bot/test_handlers.py -v
```
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add bot/handlers.py tests/bot/test_handlers.py
git commit -m "feat: add bot/handlers.py meal utilities (infer_meal_type, format, save, summary)"
```

---

### Task 4: bot/handlers.py — Telegram Message Handlers

**Files:**
- Modify: `bot/handlers.py` (add async Telegram handler functions at the bottom)

**Interfaces:**
- Consumes: `bot.vision.analyze_food_photo`, `bot.vision.apply_correction`, all utilities from Task 3
- Produces:
  - `handle_photo(update, context) -> None` — async
  - `handle_text(update, context) -> None` — async
  - `cmd_today(update, context) -> None` — async
  - `cmd_note(update, context) -> None` — async
  - `cmd_status(update, context) -> None` — async
  - `cmd_week(update, context) -> None` — async (stub)
  - `PENDING_MEAL_KEY: str` — context.user_data key for pending meal state

- [ ] **Step 1: Write failing tests for Telegram handlers**

Add to `tests/bot/test_handlers.py`:
```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_update(text=None, has_photo=False, args=None):
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = text
    update.message.date = datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc)
    if has_photo:
        photo_mock = MagicMock()
        photo_mock.file_id = "test-file-id"
        update.message.photo = [photo_mock]
    else:
        update.message.photo = []
    return update


def _make_context(user_data=None):
    context = MagicMock()
    context.user_data = user_data if user_data is not None else {}
    context.bot.get_file = AsyncMock()
    context.args = []
    return context


def test_handle_text_confirm_saves_meal(session):
    from bot.handlers import handle_text, PENDING_MEAL_KEY
    pending = {
        "data": {
            "foods": [{"name": "苹果", "weight_g": 150, "calories": 80,
                       "protein_g": 0, "carbs_g": 20, "fat_g": 0}],
            "total_calories": 80,
            "total_protein_g": 0,
            "total_carbs_g": 20,
            "total_fat_g": 0,
        },
        "recorded_at": datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc),
    }
    update = _make_update(text="确认")
    context = _make_context(user_data={PENDING_MEAL_KEY: pending})

    with patch("bot.handlers.SessionLocal") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        asyncio.run(handle_text(update, context))

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    assert PENDING_MEAL_KEY not in context.user_data
    update.message.reply_text.assert_called_with("✅ 已保存")


def test_handle_text_no_pending_does_nothing():
    from bot.handlers import handle_text
    update = _make_update(text="确认")
    context = _make_context()
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_not_called()


def test_handle_text_correction_updates_pending():
    from bot.handlers import handle_text, PENDING_MEAL_KEY
    original_data = {
        "foods": [{"name": "牛排", "weight_g": 200, "calories": 480,
                   "protein_g": 42, "carbs_g": 0, "fat_g": 32}],
        "total_calories": 480,
        "total_protein_g": 42,
        "total_carbs_g": 0,
        "total_fat_g": 32,
    }
    pending = {
        "data": original_data,
        "recorded_at": datetime.datetime(2026, 6, 22, 19, 0, tzinfo=datetime.timezone.utc),
    }
    new_data = {
        "foods": [{"name": "牛排", "weight_g": 300, "calories": 720,
                   "protein_g": 63, "carbs_g": 0, "fat_g": 48}],
        "total_calories": 720,
        "total_protein_g": 63,
        "total_carbs_g": 0,
        "total_fat_g": 48,
    }
    update = _make_update(text="牛排是 300g")
    context = _make_context(user_data={PENDING_MEAL_KEY: pending})

    with patch("bot.handlers.apply_correction", return_value=new_data) as mock_corr:
        asyncio.run(handle_text(update, context))
        mock_corr.assert_called_once_with(original_data, "牛排是 300g")

    assert context.user_data[PENDING_MEAL_KEY]["data"] == new_data
    assert update.message.reply_text.call_count == 2  # "正在修正..." + new summary


def test_cmd_note_saves_with_note_text(session):
    from bot.handlers import cmd_note
    update = _make_update(text="/note 喝了一杯咖啡")
    context = _make_context()
    context.args = ["喝了一杯咖啡"]

    with patch("bot.handlers.SessionLocal") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        asyncio.run(cmd_note(update, context))

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert added.user_note == "喝了一杯咖啡"
    assert added.confirmed is True


def test_cmd_note_no_args_replies_with_usage():
    from bot.handlers import cmd_note
    update = _make_update()
    context = _make_context()
    context.args = []
    asyncio.run(cmd_note(update, context))
    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "用法" in call_text


def test_cmd_status_replies():
    from bot.handlers import cmd_status
    update = _make_update()
    context = _make_context()
    asyncio.run(cmd_status(update, context))
    update.message.reply_text.assert_called_once()


def test_cmd_week_replies_with_coming_soon():
    from bot.handlers import cmd_week
    update = _make_update()
    context = _make_context()
    asyncio.run(cmd_week(update, context))
    call_text = update.message.reply_text.call_args[0][0]
    assert "功能开发中" in call_text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_handlers.py::test_handle_text_confirm_saves_meal -v
```
Expected: FAIL with `ImportError: cannot import name 'handle_text'`

- [ ] **Step 3: Add Telegram handler functions to bot/handlers.py**

Append to the bottom of `bot/handlers.py` (after `get_today_summary`):
```python
from telegram import Update
from telegram.ext import ContextTypes
from bot.vision import analyze_food_photo, apply_correction
from db.base import SessionLocal

PENDING_MEAL_KEY = "pending_meal"


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("识别中...")
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    data = analyze_food_photo(image_bytes)
    context.user_data[PENDING_MEAL_KEY] = {
        "data": data,
        "recorded_at": update.message.date,
    }
    await update.message.reply_text(format_meal_summary(data))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    pending = context.user_data.get(PENDING_MEAL_KEY)
    if not pending:
        return
    if text == "确认":
        with SessionLocal() as session:
            save_meal(session, pending["data"], pending["recorded_at"], confirmed=True)
            session.commit()
        del context.user_data[PENDING_MEAL_KEY]
        await update.message.reply_text("✅ 已保存")
    else:
        await update.message.reply_text("正在修正...")
        new_data = apply_correction(pending["data"], text)
        context.user_data[PENDING_MEAL_KEY]["data"] = new_data
        await update.message.reply_text(format_meal_summary(new_data))


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import datetime
    today = datetime.date.today()
    with SessionLocal() as session:
        reply = get_today_summary(session, today)
    await update.message.reply_text(reply)


async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note = " ".join(context.args) if context.args else ""
    if not note:
        await update.message.reply_text("用法：/note <备注内容>，例如：/note 喝了一杯咖啡")
        return
    recorded_at = update.message.date
    with SessionLocal() as session:
        meal = Meal(
            recorded_at=recorded_at,
            meal_type=infer_meal_type(recorded_at),
            foods=[],
            user_note=note,
            confirmed=True,
        )
        session.add(meal)
        session.commit()
    await update.message.reply_text(f"✅ 备注已保存：{note}")


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("功能开发中，周报将在 Phase 7 上线")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✅ 系统运行中")
```

- [ ] **Step 4: Run all handler tests**

```bash
pytest tests/bot/test_handlers.py -v
```
Expected: PASS (all tests)

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest -v
```
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add bot/handlers.py tests/bot/test_handlers.py
git commit -m "feat: add Telegram message handlers (photo, confirm/correct, commands)"
```

---

### Task 5: main.py — Bot Entry Point

**Files:**
- Create: `main.py`

**Interfaces:**
- Consumes: `config.TELEGRAM_BOT_TOKEN`, all handlers from `bot/handlers.py`
- Produces: `create_app() -> Application` (testable factory), `__main__` block runs polling

- [ ] **Step 1: Write failing test for create_app**

Create `tests/test_main.py`:
```python
import pytest
from unittest.mock import patch


def test_create_app_registers_handlers(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-12345")
    import importlib, config
    importlib.reload(config)

    import main
    importlib.reload(main)

    app = main.create_app()
    # python-telegram-bot stores handlers in groups; check group 0
    handler_types = [type(h).__name__ for h in app.handlers.get(0, [])]
    assert "MessageHandler" in handler_types
    assert "CommandHandler" in handler_types
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_main.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Create main.py**

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


def create_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("note", cmd_note))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("status", cmd_status))
    return app


if __name__ == "__main__":
    create_app().run_polling()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_main.py -v
```
Expected: PASS (1 test)

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```
Expected: All tests pass; no regressions

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add main.py bot application factory and entry point"
```

---

## Self-Review

### Spec Coverage Check

| PRD Requirement | Covered by |
|----------------|------------|
| User sends food photo → Bot replies "识别中..." | Task 4 `handle_photo` |
| Claude Vision API analyzes food photo → JSON | Task 2 `analyze_food_photo` |
| Bot formats recognition result with foods + totals | Task 3 `format_meal_summary` |
| User replies "确认" → save to meals table, confirmed=true | Task 4 `handle_text` |
| User replies correction → re-estimate | Task 4 `handle_text` + Task 2 `apply_correction` |
| Meal type inferred from time (早/午/晚/加餐) | Task 3 `infer_meal_type` |
| /today command → today's meal summary | Task 4 `cmd_today` |
| /note command → save text note without photo | Task 4 `cmd_note` |
| /status command → system status | Task 4 `cmd_status` |
| /week command → reply (stub, Phase 7) | Task 4 `cmd_week` |
| Credentials from env vars only | Task 1 config + Global Constraints |
| Write to meals table via SQLAlchemy | Task 3 `save_meal` |

### Placeholder Scan
None found. All steps contain concrete code.

### Type Consistency Check
- `save_meal(session, data: dict, recorded_at: datetime.datetime, confirmed: bool)` — used consistently in Tasks 3 and 4
- `PENDING_MEAL_KEY` defined once in Task 4, imported in tests
- `format_meal_summary(data: dict) -> str` — same signature in Task 3 definition and Task 4 usage
- `apply_correction(original_data: dict, correction: str) -> dict` — Task 2 definition matches Task 4 call
