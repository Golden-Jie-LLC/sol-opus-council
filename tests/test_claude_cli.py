from __future__ import annotations

import json
import os
import subprocess
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
    SchemaCompatibilityError,
)
from sol_opus_council.schema_validation import load_schema, validate_schema
from sol_opus_council.util import canonical_json, sha256_text
from tests.helpers import initial, prompt_review, question_review


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

    def test_all_provider_schemas_are_normalized_without_losing_constraints(self) -> None:
        cases = (
            ("initial", initial()),
            ("question-review", question_review(1, ready=True)),
            ("prompt-review", prompt_review(1, ready=True)),
        )
        for number, (schema_name, structured_output) in enumerate(cases, start=1):
            self.response(number, self.normal(structured_output=structured_output))
            result = self.adapter().invoke(
                "prompt", schema_name, session_id=self.session_id if number > 1 else None
            )
            runtime = json.loads(
                (result.call_directory / "runtime-schema.json").read_text(encoding="utf-8")
            )
            expected = load_schema(schema_name)
            expected.pop("$schema")
            expected.pop("$id")
            self.assertEqual(runtime, expected)
            self.assertNotIn("$schema", runtime)
            self.assertNotIn("$id", runtime)

    def test_schema_artifacts_distinguish_canonical_identity_from_runtime_payload(self) -> None:
        self.response(1, self.normal())
        result = self.adapter().invoke("prompt", "initial")
        call = result.call_directory
        canonical_text = (call / "canonical-schema.json").read_text(encoding="utf-8")
        runtime_text = (call / "runtime-schema.json").read_text(encoding="utf-8").rstrip("\n")
        audit = json.loads((call / "schema-audit.json").read_text(encoding="utf-8"))
        argv = json.loads((call / "argv.json").read_text(encoding="utf-8"))
        wire_schema = argv[argv.index("--json-schema") + 1]

        self.assertEqual(json.loads(canonical_text)["$schema"], audit["canonical_schema_dialect"])
        self.assertEqual(json.loads(canonical_text)["$id"], audit["canonical_schema_id"])
        self.assertEqual(audit["removed_top_level_metadata"], ["$schema", "$id"])
        self.assertEqual(wire_schema, runtime_text)
        self.assertEqual(sha256_text(canonical_text), audit["canonical_schema_sha256"])
        self.assertEqual(sha256_text(runtime_text), audit["runtime_schema_sha256"])
        self.assertEqual(
            (call / "canonical-schema.sha256").read_text(encoding="utf-8").strip(),
            audit["canonical_schema_sha256"],
        )
        self.assertEqual(
            (call / "runtime-schema.sha256").read_text(encoding="utf-8").strip(),
            audit["runtime_schema_sha256"],
        )
        self.assertEqual(canonical_text, canonical_json(load_schema("initial")))

    def test_host_validation_receives_the_original_canonical_schema(self) -> None:
        self.response(1, self.normal())
        with patch(
            "sol_opus_council.claude_cli.validate_schema", wraps=validate_schema
        ) as validator:
            self.adapter().invoke("prompt", "initial")
        schema_argument = validator.call_args.args[1]
        self.assertIn("$schema", schema_argument)
        self.assertIn("$id", schema_argument)

    def test_claude_2_1_247_regression_fixture_rejects_canonical_and_accepts_runtime(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "claude-code-2.1.247-schema-rejection.json"
        raw_root = self.root / "raw-rejection"
        raw_env = dict(os.environ)
        raw_env["FAKE_CLAUDE_ROOT"] = str(raw_root)
        raw_env["FAKE_CLAUDE_SCHEMA_COMPAT_FIXTURE"] = str(fixture)
        canonical = load_schema("initial")
        rejected = subprocess.run(
            [*self.command, "--json-schema", json.dumps(canonical)],
            input="prompt",
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=raw_env,
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("no schema with key or ref", rejected.stderr)

        os.environ["FAKE_CLAUDE_SCHEMA_COMPAT_FIXTURE"] = str(fixture)
        self.response(1, self.normal())
        result = self.adapter().invoke("prompt", "initial")
        runtime = json.loads(
            (result.call_directory / "runtime-schema.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("$schema", runtime)

    def test_unsupported_schema_fails_before_child_process(self) -> None:
        unsupported = load_schema("initial")
        unsupported["unevaluatedProperties"] = False
        with (
            patch("sol_opus_council.claude_cli.load_schema", return_value=unsupported),
            self.assertRaises(SchemaCompatibilityError),
        ):
            self.adapter().invoke("prompt", "initial")
        self.assertFalse((self.fake_root / "count.txt").exists())


if __name__ == "__main__":
    unittest.main()
