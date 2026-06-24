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
    # 14:00 UTC = 07:00 PDT → 早餐
    dt = datetime.datetime(2026, 6, 22, 14, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "早餐"


def test_infer_meal_type_lunch():
    from bot.handlers import infer_meal_type
    # 19:00 UTC = 12:00 PDT → 午餐
    dt = datetime.datetime(2026, 6, 22, 19, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "午餐"


def test_infer_meal_type_dinner():
    from bot.handlers import infer_meal_type
    # 02:00 UTC June 23 = 19:00 PDT June 22 → 晚餐
    dt = datetime.datetime(2026, 6, 23, 2, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "晚餐"


def test_infer_meal_type_late_night_snack():
    from bot.handlers import infer_meal_type
    # 23:00 UTC = 16:00 PDT → 加餐（14:00–17:00 之间）
    dt = datetime.datetime(2026, 6, 22, 23, 0, tzinfo=datetime.timezone.utc)
    assert infer_meal_type(dt) == "加餐"


def test_infer_meal_type_early_morning_snack():
    from bot.handlers import infer_meal_type
    # 10:00 UTC = 03:00 PDT → 加餐（凌晨）
    dt = datetime.datetime(2026, 6, 22, 10, 0, tzinfo=datetime.timezone.utc)
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
    # 19:00 UTC = 12:00 PDT → 午餐
    recorded_at = datetime.datetime(2026, 6, 22, 19, 0, tzinfo=datetime.timezone.utc)
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


import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import config as _config


_TEST_CHAT_ID = 123456789


@pytest.fixture(autouse=True)
def patch_chat_id(monkeypatch):
    monkeypatch.setattr(_config, "TELEGRAM_CHAT_ID", str(_TEST_CHAT_ID))


def _make_update(text=None, has_photo=False, args=None):
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = text
    update.message.date = datetime.datetime(2026, 6, 22, 12, 0, tzinfo=datetime.timezone.utc)
    update.effective_chat.id = _TEST_CHAT_ID
    if has_photo:
        photo_mock = MagicMock()
        photo_mock.file_id = "test-file-id"
        photo_mock.file_size = 1024
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


def test_handle_text_no_pending_non_confirm_does_nothing():
    from bot.handlers import handle_text
    update = _make_update(text="你好")
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
    with patch("bot.handlers.SessionLocal") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.order_by.return_value.first.return_value = None
        asyncio.run(cmd_status(update, context))
    update.message.reply_text.assert_called_once()
    assert "状态" in update.message.reply_text.call_args[0][0]


def test_cmd_week_replies_when_no_data():
    from bot.handlers import cmd_week
    update = _make_update()
    context = _make_context()
    with patch("bot.handlers.generate_weekly_report", return_value=None), \
         patch("bot.handlers.SessionLocal") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        asyncio.run(cmd_week(update, context))
    call_text = update.message.reply_text.call_args[0][0]
    assert "暂无" in call_text or "无" in call_text


def test_handle_photo_sets_pending_and_replies():
    from bot.handlers import handle_photo, PENDING_MEAL_KEY
    fake_data = {
        "foods": [{"name": "苹果", "weight_g": 150, "calories": 80,
                   "protein_g": 0, "carbs_g": 20, "fat_g": 0}],
        "total_calories": 80,
        "total_protein_g": 0,
        "total_carbs_g": 20,
        "total_fat_g": 0,
    }
    update = _make_update(has_photo=True)
    context = _make_context()
    mock_file = MagicMock()
    mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake-image"))
    context.bot.get_file = AsyncMock(return_value=mock_file)

    with patch("bot.handlers.analyze_food_photo", return_value=fake_data):
        asyncio.run(handle_photo(update, context))

    assert PENDING_MEAL_KEY in context.user_data
    assert context.user_data[PENDING_MEAL_KEY]["data"] == fake_data
    assert update.message.reply_text.call_count == 2  # "识别中..." + summary


def test_handle_photo_api_failure_sends_error_message():
    from bot.handlers import handle_photo, PENDING_MEAL_KEY
    update = _make_update(has_photo=True)
    context = _make_context()
    mock_file = MagicMock()
    mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake-image"))
    context.bot.get_file = AsyncMock(return_value=mock_file)

    with patch("bot.handlers.analyze_food_photo", side_effect=Exception("API error")):
        asyncio.run(handle_photo(update, context))

    assert PENDING_MEAL_KEY not in context.user_data
    last_reply = update.message.reply_text.call_args_list[-1][0][0]
    assert "失败" in last_reply


def test_handle_text_confirm_with_no_pending_replies():
    from bot.handlers import handle_text
    update = _make_update(text="确认")
    context = _make_context()
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "没有" in call_text or "重新" in call_text


# --- cmd_week tests ---


def test_cmd_week_sends_report_when_data_available(session):
    from bot.handlers import cmd_week
    report_text = "📊 本周周报：运动两次，睡眠质量提升。"

    update = _make_update()
    context = _make_context()

    with patch("bot.handlers.generate_weekly_report", return_value=report_text), \
         patch("bot.handlers.SessionLocal") as MockSession:
        MockSession.return_value.__enter__ = MagicMock(return_value=session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        asyncio.run(cmd_week(update, context))

    update.message.reply_text.assert_called_once_with(report_text)


def test_cmd_week_sends_no_data_message_when_report_is_none(session):
    from bot.handlers import cmd_week

    update = _make_update()
    context = _make_context()

    with patch("bot.handlers.generate_weekly_report", return_value=None), \
         patch("bot.handlers.SessionLocal") as MockSession:
        MockSession.return_value.__enter__ = MagicMock(return_value=session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        asyncio.run(cmd_week(update, context))

    reply = update.message.reply_text.call_args[0][0]
    assert "无" in reply or "暂无" in reply
