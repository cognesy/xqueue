"""Database integrity and maintenance services."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, inspect

from libs.domain.models import DatabaseCheckResult, DatabaseVacuumResult, HealthStatus


REQUIRED_TABLES = ("attempts", "events", "jobs", "queues", "workers")


class DatabaseMaintenanceService:
    """Run database integrity and maintenance operations."""

    def __init__(self, engine: Engine, *, database_path: Path) -> None:
        self._engine = engine
        self._database_path = database_path

    def check(self) -> DatabaseCheckResult:
        with self._engine.connect() as connection:
            integrity_result = str(connection.exec_driver_sql("PRAGMA integrity_check").scalar() or "unknown")

        table_names = set(inspect(self._engine).get_table_names())
        missing_tables = sorted(set(REQUIRED_TABLES) - table_names)
        status = HealthStatus.OK if integrity_result == "ok" and not missing_tables else HealthStatus.ERROR

        return DatabaseCheckResult(
            status=status,
            database_path=str(self._database_path),
            integrity_result=integrity_result,
            required_tables=list(REQUIRED_TABLES),
            missing_tables=missing_tables,
        )

    def vacuum(self) -> DatabaseVacuumResult:
        size_before = self._database_path.stat().st_size if self._database_path.exists() else None
        with self._engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.exec_driver_sql("VACUUM")
        size_after = self._database_path.stat().st_size if self._database_path.exists() else None
        return DatabaseVacuumResult(
            database_path=str(self._database_path),
            size_before_bytes=size_before,
            size_after_bytes=size_after,
        )
