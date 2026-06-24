# SSI Data Capability Matrix

## Purpose

This matrix is an audit and planning aid for the VN dashboard. It is not a new API contract and does not replace `docs/VN_DATA_CONTRACT.md`.

Statuses are conservative and should be refreshed when provider behavior, endpoint permissions, or response shapes change. `reliable` means observed reliable for the audit run and audit inputs, not a permanent provider guarantee.

Use `scripts/audit_vn_data_capability.ps1` to refresh local evidence from existing app endpoints before adding new dashboard fields or UI modules.

Last local audit baseline: 2026-06-24, using `FPT,VPB,ACB,SSI,GMD,GAS,POW,VNM` and selected ticker `FPT` against `http://127.0.0.1:8000`.

## Status Vocabulary

| Status | Meaning |
| --- | --- |
| `reliable` | Observed usable for this audit run and input set, with source and safe fields clear. |
| `partial` | Some usable fields exist, but freshness, cadence, completeness, or ticker coverage is not fully proven. |
| `unavailable` | The source or section is enabled or represented but returned no usable data. |
| `disabled` | The section is intentionally off in the current contract/runtime. |
| `future-provider` | The domain needs a separate future provider contract and is not SSI market data. |
| `unknown-needs-verification` | Current responses do not provide enough evidence to classify safely. |

## Capability Matrix

| Data domain | Source owner | Existing path/function | Current status | Reliable fields | Partial/unavailable fields | Freshness/cadence | UI usage | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Daily OHLCV | SSI DailyOhlc | `GET /api/v1/stocks/vn/watchlist`, `GET /api/v1/stocks/vn/chart`, `VietnamMarketService.build_watchlist`, `VietnamMarketService.build_chart` | `reliable` | `date`, `open`, `high`, `low`, `close`, `daily_close`, `ohlcv_close`, `volume`, chart candles | `amount` or value fields may be missing by ticker/provider row | Daily candle freshness depends on SSI daily row date and finality metadata; final close can still be `unknown` | Primary watchlist, selected ticker, company price/trading stats, chart | Baseline observed 8/8 rows with date, close, volume, and SSI daily source evidence. |
| Latest daily close | SSI DailyOhlc | `latest_price`, `latest_price_source`, company `price.canonical_source` | `reliable` | `latest_price`, `latest_price_date`, `latest_price_source`, `daily_close` | Finality can be `unknown`; DailyStockPrice close can disagree | Same daily row cadence as DailyOhlc | Primary daily price only | Baseline observed 8/8 rows with `latest_price_source=SSI DailyOhlc`; do not infer realtime from this field. |
| Daily volume/value | SSI DailyOhlc | Watchlist row daily fields, company `trading_stats` | `reliable` | `volume`, `amount`/`value` when present with DailyOhlc row | Matched value is not a substitute | Same daily row cadence as DailyOhlc | Daily liquidity context and chart volume | Baseline observed volume and value/amount on 8/8 rows. |
| DailyStockPrice reference/ceiling/floor | SSI DailyStockPrice | `daily_stock_price`, `price_limit`, company `price.reference_source` | `reliable` | `reference_price`, `ceiling_price`, `floor_price` | Missing limit fields should remain null/unavailable | Latest DailyStockPrice row; date alignment should be checked against DailyOhlc | Price context and selected ticker quick facts | Baseline observed DailyStockPrice ok and limit fields on 8/8 rows; does not replace canonical daily close. |
| Matched volume/value | SSI DailyStockPrice | `daily_stock_price`, `ssi_matched_volume`, `ssi_matched_value` | `reliable` | `matched_volume`, `matched_value` | Missing matched fields are partial/unavailable, not zero | DailyStockPrice row cadence; can differ from DailyOhlc volume | Trading-stat detail only | Baseline observed matched volume/value on 8/8 rows. |
| Foreign buy/sell/net volume | SSI DailyStockPrice | `daily_stock_price`, `foreign`, `ssi_foreign_net_volume` | `reliable` | `foreign_buy_volume`, `foreign_sell_volume`, `foreign_net_volume` | Missing fields should remain null; historical windows can be insufficient | Latest DailyStockPrice row; date alignment matters | Foreign-flow summary and scan table | Baseline observed buy/sell/net volume on 8/8 rows; null is not zero. |
| Foreign buy/sell/net value | SSI DailyStockPrice | `daily_stock_price`, `foreign`, `ssi_foreign_net_value` | `reliable` | `foreign_buy_value`, `foreign_sell_value`, `foreign_net_value` | Value fields can be absent while volume fields exist | Latest DailyStockPrice row; date alignment matters | Future value-based foreign-flow display | Baseline observed buy/sell/net value on 8/8 rows; do not mix with share-volume summaries. |
| Technical indicators | Derived from SSI DailyOhlc | `indicators`, `calculate_vietnam_indicators` | `reliable` | `rsi14_wilder`/`rsi14`, `ma20`, `ma50`, Bollinger fields when present, volume ratio | Missing history yields unavailable indicator fields | Derived from daily history window | Scan table, selected ticker technical context | Baseline observed RSI14 and MA20/MA50 on 8/8 rows; RSI14 remains Wilder/RMA. |
| Intraday OHLCV / intraday pulse | SSI IntradayOhlc | `intraday_status`, `intraday_candles`, `intraday_pulse`, company `intraday` | `unavailable` | `intraday_candles`, `intraday_pulse`, granularity fields only when status is `ok` and dates match | Stale, disabled, mismatched, empty, or malformed candles remain unavailable/disabled | Provider-returned cadence; freshness must match daily trading date | Optional live layer only | Phase 4.0B live root cause: current API fields show SSI IntradayOhlc returns stale/mismatched data, for example `intraday_latest_date=2026-06-17` versus `daily_price_date=2026-06-24`, `date_match=mismatched`, requested `1h`, observed `1m`/60s. Public candle count remains 0 and pulse remains null while stale candles are withheld. |
| Realtime snapshot | SSI realtime contract | `GET /api/v1/stocks/vn/realtime`, `realtime_status`, `realtime_snapshot` | `unavailable` | Snapshot fields only with `status=ok` and non-null snapshot | Endpoint permissions, row shape, and live availability can be unavailable | Realtime cadence not proven until current `ok` response exists | Optional live layer only | Baseline observed endpoint `unavailable`, 0 quote rows, and 0/8 usable watchlist snapshots. |
| Trade tape | SSI trade-tape contract | `GET /api/v1/stocks/vn/realtime/trades`, `trade_tape_status`, `trade_tape` | `unavailable` | Trade rows only with `status=ok` and non-empty rows | Endpoint permissions, row shape, and live availability can be unavailable | Trade-list cadence not proven until current `ok` response exists | Optional live layer only | Baseline observed endpoint `unavailable`, 0 trade rows, and 0/8 usable watchlist trade rows. |
| Index data / index components | SSI IndexList / SSI IndexComponents | `GET /api/v1/stocks/vn/index-list`, `GET /api/v1/stocks/vn/index-components`, `build_index_list`, `build_index_components` | `partial` | SSI-returned index identifiers and component rows | VN30 components can be unavailable depending on endpoint/permission | SSI endpoint response cadence; not tied to watchlist daily validity | Diagnostics and future index context | Baseline observed IndexList `ok` with 10 rows and VN30 components `unavailable` with 0 rows. |
| Profile / securities metadata | SSI Securities / SSI SecuritiesDetails | `symbol_metadata`, company `profile`, `source_coverage` | `partial` | Ticker, exchange, market, name, issuer, security type, lot size, listed shares/date when present | Optional fields can remain null while provider status is `ok` | Metadata cadence is provider-specific and not daily price cadence | Header/profile/source coverage | Baseline company profile status was `ok`, but only 1 of name/exchange/industry was present. |
| News | NewsProvider future; current runtime disabled | Watchlist `news_status`, company `news` placeholder | `disabled` | None today | `news=[]`, `news_status.status=disabled`, company placeholder | No news freshness contract today | Disabled/unavailable state only | Baseline observed disabled watchlist news and company `not_implemented`; Mozyfin owns no VN runtime news path. |
| Financials | External provider future | Company `financials` placeholder | `future-provider` | None today | Placeholder items remain empty | No cadence until provider contract exists | Future external data layer | Baseline company financials status was `not_implemented`; requires explicit provider contract. |
| Corporate actions / dividends | External provider future | Company `events` placeholder; corporate-action route is unavailable until a verified source exists | `future-provider` | None today | Placeholder items remain empty | No cadence until provider contract exists | Future external data layer | Baseline company events status was `not_implemented`; do not infer corporate actions or dividends from price gaps. |
| Macro/events | External provider future | No current SSI-owned dashboard data block | `future-provider` | None today | No current usable macro/events rows | No cadence until provider contract exists | Future external data layer | Baseline observed no macro provider block in current dashboard/company responses. |

## Phase 4.0B Intraday Root-Cause Result

Phase 4.0B did not find an endpoint-wiring failure. The existing backend calls the SSI IntradayOhlc provider through the current SSI auth/cache path and maps provider-returned cadence fields.

Live force-refresh evidence on 2026-06-24 showed intraday remains unavailable because the latest returned intraday candle date does not match the current SSI DailyOhlc date. The projected local API response for `FPT` reported:

- `intraday_status.status=unavailable`
- `intraday_status.message=SSI IntradayOhlc latest candle date does not match latest daily trading date.`
- `intraday_latest_date=2026-06-17`
- `daily_price_date=2026-06-24`
- `date_match=mismatched`
- `intraday_requested_timeframe=1h`
- `intraday_actual_granularity=1m`
- `intraday_actual_granularity_seconds=60`
- `intraday_candles=[]`
- `intraday_pulse=null`

The implementation keeps malformed normalized intraday rows unavailable instead of exposing an `ok` pulse from null-only rows. Live intraday is still `unavailable`; mocked backend tests verify the available, stale, empty, malformed, failure, and disabled paths.

## Required Guardrails

- This matrix is an audit/planning aid, not a new API contract.
- `docs/VN_DATA_CONTRACT.md` remains the contract source for public status, null, empty-list, and source-ownership semantics.
- SSI DailyOhlc owns canonical daily close/OHLCV/chart fields.
- SSI DailyStockPrice owns reference/ceiling/floor, matched stats, and foreign-flow fields.
- Indicators are derived from SSI DailyOhlc.
- Realtime and trade tape are optional and must not be called reliable unless the current audit observes `ok` status and usable data.
- News, fundamentals, corporate actions, dividends, and macro need future provider contracts.
- Corporate actions and dividends must not be inferred from price gaps.
- Mozyfin/KBS fallback must not be reintroduced.
- KBS remains legacy-only and disabled by default.

## Local Refresh Command

Run from the repository root with the backend already started:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit_vn_data_capability.ps1
```

Use cache bypass only when the audit explicitly needs current provider fetches:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit_vn_data_capability.ps1 -ForceRefresh
```
