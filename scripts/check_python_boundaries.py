from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]

CAPABILITIES = (
    "controller",
    "jobs",
    "maintenance",
    "queues",
    "workers",
    "workspace",
)

# Workspace resolution happens once, in the composition root, and the decided
# root is handed down. A capability that imports the resolver would answer
# "which workspace am I in" for itself, and could answer it differently from the
# runtime that opened it. `workspace` is absent because the resolver lives there.
ROOT_CONSUMING_CAPABILITIES = tuple(f"libs/{capability}/" for capability in CAPABILITIES if capability != "workspace")

# Allowlist, deliberately: everything under xqueue is private to the CLI until
# it is named here, so a new capability module cannot become CLI-reachable by
# simply existing.
CLI_PUBLIC_SURFACE = (
    "xqueue.core.errors",
    # The CLI is the process entrypoint and owns logging bootstrap; no other
    # runtime module is reachable from it.
    "xqueue.runtime.logging",
    *(f"xqueue.{capability}.models" for capability in CAPABILITIES),
)


@dataclass(frozen=True, slots=True)
class Violation:
    rule: str
    path: str
    line: int
    imported: str


def _imports(source: str, *, filename: str) -> list[tuple[int, str]]:
    tree = ast.parse(source, filename=filename)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
    return found


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _is_library_module(module: str) -> bool:
    """True for the xqueue library package only; xqueue_cli is not part of it."""
    return module == "xqueue" or module.startswith("xqueue.")


def check_source(path: str, source: str) -> list[Violation]:
    normalized = PurePosixPath(path).as_posix()
    violations: list[Violation] = []
    for line, imported in _imports(source, filename=normalized):
        if normalized.startswith("apps/cli/") and _matches(imported, ("sqlalchemy", "xqueue.adapters")):
            violations.append(Violation("cli-sealed-boundary", normalized, line, imported))
        if (
            normalized.startswith("apps/cli/")
            and _is_library_module(imported)
            and imported != "xqueue"
            and not _matches(imported, CLI_PUBLIC_SURFACE)
            # Sealed persistence is already reported as cli-sealed-boundary.
            and not _matches(imported, ("xqueue.adapters",))
        ):
            violations.append(Violation("cli-sdk-only", normalized, line, imported))
        if normalized.startswith("libs/core/") and _matches(
            imported,
            (
                "xqueue.actions",
                "xqueue.adapters",
                "xqueue.controller",
                "xqueue.infra",
                "xqueue.jobs",
                "xqueue.maintenance",
                "xqueue.queues",
                "xqueue.runtime",
                "xqueue.services",
                "xqueue.workers",
                "xqueue.workspace",
                "xqueue_cli",
            ),
        ):
            violations.append(Violation("core-no-upward-imports", normalized, line, imported))
        if normalized.startswith("libs/adapters/") and _matches(imported, ("xqueue_cli",)):
            violations.append(Violation("adapters-no-channel-imports", normalized, line, imported))
        if (
            normalized.startswith("libs/queues/")
            and _matches(imported, ("xqueue.jobs",))
            and not _matches(imported, ("xqueue.jobs.models",))
        ):
            violations.append(Violation("queues-public-jobs-contract-only", normalized, line, imported))
        if normalized.startswith(ROOT_CONSUMING_CAPABILITIES) and _matches(imported, ("xqueue.workspace.resolver",)):
            violations.append(Violation("capabilities-do-not-resolve-workspaces", normalized, line, imported))
    return violations


def scan_repository(root: Path = REPO_ROOT) -> list[Violation]:
    violations: list[Violation] = []
    for directory in (root / "apps", root / "libs"):
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(root).as_posix()
            violations.extend(check_source(relative, path.read_text()))
    return violations


def main() -> int:
    violations = scan_repository()
    if not violations:
        print("Python architecture boundaries passed")
        return 0
    for violation in violations:
        print(
            f"{violation.path}:{violation.line}: {violation.rule}: forbidden import {violation.imported}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
