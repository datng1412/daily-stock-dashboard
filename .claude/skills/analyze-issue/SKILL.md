# Analyze Issue

Use `/analyze-issue <issue_number>` to assess a GitHub issue. Follow [AGENTS.md](../../../AGENTS.md) and write the local analysis in English.

1. Read the issue and comments with `gh issue view <issue_number> --comments`. Confirm repository, commit or release, environment, reproduction, and sanitized errors.
2. Check relevant code, tests, workflows, configuration, and documentation. Determine whether the issue is reproducible and within repository scope. Distinguish a code defect, setup problem, misuse, and external dependency failure.
3. Check effects on API compatibility, fallback, reports, notifications, auth, desktop, and release where relevant.
4. Save the analysis to `.claude/reviews/issues/issue-<number>.md`.

Record the date and pending review status, version baseline, validity, evidence, impact, root cause or reasoning, priority (P0–P3), difficulty, recommended action, and rollback if a fix is proposed. Include a draft reply when useful. Use the PR title guidance in AGENTS.md.

Read-only investigation and the local report are allowed. Obtain explicit authorization to label, comment, close, or start an issue fix.
