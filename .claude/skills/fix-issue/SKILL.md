# Fix Issue

Use `/fix-issue <issue_number>` for a scoped fix. Follow [AGENTS.md](../../../AGENTS.md). Start with the local issue analysis or record the minimum reproduction, root cause, and scope before editing.

1. Inspect staged and working changes. Use the current checkout unless instructed otherwise.
2. Fix the root cause using existing entry points and tests. Preserve applicable API, configuration, fallback, and fail-open behavior.
3. Update existing English documentation owners where affected. Update `.env.example` for new settings and follow the flat English `[Unreleased]` format when a changelog entry is required.
4. Run the closest checks in the repository validation matrix. Record commands, outcomes, gaps, compatibility risks, and rollback in `.claude/reviews/issues/issue-<number>.md`.
5. Follow AGENTS.md for branch, commit, tag, push, PR, and issue actions. External mutations require explicit authorization.

Keep the fix and local analysis scoped to the issue. Use the repository title convention for a proposed PR.
