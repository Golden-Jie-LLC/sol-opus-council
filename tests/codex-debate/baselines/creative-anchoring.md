# RED baseline: creative-anchoring (2026-07-19, sonnet)

Scenario origin: an advisory debate between Claude and Codex about the skill's
own prompt templates (2026-07-19) converged on three genericness gaps, the
largest being that `fenced-subject.md` mandated numbering claims inside the
fenced copy — which distorts a creative or precisely formatted subject — while
the canonical citation rule offered no anchor usable for such subjects. The
scenario debates a limerick with a locked punchline: the checks assert
verbatim fencing, the quoted/structural-anchor vocabulary, the topic-neutral
role wording, and that a constraint-bound concession is recorded without
revising the locked line.

## RED (skill suppressed): 8/20

- Call 1: prompt passed as an argv argument, not stdin; no sandbox flags; no
  role fragment, no advisory label, no verdict contract; the poem paraphrased
  inside prose with `---` separators rather than fenced.
- Call 2: `exec resume --last` (forbidden), free-form conversational reply.
- Three calls total, no ledger, no rules footer, no verdict in the report.
- The agent did honor the punchline constraint and revised line 2, so the
  failure axis is protocol and fencing, not editorial judgment.

## Pre-edit skill (GREEN run before the wording edits): 16/20, FAIL

Debate mechanics were fully correct (2 calls, read-only, ledger, footer,
verdict, advisory labels, constraint honored). The four failures were exactly
the edits' targets: the role fragment still read "adversarial technical
reviewer", the citation rule offered no quoted/structural anchors, and —
decisive for O2 — the agent obeyed the then-current `fenced-subject.md` slot
doc and rewrote the poem into claim lines inside the fence:

    C1 (title): # The Recursion Limerick
    C2 (line 1): There once was a coder named Lee
    ...
    C6 (line 5, LOCKED — do not propose changes): returned undefined — eventually.

flattening the indentation of lines 3–4 and prepending claim IDs to every
line: the artifact under review was no longer the artifact. This run is the
failing test that motivated the verbatim-fencing guidance in
`fenced-subject.md` and the anchor vocabulary in `role-and-rules.md`.
