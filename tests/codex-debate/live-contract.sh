#!/usr/bin/env bash
# Contract check against the REAL Codex CLI: does the canonical fragment
# wording actually make Codex obey the mechanical reply contract?
#
# Sends the assembled advisory round-1 prompt N times and asserts, per reply:
#   - exactly one line starts with VERDICT:
#   - it is the last non-empty line, with exact grammar
#   - objections are numbered
#   - word count within tolerance (round 1 may exceed the ~400 cap to
#     enumerate; > 900 words is a warning, not a failure)
#
# Slow and nondeterministic by nature: run after editing a prompt fragment or
# upgrading the Codex CLI/model — not as part of the stub suite.
# Usage: live-contract.sh [N]   (default 3 calls)
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
FRAG="$HERE/../../plugins/codex-debate/skills/codex-debate/references/prompts"
SUBJECT="$HERE/scenarios/advisory-happy/subject.md"
[ -d "$FRAG" ] || {
    echo "prompt fragment directory not found: $FRAG" >&2
    exit 2
}
N="${1:-3}"

command -v codex > /dev/null || {
    echo "real codex CLI not found on PATH" >&2
    exit 2
}
case "$(command -v codex)" in
    /tmp/*)
        echo "refusing to run: codex on PATH looks like a test stub" >&2
        exit 2
        ;;
esac

WD="$(mktemp -d)"
strip() { sed '/^<!--/d' "$1"; }

{
    strip "$FRAG/role-and-rules.md"
    echo
    strip "$FRAG/advisory-inline-extras.md"
    echo
    echo "Attack the weakest claims of the position below; where a claim overreaches the evidence, say exactly how."
    echo
    strip "$FRAG/fenced-subject.md" |
        sed -e 's/{{LABEL}}/ARTIFACT v1/g' \
            -e "/{{SUBJECT}}/r $SUBJECT" -e '/{{SUBJECT}}/d'
} > "$WD/p1.md"

if grep -q '{{' "$WD/p1.md"; then
    echo "FAIL - assembled prompt contains unresolved {{slot}} tokens" >&2
    exit 1
fi

pass=0
fail=0
warn=0
check() {
    if [ "$2" -eq 0 ]; then
        echo "ok   - $1"
        pass=$((pass + 1))
    else
        echo "FAIL - $1"
        fail=$((fail + 1))
    fi
}

check_that() { # check_that <name> <command...>: condition runs as a command
    local name="$1"
    shift
    if "$@"; then
        check "$name" 0
    else
        check "$name" 1
    fi
}

for i in $(seq 1 "$N"); do
    echo "== live call $i/$N =="
    set +e
    codex exec --skip-git-repo-check -s read-only -o "$WD/r$i.md" - \
        < "$WD/p1.md" > "$WD/log$i.txt" 2>&1
    rc=$?
    set -e
    check "call $i exits 0" "$rc"
    check_that "call $i reply non-empty" [ -s "$WD/r$i.md" ]
    [ -s "$WD/r$i.md" ] || continue

    R="$WD/r$i.md"
    vcount=$(grep -c '^VERDICT:' "$R" || true)
    check_that "call $i has exactly one VERDICT line (got $vcount)" [ "$vcount" -eq 1 ]
    last=$(grep -v '^[[:space:]]*$' "$R" | tail -1)
    printf '%s' "$last" | grep -qE '^VERDICT: (AGREEMENT|DISPUTE REMAINS)$'
    check "call $i verdict is last non-empty line with exact grammar" $?
    grep -qE '^[[:space:]]*1[.)]' "$R"
    check "call $i objections are numbered" $?
    words=$(wc -w < "$R")
    if [ "$words" -gt 900 ]; then
        echo "warn - call $i reply is $words words (cap tolerance exceeded)"
        warn=$((warn + 1))
    fi
done

echo "----"
echo "passed=$pass failed=$fail warnings=$warn  (transcripts: $WD)"
[ "$fail" -eq 0 ]
