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
