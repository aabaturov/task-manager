"""Telegram bot for the Task Manager.

Owner-only. Sends plain text -> choose a project via inline buttons -> task is
saved. /tasks lists all tasks grouped by project with delete buttons.
Shares the same SQLite database as the web app via SQLAlchemy.
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from app.models import Project, Task


def _label(project: Project) -> str:
    """Project name prefixed with its emoji icon when present (SPEC-001 F1)."""
    icon = (project.icon or "").strip()
    return f"{icon} {project.name}".strip() if icon else project.name

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
        "• /tasks — показать все задачи с кнопками удаления."
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
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)
    )

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
