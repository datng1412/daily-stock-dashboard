# VN Dashboard Roadmap

## Purpose

The Vietnam dashboard is a data-quality-first, source-aware stock inspection workspace. It should help users inspect price, volume, source coverage, unavailable states, and data freshness without turning the UI into trading advice.

The dashboard must remain:

* Data-focused
* Inspect-only
* Source-aware
* Clear about stale or unavailable data
* Neutral in wording

## Phase 4.11C - Completed-session SSI 1m history (implemented)

- Added the isolated `/vn/intraday-chart` contract for one explicit prior Vietnam date using only SSI `IntradayOhlc` resolution 1, fixed page 1/1,000, one call per cache miss, strict Vietnam-time normalization, sparse gaps, and deterministic duplicate-minute selection.
- Added a bounded 500-entry process-local LRU with 24-hour positive/no-data TTL, 60-second negative TTL, and seven-day stale-if-error recovery.
- Added dashboard `1D | 1m history` ownership, explicit completed-date selection, request-ID stale-response guards, Unix-second Lightweight Charts data, active-bar indicators, and `Daily S/R` labelling.
- Deferred current-session history, 5m/15m/30m/1h, aggregation, further pagination, HNX/UPCOM verification, realtime candles, and external/fallback providers.
- Automated browser smoke remains pending because the local browser integration failed before navigation with `Cannot redefine property: process`; do not treat deterministic tests as visual/network proof.

## Phase 4.11D-2 - Current-session delayed SSI 1m history (implemented)

- The existing endpoint now accepts Today in Vietnam time and rejects only future dates. SSI `IntradayOhlc` remains the sole candle source; D1/latest-price ownership remains SSI DailyOhlc.
- Current responses expose scheduled session, freshness, provider-refresh time, newest raw-bar age, and response-level provisional/inferred-final state. The schedule is clock-derived and holiday/halt/half-session/HNX/UPCOM semantics remain unresolved.
- Current-date cache bounds are 15 seconds positive, 5 seconds empty, 10 seconds negative, and five minutes stale-if-error. Completed-date 24-hour/60-second/seven-day behavior remains unchanged.
- The dashboard now presents `1D | 1m`, defaults 1m to Today, retains completed selection, polls at minute boundary plus seven seconds only during eligible sessions, wakes once after lunch, reconciles once after close, pauses while hidden, and never labels this delayed path `Live`.
- Phase 4.11D-3 remains blocked: X-TRADE lacks proven identity/sequence/replay semantics and cannot construct candles.

### Phase 4.11C-1 - Runtime validation fixes

- Fixed the RSI pane display defect without changing Wilder/RMA calculations: canonical 0–100 RSI values now use an explicit numeric series formatter and the existing supported 0–100 autoscale instead of inheriting the board-price formatter.
- Separated `Timeframe` (`1D`, `1m history`) from the D1-only `Range` (`1M`, `3M`, `6M`, `1Y`) controls. The completed-date control replaces the range group in 1m history.

### Phase 4.11C-2 - Runtime scale and Vietnam-time formatting

- Removed chart-level board-price formatter ownership after browser evidence showed it overrode the RSI series formatter. Pane 2 now exclusively owns its visible right scale, retains canonical RSI values, fixes the supported autoscale to 0–100, and keeps guides at exactly 30 and 70.
- Added deterministic `Asia/Ho_Chi_Minh` formatting for one-minute axis ticks (`HH:mm`), native crosshair labels, and HTML tooltips without shifting Unix timestamps. Daily mode continues to use `BusinessDay` tick fallback and date labels.
- This is frontend presentation work only: no backend, provider, cache, endpoint, request ownership, timeframe, aggregation, or data-source behavior changed. Automated browser proof remains subject to the documented in-app browser setup limitation.
- Validation passed 228 focused frontend tests, 18 formatter tests under a non-Vietnam process timezone, 8 endpoint regression tests, TypeScript, ESLint, and production build. The broader suite retained the known four unrelated failures (839 passed, two skipped); browser setup again stopped before navigation with `Cannot redefine property: process`, so visual and network proof remain explicitly unverified.
- Removed pre-route regex interception for `interval`; unsupported values now return `422`, `vn_intraday_chart_invalid_request`, and `Only interval=1m is supported` before the SSI service is called.
- Retained the 148 px right price-scale minimum because browser automation remained blocked before navigation and no responsive evidence justified changing readable S/R labels.
- Focused validation passed 160 backend tests and 226 frontend tests, Python compilation, TypeScript, ESLint, and production build. The broader frontend suite retained four unrelated baseline failures with 837 passes and two skips.
- A current-repository backend runtime verified both custom 422 contracts. A final spaced, single-call valid-history attempt returned `status=unavailable`, `failure_class=network_error`, and zero bars in the restricted validation environment, so the earlier 226-bar runtime proof remains the latest usable-session evidence and no new visual/network success is claimed.

Companion product docs:

* `docs/VN_PRODUCT_SPEC.md` defines the product goal, screens, UX principles, MVP scope, and milestones.
* `docs/VN_DATA_CONTRACT.md` defines public statuses, null/empty missing-data rules, live-section contracts, source ownership, and UI rendering rules.
* `docs/SSI_DATA_CAPABILITY_MATRIX.md` records current audit evidence for displayable data domains and should be consulted before adding fields or UI modules.
* `docs/VN_DATA_QUALITY_TODOS.md` tracks prioritized data correctness, live-section semantics, enrichment, and cleanup work.

## Core data rules

These rules must not be broken.

* SSI DailyOhlc is the strict daily OHLCV source for supported VN REST market data.
* `latest_price` comes from SSI DailyOhlc close when SSI daily data is available.
* SSI realtime snapshot is realtime board state only.
* SSI trade tape is separate from daily OHLCV.
* Do not replace daily close with SSI realtime snapshot.
* Do not use SSI trade tape as official daily close.
* KBS is legacy-only and disabled by default; it must require `VN_ALLOW_LEGACY_KBS_PROVIDER=true` and `KBS_ENABLED=true`.
* Do not infer corporate actions from price/reference gaps.
* Do not mutate raw OHLCV close for dividends.
* Corporate actions must come from an explicit event/history source.
* No trading-instruction, price-target, or recommendation wording.
* Use neutral labels such as status, trend, momentum, liquidity, source, unavailable, last updated.

## Provider strategy

This roadmap is the source of truth for Vietnam dashboard provider ownership. SSI FastConnect Data is the strict official market-data source for supported Vietnam market data, including realtime snapshot and trade-tape contracts where SSI endpoints are available. Mozyfin is disabled for VN dashboard runtime because the free tier no longer supports the news/social API paths the dashboard previously used. KBS is disabled by default and is legacy-only behind explicit development flags.

Phase SSI-V3-A1 records the live FastConnect migration gate: official V3 API/SDK contracts were mapped, then one authorized existing-key request received HTTP 401 when current V2 values were supplied as V3 raw `apiKey`/`apiSecret`. Outcome D keeps V2 production ownership unchanged while SSI resolves V3 activation and identifier/key mapping. The customer notice records V2 maintenance through 30/06/2027 and V3 replacement from 01/07/2027. See `docs/SSI_FASTCONNECT_V3_MIGRATION.md`.

Phase SSI-V3-B2 implements the offline disabled V3 REST foundation: pinned official SDK, dedicated configuration, lazy shared Auth/Data lifecycle, and normalized securities, daily/completed-history OHLC, index-list, and index-summary capabilities. Phase SSI-V3-B3 adds direct-only, production-disabled `securitiesSummary` normalization for symbol history and same-shape index rows, retaining official gross foreign fields omitted by the high-level SDK model. Missing remains null, zero remains zero, no scaling is applied, and net volume/value require complete gross pairs. DailyStockPrice, public foreign-flow history/APIs, analytics, VN30 inputs, extended metadata, current-session intraday, production IndexComponents, and realtime remain explicitly V2-owned. No live credential/data check, fallback, shadow traffic, deployed enablement, API/frontend, cache, startup, or realtime change occurred. Units/finality/live parity remain gated; B4/B5 and realtime C remain separately authorized future phases.

Phase SSI-V3-B3.1 repairs the V3 Market Data REST credential gate: dedicated API key/secret are required, while Client ID is optional and private key/OTP remain unused. The new terminal-only acceptance tool is double-guarded and bounded to one authentication lifecycle plus four FPT/HOSE operations. On 2026-07-22 the REST selector remained V2 and the environment guard was disabled, producing G/NOT_RUN with zero provider calls; configured Client ID presence also means empty-Client-ID live authentication is not yet proven. This phase changes no public dashboard/API behavior, provider ownership, fallback rule, startup, or realtime path. B4 remains blocked on an accepted bounded live result plus unit/finality evidence.

### Current provider ownership

| Capability or data domain | Owner | Current implementation state | Dashboard rule |
| --- | --- | --- | --- |
| Securities | SSI FastConnect Data REST | Implemented and wired as same-provider metadata fallback | Use for symbol metadata |
| SecuritiesDetails | SSI FastConnect Data REST | Implemented and wired | Use for exchange, security type, listed info, issuer/name, lot size, listed shares, and listed date if available |
| IndexList | SSI FastConnect Data REST | Implemented and exposed through backend API | Discover official index identifiers instead of hardcoded assumptions |
| IndexComponents | SSI FastConnect Data REST | Provider, service, API, and VN30 live discovery coverage added | Use for index membership and VN30 diagnostics only when SSI returns exact real rows |
| DailyOhlc | SSI FastConnect Data REST | Implemented and wired for daily data/chart | Use for daily OHLCV, chart candles, and internal indicators |
| IntradayOhlc | SSI FastConnect Data REST | Implemented and wired for watchlist/company intraday pulse | Use for compact intraday candles; keep separate from daily close and SSI realtime |
| DailyStockPrice | SSI FastConnect Data REST | Implemented and wired for selected-ticker enrichment | Use for reference, ceiling/floor, adjusted close if provided, matched volume/value, put-through volume/value, and foreign buy/sell/net volume/value |
| DailyIndex | SSI FastConnect Data REST | Implemented provider/service/API/dashboard context with 29-day chunking | Use only for optional source-labeled index value, change, breadth, and liquidity |
| Realtime snapshot | SSI FastConnect Data streaming | Provider, service, API, and UI contract added; buffered `X`, `X-QUOTE`, `X-TRADE`, and `F` parser coverage exists; config-disabled background manager/cache skeleton added; official-client adapter added behind disabled runtime flag; Phase 4.7B keeps public copy short and moves technical detail to sectioned diagnostics; Phase 4.8R adds market-session-aware stream-health diagnostics, active-window stale-stream watchdog reconnects, after-hours last-known-row copy, and tab-focus selected live refresh | Keep unavailable and separate from daily close, intraday, trade tape, session status, and official daily OHLCV until the background adapter safely populates current rows |
| Trade tape | SSI FastConnect Data streaming or future verified trade contract | Phase 4.7C adds a bounded process-local X-TRADE event buffer populated only by the background streaming manager; Phase 4.8E adds startup-owned `X-TRADE:{symbol}` subscriptions when trade tape is enabled; Phase 4.8E-2 returns buffered timestamped rows even when stream freshness is stale; Phase 4.8E-3 shows SSI-style B/S and change columns from explicit side/reference fields; Phase 4.8E-4 maps observed `BU`/`SD` side codes while preserving raw side audit fields; true historical list/history semantics still need confirmation | Keep latest-event tape separate from official daily OHLCV, DailyStockPrice, and realtime snapshot |
| Trading session/status | SSI FastConnect Data streaming `F:{symbol}` | Phase 4.8G adds background lifecycle subscription, parser, dedicated cache, optional watchlist fields, and diagnostics for raw SSI `TradingSession` / `TradingStatus` context | Code meanings, final-close/finality semantics, and polished frontend UI remain deferred until live payload evidence proves them |
| Legacy realtime snapshot/trade tape | KBS | Disabled by default; only available behind explicit legacy flags | Do not silently fallback from SSI to KBS |
| News | Future NewsProvider | Disabled by default; Phase 5.1B Vnstock status gate is `blocked_pending_terms`; Phase 5.1B-Local permits only explicit local/personal bounded RSS mode; Phase 5.1C permits only selected/company-ticker Community headlines (max 3, 30-minute cache) with validated absolute links only | Do not call Mozyfin; do not treat local personal Vnstock modes as production provider or SSI market-data fallback |
| Unsupported fundamentals | External provider required | Not implemented | Keep explicitly labeled; do not mix with SSI market-data fields |
| BCTC/KQKD, financial statements, financial ratios | External provider required | Not implemented | Investigate separately |
| Corporate actions, dividends, rights, splits | External provider required | Stub/unavailable | Events must come from explicit source data |
| Macro/Fed/oil/USD/gold | External provider required | Not implemented | Keep outside SSI market-data ownership |

SSI should be used for symbol metadata, exchange/security type/listed info when available, index list/components, daily OHLCV, chart candles, internal indicators from SSI OHLCV, reference/ceiling/floor, adjusted close if provided, matched volume/value, put-through volume/value, foreign buy/sell/net volume/value, daily index value/change/breadth/liquidity, intraday OHLCV, realtime snapshot, trade tape, and raw `F:{symbol}` session/status context when the background stream cache has usable rows.

Mozyfin owns no VN dashboard runtime path. It must not be used for VN backend or UI news/social, OHLCV, chart, reference, foreign-flow, index, metadata, intraday, or fallback behavior. Future news should be implemented through a separate NewsProvider contract.

KBS owns no default VN dashboard runtime path. It is retained as an explicit legacy development provider for realtime snapshot/trade tape only and must not be used as silent fallback for SSI-owned data.

### Strict source rules

```text
If data is official market price/volume/index/symbol and SSI has an endpoint, use SSI.
If data is a technical indicator from price/volume, calculate internally from SSI data.
If data is realtime snapshot or trade tape and SSI is unavailable, show unavailable. Do not silently fallback.
If data is news/fundamentals/corporate actions/macro, use an external provider.
If SSI-owned data is unavailable, show unavailable. Do not silently fallback.
```

### Current known implementation state

* SSI AccessToken works when local SSI credentials are configured.
* DailyOhlc works for the direct 1Y query used by the chart path.
* DailyStockPrice works but requires 29-day provider-level chunking because SSI rejects broad ranges.
* DailyIndex works but requires 29-day provider-level chunking because SSI rejects broad ranges.
* IndexList is exposed through `/api/v1/stocks/vn/index-list` and should be used to discover SSI-returned index codes.
* IndexComponents is exposed through `/api/v1/stocks/vn/index-components?index_code=...`. The explicit normalized code is sent directly through the live-verified `indexCode` shape; IndexList is not a prerequisite. Empty/provider-failed responses still return `rows=[]`; do not hardcode components or fallback to another provider.
* SSI IntradayOhlc is implemented for the watchlist/company intraday pulse through the same SSI auth/cache path. If SSI returns no candles, stale rows, malformed rows, provider code `429`, or the endpoint is disabled, expose a clean SSI `disabled`/`unavailable` intraday status and keep daily rows OK.
* Phase 4.0B fixed the IntradayOhlc paging bug by using internal `pageSize=1000`, sorting provider rows, and applying the public candle limit afterward. Phase 4.0B-2 added sanitized failure classification for current live failures; the observed FPT failure was SSI provider code `429` with HTTP 200, classified as `rate_limited`. Phase 4.0B-3 added a symbol/timeframe-scoped cooldown after IntradayOhlc rate-limit signals so repeat requests return unavailable without hitting SSI.
* `/api/v1/stocks/vn/chart` should be SSI-backed and should return SSI source metadata.
* `/api/v1/stocks/vn/watchlist` must remain SSI-backed for SSI-owned fields, including daily close, reference, ceiling/floor, matched value, put-through value, foreign flow, and source metadata.
* `/api/v1/stocks/vn/company/{ticker}` is the current company research contract/page shell that reuses the SSI-backed watchlist row for market-data blocks.
* Mozyfin fallback for SSI-owned fields is not allowed.
* SSI realtime snapshot and trade tape are exposed through the existing realtime endpoints and dashboard/company UI blocks.
* Phase 4.0C-2 searched the repository for a supported SSI FastConnect realtime REST endpoint, SDK method, enum, docs reference, or hidden contract and did not find one.
* Phase 4.0C-3 confirmed SSI realtime is streaming-based and added deterministic parser coverage for buffered `X`, `X-QUOTE`, and `X-TRADE` messages.
* Phase 4.0C-5 added a config-disabled background streaming manager/cache skeleton. `get_realtime_snapshot()` can read only from a running manager and fresh cache when `SSI_STREAMING_REALTIME_ENABLED=true`; default runtime returns `SSI streaming realtime manager disabled.` and still does not probe speculative REST candidate names.
* Phase 4.0C-6 added the official `ssi-fc-data` adapter behind the same disabled runtime flag. The package is imported lazily, the official client is instantiated only on explicit manager start, and missing config/package states fail closed with sanitized reasons.
* Phase 4.0C-7E changed the default SSI streaming channel template to the live-verified no-space form `X:{symbol}`. Old spaced forms are preserved only for explicit overrides and diagnostics.
* Phase 4.0C-8 added a FastAPI startup/shutdown bootstrap for the SSI streaming realtime manager. It runs only when `SSI_STREAMING_REALTIME_ENABLED=true` and `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS` is a small explicit symbol list. Request handlers still only read cache/status and do not start streams or subscribe dynamically.
* Docker/Render images must install official SSI `python-fcdata` tag `v2.2.2` from `requirements.txt`. If the package is absent, an otherwise enabled backend can only report `package_unavailable` through `/api/v1/stocks/vn/realtime`; request handlers still must not start streams or subscribe dynamically.
* Phase 4.8R adds manager-owned stream health diagnostics and market-session-aware stale-stream recovery. Running/subscribed state alone is not health proof; health depends on last message age, observed message/parser counters, sanitized error state, reconnect state, and a holiday-unaware Vietnam session window. The lifecycle monitor may reconnect preserved bootstrap channels after stale inactivity with backoff/debounce only during active trading/auction windows; outside active windows stale/missing X, X-QUOTE, or X-TRADE rows classify as market closed or after-hours stale, preserve last-known rows where available, and do not trigger reconnect solely because counters stop advancing. Request handlers remain cache readers and do not add subscriptions.
* Phase 4.8R-Live after-hours proof on 2026-07-10 confirmed `post_close` resolves to `market_closed`/`after_hours_stale` rather than a reconnect loop: normal endpoint reads preserved 154 expected subscriptions with zero reconnects, stale X-QUOTE ladders stayed available as last-known rows, and DailyOhlc ownership remained unchanged. The run also fixed a duplicate-bind shutdown race that could otherwise let a late client start revive the manager after shutdown. Active-window health progression and a live manager reconnect remain future runtime-proof items.
* Phase 4.0C-10B release-gate validation confirmed disabled and enabled SSI realtime modes keep daily watchlist rows on `SSI DailyOhlc`, keep optional realtime separate, stop polling while the tab is hidden, and shut down the lifecycle with `SIGINT` without traceback or secret-like log output. Local `npm.cmd` remained blocked by the Windows host-profile `EPERM` issue, so web validation used direct local Vite/Vitest entry points. In the disabled-mode headless browser smoke, the chart card was attached with 125 SSI daily points but its bounding box stayed hidden; the enabled-mode smoke rendered the chart card visibly.
* Phase 4.5B implemented bounded SSI DailyStockPrice historical foreign-flow summaries from the existing per-symbol recent window. Current classification: DailyOhlc and DailyStockPrice are `strong`; IndexList, exact VN30 IndexComponents, and supported market metadata are `usable`; DailyIndex and IntradayOhlc are `partial`; true trade-tape history is `unavailable_parameter_unknown`; realtime snapshot is `optional_live_dependent`; `VNINDEX` remains unresolved; fundamentals, statements, ratios, corporate actions, dividends/rights/splits, news, and macro are `external_provider_required`.
* Phase 4.5C live gate on 2026-06-29 confirmed SSI AccessToken, DailyOhlc, chunked DailyStockPrice, IndexList, DailyIndex, and VN30 IndexComponents are reachable with sanitized smoke output. DailyStockPrice recent history populated 20 rows for FPT/HPG/SSI and produced non-null 5D/20D foreign-net summaries while `latest_price_source` remained `SSI DailyOhlc`. VN30 DailyIndex remained `partial` because the public row lacked a usable positive `index_value` and `exchange`; exact `VNINDEX` remained unresolved. Intraday, realtime snapshot, and trade tape remained optional/unavailable without blocking daily rows.
* SSI realtime/trade-tape live endpoint names and entitlements may return unavailable. Unavailable states should include sanitized diagnostics without tokens, credentials, auth headers, or raw provider bodies.
* Dashboard provider-status UI must keep core daily SSI availability separate from optional SSI realtime, SSI trade tape, SSI index components, and disabled news states. A `Partial` dashboard status can mean optional sections are unavailable; it must not imply daily SSI data failed when daily rows are OK.
* KBS legacy realtime/trade-tape paths are disabled by default and require explicit legacy flags.
* News/social are disabled/not implemented until a separate NewsProvider is added.
* Local DB market-data storage is deferred; current mode is SSI live API plus backend cache/TTL.

## Product phase plan

This is the end-to-end VN dashboard product plan. Phase 0 freezes the current SSI provider milestone. Later phases expand product quality, diagnostics, enrichment, and workflow without changing the core product boundary: data quality first, no hidden fallback providers, no fake realtime, and no recommendation wording.

### Phase 0 - SSI Provider Milestone Freeze

Purpose:

Freeze and commit the current SSI-provider migration milestone.

Scope:

* SSI daily data is primary.
* Mozyfin is disabled for VN runtime.
* KBS is legacy optional only and disabled by default.
* News is disabled.
* Live sections return `null` or `[]` when unavailable.
* UI does not render fake metrics for unavailable live sections.
* Product/data-contract docs define the product boundary.

Validation:

* Backend tests:
  * `tests/test_vietnam_observability.py`
  * `tests/test_vietnam_market_service_no_mozyfin.py`
  * `tests/test_vietnam_market_service_realtime.py`
  * `tests/test_vietnam_market_service_intraday.py`
* Frontend validation from `apps/dsa-web`:
  * `npm run build`
  * `VietnamCompanyResearchPage`
  * `VietnamDashboardPage.test.tsx`
* `git diff --check`
* Manual smoke:
  * `/vietnam`
  * `/vietnam/company/FPT`

Suggested commit:

```text
feat: make SSI the VN dashboard provider
```

Exit criteria:

* Daily SSI data is visible.
* News is disabled.
* Intraday, realtime, and trade tape unavailable states are concise.
* No fake metric rows.
* No endpoint dumps in primary UI.
* No Mozyfin/KBS normal fallback wording.

### Phase 1 - Data Quality Summary

Purpose:

Turn data inconsistencies and missingness into visible product features.

Problems:

* DailyOhlc versus DailyStockPrice mismatch can occur on the same ticker/date. Latest smoke example:
  * FPT `2026-06-22` DailyOhlc/dashboard close: `70,700`.
  * FPT `2026-06-22` DailyStockPrice close/adjusted close: `70,800`.
  * DailyOhlc volume: `3,642,400`.
  * DailyStockPrice matched volume: `3,643,500`.
* `final_close_status` can be `unknown`.
* `adjusted_price_status` can be `unknown`.
* Intraday can be stale or mismatched.
* `realtime_snapshot` can be `null` or unavailable.
* `trade_tape` can be empty or unavailable.
* Profile metadata can be partial.

Planned behavior:

* Add Data Quality Summary to dashboard selected ticker and company detail.
* Show source mismatch explicitly.
* Show canonical latest price source.
* Show final/provisional/unknown close state.
* Show adjusted/unadjusted unknown state.
* Show intraday stale/unavailable.
* Show realtime/trade-tape unavailable.
* Show metadata partial state.

Acceptance criteria:

* User does not need to compare cards manually to notice mismatches.
* Canonical latest price source is explicit.
* Data-quality warnings are neutral.
* Daily data remains visible even when live sections are unavailable.

Suggested commit:

```text
feat: add VN data quality summary
```

### Phase 2 - Clean Public Contract and Diagnostics Split

Purpose:

Make the API contract and diagnostics separation clean.

Problems:

* Trade tape unavailable contract must be `trade_tape = []`, not a placeholder object with inner `trades: []`.
* `realtime_status.message` and `trade_tape_status.message` can contain endpoint dumps.
* Stale intraday metadata can appear as top-level usable-looking data.
* Top-level `intraday_timeframe` can be confused with actual candle interval.
* Realtime/trade-tape 404 responses can refresh too aggressively.

Contract target:

* `intraday_pulse = null` when unavailable or stale.
* `intraday_candles = []` when unavailable, stale, or no usable rows exist.
* `realtime_snapshot = null` when unavailable.
* `trade_tape = []` when unavailable or no rows exist.
* `*_status` contains:
  * `status`
  * `source`
  * short user-safe message
* `diagnostics` contains:
  * attempted endpoints
  * last endpoint
  * HTTP status
  * raw provider error summary
  * retryable flag
  * stale date mismatch details

Acceptance criteria:

* No placeholder object for missing list data.
* Primary UI never consumes endpoint dumps or raw provider errors.
* Diagnostics preserve debug detail.
* 404/non-retryable failures use backoff or longer TTL.
* UI availability is based on status plus null/empty checks.

Suggested commit:

```text
fix: clean VN live data contract and diagnostics
```

### Phase 3 - Progressive Dashboard Workspace

Purpose:

Turn `/vietnam` into a progressive, source-aware market inspection workspace:

```text
Daily scan first.
Ticker explanation second.
Live/diagnostics third.
External/future data last.
```

Phase 3.0A status:

* Implemented frontend-only watchlist preset groups on `/vietnam`.
* Preset names: VN30, Banks, Securities, Real estate, Consumer, Logistics, Tech, Oil & gas, and Electricity.
* Preset switching replaces the active ticker list through the existing watchlist request path.
* If the current selected ticker is in the new preset, it remains selected; otherwise the first preset ticker becomes selected.
* Presets are scan buckets only. New provider calls, polling changes, source semantics changes, and trading-advice wording remain out of scope.

Phase 3.0B status:

* Added a `Custom` preset workflow on `/vietnam`.
* Custom input accepts comma, whitespace, semicolon, and newline separators; normalizes tickers to uppercase; removes duplicates; and keeps only the first 30 valid tickers.
* Custom lists can be applied for the current session, saved to browser localStorage under `vnDashboard.customWatchlist.v1`, or cleared locally.
* Invalid or empty custom input does not replace the active watchlist.
* Custom persistence is local-only: no backend storage, server sync, new endpoints, provider calls, polling changes, or source semantics changes.

Phase 3.1 status:

* Polished the `/vietnam` indicator table as the main daily scan surface.
* Prioritized compact columns for ticker, SSI DailyOhlc daily close, percent change, RSI14, MA state, volume versus 20D average, SSI DailyStockPrice foreign net volume, data quality, and realtime/live status.
* Added client-side sorting for ticker, daily close, percent change, RSI14, volume ratio, foreign net volume, and data quality.
* Sorting keeps null values last, does not issue API calls, and does not change the selected ticker.
* Realtime/live status remains a separate availability badge and does not replace daily data.

### Phase 3.2 - Data Readiness and Progressive Loading UX

Phase 3.2A status:

* Added a compact `/vietnam` Data Readiness strip near the top of the dashboard.
* Readiness items cover Daily data, Reference / foreign, Indicators, Intraday, Realtime, Trade tape, and News.
* The strip is visual/status-only and derives from already loaded frontend watchlist data, selected ticker data, realtime quote status, and trade-tape status.
* No backend/API contract fields, provider calls, endpoints, polling, or request-orchestration behavior changed in Phase 3.2A.
* Provider endpoint details, HTTP status, and raw provider summaries stay in diagnostics rather than the primary readiness strip.

Phase 3.2B status:

* Added lightweight explanations to the `/vietnam` Data Readiness strip.
* Each readiness item exposes factual source/status context through tooltip/accessibility text.
* Explanations derive from the same already loaded frontend watchlist, selected ticker, realtime, and trade-tape state used by the strip.
* No backend/API contract fields, provider calls, endpoints, polling, or request-orchestration behavior changed in Phase 3.2B.
* Explanations do not expose endpoint details, HTTP status, retryability, raw provider summaries, or advisory labels.

Phase 3.2C status:

* Kept previous successful watchlist rows visible while refresh, preset, reset, or custom apply requests are in flight.
* Added compact `Updating...` and `Last update failed` states with `Showing previous data` helper copy.
* Preset/custom/reset changes are pending intents and commit only after the existing watchlist request succeeds.
* Request-level failures preserve the previous committed rows, list/preset, and selected ticker.
* Successful responses still commit when requested tickers return unavailable rows, because unavailable rows are row-level states rather than request-level failures.
* Local request-id protection ignores older/slower responses so rapid preset/custom changes cannot overwrite newer intent or clear newer error/loading state.
* No backend/API contract fields, provider calls, endpoints, polling, dependencies, or public contracts changed in Phase 3.2C.

Phase 3.2D status:

* Added compact section-level states to existing `/vietnam` areas, including refresh controls, watchlist controls, the indicator scan table, selected ticker summary, stock detail, inspect chart, intraday, realtime, trade tape, and diagnostics/source details.
* Added serious daily-data-unavailable copy when no daily rows are available after first load.
* Kept optional intraday, realtime, trade-tape, and disabled news states visually minor when valid daily SSI rows exist.
* Preserved Phase 3.2C previous-data refresh behavior: prior rows remain visible during refresh and pending preset/custom changes.
* Kept provider endpoint details, HTTP status, retryability, and sanitized raw provider summaries in diagnostics rather than primary UI.
* No backend/API contract fields, provider calls, endpoints, polling, dependencies, or public contracts changed in Phase 3.2D.

Request-state vocabulary:

* `idle`
* `loading`
* `refreshing`
* `success`
* `partial`
* `failed`

Clarification: `success` is frontend request-state vocabulary. The preferred user-facing section label is `ready`.

Acceptance criteria:

* First load and refresh are visually distinct.
* Daily scan rows remain visible during refresh when prior data exists.
* Optional realtime, trade-tape, news, or future-module failures do not erase valid daily SSI data.
* Provider endpoint details remain in diagnostics, not the primary readiness strip.

### Phase 3.3 - Selected Ticker Progressive Disclosure

Goal:

Keep the selected ticker top summary compact and move secondary fields into expandable groups:

* Price context.
* Flow context.
* Technical context.
* Live context.
* Source coverage.
* Diagnostics.

Phase 3.3A status:

* Reworked the `/vietnam` selected ticker header into a compact daily explanation surface: daily close, change percent, daily volume versus 20D average, SSI DailyStockPrice foreign net volume, RSI14/MA state, live status, and compact Data Quality Summary.
* Moved secondary selected ticker details into disclosure groups: Price context, Flow context, Technical context, Live context, Source coverage, News context, and Diagnostics.
* Kept Price context open by default and kept live/source/news/diagnostics lower priority.
* Preserved existing data, source ownership, diagnostics, provider behavior, fetch paths, polling behavior, and API contracts.
* Kept raw fields, cache internals, and rule inputs in Diagnostics rather than primary cards.

Phase 3.3B status:

* Shortened selected ticker labels and reduced visible duplication across the compact header and disclosure groups.
* Kept source ownership clear at section level without repeating `SSI DailyOhlc` or `SSI DailyStockPrice` on every field.
* Kept News context optional and used `News available`, `News disabled`, or `News not implemented` based on already loaded data/status only.
* Kept raw fields, endpoint/provider diagnostics, cache internals, and rule inputs inside Diagnostics.
* Added no data fields, endpoints, provider calls, polling, dependencies, fetch paths, or API contract changes.

Folded-in historical Phase 3/5 items:

* Profile completeness and partial metadata belong in source coverage and Data Quality Summary.
* Metadata follow-up should improve explanation quality without failing valid daily data.
* Foreign-flow detail should remain DailyStockPrice-specific and source-labeled.

Acceptance criteria:

* Selected ticker explanation is compact by default.
* Daily close, reference/limits, matched volume, foreign flow, chart, and compact Data Quality Summary remain easy to inspect.
* Diagnostics are available but lower priority.
* No full-page debug-board layout.

### Phase 3.4 - Data Request Orchestration Cleanup

Goal:

Make frontend/UI request behavior explicit without changing public API contract fields:

* `idle`
* `loading`
* `refreshing`
* `success`
* `partial`
* `failed`

Rules:

* Ignore older or slower responses.
* Abort or ignore obsolete requests on rapid preset switches.
* Prevent duplicate requests from typing, sorting, or diagnostics expansion.
* Do not document these request states as API response fields.

Acceptance criteria:

* Rapid preset changes cannot reapply stale watchlist responses.
* Sorting and filtering remain client-side.
* Typing in custom watchlist input does not trigger API calls.
* Diagnostics expansion does not call providers unless a future task explicitly designs it.

### Phase 3.5 - Table Filtering and Scan Presets

Goal:

Add local filters for the scan table:

* Data quality.
* Live status.
* Foreign net positive/negative.
* Volume ratio.
* RSI range.
* Ticker search.

Rules:

* Client-side only.
* No recommendation wording.
* Filtering must not trigger watchlist reloads.
* Filtering must not hide unavailable tickers by default without a visible active filter.

Acceptance criteria:

* Existing preset and custom watchlist behavior remains intact.
* Sorting and filtering compose predictably.
* Null values stay visible unless filtered by an explicit state filter.

Phase 3.5A status:

* Added compact local scan controls near the indicator table for ticker search, data quality, live status, foreign net, volume versus 20D average, and RSI14.
* Filters are React local state only. They are not persisted to localStorage, do not use URL query params, do not create saved filter views, and do not call backend APIs or provider paths.
* Filtering starts from the current committed watchlist rows, applies filters with AND logic, then applies the existing client-side sort to the filtered rows.
* Data quality filters map existing `ok`/`ready`-like row status to `Ready`, partial/degraded row status to `Partial`, and missing, unavailable, disabled, or unknown row quality to `Unavailable` unless an existing row-level state is more precise. Raw diagnostics are not inspected for data-quality filtering.
* Foreign net positive/negative, elevated volume, and RSI numeric ranges are neutral scan categories only.
* Reset filters clears only ticker search and filter select values. It does not clear the custom watchlist input, active preset, active watchlist, committed rows, or selected ticker.
* The table shows a client-derived `Showing X of Y rows` count and a compact `No rows match current filters.` empty state when filters exclude all rows.
* If the selected ticker is hidden by active filters, the selected ticker summary remains visible when the row data still exists and the table shows `Selected ticker is hidden by filters.` No different ticker is auto-selected because of filters.
* No backend/API contract fields, endpoints, provider calls, polling, dependencies, or source semantics changed in Phase 3.5A.

## Data-first implementation pivot

The dashboard has enough UI foundation after Phase 3.5A. The recommended implementation order is now:

```text
Data capability first.
Then reliability.
Then contract/status normalization.
Then UI rendering.
```

Each next task must answer:

* Does the data exist?
* Is it reliable?
* Is it fresh?
* Which source owns it?
* Which exact fields are safe to display?
* What should remain unavailable, disabled, or external-provider-required?

Phase 4.0A adds the local capability audit and matrix. Additional table-filter polish, saved filter views, further selected-ticker copy polish, broader dashboard layout changes, chart UX polish, and new visual badges are paused. They are deferred, not cancelled, until the data-capability matrix and priority data fixes are complete.

## Priority data domains

1. SSI DailyOhlc: daily OHLCV and canonical latest daily close.
2. SSI DailyStockPrice: reference, matched statistics, and foreign flow.
3. Technical indicators derived from SSI DailyOhlc.
4. Intraday OHLCV cadence and freshness.
5. Realtime snapshot.
6. Trade tape.
7. Index and index components.
8. Profile and securities metadata.
9. News external provider.
10. Financials external provider.
11. Corporate actions and dividends external provider.
12. Macro and events external provider.

This ordering does not claim availability. Every domain must be classified from evidence before implementation relies on it.

## Do not implement yet

* News UI expansion before a NewsProvider exists.
* Financials UI before a provider contract exists.
* Corporate actions or dividends before a provider contract exists.
* WebSocket or realtime streaming before SSI realtime is verified.
* Backend database or cache expansion before measured latency or rate-limit evidence exists.
* More UI polish unless it is required to expose verified data safely.

### Phase 3.6 - Chart UX Upgrade

Status: deferred after Phase 3.5A pending the data-capability matrix and priority reliability work.

Goal:

Improve the daily chart as an inspection tool:

* Better chart loading and empty states.
* Source/freshness line.
* Better tooltip.
* Keep daily chart separate from realtime and intraday.

Rules:

* Chart candles remain SSI DailyOhlc.
* Realtime snapshot and intraday pulse must not overwrite daily chart data.
* Missing chart data should render a section state, not fake candles.

Acceptance criteria:

* Chart loading, refreshing, empty, and unavailable states are distinct.
* Source and freshness are visible without clutter.
* Tooltip values are source-aware and avoid fake precision.

Current issues:

* Profile can show unavailable fields while source coverage says OK.
* Price Summary and Trading Stats can show different close values without a prominent warning.
* Source Coverage is useful but too technical as a primary section.
* News/Financials/Events are separate empty cards.
* Live sections are truthful but should be grouped and lower prominence when unavailable.

Target layout:

1. Header / Hero
   * ticker
   * exchange
   * latest price
   * price date
   * canonical source
   * overall data status
   * badges: Daily OK, Profile partial, Live unavailable, News disabled, Inspect-only
2. Data Quality Summary
   * DailyOhlc versus DailyStockPrice mismatch
   * final close status
   * adjusted price status
   * intraday stale/mismatched
   * realtime unavailable
   * trade tape unavailable
   * metadata partial
3. Daily Core Data
   * Price Summary - canonical daily source
   * Trading Stats - source-specific values
   * Foreign Flow - SSI DailyStockPrice
   * Technical Snapshot - derived from SSI DailyOhlc
4. Live Data Availability
   * Intraday
   * Realtime
   * Trade tape
5. Future Modules
   * News: disabled/not implemented
   * Financials: not implemented
   * Events/corporate actions: not implemented/unavailable
6. Diagnostics
   * Collapsible
   * Source coverage
   * Endpoint diagnostics
   * Cache metadata
   * Safe raw details

Acceptance criteria:

* Page reads like a data-quality report.
* Daily core data is dominant.
* Data-quality warnings appear above detailed cards.
* Profile status is partial when key fields are missing.
* Future modules are grouped.
* No endpoint dumps in primary UI.
* No recommendation wording.

Suggested commit:

```text
feat: redesign VN company detail as data quality report
```

### Phase 4.0A - VN Data Capability Probe

Goal:

Audit actual VN dashboard data capability before changing production behavior.

Scope:

* Add local audit script `scripts/audit_vn_data_capability.ps1`.
* Build SSI/data-capability matrix `docs/SSI_DATA_CAPABILITY_MATRIX.md`.
* Inspect domain presence, source ownership, freshness, row coverage, and safe display fields.
* Classify each domain using the current Phase 4.5A vocabulary:
  * `strong`
  * `usable`
  * `partial`
  * `optional_live_dependent`
  * `unavailable_parameter_unknown`
  * `unavailable_permission_or_entitlement`
  * `external_provider_required`
  * `not_implemented`
  * `deferred`
* Keep audit output secret-safe.
* Make no production behavior, API contract, provider-call, or UI change.
* Require future UI/data work to consult the matrix before adding fields.

Acceptance criteria:

* The matrix covers all priority data domains.
* The audit script consumes existing app endpoints only.
* Evidence distinguishes data absence from request failure.
* Optional unavailable domains are reported without making the audit fail when the audit request succeeds.
* External-provider-required domains are reported explicitly as external-provider-required, not implemented, or disabled.
* Phase 4.0B through Phase 4.4A can use the matrix to choose scoped reliability work.

### Phase 4.0B - Intraday Root-Cause and Implementation

Status: completed on 2026-06-24.

Goal:

Find the root cause for Phase 4.0A intraday unavailability and fix only the existing SSI intraday path when the evidence supports a backend/provider correction.

Scope:

* Trace the watchlist and company intraday path through `VietnamMarketService` and SSI IntradayOhlc.
* Verify whether the endpoint is called, wired, parsed, freshness-checked, and exposed through the existing public fields.
* Keep `intraday_pulse = null` and `intraday_candles = []` when SSI intraday rows are stale, mismatched, empty, disabled, failed, or malformed.
* Improve audit evidence for intraday status, public candle count, timestamp range when public candles exist, requested timeframe, observed granularity, date match, and unavailable reason.
* Keep daily OHLCV, `latest_price`, DailyStockPrice, realtime, trade tape, news, index, financials, corporate actions/dividends, macro, provider credentials, and frontend UI polish out of scope.

Rules:

* Do not infer intraday from daily data.
* Do not use realtime snapshot or trade tape as intraday fallback.
* Do not add Mozyfin/KBS or new provider fallback.
* Do not weaken the freshness guard that compares SSI IntradayOhlc date with SSI DailyOhlc date.

Result:

* Existing SSI IntradayOhlc wiring is active; the root cause was a fetcher page-size/order bug, not a missing company route call.
* Before the fix, the dashboard requested a 7-day IntradayOhlc window with public `intraday_limit` as SSI `pageSize` and `ascending=true`. With the default public limit of 8, SSI returned only oldest first-page rows from `2026-06-17`, so the service correctly marked intraday stale against SSI DailyOhlc `2026-06-24`.
* The SSI fetcher now paginates IntradayOhlc internally with `pageSize=1000`, sorts normalized rows, and returns only the latest public limit to the service/API.
* Direct patched-fetcher verification returned 8 FPT rows using 2 pages, from `2026-06-24T14:23:56` to `2026-06-24T14:45:00`.
* Isolated patched-backend audit reported intraday as `partial`: FPT had `intraday_status=ok`, `intraday_latest_date=2026-06-24`, `daily_price_date=2026-06-24`, `date_match=matched`, public candle count 8, and non-null pulse, while some other audit tickers still returned unavailable/request-failed intraday.
* The backend now filters normalized intraday rows that have no usable timestamp/date or close value so null-only malformed rows remain unavailable instead of becoming an `ok` pulse.
* Intraday remains a partial capability until current-date coverage is observed across the broader ticker set.

Acceptance criteria:

* Root cause documented in `docs/SSI_DATA_CAPABILITY_MATRIX.md`.
* Mocked backend tests cover available, stale/mismatched, empty, malformed, failure, and disabled intraday paths.
* Audit script reports intraday status and evidence without direct SSI calls or full raw payload dumps.
* Daily SSI rows remain valid when intraday is optional/unavailable.

### Phase 4.0B-3 - Intraday Rate-Limit Guardrails

Status: completed on 2026-06-25.

Goal:

Reduce repeated SSI IntradayOhlc calls after provider-side rate-limit signals while keeping the public intraday contract explicit and unavailable.

Result:

* Added `SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS=60` as the default per-process cooldown window; `0` disables the guard.
* The SSI fetcher records cooldown only after `rate_limited` classifications from HTTP `429` or SSI provider code `429`.
* Cooldown keys are scoped by normalized ticker and requested timeframe.
* Active cooldown returns `intraday_status.status=unavailable`, `failure_class=rate_limited`, `intraday_candles=[]`, and `intraday_pulse=null` without requesting a token or calling `GET /Market/IntradayOhlc`.
* Force-refresh callers still respect the fetcher cooldown because suppression happens before provider request construction.
* DailyOhlc, DailyStockPrice, `latest_price`, realtime snapshot, and trade tape behavior are unchanged.

### Phase 4.0C - SSI Realtime and Trade-Tape Verification

Status: realtime snapshot root cause verified; trade tape remains unavailable pending separate endpoint verification.

Goal:

Verify SSI realtime and trade-tape contracts.

Scope:

* Confirm endpoint names.
* Confirm entitlement/permission requirements.
* Confirm response row shapes.
* Classify provider errors:
  * 404 endpoint unavailable/not found.
  * 401/403 auth or entitlement.
  * 200 empty.
  * Timeout/network.
* Decide retry/backoff behavior.
* Keep the clean unavailable contract if endpoints remain unavailable.

Rules:

* Do not fake realtime from daily close.
* Do not use KBS fallback silently.
* Do not use FC Trading/order/account APIs.
* Do not claim live support until verified rows exist with `realtime_status.status = ok` or `trade_tape_status.status = ok`.

Acceptance criteria:

* Either SSI realtime/trade tape works with clear `ok` status and data rows, or it remains clearly unavailable with diagnostics.
* Non-retryable failures use longer TTL/backoff only if implementation evidence justifies it.
* UI states stay concise and daily scan data remains visible.

Phase 4.0C realtime snapshot result on 2026-06-24:

* `GET /api/v1/stocks/vn/realtime?tickers=FPT` is correctly wired through `VietnamMarketService.build_realtime_snapshot` to `SsiFastConnectFetcher.get_realtime_snapshot`.
* The live backend config was not disabled: the endpoint returned `unavailable`, not `disabled`.
* The observed live endpoint response returned `0` quote rows and reported a 404 from the SSI realtime REST candidate path.
* The force-refresh FPT audit reported `watchlist usable snapshots=0/1` while daily OHLCV, DailyStockPrice, foreign flow, indicators, and FPT intraday pulse stayed reliable.
* No realtime snapshot is inferred from daily OHLCV, intraday candles, or trade tape. Keep `realtime_snapshot=null` until SSI returns current usable realtime quote rows with `status=ok`.

Phase 4.0C-2 realtime endpoint discovery result:

* Repository discovery generated `ssi_realtime_endpoint_discovery.txt` and inspected existing SSI provider code, service code, config/env names, smoke scripts, integration docs, roadmap/runbook docs, and `docs/resources/realtime-data/ssi-iboard.md`.
* Found candidate names `RealtimeQuote`, `RealtimePrice`, `RealtimeSnapshot`, and `SecuritiesRealtime` only as existing speculative REST candidates, plus the internal `SsiFastConnectFetcher.get_realtime_snapshot` method and public `GET /api/v1/stocks/vn/realtime` route.
* Found no verified SSI FastConnect SDK package, endpoint path, SDK method, enum, or hidden repo contract for realtime quotes.
* `docs/resources/realtime-data/ssi-iboard.md` remains reference-only because authentication, rate limits, timestamp semantics, and price semantics are unknown.
* The fetcher no longer calls token or HTTP request paths for speculative realtime REST candidates.
* Deterministic tests keep realtime row mapping as a private parser regression, cover the explicit unavailable discovery state, and keep realtime unavailable separate from daily and intraday behavior.

Phase 4.0C-3 SSI streaming realtime result:

* Official SSI FastConnect realtime evidence points to streaming data types rather than REST quote endpoints.
* The fetcher now includes deterministic parser coverage for buffered `X`, `X-QUOTE`, and `X-TRADE` envelopes.
* `X-QUOTE` is quote context only and must not create a last-trade price.
* `X` and `X-TRADE` can populate latest-trade snapshot fields only when `LastPrice` is present.
* A single `X-TRADE` stream message is not full trade-tape history.
* Phase 4.0C-5 supersedes the parser-only runtime state with a config-disabled background manager/cache skeleton. The default response remains unavailable with `SSI streaming realtime manager disabled.`
* Phase 4.0C-6 adds the official-client adapter behind `SSI_STREAMING_REALTIME_ENABLED=false` by default. The adapter suppresses the official header-printing path during stream start, uses symbol-scoped channels only, and remains a background-manager path rather than a request-handler path.
* Phase 4.0C-7B adds `scripts/verify_ssi_streaming_realtime.py` as a dev-only local verification path. It validates config/channel safety, starts the manager explicitly in a standalone process, uses the real parser, polls only the script-local cache, and stops the manager in `finally`. It does not populate the FastAPI backend cache.
* Phase 4.0C-7C adds safe callback/channel diagnostics to the verifier, including diagnosis labels, bounded envelope key/type samples, sequential channel-template discovery, and optional `InsecureRequestWarning` suppression.
* Phase 4.0C-7D adds direct official-client handshake/subscription inspection, safe installed-package metadata inspection, selected-channel shape checks, and symbol-scoped channel format variants.
* Phase 4.0C-7E records the live no-space channel finding: `X:FPT`, `X-QUOTE:FPT`, and `X-TRADE:FPT` receive callbacks/cache hits in verifier runs, while `X: FPT`, `X-QUOTE: FPT`, and `X-TRADE: FPT` did not.
* Phase 4.0C-8 adds backend lifecycle startup/shutdown ownership for the process-local SSI streaming manager. Bootstrap symbols are configured by `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS`, default empty. Requests do not create streams, do not add subscriptions, and do not subscribe to symbols outside the startup list.
* Phase 4.0C-9 tunes realtime cache reads and UI polling: `/api/v1/stocks/vn/realtime` bypasses the generic VN response cache and returns no-store headers, quote polling is separate from watchlist/chart/company refresh with a 3-second default, trade-tape polling remains separately opt-in, and ISO timestamps with microsecond fractions render as Vietnam time with freshness labels.
* Phase 4.0C-10 hardens the SSI streaming realtime runtime with idle/stuck-stream diagnostics, lifecycle-owned reconnect monitoring, bounded exponential backoff, reconnect attempt counters, sanitized runtime diagnostics, and clean shutdown/cancellation. Phase 4.8R supersedes the earlier no-market-hours limitation with a holiday-unaware Vietnam session classifier: active-window stale streams may reconnect with debounce, while off-hours silence is classified as market closed/after-hours stale and does not create reconnect loops.
* Future streaming work must avoid `X: ALL` in runtime and must not run long-lived stream connections inside request handlers. WebSocket/SSE delivery and trade-tape product implementation remain future phases, not part of Phase 4.0C-10.

Phase 4.0C-4 official Python FC Data client inspection result:

* Installed package: `ssi-fc-data` / import module `ssi_fc_data`, version `2.2.2`.
* Relevant modules: `ssi_fc_data.fc_md_client`, `ssi_fc_data.fc_md_stream`, `ssi_fc_data.model.api`, and bundled `ssi_fc_data.signalr` transport modules.
* Official stream wrapper: `MarketDataStream(config, MarketDataClient(config))`.
* Start call: `MarketDataStream.start(on_message, on_error, selected_channel)`.
* Subscription/change call: `MarketDataStream.swith_channel(channel)`, which invokes SignalR hub method `SwitchChannels`.
* SignalR constants: `v2.0/signalr`, hub `FcMarketDataV2Hub`, message method `Broadcast`, error method `Error`.
* Subscription format is a caller-provided channel string. Live verification showed symbol-scoped no-space channels such as `X-TRADE:FPT`, `X-QUOTE:FPT`, or `X:FPT` receive callbacks, while spaced forms such as `X: FPT` did not. Do not use `X:ALL` or any `ALL` subscription.
* Runtime adapter remains deferred: the official client starts a daemon websocket thread, exposes no documented bounded receive/wait API, has a negotiation `print(self.headers)` path that can leak authorization headers, and its public `Connection.close()` path calls a non-existent transport `close()` method instead of the available `stop()` method.
* Minimal future live design: a background adapter that wraps or patches the official client to prevent header printing, subscribes only to symbol-scoped channels, writes latest parsed messages into the existing thread-safe cache, uses the Phase 4.0C-3 parser, and leaves request handlers as bounded cache readers.

### Phase 4.1A - Intraday Cadence and Freshness Correctness

Status: completed in the current working tree.

Goal:

Detect actual returned intraday cadence and avoid overclaiming a fixed interval unless verified.

Scope:

* Compare requested timeframe with returned candle spacing.
* Label stale, mismatched, unavailable, and disabled intraday states clearly.
* Keep intraday separate from daily close and realtime snapshot.

Acceptance criteria:

* UI labels describe the actual returned cadence or an unknown/unavailable state.
* Stale intraday never appears as a fresh live signal.
* Daily SSI rows remain valid when intraday is optional/unavailable.

Implemented result:

* `intraday_requested_timeframe` remains the request hint, while `intraday_actual_granularity`, `intraday_actual_granularity_seconds`, and `intraday_cadence_status` are derived from sorted provider timestamps.
* Cadence status is conservative: regular rows are `matched` or `different_from_requested`, irregular spacing is `irregular`, insufficient timestamps are `unknown`, and disabled/unavailable sections are `unavailable`.
* Stale/date-mismatched intraday still returns `intraday_candles=[]` and `intraday_pulse=null` with sanitized `stale_or_date_mismatched` diagnostics; daily SSI rows and `latest_price=SSI DailyOhlc` remain valid.
* Dashboard and company UI copy now says provider cadence or returned-cadence caveats instead of presenting requested `1h` as the actual interval.

### Phase 4.2A - DailyStockPrice Enrichment Reliability

Status: completed in the current working tree.

Goal:

Verify SSI DailyStockPrice enrichment fields and normalize missing or partial coverage.

Scope:

* Reference, ceiling, and floor.
* Matched volume and matched value.
* Foreign buy, sell, and net volume.
* Foreign buy, sell, and net value when SSI returns them.
* Date alignment, units, source labels, and row completeness.

Rules:

* Keep canonical daily close on SSI DailyOhlc.
* Do not substitute DailyOhlc volume for matched volume.
* Missing fields remain missing or partial; do not create synthetic values.

Acceptance criteria:

* Each enrichment field has verified source, unit, date, and missing-state behavior.
* Partial DailyStockPrice coverage does not invalidate usable DailyOhlc rows.

Implemented result:

* Existing evidence-backed aliases cover reference/limits, matched and put-through statistics, foreign volume/value, adjusted close, and trading date; no speculative provider aliases or chunking changes were added.
* Watchlist and company contracts now expose an explicit `SSI DailyStockPrice` block with availability status, quality status, date match, missing-field coverage, value-specific units, and sanitized diagnostics.
* Date alignment is `matched`, `mismatched`, `unknown`, or `unavailable`. A mismatch keeps the DailyOhlc row usable, marks enrichment partial, and surfaces a concise source-labeled caveat.
* Missing values remain null and absent units metadata does not imply availability. DailyOhlc volume and DailyStockPrice matched volume remain separate concepts.
* Dashboard and company UI show DailyStockPrice volume as shares and value/price fields as VND, hide missing optional metrics, and keep canonical daily close on SSI DailyOhlc.
* Targeted backend tests, company/watchlist frontend tests, TypeScript compilation, lint, and the production Vite build passed. Browser UI smoke passed against the current static build; current-code live API smoke was not run because the available port 8000 backend predated this phase and no separate credential-safe live process was available.

### Phase 4.3A - Profile and Securities Metadata Reliability

Status: completed on 2026-06-28.

Goal:

Verify SSI profile and securities metadata coverage without conflating metadata completeness with daily-row validity.

Scope:

* Ticker name.
* Exchange and market.
* Industry or sector when available.
* Security type.
* Issuer, lot size, listed shares, and listed date when available.

Acceptance criteria:

* Available fields have explicit SSI source ownership.
* Missing optional metadata remains null and produces partial metadata state.
* Metadata partial state does not make valid daily data unavailable.

Result:

* `SecuritiesDetails` remains the primary SSI metadata endpoint, with `Securities` as the only fallback and only within SSI.
* Symbol, exchange, market, name, English name, industry, sector, security type, issuer, lot size, listed shares, and listed date are normalized only from observed SSI aliases.
* Metadata now exposes independent provider availability and quality state through `status`, `quality_status`, `completeness`, `missing_fields`, and `field_coverage`.
* Metadata selection requires an exact requested-symbol match. A lone mismatched or symbol-less row is no longer accepted.
* Dashboard and company profile views hide missing metadata rows, show concise partial/unavailable states, and keep sanitized endpoint diagnostics collapsed.
* Valid SSI DailyOhlc and DailyStockPrice data remains usable when metadata is partial or unavailable. `latest_price` remains SSI DailyOhlc.
* Targeted validation passed: 106 backend tests and 141 dashboard/company frontend tests, plus direct TypeScript compilation, ESLint, and production Vite build.
* Current-code API/browser smoke on FPT returned metadata `status=ok`, `quality_status=partial`, source `SSI Securities`, and coverage for symbol/exchange/market only. The UI hid absent metadata rows, showed the partial caveat, retained SSI DailyOhlc `latest_price=70,800`, and retained DailyStockPrice enrichment.
* The normal `npm.cmd --prefix apps\dsa-web run build` launcher remained blocked by Windows `EPERM` while resolving `C:\Users\dat.tienn`; equivalent local TypeScript, ESLint, and Vite entry points passed.

### Phase 4.4A - Index Data Capability

Status: completed on 2026-06-29.

Goal:

Verify index and component capability from existing SSI contracts.

Scope:

* VNINDEX and VN30 identifiers/rows when returned.
* Index cadence and freshness.
* Index components and membership rows when returned.
* Source/status classification for unavailable or partial coverage.

Rules:

* Do not hardcode component membership as provider output.
* Index failure must remain separate from watchlist daily validity.

Acceptance criteria:

* Index domains have explicit source, cadence, freshness, and status classification.
* Unavailable components remain `[]` with concise unavailable state and diagnostics.

Result:

* Added `/api/v1/stocks/vn/daily-index` for bounded recent `VNINDEX,VN30` context. It returns only latest real SSI rows, explicit source/status/date/date-match, field coverage, missing fields, and sanitized diagnostics.
* IndexList is authoritative for DailyIndex identifiers and general index discovery. Explicit IndexComponents codes are sent directly through the verified `indexCode` shape; unavailable/no-row results remain empty and are not replaced by guessed members.
* IndexList preserves SSI-returned cross-market rows even when a market filter was requested and exposes returned markets under diagnostics.
* IndexComponents remains empty-list-safe. No VN30 constituents are hardcoded and no fallback provider is used.
* The dashboard renders a separate optional market-index section. Real DailyIndex values and real component counts render when present; unavailable index data does not clear watchlist rows, selected ticker, chart, or live sections.
* `latest_price` remains SSI DailyOhlc. DailyStockPrice, intraday, realtime, metadata, and company-page behavior are unchanged.
* Phase 4.4A live smoke returned IndexList `status=ok` with 10 rows across HNX/HOSE. The response included `VN30` but no exact `VNINDEX`; DailyIndex returned no usable VNINDEX/VN30 rows, and VN30 IndexComponents remained unavailable. Phase 4.4B superseded the VN30 availability finding with exact DailyIndex and IndexComponents discovery; no guessed rows or membership were emitted.
* Watchlist smoke returned FPT/HPG/SSI as usable with `latest_price_source=SSI DailyOhlc` and `fallback_used=false`. Browser smoke kept six rows, selected FPT, chart, and realtime controls visible while showing concise DailyIndex/IndexComponents unavailable copy.
* Targeted validation passed: 111 backend tests, 7 legacy-file index compatibility tests, and 151 frontend tests, plus Python compilation, TypeScript, ESLint, and production Vite build. The normal npm launcher remained blocked by Windows profile `EPERM`; equivalent local entry points passed.
* A full `tests/test_mozyfin_vn_adapter.py` run still has 28 unrelated failures in Mozyfin-era expectations and stale stubs (legacy source labels, fallback/cache behavior, and old intraday signatures). All seven index-focused tests in that file pass; migrating the remaining legacy tests is outside Phase 4.4A.

### Phase 4.4B - SSI Index Identifier / Parameter Discovery

Status: completed on 2026-06-29.

Goal:

Resolve the Phase 4.4A DailyIndex and IndexComponents uncertainty with bounded, provider-derived identifier and parameter probes.

Result:

* Added the manual-only `scripts/probe_ssi_index_capability.py`. It runs sequentially, reads only the existing SSI configuration, prints normalized whitelisted summaries, and is not imported by startup, request handlers, or the normal audit.
* The default hard budget is three IndexList requests (no market, `HOSE`, `HNX`), at most 10 IndexList-derived candidates, at most two recent date windows capped at 29 days, at most two component market variants per candidate, and a 1.15-second inter-request delay.
* Live IndexList requests with `HOSE` and `HNX` each returned the same 10 cross-market HNX/HOSE rows. Exact `VN30` was present; exact `VNINDEX` and a verified HOSE broad-index alias were absent. The no-market request remained unavailable, so the daily-index service now resolves through the verified market-qualified `HOSE` request while still requiring an exact returned identifier. No missing identifier was invented.
* Live DailyIndex discovery proved that `indexID=VN30` returns usable rows: 5 rows for 2026-06-23 through 2026-06-29 and 22 rows for 2026-06-01 through 2026-06-29, latest date 2026-06-29. The same windows with `indexCode=VN30` remained unavailable. Production already uses `indexID`; only the prerequisite IndexList call needed the verified market-qualified parameter.
* Live IndexComponents discovery exposed a nested provider envelope: each outer index row contains an `IndexComponent` list whose members use `StockSymbol`. `indexID=VN30` returned only mismatched HNX outer rows, so exact filtering correctly produced zero VN30 members. `indexCode=VN30`, with market omitted or `HOSE`, returned an exact VN30 outer row and 30 nested members.
* The provider now sends the live-verified `indexCode` shape first and flattens nested component rows only when the outer SSI index identifier exactly matches the request. This avoids an unnecessary `indexID` request that could cause the working retry to be rate-limited. It never reuses HNX members for VN30 and never hardcodes constituents.
* IndexList, DailyIndex, and IndexComponents requests from one fetcher are spaced by a narrow 1.15-second provider-safety interval. This prevents the required DailyIndex discovery lookup from immediately rate-limiting DailyIndex. Explicit IndexComponents uses one verified request shape and a process cache rather than parameter variants.
* The live latest VN30 row carried a provider `IndexValue` of zero despite non-zero change/liquidity fields. Because a zero index level is not a usable market level, normalization now exposes it as null and marks `index_value` missing/partial rather than rendering a fake zero.
* SSI error parsing now recognizes direct nested error records and safely classifies observed request-null-style codes as bad request parameters without exposing provider messages or payload bodies.
* Public endpoints and fields are unchanged. DailyIndex and IndexComponents remain optional and empty-list-safe when unavailable. `latest_price` remains SSI DailyOhlc; DailyStockPrice, intraday, realtime, metadata, and trade-tape behavior are unchanged.
* Final live API smoke returned IndexList `ok` with 10 rows, DailyIndex `partial` with one VN30 row and unavailable VNINDEX, and IndexComponents `ok` with 30 exact VN30 members. The VN30 row was dated 2026-06-29 and exposed the non-positive provider level as null/partial. FPT/HPG/SSI watchlist rows remained `ok`, `latest_price_source=SSI DailyOhlc`, and `fallback_used=false`.
* Targeted validation passed 127 tests across the index probe, SSI fetcher, index service, no-Mozyfin, realtime, DailyStockPrice, and profile metadata suites. Requested Python compilation passed. No frontend files or public API fields changed, so frontend tests/build and browser smoke were not required.

### Phase 4.5A - SSI Remaining Capability Completion Before External Providers

Status: completed on 2026-06-29.

Goal:

Audit the remaining SSI FastConnect market-data capability surface before implementing VNStocks, FiinGroup, or any other external provider.

Result:

* Updated `docs/SSI_DATA_CAPABILITY_MATRIX.md` to use the Phase 4.5A status vocabulary: `strong`, `usable`, `partial`, `optional_live_dependent`, `unavailable_parameter_unknown`, `unavailable_permission_or_entitlement`, `external_provider_required`, `not_implemented`, and `deferred`.
* Confirmed current strong SSI-owned domains: DailyOhlc for canonical daily OHLCV/chart/`latest_price`, and DailyStockPrice for reference/limits, matched/put-through, adjusted-close when present, and latest foreign-flow enrichment.
* Confirmed current usable SSI-owned domains: IndexList, exact VN30 IndexComponents, and supported market metadata from Securities/SecuritiesDetails when provider rows contain fields.
* Confirmed current partial SSI-owned domains: DailyIndex because VN30 rows exist but the latest provider level can be invalid/non-positive and `VNINDEX` is still unresolved; IntradayOhlc because freshness/rate-limit/current-row coverage remains variable.
* Confirmed true trade-tape history is `unavailable_parameter_unknown`: `X-TRADE` is latest-trade stream context, not verified historical trade tape, and REST trade-history parameters/permissions are not proven.
* Confirmed realtime snapshot remains `optional_live_dependent`: parser/cache/adapter/lifecycle infrastructure exists, but public realtime rows require explicitly enabled streaming runtime, configured bootstrap symbols, a running manager, and fresh cache rows.
* Confirmed external-provider-required gaps under current repo evidence: fundamentals, financial statements, ratios, corporate actions, dividends, rights, splits, news, macro, and explicit source-labeled VNINDEX fallback if SSI remains unresolved.
* VNStocks and FiinGroup are candidate external providers only. No runtime provider, fallback path, scraping, provider config, credentials, API schema, frontend behavior, or `latest_price` semantics changed in this phase.

Exit criteria:

* Remaining SSI gaps are separated from external-provider gaps in `docs/SSI_DATA_CAPABILITY_MATRIX.md`.
* Existing stale index wording is corrected so VN30 IndexComponents are described as SSI-usable only when exact provider rows are returned.
* Phase 5 implementation remains gated behind separate provider qualification; external providers must not overwrite SSI-owned fields.

### Phase 4.5B - SSI Remaining Partial Data Implementation

Status: completed on 2026-06-29.

Goal:

Make remaining SSI-owned partial data more available where the current repository has enough evidence to do so safely, without implementing VNStocks, FiinGroup, external fallback, fake data, or changed daily-price ownership.

Result:

* Implemented bounded DailyStockPrice historical foreign-flow enrichment by preserving up to 20 recent rows from the same per-symbol recent-window request already used for latest DailyStockPrice enrichment.
* Populated `indicators.foreign_net_5d_latest_available`, `indicators.foreign_net_20d_latest_available`, `indicators.foreign_net_latest_available_date`, and `indicators.foreign_net_history_count` from SSI `foreign_net_volume` rows in shares. Short history remains null/partial; explicit SSI zero values remain zero.
* Added selected-ticker visibility for real 5D/20D foreign net summaries without changing broad layout, realtime polling, DailyOhlc ownership, or unavailable-state semantics.
* Left `final_close_status` conservative. The current SSI DailyOhlc/DailyStockPrice service path does not expose an explicit final/session confirmation field, so daily finality remains `unknown` instead of a heuristic final state.
* Left DailyIndex VN30 level semantics unchanged. The parser already handles known level aliases and normalizes non-positive provider levels to null; no evidence-backed correction was identified.
* Left VNINDEX unresolved. Production still requires an exact SSI IndexList row and does not guess a broad HOSE identifier.
* Confirmed true historical trade tape remains unproven. `X-TRADE` is latest-trade stream context for realtime snapshots, not historical trade-tape rows.

Exit criteria:

* Watchlist rows remain stable and `latest_price_source=SSI DailyOhlc`.
* DailyStockPrice 5D/20D history uses only bounded per-symbol SSI rows and does not add broad full-market scans.
* No external provider runtime, fallback provider, VNStocks, FiinGroup, scraping, fake rows, WebSocket/SSE, FC Trading/order/account APIs, or commit/push is introduced.

### Phase 4.5C - SSI Live Capability Gate and Evidence-Based Fix

Status: completed on 2026-06-29.

Goal:

Run the remaining SSI capability gate against deterministic tests first, then live SSI only where credentials and network are available. Fix only evidence-backed defects and document provider/entitlement gaps without adding external providers, fallback providers, fake rows, streaming UI productization, or daily-price ownership changes.

Result:

* Deterministic backend coverage passed for the SSI fetcher, DailyStockPrice, intraday, profile metadata, index, realtime, and no-Mozyfin suites.
* Live SSI smoke confirmed AccessToken, DailyOhlc, chunked DailyStockPrice, IndexList, DailyIndex, and VN30 IndexComponents remain reachable with sanitized output only.
* DailyStockPrice live history returned 249 rows for FPT in the 2025-06-30 to 2026-06-29 smoke window and the local API smoke populated 20 recent foreign-flow rows for FPT, HPG, and SSI. The selected rows produced non-null latest-available 5D/20D foreign-net summaries without changing `latest_price_source=SSI DailyOhlc`.
* VN30 DailyIndex remained optional and partial. The local API smoke returned a VN30 row dated 2026-06-29, but the public row still lacked a usable `index_value` and `exchange`; exact `VNINDEX` remained `identifier_unavailable`.
* VN30 IndexComponents remained usable. The local API smoke returned 30 component rows through exact `index_code=VN30`, with no hardcoded constituents or fallback provider.
* IntradayOhlc, realtime snapshot, and trade tape remained unavailable in the local API smoke. Daily SSI watchlist rows stayed `ok`, and missing object/list contracts remained `null`/`[]`.
* No evidence-backed parser or service bug was found for DailyIndex level aliases, VNINDEX identifier resolution, true trade-tape history, or final close/session status. Those remain deferred/provider-dependent rather than guessed.
* Fixed a frontend regression-test race in the selected 5-second trade-tape polling case: the test now waits for the initial selected-ticker chart request before recording the baseline used to assert trade-tape polling does not refresh chart, watchlist, or corporate-actions data.

Exit criteria:

* `latest_price` remains SSI DailyOhlc.
* DailyStockPrice 5D/20D foreign-flow summaries remain bounded to per-symbol recent SSI rows.
* DailyIndex remains optional/partial until SSI returns a usable positive level and exact identifier evidence.
* Intraday, realtime, and trade tape unavailable states remain non-fatal and do not erase daily rows.
* No external provider runtime, fallback provider, VNStocks, FiinGroup, scraping, fake rows, WebSocket/SSE, FC Trading/order/account APIs, or commit/push is introduced.

### Phase 4.6B - VN30 Filter Data Completeness and Watchlist UX Hardening

Status: implemented in current working tree; live SSI smoke not run in this phase.

Result:

* Diagnosed the VN30 filter path: the backend IndexComponents path flattens exact nested `IndexComponent[].StockSymbol` rows, but the frontend VN30 preset still used a static local member list. The filter now uses SSI IndexComponents rows when available and keeps the current watchlist visible when VN30 components are unavailable. Phase 4.6F-4 later made explicit component codes independent from IndexList.
* Added additive watchlist completeness counters: `requested_tickers_count`, `returned_rows_count`, and `missing_tickers`, also mirrored under `data_quality` for diagnostics. These fields do not change existing rows or price ownership.
* Added row-level data-quality reason codes for partial/missing values such as `daily_ohlcv_missing`, `daily_stock_price_missing`, `ta_insufficient_history`, `rsi_missing`, `ma_state_insufficient_data`, `foreign_flow_missing`, `provider_empty`, and `provider_error`.
* Hardened preset/custom filter UX so active-filter clicks are no-ops, pending filter requests disable filter buttons, the pending filter shows a loading state, and previous successful rows remain visible.
* Improved the watchlist table with compact reason titles/ARIA labels for missing cells and `Partial`/`Unavailable`/realtime badges, including realtime disabled, not bootstrapped, cache miss, idle, and stale states when available.
* Preserved SSI source ownership: no hardcoded VN30 provider output, no fake values, no external provider runtime, no fallback provider, and `latest_price` remains SSI DailyOhlc.

### Phase 4.6C - Watchlist Filter Picker and VN30 Retry UX

Status: completed on 2026-06-29; live SSI/browser smoke not required for this frontend state-flow phase.

Result:

* Removed the VN30 disabled dead-end. Unknown component state remains actionable, loading temporarily disables the VN30 action, and unavailable/error responses expose a retry affordance while current watchlist rows remain visible.
* VN30 retry reuses an in-flight component request, normalizes and deduplicates only real SSI IndexComponents symbols, and uses a filter-intent sequence so an older component response cannot overwrite a newer preset/custom selection.
* Replaced the comma-separated custom input with a bounded search and multi-select picker. Options are derived from loaded SSI VN30 components, current response rows, and saved custom symbols; selected symbols render as removable chips.
* Exact syntactically valid symbols outside loaded options require an explicit `Validate on apply` selection. The existing complete-watchlist response check keeps the prior snapshot if the backend does not return every requested row.
* Custom apply saves normalized uppercase unique symbols locally only after a successful response, disables picker controls while pending, suppresses duplicate apply clicks, and keeps previous rows visible.
* No public API/schema fields changed. SSI ownership, watchlist counters, row-level reason codes, and `latest_price_source=SSI DailyOhlc` remain unchanged.

### Phase 4.6D - VN30 Loading Split and Performance Diagnostics

Status: completed on 2026-06-29 with deterministic frontend validation and bounded live SSI timing.

Result:

* Classified the reported delay as `watchlist_30_rows_slow`, `backend_batch_slow`, and `combined_loading_state_misleading`. A local bounded smoke measured exact SSI VN30 IndexComponents at 1.66 seconds, the first normal-cache 30-symbol watchlist at 95.99 seconds, and an immediate repeat at 52.21 seconds.
* Confirmed normal VN30 selection does not send `force_refresh=true`. Already-loaded `status=ok` IndexComponents symbols are normalized, deduplicated, and reused in frontend state; unavailable/error state remains explicitly retryable.
* Split the frontend state presentation into `Loading VN30 members...` and `Loading N VN30 rows`. The member spinner stops once components resolve even while the heavier watchlist request remains pending, and previous successful rows remain visible.
* Added soft row-loading stages after 3 seconds (`Still loading`) and 8 seconds (`Taking longer than expected`). Requests are not automatically duplicated or cancelled; after failure, selecting the filter again retries through the existing request-sequence protection.
* Added development-only console timing events for `vn30_components` and `watchlist_fetch`. Events contain only duration, status, filter/cache intent, and safe row/count fields; they are suppressed in tests and production.
* Confirmed the backend builds watchlist symbols sequentially. Each cold symbol path can traverse cached/remote DailyOhlc, symbol metadata, bounded DailyStockPrice history, optional intraday, realtime, trade-tape, and indicator derivation. The endpoint creates a new `VietnamMarketService` per request, whose SSI fetcher cache is instance-local; this explains why an immediate repeat still remained slow even though module-level cache layers reduced elapsed time.
* Deferred backend service/fetcher lifetime or concurrency changes. Sharing the SSI fetcher across requests affects token/cache lifecycle, streaming-manager attachment, thread safety, and provider pacing, so it requires a separately tested Phase 6 performance/caching task rather than broad parallelization here.
* No public API/schema fields, backend behavior, data-source ownership, or price semantics changed. No hardcoded VN30 runtime output, fake rows, external provider, or fallback was added.

### Phase 4.6E - VN30 Progressive Watchlist Hydration

Status: completed on 2026-07-02 with deterministic frontend validation; live timing was not repeated.

Result:

* Confirmed the Phase 4.6D diagnosis: SSI VN30 membership resolution is the shorter stage, while one frontend request previously waited for the backend's sequential work across every requested ticker before committing any VN30 row.
* Chose `frontend_batch_requests` over visible-window fetching. The current table has no virtualization, and six sequential five-ticker HTTP requests for a 30-member index provide a smaller, deterministic change with bounded SSI pressure.
* Once exact SSI IndexComponents symbols resolve, the table immediately switches from previous rows to ordered VN30 shell rows. Tickers and membership provenance are visible, while numeric cells remain `Loading...` or `—`; shells never enter the committed market-data snapshot as real values.
* Each successful batch replaces only its shell rows and updates `Loaded X/N`. Normal selection always uses `force_refresh=false`. Development timing events now include safe batch index/count fields. Explicit toolbar Force Refresh retains its existing force-refresh semantics.
* Failed or incomplete batches preserve completed rows, mark only affected shells unavailable with a concise reason, and expose a retry that requests only failed tickers. Aggregated frontend counters use the full requested membership, currently hydrated row count, and failed ticker list.
* The active VN30 action suppresses duplicate clicks while hydration is pending. Other presets and the clear action remain available; their newer filter intent cancels the VN30 UI run, and late batch responses cannot overwrite it or trigger the next batch.
* A successful SSI-derived component list remains available while its successful response is current. Phase 4.6F-3F later removed hydration from a last-successful list after a newer unavailable/no-row/failure/timeout response; those terminal responses now require an explicit VN30 retry.
* The 3-second and 8-second states now include loaded-row progress. Backend construction, public API/schema fields, provider calls, and caches are unchanged; shared cache/service lifetime remains a future performance task requiring thread-safety, token-lifecycle, and SSI pacing review.
* No hardcoded VN30 provider output, fake data, external provider runtime, fallback provider, SSE/WebSocket behavior, or `latest_price` change was introduced.

### Phase 4.6F - Watchlist Backend Hydration Profiling and Bounded Batch Strategy

Status: completed on 2026-07-02 with bounded live SSI profiling and deterministic backend/frontend tests.

Result:

* Added manual-only `scripts/profile_vn_watchlist_hydration.py`. It accepts fixed 1/5/10 cases or explicit bounded custom tickers, requires an opt-in flag above 10 up to the hard cap of 30, and emits only aggregate stage/cache/status/source timings. Raw payloads, credentials, headers, tokens, account identifiers, and exception messages are excluded.
* Cold live profiles with normal cache semantics and optional intraday enabled measured 3.559s for FPT, 15.984s for five tickers, and 32.145s for ten tickers. Full 30-row profiling was skipped to avoid repeating the already measured 95.99-second provider load and unnecessary SSI pressure.
* The ten-row stage totals were DailyOhlc 10.861s, metadata 7.529s, optional intraday 5.953s, optional trade tape 4.102s, DailyStockPrice plus foreign history 3.385s, TA 0.279s, and serialization 0.0013s. This classifies the backend as sequential provider-I/O bound; TA and serialization are not optimization targets.
* Confirmed no duplicate DailyStockPrice request exists inside one row: the latest enrichment and 5D/20D foreign-flow history already share one bounded provider response. The evidence-backed defect was cache scope: DailyStockPrice used only the request-scoped fetcher cache while DailyOhlc, metadata, and optional sections also used the process-level service cache.
* Added a 300-second process-level cache entry for the combined DailyStockPrice enrichment/history tuple. It uses existing locking/single-flight behavior, includes provider/market/Vietnam date/lookback/limit in its key, and honors explicit force refresh. A five-row immediate repeat improved from 3.564s to 2.293s, with five DailyStockPrice cache hits and unchanged `latest_price_source=SSI DailyOhlc`.
* Replaced the inline frontend batch literal with `VN30_WATCHLIST_BATCH_SIZE_DEFAULT=5`, minimum 3, maximum 10, plus pure resolver/chunk helpers. The default remains five because live results were approximately linear and five rows reached the first useful batch in roughly half the ten-row time. Progress now discloses the resolved size.
* Backend concurrency, shared global fetchers/tokens, and broad optional-section behavior changes remain deferred. They require SSI pacing/rate-limit, thread-safety, token lifecycle, streaming-manager attachment, and product-contract review. No evidence justified a provider call burst.
* No public endpoint/schema shape changed. The additive `cache_status.daily_stock_price_cache` diagnostic follows the existing map contract. No hardcoded VN30 membership, fake data, fallback provider, external runtime, or price-source change was introduced.

### Phase 4.6F-2 - Remove Hardcoded Initial VN Watchlist Auto-Selection

Status: completed on 2026-07-02 with deterministic frontend validation; no backend/API behavior changed.

Result:

* Diagnosed the unwanted fresh-start load as frontend state initialization: `/vietnam` initialized `watchlist` from a hardcoded symbol list, initialized `selectedTicker` to the first symbol, and immediately called the watchlist API. Because the frontend API omits `tickers` for empty arrays, any unguarded empty call could also hit the backend's direct no-`tickers` service default.
* Changed fresh browser sessions with empty localStorage to start with no active tickers, no selected ticker, disabled ordinary watchlist refresh, and explicit empty-start copy: `Choose a preset or enter tickers to start.`
* Preserved saved custom watchlists: if localStorage has a valid saved custom list, it is restored, loaded, shown as the Custom preset, and still saved/cleared through the existing browser-local flow.
* Preserved user-driven preset and custom flows. Clicking a preset uses the existing request path and selects the first valid returned ticker when needed; custom exact symbols still require explicit `Validate on apply`; stale/pending request protection remains in place.
* Kept Phase 4.6F batching unchanged. The default/min/max batch-size helper controls hydration chunking only and does not create, cap, replace, or imply watchlist membership.
* No public API/schema change, provider behavior change, hardcoded VN30 output, fake data, fallback provider, external runtime, or `latest_price` change was introduced.

### Phase 4.6F-3A - Separate VN30 Member Preload State From Active Watchlist Loading UI

Status: completed on 2026-07-02 with deterministic frontend validation; no backend/API behavior changed.

Result:

* Diagnosed the fresh empty-start copy issue as frontend state ownership drift: VN30 member preload used a preset-local loading flag, but the preset status copy still said `current rows stay visible` even when no committed watchlist rows existed.
* Kept fresh `/vietnam` sessions empty when localStorage has no saved custom list. VN30 member preload can mark only the VN30 preset as loading/unavailable; it does not trigger active watchlist hydration progress, previous-row refresh copy, or a hardcoded watchlist request.
* Previous-row copy such as `current rows stay visible` and `Showing previous data` remains reserved for flows where committed rows already exist. User-driven preset/custom/VN30 hydration still uses existing loading and progressive batch behavior after a watchlist load is actually requested.
* VN30 member unavailable state clears loading, leaves preset/custom controls usable, and does not create a full-dashboard failure state or fallback members.
* No public API/schema change, provider behavior change, hardcoded VN30 output, fake data, fallback provider, external runtime, or `latest_price` change was introduced.

### Phase 4.6F-3B - Make VN30 Member Loading Lazy and User-Driven

Status: completed on 2026-07-02 with deterministic frontend validation; no backend/API behavior changed.

Result:

* Diagnosed the fresh empty-start spinner as frontend eager loading: index coverage loaded IndexList, DailyIndex, and VN30 IndexComponents together on mount, so empty sessions could show `Loading VN30 members...` even with no active watchlist.
* Changed index coverage to load only IndexList and DailyIndex on page mount. VN30 IndexComponents now load only after the user selects the VN30 preset or retry action.
* Added a bounded VN30 component request timeout so an unresolved user-driven member request clears the loading state and returns the VN30 action to retryable unavailable status. It does not start watchlist hydration, create default rows, or emit fallback/hardcoded VN30 members.
* Updated index coverage copy to distinguish not-yet-loaded VN30 components from unavailable provider results.
* Preserved Phase 4.6F progressive hydration, resolved batch size behavior, normal `force_refresh=false` VN30 batches, saved custom restore, and empty-start no-watchlist behavior.
* No public API/schema change, provider behavior change, hardcoded VN30 output, fake data, fallback provider, external runtime, or `latest_price` change was introduced.

### Phase 4.6F-3C - Restore Preset Button Clickability After Empty-Start UX

Status: completed on 2026-07-02 with deterministic frontend validation; no backend/API behavior changed.

Result:

* Diagnosed the clickability regression as frontend request-state gating: a pending non-VN30 preset/custom request used a broad guard and disabled state that blocked all other preset/custom actions.
* Changed preset/custom selection so only the exact pending action is disabled for duplicate-click protection. Other presets remain clickable and can supersede the older pending request through the existing request-id stale-response guard.
* Kept fresh `/vietnam` sessions empty when localStorage has no saved custom list. Empty-start sessions still do not call the watchlist endpoint with omitted tickers and still do not preload VN30 IndexComponents.
* Confirmed non-VN30 presets use local scan bucket membership and do not depend on VN30 member loading, failure, or unavailability.
* Preserved lazy VN30 member loading, existing progressive VN30 hydration, resolved batch-size behavior, normal `force_refresh=false` batches, saved custom restore, and Force Refresh disabled/no-op behavior when no active watchlist exists.
* No public API/schema change, provider behavior change, hardcoded VN30 output, fake data, fallback provider, external runtime, or `latest_price` change was introduced.

### Phase 4.6F-3D - Restore Local Preset Clickability and Decouple Index Coverage From VN30 State

Status: completed on 2026-07-02 with deterministic frontend validation; no backend/API behavior changed.

Result:

* Diagnosed the remaining state leak as frontend diagnostic coupling: background IndexList/DailyIndex failures shared the same index coverage error surface as user-driven VN30 component failures, so diagnostics could imply VN30 component unavailability before VN30 was selected.
* Kept every non-VN30 preset as a local scan bucket with its existing static ticker list. Banks, Securities, Real estate, Consumer, Logistics, Tech, Oil & gas, and Electricity load through the normal watchlist path from fresh empty start and do not call SSI IndexComponents.
* Changed index coverage diagnostics so pending/unavailable/rate-limited IndexList or DailyIndex does not label VN30 components as unavailable, does not show `Loading VN30 members...`, and does not disable local presets or custom input.
* Kept VN30 component failure in the VN30 preset retry flow. It can mark VN30 components unavailable after a user-driven VN30 request, but it no longer sets the generic IndexList/DailyIndex coverage error.
* Preserved empty-start no-default-watchlist behavior, lazy VN30 member loading, progressive VN30 hydration, resolved batch-size behavior, saved custom restore, and Force Refresh disabled/no-op behavior when no active watchlist exists.
* No public API/schema change, provider behavior change, hardcoded VN30 output, fake data, fallback provider, external runtime, or `latest_price` change was introduced.

### Phase 4.6F-3E - Make Local Presets Direct Watchlist Actions and Make VN30 Unavailable Settle

Status: completed on 2026-07-02 with deterministic frontend validation; no backend/API behavior changed.

Result:

* Diagnosed the current local preset path as functionally direct but still embedded in the mixed VN30 handler, which made the action boundary difficult to verify against manual click reports. Split non-VN30 presets into an explicit direct watchlist action path.
* Banks, Securities, Real estate, Consumer, Logistics, Tech, Oil & gas, and Electricity now resolve their existing static local scan-bucket lists and call the normal watchlist load path directly. They do not depend on custom picker selected symbols/options, current rows, committed rows, active watchlist state, VN30 members, IndexList, or DailyIndex.
* Added request-id ownership to the VN30 component request state. Fulfilled unavailable/no-row responses, rejected requests, and bounded timeouts clear `Loading VN30 members...` and settle to Retry VN30 / unavailable copy without starting watchlist hydration.
* Confirmed a local preset can be selected after VN30 component unavailability, with no additional IndexComponents call and no hardcoded VN30 fallback members.
* Preserved empty-start no-default-watchlist behavior, lazy VN30 member loading, progressive VN30 hydration, resolved batch-size behavior, custom picker workflow, saved custom restore, and Force Refresh disabled/no-op behavior when no active watchlist exists.
* No public API/schema change, provider behavior change, hardcoded VN30 output, fake data, fallback provider, external runtime, realtime behavior, or `latest_price` change was introduced.

### Phase 4.6F-3F - Make VN30 Member Resolution a Terminal State Machine

Status: completed on 2026-07-02 with deterministic frontend validation; no backend/API behavior changed.

Result:

* Found the live-only gap that direct page tests had missed: React StrictMode replayed the mount effect cleanup, which set the shared unmounted guard to `true`, while the following setup did not reset it. The completed VN30 response was therefore ignored and the member state stayed loading. The effect setup now explicitly restores the mounted guard.
* Replaced the implicit VN30 member `loading` boolean plus response-derived availability with explicit `not_loaded`, `loading`, `ready`, `unavailable`, `failed`, and `timeout` states.
* Only the latest user-driven VN30 request owns its state transition. Usable normalized SSI component rows enter `ready`; HTTP-successful unavailable/no-row/failure-diagnostic responses, network rejection, and bounded timeout enter terminal retry states.
* Terminal non-ready member responses clear `Loading VN30 members...`, show Retry VN30/unavailable, and start no watchlist hydration. Rendering the retry state does not issue another request; only an explicit retry action does.
* Removed the last-successful-member hydration path after a newer unavailable/no-row response so completed unavailability cannot create shell rows or an active VN30 watchlist.
* Added React StrictMode regression coverage plus fulfilled unavailable/no-row/failure-diagnostic, rejection, timeout, explicit retry, no-loop, local-preset-after-failure, fresh-start, and success-path coverage.
* Preserved fresh empty start, lazy member loading, direct local preset actions, custom controls, successful SSI VN30 progressive hydration, bounded batch sizing, and stale-intent protection.
* No public API/schema change, provider behavior change, hardcoded VN30 output, fake data, fallback provider, external runtime, realtime behavior, or `latest_price` change was introduced.

### Phase 4.6F-4 - Fix VN IndexComponents API Resolution and Negative Cache Behavior

Status: completed on 2026-07-02 with deterministic backend/fetcher validation and bounded local API smoke.

Result:

* Diagnosed `/index-components?index_code=VN30` as service-gated by IndexList even though the endpoint already required an explicit code. An unavailable IndexList therefore returned `index_list_unavailable` without attempting SSI IndexComponents.
* Explicit normalized component codes now call SSI IndexComponents directly with the live-verified `indexCode`, `pageIndex=1`, `pageSize=1000`, and optional normalized market. IndexList is recorded as `not_required` and remains separate discovery/DailyIndex context.
* Removed speculative IndexComponents parameter variants. Empty, mismatched, provider-error, and rate-limited responses use one provider request per uncached service resolution and remain clean unavailable with `rows=[]`.
* Added a process-level cache across request-scoped services keyed by SSI provider, IndexComponents endpoint, normalized index code, and optional market. Usable rows cache for 300 seconds; unavailable/rate-limited/no-row results cache for 60 seconds. `force_refresh=true` intentionally bypasses it.
* Added sanitized cache diagnostics (`cache_status`, TTL, negative flag, safe key, expiry), direct-resolution diagnostics, and deterministic tests for IndexList-independent success, no-row/unavailable/rate-limit behavior, cache hits, normalized keys, force-refresh bypass, exact nested rows, and no parameter probes.
* No hardcoded VN30 output, fake rows, fallback provider, external runtime, frontend behavior change, realtime behavior change, or `latest_price` change was introduced.

### Phase 4.7A-docs - Stock Detail Metrics Availability Audit

Status: completed on 2026-07-02 as a documentation-only audit.

Result:

* Inspected the current backend schemas, SSI fetcher mappings, Vietnam market service normalization, frontend API types, dashboard rendering, and existing docs for stock-detail labels such as open, average, matched/put-through value, foreign buy/sell/room, 52-week high/low, average volume, EPS, valuation ratios, beta, share count, market cap, dividends, ROE, and ROA.
* Documented the exact current availability matrix in `docs/VN_DATA_CONTRACT.md` and `docs/DATA_DICTIONARY.md`.
* Confirmed available-now fields remain source-owned: SSI DailyOhlc for daily open/high/low/close/volume/value and SSI DailyStockPrice for reference/limits, matched value/volume, put-through value/volume, and latest foreign buy/sell/net volume/value.
* Recorded non-implemented but computable future metrics at the time of the audit: 52-week high/low and 10D/3M average volume. Phase 5.0D-2 later identified price-vs-reference % and daily range % as SSI-derivable metrics as well. Phase 4.8A has since implemented this safe SSI-derived subset with explicit null/coverage statuses.
* Recorded ambiguous fields needing provider-semantics confirmation before display: average price, foreign room, and exact outstanding quantity. Current `listed_shares` is metadata, not an approved market-cap/outstanding-share basis.
* Recorded future-provider-required fields: EPS TTM, P/E TTM, P/B, dividend ratio/date, ROE, and ROA. Corporate-action contract fields remain disabled/not configured by default and must not be inferred from price gaps.
* Deferred beta pending SSI index data and methodology; deferred market cap pending share-basis verification.
* No runtime code, schema, frontend UI, parser mappings, tests, provider behavior, fallback behavior, or `latest_price` ownership changed.

### Phase 4.8A - SSI-Derived Metrics Completion

Status: completed on 2026-07-06.

Goal:

Complete safe metrics that should be calculated internally from SSI-owned inputs before assigning any domain to an external provider.

Scope:

* 52W high/low from SSI DailyOhlc high/low history.
* 10D average volume from SSI DailyOhlc volume history.
* 3M average volume from SSI DailyOhlc volume history.
* Price vs reference % from SSI DailyOhlc close plus SSI DailyStockPrice reference price.
* Daily range % from SSI DailyOhlc high/low/close.
* Optional beta only after SSI index data and beta methodology are verified.

Rules:

* No external provider.
* No `latest_price` change.
* No fake rows.
* No provider fallback.
* No corporate-action inference.
* Metrics must return null/unavailable when SSI history or required SSI fields are insufficient.

Acceptance criteria:

* Metrics are source-labeled as SSI-derived/internal.
* Inputs and required history windows are documented.
* Insufficient history returns null/unavailable, not guessed values.
* DailyOhlc remains canonical.
* External providers are not used for any metric that SSI can provide or that can be calculated from SSI-owned data.

Result:

* Added SSI-derived metrics to watchlist `indicators` and company `technical`: `high_52w`, `low_52w`, `avg_volume_10d`, `avg_volume_3m`, `price_vs_reference_pct`, and `daily_range_pct`.
* Added coverage/status fields for 52W high/low, 10D/3M average volume, price-vs-reference, daily range, and aggregate SSI-derived metric status/source.
* Implemented formulas from SSI DailyOhlc and SSI DailyStockPrice only. `latest_price` remains SSI DailyOhlc, DailyStockPrice remains enrichment/reference owner, and no external provider/fallback path was added.
* Added compact dashboard/company rendering for the new metrics with source-aware unavailable copy.
* Phase 4.8A-Fix corrected frontend API adapter mapping for numeric-suffix fields (`52w`, `10d`, `3m`) so values render with their dates/statuses, and tightened backend valid-row rules for 52W, volume, reference, and daily-range formulas.
* Left beta deferred pending SSI index data and methodology verification.

### Phase 4.9A - Short-Term Daily Support and Resistance Zones

Status: completed on 2026-07-10.

The `/vietnam` indicator table now shows compact Support and Resistance columns from `indicators.short_term_zones`. The service derives up to two nearest zones on each side from exactly the latest 60 valid unique SSI DailyOhlc D1 sessions, using ATR14 Wilder/RMA and five-session swing pivots. Zones are source-labeled `derived from SSI DailyOhlc`, never cross the latest daily close, and remain unavailable rather than guessed when history or ATR is insufficient. This calculation adds no provider call, polling, realtime dependency, fallback, or change to `latest_price` ownership.

### Phase 4.9B - Short-Term Support/Resistance Chart Overlay

Status: completed on 2026-07-13.

The selected ticker's existing daily inspect chart now has an optional `S/R zones` overlay that reuses Phase 4.9A `indicators.short_term_zones` only. It draws at most S1/S2/R1/R2 as subtle support/resistance bands behind candles and technical lines, clips them to the price plot, and keeps the existing visible-candle y-domain unchanged. Compact and expanded chart views share the control and rendering path; unavailable or malformed ranges produce no band. The frontend does not calculate zones, make a request, alter polling, use realtime/intraday/order-book/trade inputs, or change `latest_price`.

### Phase 4.9B-1 - Support/Resistance Overlay Readability

Status: completed on 2026-07-13.

The single `S/R` chart control now defaults off. When enabled, the same Phase 4.9A ranges use a two-level hierarchy: S1/R1 are primary solid midpoint lines with compact right-edge range labels, while S2/R2 are faint dashed lines with rank-only markers and title-only ranges. Faint bands remain clipped behind candles, label offsets are deterministic, and the candle y-domain, selected-ticker ownership guard, requests, polling, providers, and `latest_price` remain unchanged.

### Phase 4.10L - TradingView Lightweight Charts 5.2 Cutover

Status: production cutover complete on 2026-07-14; manual browser parity/network inspection remains pending.

The VN daily inspect chart now uses the separate, no-fetch `VietnamLightweightChart` built against the official open-source `lightweight-charts@5.2.0` npm package as its sole renderer. It maps valid SSI DailyOhlc trading-date strings directly to `BusinessDay` values, keeps raw-VND chart values and existing board-style display formatting, and provides native candlesticks, price/time scales, zoom/pan, crosshair tooltip, volume and RSI panes, MA20/MA50, and Bollinger lines. Phase 4.9A S1/S2/R1/R2 ranges remain backend-owned and default-off; a passive series primitive draws their exact bands/midpoints and exposes rank-prefixed values through native right-price-axis views without autoscale expansion.

Lightweight Charts is only a rendering engine. It does not provide StockClock market data, and the chart includes visible TradingView attribution without implying data supply or endorsement. Chart interaction creates no provider request; no Advanced Charts package, embed widget, external market-data provider, backend contract change, fake bar, or `latest_price` change is part of this phase.

The temporary development-only engine flag and custom SVG renderer were removed during cutover. Card-level range selection continues to request the existing daily chart contract, while native scale interaction, crosshair use, indicator toggles, S/R toggling, and compact/expanded transitions do not request market data. On 2026-07-14, 17 focused chart tests, 192 dashboard tests, TypeScript, ESLint, and the production build passed for the sole-engine implementation. The distinct broader frontend suite reported 822 passes, 2 skips, and 4 unrelated current failures in UI governance, stock-name truncation, and two async dialog tests; those areas were not changed for this chart cutover.

The production cutover was user-directed despite the browser-tooling blocker. Manual browser parity and request-network inspection remain a follow-up because the available in-app browser integration could not initialize before navigation, including after a clean reconnect. This is a validation-environment limitation rather than evidence of runtime failure. When browser tooling is available, verify DailyOhlc OHLC/date/price parity, native interaction, compact/expanded ownership, S/R price-axis readability, responsive layout, attribution visibility, and absence of unexpected external market-data traffic.

### Phase 4.11A - Lightweight Charts Runtime Hardening

Status: deterministic hardening complete on 2026-07-14; automated browser and interaction-network proof remain blocked before navigation.

The chart now creates once per mounted component and uses refs for every chart API object. Cleanup marks callbacks disposed before unsubscribing crosshair and logical-range handlers, detaches and clears the S/R primitive, drops refs, and removes the chart. Changing indicator visibility, S/R, data, pane proportions, or the `expanded` prop does not reconstruct the mounted chart. The dashboard architecture still mounts only one compact or expanded chart at a time and transfers already-loaded props without a market-data request.

Lightweight Charts `autoSize` is the only resize owner; there is no custom `ResizeObserver`, timer, animation frame, or device-pixel-ratio path. Compact height is clamped to 420–540 px and uses 68% price / 14% volume / 18% RSI stretch factors. Expanded height is clamped to 480–760 px and uses 70% / 12% / 18%. Volume and RSI remain always visible, so repeated pane visibility toggling is not a supported state. The native right scale keeps a constant 148 px minimum for board-formatted price and full S/R range labels, avoiding plot-width changes when S/R is toggled.

Crosshair tooltip content remains component-local, pointer-transparent, bounded to the chart container, and visually suppressed for loading, unavailable, missing-series, or mismatched-ticker states. Repeated movement over the same bar updates its position through the tooltip element ref rather than rerendering the dashboard. Ticker and range-preset changes clear the old chart, diagnostics ownership, and saved logical range before loading; late responses remain request-ID guarded. Compact/expanded transitions alone retain the latest logical range, while a new ticker deliberately fits its own data.

Validation covers 60, 250, and 500 mapped daily sessions; 24 focused chart tests and 193 Vietnam dashboard tests pass, as do TypeScript, ESLint, and the production build. The broader suite reported 829 passes, 2 skips, the same four unrelated Phase 4.10L baseline failures, and one HomePage async failure that passed all 16 tests in isolation. The local backend and frontend were already listening on 127.0.0.1:8000 and :5173, but browser setup again failed with `Cannot redefine property: process`; therefore visual resize/interaction proof and browser network capture remain pending and are not claimed as passed.

### Phase 4.11B - SSI Intraday Chart Contract Audit

Status: Phase 4.11B-3 bounded live verification completed on 2026-07-14; Phase 4.11C has since implemented only one-completed-date `1m` history through the production endpoint/UI.

The repository has a real SSI `IntradayOhlc` adapter used by the optional watchlist/company pulse, but it is not a full chart-history contract. Current behavior requests seven calendar days, pages internally at 1,000 rows (generic maximum 20 pages), returns the latest eight rows by default, caches for 60 seconds, rejects stale daily-date mismatches, and applies a 60-second ticker/timeframe rate-limit cooldown. Deterministic fixtures prove sorting, mapping, cadence detection, pagination, malformed-row rejection, and unavailable-state behavior; they do not prove SSI interval support.

The installed `ssi_fc_data` 2.2.2 SDK exposes `IntradayOhlc` and integer `resolution=1` but no interval enum, units, timestamp zone, or final-bar flag. Phase 4.11B-3 used four IntradayOhlc and four matching DailyOhlc calls for completed HOSE sessions: FPT and HPG on 2026-06-23 and 2026-06-24. Every response had 226 rows/records with identical fields. Flooring raw Vietnam wall times produced 226 unique ascending minute buckets; each session had continuous buckets 09:15-11:29 and 13:00-14:29 with every within-segment transition exactly 60 seconds, plus a final 14:45 row. No unexplained gap, duplicate, invalid timestamp, or ordering error was observed.

All 904 OHLC rows were valid. First open, maximum high, minimum low, final close, and summed volume exactly reconciled with same-date DailyOhlc in all four samples; each volume ratio was 1.0. Raw times are classified `likely_last_trade_time_but_not_fully_verified`, and volume is `likely_per_bar_shares` while public copy remains neutral `Volume`. Canonical chart time floors the raw `Asia/Ho_Chi_Minh` wall time to minute start before Unix-second conversion; no filler bar or forward-fill is allowed. The first 09:15 bar and final 14:45 bar reconcile with daily open/close, but exact ATO/ATC aggregation remains ambiguous.

Values 5, 15, 30, and 60 were accepted by the endpoint but did not select corresponding output cadence in tested SSI behavior. They remain unsupported mappings to 5m/15m/30m/1h and must not be exposed or synthesized by backend aggregation.

Phase 4.11C implements only `GET /api/v1/stocks/vn/intraday-chart?ticker=FPT&interval=1m&date=2026-06-24`. The date must be strictly before the current Vietnam date, the provider query is one translated `DD/MM/YYYY` day with `pageSize=1000`, and output is capped at 1,000 bars. Pagination itself remains unverified because every tested `totalRecord` was 226. Cache identity is `intraday_chart:{ticker}:1m:{vn_trading_date}:page:1`, with 86,400-second positive TTL, 60-second negative TTL, bounded stale-if-error, and 500 LRU entries. Current-session support, multi-day ranges, pagination, higher intervals, realtime updates, aggregation, and fallback remain deferred. Phase 4.11D separately owns realtime/current-session finality. X, X-QUOTE, X-TRADE, DailyStockPrice, and Phase 4.8S snapshots remain forbidden candle sources.

### Phase 4.11D-1 - Current-Session SSI and X-TRADE Audit

Status: documentation/evidence audit complete on 2026-07-16; no production current-session behavior implemented.

Eight bounded current-date FPT IntradayOhlc requests covered 09:12-09:20 Vietnam time. SSI returned `NoDataFound` through 09:15:05, then exposed a 09:15:59 opening row and a changing current-minute row at 09:16:05. Repeated requests proved raw time/OHLC/volume revision inside the minute; after a newer minute appeared, the previous row remained stable in later samples. The final request returned six valid unique normalized buckets with zero rejected/duplicate rows. Provider-response latency was 0.423-1.116 seconds (median 0.615, eight calls). Provider finality remains absent, so finality is `inferred_finality_with_reconciliation`.

Phase 4.11D-2 gate: `open_as_delayed_only`. Future work may add bounded minute-boundary SSI polling about 5-10 seconds after each continuous-trading boundary, pause during lunch/pre-open, retain usable cache on failure, reconcile authoritatively after close, and label the experience `Updating`/`Delayed`, never `Live` from this evidence.

### Phase 4.11E - Current-Session Production Hardening and Observability

Status: implementation, deterministic validation, and bounded backend runtime health/cache/coalescing proof complete on 2026-07-16; SSI data remained unavailable as a sanitized local `network_error`, and browser evidence remains blocked.

The phase adds bounded concurrency-safe worker-local metrics, sanitized `vn_intraday_provider_fetch` events, a read-only no-store health route, exact-key process-local coalescing, separate provider-snapshot/newest-bar ages, and current-session cache/date-rollover guards. The dashboard centralizes active refresh triggers behind one owned request path, retains one market-data timeout plus one request-free countdown timeout, prevents scheduled/manual/visibility overlap, preserves bars during refresh, wakes once after lunch, reconciles once after close, and rolls semantic Today in Vietnam time. Metrics reset on restart and are per worker; there is no distributed lock or deployment-global health aggregation.

The contract stays SSI-only: DailyOhlc owns D1/latest price; IntradayOhlc owns 1m; X-TRADE candle aggregation and Phase 4.11D-3 remain blocked; TradingView is rendering-only; no external provider, WebSocket, realtime overlay, higher timeframe, filler, or forward fill was added.

Runtime proof started with HTTP 200/no-store `unknown` health and zero provider calls. A completed-date miss/repeat/force sequence ended with four endpoint requests, three actual provider calls, one cache hit, two misses, one refresh, zero in-flight work, and `degraded` health because SSI was locally unavailable as `network_error`; no current or completed bars were observed. Five concurrent same-key forced requests then yielded one actual provider call, four coalesced waiters, maximum same-key waiter count four, and clean in-flight removal. Automated browser navigation terminated twice before the page could be inspected, so no D1, completed 1m, Today, transition, visual, or network proof is claimed.

Phase 4.11E-R verified that `/intraday-chart/health` and the broader `/observability` endpoint are intentionally distinct typed routes. It also verified the existing implementation already calculates newest-bar age from the accepted raw SSI timestamp, including the latest-raw-time duplicate winner, while keeping the candle bucket at minute start and snapshot age at successful fetch time. Production code, cache policy, and provider behavior therefore required no repair; focused route and frozen-time tests were strengthened.

One bounded `X-TRADE:FPT` observation captured 206 events across two 30-second windows and one controlled reconnect. All observed events had trade price, `LastVol`, cumulative `TotalVol`, side, date/time, and session/status, but no ID or sequence; 109 visible tuples collided. The current manager stores receive order and performs no event deduplication, so replay/loss/correction detection and authoritative close/volume aggregation are unsafe. Phase 4.11D-3 gate: `blocked`. A future reconnect must suspend provisional trust and refresh/reconcile from SSI IntradayOhlc before resuming. No X/X-QUOTE/F/R/MI/persisted-snapshot candle path is allowed.

### Phase 4.8F - SSI Remaining Data Capability Audit

Status: completed on 2026-07-08 as a documentation-only audit.

Goal:

Document SSI FastConnect capabilities that StockClock already uses, capabilities that SSI can still likely power but StockClock does not fully expose yet, and the boundary between SSI-owned data and external-provider-required gaps.

Result:

* Added `docs/SSI_REMAINING_DATA_AUDIT.md` with a capability matrix covering DailyOhlc, DailyStockPrice, IntradayOhlc, Securities/SecuritiesDetails, IndexList, IndexComponents, DailyIndex, realtime `X`, trade tape `X-TRADE`, `X-QUOTE`, `F`, `R`, `MI`, `B`, and instrument metadata candidates.
* Classified the strongest missing SSI-backed runtime-proof targets as trading session/status from `F`, order book from `X-QUOTE`, realtime foreign room from `R`, realtime market index pulse from `MI`, DailyStockPrice unused fields, and SecuritiesDetails extended metadata.
* Kept realtime OHLCV `B`, derivatives/futures, covered warrants, ETF/fund, and bond metadata as later instrument/streaming tracks.
* Reconfirmed `latest_price` remains SSI DailyOhlc and external providers must not overwrite SSI-owned prices, OHLCV, DailyStockPrice enrichment, intraday, realtime, trade tape, order book, foreign room, index data, or metadata.
* No runtime provider, backend endpoint, frontend UI, schema, tests, config/env, credentials, streaming subscription code, fallback provider, scraping, fake data, commit, or push was added.

Recommended next SSI-backed runtime-proof order:

1. Phase 4.8G - Trading Session/Status from SSI `F:{symbol}` runtime proof. Implemented as optional cache-backed watchlist context; code mapping and UI productization remain deferred.
2. Phase 4.8H - `X-QUOTE` Order Book Ladder. Implemented as optional cache-backed watchlist/company context with selected-ticker UI; further market-specific depth semantics remain deferred.
3. Phase 4.8I - Realtime Foreign Room from SSI `R`. Implemented as optional cache-backed watchlist context; live payload proof and UI productization remain deferred.
4. Phase 4.8I-Live - live smoke for SSI `R:{symbol}` during market hours.
5. Phase 4.8I-UI - foreign-room UI only after live proof.
6. Phase 4.8J - Realtime Market Index Pulse from SSI `MI`. Implemented as optional cache-backed index API context; live payload proof and UI productization remain deferred.
7. Phase 4.8J-Live - live smoke for SSI `MI:{index_code}` during market hours.
8. Phase 4.8J-UI - market pulse UI only after live proof.
9. Phase 4.8K - DailyStockPrice Unused Field Audit/Exposure.
10. Phase 4.8L - SecuritiesDetails Extended Metadata.
11. Later - Realtime OHLCV `B`, derivatives/futures, covered warrant, ETF/fund, and bond modules.

### Phase 4.8G - SSI F Trading Session/Status Runtime Proof

Status: backend/API runtime-proof path implemented on 2026-07-08; selected-ticker frontend UI implemented on 2026-07-09.

Result:

* Startup-owned SSI streaming now includes symbol-scoped `F:{symbol}` subscriptions alongside `X:{symbol}` and `X-TRADE:{symbol}` for configured bootstrap symbols.
* Parsed `F` rows are stored in a dedicated session/status cache, not in the realtime quote cache or trade-tape buffer.
* Watchlist rows can expose `session_status_source`, `session_status`, and `session_status_status`; technical state lives under `diagnostics.session_status`.
* Safe fields only are surfaced: ticker/symbol, exchange, trading date, time, raw `trading_session`, raw `trading_status`, stream timestamp/type, cache age, and source.
* No status-code business meanings are mapped yet. Open/closed/halted/final labels, polished frontend rendering, and `final_close_status` support remain deferred until live evidence proves exact SSI meanings.

Boundaries:

* Request handlers remain cache readers only and must not start streams, subscribe dynamically, use all-market channels, or call trading/order/account APIs.
* `F` session/status context must not replace SSI DailyOhlc, DailyStockPrice, realtime snapshot, trade tape, or `latest_price`.

### Phase 4.8S - Persist Last-Known SSI Streaming Snapshots

Status: completed on 2026-07-13.

Add disabled-by-default, bounded operational JSON persistence for user-safe normalized SSI streaming caches. The lifecycle restores once before existing manager startup; each restored X/X-QUOTE/X-TRADE/R/MI/F context is explicitly stale and is superseded only by a live row from that same context. Snapshots are atomic, debounced, bounded, gitignored, and non-fatal when missing/corrupt/expired. They are not historical storage, do not add subscriptions or request-time work, and do not affect SSI DailyOhlc `latest_price`.

### Phase 4.8H - SSI X-QUOTE Order Book Ladder

Status: implemented on 2026-07-08 as a backend/API runtime-proof path.

Result:

* Startup-owned SSI streaming now includes symbol-scoped `X-QUOTE:{symbol}` subscriptions alongside `X:{symbol}`, `X-TRADE:{symbol}`, and `F:{symbol}` for configured bootstrap symbols.
* Parsed `X-QUOTE` rows are stored in a dedicated latest order-book cache, not in the realtime quote cache, trade-tape buffer, or session/status cache.
* Watchlist rows can expose `order_book_source`, `order_book`, and `order_book_status`; technical state lives under `diagnostics.order_book`.
* Safe fields only are surfaced: ticker/symbol, exchange, bid/ask levels, trading date, time, stream timestamp/type, cache age, and source. Bid/ask levels require positive price and nonnegative volume; malformed levels are dropped rather than filled.
* Dashboard and company selected-ticker panels now render `Order Book — SSI X-QUOTE` when cached rows exist, using dynamic level counts, bid/ask matching by level, full-share volumes, board-style price formatting, SSI board colors when reference/ceiling/floor are available, and explicit stale/unavailable states.
* Stale but usable `X-QUOTE` cache rows remain visible as last-known ladders with `order_book_status.status=stale`, stale copy, cache age metadata, and no effect on DailyOhlc `latest_price`. Empty/no-usable-level cache still returns `order_book=null`.
* The dashboard selected ticker and company detail live context refresh through existing watchlist/company responses on a short visible-tab interval so short-TTL X-QUOTE updates can surface without dynamic stream subscription or a new endpoint.
* Live proof on 2026-07-09 09:35-09:41 +07 verified usable FPT/HPG/SSI/ACB X-QUOTE rows. The UI does not claim every market/exchange always provides exactly three levels; further market-specific depth and unit semantics remain deferred until more live payload evidence proves exact meanings.

Boundaries:

* Request handlers remain cache readers only and must not start streams, subscribe dynamically, use all-market channels, or call trading/order/account APIs.
* `X-QUOTE` order-book context must not replace SSI DailyOhlc, DailyStockPrice, realtime snapshot, trade tape, session/status, intraday, indicators, or `latest_price`.
* `latest_price_source` remains `SSI DailyOhlc`.
* Phase 4.8H-UI does not add F session/status UI, R foreign-room UI, or MI market-index pulse UI.

### Phase 4.8I - SSI R Foreign Room Backend/API Support

Status: implemented on 2026-07-08 as a backend/API runtime-proof path.

Result:

* Startup-owned SSI streaming now includes symbol-scoped `R:{symbol}` subscriptions alongside `X:{symbol}`, `X-QUOTE:{symbol}`, `X-TRADE:{symbol}`, and `F:{symbol}` for configured bootstrap symbols.
* Parsed `R` rows are stored in a dedicated latest foreign-room cache, not in the realtime quote cache, trade-tape buffer, order-book cache, or session/status cache.
* Watchlist rows can expose `foreign_room_source`, `foreign_room`, and `foreign_room_status`; technical state lives under `diagnostics.foreign_room`.
* Safe fields only are surfaced: ticker/symbol, exchange, total/current room, foreign buy/sell volume/value when explicitly provided, trading date, time, stream timestamp/type, cache age, source, and `value_semantics_status`.
* No frontend foreign-room UI is productized yet. Value-unit semantics, approximate-value behavior, exchange-specific caveats, and final display copy remain deferred until live payload evidence proves exact meanings.

Boundaries:

* Request handlers remain cache readers only and must not start streams, subscribe dynamically, use all-market channels, or call trading/order/account APIs.
* `R` foreign-room context must not replace SSI DailyOhlc, DailyStockPrice daily foreign flow, realtime snapshot, trade tape, order book, session/status, intraday, indicators, or `latest_price`.
* `latest_price_source` remains `SSI DailyOhlc`.

### Phase 4.8J - SSI MI Realtime Market Index Pulse Backend/API Support

Status: implemented on 2026-07-09 as a backend/API runtime-proof path; live proof and UI remain deferred.

Result:

* Startup-owned SSI streaming now includes bounded `MI:{index_code}` subscriptions for `VNINDEX`, `VN30`, `HNX`, and `UPCOM` alongside the existing stock-scoped `X:{symbol}`, `X-QUOTE:{symbol}`, `R:{symbol}`, `X-TRADE:{symbol}`, and `F:{symbol}` channels when the streaming lifecycle is enabled and stock bootstrap symbols are configured.
* Parsed `MI` rows are stored in a dedicated latest market-index cache, not in the realtime quote cache, trade-tape buffer, order-book cache, foreign-room cache, session/status cache, REST DailyIndex rows, or stock watchlist rows.
* The separate market-index pulse API can expose `market_index_pulse_source`, `market_index_pulse`, and `market_index_pulse_status`; technical state lives under `diagnostics.market_index_pulse`.
* Safe fields only are surfaced: index code, exchange, index value, estimated index value, change/change %, total trades, total volume/value, advances/unchanged/declines, trading date/time, stream timestamp/type, cache age, source, and live-proof caveats.
* Malformed numeric fields are null/dropped; rows with no usable MI metric are unavailable. No fake index values are synthesized.
* No frontend market-pulse UI is productized yet. Channel format, value units, breadth semantics, and timestamp/freshness behavior remain deferred until live payload evidence proves exact meanings.

Boundaries:

* Request handlers remain cache readers only and must not start streams, subscribe dynamically, use all-market channels, or call trading/order/account APIs.
* `MI` market-index pulse must not replace SSI DailyOhlc, DailyStockPrice, REST DailyIndex, realtime snapshot, trade tape, order book, foreign room, session/status, intraday, indicators, or `latest_price`.
* `latest_price_source` remains `SSI DailyOhlc`.

### Phase 5.0A - External Provider Contract Design

Status: completed on 2026-06-29.

Goal:

Select the next missing VN data domain and provider strategy after the SSI-first capability audit, without mixing external ownership into SSI market data.

Result:

* Added `docs/VN_EXTERNAL_PROVIDER_STRATEGY.md` with a scored domain matrix, candidate provider/source matrix, verified official sources, unresolved facts, legal gates, implementation order, and next-phase entry criteria.
* Selected corporate actions/dividends/rights/splits as the first external domain because they affect price interpretation and event correctness.
* Selected FiinGroup API Datafeed as the preferred automated candidate only after written commercial entitlement and storage/display/redistribution approval. Public documentation verifies structured event, issuance, company, news, financial, ratio, macro, and HOSE index schemas; authentication, production URL, pricing, rate limits, SLA, historical depth, and rights remain `needs_verification`.
* Selected provenance-required manual import as the fallback corporate-actions strategy. VSDC public notices verify rich event content, but public pages are not an automation license and must not be scraped.
* Verified HNX official RSS and commercial information packages as later candidates. Cross-exchange coverage and retention/display/redistribution rights remain unresolved.
* Deferred financial statements, ratios, metadata fallback, news, macro, and explicit external VNINDEX in that order. Existing user-owned portfolio accounts/manual entries/CSV import are a separate implemented subsystem; broker integration is not a missing market-data provider.
* No provider interface, credentials, config, endpoint, schema, backend behavior, or frontend behavior changed. Future blocks remain `disabled`, `not_implemented`, or `unavailable` with null/empty contracts.
* SSI ownership is unchanged: `latest_price` remains SSI DailyOhlc, and external providers may not overwrite SSI-owned fields or break daily rows.

### Phase 5.0B - CorporateActionsProvider Qualification and Contract Proof

Status: contract proof completed on 2026-06-29; provider access/legal qualification remains unresolved.

Goal:

Resolve the access/legal gate and prove one bounded corporate-action contract before production integration.

Scope:

* Obtain FiinGroup entitlement, auth, endpoint, rate-limit, correction, provenance, storage, display, and redistribution answers.
* Define a thin `CorporateActionsProvider` response with separate announcement, ex, record, and payment/execution dates.
* Use one sanitized licensed fixture, or a provenance-required manual fixture if commercial access is not approved.
* Cover cash dividends, stock dividends/bonus, rights, splits, corrections/cancellations, and missing optional dates.

Rules:

* No live adapter until written access and legal gates pass.
* No scraping VSDC, HOSE, HNX, SSC, company pages, or undocumented endpoints.
* No raw provider payload, credential, token, or commercial account data in fixtures.
* Provider failures return `events=[]` and do not affect SSI daily data.

Acceptance criteria:

* Provider/source decision is written and evidence-backed.
* Contract tests prove null/empty, provenance, correction, duplicate, and SSI-isolation behavior.
* Adapter remains disabled by default until a live proof is explicitly approved.

Result:

* Added a `CorporateActionsProvider` boundary with disabled and not-configured implementations that perform no external I/O.
* Added disabled-by-default `VN_CORPORATE_ACTIONS_PROVIDER_*` config placeholders for future provider wiring.
* Expanded the public corporate-actions response with normalized `events`, backward-compatible `items`, provider/source labels, and sanitized diagnostics.
* Preserved `events=[]`/`items=[]` for disabled, not-configured, unavailable, and error states.
* Proved provider failure remains optional and does not affect SSI DailyOhlc/DailyStockPrice rows or `latest_price`.
* Updated dashboard rendering so the corporate-actions card shows an unavailable/disabled future-module state rather than implying verified absence of events.
* Did not implement VNStocks, FiinGroup, scraping, external fallback runtime, fake events, FC Trading, WebSocket/SSE product behavior, or any change to `latest_price`.

### Phase 5.0C - Corporate Actions Contract Hardening and Offline Test Hygiene

Status: completed on 2026-06-29.

Result:

* Hardened the corporate-actions alias contract so `events` is canonical and legacy `items` is derived from it across service, API schema, and dashboard rendering.
* Added deterministic coverage for divergent provider/schema input so `items` cannot drift from `events`.
* Tightened the future provider qualification checklist for entitlement, terms, pricing, SLA, rate limits, symbol mapping, event/date semantics, source documents, raw payload storage, and privacy/security constraints.
* Documented unrelated LiteLLM remote pricing refresh as offline TestClient import noise when the full FastAPI app is imported for a stock-only smoke; deterministic tests should use the existing LiteLLM stub instead of changing production startup semantics.
* Did not implement VNStocks, FiinGroup, external provider runtime, fallback providers, scraping, fake events, or changes to SSI `latest_price` ownership.

### Phase 5.0D - External Provider Qualification: VNStock / FiinQuant / FiinGroup API Datafeed

Status: completed on 2026-07-06 as a documentation-only qualification pass.

Result:

* Updated `docs/VN_EXTERNAL_PROVIDER_STRATEGY.md` with a current provider qualification matrix comparing Vnstock, FiinQuant, FiinGroup API Datafeed, and manual/provenance-required import.
* Classified Vnstock as `prototype_only` unless licensing, source-owner terms, storage/display rights, redistribution rights, rate limits, and data provenance are explicitly resolved.
* Classified FiinQuant as `candidate_after_entitlement` for licensed realtime/tick/orderbook and research workflows; it is not an automatic SSI replacement and must not overwrite DailyOhlc, DailyStockPrice, realtime, or trade-tape ownership.
* Kept FiinGroup API Datafeed as `preferred_after_entitlement` for automated corporate actions/dividends/rights/splits first, followed by financial statements, ratios, news, metadata fallback, macro, and source-labeled external index context.
* Kept manual/provenance-required import as the offline fallback for corporate actions and dividends only when source references are explicit.
* Defined Phase 5.1A entry criteria: written entitlement, auth, production endpoint/package path, rate limits/SLA/pricing, storage/display/redistribution rights, source provenance, historical depth, correction/cancellation semantics, SSI symbol mapping, licensed fixture, disabled-by-default config plan, and explicit SSI ownership isolation.
* Did not implement VNStock, FiinQuant, FiinGroup, external provider runtime, fallback providers, scraping, credentials, config flags, API endpoints, frontend changes, fake data, or changes to SSI `latest_price` ownership.

### Phase 5.0D-2 - SSI-First Data Ownership Matrix Docs Update

Status: completed on 2026-07-06 as a documentation-only ownership clarification.

Result:

* Made `docs/SSI_DATA_CAPABILITY_MATRIX.md` the canonical SSI-first ownership matrix.
* Clarified that SSI owns every field it can provide, and metrics calculable from SSI-owned fields must be calculated internally as SSI-derived data.
* Classified DailyOhlc, `latest_price`, chart candles, DailyStockPrice enrichment, intraday, realtime, trade tape, index data, and SSI-returned metadata as SSI-owned.
* Classified MA/RSI/Bollinger, 20D indicators, bounded DailyStockPrice foreign-flow summaries, and planned 52W high/low, 10D/3M average volume, price-vs-reference %, and daily range % as SSI-derived/internal.
* Deferred beta until SSI index data and methodology are verified; deferred market cap until share-basis semantics are verified.
* Kept corporate actions/dividends/rights/splits, financial statements, EPS/P/E/P/B/ROE/ROA, news, macro, and approved source-labeled non-SSI metadata/index context as external-provider domains.
* Added Phase 4.8A as the planned SSI-derived metrics completion phase before assigning SSI-computable metrics to external providers.
* Did not change runtime code, schemas, frontend behavior, configuration, provider adapters, fallback behavior, fake data behavior, or `latest_price` ownership.

### Phase 5.1A - News Provider Research and Planning

Status: completed on 2026-07-07 as a documentation-only planning pass.

Goal:

Select the best first VN stock/company/market news provider to implement later, without adding runtime calls, credentials, adapters, scraping, RSS ingestion, fallback providers, fake rows, frontend changes, config changes, or SSI ownership changes.

Result:

* Added `docs/VN_NEWS_PROVIDER_RESEARCH.md` with the future `NewsProvider` item contract, provider capability gates, FiinGroup/Vietstock/WiGroup comparison matrix, lower-priority source classification, legal gates, and recommended future architecture.
* Classified FiinGroup API Datafeed News as `preferred_after_entitlement` for the first automated NewsProvider target because official public schemas expose ticker, organization code, title, short/full content, source, source link, publication, create/update, status, and source-code fields.
* Classified Vietstock DataFeed as `candidate_after_entitlement` because official pages list API/Sync delivery, Vietnamese/English support, 24/7 news, company news, and Vietnam news categories, but item-level ticker/source/deduplication schema and rights still need commercial review.
* Classified WiGroup WiFeed/WiData as `candidate_after_entitlement`, likely strongest as a secondary macro/industry/company-news/report source unless a licensed API sample proves ticker-tagged stock-news rows, source URLs, deduplication fields, and display/storage rights.
* Phase 5.1A-2 documents current access status: public docs/schema access is not legal/runtime API access; FiinGroup is `preferred_after_entitlement`, Vietstock is `candidate_after_entitlement`, and Vnstock/VNStock is `prototype_only` for research/manual comparison.
* Classified public RSS/web pages as `blocked_pending_terms`, scraping/unofficial endpoints as `not_allowed_now`, and NewsAPI/GDELT as `secondary_macro_context_only`.
* Left runtime unchanged: news remains disabled/not implemented with `news=[]`, no provider calls, no credentials, no fallback, no fake rows, and no change to `latest_price`.

### Phase 5.1B - Experimental Vnstock News Provider

Status: completed as a contract-only, no-network legal/terms gate.

Result:

* Verified the Vnstock News documentation for RSS `Crawler`, sitemap-oriented `BatchCrawler`/`AsyncBatchCrawler`, and its documented normalized article shape.
* The current license requires written approval for commercial integration and Vnstock is not the source-data owner, so `VN_NEWS_PROVIDER=vnstock_news` returns `news=[]` with `news_status.status=unavailable` and `reason_code=blocked_pending_terms`.
* Added offline normalization tests for URL/provenance preservation, bounded rows, and default full-content omission. No Vnstock package import/dependency, RSS/sitemap request, batch/async crawler, background job, cache write, credential, scraping, fake row, or fallback is enabled.
* SSI remains the owner of all market-data paths and `latest_price` remains SSI DailyOhlc.

### Phase 5.1B-Local - Vnstock News Personal Research Mode

Status: implemented as an explicit local-only runtime option.

* Added `VN_NEWS_PROVIDER=vnstock_news_personal` plus `VNSTOCK_NEWS_PERSONAL_ENABLED=true` for personal local research dashboards only.
* Kept `VN_NEWS_PROVIDER=disabled` as the default and kept `VN_NEWS_PROVIDER=vnstock_news` as `blocked_pending_terms`.
* Uses only lazy optional `vnstock_news.Crawler(...).get_articles_from_feed(limit_per_feed=N)` with bounded sites, per-site limits, TTL cache, and full content omitted by default.
* Package-missing, provider-error, and empty-feed states return explicit unavailable statuses without breaking SSI daily/watchlist/company rows.
* This mode is news-only and must not provide prices, OHLCV, realtime quotes, order book, trade tape, foreign room, market index, metadata, fallback data, or `latest_price` changes.

Future news phases:

* Phase 5.1B - NewsProvider Entitlement Pack: obtain written entitlement, trial credential status, API/auth/rate-limit/SLA/pricing terms, display/storage/redistribution rights, source attribution rules, ticker mapping, historical depth, and a sanitized licensed fixture.
* Phase 5.1C - Licensed NewsProvider Adapter: implement a disabled-by-default provider adapter only after Phase 5.1B passes.
* Phase 5.1D - News UI Cards: render source-labeled company and market news cards only after licensed API rows exist.

### Deferred corporate-actions live-provider track

Goal:

Add verified event rows only after Phase 5.0B passes.

Scope:

* Dividends.
* Bonus/stock dividends.
* Rights.
* Splits.
* Event history and corrections.

Rules:

* Keep source URL/document provenance.
* Do not infer events from price/reference gaps.
* Do not mutate SSI DailyOhlc or claim adjusted-price correctness.

Acceptance criteria:

* Real event rows are source/date labeled.
* Unavailable data remains `events=[]`.
* No external failure changes SSI daily rows.

### Phase 5.2A - Financial Statements Provider

Goal:

Add raw, period-aware financial statements through the approved commercial provider boundary.

Rules:

* Distinguish consolidated/separate reports, company type, period length, report date, audit state, units, and restatements.
* Keep raw statements separate from provider ratios and local derivations.
* Missing financials do not affect market-data status.

### Phase 5.3A - Metadata Fallback and Financial Ratios

Goal:

Fill SSI-null metadata fields under explicit per-field source priority, then add separately labeled provider ratios.

Rules:

* Never silently overwrite SSI metadata.
* Do not compute ratios from incomplete statements unless a separate derivation contract is approved.
* Keep provider methodology and calculation date visible.

### Superseded placeholder - NewsProvider Implementation

Goal:

Add sourced watchlist/company news after a provider contract is selected. Phase 5.1A now owns the research/planning step, Phase 5.1B owns entitlement, Phase 5.1C owns the licensed disabled-by-default adapter, and Phase 5.1D owns UI cards.

Scope:

* Keep news disabled until implemented.
* Include source, title, URL, published time, and matched ticker/company evidence when implemented.
* Cache and dedupe only after provider semantics are documented.

Rules:

* No Mozyfin news/social fallback.
* No heavy scraping unless explicitly approved.
* News failure must not block daily SSI data.

Acceptance criteria:

* `news = []` and `news_status.status = disabled` until provider exists.
* When implemented, news is source-labeled and matched transparently.
* No fake news items.

### Phase 5.5A - Macro and Explicit External Index Context

Goal:

Add a small approved macro series set and, only if licensed, an explicit external VNINDEX fallback.

Rules:

* Review each series owner, API key, revision cadence, units, display notice, and redistribution term separately.
* External VNINDEX must be explicitly source-labeled and must never be presented as SSI.
* Keep macro context neutral and separate from trading advice.

Acceptance criteria:

* No generic unrestricted macro or index feed is assumed.
* Missing macro/index context does not affect SSI daily rows.

### Phase 6.0A - Backend Performance and Caching After Data Reliability

Goal:

Improve backend performance only when rate limits or latency justify it.

Use later:

* Backend DB/cache.
* Historical DailyOhlc/DailyStockPrice cache.
* Provider diagnostics history.
* Background jobs.

Rules:

* Do not add durable storage while current backend TTL cache is enough.
* Persist source, date, and `fetched_at` if durable storage is introduced later.
* Keep stale data clearly labeled.

Acceptance criteria:

* Performance work has measured rate-limit or latency evidence.
* Runtime cache and durable storage semantics are documented separately.
* Daily source ownership remains SSI DailyOhlc for canonical daily fields.

### Phase 7.0 - Product Packaging

Goal:

Make the VN dashboard easier to operate and release.

Scope:

* Clean runbooks.
* Current startup scripts.
* Clear smoke/test/release checklist.
* Deprecated docs clearly marked.

Rules:

* Do not change provider semantics while packaging.
* Keep live/fixture mode explicit.
* Keep deprecated Mozyfin/KBS-era docs marked as historical or superseded.

Acceptance criteria:

* A maintainer can start, smoke-test, and validate the VN dashboard from current docs.
* Deprecated docs no longer contradict the current SSI-strict, progressive workspace direction.

## Known data-quality TODOs

### P0 - contract/data correctness

* Investigate SSI DailyOhlc vs DailyStockPrice mismatch on the same ticker/date. Latest smoke observed FPT on `2026-06-22` with SSI DailyOhlc/dashboard `latest_price`, `ohlcv_close`, and `daily_close` at `70,700`, while SSI DailyStockPrice `close` and `adjusted_close` were `70,800`. The same check showed DailyOhlc `volume = 3,642,400` and DailyStockPrice `matched_volume = 3,643,500`. The dashboard currently uses SSI DailyOhlc close as canonical `latest_price`; follow-up work must decide canonical source and final/provisional status semantics before changing this behavior.

### P1 - live-section semantics

* Completed in Phase 4.7B: unavailable watchlist/company trade tape now uses list-shaped `trade_tape = []`, company status lives in `trade_tape_status`, and sanitized endpoint/provider details live under `diagnostics.trade_tape`.
* Completed in Phase 4.7B: realtime/trade-tape public status messages are short and user-safe; detailed attempted endpoints, HTTP status, retryability, and sanitized provider summaries live under `diagnostics.realtime` or `diagnostics.trade_tape`.
* Completed in Phase 4.7C: trade tape now reads only the background streaming X-TRADE event buffer. Request handlers do not start streams, add subscriptions, use all-market channels, or probe unverified REST candidate names. Historical time-and-sales remains unverified.
* Completed in Phase 4.8E: startup-owned SSI streaming now subscribes to `X:{symbol}` for realtime snapshots and `X-TRADE:{symbol}` for trade-tape rows when trade tape is enabled. Diagnostics distinguish `xtrade_not_subscribed`, disabled, subscribed-empty, stale, and cache-hit states.
* Completed in Phase 4.8E-2: buffered `X-TRADE` rows with timestamp, price, and volume remain visible even when stream freshness is stale. Stale/cache age stays in diagnostics; the UI renders matched-order rows with traded time and SSI board price colors instead of showing loading/stale/lunch-break empty states.
* Completed in Phase 4.8E-3: trade tape now renders SSI-style `Time`, `B/S`, `Vol`, `Price`, `+/-`, and `+/-(%)` columns. B/S comes only from explicit X-TRADE side/aggressor values, unknown side stays `—`, and change fields use trade price versus SSI DailyStockPrice reference without changing `latest_price`.
* Completed in Phase 4.8E-4: observed X-TRADE raw side codes `BU` and `SD` normalize to Buy/Sell, raw `side_if_available` stays visible for audit, and side remains independent from SSI board price color or reference-based change direction.
* Completed in Phase 4.8E-5: dashboard/company trade-tape sections perform bounded selected-ticker warm-up refetch while X-TRADE startup, subscribed-empty, or cache-empty diagnostics are pending. Rows stay the highest-priority render state, and reference/equal/zero-change price colors use dedicated yellow rather than warning/orange.
* Deprecate top-level `intraday_timeframe`. Use `intraday_requested_timeframe` and `intraday_actual_granularity`; the UI must not interpret `intraday_timeframe` as usable candle interval when `intraday_status.status != ok`.
* Move stale intraday `latest_date` and `date_match` metadata into status/diagnostics when no usable intraday data exists. Keep `intraday_candles = []` and `intraday_pulse = null` for unavailable/stale intraday sections.
* Add backoff or longer TTL for non-retryable SSI realtime/trade-tape 404 responses. Desired future behavior: mark `retryable=false`, use a longer TTL/backoff, and avoid repeated endpoint probes that are known unavailable.

### P2 - data enrichment

* Revalidate SSI Securities/SecuritiesDetails aliases only when a sanitized live row-key audit provides new provider evidence. Phase 4.3A intentionally leaves unsupported optional metadata null.
* Completed in Phase 4.5B: SSI DailyStockPrice foreign-flow history now preserves up to 20 recent returned rows per symbol and populates latest-available 5D/20D foreign net volume summaries when enough `foreign_net_volume` rows exist. Future work should only add durable caching or wider history if measured latency/rate-limit evidence justifies it.
* Clean quote metadata semantics. Current responses can have `quote_date` while `quote_price_date` and `quote_price_raw_field` are null/unreliable. Distinguish quote metadata from actual price source.
* Improve `final_close_status`. Current response can say `final_close_status=unknown` and warn the daily candle may still be in progress. Desired follow-up: use VN trading calendar/session time when possible, expose `in_progress`/`provisional` during session, and use `final` or `unknown_after_close` after session if SSI does not confirm finality.

### P3 - cleanup

* Clarify `cache_errors` vs provider unavailable. Provider 404/unavailable is not the same as cache failure.
* Clarify units metadata vs data availability. Units may list intraday/realtime fields even when data is unavailable; UI availability must depend on status plus null/empty checks, not units presence.

## Current known issues / follow-up notes

### SSI symbol metadata is currently limited

Live SSI metadata can be `status=ok` while only providing:

* `symbol`
* `exchange`
* `market`
* `source`

Optional fields may remain null:

* Vietnamese name
* English name
* issuer
* security type
* lot size
* listed shares
* listed date

Null optional metadata is not fatal. The UI should hide optional metadata rows when absent. Future work should inspect additional SSI field names or alternate SSI response shapes before promising richer company metadata.

Observed live watchlist payload for ticker `SSI` after Priority 1:

* Core market-data state was valid: `status=ok`, `source=SSI`, `actual_source=SSI`, `fallback_used=false`, `data_quality.missing_fields={}`, `validation.missing_fields=[]`.
* SSI DailyOhlc fields were present: `latest_price`, `daily_close`, `ohlcv_close`, `open`, `high`, `low`, `close`, `previous_close`, `volume`, and `amount`.
* SSI DailyStockPrice was present with `daily_stock_price.status=ok`, reference/ceiling/floor, matched volume/value, put-through volume/value, and latest foreign buy/sell/net volume/value.
* Metadata remained limited: `company_name`, `name`, `security_type`, `issuer`, `lot_size`, `listed_shares`, and `listed_date` were null even though `symbol_metadata.status=ok` can mean symbol/exchange/market/source only.

Treat these null metadata fields as optional and non-fatal. Hide absent metadata rows in the UI.

### SSI index component availability is not fully confirmed

Live IndexList validation with `market=HOSE` returned `status=ok`, `source=SSI`, `fallback_used=false`, and 10 normalized rows. Observed normalized keys are:

* `index_id`
* `index_code`
* `index_name`
* `exchange`
* `market`
* `source`

The same live check showed that `market=HOSE` can still return cross-market-looking index codes such as `HNX30`, `HNXINDEX`, `HNXUPCOMINDEX`, `VN100`, `VN30`, and sector/style indexes. Treat the returned SSI rows as the authority, but do not assume the request market filter is strict.

Phase 4.4B superseded the earlier unavailable VN30 IndexComponents finding. Live discovery proved that `indexCode=VN30`, with market omitted or `market=HOSE`, can return an exact outer VN30 row with 30 nested members. Missing identifiers, mismatched outer rows, empty nested lists, or provider failures must still return `rows=[]`. Do not hardcode VN30 components and do not use Mozyfin/KBS fallback for SSI-owned index membership. Keep the UI and diagnostics tolerant of unavailable component rows.

Audit blocker fixed before the current SSI milestone: SSI `IndexComponents` provider error/status payloads must parse case-insensitive fields such as `code`, `errorCode`, `status`, and `Status` into a clean SSI unavailable response. They must not raise backend 500s from parser helper errors.

Frontend follow-up after Priority 2: backend API coverage alone was not enough for dashboard visibility. The web UI must explicitly call `/api/v1/stocks/vn/index-list` and `/api/v1/stocks/vn/index-components`, and it must render the SSI index coverage section even when VN30 components return zero rows or `status=unavailable`.

### Quote fields are intentionally missing in strict SSI daily mode

Observed live watchlist payload can include:

* `quote_cache = missing`
* `quote = null`
* `quote_price_date = null`
* `quote_price_raw_field = null`

This is not fatal because the current design uses SSI DailyOhlc close for `latest_price`. Keep the warning that quote does not provide a reliable latest price and latest price uses SSI DailyOhlc close. Realtime/quote work should use the SSI realtime contract when available and must not force a REST quote fallback into the daily close path.

### Row-level status must not mix optional source caveats with SSI daily validity

Confirmed UI issue after strict SSI migration: rows could show valid SSI DailyOhlc close/date/volume, valid SSI DailyStockPrice reference/foreign/matched fields, and valid realtime snapshot values while the scan badge still showed `Data unavailable` or `Data source error`.

Root cause: the frontend primary scan state was using broad validation/cache/realtime state. Optional quote cache, limited metadata, unavailable corporate actions, final/adjusted unknown statuses, disabled intraday, disabled news/cache state, or realtime snapshot context could be elevated into a row-level data error.

Fixed status taxonomy:

* Row-level `Data unavailable` is reserved for missing/invalid required SSI DailyOhlc fields, explicit row unavailable state, row error, or SSI DailyOhlc cache error.
* Quote missing, limited metadata, unavailable corporate actions, final/adjusted unknown statuses, disabled intraday, disabled news/cache states, and SSI realtime issues remain caveats or separate source states.
* Cache labels shown in the primary watchlist/table should refer to SSI DailyOhlc. Broader source refresh/cache details belong in diagnostics.
* Source labels should stay explicit: daily close/chart = `SSI DailyOhlc`, reference/limits/foreign/matched/put-through = `SSI DailyStockPrice`, realtime snapshot/trade tape = `SSI`, intraday = `SSI IntradayOhlc`.

### VN news provider disabled

Mozyfin free-tier news/social API paths are no longer available for the dashboard, so VN news is disabled/not implemented by default. Watchlist and company research responses should return a stable disabled or `not_implemented` news block instead of a Mozyfin plan/auth error. Future work should add a separate NewsProvider contract and then normalize/decode Vietnamese text before rendering.

News rendering must remain independent from optional SSI realtime caveats. Missing quote fields, limited symbol metadata, unavailable index components, final/adjusted unknown statuses, disabled intraday, or SSI realtime issues must not hide selected ticker news if a future NewsProvider supplies rows.

### SSI IntradayOhlc operational notes

SSI IntradayOhlc is now the strict VN intraday candle source. Watchlist and company research payloads should expose `intraday_source=SSI` with `intraday_status.status=ok` when candles exist. If SSI returns no candles, the endpoint fails, or `SSI_FASTCONNECT_INTRADAY_ENABLED=false`, the intraday block should show `unavailable` or `disabled` without changing the row-level SSI DailyOhlc status.

Intraday candles are not realtime matched quotes and are not the official daily close. SSI realtime snapshot and trade tape remain separate from SSI IntradayOhlc until endpoint semantics are fully verified. Do not mix intraday candle data with official SSI DailyOhlc close.

Latest live smoke found SSI IntradayOhlc can return an older latest candle date than SSI DailyOhlc, for example daily date `2026-06-19` with latest intraday candle date `2026-06-12`. The service must compare latest intraday candle date with latest daily trading date. If they differ, keep the daily SSI row `ok`, but mark intraday unavailable with a sanitized date-mismatch message and do not derive intraday pulse labels from stale candles.

The same smoke found the requested dashboard timeframe label may not describe actual returned candle cadence; returned timestamps can be minute-like. Treat intraday cadence as provider-returned and detect it from timestamps when possible. UI labels should use neutral names such as latest intraday close, intraday change, and session intraday volume instead of claiming a fixed candle interval.

Contract cleanup before the current SSI milestone commit: `intraday_requested_timeframe` is the SSI request hint, while `intraday_actual_granularity` and `intraday_actual_granularity_seconds` describe detected returned cadence. The compatibility `intraday_timeframe` field remains for existing clients but must not be presented as actual candle granularity.

Unavailable live-section data must stay empty instead of becoming fake metrics. If SSI intraday is disabled, unavailable, stale, or has no current candle rows, return `intraday_pulse = null`, `intraday_candles = []`, and render a concise `SSI intraday unavailable` state. If SSI realtime snapshot is unavailable, return `realtime_snapshot = null` and do not render snapshot price/time/change/session-volume rows. If SSI trade tape has no rows, return `trade_tape = []`, keep status in `trade_tape_status`, and render `SSI trade tape unavailable`; attempted endpoints, HTTP status, and sanitized diagnostics belong in details/logs, not primary metric rows.

### Final close / adjusted price status remains conservative

`final_close_status = unknown` and `adjusted_price_status = unknown` should remain conservative unless SSI provides explicit finality/adjustment metadata. Do not infer corporate actions from adjusted close/reference gaps. Do not mutate raw OHLCV close.

Observed live watchlist payload can also include `candle_status = unknown`, `price_adjustment_status = unknown`, and `corporate_action.status = unavailable`. Keep these conservative warnings until an explicit source provides finality, adjustment, or event metadata.

### Foreign rolling history is separate from latest SSI foreign flow

Watchlist payloads can still include null legacy rolling fields:

* `foreign_net_5d`
* `foreign_net_20d`

Phase 4.5B populates `foreign_net_5d_latest_available`, `foreign_net_20d_latest_available`, `foreign_net_latest_available_date`, and `foreign_net_history_count` from recent SSI DailyStockPrice `foreign_net_volume` rows when enough rows are returned. Latest matched-date foreign buy/sell/net volume/value remains separate and valid from SSI DailyStockPrice.

### DailyOhlc vs DailyStockPrice consistency

Current live checks showed watchlist daily close and DailyStockPrice close can align after refresh. If DailyOhlc close and DailyStockPrice close differ, first check:

* same trading date
* cache freshness
* old backend response
* chart/watchlist TTL mismatch

Do not use DailyStockPrice close to silently overwrite DailyOhlc close unless that behavior is explicitly designed. Keep labels separate:

* Daily close: SSI DailyOhlc
* Reference/limits/foreign/matched/put-through: SSI DailyStockPrice

### PowerShell JSON depth can mislead debugging

`ConvertTo-Json -Depth 4` may stringify nested objects as `@{...}`. Use `ConvertTo-Json -Depth 12` before assuming the backend response shape is broken.

### SSI DailyStockPrice / DailyIndex chunking

These endpoints require <=29/30-day windows. Full-year chunking is allowed for smoke/debug/internal validation, but should not become heavy automatic UI behavior. The UI should keep DailyStockPrice quick facts to recent windows unless a later design changes this.

### Local DB remains deferred

Current design remains SSI live API plus backend cache/TTL. Local market-data DB is intentionally deferred because current call volume is low. Revisit only if SSI rate limits, latency, or repeated full-history calls become a problem.

### Strict provider boundaries remain mandatory

SSI-owned market data must not silently fallback to Mozyfin/KBS. Mozyfin owns no VN dashboard runtime path. KBS is legacy-only for explicit development diagnostics and is disabled by default.

Normal VN watchlist, company, realtime, index, corporate-action, and observability paths must not construct `MozyfinFetcher` or require Mozyfin CLI/key/fixture configuration when `MOZYFIN_ENABLED=false`, `MOZYFIN_NEWS_ENABLED=false`, and `VN_ALLOW_LEGACY_MOZYFIN_PROVIDER=false`. Corporate actions should return explicit unavailable/manual-unavailable state until a verified external event provider exists.

Observability cleanup before the current SSI milestone commit: the `mozyfin` block is minimal when disabled (`status`, `source`, `reason`). Generic VN request/cache/single-flight counters belong under `dashboard_runtime` so SSI runtime activity is not shown as Mozyfin activity. SSI health is split into `ssi_core`, `ssi_intraday`, `ssi_realtime`, and `ssi_trade_tape` so daily/intraday/realtime/tape availability can be read separately.

External providers are required for:

* BCTC/KQKD
* financial statements
* financial ratios
* corporate actions
* dividends/rights/splits
* macro/Fed/oil/USD/gold

## Product/design principles

* Make selected ticker context obvious first.
* Keep price-source separation visible but not noisy.
* Prioritize the chart and selected ticker information over diagnostics.
* Collapse technical/debug sections by default.
* Keep chart interaction close to broker-style inspection.
* Optimize the dashboard for quick scanning.
* Keep mobile layout chart-first.
* Avoid clutter from too many equal-weight cards.
* Use compact labels and consistent spacing.
* Keep dark dashboard style consistent across pages.

## Completed

### Data and source separation

* Vietnam watchlist cards
* SSI daily OHLCV source
* SSI realtime snapshot contract
* SSI trade tape contract
* SSI DailyStockPrice reference/limit/foreign/matched detail block
* SSI IntradayOhlc intraday pulse
* Daily close / realtime snapshot / trade tape separation
* Legacy KBS snapshot state kept disabled by default
* SSI unavailable/error normalization
* Data freshness and status layer
* Observability endpoint

### Dashboard features

* Intraday pulse
* Selected ticker details
* Watchlist cards
* Inspect chart endpoint
* Inspect chart with candles, volume, RSI14, MA20, MA50, Bollinger
* Date axis for inspect chart
* Inspect chart zoom, pan, and reset controls
* Expanded inspect chart mode
* Watchlist scan summary and table scan-state column
* Relative timestamps for news
* News timestamp parsing from Mozyfin `published_date`
* Corporate actions stub endpoint
* English frontend page text

### Stability and correctness

* Mozyfin watchlist dedupe
* Mozyfin cache/single-flight protection
* KBS refresh overlap protection
* KBS provider error handling
* Frontend KBS refresh guard
* Observability non-fatal tracking
* Tests for Vietnam dashboard data semantics

## Current product issues

The dashboard still has UI opportunities, but they are not the next implementation priority after Phase 3.5A. Keep these as deferred product observations until the Phase 4.0A capability matrix and priority reliability work are complete.

Current weak points:

* Main screen can feel cluttered.
* Selected ticker header is not strong enough.
* Debug/status information can dominate the view.
* Inspect chart still needs broker-style interactions.
* News needs better grouping and freshness context.
* Mobile layout needs chart-first prioritization.
* Watchlist view needs a denser table mode for comparison.

## Product and UI backlog

These items remain useful but are deferred. Use the Phase 4.0A through Phase 6.0A data-first sequence for current implementation order. Revisit this UI backlog when verified data capability requires rendering changes or after the priority reliability work is complete.

### 1. Improve dashboard visual hierarchy and reduce clutter

Status: partial in first roadmap batch; updated selected-ticker hierarchy in the scanability pass.

Implemented so far:

* Added a compact Data status summary near the top.
* Moved selected ticker context and inspect chart ahead of secondary comparison cards.
* Moved provider/cache/debug details behind collapsed diagnostics.
* Moved the watchlist scan summary and indicator table above the selected ticker area so the table is the primary scan surface.
* Simplified the selected ticker card into a compact identity, primary metrics, and compact data-quality summary.

Goal:

Make the dashboard easier to scan when this deferred UI work resumes.

Target layout:

* Top: market status and data freshness
* Left: watchlist
* Center: selected ticker and inspect chart
* Right: compact quick facts
* Bottom: news, trade tape, diagnostics

Rules:

* Important information first.
* Diagnostics secondary.
* Avoid equal visual weight for every card.
* Use spacing and typography to separate primary, secondary, and debug content.

### 2. Improve selected ticker header

Status: partial; compact summary pass implemented.

Implemented so far:

* Added a compact selected ticker header.
* Shows symbol/company label, Daily close, price date, Vs SSI reference, foreign net volume, daily volume versus 20D average, Latest news, and SSI source badges.
* Keeps SSI daily, SSI DailyStockPrice, SSI intraday, and SSI realtime labels visually separate.
* Shows realtime/trade-tape status badges in the selected summary only when they need attention.

Goal:

Make the selected ticker context obvious.

Suggested header content:

* Symbol and company name
* SSI daily close
* Price vs SSI reference
* Foreign net volume or value with clear units
* Daily volume versus 20D average volume
* News freshness
* Daily source badge and meaningful live-status badges

Example:

```text
ACB — Asia Commercial Bank
Daily close: 22.65
Price vs SSI reference: -0.88%
Foreign net volume: -1.58M shares
Daily volume: 14.64M / 20D avg 31.43M
Source: SSI DailyOhlc
```

Design rules:

* Keep it compact.
* Use small badges for `Daily`, `Realtime`, `Reference`, `News`.
* Do not mix source meanings.
* Do not add trading instruction wording.

### 3. Collapse debug and observability sections by default

Status: partial in first roadmap batch.

Implemented so far:

* Data status defaults to OK/Partial/Unavailable.
* Provider diagnostics, cache diagnostics, raw freshness, request times, counters, and KBS details are available under Show diagnostics.

Goal:

Keep diagnostics useful but not visually dominant.

Default visible:

```text
Data status: OK / Partial / Unavailable
```

Collapsed details:

* Provider diagnostics
* Cache diagnostics
* Raw errors
* Last request times
* Single-flight/cache info

Rules:

* Debug information should be available but not primary.
* No raw provider error should be primary UI text.
* Raw error details can remain inside expanded diagnostics.

### 4. Add zoom, pan, and reset to inspect chart

Status: complete in current codebase.

Implemented:

* Zoom in and zoom out controls.
* Pan left and pan right controls.
* Reset to the full selected range.
* Visible candle window rendering while the full chart data remains loaded.
* Date labels and hover data update with the visible window.
* Candles, volume, RSI14, MA20/MA50, and Bollinger overlays stay aligned.

Goal:

Make the chart closer to SSI/VPS-style inspection.

Required controls:

* Zoom in
* Zoom out
* Pan left
* Pan right
* Reset

Behavior:

* Keep full chart data loaded.
* Render a visible window subset.
* Zoom around current center.
* Pan through historical points.
* Reset to full selected range.
* Date labels and tooltip must update with visible window.
* Candles, volume, RSI, and overlays must stay aligned.

### 5. Add fullscreen chart mode

Status: complete in current batch.

Implemented:

* Expanded chart button on the inspect chart.
* Larger chart overlay using the existing loaded SSI daily OHLCV chart points.
* Same range, MA20/MA50/Bollinger, zoom, pan, and reset controls.
* Close button and Escape key support.
* Daily OHLCV and SSI realtime separation remains visible in expanded mode.
* Compact and expanded modes share the same chart control components to keep behavior aligned.

Goal:

Give enough space for proper chart inspection.

Requirements:

* Fullscreen or expanded chart button
* Larger candle area
* Volume and RSI remain visible
* Same MA20/MA50/Bollinger toggles
* Same range and zoom controls
* Escape/close support
* Mobile-friendly layout

### 6. Make SSI FastConnect the strict REST market-data owner

Status: strict SSI defaults added for supported REST market data; Mozyfin/KBS fallback removed for SSI-owned paths.

Implemented so far:

* Added disabled-by-default SSI FastConnect FC Data configuration placeholders.
* Added standalone SSI FC Data provider foundation for AccessToken, Securities, SecuritiesDetails, DailyOhlc, DailyStockPrice, and DailyIndex.
* Made SSI the default and strict source for Vietnam daily OHLCV, chart OHLCV, DailyStockPrice, reference/ceiling/floor, foreign flow, and DailyIndex preparation.
* Removed Mozyfin fallback from SSI-owned OHLCV/chart/index/reference/foreign paths.
* Added chart source metadata so the inspect chart can show SSI or SSI unavailable labels.
* Added DailyStockPrice fields for reference, ceiling/floor, matched/put-through values, total volume/value, and foreign flow through `VN_DAILY_STOCK_PRICE_PROVIDER=ssi`.
* Added UI detail rendering for SSI reference, ceiling/floor, foreign net volume/value, matched value, put-through value, and adjusted close when available.
* Wired chunked SSI DailyStockPrice rows into explicit `daily_stock_price.status=ok` API/UI state, optional `ssi_*` convenience fields, and stale foreign-history caveat suppression.
* Added chart response `candles` compatibility alongside `points` and a configurable Vite API proxy target for non-default local backend ports.
* Expanded tolerant mappings for SSI DailyOhlc, DailyStockPrice, DailyIndex, and SecuritiesDetails field-name variants.
* Added 29-day provider-level chunking for SSI DailyStockPrice and DailyIndex, which reject broad ranges even though DailyOhlc supports direct 1Y chart queries.
* Added mocked provider tests and a local safe smoke script.
* Replaced KBS realtime/trade tape behavior with SSI realtime/trade-tape contracts and replaced Mozyfin news with a disabled/not_implemented VN news state.

Goal:

Use SSI FastConnect as the strict owner for supported VN REST market data while keeping unsupported domains explicit.

Scope:

* Provider skeleton and secure configuration placeholders.
* Authentication and connection smoke tests.
* Clean unavailable states when SSI-owned data is unavailable.
* Explicit source labels for SSI values and disabled/not_implemented unsupported domains.

Rules:

* SSI-owned data must not fall back to Mozyfin or KBS.
* `latest_price` uses SSI DailyOhlc close when SSI daily rows are available.
* KBS realtime/trade-tape paths remain legacy-only behind explicit development flags; VN news remains disabled until a separate NewsProvider is implemented.
* If SSI is unavailable, show unavailable rather than silently replacing values.

### 7. Improve news structure

Goal:

Make news easier to interpret by freshness and relevance.

Sections:

* Latest news
* Selected ticker news
* Market news
* Macro news

Each item should show:

```text
Source · relative time · ticker/context if available
```

Add freshness state:

```text
No fresh news in the last 24h
```

Rules:

* Do not mix stale and fresh news without visible time labels.
* Do not imply importance unless source data supports it.
* Keep source and timestamp visible.

### 8. Add watchlist table view

Status: partial in current scanability batch.

Implemented:

* Added a compact watchlist scan summary with neutral `Strong`, `Improving`, `Neutral`, `Weakening`, `Risk elevated`, and `Data unavailable` counts.
* Added a table-level scan-state column derived from existing status labels, cache freshness, and optional live-section state.
* Kept normal warnings as secondary table context so warning-only rows do not dominate the scan summary.
* Separated source/data caveats such as foreign-date mismatch, indicator-input caution, unconfirmed final close, and unknown adjusted-price metadata from primary market scan labels.
* Kept caveats visible in compact row disclosures because existing response fields identify the limitations but do not provide enough confirmed source metadata to resolve them automatically.
* Kept scan states ticker-level because the current watchlist payload does not include a sector field.

Goal:

Allow faster comparison across tickers.

Suggested columns:

* Symbol
* Daily close
* SSI realtime snapshot status
* Change vs reference
* RSI14
* MA trend
* Session volume / 20D avg
* News age
* Data status

Rules:

* Table view should complement cards, not remove cards.
* Sorting can be added later.
* Keep labels neutral.

### 9. Improve mobile layout

Goal:

Make the dashboard usable on smaller screens.

Mobile order:

1. Selected ticker header
2. Inspect chart
3. Quick facts
4. News
5. Watchlist
6. Realtime details
7. Diagnostics

Rules:

* Chart-first on mobile.
* Hide or collapse debug sections.
* Avoid dense side-by-side layouts.
* Keep buttons reachable and compact.

### 10. Add real corporate actions source later

Goal:

Show recent and upcoming corporate actions without inference.

Allowed sources:

* Explicit corporate action calendar/history source
* Event history source with ex-date/record date/payment date
* Structured provider API if available

Required fields:

* Ticker
* Event type
* Ex-date
* Record date
* Payment date if available
* Cash dividend per share if available
* Stock dividend/bonus/rights ratio if available
* Source URL or source name

Rules:

* Do not infer from price gaps.
* Do not mutate OHLCV.
* Do not call reference price dividend-adjusted unless confirmed.
* Keep card hidden or compact when unavailable.

## Near-term SSI implementation sequence

This section records the earlier SSI migration sequence and implementation history. It is not the current next-task order. The current next task is Phase 4.0A, followed by the data-reliability phases above.

### Priority 0 - Finalize current SSI strict migration

* Validate browser UI with a real local SSI environment.
* Confirm chart and watchlist use SSI consistently.
* Confirm the DailyStockPrice panel displays reference, ceiling/floor, foreign, matched, and put-through fields when SSI returns them.
* Confirm news is disabled/not_implemented and does not show Mozyfin plan/auth errors.
* Confirm SSI realtime snapshot and trade tape remain separate from daily close and intraday candles.
* Run a secret scan before committing.
* Commit the current SSI phase after validation.

### Priority 1 - SSI Securities/SecuritiesDetails metadata

Status: implemented in the current working tree.

* Added SSI-only symbol metadata coverage through `SecuritiesDetails`, with `Securities` as a same-provider metadata fallback.
* Added company name, exchange, market, industry/sector, security type, issuer, lot size, listed shares, and listed date when SSI returns them.
* Added compact selected-ticker metadata display.
* Missing metadata fields remain unavailable/null; Mozyfin is not used for SSI-owned symbol metadata.

### Priority 2 - SSI IndexList/IndexComponents

Status: provider, service, API, and mocked parser coverage added in the current working tree.

* Added SSI-only index list coverage through `/api/v1/stocks/vn/index-list`.
* Added SSI-only index component coverage through `/api/v1/stocks/vn/index-components?index_code=...`; the endpoint also accepts the legacy `index=...` query alias.
* Added compact dashboard diagnostics for SSI index coverage so IndexList identifier resolution, provider identifier, and VN30 component availability are visible.
* Avoid hardcoded index assumptions. Use IndexList for discovery and DailyIndex identifiers; send an explicit caller-provided IndexComponents code directly through the verified SSI `indexCode` shape.
* Live IndexList works in the current SSI environment.
* Phase 4.4B live discovery proved exact SSI VN30 IndexComponents rows through `indexCode=VN30`; continue verifying any other index before relying on component rows.

### Implemented note - Vietnam Company Research Terminal shell

Status: implemented in the current working tree as a data contract and page skeleton.

* Added `/api/v1/stocks/vn/company/{ticker}` as a source-aware company research snapshot endpoint.
* Reuses the existing SSI-backed Vietnam watchlist contract for profile, price, trading stats, foreign flow, and technical snapshot blocks.
* Keeps source coverage explicit for Daily OHLCV, DailyStockPrice, Profile, News, Financials, and Corporate actions.
* News, financials, and events are placeholders with `not_implemented` status; missing provider coverage must not make the company page unavailable.
* Does not scrape Mozyfin, implement a news provider, implement fundamentals, or infer corporate actions.
* Dashboard ticker symbols link to `/vietnam/company/{ticker}` for drill-down.

### Priority 3 - IntradayOhlc

Status: implemented in the current working tree for compact watchlist/company intraday pulse.

* Added SSI IntradayOhlc provider support using existing SSI auth, base URL, cache, and secret-safe error handling.
* Wired SSI intraday candles into `/api/v1/stocks/vn/watchlist` and `/api/v1/stocks/vn/company/{ticker}`.
* Preserved `intraday_source=SSI`, `intraday_status.status=ok|unavailable|disabled`, and no Mozyfin/KBS candle fallback.
* Kept intraday candles separate from official SSI DailyOhlc close and SSI realtime snapshot/trade tape.

### Implemented note - SSI realtime snapshot and trade tape contracts

Status: provider, service, API, and UI contract added in the current working tree.

* Added SSI FastConnect realtime snapshot and trade-tape provider methods using existing SSI auth, cache, timeout, and secret-safe error handling.
* Wired `/api/v1/stocks/vn/realtime` and `/api/v1/stocks/vn/realtime/trades` to SSI by default.
* Added watchlist and company research fields for `realtime_snapshot`, `realtime_status`, `trade_tape`, and `trade_tape_status`.
* Updated dashboard/company UI labels to show SSI realtime and SSI trade tape, with neutral unavailable states when SSI returns no usable rows.
* Disabled KBS by default; KBS is legacy-only behind `VN_ALLOW_LEGACY_KBS_PROVIDER=true` and `KBS_ENABLED=true`.
* Live SSI realtime/trade-tape endpoint names, permissions, and row shapes still require validation in an environment with the relevant SSI data entitlements.

### Priority 4 - SSI streaming/protocol hardening

Status: Phase 4.0C-8 added backend lifecycle startup/shutdown for the process-local SSI streaming manager. It remains config-gated and bootstrap-symbol-gated; realtime is reliable only when live startup subscriptions produce fresh cache rows.

* Add controlled application lifecycle startup only after live environment validation confirms credentials, permissions, stop behavior, retry/backoff, and stream freshness.
* Keep the verification-script cache separate from the backend cache; Phase 4.0C-8 backend bootstrap owns only the FastAPI process-local manager/cache.
* Support safe subscriptions for market data, foreign room, index data, and realtime bars.
* Add heartbeat, reconnect, and cache behavior.
* Compare live SSI stream/probe behavior against dashboard REST expectations.
* Keep unavailable states explicit until SSI realtime/trade-tape endpoints are proven stable.

### Priority 5 - External fundamentals, corporate actions, and news

* Qualify corporate actions first using the Phase 5.0B access/legal gate.
* Evaluate an external BCTC/KQKD provider after corporate actions.
* Evaluate a separate NewsProvider after financial/company data; do not rely on Mozyfin free-tier news/social APIs.

### Deferred - Local DB market-data store

Local DB market-data storage is deferred because current dashboard call volume is low and backend cache/TTL is sufficient for the present SSI live API mode. Revisit a DB-backed store if SSI rate limits, repeated full-range fetches, UI latency, or historical replay requirements become a practical problem.

## SSI migration rules

* SSI credential access remains disabled by default until config is present, but supported VN REST provider selection defaults to SSI.
* Never commit SSI credentials.
* Never print tokens, private keys, account IDs, or secrets.
* Add `.env.example` placeholders only.
* Do not add FC Trading or account/order/cash/stock-transfer actions.
* Do not use Mozyfin or KBS fallback for SSI-owned data.
* If SSI-owned data is unavailable, return unavailable.
* Keep VN news disabled until a separate NewsProvider is implemented.
* Keep KBS legacy realtime disabled by default unless explicitly enabled for development diagnostics.
* Keep source labels explicit: `SSI` for market data and realtime/trade tape; `disabled`/`not_implemented` for unsupported news/fundamentals/events.

## Later backlog

### Market breadth

* VNINDEX / VN30 snapshot
* Number of advancing/declining stocks
* Sector breadth
* Volume breadth
* Index vs watchlist relative strength

### Portfolio-aware dashboard

* User holdings summary
* Position exposure
* Cost basis if available
* Watchlist vs holdings distinction
* Portfolio news filtering

### Alert rules

* Price level alert
* RSI threshold alert
* Volume spike alert
* KBS freshness alert
* News freshness alert

Rules:

* Alerts should be neutral.
* No trading instruction wording.

### Chart event overlay

* Corporate action markers
* News markers
* Large volume markers
* Earnings/result date markers if available

Rules:

* Events must come from explicit sources.
* No inferred corporate action markers.

### Better chart engine

Possible future migration:

* `lightweight-charts`
* Better candlestick rendering
* Native pan/zoom
* Price scale
* Crosshair synchronization
* Mobile gesture support

Use only if custom SVG becomes too costly to maintain.

## Engineering standards

For each change:

* Keep scope small.
* Preserve existing data semantics.
* Add focused tests.
* Avoid broad rewrites.
* Avoid unnecessary dependencies.
* Keep frontend/backend contracts explicit.
* Keep error handling non-fatal.
* Keep unavailable states clean.
* Update changelog when a user-visible feature changes.

## Validation checklist

Run the checklist that matches the changed surface, then record gaps in the handoff.

Backend checks:

```powershell
python -m py_compile <changed_python_files>
python -m pytest <relevant_tests> -q
```

Frontend checks:

```powershell
cd apps\dsa-web
npm.cmd test -- VietnamDashboardPage.test.tsx
npm.cmd run build
cd ..\..
```

SSI smoke checks:

```powershell
python scripts\ssi_fastconnect_smoke.py
python scripts\ssi_fastconnect_smoke.py --probe
```

Manual browser validation:

1. Start backend and frontend with a real local SSI environment.
2. Open `/vietnam`.
3. Confirm selected ticker loads.
4. Confirm chart uses SSI DailyOhlc.
5. Confirm watchlist uses SSI for SSI-owned fields.
6. Confirm DailyStockPrice fields populate when SSI returns them.
7. Confirm SSI realtime snapshot and trade tape remain separate realtime blocks.
8. Confirm news is disabled/not_implemented or supplied by a future separate NewsProvider.
9. Confirm diagnostics do not dominate the page.

Guardrail checks:

* Run `git diff --check`.
* Run a secret scan before commit.
* Confirm no SSI credentials, tokens, auth headers, consumer IDs, consumer secrets, private keys, account IDs, or raw auth responses appear in docs, tests, fixtures, logs, or output.
* Confirm no FC Trading, order placement, account actions, cash transfer, stock transfer, or portfolio trading actions were added.
* Confirm no trading-instruction, price-target, or recommendation wording appears.
* Confirm no Mozyfin fallback exists for SSI-owned market data.
* Confirm KBS is disabled by default and only available behind explicit legacy diagnostics flags.
* Confirm VN news is disabled/not_implemented until a separate NewsProvider exists, and unsupported domains remain separate from SSI market data.

### Phase 4.11F - SSI Streaming Lifecycle and Subscription Recovery

Implemented with deterministic fake-transport proof. The existing process-local manager is the single application lifecycle/reconnect owner for the official adapter's channel transport cohort. Every logical start/restart increments a generation; current-generation open/close/error/message callbacks alone may update lifecycle state, caches, freshness, or persisted-snapshot dirtiness. Approved configured channels restore once per generation, partial context failure is isolated, and a fresh current-generation event is required before that context becomes ready. Retryable active-session failures use one bounded 2/5/10/20/30-second schedule with bounded jitter; explicit auth/authorization/config/subscription failures fail fast. Lunch/closed silence does not trigger recovery, ATC uses normal active-session policy, and stale cache remains visible. The broad observability route exposes worker-local transport/context state; stream panels use concise reconnecting/stale/closed copy. A bounded after-hours smoke on 2026-07-16 observed authorization fail-fast at generation 1 with zero reconnect schedules/attempts and unavailable optional panels. Active-session natural-disconnect runtime proof remains pending, so continuity is not guaranteed. Phase 4.11D-3 remains blocked and no stream is a candle source.

Phase 4.11F-A attempted active-session acceptance on 2026-07-17 from 09:19 to 09:32 ICT. Deterministic acceptance remained green (146 tests), but bounded normal-entrypoint launches (including one Web UI auto-build-disabled diagnostic retry) and direct single-worker Uvicorn did not become HTTP-ready, preventing observability, provider authorization, subscription, event-readiness, and endpoint proof. The diagnostic retry consumed one more substantive process launch than the intended two-start cap, after which no further server was started. Import and core configuration-service construction completed in isolation, but the exact pre-listener blocker was not established; no speculative code or credential change was made. Status: application runtime acceptance blocked before HTTP readiness. Initial live readiness and natural reconnect remain pending.

Phase 4.11F-R1 corrected that first-attempt diagnosis and hardened the pre-existing launcher boundary. Direct Uvicorn and the normal launcher both reached application startup and port binding in approximately five seconds while SSI bootstrap continued independently and reported authorization failures afterward. `start_api_server()` now reports success only after Uvicorn readiness, surfaces background startup failure/timeout, and keeps one worker without reload. Deterministic tests prove HTTP, broad observability, and intraday health remain reachable for immediate, blocked, authorization, network-failure, and no-event stream starts. Status: R1 implemented and validated; Phase 4.11F-A active-session fresh-event/natural-reconnect retry remains pending.

Phase 4.11F-A2 completed the bounded active-session retry on 2026-07-17 during the scheduled continuous morning. The normal launcher became HTTP-ready in 4.66 seconds and both no-store health surfaces were readable, closing the R1 readiness question. SSI rejected all 154 planned context subscriptions as `authorization` before any physical transport opened; all six contexts had zero current-generation events and reconnect scheduling correctly remained at zero. Repeated health and stream-backed endpoint reads were non-mutating and degraded to sanitized unavailable/empty responses. Status: active-session acceptance outcome C, blocked by provider authorization/entitlement rather than application lifecycle readiness. Natural disconnect, restoration, and fresh post-reconnect event proof remain pending until authorized transport access is available; do not retry by changing credentials or weakening fail-fast behavior speculatively.

Phase 4.11G reconciled that result with historical success. Unchanged SSI 2.2.2 credentials/configuration produced live callbacks for all six minimal contexts, the StockClock X-only path worked through 30 symbols, and a normal 154-channel backend accepted current-generation events with no authorization or subscription failures. A2's sanitized 403 classification was valid as a forbidden response at that time, but it did not prove missing entitlement. The evidence-backed integration defect was duplicate SDK client/token construction per channel: one generation could request the same access token up to 154 times before opening all transports. One shared `MarketDataClient` now owns the cached token for the generation's channel-specific streams. The dev verifier also follows the current generation callback signature and no longer silently expands a requested X diagnostic into every optional context. Status: live streaming works; entitlement is not the current blocker. Natural disconnect, restoration, and post-reconnect freshness proof remain pending.

### Phase 4.12 - Foreign Flow Product and Delivery Sequence

Status: Phase 4.12A-Lite completed the DailyStockPrice-only contract gate with outcome A, full symbol daily contract. Exact buy/sell/net volume and value fields, shares/VND units, provider trading dates, multi-date history, direct-net agreement, and latest-date-inclusive 5D/20D rolling semantics are verified. Rows are `daily_available`; active-session cumulative behavior and an explicit provider-final marker remain unproven. No runtime API or frontend was added.

Delivery order and gates:

1. **Phase 4.12A-Lite - DailyStockPrice contract confirmation (completed):** verified the full symbol daily contract only. SSI `R` remains foreign-room context; no stream was inspected as flow.
2. **Phase 4.12B - Historical symbol API (implemented):** exposes one bounded SSI DailyStockPrice symbol endpoint with recent-session/date-range modes, typed `daily_available` rows, latest row, honest coverage, null-aware 5/20/60-session summaries, dedicated cache/coalescing, stale-if-error, and process-local observability. It adds no frontend, current-session source, ranking, aggregate, fallback provider, or DailyOhlc ownership change.
   * Phase 4.12B-R1 outcome B: the normal launcher reached HTTP readiness in 6.226 seconds. All bounded FPT probes returned the correct typed `network_error` unavailable state under local SSI network unavailability; the repeated 20-session key used negative cache with no provider-call increase, observability remained no-store/read-only, and active in-flight returned to zero. No application, launcher, endpoint, provider, or configuration repair was required.
3. **Phase 4.12C - Current-session snapshot and reconciliation:** proceed only if an official cumulative current source is proven; detect resets and reconcile provisional with final.
4. **Phase 4.12D-1 - Daily watchlist and rankings (implemented):** one bounded POST batch accepts up to 30 normalized unique symbols, reuses the Phase 4.12B DailyStockPrice service with concurrency capped at four, returns ordered per-symbol latest/5-session/20-session summaries and explicit coverage/state, and builds watchlist-scoped rankings without history arrays. The dashboard makes one cancellable request per non-empty watchlist, retains prior successful data during failed refresh, and adds `NN ròng`, `NN 5P`, and latest-session/5/20-session rankings. Current-session columns remain gated on Phase 4.12C; market-wide aggregation remains gated on Phase 4.12E/F.
   * Runtime acceptance used the normal launcher on port 8012. Current SSI network unavailability produced five explicit unavailable rows; an identical repeat reused all five negative-cache entries without increasing provider calls, and active work returned to zero. Production-handler validation also confirmed invalid symbols return HTTP 422 before provider work after correcting a custom-validator serialization mismatch. Browser smoke was environment-blocked before navigation; deterministic frontend tests and production build passed.
5. **Phase 4.12E-1 - Dedicated foreign-flow workspace (implemented):** adds the lazy `/foreign-flow` route and shared desktop/mobile navigation item. The page reuses the current custom-watchlist ownership and the D-1 batch through one shared cancellable request hook, then renders null-aware `Phiên gần nhất`/5/20 value-or-volume summaries, watchlist-only rankings, and a sortable/filterable scanner. URL parameters own presentation state; empty scope makes no request; over-limit scope makes one first-30 request with a visible `30/N` notice; no history N+1, polling, stream, provider, or schema was added.
   * Phase 4.12E-1-R1 normalizes the existing backend `*_5d`/`*_20d` fields at the frontend API boundary, makes summary/ranking/scanner coverage and state follow the selected window, and prevents non-finite or unavailable values from rendering malformed coverage. Units and `aria-sort` are explicit; technical `daily_available` stays internal. No backend, request, source, or scope changed.
   * Phase 4.12E-1-R2 derives a rich watchlist-only workspace from that same response: paired latest value/volume totals; cumulative-net-only 5/20 summaries; selected-window breadth and coverage; top-1/3/5 absolute-flow concentration; a deterministic keyboard-accessible SVG treemap sized by absolute selected net flow; shared-scale buy/sell bars; and URL-owned overview/detail scanner density. It adds no historical aggregate series, current-session claim, market/exchange/sector scope, request, dependency, backend, or schema.
   * Phase 4.12E-1-R2A runtime acceptance completed with outcome B. The normal launcher reached HTTP readiness on port 8012 without a production repair; the prior no-listener result was traced to a probe-harness false negative. A direct five-symbol `/foreign-flow` browser run produced one bounded batch and no symbol-history request. SSI was locally unavailable as `network_error`, and the desktop/mobile UI preserved all requested rows while rendering null summaries, five unavailable breadth members, and explicit insufficient-data treemap/bar/concentration states. Presentation controls did not refetch. Positive SSI visualization evidence remains pending a network-available run.
6. **Phase 4.12E-2 - VN30 aggregate (implemented; runtime acceptance pending):** `GET /api/v1/stocks/vn/foreign-flow/vn30` resolves exact SSI IndexComponents membership, reuses cached DailyStockPrice symbol history with concurrency four, and returns a common maximum-20-date series, aligned latest/5/20 value and volume totals, separate coverage/breadth, component summaries, rankings, aggregate cache/single-flight metadata, and sanitized counters. `/foreign-flow?scope=vn30` owns one request and renders summary, history modes, breadth, concentration, treemap, bars, and scanner without frontend fan-out. Signed net values use green for positive, red for negative, neutral styling for zero, and unavailable styling for null/non-finite data across the chart, summaries, rankings, and scanner. Historical totals use current membership and remain `historical_constituent_correct=false`. Deterministic validation passed; two bounded launcher attempts exited before HTTP readiness, so runtime proof is deferred to Phase 4.12E-2B.
7. **Phase 4.12F - HOSE scale hardening (gate blocked):** Phase 4.12F-A returned outcome E because 736 exact SSI Securities rows lacked normalized type. Phase 4.12F-A1 then returned outcome F after the first deterministic SecuritiesDetails request produced no exact HOSE row. Phase 4.12F-A2 proved the installed SDK's four query keys and empty page defaults, added bounded provider-derived candidate and response-shape diagnostics, and issued one bounded live command; however, its sanitized terminal result was not retained, so A2 also remains outcome F and no direct provider/fetcher conclusion is claimed. No type-bearing Details row, broader classification, DailyStockPrice call, aggregate, or frontend scope exists. HOSE remains unavailable; a future follow-up may repeat only one narrowly captured exact-symbol probe.
8. **Phase 4.12E-3 - Symbol analytics (implemented deterministically):** the existing symbol endpoint adds null-aware value/volume analytics over at most 60 accepted provider rows. `/foreign-flow` requests that history only after the explicit detail action, then renders local 5/20/60 summaries, streak/reversal/comparison/extrema cards, net/buy-sell/cumulative/rolling charts, and a sortable history table without refetching for presentation changes. Optional runtime smoke was skipped; E-2 runtime acceptance remains deferred.
9. **Phase 4.13A - Price, liquidity, and foreign-flow context (future):** requires explicit ownership, denominator, and interpretation gates; no price/flow join exists yet.
10. **Phase 4.13B - Foreign-flow alerts (future):** requires finality, correction, cooldown, and dedup gates; no alert runtime exists yet.

The MVP is limited to summary, top buyers/sellers, watchlist table, and symbol detail. Sector aggregation is P1 and requires authoritative classification coverage. Historical constituent-correct VN30, negotiated-order splits, advanced anomaly analysis, export/reports, ownership analysis, and alerts are later work.
