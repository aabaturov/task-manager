from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    login: str
    password: str


# ----------------------------------------------------------------- projects
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    icon: str | None = Field(default=None, max_length=16)
    type: Literal["local", "global"] = "local"


class ProjectUpdate(BaseModel):
    """All fields optional; only the provided ones are applied.

    ``icon`` provided as null/empty clears the icon. ``pinned`` toggles the
    pin (server enforces at most 3 pinned projects).
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    icon: str | None = Field(default=None, max_length=16)
    type: Literal["local", "global"] | None = None
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
    project_id: int
    text: str
    created_at: datetime
    position: int
    important: bool
    deadline: date | None
    done: bool


class ReorderIn(BaseModel):
    task_ids: list[int]


# --------------------------------------------------------------- day slots
class DaySlotOut(BaseModel):
    index: int
    task_ids: list[int]


class DaySlotSet(BaseModel):
    task_ids: list[int]
