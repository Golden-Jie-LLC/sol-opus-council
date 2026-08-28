# Contributing

Use Python 3.11 or newer. From the repository root:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
ruff check .
ruff format --check .
```

The test suite must remain deterministic and must not require a real Claude or
Codex login. Use `tests/fake_claude.py` for process, retry, session, schema, and
permission behavior. A real Opus smoke is optional, local-only, and allowed only
after deterministic parser/schema/read-only/fail-closed tests pass.

When changing a skill, verify both repo- and user-scope installation behavior,
`agents/openai.yaml`, explicit-only invocation, and the `/skills` discovery
path. Do not add deprecated custom prompts as a core entrypoint.

Never enable Claude write tools, Bash, browser mutation, arbitrary MCP tools,
fallback models, `--continue`, or business-repository artifact writes. Keep the
MIT License and upstream attribution.
