"""Canonical context packet construction and deterministic rendering."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .util import canonical_json, sha256_text

LIST_FIELDS = (
    "hard_constraints",
    "relevant_prior_context",
    "prior_decisions",
    "known_facts",
    "evidence",
    "unknowns",
    "out_of_scope",
)

PROVIDER_AUTHORIZATION = {
    "basis": "explicit_council_invocation",
    "provider": "Anthropic Claude Opus via local Claude Code CLI",
    "scope": "minimum task-relevant context",
    "additional_provider_confirmation_required": False,
    "stricter_governing_prohibitions_still_apply": True,
}

PROVIDER_DATA_BOUNDARY = {
    "exclude_by_default": [
        "secrets_api_keys_credentials_env",
        "personal_financial_account_or_holdings_data",
        "bulk_raw_private_database_contents",
        "unrelated_private_material",
    ],
    "restricted_sensitive_material_requires_separate_handling": True,
}


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def repository_context(repo: Path | None) -> dict[str, Any]:
    if repo is None:
        return {
            "root": None,
            "branch": None,
            "head_sha": None,
            "dirty": None,
            "relevant_paths": [],
            "governing_instructions": [],
        }
    root = repo.resolve()
    status = _git(root, "status", "--porcelain")
    instructions = [
        str(path.relative_to(root)).replace("\\", "/") for path in sorted(root.rglob("AGENTS.md"))
    ]
    return {
        "root": str(root),
        "branch": _git(root, "branch", "--show-current") or None,
        "head_sha": _git(root, "rev-parse", "HEAD") or None,
        "dirty": bool(status),
        "relevant_paths": [],
        "governing_instructions": instructions,
    }


@dataclass(frozen=True)
class ContextPacket:
    payload: dict[str, Any]

    @classmethod
    def build(
        cls,
        *,
        mode: str,
        run_id: str,
        user_request: str,
        supplied: dict[str, Any] | None = None,
        repo_root: Path | None = None,
        version: int = 1,
    ) -> ContextPacket:
        extra = dict(supplied or {})
        payload: dict[str, Any] = {
            "schema_version": 1,
            "packet_version": version,
            "run_id": run_id,
            "mode": mode,
            "language": extra.pop("language", "auto"),
            "user_request_verbatim": user_request,
            "desired_output": extra.pop(
                "desired_output",
                "A reviewed answer" if mode == "QUESTION" else "A reviewed Codex execution prompt",
            ),
            "provider_authorization": dict(PROVIDER_AUTHORIZATION),
            "provider_data_boundary": {
                "exclude_by_default": list(PROVIDER_DATA_BOUNDARY["exclude_by_default"]),
                "restricted_sensitive_material_requires_separate_handling": True,
            },
        }
        for field in LIST_FIELDS:
            value = extra.pop(field, [])
            payload[field] = value if isinstance(value, list) else [value]
        supplied_repo = extra.pop("repository", {})
        repo_data = repository_context(repo_root)
        if isinstance(supplied_repo, dict):
            repo_data.update(supplied_repo)
        payload["repository"] = repo_data
        if extra:
            payload["additional_context"] = extra
        return cls(payload)

    def render(self) -> str:
        return (
            "# Canonical Context Packet\n\n"
            "This packet is frozen. The JSON block is the canonical structured value.\n\n"
            "```json\n"
            f"{canonical_json(self.payload)}"
            "```\n"
        )

    @property
    def sha256(self) -> str:
        return sha256_text(self.render())
