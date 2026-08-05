#!/usr/bin/env python3
"""Deterministic codex-debate report renderer: JSON in -> pre-rendered HTML out.

Usage: python3 render_debate_report.py input.json -o output.html

Stdlib only. Identical input JSON produces byte-identical HTML: no timestamps,
no randomness, input order preserved everywhere. Every content string passes
through html.escape before interpolation. The exact input JSON is embedded as
an inert data island (<script type="application/json" id="debate-data">) with
'</' escaped as '<\\/'; after writing, the script re-extracts the island from
its own output, round-trips it, and exits nonzero on any mismatch.

The ruling ledger is DERIVED from the objection entries carried on messages in
`rounds` and `freshEyes.messages` — the JSON has no separate ledger array.

Input validation is delegated to validate_debate_report.py, which interprets
schema/debate-report.schema.json — the single source of truth for the input
shape. Only the schemaVersion gate stays here; nothing is written unless the
input validates and renders in full.
"""

import argparse
import html
import json
import sys
from pathlib import Path

import validate_debate_report

SCHEMA_VERSION = 1

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "debate-report.schema.json"

ISLAND_OPEN = '<script type="application/json" id="debate-data">'
ISLAND_CLOSE = "</script>"

SPEAKERS = {
    # speaker id -> (display label, message CSS class)
    "claude": ("Claude", "claude"),
    "codex": ("Codex", "codex"),
    "codex-fresh": ("Codex (fresh)", "codex fresh"),
}

PANEL_CLASS = {"claude": "claude-panel", "codex": "codex-panel"}

STATUSES = ("accepted", "rejected", "unresolved")
STATUS_LABEL = {"accepted": "Accepted", "rejected": "Rejected", "unresolved": "Unresolved"}

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

CSS = """\
  :root {
    color-scheme: light dark;

    /* Claude / Anthropic — terracotta "Crail" */
    --claude-accent: #D97757;
    --claude-accent-strong: #B85C3E;   /* darkened for text-on-light contrast */
    --claude-tint: #FBF1ED;

    /* Codex / OpenAI — ChatGPT green-teal */
    --codex-accent: #10A37F;
    --codex-accent-strong: #0B7A5F;    /* darkened for text-on-light contrast */
    --codex-tint: #EBF7F3;

    /* Status chips — deliberately non-brand hues (leafy green / red / amber) */
    --ok-text: #2C6E31;
    --ok-bg: #EAF5EB;
    --ok-border: #9CCB9F;
    --no-text: #A93226;
    --no-bg: #FBEBE9;
    --no-border: #E5A49C;
    --open-text: #8A5D0B;
    --open-bg: #FBF3DF;
    --open-border: #DFC182;

    --bg: #FAF9F7;
    --surface: #FFFFFF;
    --text: #1F1E1C;
    --text-muted: #5C594F;
    --border: #E4E1DA;
    --code-bg: #F1EFEA;
    --verdict-tint: #F4F2EE;
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --claude-accent: #E08B6D;
      --claude-accent-strong: #E8A188;
      --claude-tint: #322622;

      --codex-accent: #2BB894;
      --codex-accent-strong: #52C9AB;
      --codex-tint: #16302A;

      --ok-text: #8FD194;
      --ok-bg: #1E2F20;
      --ok-border: #3E5C41;
      --no-text: #F0968B;
      --no-bg: #372220;
      --no-border: #6B3B36;
      --open-text: #E3BC69;
      --open-bg: #322A16;
      --open-border: #6B5A2E;

      --bg: #1A1918;
      --surface: #232120;
      --text: #EDEAE4;
      --text-muted: #A8A399;
      --border: #3A3733;
      --code-bg: #2B2926;
      --verdict-tint: #262421;
    }
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.55;
    padding: 1.5rem 1rem 4rem;
  }

  .page {
    max-width: 48rem;
    margin: 0 auto;
  }

  /* ---------- Section shells ---------- */
  section.block { margin-bottom: 2.5rem; }

  .section-head { margin-bottom: 1rem; }

  .section-head h2 {
    font-size: 1.15rem;
    letter-spacing: -0.005em;
  }

  .used-by {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 0.15rem;
  }

  /* ---------- Header / metadata ---------- */
  .report-header {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1rem;
  }

  .report-header .kicker {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.35rem;
  }

  .report-header h1 {
    font-size: 1.45rem;
    line-height: 1.3;
    margin-bottom: 1rem;
    letter-spacing: -0.01em;
  }

  dl.meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10.5rem, 1fr));
    gap: 0.75rem 1.5rem;
    font-size: 0.875rem;
  }

  dl.meta dt {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.1rem;
  }

  dl.meta dd { font-weight: 500; }

  .meta-wide { grid-column: 1 / -1; }

  .participants { display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center; }

  .chip {
    display: inline-block;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.1rem 0.55rem;
    border-radius: 999px;
    border: 1px solid transparent;
  }
  .chip.claude {
    color: var(--claude-accent-strong);
    background: var(--claude-tint);
    border-color: var(--claude-accent);
  }
  .chip.codex {
    color: var(--codex-accent-strong);
    background: var(--codex-tint);
    border-color: var(--codex-accent);
  }

  .status-pill {
    display: inline-block;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.1rem 0.6rem;
    border-radius: 999px;
    background: var(--verdict-tint);
    border: 1px solid var(--border);
  }

  .template-note {
    font-size: 0.8rem;
    color: var(--text-muted);
    border: 1px dashed var(--border);
    border-radius: 10px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 2rem;
  }

  /* ---------- Status chips (accepted / rejected / unresolved) ---------- */
  .status-chip {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.08rem 0.5rem;
    border-radius: 999px;
    border: 1px solid transparent;
    white-space: nowrap;
  }
  .status-chip.accepted   { color: var(--ok-text);   background: var(--ok-bg);   border-color: var(--ok-border); }
  .status-chip.rejected   { color: var(--no-text);   background: var(--no-bg);   border-color: var(--no-border); }
  .status-chip.unresolved { color: var(--open-text); background: var(--open-bg); border-color: var(--open-border); }

  /* ---------- Lock / session badges ---------- */
  .lock-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.12rem 0.6rem;
    border-radius: 999px;
    background: var(--verdict-tint);
    border: 1px solid var(--border);
    color: var(--text-muted);
  }
  .lock-badge .lock-glyph { font-size: 0.85em; }

  .session-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.12rem 0.6rem;
    border-radius: 999px;
    color: var(--codex-accent-strong);
    background: var(--codex-tint);
    border: 1px dashed var(--codex-accent);
  }

  /* ---------- Panels (pre-registered, verdict, etc.) ---------- */
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
  }

  .panel-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .panel-head .speaker {
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .panel.claude-panel {
    border-left: 4px solid var(--claude-accent);
    background: var(--claude-tint);
  }
  .panel.claude-panel .speaker { color: var(--claude-accent-strong); }

  .panel.codex-panel {
    border-left: 4px solid var(--codex-accent);
    background: var(--codex-tint);
  }
  .panel.codex-panel .speaker { color: var(--codex-accent-strong); }

  .finding-list { margin: 0 0 0 1.25rem; font-size: 0.93rem; }
  .finding-list li { margin-bottom: 0.4rem; }
  .finding-list li:last-child { margin-bottom: 0; }
  .finding-id { font-weight: 700; }

  /* ---------- Blind commit: two locked columns ---------- */
  .blind-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
    gap: 1rem;
  }

  .overlap-note {
    margin-top: 0.75rem;
    font-size: 0.83rem;
    color: var(--text-muted);
  }

  /* ---------- Rounds ---------- */
  .round { margin-bottom: 2.25rem; }
  .round:last-child { margin-bottom: 0; }

  .round-separator {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 0 0 1.1rem;
    color: var(--text-muted);
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .round-separator::before,
  .round-separator::after {
    content: "";
    flex: 1;
    border-top: 1px solid var(--border);
  }

  /* ---------- Messages ---------- */
  article.message {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left-width: 4px;
    border-radius: 10px;
    padding: 1rem 1.25rem 1.1rem;
    margin-bottom: 1rem;
  }

  article.message.claude {
    border-left-color: var(--claude-accent);
    background: var(--claude-tint);
  }
  article.message.codex {
    border-left-color: var(--codex-accent);
    background: var(--codex-tint);
  }

  article.message.fresh {
    border-style: dashed;
    border-left-style: solid;
  }

  .message-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .speaker {
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  .message.claude .speaker { color: var(--claude-accent-strong); }
  .message.codex .speaker { color: var(--codex-accent-strong); }

  .role-tag {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .message-head .status-chip { margin-left: auto; }

  .message p { margin-bottom: 0.65rem; font-size: 0.95rem; }
  .message p:last-child { margin-bottom: 0; }

  .message ul {
    margin: 0 0 0.65rem 1.25rem;
    font-size: 0.95rem;
  }
  .message li { margin-bottom: 0.25rem; }

  code {
    font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
    font-size: 0.85em;
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.06em 0.3em;
  }

  .codeblock {
    overflow-x: auto;
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin: 0.35rem 0 0.75rem;
  }
  .codeblock pre {
    padding: 0.8rem 1rem;
    font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
    font-size: 0.82rem;
    line-height: 1.5;
    white-space: pre;
  }
  .codeblock code {
    background: none;
    border: none;
    padding: 0;
    font-size: inherit;
  }

  /* ---------- Ruling ledger ---------- */
  .ledger-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 4px solid var(--claude-accent);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
  }

  .ledger-scroll { overflow-x: auto; }

  table.ledger {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
    min-width: 34rem;
  }

  table.ledger th {
    text-align: left;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    padding: 0.4rem 0.75rem 0.4rem 0;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
  }

  table.ledger td {
    padding: 0.55rem 0.75rem 0.55rem 0;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  table.ledger tr:last-child td { border-bottom: none; }
  table.ledger td.num { font-weight: 700; white-space: nowrap; }
  table.ledger td.round-col { white-space: nowrap; }
  table.ledger td .status-chip { margin-top: 0.05rem; }

  .ledger-tally {
    margin-top: 0.8rem;
    font-size: 0.83rem;
    color: var(--text-muted);
  }

  /* ---------- Verdict ---------- */
  .verdict {
    background: var(--verdict-tint);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
  }

  .verdict h3 {
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin: 1rem 0 0.4rem;
  }
  .verdict h3:first-child { margin-top: 0; }

  .verdict ul { margin-left: 1.25rem; font-size: 0.93rem; }
  .verdict li { margin-bottom: 0.35rem; }
  .verdict .attribution { color: var(--text-muted); font-size: 0.85em; }

  .da-subblock {
    margin-top: 1.25rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 4px solid var(--claude-accent);
    border-radius: 10px;
    padding: 1rem 1.25rem;
  }
  .da-subblock .da-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }
  .da-subblock .da-title {
    font-size: 0.9rem;
    font-weight: 700;
  }
  .da-subblock p, .da-subblock ul { font-size: 0.9rem; }
  .da-subblock ul { margin-left: 1.25rem; }
  .da-subblock li { margin-bottom: 0.3rem; }

  /* ---------- Fresh-eyes ---------- */
  .fresh-eyes-wrap {
    border: 1px dashed var(--codex-accent);
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
  }
  .fresh-eyes-wrap .fresh-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  .fresh-eyes-wrap .fresh-head .speaker { color: var(--codex-accent-strong); }
  .fresh-eyes-wrap article.message:last-child { margin-bottom: 0; }

  footer.page-footer {
    margin-top: 2rem;
    text-align: center;
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  @media (max-width: 30rem) {
    body { padding: 1rem 0.6rem 3rem; }
    .report-header { padding: 1.1rem 1.1rem; }
    article.message { padding: 0.85rem 0.9rem 0.95rem; }
    .panel { padding: 1rem 1rem; }
    .verdict { padding: 1.1rem 1.1rem; }
    .fresh-eyes-wrap { padding: 0.9rem 0.9rem; }
  }
"""


class ReportError(Exception):
    """Malformed or unsupported input; the report is never partially emitted."""


def esc(value):
    return html.escape(str(value), quote=True)


# ---------------------------------------------------------------- validation

def validate(data):
    """Gate on schemaVersion, then enforce the JSON Schema file in full."""
    if not isinstance(data, dict):
        raise ReportError("top level must be a JSON object")
    version = data.get("schemaVersion")
    if version != SCHEMA_VERSION:
        raise ReportError(
            f"unsupported schemaVersion {version!r}; this renderer supports {SCHEMA_VERSION}"
        )
    schema = validate_debate_report.load_schema(SCHEMA_PATH)
    violations = validate_debate_report.validate(data, schema)
    if violations:
        raise ReportError("input does not match the schema:\n  " + "\n  ".join(violations))


# ---------------------------------------------------------------- rendering

def format_date(iso_date):
    year, month, day = int(iso_date[0:4]), int(iso_date[5:7]), int(iso_date[8:10])
    return f"{MONTHS[month - 1]} {day}, {year}"


def render_blocks(blocks):
    out = []
    for block in blocks:
        if block["type"] == "paragraph":
            out.append(f"          <p>{esc(block['text'])}</p>")
        elif block["type"] == "list":
            items = "".join(f"\n            <li>{esc(item)}</li>" for item in block["items"])
            out.append(f"          <ul>{items}\n          </ul>")
        elif block["type"] == "code":
            out.append(
                "          <div class=\"codeblock\"><pre><code>"
                f"{esc(block['code'])}</code></pre></div>"
            )
    return "\n".join(out)


def render_message(msg):
    label, css_class = SPEAKERS[msg["speaker"]]
    head = [
        f'            <span class="speaker">{esc(label)}</span>',
        f'            <span class="role-tag">{esc(msg["role"])}</span>',
    ]
    objection = msg.get("objection")
    if objection is not None:
        status = objection["status"]
        head.append(
            f'            <span class="status-chip {status}">{STATUS_LABEL[status]}</span>'
        )
    head_html = "\n".join(head)
    return (
        f'        <article class="message {css_class}">\n'
        f'          <div class="message-head">\n{head_html}\n          </div>\n'
        f"{render_blocks(msg['content'])}\n"
        f"        </article>"
    )


def render_finding_list(findings):
    items = "\n".join(
        f'            <li><span class="finding-id">{esc(f["id"])}.</span> {esc(f["text"])}</li>'
        for f in findings
    )
    return f'          <ol class="finding-list">\n{items}\n          </ol>'


def render_locked_panel(speaker, role, lock_label, findings, indent=""):
    label, _ = SPEAKERS[speaker]
    return (
        f'{indent}        <div class="panel {PANEL_CLASS[speaker]}">\n'
        f'{indent}          <div class="panel-head">\n'
        f'{indent}            <span class="speaker">{esc(label)}</span>\n'
        f'{indent}            <span class="role-tag">{esc(role)}</span>\n'
        f'{indent}            <span class="lock-badge"><span class="lock-glyph" '
        f'aria-hidden="true">\U0001f512</span> {esc(lock_label)}</span>\n'
        f"{indent}          </div>\n"
        f"{render_finding_list(findings)}\n"
        f"{indent}        </div>"
    )


def render_header(data):
    parts = []
    for i, participant in enumerate(data["participants"]):
        if i > 0:
            parts.append('            <span aria-hidden="true">vs</span>')
        label, _ = SPEAKERS[participant]
        parts.append(f'            <span class="chip {participant}">{esc(label)}</span>')
    participants_html = "\n".join(parts)

    rows = [
        "        <div>",
        "          <dt>Date</dt>",
        f'          <dd><time datetime="{esc(data["date"])}">{esc(format_date(data["date"]))}</time></dd>',
        "        </div>",
        "        <div>",
        "          <dt>Participants</dt>",
        '          <dd class="participants">',
        participants_html,
        "          </dd>",
        "        </div>",
        "        <div>",
        "          <dt>Shape</dt>",
        f"          <dd>{esc(data['shape'])}</dd>",
        "        </div>",
        "        <div>",
        "          <dt>Mode</dt>",
        f"          <dd>{esc(data['mode'])}</dd>",
        "        </div>",
        "        <div>",
        "          <dt>Rigor</dt>",
        f"          <dd>{esc(data['rigor'])}</dd>",
        "        </div>",
        "        <div>",
        "          <dt>Round cap</dt>",
        f"          <dd>{esc(data['roundCap'])}</dd>",
        "        </div>",
        '        <div class="meta-wide">',
        "          <dt>Termination</dt>",
        f'          <dd><span class="status-pill">{esc(data["termination"])}</span></dd>',
        "        </div>",
    ]
    if data["bindingAnchor"] is not None:
        rows += [
            '        <div class="meta-wide">',
            "          <dt>Binding anchor</dt>",
            f"          <dd>{esc(data['bindingAnchor'])}</dd>",
            "        </div>",
        ]
    rows_html = "\n".join(rows)
    return (
        '    <header class="report-header">\n'
        '      <p class="kicker">codex-debate · debate report</p>\n'
        f"      <h1>{esc(data['subject'])}</h1>\n"
        '      <dl class="meta">\n'
        f"{rows_html}\n"
        "      </dl>\n"
        "    </header>"
    )


def render_pre_registered(pre):
    return (
        '      <section class="block" aria-labelledby="prereg-title">\n'
        '        <div class="section-head">\n'
        '          <h2 id="prereg-title">Pre-registered assessment</h2>\n'
        "        </div>\n"
        f"{render_locked_panel(pre['speaker'], pre['role'], pre['lockLabel'], pre['findings'])}\n"
        "      </section>"
    )


def render_blind_commit(blind):
    columns = "\n".join(
        render_locked_panel(
            col["speaker"], col["role"], col["lockLabel"], col["findings"], indent="  "
        )
        for col in blind["columns"]
    )
    overlap = ""
    if "overlapNote" in blind:
        overlap = f'\n        <p class="overlap-note">{esc(blind["overlapNote"])}</p>'
    return (
        '      <section class="block" aria-labelledby="blind-title">\n'
        '        <div class="section-head">\n'
        '          <h2 id="blind-title">Blind commit</h2>\n'
        "        </div>\n"
        '        <div class="blind-grid">\n'
        f"{columns}\n"
        f"        </div>{overlap}\n"
        "      </section>"
    )


def render_rounds(data):
    round_cap = data["roundCap"]
    sections = []
    for i, rnd in enumerate(data["rounds"], start=1):
        messages = "\n".join(render_message(msg) for msg in rnd["messages"])
        sections.append(
            f'      <section class="round" aria-labelledby="round-{i}">\n'
            f'        <h3 class="round-separator" id="round-{i}">Round {i} of {round_cap}</h3>\n'
            f"{messages}\n"
            "      </section>"
        )
    rounds_html = "\n\n".join(sections)
    return (
        '      <section class="block" aria-labelledby="rounds-title">\n'
        '        <div class="section-head">\n'
        '          <h2 id="rounds-title">Debate rounds</h2>\n'
        "        </div>\n"
        f"{rounds_html}\n"
        "      </section>"
    )


def derive_ledger(data):
    """Single source of truth: ledger rows come from objection entries on the
    messages in rounds (in order), then fresh-eyes messages."""
    rows = []
    for i, rnd in enumerate(data["rounds"], start=1):
        for msg in rnd["messages"]:
            if "objection" in msg:
                rows.append({"round": str(i), "fresh": False, **msg["objection"]})
    if "freshEyes" in data:
        for msg in data["freshEyes"]["messages"]:
            if "objection" in msg:
                rows.append({"round": "Fresh eyes", "fresh": True, **msg["objection"]})
    return rows


def render_ledger(data):
    rows = derive_ledger(data)
    body = []
    for row in rows:
        status = row["status"]
        body.append(
            "              <tr>\n"
            f'                <td class="num">{esc(row["id"])}</td>\n'
            f"                <td>{esc(row['title'])}</td>\n"
            f'                <td class="round-col">{esc(row["round"])}</td>\n'
            f'                <td><span class="status-chip {status}">{STATUS_LABEL[status]}</span></td>\n'
            f"                <td>{esc(row['reason'])}</td>\n"
            "              </tr>"
        )
    body_html = "\n".join(body)

    counts = {status: 0 for status in STATUSES}
    for row in rows:
        counts[row["status"]] += 1
    tally = (
        f"Tally: {counts['accepted']} accepted · {counts['rejected']} rejected "
        f"· {counts['unresolved']} unresolved"
    )
    open_labels = [
        ("fresh-eyes finding " + row["id"]) if row["fresh"] else ("objection #" + row["id"])
        for row in rows
        if row["status"] == "unresolved"
    ]
    if open_labels:
        if len(open_labels) == 1:
            joined = open_labels[0]
        else:
            joined = ", ".join(open_labels[:-1]) + " and " + open_labels[-1]
        tally += f" ({joined})"
    tally += "."

    return (
        '      <section class="block" aria-labelledby="ledger-title">\n'
        '        <div class="section-head">\n'
        '          <h2 id="ledger-title">Ruling ledger</h2>\n'
        "        </div>\n"
        '        <div class="ledger-panel">\n'
        '          <div class="ledger-scroll">\n'
        '            <table class="ledger">\n'
        "              <thead>\n"
        "                <tr>\n"
        '                  <th scope="col">#</th>\n'
        '                  <th scope="col">Objection</th>\n'
        '                  <th scope="col">Round</th>\n'
        '                  <th scope="col">Status</th>\n'
        '                  <th scope="col">Reason</th>\n'
        "                </tr>\n"
        "              </thead>\n"
        "              <tbody>\n"
        f"{body_html}\n"
        "              </tbody>\n"
        "            </table>\n"
        "          </div>\n"
        f'          <p class="ledger-tally">{esc(tally)}</p>\n'
        "        </div>\n"
        "      </section>"
    )


def render_verdict_items(items):
    out = []
    for item in items:
        text = esc(item["text"])
        if "attribution" in item:
            text += f' <span class="attribution">{esc(item["attribution"])}</span>'
        out.append(f"            <li>{text}</li>")
    return "\n".join(out)


def render_verdict(verdict):
    da_html = ""
    if "devilsAdvocate" in verdict:
        da = verdict["devilsAdvocate"]
        points = []
        for point in da["points"]:
            if "label" in point:
                points.append(
                    f"              <li><strong>{esc(point['label'])}:</strong> "
                    f"{esc(point['text'])}</li>"
                )
            else:
                points.append(f"              <li>{esc(point['text'])}</li>")
        points_html = "\n".join(points)
        da_html = (
            "\n"
            '          <div class="da-subblock">\n'
            '            <div class="da-head">\n'
            f'              <span class="da-title">{esc(da["title"])}</span>\n'
            f'              <span class="status-pill">{esc(da["outcome"])}</span>\n'
            "            </div>\n"
            f"            <p>{esc(da['intro'])}</p>\n"
            "            <ul>\n"
            f"{points_html}\n"
            "            </ul>\n"
            "          </div>"
        )
    return (
        '      <section class="block" aria-labelledby="verdict-title">\n'
        '        <div class="section-head">\n'
        '          <h2 id="verdict-title">Consensus / Verdict</h2>\n'
        "        </div>\n"
        '        <div class="verdict">\n'
        "          <h3>Agreed</h3>\n"
        "          <ul>\n"
        f"{render_verdict_items(verdict['agreed'])}\n"
        "          </ul>\n"
        "\n"
        "          <h3>Unresolved</h3>\n"
        "          <ul>\n"
        f"{render_verdict_items(verdict['unresolved'])}\n"
        f"          </ul>{da_html}\n"
        "        </div>\n"
        "      </section>"
    )


def render_fresh_eyes(fresh):
    label, _ = SPEAKERS[fresh["speaker"]]
    messages = "\n".join(render_message(msg) for msg in fresh["messages"])
    return (
        '      <section class="block" aria-labelledby="fresh-title">\n'
        '        <div class="section-head">\n'
        '          <h2 id="fresh-title">Fresh-eyes verdict</h2>\n'
        "        </div>\n"
        '        <div class="fresh-eyes-wrap">\n'
        '          <div class="fresh-head">\n'
        f'            <span class="speaker">{esc(label)}</span>\n'
        f'            <span class="session-badge">{esc(fresh["sessionBadge"])}</span>\n'
        f'            <span class="role-tag">{esc(fresh["role"])}</span>\n'
        "          </div>\n"
        f"{messages}\n"
        "        </div>\n"
        "      </section>"
    )


def render_footer(data):
    n = len(data["rounds"])
    passes = f"{n} round{'' if n == 1 else 's'}"
    if "freshEyes" in data:
        passes += " + fresh-eyes pass"
    return (
        '    <footer class="page-footer">\n'
        f"      <p>Generated by the codex-debate skill · {esc(passes)} · "
        "Codex (OpenAI) prosecuting, Claude (Anthropic) ruling</p>\n"
        "      <p>Transcripts and the Codex session persist until removed — "
        "see the run report for paths.</p>\n"
        "    </footer>"
    )


def make_island(data):
    """Serialize the input exactly (order preserved) and make it inert inside
    a <script> element: '</' becomes '<\\/', which is invisible to JSON once
    reversed and prevents any '</script>' from terminating the island."""
    return json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")


def unescape_island(text):
    return text.replace("<\\/", "</")


def extract_island(html_text):
    start = html_text.find(ISLAND_OPEN)
    if start == -1:
        raise ReportError("data island not found in rendered output")
    start += len(ISLAND_OPEN)
    end = html_text.find(ISLAND_CLOSE, start)
    if end == -1:
        raise ReportError("data island is not terminated in rendered output")
    return html_text[start:end].strip("\n")


def render(data):
    sections = []
    if "preRegistered" in data:
        sections.append(render_pre_registered(data["preRegistered"]))
    if "blindCommit" in data:
        sections.append(render_blind_commit(data["blindCommit"]))
    sections.append(render_rounds(data))
    sections.append(render_ledger(data))
    sections.append(render_verdict(data["verdict"]))
    if "freshEyes" in data:
        sections.append(render_fresh_eyes(data["freshEyes"]))
    main_html = "\n\n".join(sections)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(data['subject'])}</title>\n"
        "<style>\n"
        f"{CSS}"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="page">\n'
        "\n"
        f"{render_header(data)}\n"
        "\n"
        "  <main>\n"
        "\n"
        f"{main_html}\n"
        "\n"
        "  </main>\n"
        "\n"
        f"{render_footer(data)}\n"
        "\n"
        "</div>\n"
        f"{ISLAND_OPEN}\n"
        f"{make_island(data)}\n"
        f"{ISLAND_CLOSE}\n"
        "</body>\n"
        "</html>\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Render a codex-debate report from JSON to self-contained HTML."
    )
    parser.add_argument("input", help="path to the debate-report JSON file")
    parser.add_argument("-o", "--output", required=True, help="path to write the HTML report")
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    out_path = Path(args.output)

    try:
        raw = in_path.read_text(encoding="utf-8")
    except OSError as err:
        print(f"error: cannot read {in_path}: {err}", file=sys.stderr)
        return 2

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as err:
        print(f"error: {in_path} is not valid JSON: {err}", file=sys.stderr)
        return 2

    try:
        validate(data)
        rendered = render(data)
    except (ReportError, validate_debate_report.SchemaError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    out_path.write_text(rendered, encoding="utf-8")

    # Built-in integrity check: the island in the file we just wrote must
    # round-trip to exactly the input we parsed.
    written = out_path.read_text(encoding="utf-8")
    try:
        island = extract_island(written)
        round_tripped = json.loads(unescape_island(island))
    except (ReportError, json.JSONDecodeError) as err:
        print(f"error: data-island integrity check failed: {err}", file=sys.stderr)
        return 3
    if round_tripped != data:
        print(
            "error: data-island integrity check failed: "
            "round-tripped island differs from input",
            file=sys.stderr,
        )
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
