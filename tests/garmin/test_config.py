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
