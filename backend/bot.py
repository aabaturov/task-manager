"""Telegram bot for the Task Manager.

Owner-only. Sends plain text -> choose a project via inline buttons -> task is
saved. /tasks lists all tasks grouped by project with delete buttons.
Shares the same SQLite database as the web app via SQLAlchemy.

SPEC-002:
  * A persistent reply keyboard on /start with two buttons.
  * A read-only "Дела на день" (day slots) screen mirroring the web DayPanel.
"""
import html
import logging

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
from app.models import DaySlotItem, Project, Task


# --------------------------------------------------------------- constants
# Button captions and the filter strings MUST be the same constants so the
# emojis are matched character-for-character (SPEC-002 F1 edge cases).
BTN_TASKS = "📋 Все задачи"
BTN_DAY = "📅 Дела на день"

# Number of day slots, mirroring backend `SLOT_COUNT` (SPEC-001 F8 / web).
SLOT_COUNT = 3

# Telegram hard limit per message; we split day-slot output on slot borders.
TELEGRAM_MAX_LEN = 4096


def _reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard with both buttons in one row (SPEC-002 F1)."""
    return ReplyKeyboardMarkup(
        [[BTN_TASKS, BTN_DAY]],
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

# Pending task text keyed by chat, kept until a project is chosen.
PENDING: dict[int, str] = {}


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
        "• Пришли любой текст — я предложу выбрать проект и сохраню задачу.\n"
        f"• «{BTN_TASKS}» — показать все задачи с кнопками удаления.\n"
        f"• «{BTN_DAY}» — посмотреть слоты на день.",
        reply_markup=_reply_keyboard(),
    )


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    with SessionLocal() as db:
        projects = db.query(Project).order_by(Project.created_at).all()
        if not projects:
            await update.message.reply_text(
                "Пока нет ни одного проекта. Создай проект в веб-интерфейсе, "
                "потом возвращайся."
            )
            return
        buttons = [
            [InlineKeyboardButton(_label(p), callback_data=f"pick:{p.id}")]
            for p in projects
        ]

    PENDING[update.effective_chat.id] = text
    await update.message.reply_text(
        f"Куда сохранить задачу?\n«{text}»",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def pick_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_owner(update):
        return

    project_id = int(query.data.split(":", 1)[1])
    text = PENDING.pop(update.effective_chat.id, None)
    if text is None:
        await query.edit_message_text("Задача устарела, пришли её ещё раз.")
        return

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            await query.edit_message_text("Проект больше не существует.")
            return
        max_pos = (
            db.query(func.max(Task.position))
            .filter(Task.project_id == project_id)
            .scalar()
        )
        position = 0 if max_pos is None else max_pos + 1
        db.add(Task(project_id=project_id, text=text, position=position))
        db.commit()
        project_label = _label(project)

    await query.edit_message_text(f"✅ Сохранено в «{project_label}»:\n«{text}»")


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
    Returns ``[{"index": int, "task_ids": [int, ...]}, ...]`` for indexes
    0..SLOT_COUNT-1, in order.
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

    One block per non-empty slot, in `index` order. Each block:
      ``Слот N`` (1-based) header + a line per task, where each task shows the
      project label and text. Done tasks render as ``✅ <s>текст</s>``.
    User text and project labels are HTML-escaped. Blocks are packed into
    messages without exceeding TELEGRAM_MAX_LEN, never splitting a slot.
    Returns a list of message strings (HTML), or a single "nothing" message.
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
                    # Defensive fallback: dangling id -> skip silently.
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
                # Empty slot (or emptied by dangling ids) -> skip, no header.
                continue
            header = f"<b>Слот {slot['index'] + 1}</b>"
            blocks.append(header + "\n" + "\n".join(task_lines))

    if not blocks:
        return ["На день пока ничего не выбрано."]

    # Pack blocks into messages, never splitting a slot across messages.
    messages: list[str] = []
    current = ""
    for block in blocks:
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) <= TELEGRAM_MAX_LEN:
            current = candidate
        else:
            if current:
                messages.append(current)
            # A single oversized block still gets sent as its own message.
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


def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

    # Ensure tables exist (web service usually creates them, but be safe).
    init_db()

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CallbackQueryHandler(pick_project, pattern=r"^pick:\d+$"))
    app.add_handler(CallbackQueryHandler(delete_task, pattern=r"^del:\d+$"))
    # Exact button handlers MUST come before the catch-all add-task handler,
    # otherwise pressing a button would create a task named after it.
    app.add_handler(MessageHandler(filters.Text([BTN_TASKS]), show_all_tasks))
    app.add_handler(MessageHandler(filters.Text([BTN_DAY]), day_screen))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)
    )

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
