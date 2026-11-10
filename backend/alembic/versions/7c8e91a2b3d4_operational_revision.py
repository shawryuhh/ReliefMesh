"""Create operational revision storage (not yet wired to writes).

Revision ID: 7c8e91a2b3d4
Revises: 0f0c42fad357
"""
from alembic import op
import sqlalchemy as sa

revision = "7c8e91a2b3d4"
down_revision = "0f0c42fad357"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_revision",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_operational_revision_singleton"),
        sa.CheckConstraint("revision >= 0", name="ck_operational_revision_nonnegative"),
    )
    op.execute("INSERT INTO operational_revision (id, revision) VALUES (1, 0)")


def downgrade() -> None:
    op.drop_table("operational_revision")
