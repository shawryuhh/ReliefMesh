"""Tests for the revision storage migration; not a live revision protocol."""
from sqlalchemy import text
from app.db.session import SessionLocal


def test_revision_singleton_initialized():
    with SessionLocal() as db:
        rows = db.execute(text("SELECT id, revision FROM operational_revision")).all()
        assert rows == [(1, 0)]


def test_revision_update_rolls_back():
    with SessionLocal() as db:
        db.execute(text("UPDATE operational_revision SET revision = revision + 1 WHERE id = 1"))
        assert db.scalar(text("SELECT revision FROM operational_revision WHERE id = 1")) == 1
        db.rollback()
    with SessionLocal() as db:
        assert db.scalar(text("SELECT revision FROM operational_revision WHERE id = 1")) == 0


def test_revision_update_commits():
    with SessionLocal() as db:
        db.execute(text("UPDATE operational_revision SET revision = revision + 1 WHERE id = 1"))
        db.commit()
    with SessionLocal() as db:
        assert db.scalar(text("SELECT revision FROM operational_revision WHERE id = 1")) == 1
        db.execute(text("UPDATE operational_revision SET revision = 0 WHERE id = 1"))
        db.commit()
