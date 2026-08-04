from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_expected_schema(monkeypatch, tmp_path: Path) -> None:
    database_path = tmp_path / "schema.db"
    monkeypatch.setenv("XQUEUE_DB_PATH", str(database_path))

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {"jobs", "attempts", "workers", "events", "queues"} <= table_names

    jobs_indexes = {index["name"] for index in inspector.get_indexes("jobs")}
    attempts_indexes = {index["name"] for index in inspector.get_indexes("attempts")}
    queues_indexes = {index["name"] for index in inspector.get_indexes("queues")}

    assert "ix_jobs_claim" in jobs_indexes
    assert "ix_jobs_worker_state" in jobs_indexes
    assert "ix_attempts_job_id" in attempts_indexes
    assert "ix_queues_state" in queues_indexes
