from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sol_opus_council.installer import install, uninstall


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "target"
        self.repo.mkdir()
        self.source = Path(__file__).resolve().parents[1]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_repo_install_places_exactly_two_skills(self) -> None:
        result = install("repo", self.repo, self.source)
        skills = Path(result["skills_root"])
        self.assertTrue((skills / "question" / "SKILL.md").is_file())
        self.assertTrue((skills / "prompt" / "SKILL.md").is_file())
        self.assertEqual(result["skills"], ["question", "prompt"])

    def test_user_install_uses_codex_home_skill_root(self) -> None:
        codex_home = self.root / "codex-home"
        with patch.dict("os.environ", {"CODEX_HOME": str(codex_home)}):
            result = install("user", source_root=self.source)
            self.assertEqual(Path(result["skills_root"]), (codex_home / "skills").resolve())
            self.assertTrue((codex_home / "skills" / "question" / "SKILL.md").is_file())
            uninstall("user")

    def test_install_includes_shared_runtime(self) -> None:
        result = install("repo", self.repo, self.source)
        support = Path(result["skills_root"]) / "_sol-opus-council"
        self.assertTrue((support / "council.py").is_file())
        self.assertTrue((support / "schemas" / "initial.schema.json").is_file())
        self.assertFalse(any(path.name == "__pycache__" for path in support.rglob("*")))
        self.assertFalse(any(path.suffix == ".pyc" for path in support.rglob("*")))

    def test_install_is_idempotent(self) -> None:
        first = install("repo", self.repo, self.source)
        second = install("repo", self.repo, self.source)
        self.assertEqual(first["skills_root"], second["skills_root"])

    def test_uninstall_is_idempotent(self) -> None:
        install("repo", self.repo, self.source)
        first = uninstall("repo", self.repo)
        second = uninstall("repo", self.repo)
        self.assertFalse(first["already_absent"])
        self.assertTrue(second["already_absent"])

    def test_uninstall_removes_owned_skills(self) -> None:
        result = install("repo", self.repo, self.source)
        root = Path(result["skills_root"])
        uninstall("repo", self.repo)
        self.assertFalse((root / "question").exists())
        self.assertFalse((root / "prompt").exists())

    def test_metadata_is_explicit_only_with_expected_display_names(self) -> None:
        result = install("repo", self.repo, self.source)
        root = Path(result["skills_root"])
        question = (root / "question" / "agents" / "openai.yaml").read_text(encoding="utf-8")
        prompt = (root / "prompt" / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "QUESTION"', question)
        self.assertIn('display_name: "PROMPT"', prompt)
        self.assertIn("allow_implicit_invocation: false", question)
        self.assertIn("allow_implicit_invocation: false", prompt)

    def test_skills_require_narrow_claude_session_persistence(self) -> None:
        result = install("repo", self.repo, self.source)
        root = Path(result["skills_root"])
        for name in ("question", "prompt"):
            skill = (root / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("~/.claude/projects", skill)
            self.assertIn("never use `--continue`", skill)


if __name__ == "__main__":
    unittest.main()
