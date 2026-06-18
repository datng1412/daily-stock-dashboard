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

SSI FastConnect is the strict official market-data provider for supported Vietnam REST market data.

Mozyfin and KBS must not be removed immediately, but they no longer act as fallback for SSI-owned REST data. Mozyfin remains for news and unsupported domains. KBS remains for realtime snapshot and trade tape until SSI streaming is implemented and validated. Dashboard source labels must remain honest and explicit.

### Provider capability matrix

| Capability | Owner | Current implementation status | Dashboard rule |
| --- | --- | --- | --- |
| AccessToken | SSI FastConnect Data REST | Implemented provider auth foundation | Environment credentials only; never expose tokens |
| Securities | SSI FastConnect Data REST | Implemented provider method | Use for symbol metadata when wired |
| SecuritiesDetails | SSI FastConnect Data REST | Implemented provider method | Use for exchange, type, listed info, and names when wired |
| IndexComponents | SSI FastConnect Data REST | SSI-owned future provider method | Use for index membership/watchlist generation after validation |
| IndexList | SSI FastConnect Data REST | Implemented provider method | Discover official index identifiers before DailyIndex calls |
| DailyOhlc | SSI FastConnect Data REST | Implemented and wired for daily data/chart | Primary daily close, OHLCV, chart, and internal indicators |
| IntradayOhlc | SSI FastConnect Data REST | SSI-owned later phase | Migrate intraday pulse after endpoint validation |
| DailyIndex | SSI FastConnect Data REST | Implemented provider method with 29-day chunking | Use for index value, change, breadth, and liquidity when wired |
| DailyStockPrice | SSI FastConnect Data REST | Implemented and wired for selected-ticker enrichment | Use for reference, ceiling/floor, adjusted close, matched, put-through, and foreign flow |
| Realtime best bid/ask | SSI streaming later | Not implemented | KBS remains temporary realtime source |
| Realtime matched data | SSI streaming later | Not implemented | KBS trade tape remains separate |
| Realtime foreign room | SSI streaming later | Not implemented | Show unavailable until SSI streaming is stable |
| Realtime index stream | SSI streaming later | Not implemented | Keep daily index separate from realtime blocks |
| Realtime bars/OHLC | SSI streaming later | Not implemented | Do not treat KBS snapshot as official daily OHLCV |
| News | External provider | Mozyfin remains active | Keep separate from SSI-owned market data |
| Financial statements and ratios | External provider | Unsupported/future provider | Do not infer fundamentals from price data |
| Corporate actions, dividends, rights, splits | External provider | Stub/unavailable | Do not infer events from reference/adjusted-price gaps |
| Macro/Fed/oil/USD/gold | External provider | Unsupported/future provider | Keep outside SSI market-data ownership |

Decision rule:

```text
If data is official market price/volume/index/symbol and SSI has endpoint: use SSI.
If data is derived indicator from price/volume: calculate internally from SSI.
If data is realtime and SSI streaming is not ready: use KBS, label clearly.
If data is news/fundamentals/corporate actions/macro: use external provider.
If SSI-owned data is unavailable: show unavailable, do not silently fallback.
```

| Area | Preferred future provider | Current/fallback provider | Notes |
| --- | --- | --- | --- |
| Daily OHLCV | SSI DailyOhlc | None | Unavailable if SSI is unavailable |
| Inspect chart | SSI DailyOhlc | None | Indicators remain calculated internally |
| Daily stock price | SSI DailyStockPrice | None | Use for reference, ceiling/floor, foreign flow |
| Reference / ceiling / floor | SSI DailyStockPrice | None | Do not infer corporate actions |
| Foreign flow | SSI DailyStockPrice | None | Unavailable if SSI is unavailable |
| Daily index | SSI DailyIndex | None | Use for VNINDEX/VN30 snapshot and breadth |
| Index components | SSI IndexComponents | Static/manual fallback | Use for VN30/watchlist generation |
| Symbol metadata | SSI Securities/SecuritiesDetails | Existing metadata fallback | Use for exchange/type/company name |
| Intraday OHLCV | SSI IntradayOhlc later | Existing intraday implementation until migrated | Use for intraday pulse later |
| Realtime snapshot | SSI streaming later | KBS | KBS remains until SSI streaming is stable |
| Trade tape | SSI streaming later | KBS | Do not remove KBS yet |
| News | Mozyfin | Other future news provider | SSI FC Data does not currently own news in roadmap |
| Corporate actions | Future explicit event source | Stub/unavailable | Do not infer from price/reference gaps |
| Fundamentals/TA | Mozyfin or future source | Internal calculations | Use whichever source is validated |

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

## Next priorities

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
* Larger chart overlay using the existing loaded Mozyfin daily OHLCV chart points.
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

## SSI FastConnect integration track

1. Provider skeleton and secure config.
2. Auth/connection smoke test.
3. DailyOhlc strict provider selection.
4. DailyStockPrice mapping and strict enrichment.
5. DailyIndex backend preparation and market breadth.
6. Securities metadata and index components.
7. IntradayOhlc for intraday pulse.
8. SSI streaming prototype.
9. Realtime transition away from KBS only after SSI streaming is stable.
10. Keep Mozyfin news and unsupported domains explicit.
11. Apply SSI migration rules before each new SSI-owned area.

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

Frontend changes:

```powershell
cd apps\dsa-web
npm.cmd test -- VietnamDashboardPage.test.tsx
npm.cmd run build
cd ..\..
git diff --check
```

Backend changes:

```powershell
python -m py_compile <changed_python_files>
python -m pytest <relevant_tests> -q
git diff --check
```

Manual dashboard check:

1. Open `/vietnam`.
2. Confirm selected ticker loads.
3. Confirm SSI daily close remains separate from KBS snapshot.
4. Confirm chart works.
5. Confirm news shows relative time.
6. Confirm KBS unavailable path is clean.
7. Confirm diagnostics do not dominate the page.
8. Confirm no buy/sell/hold/recommendation wording appears.

## Recommended implementation order

1. Commit current stable fixes.
2. Add this roadmap file.
3. Improve visual hierarchy and reduce clutter.
4. Improve selected ticker header.
5. Collapse debug/observability sections.
6. Add zoom/pan/reset to chart.
7. Add fullscreen chart mode.
8. Add SSI FastConnect provider skeleton and comparison layer.
9. Group news.
10. Add watchlist table view.
11. Improve mobile layout.
12. Revisit corporate actions source.
