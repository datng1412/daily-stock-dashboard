# Vietnam Dashboard Data Contract

## Purpose

This document defines the public data contract for the VN dashboard and company research page. It is intentionally data-quality-first: valid daily SSI data should remain visible even when optional live or enrichment sections are unavailable.

## Completed-session 1-minute chart history (Phase 4.11C)

`GET /api/v1/stocks/vn/intraday-chart?ticker=FPT&interval=1m&date=YYYY-MM-DD` returns one completed or current Vietnam date from SSI `IntradayOhlc`. Only `1m` is accepted; dates after the current `Asia/Ho_Chi_Minh` date return the endpoint-specific 422 contract. `ready` contains usable sparse bars; a current date without usable bars is `unavailable`; `failed` means a nonempty response had no usable bars. Stale-if-error data remains `ready` and is disclosed by `cache.is_stale=true` plus `freshness=stale`.

Unsupported intervals are validated by this endpoint before SSI is called and return HTTP 422 with `error=vn_intraday_chart_invalid_request` and `message=Only interval=1m is supported`. Invalid current/future dates use the same error code with the completed-date message. The broader global request-validation copy does not own these intraday allowlist errors.

Provider `DD/MM/YYYY` plus `HH:MM:SS` values are interpreted in `Asia/Ho_Chi_Minh`, floored to minute start, and returned as Unix seconds. OHLC must be finite and positive, volume finite and non-negative, and invalid or wrong-date rows are rejected. If multiple rows normalize to one minute, the latest original provider timestamp wins; identical timestamps keep the last stable occurrence. Missing minutes remain gaps. D1 remains SSI `DailyOhlc`; current-session candles, higher intervals, aggregation, pagination beyond page 1, realtime candle substitution, and provider fallback are not supported.

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

If SSI DailyOhlc is unavailable but SSI DailyStockPrice returns usable enrichment, `latest_price`, `daily_close`, and OHLCV fields must remain null/unavailable. The row may still expose source-labeled DailyStockPrice fields such as reference, ceiling/floor, matched/put-through, and foreign-flow values. DailyStockPrice close must not become `latest_price`.

Company detail aligns shared canonical daily fields with the watchlist row: `latest_price`, `daily_close`, daily OHLCV open/high/low/close/volume, and daily trading value use SSI DailyOhlc fields. In the company price block, `price.source` and `price.canonical_source` identify `SSI DailyOhlc`; `price.reference_source` identifies `SSI DailyStockPrice` for reference, ceiling, and floor fields. Company foreign-flow, matched, put-through, and adjusted-close fields remain SSI DailyStockPrice-specific and must be labeled as such when shown.

## Stock Detail Metrics Availability

This matrix maps common stock-detail panel labels to the current repository contract. It documents only fields that already exist today; it does not authorize new API fields, parser mappings, computed metrics, or provider integrations.

Status values:

* `Available now`: already exposed by the current strict SSI runtime/API/schema/frontend data model when the source returns the field.
* `Present internally, not exposed`: normalized internally but not part of the current public contract.
* `SSI-derived implemented`: calculated internally from SSI-owned fields with null/coverage semantics.
* `SSI-derived later, not implemented`: can be derived from SSI-owned data, but the current code does not compute this exact metric.
* `Deferred pending methodology/semantics`: should not be treated as external-provider-required until SSI inputs, share-count semantics, or methodology are verified.
* `Not available / future provider required`: requires a future fundamentals, corporate-actions, or other external provider contract.
* `Ambiguous, needs provider confirmation`: a related field exists, but its semantics or population path are not confirmed enough to present under the screenshot label.

| UI label | Meaning | Current status | Current source | Current API/schema field | Notes / future work |
| --- | --- | --- | --- | --- | --- |
| Open | Daily/session open price | Available now | SSI DailyOhlc for canonical daily rows; SSI DailyStockPrice may also expose an enrichment `open` | Watchlist `open`; company `trading_stats.open`; chart `points[].open`; nested `daily_stock_price.open` when present | Treat as daily candle/session open, not realtime open, unless a future realtime-detail design explicitly uses realtime data. |
| Average | Average trading price | Ambiguous, needs provider confirmation | Optional SSI realtime schema placeholder only | `realtime_snapshot.average_price` / realtime quote `average_price` exists in schema/types but current provider mapping does not populate it | Do not show as available stock-detail data until SSI realtime payload semantics and mapping are verified. |
| Matched val | Matched trading value | Available now | SSI DailyStockPrice | `daily_stock_price.matched_value`; compatibility `ssi_matched_value` | Do not fill from DailyOhlc `amount`/`value`; source label must remain DailyStockPrice. |
| PT val | Put-through trading value | Available now | SSI DailyStockPrice | `daily_stock_price.put_through_value`; compatibility `ssi_put_through_value` | Null means SSI did not provide the field; zero remains a real provider value. |
| High 52W | 52-week high | SSI-derived implemented | SSI DailyOhlc high history | `indicators.high_52w`; company `technical.high_52w`; date `high_52w_date` | Uses the latest 252 returned DailyOhlc rows; null when fewer than 120 usable high/low rows are available. |
| Avg. vol. 3M | Three-month average volume | SSI-derived implemented | SSI DailyOhlc volume history | `indicators.avg_volume_3m`; company `technical.avg_volume_3m` | Uses up to 63 latest usable volume rows; `complete` at >=60, `partial` at >=30, null below 30. |
| Avg. vol. 10D | Ten-day average volume | SSI-derived implemented | SSI DailyOhlc volume history | `indicators.avg_volume_10d`; company `technical.avg_volume_10d` | Requires 10 usable volume rows; null below 10. |
| EPS (TTM) | Trailing-twelve-month earnings per share | Not available / future provider required | Future fundamentals provider | No current EPS field | Not implemented in SSI runtime; do not infer from price data. |
| P/E (TTM) | Price-to-earnings ratio | Not available / future provider required | Future fundamentals/ratios provider | No current P/E field | Do not compute from missing EPS. |
| P/B | Price-to-book ratio | Not available / future provider required | Future fundamentals/ratios provider | No current P/B field | Requires book-value/fundamentals source. |
| Beta | Market beta | Deferred pending methodology/semantics | SSI DailyOhlc plus verified SSI index data and documented beta methodology, or future source-labeled provider only if SSI cannot support it | No current beta field | Do not default to external provider; verify SSI index input and methodology first. |
| FR. buy vol | Foreign buy volume | Available now | SSI DailyStockPrice | `daily_stock_price.foreign_buy_volume`; `foreign.buy`; raw-field marker `foreign_buy_raw_field` | Unit is shares when quantity fields exist. |
| FR. sell vol | Foreign sell volume | Available now | SSI DailyStockPrice | `daily_stock_price.foreign_sell_volume`; `foreign.sell`; raw-field marker `foreign_sell_raw_field` | Unit is shares when quantity fields exist. |
| FR. room | Foreign ownership room/remaining room | Optional backend/API live context | SSI `R:{symbol}` streaming cache | Watchlist `foreign_room_source`, `foreign_room`, `foreign_room_status`, and `diagnostics.foreign_room` | Separate from DailyStockPrice daily foreign flow. Value-unit and approximate-value semantics remain `needs_semantics_proof` until live provider evidence confirms them. |
| PT vol | Put-through trading volume | Available now | SSI DailyStockPrice | `daily_stock_price.put_through_volume`; compatibility `ssi_put_through_volume` | Do not substitute DailyOhlc volume or matched volume. |
| Low 52W | 52-week low | SSI-derived implemented | SSI DailyOhlc low history | `indicators.low_52w`; company `technical.low_52w`; date `low_52w_date` | Uses the latest 252 returned DailyOhlc rows; null when fewer than 120 usable high/low rows are available. |
| Outs. qty | Outstanding quantity / share count | Ambiguous, needs provider confirmation | SSI SecuritiesDetails/Securities metadata when provider returns share-count fields | `symbol_metadata.listed_shares`; watchlist/company `listed_shares`; profile `listed_shares` | Exposed field is listed shares / provider share-count metadata. Do not label it as exact outstanding quantity until SSI semantics are confirmed. |
| Market cap | Equity market capitalization | Deferred pending methodology/semantics | SSI or verified external share-count semantics plus canonical price rule | No current market-cap field | Do not compute from `latest_price * listed_shares` until share-count basis and product behavior are verified. |
| Dividend ratio | Cash/stock dividend ratio | Not available / future provider required | Future CorporateActionsProvider | Future contract fields may include `cash_dividend_per_share` and `stock_dividend_ratio`, but default provider returns empty lists | Corporate actions are disabled/not configured by default and must not be inferred from price gaps. |
| Next div. date | Next dividend/ex-date/payment date | Not available / future provider required | Future CorporateActionsProvider | Future event fields may include `ex_date`, `record_date`, and `payment_date`, but no live provider exists | `events=[]` means no verified rows are available, not confirmed absence of dividends. |
| ROE | Return on equity | Not available / future provider required | Future fundamentals/financial statements provider | No current ROE field | Not implemented. |
| ROA | Return on assets | Not available / future provider required | Future fundamentals/financial statements provider | No current ROA field | Not implemented. |

## Data Quality Summary Contract

Watchlist rows and company detail responses expose `data_quality_summary` as a Phase 1 summary layer. This field is additive and must not change canonical price behavior.

Required rules:

* `canonical_price_source` remains `SSI DailyOhlc` while the DailyOhlc versus DailyStockPrice decision is unresolved.
* `overall_status` uses `ok`, `partial`, or `unavailable` for summary quality only.
* `issues` contains short user-safe messages and source-labeled fields.
* `issues` must not contain endpoint names, HTTP status, attempted endpoints, raw provider errors, credentials, tokens, account IDs, or raw auth responses.
* `checks` records section quality for daily OHLCV, DailyStockPrice, final close, adjusted price, intraday, realtime, order book, foreign room, trade tape, profile, and news.
* Optional live-section unavailable states may make the summary `partial`, but they must not make valid daily SSI data unavailable.

Watchlist responses may also expose additive request-completeness counters:

```text
requested_tickers_count = normalized unique ticker count requested by the watchlist path
returned_rows_count = number of rows returned in the response
missing_tickers = requested normalized tickers not represented by a row
```

The same counters may appear under `data_quality` for diagnostics. A complete response should include one row per normalized requested ticker. If a row is partial or unavailable, it should stay visible and explain why through `data_quality_summary.issues` rather than disappearing.

## SSI-Derived Metrics Contract

Phase 4.8A adds these additive fields under watchlist `indicators` and company `technical`. They are calculated internally and never change row status or canonical `latest_price`.

| Field | Formula / source | Null and coverage behavior |
| --- | --- | --- |
| `high_52w`, `low_52w` | Max high / min low from the latest 252 returned SSI DailyOhlc rows | `high_low_52w_coverage_status` is `complete` at >=240 usable high/low rows, `partial` at >=120, and `insufficient` below 120. A usable row requires a valid date plus positive numeric high and low. Values and dates are both null when insufficient. Dates are `high_52w_date` and `low_52w_date`. |
| `avg_volume_10d` | Average volume from the latest 10 usable SSI DailyOhlc volume rows | Requires 10 usable rows; otherwise null with `avg_volume_10d_coverage_status=insufficient`. A usable volume row is numeric and >=0. |
| `avg_volume_3m` | Average volume from up to the latest 63 usable SSI DailyOhlc volume rows | `avg_volume_3m_coverage_status` is `complete` at >=60 rows, `partial` at >=30, and `insufficient` below 30. Value is null when insufficient. A usable volume row is numeric and >=0. |
| `price_vs_reference_pct` | `(DailyOhlc close - DailyStockPrice reference_price) / reference_price * 100` | Requires positive DailyOhlc close and positive DailyStockPrice reference. Status is `ok`, `daily_close_unavailable`, or `reference_unavailable`. |
| `daily_range_pct` | `(DailyOhlc high - DailyOhlc low) / DailyOhlc close * 100` | Requires numeric DailyOhlc high/low, positive close, and high >= low. Status is `ok` or `insufficient`. |
| `short_term_zones` | Compact D1 support/resistance zones | Object with `status`, `reason_code`, `source`, `timeframe`, `lookback_sessions`, `support[]`, and `resistance[]`. Source is `derived from SSI DailyOhlc`; timeframe is `D1`; lookback is 60 valid unique sessions. Each public zone contains only numeric `lower` and `upper`. ATR14 Wilder/RMA plus two-before/two-after swing pivots define local zones. Zones crossing the latest daily close are excluded; support is nearest-first below, resistance nearest-first above, at most two each. Insufficient valid history or ATR returns `status=unavailable` and empty lists. The selected ticker's optional daily-chart overlay reuses these ranges as at most S1/S2/R1/R2 clipped bands without a new request or y-domain change. No provider call, realtime input, fallback, or `latest_price` change is allowed. |
| `ssi_derived_metrics_status`, `ssi_derived_metrics_source` | Aggregate source/status for the fields above | Source is `SSI DailyOhlc + SSI DailyStockPrice`; status is `ok`, `partial`, or `insufficient`. |

Reason codes used for row-level partial/missing explanations include:

* `daily_ohlcv_missing`
* `daily_stock_price_missing`
* `ta_insufficient_history`
* `rsi_missing`
* `ma_state_insufficient_data`
* `foreign_flow_missing`
* `metadata_partial` / `profile_partial`
* `realtime_ticker_not_bootstrapped`
* `realtime_config_disabled`
* `realtime_cache_empty`
* `realtime_cache_stale`
* `intraday_unavailable_no_rows`
* `provider_empty`
* `provider_error`

These codes describe data availability only. They must not synthesize values, hide rows, or change `latest_price`, which remains SSI DailyOhlc when daily rows are usable.

## Live Section Contract

### Persisted last-known streaming metadata

When the optional lifecycle snapshot is enabled, normalized restored live rows may add `snapshot_source="persisted"`, `snapshot_captured_at`, `snapshot_trading_date`, `snapshot_schema_version=1`, `is_stale=true`, and `cache_status="persisted_stale"`. These fields are additive diagnostics/freshness metadata only. They never make X current/live, never replace `latest_price` or DailyOhlc, and never change empty/null contracts when no persisted row exists. During active sessions the user-facing state is waiting for live SSI updates; after close it is last-known stale data.

This is the Phase 2 public contract. Missing live objects and lists must not be represented by placeholder objects or fake metric rows.

### Intraday

When SSI IntradayOhlc is usable:

```text
intraday_status.status = ok
intraday_status.reason_code = ok or cadence_mismatch
intraday_source = SSI IntradayOhlc
intraday_requested_timeframe = request hint, for example 1h
intraday_actual_granularity = detected provider-returned cadence, for example 1m or 1h
intraday_actual_granularity_seconds = detected cadence in seconds when regular
intraday_cadence_status = matched, different_from_requested, irregular, unknown, or unavailable
intraday_candles = [ ... ]
intraday_pulse = { ... }
```

When intraday is unavailable, stale, disabled, or date-mismatched:

```text
intraday_status.status = unavailable or disabled
intraday_status.reason_code = disabled, unavailable_no_rows, unavailable_date_mismatch, unavailable_rate_limited, unavailable_provider_error, unavailable_unknown, or unknown
intraday_source = SSI IntradayOhlc
intraday_cadence_status = unavailable or unknown
intraday_candles = []
intraday_pulse = null
```

Stale latest-date metadata, date-match details, and cadence diagnostics should move to `intraday_status` or diagnostics when there is no usable intraday section. `intraday_timeframe` is a compatibility request hint and must not be treated as the actual provider interval unless `intraday_cadence_status = matched`.

The company endpoint follows the same missing-object rule. When nested company `intraday.status = unavailable`, `intraday.candles = []` and `intraday.pulse = null`. Company `intraday.cadence_status` mirrors the watchlist cadence classification, and `intraday.diagnostics` may carry sanitized failure details such as `failure_class`, `endpoint`, `http_status`, and provider code.

### Realtime Snapshot

When SSI realtime snapshot is usable:

```text
realtime_status.status = ok
realtime_status.reason_code = cache_hit
realtime_snapshot = { ... }
```

When no usable SSI realtime snapshot exists:

```text
realtime_status.status = unavailable or disabled
realtime_status.reason_code = disabled, config_disabled, not_started, bootstrap_symbols_empty, ticker_not_bootstrapped, running_idle, cache_empty, cache_stale, connection_error, auth_or_entitlement_failure, network_or_tls_failure, rate_limited, or unknown
realtime_snapshot = null
```

`realtime_status.message` is short user-facing copy such as `SSI realtime unavailable.`, `SSI realtime cache miss.`, `SSI realtime manager disabled.`, or `SSI realtime stale.` Technical state is not embedded in this message. Sanitized provider/runtime details live under `diagnostics.realtime`.

The primary UI should not render snapshot price, snapshot time, change, or session-volume metric rows when `realtime_snapshot` is `null`.

SSI realtime is streaming-backed. The service may read from a background manager/cache only when `SSI_STREAMING_REALTIME_ENABLED=true`, lifecycle bootstrap symbols are configured, the manager is running, and the cache row is fresh. Request handlers must not open streams, stop streams, reconnect streams, or subscribe requested tickers dynamically. The lifecycle monitor may reconnect preserved bootstrap channels when a running stream becomes stale during active holiday-unaware Vietnam trading/auction windows; that recovery remains manager-owned and debounced. Outside active windows, missing or stale X/X-QUOTE/X-TRADE rows classify as market-closed/after-hours state and must not trigger reconnect solely because row counters stop advancing. When streaming runtime is disabled, bootstrap symbols are empty, config/package setup is incomplete, the manager is not started, cache is empty/stale, runtime is idle/stale/reconnecting/market-closed, or the manager is errored, the public object remains `null` and diagnostics carry the safe reason.

`GET /api/v1/stocks/vn/realtime` bypasses the generic VN response cache so each poll can reflect the latest process-local streaming cache. The streaming cache remains authoritative for freshness through optional fields such as `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, and `cache_ttl_seconds`. Frontend polling for this endpoint is separate from watchlist, company, chart, and trade-tape refresh. Unexpected realtime request errors should fail open as a normal optional unavailable realtime response, not as a daily dashboard failure.

`GET /api/v1/stocks/vn/realtime` also exposes compatible top-level `reason_code`, `classification`, and `status_message` fields. These fields classify the optional realtime state only; they must not replace `latest_price` and must not mark DailyOhlc or DailyStockPrice unavailable.

Sanitized realtime diagnostics may include `stream_health`, holiday-unaware `market_session` fields, `runtime_status`, `manager_state`, `bootstrap_status`, `channels`, `subscription_count`, `expected_subscription_count`, `bootstrap_symbols`, `bootstrap_rejected_symbols`, `messages_observed`, `parser_rows_observed`, per-context observed-row counters, `last_message_at`, `last_message_age_seconds`, `latest_error`, `last_error_at`, `idle_timeout_seconds`, `is_idle`, `idle_since`, `reconnect_enabled`, `reconnect_attempt_count`, `reconnect_count`, `last_reconnect_at`, `next_reconnect_at`, `reconnect_backoff_seconds`, `last_reconnect_reason`, and `last_reconnect_error`. `runtime_status=running_idle` or `stream_health=stale|reconnecting|failed|market_closed|idle_market_closed|after_hours_stale` is an optional realtime runtime state only; it must not mark DailyOhlc or DailyStockPrice unavailable.

### Trade Tape

When SSI trade tape has usable rows:

```text
trade_tape_status.status = ok
trade_tape_status.reason_code = buffered_rows_available, streaming_trade_tape_supported, or historical_trade_tape_supported
trade_tape = [ ... ]
```

Buffered SSI `X-TRADE:{symbol}` rows remain visible even when stream freshness is stale. In that case, diagnostics can still report `streaming_status=cache_stale`, `cache_status=stale`, `latest_trade_age_seconds`, `trade_tape_buffer_row_count`, and `trade_tape_returned_row_count`, but stale freshness is not a visibility gate because every trade row carries its own traded timestamp.

Usable trade rows expose the current matched-order fields:

* `timestamp` and `timestamp_display`
* `side` as `buy`, `sell`, or `null`
* `side_label` as `Buy`, `Sell`, or `null`
* `price`
* `volume`
* `change`
* `change_pct`
* `source`

`side` is normalized only from explicit SSI `X-TRADE` side/aggressor fields such as `Side`, `MatchType`, or `BuySell`. Observed SSI raw codes include `BU = buy` and `SD = sell`; legacy/localized explicit codes such as `B`, `BUY`, `MUA`, `1`, `S`, `SELL`, `BAN`, `BÁN`, and `2` remain supported. Unknown side values remain `null`, and the raw candidate is preserved in `side_if_available` for audit. The backend and UI must not infer Buy/Sell from SSI board price color or positive/negative `change`; a `sell` row can still have positive price-vs-reference change. `change` and `change_pct` are calculated from trade price versus positive SSI DailyStockPrice `reference_price`; they remain null when reference is missing or non-positive.

When no trade rows exist:

```text
trade_tape_status.status = unavailable or disabled
trade_tape_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, stream_cache_stale, latest_trade_stream_only, unavailable_no_rows, unavailable_provider_error, unavailable_unknown, not_implemented, or unknown
trade_tape = []
```

`trade_tape_status.message` is short user-facing copy such as `SSI trade tape unavailable.`, `SSI trade tape disabled.`, or `No SSI trade rows available.` Technical details are not embedded in this message.

The watchlist and company public contracts both use a list for `trade_tape`; company status is separate in `trade_tape_status`. Company realtime follows the same split with `realtime_snapshot` and `realtime_status`. Phase 4.7C allows only process-local, streaming-backed `X-TRADE` events to populate `trade_tape` when the background SSI streaming manager is enabled, running, symbol-bootstrapped, and the per-symbol buffer contains parsed trade events. Phase 4.8E registers `X-TRADE:{symbol}` at startup alongside realtime `X:{symbol}` when trade tape is enabled and exposes diagnostics for not-subscribed, subscribed-empty, stale, and cache-hit states. Phase 4.8E-2 makes freshness diagnostic-only when buffered rows exist. Request handlers only read this buffer; they must not start streams, add subscriptions, or use `X:ALL`.

Each streaming trade row is latest-event tape data, not historical time-and-sales history. Public rows may include `ticker`, `price`, `volume`, `value`, `side`, `timestamp`, `timestamp_display`, `source`, `sequence`, and `raw_type`, plus compatibility aliases such as `time`, `side_if_available`, and `sequence_if_available`. Price, volume, and timestamp are required; rows missing any of those fields are dropped. `X-QUOTE` and `X` snapshot messages do not create trade-tape rows. `GET /api/v1/stocks/vn/realtime/trades` retains its top-level `trades` list plus short `status_message`; sanitized technical detail lives in its `diagnostics` object.

### Order Book / Bid-Ask Ladder

SSI `X-QUOTE:{symbol}` order-book context is an optional live watchlist block. It is produced only by the background streaming lifecycle and a dedicated process-local latest-row cache.

When SSI `X-QUOTE` has a usable fresh cached row:

```text
order_book_status.status = ok
order_book_status.reason_code = cache_hit
order_book = { ... }
```

When SSI `X-QUOTE` has a stale but usable cached row:

```text
order_book_status.status = stale
order_book_status.reason_code = stream_cache_stale
order_book = { ... is_stale=true ... }
```

The `order_book` object may include `ticker`, `symbol`, `exchange`, `bids`, `asks`, `trading_date`, `time`, `stream_timestamp`, `stream_data_type=X-QUOTE`, `r_type`, `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, and `cache_ttl_seconds`. Each `bids[]` / `asks[]` level may include `level`, `price`, and `volume`. A usable level requires positive `price` and nonnegative `volume`; malformed or empty levels are dropped and never replaced with fake placeholders.

When no usable row exists:

```text
order_book_status.status = unavailable or disabled
order_book_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, xquote_not_subscribed, xquote_disabled, unavailable_unknown, or unknown
order_book = null
```

`X-QUOTE` rows must not populate `latest_price`, `realtime_snapshot`, `trade_tape`, `session_status`, `foreign_room`, DailyOhlc, DailyStockPrice, or indicators. Request handlers must not start streams, add dynamic subscriptions, or use all-market channels. Price/volume units, market-specific level counts, empty-book behavior, and UI product rendering still require live evidence before stronger product claims.

### Foreign Room

SSI `R:{symbol}` foreign-room context is an optional live watchlist block. It is produced only by the background streaming lifecycle and a dedicated process-local latest-row cache.

When SSI `R` has a usable cached row:

```text
foreign_room_status.status = ok
foreign_room_status.reason_code = cache_hit
foreign_room = { ... }
```

The `foreign_room` object may include `ticker`, `symbol`, `exchange`, `total_room`, `current_room`, `foreign_buy_volume`, `foreign_sell_volume`, `foreign_buy_value`, `foreign_sell_value`, `trading_date`, `time`, `stream_timestamp`, `stream_data_type=R`, `r_type`, `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, `cache_ttl_seconds`, and `value_semantics_status`. Numeric room/volume/value fields must be valid nonnegative numbers when present; malformed fields are set null/dropped and rows with no usable R metric are unavailable.

When no usable row exists:

```text
foreign_room_status.status = unavailable or disabled
foreign_room_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, stream_cache_stale, r_not_subscribed, r_disabled, unavailable_unknown, or unknown
foreign_room = null
```

`R` rows must not populate `latest_price`, `realtime_snapshot`, `trade_tape`, `order_book`, `session_status`, DailyOhlc, DailyStockPrice, or indicators. They also do not replace DailyStockPrice daily foreign buy/sell/net enrichment. Request handlers must not start streams, add dynamic subscriptions, or use all-market channels. Foreign buy/sell value units and any exchange-specific approximate-value semantics remain `needs_semantics_proof` until live payload evidence confirms them.

### Trading Session / Status

SSI `F:{symbol}` session/status context is an optional live watchlist block. It is produced only by the background streaming lifecycle and a dedicated process-local cache.

When SSI `F` has a usable cached row:

```text
session_status_status.status = ok
session_status_status.reason_code = cache_hit
session_status = { ... }
```

The `session_status` object may include `ticker`, `symbol`, `exchange`, `trading_date`, `time`, `trading_session`, `trading_status`, `stream_timestamp`, `stream_data_type=F`, `r_type`, `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, and `cache_ttl_seconds`.

When no usable row exists:

```text
session_status_status.status = unavailable or disabled
session_status_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, stream_cache_stale, f_not_subscribed, f_disabled, unavailable_unknown, or unknown
session_status = null
```

`trading_session` and `trading_status` preserve raw SSI-observed values. The public contract does not map them to business labels such as open, closed, halted, suspended, lunch break, or final until live payload evidence proves exact meanings. `F` rows must not populate `latest_price`, `realtime_snapshot`, `trade_tape`, DailyOhlc, DailyStockPrice, or indicators. Request handlers must not start streams, add dynamic subscriptions, or use all-market channels.

### Market Index Pulse

SSI `MI:{index_code}` market-index pulse is an optional live index block. It is produced only by the background streaming lifecycle and a dedicated process-local market-index cache.

When SSI `MI` has usable cached rows:

```text
market_index_pulse_status.status = ok or partial
market_index_pulse_status.reason_code = cache_hit
market_index_pulse = [ ... ]
```

Each `market_index_pulse[]` row may include `index_code`, `exchange`, `index_value`, `estimated_index_value`, `change`, `change_pct`, `total_trades`, `total_volume`, `total_value`, `advances`, `unchanged`, `declines`, `trading_date`, `time`, `stream_timestamp`, `stream_data_type=MI`, `r_type`, `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, `cache_ttl_seconds`, `channel_format_status`, and `value_semantics_status`. Positive index values and nonnegative totals/breadth counts are required when present; malformed numeric fields are set null/dropped, and rows with no usable MI metric are unavailable.

When no usable row exists:

```text
market_index_pulse_status.status = unavailable or disabled
market_index_pulse_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, stream_cache_stale, mi_not_subscribed, mi_disabled, unavailable_unknown, or unknown
market_index_pulse = []
```

`MI` rows are exposed through the separate market-index pulse endpoint. They must not populate stock watchlist rows, `latest_price`, `realtime_snapshot`, `trade_tape`, `order_book`, `foreign_room`, `session_status`, DailyOhlc, DailyStockPrice, or REST DailyIndex rows. Request handlers must not start streams, add dynamic subscriptions, or use all-market channels. The `MI:{index_code}` channel format and value/breadth units remain `needs_live_proof` until market-hours live payload evidence confirms exact SSI semantics.

### Diagnostics

Diagnostics may include:

* Attempted endpoint names.
* Last endpoint.
* HTTP status.
* Provider status code.
* Retryable flag.
* Failure classification.
* Cooldown or reconnect backoff timing.
* A bounded sanitized provider-error summary.

Watchlist/company live diagnostics use:

```text
diagnostics.realtime = { ... }
diagnostics.trade_tape = { ... }
diagnostics.session_status = { ... }
diagnostics.order_book = { ... }
```

Status blocks do not carry endpoint dumps or raw provider messages. Diagnostics must not contain tokens, Authorization headers, cookies, account IDs, consumer credentials, full provider bodies, or stack traces. Secret-like diagnostic strings are redacted and URLs in provider summaries are collapsed.
* Stale-date details.
* Row counts.
* Normalized keys.
* Realtime failure mode such as `rest_unsupported`, `streaming_disabled`, `streaming_manager_not_started`, `streaming_cache_empty`, `streaming_cache_stale`, `streaming_manager_error`, `live_adapter_not_enabled`, or `streaming_parsed_rows`.
* Realtime manager/cache fields such as `streaming_status`, `manager_state`, `cache_status`, `parsed_streaming_rows`, and cache age or stale reason.
* Intraday failure mode such as `rate_limited`, `bad_request_params`, `auth_failed`, `permission_denied`, `timeout`, `network_error`, `parse_failed`, `provider_unavailable`, or `empty_response`.
* Intraday request diagnostics such as `endpoint=IntradayOhlc`, HTTP status, provider code, requested timeframe, internal request page size, and public candle limit.
* Sanitized provider error summaries.

Diagnostics must not include:

* SSI credentials.
* Tokens.
* Auth headers.
* Account IDs.
* Raw auth responses.
* Full raw provider payloads.

## News Contract

News is disabled until a separate VN news provider is implemented. The production Vnstock News configuration remains a legal/terms gate, not a crawler. A separate `vnstock_news_personal` mode may be enabled only for local/personal research.

Current public shape:

```text
news = []
news_status.status = disabled
news_status.source = disabled
```

When `VN_NEWS_PROVIDER=vnstock_news` is explicitly selected before written commercial and source-owner terms are recorded:

```text
news = []
news_status.status = unavailable
news_status.source = Vnstock News
news_status.provider = vnstock_news
news_status.reason_code = blocked_pending_terms
news_status.rights_status = blocked_pending_terms
```

When `VN_NEWS_PROVIDER=vnstock_news_personal` and `VNSTOCK_NEWS_PERSONAL_ENABLED=true` are selected locally, the service may lazily import the optional `vnstock_news` package and use only the documented RSS `Crawler.get_articles_from_feed` path with bounded sites, per-site limits, and process-local TTL cache. If the package is missing or fetch fails, `news=[]` and `news_status.status=unavailable` with `provider_package_missing`, `provider_error`, or `provider_no_items`.

`VN_NEWS_PROVIDER=vnstock_community` is a separate local/personal ticker-news mode using the installed free `vnstock` Community package. It may call only `Reference().company(ticker).news()` for an explicit selected/company ticker, never for every watchlist row. It returns at most three rows and uses a bounded 30-minute per-ticker cache. Success is `status=ok`, `reason_code=community_news_ready`; unavailable states include `invalid_ticker`, `provider_package_missing`, `provider_timeout`, `provider_error`, and `provider_no_items`. General force refresh does not bypass this news cache.

Personal-mode rows must include source URL/provenance and carry:

```text
news_status.provider = vnstock_news_personal
news_status.provider_mode = local_personal_research_only
news_status.rights_status = personal_research_only
```

Full article `content` is omitted by default. Ticker relevance is weak exact-symbol matching in title/summary only for the Sponsor RSS mode; it is not official ticker tagging. Community rows are already requested for the explicit ticker, but do not fabricate ticker metadata beyond that request context. Community `head` is unverified and is not exposed as a summary/source. A relative Community URL remains `raw_url`; `url=null` until a verified provider-specific article origin exists. An absolute `url` is exposed only after HTTP(S), hostname, and credential validation; the UI never uses `raw_url` as a link target.

News disabled/unavailable state must not be treated as a daily market-data failure. Mozyfin is not a VN runtime news fallback.

Phase 5.1B adds the explicit Vnstock status gate and offline normalization contract. Phase 5.1B-Local adds only an optional local personal RSS mode. Phase 5.1C adds a separate bounded Community ticker-news adapter. None of these modes adds credentials, market-data provider behavior, fallback provider, hosted production approval, or SSI ownership changes.

Future normalized news rows should include:

| Field | Rule |
| --- | --- |
| `id` | Stable dashboard item ID derived from provider namespace and item identity. |
| `title` | Required for a usable row. |
| `summary` | Nullable; only populated when supplied and licensed for display. |
| `source` | Publisher/source label. |
| `source_url` | Nullable but preferred for attribution and deduplication. |
| `published_at` | Provider publication timestamp; ingestion time must not replace it. |
| `tickers` | Normalized ticker list; empty list is allowed for market-wide news. |
| `market` | Market label such as `VN` when applicable. |
| `category` | Normalized category such as company, market, macro, industry, policy, earnings, corporate actions, disclosure, or other. |
| `language` | Provider language code when available. |
| `provider` | Provider adapter label. |
| `provider_item_id` | Provider-native ID when available. |
| `ingested_at` | Dashboard ingestion timestamp. |
| `sentiment` | Null unless the provider supplies a licensed methodology. |
| `importance` | Null unless the provider supplies a licensed methodology. |

Before any live news adapter is implemented, the provider must have written entitlement, production API/auth details, rate limits/SLA, display/storage/redistribution rights, full-text versus headline/summary/link rules, attribution requirements, source URL/provenance behavior, ticker mapping, historical depth, incremental update filters, Vietnamese encoding/timezone handling, and a sanitized licensed fixture.

## Future Module Contract

Future enrichment modules such as financials, corporate actions, events, ownership, and richer profile details may appear as placeholder sections while implementation is pending. If they are exposed before implementation, their status may be:

```text
disabled
not_configured
not_implemented
unavailable
partial
ok
error
```

Rules:

* `not_implemented` means no provider integration exists yet.
* `not_configured` means a future provider name was selected but no authorized adapter is wired.
* `disabled` means the feature exists but is intentionally off.
* `unavailable` means the feature is enabled or attempted but no usable data was returned.
* Placeholder future sections must use `null` for missing objects and `[]` for missing lists.
* Future-module placeholders must not be rendered as provider failures or daily-data failures.

### CorporateActionsProvider Contract

Phase 5.0B adds a contract proof only. It does not add a live external provider.

`GET /api/v1/stocks/vn/corporate-actions` returns:

* `status`: `disabled`, `not_configured`, `not_implemented`, `unavailable`, `partial`, `ok`, or `error`.
* `source`: `CorporateActionsProvider disabled` when the default disabled provider is used, otherwise the future provider contract source.
* `provider`: a sanitized provider label such as `disabled` or a future configured provider name.
* `events`: canonical normalized corporate-action rows, or `[]` when no verified rows exist.
* `items`: backward-compatible alias derived from `events`.
* `diagnostics`: sanitized provider diagnostics only.

Normalized event rows may include `ticker`, `event_id`, `event_type`, `event_subtype`, `title`, `announcement_date`, `ex_date`, `record_date`, `payment_date`, `effective_date`, `cash_dividend_per_share`, `cash_dividend_currency`, `stock_dividend_ratio`, `bonus_share_ratio`, `rights_issue_ratio`, `rights_issue_price`, `split_ratio`, `source`, `source_url`, `source_document_url`, `provider`, `provider_event_id`, `last_updated`, `raw_available`, `confidence`, `status`, and `missing_fields`. Compatibility aliases `rights_ratio`, `description`, and `last_checked_at` may remain while existing UI code migrates.

Corporate-action diagnostics may include provider, request domain, status, row count, failure class, last checked time, and requested ticker count. They must not include raw provider bodies, tokens, auth headers, API keys, account IDs, commercial credentials, or raw auth responses.

Disabled, not-configured, unavailable, and provider-error states must keep `events=[]` and `items=[]`. They must not imply the ticker has no corporate actions; they mean no verified provider rows are available to this dashboard.

Future adapters must treat `events` as the only canonical event list. If an adapter or legacy caller provides both `events` and `items`, the service/API keeps `events` and derives `items` from it so the two lists cannot diverge.

## Source Ownership

The SSI-first rule is: if SSI can provide a market-data field, SSI owns it; if a metric can be calculated from SSI-owned data, calculate it internally and label it as SSI-derived/internal. External providers are limited to domains SSI cannot provide or cannot legally/technically support with verified semantics. The canonical ownership matrix lives in `docs/SSI_DATA_CAPABILITY_MATRIX.md`.

| Data block | Owner | Public rule |
| --- | --- | --- |
| Daily OHLCV | SSI DailyOhlc | Canonical daily close and chart candles |
| `latest_price` | SSI DailyOhlc | Uses DailyOhlc close until canonical-source mismatch is resolved |
| Reference/ceiling/floor | SSI DailyStockPrice | Use when available |
| Matched volume/value | SSI DailyStockPrice | Use when available |
| Put-through volume/value | SSI DailyStockPrice | Use when available |
| Latest foreign flow | SSI DailyStockPrice | Use latest matched-date row when available |
| Foreign 5D/20D flow | SSI DailyStockPrice | Compute only from returned recent DailyStockPrice `foreign_net_volume` rows; null when history is insufficient |
| Technical indicators and SSI-derived metrics | SSI-derived internal | MA20/MA50, RSI14, Bollinger 20,2, 20D average volume, 20D high/low, volume ratio, 52W high/low, 10D average volume, 3M average volume, price-vs-reference %, daily range %, and short-term D1 zones are derived from SSI DailyOhlc and DailyStockPrice inputs where applicable and must not use external provider substitutes |
| Deferred beta / market cap | SSI-derived or source-labeled after proof | Beta requires verified SSI index data and methodology; market cap requires verified share-count semantics before calculation |
| Index list | SSI IndexList | Use SSI-returned index codes and identifiers |
| Daily index | SSI DailyIndex | Optional index value/change/liquidity/breadth rows only after exact IndexList resolution |
| Index components | SSI IndexComponents | Use an explicit normalized index code directly; expose rows only when SSI returns exact usable members |
| Symbol metadata | SSI SecuritiesDetails, then SSI Securities fallback | Optional fields remain null; metadata availability/quality never changes daily validity |
| Intraday candles | SSI IntradayOhlc | Strict source; no fallback |
| Realtime snapshot | SSI FastConnect streaming realtime contract | Parser, manager/cache, official-client adapter, and FastAPI startup bootstrap exist behind disabled-by-default config; request handlers read process-local cache only |
| Trade tape / latest trade events | SSI streaming X-TRADE event buffer | Fresh bootstrapped X-TRADE rows may populate latest-event tape; full historical time-and-sales remains unverified |
| SSI `X-QUOTE` stream | SSI streaming runtime proof | Order-book context may appear in watchlist `order_book`; level-count/unit proof and UI remain deferred and must not affect price ownership |
| SSI `R` stream | SSI streaming runtime proof | Foreign-room context may appear in watchlist `foreign_room`; value-unit/approximation proof and UI remain deferred and must not replace DailyStockPrice foreign flow |
| SSI `F` stream | SSI streaming runtime proof | Raw trading session/status context may appear in watchlist `session_status`; code meanings and finality labels remain deferred and must not affect price ownership |
| SSI `MI` stream | SSI streaming runtime proof | Market-index pulse may appear in `market_index_pulse`; channel/field live proof and UI remain deferred and must not replace DailyIndex or affect price ownership |
| Future SSI `B` stream | SSI streaming after runtime proof | Realtime bars must remain separate source-labeled blocks; no fake placeholders and no request-handler stream starts |
| Future SSI extended instrument metadata | SSI SecuritiesDetails/Securities after runtime proof | Derivative, covered warrant, ETF/fund, and bond fields require exact row-key evidence and instrument-specific semantics before exposure |
| News | Future NewsProvider | Disabled by default; `vnstock_news` is unavailable with `blocked_pending_terms`; `vnstock_news_personal` is local/personal research only |
| Financials | Future external provider | Not implemented |
| Corporate actions | `CorporateActionsProvider` future external boundary | Disabled/not configured by default; no inference |
| Mozyfin | Disabled for VN runtime | No fallback |
| KBS | Legacy optional only | Disabled by default |

Compatibility aliases must stay within the same source owner. Do not use SSI DailyStockPrice close to overwrite `latest_price`, do not use DailyOhlc volume to fill matched volume, and do not use realtime, trade-tape, Mozyfin, or KBS values to fill daily fields.

Future SSI-backed fields from Phase 4.8F must be additive and explicit. Public rows need source labels, availability status, missing-field/null semantics, and sanitized diagnostics. Missing streaming data must stay `null` or `[]` rather than placeholder metrics, and external providers must not fill order book, trading status, foreign room, market-index pulse, realtime bars, or SSI-returned instrument metadata while SSI can provide those fields.

## Index Data Contract

Index data is optional and independent of watchlist/company daily validity:

* IndexList unavailable: `rows=[]`, `status=unavailable`.
* DailyIndex unavailable: `rows=[]`, `status=unavailable`.
* IndexComponents unavailable: `rows=[]`, `status=unavailable`.
* Missing optional index fields remain `null`; provider zero values remain zero.
* DailyIndex `date_match` compares requested indexes with the newest DailyIndex date in the same response. It does not assert exchange-session finality.
* Exact SSI IndexList identifiers remain required for DailyIndex discovery. An explicit IndexComponents `index_code` is attempted directly through SSI `indexCode`; IndexList failure does not block that request.
* Diagnostics may include endpoint, requested market/code, selected identifier, IndexList status (`not_required` for explicit IndexComponents), normalized row count, field coverage, missing fields, failure class, and sanitized process-cache status/TTL/key fields. Raw provider payloads and authentication data are excluded.

## Symbol Metadata Contract

`symbol_metadata.status` describes provider availability and remains `ok` or `unavailable`. `quality_status` separately describes field completeness as `complete`, `partial`, `unknown`, or `unavailable`.

The metadata block exposes nullable `symbol`, `exchange`, `market`, `name`, `name_en`, `industry`, `sector`, `security_type`, `issuer`, `lot_size`, `listed_shares`, and `listed_date`, plus:

* `completeness`: covered-field ratio from `0` to `1`.
* `missing_fields`: normalized optional fields with no SSI value.
* `field_coverage`: per-field boolean coverage.
* `source`: the selected SSI endpoint.
* `diagnostics`: sanitized endpoint attempts, row counts, selection source, and failure class.

`SecuritiesDetails` is attempted first. `Securities` is an allowed same-provider fallback. A row is usable only when its normalized symbol exactly matches the requested ticker. Do not infer missing names, industry, sector, issuer, or listing fields from the ticker, exchange, prices, or another provider.

### DailyStockPrice Enrichment Contract

`daily_stock_price.status` records provider-row availability. `daily_stock_price.quality_status` is `ok`, `partial`, or `unavailable`; it does not downgrade a usable SSI DailyOhlc row.

Date alignment is exposed through `daily_stock_price.date`, `daily_stock_price.date_match`, and the compatibility fields `daily_stock_price_date`, `daily_stock_price_date_match`, and `daily_stock_price_staleness_reason`. Date-match values are `matched`, `mismatched`, `unknown`, or `unavailable`. Missing dates are `unknown`; failed or empty DailyStockPrice requests are `unavailable`.

`missing_fields` and `field_coverage` describe normalized enrichment completeness. `units` includes only fields whose values exist, so units metadata is not evidence that a null field is available. Price/value fields use VND; volume fields use shares. Zero returned by SSI remains zero, while missing values remain null.

The watchlist indicators expose bounded recent foreign-flow summaries as `foreign_net_5d_latest_available`, `foreign_net_20d_latest_available`, `foreign_net_latest_available_date`, and `foreign_net_history_count`. These values are derived only from the existing per-symbol recent DailyStockPrice rows and `foreign_net_volume` in shares. They stay null when fewer than the required 5 or 20 returned rows have usable net volume; they do not mix value and volume units.

Sanitized `daily_stock_price.diagnostics` may include endpoint name, requested symbol/date range, normalized row count, selected row date, DailyOhlc date, date match, DailyStockPrice foreign-history row counts/date span/status, missing fields, field coverage, and failure class. It must not include raw provider payloads, credentials, tokens, auth headers, account identifiers, or raw auth responses.

## External Provider Boundary

Phase 4.5A/5.0A do not add a live external provider. Phase 5.0B adds only a disabled-by-default `CorporateActionsProvider` contract proof. Corporate actions are the first selected domain for provider qualification, but they remain `disabled`, `not_configured`, or unavailable until the access and legal gates in `docs/VN_EXTERNAL_PROVIDER_STRATEGY.md` pass. VNStocks and FiinGroup are candidate external providers only, both `needs_verification`; they are not runtime sources, fallback providers, or implementation sources in the current contract.

External provider rules:

* External rows must carry their own provider/source labels and provenance.
* External providers must not overwrite SSI-owned daily, DailyStockPrice, intraday, realtime, index, or metadata fields silently.
* External-provider failure must preserve valid SSI watchlist/company data.
* Disabled or not-implemented list domains return `[]`; missing objects return `null`.
* Public disclosure pages are not an automation contract and must not be scraped without explicit approval and verified terms.
* A future metadata fallback may fill only SSI-null fields under explicit per-field priority and source rules.
* A future external VNINDEX value must be explicitly labeled as external and must never be presented as SSI.

## UI Rendering Rules

### Daily Data

Render daily data when the row has valid SSI DailyOhlc fields and daily status is OK. Optional section failures should not hide daily close, chart, or DailyStockPrice fields.

Frontend compact numeric formatting is presentation-only. API price fields remain raw VND/share values, but VN price-like values are displayed in board-style thousand-VND units with two decimals and no suffix, for example `72,100` becomes `72.10`. Share volumes may use `K`/`M`; VND trading values may use `K`/`M`/`B`/`T`. This formatting must not change `latest_price`, source labels, API payloads, or missing-data semantics.

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

`cache_status.daily_stock_price_cache` may report `hit`, `miss`, `refresh`, or `stale` for the bounded recent DailyStockPrice enrichment/history result. Its process-local TTL is 300 seconds. `force_refresh=true` bypasses this freshness check. This diagnostic cache field does not change source ownership: `latest_price` remains SSI DailyOhlc, while the cached enrichment remains SSI DailyStockPrice.

IndexComponents diagnostics may report `cache_status`, `cache_ttl_seconds`, `cache_negative`, and a sanitized key containing only provider, endpoint, normalized index code, and optional market. Usable rows use a 300-second TTL. Unavailable, rate-limited, and no-row responses use a 60-second negative TTL. `force_refresh=true` bypasses this cache.

## Recently Completed Contract Cleanup

* Phase 4.7B completed: unavailable watchlist/company `trade_tape` is `[]`, status stays in `trade_tape_status`, realtime data/status stay split, and sanitized provider details live under sectioned `diagnostics` instead of status messages.
* Phase 2.1 completed: unavailable company `intraday.pulse` is `null`, not `{}`.
* Phase 4.7B completed: frontend rendering treats unavailable live objects as `null`, missing watchlist/company trade tape as `[]`, and sectioned diagnostics as diagnostics-only UI content.

## Phase 4.11B / 4.11B-3 Future Intraday Chart Contract

Phase 4.11B is documentation-only. The current watchlist/company `intraday_candles` pulse remains an optional compact SSI block; it is not the production history contract for Lightweight Charts. No intraday chart endpoint or timeframe UI exists yet.

### Evidence boundary and interval vocabulary

The installed `ssi_fc_data` 2.2.2 package defines `IntradayOhlc` and an integer `resolution` field with default `1`, but it provides no interval enum, unit definition, supported-value list, query-range limit, final-bar field, or session semantics. Its official repository sample supplies `DD/MM/YYYY` dates and `resolution=1`; the installed package itself contains no resolution mapping. The repository adapter currently accepts arbitrary request strings and has deterministic cadence fixtures for `1m`, `5m`, and `1h`; those fixtures verify StockClock normalization only, not SSI interval support.

Phase 4.11B-3 completed the evidence gate for a deliberately restricted completed-session interval. Phase 4.11C has since implemented the production public interval allowlist as exactly `1m` for one completed Vietnam date through the separate endpoint and UI.

| Public candidate | Provider candidate | Status | Rule |
| --- | --- | --- | --- |
| `1m` | `resolution=1` | `verified` for one completed HOSE session per request | Four FPT/HPG sessions produced one unique floored minute bucket per row, exact continuous-session minute cadence, exact DailyOhlc OHLC/volume reconciliation, and fewer than 1,000 rows. |
| `5m` | `resolution=5` | `unsupported_mapping` | Accepted but returned the same 226-row minute-like cadence; 0% of deltas matched 300 seconds. |
| `15m` | `resolution=15` | `unsupported_mapping` | Accepted but returned the same 226-row minute-like cadence; 0% of deltas matched 900 seconds. |
| `30m` | `resolution=30` | `unsupported_mapping` | Accepted but returned the same 226-row minute-like cadence; 0% of deltas matched 1,800 seconds. |
| `1h` | `resolution=60` | `unsupported_mapping` | Accepted but returned the same 226-row minute-like cadence; 0% of deltas matched 3,600 seconds. Existing `timeFrame=1h` hints remain non-authoritative. |

Phase 4.11B-2 used six of seven allowed provider calls to establish the request shape and reject unsupported higher-resolution mappings. Phase 4.11B-3 then used four `IntradayOhlc` and four matching `DailyOhlc` calls: FPT and HPG on completed HOSE sessions `2026-06-23` and `2026-06-24`. Every intraday request used one ticker/date, `resolution=1`, `pageIndex=1`, `pageSize=1000`, and `ascending=true`; every call succeeded with 226 rows and `totalRecord=226`. All four sessions had the identical raw fields `TradingDate`, `Time`, `Open`, `High`, `Low`, `Close`, `Volume`, `Value`, and `Symbol`.

Raw timestamps remain timezone-free `TradingDate=DD/MM/YYYY` plus `Time=HH:MM:SS`. In each sample, 225 of 226 rows had nonzero seconds, while flooring in `Asia/Ho_Chi_Minh` produced 226 unique, ascending minute buckets with no duplicate bucket, invalid timestamp, or out-of-order row. The continuous buckets were `09:15` through `11:29` and `13:00` through `14:29`; all 223 within-segment transitions were exactly 60 seconds. The apparent 11:30 and 14:30 boundary omissions are half-open session boundaries, not unexplained missing bars. A separate final `14:45:00` row was present in every sample.

The raw `Time` value is classified `likely_last_trade_time_but_not_fully_verified`: its seconds vary within the minute and consistently land near the minute end, but neither the SDK nor official sample defines it and no trade-level comparison was performed. The canonical chart timestamp is therefore the raw Vietnam wall time floored to minute start, then converted to Unix seconds. Flooring changes only placement, never OHLCV. Invalid timestamps are rejected; the four live samples had no duplicate normalized bucket, while a future duplicate uses stable last-provider-row-wins handling with a diagnostic count. The current adapter's naive-as-UTC helper is not canonical and must be corrected in Phase 4.11C.

All 904 intraday OHLC rows passed consistency validation. For every ticker/date, first open, maximum high, minimum low, and final close exactly matched the same-date SSI DailyOhlc row (zero absolute and percentage difference). The first 09:15 row also matched DailyOhlc open, and the final 14:45 row matched DailyOhlc close. This is observed reconciliation, but the exact ATO/ATC aggregation mechanism and the locations of session extrema remain ambiguous.

`Volume` was numeric, positive, non-missing, and non-cumulative in all four sessions. Per-session intraday sums exactly equalled DailyOhlc volume: FPT `5,737,500` and `5,968,500`, HPG `29,071,800` and `12,927,300`, each ratio `1.0`. This supports `likely_per_bar_shares`; because SSI's inspected materials do not explicitly define the unit, the first UI must label it neutrally as `Volume`, not assert `shares`. No missing candles are synthesized or forward-filled; Lightweight Charts must display sparse normalized timestamps as gaps. These findings are limited to FPT/HPG on HOSE and do not generalize to HNX, UPCOM, holidays, half sessions, halts, or post-close/negotiated behavior.

Phase 4.11C implements only one-date, completed-session `1m` history. Current-session bars, multiple days, pagination, higher intervals, realtime updates, aggregation, and fallback remain outside the runtime allowlist.

Aliases are case-sensitive and rejected unless added to the verified allowlist. `60m`, `1H`, numeric strings, and provider-specific spellings must not be accepted silently.

### Endpoint selection and request bounds

Phase 4.11C implements a separate endpoint rather than widening the daily endpoint:

```text
GET /api/v1/stocks/vn/intraday-chart
  ?ticker=FPT
  &interval=1m
  &date=2026-06-24
```

`/vn/chart` remains D1-only and SSI DailyOhlc-owned. The separate endpoint makes cache, source, timestamp, and diagnostics explicit without breaking the existing daily client; it has no provisional-bar behavior.

Request rules for the first implementation are deliberately narrower than the earlier range proposal:

* Public `ticker` is required, normalized uppercase, and validated with the existing VN ticker rules. The SSI provider request continues to use its own `symbol` field.
* `interval` is required and its only accepted value is `1m`; 5m/15m/30m/1h are rejected before any SSI call.
* `date` is one ISO `YYYY-MM-DD` Vietnam trading date. The backend converts it to SSI `DD/MM/YYYY` and requests only that date.
* The date must be strictly earlier than the current date in `Asia/Ho_Chi_Minh`. Current-day and future dates are rejected; same-day closed-session support remains deferred because holiday/session finality is not yet authoritative.
* The response is capped at 1,000 usable bars. One provider page uses `pageSize=1000`; multi-page behavior is not part of the first scope.
* The current process-wide provider timeout is 10 seconds per attempt.
* Intraday provider concurrency is one per process initially. Identical requests use single-flight ownership. No parameter-variant fan-out is allowed after the verified request shape is selected.
* Automatic retry count is zero in the first implementation. SSI/HTTP `429`, auth, permission, and invalid-parameter failures are never retried; the existing 60-second rate-limit cooldown remains applicable. `force_refresh=true` bypasses usable positive/negative cache lookup but not validation, single-flight, pacing, cooldown, or stale-recovery safeguards.

### Canonical response

```json
{
  "ticker": "FPT",
  "exchange": "HOSE",
  "interval": "1m",
  "timezone": "Asia/Ho_Chi_Minh",
  "status": "ready",
  "reason_code": null,
  "bars": [
    {"time": 1719800100, "open": 128000, "high": 128500, "low": 127800, "close": 128300, "volume": 125400}
  ],
  "source": {"provider": "ssi_fastconnect", "dataset": "IntradayOhlc"},
  "cache": {"status": "miss", "is_stale": false, "captured_at": "...", "expires_at": "..."},
  "diagnostics": {"requested_date": "2026-06-24", "returned_bars": 1, "rejected_rows": 0, "duplicate_timestamps": 0}
}
```

`time` is a Unix timestamp in seconds representing the floored minute start. Verified SSI fields are separate timezone-free `TradingDate` (`DD/MM/YYYY`) and `Time` (`HH:MM:SS`). They must be interpreted as `Asia/Ho_Chi_Minh` wall time, floored to the minute, and then converted; never treat them as UTC or parse them in the browser. Bars are sorted ascending and unique by `(ticker, interval, time)`. For duplicates, the last provider row in stable provider order wins and the discarded count is diagnostic.

OHLC values remain raw VND/share. Volume remains the non-negative SSI `Volume` value and is labelled `Volume`; `likely_per_bar_shares` is evidence, not a public unit guarantee. A usable row requires finite positive OHLC, `high >= max(open, close, low)`, `low <= min(open, close, high)`, and finite non-negative volume. Malformed rows are rejected individually. A response may remain `ready` when usable rows remain, with `reason_code=partial_rows_rejected`; if no usable row remains after a non-empty provider response, return `failed`, not an empty success. `is_final` is absent because completed dates are the only accepted scope.

Top-level statuses are `ready`, `unavailable`, and `failed`. Staleness belongs under `cache.is_stale` rather than a fourth top-level status:

* Explicit provider success with no rows: HTTP 200, `ready`, `bars=[]`, `reason_code=no_data`.
* Provider unavailable/rate-limited/permission failure with no usable cache: HTTP 200, `unavailable`, `bars=[]`, sanitized `reason_code`.
* Provider failure with a bounded usable stale entry: HTTP 200, `ready`, preserved bars, `cache.status=stale`, `cache.is_stale=true`, `reason_code=stale_cache_recovery`.
* Unsupported interval, current/future date, invalid date, or invalid symbol syntax: HTTP 422; do not call SSI.
* Malformed provider success with no usable bars: HTTP 502, `failed`, `bars=[]`.

### Cache and freshness design

Cache the completed provider day under an independent identity such as `intraday_chart:{ticker}:1m:{vn_trading_date}:page:1`. Do not reuse DailyOhlc cache entries, the existing compact-pulse key, or Phase 4.8S streaming snapshot persistence.

Treat completed history as immutable for the initial contract: positive entries use a 86,400-second TTL, unavailable/no-data entries use 60 seconds, usable expired history may be served stale for up to seven days after an SSI failure, and the process-local cache is capped at 500 LRU keys. There is no active/lunch/current-day cache policy in Phase 4.11C.

The existing Vietnam market-phase helper is HOSE-like and holiday-unaware. Phase 4.11C avoids that ambiguity by accepting only dates strictly before the current Vietnam date. SSI ATO/ATC mechanics, post-close/negotiated rows, suspensions, half sessions, holidays, HNX, and UPCOM remain unverified and must not be encoded as provider facts.

### Frontend ownership and source split

The future dashboard owns selected ticker, selected interval, selected completed date, request key, request ID, loading/unavailable state, and stale-response rejection. Ticker, interval, or date change invalidates the old request and clears the old presentation; only a matching `(ticker, interval, date, request_id)` response may apply. The chart component receives normalized bars and metadata and performs no request.

`1D` continues to call `/vn/chart` and use SSI DailyOhlc. The implemented `1m` option calls `/vn/intraday-chart` for Today or an available completed date and uses only SSI IntradayOhlc; current-day data is delayed bounded polling, not realtime data. DailyStockPrice, X, X-QUOTE, X-TRADE, and persisted streaming snapshots never become candles. Indicators use the active timeframe bars; Phase 4.9A zones remain daily and read `Daily S/R` over intraday history.

### Observability requirements

Phase 4.11C should count requests by public interval, provider latency, cache hit/miss/refresh/stale outcomes, returned bars, rejected rows, duplicate timestamps, provider-unavailable responses, unsupported intervals, stale recoveries, invalid/current-date rejections, and frontend ownership discards. Diagnostics may expose sanitized requested date, provider page count, returned/rejected counts, and cache age. Logs and responses must never include credentials, access tokens, authorization headers, full provider payloads, account IDs, consumer IDs, or consumer secrets.

## Phase 4.11D-1 Current-Session Source Audit

Phase 4.11D-1 is evidence and contract work only. It does not enable the current date, add polling, add a provisional schema field, aggregate X-TRADE, or change the completed-session endpoint.

On 2026-07-16, eight bounded FPT `IntradayOhlc` calls used the current Vietnam date, `resolution=1`, page 1, page size 1,000, and ascending order. Calls at 09:12:34 and 09:15:05 returned HTTP 200 with provider code `NoDataFound`. At 09:16:05, SSI returned the 09:15:59 opening row plus a 09:16:05 row for the still-open minute. Repeated calls at 09:16:30 and 09:16:55 changed that row's raw `Time`, OHLC, and volume. At 09:17:10 a newer normalized bucket existed and the prior row had advanced through 09:16:58; it remained unchanged at 09:17:30 and 09:20:05. The final sample returned six valid unique buckets, zero rejected rows, and zero duplicate normalized buckets.

SSI current-session behavior is therefore classified `provisional_current_bar`. The raw `Time` is the newest provider event time within the bucket, not its canonical bucket start. Previous-bucket finality is `inferred_finality_with_reconciliation`: a prior bucket may be treated as provisionally closed when a newer normalized bucket appears, but SSI exposes no provider finality flag and SSI remains authoritative on every refresh. `provider_finality_verified` is not claimed.

Provider-response latency was 0.423-1.116 seconds (median 0.615, sample count 8, including two valid `NoDataFound` responses). For the five repeated current-bucket observations, observation time minus normalized bucket start was approximately 5, 30, 55, 10.8, and 30 seconds (minimum 5, median 30, maximum 55, sample count 5). The first new 09:17 bucket was observed at 09:17:10 with raw time 09:17:04. This is a bounded opening-session sample, not a full-day latency SLA.

Phase 4.11D-2 implements the delayed-only gate. Current responses add `session_state`, `freshness`, `last_provider_refresh_at`, `newest_bar_age_seconds`, and `current_bar_state`. The backend uses 15-second positive, 5-second empty, 10-second negative, and five-minute stale-if-error current-date bounds; completed dates retain 24-hour/60-second/seven-day policy. The dashboard schedules one 09:15:07 opening wake-up when Today remains selected from pre-open, one absolute-time request near each eligible minute boundary plus seven seconds, one 13:00:07 afternoon baseline after lunch, and one 14:45:20 post-close reconciliation. It uses `Updating`, `Delayed`, `Stale`, `Pre-open`, `Lunch break`, `Closed`, `Completed`, or `No data yet`, never `Live`; hidden tabs and completed/D1 views do not poll.

Phase 4.11E adds `provider_snapshot_age_seconds` without replacing `newest_bar_age_seconds`. The former is current Vietnam time minus the successful fetch timestamp that produced the cached snapshot; cache hits increase it, and stale recovery preserves the original timestamp. The latter remains current Vietnam time minus the newest accepted raw SSI `TradingDate + Time`. During an active scheduled window, `updating` requires a snapshot age no greater than 30 seconds and a newest normalized bucket in the current or immediately previous minute. `stale` applies to stale-if-error data or an active-session provider snapshot older than 90 seconds. A recent snapshot with an older bucket is `delayed`; lunch does not become stale solely because no candle is expected. No current-date stale entry crosses Vietnam midnight.

The cache identity is provider-owned and contains SSI FastConnect/`IntradayOhlc`, normalized ticker, `1m`, Vietnam trading date, page 1, and page size 1,000. Concurrent requests for the exact same key share one process-local provider fetch, including normal/force overlap; a waiter never cancels the shared fetch and the in-flight entry is removed after success or failure. `force_refresh=true` still bypasses a fresh cache when no same-key fetch is active. This is worker-local coalescing, not a distributed lock.

`GET /api/v1/stocks/vn/intraday-chart/health` performs no SSI call and no cache refresh. It returns bounded worker-local request/cache/provider/data-quality/concurrency counters, latency aggregates, current Vietnam session state, and one sanitized last-provider-result snapshot; it never returns bars, cache keys, raw provider rows, exception messages, headers, accounts, or credentials. `status=unknown` means no provider attempt in that worker, `ok` means the most recent meaningful result was usable or expected no-data, and `degraded` means the latest attempt failed/was unavailable or required stale recovery. Market closed, lunch, and pre-open do not by themselves make health degraded. Metrics reset at process restart and each Render worker has independent values.

This is the canonical Phase 4.11E intraday-chart operational route. `GET /api/v1/stocks/vn/observability` remains a separate established dashboard-wide provider/cache status contract with `VietnamObservabilityResponse`; it is not an alias for intraday-chart health. OpenAPI exposes both paths with distinct response schemas, and neither route starts an SSI fetch.

A live `X-TRADE:FPT` audit observed 124 events in 30 seconds, performed one controlled disconnect/reconnect, then observed 82 events in the next 30 seconds without transport errors. Every event exposed `Symbol`, `TradingDate`, `Time`, `LastPrice`, `LastVol`, `TotalVol`, `Side`, `TradingSession`, and `TradingStatus`; none exposed a trade ID, sequence, message ID, channel sequence, correction flag, or cancel flag. Visible `(ticker,date,time,price,last-volume,side)` tuples collided 109 times across the two windows. `TotalVol` behaved as a cumulative session total and `LastVol` matched the increment when the total advanced, but repeated deliveries with unchanged `TotalVol` make raw summation unsafe. Volume is classified `likely_incremental`; ordering is `receive_order_only`; deduplication is `unsafe`; replay/gap/correction behavior is `unavailable`.

Phase 4.11D-3 is `blocked`. X-TRADE must not create or update chart candles until stable identity or ordering, replay/gap detection, correction semantics, and safe deduplication are verified. A reconnect cannot currently prove missed or replayed events, so the conservative future rule remains: suspend provisional trust, fetch a fresh SSI IntradayOhlc baseline, replace/reconcile the latest bars, then resume only after the stream is healthy. SSI wins every mismatch. X snapshot, X-QUOTE, F, R, MI, the compact pulse, DailyStockPrice, and persisted streaming snapshots are not candle sources.

Scheduled HOSE classification is clock-derived in `Asia/Ho_Chi_Minh`: pre-open before 09:15, morning 09:15-11:30, lunch 11:30-13:00, afternoon 13:00-14:30, ATC 14:30-14:45, and closed afterward or on weekends. This does not prove an exchange holiday, halt, half session, HNX, or UPCOM schedule. No bar exists without an SSI row, morning bars are never extended through lunch, successful refreshes authoritatively replace the array, and date/ticker/timeframe/request-ID ownership prevents stale responses from winning.

Late-event policy remains closed while X-TRADE is blocked. A future stream overlay may revise only the current bucket and, if later evidence supports it, the immediately previous bucket for a short measured grace period. It must bucket by provider exchange date/time in `Asia/Ho_Chi_Minh`, never receive time; never span lunch; never reopen unlimited history; and discard provisional state whenever SSI differs, omits the provisional bucket, reconnects, or changes session/date. Until a provider-backed identity/order key exists, no composite visible-field key is safe enough to accept or reject a late event.

Future current-session metadata may include `session_state`, `freshness`, `last_provider_refresh_at`, `newest_bar_age_seconds`, and `current_bar_state`, but no field is added by this audit. Recommended UI states are `Completed`, `Updating`, `Delayed`, `Reconnecting`, `Stale`, and `Closed`; `Live` remains unapproved. Future observability must count SSI requests/latency/revisions/newest-bar age, X-TRADE events/duplicates/out-of-order/sequence gaps/reconnects, reconciliation mismatches, provisional replacements, stale transitions, and current-session unavailability without logging raw payloads or credentials.

## Known Contract TODOs

### P0

* Phase 1: investigate SSI DailyOhlc vs DailyStockPrice same-date mismatch. Latest smoke observed FPT on `2026-06-22` with DailyOhlc/dashboard close fields at `70,700`, DailyStockPrice close/adjusted close at `70,800`, DailyOhlc volume at `3,642,400`, and DailyStockPrice matched volume at `3,643,500`.
### P1

* Phase 2: deprecate top-level `intraday_timeframe`.
* Phase 2: move stale intraday latest-date/date-match metadata into status/diagnostics when no usable intraday data exists.
* Phase 2 and Phase 4.0: add backoff or longer TTL for non-retryable SSI realtime/trade-tape 404 responses.

### P2

* Future selected-ticker/source-coverage work: add aliases only after sanitized SSI row-key evidence; unsupported metadata stays null.
* Future DailyStockPrice history or caching work: consider durable caching only if measured latency/rate-limit evidence requires it. The current contract already supports bounded in-memory latest-available 5D/20D foreign net volume from recent SSI DailyStockPrice rows.
* Phase 1 and Phase 2: clean quote metadata semantics when quote is disabled or unreliable.
* Phase 1: improve `final_close_status` using VN session/calendar rules.

### P3

* Phase 2 and Phase 6.0: clarify cache errors versus provider unavailable.
* Phase 2: clarify units metadata versus data availability.
