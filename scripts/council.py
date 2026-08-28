#!/usr/bin/env python3
"""Bootstrap the council CLI from a checkout or installed skill runtime."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for candidate in (HERE.parent / "src", HERE):
    if (candidate / "sol_opus_council").is_dir():
        sys.path.insert(0, str(candidate))
        break

from sol_opus_council.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
