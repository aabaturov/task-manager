from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # SPEC-001 Feature 1: optional emoji icon shown on web and in the bot.
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # SPEC-001 Feature 6: visual board organisation.
    type: Mapped[str] = mapped_column(String(10), default="local", nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Order within the "pinned" section (set when a project is pinned).
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Task.position",
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # SPEC-001 Feature 5: manual ordering within a project.
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # SPEC-001 Feature 3: "important" flag and optional deadline.
    important: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    # SPEC-001 Feature 4: "done" status (strike-through, not deletion).
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="tasks")

    slot_item: Mapped["DaySlotItem | None"] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class DaySlotItem(Base):
    """SPEC-001 Feature 8: one membership of a task in a day-panel slot.

    Three fixed slots (index 0..2). A task can be in at most one slot
    (unique task_id). ``position`` orders tasks inside a slot.
    """

    __tablename__ = "day_slot_items"
    __table_args__ = (UniqueConstraint("task_id", name="uq_day_slot_task"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    task: Mapped["Task"] = relationship(back_populates="slot_item")
