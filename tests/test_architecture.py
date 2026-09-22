"""Integration checks against a disposable PostgreSQL database only.

Run through scripts/test-architecture.sh; this suite deletes its test tables.
"""
import asyncio
from concurrent.futures import ProcessPoolExecutor
import importlib.util
import multiprocessing
import os
from pathlib import Path
import unittest

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import TimeoutError

ROOT = Path(__file__).resolve().parents[1]
SERVICES = [("household", "Member", 3), ("task", "Task", 4), ("device", "Device", 3)]


def load(service):
    spec = importlib.util.spec_from_file_location(
        f"{service}_app", ROOT / "services" / f"{service}-service" / "app" / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def initialize(service):
    module = load(service)
    try:
        module.initialize_database()
    finally:
        module.engine.dispose()


async def http_status(app, path):
    """Exercise the ASGI route and exception handling without extra test dependencies."""
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "", "headers": [],
        "client": ("127.0.0.1", 12345), "server": ("test", 80),
    }, receive, send)
    return next(m["status"] for m in messages if m["type"] == "http.response.start")


class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("HOMEHUB_DISPOSABLE_DATABASE") != "1":
            raise RuntimeError("Use the disposable database test runner")

    def reset(self, module, service):
        with module.engine.begin() as connection:
            module.Base.metadata.drop_all(connection)
            connection.execute(text(f"DROP TABLE IF EXISTS {service}_initialization"))

    def test_concurrent_initialization_and_deleted_data(self):
        for service, model_name, expected in SERVICES:
            with self.subTest(service=service):
                module = load(service)
                self.reset(module, service)
                # Independent processes emulate replicas, each with its own pool.
                with ProcessPoolExecutor(max_workers=8, mp_context=multiprocessing.get_context("spawn")) as pool:
                    list(pool.map(initialize, [service] * 8))
                model = getattr(module, model_name)
                with module.engine.begin() as connection:
                    self.assertEqual(connection.scalar(select(func.count()).select_from(model)), expected)
                    self.assertEqual(connection.scalar(text(f"SELECT count(*) FROM {service}_initialization")), 1)
                    if service == "device":
                        connection.execute(module.Signal.__table__.delete())
                        connection.execute(module.Sampling.__table__.delete())
                    connection.execute(model.__table__.delete())
                module.initialize_database()
                with module.engine.connect() as connection:
                    self.assertEqual(connection.scalar(select(func.count()).select_from(model)), 0)
                module.engine.dispose()

    def test_existing_data_adopted_and_failed_seed_rolled_back(self):
        for service, model_name, expected in SERVICES:
            with self.subTest(service=service):
                module = load(service)
                self.reset(module, service)
                module.initialize_database()
                model = getattr(module, model_name)
                # Simulate an installation created before initialization markers existed.
                with module.engine.begin() as connection:
                    connection.execute(text(f"DROP TABLE {service}_initialization"))
                module.initialize_database()
                with module.engine.connect() as connection:
                    self.assertEqual(connection.scalar(select(func.count()).select_from(model)), expected)
                self.reset(module, service)
                original_session = module.Session
                original_sleep = module.time.sleep

                class FailingSession(original_session):
                    def flush(self, *args, **kwargs):
                        super().flush(*args, **kwargs)
                        raise RuntimeError("Simulated failure after seed insertion")

                module.Session = FailingSession
                module.time.sleep = lambda _: None
                try:
                    with self.assertRaises(RuntimeError):
                        module.initialize_database()
                finally:
                    module.Session = original_session
                    module.time.sleep = original_sleep
                with module.engine.connect() as connection:
                    self.assertIsNone(connection.scalar(text(f"SELECT to_regclass('{service}_initialization')")))
                    self.assertIsNone(connection.scalar(text(f"SELECT to_regclass('{model.__tablename__}')")))
                module.initialize_database()
                with module.engine.connect() as connection:
                    self.assertEqual(connection.scalar(select(func.count()).select_from(model)), expected)
                module.engine.dispose()

    def test_readiness_liveness_and_pool_budget(self):
        for service, _, _ in SERVICES:
            with self.subTest(service=service):
                module = load(service)
                module.initialize_database()
                self.assertEqual(asyncio.run(http_status(module.app, "/ready")), 200)
                with module.engine.connect(), module.engine.connect():
                    with self.assertRaises(TimeoutError):
                        module.engine.connect()
                    self.assertEqual(asyncio.run(http_status(module.app, "/ready")), 503)
                    self.assertEqual(asyncio.run(http_status(module.app, "/health")), 200)
                self.assertEqual(asyncio.run(http_status(module.app, "/ready")), 200)
                with module.engine.begin() as connection:
                    module.Base.metadata.drop_all(connection)
                self.assertEqual(asyncio.run(http_status(module.app, "/ready")), 503)
                self.assertEqual(asyncio.run(http_status(module.app, "/health")), 200)
                module.initialize_database()
                working_engine = module.engine
                module.engine = create_engine(
                    "postgresql+psycopg://invalid:invalid@127.0.0.1:1/unavailable",
                    connect_args={"connect_timeout": 2},
                )
                try:
                    self.assertEqual(asyncio.run(http_status(module.app, "/ready")), 503)
                    self.assertEqual(asyncio.run(http_status(module.app, "/health")), 200)
                finally:
                    module.engine.dispose()
                    module.engine = working_engine
                self.assertEqual(asyncio.run(http_status(module.app, "/ready")), 200)
                module.engine.dispose()


if __name__ == "__main__":
    unittest.main(verbosity=2)
