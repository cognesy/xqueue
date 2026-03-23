"""File-based job log inspection and cleanup services."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from libs.domain.errors import NotFoundError


class JobLogService:
    """Inspect and clean up file-based attempt logs."""

    def tail(self, *, path: str, lines: int) -> tuple[list[str], bool]:
        log_path = Path(path)
        if not log_path.exists():
            raise NotFoundError("log file not found", details={"path": str(log_path)})

        with log_path.open("r", encoding="utf-8") as handle:
            collected = deque(maxlen=lines)
            total_lines = 0
            for line in handle:
                total_lines += 1
                collected.append(line.rstrip("\n"))

        return list(collected), total_lines > lines

    def delete_paths(self, *, paths: list[str]) -> list[str]:
        deleted_paths: list[str] = []
        candidate_directories: set[Path] = set()

        for raw_path in paths:
            log_path = Path(raw_path)
            if not log_path.exists():
                continue
            log_path.unlink()
            deleted_paths.append(str(log_path))
            candidate_directories.add(log_path.parent)

        for directory in sorted(candidate_directories, key=lambda item: len(item.parts), reverse=True):
            self._remove_empty_parents(directory)

        return deleted_paths

    def _remove_empty_parents(self, directory: Path) -> None:
        current = directory
        while current.exists():
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
