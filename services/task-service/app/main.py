import os
import time
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://homehub:homehub_dev@localhost:5432/homehub")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    due_date: date | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    due_date: date | None = None
    priority: str | None = Field(default=None, pattern="^(low|medium|high)$")
    completed: bool | None = None


def task_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "priority": task.priority,
        "completed": task.completed,
    }


def initialize_database() -> None:
    for attempt in range(10):
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as session:
                if not session.scalar(select(Task.id).limit(1)):
                    session.add_all([
                        Task(title="Take recycling outside", due_date=date.today(), priority="high"),
                        Task(title="Water the balcony herbs", due_date=date.today(), priority="medium", completed=True),
                        Task(title="Plan weekend groceries", priority="medium"),
                        Task(title="Replace hallway bulb", priority="low"),
                    ])
                    session.commit()
            return
        except Exception:
            if attempt == 9:
                raise
            time.sleep(2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="HomeHub Task Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "task-service"}


@app.get("/api/tasks")
def list_tasks():
    with Session(engine) as session:
        return [task_dict(task) for task in session.scalars(select(Task).order_by(Task.id)).all()]


@app.post("/api/tasks", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate):
    with Session(engine) as session:
        task = Task(**payload.model_dump())
        session.add(task)
        session.commit()
        session.refresh(task)
        return task_dict(task)


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        session.commit()
        session.refresh(task)
        return task_dict(task)


@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        session.delete(task)
        session.commit()
