import os
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import schemas
from .auth import (
    check_credentials,
    login_session,
    logout_session,
    require_auth,
)
from .config import settings
from .database import SessionLocal, init_db
from .models import DaySlotItem, LightTask, Project, Task

PINNED_LIMIT = 3  # SPEC-001 Feature 6
SLOT_COUNT = 3  # SPEC-001 Feature 8

app = FastAPI(title="Task Manager")
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# Create tables on import so they exist regardless of how the app is launched.
init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _next_position(db: Session, project_id: int) -> int:
    max_pos = (
        db.query(func.max(Task.position))
        .filter(Task.project_id == project_id)
        .scalar()
    )
    return 0 if max_pos is None else max_pos + 1


# ---------------------------------------------------------------- auth routes
@app.post("/api/login")
def login(data: schemas.LoginIn, request: Request):
    if not check_credentials(data.login, data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    login_session(request)
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request):
    logout_session(request)
    return {"ok": True}


@app.get("/api/me", dependencies=[Depends(require_auth)])
def me():
    return {"ok": True}


# ------------------------------------------------------------- project routes
@app.get(
    "/api/projects",
    response_model=list[schemas.ProjectOut],
    dependencies=[Depends(require_auth)],
)
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at).all()


@app.post(
    "/api/projects",
    response_model=schemas.ProjectOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
)
def create_project(data: schemas.ProjectCreate, db: Session = Depends(get_db)):
    icon = (data.icon or "").strip() or None
    project = Project(name=data.name.strip(), icon=icon, type=data.type)
    db.add(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this name already exists",
        )
    db.refresh(project)
    return project


@app.patch(
    "/api/projects/{project_id}",
    response_model=schemas.ProjectOut,
    dependencies=[Depends(require_auth)],
)
def update_project(
    project_id: int, data: schemas.ProjectUpdate, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    fields = data.model_dump(exclude_unset=True)

    if "name" in fields and fields["name"] is not None:
        project.name = fields["name"].strip()
    if "icon" in fields:
        icon = (fields["icon"] or "").strip()
        project.icon = icon or None
    if "type" in fields and fields["type"] is not None:
        project.type = fields["type"]
    if "pinned" in fields and fields["pinned"] is not None:
        _set_pinned(db, project, fields["pinned"])

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this name already exists",
        )
    db.refresh(project)
    return project


def _set_pinned(db: Session, project: Project, pinned: bool) -> None:
    if pinned and not project.pinned:
        current = (
            db.query(func.count(Project.id))
            .filter(Project.pinned.is_(True), Project.id != project.id)
            .scalar()
        )
        if current >= PINNED_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Можно закрепить не более {PINNED_LIMIT} проектов",
            )
        project.pinned = True
        project.pinned_at = func.now()
    elif not pinned:
        project.pinned = False
        project.pinned_at = None


@app.delete(
    "/api/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_auth)],
)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/api/projects/{project_id}/reorder",
    response_model=list[schemas.TaskOut],
    dependencies=[Depends(require_auth)],
)
def reorder_tasks(
    project_id: int, data: schemas.ReorderIn, db: Session = Depends(get_db)
):
    """Set manual order of tasks within a project (SPEC-001 Feature 5)."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = (
        db.query(Task)
        .filter(Task.project_id == project_id)
        .order_by(Task.position, Task.id)
        .all()
    )
    by_id = {t.id: t for t in tasks}

    # Provided ids must belong to this project.
    seen: list[int] = []
    for tid in data.task_ids:
        if tid not in by_id:
            raise HTTPException(
                status_code=400, detail="Task does not belong to this project"
            )
        if tid not in seen:
            seen.append(tid)

    # Any task not mentioned (e.g. added via bot mid-drag) keeps its relative
    # order at the end.
    ordered = seen + [t.id for t in tasks if t.id not in seen]
    for index, tid in enumerate(ordered):
        by_id[tid].position = index

    db.commit()
    return (
        db.query(Task)
        .filter(Task.project_id == project_id)
        .order_by(Task.position)
        .all()
    )


# ---------------------------------------------------------------- task routes
@app.get(
    "/api/tasks",
    response_model=list[schemas.TaskOut],
    dependencies=[Depends(require_auth)],
)
def list_tasks(project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Task)
    if project_id is not None:
        query = query.filter(Task.project_id == project_id)
    return query.order_by(Task.project_id, Task.position).all()


@app.post(
    "/api/tasks",
    response_model=schemas.TaskOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
)
def create_task(data: schemas.TaskCreate, db: Session = Depends(get_db)):
    if db.get(Project, data.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    task = Task(
        project_id=data.project_id,
        text=data.text.strip(),
        position=_next_position(db, data.project_id),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.patch(
    "/api/tasks/{task_id}",
    response_model=schemas.TaskOut,
    dependencies=[Depends(require_auth)],
)
def update_task(
    task_id: int, data: schemas.TaskUpdate, db: Session = Depends(get_db)
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача больше не существует")

    fields = data.model_dump(exclude_unset=True)

    if "text" in fields and fields["text"] is not None:
        text = fields["text"].strip()
        if not text:
            raise HTTPException(status_code=422, detail="Text cannot be empty")
        task.text = text
    if "important" in fields and fields["important"] is not None:
        task.important = fields["important"]
    if "deadline" in fields:
        task.deadline = fields["deadline"]  # may be None to clear
    if "done" in fields and fields["done"] is not None:
        task.done = fields["done"]

    db.commit()
    db.refresh(task)
    return task


@app.delete(
    "/api/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_auth)],
)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------ day-slot routes
@app.get(
    "/api/day-slots",
    response_model=list[schemas.DaySlotOut],
    dependencies=[Depends(require_auth)],
)
def get_day_slots(db: Session = Depends(get_db)):
    items = db.query(DaySlotItem).order_by(
        DaySlotItem.slot_index, DaySlotItem.position
    ).all()
    by_slot: dict[int, list[int]] = {i: [] for i in range(SLOT_COUNT)}
    for item in items:
        if 0 <= item.slot_index < SLOT_COUNT:
            by_slot[item.slot_index].append(item.task_id)
    return [
        schemas.DaySlotOut(index=i, task_ids=by_slot[i]) for i in range(SLOT_COUNT)
    ]


@app.put(
    "/api/day-slots/{index}",
    response_model=list[schemas.DaySlotOut],
    dependencies=[Depends(require_auth)],
)
def set_day_slot(
    index: int, data: schemas.DaySlotSet, db: Session = Depends(get_db)
):
    """Replace the contents of one slot (SPEC-001 Feature 8).

    A task may live in at most one slot, so selecting a task that already
    sits in another slot moves it here.
    """
    if not (0 <= index < SLOT_COUNT):
        raise HTTPException(status_code=404, detail="Slot not found")

    # De-duplicate while preserving order.
    task_ids: list[int] = []
    for tid in data.task_ids:
        if tid not in task_ids:
            task_ids.append(tid)

    # Every referenced task must exist.
    for tid in task_ids:
        if db.get(Task, tid) is None:
            raise HTTPException(status_code=404, detail=f"Task {tid} not found")

    # Clear this slot, then (re)assign each task to it, pulling it out of any
    # other slot it might currently be in.
    db.query(DaySlotItem).filter(DaySlotItem.slot_index == index).delete()
    db.flush()
    for position, tid in enumerate(task_ids):
        db.query(DaySlotItem).filter(DaySlotItem.task_id == tid).delete()
        db.flush()
        db.add(DaySlotItem(slot_index=index, task_id=tid, position=position))

    db.commit()
    return get_day_slots(db)


# --------------------------------------------------------- light-task routes
# SPEC-004 Feature 2: a standalone "не забыть" list, unrelated to projects.
def _next_light_position(db: Session) -> int:
    max_pos = db.query(func.max(LightTask.position)).scalar()
    return 0 if max_pos is None else max_pos + 1


@app.get(
    "/api/light-tasks",
    response_model=list[schemas.LightTaskOut],
    dependencies=[Depends(require_auth)],
)
def list_light_tasks(db: Session = Depends(get_db)):
    # Ordered by creation time (position as a stable tie-breaker).
    return (
        db.query(LightTask)
        .order_by(LightTask.created_at, LightTask.position, LightTask.id)
        .all()
    )


@app.post(
    "/api/light-tasks",
    response_model=schemas.LightTaskOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
)
def create_light_task(
    data: schemas.LightTaskCreate, db: Session = Depends(get_db)
):
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text cannot be empty")
    item = LightTask(text=text, position=_next_light_position(db))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch(
    "/api/light-tasks/{light_id}",
    response_model=schemas.LightTaskOut,
    dependencies=[Depends(require_auth)],
)
def update_light_task(
    light_id: int, data: schemas.LightTaskUpdate, db: Session = Depends(get_db)
):
    item = db.get(LightTask, light_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Light task not found")

    fields = data.model_dump(exclude_unset=True)
    if "text" in fields and fields["text"] is not None:
        text = fields["text"].strip()
        if not text:
            raise HTTPException(status_code=422, detail="Text cannot be empty")
        item.text = text
    if "done" in fields and fields["done"] is not None:
        item.done = fields["done"]

    db.commit()
    db.refresh(item)
    return item


@app.delete(
    "/api/light-tasks/{light_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_auth)],
)
def delete_light_task(light_id: int, db: Session = Depends(get_db)):
    item = db.get(LightTask, light_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Light task not found")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------- event routes
# SPEC-004 Feature 3: an event is a task bound to a date and time. Events come
# from two sources: standalone tasks (project_id NULL) created in the calendar,
# and project tasks given a date/time. The calendar reads all tasks that carry
# an ``event_date`` (a bound time is required to *create* one).
def _event_query(db: Session):
    return db.query(Task).filter(Task.event_date.isnot(None))


@app.get(
    "/api/events",
    response_model=list[schemas.EventOut],
    dependencies=[Depends(require_auth)],
)
def list_events(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
):
    """Events whose ``event_date`` falls in [start, end] (inclusive).

    Both bounds optional; omitting them returns every event. Used by the
    calendar grid (Feature 3) and the bot reminder (Feature 4).
    """
    query = _event_query(db)
    if start is not None:
        query = query.filter(Task.event_date >= start)
    if end is not None:
        query = query.filter(Task.event_date <= end)
    return query.order_by(Task.event_date, Task.event_time, Task.id).all()


@app.post(
    "/api/events",
    response_model=schemas.EventOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
)
def create_event(data: schemas.EventCreate, db: Session = Depends(get_db)):
    """Create a standalone event (no project) from the calendar.

    Time is mandatory (enforced by the schema). The event lives only in the
    calendar; it never appears on the project board (project_id is NULL).
    """
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text cannot be empty")
    task = Task(
        project_id=None,
        text=text,
        event_date=data.event_date,
        event_time=data.event_time,
        position=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.patch(
    "/api/events/{task_id}",
    response_model=schemas.EventOut,
    dependencies=[Depends(require_auth)],
)
def update_event(
    task_id: int, data: schemas.EventUpdate, db: Session = Depends(get_db)
):
    """Edit a standalone event (text/date/time/done) from the calendar.

    Only standalone events (project_id NULL) may be edited here; project-task
    events are edited through the task/project routes. Time stays mandatory:
    clearing it while a date remains is rejected.
    """
    task = db.get(Task, task_id)
    if task is None or task.event_date is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if task.project_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Project-task events are edited through the task routes",
        )

    fields = data.model_dump(exclude_unset=True)
    if "text" in fields and fields["text"] is not None:
        text = fields["text"].strip()
        if not text:
            raise HTTPException(status_code=422, detail="Text cannot be empty")
        task.text = text
    if "event_date" in fields and fields["event_date"] is not None:
        task.event_date = fields["event_date"]
    if "event_time" in fields:
        if fields["event_time"] is None:
            raise HTTPException(
                status_code=422, detail="Время события обязательно"
            )
        task.event_time = fields["event_time"]
    if "done" in fields and fields["done"] is not None:
        task.done = fields["done"]

    db.commit()
    db.refresh(task)
    return task


@app.delete(
    "/api/events/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_auth)],
)
def delete_event(task_id: int, db: Session = Depends(get_db)):
    """Delete a standalone event. Project-task events are deleted as tasks."""
    task = db.get(Task, task_id)
    if task is None or task.event_date is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if task.project_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Project-task events are deleted through the task routes",
        )
    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.put(
    "/api/tasks/{task_id}/event",
    response_model=schemas.TaskOut,
    dependencies=[Depends(require_auth)],
)
def set_task_event(
    task_id: int, data: schemas.TaskEventBind, db: Session = Depends(get_db)
):
    """Attach or clear a date-binding on an existing project task (Feature 3/4).

    - Both date and time given -> the task becomes an event (calendar).
    - Both null -> the binding is cleared; the task stays a normal task.
    Date-binding is independent of the task's deadline.
    """
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача больше не существует")

    has_date = data.event_date is not None
    has_time = data.event_time is not None
    if has_date != has_time:
        raise HTTPException(
            status_code=422,
            detail="Дата и время привязки задаются вместе (время обязательно)",
        )
    task.event_date = data.event_date
    task.event_time = data.event_time
    db.commit()
    db.refresh(task)
    return task


# ----------------------------------------------------- serve React static SPA
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")
if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
