from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkillProviderAuthorizationTests(unittest.TestCase):
    def _skill_text(self, name: str) -> str:
        return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    def test_explicit_council_invocation_is_provider_authorization(self) -> None:
        for name in ("question", "prompt"):
            text = self._skill_text(name)
            self.assertIn("is itself the user's authorization", text)
            self.assertIn("Do not ask for a second provider-consent", text)
            self.assertIn("minimum task-relevant context", text)

    def test_default_authorization_gate_is_satisfied_without_double_consent(self) -> None:
        for name in ("question", "prompt"):
            text = self._skill_text(name)
            self.assertIn("requires explicit user authorization is satisfied", text)
            self.assertIn("do not ask\nthe user again", text)

    def test_stricter_repository_prohibitions_still_win(self) -> None:
        for name in ("question", "prompt"):
            text = self._skill_text(name)
            self.assertIn("does not override a stricter governing instruction", text)
            self.assertIn("even with user authorization", text)
            self.assertIn("non-exportable", text)

    def test_sensitive_data_is_not_implicitly_authorized(self) -> None:
        for name in ("question", "prompt"):
            text = self._skill_text(name)
            self.assertIn("secrets, API keys, credentials, `.env`", text)
            self.assertIn("personal financial account or holdings data", text)
            self.assertIn("bulk raw private\ndatabase contents", text)
            self.assertIn("unrelated private material", text)
            self.assertIn("explicit separate handling", text)


if __name__ == "__main__":
    unittest.main()
