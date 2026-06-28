from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    login: str
    password: str


# ----------------------------------------------------------------- projects
# SPEC-004 Feature 1: type values renamed "local"->"temporary",
# "global"->"permanent"; default is "temporary".
ProjectType = Literal["temporary", "permanent"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    icon: str | None = Field(default=None, max_length=16)
    type: ProjectType = "temporary"


class ProjectUpdate(BaseModel):
    """All fields optional; only the provided ones are applied.

    ``icon`` provided as null/empty clears the icon. ``pinned`` toggles the
    pin (server enforces at most 3 pinned projects).
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    icon: str | None = Field(default=None, max_length=16)
    type: ProjectType | None = None
    pinned: bool | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    icon: str | None
    type: str
    pinned: bool
    pinned_at: datetime | None


# -------------------------------------------------------------------- tasks
class TaskCreate(BaseModel):
    project_id: int
    text: str = Field(min_length=1)


class TaskUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    important: bool | None = None
    deadline: date | None = None
    done: bool | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    text: str
    created_at: datetime
    position: int
    important: bool
    deadline: date | None
    done: bool
    # SPEC-004 Feature 3: date-binding (event) fields.
    event_date: date | None
    event_time: time | None


class ReorderIn(BaseModel):
    task_ids: list[int]


# --------------------------------------------------------------- day slots
class DaySlotOut(BaseModel):
    index: int
    task_ids: list[int]


class DaySlotSet(BaseModel):
    task_ids: list[int]


# ----------------------------------------------------------- light tasks
# SPEC-004 Feature 2: standalone "не забыть" list.
class LightTaskCreate(BaseModel):
    text: str = Field(min_length=1)


class LightTaskUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    done: bool | None = None


class LightTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    done: bool
    created_at: datetime
    position: int


# --------------------------------------------------------- calendar events
# SPEC-004 Feature 3: an "event" is a task bound to a date and time. It may be
# standalone (no project) or a project task that was given a date/time.
class EventCreate(BaseModel):
    """Create a standalone event from the calendar (text + date + time)."""

    text: str = Field(min_length=1)
    event_date: date
    event_time: time  # required in v1


class EventUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    event_date: date | None = None
    event_time: time | None = None
    done: bool | None = None


class TaskEventBind(BaseModel):
    """Attach/detach a date-binding to an existing project task.

    Passing ``event_date``/``event_time`` as null clears the binding (the task
    leaves the calendar but stays a normal task). When binding, both are
    required (time is mandatory in v1).
    """

    event_date: date | None = None
    event_time: time | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    text: str
    event_date: date
    event_time: time | None
    done: bool
