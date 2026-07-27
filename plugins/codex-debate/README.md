# Codex Debate

Claude Code skills that get you a second opinion from an independent AI agent. Current skills:

- **codex-debate**: an iterative adversarial debate between Claude (leading agent) and the headless [Codex CLI](https://github.com/openai/codex) over a spec, design, plan, document, position, refactoring, or codebase, running to convergence or a round cap.

## Installation

```text
/plugin marketplace add octanevz/codex-debate
/plugin install codex-debate@octanevz
```

The codex-debate skill additionally requires the `codex` CLI to be installed and logged in; Codex access requires a ChatGPT plan that includes Codex or a funded OpenAI API account.

## Security and cost notes for codex-debate

- Codex is always run strictly read-only (sandboxed, approvals off): it never modifies files; Claude reviews every suggestion and applies accepted changes itself. That guarantee covers Codex's own commands; MCP servers and hooks you have configured for Codex yourself run outside the sandbox and remain your own trust decision.
- Debates call the external Codex CLI: OpenAI-side usage costs apply, and debated content (inlined subjects or files Codex reads from your repository) is sent to OpenAI.
- Debate transcripts are written to a temporary directory, and Codex durably stores its session under the active Codex home (`$CODEX_HOME`, default `~/.codex`) until deleted; the skill discloses both and cleans them up on request.

Full documentation, worked examples, and the compliance test suite live in the [repository](https://github.com/octanevz/codex-debate).
