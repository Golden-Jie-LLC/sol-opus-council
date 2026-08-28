# Migration design: Sol–Opus Council for Codex

## Baseline

The migration starts from `octanevz/codex-debate` commit
`aeebb0485da07d04d28083809e2b237133c5dee7`. The upstream product is a
Claude-hosted plugin that asks the Codex CLI to review work. This fork reverses
the host/peer relationship: Codex is the only user interface and Claude Code is
a headless, read-only Opus peer.

## Product boundary

The only user workflows are the explicit Codex skills `question` and `prompt`.
They share one deterministic Python runtime and one protocol source. The
runtime owns artifacts, hashes, schemas, Claude process isolation, retries,
session identity, round accounting, and fail-closed termination. The Codex host
owns contextual judgment, the independent Sol position, synthesis, and each
objection ruling.

Council work is THINK-only. It writes only beneath the configured council run
directory and never changes the user's business repository. A successful
PROMPT run returns a frozen, jointly signed execution prompt but never executes
it.

## Safety and protocol invariants

- Freeze one canonical context packet and hash it before either blind position.
- Persist and hash the Sol initial position before the first Claude call.
- Build the blind Opus prompt only from the packet, role, schema, and read
  permissions; reject any Sol-content or Sol-hash leak.
- Invoke only `--model opus`; never pass a fallback model.
- Use Claude `--safe-mode`, an empty strict MCP config, and an explicit
  read-only built-in tool allowlist. Never expose Bash, Write, Edit, browser
  control, or mutation-capable MCP tools.
- Resume only the recorded UUID with `--resume`; never use `--continue`.
- Give every attempt unique prompt/stdout/stderr/parsed files.
- Count only completed structured reviews toward the 3-round QUESTION cap or
  10-round PROMPT cap. Context repairs and mechanical retries are separate and
  bounded.
- Stop immediately when the mode-specific agreement contract is satisfied.
- In PROMPT mode, style and alternative implementation preferences are
  non-blocking. A genuine open material blocker prevents `FINAL_CODEX_PROMPT`.

## Distribution

Canonical skill sources live under `skills/`. The installer copies both skills
and one private sibling runtime into either `<repo>/.agents/skills` or
`$CODEX_HOME/skills` (default `~/.codex/skills`). `agents/openai.yaml` makes both skills explicit-only and
provides the QUESTION/PROMPT display names. The stable invocation is
`$question ...` and `$prompt ...`; `/skills` is the supported selector.
