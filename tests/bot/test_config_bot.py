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
