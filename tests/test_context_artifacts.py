from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sol_opus_council.context_packet import ContextPacket
from sol_opus_council.errors import ContextRepairLimitError, ProtocolStateError
from sol_opus_council.protocol import CouncilCoordinator, CouncilMode
from sol_opus_council.util import sha256_text


class ContextArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def coordinator(self) -> CouncilCoordinator:
        return CouncilCoordinator.begin(
            mode=CouncilMode.QUESTION,
            request="逐字请求\nsecond line",
            runs_root=self.root / "runs",
            context={"language": "zh-CN", "hard_constraints": ["只读"]},
        )

    def test_request_is_preserved_verbatim(self) -> None:
        coordinator = self.coordinator()
        text = coordinator.artifacts.context_text()
        self.assertIn("逐字请求\\nsecond line", text)

    def test_context_hash_matches_rendered_packet(self) -> None:
        coordinator = self.coordinator()
        state = coordinator.artifacts.state()
        self.assertEqual(state["context_hash"], sha256_text(coordinator.artifacts.context_text()))

    def test_context_packet_is_deterministic(self) -> None:
        first = ContextPacket.build(mode="QUESTION", run_id="x", user_request="same")
        second = ContextPacket.build(mode="QUESTION", run_id="x", user_request="same")
        self.assertEqual(first.render(), second.render())
        self.assertEqual(first.sha256, second.sha256)

    def test_context_packet_records_explicit_provider_authorization(self) -> None:
        packet = ContextPacket.build(mode="QUESTION", run_id="x", user_request="same")
        authorization = packet.payload["provider_authorization"]
        self.assertEqual(authorization["basis"], "explicit_council_invocation")
        self.assertIn("Anthropic Claude Opus", authorization["provider"])
        self.assertEqual(authorization["scope"], "minimum task-relevant context")
        self.assertFalse(authorization["additional_provider_confirmation_required"])
        self.assertTrue(authorization["stricter_governing_prohibitions_still_apply"])

    def test_context_packet_records_restricted_sensitive_data_boundary(self) -> None:
        packet = ContextPacket.build(mode="PROMPT", run_id="x", user_request="same")
        boundary = packet.payload["provider_data_boundary"]
        excluded = set(boundary["exclude_by_default"])
        self.assertIn("secrets_api_keys_credentials_env", excluded)
        self.assertIn("personal_financial_account_or_holdings_data", excluded)
        self.assertIn("bulk_raw_private_database_contents", excluded)
        self.assertIn("unrelated_private_material", excluded)
        self.assertTrue(boundary["restricted_sensitive_material_requires_separate_handling"])

    def test_context_repair_increments_version(self) -> None:
        coordinator = self.coordinator()
        old_hash = coordinator.artifacts.state()["context_hash"]
        new_hash = coordinator.revise_context(request="changed", context={"known_facts": ["x"]})
        state = coordinator.artifacts.state()
        self.assertEqual(state["context_version"], 2)
        self.assertNotEqual(old_hash, new_hash)

    def test_context_repair_invalidates_positions_and_signoffs(self) -> None:
        coordinator = self.coordinator()
        coordinator.lock_sol_initial("independent")
        state = coordinator.artifacts.state()
        state["sol_signoff"] = {"candidate_hash": "old"}
        coordinator.artifacts.save_state(state)
        coordinator.revise_context(request="changed", context={})
        state = coordinator.artifacts.state()
        self.assertEqual(state["phase"], "context_frozen")
        self.assertIsNone(state["sol_signoff"])
        self.assertIsNone(state["session_id"])

    def test_context_repairs_are_bounded_to_two(self) -> None:
        coordinator = self.coordinator()
        coordinator.revise_context(request="v2", context={})
        coordinator.revise_context(request="v3", context={})
        with self.assertRaises(ContextRepairLimitError):
            coordinator.revise_context(request="v4", context={})

    def test_sol_initial_must_be_nonempty(self) -> None:
        with self.assertRaises(ProtocolStateError):
            self.coordinator().lock_sol_initial("  ")

    def test_sol_initial_is_hashed_on_disk(self) -> None:
        coordinator = self.coordinator()
        digest = coordinator.lock_sol_initial("locked position")
        self.assertEqual(digest, sha256_text("locked position"))
        self.assertTrue((coordinator.artifacts.root / "sol-initial.md.sha256").is_file())

    def test_artifacts_live_beneath_runs_root(self) -> None:
        coordinator = self.coordinator()
        self.assertIn(self.root / "runs", coordinator.artifacts.root.parents)

    def test_candidate_change_invalidates_signoffs(self) -> None:
        coordinator = CouncilCoordinator.begin(
            mode=CouncilMode.PROMPT,
            request="build it",
            runs_root=self.root / "runs",
        )
        state = coordinator.artifacts.state()
        state["phase"] = "complete"
        state["sol_signoff"] = {"candidate_hash": "old"}
        state["opus_signoff"] = {"candidate_hash": "old"}
        coordinator.artifacts.save_state(state)
        coordinator.invalidate_after_candidate_change("# Objective\n\nNew material")
        state = coordinator.artifacts.state()
        self.assertIsNone(state["sol_signoff"])
        self.assertIsNone(state["opus_signoff"])
        self.assertEqual(state["phase"], "reviewing")


if __name__ == "__main__":
    unittest.main()
