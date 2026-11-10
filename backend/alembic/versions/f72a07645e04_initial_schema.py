"""initial schema: incidents, resources, assignments, action_logs

Revision ID: f72a07645e04
Revises:
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f72a07645e04"
down_revision = None
branch_labels = None
depends_on = None

severity_enum = postgresql.ENUM(
    "LOW", "MEDIUM", "HIGH", "CRITICAL", name="severity_enum"
)
incident_status_enum = postgresql.ENUM(
    "UNASSIGNED", "ASSIGNED", "ACTIVE", "RESOLVED", "CANCELLED",
    name="incident_status_enum",
)
resource_status_enum = postgresql.ENUM(
    "AVAILABLE", "DISPATCHED", "ACTIVE", "UNAVAILABLE", name="resource_status_enum"
)
assignment_status_enum = postgresql.ENUM(
    "ASSIGNED", "ACTIVE", "COMPLETED", "CANCELLED", "SUPERSEDED",
    name="assignment_status_enum",
)


def upgrade() -> None:
    bind = op.get_bind()
    severity_enum.create(bind, checkfirst=True)
    incident_status_enum.create(bind, checkfirst=True)
    resource_status_enum.create(bind, checkfirst=True)
    assignment_status_enum.create(bind, checkfirst=True)

    # Fixed sequences for incident/assignment human-readable IDs. Resource ID
    # sequences are created on demand per type prefix by
    # app.services.id_generator (see that module for why).
    op.execute("CREATE SEQUENCE incident_seq")
    op.execute("CREATE SEQUENCE assignment_seq")

    op.create_table(
        "incidents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "LOW", "MEDIUM", "HIGH", "CRITICAL",
                name="severity_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("priority_score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("people_affected", sa.Integer(), nullable=True),
        sa.Column("needs", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "UNASSIGNED", "ASSIGNED", "ACTIVE", "RESOLVED", "CANCELLED",
                name="incident_status_enum", create_type=False,
            ),
            nullable=False,
            server_default="UNASSIGNED",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_incidents_type", "incidents", ["type"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_priority_score", "incidents", ["priority_score"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])

    op.create_table(
        "resources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("capabilities", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "AVAILABLE", "DISPATCHED", "ACTIVE", "UNAVAILABLE",
                name="resource_status_enum", create_type=False,
            ),
            nullable=False,
            server_default="AVAILABLE",
        ),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_resources_type", "resources", ["type"])
    op.create_index("ix_resources_status", "resources", ["status"])

    op.create_table(
        "assignments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "incident_id", sa.String(),
            sa.ForeignKey("incidents.id"), nullable=False,
        ),
        sa.Column(
            "resource_id", sa.String(),
            sa.ForeignKey("resources.id"), nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "ASSIGNED", "ACTIVE", "COMPLETED", "CANCELLED", "SUPERSEDED",
                name="assignment_status_enum", create_type=False,
            ),
            nullable=False,
            server_default="ASSIGNED",
        ),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_source", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_assignments_incident_id", "assignments", ["incident_id"])
    op.create_index("ix_assignments_resource_id", "assignments", ["resource_id"])
    op.create_index("ix_assignments_status", "assignments", ["status"])
    # The core concurrency-safety constraint: a resource can have at most one
    # live (ASSIGNED or ACTIVE) assignment at a time. Enforced by the
    # database itself, not just application-level locking.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_assignment_live_resource
        ON assignments (resource_id)
        WHERE status IN ('ASSIGNED', 'ACTIVE')
        """
    )

    op.create_table(
        "action_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("result", sa.String(), nullable=True),
        sa.Column(
            "incident_id", sa.String(),
            sa.ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "resource_id", sa.String(),
            sa.ForeignKey("resources.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "assignment_id", sa.String(),
            sa.ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_action_logs_timestamp", "action_logs", ["timestamp"])
    op.create_index("ix_action_logs_action", "action_logs", ["action"])
    op.create_index("ix_action_logs_incident_id", "action_logs", ["incident_id"])
    op.create_index("ix_action_logs_resource_id", "action_logs", ["resource_id"])
    op.create_index("ix_action_logs_assignment_id", "action_logs", ["assignment_id"])


def downgrade() -> None:
    op.drop_table("action_logs")
    op.drop_index("uq_assignment_live_resource", table_name="assignments")
    op.drop_table("assignments")
    op.drop_table("resources")
    op.drop_table("incidents")

    op.execute("DROP SEQUENCE IF EXISTS assignment_seq")
    op.execute("DROP SEQUENCE IF EXISTS incident_seq")

    bind = op.get_bind()
    assignment_status_enum.drop(bind, checkfirst=True)
    resource_status_enum.drop(bind, checkfirst=True)
    incident_status_enum.drop(bind, checkfirst=True)
    severity_enum.drop(bind, checkfirst=True)
