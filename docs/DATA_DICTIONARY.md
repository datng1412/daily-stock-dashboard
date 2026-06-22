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
| `latest_price_raw_field` | Raw provider field used for latest price when available | Provider normalization metadata | text | yes | no | Diagnostics only | Must not be used as proof of realtime support. |
| `daily_close` | Daily close value exposed by watchlist/company contract | SSI DailyOhlc | VND | yes | yes | Daily core data | Same semantic owner as `latest_price` when DailyOhlc is valid. |
| `ohlcv_close` | Close from normalized OHLCV row | SSI DailyOhlc | VND | yes | yes | Data Quality Summary/diagnostics | Used to compare with DailyStockPrice close. |
| `daily_stock_price.close` | Close from DailyStockPrice endpoint | SSI DailyStockPrice | VND | yes | no, pending decision | Trading stats or source comparison | Handoff found FPT `2026-06-22` mismatch vs DailyOhlc; Phase 1 must decide company price source alignment. |
| `adjusted_close` | Adjusted close when provider supplies it | SSI DailyStockPrice | VND | yes | no | Trading stats/detail | Do not infer corporate actions from adjusted-close gaps. |
| `reference_price` | Session reference/basic price | SSI DailyStockPrice | VND | yes | no | Daily core data/limits | Separate from canonical latest price. |
| `ceiling_price` | Daily price ceiling | SSI DailyStockPrice | VND | yes | no | Price limit block | Render only when value exists. |
| `floor_price` | Daily price floor | SSI DailyStockPrice | VND | yes | no | Price limit block | Render only when value exists. |
| `volume` | Daily OHLCV volume | SSI DailyOhlc | shares | yes | yes for daily volume | Daily core data/chart | Can differ from DailyStockPrice matched volume. |
| `matched_volume` | Matched trading volume | SSI DailyStockPrice | shares | yes | source-specific | Trading stats | Handoff FPT example differed from DailyOhlc volume. |
| `matched_value` | Matched trading value | SSI DailyStockPrice | VND | yes | source-specific | Trading stats/liquidity | Keep source label visible. |
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
| `foreign_net_5d` | Five-session net foreign flow | Future DailyStockPrice history | VND or shares, depending field | yes | no | Data Quality Summary/Foreign flow | Use `insufficient_history` when rows are not enough. |
| `foreign_net_20d` | Twenty-session net foreign flow | Future DailyStockPrice history | VND or shares, depending field | yes | no | Foreign flow | Compute only from matched-date historical rows. |

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
| `profile_quality` / `profile.completeness` | Data-quality completeness for profile fields | Service-derived quality classification | classification | yes | yes for UI quality | Header badge/Data Quality Summary | Preferred future shape for partial metadata. |

## Live Data Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `intraday_candles` | Usable intraday candles | SSI IntradayOhlc | list of OHLCV candles | no, empty list if unavailable | no | Live availability/chart adjunct | `[]` when unavailable/stale/no usable rows. |
| `intraday_pulse` | Compact intraday summary object | Derived from usable SSI IntradayOhlc | object | yes | no | Live availability/Data Quality Summary | Handoff found company endpoint can return `{}` when unavailable; Phase 2 target is `null`. |
| `realtime_snapshot` | Realtime snapshot object | SSI realtime contract | object | yes | no | Live availability | `null` until SSI realtime is confirmed and status is `ok`. |
| `trade_tape` | Trade tape row list | SSI trade-tape contract | list | no, empty list if unavailable | no | Live availability | Target public contract is `[]` when unavailable/no rows; wrapper object with inner `trades: []` is legacy/current cleanup. |
| `trade_tape_status` | Public status/source/message for trade tape | Service status wrapper | object | yes | no | Live availability status | Message should be short; endpoint details belong in `diagnostics.trade_tape`. |

## Diagnostics Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `diagnostics.realtime` | Technical details for realtime snapshot attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | May include endpoint labels, last endpoint, HTTP status, retryable flag, sanitized error summary. |
| `diagnostics.trade_tape` | Technical details for trade tape attempts | Provider/service diagnostics | object | yes | no | Collapsible diagnostics only | Must not leak tokens, auth headers, account IDs, or raw auth responses. |

## Profile Fields

| Field | Meaning | Source | Unit | Nullable | Canonical | UI placement | Known caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `profile.name` | Company/security display name | SSI Securities/SecuritiesDetails when available | text | yes | yes for display if present | Company hero/header | Handoff found this can be `null` while provider status is `ok`; show profile partial. |
| `profile.industry` | Industry/sector label if available | SSI metadata if available | text | yes | no | Company profile/details | Do not invent industry; hide row if absent. |
| `profile.completeness` / `profile_quality` | Quality classification for profile missingness | Service-derived | classification | yes | yes for UI status | Header badge/Data Quality Summary | Preferred future contract: `partial` when key fields are missing even if provider status is `ok`. |

## Current Decision Points

- Company price source: company endpoint can report price source as SSI DailyStockPrice while dashboard canonical `latest_price` is SSI DailyOhlc close. Phase 1 must either align company price with DailyOhlc or document the company price block as DailyStockPrice-specific.
- Future module statuses: live-provider statuses remain `ok`, `unavailable`, `disabled`; future modules may use `not_implemented` until Phase 2 chooses a normalized shape.
