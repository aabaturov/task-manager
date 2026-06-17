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


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _migrate() -> None:
    """Add SPEC-001 columns to pre-existing v1.0 tables (idempotent).

    ``create_all`` never alters existing tables, so a database created under
    v1.0 would miss the new project/task columns. We add them with safe
    defaults and backfill task ``position`` so old data keeps working.
    """
    with engine.begin() as conn:
        # projects -----------------------------------------------------------
        if not _column_exists(conn, "projects", "icon"):
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN icon VARCHAR(16)")
        if not _column_exists(conn, "projects", "type"):
            conn.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN type VARCHAR(10) "
                "NOT NULL DEFAULT 'local'"
            )
        if not _column_exists(conn, "projects", "pinned"):
            conn.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT 0"
            )
        if not _column_exists(conn, "projects", "pinned_at"):
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN pinned_at DATETIME")

        # tasks --------------------------------------------------------------
        backfill_positions = False
        if not _column_exists(conn, "tasks", "position"):
            conn.exec_driver_sql(
                "ALTER TABLE tasks ADD COLUMN position INTEGER NOT NULL DEFAULT 0"
            )
            backfill_positions = True
        if not _column_exists(conn, "tasks", "important"):
            conn.exec_driver_sql(
                "ALTER TABLE tasks ADD COLUMN important BOOLEAN NOT NULL DEFAULT 0"
            )
        if not _column_exists(conn, "tasks", "deadline"):
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN deadline DATE")
        if not _column_exists(conn, "tasks", "done"):
            conn.exec_driver_sql(
                "ALTER TABLE tasks ADD COLUMN done BOOLEAN NOT NULL DEFAULT 0"
            )

        if backfill_positions:
            project_ids = [
                row[0]
                for row in conn.exec_driver_sql("SELECT id FROM projects").fetchall()
            ]
            for pid in project_ids:
                rows = conn.exec_driver_sql(
                    "SELECT id FROM tasks WHERE project_id = ? "
                    "ORDER BY created_at, id",
                    (pid,),
                ).fetchall()
                for index, (task_id,) in enumerate(rows):
                    conn.exec_driver_sql(
                        "UPDATE tasks SET position = ? WHERE id = ?", (index, task_id)
                    )


def init_db() -> None:
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    _migrate()
