# CLAUDE.md

Guidance for Claude Code and other coding agents (see `AGENTS.md`) when working in this repository, ordered by workflow: edit → test → lint → release.

Layout: the repository root is the marketplace (`.claude-plugin/marketplace.json`); each installable plugin lives under `plugins/<plugin>/` with its own `.claude-plugin/plugin.json`, `skills/<name>/` directories, `README.md`, `LICENSE`, and `CHANGELOG.md`. Tests, baselines, and contributor files stay at the repository root — installations copy only the plugin directory.

## Editing and testing skills

- When editing a skill that has a compliance suite under `tests/<name>/`, run the relevant scenarios before committing (each scenario run costs one headless Claude session); CONTRIBUTING.md documents usage. The suites load the skill via a `~/.claude/skills` symlink into `plugins/<plugin>/skills/<name>/`.
- Some suites include a live check against a real external CLI (currently `tests/codex-debate/live-contract.sh`, covering the three fragments it assembles from the skill's `references/prompts/`: `role-and-rules.md`, `advisory-inline-extras.md`, and `fenced-subject.md`). Run a live check after changing what it covers or upgrading the CLI it calls, not routinely.
- After changing a skill's frontmatter `description`, run the triggering suite (`tests/skill-triggering/run.sh`; costs API calls, not in CI): compliance suites exercise behavior after invocation, not routing. (Adopt `claude plugin eval` for this once it leaves early access.)
- After changing manifests or the repository layout, run the install smoke test: `tests/plugin-install/smoke.sh`.
- Recorded RED baselines under `tests/<name>/baselines/` are historical evidence; do not re-run or overwrite them casually.

## Before committing: lint and format

CI (`.github/workflows/ci.yml`) runs these on every push to `main` and every PR; run them locally first and fix findings — each must come back clean.

```bash
# all from the repository root

# shell scripts: every tracked script and test stub, same command as CI
git ls-files '*.sh' 'tests/*/bin/*' | xargs shellcheck

# report formatting diffs; fix with: shfmt -w <files>
shfmt -d .

# markdown
markdownlint-cli2 "**/*.md"

# manifests
claude plugin validate . --strict
claude plugin validate plugins/codex-debate --strict
```

Notes:

- `shfmt` reads its settings (indent, case indent, redirect spacing) from the repository root `.editorconfig`, so running from the root works; run it without style flags. The pinned style covers each suite's top-level scripts and `bin/codex`; nested `scenarios/*/checks.sh` stay on shfmt's default style.
- Markdown lint config is layered: the root `.markdownlint.jsonc` plus nested ones that exempt prompt/fixture payload files (delivered verbatim to agents, not documents) from document-shape rules. Always lint from the repository root; from a subdirectory, config discovery stops at the working directory and produces spurious findings.
- CI pins its tool versions (shfmt, markdownlint-cli2, Claude Code CLI), which may differ from what is installed locally; when local and CI results disagree, the versions pinned in `.github/workflows/ci.yml` are the authority.

## Releasing

- A release ships as a single commit: the plugin/test changes, the version bump, and the changelog entry together.
- The version lives only in `plugins/<plugin>/.claude-plugin/plugin.json` — the marketplace entry carries no version, so there is nothing to keep in sync.
- Add a `plugins/<plugin>/CHANGELOG.md` entry (changelog style, newest first) with a `**Full changelog:**` compare link; repeated per-version headings are fine — `MD024` is relaxed to `siblings_only`. First-release exception: a plugin's first version has no prior tag to compare against, so its entry links the release tag instead (as v0.1.0 does).
- Tag with `claude plugin tag plugins/<plugin>` — it creates an annotated `<plugin>--v<version>` tag after validating the manifests agree — and push the branch and tag together. (Repo-wide `vX.Y.Z` tags were used through v0.2.1.)
