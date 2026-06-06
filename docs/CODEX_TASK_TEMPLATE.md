# Codex Task Template

Use this template when starting a new Codex task for this repository.

## Request

State the desired outcome in one or two sentences.

## Constraints

- Do not commit unless explicitly requested.
- Do not change application code unless the task requires it.
- Preserve existing user changes.
- Do not print secrets or API keys.
- Keep changes scoped to the requested area.

## Current Context

- Relevant docs:
  - `AGENTS.md`
  - `docs/PROJECT_STATE.md`
  - `docs/DECISIONS.md`
  - `docs/RUNBOOK_VN.md`
  - `docs/REVIEW_CHECKLIST.md`
- Relevant runtime mode:
  - Live Mozyfin
  - Fixture Mozyfin
  - Not applicable

## Investigation Checklist

- Read the relevant implementation before editing.
- Identify whether the issue is code, config, process, cache, dependency, or documentation.
- For VN dashboard data freshness, check:
  - backend process and port
  - `MOZYFIN_FIXTURE_DIR`
  - `MOZYFIN_API_KEY` presence only
  - Mozyfin CLI direct output
  - health endpoint
  - force refresh endpoint
  - UI displayed source/date

## Implementation Plan

1. Summarize the smallest safe change.
2. List files expected to change.
3. State validation commands before editing if risk is nontrivial.

## Validation Evidence

Record commands and outcomes:

```text
Command:
Result:
Notes:
```

## Final Response Shape

Use this structure:

```text
Changed:
- ...

Verified:
- ...

Assumptions:
- ...

Not done:
- ...
```

## Vietnam Dashboard Guardrails

- Do not convert neutral labels into buy/sell recommendations.
- Do not describe 1H OHLCV intraday pulse as realtime quote data.
- Do not treat current quote output as reliable latest matched price.
- Keep Wilder/RMA as the user-facing RSI14 method unless a task explicitly changes it.
- Keep VN visible timestamps in Vietnam time.
- Keep live/fixture mode explicit in API and UI.
