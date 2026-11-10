"""Demo reset must invalidate an older operational snapshot revision."""
from app.db.session import SessionLocal
from app.services.operational_revision import current_operational_revision
from scripts.seed_demo_data import reset_tables


def test_reset_advances_revision_and_does_not_reuse_old_value(client):
    created = client.post("/incidents", json={
        "location": "Synthetic test location", "type": "flood", "severity": "HIGH",
    })
    assert created.status_code == 201, created.text
    with SessionLocal() as db:
        before = current_operational_revision(db)
        assert before >= 1
        reset_tables(db)
    with SessionLocal() as db:
        after = current_operational_revision(db)
        assert after == before + 1
