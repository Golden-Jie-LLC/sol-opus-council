# Repository guidance

This repository ships exactly two explicit Codex skills and one shared Python
runtime. Preserve the product boundary: Codex is the only UI; Claude Code is a
headless, read-only Opus peer; PROMPT never executes its output.

Before committing, run:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
ruff check .
ruff format --check .
```

Keep process arguments as lists, paths as `pathlib.Path`, writes atomic and
UTF-8, retries/rounds/context repair bounded, and errors typed. Never log
credentials, enable a non-Opus fallback, use `--continue`, or give Claude Bash,
write tools, mutation-capable MCP, browser mutation, or repository write
access. Normal CI must use the fake Claude executable and make no live calls.
