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

    with patch("telegram.Bot", return_value=mock_bot):
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

    with patch("telegram.Bot") as MockBot:
        import notifications.telegram as notif
        importlib.reload(notif)
        notif.send_alert("test")
        MockBot.assert_not_called()


def test_send_alert_noop_when_chat_id_missing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    import importlib, config
    importlib.reload(config)

    with patch("telegram.Bot") as MockBot:
        import notifications.telegram as notif
        importlib.reload(notif)
        notif.send_alert("test")
        MockBot.assert_not_called()
