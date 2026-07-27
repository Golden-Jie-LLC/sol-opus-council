# RED baseline: advisory-happy (2026-07-18, sonnet, skill masked)

Checks: 8 passed / 15 failed. Workdir evidence summarized below; the agent
completed a debate and produced a confident report — every failure is silent.

## Observed behavior (verbatim evidence)

- `codex exec <entire prompt as one argv argument>` — no stdin piping, no `-`;
  `prompt.md` captured empty. Shell-quoting of a multi-paragraph argv is fragile.
- **No sandbox flag at all** on any call: against real Codex these calls run
  `workspace-write` — the "debate partner" could have edited the repo.
- No `-o` output files: the agent parsed replies out of banner-mixed stdout.
- No session resume: three independent `exec` calls; call 3 re-explains the
  entire debate history ("incorporating your three objections from the previous
  round...") because nothing carries memory.
- Invented a weaker verdict grammar: asked for `VERDICT: AGREE` /
  `VERDICT: DISPUTE REMAINS` (mixed vocabulary), with no exactly-one-line or
  last-line constraint.
- Misreporting: the scripted reply said `VERDICT: AGREEMENT`; the agent's
  report claims Codex output "explicit `VERDICT: AGREE`" — a fabricated quote.
  It also reported "agreement after 1 round" after two debate calls.
- No injection fencing: subject inlined between bare `---` lines with no
  data-under-review marking.
- No stable IDs, no dispute ledger, no advisory/binding distinction, no
  advisory labeling in the report, no transcript disclosure.

## What the baseline agent got right unaided

- Discovered the CLI via `codex exec --help` before first use.
- Applied concessions to the document and re-submitted a revision.
- Told Codex "do not simply agree by default" — an unprompted sycophancy guard.
- Numbered its objections and cited claim numbers.

## Notes for interpreting GREEN

An earlier RED attempt was invalidated: the agent inspected `$(which codex)`,
followed `STUB_REPLIES` into the repo, and read the committed v0.1.0 SKILL.md
(passing exactly the v0.1.0-era checks). The harness now stages the stub and
replies into the temp workdir and shows a realistic run header. Baseline agents
are resourceful: keep harness paths pointing only at temp directories.
