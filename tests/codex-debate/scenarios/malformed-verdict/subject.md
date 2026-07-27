# Position: Our team should adopt Conventional Commits

1. Prefixed commit messages (feat:, fix:, chore:) make history scannable: a reader can triage a log without opening diffs.
2. The convention enables automated changelog generation and semantic-version bumping directly from history.
3. Enforcement is cheap: a commitlint hook in CI rejects malformed messages with negligible maintenance burden.
4. Therefore all of our repositories should adopt Conventional Commits, enforced in CI from next sprint.
