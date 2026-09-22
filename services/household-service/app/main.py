import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from sqlalchemy import Boolean, Integer, String, create_engine, select, text
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


class Member(Base):
    __tablename__ = "household_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(40), default="Member")
    at_home: Mapped[bool] = mapped_column(Boolean, default=True)


def initialize_database() -> None:
    for attempt in range(10):
        try:
            # Serialize schema creation and seeding across this service's replicas.
            # The lock and marker are committed atomically with the seed rows.
            with engine.begin() as connection:
                connection.execute(text("SELECT pg_advisory_xact_lock(71001)"))
                Base.metadata.create_all(connection)
                connection.execute(text(
                    "CREATE TABLE IF NOT EXISTS household_initialization "
                    "(version INTEGER PRIMARY KEY)"
                ))
                initialized = connection.scalar(text(
                    "SELECT version FROM household_initialization WHERE version = 1"
                ))
                if initialized is None:
                    with Session(bind=connection) as session:
                        # Adopt existing installations without duplicating their data.
                        if session.scalar(select(Member.id).limit(1)) is None:
                            session.add_all([
                                Member(name="Alex", role="Parent", at_home=True),
                                Member(name="Mika", role="Parent", at_home=False),
                                Member(name="Noa", role="Member", at_home=True),
                            ])
                        session.flush()
                    connection.execute(text(
                        "INSERT INTO household_initialization (version) VALUES (1)"
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


app = FastAPI(title="HomeHub Household Service", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "household-service"}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as connection:
            # Also detects missing tables/permissions, not just a live DB socket.
            connection.execute(select(Member.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ready", "service": "household-service"}


@app.get("/api/households")
def get_household():
    with Session(engine) as session:
        members = session.scalars(select(Member).order_by(Member.id)).all()
        return {
            "id": 1,
            "name": "Anderson Home",
            "members": [
                {"id": member.id, "name": member.name, "role": member.role, "at_home": member.at_home}
                for member in members
            ],
        }


@app.get("/api/households/members")
def get_members():
    with Session(engine) as session:
        members = session.scalars(select(Member).order_by(Member.id)).all()
        return [
            {"id": member.id, "name": member.name, "role": member.role, "at_home": member.at_home}
            for member in members
        ]
