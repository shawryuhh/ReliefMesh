"""Transactional revision helper for the operational snapshot.

Call exactly once in the same outer transaction as an operational mutation.
Do not call independently from nested audit logging. Not yet wired to services.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def bump_operational_revision(db: Session) -> int:
    """Atomically increment the singleton row, returning the new revision.

    PostgreSQL locks the updated row until commit/rollback. The increment
    rolls back with the caller's transaction. This helper never commits.
    """
    revision = db.execute(text(
        "UPDATE operational_revision SET revision = revision + 1 "
        "WHERE id = 1 RETURNING revision"
    )).scalar_one_or_none()
    if revision is None:
        raise RuntimeError("Operational revision singleton missing")
    return int(revision)


def current_operational_revision(db: Session) -> int:
    """Read the revision in the caller's existing database transaction."""
    value = db.execute(text(
        "SELECT revision FROM operational_revision WHERE id = 1"
    )).scalar_one_or_none()
    if value is None:
        raise RuntimeError("Operational revision singleton missing")
    return int(value)
