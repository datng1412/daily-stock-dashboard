# VN Dashboard Test Strategy

## Purpose

This strategy defines the expected validation for VN dashboard documentation, API contracts, and UI states. It is scoped to SSI-first VN dashboard work and should be referenced before Phase 1-3 implementation tasks.

## Required Backend Tests

Run these before a Phase 0/1/2/3 runtime milestone commit:

```powershell
python -m pytest tests/test_vietnam_observability.py -q
python -m pytest tests/test_vietnam_market_service_no_mozyfin.py -q
python -m pytest tests/test_vietnam_market_service_realtime.py -q
python -m pytest tests/test_vietnam_market_service_intraday.py -q
```

Expected protection:

- Mozyfin is not constructed for strict VN runtime.
- KBS remains legacy optional only and disabled by default.
- News is disabled until a separate provider exists.
- SSI realtime unavailable returns `realtime_snapshot = null`.
- SSI intraday stale/unavailable returns `intraday_pulse = null` and `intraday_candles = []`.
- SSI trade tape unavailable returns public `trade_tape = []`.
- Observability separates disabled provider, provider unavailable, and cache state.

## Required Frontend Build And Tests

Do not run npm from the repo root. Use `--prefix apps\dsa-web`.

```powershell
npm.cmd --prefix apps\dsa-web run build
npm.cmd --prefix apps\dsa-web test -- VietnamCompanyResearchPage
npm.cmd --prefix apps\dsa-web test -- VietnamDashboardPage.test.tsx
```

If `C:` temp/cache space is constrained:

```powershell
$env:TEMP = "D:\stock-dashboard.tmp"
$env:TMP = "D:\stock-dashboard.tmp"
$env:npm_config_cache = "D:\stock-dashboard.tmp\npm-cache"
```

## Docs-Only Validation

For docs-only changes:

```powershell
git diff --check
```

Recommended guardrail scans:

```powershell
Select-String -Path docs\*.md -Pattern "trades\s*=\s*\[\]|trades:\s*\[\]" -CaseSensitive:$false
Select-String -Path docs\*.md -Pattern "confirmed live|implemented news|Mozyfin fallback|KBS fallback" -CaseSensitive:$false
Select-String -Path docs\*.md -Pattern "buy|sell|hold|target price|recommendation" -CaseSensitive:$false
```

Interpretation:

- `trades: []` is allowed only when describing the legacy/current wrapper cleanup issue.
- Recommendation terms are allowed only in prohibitions or historical changelog entries.
- Provider claim hits must be reviewed for context.

## Phase 1 Contract Tests Needed

Add focused tests when implementing Data Quality Summary:

- DailyOhlc versus DailyStockPrice mismatch appears with both source labels.
- Canonical latest price source is explicit.
- `final_close_status` unknown/provisional/final produces neutral UI copy.
- `adjusted_price_status = unknown` does not infer corporate actions.
- Profile provider `ok` plus missing `name`/`industry` produces profile completeness `partial`.
- Company price source decision is reflected consistently in API and UI.

## Phase 2 Contract Tests Needed

Add focused tests for public contract cleanup:

- Company unavailable intraday returns `pulse = null`, not `{}`.
- Watchlist/company unavailable trade tape returns `trade_tape = []`, not a wrapper object.
- `realtime_status.message` and `trade_tape_status.message` are short and user-safe.
- Endpoint attempts, last endpoint, HTTP status, raw provider error summary, retryable flag, and stale-date details live under diagnostics.
- `intraday_timeframe` is not treated as actual returned cadence.
- Non-retryable realtime/trade-tape 404 responses use backoff or longer TTL.

## Phase 3 UI State Tests Needed

Add or update frontend tests for:

- Company hero shows ticker, exchange, latest price, price date, canonical source, and overall data status.
- Data Quality Summary appears above detailed cards.
- Daily core data remains dominant.
- Live unavailable sections are grouped and lower prominence.
- Future modules are grouped as disabled/not implemented/unavailable.
- Collapsible diagnostics contain source coverage and endpoint diagnostics.
- Primary UI contains no endpoint dumps or raw provider errors.
- Null metadata rows are hidden; profile partial is visible.

## Manual Smoke Checklist

With backend running:

```text
GET /api/v1/stocks/vn/watchlist?tickers=FPT&force_refresh=true
GET /api/v1/stocks/vn/company/FPT?force_refresh=true
GET /api/v1/stocks/vn/observability
GET /api/v1/stocks/vn/index-components?index_code=VN30
GET /vietnam
GET /vietnam/company/FPT
```

Check:

- Daily SSI data visible when DailyOhlc works.
- News disabled or future module not implemented.
- Missing realtime/trade tape shown as unavailable.
- Intraday unavailable if stale/mismatched.
- No fake metric rows.
- No Mozyfin/KBS normal fallback.
- No endpoint dumps in primary UI.

## Legacy/Quarantine Notes

- KBS tests or code paths are legacy-only unless explicitly enabled.
- Mozyfin VN paths are disabled for runtime and should not be used as fallback.
- Tests that require live SSI credentials should be kept out of deterministic CI unless explicitly marked.
- API snapshots should be reviewed before becoming fixtures because they can contain environment-specific diagnostics.
