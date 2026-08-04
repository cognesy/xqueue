from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RULES = REPO_ROOT / ".semgrep" / "xqueue-architecture.yml"
ALLOWED_FINDINGS: set[tuple[str, str]] = set()


def _rule_id(result: dict[str, Any]) -> str:
    return str(result["check_id"]).rsplit(".", 1)[-1]


def main() -> int:
    command = [
        "uvx",
        "semgrep",
        "scan",
        "--quiet",
        "--json",
        "--config",
        str(RULES),
        "apps",
        "libs",
        "tests",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        sys.stderr.write(completed.stderr)
        return completed.returncode

    report = json.loads(completed.stdout)
    findings = {(_rule_id(result), str(result["path"])) for result in report.get("results", [])}
    unexpected = findings - ALLOWED_FINDINGS
    stale_allowances = ALLOWED_FINDINGS - findings

    if unexpected:
        for rule_id, path in sorted(unexpected):
            print(f"unexpected architecture finding: {rule_id} {path}", file=sys.stderr)
        return 1

    if stale_allowances:
        for rule_id, path in sorted(stale_allowances):
            print(f"remove resolved architecture allowance: {rule_id} {path}", file=sys.stderr)
        return 1

    print(f"architecture ratchet passed ({len(findings)} allowed findings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
