#!/usr/bin/env bash
# Mechanical assertions for creative-anchoring. Usage: checks.sh <workdir>
# The subject is a poem: inline claim numbering would distort the artifact,
# so the fenced copy must stay verbatim and objections must be anchorable by
# short quoted or structural anchors instead of claim numbers.
set -u
WD="${1:?usage: checks.sh <workdir>}"
LOG="$WD/stublog"
OUT="$WD/agent-output.md"
HERE="$(cd "$(dirname "$0")" && pwd)"
ORIG="$HERE/subject.md"
pass=0
fail=0

check() { # check <name> <condition-exit-code>
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

calls=$(find "$LOG" -maxdepth 1 -type d -name 'call-*' 2>/dev/null | wc -l)
check_that "exactly 2 codex calls (got $calls)" [ "$calls" -eq 2 ]

A1="$LOG/call-1/argv.txt"
A2="$LOG/call-2/argv.txt"
P1="$LOG/call-1/prompt.md"
P2="$LOG/call-2/prompt.md"

if [ -f "$A1" ]; then
	grep -qx 'exec' "$A1" && ! grep -qx 'resume' "$A1"
	check "call 1 is exec, not resume" $?
	grep -qx -- '-s' "$A1" && grep -qx 'read-only' "$A1"
	check "call 1 has -s read-only" $?
else
	check "call 1 argv exists" 1
fi

if [ -f "$A2" ]; then
	grep -qx 'resume' "$A2"
	check "call 2 is resume" $?
	grep -q 'sandbox_mode' "$A2"
	check "call 2 has sandbox_mode override" $?
	check_that "call 2 not rejected for bad flags" [ ! -f "$LOG/call-2/rejected.txt" ]
else
	check "call 2 argv exists" 1
fi

if [ -f "$P1" ]; then
	grep -q 'adversarial reviewer and debater' "$P1"
	check "round 1 carries topic-neutral role wording" $?
	! grep -q 'adversarial technical reviewer' "$P1"
	check "round 1 does not carry the old technical-reviewer wording" $?
	grep -q 'short quoted or structural anchors' "$P1"
	check "round 1 citation rule permits quoted/structural anchors" $?
	grep -q 'This debate is ADVISORY' "$P1"
	check "round 1 labeled advisory" $?
	# Verbatim fencing: the body between the BEGIN/END fence lines must equal
	# the subject byte-for-byte (modulo edge blank lines) — inserted claim
	# numbers, reflow, stripped indentation, or quoting the poem intact
	# elsewhere while fencing a distorted copy all break the equality.
	fence_body=$(awk '/^--- BEGIN .*data under review/ { f = 1; next } /^--- END / { f = 0 } f' "$P1" | sed '/./,$!d')
	orig_body=$(cat "$ORIG")
	verbatim=1
	[ -n "$fence_body" ] && [ "$fence_body" = "$orig_body" ] && verbatim=0
	check "poem fenced verbatim (fence body equals subject byte-for-byte)" "$verbatim"
	! grep -q '{{' "$P1"
	check "no unfilled {{slots}} in round 1" $?
	! grep -q '<!--' "$P1"
	check "no template header comments leaked" $?
else
	check "round 1 prompt captured" 1
fi

if [ -f "$P2" ]; then
	grep -q '\[O1' "$P2"
	check "round 2 opens with O-ID ledger" $?
	grep -q 'State any remaining or new objections, or agree.' "$P2"
	check "round 2 carries rules footer" $?
	grep -q 'Still ADVISORY' "$P2"
	check "round 2 mode line filled" $?
else
	check "round 2 prompt captured" 1
fi

# Anchor resolution: every double-quoted span in the scripted reply must
# occur verbatim in the subject. The stub replays fixtures and cannot assert,
# so this guards the fixture itself from drifting toward unanchored
# objections and keeps the anchoring contract executable.
R1="$HERE/replies/reply-1.md"
anchors=$(grep -oE '"[^"]+"' "$R1" | sed 's/^"//; s/"$//')
count=0
unresolved=0
while IFS= read -r a; do
	[ -n "$a" ] || continue
	count=$((count + 1))
	grep -Fq -- "$a" "$ORIG" || unresolved=1
done <<<"$anchors"
check_that "reply-1 carries quoted anchors (got $count)" [ "$count" -ge 2 ]
check "every reply-1 anchor resolves within the subject" "$unresolved"

# Per-objection anchoring: each numbered objection block must itself carry a
# quoted anchor — a globally sufficient count must not hide an unanchored
# objection. Combined with the resolution check above, this makes the
# anchoring contract executable per objection.
blocks=$(grep -cE '^[0-9]+\.' "$R1")
unanchored=0
for i in $(seq 1 "$blocks"); do
	awk -v n="$i" '/^[0-9]+\./ { c++ } c == n' "$R1" | grep -qE '"[^"]+"' || unanchored=1
done
check_that "reply-1 has numbered objection blocks (got $blocks)" [ "$blocks" -ge 2 ]
check "each reply-1 objection block carries its own quoted anchor" "$unanchored"

if [ -f "$WD/work/subject.md" ]; then
	grep -Fq 'returned undefined — eventually.' "$WD/work/subject.md"
	check "constrained punchline preserved verbatim in the artifact" $?
	! grep -Fq 'nested more than three levels deep' "$WD/work/subject.md"
	check "conceded meter objection applied (second line revised)" $?
else
	check "debated artifact exists" 1
fi

if [ -f "$OUT" ]; then
	grep -qi 'agreement' "$OUT"
	check "report states the verdict" $?
	grep -qi 'advisor' "$OUT"
	check "report labeled advisory" $?
else
	check "agent output captured" 1
fi

echo "----"
echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
