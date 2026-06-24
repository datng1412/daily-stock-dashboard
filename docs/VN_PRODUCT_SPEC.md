# Vietnam Dashboard Product Spec

## Product Goal

The Vietnam dashboard is a data-quality-first market inspection workspace for VN tickers. It helps users inspect official daily market data, source coverage, freshness, and unavailable provider states without turning the product into a trading-decision tool.

This is not an AI stock advisor. It does not provide buy, sell, hold, target-price, portfolio, or order-placement recommendations. The product is a market-data quality dashboard.

The product should answer:

* What is the current official daily market-data state for this ticker?
* Which source provided each block?
* Which fields are present, stale, disabled, or unavailable?
* Which optional live or enrichment sections are safe to display?
* Which provider limitations still need investigation?

## Non-Goals

The Vietnam dashboard must not:

* Provide buy, sell, hold, target-price, trading-instruction, valuation-call, portfolio-action, or account-action guidance.
* Use FC Trading, order, account, cash, or stock-transfer APIs.
* Hide source uncertainty behind blended fallback values.
* Use Mozyfin as a VN runtime fallback.
* Use KBS as a normal VN runtime fallback.
* Present unavailable live data as placeholder metrics.
* Infer corporate actions, finality, or adjustment events from price gaps.

## Primary User

The primary user is a retail investor or operator who wants a clear, source-aware view of VN ticker data quality before doing deeper manual research.

The user needs fast scanning, but the dashboard should prefer correctness and source clarity over dense but ambiguous live metrics.

## Core Screens

### VN Market Dashboard

Purpose:

* Show watchlist-level daily market data from SSI.
* Keep the selected ticker and chart central.
* Surface DailyStockPrice fields when SSI provides them.
* Keep optional intraday, realtime, trade-tape, index, and news states separate from daily row validity.

Required first-order blocks:

* Watchlist table/cards.
* Preset scan buckets for VN30, sectors, and common market groups.
* Sortable indicator table as the primary watchlist scan surface.
* Compact selected ticker summary.
* SSI DailyOhlc chart.
* SSI DailyStockPrice quick facts.
* Source and freshness summary.
* Compact unavailable states for optional sections.

### Company Research Page

Purpose:

* Provide a ticker-level research shell using the same SSI-backed market-data contract.
* Show source coverage for profile, price, trading stats, foreign flow, technical snapshot, news, financials, and events.
* Keep not-implemented domains explicit.

Current scope:

* SSI-backed market-data blocks.
* News, financials, and events as disabled or not-implemented placeholders.
* No scraping, no FC Trading, and no inferred events.

### Diagnostics/Data-Quality Panel

Purpose:

* Keep technical provider details available without making them primary UI metrics.
* Explain why optional sections are unavailable.
* Preserve enough information for debugging endpoint behavior, cache state, and source freshness.

Allowed details:

* Attempted endpoint names.
* HTTP status.
* Retryability.
* Stale-date diagnostics.
* Cache timing.
* Provider row counts and normalized key coverage.

Forbidden details:

* SSI credentials.
* Tokens.
* Auth headers.
* Account IDs.
* Raw auth responses.
* Full raw provider payloads.

## UX Principles

### Daily Data First

Daily SSI data is the primary dashboard surface. If SSI DailyOhlc is valid, the row can remain OK even when optional intraday, realtime, trade-tape, index-component, metadata, or news sections are unavailable.

### Source Transparency

Every block should make source ownership clear:

* Daily close and chart: SSI DailyOhlc.
* Reference, limits, matched, put-through, and latest foreign flow: SSI DailyStockPrice.
* Intraday candles: SSI IntradayOhlc.
* Realtime snapshot: SSI realtime contract.
* Trade tape: SSI trade-tape contract.
* News: disabled until a separate provider exists.
* Financials and corporate actions: future external providers.

### No Fake Realtime

Do not label daily close, intraday candles, or stale snapshots as realtime matched prices. Realtime snapshot and trade tape are separate contracts and must not overwrite official daily close.

### Missing Data As State

Unavailable optional sections should render a concise section-level state, not metric rows with placeholder values.

Examples:

```text
SSI intraday unavailable.
SSI realtime unavailable. Daily SSI data is still available.
SSI trade tape unavailable.
News disabled.
```

### Diagnostics Separate From Primary UI

Primary UI should show concise source/status copy. Endpoint attempts, HTTP status, retryability, stale-date details, and provider error summaries belong in diagnostics/logs.

### Scan First, Detail Second

On `/vietnam`, the indicator table should sit above the selected ticker detail so users can scan the watchlist first, then inspect the selected ticker. The selected ticker area should remain a compact summary, while diagnostics, index coverage, and deeper per-ticker detail stay lower on the page.

## Progressive Data Workspace Direction

`/vietnam` should become a progressive, source-aware market inspection workspace. It should not display all fields with equal priority. The dashboard should follow this order:

1. Primary scan layer.
2. Selected ticker explanation layer.
3. Optional live layer.
4. Diagnostics layer.
5. Future external data layer.

Core principle:

```text
Daily scan first.
Ticker explanation second.
Live/diagnostics third.
External/future data last.
```

The primary scan layer should answer what the current daily SSI state is across the active watchlist. The selected ticker explanation layer should explain why the selected ticker looks that way. Optional live, diagnostics, and future external data should remain available, but they must not crowd out the daily scan or imply that unavailable optional sections invalidate valid daily SSI data.

## Data Priority Model

### Tier 1 - Core Scan Data

Primary table/watchlist scan fields:

* Ticker.
* Daily close.
* Percent change.
* RSI14.
* MA state.
* Volume / 20D average.
* Foreign net volume.
* Data quality.
* Live status.

Source ownership:

* Daily close, OHLCV, and chart: SSI DailyOhlc.
* Foreign net volume: SSI DailyStockPrice.
* Indicators: derived from SSI DailyOhlc.

### Tier 2 - Selected Ticker Explanation

Selected ticker fields should explain the scan result without expanding into a full debug board:

* Daily close.
* Reference price.
* Ceiling / floor.
* Volume / 20D average.
* Matched volume.
* Foreign buy/sell/net.
* Chart.
* Compact Data Quality Summary.

### Tier 3 - Optional Live Layer

Optional live fields:

* Realtime snapshot.
* Trade tape.
* Intraday pulse.
* Index coverage.

Rules:

* Optional live data must never block the daily scan.
* Optional live failure should show a compact unavailable state.
* Diagnostics remain available but lower priority.

### Tier 4 - Future External Data

Future external domains:

* News.
* Financials.
* Corporate actions.
* Dividends.
* Macro.

Rules:

* These require separate provider contracts.
* Do not mix them into SSI market data.
* Do not infer corporate actions from price gaps.

## MVP Scope

The current MVP is:

* Strict SSI DailyOhlc for daily watchlist data and chart candles.
* SSI DailyStockPrice for reference, ceiling/floor, matched, put-through, and latest foreign-flow fields.
* SSI symbol metadata when available.
* SSI IndexList and IndexComponents diagnostics when available.
* SSI IntradayOhlc contract with freshness validation.
* SSI realtime and trade-tape contracts with explicit unavailable states when live rows are not confirmed.
* Company research page shell using the same source-aware market-data contract.
* Frontend-only watchlist preset groups for VN30, Banks, Securities, Real estate, Consumer, Logistics, Tech, Oil & gas, and Electricity.
* Local-only custom watchlist input using browser localStorage; no server sync.
* News disabled until a separate provider is implemented.

## Current Limitations

Current known limitations are part of the product surface and should be visible in concise unavailable states or diagnostics:

* SSI DailyOhlc and DailyStockPrice can disagree on the same ticker/date; `latest_price` currently remains SSI DailyOhlc close until canonical source and final/provisional semantics are resolved.
* `final_close_status` can be `unknown` because SSI finality metadata and VN session/calendar rules are not fully wired.
* SSI IntradayOhlc can be stale or mismatched against the daily trading date, so `intraday_pulse` should be `null` and `intraday_candles` should be `[]` when no usable current intraday data exists.
* SSI realtime snapshot and trade tape are not confirmed live in the latest smoke; endpoint candidates can return unavailable or 404.
* Trade tape may still need contract cleanup from a placeholder wrapper object to `trade_tape = []` when unavailable.
* Symbol metadata can be partial; optional company name, issuer, lot size, listed shares, listed date, and security type may remain null.
* Foreign-flow rolling windows can be unavailable when SSI DailyStockPrice history is insufficient.
* News is disabled until a separate provider is implemented.

## Future Milestones

The full implementation roadmap is tracked in `docs/VN_DASHBOARD_ROADMAP.md`. Product milestones are summarized here so the spec stays aligned with the end-to-end plan.

### Phase 0 - SSI Provider Milestone Freeze

Freeze the SSI-provider migration milestone: SSI daily data is primary, Mozyfin is disabled for VN runtime, KBS is legacy optional only, news is disabled, and unavailable live sections use `null` or `[]` instead of fake metrics.

### Phase 1 - Data Quality Summary

Turn source mismatch, finality uncertainty, stale intraday, unavailable live data, and partial metadata into visible neutral warnings on the dashboard selected ticker and company detail.

### Phase 2 - Clean Public Contract and Diagnostics Split

Normalize unavailable public data to `intraday_pulse = null`, `intraday_candles = []`, `realtime_snapshot = null`, and `trade_tape = []`; keep endpoint attempts, HTTP status, raw provider errors, retryability, and stale-date details in diagnostics.

### Phase 3 - Progressive Dashboard Workspace

Phase 3.0A implemented a frontend-only watchlist preset-group pass before the company detail redesign. Preset groups are scan buckets only: switching a preset changes the requested ticker list, keeps the selected ticker when it remains in the group, otherwise selects the first ticker, and does not add provider calls, polling, or data-source changes.

Phase 3.0B added a local Custom preset workflow. Users can apply, save, and clear a comma/whitespace/semicolon/newline-separated ticker list stored under `vnDashboard.customWatchlist.v1` in browser localStorage. Invalid or empty custom input does not replace the active watchlist. The feature is local-only and does not add backend storage, server sync, or new endpoints.

Phase 3.1 polished the `/vietnam` indicator table into the main daily scan surface. The table prioritizes ticker, SSI DailyOhlc daily close, change percent, RSI14, MA state, daily volume versus 20D average, SSI DailyStockPrice foreign net volume, data quality, and realtime/live status. Sorting is client-side only and does not trigger watchlist reloads or change data-source semantics.

Phase 3.2A adds a compact `/vietnam` Data Readiness strip near the top of the dashboard. The strip is visual/status-only and derives its states from already loaded frontend response data and live-section status objects. It does not add backend fields, endpoints, provider calls, polling, request orchestration, or refresh-preservation behavior.

Phase 3.2B adds lightweight explanations to the Data Readiness strip so each item has factual source/status context. The explanations are frontend-only, derive from the same already loaded response/status data, and do not add backend fields, endpoints, provider calls, polling, request orchestration, or refresh-preservation behavior.

Phase 3.2C keeps the previous successful `/vietnam` watchlist visible while a refresh, preset switch, reset, or custom apply request is in flight. It adds frontend request-state UX only: `Updating...` and `Last update failed` copy, local stale-response protection for rapid list changes, and commit-on-success behavior for preset/custom list changes. It does not add backend fields, endpoints, provider calls, polling, or public contract changes. Request-level failures preserve the prior committed rows/list/preset, while successful responses that include unavailable ticker rows still commit and use existing row-level unavailable states.

Phase 3.2D adds section-level loading and unavailable state cleanup across existing `/vietnam` sections. It keeps the daily scan primary, makes optional intraday/realtime/trade-tape/news unavailable states visually minor, keeps diagnostics lower priority, and preserves the Phase 3.2C previous-data refresh behavior. It does not add backend fields, endpoints, provider calls, polling, or public contract changes.

Phase 3.3A organizes the `/vietnam` selected ticker detail into progressive disclosure groups without adding data or changing API behavior. The compact selected ticker header keeps daily close, change percent, volume versus 20D average, foreign net volume, RSI/MA state, live status, and compact Data Quality Summary visible. Secondary detail moves into Price context, Flow context, Technical context, Live context, Source coverage, News context, and Diagnostics groups. Price context is open by default; live, source, news, and diagnostics remain lower priority. Raw fields, cache internals, and rule inputs stay in Diagnostics.

Phase 3.3B polishes selected ticker field copy and density without adding data, endpoints, provider calls, fetch paths, or contract fields. It shortens repeated labels, reduces duplicate visible source wording, keeps source coverage available at section level, uses neutral inspect-only copy, keeps optional live/news states calm, and keeps raw fields/cache/rule inputs inside Diagnostics.

Next Phase 3 work continues the progressive workspace direction: selected ticker disclosure polish, request-state orchestration cleanup, local filtering, and chart UX polish. The company detail page remains part of the same source-aware explanation layer, not a separate advisor experience.

### Phase 4.0 - SSI Realtime and Trade Tape Investigation

Confirm whether available SSI FastConnect Data endpoints and entitlements can provide usable realtime snapshot and trade tape. Do not claim live support until `realtime_snapshot` is non-null and status is `ok`.

### Phase 4.1 - Intraday Cadence Clarity

Detect actual returned intraday cadence, avoid overclaiming a fixed interval unless verified, and label stale or unavailable intraday clearly.

### Phase 5.0 - External Provider Architecture

Define NewsProvider, FundamentalsProvider, CorporateActionsProvider, and MacroProvider as separate contracts. Keep them separate from SSI market data.

### Phase 5.1 - NewsProvider

Add sourced watchlist/company news when a provider is selected. Until then, keep `news = []` and `news_status.status = disabled`.

### Phase 5.2 - Corporate Actions and Dividends

Add verified event data only. Do not infer dividends or corporate actions from price gaps.

### Phase 6.0 - Backend Performance and Caching

Improve backend cache, durable storage, or background jobs only when rate limits or latency justify the added complexity.

### Phase 7.0 - Product Packaging

Clean runbooks, startup scripts, smoke/test/release checklists, and deprecated docs so the VN dashboard can be operated consistently.

## Use Now

This is near-term architecture guidance for future implementation tasks, not code work in this documentation update.

* React local state.
* `useMemo` for sorted/filtered rows.
* `useRef` request IDs for stale response protection.
* `localStorage` for browser-only preferences.
* Section-level status objects.
* Existing backend TTL cache.
* Smoke script per milestone.

## Use Later

Use these only when the trigger condition is met, documented, and implemented in a separate future task:

* TanStack Query or SWR-style query manager if async state becomes too complex.
* Table virtualization if watchlist size grows above 100+ rows.
* Backend DB if SSI rate limits or latency become real.
* Separate provider modules for news, fundamentals, events, and macro data.
* Background jobs only after provider contracts stabilize.
* Realtime streaming only after the SSI realtime contract is verified.

## Avoid For Now

Avoid these until their trigger condition is met, documented, and handled in a separate task:

* WebSocket before SSI realtime contract is verified.
* Table virtualization for 10-30 tickers.
* Backend database before rate-limit or latency pressure is real.
* One giant endpoint that returns everything.
* One global loading spinner.
* Raw provider errors in primary UI.
* Mixing DailyOhlc, DailyStockPrice, realtime, and trade-tape values.
* AI buy/sell/hold recommendation labels.
* Mozyfin/KBS fallback.
* Fake realtime or stale snapshots labeled as live.
* Inferred dividends or corporate actions.
