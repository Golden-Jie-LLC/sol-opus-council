from __future__ import annotations

from typing import Any


def initial(*, status: str = "SUFFICIENT") -> dict[str, Any]:
    return {
        "context_status": status,
        "missing_context": [] if status == "SUFFICIENT" else ["material fact"],
        "position": "Independent Opus position",
        "key_reasons": ["reason"],
        "assumptions": [],
        "risks": [],
        "uncertainties": [],
        "confidence": 0.8,
    }


def blocker(identifier: str = "source-1") -> dict[str, str]:
    return {
        "id": identifier,
        "target": "candidate",
        "issue": "material omission",
        "why_it_matters": "could cause an incorrect result",
        "required_change": "add the missing requirement",
    }


def question_review(round_number: int, *, ready: bool, blockers: list[dict] | None = None) -> dict:
    return {
        "round": round_number,
        "verdict": "AGREEMENT" if ready else "DISPUTE_REMAINS",
        "accepted_resolutions": [],
        "blocking_objections": [] if ready else (blockers or [blocker()]),
        "non_blocking_suggestions": [],
        "incorrect_or_missing_assumptions": [],
        "proposed_changes": [],
    }


def prompt_review(
    round_number: int,
    *,
    ready: bool,
    blockers: list[dict] | None = None,
    suggestions: list[str] | None = None,
) -> dict:
    gates = {
        "user_intent_preserved": ready,
        "material_requirements_present": ready,
        "material_constraints_present": ready,
        "no_material_contradictions": ready,
        "context_sufficient_for_execution": ready,
        "implementation_scope_clear": ready,
        "material_edge_cases_addressed": ready,
        "verification_sufficient": ready,
        "no_unresolved_material_placeholders": ready,
        "ready_for_codex_execution": ready,
    }
    return {
        "round": round_number,
        "verdict": "READY_FOR_CODEX" if ready else "REVISION_REQUIRED",
        "accepted_resolutions": [],
        "blocking_objections": [] if ready else (blockers or [blocker()]),
        "non_blocking_suggestions": suggestions or [],
        "incorrect_or_missing_assumptions": [],
        "proposed_changes": [],
        "execution_readiness": gates,
    }
