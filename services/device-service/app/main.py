import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Boolean, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://homehub:homehub_dev@localhost:5432/homehub")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    room: Mapped[str] = mapped_column(String(80))
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    value: Mapped[str] = mapped_column(String(40), default="Ready")


class DeviceState(BaseModel):
    online: bool | None = None
    value: str | None = None


def device_dict(device: Device) -> dict:
    return {"id": device.id, "name": device.name, "room": device.room, "online": device.online, "value": device.value}


def initialize_database() -> None:
    for attempt in range(10):
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as session:
                if not session.scalar(select(Device.id).limit(1)):
                    session.add_all([
                        Device(name="Living room climate", room="Living room", value="21.4 C"),
                        Device(name="Entry light", room="Hallway", value="Off"),
                        Device(name="Washing machine", room="Utility room", value="38 min"),
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


app = FastAPI(title="HomeHub Device Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "device-service"}


@app.get("/api/devices")
def list_devices():
    with Session(engine) as session:
        return [device_dict(device) for device in session.scalars(select(Device).order_by(Device.id)).all()]


@app.patch("/api/devices/{device_id}")
def update_device(device_id: int, payload: DeviceState):
    with Session(engine) as session:
        device = session.get(Device, device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(device, field, value)
        session.commit()
        session.refresh(device)
        return device_dict(device)
