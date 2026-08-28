"""Idempotent repository- and user-scoped skill installation."""

from __future__ import annotations

import json
import os
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Any

from .errors import CouncilError
from .util import atomic_write_json

SUPPORT_NAME = "_sol-opus-council"
SKILL_NAMES = ("question", "prompt")
COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.py[cod]", ".pytest_cache", ".ruff_cache")


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def skills_root(scope: str, repo: Path | None = None) -> Path:
    if scope == "user":
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
        return codex_home.resolve() / "skills"
    if scope == "repo":
        if repo is None:
            raise CouncilError("--repo is required for repo-scoped installation")
        return repo.resolve() / ".agents" / "skills"
    raise CouncilError(f"unsupported install scope: {scope}")


def install(
    scope: str, repo: Path | None = None, source_root: Path | None = None
) -> dict[str, Any]:
    source = (source_root or repository_root()).resolve()
    target = skills_root(scope, repo)
    target.mkdir(parents=True, exist_ok=True)
    installed_files: list[str] = []
    for name in SKILL_NAMES:
        source_skill = source / "skills" / name
        if not (source_skill / "SKILL.md").is_file():
            raise CouncilError(f"missing source skill: {source_skill}")
        destination = target / name
        shutil.copytree(source_skill, destination, dirs_exist_ok=True, ignore=COPY_IGNORE)
        installed_files.extend(
            str(path.relative_to(target)).replace("\\", "/")
            for path in destination.rglob("*")
            if path.is_file()
        )
    support = target / SUPPORT_NAME
    package_target = support / "sol_opus_council"
    shutil.copytree(
        source / "src" / "sol_opus_council",
        package_target,
        dirs_exist_ok=True,
        ignore=COPY_IGNORE,
    )
    shutil.copytree(source / "schemas", support / "schemas", dirs_exist_ok=True, ignore=COPY_IGNORE)
    shutil.copy2(source / "scripts" / "council.py", support / "council.py")
    installed_files.extend(
        str(path.relative_to(target)).replace("\\", "/")
        for path in support.rglob("*")
        if path.is_file() and path.name != "install-manifest.json"
    )
    manifest = {
        "schema_version": 1,
        "product": "sol-opus-council",
        "scope": scope,
        "skills": list(SKILL_NAMES),
        "files": sorted(set(installed_files)),
    }
    atomic_write_json(support / "install-manifest.json", manifest)
    return {"ok": True, "scope": scope, "skills_root": str(target), "skills": list(SKILL_NAMES)}


def uninstall(scope: str, repo: Path | None = None) -> dict[str, Any]:
    target = skills_root(scope, repo)
    manifest_path = target / SUPPORT_NAME / "install-manifest.json"
    if not manifest_path.is_file():
        return {"ok": True, "already_absent": True, "skills_root": str(target)}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in sorted(manifest.get("files", []), reverse=True):
        path = (target / relative).resolve()
        if target.resolve() not in path.parents:
            raise CouncilError(f"unsafe install manifest path: {relative}")
        path.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)
    for directory in sorted(
        [target / name for name in (*SKILL_NAMES, SUPPORT_NAME)],
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        for nested in sorted(
            [path for path in directory.rglob("*") if path.is_dir()],
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            with suppress(OSError):
                nested.rmdir()
        with suppress(OSError):
            directory.rmdir()
    return {"ok": True, "already_absent": False, "skills_root": str(target)}
