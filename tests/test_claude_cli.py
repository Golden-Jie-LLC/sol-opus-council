from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sol_opus_council.claude_cli import READ_ONLY_TOOLS, ClaudeCLIAdapter
from sol_opus_council.errors import (
    AuthenticationError,
    MalformedOutputError,
    OpusUnavailableError,
    ProcessError,
    ProcessTimeoutError,
)
from tests.helpers import initial


class ClaudeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fake_root = self.root / "fake"
        (self.fake_root / "responses").mkdir(parents=True)
        self.command = (sys.executable, str(Path(__file__).with_name("fake_claude.py")))
        self.session_id = str(uuid4())
        self.env = patch.dict(
            os.environ,
            {"FAKE_CLAUDE_ROOT": str(self.fake_root), "FAKE_CLAUDE_AUTH": "1"},
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def response(self, number: int, value: dict) -> None:
        (self.fake_root / "responses" / f"{number:02d}.json").write_text(
            json.dumps(value), encoding="utf-8"
        )

    def normal(self, **overrides: object) -> dict:
        value = {
            "session_id": self.session_id,
            "model": "claude-opus-5",
            "structured_output": initial(),
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        value.update(overrides)
        return value

    def adapter(self, **kwargs: object) -> ClaudeCLIAdapter:
        return ClaudeCLIAdapter(self.command, self.root / "artifacts", **kwargs)

    def test_preflight_detects_version_and_auth(self) -> None:
        features = self.adapter().preflight()
        self.assertIn("2.1.247", features.version)
        self.assertTrue(features.authenticated)

    def test_authentication_failure_is_explicit(self) -> None:
        os.environ["FAKE_CLAUDE_AUTH"] = "0"
        with self.assertRaises(AuthenticationError):
            self.adapter().preflight()

    def test_invocation_is_opus_only_and_read_only(self) -> None:
        self.response(1, self.normal())
        self.adapter().invoke("prompt", "initial")
        argv = json.loads((self.fake_root / "call-01" / "argv.json").read_text())
        joined = " ".join(argv)
        self.assertIn("--model opus", joined)
        self.assertIn("--effort high", joined)
        self.assertIn("--safe-mode", argv)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--tools") + 1], ",".join(READ_ONLY_TOOLS))
        self.assertNotIn("Write", joined)
        self.assertNotIn("Edit", joined)
        self.assertNotIn("Bash", joined)
        self.assertNotIn("--fallback-model", argv)

    def test_resume_uses_explicit_session_id_not_continue(self) -> None:
        self.response(1, self.normal())
        self.adapter().invoke("review", "initial", session_id=self.session_id)
        argv = json.loads((self.fake_root / "call-01" / "argv.json").read_text())
        self.assertEqual(argv[argv.index("--resume") + 1], self.session_id)
        self.assertNotIn("--continue", argv)

    def test_each_attempt_has_unique_output_directory(self) -> None:
        self.response(1, {"__stdout_raw": "not-json"})
        self.response(2, self.normal())
        result = self.adapter().invoke("prompt", "initial")
        calls = list((self.root / "artifacts" / "calls").iterdir())
        self.assertEqual(len(calls), 2)
        self.assertTrue((result.call_directory / "parsed.json").is_file())

    def test_malformed_json_gets_one_corrective_retry(self) -> None:
        self.response(1, {"__stdout_raw": "bad"})
        self.response(2, self.normal())
        self.adapter().invoke("prompt", "initial")
        prompt = (self.fake_root / "call-02" / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("CORRECTIVE RETRY", prompt)

    def test_two_malformed_outputs_fail(self) -> None:
        self.response(1, {"__stdout_raw": "bad"})
        self.response(2, {"__stdout_raw": "also bad"})
        with self.assertRaises(MalformedOutputError):
            self.adapter().invoke("prompt", "initial")

    def test_transient_failure_retries_without_becoming_disagreement(self) -> None:
        self.response(1, {"__stderr": "overloaded", "__return_code": 1})
        self.response(2, self.normal())
        result = self.adapter(transient_retries=1).invoke("prompt", "initial")
        self.assertEqual(result.structured_output["context_status"], "SUFFICIENT")

    def test_non_transient_failure_is_explicit(self) -> None:
        self.response(1, {"__stderr": "fatal", "__return_code": 2})
        with self.assertRaises(ProcessError):
            self.adapter().invoke("prompt", "initial")

    def test_opus_unavailable_never_falls_back(self) -> None:
        self.response(1, {"__stderr": "Opus unavailable", "__return_code": 1})
        with self.assertRaises(OpusUnavailableError):
            self.adapter().invoke("prompt", "initial")

    def test_resolved_non_opus_model_is_rejected(self) -> None:
        self.response(1, self.normal(model="claude-sonnet-5"))
        with self.assertRaises(OpusUnavailableError):
            self.adapter().invoke("prompt", "initial")

    def test_timeout_kills_process_and_records_failure(self) -> None:
        self.response(1, {"__sleep": 1, **self.normal()})
        with self.assertRaises(ProcessTimeoutError):
            self.adapter(timeout_seconds=0.05).invoke("prompt", "initial")

    def test_structured_schema_failure_is_corrected(self) -> None:
        invalid = self.normal(structured_output={"context_status": "SUFFICIENT"})
        self.response(1, invalid)
        self.response(2, self.normal())
        self.adapter().invoke("prompt", "initial")
        self.assertTrue((self.fake_root / "call-02").is_dir())

    def test_usage_metadata_is_preserved(self) -> None:
        self.response(1, self.normal(total_cost_usd=0.01))
        result = self.adapter().invoke("prompt", "initial")
        self.assertEqual(result.usage["total_cost_usd"], 0.01)


if __name__ == "__main__":
    unittest.main()
