"""Feature-detected, read-only Claude Code CLI adapter."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from .errors import (
    AuthenticationError,
    MalformedOutputError,
    OpusUnavailableError,
    PreflightError,
    ProcessError,
    ProcessTimeoutError,
    SchemaValidationError,
)
from .schema_validation import load_schema, validate_schema
from .util import atomic_write_json, atomic_write_text

READ_ONLY_TOOLS = ("Read", "Glob", "Grep", "WebSearch", "WebFetch")
REQUIRED_FLAGS = (
    "--print",
    "--model",
    "--effort",
    "--output-format",
    "--json-schema",
    "--resume",
    "--tools",
    "--safe-mode",
    "--strict-mcp-config",
)
TRANSIENT_MARKERS = ("overloaded", "rate limit", "temporarily unavailable", "server error", "529")
MODEL_MARKERS = ("model not found", "opus unavailable", "invalid model")


@dataclass(frozen=True)
class ClaudeFeatures:
    command: tuple[str, ...]
    version: str
    help_text: str
    authenticated: bool
    auth_method: str

    @classmethod
    def detect(cls, command: Sequence[str], timeout: float = 20) -> ClaudeFeatures:
        base = tuple(str(part) for part in command)
        if not base:
            raise PreflightError("Claude command is empty")

        def probe(*args: str) -> subprocess.CompletedProcess[str]:
            try:
                return subprocess.run(
                    [*base, *args],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise PreflightError(f"Claude preflight failed: {exc}") from exc

        version_result = probe("--version")
        help_result = probe("--help")
        auth_result = probe("auth", "status")
        if version_result.returncode != 0 or help_result.returncode != 0:
            raise PreflightError("Claude --version/--help failed")
        help_text = f"{help_result.stdout}\n{help_result.stderr}"
        missing = [flag for flag in REQUIRED_FLAGS if flag not in help_text]
        if missing:
            raise PreflightError(f"Claude CLI lacks required flags: {', '.join(missing)}")
        authenticated = False
        auth_method = "unknown"
        try:
            auth = json.loads(auth_result.stdout)
            if isinstance(auth, dict):
                authenticated = bool(auth.get("loggedIn"))
                auth_method = str(auth.get("authMethod", "unknown"))
        except json.JSONDecodeError:
            authenticated = auth_result.returncode == 0 and "logged" in auth_result.stdout.lower()
        return cls(
            command=base,
            version=version_result.stdout.strip(),
            help_text=help_text,
            authenticated=authenticated,
            auth_method=auth_method,
        )


@dataclass(frozen=True)
class ClaudeResult:
    structured_output: dict[str, Any]
    session_id: str
    raw: dict[str, Any]
    usage: dict[str, Any]
    call_directory: Path


class ClaudeCLIAdapter:
    def __init__(
        self,
        command: Sequence[str],
        artifact_root: Path,
        *,
        timeout_seconds: float = 300,
        transient_retries: int = 2,
        malformed_retries: int = 1,
        require_auth: bool = True,
    ) -> None:
        self.command = tuple(str(part) for part in command)
        self.artifact_root = artifact_root
        self.timeout_seconds = timeout_seconds
        self.transient_retries = transient_retries
        self.malformed_retries = malformed_retries
        self.require_auth = require_auth
        self._features: ClaudeFeatures | None = None

    def preflight(self) -> ClaudeFeatures:
        if self._features is None:
            self._features = ClaudeFeatures.detect(self.command)
        if self.require_auth and not self._features.authenticated:
            raise AuthenticationError("Claude Code is not logged in")
        return self._features

    def build_args(self, schema: dict[str, Any], session_id: str | None = None) -> list[str]:
        args = [
            *self.command,
            "-p",
            "--model",
            "opus",
            "--effort",
            "high",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
            "--safe-mode",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-chrome",
            "--permission-mode",
            "dontAsk",
            "--tools",
            ",".join(READ_ONLY_TOOLS),
        ]
        if session_id:
            UUID(session_id)
            args.extend(["--resume", session_id])
        return args

    def invoke(
        self, prompt: str, schema_name: str, *, session_id: str | None = None
    ) -> ClaudeResult:
        self.preflight()
        schema = load_schema(schema_name)
        transient_attempts = 0
        malformed_attempts = 0
        attempt = 0
        current_prompt = prompt
        while True:
            attempt += 1
            call_dir = self.artifact_root / "calls" / f"{attempt:02d}-{uuid4().hex}"
            call_dir.mkdir(parents=True, exist_ok=False)
            atomic_write_text(call_dir / "prompt.txt", current_prompt)
            args = self.build_args(schema, session_id)
            atomic_write_json(call_dir / "argv.json", args)
            started = time.monotonic()
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            try:
                process = subprocess.Popen(
                    args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creationflags,
                )
                stdout, stderr = process.communicate(current_prompt, timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                process.kill()
                stdout, stderr = process.communicate()
                atomic_write_text(call_dir / "stdout.txt", stdout)
                atomic_write_text(call_dir / "stderr.txt", stderr)
                raise ProcessTimeoutError(
                    f"Claude timed out after {self.timeout_seconds:g}s"
                ) from exc
            except OSError as exc:
                raise ProcessError(f"unable to start Claude: {exc}") from exc
            atomic_write_text(call_dir / "stdout.txt", stdout)
            atomic_write_text(call_dir / "stderr.txt", stderr)
            atomic_write_json(
                call_dir / "process.json",
                {"return_code": process.returncode, "duration_seconds": time.monotonic() - started},
            )
            combined = f"{stdout}\n{stderr}".lower()
            if any(marker in combined for marker in MODEL_MARKERS):
                raise OpusUnavailableError("Opus is unavailable; fallback is forbidden")
            if process.returncode != 0:
                if (
                    any(marker in combined for marker in TRANSIENT_MARKERS)
                    and transient_attempts < self.transient_retries
                ):
                    transient_attempts += 1
                    continue
                raise ProcessError(f"Claude exited with code {process.returncode}")
            try:
                raw = json.loads(stdout)
                if not isinstance(raw, dict):
                    raise ValueError("top-level result is not an object")
                structured = raw.get("structured_output")
                if structured is None and isinstance(raw.get("result"), str):
                    structured = json.loads(raw["result"])
                if not isinstance(structured, dict):
                    raise ValueError("structured_output is missing")
                validate_schema(structured, schema)
                result_session = raw.get("session_id") or session_id
                if not isinstance(result_session, str):
                    raise ValueError("session_id is missing")
                UUID(result_session)
                resolved_model = raw.get("model")
                if isinstance(resolved_model, str) and "opus" not in resolved_model.lower():
                    raise OpusUnavailableError(f"resolved model is not Opus: {resolved_model}")
            except OpusUnavailableError:
                raise
            except (json.JSONDecodeError, SchemaValidationError, ValueError, TypeError) as exc:
                if malformed_attempts < self.malformed_retries:
                    malformed_attempts += 1
                    current_prompt = (
                        prompt + "\n\nCORRECTIVE RETRY: return non-empty JSON structured output "
                        "that exactly matches the supplied schema."
                    )
                    continue
                raise MalformedOutputError(f"malformed Claude JSON: {exc}") from exc
            atomic_write_json(call_dir / "parsed.json", raw)
            usage = {
                key: raw[key]
                for key in (
                    "usage",
                    "total_cost_usd",
                    "duration_ms",
                    "duration_api_ms",
                    "num_turns",
                    "model",
                )
                if key in raw
            }
            return ClaudeResult(structured, result_session, raw, usage, call_dir)


def find_claude_command(explicit: str | None = None) -> tuple[str, ...]:
    if explicit:
        return (explicit,)
    configured = os.environ.get("CLAUDE_BIN")
    if configured:
        return (configured,)
    from shutil import which

    located = which("claude")
    if not located:
        raise PreflightError("Claude CLI not found; set CLAUDE_BIN or add claude to PATH")
    return (located,)


def redact_stderr(stderr: str) -> str:
    return re.sub(r"(?i)(token|api[_-]?key|authorization)\s*[:=]\s*\S+", r"\1=<redacted>", stderr)
