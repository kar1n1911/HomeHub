import os
import time
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, Integer, String, DateTime, ForeignKey, create_engine, select, text, func, or_
from sqlalchemy.engine import URL
from sqlalchemy.dialects.postgresql import JSONB, insert
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


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    room: Mapped[str] = mapped_column(String(80))
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    value: Mapped[str] = mapped_column(String(40), default="Ready")


class Sampling(Base):
    __tablename__ = "device_sampling"
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), primary_key=True)
    interval: Mapped[int] = mapped_column(Integer, default=60)
    next_poll: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_emit: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Signal(Base):
    __tablename__ = "device_signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    data: Mapped[dict] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    forwarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    room: str = Field(min_length=1, max_length=80)
    value: str = Field(default="Ready", max_length=40)
    poll_interval_seconds: int = Field(default=60, ge=5, le=3600)

    @field_validator("name", "room", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class DeviceState(BaseModel):
    online: bool | None = None
    value: str | None = Field(default=None, max_length=40)

    @field_validator("online", "value", mode="before")
    @classmethod
    def disallow_null(cls, value):
        if value is None:
            raise ValueError("Explicit null is not allowed")
        return value


class Reading(BaseModel):
    message_id: UUID
    online: bool = True
    value: str = Field(max_length=40)


class Ack(BaseModel):
    id: UUID
    lease: UUID


def require_pipeline(authorization: str = Header(default="")):
    path = os.getenv("PIPELINE_TOKEN_FILE")
    token = Path(path).read_text().strip() if path else os.getenv("PIPELINE_TOKEN", "")
    if not token or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "Internal pipeline credentials required")


def device_dict(device: Device, sampling=None) -> dict:
    return {"id": device.id, "name": device.name, "room": device.room,
            "online": device.online, "value": device.value,
            "poll_interval_seconds": sampling.interval if sampling else 60,
            "source": "simulated", "next_poll": sampling.next_poll.isoformat() if sampling else None}


def signal_data(device):
    return {"device_id": device.id, "name": device.name, "room": device.room,
            "online": device.online, "value": device.value}


def ensure_capacity(session):
    # Serialize capacity decisions; never acknowledge a push we cannot store.
    session.execute(text("SELECT pg_advisory_xact_lock(72003)"))
    if session.scalar(select(func.count()).select_from(Signal).where(Signal.forwarded_at.is_(None))) >= 10000:
        raise HTTPException(503, "Signal backlog full; retain and retry this message ID")


def emit(session, device, now, message_id=None):
    signal = Signal(id=message_id or str(uuid4()), device_id=device.id,
                    data=signal_data(device), occurred_at=now)
    session.add(signal)
    sampling = session.get(Sampling, device.id)
    if sampling:
        sampling.last_hash = hashlib.sha256(json.dumps(signal.data, sort_keys=True).encode()).hexdigest()
        sampling.last_emit = now
    return signal


def initialize_database() -> None:
    for attempt in range(10):
        try:
            # Serialize schema creation and seeding across this service's replicas.
            # The lock and marker are committed atomically with the seed rows.
            with engine.begin() as connection:
                connection.execute(text("SELECT pg_advisory_xact_lock(71003)"))
                Base.metadata.create_all(connection)
                connection.execute(text(
                    "CREATE TABLE IF NOT EXISTS device_initialization "
                    "(version INTEGER PRIMARY KEY)"
                ))
                initialized = connection.scalar(text(
                    "SELECT version FROM device_initialization WHERE version = 1"
                ))
                if initialized is None:
                    with Session(bind=connection) as session:
                        # Adopt existing installations without duplicating their data.
                        if session.scalar(select(Device.id).limit(1)) is None:
                            session.add_all([
                                Device(name="Living room climate", room="Living room", value="21.4 C"),
                                Device(name="Entry light", room="Hallway", value="Off"),
                                Device(name="Washing machine", room="Utility room", value="38 min"),
                            ])
                        session.flush()
                    connection.execute(text(
                        "INSERT INTO device_initialization (version) VALUES (1)"
                    ))
                connection.execute(text(
                    "INSERT INTO device_sampling (device_id, interval, next_poll) "
                    "SELECT id, 60, clock_timestamp() + ((id * 17) % 60) * interval '1 second' FROM devices "
                    "ON CONFLICT (device_id) DO NOTHING"
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


app = FastAPI(title="HomeHub Device Service", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "device-service"}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as connection:
            # Also detects missing tables/permissions, not just a live DB socket.
            connection.execute(select(Device.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ready", "service": "device-service"}


@app.get("/api/devices")
def list_devices():
    with Session(engine) as session:
        rows = session.execute(select(Device, Sampling).outerjoin(Sampling).order_by(Device.id)).all()
        return [device_dict(device, sampling) for device, sampling in rows]


@app.post("/api/devices", status_code=201)
def create_device(payload: DeviceCreate):
    with Session(engine) as session, session.begin():
        ensure_capacity(session)
        device = Device(name=payload.name, room=payload.room, value=payload.value)
        session.add(device)
        session.flush()
        now = session.scalar(select(func.clock_timestamp()))
        sampling = Sampling(device_id=device.id, interval=payload.poll_interval_seconds,
                            next_poll=now + timedelta(seconds=(device.id * 17) % payload.poll_interval_seconds + 1))
        session.add(sampling)
        session.flush()
        emit(session, device, now)
        return device_dict(device, sampling)


@app.patch("/api/devices/{device_id}")
def update_device(device_id: int, payload: DeviceState):
    with Session(engine) as session, session.begin():
        ensure_capacity(session)
        device = session.get(Device, device_id, with_for_update=True)
        if device is None:
            raise HTTPException(404, "Device not found")
        changed = False
        for field, value in payload.model_dump(exclude_unset=True).items():
            changed |= getattr(device, field) != value
            setattr(device, field, value)
        if changed:
            emit(session, device, session.scalar(select(func.clock_timestamp())))
        return device_dict(device, session.get(Sampling, device.id))


@app.post("/api/devices/{device_id}/signals", status_code=202)
def push_signal(device_id: int, payload: Reading):
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(72003)"))
        existing = session.get(Signal, str(payload.message_id))
        if existing:
            if existing.device_id != device_id or existing.data['value'] != payload.value or existing.data['online'] != payload.online:
                raise HTTPException(409, "Message ID already used for different data")
            return {"id": existing.id, "status": "stored", "duplicate": True}
        ensure_capacity(session)
        device = session.get(Device, device_id, with_for_update=True)
        if not device:
            raise HTTPException(404, "Device not found")
        device.online, device.value = payload.online, payload.value
        emit(session, device, session.scalar(select(func.clock_timestamp())), str(payload.message_id))
        return {"id": str(payload.message_id), "status": "stored", "duplicate": False}


@app.post("/internal/signals/claim", dependencies=[Depends(require_pipeline)])
def collect_and_claim():
    with Session(engine) as session, session.begin():
        now = session.scalar(select(func.clock_timestamp()))
        session.execute(text("SELECT pg_advisory_xact_lock(72003)"))
        backlog = session.scalar(select(func.count()).select_from(Signal).where(Signal.forwarded_at.is_(None)))
        # Simulated polling reads the current stored device state; real adapters can
        # push every reading with a durable message_id through the REST endpoint.
        if backlog < 9990:
            due = session.scalars(select(Sampling).where(Sampling.next_poll <= now)
                                  .order_by(Sampling.next_poll).limit(10).with_for_update(skip_locked=True)).all()
            for sampling in due:
                device = session.get(Device, sampling.device_id)
                digest = hashlib.sha256(json.dumps(signal_data(device), sort_keys=True).encode()).hexdigest()
                if digest != sampling.last_hash or not sampling.last_emit or (now - sampling.last_emit).total_seconds() >= 300:
                    emit(session, device, now)
                # No catch-up storm after downtime; current snapshots cannot recover
                # historical physical readings that a device never buffered.
                sampling.next_poll = now + timedelta(seconds=sampling.interval)
        signals = session.scalars(select(Signal).where(Signal.forwarded_at.is_(None),
            or_(Signal.lease_until.is_(None), Signal.lease_until <= now))
            .order_by(Signal.occurred_at).limit(20).with_for_update(skip_locked=True)).all()
        result = []
        for signal in signals:
            signal.lease, signal.lease_until = str(uuid4()), now + timedelta(seconds=30)
            result.append({"id": signal.id, "lease": signal.lease,
                           "time": signal.occurred_at.isoformat(), "data": signal.data})
        return result


@app.post("/internal/signals/ack", dependencies=[Depends(require_pipeline)])
def acknowledge(items: list[Ack]):
    if len(items) > 20:
        raise HTTPException(422, "Maximum 20 acknowledgements")
    with Session(engine) as session, session.begin():
        for item in items:
            signal = session.get(Signal, str(item.id), with_for_update=True)
            if signal and signal.lease == str(item.lease) and signal.forwarded_at is None:
                signal.forwarded_at = session.scalar(select(func.clock_timestamp()))
        return {"status": "acknowledged"}
