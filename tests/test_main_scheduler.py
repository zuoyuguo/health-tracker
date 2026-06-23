import pytest
from unittest.mock import MagicMock, patch


def test_main_starts_scheduler(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import importlib, config
    importlib.reload(config)

    import main
    importlib.reload(main)

    mock_scheduler = MagicMock()
    mock_app_instance = MagicMock()

    # Patch at call time inside _run()
    # Since main.py imports create_scheduler at the module level, patch main.create_scheduler
    with patch("main.create_app", return_value=mock_app_instance) as mock_app:
        with patch("main.create_scheduler", return_value=mock_scheduler) as mock_create:
            main._run()

            mock_create.assert_called_once()
            mock_scheduler.start.assert_called_once()
            mock_app_instance.run_polling.assert_called_once()
