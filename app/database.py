import sys

try:
    import pysqlite3

    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = "sqlite:///resident_schedule.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    return SessionLocal()


def init_db(db_engine=None):
    """Create all tables. Pass a custom engine for testing."""
    from app.models import Base

    target = db_engine or engine
    Base.metadata.create_all(target)
