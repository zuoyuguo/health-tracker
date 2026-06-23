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
