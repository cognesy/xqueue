"""Repo-local session hook installer for Claude Code and Codex."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLAUDE_SETTINGS_REL = ".claude/settings.json"
CODEX_HOOKS_REL = ".codex/hooks.json"
CODEX_CONFIG_REL = ".codex/config.toml"
SESSION_HISTORY_REL = ".xqueue/session-history.jsonl"


@dataclass(frozen=True)
class HookInstallResult:
    executable_path: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True)
class ClaudeHookStatusResult:
    settings_path: str
    settings_exists: bool
    session_start_matches: bool
    stop_matches: bool


@dataclass(frozen=True)
class CodexHookStatusResult:
    config_path: str
    hooks_path: str
    config_exists: bool
    hooks_exists: bool
    feature_enabled: bool
    session_start_matches: bool
    session_end_matches: bool


@dataclass(frozen=True)
class HookStatusResult:
    executable_path: str
    claude: ClaudeHookStatusResult
    codex: CodexHookStatusResult


def resolve_executable() -> Path:
    """Resolve the absolute path of the xq executable."""
    which = shutil.which("xq")
    if which:
        return Path(which).resolve()
    return Path(sys.argv[0]).resolve()


def ensure_agent_hooks(project_root: Path) -> HookInstallResult:
    """Install or update repo-local Claude Code and Codex hooks."""
    executable = resolve_executable()
    changed_files: list[str] = []

    if _ensure_claude_hooks(project_root, executable):
        changed_files.append(str(project_root / CLAUDE_SETTINGS_REL))
    if _ensure_codex_hooks(project_root, executable):
        changed_files.append(str(project_root / CODEX_HOOKS_REL))
    if _ensure_codex_config(project_root):
        changed_files.append(str(project_root / CODEX_CONFIG_REL))

    return HookInstallResult(
        executable_path=str(executable),
        changed_files=tuple(changed_files),
    )


def inspect_agent_hooks(project_root: Path) -> HookStatusResult:
    """Inspect repo-local hook installation state."""
    executable = resolve_executable()
    return HookStatusResult(
        executable_path=str(executable),
        claude=_inspect_claude(project_root, executable),
        codex=_inspect_codex(project_root, executable),
    )


def capture_session_end(project_root: Path) -> Path:
    """Append a session-end record to the repo-local history log."""
    log_path = project_root / SESSION_HISTORY_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": "session_end",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    return log_path


def _session_start_cmd(executable: Path) -> str:
    return f"{executable} hooks session-start"


def _session_end_cmd(executable: Path) -> str:
    return f"{executable} hooks session-end"


def _ensure_claude_hooks(project_root: Path, executable: Path) -> bool:
    settings_path = project_root / CLAUDE_SETTINGS_REL
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_json(settings_path)
    hooks = payload.setdefault("hooks", {})
    changed = False
    changed |= _upsert_claude_hook(hooks, "SessionStart", _session_start_cmd(executable))
    changed |= _upsert_claude_hook(hooks, "Stop", _session_end_cmd(executable))
    if changed or not settings_path.exists():
        settings_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return True
    return False


def _inspect_claude(project_root: Path, executable: Path) -> ClaudeHookStatusResult:
    settings_path = project_root / CLAUDE_SETTINGS_REL
    payload = _load_json(settings_path) if settings_path.exists() else {}
    hooks = payload.get("hooks", {}) if isinstance(payload, dict) else {}
    return ClaudeHookStatusResult(
        settings_path=str(settings_path),
        settings_exists=settings_path.exists(),
        session_start_matches=_claude_hook_matches(hooks, "SessionStart", _session_start_cmd(executable)),
        stop_matches=_claude_hook_matches(hooks, "Stop", _session_end_cmd(executable)),
    )


def _upsert_claude_hook(hooks: dict[str, Any], event: str, command: str) -> bool:
    entries = hooks.get(event)
    if not isinstance(entries, list):
        hooks[event] = [{"hooks": [{"type": "command", "command": command}]}]
        return True
    suffix = command.split(" ", 1)[1] if " " in command else command
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hook_items = entry.get("hooks")
        if not isinstance(hook_items, list):
            continue
        for hook in hook_items:
            if not isinstance(hook, dict):
                continue
            existing = hook.get("command", "")
            if isinstance(existing, str) and existing.endswith(suffix):
                if existing != command or hook.get("type") != "command":
                    hook["type"] = "command"
                    hook["command"] = command
                    return True
                return False
    entries.append({"hooks": [{"type": "command", "command": command}]})
    return True


def _claude_hook_matches(hooks: dict[str, Any], event: str, command: str) -> bool:
    entries = hooks.get(event)
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks", []):
            if isinstance(hook, dict) and hook.get("command") == command:
                return True
    return False


def _ensure_codex_hooks(project_root: Path, executable: Path) -> bool:
    hooks_path = project_root / CODEX_HOOKS_REL
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_json(hooks_path)
    hooks = payload.setdefault("hooks", {})
    changed = False
    changed |= _upsert_codex_hook(hooks, "SessionStart", _session_start_cmd(executable))
    changed |= _upsert_codex_hook(hooks, "SessionEnd", _session_end_cmd(executable))
    if changed or not hooks_path.exists():
        hooks_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return True
    return False


def _ensure_codex_config(project_root: Path) -> bool:
    config_path = project_root / CODEX_CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        content = config_path.read_text(encoding="utf-8")
        if "codex_hooks = true" not in content:
            config_path.write_text(content.rstrip() + "\n\n[features]\ncodex_hooks = true\n", encoding="utf-8")
            return True
        return False

    config_path.write_text("[features]\ncodex_hooks = true\n", encoding="utf-8")
    return True


def _inspect_codex(project_root: Path, executable: Path) -> CodexHookStatusResult:
    hooks_path = project_root / CODEX_HOOKS_REL
    config_path = project_root / CODEX_CONFIG_REL
    payload = _load_json(hooks_path) if hooks_path.exists() else {}
    hooks = payload.get("hooks", {}) if isinstance(payload, dict) else {}
    feature_enabled = config_path.exists() and "codex_hooks = true" in config_path.read_text(encoding="utf-8")
    return CodexHookStatusResult(
        config_path=str(config_path),
        hooks_path=str(hooks_path),
        config_exists=config_path.exists(),
        hooks_exists=hooks_path.exists(),
        feature_enabled=feature_enabled,
        session_start_matches=_codex_hook_matches(hooks, "SessionStart", _session_start_cmd(executable)),
        session_end_matches=_codex_hook_matches(hooks, "SessionEnd", _session_end_cmd(executable)),
    )


def _upsert_codex_hook(hooks: dict[str, Any], event: str, command: str) -> bool:
    entries = hooks.get(event)
    if not isinstance(entries, list):
        hooks[event] = [{"type": "command", "command": command}]
        return True
    suffix = command.split(" ", 1)[1] if " " in command else command
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        existing = entry.get("command", "")
        if isinstance(existing, str) and existing.endswith(suffix):
            if existing != command or entry.get("type") != "command":
                entry["type"] = "command"
                entry["command"] = command
                return True
            return False
    entries.append({"type": "command", "command": command})
    return True


def _codex_hook_matches(hooks: dict[str, Any], event: str, command: str) -> bool:
    entries = hooks.get(event)
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if isinstance(entry, dict) and entry.get("command") == command:
            return True
    return False


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


__all__ = [
    "ClaudeHookStatusResult",
    "CodexHookStatusResult",
    "HookInstallResult",
    "HookStatusResult",
    "capture_session_end",
    "ensure_agent_hooks",
    "inspect_agent_hooks",
    "resolve_executable",
]
