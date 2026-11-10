"""Seeds demo data for the canonical Krishna Apartments scenario.

Run with:  python -m scripts.seed_demo_data [--reset] [--fleet-only] [--stop-at STAGE]

Goes through the real service layer (incident_service, resource_service,
recommendation_service, disruption_service) rather than raw INSERTs, so the
seeded data is guaranteed to satisfy exactly the same rules the live API
enforces — this script is effectively the AI/n8n and coordinator sides of the
demo, feeding already-decided payloads into the same contracts a real
integration would use. It also serves as an end-to-end smoke test of the full
recommendation -> approval -> disruption -> replacement proposal ->
replacement approval flow against whatever DATABASE_URL points at.
--stop-at leaves the incident at an earlier stage, so the remaining steps can
be driven live from the UI during a demo.

By default this ADDS to whatever's already in the target database. Pass
--reset to truncate every application table first (and reset the ID
sequences this script relies on) — only do this against a database you're
fine losing all rows in, e.g. your local dev DB before a demo. Never point
this at anything shared without --reset being a deliberate choice.
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.enums import Severity
from app.schemas.disruption import DisruptionReport
from app.schemas.incident import IncidentCreate
from app.schemas.recommendation import (
    RecommendationApprove,
    RecommendationCreate,
    RecommendationProposeReplacement,
)
from app.schemas.resource import ResourceCreate
from app.services import disruption_service, incident_service, recommendation_service, resource_service
from app.services.id_generator import resource_prefix_for_type
from app.services.operational_revision import bump_operational_revision

APP_TABLES = ["incidents", "resources", "assignments", "action_logs", "reports", "recommendations"]

# Identity the seeded approvals are recorded under — the same value
# require_coordinator derives for the coordinator API key over HTTP.
COORDINATOR = "coordinator"

# Stages --stop-at can leave the canonical incident at, in narrative order.
STAGES = ["awaiting_approval", "dispatched", "blocked", "awaiting_replacement", "replaced"]

# Order matters: ambulances are created in this order so the canonical
# narrative's AMB-02 and AMB-05 land on the resources actually used in it.
FLEET = [
    ("ambulance", "Sector 12 Depot", 12.953, 77.640, ["basic_life_support", "medical"], 2),
    ("ambulance", "Sector 12 Depot", 12.949, 77.614, ["advanced_life_support", "medical"], 2),  # -> AMB-02
    ("ambulance", "Sector 9 Depot", 12.921, 77.605, ["advanced_life_support", "medical"], 2),
    ("ambulance", "Sector 9 Depot", 12.906, 77.655, ["basic_life_support", "medical"], 2),
    ("ambulance", "Sector 4 Depot", 12.936, 77.664, ["advanced_life_support", "medical"], 2),  # -> AMB-05
    ("rescue_unit", "Central Depot", 12.928, 77.602, ["water_rescue", "first_aid", "medical"], 6),  # -> RESCUE-01
    ("rescue_unit", "North Depot", 12.932, 77.619, ["water_rescue", "first_aid"], 6),
    ("volunteer", "Community Hall", 12.925, 77.650, ["evacuation_support"], None),
    ("shelter", "Agara Relief Centre", 12.904, 77.620, ["shelter", "supplies"], 120),
    ("hospital", "South City Medical Centre", 12.914, 77.630, ["emergency_care", "icu", "trauma", "medical"], 18),
]


def reset_tables(db: Session) -> None:
    db.execute(text(f"TRUNCATE TABLE {', '.join(APP_TABLES)} RESTART IDENTITY CASCADE"))
    # Resource ID sequences are created on demand per type prefix (see
    # app.services.id_generator) and aren't reset by RESTART IDENTITY above,
    # since they aren't owned by a table's identity column. Reset every
    # sequence this seed run uses, so a repeated --reset always reproduces
    # the exact same resource IDs, not just the narrative-critical ones.
    prefixes = {resource_prefix_for_type(resource_type) for resource_type, *_ in FLEET}
    for prefix in prefixes:
        seq_name = f"resource_seq_{prefix.lower()}"
        exists = db.execute(
            text("SELECT 1 FROM pg_sequences WHERE sequencename = :name"), {"name": seq_name}
        ).scalar()
        if exists:
            db.execute(text(f'SELECT setval(\'"{seq_name}"\', 1, false)'))
    # Fixed sequences from the migrations; incident/assignment are advanced
    # explicitly by seed_narrative_scenario anyway.
    for seq_name in ("report_seq", "recommendation_seq"):
        db.execute(text(f"SELECT setval('{seq_name}', 1, false)"))
    bump_operational_revision(db)
    db.commit()


def seed_fleet(db: Session) -> None:
    print("Seeded fleet:")
    for resource_type, location, latitude, longitude, capabilities, capacity in FLEET:
        resource = resource_service.create_resource(
            db,
            ResourceCreate(
                type=resource_type,
                location=location,
                latitude=latitude,
                longitude=longitude,
                capabilities=capabilities,
                capacity=capacity,
            ),
        )
        print(f"  {resource.id:<10} {resource.type:<12} {resource.location}")


def seed_narrative_scenario(db: Session, stop_at: str = "replaced") -> None:
    # Advances the sequences so this run's incident/assignment IDs match the
    # canonical demo narrative (INC-1042, ASG-887) regardless of what ran
    # before. Both sequences always exist (created in the initial migration),
    # so this is safe with or without --reset.
    db.execute(text("SELECT setval('incident_seq', 1041)"))
    db.execute(text("SELECT setval('assignment_seq', 886)"))
    db.commit()

    incident = incident_service.create_incident(
        db,
        IncidentCreate(
            location="Krishna Apartments, Block C",
            latitude=12.9352,
            longitude=77.6146,
            type="flood",
            severity=Severity.CRITICAL,
            people_affected=4,
            needs=["medical", "evacuation"],
            confidence=0.88,
            priority_score=94,
            report_metadata={
                "channel": "whatsapp",
                "raw_text": (
                    "Water entering Krishna Apartments Block C. "
                    "My grandmother cannot walk."
                ),
            },
        ),
    )

    amb_02 = resource_service.get_resource(db, "AMB-02")
    rescue_01 = resource_service.get_resource(db, "RESCUE-01")
    amb_05 = resource_service.get_resource(db, "AMB-05")

    def reached(stage: str) -> bool:
        return STAGES.index(stage) >= STAGES.index(stop_at)

    print(f"\nSeeded canonical scenario on incident {incident.id}:")

    # Mirrors the frontend mock fixtures (plan.reason / explain.* keys) so the
    # UI renders the seeded plans exactly like the mock ones.
    initial = recommendation_service.create_recommendation(
        db,
        incident.id,
        RecommendationCreate(
            recommended_resources=[amb_02.id, rescue_01.id],
            reason="plan.reason",
            explanation=[
                {"key": "explain.distance", "params": {"id": amb_02.id, "distance": 2.1}},
                {"key": "explain.water", "params": {"id": rescue_01.id}},
            ],
            confidence=0.91,
            priority_score=94,
            analysis_revision="seed-analysis-1",
        ),
    )[0]
    print(f"  {initial.id} v{initial.version}: {amb_02.id} + {rescue_01.id} proposed, awaiting approval")
    if reached("awaiting_approval"):
        return

    recommendation_service.approve_recommendation(
        db, incident.id, RecommendationApprove(version=initial.version), COORDINATOR
    )
    print(f"  v{initial.version} approved: {amb_02.id} + {rescue_01.id} dispatched")
    if reached("dispatched"):
        return

    disruption_service.report_disruption(
        db,
        incident.id,
        DisruptionReport(resource_id=amb_02.id, eta_minutes=24, previous_eta_minutes=6),
    )
    print(f"  {amb_02.id} blocked by road obstruction (ETA 6 -> 24 min)")
    if reached("blocked"):
        return

    replacement = recommendation_service.propose_replacement(
        db,
        incident.id,
        RecommendationProposeReplacement(
            base_version=initial.version,
            replacement_for=amb_02.id,
            recommended_resources=[amb_05.id, rescue_01.id],
            reason="plan.replacementReason",
            explanation=[
                {"key": "explain.blocked", "params": {"id": amb_02.id, "old": 6, "eta": 24}},
                {"key": "explain.available", "params": {"id": amb_05.id}},
                {"key": "explain.eta", "params": {"id": amb_05.id, "eta": 9}},
                {"key": "explain.continues", "params": {"id": rescue_01.id}},
            ],
            confidence=0.91,
            priority_score=94,
            analysis_revision="seed-analysis-2",
        ),
    )[0]
    print(f"  {replacement.id} v{replacement.version}: {amb_05.id} proposed to replace {amb_02.id}, awaiting approval")
    if reached("awaiting_replacement"):
        return

    recommendation_service.approve_recommendation(
        db, incident.id, RecommendationApprove(version=replacement.version), COORDINATOR
    )
    print(f"  v{replacement.version} approved: {amb_02.id} released, {amb_05.id} dispatched, {rescue_01.id} continues")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate all application tables first.",
    )
    parser.add_argument(
        "--fleet-only",
        action="store_true",
        help="Seed the resource fleet only; skip the incident/recommendation narrative.",
    )
    parser.add_argument(
        "--stop-at",
        choices=STAGES,
        default="replaced",
        help="Leave the canonical incident at this stage (default: run the full flow).",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            reset_tables(db)

        seed_fleet(db)

        if not args.fleet_only:
            seed_narrative_scenario(db, args.stop_at)


if __name__ == "__main__":
    main()
