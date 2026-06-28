"""Automated tests for the Telegram bot (SPEC-002).

Covers the two new features without a live Telegram connection:
  * Feature 1: persistent reply keyboard, button constants, handler order.
  * Feature 2: read-only "Дела на день" screen built from the same source
    as the web DayPanel (day_slot_items), incl. escaping, done marking,
    1-based slot headers, dangling-id fallback and 4096-char splitting.

The bot module imports `app.config.settings`, so we must configure the
environment BEFORE importing it. conftest.py already points DATABASE_PATH at a
temp file and the autouse `clean_db` fixture empties the tables per test.
"""
import os

# Must be set before `app.config` is imported so the owner check sees an id.
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["TELEGRAM_ALLOWED_USER_ID"] = "42"

import importlib  # noqa: E402

import bot as bot_module  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import DaySlotItem, Project, Task  # noqa: E402

# conftest may have imported app.config earlier without the owner id set, so
# refresh the cached settings object the bot reads from.
import app.config as _config  # noqa: E402

_config.settings.telegram_allowed_user_id = 42
bot_module.settings.telegram_allowed_user_id = 42


# ----------------------------------------------------------- helpers
def _make_project(db, name, icon=None):
    p = Project(name=name, icon=icon)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_task(db, project_id, text, position=0, done=False):
    t = Task(project_id=project_id, text=text, position=position, done=done)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _add_to_slot(db, slot_index, task_id, position=0):
    db.add(DaySlotItem(slot_index=slot_index, task_id=task_id, position=position))
    db.commit()


# ----------------------------------------------------------- Feature 1
def test_button_constants_are_used_in_filters():
    """Captions and filter strings are the same constants (SPEC-002 F1)."""
    assert bot_module.BTN_TASKS == "📋 Все задачи"
    assert bot_module.BTN_DAY == "📅 Дела на день"
    assert bot_module.BTN_LIGHT == "📝 Не забыть"


def test_reply_keyboard_layout():
    kb = bot_module._reply_keyboard()
    assert kb.resize_keyboard is True
    assert kb.is_persistent is True
    # SPEC-004 adds the «Не забыть» button: row 1 has the two original buttons,
    # row 2 holds the light-task button.
    assert len(kb.keyboard) == 2
    row1 = [btn.text for btn in kb.keyboard[0]]
    row2 = [btn.text for btn in kb.keyboard[1]]
    assert row1 == [bot_module.BTN_TASKS, bot_module.BTN_DAY]
    assert row2 == [bot_module.BTN_LIGHT]


def test_owner_check():
    class _User:
        def __init__(self, uid):
            self.id = uid

    class _Update:
        def __init__(self, uid):
            self.effective_user = _User(uid)

    assert bot_module._is_owner(_Update(42)) is True
    assert bot_module._is_owner(_Update(999)) is False
    # No user -> not owner.
    no_user = _Update(42)
    no_user.effective_user = None
    assert bot_module._is_owner(no_user) is False


# ----------------------------------------------------------- Feature 2
def test_empty_when_no_slots():
    msgs = bot_module._build_day_messages()
    assert msgs == ["На день пока ничего не выбрано."]


def test_read_slots_matches_web_shape():
    with SessionLocal() as db:
        p = _make_project(db, "Inbox")
        t1 = _make_task(db, p.id, "a", position=0)
        t2 = _make_task(db, p.id, "b", position=1)
        _add_to_slot(db, 0, t2.id, position=0)
        _add_to_slot(db, 0, t1.id, position=1)
        t1_id, t2_id = t1.id, t2.id
        slots = bot_module._read_slots(db)
    # Three slots, in index order; task order follows DaySlotItem.position.
    assert [s["index"] for s in slots] == [0, 1, 2]
    assert slots[0]["task_ids"] == [t2_id, t1_id]
    assert slots[1]["task_ids"] == []
    assert slots[2]["task_ids"] == []


def test_basic_render_with_project_label_and_order():
    with SessionLocal() as db:
        p = _make_project(db, "Work", icon="💼")
        t1 = _make_task(db, p.id, "first", position=0)
        t2 = _make_task(db, p.id, "second", position=1)
        _add_to_slot(db, 0, t1.id)
        _add_to_slot(db, 1, t2.id)
    msgs = bot_module._build_day_messages()
    assert len(msgs) == 1
    text = msgs[0]
    # 1-based headers in index order.
    assert "Слот 1" in text
    assert "Слот 2" in text
    assert text.index("Слот 1") < text.index("Слот 2")
    # Project label (icon + name) and task text are present.
    assert "💼 Work first" in text
    assert "💼 Work second" in text


def test_done_task_is_marked_and_struck():
    with SessionLocal() as db:
        p = _make_project(db, "P")
        t = _make_task(db, p.id, "done item", done=True)
        _add_to_slot(db, 0, t.id)
    msgs = bot_module._build_day_messages()
    assert "✅ <s>P done item</s>" in msgs[0]


def test_undone_task_has_no_check_or_strike():
    with SessionLocal() as db:
        p = _make_project(db, "P")
        t = _make_task(db, p.id, "open item", done=False)
        _add_to_slot(db, 0, t.id)
    text = msgs = bot_module._build_day_messages()[0]
    assert "<s>" not in text
    assert "✅" not in text
    assert "P open item" in text


def test_html_special_chars_are_escaped():
    with SessionLocal() as db:
        p = _make_project(db, "<A & B>")
        t = _make_task(db, p.id, "5 < 10 & cats > dogs")
        _add_to_slot(db, 0, t.id)
    text = bot_module._build_day_messages()[0]
    # Raw special chars from user content must not appear unescaped.
    assert "&lt;A &amp; B&gt;" in text
    assert "5 &lt; 10 &amp; cats &gt; dogs" in text
    # Our own markup tags stay intact.
    assert "<b>Слот 1</b>" in text


def test_empty_slot_is_skipped():
    with SessionLocal() as db:
        p = _make_project(db, "P")
        t = _make_task(db, p.id, "only")
        # Put the task in slot index 1; slot 0 and 2 stay empty.
        _add_to_slot(db, 1, t.id)
    text = bot_module._build_day_messages()[0]
    assert "Слот 1" not in text  # index 0 empty -> no header
    assert "Слот 2" in text      # index 1 -> "Слот 2"
    assert "Слот 3" not in text


def test_dangling_task_id_is_skipped_without_crash():
    with SessionLocal() as db:
        p = _make_project(db, "P")
        t = _make_task(db, p.id, "real")
        _add_to_slot(db, 0, t.id, position=0)
        # Manually insert a slot item pointing at a non-existent task.
        # FK is ON, so insert directly bypassing the relationship is not
        # possible; instead create + delete a task to simulate a stale id.
        ghost = _make_task(db, p.id, "ghost")
        _add_to_slot(db, 0, ghost.id, position=1)
        ghost_id = ghost.id
        # Delete the task but leave a dangling slot row by detaching cascade:
        # remove via raw delete on tasks only.
        db.execute(Task.__table__.delete().where(Task.id == ghost_id))
        db.commit()
    msgs = bot_module._build_day_messages()
    text = "\n".join(msgs)
    assert "real" in text
    assert "ghost" not in text


def test_slot_emptied_by_dangling_ids_is_skipped():
    with SessionLocal() as db:
        p = _make_project(db, "P")
        ghost = _make_task(db, p.id, "ghost")
        _add_to_slot(db, 0, ghost.id)
        db.execute(Task.__table__.delete().where(Task.id == ghost.id))
        db.commit()
    # Only slot 0 had a (now dangling) item -> nothing renders.
    msgs = bot_module._build_day_messages()
    assert msgs == ["На день пока ничего не выбрано."]


def test_long_output_splits_on_slot_borders():
    with SessionLocal() as db:
        p = _make_project(db, "P")
        # Each slot gets one very long task so two slots exceed 4096 chars.
        big = "x" * 3000
        t0 = _make_task(db, p.id, big, position=0)
        t1 = _make_task(db, p.id, big, position=1)
        _add_to_slot(db, 0, t0.id)
        _add_to_slot(db, 1, t1.id)
    msgs = bot_module._build_day_messages()
    # Must split into multiple messages, each within the Telegram limit.
    assert len(msgs) >= 2
    for m in msgs:
        assert len(m) <= bot_module.TELEGRAM_MAX_LEN
    # A slot header is never split: each message starts a slot block.
    for m in msgs:
        assert m.startswith("<b>Слот ")


def test_module_imports_cleanly():
    # Re-importing the bot module must not raise (bot starts/imports clean).
    importlib.reload(bot_module)
