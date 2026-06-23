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
