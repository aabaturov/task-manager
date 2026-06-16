import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# Make sure the directory holding the SQLite file exists.
db_dir = os.path.dirname(settings.database_path)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
