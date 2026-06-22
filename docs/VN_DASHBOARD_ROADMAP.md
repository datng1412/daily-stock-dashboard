# VN Dashboard Roadmap

## Purpose

The Vietnam dashboard is a source-aware stock inspection workspace. It should help users inspect price, volume, news, realtime board state, and data freshness without turning the UI into trading advice.

The dashboard must remain:

* Data-focused
* Inspect-only
* Source-aware
* Clear about stale or unavailable data
* Neutral in wording

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
* No buy/sell/hold/recommendation wording.
* Use neutral labels such as status, trend, momentum, liquidity, source, unavailable, last updated.

## Provider strategy

This roadmap is the source of truth for Vietnam dashboard provider ownership. SSI FastConnect Data is the strict official market-data source for supported Vietnam market data, including realtime snapshot and trade-tape contracts where SSI endpoints are available. Mozyfin is disabled for VN dashboard runtime because the free tier no longer supports the news/social API paths the dashboard previously used. KBS is disabled by default and is legacy-only behind explicit development flags.

### Current provider ownership

| Capability or data domain | Owner | Current implementation state | Dashboard rule |
| --- | --- | --- | --- |
| Securities | SSI FastConnect Data REST | Implemented and wired as same-provider metadata fallback | Use for symbol metadata |
| SecuritiesDetails | SSI FastConnect Data REST | Implemented and wired | Use for exchange, security type, listed info, issuer/name, lot size, listed shares, and listed date if available |
| IndexList | SSI FastConnect Data REST | Implemented and exposed through backend API | Discover official index identifiers instead of hardcoded assumptions |
| IndexComponents | SSI FastConnect Data REST | Provider, service, and API coverage added; live availability needs SSI endpoint/permission confirmation | Use for index membership and VN30 diagnostics only when SSI returns rows |
| DailyOhlc | SSI FastConnect Data REST | Implemented and wired for daily data/chart | Use for daily OHLCV, chart candles, and internal indicators |
| IntradayOhlc | SSI FastConnect Data REST | Implemented and wired for watchlist/company intraday pulse | Use for compact intraday candles; keep separate from daily close and SSI realtime |
| DailyStockPrice | SSI FastConnect Data REST | Implemented and wired for selected-ticker enrichment | Use for reference, ceiling/floor, adjusted close if provided, matched volume/value, put-through volume/value, and foreign buy/sell/net volume/value |
| DailyIndex | SSI FastConnect Data REST | Implemented provider method with chunking; dashboard consumption is next | Use for daily index value, change, breadth, and liquidity |
| Realtime snapshot | SSI FastConnect Data/streaming | Provider, service, API, and UI contract added; live endpoint names/permissions need confirmation | Keep separate from daily close and official daily OHLCV |
| Trade tape | SSI FastConnect Data/streaming | Provider, service, API, and UI contract added; live endpoint names/permissions need confirmation | Keep separate from official daily OHLCV |
| Legacy realtime snapshot/trade tape | KBS | Disabled by default; only available behind explicit legacy flags | Do not silently fallback from SSI to KBS |
| News | Future NewsProvider | Disabled/not implemented | Do not call Mozyfin; return explicit disabled/not_implemented state |
| Unsupported fundamentals | External provider required | Not implemented | Keep explicitly labeled; do not mix with SSI market-data fields |
| BCTC/KQKD, financial statements, financial ratios | External provider required | Not implemented | Investigate separately |
| Corporate actions, dividends, rights, splits | External provider required | Stub/unavailable | Events must come from explicit source data |
| Macro/Fed/oil/USD/gold | External provider required | Not implemented | Keep outside SSI market-data ownership |

SSI should be used for symbol metadata, exchange/security type/listed info when available, index list/components, daily OHLCV, chart candles, internal indicators from SSI OHLCV, reference/ceiling/floor, adjusted close if provided, matched volume/value, put-through volume/value, foreign buy/sell/net volume/value, daily index value/change/breadth/liquidity, intraday OHLCV, realtime snapshot, and trade tape.

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
* IndexComponents is exposed through `/api/v1/stocks/vn/index-components?index_code=...`, but the current local SSI environment returned a clean unavailable state for `VN30`; do not hardcode components or fallback to another provider.
* SSI IntradayOhlc is implemented for the watchlist/company intraday pulse through the same SSI auth/cache path. If SSI returns no candles or the endpoint is disabled, expose a clean SSI `disabled`/`unavailable` intraday status and keep daily rows OK.
* `/api/v1/stocks/vn/chart` should be SSI-backed and should return SSI source metadata.
* `/api/v1/stocks/vn/watchlist` must remain SSI-backed for SSI-owned fields, including daily close, reference, ceiling/floor, matched value, put-through value, foreign flow, and source metadata.
* `/api/v1/stocks/vn/company/{ticker}` is a Phase 1 company research contract/page shell that reuses the SSI-backed watchlist row for market-data blocks.
* Mozyfin fallback for SSI-owned fields is not allowed.
* SSI realtime snapshot and trade tape are exposed through the existing realtime endpoints and dashboard/company UI blocks.
* SSI realtime/trade-tape live endpoint names and entitlements may return unavailable. Unavailable states should include sanitized attempted-endpoint diagnostics without tokens, credentials, auth headers, or raw provider bodies.
* Dashboard provider-status UI must keep core daily SSI availability separate from optional SSI realtime, SSI trade tape, SSI index components, and disabled news states. A `Partial` dashboard status can mean optional sections are unavailable; it must not imply daily SSI data failed when daily rows are OK.
* KBS legacy realtime/trade-tape paths are disabled by default and require explicit legacy flags.
* News/social are disabled/not implemented until a separate NewsProvider is added.
* Local DB market-data storage is deferred; current mode is SSI live API plus backend cache/TTL.

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

Live IndexComponents validation for `VN30`, with and without `market=HOSE`, returned a clean unavailable SSI state in the current environment. This may be endpoint permission, endpoint path, SSI data availability, or undocumented parameter shape. Do not hardcode VN30 components and do not use Mozyfin/KBS fallback for SSI-owned index membership. Keep the UI and diagnostics tolerant of unavailable component rows.

Audit blocker fixed before Phase 3 commit: SSI `IndexComponents` provider error/status payloads must parse case-insensitive fields such as `code`, `errorCode`, `status`, and `Status` into a clean SSI unavailable response. They must not raise backend 500s from parser helper errors.

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

Live Phase 3 smoke found SSI IntradayOhlc can return an older latest candle date than SSI DailyOhlc, for example daily date `2026-06-19` with latest intraday candle date `2026-06-12`. The service must compare latest intraday candle date with latest daily trading date. If they differ, keep the daily SSI row `ok`, but mark intraday unavailable with a sanitized date-mismatch message and do not derive intraday pulse labels from stale candles.

The same smoke found the requested dashboard timeframe label may not describe actual returned candle cadence; returned timestamps can be minute-like. Treat intraday cadence as provider-returned and detect it from timestamps when possible. UI labels should use neutral names such as latest intraday close, intraday change, and session intraday volume instead of claiming a fixed candle interval.

Contract cleanup before Phase 3 commit: `intraday_requested_timeframe` is the SSI request hint, while `intraday_actual_granularity` and `intraday_actual_granularity_seconds` describe detected returned cadence. The compatibility `intraday_timeframe` field remains for existing clients but must not be presented as actual candle granularity.

### Final close / adjusted price status remains conservative

`final_close_status = unknown` and `adjusted_price_status = unknown` should remain conservative unless SSI provides explicit finality/adjustment metadata. Do not infer corporate actions from adjusted close/reference gaps. Do not mutate raw OHLCV close.

Observed live watchlist payload can also include `candle_status = unknown`, `price_adjustment_status = unknown`, and `corporate_action.status = unavailable`. Keep these conservative warnings until an explicit source provides finality, adjustment, or event metadata.

### Foreign rolling history is separate from latest SSI foreign flow

Observed live watchlist payload can include null rolling fields:

* `foreign_net_5d`
* `foreign_net_20d`
* `foreign_net_5d_latest_available`
* `foreign_net_20d_latest_available`

Latest matched-date foreign buy/sell/net volume/value can still be present and valid from SSI DailyStockPrice. Rolling 5D/20D foreign flow requires historical foreign-flow rows and should be handled as a separate enhancement if needed.

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

Observability cleanup before Phase 3 commit: the `mozyfin` block is minimal when disabled (`status`, `source`, `reason`). Generic VN request/cache/single-flight counters belong under `dashboard_runtime` so SSI runtime activity is not shown as Mozyfin activity. SSI health is split into `ssi_core`, `ssi_intraday`, `ssi_realtime`, and `ssi_trade_tape` so daily/intraday/realtime/tape availability can be read separately.

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
* KBS realtime snapshot
* KBS trade tape
* SSI DailyStockPrice reference/limit/foreign/matched detail block
* SSI IntradayOhlc intraday pulse
* Daily close / realtime snapshot / trade tape separation
* Phase-aware KBS snapshot state
* KBS unavailable/error normalization
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

The dashboard has many useful blocks, but the next improvements should focus on hierarchy and usability.

Current weak points:

* Main screen can feel cluttered.
* Selected ticker header is not strong enough.
* Debug/status information can dominate the view.
* Inspect chart still needs broker-style interactions.
* News needs better grouping and freshness context.
* Mobile layout needs chart-first prioritization.
* Watchlist view needs a denser table mode for comparison.

## Product and UI backlog

These items remain useful, but they are not the near-term SSI migration sequence. Use the `Near-term SSI implementation sequence` section for provider work order.

### 1. Improve dashboard visual hierarchy and reduce clutter

Status: partial in first roadmap batch.

Implemented so far:

* Added a compact Data status summary near the top.
* Moved selected ticker context and inspect chart ahead of secondary comparison cards.
* Moved provider/cache/debug details behind collapsed diagnostics.

Goal:

Make the dashboard easier to scan before adding more data features.

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

Status: partial in first roadmap batch.

Implemented so far:

* Added a compact selected ticker header.
* Shows symbol/company label, Daily close, SSI realtime, Vs SSI reference, Session volume, 20D avg volume, Latest news, and SSI source badges.
* Keeps SSI daily, SSI DailyStockPrice, SSI intraday, and SSI realtime labels visually separate.

Goal:

Make the selected ticker context obvious.

Suggested header content:

* Symbol and company name
* SSI daily close
* SSI realtime snapshot price
* Price vs SSI reference
* Session volume
* 20D average volume
* News freshness
* Data source badges

Example:

```text
ACB — Asia Commercial Bank
Daily close: 22.65
SSI realtime: 22.65
Price vs SSI reference: -0.88%
Volume: 14.64M / 20D avg 31.43M
Sources: SSI daily · SSI realtime
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
* Daily OHLCV and KBS snapshot separation remains visible in expanded mode.
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
* Added a table-level scan-state column derived from existing status labels, cache freshness, and KBS snapshot state.
* Kept normal warnings as secondary table context so warning-only rows do not dominate the scan summary.
* Separated source/data caveats such as foreign-date mismatch, indicator-input caution, unconfirmed final close, and unknown adjusted-price metadata from primary market scan labels.
* Kept caveats visible in compact row disclosures because existing response fields identify the limitations but do not provide enough confirmed source metadata to resolve them automatically.
* Kept scan states ticker-level because the current watchlist payload does not include a sector field.

Goal:

Allow faster comparison across tickers.

Suggested columns:

* Symbol
* Daily close
* KBS snapshot
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
* Added company name, exchange, market, security type, issuer, lot size, listed shares, and listed date when SSI returns them.
* Added compact selected-ticker metadata display.
* Missing metadata fields remain unavailable/null; Mozyfin is not used for SSI-owned symbol metadata.

### Priority 2 - SSI IndexList/IndexComponents

Status: provider, service, API, and mocked parser coverage added in the current working tree.

* Added SSI-only index list coverage through `/api/v1/stocks/vn/index-list`.
* Added SSI-only index component coverage through `/api/v1/stocks/vn/index-components?index_code=...`.
* Added compact dashboard diagnostics for SSI index coverage so IndexList and VN30 component availability are visible.
* Avoid hardcoded index assumptions; use SSI-returned index codes from IndexList.
* Live IndexList works in the current SSI environment.
* Live IndexComponents for `VN30` currently returns clean unavailable; verify SSI endpoint permission/path/parameter shape before relying on component rows.

### Phase 1 - Vietnam Company Research Terminal shell

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

### Phase 3 - SSI realtime snapshot and trade tape

Status: provider, service, API, and UI contract added in the current working tree.

* Added SSI FastConnect realtime snapshot and trade-tape provider methods using existing SSI auth, cache, timeout, and secret-safe error handling.
* Wired `/api/v1/stocks/vn/realtime` and `/api/v1/stocks/vn/realtime/trades` to SSI by default.
* Added watchlist and company research fields for `realtime_snapshot`, `realtime_status`, `trade_tape`, and `trade_tape_status`.
* Updated dashboard/company UI labels to show SSI realtime and SSI trade tape, with neutral unavailable states when SSI returns no usable rows.
* Disabled KBS by default; KBS is legacy-only behind `VN_ALLOW_LEGACY_KBS_PROVIDER=true` and `KBS_ENABLED=true`.
* Live SSI realtime/trade-tape endpoint names, permissions, and row shapes still require validation in an environment with the relevant SSI data entitlements.

### Priority 4 - SSI streaming/protocol hardening

* Build a standalone streaming client.
* Support safe subscriptions for market data, foreign room, index data, and realtime bars.
* Add heartbeat, reconnect, and cache behavior.
* Compare live SSI stream/probe behavior against dashboard REST expectations.
* Keep unavailable states explicit until SSI realtime/trade-tape endpoints are proven stable.

### Priority 5 - External fundamentals, corporate actions, and news

* Investigate an external BCTC/KQKD provider.
* Investigate a corporate actions source.
* Investigate a separate NewsProvider; do not rely on Mozyfin free-tier news/social APIs.

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
* Confirm no buy/sell/hold/recommendation wording appears.
* Confirm no Mozyfin fallback exists for SSI-owned market data.
* Confirm KBS is disabled by default and only available behind explicit legacy diagnostics flags.
* Confirm VN news is disabled/not_implemented until a separate NewsProvider exists, and unsupported domains remain separate from SSI market data.
