"""Ports owned by the jobs capability."""

from __future__ import annotations

from typing import Protocol


class JobLogPort(Protocol):
    """Filesystem operations required by job use cases.

    Use cases that read or remove attempt log files annotate their dependency
    with this protocol, so the seam is type-checked rather than merely
    described. It is also what lets the maintenance capability depend on log
    removal without importing the jobs implementation.
    """

    def tail(self, *, path: str, lines: int) -> tuple[list[str], bool]: ...

    def delete_paths(self, *, paths: list[str]) -> list[str]: ...
