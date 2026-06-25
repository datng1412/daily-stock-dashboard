# Vietnam Dashboard Data Contract

## Purpose

This document defines the public data contract for the VN dashboard and company research page. It is intentionally data-quality-first: valid daily SSI data should remain visible even when optional live or enrichment sections are unavailable.

## Status Enum

Public section statuses should use:

```text
ok
unavailable
disabled
```

Use `ok` only when the section has usable data for its purpose. Use `unavailable` when the source is enabled but no usable data is available. Use `disabled` when the section is intentionally off.

Technical sub-statuses, provider codes, HTTP status, retryability, and endpoint attempts belong in diagnostics.

Profile completeness labels such as `partial` are data-quality classifications, not provider status enum values. Provider/live-section statuses should remain `ok`, `unavailable`, or `disabled`.

Future modules that are already exposed in placeholder API sections may use `not_implemented` until Phase 2 normalizes or removes those sections. Do not use `not_implemented` for live provider probes that were attempted; those remain `unavailable` when enabled but no usable data exists.

## Missing Data Rules

Use these rules consistently across backend responses and frontend rendering:

* Missing object data: `null`.
* Missing list data: `[]`.
* Do not emit placeholder objects for unavailable sections.
* Do not create metric rows from unavailable sections.
* Do not show `-` or `Unavailable` as if it were a metric value.
* Keep diagnostics separate from primary metric fields.

## Daily Data Contract

Daily data is the primary public contract for the VN dashboard.

Required daily fields when the watchlist row is usable:

* `latest_price`: sourced from SSI DailyOhlc close while the DailyOhlc versus DailyStockPrice mismatch is unresolved.
* `latest_price_source`: identifies the source as SSI DailyOhlc or equivalent SSI daily source label.
* OHLCV fields: `open`, `high`, `low`, `close`, `daily_close`, `ohlcv_close`, `volume`, and value/amount fields when SSI provides them.
* Price date fields: `latest_price_date`, `ohlcv_date`, or the current normalized daily trading date.
* Source fields: `source`, `actual_source`, `fallback_used`, and block-specific source labels.
* Finality fields: `final_close_status` or equivalent final/provisional/unknown field when available.

Daily finality must stay explicit:

* `final` means the system has a defensible final-close signal.
* `provisional` or `in_progress` means the daily candle may still change.
* `unknown` means the dashboard has no reliable finality signal.

If daily SSI data is unavailable, the row should expose an unavailable status and null daily metrics rather than borrowing live, intraday, or legacy-provider values.

Company detail aligns shared canonical daily fields with the watchlist row: `latest_price`, `daily_close`, daily OHLCV open/high/low/close/volume, and daily trading value use SSI DailyOhlc fields. In the company price block, `price.source` and `price.canonical_source` identify `SSI DailyOhlc`; `price.reference_source` identifies `SSI DailyStockPrice` for reference, ceiling, and floor fields. Company foreign-flow, matched, put-through, and adjusted-close fields remain SSI DailyStockPrice-specific and must be labeled as such when shown.

## Data Quality Summary Contract

Watchlist rows and company detail responses expose `data_quality_summary` as a Phase 1 summary layer. This field is additive and must not change canonical price behavior.

Required rules:

* `canonical_price_source` remains `SSI DailyOhlc` while the DailyOhlc versus DailyStockPrice decision is unresolved.
* `overall_status` uses `ok`, `partial`, or `unavailable` for summary quality only.
* `issues` contains short user-safe messages and source-labeled fields.
* `issues` must not contain endpoint names, HTTP status, attempted endpoints, raw provider errors, credentials, tokens, account IDs, or raw auth responses.
* `checks` records section quality for daily OHLCV, DailyStockPrice, final close, adjusted price, intraday, realtime, trade tape, profile, and news.
* Optional live-section unavailable states may make the summary `partial`, but they must not make valid daily SSI data unavailable.

## Live Section Contract

This is the Phase 2 public contract. Missing live objects and lists must not be represented by placeholder objects or fake metric rows.

### Intraday

When SSI IntradayOhlc is usable:

```text
intraday_status.status = ok
intraday_source = SSI IntradayOhlc
intraday_candles = [ ... ]
intraday_pulse = { ... }
```

When intraday is unavailable, stale, disabled, or date-mismatched:

```text
intraday_status.status = unavailable or disabled
intraday_source = SSI IntradayOhlc
intraday_candles = []
intraday_pulse = null
```

Stale latest-date metadata and date-match details should move to `intraday_status` or diagnostics when there is no usable intraday section.

The company endpoint follows the same missing-object rule. When nested company `intraday.status = unavailable`, `intraday.candles = []` and `intraday.pulse = null`.

### Realtime Snapshot

When SSI realtime snapshot is usable:

```text
realtime_status.status = ok
realtime_snapshot = { ... }
```

When no usable SSI realtime snapshot exists:

```text
realtime_status.status = unavailable or disabled
realtime_snapshot = null
```

The primary UI should not render snapshot price, snapshot time, change, or session-volume metric rows when `realtime_snapshot` is `null`.

### Trade Tape

When SSI trade tape has usable rows:

```text
trade_tape_status.status = ok
trade_tape = [ ... ]
```

When no trade rows exist:

```text
trade_tape_status.status = unavailable or disabled
trade_tape = []
```

The watchlist public contract is a list for `trade_tape`. Company detail keeps a nested `trade_tape.trades` list because the company page groups block status and rows together.

### Diagnostics

Diagnostics may include:

* Attempted endpoint names.
* Last endpoint.
* HTTP status.
* Provider status code.
* Retryable flag.
* Stale-date details.
* Row counts.
* Normalized keys.
* Realtime failure mode such as `rest_unsupported`, `streaming_adapter_not_implemented`, `streaming_no_message`, or `streaming_parsed_rows`.
* Sanitized provider error summaries.

Watchlist live-section status objects may include a nested `diagnostics` object for sanitized provider details that were previously embedded in public messages. The public `message` field must remain short and user-safe.

Diagnostics must not include:

* SSI credentials.
* Tokens.
* Auth headers.
* Account IDs.
* Raw auth responses.
* Full raw provider payloads.

## News Contract

News is disabled until a separate VN news provider is implemented.

Current public shape:

```text
news = []
news_status.status = disabled
news_status.source = disabled
```

News disabled state must not be treated as a daily market-data failure. Mozyfin is not a VN runtime news fallback.

## Future Module Contract

Future enrichment modules such as financials, corporate actions, events, ownership, and richer profile details may appear as placeholder sections while implementation is pending. If they are exposed before implementation, their status may be:

```text
not_implemented
```

Rules:

* `not_implemented` means no provider integration exists yet.
* `disabled` means the feature exists but is intentionally off.
* `unavailable` means the feature is enabled or attempted but no usable data was returned.
* Placeholder future sections must use `null` for missing objects and `[]` for missing lists.
* Future-module placeholders must not be rendered as provider failures or daily-data failures.

## Source Ownership

| Data block | Owner | Public rule |
| --- | --- | --- |
| Daily OHLCV | SSI DailyOhlc | Canonical daily close and chart candles |
| `latest_price` | SSI DailyOhlc | Uses DailyOhlc close until canonical-source mismatch is resolved |
| Reference/ceiling/floor | SSI DailyStockPrice | Use when available |
| Matched volume/value | SSI DailyStockPrice | Use when available |
| Put-through volume/value | SSI DailyStockPrice | Use when available |
| Latest foreign flow | SSI DailyStockPrice | Use latest matched-date row when available |
| Foreign 5D/20D flow | Future enhancement | Compute only from matched-date historical DailyStockPrice rows |
| Index list | SSI IndexList | Use SSI-returned index codes |
| Index components | SSI IndexComponents | Use only when SSI returns rows |
| Symbol metadata | SSI Securities/SecuritiesDetails | Optional fields may remain null |
| Intraday candles | SSI IntradayOhlc | Strict source; no fallback |
| Realtime snapshot | SSI FastConnect streaming realtime contract | Parser covered for buffered `X`, `X-QUOTE`, and `X-TRADE`; live streaming adapter not implemented |
| Trade tape | SSI trade-tape contract | Contract exists; live list/history semantics not confirmed |
| News | Future NewsProvider | Disabled now |
| Financials | Future external provider | Not implemented |
| Corporate actions | Future external provider | Not implemented; no inference |
| Mozyfin | Disabled for VN runtime | No fallback |
| KBS | Legacy optional only | Disabled by default |

Compatibility aliases must stay within the same source owner. Do not use SSI DailyStockPrice close to overwrite `latest_price`, do not use DailyOhlc volume to fill matched volume, and do not use realtime, trade-tape, Mozyfin, or KBS values to fill daily fields.

## UI Rendering Rules

### Daily Data

Render daily data when the row has valid SSI DailyOhlc fields and daily status is OK. Optional section failures should not hide daily close, chart, or DailyStockPrice fields.

The dashboard top summary `Foreign net volume` aggregates `ssi_foreign_net_volume` from the latest successful complete watchlist response and labels the unit as shares. It must not aggregate legacy `foreign_net` fallbacks, incomplete refresh rows, auxiliary realtime/trade/index/corporate-action responses, or mix volume with `ssi_foreign_net_value` in VND.

Daily volume labels should identify SSI DailyOhlc ownership, for example `Daily OHLCV volume`. Active realtime and trade-tape controls should use `Realtime snapshot`, `SSI realtime`, or `Trade tape`; KBS and Mozyfin names are allowed only in legacy diagnostics or superseded historical docs.

### Optional Live Metrics

Render optional live metrics only when actual data exists:

* Intraday metrics require `intraday_status.status = ok`, non-empty `intraday_candles`, and non-null `intraday_pulse`.
* Realtime metrics require `realtime_status.status = ok` and non-null `realtime_snapshot`.
* Trade tape requires `trade_tape_status.status = ok` and non-empty `trade_tape`.

Otherwise render concise states:

```text
SSI intraday unavailable.
SSI realtime unavailable. Daily SSI data is still available.
SSI trade tape unavailable.
```

### Diagnostics Panel

The diagnostics/data-quality panel may show endpoint details, HTTP status, retryability, and stale-date metadata. Primary cards should not show raw endpoint attempts or provider error text.

### Units Metadata

Units metadata does not prove data availability. UI availability must depend on status plus null/empty checks.

### Cache Errors

Cache errors and provider unavailable states are separate concepts. A provider 404 or unavailable live endpoint should not be shown as a daily SSI cache failure.

## Recently Completed Contract Cleanup

* Phase 2.1 completed: unavailable watchlist `trade_tape` is `[]`, status stays in `trade_tape_status`, and sanitized provider details move to status diagnostics instead of public messages.
* Phase 2.1 completed: unavailable company `intraday.pulse` is `null`, not `{}`.
* Phase 2.2 completed: frontend rendering treats unavailable live objects as `null`, missing watchlist trade tape as `[]`, company trade rows as `trade_tape.trades = []`, and status diagnostics as diagnostics-only UI content.

## Known Contract TODOs

### P0

* Phase 1: investigate SSI DailyOhlc vs DailyStockPrice same-date mismatch. Latest smoke observed FPT on `2026-06-22` with DailyOhlc/dashboard close fields at `70,700`, DailyStockPrice close/adjusted close at `70,800`, DailyOhlc volume at `3,642,400`, and DailyStockPrice matched volume at `3,643,500`.
### P1

* Phase 2: deprecate top-level `intraday_timeframe`.
* Phase 2: move stale intraday latest-date/date-match metadata into status/diagnostics when no usable intraday data exists.
* Phase 2 and Phase 4.0: add backoff or longer TTL for non-retryable SSI realtime/trade-tape 404 responses.

### P2

* Future selected-ticker/source-coverage work: improve SSI metadata mapping for company name, issuer, security type, lot size, listed shares, listed date, and industry if available.
* Future DailyStockPrice history or caching work: add historical SSI DailyStockPrice foreign-flow support if available.
* Phase 1 and Phase 2: clean quote metadata semantics when quote is disabled or unreliable.
* Phase 1: improve `final_close_status` using VN session/calendar rules.

### P3

* Phase 2 and Phase 6.0: clarify cache errors versus provider unavailable.
* Phase 2: clarify units metadata versus data availability.
