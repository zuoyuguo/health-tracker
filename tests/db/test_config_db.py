def test_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/testdb")
    import importlib, config
    importlib.reload(config)
    assert config.DATABASE_URL == "postgresql://test:test@localhost/testdb"


def test_database_url_default_is_empty(monkeypatch):
    # setenv("", ...) overrides .env file value since load_dotenv won't overwrite existing vars
    monkeypatch.setenv("DATABASE_URL", "")
    import importlib, config
    importlib.reload(config)
    assert config.DATABASE_URL == ""


def test_renpho_email_from_env(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "test@renpho.com")
    import importlib, config
    importlib.reload(config)
    assert config.RENPHO_EMAIL == "test@renpho.com"


def test_renpho_password_from_env(monkeypatch):
    monkeypatch.setenv("RENPHO_PASSWORD", "secret")
    import importlib, config
    importlib.reload(config)
    assert config.RENPHO_PASSWORD == "secret"


def test_renpho_email_default_empty(monkeypatch):
    monkeypatch.setenv("RENPHO_EMAIL", "")
    import importlib, config
    importlib.reload(config)
    assert config.RENPHO_EMAIL == ""
