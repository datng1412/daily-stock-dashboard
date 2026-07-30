# VN API Catalog

## Purpose

This catalog documents the VN dashboard API surface used by the current dashboard and company detail page. It does not invent future endpoints. Contract details should stay aligned with `docs/VN_DATA_CONTRACT.md`, `docs/DATA_DICTIONARY.md`, and `docs/UI_STATES.md`.

Global rules:

- SSI is the strict primary VN market-data provider.
- Mozyfin is disabled for VN runtime.
- KBS is legacy optional only and disabled by default.
- News is disabled until a separate provider exists.

## Completed foreign-flow restart behavior

The existing symbol-history and aggregate routes keep their public schemas.
Accepted completed SSI DailyStockPrice symbol rows are rehydrated at application
startup from the bounded schema-v1 cache below `DATA_CACHE_DIR`. Valid newer
accepted dates survive process restart and weaker/empty/failed refreshes; valid
same-date corrections replace one row. This store is an internal completed-data
continuity mechanism, not a fallback provider. Current `room.{symbol}` payloads
and provisional aggregates are never persisted into it.

## `GET /api/v1/stocks/vn/foreign-flow/current/{ticker}`

Returns the process-shared SSI V3 `room.{ticker}` provisional current-session
snapshot when one has been received. Raw `bq`/`sq`/`bv`/`sv` presence is
audited before typed SDK defaults, each message replaces the prior
symbol/session snapshot, and the application never locally accumulates room
messages. Room capacity (`tr`/`cr`) remains separate from foreign trading flow.

`data_state` is one of `waiting`, `ready`, `stale`, `market_closed`,
`unavailable`, or `error`. `current` stays `null` until at least one complete
buy/sell value or volume pair is present; missing fields are never fabricated
as zero. `latest_completed_comparison` is independently sourced from an earlier
SSI V3 DailyStockPrice session. Provisional current values are never appended
to historical daily rows. The route never owns a stream client. It may record
one bounded symbol lease and request recovery from the process-owned lifecycle
when the shared client is disconnected or retryably failed. Repeated polls,
manual refresh, and page reload share one scheduled attempt and cooldown;
they do not create concurrent provider connections. `force_refresh=true`
identifies an explicit recovery touch while retaining no-store response
semantics and the existing subscription cohort. The additive
`recovery_trigger=route_touch|visibility_resume|manual_refresh` query identifies
the recovery cause; it does not transfer stream ownership to the route.

A valid prior snapshot remains present with `data_state=stale` during
reconnection. Without a usable snapshot, the current capability is
`unavailable`; completed DailyStockPrice capabilities remain independently
usable. Successful connection clears the prior retryable stream failure, and
only a newer provider message replaces the cached snapshot.

## `POST /api/v1/stocks/vn/industry-flow`

Accepts exactly one bounded universe selector: `symbols` or `index_code`, plus ISO `from_date` and `to_date`. Valid provider-backed ready and partial responses retain their existing rows. The response also exposes `data_state`, `usable`, and a sanitized `failure_class`.

Request-shape, identifier, and date validation errors return HTTP 422. Provider or membership unavailability returns HTTP 200 typed unavailable with empty rows and explicit SSI provenance; it is not reclassified as invalid input or unsupported. Unexpected service invariants use sanitized HTTP 500 behavior.

## `GET /api/v1/stocks/vn/foreign-flow/watchlist`

Returns one bounded foreign-flow screener response for 1–30 user-controlled, normalized unique symbols. Query parameters are `tickers=FPT,SSI,HPG`, `sessions=1|5|20|60` (the product requests 60 once), and optional `force_refresh=true`. The response preserves normalized input order, isolates per-symbol failures, and returns completed-session buy/sell/net value and volume metrics for 1/5/20/60 sessions without history arrays.

Top-level status is `ready`, `partial`, or `unavailable`; per-symbol availability, source freshness, cache state/age, failure class, session coverage, streak basis, and explicit-zero anomaly metadata remain separate. Authentication, authorization, timeout, and provider failures are never reclassified as unsupported. Missing metrics remain null and provider-backed zero remains zero. Worker concurrency is capped at four, each ticker is bounded to 20 seconds, and the total request is bounded to 45 seconds. This endpoint does not claim current-session foreign flow.

## Symbol foreign-flow history and analytics

`GET /api/v1/stocks/vn/foreign-flow/symbol/{ticker}` accepts the existing recent-session or paired date-range request. The frontend inspection path uses `limit=60`. The response additively includes optional `analytics` with separate value/volume 5/20/60 statistics and date-aligned rolling 5/20 series. Existing clients may ignore the field. Cache, single-flight, force-refresh, stale-if-error, sanitization, and provider ownership remain unchanged; there is no new endpoint and no current-session or polling behavior.
- Missing object data returns `null`.
- Missing list data returns `[]`.
- Live-provider statuses use `ok`, `unavailable`, or `disabled`.
- Future modules may use `not_implemented` until Phase 2 decides whether to normalize them.
- Diagnostics carry endpoint/http/raw-provider details; primary fields do not.
- Active UI labels must not present SSI realtime or SSI trade-tape contracts as KBS. KBS/Mozyfin names are legacy diagnostics or historical context only.

## `GET /api/v1/stocks/vn/watchlist/health`

Purpose:

- Return data-quality metadata for configured or requested VN watchlist tickers.
- Support health checks without changing watchlist market-data ownership.

Common params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `tickers` | Optional comma-separated VN symbols | Defaults to configured VN watchlist. |

Response rules:

- Health/status metadata should be concise and source-aware.
- Missing ticker-level objects should be `null`; missing ticker lists should be `[]`.
- Health output must not imply Mozyfin/KBS fallback availability for SSI-owned data.

## `GET /api/v1/stocks/vn/watchlist`

Purpose:

- Return source-aware watchlist rows for VN tickers.
- Drive the VN market dashboard selected ticker, daily data, live availability, and source status.

Common params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `tickers` | Comma-separated VN symbols | Example: `FPT,VPB,MSB`. |
| `force_refresh` | Bypass normal cache freshness checks | Does not change provider ownership. |
| `include_intraday` | Request intraday section if supported | Stale/mismatched intraday must be unavailable. |

Response sections:

- Daily OHLCV fields from SSI DailyOhlc.
- DailyStockPrice enrichment from SSI DailyStockPrice.
- Intraday section from SSI IntradayOhlc.
- Realtime snapshot status/object.
- Trade tape status/list.
- Order book status/object.
- News status/list.
- Source/cache/diagnostics metadata.
- data_quality_summary with canonical price source, checks, and user-safe issues.
- Additive request-completeness counters: `requested_tickers_count`, `returned_rows_count`, and `missing_tickers`.

Current symbol foreign flow:

- `GET /api/v1/stocks/vn/foreign-flow/current/{ticker}` returns the process-shared SSI V3 `ForeignRoomMessage` snapshot as `waiting`, `ready`, `stale`, `market_closed`, `unavailable`, or `error`.
- The route may idempotently ensure the ticker on an already running shared stream manager; it never owns the WebSocket. Repeated reads and `force_refresh=true` do not duplicate subscriptions.
- Responses use `Cache-Control: no-store, no-cache, max-age=0` and `Pragma: no-cache`. `force_refresh` re-reads the shared cache only.
- `current` remains null until a usable gross value or volume pair arrives. Explicit provider zero remains zero; missing values remain null. DailyStockPrice comparison data stays separate and completed-session authoritative.

Source ownership:

- `latest_price`, daily close, chart-compatible OHLCV: SSI DailyOhlc.
- Reference, ceiling/floor, matched/put-through, latest foreign flow: SSI DailyStockPrice.
- Intraday: SSI IntradayOhlc.
- Realtime snapshot: SSI realtime contract when usable.
- Trade tape: SSI trade-tape contract when usable.
- Order book: SSI `X-QUOTE:{symbol}` stream context when usable.
- Foreign room: SSI `R:{symbol}` stream context when usable.
- Trading session/status: SSI `F:{symbol}` stream context when usable.
- Market index pulse: SSI `MI:{index_code}` stream context when usable.
- News: disabled now; future separate provider.

Null/empty rules:

- `intraday_pulse = null` when unavailable/stale.
- `intraday_candles = []` when unavailable/stale/no usable rows.
- `realtime_snapshot = null` when unavailable.
- `trade_tape = []` when unavailable/no rows.
- `order_book = null` when unavailable/no usable `X-QUOTE` row. A stale but usable cached `X-QUOTE` row may still return an `order_book` object with `is_stale=true` and `order_book_status.status=stale`.
- `foreign_room = null` when unavailable/no usable `R` row.
- `session_status = null` when unavailable/no usable `F` row.
- `news = []` while disabled or unavailable. `VN_NEWS_PROVIDER=vnstock_news` returns an explicit `news_status` gate with `status=unavailable` and `reason_code=blocked_pending_terms`; it does not fetch articles.
- `GET /api/v1/stocks/vn/company-news?ticker=FPT` is selected-ticker-only for the optional Community mode and returns at most three rows. `raw_url` preserves the upstream string; `url` is a validated absolute HTTP(S) URL or `null`, so clients must never link `raw_url` directly.

Implemented contract notes:

- Watchlist `trade_tape` is public list data. It returns `[]` when unavailable/no rows and trade rows when usable.
- Realtime/trade-tape/order-book/foreign-room/session-status messages are short and user-safe. Sanitized provider details appear under sectioned diagnostics such as `diagnostics.realtime`, `diagnostics.trade_tape`, `diagnostics.order_book`, `diagnostics.foreign_room`, or `diagnostics.session_status`.
- SSI trade tape rows are populated only from the background streaming X-TRADE event buffer when parsed rows exist for a bootstrapped symbol. Startup-owned streaming subscribes to `X-TRADE:{symbol}` when trade tape is enabled. Buffered rows can be returned even when stream freshness is stale; diagnostics retain stale/cache age details while row visibility is driven by the presence of real timestamped trade rows. Rows may include `side`, `side_label`, `side_if_available`, `change`, and `change_pct`; observed raw side codes `BU` and `SD` map to `buy` and `sell`, `side_if_available` preserves the raw value, and `side` comes only from explicit X-TRADE side/aggressor fields. `change` is trade price versus SSI DailyStockPrice reference. Request handlers do not start streams, add subscriptions, use all-market channels, or probe unverified REST candidate names.
- SSI `X-QUOTE:{symbol}` rows are populated only from the background streaming order-book cache. Watchlist rows may include `order_book_source`, `order_book`, and `order_book_status`; level rows require positive price and nonnegative volume, malformed levels are dropped, and no fake bid/ask rows are synthesized. Stale cached rows remain visible as last-known ladders with stale status/age diagnostics instead of being converted to `order_book=null`. `X-QUOTE` rows do not create realtime quotes, trade-tape rows, session/status rows, DailyOhlc rows, DailyStockPrice enrichment, or `latest_price`.
- SSI `R:{symbol}` rows are populated only from the background streaming foreign-room cache. Watchlist rows may include `foreign_room_source`, `foreign_room`, and `foreign_room_status`; room/volume/value fields require nonnegative numeric values, malformed fields are null/dropped, and no fake foreign-room values are synthesized. `R` rows do not create realtime quotes, trade-tape rows, order-book rows, session/status rows, DailyOhlc rows, DailyStockPrice enrichment, or `latest_price`. Foreign buy/sell value semantics remain `needs_semantics_proof`.
- SSI `F:{symbol}` rows are populated only from the background streaming session/status cache. Watchlist rows may include `session_status_source`, `session_status`, and `session_status_status`; raw `trading_session` and `trading_status` values are preserved without mapping business meanings. `F` rows do not create realtime quotes, trade-tape rows, DailyOhlc rows, DailyStockPrice enrichment, or `latest_price`.
- SSI `MI:{index_code}` rows are populated only from the background streaming market-index cache. `GET /api/v1/stocks/vn/market-index-pulse` may include `market_index_pulse_source`, `market_index_pulse`, and `market_index_pulse_status`; malformed numeric fields are null/dropped, and no fake index values are synthesized. `MI` rows do not create stock watchlist rows, realtime quotes, DailyIndex rows, DailyOhlc rows, DailyStockPrice enrichment, or `latest_price`. Channel/field semantics remain `needs_live_proof`.
- Intraday cadence fields are public: `intraday_requested_timeframe` is the request hint, `intraday_actual_granularity` / `intraday_actual_granularity_seconds` describe detected regular provider spacing, and `intraday_cadence_status` is `matched`, `different_from_requested`, `irregular`, `unknown`, or `unavailable`.
- Intraday unavailable status may include sanitized diagnostics such as `failure_class`, `endpoint=IntradayOhlc`, HTTP status, provider code, requested timeframe, internal page size, public limit, usable row count, date match, and cadence status.
- DailyOhlc and DailyStockPrice can disagree on same ticker/date.
- `daily_stock_price` exposes `status`, `quality_status`, `source=SSI DailyStockPrice`, `date`, `date_match`, `staleness_reason`, normalized enrichment fields, `missing_fields`, value-specific `units`, and sanitized diagnostics.
- `indicators.foreign_net_5d_latest_available`, `indicators.foreign_net_20d_latest_available`, `indicators.foreign_net_latest_available_date`, and `indicators.foreign_net_history_count` are populated from the same bounded per-symbol DailyStockPrice recent window when enough returned `foreign_net_volume` rows exist.
- Top-level compatibility fields are `daily_stock_price_date`, `daily_stock_price_date_match`, and `daily_stock_price_staleness_reason`. A mismatch never changes `latest_price` or the daily row status.
- Row-level partial-data issue codes can include `daily_ohlcv_missing`, `daily_stock_price_missing`, `ta_insufficient_history`, `rsi_missing`, `ma_state_insufficient_data`, `foreign_flow_missing`, `provider_empty`, and `provider_error`. They explain missing display cells without synthesizing values or changing `latest_price`.

Future changes:

- Phase 1: keep dashboard top aggregates tied to the latest successful complete watchlist response; incomplete refreshes and auxiliary responses must not update summary cards.
- Phase 2 cleanup: live public contract uses `null`/`[]` for missing data and keeps endpoint/http details in diagnostics.
- Phase 3: ensure company detail consumes the same contract consistently.

## `GET /api/v1/stocks/vn/chart`

Purpose:

- Return selected-symbol daily OHLCV chart data for the VN dashboard.
- Keep chart candles aligned with the configured VN chart provider, currently SSI DailyOhlc for SSI-owned daily data.

Common params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `symbol` | VN symbol | Example: `FPT`. |
| `range` | Chart range | Current accepted labels are `1M`, `3M`, `6M`, and `1Y`. |

Response rules:

- Chart candles are daily OHLCV data, not realtime matched prices.
- Missing candles return `[]`.
- Chart unavailability should not be filled from realtime, intraday, Mozyfin, or KBS data.

## Vietnam index endpoints

### `GET /api/v1/stocks/vn/index-list`

Returns SSI IndexList `rows` with `index_id`, `index_code`, `index_name`, `exchange`, `market`, `source`, `missing_fields`, and `field_coverage`. The response includes `status`, `source`, `count`, `fallback_used=false`, and sanitized `diagnostics`. SSI-returned rows remain authoritative even when the requested market filter is not strict.

### `GET /api/v1/stocks/vn/daily-index`

Accepts comma-separated `index_codes` (default `VNINDEX,VN30`), optional `from_date`/`to_date`, bounded `limit`, and `force_refresh`. Each returned latest row may include index value, change/percent, volume/value, matched/put-through fields, breadth counts, session, exchange, date/date-match, source, missing fields, and field coverage.

Unavailable indexes do not produce placeholder rows. Overall status is `ok`, `partial`, or `unavailable`; `rows=[]` when no requested index has usable SSI data.

### `GET /api/v1/stocks/vn/market-index-pulse`

Accepts comma-separated `index_codes` (default `VNINDEX,VN30,HNX,UPCOM`) and reads only the process-local SSI streaming `MI:{index_code}` cache. The response includes `market_index_pulse_source`, `market_index_pulse`, `market_index_pulse_status`, `requested_index_codes`, `count`, `fallback_used=false`, and sanitized `diagnostics.market_index_pulse`.

Usable rows may include `index_code`, `exchange`, `index_value`, `estimated_index_value`, `change`, `change_pct`, `total_trades`, `total_volume`, `total_value`, `advances`, `unchanged`, `declines`, trading date/time, stream timestamp, cache age, and `channel_format_status=value_semantics_status=needs_live_proof` until live evidence proves exact SSI semantics. The endpoint does not start streams, add dynamic subscriptions, use `ALL`, replace REST DailyIndex, or populate stock watchlist rows.

### `GET /api/v1/stocks/vn/index-components`

Uses the explicit normalized `index_code` to call SSI IndexComponents directly. SSI IndexList remains separate discovery/diagnostic context and does not block an explicit component request. Returns real SSI component rows and count when available; otherwise `status=unavailable` and `rows=[]`. Successful results are process-cached for 300 seconds; unavailable/rate-limited/no-row results are negatively cached for 60 seconds. Missing optional name/weight/exchange fields remain null. The endpoint never supplies hardcoded VN30 membership or another-provider fallback.

## `GET /api/v1/stocks/vn/company/{ticker}`

Purpose:

- Return company-detail snapshot for one VN ticker.
- Reuse SSI-backed market data while grouping profile, price, trading stats, live availability, future modules, and diagnostics.

Path params:

| Param | Meaning |
| --- | --- |
| `ticker` | VN symbol, for example `FPT`. |

Common query params:

| Param | Meaning |
| --- | --- |
| `force_refresh` | Bypass normal cache freshness checks for the snapshot. |

Response sections:

- Header/profile.
- Price summary.
- Trading stats.
- DailyStockPrice enrichment.
- Foreign flow.
- Technical snapshot.
- Intraday.
- Realtime.
- Trade tape.
- News when a configured provider returns usable items. Fundamentally unsupported financials/events are retained as nullable compatibility fields but hidden from the product page.
- Source coverage and diagnostics.
- data_quality_summary reused from the SSI-backed watchlist row.

Source ownership:

- Daily core values align with SSI DailyOhlc canonical source for shared watchlist/company fields.
- Company `price.source` and `price.canonical_source` identify the actual SSI daily source selected by the market service. Fresh DailyOhlc remains preferred; an explicitly degraded newer DailyStockPrice selection keeps that source label. `price.reference_source` identifies `SSI DailyStockPrice` for reference, ceiling, and floor fields.
- Company `trading_stats` uses SSI DailyOhlc daily open/high/low/close/volume/value.
- Reference/limits, foreign flow, matched/put-through, and adjusted-close values use SSI DailyStockPrice when exposed.
- Company `daily_stock_price` retains the source-specific enrichment block and date-match metadata. Foreign flow declares shares for volume and VND for value.
- Profile metadata uses exact-symbol V3 `securitiesByBoard?symbol=` when available, including ICB industry/sector only when SSI returns a mapped metadata field.
- `profile.status` reports availability. `profile.quality_status`, `profile.completeness`, `profile.missing_fields`, and `profile.field_coverage` report completeness independently.

Null/empty rules:

- `intraday.candles = []` and `intraday.pulse = null` when intraday is unavailable.
- `intraday.requested_timeframe` is a request hint; `intraday.actual_granularity`, `intraday.actual_granularity_seconds`, and `intraday.cadence_status` describe the detected provider-returned cadence when available.
- `realtime_snapshot = null` when unavailable.
- `trade_tape = []` when unavailable/no rows.
- Live-section diagnostics may include additive SSI streaming lifecycle fields such as `stream_health`, holiday-unaware `market_session` fields, `last_message_at`, `last_message_age_seconds`, `last_reconnect_at`, `last_reconnect_reason`, `reconnect_count`, `last_reconnect_error`, `subscription_count`, `expected_subscription_count`, and per-context observed-row counters. These fields are diagnostics only; they do not start streams, add subscriptions, or alter daily price ownership.
- Future module lists stay empty while not implemented/unavailable.
- Missing optional DailyStockPrice and foreign-flow metrics remain null and are not rendered as zero.
- Missing optional profile fields remain null. Profile unavailability does not clear usable DailyOhlc or DailyStockPrice sections.

Implemented contract notes:

- Company intraday unavailable shape is `status = unavailable`, `candles = []`, and `pulse = null`.
- Company `intraday.diagnostics` is optional and diagnostic-only; it may include sanitized SSI IntradayOhlc failure classification such as `rate_limited` without raw provider payloads or secrets.
- Profile can have `name = null` and `industry = null` while provider status is `ok`; this is provider OK plus `quality_status = partial`.
- Profile fields include symbol, name/name_en, exchange, market, industry, sector, security type, issuer, lot size, listed shares, and listed date. Unsupported values remain null. `source_endpoint`, `provider_version`, `fetched_at`, `cache_status`, `data_state`, and `failure_class` expose sanitized lineage.
- Company price and trading stats now align shared daily values with SSI DailyOhlc; remaining numeric differences versus DailyStockPrice are intentional when fields are explicitly labeled as reference, matched, put-through, adjusted, or foreign-flow values.
- News renders only when a configured provider returns items. Financials/events/corporate-action compatibility fields may remain typed `not_implemented`, but unsupported empty cards are hidden. `not_implemented` is allowed for future modules, not live-provider statuses.

Future changes:

- Phase 1: add Data Quality Summary above detailed cards.
- Phase 2 cleanup: frontend renders normalized null/list live contracts and keeps diagnostics lower priority.
- Phase 3: redesign page into data-quality report layout.

## `GET /api/v1/stocks/vn/observability`

Purpose:

- Expose provider/cache/runtime status for debugging the VN dashboard.
- Help distinguish daily SSI availability from optional live-section failures.

Params:

- No required params documented for current use.

Response sections:

- SSI core status.
- SSI intraday status.
- SSI realtime status.
- SSI trade-tape status.
- Disabled Mozyfin status.
- Legacy KBS status.
- Cache/single-flight/dashboard runtime counters.

Source ownership:

- Observability reports runtime state; it does not own market data.

Null/empty rules:

- Disabled provider blocks should be concise and should not contain active counters from other providers.
- Provider unavailable is separate from cache error.

Current known caveats from handoff snapshots:

- Observability currently reports SSI realtime/trade tape unavailable in the local smoke context.
- Diagnostics must remain sanitized and secret-free.

Future changes:

- Phase 2: align diagnostics structure with public/live status split.
- Phase 4: add clearer retryability/backoff observability for realtime/trade-tape endpoint investigation.

## `GET /api/v1/stocks/vn/index-list`

Purpose:

- Return SSI FastConnect index identifiers for VN index metadata discovery.
- Support index coverage diagnostics without hardcoded index lists.

Common params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `market` | Optional market/exchange filter | Examples: `HOSE`, `HNX`, `UPCOM`. |

Response rules:

- Index rows should come from SSI when available.
- Missing index rows return `[]` with an unavailable or empty state as appropriate.
- Do not substitute Mozyfin/KBS index metadata.

## `GET /api/v1/stocks/vn/index-components`

Purpose:

- Return SSI index component rows when available.
- Support VN30/index coverage diagnostics without hardcoded constituents.

Common params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `index_code` | SSI index code | Example: `VN30`. |

Response sections:

- Index code/status/source.
- Component rows when SSI returns usable data.
- Unavailable status and sanitized diagnostics when SSI does not return rows.
- `index_code=...` is the documented query parameter; `index=...` remains accepted as a backward-compatible alias.

Source ownership:

- SSI IndexComponents owns component rows when available.
- Explicit `index_code` is sent directly through the verified SSI `indexCode` parameter. IndexList is not a prerequisite for this endpoint.
- Normal responses use a process cache keyed by SSI provider, endpoint, normalized index code, and normalized optional market. `force_refresh=true` bypasses that cache intentionally.
- No Mozyfin/KBS fallback.

Null/empty rules:

- Component lists should be `[]` when no usable SSI rows exist.
- Status should be `unavailable` when provider request fails or returns no usable rows.

Current known caveats from handoff snapshots:

- Phase 4.4B proved exact VN30 component rows through SSI `indexCode=VN30`; those rows are usable only when SSI returns an exact provider row and real nested members.
- Any missing identifier, mismatched outer index, empty nested list, or provider failure still returns `rows=[]` with concise unavailable state and no hardcoded members.

Future changes:

- Phase 1: include index component missingness in Data Quality Summary only when relevant.
- Phase 2: keep endpoint/http details in diagnostics.

## `GET /api/v1/stocks/vn/corporate-actions`

Purpose:

- Return explicitly sourced VN corporate-action events when a verified provider is configured.
- Keep unsupported event data separate from SSI market-data health.

Common params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `tickers` | Optional comma-separated VN symbols | Defaults to configured VN watchlist. |
| `months_back` | Recent historical window | Current route bounds are 1 to 24 months. |

Response rules:

- Corporate actions remain disabled, not configured, unavailable, or not implemented until a verified structured source exists.
- Missing event lists return canonical `events=[]` and the backward-compatible alias `items=[]`.
- `items` is compatibility-only and is derived from `events`; clients should read `events` first.
- The response includes sanitized `source`, `provider`, and `diagnostics` fields for the provider contract state.
- Normalized rows may include event dates, dividend/rights/split values, source URLs/documents, provider event IDs, and missing-field metadata when a future authorized provider supplies them.
- Do not infer dividends, rights, splits, or adjustment events from price/reference gaps.
- Disabled or failed provider states do not affect SSI daily data or `latest_price`.

## `GET /api/v1/stocks/vn/foreign-flow/symbol/{ticker}`

Purpose:

- Return bounded historical foreign buy/sell/net volume and value for exactly one VN symbol from SSI DailyStockPrice.
- Provide latest-row and 5/20/60-session summaries without joining price, realtime, foreign-room, ranking, or aggregate data.

Query modes:

| Mode | Parameters | Bounds |
| --- | --- | --- |
| Recent sessions | Optional `limit` | Defaults to 20; 1 to 120. |
| Date range | `from_date` and `to_date` | Both required, inclusive ISO dates, maximum 168 calendar days; cannot include `limit`. |

Response rules:

- Source/finality constants are `ssi_fastconnect`, `daily_stock_price`, shares, VND, and `daily_available`.
- Rows are ascending and unique by provider trading date; the last valid duplicate wins and missing dates are not synthesized.
- Direct net fields are preferred. Buy-minus-sell fallback requires both non-null sides; direct mismatches are preserved and counted, not overwritten.
- Window sums are null when no row contributes and expose contributing, positive, negative, zero, null, covered, and completeness counts.
- Empty periods return HTTP 200 with `rows=[]`; invalid ticker/query shape returns HTTP 422; unavailable provider state is sanitized and may use bounded stale positive cache recovery.
- Cache and same-key coalescing are process-local. `force_refresh` bypasses fresh reuse but may join an identical in-flight fetch.

## `POST /api/v1/stocks/vn/foreign-flow/batch`

Purpose:

- Return daily foreign-flow summaries and watchlist-scoped rankings for 1 to 30 normalized unique VN symbols in one request.

## `GET /api/v1/stocks/vn/foreign-flow/vn30`

- Query: `top_n=1..10` (default 10), `force_refresh=false|true`, and additive
  `recovery_trigger=route_touch|visibility_resume|manual_refresh`.
- Uses exact SSI IndexComponents `VN30` membership and SSI DailyStockPrice only; no IndexList prerequisite, hardcoded members, or fallback.
- Returns current-membership identity/disclosure, at most 60 observed dates, aligned latest/5/20/60 buy/sell/net value and volume, separate family coverage/breadth, member summaries, deterministic ranking pairs, cache/single-flight metadata, and bounded timing.
- A cold membership-unavailable state is HTTP 200 typed `unavailable` with empty series/components/rankings and no component-history work. A failed refresh may retain the last validated SSI membership and return partial usable completed data with explicit retained/age/failure diagnostics.
- Reuse the Phase 4.12B SSI DailyStockPrice symbol service with a 60-session window; no price joins, realtime/current-session fields, foreign-room data, or market-wide aggregate are returned.

Request body:

```json
{"tickers":["FPT","VCB"],"top_n":5,"force_refresh":false}
```

`top_n` is 1 to 10. Symbols are trimmed, uppercased, deduplicated by first occurrence, and returned in stable normalized request order. Invalid syntax, wildcards, `ALL`, an empty normalized list, or more than 30 unique symbols returns HTTP 422.

Response rules:

- Every normalized requested symbol has one result, including typed `empty` or `unavailable` results; one symbol failure does not fail the batch.
- Each `rows[]` result carries latest buy/sell/net volume and value plus 5-session/20-session cumulative net volume/value, coverage/completeness, `data_state`, freshness, source, and `daily_available` finality. Missing values remain null and explicit zero remains zero.
- Top-level counts distinguish fresh, stale, empty, and unavailable symbols. Coverage is usable (`ready` or retained `stale`) divided by normalized symbols; `ready` requires complete fresh coverage.
- Rankings contain `latest_net_value`, `net_value_5d`, and `net_value_20d` `top_buy`/`top_sell` lists, sort by signed net value with ticker as the deterministic tie-break, and exclude null and zero. Eligible stale or incomplete rows remain visible with their trust metadata.
- The endpoint uses bounded concurrency capped at four. The underlying symbol service may make its existing bounded expanding-date attempts on a cold miss; batch execution adds no separate ranking fetch.

## Planned `GET /api/v1/stocks/vn/news`

Status: planned only. No route, provider adapter, credentials, config flag, scraping path, or fallback provider is implemented in Phase 5.1A.

Purpose:

- Return licensed, source-labeled VN market and ticker/company news after a future `NewsProvider` entitlement gate passes.
- Keep news separate from SSI-owned market data.

Potential params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `ticker` | Optional normalized VN symbol | Example future shape: `/api/v1/stocks/vn/news?ticker=FPT`. |
| `category` | Optional normalized category | Examples: company, market, macro, industry, policy, earnings, corporate actions, disclosure. |
| `language` | Optional language filter | Provider support must be verified. |
| `limit` | Bounded item count | Exact bounds require future contract proof. |

Planned response rules:

- Current default remains `news=[]` with `news_status.status=disabled`. The explicit production Vnstock News gate returns `unavailable` plus `blocked_pending_terms` without calling the package.
- Local personal mode may return bounded `Vnstock News` rows only when `VN_NEWS_PROVIDER=vnstock_news_personal` and `VNSTOCK_NEWS_PERSONAL_ENABLED=true`; package-missing or fetch failures return explicit unavailable reason codes and do not affect SSI market-data rows.
- Future usable rows should include item ID, title, summary when allowed, source, source URL when available, published timestamp, tickers, market, category, language, provider, provider item ID, ingestion timestamp, and nullable sentiment/importance only if provider methodology is licensed.
- News failure must not affect SSI DailyOhlc, DailyStockPrice, intraday, realtime, trade tape, index, or metadata sections.
- Public RSS, public web pages, browser scraping, and unofficial endpoints are not accepted as production providers without explicit terms approval.

## `GET /api/v1/stocks/vn/realtime`

Purpose:

- Return SSI realtime/snapshot quote rows when the SSI live contract is usable.
- Otherwise return an explicit SSI unavailable/disabled state without changing daily close semantics.

Common params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `tickers` | Comma-separated VN symbols | Required by current route. |

Response rules:

- Realtime output is optional and not a substitute for SSI DailyOhlc.
- Missing quote lists return `[]`; embedded unavailable snapshot objects should be `null`.
- SSI realtime is a FastConnect streaming contract. The backend has parser/cache coverage for buffered `X` quote snapshots, `X-QUOTE` order-book rows, `R` foreign-room rows, `MI` market-index rows, `X-TRADE` trade rows, and separate `F` session/status messages, plus an official-client adapter behind the disabled streaming runtime flag and FastAPI startup bootstrap behind `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS`. `X-QUOTE`, `R`, `MI`, `X-TRADE`, and `F` rows are separate live contexts and do not populate this endpoint's quote list.
- Request handlers do not open streams, start managers, or add dynamic ticker subscriptions. When `SSI_STREAMING_REALTIME_ENABLED=false`, the endpoint returns unavailable with reason `SSI streaming realtime manager disabled.` even if old cache data exists.
- When streaming is enabled, this endpoint may read only from a running process-local manager and fresh cache rows created by startup bootstrap. Disabled, empty-bootstrap-symbols, incomplete-config, package-unavailable, not-started, empty-cache, stale-cache, and manager-error states remain unavailable with `realtime_snapshot=null`; safe manager/cache details belong in diagnostics.
- The endpoint bypasses the generic VN response cache and returns no-store response headers so process-local streaming cache updates can surface on the next poll. Streaming cache TTL and per-row `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, and `cache_ttl_seconds` remain the freshness contract.
- Runtime diagnostics may include `stream_health`, holiday-unaware `market_session` fields, `runtime_status`, `manager_state`, `messages_observed`, `parser_rows_observed`, idle fields, reconnect counters, next reconnect time, current backoff, and sanitized error summaries. `running_idle`, `market_closed`, `idle_market_closed`, and `after_hours_stale` are realtime runtime diagnostics and do not imply daily SSI data failed.
- Reconnect is lifecycle-owned. During active Vietnam trading/auction windows the monitor may reconnect a stale running stream with debounce; outside active windows it must not reconnect solely because X, X-QUOTE, or X-TRADE counters stop advancing. This endpoint does not trigger reconnect, does not start or stop streams, and does not subscribe request tickers outside the bootstrap symbol list.
- Legacy KBS may exist behind explicit development flags, but it is not a normal VN runtime fallback.
- Primary UI should label this section as SSI realtime or realtime snapshot, not KBS.

## `GET /api/v1/stocks/vn/realtime/trades`

Purpose:

- Return SSI trade-tape rows when the SSI trade-tape contract is usable.
- Otherwise return an explicit SSI unavailable/disabled state.

Common params:

| Param | Meaning | Notes |
| --- | --- | --- |
| `symbol` | VN ticker | Required by current route. |
| `limit` | Maximum trade rows | Current route bounds are 1 to 500. |

Response rules:

- Missing trade rows return `[]`.
- Trade tape is separate from daily OHLCV, intraday OHLCV, and realtime snapshot.
- SSI trade tape is streaming-buffer backed for latest X-TRADE events only. Diagnostics distinguish not-subscribed, disabled, subscribed-empty, stale, cache-hit, and `buffered_rows_available` states. Trade rows use SSI-style matched-order fields: time, B/S side when explicit, volume, price, change, and change percent. Public rows can expose `side`, `side_label`, and raw `side_if_available`; observed `BU`/`SD` codes mean Buy/Sell but side is never inferred from price color or change. True historical time-and-sales remains unverified; endpoint/http details belong in diagnostics if a future verified source is added.
- Legacy KBS may exist behind explicit development flags, but it is not a normal VN runtime fallback.
- Primary UI should label this section as trade tape, not KBS.

## `GET /api/v1/stocks/vn/foreign-flow/current-aggregate`

Purpose:

- Return display-only current-session foreign-flow totals from the process-owned SSI V3 `ForeignRoomMessage` cache.
- Support `scope=vn30` using current SSI IndexComponents membership, or `scope=watchlist` using only normalized user-selected `tickers`.
- Optionally include current-VN30 ICB groups when `include_industries=true`.

Response rules:

- Responses are no-store and do not start or own a provider connection.
- `provider_session_date` is provider-backed; snapshots from different dates are never mixed.
- `coverage` separates requested, classified, subscribed, observed, complete-volume, complete-value, missing, and stale symbols.
- Missing fields remain null and are excluded from sums; explicit audited provider zero remains zero.
- `display_series` retains source kind, finality, current/completed/partial/stale flags, coverage counts, values, and provider timestamps when available. Top-level `data_state` remains the aggregate current state that clients propagate into display models.
- `display_series`, `display_windows`, `rankings`, `items`, and `groups` are provisional presentation data. Numeric completeness and coverage do not promote them to accepted data, and they do not mutate completed DailyStockPrice history.
- Accepted DailyStockPrice for the same date has precedence. Proprietary flow is not part of this route.
- Optional `recovery_trigger=route_touch|visibility_resume|manual_refresh`
  identifies the bounded recovery cause. It does not start a stream.
- Retryable membership/authentication failure may return a partial usable
  response built from retained SSI membership, accepted completed history, and
  stale process-owned snapshots. Diagnostics disclose retention, age, refresh
  failure, cache bypass, and recovery state. A cold state remains unavailable.
