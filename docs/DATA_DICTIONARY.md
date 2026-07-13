# VN Data Dictionary

## Purpose

This dictionary defines the public and UI-relevant fields used by the VN dashboard and company detail page. It should be read with `docs/VN_DATA_CONTRACT.md`, `docs/API_CATALOG.md`, and `docs/UI_STATES.md`.

Conventions:

- Canonical means the dashboard should treat the field as the primary user-facing value for its concept.
- Nullable means the field may be `null` or absent when source data is unavailable.
- Missing lists should be `[]`.
- Missing objects should be `null`.
- Diagnostics fields are for debugging and should not become primary metric rows.
- Frontend display formatting is UI-only. Raw API price fields remain VND/share numeric values; VN price-like fields are displayed in board-style thousand-VND units with two decimals and no suffix, for example `72,100` renders as `72.10`. Share-volume fields may render with `K`/`M` suffixes, and VND trading-value fields may render with `K`/`M`/`B`/`T` suffixes. Tooltips/titles may expose the raw VND or share count.
- Frontend directional coloring is UI-only. Daily/latest price and `price_vs_reference_pct` are colored by comparing SSI DailyOhlc close/latest price with SSI DailyStockPrice `reference_price`, `ceiling_price`, and `floor_price`: ceiling is purple/magenta, floor is blue/cyan, reference/equal is dedicated yellow, above reference is green, below reference is red, and missing/non-positive inputs are neutral. Trade-tape zero change uses the same reference yellow. Raw API values and field ownership do not change.

## Stock Detail Panel Availability Summary

The stock-detail screenshot labels map to the current dictionary as follows. This is documentation-only: it does not add fields or authorize fallback data.

| Screenshot label | Dictionary/current field | Current status | Source / note |
| --- | --- | --- | --- |
| Open | `open`, company `trading_stats.open`, chart `points[].open` | Available now | SSI DailyOhlc daily/session open; nested `daily_stock_price.open` may also exist as DailyStockPrice enrichment. |
| Average | `realtime_snapshot.average_price` placeholder | Ambiguous, needs provider confirmation | Schema/type exists for optional realtime, but current SSI mapping does not populate it. |
| Matched val | `daily_stock_price.matched_value`, `ssi_matched_value` | Available now | SSI DailyStockPrice. |
| PT val | `daily_stock_price.put_through_value`, `ssi_put_through_value` | Available now | SSI DailyStockPrice. |
| High 52W | `indicators.high_52w`, company `technical.high_52w` | SSI-derived implemented | Calculated from SSI DailyOhlc high history; null when fewer than 120 usable high/low rows are available. |
| Avg. vol. 3M | `indicators.avg_volume_3m`, company `technical.avg_volume_3m` | SSI-derived implemented | Calculated from up to 63 SSI DailyOhlc volume rows; null below 30 usable rows. |
| Avg. vol. 10D | `indicators.avg_volume_10d`, company `technical.avg_volume_10d` | SSI-derived implemented | Calculated from 10 SSI DailyOhlc volume rows; null below 10 usable rows. |
| EPS (TTM) | none | Not available / future provider required | Future fundamentals provider. |
| P/E (TTM) | none | Not available / future provider required | Future ratios/fundamentals provider. |
| P/B | none | Not available / future provider required | Future ratios/fundamentals provider. |
| Beta | none | Deferred pending SSI index methodology | Do not default to external provider; requires SSI index input and documented beta method, or a later explicit source-labeled provider decision if SSI cannot support it. |
| FR. buy vol | `daily_stock_price.foreign_buy_volume`, `foreign.buy` | Available now | SSI DailyStockPrice shares quantity when present. |
| FR. sell vol | `daily_stock_price.foreign_sell_volume`, `foreign.sell` | Available now | SSI DailyStockPrice shares quantity when present. |
| FR. room | `foreign_room.current_room` / `foreign_room.total_room` | SSI R streaming cache | Optional watchlist live context. Separate from DailyStockPrice daily foreign flow; value/unit semantics remain `needs_semantics_proof`. |
| PT vol | `daily_stock_price.put_through_volume`, `ssi_put_through_volume` | Available now | SSI DailyStockPrice. |
| Low 52W | `indicators.low_52w`, company `technical.low_52w` | SSI-derived implemented | Calculated from SSI DailyOhlc low history; null when fewer than 120 usable high/low rows are available. |
| Outs. qty | `symbol_metadata.listed_shares`, `listed_shares`, profile `listed_shares` | Ambiguous, needs provider confirmation | Current field is listed shares/provider share-count metadata; do not relabel as exact outstanding quantity without provider confirmation. |
| Market cap | none | Deferred pending share-basis verification | Do not compute from `latest_price * listed_shares` until share-count semantics and product behavior are designed. |
| Dividend ratio | future `events[].stock_dividend_ratio` / `cash_dividend_per_share` contract only | Not available / future provider required | CorporateActionsProvider is disabled/not configured by default. |
| Next div. date | future event `ex_date`, `record_date`, `payment_date` contract only | Not available / future provider required | No verified corporate-action rows today. |
| ROE | none | Not available / future provider required | Future financial statements/fundamentals provider. |
| ROA | none | Not available / future provider required | Future financial statements/fundamentals provider. |

## Price And Daily Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `latest_price` | Canonical dashboard latest daily price | SSI DailyOhlc close | VND | yes | yes | Watchlist, selected ticker header, company hero | Can differ from DailyStockPrice close; Phase 1 should surface mismatch. |
| `latest_price_source` | Source label for `latest_price` | Service metadata | text | yes | yes | Source badge near latest price | Should identify SSI DailyOhlc when daily data is canonical. |
| `price.source` / `price.canonical_source` | Company price block canonical source | SSI DailyOhlc | text | yes | yes | Company price summary source note | Must not be a mixed DailyOhlc/DailyStockPrice label. |
| `price.reference_source` | Company reference/limit field source | SSI DailyStockPrice | text | yes | no | Company price summary source note | Applies to reference, ceiling, and floor fields only. |
| `latest_price_raw_field` | Raw provider field used for latest price when available | Provider normalization metadata | text | yes | no | Diagnostics only | Must not be used as proof of realtime support. |
| `daily_close` | Daily close value exposed by watchlist/company contract | SSI DailyOhlc | VND | yes | yes | Daily core data | Same semantic owner as `latest_price` when DailyOhlc is valid. |
| `ohlcv_close` | Close from normalized OHLCV row | SSI DailyOhlc | VND | yes | yes | Data Quality Summary/diagnostics | Used to compare with DailyStockPrice close. |
| `daily_stock_price.close` | Close from DailyStockPrice endpoint | SSI DailyStockPrice | VND | yes | no, pending decision | Trading stats or source comparison | Handoff found FPT `2026-06-22` mismatch vs DailyOhlc; Phase 1 must decide company price source alignment. |
| `adjusted_close` | Adjusted close when provider supplies it | SSI DailyStockPrice | VND | yes | no | Trading stats/detail | Do not infer corporate actions from adjusted-close gaps. |
| `reference_price` | Session reference/basic price | SSI DailyStockPrice | VND | yes | no | Daily core data/limits | Separate from canonical latest price. |
| `ceiling_price` | Daily price ceiling | SSI DailyStockPrice | VND | yes | no | Price limit block | Render only when value exists. |
| `floor_price` | Daily price floor | SSI DailyStockPrice | VND | yes | no | Price limit block | Render only when value exists. |
| `daily_stock_price.quality_status` | Enrichment completeness independent of DailyOhlc validity | Service-derived from SSI DailyStockPrice row | `ok`, `partial`, or `unavailable` | no | no | Source coverage/data quality | Partial enrichment must not invalidate a usable DailyOhlc row. |
| `daily_stock_price.date_match` / `daily_stock_price_date_match` | DailyStockPrice date alignment against DailyOhlc | Service-derived | `matched`, `mismatched`, `unknown`, or `unavailable` | no | no | Source coverage/caveat | Missing DailyStockPrice date is `unknown`; request failure/empty rows are `unavailable`. |
| `daily_stock_price.missing_fields` | Normalized enrichment fields that SSI did not supply | Service-derived | list of field names | no | no | Diagnostics/source coverage | Missing is null, not zero. |
| `daily_stock_price.units` | Units for enrichment fields that have values | Service-derived | field-to-unit map | no | no | Diagnostics/UI formatting | Omits null fields so units do not imply availability. |
| `volume` | Daily OHLCV volume | SSI DailyOhlc | shares | yes | yes for daily volume | Daily core data/chart | Can differ from DailyStockPrice matched volume. |
| `matched_volume` | Matched trading volume | SSI DailyStockPrice | shares | yes | source-specific | Trading stats | Handoff FPT example differed from DailyOhlc volume. |
| `matched_value` | Matched trading value | SSI DailyStockPrice | VND | yes | source-specific | Trading stats/liquidity | Keep source label visible. |
| `put_through_volume` | Put-through trading volume | SSI DailyStockPrice | shares | yes | source-specific | Trading stats | Do not fill from DailyOhlc volume. |
| `put_through_value` | Put-through trading value | SSI DailyStockPrice | VND | yes | source-specific | Trading stats | Null remains unavailable; provider zero remains zero. |
| `amount` / `value` | Daily trading value/amount from OHLCV or provider | SSI DailyOhlc or normalized source field | VND | yes | source-specific | Chart/daily core | Label source to avoid mixing with matched value. |

## SSI-Derived Metric Fields

These fields are additive Phase 4.8A metrics. They live under watchlist `indicators` and company `technical`, are source-labeled SSI-derived, and never change `latest_price`.

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `high_52w` / `low_52w` | Highest high and lowest low from latest returned 52-week-style history | SSI DailyOhlc high/low history | VND | yes | no | Selected ticker technical context, company technical snapshot | Uses up to 252 returned rows; a usable row needs a valid date plus positive numeric high and low; null when fewer than 120 usable rows exist. |
| `high_52w_date` / `low_52w_date` | Dates of the returned high/low observations | SSI DailyOhlc row dates | date | yes | no | Detail/diagnostics | Null when 52W values are null; a date must not appear without its value. |
| `high_low_52w_history_count` | Usable high/low row count in the 252-row window | SSI DailyOhlc | rows | no | no | Detail/diagnostics | `complete` >=240, `partial` >=120, `insufficient` below 120. |
| `avg_volume_10d` | Ten-row average daily volume | SSI DailyOhlc volume | shares | yes | no | Selected ticker flow context, company technical snapshot | Requires 10 usable numeric volume rows; negative volumes are not usable. |
| `avg_volume_3m` | Three-month approximate average daily volume | SSI DailyOhlc volume | shares | yes | no | Selected ticker flow context, company technical snapshot | Uses up to 63 usable numeric volume rows; `complete` >=60, `partial` >=30, `insufficient` below 30. |
| `price_vs_reference_pct` | Daily close versus reference price percentage | SSI DailyOhlc close plus SSI DailyStockPrice reference | percent | yes | no | Selected ticker price context, company technical snapshot | Null when DailyOhlc close is unavailable/non-positive or reference is missing/non-positive. |
| `daily_range_pct` | Daily high/low range as percentage of close | SSI DailyOhlc high/low/close | percent | yes | no | Selected ticker technical context, company technical snapshot | Formula: `(high - low) / close * 100`; null when high/low/close are incomplete, close is non-positive, or high is below low. |
| `short_term_zones` | Short-term daily support/resistance contract | Derived from SSI DailyOhlc | object | no | no | `/vietnam` indicator table | Uses exactly the latest 60 valid unique D1 rows, ATR14 Wilder/RMA, and five-session pivots. `status=unavailable` with empty arrays when history/ATR is insufficient; never uses realtime or a fallback. |
| `short_term_zones.support[]` / `short_term_zones.resistance[]` | Nearest compact price zones below/above latest daily close | Derived from SSI DailyOhlc | VND | no, empty list when none/unavailable | no | Support / Resistance table columns and optional selected-ticker daily-chart bands | At most two zones per side, nearest first; each item exposes only `lower` and `upper`; zones crossing the latest close are excluded. The chart visualizes existing values only as clipped S1/S2/R1/R2 bands and does not calculate ranges, add requests, or alter the chart scale. |
| `ssi_derived_metrics_status` / `ssi_derived_metrics_source` | Aggregate status/source label for Phase 4.8A metrics | Service-derived from SSI inputs | text | no | no | Source/status copy | Source is `SSI DailyOhlc + SSI DailyStockPrice`. |

## Foreign Flow Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `foreign_buy_volume` | Latest foreign buy volume | SSI DailyStockPrice | shares | yes | source-specific | Foreign flow | Available only if DailyStockPrice returns it. |
| `foreign_sell_volume` | Latest foreign sell volume | SSI DailyStockPrice | shares | yes | source-specific | Foreign flow | Same date alignment should be checked. |
| `foreign_net_volume` | Latest foreign net volume | SSI DailyStockPrice | shares | yes | source-specific | Foreign flow | Null is not zero. |
| `foreign_buy_value` | Latest foreign buy value | SSI DailyStockPrice | VND | yes | source-specific | Foreign flow | Render only when present. |
| `foreign_sell_value` | Latest foreign sell value | SSI DailyStockPrice | VND | yes | source-specific | Foreign flow | Render only when present. |
| `foreign_net_value` | Latest foreign net value | SSI DailyStockPrice | VND | yes | source-specific | Foreign flow | Null is not zero. |
| `foreign_net_5d_latest_available` | Five returned-row net foreign volume summary | SSI DailyStockPrice recent rows | shares | yes | no | Selected ticker foreign flow | Computed only from returned `foreign_net_volume` rows; null when fewer than 5 usable rows exist. |
| `foreign_net_20d_latest_available` | Twenty returned-row net foreign volume summary | SSI DailyStockPrice recent rows | shares | yes | no | Selected ticker foreign flow | Computed only from returned `foreign_net_volume` rows; null when fewer than 20 usable rows exist. |
| `foreign_net_history_count` | Count of recent DailyStockPrice rows with usable foreign net volume | SSI DailyStockPrice recent rows | rows | no | no | Selected ticker foreign flow/diagnostics | Counts provider-returned rows, not an exchange trading calendar. |

## Data Quality Summary Field

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data_quality_summary` | Additive summary of source mismatches, section checks, partial metadata, stale intraday, unavailable optional live sections, and finality/adjustment uncertainty | Service-derived from existing watchlist/company fields | object | no, defaults to `{}` at schema boundary | yes for quality summary, no for price | Data Quality Summary | Must not change `latest_price`; messages are short and must not include endpoint dumps or raw provider errors. |
| `requested_tickers_count` | Count of normalized unique tickers requested by the VN watchlist response | Service-derived from request normalization | count | no | no | Watchlist completeness | Additive diagnostic counter only; duplicates/invalid input are removed before counting. |
| `returned_rows_count` | Count of watchlist rows returned for the VN watchlist response | Service-derived from response rows | count | no | no | Watchlist completeness | Should match requested count for a complete normalized request; does not imply every row is fully available. |
| `missing_tickers` | Normalized requested tickers not represented by any watchlist row | Service-derived from request/response comparison | list | no, empty list when complete | no | Watchlist completeness | Missing tickers should be explicit instead of silently disappearing. |

## News Fields

| Field | Meaning | Source | Nullable | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- |
| `news[]` | Optional source-labeled headline rows | Local Vnstock mode when explicitly selected | no, empty list when unavailable | Selected ticker / company news | Community mode is selected/company-ticker only and capped at three rows; it must not fan out across a watchlist. |
| `news[].raw_url` | Original provider URL string | Vnstock Community | yes | Not normally displayed | Relative values are retained for provenance but never made clickable without a verified safe origin. |
| `news[].url` | Safe absolute article URL | Provider-returned `http`/`https` URL | yes | Clickable title only when present | `null` for a relative/unverified origin, malformed, credentialed, local, `javascript:`, `data:`, `file:`, `ftp:`, or arbitrary protocol-relative URL. |
| `news[].summary`, `author`, `category`, `image_url` | Optional article metadata | Vnstock Community | yes | Only if actually supplied/verified | Current Community contract does not fabricate these fields; `head` is not used pending semantics proof. |
| `news_status.reason_code` | Optional news availability classification | News adapter | yes | Compact section state | Community values include `community_news_ready`, `provider_no_items`, `provider_package_missing`, `provider_timeout`, `provider_error`, and `invalid_ticker`. |

## Status And Quality Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `final_close_status` | Finality of daily close | Service/session/source metadata | enum/classification | yes | yes for finality | Data Quality Summary, daily badge | Current value can be `unknown`; do not imply final close if not confirmed. |
| `adjusted_price_status` | Adjustment metadata availability | Service/source metadata | enum/classification | yes | yes for adjustment caveat | Data Quality Summary | `unknown` means no reliable adjusted-price event semantics. |
| `profile.status` | Provider response status for profile block | SSI Securities/SecuritiesDetails normalization | provider status | yes | no for completeness | Source coverage/diagnostics | May be `ok` while fields are null. |
| `profile.quality_status` | Data-quality classification for profile fields | Service-derived from SSI field coverage | classification | no | yes for UI quality | Header badge/Data Quality Summary | `complete`, `partial`, `unknown`, or `unavailable`; independent of daily validity. |
| `profile.completeness` | Covered metadata fields divided by defined metadata fields | Service-derived | ratio 0..1 | no | yes for UI quality | Source coverage/diagnostics | `0` when metadata is unavailable. |
| `profile.missing_fields` / `profile.field_coverage` | Explicit absent fields and per-field coverage | Service-derived | list/object | no | no | Source coverage/diagnostics | Missing fields stay null and must not be inferred. |

## Live Data Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `intraday_candles` | Usable intraday candles | SSI IntradayOhlc | list of OHLCV candles | no, empty list if unavailable | no | Live availability/chart adjunct | `[]` when unavailable/stale/no usable rows. |
| `intraday_pulse` | Compact intraday summary object | Derived from usable SSI IntradayOhlc | object | yes | no | Live availability/Data Quality Summary | Phase 2.1 normalizes unavailable watchlist/company intraday pulse to `null`. |
| `intraday_requested_timeframe` / `intraday.requested_timeframe` | SSI IntradayOhlc request hint | API query/service config | text | yes | no | Intraday cadence note | Compatibility `intraday_timeframe` has the same request-hint meaning and is not proof of actual candle interval. |
| `intraday_actual_granularity` / `intraday.actual_granularity` | Detected provider-returned candle cadence | Service-derived from sorted provider timestamps | text | yes | no | Intraday cadence badge/note | Values include `1m`, `5m`, `15m`, `30m`, `1h`, `daily-like`, or `unknown`; do not infer when status is unavailable. |
| `intraday_actual_granularity_seconds` / `intraday.actual_granularity_seconds` | Detected regular candle spacing in seconds | Service-derived from sorted provider timestamps | seconds | yes | no | Diagnostics/cadence note | Null for single-row, missing timestamp, or irregular cadence. |
| `intraday_cadence_status` / `intraday.cadence_status` | Relationship between requested timeframe and detected provider cadence | Service-derived classification | enum | yes | no | Intraday cadence note | Values: `matched`, `different_from_requested`, `irregular`, `unknown`, `unavailable`. |
| `intraday_status.diagnostics` / `intraday.diagnostics` | Technical details for unavailable SSI intraday requests | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | May include `failure_class`, `endpoint=IntradayOhlc`, HTTP status, provider code, requested timeframe, internal page size, and public candle limit; never render as primary metrics. |
| `realtime_snapshot` | Realtime snapshot object | SSI FastConnect streaming realtime contract | object | yes | no | Live availability | `null` until SSI streaming messages are connected through a running background manager, parsed, cached fresh, and status is `ok`; parser/cache/adapter tests alone are not live support. |
| `realtime_snapshot.age_seconds` | Age of the process-local streaming cache row at response time | SSI streaming manager cache | seconds | yes | no | Realtime freshness label | Used for labels such as `updated 2s ago`; does not change daily price ownership. |
| `realtime_snapshot.is_stale` / `stale_reason` | Whether the streaming cache row exceeded its TTL and why | SSI streaming manager cache | boolean/text | yes | no | Realtime freshness/status | Stale rows should produce unavailable or stale live-section state rather than fake current metrics. |
| `snapshot_source`, `snapshot_captured_at`, `snapshot_trading_date`, `snapshot_schema_version` | Additive last-known streaming snapshot provenance | Lifecycle-owned normalized SSI cache snapshot | text/date/integer | yes | no | Live freshness/detail state | Present only after a valid restart restore. `snapshot_source=persisted` always pairs with stale state and is replaced by live SSI rows. |
| `realtime_snapshot.cached_at` / `cache_ttl_seconds` | Cache write time and TTL for the process-local realtime row | SSI streaming manager cache | timestamp/seconds | yes | no | Diagnostics/freshness | Frontend may show `stale >15s`; the generic VN response cache is bypassed for `/vn/realtime`. |
| `trade_tape` | Watchlist/company trade tape row list | SSI trade-tape contract | list | no, empty list if unavailable | no | Live availability | Populated only from background X-TRADE event-buffer rows for bootstrapped symbols. Unavailable/no-row state remains `[]`; frontend may perform bounded selected-ticker warm-up refetch while diagnostics show startup/cache-empty states. |
| `trade_tape_status` | Public status/source/message for trade tape | Service status wrapper | object | yes | no | Live availability status | Message should be short; sanitized endpoint/provider details belong under sectioned diagnostics such as `diagnostics.trade_tape`. |
| `trade_tape[].ticker` / `symbol` | Trade-event ticker | SSI X-TRADE buffer | text | yes | no | Trade tape rows | Present when streaming event row is usable. |
| `trade_tape[].price` | Trade-event price | SSI X-TRADE buffer | VND/provider price unit | no for usable row | no | Trade tape rows | Required for a usable buffered trade row. |
| `trade_tape[].volume` | Trade-event volume | SSI X-TRADE buffer `LastVol` | shares | no for usable row | no | Trade tape rows | Required for a usable buffered trade row; this is not DailyStockPrice matched volume. |
| `trade_tape[].timestamp` / `timestamp_display` / `time` | Trade-event time | SSI X-TRADE buffer | timestamp/text | no for usable row | no | Trade tape rows | Required timestamp is parsed from provider trading date/time; display text preserves provider time when present. |
| `trade_tape[].side` / `side_if_available` / `sequence` / `sequence_if_available` / `raw_type` | Optional trade-event metadata | SSI X-TRADE buffer | text | yes | no | Trade tape rows/diagnostics | Missing side or sequence stays null; `raw_type` should be `X-TRADE` for streaming-buffer rows. |
| `order_book` | Optional bid/ask ladder object | SSI X-QUOTE streaming cache | object | yes, null if unavailable | no | Selected ticker order-book section | Populated only from background `X-QUOTE:{symbol}` stream rows. Stale cached rows remain visible as last-known ladders when usable. It must not replace DailyOhlc, realtime snapshot, trade tape, or session/status. |
| `order_book_status` | Public status/source/message for order book | Service status wrapper | object | yes | no | Live availability status | Message should be short. `stale` means last-known levels are visible but not current; missing/cache-empty state stays optional and must not mark the daily row unavailable. |
| `order_book.bids[]` / `order_book.asks[]` | Bid/ask ladder levels | SSI X-QUOTE streaming cache | list of `{level, price, volume}` | no, empty list inside usable object | no | Dashboard/company selected-ticker order-book ladder | Each level requires positive price and nonnegative volume. Malformed or empty levels are dropped and never synthesized. The UI renders dynamic level counts, matches bid/ask sides by `level`, formats prices as board-style thousand-VND values, and shows volumes as full shares. |
| `order_book.age_seconds` / `is_stale` / `stale_reason` / `cached_at` / `cache_ttl_seconds` | Freshness metadata for latest order-book cache row | SSI streaming manager cache | seconds/boolean/text/timestamp | yes | no | Diagnostics/freshness | Stale cache should preserve real last-known levels with stale copy; empty cache remains unavailable. Neither state may create fake levels. |
| `stream_health` / `diagnostics.*.stream_health` | Process-local SSI streaming lifecycle health | SSI streaming manager | enum | yes | no | Diagnostics only | Values include `healthy`, `idle`, `stale`, `reconnecting`, `failed`, `disabled`, `not_started`, `market_closed`, `idle_market_closed`, and `after_hours_stale`. Health depends on latest message age/counters, reconnect state, and the holiday-unaware Vietnam session window, not just subscribed channels. |
| `market_session` / `market_session_active` / `market_session_label` | Holiday-unaware Vietnam market session classification | SSI streaming manager | text/boolean | yes | no | Diagnostics only | Used only to avoid treating normal pre-open, lunch, post-close, after-hours, or weekend stream silence as a transport failure. Active windows include ATO, continuous morning/afternoon, and ATC. |
| `last_message_age_seconds` / `diagnostics.*.last_message_age_seconds` | Age of the latest observed stream message | SSI streaming manager | seconds | yes | no | Diagnostics/freshness | Null means no message has been observed yet. Stale/reconnecting state is optional live context only and does not alter DailyOhlc price ownership. |
| `subscription_count` / `expected_subscription_count` | Current versus expected startup-owned stream channel count | SSI streaming manager | count | yes | no | Diagnostics only | Used for lifecycle diagnostics. Request handlers must not use this to add dynamic channels or broad subscriptions. |
| `reconnect_count` / `last_reconnect_reason` / `last_reconnect_error` | Manager-owned reconnect diagnostics | SSI streaming manager | count/text | yes | no | Diagnostics only | Phase 4.8R uses `stream_stale` when a running stream is quiet past idle timeout and lifecycle still wants streaming. Errors are sanitized. |
| `foreign_room` | Optional foreign-room object | SSI R streaming cache | object | yes, null if unavailable | no | Future foreign-room UI | Populated only from background `R:{symbol}` stream rows. It must not replace DailyOhlc, DailyStockPrice foreign flow, realtime snapshot, trade tape, order book, or session/status. |
| `foreign_room_status` | Public status/source/message for foreign room | Service status wrapper | object | yes | no | Live availability status | Message should be short. Missing/stale/cache-empty state stays optional and must not mark the daily row unavailable. |
| `foreign_room.total_room` / `current_room` | Foreign ownership room metrics | SSI R streaming cache | provider numeric unit | yes | no | Future foreign-room UI | Values must be valid nonnegative numbers. Units/semantics still require live provider proof. |
| `foreign_room.foreign_buy_volume` / `foreign_sell_volume` / `foreign_buy_value` / `foreign_sell_value` | Live foreign trading/room context metrics | SSI R streaming cache | provider numeric unit | yes | no | Future foreign-room UI | Values are parsed only from explicit R fields such as `FBuyVol`, `FSellVol`, `FBuyVal`, and `FSellVal`; no values are inferred from DailyStockPrice or price data. |
| `foreign_room.value_semantics_status` | Foreign-room value caveat | Service/provider status | text | yes | no | Diagnostics/product gating | `needs_semantics_proof` until field units and approximate-value behavior are proven. |
| `session_status` | Optional trading session/status object | SSI F streaming cache | object | yes, null if unavailable | no | Future live context/status section | Populated only from background `F:{symbol}` stream rows. It preserves raw SSI `trading_session` / `trading_status` values and must not replace DailyOhlc, realtime snapshot, or trade tape. |
| `session_status_status` | Public status/source/message for session status | Service status wrapper | object | yes | no | Live availability status | Message should be short. Raw code meanings remain unmapped until proven by live payload evidence. |
| `session_status.trading_session` / `trading_status` | Raw SSI session/status values | SSI F stream | text | yes | no | Future status label input | Values are not interpreted as open/closed/halted/final labels yet. |
| `session_status.age_seconds` / `cached_at` / `cache_ttl_seconds` | Cache age and TTL for the session/status row | SSI streaming manager cache | seconds/timestamp | yes | no | Diagnostics/freshness | Stale or missing rows should show unavailable status, not fake values. |
| `market_index_pulse` | Optional realtime market-index pulse rows | SSI MI streaming cache | list | no, empty list if unavailable | no | Future market pulse UI | Populated only from background `MI:{index_code}` stream rows. It must not replace REST DailyIndex, stock watchlist rows, DailyOhlc, DailyStockPrice, or latest price. |
| `market_index_pulse_status` | Public status/source/message for market-index pulse | Service status wrapper | object | yes | no | Live availability status | Message should be short. Channel and value semantics remain `needs_live_proof` until live evidence confirms them. |
| `market_index_pulse[].index_value` / `estimated_index_value` | Index level from MI row | SSI MI streaming cache | index points | yes | no | Future market pulse UI | Positive numeric values only; malformed values are null/dropped and never synthesized. |
| `market_index_pulse[].change` / `change_pct` | Index point and percent change from MI row | SSI MI streaming cache | points / percent | yes | no | Future market pulse UI | Signed values are allowed. Do not infer sentiment or trading recommendations. |
| `market_index_pulse[].total_volume` / `total_value` / `total_trades` | MI market activity totals | SSI MI streaming cache | count / shares / value after proof | yes | no | Future market pulse UI | Nonnegative numeric values only. Units remain `needs_live_proof`. |
| `market_index_pulse[].advances` / `unchanged` / `declines` | MI breadth counts | SSI MI streaming cache | count | yes | no | Future market pulse UI | Nonnegative numeric values only; do not infer from watchlist rows. |
| `diagnostics.realtime` / `diagnostics.trade_tape` / `diagnostics.order_book` / `diagnostics.foreign_room` / `diagnostics.session_status` / `diagnostics.market_index_pulse` | Technical live-section diagnostics | Service/provider diagnostics | object | yes | no | Collapsible diagnostics only | May include allowlisted endpoint, HTTP status, provider code, failure class, retryable flag, cooldown/backoff, streaming channel/cache status, requested index codes, or sanitized provider summary; never render as primary metrics. |

## Corporate Actions Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `corporate_actions.status` | Availability of the future corporate-actions provider contract | CorporateActionsProvider boundary | enum | no | yes for section state | Corporate actions card/source coverage | Default is disabled; disabled/not-configured/error states do not prove the ticker has no events. |
| `corporate_actions.source` / `provider` | Contract and provider labels | CorporateActionsProvider boundary | text | yes | yes for provenance | Source badge/diagnostics | Future provider names are labels only until a live adapter is authorized. |
| `corporate_actions.events` | Normalized corporate-action event rows | Future external provider | list | no, empty list if unavailable | yes for event list | Corporate actions card/future event overlay | `[]` means no verified rows are available, not verified absence of actions. |
| `corporate_actions.items` | Backward-compatible alias derived from `events` | CorporateActionsProvider boundary | list | no, empty list if unavailable | no | Compatibility/API clients | Cannot diverge from canonical `events`; clients should migrate to `events`. |
| `events[].event_type` | Normalized event type | Future external provider | enum/text | no | yes for event classification | Event row label | Values include cash dividend, stock dividend, bonus share, rights issue, stock split, merger, listing change, meeting, other, and unknown. |
| `events[].announcement_date` / `ex_date` / `record_date` / `payment_date` / `effective_date` | Distinct event dates | Future external provider | date/text | yes | yes when supplied | Event row details | Do not substitute one date for another; missing remains null. |
| `events[].cash_dividend_per_share` / `cash_dividend_currency` | Cash dividend amount and currency | Future external provider | VND or provider currency | yes | source-specific | Event row details | Null is not zero. |
| `events[].stock_dividend_ratio` / `bonus_share_ratio` / `rights_issue_ratio` / `rights_issue_price` / `split_ratio` | Stock dividend, bonus, rights, issue price, and split terms | Future external provider | ratio/VND | yes | source-specific | Event row details | Do not derive ratios from price gaps or reference-price changes. |
| `events[].source` / `source_url` / `source_document_url` / `provider_event_id` | Provenance and provider identity | Future external provider | text/url | yes | yes for auditability | Event row source note/diagnostics | Future adapters must retain provenance; raw provider bodies stay out of public responses. |
| `events[].missing_fields` | Normalized optional fields absent from the provider row | Service/provider normalization | list | no | no | Diagnostics/source coverage | Missing fields should not be rendered as fake metric rows. |
| `corporate_actions.diagnostics` | Sanitized provider diagnostics | CorporateActionsProvider boundary | object | no | no | Collapsible diagnostics only | May include provider, request domain, status, row count, failure class, last checked time, and requested ticker count only. |

## Diagnostics Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `diagnostics.realtime` | Technical details for realtime snapshot attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | May include REST unsupported state, streaming disabled/configuration-incomplete/package-unavailable/not-started/cache-empty/cache-stale/cache-hit/manager-error state, parsed row counts, manager/cache labels, subscribed channel names, and sanitized error summary. |
| `runtime_status` / `diagnostics.runtime_status` | Process-local SSI streaming manager runtime state | SSI streaming lifecycle manager | enum | yes | no | Diagnostics/freshness only | Values include `disabled`, `not_started`, `starting`, `running`, `running_idle`, `reconnecting`, `errored`, `stopped`, and `shutdown`. `running_idle` does not change daily SSI validity. |
| `diagnostics.is_idle` / `idle_since` / `idle_timeout_seconds` | Whether the stream has been quiet past the configured idle timeout | SSI streaming lifecycle manager | boolean/timestamp/seconds | yes | no | Diagnostics/freshness only | Idle only triggers stale-stream reconnect during active holiday-unaware Vietnam trading/auction windows. Outside active windows it is classified as market-closed or after-hours stale state. |
| `diagnostics.reconnect_attempt_count` / `last_reconnect_at` / `next_reconnect_at` | Reconnect attempt count and timing | SSI streaming lifecycle manager | count/timestamp | yes | no | Diagnostics only | Attempts are counted after the initial bootstrap start. `0` max attempts config means unlimited while lifecycle wants streaming. |
| `diagnostics.reconnect_backoff_seconds` / `last_reconnect_reason` / `last_reconnect_error` | Current reconnect backoff and sanitized reason/error | SSI streaming lifecycle manager | seconds/text | yes | no | Diagnostics only | Backoff is bounded by config; error summaries must remain sanitized and must not include raw payloads, headers, tokens, or account IDs. |
| `diagnostics.trade_tape` | Technical details for trade tape attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | Must not leak tokens, auth headers, account IDs, or raw auth responses. |
| `diagnostics.session_status` | Technical details for SSI F session/status attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | May include `streaming_status`, `cache_status`, `manager_state`, `session_status_channels`, row counters, and cache age. Must not leak tokens, auth headers, account IDs, or raw provider bodies. |
| `diagnostics.foreign_room` | Technical details for SSI R foreign-room attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | May include `streaming_status`, `cache_status`, `manager_state`, `foreign_room_channels`, row counters, and cache age. Must not leak tokens, auth headers, account IDs, or raw provider bodies. |
| `diagnostics.market_index_pulse` | Technical details for SSI MI market-index pulse attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | May include `streaming_status`, `cache_status`, `manager_state`, `market_index_channels`, requested index codes, row counters, and cache age. Must not leak tokens, auth headers, account IDs, or raw provider bodies. |

## Profile Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `profile.name` | Company/security display name | SSI Securities/SecuritiesDetails when available | text | yes | yes for display if present | Company hero/header | Handoff found this can be `null` while provider status is `ok`; show profile partial. |
| `profile.name_en` | English company/security name | SSI Securities/SecuritiesDetails when available | text | yes | no | Company profile/details | Hide when absent. |
| `profile.exchange` / `profile.market` | SSI exchange and market labels | SSI Securities/SecuritiesDetails | text | yes | no | Header/profile | Keep distinct when SSI provides distinct values; do not invent either value. |
| `profile.industry` / `profile.sector` | Industry and sector labels | SSI Securities/SecuritiesDetails | text | yes | no | Company profile/details | Preserve separate fields; hide duplicate or absent display rows. |
| `profile.security_type` / `profile.issuer` | Security classification and issuer | SSI Securities/SecuritiesDetails | text | yes | no | Company profile/details | Do not derive from ticker or exchange. |
| `profile.lot_size` / `profile.listed_shares` | Trading lot and listed share count | SSI Securities/SecuritiesDetails | shares | yes | no | Company profile/details | Zero is preserved; missing is null. |
| `profile.listed_date` | SSI listing date | SSI Securities/SecuritiesDetails | date/text | yes | no | Company profile/details | No date inference. |

## Index Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `index_list.rows[].index_id` / `index_code` | SSI-owned identifier and public code | SSI IndexList | text | one required | yes for dependent index requests | Diagnostics/index discovery | Requested market filters may return cross-market rows. |
| `daily_index.rows[].index_value` | Daily index level | SSI DailyIndex | index points | yes | yes for optional index context | Market index context | Never substitutes for ticker `latest_price`. |
| `daily_index.rows[].change` / `change_pct` | Provider daily point and percent change | SSI DailyIndex | points / percent | yes | no | Market index context | Hide when absent; do not derive one from the other. |
| `daily_index.rows[].total_volume` / `total_value` | Provider daily index market volume/value | SSI DailyIndex | shares / VND | yes | no | Optional index detail | Do not mix with ticker volume or DailyStockPrice matched values. |
| `daily_index.rows[].advances` / `declines` / `unchanged` | Provider-returned market breadth counts | SSI DailyIndex | count | yes | no | Optional index context | Show only when SSI returns real counts; never infer from watchlist rows. |
| `daily_index.rows[].date_match` | Alignment with newest DailyIndex date in the response | Service-derived | classification | no | no | Index freshness note/diagnostics | `matched`, `mismatched`, or `unknown`; not exchange-session finality. |
| `index_components.rows[]` | Real SSI index membership rows | SSI IndexComponents | list | no | no | Optional count/diagnostics | Empty when unavailable; no hardcoded VN30 members. |
| Index `missing_fields` / `field_coverage` | Explicit optional-field availability | Service-derived from SSI rows | list/object | no | no | Diagnostics | Missing stays null; zero stays zero. |
| `index_components.diagnostics.cache_status` / `cache_ttl_seconds` / `cache_negative` / `cache_key` | Process-cache result and sanitized cache identity for explicit IndexComponents requests | Service cache over SSI IndexComponents | diagnostic object | yes | no | Index diagnostics only | Usable rows cache for 300 seconds; unavailable/rate-limited/no-row responses cache for 60 seconds. Key contains provider, endpoint, normalized index code, and optional market only. |
| `cache_status.daily_stock_price_cache` | Process-cache result for the combined recent DailyStockPrice enrichment/history request | Service cache over SSI DailyStockPrice | `hit`, `miss`, `refresh`, or `stale` | yes | no | Diagnostics/cache metadata | TTL is 300 seconds; force refresh bypasses freshness. It does not change DailyOhlc canonical price ownership. |

## Current Decision Points

- Company shared daily fields: company `latest_price`, `daily_close`, daily OHLCV open/high/low/close/volume, and daily value align with the watchlist SSI DailyOhlc fields. Company reference, limits, foreign flow, matched/put-through, and adjusted-close values remain SSI DailyStockPrice-specific.
- Dashboard top summary `Foreign net volume` sums `ssi_foreign_net_volume` from the latest successful complete watchlist response in shares. Do not mix this with `ssi_foreign_net_value`, which is VND and should be shown as a separate value-based metric if added.
- Active dashboard labels use `Realtime snapshot`, `SSI realtime`, and `Trade tape` for live sections. Realtime status may be unavailable because the streaming manager is disabled, not started, empty, stale, or errored. KBS/Mozyfin names are reserved for legacy diagnostics or historical notes, not normal runtime UI.
- Future module statuses: corporate actions may use `disabled`, `not_configured`, `not_implemented`, `unavailable`, `partial`, `ok`, or `error`; other live-provider statuses remain `ok`, `unavailable`, or `disabled` unless their own contract expands.

## Standard Source Labels

- `SSI DailyOhlc`: canonical daily OHLCV, daily close, chart candles, daily volume, and daily trading value.
- `SSI DailyStockPrice`: reference, ceiling, floor, matched/put-through, adjusted-close, and foreign-flow fields.
- `derived from SSI DailyOhlc`: technical indicators computed from canonical daily OHLCV.
- `SSI-derived/internal`: metrics calculated from SSI-owned inputs, including existing MA/RSI/Bollinger/20D indicators and Phase 4.8A metrics such as 52W high/low, 10D/3M average volume, price-vs-reference %, and daily range %.
- `SSI Securities` / `SSI SecuritiesDetails`: security metadata and profile fields when available.
- `SSI IntradayOhlc`: intraday candles and derived intraday pulse.
- `SSI realtime contract`: optional FastConnect streaming realtime snapshot contract; live support is not confirmed by this label or by parser/cache/adapter test presence.
- `SSI trade-tape contract`: optional trade-tape contract; live support is not confirmed by this label.
- `SSI IndexList` / `SSI DailyIndex` / `SSI IndexComponents`: index identifiers, daily index context, and component rows.
- `CorporateActionsProvider disabled`: default future-module state for corporate actions; no external provider call is made.
- `disabled`: intentionally disabled public sections, including current VN news status.
- `Vnstock News`: an experimental connector label. `VN_NEWS_PROVIDER=vnstock_news` remains blocked pending written commercial and source-owner terms. `VN_NEWS_PROVIDER=vnstock_news_personal` is local/personal research only and may return bounded RSS rows only when explicitly enabled.
- `blocked_pending_terms`: external-provider legal/access gate; it is not a provider/network failure and must not affect SSI daily fields.
- `personal_research_only`: local-only Vnstock News mode status; not approved for hosted/public/commercial deployment or redistribution.
- `NewsProvider future`: future VN news domain; not implemented today.
- `external provider future`: future financials/corporate-action domains; not implemented today.

Compatibility aliases may map raw provider field names into the same source owner only. They must not substitute across DailyOhlc, DailyStockPrice, intraday, realtime, trade tape, Mozyfin, or KBS ownership boundaries.
