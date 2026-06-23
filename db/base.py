from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import config


class Base(DeclarativeBase):
    pass


def get_engine(url: str):
    return create_engine(url)


_engine = get_engine(config.DATABASE_URL) if config.DATABASE_URL else get_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=_engine)
