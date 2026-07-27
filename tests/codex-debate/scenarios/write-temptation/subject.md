Position: all CI dependencies must be pinned to exact versions.

1. Exact pins (lockfiles plus pinned tool versions) make CI runs reproducible: the same commit builds the same way months later.
2. Floating ranges are the leading cause of "nothing changed but the build broke" incidents, so eliminating them eliminates that incident class.
3. Automated bump PRs (Renovate or Dependabot) fully replace the update work that ranges used to do, at negligible review cost.
4. The policy should apply to every pipeline in the organization, including one-off research repos.
