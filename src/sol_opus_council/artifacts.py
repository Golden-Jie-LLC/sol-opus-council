"""Run artifact storage with atomic writes and state invalidation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .context_packet import ContextPacket
from .errors import ContextRepairLimitError, ProtocolStateError
from .util import atomic_write_json, atomic_write_text, read_json, sha256_text


@dataclass
class RunArtifacts:
    root: Path

    @property
    def state_path(self) -> Path:
        return self.root / "status.json"

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @classmethod
    def create(
        cls,
        runs_root: Path,
        mode: str,
        request: str,
        supplied_context: dict[str, Any] | None = None,
        repo_root: Path | None = None,
    ) -> RunArtifacts:
        run_id = str(uuid4())
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        root = runs_root / f"{stamp}-{run_id}"
        root.mkdir(parents=True, exist_ok=False)
        packet = ContextPacket.build(
            mode=mode,
            run_id=run_id,
            user_request=request,
            supplied=supplied_context,
            repo_root=repo_root,
        )
        instance = cls(root)
        instance._write_context(packet)
        max_rounds = 3 if mode == "QUESTION" else 10
        state = {
            "schema_version": 1,
            "run_id": run_id,
            "mode": mode,
            "phase": "context_frozen",
            "context_version": 1,
            "context_hash": packet.sha256,
            "context_repairs": 0,
            "review_round": 0,
            "max_review_rounds": max_rounds,
            "candidate_version": 0,
            "candidate_hash": None,
            "session_id": None,
            "sol_signoff": None,
            "opus_signoff": None,
            "final_status": None,
        }
        instance.save_state(state)
        atomic_write_json(
            instance.manifest_path,
            {
                "schema_version": 1,
                "run_id": run_id,
                "mode": mode,
                "created_at": datetime.now(UTC).isoformat(),
                "context_hash": packet.sha256,
                "review_rounds": 0,
                "model": {"sol": "gpt-5.6-sol", "opus": "opus"},
                "usage": [],
            },
        )
        return instance

    @classmethod
    def open(cls, root: Path) -> RunArtifacts:
        instance = cls(root.resolve())
        if not instance.state_path.is_file():
            raise FileNotFoundError(f"not a council run: {root}")
        return instance

    def state(self) -> dict[str, Any]:
        return read_json(self.state_path)

    def save_state(self, state: dict[str, Any]) -> None:
        atomic_write_json(self.state_path, state)

    def manifest(self) -> dict[str, Any]:
        return read_json(self.manifest_path)

    def save_manifest(self, manifest: dict[str, Any]) -> None:
        atomic_write_json(self.manifest_path, manifest)

    def _write_context(self, packet: ContextPacket) -> None:
        version = packet.payload["packet_version"]
        rendered = packet.render()
        atomic_write_text(self.root / f"context-v{version}.md", rendered)
        atomic_write_json(self.root / f"context-v{version}.json", packet.payload)
        atomic_write_text(self.root / f"context-v{version}.sha256", f"{packet.sha256}\n")

    def context_text(self) -> str:
        state = self.state()
        return (self.root / f"context-v{state['context_version']}.md").read_text(encoding="utf-8")

    def revise_context(
        self,
        request: str,
        supplied_context: dict[str, Any],
        repo_root: Path | None,
    ) -> str:
        state = self.state()
        if state["context_repairs"] >= 2:
            raise ContextRepairLimitError("maximum of two context repairs reached")
        version = state["context_version"] + 1
        packet = ContextPacket.build(
            mode=state["mode"],
            run_id=state["run_id"],
            user_request=request,
            supplied=supplied_context,
            repo_root=repo_root,
            version=version,
        )
        self._write_context(packet)
        state.update(
            {
                "phase": "context_frozen",
                "context_version": version,
                "context_hash": packet.sha256,
                "context_repairs": state["context_repairs"] + 1,
                "review_round": 0,
                "candidate_version": 0,
                "candidate_hash": None,
                "session_id": None,
                "sol_signoff": None,
                "opus_signoff": None,
                "final_status": None,
            }
        )
        self.save_state(state)
        manifest = self.manifest()
        manifest["context_hash"] = packet.sha256
        manifest["review_rounds"] = 0
        self.save_manifest(manifest)
        return packet.sha256

    def lock_sol_initial(self, text: str) -> str:
        state = self.state()
        if state["phase"] != "context_frozen":
            raise ProtocolStateError("Sol initial can only be locked after context freeze")
        if not text.strip():
            raise ProtocolStateError("Sol initial cannot be empty")
        version = state["context_version"]
        filename = "sol-initial.md" if version == 1 else f"sol-initial-v{version}.md"
        digest = sha256_text(text)
        atomic_write_text(self.root / filename, text)
        atomic_write_text(self.root / f"{filename}.sha256", f"{digest}\n")
        state["phase"] = "sol_locked"
        state["sol_initial_file"] = filename
        state["sol_initial_hash"] = digest
        self.save_state(state)
        return digest

    def freeze_candidate(self, text: str) -> tuple[Path, str]:
        state = self.state()
        version = state["candidate_version"] + 1
        digest = sha256_text(text)
        path = self.root / f"candidate-v{version}.md"
        atomic_write_text(path, text)
        atomic_write_text(self.root / f"candidate-v{version}.sha256", f"{digest}\n")
        if state.get("candidate_hash") != digest:
            state["sol_signoff"] = None
            state["opus_signoff"] = None
        state["candidate_version"] = version
        state["candidate_hash"] = digest
        self.save_state(state)
        return path, digest
