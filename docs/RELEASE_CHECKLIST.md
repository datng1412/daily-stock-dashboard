# VN Dashboard Release Checklist

## Purpose

Use this checklist before committing VN dashboard documentation or runtime milestones. It is designed for the SSI-first dashboard and the Phase 0-9 roadmap.

## Before Any Commit

```powershell
git status --short
git diff --stat
git diff --check
```

Review scope:

- No unrelated runtime or formatting churn.
- No `.env`, credentials, tokens, auth headers, account IDs, raw auth responses, temp cache, npm cache, or handoff zips unless explicitly requested.
- No hidden Mozyfin/KBS fallback language.
- No fake realtime from daily close.
- No recommendation wording except prohibitions/historical release notes.

## Docs-Only Commit

Required:

```powershell
git diff --check
```

Review:

- Cross-links point to existing docs.
- Commands use correct Windows paths when documented as PowerShell.
- Public contracts stay consistent: missing object `null`, missing list `[]`.
- Changelog `[Unreleased]` has one concise documentation entry for the docs batch.

Suggested commit examples:

```text
docs: complete VN dashboard documentation system
docs: document VN API contracts and UI states
docs: align VN data-quality roadmap
```

## Runtime Commit

Run the relevant backend and frontend checks:

```powershell
python -m pytest tests/test_vietnam_observability.py -q
python -m pytest tests/test_vietnam_market_service_no_mozyfin.py -q
python -m pytest tests/test_vietnam_market_service_realtime.py -q
python -m pytest tests/test_vietnam_market_service_intraday.py -q
npm.cmd --prefix apps\dsa-web run build
npm.cmd --prefix apps\dsa-web test -- VietnamCompanyResearchPage
npm.cmd --prefix apps\dsa-web test -- VietnamDashboardPage.test.tsx
git diff --check
```

Add narrower tests for changed contracts or UI states.

Suggested commit examples:

```text
feat: add VN data quality summary
fix: clean VN live data contract and diagnostics
feat: redesign VN company detail as data quality report
```

## Manual Smoke

With backend running:

```text
/vietnam
/vietnam/company/FPT
/api/v1/stocks/vn/watchlist?tickers=FPT&force_refresh=true
/api/v1/stocks/vn/company/FPT?force_refresh=true
/api/v1/stocks/vn/observability
/api/v1/stocks/vn/index-components?index_code=VN30
```

Expected:

- Daily SSI data visible if credentials and DailyOhlc are available.
- News disabled until separate provider exists.
- Optional live sections concise when unavailable.
- Diagnostics collapsible or secondary.

## Security Scan

Before sharing handoff artifacts or opening a PR:

```powershell
Select-String -Path docs\*.md -Pattern "token|secret|authorization|bearer|consumer|password|apikey|api_key|access_token|private_key" -CaseSensitive:$false
```

For handoff packages:

```powershell
Get-ChildItem .handoff -Recurse -File |
  Select-String -Pattern "token|secret|authorization|bearer|consumer|password|apikey|api_key|access_token|private_key" -CaseSensitive:$false
```

Safe hits include guardrail text and placeholder variable names. Real values must be redacted or the file must be removed.

## Guardrail Scans

```powershell
Select-String -Path docs\*.md -Pattern "trades\s*=\s*\[\]|trades:\s*\[\]" -CaseSensitive:$false
Select-String -Path docs\*.md -Pattern "confirmed live|implemented news|Mozyfin fallback|KBS fallback" -CaseSensitive:$false
Select-String -Path docs\*.md -Pattern "buy|sell|hold|target price|recommendation" -CaseSensitive:$false
```

Review hits manually. Some hits are expected in prohibitions, historical changelog, source field names, or legacy cleanup descriptions.

## When Not To Commit

Do not commit if:

- A validation command failed and the failure is not documented.
- Runtime code changed during a docs-only task.
- Public docs claim SSI realtime/trade tape is live before verified rows exist.
- Future module statuses conflict with `docs/VN_DATA_CONTRACT.md`.
- Secrets or raw auth responses are present.
- The PR would mix unrelated docs, runtime, and formatting churn without reason.
