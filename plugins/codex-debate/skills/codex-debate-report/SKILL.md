---
name: codex-debate-report
description: Use when a Claude-vs-Codex debate — finished or still in progress — should be written out as a standalone shareable HTML report, e.g. "write the debate up as a report", "generate an HTML report of the debate", "render the debate report", "export the discussion as HTML". Not for running debates (that is codex-debate; this skill only renders one that already happened), and not a general HTML or report generator — it renders exactly one document shape, the debate-report JSON defined by its schema.
---

# Codex Debate Report

Render a codex-debate run as a self-contained HTML report. The debate is first assembled as a JSON file — the single source of truth — conforming to `schema/debate-report.schema.json` (schemaVersion 1) in this skill's directory, then validated and rendered by the scripts there. **The HTML is never hand-written or hand-edited**: to change anything in a report, change the JSON and regenerate. Both scripts are stdlib-only Python 3; the renderer is deterministic, so identical JSON yields byte-identical HTML.

## Pipeline

From this skill's directory:

```bash
python3 scripts/validate_debate_report.py report.json          # exit 0 = valid; violations print with JSON-pointer paths
python3 scripts/render_debate_report.py report.json -o report.html
```

The renderer re-validates internally and writes nothing on invalid input, but run the validator first anyway — its violation list is the fix loop. Scripts resolve the schema relative to their own location, so they work from any working directory.

The rendered file embeds the exact input JSON as an inert data island: `<script type="application/json" id="debate-data">`. An agent reading an existing report parses the island instead of scraping HTML: extract the text between the island's open and close tags, reverse the inerting escape by replacing every `<\/` with `</`, then parse as JSON. The renderer performs this exact round-trip on its own output after writing and exits nonzero on any mismatch, so the island is trustworthy. This also means a report whose source JSON is lost can be regenerated: recover the JSON from the island, edit, re-render.

## Filling the JSON from a debate

- **Roles.** Codex attacks, Claude rules — `speaker` and `role` fields on messages reflect that, matching the codex-debate protocol. Do not swap them.
- **Objections and rulings.** Attach an `objection` entry (`id`, `title`, `status`, `reason`) to the message that rules on the point: `status` is `accepted`, `rejected`, or `unresolved`, and `reason` is the one-line ruling. Do not build a separate ledger — the ruling ledger table and its tally are derived from these entries in document order (rounds, then fresh-eyes).
- **Content.** Content blocks are plain text only — `paragraph`, `list`, `code`. No markdown or HTML inside strings; the renderer escapes everything it interpolates.
- **Shapes.** The optional sections map to the README's debate shapes: `preRegistered` for a pre-registered assessment, `blindCommit` for blind commit then cross-attack, `verdict.devilsAdvocate` for a devil's advocate joint verdict, and `freshEyes` for a fresh-eyes verdict pass (its messages use speaker `codex-fresh`). Omit what the debate didn't use; `rounds`, the derived ledger, and `verdict` render for every shape.
- **Honesty.** A capped debate reports its open points as `unresolved` and says so in `termination`; never render fake convergence.

## Output location and naming

Defaults, overridable per project:

- Directory: `debate-reports/` at the root of the project the debate was about; create it if absent. Keep the source JSON next to the HTML with the same basename.
- Filename: `<YYYY-MM-DD>-<subject-slug>.html`. The date comes from the JSON's `date` field — that field is the source of the report's date, not the clock at render time. The slug is the debate subject in kebab-case: lowercase, runs of non-alphanumerics collapsed to single hyphens, trimmed. On collision append `-2`, `-3`, ….
- A project may override directory and naming via its CLAUDE.md or a config file — an instruction like "debate reports go to `docs/reviews/`" wins over these defaults. The user's explicit ask in the conversation wins over both.

## Worked example

Validate and render the canonical sample, from this skill's directory:

```bash
python3 scripts/validate_debate_report.py references/examples/debate-report-sample.json
python3 scripts/render_debate_report.py references/examples/debate-report-sample.json -o /tmp/debate-report.html
```

The output is byte-identical to `references/examples/debate-report-rendered.html`.

## What lives where

- `schema/debate-report.schema.json` — the input contract. The validator interprets this file directly (a deliberately small JSON Schema subset); it is the single source of truth for the input shape.
- `scripts/` — `validate_debate_report.py` and `render_debate_report.py`.
- `references/examples/` — the canonical sample JSON and its rendered HTML, kept byte-in-sync; after any renderer or schema change, re-render the sample and commit both together.
- `references/prototypes/` — historical design iterations, kept for provenance only. The first (`debate-report.html`) predates the role correction and shows Claude attacking. Not authoritative — never copy structure or wording from them.
