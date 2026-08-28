from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sol_opus_council.errors import CandidateValidationError, ProtocolStateError
from sol_opus_council.protocol import CouncilCoordinator, CouncilMode, ScriptedAdapter
from tests.helpers import initial, prompt_review, question_review


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.session_id = str(uuid4())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def setup_run(
        self, mode: CouncilMode, review_outputs: list[dict]
    ) -> tuple[CouncilCoordinator, ScriptedAdapter]:
        coordinator = CouncilCoordinator.begin(
            mode=mode,
            request="user request",
            runs_root=self.root / "runs",
            context={"hard_constraints": ["preserve intent"]},
        )
        coordinator.lock_sol_initial("SOL_SENTINEL independent position")
        adapter = ScriptedAdapter(
            [initial(), *review_outputs], self.root / "scripted", self.session_id
        )
        coordinator.opus_initial(adapter)
        return coordinator, adapter

    def resolve_all(self, coordinator: CouncilCoordinator) -> list[dict]:
        path = coordinator.artifacts.root / "ledger.json"
        if not path.is_file():
            return []
        ledger = json.loads(path.read_text(encoding="utf-8"))
        return [
            {"id": entry["id"], "status": "resolved", "reason": "candidate fixed"}
            for entry in ledger["entries"]
            if entry["status"] == "open"
        ]

    def test_blind_initial_prompt_excludes_sol_content_and_hash(self) -> None:
        coordinator, adapter = self.setup_run(CouncilMode.QUESTION, [])
        prompt = adapter.calls[0]["prompt"]
        state = coordinator.artifacts.state()
        self.assertNotIn("SOL_SENTINEL", prompt)
        self.assertNotIn(state["sol_initial_hash"], prompt)

    def test_blind_initial_does_not_count_as_review_round(self) -> None:
        coordinator, _ = self.setup_run(CouncilMode.QUESTION, [])
        self.assertEqual(coordinator.artifacts.state()["review_round"], 0)

    def test_missing_context_enters_bounded_repair_phase(self) -> None:
        coordinator = CouncilCoordinator.begin(
            mode=CouncilMode.QUESTION,
            request="request",
            runs_root=self.root / "runs",
        )
        coordinator.lock_sol_initial("initial")
        adapter = ScriptedAdapter(
            [initial(status="MISSING_CONTEXT")], self.root / "s", self.session_id
        )
        coordinator.opus_initial(adapter)
        self.assertEqual(coordinator.artifacts.state()["phase"], "missing_context")
        self.assertEqual(coordinator.artifacts.state()["review_round"], 0)

    def test_question_round_one_agreement_stops(self) -> None:
        coordinator, adapter = self.setup_run(
            CouncilMode.QUESTION, [question_review(1, ready=True)]
        )
        result = coordinator.review(candidate="Direct answer", sol_ready=True, adapter=adapter)
        self.assertTrue(result["ready"])
        self.assertEqual(result["round"], 1)
        self.assertEqual(coordinator.artifacts.state()["final_status"], "AGREEMENT")

    def test_question_round_one_agreement_requires_sol_ready(self) -> None:
        coordinator, adapter = self.setup_run(
            CouncilMode.QUESTION, [question_review(1, ready=True)]
        )
        result = coordinator.review(candidate="Direct answer", sol_ready=False, adapter=adapter)
        self.assertFalse(result["ready"])
        self.assertEqual(coordinator.artifacts.state()["phase"], "reviewing")

    def test_question_round_two_agreement_skips_round_three(self) -> None:
        coordinator, adapter = self.setup_run(
            CouncilMode.QUESTION,
            [question_review(1, ready=False), question_review(2, ready=True)],
        )
        coordinator.review(candidate="Answer v1", sol_ready=False, adapter=adapter)
        result = coordinator.review(
            candidate="Answer v2",
            sol_ready=True,
            adapter=adapter,
            rulings=self.resolve_all(coordinator),
        )
        self.assertTrue(result["ready"])
        self.assertEqual(coordinator.artifacts.state()["review_round"], 2)
        self.assertEqual(len(adapter.calls), 3)  # initial + two reviews

    def test_question_cap_is_three(self) -> None:
        coordinator, adapter = self.setup_run(
            CouncilMode.QUESTION,
            [question_review(i, ready=False) for i in range(1, 4)],
        )
        for round_number in range(1, 4):
            coordinator.review(
                candidate=f"Answer v{round_number}", sol_ready=False, adapter=adapter
            )
        state = coordinator.artifacts.state()
        self.assertEqual(state["review_round"], 3)
        self.assertEqual(state["final_status"], "UNRESOLVED_AFTER_3_ROUNDS")
        final = (coordinator.artifacts.root / "final-answer.md").read_text(encoding="utf-8")
        self.assertIn("unresolved after 3 review rounds", final)

    def test_question_cannot_run_round_four(self) -> None:
        coordinator, adapter = self.setup_run(
            CouncilMode.QUESTION,
            [question_review(i, ready=False) for i in range(1, 4)],
        )
        for i in range(1, 4):
            coordinator.review(candidate=f"v{i}", sol_ready=False, adapter=adapter)
        with self.assertRaises(ProtocolStateError):
            coordinator.review(candidate="v4", sol_ready=False, adapter=adapter)

    def test_prompt_round_one_ready_stops(self) -> None:
        coordinator, adapter = self.setup_run(CouncilMode.PROMPT, [prompt_review(1, ready=True)])
        candidate = "# Objective\n\nImplement the requested behavior and verify it."
        result = coordinator.review(candidate=candidate, sol_ready=True, adapter=adapter)
        self.assertTrue(result["ready"])
        self.assertTrue((coordinator.artifacts.root / "FINAL_CODEX_PROMPT.md").is_file())

    def test_prompt_non_blocking_suggestion_allows_ready(self) -> None:
        review = prompt_review(1, ready=True, suggestions=["Prefer a different heading style"])
        coordinator, adapter = self.setup_run(CouncilMode.PROMPT, [review])
        result = coordinator.review(
            candidate="# Objective\n\nImplement correctly.", sol_ready=True, adapter=adapter
        )
        self.assertTrue(result["ready"])

    def test_prompt_different_implementation_preference_is_non_blocking(self) -> None:
        review = prompt_review(1, ready=True, suggestions=["Either strategy A or B is reasonable"])
        coordinator, adapter = self.setup_run(CouncilMode.PROMPT, [review])
        self.assertTrue(
            coordinator.review(
                candidate="# Objective\n\nUse any repository-consistent strategy.",
                sol_ready=True,
                adapter=adapter,
            )["ready"]
        )

    def test_prompt_open_blocker_prevents_final_prompt(self) -> None:
        coordinator, adapter = self.setup_run(CouncilMode.PROMPT, [prompt_review(1, ready=False)])
        result = coordinator.review(
            candidate="# Objective\n\nIncomplete requirement.", sol_ready=True, adapter=adapter
        )
        self.assertFalse(result["ready"])
        self.assertFalse((coordinator.artifacts.root / "FINAL_CODEX_PROMPT.md").exists())

    def test_prompt_can_be_ready_on_round_ten(self) -> None:
        outputs = [prompt_review(i, ready=i == 10) for i in range(1, 11)]
        coordinator, adapter = self.setup_run(CouncilMode.PROMPT, outputs)
        result = None
        for i in range(1, 11):
            result = coordinator.review(
                candidate=f"# Objective\n\nExecutable candidate version {i}.",
                sol_ready=i == 10,
                adapter=adapter,
                rulings=self.resolve_all(coordinator),
            )
        self.assertIsNotNone(result)
        self.assertTrue(result["ready"])
        self.assertEqual(coordinator.artifacts.state()["review_round"], 10)

    def test_prompt_cap_with_blocker_fails_closed(self) -> None:
        outputs = [prompt_review(i, ready=False) for i in range(1, 11)]
        coordinator, adapter = self.setup_run(CouncilMode.PROMPT, outputs)
        for i in range(1, 11):
            coordinator.review(
                candidate=f"# Objective\n\nDraft version {i}.",
                sol_ready=False,
                adapter=adapter,
            )
        state = coordinator.artifacts.state()
        self.assertEqual(state["final_status"], "NO_AGREEMENT_NOT_READY_FOR_CODEX_EXECUTION")
        self.assertFalse((coordinator.artifacts.root / "FINAL_CODEX_PROMPT.md").exists())
        failure = json.loads(
            (coordinator.artifacts.root / "no-agreement.json").read_text(encoding="utf-8")
        )
        self.assertIn("NO AGREEMENT", failure["status"])

    def test_prompt_signoffs_target_same_frozen_hash(self) -> None:
        coordinator, adapter = self.setup_run(CouncilMode.PROMPT, [prompt_review(1, ready=True)])
        result = coordinator.review(
            candidate="# Objective\n\nImplement and test.", sol_ready=True, adapter=adapter
        )
        state = coordinator.artifacts.state()
        self.assertEqual(state["sol_signoff"]["candidate_hash"], result["candidate_hash"])
        self.assertEqual(state["opus_signoff"]["candidate_hash"], result["candidate_hash"])
        saved_hash = (coordinator.artifacts.root / "FINAL_CODEX_PROMPT.sha256").read_text().strip()
        self.assertEqual(saved_hash, result["candidate_hash"])

    def test_prompt_placeholder_linter_fails_closed(self) -> None:
        coordinator, adapter = self.setup_run(CouncilMode.PROMPT, [prompt_review(1, ready=True)])
        with self.assertRaises(CandidateValidationError):
            coordinator.review(
                candidate="# Objective\n\nTODO: fill this", sol_ready=True, adapter=adapter
            )

    def test_review_resume_uses_initial_session(self) -> None:
        coordinator, adapter = self.setup_run(
            CouncilMode.QUESTION, [question_review(1, ready=True)]
        )
        coordinator.review(candidate="answer", sol_ready=True, adapter=adapter)
        self.assertEqual(adapter.calls[1]["session_id"], self.session_id)

    def test_artifacts_do_not_touch_business_repository(self) -> None:
        business = self.root / "business"
        business.mkdir()
        marker = business / "tracked.txt"
        marker.write_text("unchanged", encoding="utf-8")
        coordinator = CouncilCoordinator.begin(
            mode=CouncilMode.QUESTION,
            request="question",
            runs_root=self.root / "runs",
            repo_root=business,
        )
        coordinator.lock_sol_initial("position")
        self.assertEqual(marker.read_text(encoding="utf-8"), "unchanged")
        self.assertEqual(list(business.iterdir()), [marker])


if __name__ == "__main__":
    unittest.main()
