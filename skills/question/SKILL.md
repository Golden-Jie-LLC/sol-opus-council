---
name: question
description: Run the explicit QUESTION council workflow to answer a user question with an independent GPT-5.6 Sol position and a read-only Claude Opus review. Never invoke implicitly.
---

# QUESTION

Answer the text following `$question` through the Codex-hosted Sol–Opus
council. This is a THINK-only workflow: do not modify the user's business
repository, create branches, commit, push, or execute implementation work.

## Provider authorization and data boundary

Explicit invocation of `$question` is itself the user's authorization for this
council run to send the minimum task-relevant context to Anthropic Claude Opus
through the local Claude Code CLI. Do not ask for a second provider-consent
confirmation merely because Claude is a non-OpenAI model.

A governing instruction that only says external/non-OpenAI transmission
requires explicit user authorization is satisfied by the user's explicit
`$question` invocation. This does not override a stricter governing instruction
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
2. Confirm the current Codex session reports `gpt-5.6-sol` when the host exposes
   model identity. If it reports another model, stop and ask the user to switch;
   never substitute another OpenAI model. If model identity is unavailable,
   state that limitation in the run manifest and continue without guessing.
3. Run the launcher's `doctor` command. Claude must be authenticated and the
   detected CLI must support the required flags. Never request an API key or
   use the Anthropic API.
4. Claude must be able to persist its local transcript so the explicit session
   UUID can be resumed. If the Codex sandbox blocks the configured Claude
   projects directory (normally `~/.claude/projects`), request narrowly scoped
   write permission for that directory before `opus-initial`. Do not broaden
   this to business-repository write access and never use `--continue` as a
   workaround.

## Freeze independent inputs

Create request and context input files outside the business repository. Preserve
the current user request verbatim. Include only relevant history, decisions,
evidence with sources, repository state and relevant paths, governing
instructions, unknowns, hard constraints, output language, and explicit
non-goals. Do not dump the conversation.

Run `council.py begin --mode QUESTION` with those files. The runtime returns a
run directory and frozen context hash beneath the configured Codex council run
root.

Before any Claude call, independently form and save `sol-initial.md` in the run
directory with:

- direct answer;
- key reasons;
- assumptions;
- risks and uncertainties;
- confidence;
- relevant evidence references.

Do not expose hidden chain-of-thought. Call `council.py lock-sol`, then
`council.py opus-initial`. The runtime rejects a blind prompt containing the Sol
position or its hash and records the explicit Claude session UUID.

If Opus returns `MISSING_CONTEXT`, repair only materially necessary context via
`revise-context`. At most two repairs are allowed. Each repair invalidates both
blind positions, so repeat Sol lock and Opus initial from the new packet.

## Review loop

After both blind positions exist, synthesize a candidate answer in the user's
language. Save it only in the run directory and call `council.py review` with
your independent `--sol-ready` judgment and explicit rulings on the prior
ledger. Never accept or rebut an objection without checking it on its merits;
every rebuttal needs a reason.

Run at most three completed review rounds. Blind initial, context repair, and
mechanical retries are not review rounds. After each round show one short status
line such as `QUESTION round 1/3 — 2 material blockers open`.

Stop immediately when Opus returns `AGREEMENT` with no blockers, the ledger has
no open material item, and you independently judge the candidate sufficiently
correct, complete, and useful. Do not continue for wording, emphasis, or
preference differences.

If round 3 still has material disagreement, return the best synthesized answer
and visibly state `Council status: unresolved after 3 review rounds`, with only
a concise summary of material uncertainty. Never show raw transcripts or hidden
reasoning.

## Final answer

Lead with the answer. Add only compact council metadata at the end: review
rounds used, agreement status, unresolved material issue count, final artifact
path, and hash when available.
