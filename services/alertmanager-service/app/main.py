"""Durable, leased JSON delivery. Roles share code, never receiver credentials."""
import asyncio
import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import Column, DateTime, Integer, String, Text, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.exc import SQLAlchemyError
from .db import engine

log = logging.getLogger('uvicorn.error')
ROLE = os.getenv('ROLE', 'collector')
TOKEN = Path(os.environ['PIPELINE_TOKEN_FILE']).read_text().strip() if os.getenv('PIPELINE_TOKEN_FILE') else os.environ.get('PIPELINE_TOKEN', '')

class Base(DeclarativeBase):
    pass

class Message(Base):
    __tablename__ = 'signal_messages'
    id = Column(String(36), primary_key=True)
    payload = Column(JSONB, nullable=False)
    digest = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    delivered_at = Column(DateTime(timezone=True))
    lease = Column(String(36))
    lease_until = Column(DateTime(timezone=True))
    next_attempt = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text)


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def auth(authorization: str = Header('')):
    if not TOKEN or not hmac.compare_digest(authorization, 'Bearer ' + TOKEN):
        raise HTTPException(401, 'Invalid pipeline credentials')


def request(url, payload):
    req = Request(url, data=canonical(payload), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN}, method='POST')
    with urlopen(req, timeout=5) as response:
        return json.load(response)


def collect():
    with Session(engine) as session:
        if session.scalar(select(func.count()).select_from(Message).where(Message.delivered_at.is_(None))) >= 10000:
            return  # Leave additional messages durable in the source outbox.
    source = os.getenv('DEVICE_URL', 'http://device-service:8000')
    claimed = request(source + '/internal/signals/claim', {})
    # Source is acknowledged only AFTER the destination transaction commits.
    acknowledgements = []
    with Session(engine) as session, session.begin():
        for item in claimed:
            payload = {'specversion': '1.0', 'id': item['id'], 'source': 'device/' + str(item['data']['device_id']), 'type': 'homehub.device.signal', 'time': item['time'], 'datacontenttype': 'application/json', 'data': item['data']}
            digest = hashlib.sha256(canonical(payload)).hexdigest()
            session.execute(insert(Message).values(id=item['id'], payload=payload, digest=digest, attempts=0).on_conflict_do_nothing(index_elements=['id']))
            if session.get(Message, item['id']).digest != digest:
                raise RuntimeError('Source message ID content conflict')
            acknowledgements.append({'id': item['id'], 'lease': item['lease']})
    if acknowledgements:
        request(source + '/internal/signals/ack', acknowledgements)


def deliver():
    with Session(engine) as session, session.begin():
        now = session.scalar(select(func.clock_timestamp()))
        msg = session.scalar(select(Message).where(Message.delivered_at.is_(None), Message.next_attempt <= now, or_(Message.lease_until.is_(None), Message.lease_until < now)).order_by(Message.created_at).with_for_update(skip_locked=True).limit(1))
        if msg is None:
            return
        identity, payload, lease = msg.id, msg.payload, str(uuid4())
        msg.lease, msg.lease_until = lease, now + timedelta(seconds=30)
        msg.attempts += 1
    error = None
    try:
        result = request(os.getenv('RECEIVER_URL', 'http://signal-receiver:8000') + '/internal/receive', payload)
        if result.get('id') != identity or result.get('stored') is not True:
            raise ValueError('Receiver did not acknowledge durable storage')
    except Exception as exc:
        error = type(exc).__name__  # Do not log headers or credentials.
    with Session(engine) as session, session.begin():
        msg = session.get(Message, identity, with_for_update=True)
        if msg.lease != lease:
            return
        now = session.scalar(select(func.clock_timestamp()))
        if error:
            msg.error = error
            msg.next_attempt = now + timedelta(seconds=min(60, 2 ** min(msg.attempts, 6)))
            log.warning('Signal %s delivery deferred (%s)', identity, error)
        else:
            msg.delivered_at, msg.error = now, None
            log.info('Signal %s delivered', identity)
        msg.lease, msg.lease_until = None, None


async def loop():
    while True:
        try:
            await asyncio.to_thread(collect if ROLE == 'collector' else deliver)
        except Exception as exc:
            log.warning('Pipeline iteration deferred (%s)', type(exc).__name__)
        await asyncio.sleep(1 if ROLE == 'collector' else 0.2)


@asynccontextmanager
async def lifespan(app):
    if ROLE not in ('collector', 'worker', 'receiver') or not TOKEN:
        raise RuntimeError('A valid ROLE and pipeline token are required')
    for attempt in range(60):
        try:
            with engine.begin() as connection:
                connection.execute(text('SELECT pg_advisory_xact_lock(71004)'))
                Base.metadata.create_all(connection)
            break
        except SQLAlchemyError:
            if attempt == 59:
                raise
            await asyncio.sleep(2)
    task = asyncio.create_task(loop()) if ROLE in ('collector', 'worker') else None
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

app = FastAPI(title='HomeHub Signal ' + ROLE, version='0.2.0', lifespan=lifespan)

@app.get('/health')
def health():
    return {'status': 'ok', 'role': ROLE}

@app.get('/ready')
def ready():
    try:
        with Session(engine) as session:
            session.scalar(select(Message.id).limit(1))
        return {'status': 'ready'}
    except Exception:
        raise HTTPException(503, 'Database unavailable')

@app.get('/internal/queue-depth')
def queue_depth():
    with Session(engine) as session:
        return {'depth': session.scalar(select(func.count()).select_from(Message).where(Message.delivered_at.is_(None)))}

@app.get('/api/signals/stats')
def stats():
    with Session(engine) as session:
        total = session.scalar(select(func.count()).select_from(Message))
        pending = session.scalar(select(func.count()).select_from(Message).where(Message.delivered_at.is_(None)))
        recent = session.scalars(select(Message).order_by(Message.created_at.desc()).limit(10)).all()
        return {'depth': pending, 'total': total, 'delivered': total - pending, 'recent': [{'id': m.id, 'payload': m.payload, 'delivered': m.delivered_at is not None, 'attempts': m.attempts, 'error': m.error} for m in recent]}

@app.post('/internal/receive', dependencies=[Depends(auth)])
def receive(payload: dict):
    if ROLE != 'receiver':
        raise HTTPException(404)
    from uuid import UUID
    try:
        identity = str(UUID(payload['id']))
        if payload['specversion'] != '1.0' or payload['type'] != 'homehub.device.signal' or not isinstance(payload['data'], dict):
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise HTTPException(422, 'Invalid signal envelope')
    digest = hashlib.sha256(canonical(payload)).hexdigest()
    with Session(engine) as session, session.begin():
        session.execute(insert(Message).values(id=identity, payload=payload, digest=digest, attempts=0, delivered_at=func.now()).on_conflict_do_nothing(index_elements=['id']))
        if session.get(Message, identity).digest != digest:
            raise HTTPException(409, 'Message ID already has different contents')
    return {'id': identity, 'stored': True}
