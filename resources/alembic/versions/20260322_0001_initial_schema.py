"""Initial xqueue schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260322_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workers",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("queues", sa.JSON(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("process_id", sa.Integer(), nullable=True),
        sa.Column("concurrency", sa.Integer(), nullable=False),
    )
    op.create_index("ix_workers_state", "workers", ["state"])
    op.create_index("ix_workers_heartbeat_at", "workers", ["heartbeat_at"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("queue", sa.String(length=255), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("shell", sa.Boolean(), nullable=False),
        sa.Column("cwd", sa.Text(), nullable=True),
        sa.Column("env", sa.JSON(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=64), sa.ForeignKey("workers.id"), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_exit_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_jobs_queue", "jobs", ["queue"])
    op.create_index("ix_jobs_state", "jobs", ["state"])
    op.create_index("ix_jobs_available_at", "jobs", ["available_at"])
    op.create_index("ix_jobs_lease_expires_at", "jobs", ["lease_expires_at"])
    op.create_index("ix_jobs_claim", "jobs", ["state", "queue", "available_at", "priority", "created_at"])
    op.create_index("ix_jobs_worker_state", "jobs", ["worker_id", "state"])

    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=64), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=64), sa.ForeignKey("workers.id"), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=64), nullable=True),
        sa.Column("stdout_path", sa.Text(), nullable=True),
        sa.Column("stderr_path", sa.Text(), nullable=True),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_attempts_job_attempt_number"),
    )
    op.create_index("ix_attempts_job_id", "attempts", ["job_id"])
    op.create_index("ix_attempts_worker_id", "attempts", ["worker_id"])
    op.create_index("ix_attempts_state", "attempts", ["state"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("job_id", sa.String(length=64), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id"), nullable=True),
        sa.Column("worker_id", sa.String(length=64), sa.ForeignKey("workers.id"), nullable=True),
    )
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_created_at", "events", ["created_at"])
    op.create_index("ix_events_job_id", "events", ["job_id"])
    op.create_index("ix_events_attempt_id", "events", ["attempt_id"])
    op.create_index("ix_events_worker_id", "events", ["worker_id"])


def downgrade() -> None:
    op.drop_index("ix_events_worker_id", table_name="events")
    op.drop_index("ix_events_attempt_id", table_name="events")
    op.drop_index("ix_events_job_id", table_name="events")
    op.drop_index("ix_events_created_at", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_attempts_state", table_name="attempts")
    op.drop_index("ix_attempts_worker_id", table_name="attempts")
    op.drop_index("ix_attempts_job_id", table_name="attempts")
    op.drop_table("attempts")

    op.drop_index("ix_jobs_worker_state", table_name="jobs")
    op.drop_index("ix_jobs_claim", table_name="jobs")
    op.drop_index("ix_jobs_lease_expires_at", table_name="jobs")
    op.drop_index("ix_jobs_available_at", table_name="jobs")
    op.drop_index("ix_jobs_state", table_name="jobs")
    op.drop_index("ix_jobs_queue", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_workers_heartbeat_at", table_name="workers")
    op.drop_index("ix_workers_state", table_name="workers")
    op.drop_table("workers")
