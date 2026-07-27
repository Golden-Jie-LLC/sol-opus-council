#!/usr/bin/env bash
# Measure whether the codex-debate skill triggers (is invoked) for
# representative prompts. Compliance scenarios test behavior after invocation;
# this suite tests routing: each case runs N fresh headless sessions with only
# Skill+Read allowed (nothing real executes) and checks the session transcript
# for a skill invocation.
# Usage: run.sh [case ...] [--reps N] [--model M]
#   cases default to every directory under cases/; expectation is the case's
#   `expect` file: "trigger" or "no-trigger".
# Routing is probabilistic, so each direction tolerates one contrary rep:
# trigger passes at >= REPS-1 hits, no-trigger at <= 1 hit. Calibration: the
# ungated description triggered delegation prompts at ~60% (3/5 recorded
# baseline); the gated one measures 0-10%. The thresholds separate those
# rates; they are not a guarantee of deterministic routing.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_MARKER='Launching skill: codex-debate'
REPS=5
MODEL="sonnet"
CASES=()
while [ $# -gt 0 ]; do
    case "$1" in
        --reps)
            shift
            REPS="$1"
            ;;
        --model)
            shift
            MODEL="$1"
            ;;
        *) CASES+=("$1") ;;
    esac
    shift
done
if [ "${#CASES[@]}" -eq 0 ]; then
    for d in "$HERE"/cases/*/; do CASES+=("$(basename "$d")"); done
fi

overall=0
for c in "${CASES[@]}"; do
    CDIR="$HERE/cases/$c"
    if [ ! -f "$CDIR/prompt.md" ] || [ ! -f "$CDIR/expect" ]; then
        echo "FAIL - $c: missing prompt.md or expect"
        overall=1
        continue
    fi
    expect=$(cat "$CDIR/expect")
    hits=0
    for _ in $(seq 1 "$REPS"); do
        WD=$(mktemp -d)
        [ -d "$CDIR/work" ] && cp -r "$CDIR/work/." "$WD/"
        (cd "$WD" && claude -p "$(cat "$CDIR/prompt.md")" \
            --model "$MODEL" --allowedTools 'Skill,Read' \
            > out.md 2> err.txt)
        slug=$(printf '%s' "$WD" | tr '/.' '--')
        if grep -rql "$SKILL_MARKER" "$HOME/.claude/projects/$slug/" 2> /dev/null; then
            hits=$((hits + 1))
        fi
        rm -rf "$WD"
    done
    case "$expect" in
        trigger) [ "$hits" -ge $((REPS - 1)) ] && ok=1 || ok=0 ;;
        no-trigger) [ "$hits" -le 1 ] && ok=1 || ok=0 ;;
        *)
            echo "FAIL - $c: bad expect value '$expect'"
            overall=1
            continue
            ;;
    esac
    if [ "$ok" = 1 ]; then
        echo "ok   - $c: $hits/$REPS invoked (expect $expect)"
    else
        echo "FAIL - $c: $hits/$REPS invoked (expect $expect)"
        overall=1
    fi
done
exit "$overall"
