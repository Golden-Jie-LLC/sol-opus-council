from __future__ import annotations

import unittest

from sol_opus_council.errors import ProtocolStateError, SchemaValidationError
from sol_opus_council.ledger import ObjectionLedger
from sol_opus_council.schema_validation import load_schema, validate_named
from tests.helpers import blocker, initial, prompt_review, question_review


class LedgerSchemaTests(unittest.TestCase):
    def test_ids_are_never_reused(self) -> None:
        ledger = ObjectionLedger()
        first = ledger.add_blockers([blocker()], 1)[0]
        ledger.apply_rulings([{"id": first, "status": "resolved", "reason": "fixed"}])
        second = ledger.add_blockers([blocker("source-2")], 2)[0]
        self.assertEqual((first, second), ("O1", "O2"))

    def test_rebuttal_requires_reason(self) -> None:
        ledger = ObjectionLedger()
        identifier = ledger.add_blockers([blocker()], 1)[0]
        with self.assertRaises(ProtocolStateError):
            ledger.apply_rulings([{"id": identifier, "status": "rebutted", "reason": ""}])

    def test_split_records_parent_and_children(self) -> None:
        ledger = ObjectionLedger()
        parent = ledger.add_blockers([blocker()], 1)[0]
        children = ledger.split(parent, [blocker("a"), blocker("b")])
        self.assertEqual(children, ["O2", "O3"])
        self.assertEqual(ledger.get(parent)["status"], "superseded")

    def test_merge_records_sources(self) -> None:
        ledger = ObjectionLedger()
        ids = ledger.add_blockers([blocker("a"), blocker("b")], 1)
        merged = ledger.merge(ids, blocker("m"), 2)
        self.assertEqual(ledger.get(merged)["merged_from"], ids)

    def test_initial_schema_accepts_contract(self) -> None:
        validate_named(initial(), "initial")

    def test_question_schema_follows_local_ref(self) -> None:
        validate_named(question_review(1, ready=False), "question-review")

    def test_prompt_schema_accepts_ready_contract(self) -> None:
        validate_named(prompt_review(1, ready=True), "prompt-review")

    def test_schema_rejects_missing_required_field(self) -> None:
        value = initial()
        del value["confidence"]
        with self.assertRaises(SchemaValidationError):
            validate_named(value, "initial")

    def test_schema_rejects_extra_field(self) -> None:
        value = initial()
        value["hidden_chain_of_thought"] = "forbidden"
        with self.assertRaises(SchemaValidationError):
            validate_named(value, "initial")

    def test_all_schema_files_load(self) -> None:
        for name in ("initial", "question-review", "prompt-review", "manifest"):
            self.assertIsInstance(load_schema(name), dict)


if __name__ == "__main__":
    unittest.main()
