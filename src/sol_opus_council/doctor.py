"""Non-secret environment diagnostics."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .claude_cli import ClaudeFeatures


def _version(command: Sequence[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [*command, "--version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": type(exc).__name__}
    return {
        "available": result.returncode == 0,
        "version": result.stdout.strip() or result.stderr.strip(),
    }


def diagnose(claude_command: Sequence[str] | None = None) -> dict[str, Any]:
    codex = shutil.which("codex")
    claude = tuple(
        claude_command or (() if not shutil.which("claude") else (shutil.which("claude"),))
    )
    result: dict[str, Any] = {
        "operating_system": platform.platform(),
        "python": {"available": sys.version_info >= (3, 11), "version": sys.version.split()[0]},
        "codex": _version((codex,)) if codex else {"available": False},
        "claude": {"available": False, "authenticated": False},
        "ready_for_deterministic_tests": True,
        "ready_for_live_council": False,
    }
    if claude:
        try:
            features = ClaudeFeatures.detect(claude)
            result["claude"] = {
                "available": True,
                "version": features.version,
                "authenticated": features.authenticated,
                "auth_method": features.auth_method,
                "required_flags": True,
                "command": str(Path(claude[0])),
            }
            result["ready_for_live_council"] = bool(
                result["python"]["available"]
                and result["codex"]["available"]
                and features.authenticated
            )
        except Exception as exc:  # diagnostic output, no secret-bearing exception body
            result["claude"] = {
                "available": False,
                "authenticated": False,
                "error": type(exc).__name__,
            }
    return result
