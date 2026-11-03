# Analyze PR

Use `/analyze-pr <pr_number>` to review a GitHub pull request. Follow [AGENTS.md](../../../AGENTS.md) and the [PR template](../../../.github/PULL_REQUEST_TEMPLATE.md). Write the local review in English.

1. Read metadata, comments, diff, and checks with `gh pr view`, `gh pr diff`, and `gh pr checks`. Use `gh run view <run_id> --log-failed` for failed checks. Keep the current checkout unless the user authorizes a change.
2. Review necessity, relevance, title guidance, description, validation evidence, implementation, and merge decision in repository order. Use focused local verification where CI leaves a material gap.
3. Check compatibility across affected APIs, clients, configuration, deployment, fallback, reports, and notification paths. For model/API changes, verify official references, dependency window, tested paths, existing configuration handling, and minimum rollback.
4. Save findings with severity and file/line references, CI and local evidence, compatibility impact, rollback, and merge decision to `.claude/reviews/prs/pr-<number>.md`. Include a draft review comment when useful.

Read-only investigation and scoped local validation are allowed. Obtain explicit authorization to post, approve, request changes, merge, or close.
