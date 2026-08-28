from __future__ import annotations

import unittest
from copy import deepcopy

from sol_opus_council.errors import SchemaCompatibilityError
from sol_opus_council.schema_compat import DRAFT_2020_12, normalize_schema_for_claude
from sol_opus_council.schema_validation import load_schema
from sol_opus_council.util import canonical_json, sha256_text

CANONICAL_SCHEMA_HASHES = {
    "initial": "27de2141b054ad79f028fd05de0a4f5d7335654c4b30c581ce5addbdfe61bb2a",
    "question-review": "95dff9bc0353ccd4467521ddd149d10d576fdc84c68454041c202d1aef574853",
    "prompt-review": "aaad214e6a90fd8e0e3d6a18dbe96d0cd7ff7b8cbbf3f6da9160e991d1e36437",
}


class SchemaCompatibilityTests(unittest.TestCase):
    def test_canonical_schemas_keep_draft_identity_and_stable_content(self) -> None:
        for name, expected_hash in CANONICAL_SCHEMA_HASHES.items():
            with self.subTest(schema=name):
                schema = load_schema(name)
                self.assertEqual(schema["$schema"], DRAFT_2020_12)
                self.assertTrue(schema["$id"])
                self.assertEqual(sha256_text(canonical_json(schema)), expected_hash)

    def test_runtime_copy_removes_only_root_identity_without_mutation(self) -> None:
        for name in CANONICAL_SCHEMA_HASHES:
            with self.subTest(schema=name):
                canonical = load_schema(name)
                before = deepcopy(canonical)
                expected = deepcopy(canonical)
                expected.pop("$schema")
                expected.pop("$id")

                runtime = normalize_schema_for_claude(canonical)

                self.assertEqual(canonical, before)
                self.assertEqual(runtime, expected)
                self.assertNotIn("$schema", runtime)
                self.assertNotIn("$id", runtime)

    def test_nested_structural_constraints_are_preserved(self) -> None:
        question = normalize_schema_for_claude(load_schema("question-review"))
        self.assertEqual(
            question["properties"]["blocking_objections"]["$ref"], "#/$defs/objections"
        )
        self.assertEqual(
            question["$defs"]["objections"]["items"]["required"],
            ["id", "target", "issue", "why_it_matters", "required_change"],
        )
        prompt = normalize_schema_for_claude(load_schema("prompt-review"))
        readiness = prompt["properties"]["execution_readiness"]
        self.assertFalse(readiness["additionalProperties"])
        self.assertIn("ready_for_codex_execution", readiness["required"])
        self.assertEqual(readiness["properties"]["ready_for_codex_execution"]["type"], "boolean")

    def test_unsupported_future_dialect_feature_fails_closed(self) -> None:
        for path in ("root", "nested"):
            with self.subTest(path=path):
                schema = load_schema("initial")
                if path == "root":
                    schema["unevaluatedProperties"] = False
                else:
                    schema["properties"]["position"]["prefixItems"] = []
                with self.assertRaisesRegex(SchemaCompatibilityError, "unsupported schema keyword"):
                    normalize_schema_for_claude(schema)

    def test_nested_schema_identity_is_not_silently_deleted(self) -> None:
        schema = load_schema("initial")
        schema["properties"]["position"]["$schema"] = DRAFT_2020_12
        with self.assertRaisesRegex(SchemaCompatibilityError, "unsupported schema keyword"):
            normalize_schema_for_claude(schema)

    def test_schema_features_not_enforced_by_host_validator_fail_closed(self) -> None:
        schema = load_schema("initial")
        schema["additionalProperties"] = {"type": "string"}
        with self.assertRaisesRegex(SchemaCompatibilityError, "additionalProperties"):
            normalize_schema_for_claude(schema)

        schema = load_schema("initial")
        schema["properties"]["position"] = {"$ref": "https://example.test/schema"}
        with self.assertRaisesRegex(SchemaCompatibilityError, "local JSON Pointer"):
            normalize_schema_for_claude(schema)


if __name__ == "__main__":
    unittest.main()
