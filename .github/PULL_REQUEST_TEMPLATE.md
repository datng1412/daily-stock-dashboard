## PR Type

- [ ] fix
- [ ] feat
- [ ] refactor
- [ ] docs
- [ ] chore
- [ ] test

## Background And Problem

Describe the problem, its impact, and what triggers it.

## Scope Of Change

List the modules and files changed in this PR.

## Issue Link

Fill in one of:
- `Fixes #<issue_number>`
- `Refs #<issue_number>`
- If no issue, explain the motivation and acceptance criteria

## Verification Commands And Results

Include the commands you ran and their key results.

```bash
# example
./scripts/ci_gate.sh
python -m pytest -m "not network"
```

Key output & conclusion:

## Compatibility And Risk

Describe compatibility impact and potential risks (write `None` if not applicable).

- If this PR changes third-party model/API compatibility, request parameters, routing prefixes, or provider fallback behavior, include an **official source link or announcement** and clarify whether the rule is permanent, runtime-specific, or a temporary compatibility workaround.
- If this PR depends on a specific runtime or pinned dependency window (for example a LiteLLM version range, OpenAI-compatible routing, or YAML alias behavior), state the compatibility window you verified and which code paths were covered.
- If this PR touches runtime config save/cleanup/migration/backfill logic, explicitly describe whether existing config is rewritten, cleared, migrated, or left intact, and how users can restore the previous behavior.

## Rollback Plan

Provide at least one actionable rollback step (required).

- For compatibility fixes, include the **minimal rollback path** (for example `revert this PR`) and whether any additional config or data rollback is required.

## EXTRACT_PROMPT Change (if applicable)

Paste the full updated prompt here if the PR changes `EXTRACT_PROMPT` in `src/services/image_stock_extractor.py`.

<details>
<summary>Expand full EXTRACT_PROMPT</summary>

```
(paste full prompt here)
```

</details>

## Checklist

- [ ] This PR has a clear motivation and value
- [ ] Reproducible verification commands and results are included
- [ ] Compatibility and risk have been assessed
- [ ] A rollback plan is provided
- [ ] If user-visible changes are included, relevant docs and `docs/CHANGELOG.md` are updated. `README.md` is updated only for homepage-level changes, with details kept in `docs/*.md`
