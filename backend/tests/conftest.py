import os
import tempfile

# Configure the app for tests BEFORE importing it.
_DB = os.path.join(tempfile.gettempdir(), "tm_spec001_api.db")
os.environ["DATABASE_PATH"] = _DB
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("WEB_LOGIN", "u")
os.environ.setdefault("WEB_PASSWORD", "p")
os.environ["STATIC_DIR"] = "/nonexistent-skip-static"

try:
    os.remove(_DB)
except FileNotFoundError:
    pass

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DaySlotItem, Project, Task  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    """Start every test from an empty database."""
    db = SessionLocal()
    try:
        db.query(DaySlotItem).delete()
        db.query(Task).delete()
        db.query(Project).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    c = TestClient(app)
    r = c.post("/api/login", json={"login": "u", "password": "p"})
    assert r.status_code == 200
    return c
