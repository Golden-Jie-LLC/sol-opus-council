"""Council state machine and mode-specific stop contracts."""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any

from .artifacts import RunArtifacts
from .claude_cli import ClaudeCLIAdapter, ClaudeResult
from .errors import CandidateValidationError, ProtocolStateError
from .ledger import ObjectionLedger
from .prompts import build_initial_prompt, build_review_prompt
from .schema_validation import load_schema
from .util import atomic_write_json, atomic_write_text


class CouncilMode(str, Enum):
    QUESTION = "QUESTION"
    PROMPT = "PROMPT"


PLACEHOLDER_PATTERN = re.compile(r"(?im)(?:^|\b)(TODO|TBD|XXX)(?:\b|:)|<fill(?:\s+|-)?here>")


def lint_candidate(mode: CouncilMode, text: str) -> None:
    if not text.strip():
        raise CandidateValidationError("candidate cannot be empty")
    if mode is CouncilMode.PROMPT and PLACEHOLDER_PATTERN.search(text):
        raise CandidateValidationError("prompt candidate contains an unresolved placeholder")


def _render_opus_initial(structured: dict[str, Any]) -> str:
    lines = ["# Opus blind initial", "", structured["position"], ""]
    for heading, key in (
        ("Key reasons", "key_reasons"),
        ("Assumptions", "assumptions"),
        ("Risks", "risks"),
        ("Uncertainties", "uncertainties"),
    ):
        lines.extend([f"## {heading}", ""])
        lines.extend(f"- {item}" for item in structured[key])
        lines.append("")
    lines.append(f"Confidence: {structured['confidence']}")
    return "\n".join(lines).rstrip() + "\n"


class CouncilCoordinator:
    def __init__(self, artifacts: RunArtifacts) -> None:
        self.artifacts = artifacts

    @property
    def mode(self) -> CouncilMode:
        return CouncilMode(self.artifacts.state()["mode"])

    @classmethod
    def begin(
        cls,
        *,
        mode: CouncilMode,
        request: str,
        runs_root: Path,
        context: dict[str, Any] | None = None,
        repo_root: Path | None = None,
    ) -> CouncilCoordinator:
        return cls(RunArtifacts.create(runs_root, mode.value, request, context, repo_root))

    def revise_context(
        self,
        *,
        request: str,
        context: dict[str, Any],
        repo_root: Path | None = None,
    ) -> str:
        return self.artifacts.revise_context(request, context, repo_root)

    def lock_sol_initial(self, text: str) -> str:
        return self.artifacts.lock_sol_initial(text)

    def opus_initial(self, adapter: ClaudeCLIAdapter) -> ClaudeResult:
        state = self.artifacts.state()
        if state["phase"] != "sol_locked":
            raise ProtocolStateError("Opus initial requires a locked Sol initial")
        sol_text = (self.artifacts.root / state["sol_initial_file"]).read_text(encoding="utf-8")
        prompt = build_initial_prompt(
            context_text=self.artifacts.context_text(),
            mode=self.mode.value,
            schema=load_schema("initial"),
            forbidden_values=(
                sol_text if len(sol_text.strip()) >= 64 else "",
                state["sol_initial_hash"],
            ),
        )
        result = adapter.invoke(prompt, "initial")
        atomic_write_json(self.artifacts.root / "opus-initial.json", result.structured_output)
        atomic_write_text(
            self.artifacts.root / "opus-initial.md", _render_opus_initial(result.structured_output)
        )
        atomic_write_json(
            self.artifacts.root / "claude-session.json",
            {"session_id": result.session_id, "explicit_resume_required": True},
        )
        state["session_id"] = result.session_id
        if result.structured_output["context_status"] == "MISSING_CONTEXT":
            state["phase"] = "missing_context"
            state["missing_context"] = result.structured_output["missing_context"]
        else:
            state["phase"] = "blind_complete"
        self.artifacts.save_state(state)
        self._record_usage(result)
        return result

    def _ledger(self) -> ObjectionLedger:
        path = self.artifacts.root / "ledger.json"
        value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        return ObjectionLedger.from_json(value)

    def _save_ledger(self, ledger: ObjectionLedger) -> None:
        atomic_write_json(self.artifacts.root / "ledger.json", ledger.to_json())

    def _record_usage(self, result: ClaudeResult) -> None:
        manifest = self.artifacts.manifest()
        manifest.setdefault("usage", []).append(result.usage)
        self.artifacts.save_manifest(manifest)

    def review(
        self,
        *,
        candidate: str,
        sol_ready: bool,
        adapter: ClaudeCLIAdapter,
        rulings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        state = self.artifacts.state()
        if state["phase"] not in {"blind_complete", "reviewing"}:
            raise ProtocolStateError(f"cannot review during phase {state['phase']}")
        next_round = state["review_round"] + 1
        if next_round > state["max_review_rounds"]:
            raise ProtocolStateError("review round cap already reached")
        lint_candidate(self.mode, candidate)
        ledger = self._ledger()
        applied_rulings = list(rulings or [])
        ledger.apply_rulings(applied_rulings)
        _, candidate_hash = self.artifacts.freeze_candidate(candidate)
        state = self.artifacts.state()
        schema_name = "question-review" if self.mode is CouncilMode.QUESTION else "prompt-review"
        prompt = build_review_prompt(
            context_text=self.artifacts.context_text(),
            mode=self.mode.value,
            round_number=next_round,
            candidate=candidate,
            candidate_hash=candidate_hash,
            ledger=ledger.entries,
            rulings=applied_rulings,
            schema=load_schema(schema_name),
        )
        result = adapter.invoke(prompt, schema_name, session_id=state["session_id"])
        review = result.structured_output
        if review["round"] != next_round:
            raise ProtocolStateError(
                f"Claude returned round {review['round']}, expected {next_round}"
            )
        blockers = list(review["blocking_objections"])
        ledger.add_blockers(blockers, next_round)
        self._save_ledger(ledger)
        review_dir = self.artifacts.root / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(review_dir / f"round-{next_round:02d}.json", review)
        state = self.artifacts.state()
        state["review_round"] = next_round
        state["phase"] = "reviewing"
        state["open_material_blockers"] = len(ledger.open_entries())
        ready = self._ready(review, sol_ready, ledger)
        at_cap = next_round == state["max_review_rounds"]
        if ready:
            self._finalize_ready(candidate, candidate_hash, state)
        elif at_cap:
            self._finalize_cap(candidate, state, ledger)
        else:
            self.artifacts.save_state(state)
        manifest = self.artifacts.manifest()
        manifest["review_rounds"] = next_round
        self.artifacts.save_manifest(manifest)
        self._record_usage(result)
        return {
            "round": next_round,
            "ready": ready,
            "at_cap": at_cap,
            "open_material_blockers": len(ledger.open_entries()),
            "review": review,
            "candidate_hash": candidate_hash,
            "final_status": self.artifacts.state().get("final_status"),
        }

    def _ready(self, review: dict[str, Any], sol_ready: bool, ledger: ObjectionLedger) -> bool:
        if not sol_ready or ledger.open_entries() or review["blocking_objections"]:
            return False
        if self.mode is CouncilMode.QUESTION:
            return review["verdict"] == "AGREEMENT"
        readiness = review["execution_readiness"]
        return review["verdict"] == "READY_FOR_CODEX" and all(readiness.values())

    def _finalize_ready(self, candidate: str, candidate_hash: str, state: dict[str, Any]) -> None:
        state["phase"] = "complete"
        state["final_status"] = (
            "AGREEMENT" if self.mode is CouncilMode.QUESTION else "READY_FOR_CODEX"
        )
        if self.mode is CouncilMode.QUESTION:
            atomic_write_text(self.artifacts.root / "final-answer.md", candidate)
        else:
            atomic_write_text(self.artifacts.root / "FINAL_CODEX_PROMPT.md", candidate)
            atomic_write_text(
                self.artifacts.root / "FINAL_CODEX_PROMPT.sha256", f"{candidate_hash}\n"
            )
            state["sol_signoff"] = {
                "verdict": "READY_FOR_CODEX",
                "candidate_hash": candidate_hash,
            }
            state["opus_signoff"] = {
                "verdict": "READY_FOR_CODEX",
                "candidate_hash": candidate_hash,
            }
        self.artifacts.save_state(state)

    def _finalize_cap(self, candidate: str, state: dict[str, Any], ledger: ObjectionLedger) -> None:
        state["phase"] = "complete"
        if self.mode is CouncilMode.QUESTION:
            state["final_status"] = "UNRESOLVED_AFTER_3_ROUNDS"
            final = "Council status: unresolved after 3 review rounds\n\n" + candidate
            atomic_write_text(self.artifacts.root / "final-answer.md", final)
        else:
            state["final_status"] = "NO_AGREEMENT_NOT_READY_FOR_CODEX_EXECUTION"
            atomic_write_json(
                self.artifacts.root / "no-agreement.json",
                {
                    "status": "NO AGREEMENT — NOT READY FOR CODEX EXECUTION",
                    "review_rounds_used": state["max_review_rounds"],
                    "remaining_material_blockers": ledger.open_entries(),
                    "latest_draft": f"candidate-v{state['candidate_version']}.md",
                },
            )
        self.artifacts.save_state(state)

    def invalidate_after_candidate_change(self, candidate: str) -> str:
        lint_candidate(self.mode, candidate)
        _, digest = self.artifacts.freeze_candidate(candidate)
        state = self.artifacts.state()
        if state["phase"] == "complete":
            state["phase"] = "reviewing"
            state["final_status"] = None
            self.artifacts.save_state(state)
        return digest


class ScriptedAdapter:
    """Deterministic adapter for protocol tests and examples."""

    def __init__(self, outputs: list[dict[str, Any]], root: Path, session_id: str) -> None:
        self.outputs = list(outputs)
        self.root = root
        self.session_id = session_id
        self.calls: list[dict[str, Any]] = []

    def invoke(
        self, prompt: str, schema_name: str, *, session_id: str | None = None
    ) -> ClaudeResult:
        if not self.outputs:
            raise AssertionError("no scripted Claude output remains")
        if self.calls and session_id != self.session_id:
            raise AssertionError("review did not resume the explicit session id")
        structured = self.outputs.pop(0)
        call_dir = self.root / f"scripted-{len(self.calls) + 1}"
        call_dir.mkdir(parents=True, exist_ok=False)
        self.calls.append({"prompt": prompt, "schema": schema_name, "session_id": session_id})
        return ClaudeResult(
            structured_output=structured,
            session_id=self.session_id,
            raw={"structured_output": structured, "session_id": self.session_id},
            usage={},
            call_directory=call_dir,
        )
