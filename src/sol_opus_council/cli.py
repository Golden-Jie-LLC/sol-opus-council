"""Internal deterministic CLI used by the two Codex skills."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .artifacts import RunArtifacts
from .claude_cli import ClaudeCLIAdapter, find_claude_command
from .doctor import diagnose
from .errors import CouncilError
from .installer import install, uninstall
from .protocol import CouncilCoordinator, CouncilMode
from .util import canonical_json, default_runs_root


def _print_json(value: dict[str, Any]) -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="strict")
    print(canonical_json(value), end="")


def _json_file(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CouncilError(f"expected JSON object: {path}")
    return value


def _adapter(args: argparse.Namespace, run: RunArtifacts) -> ClaudeCLIAdapter:
    command = find_claude_command(args.claude)
    return ClaudeCLIAdapter(
        command,
        run.root,
        timeout_seconds=args.timeout,
        transient_retries=args.transient_retries,
        malformed_retries=1,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sol-opus-council")
    sub = parser.add_subparsers(dest="command", required=True)

    begin = sub.add_parser("begin")
    begin.add_argument("--mode", required=True, choices=[mode.value for mode in CouncilMode])
    begin.add_argument("--request-file", required=True)
    begin.add_argument("--context-json")
    begin.add_argument("--repo-root")
    begin.add_argument("--runs-root")

    revise = sub.add_parser("revise-context")
    revise.add_argument("--run", required=True)
    revise.add_argument("--request-file", required=True)
    revise.add_argument("--context-json", required=True)
    revise.add_argument("--repo-root")

    lock = sub.add_parser("lock-sol")
    lock.add_argument("--run", required=True)
    lock.add_argument("--input", required=True)

    for name in ("opus-initial", "review"):
        call = sub.add_parser(name)
        call.add_argument("--run", required=True)
        call.add_argument("--claude")
        call.add_argument("--timeout", type=float, default=300)
        call.add_argument("--transient-retries", type=int, default=2)
        if name == "review":
            call.add_argument("--candidate", required=True)
            call.add_argument("--sol-ready", action="store_true")
            call.add_argument("--rulings-json")

    status = sub.add_parser("status")
    status.add_argument("--run", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--claude")

    install_parser = sub.add_parser("install")
    install_parser.add_argument("--scope", choices=["repo", "user"], required=True)
    install_parser.add_argument("--repo")
    install_parser.add_argument("--source-root")

    uninstall_parser = sub.add_parser("uninstall")
    uninstall_parser.add_argument("--scope", choices=["repo", "user"], required=True)
    uninstall_parser.add_argument("--repo")
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "begin":
        request = Path(args.request_file).read_text(encoding="utf-8")
        coordinator = CouncilCoordinator.begin(
            mode=CouncilMode(args.mode),
            request=request,
            runs_root=Path(args.runs_root) if args.runs_root else default_runs_root(),
            context=_json_file(args.context_json),
            repo_root=Path(args.repo_root) if args.repo_root else None,
        )
        state = coordinator.artifacts.state()
        return {
            "run_dir": str(coordinator.artifacts.root),
            "context_hash": state["context_hash"],
            "context_version": state["context_version"],
        }
    if args.command == "revise-context":
        coordinator = CouncilCoordinator(RunArtifacts.open(Path(args.run)))
        digest = coordinator.revise_context(
            request=Path(args.request_file).read_text(encoding="utf-8"),
            context=_json_file(args.context_json),
            repo_root=Path(args.repo_root) if args.repo_root else None,
        )
        return {"context_hash": digest, "state": coordinator.artifacts.state()}
    if args.command == "lock-sol":
        coordinator = CouncilCoordinator(RunArtifacts.open(Path(args.run)))
        digest = coordinator.lock_sol_initial(Path(args.input).read_text(encoding="utf-8"))
        return {"sol_initial_hash": digest, "state": coordinator.artifacts.state()}
    if args.command == "opus-initial":
        run = RunArtifacts.open(Path(args.run))
        result = CouncilCoordinator(run).opus_initial(_adapter(args, run))
        return {
            "context_status": result.structured_output["context_status"],
            "missing_context": result.structured_output["missing_context"],
            "session_id": result.session_id,
            "state": run.state(),
        }
    if args.command == "review":
        run = RunArtifacts.open(Path(args.run))
        rulings_value = _json_file(args.rulings_json) if args.rulings_json else {}
        rulings = rulings_value.get("rulings", [])
        return CouncilCoordinator(run).review(
            candidate=Path(args.candidate).read_text(encoding="utf-8"),
            sol_ready=bool(args.sol_ready),
            adapter=_adapter(args, run),
            rulings=rulings,
        )
    if args.command == "status":
        return RunArtifacts.open(Path(args.run)).state()
    if args.command == "doctor":
        try:
            command = find_claude_command(args.claude)
        except CouncilError:
            command = None
        return diagnose(command)
    if args.command == "install":
        return install(
            args.scope,
            Path(args.repo) if args.repo else None,
            Path(args.source_root) if args.source_root else None,
        )
    if args.command == "uninstall":
        return uninstall(args.scope, Path(args.repo) if args.repo else None)
    raise AssertionError(args.command)


def main(argv: list[str] | None = None) -> int:
    try:
        result = execute(build_parser().parse_args(argv))
    except (CouncilError, OSError, ValueError, json.JSONDecodeError) as exc:
        _print_json({"ok": False, "error": type(exc).__name__, "message": str(exc)})
        return 1
    _print_json({"ok": True, "result": result})
    return 0


if __name__ == "__main__":
    sys.exit(main())
