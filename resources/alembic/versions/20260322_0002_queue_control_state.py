"""Add durable queue control state."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260322_0002"
down_revision = "20260322_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "queues",
        sa.Column("name", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_queues_state", "queues", ["state"])


def downgrade() -> None:
    op.drop_index("ix_queues_state", table_name="queues")
    op.drop_table("queues")
