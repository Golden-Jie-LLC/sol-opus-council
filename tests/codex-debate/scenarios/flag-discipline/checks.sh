#!/usr/bin/env bash
# flag-discipline: three uneventful rounds; every assertion is about CLI
# mechanics across a longer session. Usage: checks.sh <workdir>
set -u
WD="${1:?usage: checks.sh <workdir>}"
LOG="$WD/stublog"
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

A1="$LOG/call-1/argv.txt"
if [ -f "$A1" ]; then
	grep -qx 'exec' "$A1" && ! grep -qx 'resume' "$A1"
	check "call 1 is a fresh exec" $?
	grep -qx -- '-s' "$A1" && grep -qx 'read-only' "$A1"
	check "call 1 sandboxed read-only" $?
	grep -qx -- '--skip-git-repo-check' "$A1"
	check "call 1 has --skip-git-repo-check (cwd is not a repo)" $?
	check_that "call 1 prompt piped via stdin" [ -s "$LOG/call-1/prompt.md" ]
else
	check "call 1 argv exists" 1
fi

sid1=""
for n in 2 3; do
	A="$LOG/call-$n/argv.txt"
	if [ -f "$A" ]; then
		grep -qx 'resume' "$A"
		check "call $n is a resume" $?
		grep -q 'sandbox_mode' "$A"
		check "call $n has sandbox_mode override" $?
		grep -qx -- '--skip-git-repo-check' "$A"
		check "call $n keeps --skip-git-repo-check" $?
		check_that "call $n has no exec-only flags (-s/--color)" [ ! -f "$LOG/call-$n/rejected.txt" ]
		! grep -qx -- '--last' "$A" && ! grep -qx -- '--ephemeral' "$A"
		check "call $n avoids --last/--ephemeral" $?
		sid=$(grep -oxE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$A" | head -1)
		check_that "call $n resumes by explicit session id" [ -n "$sid" ]
		if [ "$n" = 2 ]; then
			sid1="$sid"
		else
			if [ -n "$sid" ] && [ "$sid" = "$sid1" ]; then
				check "calls 2 and 3 resume the same session" 0
			else
				check "calls 2 and 3 resume the same session" 1
			fi
		fi
		check_that "call $n prompt piped via stdin" [ -s "$LOG/call-$n/prompt.md" ]
	else
		check "call $n argv exists" 1
	fi
done

o1=$(grep -A1 -x -- '-o' "$LOG/call-1/argv.txt" 2>/dev/null | tail -1)
o2=$(grep -A1 -x -- '-o' "$LOG/call-2/argv.txt" 2>/dev/null | tail -1)
o3=$(grep -A1 -x -- '-o' "$LOG/call-3/argv.txt" 2>/dev/null | tail -1)
[ -n "$o1" ] && [ -n "$o2" ] && [ -n "$o3" ] &&
	[ "$o1" != "$o2" ] && [ "$o2" != "$o3" ] && [ "$o1" != "$o3" ]
check "three distinct -o filenames" $?

echo "----"
echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
