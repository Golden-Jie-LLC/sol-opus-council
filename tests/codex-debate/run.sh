#!/usr/bin/env bash
# Run a codex-debate skill test scenario against a headless Claude agent.
# Usage: run.sh <scenario> [--red] [--keep] [--model <model>]
#   --red   run the RED baseline: temporarily mask the codex-debate personal
#           skill so the agent works from scratch. Checks are expected to fail;
#           the point is recording baseline behavior.
#   --keep  keep the workdir even when checks pass (default: passing runs are
#           deleted, failing runs are kept for debugging).
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
SCENARIO="${1:?usage: run.sh <scenario> [--red] [--keep] [--model <model>]}"
shift
RED=0
KEEP=0
MODEL="sonnet"
while [ $# -gt 0 ]; do
    case "$1" in
        --red) RED=1 ;;
        --keep) KEEP=1 ;;
        --model)
            shift
            MODEL="$1"
            ;;
        *)
            echo "unknown arg: $1" >&2
            exit 2
            ;;
    esac
    shift
done

SDIR="$HERE/scenarios/$SCENARIO"
[ -d "$SDIR" ] || {
    echo "no such scenario: $SCENARIO" >&2
    exit 2
}

WD="$(mktemp -d)"
mkdir -p "$WD/stublog" "$WD/work" "$WD/bin"
[ -f "$SDIR/subject.md" ] && cp "$SDIR/subject.md" "$WD/work/subject.md"
[ -d "$SDIR/work" ] && cp -r "$SDIR/work/." "$WD/work/"
# Stage the stub and replies into the workdir so no env var or PATH entry
# points back into this repo (a resourceful baseline agent will follow them).
cp "$HERE/bin/codex" "$WD/bin/codex"
cp -r "$SDIR/replies" "$WD/replies"

# RED skill suppression: --disable-slash-commands empties the session's skill
# listing without touching any on-disk state (no masking, no restore trap).
# On-disk copies (repo checkouts) remain readable, so RED tasks also carry the
# task-red.md "don't read skill files" line, and the post-run contamination
# check below verifies compliance from the transcript.
RED_FLAGS=""
if [ "$RED" = 1 ]; then
    RED_FLAGS="--disable-slash-commands"
fi

echo "workdir: $WD  (mode: $([ "$RED" = 1 ] && echo RED || echo GREEN), model: $MODEL)"

TASK="$SDIR/task.md"
if [ "$RED" = 1 ] && [ -f "$SDIR/task-red.md" ]; then
    TASK="$SDIR/task-red.md"
fi

set +e
(
    cd "$WD/work" &&
        PATH="$WD/bin:$PATH" \
            STUB_LOG="$WD/stublog" \
            STUB_REPLIES="$WD/replies" \
            claude -p "$(cat "$TASK")" \
            --model "$MODEL" \
            --allowedTools 'Bash,Read,Write,Edit,Glob,Grep,Skill' \
            $RED_FLAGS
) > "$WD/agent-output.md" 2> "$WD/agent-stderr.txt"
AGENT_RC=$?
set -e

# The session transcript is the only place intermediate assistant text (e.g.
# the per-round status lines) is recorded: `claude -p` prints only the final
# message. Export it into the workdir so scenario checks can read it.
slug=$(printf '%s' "$WD/work" | tr '/.' '--')
mkdir -p "$WD/transcript"
cp "$HOME/.claude/projects/$slug/"*.jsonl "$WD/transcript/" 2> /dev/null || true

# RED contamination detection: masking can't hide repo checkouts, so verify
# from the session transcript that the agent never read a skill copy.
if [ "$RED" = 1 ]; then
    if grep -rql 'skills/codex-debate' "$HOME/.claude/projects/$slug/" 2> /dev/null; then
        echo "CONTAMINATED: baseline agent read a codex-debate skill copy (see transcript in ~/.claude/projects/$slug/)" >&2
        echo "workdir kept: $WD"
        exit 3
    fi
fi

echo "agent rc: $AGENT_RC  (output: $WD/agent-output.md)"
echo "---- checks ----"
set +e
bash "$SDIR/checks.sh" "$WD"
CHECK_RC=$?
set -e
if [ "$CHECK_RC" -eq 0 ] && [ "$KEEP" -eq 0 ]; then
    rm -rf "$WD"
    echo "workdir cleaned (passed; use --keep to retain)"
else
    echo "workdir kept: $WD"
fi
exit $CHECK_RC
