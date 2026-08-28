# Changelog

## Unreleased

- Normalize canonical Draft 2020-12 schemas at the Claude Code provider
  boundary for Claude Code 2.1.247 while preserving host-side validation and
  all structural constraints.
- Record canonical/runtime schema identities and exact payload hashes per call,
  fail closed on unsupported schema constructs, and cover the observed CLI
  rejection with a deterministic regression fixture.
- Force UTF-8 CLI JSON output on Windows legacy consoles and document the
  narrow Claude transcript permission required for explicit session resume.

## 0.1.0 - 2026-08-28

- Reverse the host/peer architecture so Codex is the only UI and Claude Code
  Opus is the read-only peer.
- Add explicit-only QUESTION and PROMPT Codex skills.
- Add canonical context packets, blind initial positions, structured schemas,
  stable objection ledgers, bounded retries, and mode-specific early stopping.
- Add cross-platform Python install, uninstall, doctor, artifact, and Claude CLI
  tooling.
- Replace the Claude-hosted plugin tests with deterministic Python unit,
  protocol, integration, and installation tests on Windows and Linux.
