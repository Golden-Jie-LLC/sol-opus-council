# Contributing

## Development setup

From the repository root, symlink a skill into Claude Code's personal skills directory (create `~/.claude/skills` first if it doesn't exist); changes in the repo are live immediately:

```bash
ln -s "$(pwd)/plugins/codex-debate/skills/codex-debate" ~/.claude/skills/codex-debate
```

Don't combine this with a plugin install of the same skill, or it will be offered twice.

New skills are added as `plugins/codex-debate/skills/<name>/SKILL.md`; the plugin discovers them automatically, so no manifest changes are needed.

## Running the tests

`tests/codex-debate/` holds a compliance suite for the `codex-debate` skill: each scenario launches a headless Claude agent against a stub `codex` CLI (`bin/codex`) that replays scripted replies and records every flag and prompt the agent sends, so no real Codex calls are made and the Codex side is fully deterministic (the Claude agent under test still varies from run to run). The symlink setup above must be in place, since the agent under test loads the skill from `~/.claude/skills`.

### Prerequisites and costs

| Suite | Needs | External cost |
| --- | --- | --- |
| Lint and manifest validation (the pre-PR set below) | `shellcheck`, `shfmt`, `markdownlint-cli2`, Claude Code CLI | None |
| Compliance scenarios (`tests/codex-debate/run.sh`) | Claude Code CLI, authenticated; the `~/.claude/skills` symlink; Codex is stubbed | Claude usage: one headless agent session per scenario run |
| Triggering suite (`tests/skill-triggering/run.sh`) | Claude Code CLI, authenticated; the `~/.claude/skills` symlink | Claude usage: several headless sessions per case (default 5 reps) |
| Install smoke test (`tests/plugin-install/smoke.sh`) | Claude Code CLI | None |
| Live contract check (`tests/codex-debate/live-contract.sh`) | Codex CLI, installed and logged in | Codex usage: 3 live calls by default (no Claude agent involved: the prompt is assembled by plain shell) |

```bash
cd tests/codex-debate

# the seven scenarios (GREEN: skill present, checks must pass)
./run.sh advisory-happy
./run.sh binding-doc
./run.sh creative-anchoring
./run.sh flag-discipline
./run.sh malformed-verdict
./run.sh sycophancy
./run.sh write-temptation

# variants (work with every scenario)
./run.sh advisory-happy --red      # baseline run (skill suppressed; failures expected)
./run.sh binding-doc --keep        # keep the workdir of a passing run for inspection
./run.sh sycophancy --model opus   # override the agent model (default: sonnet)

# occasional: real-Codex check of the frozen prompt wording
./live-contract.sh                 # 3 live calls; pass a number for more, e.g. ./live-contract.sh 5
```

Scenarios and what they verify:

| Scenario | Verifies |
| --- | --- |
| `advisory-happy` | Advisory mode selection, prompt assembly from the fragments, ledger and labeling, and the per-round status lines through a clean two-round debate |
| `binding-doc` | Binding-mode triggering, fencing with injection markers, the evidence channel (E-items), and the closing version manifest |
| `creative-anchoring` | Verbatim fencing of a creative subject (a poem with a locked punchline): no claim numbering that would distort the artifact, topic-neutral role wording, quoted/structural anchors, and a constraint-bound concession recorded without revising the locked line |
| `flag-discipline` | CLI mechanics across a three-round session: sandbox flags, session-id resumes, stdin piping, fresh `-o` files |
| `malformed-verdict` | The validation path, where a reply without a verdict line must cause exactly one corrective resume, not an abort |
| `sycophancy` | Merit-based rulings, where planted bogus objections must be rebutted in the ledger while valid ones are conceded |
| `write-temptation` | The never-writes rule, where the task and Codex itself both push for a writable sandbox and every call must stay read-only anyway |

Passing runs delete their `/tmp` workdir; failing runs keep it and print the path. RED runs use `--disable-slash-commands` and, where a scenario provides a `task-red.md`, a stricter task prompt, and are voided (exit 3) if the transcript shows the agent read any skill copy; recorded baselines live in `baselines/` and should not be re-run casually; see the notes there.

`live-contract.sh` is the one test that calls the real Codex CLI. It exercises the three fragments it assembles from `plugins/codex-debate/skills/codex-debate/references/prompts/` — `role-and-rules.md`, `advisory-inline-extras.md`, and `fenced-subject.md`; run it after editing one of those or upgrading Codex, not routinely. The other fragments are covered by the (stubbed) compliance scenarios only.

Two further suites cover what the scenarios cannot:

- `tests/skill-triggering/run.sh` measures whether the skill *triggers* for representative prompts (a genuine debate, a pure write-delegation request, a hybrid), several fresh headless sessions per case (`--reps N`, `--model M`). Compliance scenarios test behavior after invocation; this tests routing. Run it after changing the skill's frontmatter `description`; it costs API calls.
- `tests/plugin-install/smoke.sh` installs the plugin from this repository's marketplace into an isolated Claude config directory and verifies the installed artifact: the skill and its references ship, repository-only content (tests, contributor files) does not.

### Before a pull request

The minimal safe set costs no API calls; each command must come back clean:

```bash
# all from the repository root
markdownlint-cli2 "**/*.md"
claude plugin validate . --strict
claude plugin validate plugins/codex-debate --strict

# shell scripts: every tracked script and test stub, same commands as CI
# (the root .editorconfig pins the shell style)
git ls-files '*.sh' 'tests/*/bin/*' | xargs shellcheck
shfmt -d .   # prints nothing when clean
```

Beyond that, testing is change-driven: run the compliance scenarios covering what you changed, the triggering suite only after changing the skill's frontmatter `description`, the install smoke test after changing manifests or the repository layout, and the live contract check only after editing one of the three prompt fragments it assembles or upgrading Codex.
