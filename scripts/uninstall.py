#!/usr/bin/env python3
"""Uninstall QUESTION and PROMPT skills."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sol_opus_council.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["uninstall", *sys.argv[1:]]))
