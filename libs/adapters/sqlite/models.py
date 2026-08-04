"""SQLAlchemy persistence models for the SQLite adapter."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for ORM models."""


class JobModel(Base):
    """Current durable job state and operator-facing metadata."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_claim", "state", "queue", "available_at", "priority", "created_at"),
        Index("ix_jobs_worker_state", "worker_id", "state"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    queue: Mapped[str] = mapped_column(String(255), index=True)
    command: Mapped[str] = mapped_column(Text())
    shell: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)
    cwd: Mapped[str | None] = mapped_column(Text(), nullable=True)
    env: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    priority: Mapped[int] = mapped_column(Integer(), default=100, nullable=False)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    max_attempts: Mapped[int] = mapped_column(Integer(), default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    worker_id: Mapped[str | None] = mapped_column(ForeignKey("workers.id"), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    last_exit_code: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    attempts: Mapped[list["AttemptModel"]] = relationship(back_populates="job")
    worker: Mapped["WorkerModel | None"] = relationship(back_populates="jobs")
    events: Mapped[list["EventModel"]] = relationship(back_populates="job")


class AttemptModel(Base):
    """Execution-attempt history for jobs."""

    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("job_id", "attempt_number", name="uq_attempts_job_attempt_number"),)

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    worker_id: Mapped[str | None] = mapped_column(ForeignKey("workers.id"), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stdout_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    stderr_path: Mapped[str | None] = mapped_column(Text(), nullable=True)

    job: Mapped[JobModel] = relationship(back_populates="attempts")
    worker: Mapped["WorkerModel | None"] = relationship(back_populates="attempts")
    events: Mapped[list["EventModel"]] = relationship(back_populates="attempt")


class WorkerModel(Base):
    """Worker identity, queues served, heartbeat, and operational state."""

    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    queues: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    process_id: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    concurrency: Mapped[int] = mapped_column(Integer(), default=1, nullable=False)

    jobs: Mapped[list[JobModel]] = relationship(back_populates="worker")
    attempts: Mapped[list[AttemptModel]] = relationship(back_populates="worker")
    events: Mapped[list["EventModel"]] = relationship(back_populates="worker")


class QueueModel(Base):
    """Persisted queue control state."""

    __tablename__ = "queues"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EventModel(Base):
    """Append-only audit trail for significant state transitions."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("attempts.id"), nullable=True, index=True)
    worker_id: Mapped[str | None] = mapped_column(ForeignKey("workers.id"), nullable=True, index=True)

    job: Mapped[JobModel | None] = relationship(back_populates="events")
    attempt: Mapped[AttemptModel | None] = relationship(back_populates="events")
    worker: Mapped[WorkerModel | None] = relationship(back_populates="events")
