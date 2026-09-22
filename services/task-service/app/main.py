import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import date

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, Integer, String, create_engine, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# Explicit DATABASE_URL is supported for isolated tests or external deployments.
# Normal deployments inject only this service's credentials, with no shared fallback.
def database_url():
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    password_file = os.getenv("PGPASSWORD_FILE")
    password = Path(password_file).read_text().strip() if password_file else os.environ["PGPASSWORD"]
    query = {"sslmode": os.getenv("PGSSLMODE", "require")}
    if os.getenv("PGSSLROOTCERT"):
        query["sslrootcert"] = os.environ["PGSSLROOTCERT"]
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["PGUSER"], password=password,
        host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")),
        database=os.environ["PGDATABASE"], query=query,
    )


DATABASE_URL = database_url()
# Bound each replica's use of the shared database, including overflow.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=0,
    pool_timeout=2,
    connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
)


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
            # Serialize schema creation and seeding across this service's replicas.
            # The lock and marker are committed atomically with the seed rows.
            with engine.begin() as connection:
                connection.execute(text("SELECT pg_advisory_xact_lock(71002)"))
                Base.metadata.create_all(connection)
                connection.execute(text(
                    "CREATE TABLE IF NOT EXISTS task_initialization "
                    "(version INTEGER PRIMARY KEY)"
                ))
                initialized = connection.scalar(text(
                    "SELECT version FROM task_initialization WHERE version = 1"
                ))
                if initialized is None:
                    with Session(bind=connection) as session:
                        # Adopt existing installations without duplicating their data.
                        if session.scalar(select(Task.id).limit(1)) is None:
                            session.add_all([
                                Task(title="Take recycling outside", due_date=date.today(), priority="high"),
                                Task(title="Water the balcony herbs", due_date=date.today(), priority="medium", completed=True),
                                Task(title="Plan weekend groceries", priority="medium"),
                                Task(title="Replace hallway bulb", priority="low"),
                            ])
                        session.flush()
                    connection.execute(text(
                        "INSERT INTO task_initialization (version) VALUES (1)"
                    ))
            return
        except Exception:
            if attempt == 9:
                raise
            time.sleep(2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="HomeHub Task Service", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "task-service"}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as connection:
            # Also detects missing tables/permissions, not just a live DB socket.
            connection.execute(select(Task.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ready", "service": "task-service"}


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
