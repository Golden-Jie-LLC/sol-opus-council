"""Stable objection ledger owned by the Codex host."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import ProtocolStateError

VALID_STATES = {"open", "accepted", "rebutted", "resolved", "superseded"}


@dataclass
class ObjectionLedger:
    entries: list[dict[str, Any]] = field(default_factory=list)
    next_number: int = 1

    @classmethod
    def from_json(cls, value: dict[str, Any] | None) -> ObjectionLedger:
        if not value:
            return cls()
        return cls(list(value.get("entries", [])), int(value.get("next_number", 1)))

    def to_json(self) -> dict[str, Any]:
        return {"next_number": self.next_number, "entries": self.entries}

    def _allocate(self) -> str:
        identifier = f"O{self.next_number}"
        self.next_number += 1
        return identifier

    def add_blockers(self, blockers: list[dict[str, Any]], round_number: int) -> list[str]:
        identifiers: list[str] = []
        for blocker in blockers:
            identifier = self._allocate()
            self.entries.append(
                {
                    "id": identifier,
                    "source_id": blocker.get("id"),
                    "round_opened": round_number,
                    "target": blocker.get("target", ""),
                    "issue": blocker.get("issue", ""),
                    "why_it_matters": blocker.get("why_it_matters", ""),
                    "required_change": blocker.get("required_change", ""),
                    "status": "open",
                    "ruling_reason": None,
                    "history": [],
                }
            )
            identifiers.append(identifier)
        return identifiers

    def get(self, identifier: str) -> dict[str, Any]:
        for entry in self.entries:
            if entry["id"] == identifier:
                return entry
        raise ProtocolStateError(f"unknown objection id: {identifier}")

    def apply_rulings(self, rulings: list[dict[str, Any]]) -> None:
        for ruling in rulings:
            identifier = str(ruling.get("id", ""))
            status = str(ruling.get("status", ""))
            reason = str(ruling.get("reason", "")).strip()
            if status not in VALID_STATES:
                raise ProtocolStateError(f"invalid ledger status: {status}")
            if status == "rebutted" and not reason:
                raise ProtocolStateError("a rebuttal requires a reason")
            entry = self.get(identifier)
            entry["history"].append({"from": entry["status"], "to": status, "reason": reason})
            entry["status"] = status
            entry["ruling_reason"] = reason

    def split(self, identifier: str, parts: list[dict[str, Any]]) -> list[str]:
        parent = self.get(identifier)
        parent["status"] = "superseded"
        new_ids = self.add_blockers(parts, int(parent["round_opened"]))
        parent["history"].append({"event": "split", "children": new_ids})
        for child_id in new_ids:
            self.get(child_id)["split_from"] = identifier
        return new_ids

    def merge(self, identifiers: list[str], merged: dict[str, Any], round_number: int) -> str:
        for identifier in identifiers:
            self.get(identifier)["status"] = "superseded"
        merged_id = self.add_blockers([merged], round_number)[0]
        self.get(merged_id)["merged_from"] = identifiers
        return merged_id

    def open_entries(self) -> list[dict[str, Any]]:
        return [entry for entry in self.entries if entry["status"] == "open"]
