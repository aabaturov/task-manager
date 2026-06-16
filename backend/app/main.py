import os

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
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
from .models import Project, Task

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
    project = Project(name=data.name.strip())
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
    return query.order_by(Task.created_at).all()


@app.post(
    "/api/tasks",
    response_model=schemas.TaskOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
)
def create_task(data: schemas.TaskCreate, db: Session = Depends(get_db)):
    if db.get(Project, data.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    task = Task(project_id=data.project_id, text=data.text.strip())
    db.add(task)
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


# ----------------------------------------------------- serve React static SPA
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")
if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
