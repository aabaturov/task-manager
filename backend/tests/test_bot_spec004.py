"""Bot tests for SPEC-004 (file SPEC-004.md, header SPEC-002), Feature 4.

Unit-level coverage of the testable bot helpers without a live Telegram:
  * date/time parsing (event creation re-asks on bad input);
  * the read-only «Не забыть» message;
  * the "day before" reminder message builder;
  * the reminder time parsing.

The bot module reads `app.config.settings`; conftest points DATABASE_PATH at a
temp file and the autouse `clean_db` fixture empties the tables per test.
"""
import datetime as dt
import os

os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["TELEGRAM_ALLOWED_USER_ID"] = "42"

import bot as bot_module  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import LightTask, Project, Task  # noqa: E402

bot_module.settings.telegram_allowed_user_id = 42


# ----------------------------------------------------------- date/time parse
def test_parse_date_accepts_iso_and_dotted():
    assert bot_module.parse_date("2026-07-04") == dt.date(2026, 7, 4)
    assert bot_module.parse_date("04.07.2026") == dt.date(2026, 7, 4)
    assert bot_module.parse_date("  2026-07-04  ") == dt.date(2026, 7, 4)


def test_parse_date_rejects_garbage():
    assert bot_module.parse_date("not a date") is None
    assert bot_module.parse_date("2026-13-40") is None
    assert bot_module.parse_date("") is None


def test_parse_time_accepts_colon_and_variants():
    assert bot_module.parse_time("09:30") == dt.time(9, 30)
    assert bot_module.parse_time("9:30") == dt.time(9, 30)
    assert bot_module.parse_time("0930") == dt.time(9, 30)
    assert bot_module.parse_time("23:59") == dt.time(23, 59)


def test_parse_time_rejects_invalid():
    assert bot_module.parse_time("") is None
    assert bot_module.parse_time("25:00") is None
    assert bot_module.parse_time("12:99") is None
    assert bot_module.parse_time("abc") is None


def test_reminder_time_from_settings():
    bot_module.settings.reminder_time = "21:15"
    assert bot_module._reminder_time() == dt.time(21, 15)
    bot_module.settings.reminder_time = "bad"
    assert bot_module._reminder_time() == dt.time(20, 0)  # default


# ----------------------------------------------------------- «Не забыть»
def test_light_message_empty():
    assert bot_module._build_light_message() == "Список «не забыть» пуст."


def test_light_message_lists_in_order_with_done_struck():
    with SessionLocal() as db:
        db.add(LightTask(text="first", position=0, created_at=dt.datetime(2026, 1, 1)))
        db.add(
            LightTask(
                text="second", done=True, position=1,
                created_at=dt.datetime(2026, 1, 2),
            )
        )
        db.commit()
    msg = bot_module._build_light_message()
    assert "<b>Не забыть</b>" in msg
    assert "• first" in msg
    assert "✅ <s>second</s>" in msg
    assert msg.index("first") < msg.index("second")


def test_light_message_escapes_html():
    with SessionLocal() as db:
        db.add(LightTask(text="a < b & c", position=0))
        db.commit()
    msg = bot_module._build_light_message()
    assert "a &lt; b &amp; c" in msg


# ----------------------------------------------------------- reminder body
def test_reminder_none_when_no_events():
    assert bot_module._build_reminder_message(dt.date(2026, 7, 4)) is None


def test_reminder_lists_standalone_and_project_events_sorted():
    day = dt.date(2026, 7, 4)
    with SessionLocal() as db:
        p = Project(name="Work", icon="💼")
        db.add(p)
        db.commit()
        db.refresh(p)
        # standalone event at 15:00
        db.add(
            Task(
                project_id=None, text="solo", event_date=day,
                event_time=dt.time(15, 0), position=0,
            )
        )
        # project task event at 09:00
        db.add(
            Task(
                project_id=p.id, text="meeting", event_date=day,
                event_time=dt.time(9, 0), position=0,
            )
        )
        # another day -> excluded
        db.add(
            Task(
                project_id=None, text="other", event_date=dt.date(2026, 7, 5),
                event_time=dt.time(10, 0), position=0,
            )
        )
        db.commit()
    msg = bot_module._build_reminder_message(day)
    assert msg is not None
    assert "2026-07-04" in msg
    assert "09:00 — 💼 Work meeting" in msg
    assert "15:00 — solo" in msg
    # Sorted by time: meeting (09:00) before solo (15:00).
    assert msg.index("meeting") < msg.index("solo")
    # Other-day event excluded.
    assert "other" not in msg


def test_reminder_marks_done_event():
    day = dt.date(2026, 7, 4)
    with SessionLocal() as db:
        db.add(
            Task(
                project_id=None, text="did it", event_date=day,
                event_time=dt.time(9, 0), done=True, position=0,
            )
        )
        db.commit()
    msg = bot_module._build_reminder_message(day)
    assert "✅" in msg and "did it" in msg
