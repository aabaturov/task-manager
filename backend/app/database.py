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


def _project_id_is_not_null(conn) -> bool:
    """True if tasks.project_id still carries a NOT NULL constraint.

    PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk).
    """
    rows = conn.exec_driver_sql("PRAGMA table_info(tasks)").fetchall()
    for row in rows:
        if row[1] == "project_id":
            return bool(row[3])
    return False


def _rebuild_tasks_nullable_project(conn) -> None:
    """Rebuild ``tasks`` so ``project_id`` allows NULL (standalone events).

    SQLite cannot drop a NOT NULL constraint via ALTER, so we copy the table.
    Runs only when the existing column is still NOT NULL. The new shape already
    has every SPEC-001/SPEC-004 task column (this runs after the ADD COLUMNs).
    """
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    conn.exec_driver_sql(
        """
        CREATE TABLE tasks_new (
            id INTEGER PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            created_at DATETIME,
            position INTEGER NOT NULL DEFAULT 0,
            important BOOLEAN NOT NULL DEFAULT 0,
            deadline DATE,
            done BOOLEAN NOT NULL DEFAULT 0,
            event_date DATE,
            event_time TIME
        )
        """
    )
    conn.exec_driver_sql(
        """
        INSERT INTO tasks_new
            (id, project_id, text, created_at, position, important,
             deadline, done, event_date, event_time)
        SELECT id, project_id, text, created_at, position, important,
               deadline, done, event_date, event_time
        FROM tasks
        """
    )
    conn.exec_driver_sql("DROP TABLE tasks")
    conn.exec_driver_sql("ALTER TABLE tasks_new RENAME TO tasks")
    conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _migrate() -> None:
    """Add SPEC-001/SPEC-004 columns to pre-existing tables (idempotent).

    ``create_all`` never alters existing tables, so a database created under an
    earlier version would miss the new project/task columns. We add them with
    safe defaults, backfill task ``position``, rename project type values and
    relax ``tasks.project_id`` to allow standalone events.
    """
    with engine.begin() as conn:
        # projects -----------------------------------------------------------
        if not _column_exists(conn, "projects", "icon"):
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN icon VARCHAR(16)")
        if not _column_exists(conn, "projects", "type"):
            conn.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN type VARCHAR(16) "
                "NOT NULL DEFAULT 'temporary'"
            )
        if not _column_exists(conn, "projects", "pinned"):
            conn.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT 0"
            )
        if not _column_exists(conn, "projects", "pinned_at"):
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN pinned_at DATETIME")

        # SPEC-004 Feature 1: rename project type values in place.
        conn.exec_driver_sql(
            "UPDATE projects SET type = 'temporary' WHERE type = 'local'"
        )
        conn.exec_driver_sql(
            "UPDATE projects SET type = 'permanent' WHERE type = 'global'"
        )

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
        # SPEC-004 Feature 3: date-binding columns for events.
        if not _column_exists(conn, "tasks", "event_date"):
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN event_date DATE")
        if not _column_exists(conn, "tasks", "event_time"):
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN event_time TIME")

        # Relax project_id to NULL so standalone events are storable. Only an
        # old table still has the NOT NULL constraint; new ones already allow it.
        if _project_id_is_not_null(conn):
            _rebuild_tasks_nullable_project(conn)

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
