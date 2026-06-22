# VN Data Quality TODOs

## Purpose

This document tracks data-quality and contract work for the SSI-first Vietnam dashboard. The dashboard should remain a market-data quality surface: daily SSI data first, optional live sections only when real data exists, and diagnostics separated from primary UI fields.

## Phase Mapping

The product phase plan lives in `docs/VN_DASHBOARD_ROADMAP.md`. Data-quality TODOs map to that plan as follows:

| Priority | Main phase | Notes |
| --- | --- | --- |
| P0 - contract/data correctness | Phase 1 and Phase 2 | Surface mismatches in Data Quality Summary, then clean public contracts and diagnostics split. |
| P1 - live-section semantics | Phase 2 and Phase 4 | Clean stale/unavailable API shape first; investigate SSI realtime/trade-tape endpoints after contract cleanup. |
| P2 - enrichment | Phase 5, with finality work started in Phase 1 | Improve metadata and foreign-flow history after the public data-quality summary exists. |
| P3 - cleanup | Phase 2 and Phase 8 | Clarify cache/provider states now; revisit durable cache semantics if persistence is added. |

## P0 - Contract/Data Correctness

### Investigate SSI DailyOhlc vs DailyStockPrice Mismatch

Latest smoke context for FPT on `2026-06-22`:

* Dashboard `latest_price`, `ohlcv_close`, and `daily_close` from SSI DailyOhlc: `70,700`.
* SSI DailyStockPrice `close` and `adjusted_close`: `70,800`.
* SSI DailyOhlc `volume`: `3,642,400`.
* SSI DailyStockPrice `matched_volume`: `3,643,500`.

Current canonical dashboard rule:

* `latest_price` uses SSI DailyOhlc close until the mismatch is investigated.
* DailyStockPrice supplies reference, ceiling/floor, matched/put-through, and latest foreign-flow fields.

TODO:

* Confirm whether the mismatch is caused by provisional/final timing, cache windows, endpoint semantics, or field meaning.
* Decide whether DailyOhlc close or DailyStockPrice close should own canonical latest daily price after finality semantics are understood.
* Define `final_close_status` values and when they can be assigned.

### Normalize Unavailable Trade Tape Contract

Current issue:

* Responses may still expose `trade_tape` as a placeholder object containing `trades: []`.

Desired public contract:

```text
trade_tape = []
trade_tape_status.status = unavailable
trade_tape_status.source = SSI
```

TODO:

* Keep status/source/message in `trade_tape_status`.
* Move attempted endpoint, HTTP status, retryability, and raw provider error summary to `diagnostics.trade_tape`.
* Do not render placeholder trade metric rows when `trade_tape` is empty.

### Split Public Live-Section Status From Diagnostics

Current issue:

* `realtime_status.message` and `trade_tape_status.message` can contain endpoint attempts, HTTP status, and raw provider error details.

Desired public contract:

* Public `status.message` is short and user-safe.
* `diagnostics.realtime` and `diagnostics.trade_tape` hold attempted endpoints, last endpoint, HTTP status, raw provider error summary, and retryable flag.

## P1 - Live-Section Semantics

### Deprecate Top-Level Intraday Timeframe

Use:

* `intraday_requested_timeframe` for the request hint.
* `intraday_actual_granularity` for detected provider-returned cadence.

Do not treat compatibility `intraday_timeframe` as a guaranteed candle interval.

### Move Stale Intraday Details Into Status/Diagnostics

Latest smoke context:

* `intraday_status = unavailable`.
* `intraday_candles = []`.
* `intraday_pulse = null`.
* `intraday_latest_date = 2026-06-15`.
* `daily_price_date = 2026-06-22`.
* `date_match = mismatched`.

TODO:

* Keep stale intraday out of primary metric rows.
* Put latest intraday date, daily price date, and date-match details in status or diagnostics when no usable intraday data exists.

### Add Backoff For Non-Retryable SSI Live 404s

Latest smoke context:

* `realtime_snapshot = null`.
* `realtime_status = unavailable`.
* SSI realtime endpoint candidates returned unavailable or 404.
* Trade-tape endpoint candidates also returned unavailable or 404.

TODO:

* Mark known non-retryable endpoint failures with `retryable=false`.
* Add longer TTL/backoff for non-retryable realtime/trade-tape 404 responses.
* Avoid repeated endpoint probes that cannot currently produce user-visible live data.

## P2 - Enrichment

### Improve SSI Securities/SecuritiesDetails Metadata Mapping

Current issue:

* Symbol metadata still has many null optional fields.

Fields to improve when SSI provides them:

* `company_name`
* `name`
* `issuer`
* `lot_size`
* `listed_shares`
* `listed_date`
* `security_type`

Optional null metadata is not fatal. The UI should hide optional metadata rows when absent.

### Add SSI DailyStockPrice Foreign-Flow History If Available

Current issue:

* `foreign_net_5d` and `foreign_net_20d` are null because current available foreign-flow history is insufficient.

TODO:

* Fetch enough matched-date DailyStockPrice history if SSI supports it.
* Compute rolling foreign-flow windows only from aligned historical rows.
* Expose an insufficient-history state rather than implying zero flow.

### Clean Quote Metadata Semantics

Current issue:

* Quote metadata can exist while quote price fields are disabled, null, or unreliable.

TODO:

* Keep quote metadata separate from price-source availability.
* Do not use quote metadata as proof of realtime price availability.

### Improve Final Close Status

Current issue:

* `final_close_status` is currently unknown.

TODO:

* Use VN session and calendar rules where possible.
* Keep status conservative when SSI does not confirm finality.
* Do not infer finality from daily close alone.

### Corporate Actions

Current rule:

* Corporate actions remain unavailable until an explicit structured source exists.
* Do not infer dividends, rights, splits, or adjustment events from price/reference gaps.

## P3 - Cleanup

### Clarify Cache Errors vs Provider Unavailable

Provider unavailable, provider 404, and cache errors are separate states:

* Cache errors should not imply SSI DailyOhlc failed unless the daily cache actually failed.
* Optional live-section unavailable states should not make the daily row unavailable.

### Clarify Units Metadata vs Data Availability

Units metadata can describe fields that are not currently populated.

UI availability must depend on:

* Section status.
* Object null checks.
* List empty checks.

Units metadata must not be treated as data availability.
