def test_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/testdb")
    import importlib, config
    importlib.reload(config)
    assert config.DATABASE_URL == "postgresql://test:test@localhost/testdb"


def test_database_url_default_is_empty(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib, config
    importlib.reload(config)
    assert config.DATABASE_URL == ""
