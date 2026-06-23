import pytest
from sqlalchemy import text
from db.base import Base, get_engine, SessionLocal


def test_base_is_declarative_base():
    from sqlalchemy.orm import DeclarativeBase
    assert issubclass(Base, DeclarativeBase)


def test_get_engine_creates_engine():
    from sqlalchemy.engine import Engine
    engine = get_engine("sqlite:///:memory:")
    assert isinstance(engine, Engine)
    engine.dispose()


def test_get_engine_connects():
    engine = get_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
    engine.dispose()


def test_session_local_is_callable():
    # SessionLocal 是 sessionmaker 实例，应该可以被调用产生 Session
    session = SessionLocal()
    assert session is not None
    session.close()
