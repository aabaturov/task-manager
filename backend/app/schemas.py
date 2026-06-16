from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    login: str
    password: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


class TaskCreate(BaseModel):
    project_id: int
    text: str = Field(min_length=1)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    text: str
    created_at: datetime
