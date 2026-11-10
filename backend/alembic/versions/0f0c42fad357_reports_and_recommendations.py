"""reports and recommendations: persisted intake and versioned plans

Adds:
- incidents.operational_phase, severity_score, vulnerabilities, duplicate_count
- reports table (immutable originals, idempotent per producer)
- recommendations table (versioned pending-until-approved plans)
- assignments.recommendation_id, eta_minutes, distance_km, previous_eta_minutes

See TEAM_INTEGRATION_PLAN.md D2-D5, D9-D10 for the decisions behind these
columns and TEAM_CONTRACT_INVENTORY.md for the gap analysis.

Revision ID: 0f0c42fad357
Revises: f72a07645e04
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0f0c42fad357"
down_revision = "f72a07645e04"
branch_labels = None
depends_on = None

operational_phase_enum = postgresql.ENUM(
    "received", "analyzing", "prioritized", "recommended", "awaiting_approval",
    "dispatched", "blocked", "replanning", "awaiting_replacement", "resolved",
    "rejected",
    name="operational_phase_enum",
)
recommendation_state_enum = postgresql.ENUM(
    "pending", "approved", "rejected", name="recommendation_state_enum",
)


def upgrade() -> None:
    bind = op.get_bind()
    operational_phase_enum.create(bind, checkfirst=True)
    recommendation_state_enum.create(bind, checkfirst=True)

    # --- incidents: frontend-facing phase, numeric severity, report facts ---
    op.add_column(
        "incidents",
        sa.Column(
            "operational_phase",
            postgresql.ENUM(
                "received", "analyzing", "prioritized", "recommended",
                "awaiting_approval", "dispatched", "blocked", "replanning",
                "awaiting_replacement", "resolved", "rejected",
                name="operational_phase_enum", create_type=False,
            ),
            nullable=False,
            server_default="received",
        ),
    )
    op.create_index(
        "ix_incidents_operational_phase", "incidents", ["operational_phase"]
    )

    op.add_column("incidents", sa.Column("severity_score", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_incidents_severity_score_range",
        "incidents",
        "severity_score IS NULL OR (severity_score BETWEEN 1 AND 5)",
    )

    op.add_column(
        "incidents",
        sa.Column(
            "vulnerabilities", postgresql.ARRAY(sa.String()),
            nullable=False, server_default="{}",
        ),
    )
    op.add_column(
        "incidents",
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # --- reports: immutable originals, idempotent per producer ---
    op.execute("CREATE SEQUENCE report_seq")
    op.create_table(
        "reports",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "incident_id", sa.String(),
            sa.ForeignKey("incidents.id"), nullable=False,
        ),
        sa.Column("source_report_id", sa.String(), nullable=True),
        sa.Column("producer_identity", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("original_language", sa.String(), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("translated_language", sa.String(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_reports_incident_id", "reports", ["incident_id"])
    # Idempotency: the same producer resending the same source_report_id
    # must never create a second report row. Reports without a producer or
    # source id (e.g. created directly, not via automation) are unconstrained.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_reports_producer_source
        ON reports (producer_identity, source_report_id)
        WHERE producer_identity IS NOT NULL AND source_report_id IS NOT NULL
        """
    )

    # --- recommendations: versioned pending-until-approved plans ---
    op.execute("CREATE SEQUENCE recommendation_seq")
    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "incident_id", sa.String(),
            sa.ForeignKey("incidents.id"), nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending", "approved", "rejected",
                name="recommendation_state_enum", create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("recommended_resources", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("explanation", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=True),
        sa.Column("replacement_for_resource_id", sa.String(), nullable=True),
        sa.Column(
            "replaced_assignment_id", sa.String(),
            sa.ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("analysis_revision", sa.String(), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_recommendations_incident_id", "recommendations", ["incident_id"])
    op.create_index("ix_recommendations_state", "recommendations", ["state"])
    op.create_index(
        "ix_recommendations_incident_version", "recommendations", ["incident_id", "version"]
    )
    # At most one PENDING recommendation per incident — the same partial
    # unique index pattern already used for live assignments
    # (uq_assignment_live_resource in the initial migration).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_recommendation_pending_incident
        ON recommendations (incident_id)
        WHERE state = 'pending'
        """
    )

    # --- assignments: traceability to the approved plan + ETA tracking ---
    op.add_column(
        "assignments",
        sa.Column(
            "recommendation_id", sa.String(),
            sa.ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.add_column("assignments", sa.Column("eta_minutes", sa.Integer(), nullable=True))
    op.add_column("assignments", sa.Column("distance_km", sa.Float(), nullable=True))
    op.add_column("assignments", sa.Column("previous_eta_minutes", sa.Integer(), nullable=True))
    op.create_index(
        "ix_assignments_recommendation_id", "assignments", ["recommendation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_assignments_recommendation_id", table_name="assignments")
    op.drop_column("assignments", "previous_eta_minutes")
    op.drop_column("assignments", "distance_km")
    op.drop_column("assignments", "eta_minutes")
    op.drop_column("assignments", "recommendation_id")

    op.drop_index("uq_recommendation_pending_incident", table_name="recommendations")
    op.drop_index("ix_recommendations_incident_version", table_name="recommendations")
    op.drop_index("ix_recommendations_state", table_name="recommendations")
    op.drop_index("ix_recommendations_incident_id", table_name="recommendations")
    op.drop_table("recommendations")
    op.execute("DROP SEQUENCE IF EXISTS recommendation_seq")

    op.drop_index("uq_reports_producer_source", table_name="reports")
    op.drop_index("ix_reports_incident_id", table_name="reports")
    op.drop_table("reports")
    op.execute("DROP SEQUENCE IF EXISTS report_seq")

    op.drop_column("incidents", "duplicate_count")
    op.drop_column("incidents", "vulnerabilities")
    op.drop_constraint("ck_incidents_severity_score_range", "incidents", type_="check")
    op.drop_column("incidents", "severity_score")
    op.drop_index("ix_incidents_operational_phase", table_name="incidents")
    op.drop_column("incidents", "operational_phase")

    bind = op.get_bind()
    recommendation_state_enum.drop(bind, checkfirst=True)
    operational_phase_enum.drop(bind, checkfirst=True)
