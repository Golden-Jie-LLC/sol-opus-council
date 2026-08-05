<!-- No h1 caption: GitHub renders the repository name and description above. -->
<!-- markdownlint-disable-next-line MD041 -->
[![CI](https://github.com/octanevz/codex-debate/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/octanevz/codex-debate/actions/workflows/ci.yml)

## Skills

| Skill | Purpose |
| --- | --- |
| [codex-debate](#skill-codex-debate) | Claude and OpenAI's Codex CLI debate a document or question, round by round, until they agree or a round cap stops them. You decide whether the debate changes the subject or leaves it untouched. Three autonomy modes: `auto`, `interactive`, `deadlock`. |

## Skill: `codex-debate`

### Overview

Two AI agents check each other's reasoning so you don't have to take a single model's word for it. Claude leads the debate; Codex acts as an independent adversarial reviewer: it flags flaws, questions assumptions, and proposes concrete improvements, while Claude judges each point on its merits rather than politely accepting it.

### Requirements

- On the Claude side, a working Claude Code installation with plugin support (the `/plugin` command) is required for the recommended installation path below.
- The [Codex CLI](https://github.com/openai/codex) (`codex`) must be installed and findable on your `PATH` (typing `codex` in a terminal works). The debate protocol depends on specific `codex exec` and `codex exec resume` options; the skill was last verified against Codex CLI 0.145.0, and a much older version may launch fine yet fail mid-debate.
- Codex access requires a ChatGPT plan that includes Codex or a funded OpenAI API account; which plans include Codex, and at what usage limits, changes over time, so check the [official instructions](https://github.com/openai/codex) for current options.
- Codex must already be authenticated: run `codex login` once, or configure an API key per the [official instructions](https://github.com/openai/codex), before first use. The skill drives `codex` non-interactively (no prompts, no browser windows) and cannot complete a login itself.

Installation itself is two commands; see [Installation](#installation) near the end of this document.

### Anatomy of a debate

An example of what a run looks like, using the prompt ``Debate `specs/auth-design.md` with Codex until you agree``:

1. Claude reads the spec and sends it to Codex with the debate rules attached.
2. Codex replies with numbered objections, e.g. "3. Session tokens never expire."
3. Claude rules on each objection independently: concede (apply the fix to the spec) or rebut with reasons. In `interactive` mode you see these rulings and steer them before they are sent.
4. Claude replies to Codex, and steps 2 to 3 repeat; Codex remembers the whole conversation (each round resumes the same stored session via `codex exec resume`).
5. The debate ends when both sides agree (Codex declares agreement and Claude has no objections left; neither side can declare convergence alone) or when the round cap stops it. That is the stop rule for an ordinary advisory debate like this one; binding debates add further blockers, described under [Rigor](#rigor-advisory-vs-binding) below.
6. You get a report: every objection's status (accepted, rejected, or left unresolved) and why, the final document, and any unresolved disputes. If the cap ends the debate early, changes both sides already agreed on stay applied, and the report marks the remaining points as unresolved rather than presenting the document as fully agreed. The same holds if a run aborts on a tool or protocol failure: a debate is not transactional, so changes agreed before the abort stay applied, and the report identifies them.

### Debate shapes

How you frame the charge decides what the debate actually tests. Six shapes have grown out of real sessions; together they form a ladder of independence and cost. The first three keep a single independent reading and vary what the attack targets; the next two buy additional independent readings; the last buys independence from the debate itself. Each prompt below is ready to copy, with paths and subjects swapped for your own. The shapes are prompt patterns that Claude carries out while leading the debate, not separate protocol modes with machinery of their own: in the blind shape, independence rests on Claude keeping the two lists apart until both are locked in; in the fresh-eyes shape, on Claude starting a genuinely new Codex session instead of resuming the old one.

1. **Single prosecutor**, the default shape: Codex attacks, Claude rules on each objection and applies what survives. One reading, adversarially checked; right when you want your work stress-tested by an independent reviewer.

   ```text
   Debate `specs/auth-design.md` with Codex until you agree
   ```

2. **Socratic interrogation**: Codex attacks with questions instead of findings — each objection is a question the document should answer and doesn't. Claude answers or concedes the gap, answers that survive the attack are written in, and evasive answers draw the next round's fire. The same cost rung as single prosecutor, but pointed at what the document fails to say rather than flaws in what it says; prefer it for early drafts, policies, and specs whose main risk is the unstated. Expect slower convergence than a defect hunt: in the live session behind this prompt, good answers kept inviting follow-up questions and the round cap ended the debate, with the still-open questions reported unresolved — often exactly the deliverable you wanted.

   ```text
   Have Codex interrogate `docs/data-retention.md`: attack it with the questions it fails to answer, and debate the gaps until you agree
   ```

3. **Devil's advocate**: the subject is a decision already made, not a document under construction. Codex builds the strongest genuine case against it, steelmanning the rejected alternative, while Claude defends the decision on its merits; the debate converges on a joint verdict — the decision stands with its residual risks named, or both sides agree it should be revisited. Still one adversarially checked reading; what changes is the success condition, which no longer requires the attack to "win". Prefer it before committing to something hard to reverse. Typical yield, seen in the live session behind this prompt: the decision survives, but picks up obligations and named risks its original rationale lacked.

   ```text
   We decided to pin exact tool versions in CI rather than track latest. Have Codex play devil's advocate: it makes the strongest case against the decision, you defend it, and you debate to a joint verdict with residual risks named
   ```

4. **Pre-registered assessment**: Claude writes down its own assessment before Codex speaks, then Codex attacks that assessment and fills the gaps. Claude's reading cannot be anchored on Codex's, and the attack tests it directly; note that Codex still reviews with Claude's list in view, so only one side reads independently.

   ```text
   Assess `docs/incident-runbook.md` yourself first and write down your findings; then have Codex attack your assessment and fill any gaps, debating to agreement
   ```

5. **Blind commit, then cross-attack**: both sides review the subject with no sight of the other's findings and lock in their lists before either is revealed, then attack each other's lists until one joint list stands. Two fully independent readings, mutually checked; the most thorough and most expensive standalone shape. The reason it exists: in the live sessions these prompts grew out of, the two blind lists had near-zero overlap (an informal observation from a handful of runs, not a measured result), so any shape with a single independent reading leaves the other side's blind spots untested.

   ```text
   You and Codex both review `src/billing/` for defects independently. Lock in your findings blind, then cross-attack each other's lists and debate to a joint final list
   ```

6. **Fresh-eyes verdict**: an add-on to any shape above rather than a shape of its own. After the debate converges, a fresh Codex session — no memory of the debate, no stake in its compromises — attacks the agreed result, and Claude rules on what it finds. What it tests is convergence itself: a negotiated agreement drifts toward what both debaters will accept, and the session that negotiated it cannot see that drift. It costs one extra Codex session on top of the debate it checks, and its findings tend to be real, so budget an exchange or two to settle them: in the live session behind this prompt, the fresh reviewer's first reply found eight problems in a result both sides had just signed off, one of them a compromise carried over from the debate. Fresh objections still open when you stop are reported unresolved, like any capped debate.

   ```text
   Debate `specs/auth-design.md` with Codex until you agree, then have a fresh Codex session attack the agreed result and rule on what it finds
   ```

### Examples

#### How to read these examples

The round cap (how many debate rounds may run) defaults to 5 and is raised or lowered by asking: "up to 10 rounds", "round cap 8", "give it at most 12 rounds", or "max 3 rounds" as in the tables below. Budget wall-clock time as well as API cost: each Codex call typically takes one to three minutes, a debate makes at least one call per round, and corrective retries, binding exploration, and final-round evidence exchanges can add calls beyond the round cap.

Terms used below: a "ruling" is Claude's accept-or-reject decision on one Codex objection; a "proposal copy" is a copy of your document that receives the suggested edits so the original stays untouched; a "position file" is a new file holding the jointly agreed outcome when the debate does not modify an existing file; a "diff" shows the proposed changes line by line. The report identifies every deliverable it created and the transcript directory. The outcomes below describe a debate that reaches agreement; a capped debate still delivers, with unresolved points labeled (see the walkthrough above).

The Mode column shows what your wording selects, including the debate shape when it is not the default; the shapes are described above, and the modes themselves, the advisory/binding rigor levels, and the Codex options are explained in the sections that follow.

#### Technical

| You say | Mode | What you get |
| --- | --- | --- |
| ``Debate `specs/auth-design.md` with Codex until you agree`` | `auto` (default: nothing named or implied) | Runs to convergence or round cap, then reports every ruling; the spec file is changed: agreed revisions are applied to it round by round |
| `Debate this API design with Codex, let me steer each round` | `interactive` (implied by "let me steer each round") | After each Codex reply, shows its objections plus Claude's proposed rulings and waits for your go-ahead before replying to Codex; the design doc is changed only with rulings you approved |
| `Discuss adopting event sourcing with Codex; only interrupt me if you two get stuck` | `deadlock` (implied by "only interrupt me if you two get stuck") | Autonomous until the same point stays disputed two consecutive rounds with neither side moving, then asks you to break the tie; no existing file is changed, the agreed outcome is written to a new position file |
| ``mode: deadlock, model gpt-5.6-sol: iterate on `specs/payment-flow.md` with Codex until you both agree`` | `deadlock` (named explicitly) | The spec file is changed: agreed revisions applied round by round, with Codex running on the named model; ties come back to you |
| `Discussion only: work out a migration plan from REST to gRPC with Codex, change nothing` | `auto` (default) | A converged action plan both models endorse; no existing file is changed: the agreed plan lands in a new position file |
| `Ask Codex for a second opinion on this architecture doc` | `auto` (default) | An opinion-only review: Codex's objections, Claude's rulings, and a proposed revision as a diff; your file is not changed |
| `Interactive, max 3 rounds: debate my caching strategy with Codex` | `interactive` (named explicitly) | You veto or sharpen Claude's rebuttals each round, capped at 3 rounds; no existing file is changed, the agreed outcome is written to a new position file |
| `Debate with Codex whether we should adopt TDD, effort medium` | `auto` (default) | A pure topic debate ending in a jointly held position, delivered as a new position file; no existing file is changed; the named effort is forwarded to Codex |
| `Have Codex explore this repo and challenge our service boundaries` | `auto`, advisory | Codex reads the codebase itself and argues from `file:line` citations; the debate converges on a position file; opinion outcome, no code changed |
| ``Binding: debate `docs/api-policy.md` with Codex; the team will rely on the result`` | `auto`, binding (named) | The document is pinned and versioned each round; the final report anchors the agreement to the exact agreed version and states where the record is kept |
| `Review my refactoring branch with Codex and gate the merge on a binding agreement` | `auto`, binding (implied by "gate the merge") | Codex explores the base once, then debates each revision as a diff between commits; the final report names the exact commit range and any exclusions; if every point closes, it records an agreement covering exactly that range, ready to cite in the PR, and otherwise it reports the unresolved blockers |
| ``Assess `docs/incident-runbook.md` yourself first and write down your findings, then have Codex attack your assessment, debating to agreement; check in with me each round`` | `interactive` (implied by "check in with me each round"), pre-registered assessment | Claude writes its findings down before Codex speaks, then Codex attacks that assessment and fills the gaps; you approve every ruling before it is sent; the agreed assessment lands in a new position file, and the runbook itself is not changed |
| ``You and Codex both review `src/billing/` for defects independently; lock in your findings blind, then cross-attack each other's lists and debate to a joint final list`` | `auto`, advisory, blind cross-attack | Two fully independent readings, locked in before either is revealed, then attacked against each other; the joint defect list lands in a new position file; opinion outcome, no code changed |
| ``Binding: you and Codex both review `src/billing/` for defects independently; lock in your findings blind, then cross-attack to a joint list the team will rely on`` | `auto`, binding (named), blind cross-attack | Two fully independent readings, locked in before either is revealed, then attacked against each other; the joint defect list lands in a new position file, and the agreement names the exact reviewed versions it covers |
| ``Have Codex interrogate `docs/data-retention.md`: attack it with the questions it fails to answer, and debate the gaps until you agree`` | `auto` (default), Socratic interrogation | Codex's objections are the questions the document leaves unanswered; answers that survive the attack are written into the file round by round, and questions still open at the end are reported unresolved |
| `We decided to adopt event sourcing for the order service. Have Codex play devil's advocate against that decision; only interrupt me if you two get stuck` | `deadlock` (implied), devil's advocate | Codex steelmans the rejected alternatives while Claude defends the decision, and ties come back to you; the joint verdict — the decision stands with residual risks named, or should be revisited — lands in a new position file |
| ``Binding: debate `docs/api-policy.md` with Codex until you agree, then have a fresh Codex session attack the agreed version before you record it`` | `auto`, binding (named), fresh-eyes verdict | After convergence, a new Codex session with no stake in the debate's compromises attacks the agreed version; the recorded agreement covers only what survives that attack, anchored to the exact agreed version, with any still-open fresh objections reported unresolved |

#### Non-technical

The subject of a debate does not have to be software engineering: any document or question works.

| You say | Mode | What you get |
| --- | --- | --- |
| ``Have Codex challenge the argument in `drafts/sunset-the-forum.md` `` | `auto` (default) | An opinion-only review: Codex's objections, Claude's rulings, and a proposed revision as a diff; your draft is not changed |
| `Debate my conference talk abstract with Codex, check in with me each round` | `interactive` (implied by "check in with me each round") | You steer every ruling before it is sent; no existing file is changed, the agreed abstract lands in a new position file |
| ``Debate `hiring/phone-screen-rubric.md` with Codex until you agree`` | `auto` (default) | The rubric file is changed: agreed revisions are applied to it round by round |
| `Discuss with Codex whether we should move the user conference online; only interrupt me if you two get stuck` | `deadlock` (implied) | Autonomous until the same point stays disputed two consecutive rounds with neither side moving, then you break the tie; the agreed recommendation lands in a new position file |
| ``Binding: debate `handbook/remote-work-policy.md` with Codex; HR will rely on the result`` | `auto`, binding (named) | The policy is pinned and versioned each round; the final report anchors the agreement to the exact agreed version and states where the record is kept |
| ``You and Codex both critique `drafts/keynote-outline.md` independently; lock in your findings blind, then cross-attack and debate to one joint list`` | `auto` (default mode), blind cross-attack | Both critiques are locked in before either is revealed, then merged through mutual attack; the joint critique lands in a new position file, and your draft is not changed |
| ``Have Codex interrogate `handbook/parental-leave-policy.md`: attack it with the questions it fails to answer and debate the gaps until you agree; check in with me each round`` | `interactive` (implied by "check in with me each round"), Socratic interrogation | You see each unanswered question and steer every answer before it is sent back; agreed answers are written into the policy round by round |
| `We decided to drop the print edition of the newsletter. Have Codex play devil's advocate and debate to a joint verdict` | `auto` (default), devil's advocate | Codex makes the strongest case for keeping print while Claude defends the decision; the joint verdict with residual risks named lands in a new position file |
| `Debate my fundraising letter with Codex until you agree, then get a fresh Codex session to attack what you agreed on` | `auto` (default), fresh-eyes verdict | Once the letter converges, a fresh session with no memory of the debate attacks the agreed version; what survives is the deliverable, and fresh objections still open are reported unresolved |

#### Additional examples for [Herdr](https://herdr.dev/) users

If your session runs inside Herdr, a terminal multiplexer for coding agents, you can watch a debate live instead of relying on the per-round status lines alone: every prompt and reply lands in the debate's transcript directory as it is written, and a Herdr pane can follow those files. No shell commands are needed on your side; ask in plain words, the agent's own Herdr skill handles the pane control, and the agent running the debate already knows the transcript directory from its own session (the final report names it too). For these prompts to work properly, the [Herdr agent skill](https://herdr.dev/docs/agent-skill/) must be installed.

| You say | What you get |
| --- | --- |
| ``Debate `specs/auth-design.md` with Codex; show the debate trail in a pane on the right`` | A pane beside the session streams each prompt and reply as its file is written |
| `Show the running debate in a bottom pane` | The trail pane attaches to a debate already in progress |
| `The debate is done, close the trail pane` | The pane is removed; the transcripts stay in the debate directory until you have them deleted |

One detail worth passing along if a trail pane stays empty (it is a hint for the agent's Herdr skill to act on, not a command for you to run): the viewer should follow the round files by explicit names up to the round cap (`tail -n +1 -F p1.md r1.md p2.md r2.md ...`), because `tail -F` waits for files that don't exist yet, while a shell glob would never match them. The round files are not always the whole trail: corrective retries and binding exploration write extra reply files with fresh names of their own, which an explicit list misses unless the agent adds them.

### Autonomy Modes

The mode controls how often Claude checks in with you during the debate. It is written in your request in natural language; there are no command-line flags. Name it directly (`interactive`, or `mode: deadlock`) or describe what you want ("check in with me each round" means `interactive`; "only interrupt me if you two get stuck" means `deadlock`). A directly named mode wins if your wording suggests otherwise; if nothing is named or implied, `auto` is used.

| Mode | Behavior |
| --- | --- |
| `auto` (default) | Runs autonomously to convergence or the round cap, printing a one-line status after each round (round number vs cap, Codex's verdict, the ledger tally), then reports |
| `interactive` | After each Codex reply, Claude shows you Codex's points plus its own proposed concessions and rebuttals, and waits for your input before sending its reply back to Codex |
| `deadlock` | Autonomous, but pauses to ask you only when deadlocked: the same point stays disputed two consecutive rounds with neither side moving |

In `auto`, a deadlocked point is not escalated: the debate runs to the round cap and remaining disagreements are reported as unresolved.

When `deadlock` mode asks you to break a tie, useful answers include picking one side, adding a constraint both sides must respect, or sending the models down a different path entirely.

### Rigor: Advisory vs Binding

Independent of the autonomy mode, every debate runs at one of two rigor levels, chosen from your wording like everything else:

- **Advisory** (default): the verdict is a considered opinion. For project material, Codex may read your files directly and cite them by `file:line`; the report notes that its conclusions reflect your working tree as it stood when read. Fast and light; right for second opinions, design discussions, and code reviews you will act on yourself.
- **Binding**: request it when you will rely on the agreement later, e.g. "binding", "gate the merge on this", or "I need a mutually agreed record". Everything under review is pinned (inline snapshots or git commits), so the final agreement provably covers exact versions; expect more ceremony and possibly more rounds. Binding buys provenance, not correctness: it proves which exact versions the agreement covers, not that the agreement itself is sound, and two models can still agree and both be wrong. If Codex needs material it cannot see, it requests it on the record and Claude supplies or declines it inline; unresolved requests block agreement, and a request first raised in the final round earns one extra resolution exchange beyond the round cap. One caveat: the evidence trail lives in the transcript directory, which is temporary. If the agreement gates something, ask for the report and transcripts to be saved somewhere durable, such as the repository or the pull request.

> [!WARNING]
> Repo-scale binding debates (repository exploration and diff-based refactoring) are the newest and least test-covered part of the protocol; treat them as experimental for now. They also come with preconditions: a real Git repository and a clean, committed state for everything in scope. The full list lives in the skill's binding protocol reference.

### Model and Reasoning Effort

Which model Codex uses, and how much reasoning effort it spends, can be set in the request the same free-text way as everything else: "model gpt-5.6-sol", "effort medium" (any model your Codex installation supports; valid efforts: minimal, low, medium, high). Anything you set is forwarded to every Codex call, so the debate stays on one model throughout. If you set nothing, Codex runs with the defaults from its own configuration (`~/.codex/config.toml`), exactly as if you had started it yourself. These options affect only Codex; Claude runs as whatever model your Claude Code session uses. The round cap is not a Codex option: it governs the debate loop itself.

### Under the hood

Codex needs no setup beyond installation and login; the prompts carry every rule it must follow, its session memory persists across rounds, and each debate-round reply ends with a fixed agreement-or-dispute line that Claude can recognize reliably (a machine-checkable verdict). Claude validates each debate-round reply against fixed criteria: the run must succeed, produce its output file, keep a single session identity (checked once at round 1, enforced thereafter by resuming the explicit session id), and end with a well-formed verdict line, and a malformed verdict gets exactly one correction attempt. (Preparatory calls, such as the repository exploration that precedes a binding refactoring debate, are not rounds: they carry no verdict and are checked for successful execution, non-empty output, and a single session identity.) The substance behind the verdict is judged by Claude, not machinery, so on a document you don't fully control treat the review as advisory, since crafted content could try to sway it.

### Security, cost, and data handling

- Existing files are not modified unless changing them is part of your request; results are delivered as proposals and diffs. Debating a named file "until you agree" counts as requesting changes, because the file itself is the thing being converged; purely reviewing ("second opinion", "discussion only") never touches it. A run may still create new files: a proposal copy of the reviewed artifact, or the position file of a topic debate. One edge case: a fix accepted from Codex's final reply cannot be re-reviewed by Codex, so the report labels it "unreviewed by Codex".
- Codex always runs strictly read-only (sandboxed, approvals off) and never modifies your project files; its only writes are its own reply files and session bookkeeping. One boundary: that guarantee governs the sandbox around Codex's own commands; MCP servers and hooks you have configured yourself run outside it and remain your own trust decision. Claude reviews every Codex suggestion and applies accepted changes itself; the skill's hard rule forbids constructing any write-enabled Codex invocation, and the `write-temptation` test scenario (see [CONTRIBUTING.md](CONTRIBUTING.md)) exercises exactly that pressure in the compliance suite.
- Debates call the external Codex CLI: OpenAI-side usage costs apply, and debated content (inlined subjects, or repository files Codex reads directly in advisory/binding repo debates) is sent to OpenAI. Claude-side usage applies as well: your Claude Code session spends its own usage leading every round.
- Each debate leaves prompt/reply transcripts in a temp directory that is not cleaned up automatically, and a durable Codex session (the stored conversation) under the active Codex home (`$CODEX_HOME`, default `~/.codex`); both persist until you have them removed. The final report names both, offers to delete or copy the transcripts, and explains how to delete the session.

## Installation

### As a plugin (recommended)

In Claude Code:

```text
/plugin marketplace add octanevz/codex-debate
/plugin install codex-debate@octanevz
```

The skill can then be used as `codex-debate:codex-debate`, e.g.:

```text
/codex-debate:codex-debate debate `specs/auth-design.md` with Codex until you agree
```

Relative paths like `specs/auth-design.md` are resolved from the directory Claude Code was started in. Note what the phrasing selects: "until you agree" makes the named file the thing being converged, so agreed revisions are applied to it; ask for a "second opinion" instead to leave it untouched (see [Security, cost, and data handling](#security-cost-and-data-handling)). You can also simply ask in plain language ("debate this file with Codex until you agree"); Claude picks the skill up automatically.

### For contributors

Development setup and the test suites (prerequisites, API costs, and the pre-PR command set) are documented in [CONTRIBUTING.md](CONTRIBUTING.md).
