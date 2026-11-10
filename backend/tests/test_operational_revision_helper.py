"""Transactional revision helper tests against isolated PostgreSQL."""
from sqlalchemy import text
from app.db.session import SessionLocal
from app.services.operational_revision import (
    bump_operational_revision, current_operational_revision,
)


def test_bump_does_not_commit_and_rolls_back():
    with SessionLocal() as db:
        assert current_operational_revision(db) == 0
        assert bump_operational_revision(db) == 1
        assert current_operational_revision(db) == 1
        db.rollback()
    with SessionLocal() as db:
        assert current_operational_revision(db) == 0


def test_bump_commits_with_caller_transaction():
    with SessionLocal() as db:
        assert bump_operational_revision(db) == 1
        assert bump_operational_revision(db) == 2
        db.commit()
    with SessionLocal() as db:
        assert current_operational_revision(db) == 2


def test_missing_singleton_fails_closed():
    with SessionLocal() as db:
        db.execute(text("DELETE FROM operational_revision WHERE id = 1"))
        try:
            bump_operational_revision(db)
            assert False, "Expected failure for missing singleton"
        except RuntimeError as exc:
            assert "missing" in str(exc)
        finally:
            db.rollback()
