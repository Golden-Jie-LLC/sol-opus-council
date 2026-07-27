#!/usr/bin/env bash
# Install the plugin from this repository's marketplace into an isolated
# Claude config directory and verify the installed form: marketplace add,
# plugin install, skill presence, bundled references, and that repository-only
# content (tests, contributor files) is not shipped.
#
# Usage: smoke.sh [marketplace-source]
# Default source is this checkout's repository root; pass a GitHub
# owner/repo (e.g. octanevz/codex-debate) or URL to verify the public
# install flow instead. Fidelity is always checked against this checkout,
# so a remote source only makes sense when the checkout matches its HEAD.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SRC="${1:-$REPO}"
CLAUDE_CONFIG_DIR="$(mktemp -d)"
export CLAUDE_CONFIG_DIR
trap 'rm -rf "$CLAUDE_CONFIG_DIR"' EXIT

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

claude plugin marketplace add "$SRC" > /dev/null 2>&1
check "marketplace add from $SRC" $?

claude plugin install codex-debate@octanevz > /dev/null 2>&1
check "plugin install codex-debate@octanevz" $?

LIST_JSON=$(claude plugin list --json 2> /dev/null)
printf '%s' "$LIST_JSON" | grep -q '"codex-debate@octanevz"'
check "installed plugin appears in plugin list" $?

# Anchor every artifact assertion on the reported install path, never on a
# loose find: the isolated config dir also holds the marketplace copy.
PLUGROOT=$(printf '%s' "$LIST_JSON" | grep -o '"installPath": *"[^"]*"' | head -1 | sed 's/.*: *"//; s/"$//')
check "plugin list reports an install path" "$([ -n "$PLUGROOT" ] && [ -d "$PLUGROOT" ] && echo 0 || echo 1)"

if [ -n "$PLUGROOT" ] && [ -d "$PLUGROOT" ]; then
    check "installed skill directory present" "$([ -d "$PLUGROOT/skills/codex-debate" ] && echo 0 || echo 1)"
    check "SKILL.md shipped" "$([ -f "$PLUGROOT/skills/codex-debate/SKILL.md" ] && echo 0 || echo 1)"
    check "plugin README shipped" "$([ -f "$PLUGROOT/README.md" ] && echo 0 || echo 1)"
    check "plugin LICENSE shipped" "$([ -f "$PLUGROOT/LICENSE" ] && echo 0 || echo 1)"
    check "plugin CHANGELOG shipped" "$([ -f "$PLUGROOT/CHANGELOG.md" ] && echo 0 || echo 1)"
    # Exact shipment fidelity: the installed file set must equal the source
    # plugin directory's — nothing missing, nothing extra (so repo-only files
    # like tests/ or CLAUDE.md can never ship unnoticed). The CLI's own
    # .in_use/ install-tracking metadata (created for git-sourced installs)
    # is not shipped content and is excluded.
    set_diff=$(diff \
        <(cd "$REPO/plugins/codex-debate" && find . -type f | sort) \
        <(cd "$PLUGROOT" && find . -path ./.in_use -prune -o -type f -print | sort))
    if [ -z "$set_diff" ]; then
        check "installed file set equals source plugin exactly" 0
    else
        check "installed file set equals source plugin exactly" 1
        printf '%s\n' "$set_diff" | sed 's/^/       /'
    fi
fi

echo "----"
echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
