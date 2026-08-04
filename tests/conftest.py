from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_xqueue_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XQUEUE_HOME", str(tmp_path / "xqueue-home"))
    # A developer with XQUEUE_ROOT exported would otherwise win step 2 of the
    # resolver and silently redirect every test at their own workspace.
    monkeypatch.delenv("XQUEUE_ROOT", raising=False)
