import os
import pytest
from garmin.session import get_token_path


def test_get_token_path_returns_string():
    path = get_token_path()
    assert isinstance(path, str)
    assert len(path) > 0


def test_get_token_path_no_tilde(monkeypatch):
    monkeypatch.setenv("GARMINTOKENS", "~/custom_tokens")
    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)
    path = session.get_token_path()
    assert "~" not in path
    assert os.path.isabs(path)


def test_get_token_path_uses_config(monkeypatch):
    monkeypatch.setenv("GARMINTOKENS", "/tmp/test_tokens")
    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)
    assert session.get_token_path() == "/tmp/test_tokens"
