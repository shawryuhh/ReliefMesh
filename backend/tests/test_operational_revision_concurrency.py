"""Concurrency tests for the operational revision singleton.

Use two independent PostgreSQL transactions and a bounded thread pool.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import text
from app.db.session import SessionLocal
from app.services.operational_revision import (
    bump_operational_revision, current_operational_revision,
)


def test_concurrent_committed_bumps_are_serialized():
    barrier = Barrier(2)

    def worker(_):
        with SessionLocal() as db:
            # Both transactions begin before either requests the row lock.
            db.execute(text("SELECT 1"))
            barrier.wait(timeout=10)
            revision = bump_operational_revision(db)
            db.commit()
            return revision

    with ThreadPoolExecutor(max_workers=2) as pool:
        revisions = list(pool.map(worker, range(2)))
    assert sorted(revisions) == [1, 2]
    with SessionLocal() as db:
        assert current_operational_revision(db) == 2


def test_rolled_back_bump_does_not_advance_next_committed_bump():
    with SessionLocal() as db:
        assert bump_operational_revision(db) == 1
        db.rollback()
    with SessionLocal() as db:
        assert bump_operational_revision(db) == 1
        db.commit()
    with SessionLocal() as db:
        assert current_operational_revision(db) == 1
