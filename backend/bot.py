"""Telegram bot for the Task Manager.

Owner-only. Sends plain text -> choose "bind to a date" (event) or a project ->
task/event is saved. /tasks lists all tasks grouped by project with delete
buttons. Shares the same SQLite database as the web app via SQLAlchemy.

SPEC-002 (history):
  * A persistent reply keyboard on /start with two buttons.
  * A read-only "Дела на день" (day slots) screen mirroring the web DayPanel.

SPEC-004 (file SPEC-004.md, header SPEC-002):
  * Feature 4: a date-binding step in the add-task flow (creates events), a
    read-only "не забыть" (light tasks) button, and a "day before" reminder
    scheduler with catch-up of today's missed reminder on startup.
"""
import datetime as dt
import html
import logging
import re

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from sqlalchemy import func

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import DaySlotItem, LightTask, Project, Task


# --------------------------------------------------------------- constants
# Button captions and the filter strings MUST be the same constants so the
# emojis are matched character-for-character (SPEC-002 F1 edge cases).
BTN_TASKS = "📋 Все задачи"
BTN_DAY = "📅 Дела на день"
BTN_LIGHT = "📝 Не забыть"

# Number of day slots, mirroring backend `SLOT_COUNT` (SPEC-001 F8 / web).
SLOT_COUNT = 3

# Telegram hard limit per message; we split day-slot output on slot borders.
TELEGRAM_MAX_LEN = 4096

# Callback-data prefix for "bind this new task to a date" (creates an event).
CB_BIND_DATE = "bind_date"


def _reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard (SPEC-002 F1 + SPEC-004 «Не забыть»)."""
    return ReplyKeyboardMarkup(
        [[BTN_TASKS, BTN_DAY], [BTN_LIGHT]],
        resize_keyboard=True,
        is_persistent=True,
    )


def _label(project: Project) -> str:
    """Project name prefixed with its emoji icon when present (SPEC-001 F1)."""
    icon = (project.icon or "").strip()
    return f"{icon} {project.name}".strip() if icon else project.name


def _esc(text: str) -> str:
    """Escape user text for HTML parse mode (at least < > &)."""
    return html.escape(text or "", quote=False)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Per-chat add-task flow state, kept until a project/date is chosen.
#   PENDING[chat_id] = {"text": str, "stage": str, "date": date | None}
# stages: "choose" (project/date), "await_date", "await_time".
PENDING: dict[int, dict] = {}


# --------------------------------------------------------------- timezone
def _tz():
    """Return the configured timezone (falls back to UTC)."""
    if ZoneInfo is None:
        return dt.timezone.utc
    try:
        return ZoneInfo(settings.timezone)
    except Exception:  # pragma: no cover - bad TZ name -> UTC
        logger.warning("Unknown APP_TIMEZONE %r, using UTC", settings.timezone)
        return dt.timezone.utc


def _today() -> dt.date:
    return dt.datetime.now(_tz()).date()


def parse_date(text: str) -> dt.date | None:
    """Parse a user-typed date. Accepts YYYY-MM-DD and DD.MM.YYYY.

    Returns ``None`` when the text is not a valid date (bot re-asks).
    """
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(text: str) -> dt.time | None:
    """Parse a user-typed time HH:MM (or HH.MM / HHMM). None if invalid."""
    text = (text or "").strip()
    m = re.fullmatch(r"(\d{1,2})[:.\- ]?(\d{2})", text)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return dt.time(hour=hh, minute=mm)
    return None


def _reminder_time() -> dt.time:
    """Parse REMINDER_TIME (HH:MM) from settings, default 20:00."""
    t = parse_time(settings.reminder_time)
    return t or dt.time(hour=20, minute=0)


# --------------------------------------------------------------- ownership
def _is_owner(update: Update) -> bool:
    if settings.telegram_allowed_user_id is None:
        return False
    user = update.effective_user
    return user is not None and user.id == settings.telegram_allowed_user_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    await update.message.reply_text(
        "Привет! Я твой менеджер задач.\n\n"
        "• Пришли любой текст — я предложу привязать его к дате (событие) "
        "или выбрать проект.\n"
        f"• «{BTN_TASKS}» — показать все задачи с кнопками удаления.\n"
        f"• «{BTN_DAY}» — посмотреть слоты на день.\n"
        f"• «{BTN_LIGHT}» — показать список «не забыть» (только просмотр).",
        reply_markup=_reply_keyboard(),
    )


# --------------------------------------------------------------- add flow
async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    chat_id = update.effective_chat.id
    state = PENDING.get(chat_id)

    # Mid-flow: we may be waiting for a date or a time of an event.
    if state and state.get("stage") == "await_date":
        await _on_date_input(update, text, state)
        return
    if state and state.get("stage") == "await_time":
        await _on_time_input(update, text, state)
        return

    # New task text -> offer "bind to date" or a project.
    with SessionLocal() as db:
        projects = db.query(Project).order_by(Project.created_at).all()
        project_buttons = [
            [InlineKeyboardButton(_label(p), callback_data=f"pick:{p.id}")]
            for p in projects
        ]

    PENDING[chat_id] = {"text": text, "stage": "choose", "date": None}
    buttons = [
        [InlineKeyboardButton("📅 Привязать к дате", callback_data=CB_BIND_DATE)]
    ] + project_buttons
    hint = "" if project_buttons else "\n\n(Проектов пока нет — создай в вебе.)"
    await update.message.reply_text(
        f"Что сделать с задачей?\n«{text}»{hint}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def bind_to_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose «Привязать к дате»: ask the date, then the time."""
    query = update.callback_query
    await query.answer()
    if not _is_owner(update):
        return
    chat_id = update.effective_chat.id
    state = PENDING.get(chat_id)
    if not state:
        await query.edit_message_text("Задача устарела, пришли её ещё раз.")
        return
    state["stage"] = "await_date"
    state["project_id"] = None  # standalone event
    await query.edit_message_text(
        "На какую дату? Пришли дату в формате ГГГГ-ММ-ДД или ДД.ММ.ГГГГ."
    )


async def _on_date_input(update: Update, text: str, state: dict) -> None:
    d = parse_date(text)
    if d is None:
        await update.message.reply_text(
            "Не понял дату. Пришли в формате ГГГГ-ММ-ДД или ДД.ММ.ГГГГ."
        )
        return
    state["date"] = d
    state["stage"] = "await_time"
    await update.message.reply_text(
        "Во сколько? Пришли время в формате ЧЧ:ММ (время обязательно)."
    )


async def _on_time_input(update: Update, text: str, state: dict) -> None:
    t = parse_time(text)
    if t is None:
        await update.message.reply_text(
            "Не понял время. Пришли в формате ЧЧ:ММ (например 09:30)."
        )
        return
    chat_id = update.effective_chat.id
    event_text = state["text"]
    event_date = state["date"]

    with SessionLocal() as db:
        # When binding an existing project task we carry its id in the state.
        bind_task_id = state.get("bind_task_id")
        if bind_task_id is not None:
            task = db.get(Task, bind_task_id)
            if task is None:
                PENDING.pop(chat_id, None)
                await update.message.reply_text("Задача больше не существует.")
                return
            task.event_date = event_date
            task.event_time = t
            db.commit()
            label = task.text
        else:
            task = Task(
                project_id=None,
                text=event_text,
                event_date=event_date,
                event_time=t,
                position=0,
            )
            db.add(task)
            db.commit()
            label = event_text

    PENDING.pop(chat_id, None)
    await update.message.reply_text(
        f"✅ Событие создано на {event_date.isoformat()} "
        f"{t.strftime('%H:%M')}:\n«{label}»"
    )


async def pick_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_owner(update):
        return

    project_id = int(query.data.split(":", 1)[1])
    chat_id = update.effective_chat.id
    state = PENDING.get(chat_id)
    if not state:
        await query.edit_message_text("Задача устарела, пришли её ещё раз.")
        return
    text = state["text"]

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            PENDING.pop(chat_id, None)
            await query.edit_message_text("Проект больше не существует.")
            return
        max_pos = (
            db.query(func.max(Task.position))
            .filter(Task.project_id == project_id)
            .scalar()
        )
        position = 0 if max_pos is None else max_pos + 1
        task = Task(project_id=project_id, text=text, position=position)
        db.add(task)
        db.commit()
        db.refresh(task)
        project_label = _label(project)
        task_id = task.id

    # After the project is chosen, offer to bind a date to this project task.
    PENDING[chat_id] = {"text": text, "stage": "choose", "bind_task_id": task_id}
    buttons = [
        [
            InlineKeyboardButton("Да, привязать к дате", callback_data=CB_BIND_DATE),
            InlineKeyboardButton("Нет", callback_data="no_date"),
        ]
    ]
    await query.edit_message_text(
        f"✅ Сохранено в «{project_label}»:\n«{text}»\n\nПривязать к дате?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def skip_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User answered «Нет» to binding a project task to a date."""
    query = update.callback_query
    await query.answer()
    if not _is_owner(update):
        return
    chat_id = update.effective_chat.id
    state = PENDING.pop(chat_id, None)
    text = state["text"] if state else ""
    await query.edit_message_text(f"Готово. Задача «{text}» сохранена без даты.")


# --------------------------------------------------------------- task list
async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    await _send_task_list(update.message.reply_text)


async def show_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply-keyboard button «📋 Все задачи»: same output as /tasks."""
    if not _is_owner(update):
        return
    await _send_task_list(update.message.reply_text)


async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_owner(update):
        await query.answer()
        return

    task_id = int(query.data.split(":", 1)[1])
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is not None:
            db.delete(task)
            db.commit()
    await query.answer("Удалено")
    await _send_task_list(query.edit_message_text)


async def _send_task_list(send) -> None:
    with SessionLocal() as db:
        projects = db.query(Project).order_by(Project.created_at).all()
        lines: list[str] = []
        buttons: list[list[InlineKeyboardButton]] = []
        has_any = False
        for project in projects:
            project_tasks = (
                db.query(Task)
                .filter(Task.project_id == project.id)
                .order_by(Task.position)
                .all()
            )
            if not project_tasks:
                continue
            has_any = True
            lines.append(f"\n📁 {_label(project)}")
            for task in project_tasks:
                lines.append(f"  • {task.text}")
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"🗑 {task.text[:40]}",
                            callback_data=f"del:{task.id}",
                        )
                    ]
                )

    if not has_any:
        await send("Задач пока нет.")
        return

    await send(
        "Твои задачи:\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# --------------------------------------------------------------- day slots
def _read_slots(db) -> list[dict]:
    """Read day slots from the same source as the web DayPanel.

    Mirrors `app.main.get_day_slots`: items ordered by (slot_index, position),
    grouped into SLOT_COUNT slots, each holding an ordered list of task_ids.
    """
    items = (
        db.query(DaySlotItem)
        .order_by(DaySlotItem.slot_index, DaySlotItem.position)
        .all()
    )
    by_slot: dict[int, list[int]] = {i: [] for i in range(SLOT_COUNT)}
    for item in items:
        if 0 <= item.slot_index < SLOT_COUNT:
            by_slot[item.slot_index].append(item.task_id)
    return [
        {"index": i, "task_ids": by_slot[i]} for i in range(SLOT_COUNT)
    ]


def _build_day_messages() -> list[str]:
    """Build the «Дела на день» message(s).

    One block per non-empty slot, in `index` order. Done tasks render as
    ``✅ <s>текст</s>``. Blocks packed within TELEGRAM_MAX_LEN, never splitting
    a slot. Returns a list of message strings (HTML), or a single "nothing" one.
    """
    with SessionLocal() as db:
        slots = _read_slots(db)
        task_by_id = {t.id: t for t in db.query(Task).all()}
        project_by_id = {p.id: p for p in db.query(Project).all()}

        blocks: list[str] = []
        for slot in slots:
            task_lines: list[str] = []
            for tid in slot["task_ids"]:
                task = task_by_id.get(tid)
                if task is None:
                    continue
                project = project_by_id.get(task.project_id)
                label = _esc(_label(project)) if project is not None else ""
                text = _esc(task.text)
                body = f"{label} {text}".strip() if label else text
                if task.done:
                    task_lines.append(f"✅ <s>{body}</s>")
                else:
                    task_lines.append(body)
            if not task_lines:
                continue
            header = f"<b>Слот {slot['index'] + 1}</b>"
            blocks.append(header + "\n" + "\n".join(task_lines))

    if not blocks:
        return ["На день пока ничего не выбрано."]

    messages: list[str] = []
    current = ""
    for block in blocks:
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) <= TELEGRAM_MAX_LEN:
            current = candidate
        else:
            if current:
                messages.append(current)
            current = block
    if current:
        messages.append(current)
    return messages


async def day_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply-keyboard button «📅 Дела на день»: read-only day-slots screen."""
    if not _is_owner(update):
        return
    for message in _build_day_messages():
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)


# --------------------------------------------------------------- light tasks
def _build_light_message() -> str:
    """Build the read-only «Не забыть» message (SPEC-004 Feature 4).

    Lists light tasks in creation order; done ones are struck through. Empty
    list -> a "список пуст" notice. HTML-escaped, never offers actions.
    """
    with SessionLocal() as db:
        items = (
            db.query(LightTask)
            .order_by(LightTask.created_at, LightTask.position, LightTask.id)
            .all()
        )
        lines: list[str] = []
        for item in items:
            text = _esc(item.text)
            if item.done:
                lines.append(f"✅ <s>{text}</s>")
            else:
                lines.append(f"• {text}")
    if not lines:
        return "Список «не забыть» пуст."
    return "<b>Не забыть</b>\n" + "\n".join(lines)


async def light_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply-keyboard button «📝 Не забыть»: read-only light-task list."""
    if not _is_owner(update):
        return
    await update.message.reply_text(
        _build_light_message(), parse_mode=ParseMode.HTML
    )


# --------------------------------------------------------------- reminders
def _events_on(db, day: dt.date) -> list[Task]:
    """Project tasks and standalone events bound to ``day`` (sorted)."""
    return (
        db.query(Task)
        .filter(Task.event_date == day)
        .order_by(Task.event_time, Task.id)
        .all()
    )


def _build_reminder_message(day: dt.date) -> str | None:
    """Reminder text listing events on ``day``; None if there are none."""
    with SessionLocal() as db:
        events = _events_on(db, day)
        project_by_id = {p.id: p for p in db.query(Project).all()}
        if not events:
            return None
        lines: list[str] = []
        for ev in events:
            t = ev.event_time.strftime("%H:%M") if ev.event_time else "--:--"
            project = project_by_id.get(ev.project_id)
            label = (
                _esc(_label(project)) + " " if project is not None else ""
            )
            text = _esc(ev.text)
            mark = "✅ " if ev.done else ""
            lines.append(f"{mark}{t} — {label}{text}".strip())
    header = f"<b>Завтра ({day.isoformat()}) запланировано:</b>"
    return header + "\n" + "\n".join(lines)


async def _send_reminder_for(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: send tomorrow's events reminder to the owner."""
    owner = settings.telegram_allowed_user_id
    if owner is None:
        return
    tomorrow = _today() + dt.timedelta(days=1)
    message = _build_reminder_message(tomorrow)
    if message is None:
        return
    await context.bot.send_message(
        chat_id=owner, text=message, parse_mode=ParseMode.HTML
    )


def _schedule_reminders(app: Application) -> None:
    """Schedule the daily "day before" reminder and catch up on startup.

    Daily job fires at REMINDER_TIME (app timezone). On startup, if that time
    has already passed today, send today's reminder once (catch-up); older
    missed reminders are skipped (v1 limitation).
    """
    job_queue = app.job_queue
    if job_queue is None:  # pragma: no cover - requires job-queue extra
        logger.warning("JobQueue unavailable; reminders disabled")
        return

    tz = _tz()
    rt = _reminder_time()
    job_queue.run_daily(_send_reminder_for, time=dt.time(rt.hour, rt.minute, tzinfo=tz))

    now = dt.datetime.now(tz)
    scheduled_today = now.replace(
        hour=rt.hour, minute=rt.minute, second=0, microsecond=0
    )
    if now >= scheduled_today:
        # The today reminder time already passed -> catch up once now.
        job_queue.run_once(_send_reminder_for, when=1)


def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

    init_db()

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CallbackQueryHandler(pick_project, pattern=r"^pick:\d+$"))
    app.add_handler(CallbackQueryHandler(delete_task, pattern=r"^del:\d+$"))
    app.add_handler(
        CallbackQueryHandler(bind_to_date, pattern=rf"^{CB_BIND_DATE}$")
    )
    app.add_handler(CallbackQueryHandler(skip_date, pattern=r"^no_date$"))
    # Exact button handlers MUST come before the catch-all add-task handler,
    # otherwise pressing a button would create a task named after it.
    app.add_handler(MessageHandler(filters.Text([BTN_TASKS]), show_all_tasks))
    app.add_handler(MessageHandler(filters.Text([BTN_DAY]), day_screen))
    app.add_handler(MessageHandler(filters.Text([BTN_LIGHT]), light_screen))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)
    )

    _schedule_reminders(app)

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
