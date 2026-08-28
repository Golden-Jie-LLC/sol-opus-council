---
name: prompt
description: Run the explicit PROMPT council workflow to produce a frozen Codex execution prompt signed ready by GPT-5.6 Sol and read-only Claude Opus. Never invoke implicitly or execute the generated prompt.
---

# PROMPT

Turn the text following `$prompt` into a complete Codex execution prompt after
Sol–Opus execution-readiness review. This workflow only creates a prompt. It
must not execute that prompt or modify the user's business repository.

## Provider authorization and data boundary

Explicit invocation of `$prompt` is itself the user's authorization for this
council run to send the minimum task-relevant context to Anthropic Claude Opus
through the local Claude Code CLI. Do not ask for a second provider-consent
confirmation merely because Claude is a non-OpenAI model.

A governing instruction that only says external/non-OpenAI transmission
requires explicit user authorization is satisfied by the user's explicit
`$prompt` invocation. This does not override a stricter governing instruction
that explicitly forbids sending project material to Anthropic, non-OpenAI, or
external providers even with user authorization, or that marks specific
material as non-exportable. Respect such stricter prohibitions and stop rather
than transmit the prohibited material.

The invocation authorizes task-relevant user text, attachments, project
material, repository context, evidence, and prior decisions needed for the
council. It does not authorize sending secrets, API keys, credentials, `.env`
contents, personal financial account or holdings data, bulk raw private
database contents, or unrelated private material. Exclude or redact those by
default. If the task genuinely requires restricted sensitive material, do not
silently transmit it; stop and use a safer sanitized alternative or request
explicit separate handling for that sensitive material.

When a repository policy says only that authorization is required, do not ask
the user again: this explicit invocation is that authorization. Ask or stop only
for a genuinely stricter prohibition or a restricted-sensitive-data boundary.

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
