import pytest
from unittest.mock import patch, MagicMock


def test_renpho_client_wrapper_connect_calls_login(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "user@test.com")
    monkeypatch.setenv("RENPHO_PASSWORD", "pw")
    import importlib, config
    importlib.reload(config)

    mock_renpho = MagicMock()
    with patch("renpho.client.RenphoClient", return_value=mock_renpho) as MockClass:
        import importlib
        import renpho.client as rc
        importlib.reload(rc)
        wrapper = rc.RenphoClientWrapper()
        wrapper.connect()

    MockClass.assert_called_once_with("user@test.com", "pw")
    mock_renpho.login.assert_called_once()
    assert wrapper.client is mock_renpho


def test_renpho_client_wrapper_raises_on_missing_email(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "")
    monkeypatch.setenv("RENPHO_PASSWORD", "pw")
    import importlib, config
    importlib.reload(config)

    import importlib
    import renpho.client as rc
    importlib.reload(rc)
    wrapper = rc.RenphoClientWrapper()
    with pytest.raises(ValueError, match="RENPHO_EMAIL"):
        wrapper.connect()


def test_renpho_client_wrapper_raises_on_missing_password(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "user@test.com")
    monkeypatch.setenv("RENPHO_PASSWORD", "")
    import importlib, config
    importlib.reload(config)

    import importlib
    import renpho.client as rc
    importlib.reload(rc)
    wrapper = rc.RenphoClientWrapper()
    with pytest.raises(ValueError, match="RENPHO_PASSWORD"):
        wrapper.connect()
