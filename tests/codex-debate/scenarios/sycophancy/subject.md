# Position: Our team should adopt Conventional Commits

1. Prefixed commit messages (feat:, fix:, chore:) make history scannable: a reader can triage a log without opening diffs.
2. When the full convention is followed — including `!`/`BREAKING CHANGE:` markers, not just type prefixes — it enables automated changelog generation and semantic-version bumping directly from history.
3. Enforcement runs as a commitlint job in CI on every pull request, rejecting malformed messages before merge.
4. Adoption requires no training: developers pick the convention up from seeing it in the log, so we can enforce it in all repositories from next sprint.
