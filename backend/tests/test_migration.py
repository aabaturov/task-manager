"""Verify a v1.0 database is migrated in place (SPEC-001 compatibility)."""
import os
import sqlite3
import subprocess
import sys
import textwrap

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_v1_database_migrates(tmp_path):
    db = tmp_path / "v1.db"

    # Build a v1.0-shaped database (no SPEC-001 columns) with sample rows.
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY,
            name VARCHAR(200) UNIQUE NOT NULL,
            created_at DATETIME
        );
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            created_at DATETIME
        );
        """
    )
    conn.execute("INSERT INTO projects (id, name, created_at) VALUES (1, 'Old', '2025-01-01')")
    conn.execute("INSERT INTO tasks (id, project_id, text, created_at) VALUES (1, 1, 'first', '2025-01-01 10:00')")
    conn.execute("INSERT INTO tasks (id, project_id, text, created_at) VALUES (2, 1, 'second', '2025-01-01 11:00')")
    conn.commit()
    conn.close()

    # Run init_db() in a fresh process so it builds its engine from this DB.
    code = textwrap.dedent(
        """
        from app.database import init_db
        init_db()
        """
    )
    env = {**os.environ, "DATABASE_PATH": str(db), "PYTHONPATH": BACKEND_DIR}
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(db)
    project_cols = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
    task_cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    # New columns present
    assert {"icon", "type", "pinned", "pinned_at"} <= project_cols
    assert {"position", "important", "deadline", "done"} <= task_cols
    # New table created
    assert "day_slot_items" in tables

    # Defaults applied to existing rows. SPEC-004 renames the type value:
    # a v1.0 row has no type, so the ADD COLUMN default "temporary" applies.
    proj = conn.execute("SELECT type, pinned FROM projects WHERE id=1").fetchone()
    assert proj == ("temporary", 0)

    # Positions backfilled by created_at order
    positions = conn.execute(
        "SELECT id, position FROM tasks ORDER BY created_at"
    ).fetchall()
    assert positions == [(1, 0), (2, 1)]

    # SPEC-004: event columns added and tasks.project_id relaxed to NULL.
    assert {"event_date", "event_time"} <= task_cols
    pid_notnull = next(
        row[3] for row in conn.execute("PRAGMA table_info(tasks)") if row[1] == "project_id"
    )
    assert pid_notnull == 0, "project_id must allow NULL for standalone events"
    assert "light_tasks" in tables
    conn.close()


def test_spec001_type_values_renamed(tmp_path):
    """A SPEC-001-shaped DB with old 'local'/'global' types is renamed."""
    db = tmp_path / "spec001.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY,
            name VARCHAR(200) UNIQUE NOT NULL,
            created_at DATETIME,
            icon VARCHAR(16),
            type VARCHAR(10) NOT NULL DEFAULT 'local',
            pinned BOOLEAN NOT NULL DEFAULT 0,
            pinned_at DATETIME
        );
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            created_at DATETIME,
            position INTEGER NOT NULL DEFAULT 0,
            important BOOLEAN NOT NULL DEFAULT 0,
            deadline DATE,
            done BOOLEAN NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute("INSERT INTO projects (id, name, type) VALUES (1, 'A', 'local')")
    conn.execute("INSERT INTO projects (id, name, type) VALUES (2, 'B', 'global')")
    conn.execute("INSERT INTO tasks (id, project_id, text) VALUES (1, 1, 't')")
    conn.commit()
    conn.close()

    code = textwrap.dedent(
        """
        from app.database import init_db
        init_db()
        """
    )
    env = {**os.environ, "DATABASE_PATH": str(db), "PYTHONPATH": BACKEND_DIR}
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(db)
    types = dict(conn.execute("SELECT name, type FROM projects"))
    assert types == {"A": "temporary", "B": "permanent"}
    # Task data survived the project_id NOT NULL -> NULL rebuild.
    assert conn.execute("SELECT text FROM tasks WHERE id=1").fetchone() == ("t",)
    conn.close()
