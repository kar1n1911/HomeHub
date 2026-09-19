import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Boolean, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://homehub:homehub_dev@localhost:5432/homehub")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


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
            Base.metadata.create_all(engine)
            with Session(engine) as session:
                if not session.scalar(select(Member.id).limit(1)):
                    session.add_all([
                        Member(name="Alex", role="Parent", at_home=True),
                        Member(name="Mika", role="Parent", at_home=False),
                        Member(name="Noa", role="Member", at_home=True),
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


app = FastAPI(title="HomeHub Household Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "household-service"}


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
