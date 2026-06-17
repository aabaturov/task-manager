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

    # Defaults applied to existing rows
    proj = conn.execute("SELECT type, pinned FROM projects WHERE id=1").fetchone()
    assert proj == ("local", 0)

    # Positions backfilled by created_at order
    positions = conn.execute(
        "SELECT id, position FROM tasks ORDER BY created_at"
    ).fetchall()
    assert positions == [(1, 0), (2, 1)]
    conn.close()
