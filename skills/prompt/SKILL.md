---
name: prompt
description: Run the explicit PROMPT council workflow to produce a frozen Codex execution prompt signed ready by GPT-5.6 Sol and read-only Claude Opus. Never invoke implicitly or execute the generated prompt.
---

# PROMPT

Turn the text following `$prompt` into a complete Codex execution prompt after
Sol–Opus execution-readiness review. This workflow only creates a prompt. It
must not execute that prompt or modify the user's business repository.

## Before the council

1. Resolve this skill directory and the sibling runtime launcher at
   `../_sol-opus-council/council.py`.
2. Confirm the current Codex session reports `gpt-5.6-sol` when model identity
   is exposed. If it reports another model, stop and request a switch; never
   substitute another OpenAI model. If identity cannot be read, record that
   limitation instead of guessing.
3. Run `council.py doctor`. Claude must be authenticated. Use the Claude Code
   subscription login only—never an Anthropic API key, MCP server, daemon, or
   non-Opus fallback.
4. Claude must be able to persist its local transcript so the explicit session
   UUID can be resumed. If the Codex sandbox blocks the configured Claude
   projects directory (normally `~/.claude/projects`), request narrowly scoped
   write permission for that directory before `opus-initial`. Do not broaden
   this to business-repository write access and never use `--continue` as a
   workaround.

## Freeze independent inputs

Outside the business repository, preserve the current request verbatim and
construct a minimal canonical context packet containing relevant history,
decisions, repository state, governing instructions, evidence and sources,
hard constraints, unknowns, language, and non-goals. Do not dump unrelated
conversation.

Run `council.py begin --mode PROMPT`. Before any Claude call, independently
write and lock a Sol initial position containing user-intent interpretation,
objectives, constraints, likely architecture, risks, tests, acceptance criteria,
and a proposed executable-prompt outline. Do not include hidden
chain-of-thought.

Only after `lock-sol` succeeds may `opus-initial` run. The runtime builds the
blind request from the same context hash and rejects Sol content or the Sol hash
in that prompt. If Opus returns `MISSING_CONTEXT`, use at most two material
context repairs; each repair invalidates both blind positions and requires a new
blind phase.

## Execution-readiness loop

Synthesize a self-contained prompt that preserves the user's intent and the
actual repository context. Include only relevant objectives, requirements,
constraints, scope/non-goals, files to inspect, failure modes, tests,
verification, acceptance criteria, deliverables, and any user-requested Git
delivery. Do not invent files or APIs, turn examples into hard-coded behavior,
or leave material `TODO`, `TBD`, `XXX`, or fill-in placeholders.

Freeze the candidate and call `council.py review` with your independent
`--sol-ready` judgment and reasoned rulings on prior objections. The runtime
resumes only the recorded Claude session, hashes every candidate, and owns the
stable objection IDs.

Run at most ten completed review rounds, showing one compact status line per
round. Blind initial, context repair, and mechanical retries do not consume the
round budget. Stop immediately when all are true:

- Opus verdict is `READY_FOR_CODEX`;
- Opus has no blocking objections and every execution-readiness gate is true;
- the ledger has no open material blocker;
- you independently sign `READY_FOR_CODEX`;
- the candidate linter passes; and
- both sign-offs refer to the exact same frozen candidate hash.

Different reasonable implementation preferences, style suggestions, optional
optimizations, or non-material wording differences are NON_BLOCKING. Do not
upgrade them merely to prolong review.

If a genuine blocker remains after round 10, do not print a copyable final
prompt. Return `NO AGREEMENT — NOT READY FOR CODEX EXECUTION`, the rounds used,
remaining material blockers, latest draft artifact, and any truly missing
context.

## Final output

On success, show:

1. `Council execution-readiness agreement reached in N/10 review rounds.`
2. The complete `FINAL_CODEX_PROMPT` exactly as signed.
3. Its artifact path and SHA-256.

Do not execute it. Any substantive post-sign-off change invalidates both
sign-offs and requires another review within the remaining round budget.
