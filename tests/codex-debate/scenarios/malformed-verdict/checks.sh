#!/usr/bin/env bash
# malformed-verdict: reply 2 lacks a VERDICT line. Expect exactly one
# corrective resume (call 3) that asks Codex to restate its verdict, then
# clean termination on the corrected AGREEMENT. Usage: checks.sh <workdir>
set -u
WD="${1:?usage: checks.sh <workdir>}"
LOG="$WD/stublog"
OUT="$WD/agent-output.md"
pass=0
fail=0
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

calls=$(find "$LOG" -maxdepth 1 -type d -name 'call-*' 2>/dev/null | wc -l)
check_that "exactly 3 codex calls (got $calls)" [ "$calls" -eq 3 ]

A3="$LOG/call-3/argv.txt"
P3="$LOG/call-3/prompt.md"
if [ -f "$A3" ]; then
	grep -qx 'resume' "$A3"
	check "corrective call is a resume" $?
	grep -q 'sandbox_mode' "$A3"
	check "corrective resume keeps sandbox override" $?
else
	check "call 3 argv exists" 1
fi

if [ -f "$P3" ]; then
	grep -qi 'verdict' "$P3" && grep -qiE 'restat|malform|missing|last line|exactly one' "$P3"
	check "corrective prompt asks for a verdict restatement" $?
else
	check "call 3 prompt captured" 1
fi

o1=$(grep -A1 -x -- '-o' "$LOG/call-1/argv.txt" 2>/dev/null | tail -1)
o2=$(grep -A1 -x -- '-o' "$LOG/call-2/argv.txt" 2>/dev/null | tail -1)
o3=$(grep -A1 -x -- '-o' "$LOG/call-3/argv.txt" 2>/dev/null | tail -1)
[ -n "$o3" ] && [ "$o3" != "$o2" ] && [ "$o3" != "$o1" ]
check "corrective retry uses a fresh -o filename" $?

if [ -f "$OUT" ]; then
	grep -qi 'agreement' "$OUT"
	check "report states the corrected verdict" $?
	! grep -qiE 'abort|protocol failure' "$OUT"
	check "report does not treat the retry as an abort" $?
else
	check "agent output captured" 1
fi

echo "----"
echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
