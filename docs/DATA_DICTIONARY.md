# VN Data Dictionary

## Purpose

This dictionary defines the public and UI-relevant fields used by the VN dashboard and company detail page. It should be read with `docs/VN_DATA_CONTRACT.md`, `docs/API_CATALOG.md`, and `docs/UI_STATES.md`.

Conventions:

- Canonical means the dashboard should treat the field as the primary user-facing value for its concept.
- Nullable means the field may be `null` or absent when source data is unavailable.
- Missing lists should be `[]`.
- Missing objects should be `null`.
- Diagnostics fields are for debugging and should not become primary metric rows.

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
| `realtime_snapshot.cached_at` / `cache_ttl_seconds` | Cache write time and TTL for the process-local realtime row | SSI streaming manager cache | timestamp/seconds | yes | no | Diagnostics/freshness | Frontend may show `stale >15s`; the generic VN response cache is bypassed for `/vn/realtime`. |
| `trade_tape` | Watchlist trade tape row list | SSI trade-tape contract | list | no, empty list if unavailable | no | Live availability | Phase 2.1 normalizes watchlist public data to a list: `[]` when unavailable/no rows, trade rows when usable. |
| `trade_tape.trades` | Company detail trade tape rows | SSI trade-tape contract | list | no, empty list if unavailable | no | Company live availability | Company detail keeps rows under the nested block while preserving the same empty-list rule. |
| `trade_tape_status` | Public status/source/message for trade tape | Service status wrapper | object | yes | no | Live availability status | Message should be short; sanitized endpoint/provider details belong in status diagnostics or other diagnostics-only structures. |

## Diagnostics Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `diagnostics.realtime` / `realtime_status.diagnostics` | Technical details for realtime snapshot attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | May include REST unsupported state, streaming disabled/configuration-incomplete/package-unavailable/not-started/cache-empty/cache-stale/cache-hit/manager-error state, parsed row counts, manager/cache labels, subscribed channel names, and sanitized error summary. |
| `runtime_status` / `diagnostics.runtime_status` | Process-local SSI streaming manager runtime state | SSI streaming lifecycle manager | enum | yes | no | Diagnostics/freshness only | Values include `disabled`, `not_started`, `starting`, `running`, `running_idle`, `reconnecting`, `errored`, `stopped`, and `shutdown`. `running_idle` does not change daily SSI validity. |
| `diagnostics.is_idle` / `idle_since` / `idle_timeout_seconds` | Whether the stream has been quiet past the configured idle timeout | SSI streaming lifecycle manager | boolean/timestamp/seconds | yes | no | Diagnostics/freshness only | Idle is diagnostic-only for reconnect until a backend market-hours/session utility exists. |
| `diagnostics.reconnect_attempt_count` / `last_reconnect_at` / `next_reconnect_at` | Reconnect attempt count and timing | SSI streaming lifecycle manager | count/timestamp | yes | no | Diagnostics only | Attempts are counted after the initial bootstrap start. `0` max attempts config means unlimited while lifecycle wants streaming. |
| `diagnostics.reconnect_backoff_seconds` / `last_reconnect_reason` / `last_reconnect_error` | Current reconnect backoff and sanitized reason/error | SSI streaming lifecycle manager | seconds/text | yes | no | Diagnostics only | Backoff is bounded by config; error summaries must remain sanitized and must not include raw payloads, headers, tokens, or account IDs. |
| `diagnostics.trade_tape` / `trade_tape_status.diagnostics` | Technical details for trade tape attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | Must not leak tokens, auth headers, account IDs, or raw auth responses. |

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

## Current Decision Points

- Company shared daily fields: company `latest_price`, `daily_close`, daily OHLCV open/high/low/close/volume, and daily value align with the watchlist SSI DailyOhlc fields. Company reference, limits, foreign flow, matched/put-through, and adjusted-close values remain SSI DailyStockPrice-specific.
- Dashboard top summary `Foreign net volume` sums `ssi_foreign_net_volume` from the latest successful complete watchlist response in shares. Do not mix this with `ssi_foreign_net_value`, which is VND and should be shown as a separate value-based metric if added.
- Active dashboard labels use `Realtime snapshot`, `SSI realtime`, and `Trade tape` for live sections. Realtime status may be unavailable because the streaming manager is disabled, not started, empty, stale, or errored. KBS/Mozyfin names are reserved for legacy diagnostics or historical notes, not normal runtime UI.
- Future module statuses: live-provider statuses remain `ok`, `unavailable`, `disabled`; future modules may use `not_implemented` until Phase 2 chooses a normalized shape.

## Standard Source Labels

- `SSI DailyOhlc`: canonical daily OHLCV, daily close, chart candles, daily volume, and daily trading value.
- `SSI DailyStockPrice`: reference, ceiling, floor, matched/put-through, adjusted-close, and foreign-flow fields.
- `derived from SSI DailyOhlc`: technical indicators computed from canonical daily OHLCV.
- `SSI Securities` / `SSI SecuritiesDetails`: security metadata and profile fields when available.
- `SSI IntradayOhlc`: intraday candles and derived intraday pulse.
- `SSI realtime contract`: optional FastConnect streaming realtime snapshot contract; live support is not confirmed by this label or by parser/cache/adapter test presence.
- `SSI trade-tape contract`: optional trade-tape contract; live support is not confirmed by this label.
- `SSI IndexList` / `SSI DailyIndex` / `SSI IndexComponents`: index identifiers, daily index context, and component rows.
- `disabled`: intentionally disabled public sections, including current VN news status.
- `NewsProvider future`: future VN news domain; not implemented today.
- `external provider future`: future financials/corporate-action domains; not implemented today.

Compatibility aliases may map raw provider field names into the same source owner only. They must not substitute across DailyOhlc, DailyStockPrice, intraday, realtime, trade tape, Mozyfin, or KBS ownership boundaries.
