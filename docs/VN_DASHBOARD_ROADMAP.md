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
* KBS snapshot is realtime board state only.
* KBS trade tape is separate from daily OHLCV.
* Do not replace daily close with KBS snapshot.
* Do not use KBS trade tape as official daily close.
* KBS reference price is a comparison base only.
* Do not label KBS reference price as dividend-adjusted unless a corporate action source confirms it.
* Do not infer corporate actions from price/reference gaps.
* Do not mutate raw OHLCV close for dividends.
* Corporate actions must come from an explicit event/history source.
* No buy/sell/hold/recommendation wording.
* Use neutral labels such as status, trend, momentum, liquidity, source, unavailable, last updated.

## Provider strategy

This roadmap is the source of truth for Vietnam dashboard provider ownership. SSI FastConnect Data is the strict official market-data source for supported Vietnam REST market data. Mozyfin and KBS remain in the product only for domains they still own; they must not silently replace SSI-owned data.

### Current provider ownership

| Capability or data domain | Owner | Current implementation state | Dashboard rule |
| --- | --- | --- | --- |
| Securities | SSI FastConnect Data REST | Implemented and wired as same-provider metadata fallback | Use for symbol metadata |
| SecuritiesDetails | SSI FastConnect Data REST | Implemented and wired | Use for exchange, security type, listed info, issuer/name, lot size, listed shares, and listed date if available |
| IndexList | SSI FastConnect Data REST | Provider method exists | Discover official index identifiers instead of hardcoded assumptions |
| IndexComponents | SSI FastConnect Data REST | SSI-owned next phase | Use for index membership and VN30 diagnostics after validation |
| DailyOhlc | SSI FastConnect Data REST | Implemented and wired for daily data/chart | Use for daily OHLCV, chart candles, and internal indicators |
| IntradayOhlc | SSI FastConnect Data REST | Later phase | Add as separate intraday chart mode; do not confuse it with official daily close |
| DailyStockPrice | SSI FastConnect Data REST | Implemented and wired for selected-ticker enrichment | Use for reference, ceiling/floor, adjusted close if provided, matched volume/value, put-through volume/value, and foreign buy/sell/net volume/value |
| DailyIndex | SSI FastConnect Data REST | Implemented provider method with chunking; dashboard consumption is next | Use for daily index value, change, breadth, and liquidity |
| Streaming market data | SSI streaming later | Not implemented | Use for realtime market data only after standalone validation and stability checks |
| Realtime snapshot | KBS | Active temporary realtime layer | Keep separate from daily close and SSI REST data |
| Trade tape | KBS | Active temporary realtime layer | Keep separate from official daily OHLCV |
| News | Mozyfin | Active | Keep separate from SSI-owned market data |
| Unsupported fundamentals | Mozyfin or another external provider | Only if no SSI/public provider exists | Keep explicitly labeled; do not mix with SSI market-data fields |
| BCTC/KQKD, financial statements, financial ratios | External provider required | Not implemented | Investigate separately |
| Corporate actions, dividends, rights, splits | External provider required | Stub/unavailable | Events must come from explicit source data |
| Macro/Fed/oil/USD/gold | External provider required | Not implemented | Keep outside SSI market-data ownership |

SSI should be used for symbol metadata, exchange/security type/listed info when available, index list/components, daily OHLCV, chart candles, internal indicators from SSI OHLCV, reference/ceiling/floor, adjusted close if provided, matched volume/value, put-through volume/value, foreign buy/sell/net volume/value, daily index value/change/breadth/liquidity, intraday OHLCV later, and realtime streaming later.

Mozyfin owns news, unsupported external domains only, and possible fundamentals only if no SSI or public provider exists. It is not an OHLCV, chart, reference, foreign-flow, index, or SSI-owned fallback provider.

KBS owns realtime snapshot and trade tape as a temporary realtime layer until SSI streaming is implemented and stable. It is not a daily close, reference, index, chart, or daily market-data fallback provider.

### Strict source rules

```text
If data is official market price/volume/index/symbol and SSI has an endpoint, use SSI.
If data is a technical indicator from price/volume, calculate internally from SSI data.
If data is realtime and SSI streaming is not ready, use KBS and label it clearly.
If data is news/fundamentals/corporate actions/macro, use an external provider.
If SSI-owned data is unavailable, show unavailable. Do not silently fallback.
```

### Current known implementation state

* SSI AccessToken works when local SSI credentials are configured.
* DailyOhlc works for the direct 1Y query used by the chart path.
* DailyStockPrice works but requires 29-day provider-level chunking because SSI rejects broad ranges.
* DailyIndex works but requires 29-day provider-level chunking because SSI rejects broad ranges.
* `/api/v1/stocks/vn/chart` should be SSI-backed and should return SSI source metadata.
* `/api/v1/stocks/vn/watchlist` must remain SSI-backed for SSI-owned fields, including daily close, reference, ceiling/floor, matched value, put-through value, foreign flow, and source metadata.
* Mozyfin fallback for SSI-owned fields is not allowed.
* KBS remains separate for realtime snapshot and trade tape.
* Mozyfin remains separate for news and unsupported external domains.
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

### Quote fields are intentionally missing in strict SSI daily mode

Observed live watchlist payload can include:

* `quote_cache = missing`
* `quote = null`
* `quote_price_date = null`
* `quote_price_raw_field = null`

This is not fatal because the current design uses SSI DailyOhlc close for `latest_price`. Keep the warning that quote does not provide a reliable latest price and latest price uses SSI DailyOhlc close. Future realtime/quote work should come from KBS snapshot now or SSI streaming later, not a forced REST quote fallback.

### Row-level status must not mix optional source caveats with SSI daily validity

Confirmed UI issue after strict SSI migration: rows could show valid SSI DailyOhlc close/date/volume, valid SSI DailyStockPrice reference/foreign/matched fields, and valid KBS snapshot values while the scan badge still showed `Data unavailable` or `Data source error`.

Root cause: the frontend primary scan state was using broad validation/cache/KBS state. Optional quote cache, limited metadata, unavailable corporate actions, final/adjusted unknown statuses, temporary Mozyfin intraday, news cache, or KBS snapshot context could be elevated into a row-level data error.

Fixed status taxonomy:

* Row-level `Data unavailable` is reserved for missing/invalid required SSI DailyOhlc fields, explicit row unavailable state, row error, or SSI DailyOhlc cache error.
* Quote missing, limited metadata, unavailable corporate actions, final/adjusted unknown statuses, temporary Mozyfin intraday, news/cache issues, and KBS snapshot issues remain caveats or separate source states.
* Cache labels shown in the primary watchlist/table should refer to SSI DailyOhlc. Broader source refresh/cache details belong in diagnostics.
* Source labels should stay explicit: daily close/chart = `SSI DailyOhlc`, reference/limits/foreign/matched/put-through = `SSI DailyStockPrice`, realtime snapshot/trade tape = `KBS`, intraday = `Mozyfin OHLCV` until SSI IntradayOhlc is implemented.

### Mozyfin news text encoding issue

News title/summary may contain mojibake or broken Vietnamese text, for example `Khá»i ngoáº¡i`, `Cá» phiáº¿u`, or `VN-Index giÃ nh`. This is not an SSI market-data issue. Keep news source separate from SSI. Future work should normalize/decode Vietnamese news text before rendering.

### Intraday remains Mozyfin temporarily

Current `intraday_source` can still be `Mozyfin OHLCV`. This is expected until the SSI IntradayOhlc priority is implemented. The UI must clearly label intraday data as not a realtime quote and not the official SSI daily close. Do not mix intraday candle data with official daily close.

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

SSI-owned market data must not silently fallback to Mozyfin/KBS. Mozyfin is news/unsupported domains only. KBS is realtime snapshot/trade tape only.

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
* Shows symbol/company label, Daily close, KBS snapshot, Vs SSI reference, Session volume, 20D avg volume, Latest news, and SSI/KBS source badges.
* Keeps SSI daily and KBS realtime labels visually separate.

Goal:

Make the selected ticker context obvious.

Suggested header content:

* Symbol and company name
* SSI daily close
* KBS snapshot price
* Price vs SSI reference
* Session volume
* 20D average volume
* News freshness
* Data source badges

Example:

```text
ACB — Asia Commercial Bank
Daily close: 22.65
KBS snapshot: 22.65
Price vs SSI reference: -0.88%
Volume: 14.64M / 20D avg 31.43M
Sources: SSI daily · KBS realtime
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
* Preserved Mozyfin news and KBS realtime/trade tape behavior.

Goal:

Use SSI FastConnect as the strict owner for supported VN REST market data while keeping unsupported domains explicit.

Scope:

* Provider skeleton and secure configuration placeholders.
* Authentication and connection smoke tests.
* Clean unavailable states when SSI-owned data is unavailable.
* Explicit source labels for SSI, Mozyfin, and KBS values.

Rules:

* SSI-owned data must not fall back to Mozyfin or KBS.
* `latest_price` uses SSI DailyOhlc close when SSI daily rows are available.
* Do not remove Mozyfin news or KBS realtime/trade tape paths.
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
* Confirm news remains Mozyfin.
* Confirm KBS realtime snapshot and trade tape remain separate.
* Run a secret scan before committing.
* Commit the current SSI phase after validation.

### Priority 1 - SSI Securities/SecuritiesDetails metadata

Status: implemented in the current working tree.

* Added SSI-only symbol metadata coverage through `SecuritiesDetails`, with `Securities` as a same-provider metadata fallback.
* Added company name, exchange, market, security type, issuer, lot size, listed shares, and listed date when SSI returns them.
* Added compact selected-ticker metadata display.
* Missing metadata fields remain unavailable/null; Mozyfin is not used for SSI-owned symbol metadata.

### Priority 2 - SSI IndexList/IndexComponents

* Add index list and component coverage.
* Avoid hardcoded index assumptions.
* Use SSI-returned index codes.
* Prepare VN30 component display and diagnostics.

### Priority 3 - IntradayOhlc

* Add SSI intraday OHLCV as a separate chart mode.
* Keep rate-limit and cache protection.
* Do not confuse intraday data with official daily close.

### Priority 4 - SSI streaming prototype

* Build a standalone streaming client.
* Support safe subscriptions for market data, foreign room, index data, and realtime bars.
* Add heartbeat, reconnect, and cache behavior.
* Compare with KBS.
* Switch realtime only after SSI streaming is stable.

### Priority 5 - External fundamentals, corporate actions, and news

* Investigate an external BCTC/KQKD provider.
* Investigate a corporate actions source.
* Keep Mozyfin news if it remains useful.

### Deferred - Local DB market-data store

Local DB market-data storage is deferred because current dashboard call volume is low and backend cache/TTL is sufficient for the present SSI live API mode. Revisit a DB-backed store if SSI rate limits, repeated full-range fetches, UI latency, or historical replay requirements become a practical problem.

## SSI migration rules

* SSI credential access remains disabled by default until config is present, but supported VN REST provider selection defaults to SSI.
* Never commit SSI credentials.
* Never print tokens, private keys, account IDs, or secrets.
* Add `.env.example` placeholders only.
* Do not add FC Trading or account/order/cash/stock-transfer actions.
* Do not use Mozyfin or KBS fallback for SSI-owned REST data.
* If SSI-owned data is unavailable, return unavailable.
* Do not remove Mozyfin news.
* Do not remove KBS realtime until SSI streaming is stable.
* Keep source labels explicit: `SSI`, `Mozyfin`, `KBS`.

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
7. Confirm KBS snapshot and trade tape remain separate realtime blocks.
8. Confirm Mozyfin news remains separate.
9. Confirm diagnostics do not dominate the page.

Guardrail checks:

* Run `git diff --check`.
* Run a secret scan before commit.
* Confirm no SSI credentials, tokens, auth headers, consumer IDs, consumer secrets, private keys, account IDs, or raw auth responses appear in docs, tests, fixtures, logs, or output.
* Confirm no FC Trading, order placement, account actions, cash transfer, stock transfer, or portfolio trading actions were added.
* Confirm no buy/sell/hold/recommendation wording appears.
* Confirm no Mozyfin fallback exists for SSI-owned market data.
* Confirm KBS is only realtime snapshot and trade tape.
* Confirm news and unsupported domains remain separate from SSI market data.
