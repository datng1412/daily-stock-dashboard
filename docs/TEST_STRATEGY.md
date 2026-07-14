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
python -m pytest tests/test_ssi_streaming_realtime_lifecycle.py -q
python -m pytest tests/test_verify_ssi_streaming_realtime_script.py -q
```

Expected protection:

- Mozyfin is not constructed for strict VN runtime.
- KBS remains legacy optional only and disabled by default.
- News is disabled until a separate provider exists.
- SSI realtime unavailable returns `realtime_snapshot = null`.
- SSI streaming realtime stays disabled by default, does not instantiate or import the official client when disabled, never starts on import, and reads only from a running manager plus fresh cache.
- SSI official streaming adapter tests use mocked official modules, suppress header-like output, reject `X: ALL`, and fail closed when streaming config or `ssi_fc_data` is unavailable.
- SSI backend lifecycle bootstrap tests use mocked stream clients, require `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS` before startup, reject unsafe bootstrap symbols, verify no-space symbol channels, stop idempotently, and prove the realtime endpoint/service reads the process-local cache without dynamic request subscriptions.
- SSI streaming runtime hardening tests use fake clocks and mocked clients to cover idle detection, `running_idle` diagnostics without daily-data invalidation, diagnostic-only idle reconnect behavior when no backend market-hours utility exists, reconnect scheduling after start failure, bounded/capped backoff, `SSI_STREAMING_REALTIME_RECONNECT_MAX_ATTEMPTS` semantics, stop-before-reconnect, duplicate-stream prevention, lifecycle monitor ownership, clean shutdown, and no revival after shutdown begins.
- Phase 4.8R-Live validation is session-dependent: after-hours proof must confirm market-closed/after-hours-stale classification, stable subscriptions, no reconnect loop, and preserved last-known data; lifecycle tests must also cover shutdown while client start is in progress so a late client cannot revive the manager. Active-window proof of advancing health counters and one debounced live reconnect remains a separate scheduled validation.
- SSI realtime cache tests should prove `/api/v1/stocks/vn/realtime` service reads bypass the generic response cache, preserve streaming cache TTL/freshness fields, and expose newer process-local cache rows on the next read without changing DailyOhlc `latest_price`.
- SSI realtime endpoint tests should prove unexpected realtime request failures return an optional unavailable response without leaking secrets or turning the dashboard into a full-page failure.
- SSI streaming verification script tests import the script without starting streams, validate config-only/package-check/package-inspection modes, reject unsafe symbols/channels, default planned channels to no-space `X:FPT` format, preserve explicit old-space overrides with a warning, keep channel-format variants for diagnostics, use mocked manager/client/direct-official paths, classify callback/no-message/parser-zero/cache-hit/on-error/direct-start outcomes, bound safe samples, capture official stdout/stderr without raw printing, stop in `finally`, and keep the script-local cache separate from the backend cache.
- SSI intraday stale/unavailable returns `intraday_pulse = null` and `intraday_candles = []`.
- SSI intraday cadence tests cover regular `1m`, `5m`, and `1h` rows, requested-versus-actual mismatch, irregular spacing, and unavailable cadence status without changing DailyOhlc ownership.
- SSI intraday provider failures are classified into sanitized diagnostics such as `rate_limited`, without raw payloads or credentials, and without changing DailyOhlc `latest_price` ownership.
- SSI intraday provider-code/HTTP `429` starts a deterministic symbol/timeframe cooldown; active cooldown skips IntradayOhlc provider requests and remains unavailable without blocking DailyOhlc or DailyStockPrice.
- SSI trade tape unavailable returns public `trade_tape = []`.
- SSI trade tape rows come only from the background X-TRADE event buffer, not REST candidates, DailyOhlc, DailyStockPrice, or realtime snapshots.
- Observability separates disabled provider, provider unavailable, and cache state.

## Required Frontend Build And Tests

Do not run npm from the repo root. Use `--prefix apps\dsa-web`.

```powershell
npm.cmd --prefix apps\dsa-web run build
npm.cmd --prefix apps\dsa-web test -- VietnamCompanyResearchPage
npm.cmd --prefix apps\dsa-web test -- VietnamDashboardPage.test.tsx
npm.cmd --prefix apps\dsa-web test -- vietnamTime.test.ts
```

Expected protection:

- Realtime polling calls only `/api/v1/stocks/vn/realtime` and does not refresh watchlist, chart, company-like, or trade-tape paths.
- Realtime polling failures keep previous daily rows, selected ticker, chart, and any previous successful realtime snapshot visible.
- Streaming snapshot tests cover strict version/provider/timestamp validation, bounded allowlisted context rows, atomic/debounced writes, shutdown flush, corrupt/expired failure isolation, context independence, persisted-stale restore, and live-row precedence. They must use temporary directories and never print snapshot contents or secrets.
- Hidden-tab visibility handling pauses/skips realtime polling and visible-tab restoration resumes realtime polling only, without a full dashboard reload.
- Trade-tape auto-refresh tests should wait for the initial selected-ticker chart request before capturing no-refresh baselines, so the initial chart effect is not misclassified as a trade-tape timer refresh.

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
- Docs-only stock-detail availability audits should inspect current schema/type/service/fetcher evidence and should not run backend/frontend suites unless runtime files changed. The expected validation is `git diff --check`, status review, and targeted documentation grep for the audited labels.

## Phase 1 Contract Tests Needed

Add focused tests when implementing Data Quality Summary:

- DailyOhlc versus DailyStockPrice mismatch appears with both source labels.
- Canonical latest price source is explicit.
- `final_close_status` unknown/provisional/final produces neutral UI copy.
- `adjusted_price_status = unknown` does not infer corporate actions.
- Profile provider `ok` plus missing `name`/`industry` produces profile completeness `partial`.
- Company price source decision is reflected consistently in API and UI.
- SSI profile metadata maps industry/sector aliases through `symbol_metadata`, watchlist rows, and company profile only when provider data exists.
- SSI metadata tests cover complete, partial, same-SSI fallback, unavailable, and wrong/missing-symbol rows; assert sanitized diagnostics and unchanged DailyOhlc `latest_price`/DailyStockPrice enrichment.
- SSI index components use the caller's explicit normalized code directly through the verified `indexCode` shape, keep the public requested code stable, flatten exact nested `IndexComponent`/`StockSymbol` rows, reject mismatched outer indices, and expose sanitized diagnostics for unavailable component rows.
- Index capability tests cover IndexList cross-market rows, DailyIndex exact identifier resolution and partial/null/zero/date alignment, single-shape IndexComponents `indexCode` behavior, flat and nested component rows, unavailable empty lists, no hardcoded VN30 members, and unchanged DailyOhlc `latest_price`.
- IndexComponents service-cache tests prove IndexList failure does not block explicit component success, unavailable/rate-limited/no-row results are negatively cached for 60 seconds, usable rows cache for 300 seconds, normalized code/market form stable keys, immediate normal repeats avoid another SSI call, and explicit force refresh bypasses the cache.
- `tests/test_ssi_index_capability_probe.py` covers provider-derived candidate generation, exact/no-guess matching, hard candidate/date/market budgets, endpoint-specific result classification, error-row rejection, whitelisted output, secret omission, and sequential execution. Importing the script does not start a probe.
- DailyStockPrice tests cover reference/limits, matched and put-through volume/value, foreign volume/value, bounded 5D/20D latest-available foreign net volume history, adjusted close, zero-versus-null behavior, matched/mismatched/missing dates, unavailable enrichment, sanitized diagnostics, one bounded per-symbol recent-window call, and unchanged SSI DailyOhlc `latest_price`.
- Short-term zone tests cover 60 valid unique DailyOhlc D1 rows, malformed/insufficient history, ATR14 Wilder/RMA availability, two-before/two-after pivot grouping, nearest-first support/resistance selection, latest-close exclusion, compact lower/upper-only contract, and unchanged daily indicator/latest-price values. Frontend tests cover two description-only headers, compact `S1`/`R1` ranges, explicit unavailable cells, and the default-off daily-chart overlay: contract-only rendering, primary S1/R1 versus secondary S2/R2 styles, midpoint lines, title-only secondary ranges, malformed/unavailable suppression, same price formatting, no toggle request, and shared compact/expanded state.
- Phase 4.10L focused frontend tests treat `lightweight-charts` as a narrow mocked boundary. Pure mapping tests cover timezone-safe `BusinessDay` dates, ordering and deterministic duplicate handling, invalid OHLC/date/volume rejection, aligned indicator series, candle-direction volume colors, StockClock price formatting, and exact backend S/R ranges. Component tests cover one chart lifecycle, native price/volume/RSI panes, indicator visibility updates, unavailable overlays, ticker data replacement, attribution, subscriptions, primitive detach, and `chart.remove()` cleanup. Primitive tests cover at most four exact range models, primary/secondary styling, midpoint axis coordinates, invalid/unavailable suppression, and cleanup. Dashboard boundary tests cover sole-engine ownership, selected range replacement, indicator/S/R inputs, unavailable state, and compact/expanded behavior without reasserting deleted SVG geometry. Browser parity and request-network inspection remain recommended manual validation when the browser integration is available.
- Phase 4.11A adds deterministic coverage for 60/250/500-session mapping, StrictMode's single active container, per-instance cleanup, disposed crosshair/range callbacks, stable price-scale width, compact/expanded pane factors, tooltip containment and stale suppression, S/R clearing, indicator/S/R range stability, intentional ticker fitting, expand/collapse logical-range transfer, immediate range-preset reset, and rapid FPT/VPB/MSB/FPT request ownership. Volume and RSI are always-visible panes, so visibility-toggle cycling is not an applicable runtime state. Do not assert canvas pixels in JSDOM; real resize, native zoom/pan, and request-network behavior require browser validation.
- Frontend tests assert shares/VND units, explicit SSI DailyStockPrice source labels, concise date-mismatch caveats, hidden null optional metrics, retained daily rows/chart, and isolated realtime refresh behavior.
- The selected 5-second trade-tape polling regression should assert that the timer calls only the trade endpoint after initial selected-ticker chart loading has completed.

## Phase 2 Contract Tests Needed

Add focused tests for public contract cleanup:

- Company unavailable intraday returns `pulse = null`, not `{}`.
- Watchlist/company unavailable trade tape returns `trade_tape = []`, not a wrapper object.
- Watchlist/company usable trade tape rows require buffered X-TRADE price, volume, and timestamp fields; missing required fields are dropped.
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
- Profile unavailable keeps valid daily and DailyStockPrice sections visible and does not synthesize company names or metadata rows.
- Optional index context renders real SSI DailyIndex rows/counts only; index failures preserve watchlist rows, selected ticker, chart, realtime polling, and hidden-tab behavior.
- VN30 dashboard filter tests should prove the filter uses SSI IndexComponents rows when available, does not fall back to hardcoded VN30 constituents when SSI components are unavailable, exposes a retry action after unavailable/error responses, disables VN30 only while its component request is pending, suppresses repeated preset/custom clicks, ignores stale VN30 component intents, and keeps previous rows visible.
- VN30 loading tests should distinguish `Loading VN30 members` from `Loading N VN30 rows`, prove the member spinner stops before the watchlist response completes, preserve prior rows, reuse already-loaded component symbols without another IndexComponents request, keep `force_refresh=false` for normal selection, and advance fake timers through the 3-second and 8-second long-wait states.
- VN30 progressive-hydration tests should defer each resolved-size request independently and prove all SSI-derived shell rows render before batch one completes, batch results merge without clearing prior successes, membership order remains stable, `Loaded X/N` advances, and normal batches use `force_refresh=false`. Batch-strategy tests assert the named default/minimum/maximum, prove alternate preferred sizes change chunking, and avoid duplicating an inline size literal in flow tests.
- VN30 failure/race tests should prove a failed batch becomes explicit unavailable shells, retry requests only failed tickers, duplicate VN30 clicks start no second run, and switching to another preset ignores an older VN30 response and prevents later VN30 batches from starting.
- Backend hydration tests should prove bounded DailyStockPrice enrichment/history is requested once per cold symbol, reused from the process cache across request-scoped service instances, bypassed by explicit force refresh, and never changes SSI DailyOhlc `latest_price`. The manual profiler tests cover bounded ticker parsing, whitelist-only summaries, and secret-free failure output.
- Fresh-start watchlist tests should prove empty localStorage does not call the watchlist endpoint, does not select a ticker, shows the empty-start preset/custom prompt, keeps Force Refresh from creating a hardcoded list, and still allows preset clicks, custom typed apply, and saved custom restore. Batch-size tests should prove chunking preserves membership order and does not determine initial watchlist membership.
- Fresh-start VN30 lazy-loading tests should prove empty localStorage does not preload SSI IndexComponents, the idle VN30 action remains usable, user-driven member loading is preset-local, unresolved member requests settle to retryable unavailable state after the bounded timeout, no `Loaded X/N` hydration progress or previous-row copy appears without committed rows, and no hardcoded/default watchlist request is started.
- Empty-start preset clickability tests should prove all non-VN30 presets are enabled before any watchlist rows exist, non-VN30 preset clicks do not call VN30 IndexComponents, newer preset selections can supersede older pending preset requests, and VN30 member loading/unavailability does not block Banks/Securities or custom controls.
- Index/VN30 decoupling tests should prove pending, unavailable, or rate-limited IndexList/DailyIndex diagnostics do not relabel VN30 as member loading, do not set VN30 component status to unavailable before VN30 is selected, and do not block local preset or custom actions.
- Direct local-preset action tests should simulate actual clicks for every non-VN30 scan bucket, assert the watchlist API receives that bucket's static ticker list, and prove empty custom picker selections/options do not block those clicks. VN30 unavailable/no-row tests should use a fulfilled `status=unavailable` component response as well as rejected/timeout responses and assert Retry VN30 appears with no watchlist hydration.
- VN30 member terminal-state tests should observe `Loading VN30 members...` while a deferred user request is pending, then resolve HTTP-successful unavailable/no-row/failure-diagnostic responses and assert loading disappears, Retry VN30 appears, no hydration starts, and rendering the retry state does not automatically issue another IndexComponents request. The same terminal settlement must be rendered inside React StrictMode so setup/cleanup replay cannot leave the unmounted guard set. Explicit retry starts one new request; stale older intent cannot overwrite a newer preset.

## Future Progressive Loading Tests Needed

Add focused frontend tests when implementing Phase 3.2 through Phase 3.4 request-state work:

- Previous successful watchlist rows stay visible during refresh.
- First load and refresh use distinct UI states.
- Refresh uses user-facing `Updating...` or equivalent concise copy instead of blanking the table.
- Sorting and filtering do not call the watchlist endpoint.
- Searching loaded custom-picker options does not call the watchlist endpoint.
- Custom-picker tests cover symbol/name search, multi-select chips, duplicate prevention, individual removal, bounded uppercase apply, explicit exact-symbol `Validate on apply`, pending apply suppression, and local saved-symbol restoration.
- Optional live failure does not erase daily table rows, daily chart data, or DailyStockPrice fields.
- Watchlist table tests should verify missing numeric cells expose reason titles/ARIA labels and realtime badges distinguish disabled, not bootstrapped, cache miss, idle, and stale states when backend status fields provide those reasons.
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
- Which exact fields are `strong`, `usable`, `partial`, `optional_live_dependent`, `unavailable_parameter_unknown`, `unavailable_permission_or_entitlement`, `external_provider_required`, `not_implemented`, or `deferred`.
- Whether available rows are safe to use in later contract or UI tasks.

Audit outcome rules:

- An optional unavailable data domain should be reported as unavailable and should not fail the audit when the audit request itself succeeds.
- A disabled domain should be reported as disabled.
- News, financial statements, ratios, corporate actions, dividends/rights/splits, macro, and other non-SSI domains should be reported as `external_provider_required`, `not_implemented`, or disabled according to the public contract.
- VNStocks and FiinGroup should appear only as candidate external providers with `needs_verification` until a later qualification phase passes.
- Request, authentication, parsing, or audit-script failures should remain distinguishable from a valid unavailable-domain result.
- Audit output must remain secret-safe and must not print credentials, tokens, auth headers, account IDs, or full raw provider payloads.
- Capability evidence should guide later reliability and contract/status tasks before UI rendering work.

## Phase 4.11C Intraday History Contract Tests

These deterministic tests are required before implementing the future endpoint/UI; none should call live SSI:

Phase 4.11B-3 fixtures remain sanitized and deterministic. They may use `TradingDate`, `Time`, `Open`, `High`, `Low`, `Close`, and `Volume` with transformed values that preserve only the evidence-backed shape. Cover nonzero seconds, unique minute buckets, an intentional missing minute, lunch gap, final 14:45 row, malformed timestamp, duplicate normalized bucket, malformed OHLC, non-numeric volume, and one completed-session DailyOhlc reconciliation example. Never copy or commit a raw provider response. Numeric resolutions 5/15/30/60 returned minute-like rows rather than their requested cadence.

1. `DD/MM/YYYY` plus `HH:MM:SS` parses in `Asia/Ho_Chi_Minh`.
2. Timestamp conversion is independent of server-local and browser-local timezone.
3. Raw seconds floor to minute start only under the verified completed-session rule.
4. Normalized one-minute timestamps are unique.
5. Duplicate normalized buckets resolve deterministically with stable last-provider-row-wins diagnostics.
6. Rows sort ascending.
7. Missing minute buckets and lunch are preserved as gaps.
8. No filler or artificial zero-volume candle is synthesized.
9. OHLCV remains unchanged when the timestamp is normalized.
10. Invalid OHLC rows are rejected and counted.
11. Non-numeric volume follows the explicit row-rejection contract; UI copy remains `Volume`.
12. DailyOhlc is reconciliation-only and never substitutes for IntradayOhlc.
13. Exactly one completed Vietnam date is enforced.
14. Current/future dates are rejected or unavailable before an SSI call.
15. Output above 1,000 bars is bounded and the initial implementation does not page.
16. `5m`, `15m`, `30m`, and `1h` return unsupported before provider calls.
17. Cache identity uses normalized ticker, `1m`, Vietnam trading date, and page 1.
18. Public ISO date converts to SSI `DD/MM/YYYY`.
19. Public `ticker` converts to provider `symbol`.
20. DailyStockPrice, X, X-QUOTE, X-TRADE, and persisted streaming rows have no candle-source path.
21. D1 uses the daily request.
22. 1m uses the separate intraday request.
23. Selected date participates in the request key.
24. An old date response cannot replace a newer date.
25. An old interval response cannot replace a newer interval.
26. An old ticker response cannot replace a newer ticker.
27. The chart component performs no request and receives normalized bars only.
28. Missing minutes remain visible chart gaps.
29. Indicators use the active timeframe bars.
30. Phase 4.9A overlays read `Daily S/R` on 1m.

Phase 4.11D requires separate tests for provisional last bars, late/out-of-order events, reconnect, and reconciliation. Do not fold those cases into Phase 4.11C.

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

## Phase 5 External Provider Contract Tests

Phase 5.0A is documentation-only and adds no runtime tests. Phase 5.0B adds `tests/test_corporate_actions_provider_contract.py` for the disabled-by-default `CorporateActionsProvider` boundary. Deterministic tests cover:

- Provider disabled by default.
- `not_configured`/`disabled` and provider failure return `events=[]`.
- Provider failure does not alter or remove valid SSI daily watchlist/company rows.
- No provider is invoked as a silent SSI fallback.
- Event dates remain distinct: announcement, ex-date, record date, and payment/execution date.
- Missing optional values remain null; zero is not substituted for missing ratios or cash amounts.
- Corrections/cancellations and duplicate provider event IDs are deterministic.
- Source, source URL/document, and import/provider provenance are retained.
- Diagnostics contain only provider, request domain, status, row count, failure class, and fetch time.
- Tokens, auth headers, account IDs, credentials, and raw provider payloads are absent.
- Public schema compatibility keeps both `events` and legacy `items` list fields, with `events` canonical and `items` derived from `events`.
- Divergent provider or schema input cannot make public `items` differ from `events`.
- A future manual import must reject rows without ticker, event type, source provenance, and at least one usable event date.

Live provider tests remain out of deterministic CI. They require an approved commercial entitlement and sanitized fixtures.

Offline TestClient note: importing the full FastAPI app may import unrelated LLM modules because the v1 router registers all endpoint groups. If LiteLLM tries to refresh remote model pricing during a stock-only smoke in a network-blocked environment, treat it as unrelated app-import noise unless the stock/corporate-actions route fails. Deterministic tests that need app import can use the existing `tests.litellm_stub.ensure_litellm_stub()` helper rather than changing production startup behavior.

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
- Watchlist and company trade tape remain list data as `trade_tape`.
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
