"""Deterministic Claude executable used by adapter integration tests."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HELP = """Usage: claude [options]
--print --model --effort --output-format --json-schema --resume --tools
--safe-mode --strict-mcp-config --mcp-config --no-chrome --permission-mode
"""


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        print("2.1.247 (Claude Code fake)")
        return 0
    if args == ["--help"]:
        print(HELP)
        return 0
    if args == ["auth", "status"]:
        logged_in = os.environ.get("FAKE_CLAUDE_AUTH", "1") == "1"
        print(json.dumps({"loggedIn": logged_in, "authMethod": "subscription"}))
        return 0
    root = Path(os.environ["FAKE_CLAUDE_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    state = root / "count.txt"
    count = int(state.read_text(encoding="utf-8")) + 1 if state.exists() else 1
    state.write_text(str(count), encoding="utf-8")
    call = root / f"call-{count:02d}"
    call.mkdir()
    (call / "argv.json").write_text(json.dumps(args), encoding="utf-8")
    (call / "prompt.txt").write_text(sys.stdin.read(), encoding="utf-8")
    compatibility_fixture = os.environ.get("FAKE_CLAUDE_SCHEMA_COMPAT_FIXTURE")
    if compatibility_fixture:
        fixture = json.loads(Path(compatibility_fixture).read_text(encoding="utf-8"))
        schema = json.loads(args[args.index("--json-schema") + 1])
        rejected = fixture.get("reject_top_level_keywords", [])
        if any(keyword in schema for keyword in rejected):
            print(fixture["stderr"], file=sys.stderr)
            return int(fixture.get("return_code", 1))
    response_path = root / "responses" / f"{count:02d}.json"
    response = json.loads(response_path.read_text(encoding="utf-8"))
    if response.get("__sleep"):
        time.sleep(float(response["__sleep"]))
    if response.get("__stderr"):
        print(response["__stderr"], file=sys.stderr)
    if "__stdout_raw" in response:
        sys.stdout.write(str(response["__stdout_raw"]))
    else:
        sys.stdout.write(json.dumps(response, ensure_ascii=False))
    return int(response.get("__return_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
