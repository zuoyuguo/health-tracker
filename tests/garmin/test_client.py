import pytest
from unittest.mock import MagicMock, patch


def make_mock_garmin():
    mock = MagicMock()
    mock.login.return_value = (None, None)  # 成功登录返回 (None, None)
    return mock


def test_connect_calls_login_with_token_path(tmp_path, monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret")
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))

    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)

    mock_garmin_instance = make_mock_garmin()

    with patch("garmin.client.garminconnect.Garmin", return_value=mock_garmin_instance):
        import garmin.client as client_mod
        importlib.reload(client_mod)
        client = client_mod.GarminClient()
        client.connect()

    mock_garmin_instance.login.assert_called_once_with(
        tokenstore=str(tmp_path / "tokens")
    )


def test_connect_passes_credentials_to_garmin(tmp_path, monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "user@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pass123")
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))

    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)

    mock_garmin_instance = make_mock_garmin()

    with patch("garmin.client.garminconnect.Garmin") as MockGarmin:
        MockGarmin.return_value = mock_garmin_instance
        import garmin.client as client_mod
        importlib.reload(client_mod)
        client = client_mod.GarminClient()
        client.connect()
        call_kwargs = MockGarmin.call_args.kwargs
        assert call_kwargs["email"] == "user@example.com"
        assert call_kwargs["password"] == "pass123"


def test_garmin_attribute_is_accessible_after_connect(tmp_path, monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret")
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))

    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)

    mock_garmin_instance = make_mock_garmin()

    with patch("garmin.client.garminconnect.Garmin", return_value=mock_garmin_instance):
        import garmin.client as client_mod
        importlib.reload(client_mod)
        client = client_mod.GarminClient()
        client.connect()

    assert client.garmin is mock_garmin_instance


def test_connect_raises_on_login_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "wrong")
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))

    import importlib, config, garmin.session as session
    importlib.reload(config)
    importlib.reload(session)

    mock_garmin_instance = make_mock_garmin()
    mock_garmin_instance.login.side_effect = Exception("GarminConnectAuthenticationError")

    with patch("garmin.client.garminconnect.Garmin", return_value=mock_garmin_instance):
        import garmin.client as client_mod
        importlib.reload(client_mod)
        client = client_mod.GarminClient()
        with pytest.raises(Exception, match="GarminConnectAuthenticationError"):
            client.connect()
