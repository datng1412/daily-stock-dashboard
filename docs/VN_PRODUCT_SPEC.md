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
* Selected ticker header.
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

## MVP Scope

The current MVP is:

* Strict SSI DailyOhlc for daily watchlist data and chart candles.
* SSI DailyStockPrice for reference, ceiling/floor, matched, put-through, and latest foreign-flow fields.
* SSI symbol metadata when available.
* SSI IndexList and IndexComponents diagnostics when available.
* SSI IntradayOhlc contract with freshness validation.
* SSI realtime and trade-tape contracts with explicit unavailable states when live rows are not confirmed.
* Company research page shell using the same source-aware market-data contract.
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

### M1 - SSI Daily MVP Freeze

Freeze current daily data semantics around SSI DailyOhlc as canonical `latest_price` until the DailyOhlc versus DailyStockPrice mismatch is resolved.

### M2 - Data-Quality Panel

Move provider diagnostics, endpoint attempts, HTTP status, stale-date metadata, retryability, and raw provider error summaries into a dedicated diagnostics panel.

### M3 - Company Research Page Expansion

Expand the company page with richer SSI metadata, clearer source coverage, and future external provider blocks for financials and events.

### M4 - SSI Realtime/Trade-Tape Investigation

Confirm SSI realtime and trade-tape endpoint names, permissions, row shapes, retry behavior, and final public contract. Keep unavailable states explicit until confirmed.

### M5 - News Provider

Implement a separate news provider contract. Mozyfin remains disabled for VN runtime.

### M6 - Financials/Corporate Actions

Add external provider coverage for financial statements, ratios, dividends, rights, splits, and corporate action event history. Do not infer these from price gaps.
