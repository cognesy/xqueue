from __future__ import annotations

import json
from pathlib import Path

from xqueue_libs.services.session_hooks import ensure_agent_hooks, inspect_agent_hooks


def test_ensure_agent_hooks_creates_repo_local_files(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "bin" / "xq"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr("xqueue_libs.services.session_hooks.resolve_executable", lambda: executable)

    result = ensure_agent_hooks(tmp_path)

    assert result.executable_path == str(executable)
    assert (tmp_path / ".claude" / "settings.json").exists()
    assert (tmp_path / ".codex" / "hooks.json").exists()
    assert (tmp_path / ".codex" / "config.toml").exists()
    assert "hooks session-start" in (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "codex_hooks = true" in (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")


def test_ensure_agent_hooks_repairs_existing_paths(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "bin" / "xq"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr("xqueue_libs.services.session_hooks.resolve_executable", lambda: executable)

    claude_path = tmp_path / ".claude" / "settings.json"
    claude_path.parent.mkdir(parents=True, exist_ok=True)
    claude_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [{"hooks": [{"type": "command", "command": "/old/xq hooks session-start"}]}],
                    "Stop": [{"hooks": [{"type": "command", "command": "/old/xq hooks session-end"}]}],
                }
            }
        ),
        encoding="utf-8",
    )

    hooks_path = tmp_path / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [{"type": "command", "command": "/old/xq hooks session-start"}],
                    "SessionEnd": [{"type": "command", "command": "/old/xq hooks session-end"}],
                }
            }
        ),
        encoding="utf-8",
    )

    ensure_agent_hooks(tmp_path)
    status = inspect_agent_hooks(tmp_path)

    assert status.claude.session_start_matches
    assert status.claude.stop_matches
    assert status.codex.session_start_matches
    assert status.codex.session_end_matches
