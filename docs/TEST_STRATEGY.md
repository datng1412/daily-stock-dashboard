# VN Dashboard Test Strategy

## Purpose

This strategy defines the expected validation for VN dashboard documentation, API contracts, and UI states. It is scoped to SSI-first VN dashboard work and should be referenced before data-quality, contract, progressive workspace, live-section, provider, and packaging tasks.

## Required Backend Tests

Run these before a Phase 0/1/2/3 runtime milestone commit:

```powershell
python -m pytest tests/test_vietnam_observability.py -q
python -m pytest tests/test_vietnam_market_service_no_mozyfin.py -q
python -m pytest tests/test_ssi_fastconnect_fetcher.py -q
python -m pytest tests/test_vietnam_market_service_realtime.py -q
python -m pytest tests/test_vietnam_market_service_intraday.py -q
python -m pytest tests/test_ssi_streaming_realtime.py -q
python -m pytest tests/test_verify_ssi_streaming_realtime_script.py -q
```

Expected protection:

- Mozyfin is not constructed for strict VN runtime.
- KBS remains legacy optional only and disabled by default.
- News is disabled until a separate provider exists.
- SSI realtime unavailable returns `realtime_snapshot = null`.
- SSI streaming realtime stays disabled by default, does not instantiate or import the official client when disabled, never starts on import, and reads only from a running manager plus fresh cache.
- SSI official streaming adapter tests use mocked official modules, suppress header-like output, reject `X: ALL`, and fail closed when streaming config or `ssi_fc_data` is unavailable.
- SSI streaming verification script tests import the script without starting streams, validate config-only/package-check/package-inspection modes, reject unsafe symbols/channels, default planned channels to no-space `X:FPT` format, preserve explicit old-space overrides with a warning, keep channel-format variants for diagnostics, use mocked manager/client/direct-official paths, classify callback/no-message/parser-zero/cache-hit/on-error/direct-start outcomes, bound safe samples, capture official stdout/stderr without raw printing, stop in `finally`, and keep the script-local cache separate from the backend cache.
- SSI intraday stale/unavailable returns `intraday_pulse = null` and `intraday_candles = []`.
- SSI intraday provider failures are classified into sanitized diagnostics such as `rate_limited`, without raw payloads or credentials, and without changing DailyOhlc `latest_price` ownership.
- SSI intraday provider-code/HTTP `429` starts a deterministic symbol/timeframe cooldown; active cooldown skips IntradayOhlc provider requests and remains unavailable without blocking DailyOhlc or DailyStockPrice.
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
- SSI profile metadata maps industry/sector aliases through `symbol_metadata`, watchlist rows, and company profile only when provider data exists.
- SSI index components resolve provider-owned identifiers from IndexList, keep the public requested code stable, and expose sanitized diagnostics for unavailable component rows.

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

## Future Progressive Loading Tests Needed

Add focused frontend tests when implementing Phase 3.2 through Phase 3.4 request-state work:

- Previous successful watchlist rows stay visible during refresh.
- First load and refresh use distinct UI states.
- Refresh uses user-facing `Updating...` or equivalent concise copy instead of blanking the table.
- Sorting and filtering do not call the watchlist endpoint.
- Typing in the custom watchlist input does not call the watchlist endpoint.
- Saving a custom watchlist without applying does not call the watchlist endpoint.
- Optional live failure does not erase daily table rows, daily chart data, or DailyStockPrice fields.
- Diagnostics expansion does not trigger new provider calls unless a future task explicitly designs that behavior.
- Rapid preset switches ignore stale or older responses.
- Request-state transitions distinguish `idle`, `loading`, `refreshing`, internal `success`, `partial`, and `failed`.
- User-facing section state uses `ready` rather than exposing internal `success` copy.
- Disabled future modules do not appear as failures.
- News disabled remains expected until a NewsProvider exists.
- Realtime/trade-tape unavailable remains optional/minor when required DailyOhlc fields are valid.

## Capability Audit And Smoke Roles

Phase 4.0A should add a local capability-audit script that complements, rather than replaces, the existing VN dashboard smoke harness.

The smoke harness checks:

- Current application contracts and baseline behavior.
- Required watchlist/company response shapes.
- Source ownership and null/empty missing-data rules.
- Concise public status messages and diagnostics separation.
- Regression protection for currently implemented behavior.

The capability audit checks:

- Whether each priority data domain returns usable fields.
- Source ownership, row coverage, timestamps, cadence, and freshness.
- Which exact fields are reliable, partial, unavailable, disabled, future-provider, or unknown-needs-verification.
- Whether available rows are safe to use in later contract or UI tasks.

Audit outcome rules:

- An optional unavailable data domain should be reported as unavailable and should not fail the audit when the audit request itself succeeds.
- A disabled domain should be reported as disabled.
- News, financials, corporate actions, dividends, macro, and other unselected external domains should be reported as future-provider or disabled.
- Request, authentication, parsing, or audit-script failures should remain distinguishable from a valid unavailable-domain result.
- Audit output must remain secret-safe and must not print credentials, tokens, auth headers, account IDs, or full raw provider payloads.
- Capability evidence should guide later reliability and contract/status tasks before UI rendering work.

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

## Local VN Dashboard Smoke Harness

Run this after Phase 2+ VN dashboard changes when a local backend is already running:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_vn_dashboard.ps1 -SkipFrontendOpen
```

Use `-ForceRefresh` only when the goal is to bypass backend cache:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_vn_dashboard.ps1 -SkipFrontendOpen -ForceRefresh
```

Expected protection:

- Requested watchlist tickers are present.
- Daily SSI fields remain available for usable rows.
- The printed `EXPECTED Foreign net volume` is computed only from `ssi_foreign_net_volume`.
- Watchlist trade tape remains list data and company trade rows remain `trade_tape.trades`.
- Unavailable live objects use `null`; unavailable live lists use `[]`.
- Company price/trading/foreign-flow sources stay split between SSI DailyOhlc and SSI DailyStockPrice.
- News, financials, and events are not labeled as SSI market-data sections.
- Public status messages stay short while diagnostics may retain endpoint, HTTP status, provider message, and sanitized error context.

This harness is local/manual regression coverage. It requires a running backend and does not replace deterministic backend/frontend unit tests.

## Legacy/Quarantine Notes

- KBS tests or code paths are legacy-only unless explicitly enabled.
- Mozyfin VN paths are disabled for runtime and should not be used as fallback.
- Tests that require live SSI credentials should be kept out of deterministic CI unless explicitly marked.
- API snapshots should be reviewed before becoming fixtures because they can contain environment-specific diagnostics.
