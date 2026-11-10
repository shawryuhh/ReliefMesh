"""Test isolation.

Tests must never write to the development database. Instead of switching to
SQLite (which can't exercise the Postgres-specific locking behavior the
assignment service relies on), we point the app at a second, disposable
database on the *same* Postgres container/instance: `reliefmesh_test` by
default, or whatever `TEST_DATABASE_URL` says.

This has to happen before `app.db.session` is imported anywhere, since that
module builds its engine from settings at import time. Setting the
environment variable here, at the very top of conftest.py (which pytest
always imports before any test module), is enough — pydantic-settings
prefers real environment variables over the `.env` file.
"""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://reliefmesh:reliefmesh@localhost:5432/reliefmesh_test",
)

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.main import app  # noqa: E402 (must follow the env var override above)

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Truncated after every test, in no particular order — CASCADE takes care of
# the foreign-key dependencies between them regardless of listing order.
APP_TABLES = [
    "incidents", "resources", "assignments", "action_logs",
    "reports", "recommendations",
]


def _ensure_test_database_exists() -> None:
    test_url = make_url(os.environ["DATABASE_URL"])
    db_name = test_url.database
    admin_engine = create_engine(
        test_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()


def _migrate_test_database() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> None:
    """Creates (if missing) and migrates the isolated test database once per
    test session. Safe to run repeatedly — both steps are idempotent."""
    _ensure_test_database_exists()
    _migrate_test_database()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Leaves the test database empty before every test, so tests are
    repeatable and independent of each other regardless of execution order."""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.execute(text(f"TRUNCATE TABLE {', '.join(APP_TABLES)} RESTART IDENTITY CASCADE"))
        db.commit()
    # Reset revision fixture state independently of operational table cleanup.
    db.execute(text("UPDATE operational_revision SET revision = 0 WHERE id = 1"))
    db.commit()
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
