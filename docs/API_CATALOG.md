# VN API Catalog

## Purpose

This catalog documents the VN dashboard API surface used by the current dashboard and company detail page. It does not invent future endpoints. Contract details should stay aligned with `docs/VN_DATA_CONTRACT.md`, `docs/DATA_DICTIONARY.md`, and `docs/UI_STATES.md`.

Global rules:

- SSI is the strict primary VN market-data provider.
- Mozyfin is disabled for VN runtime.
- KBS is legacy optional only and disabled by default.
- News is disabled until a separate provider exists.
- Missing object data returns `null`.
- Missing list data returns `[]`.
- Live-provider statuses use `ok`, `unavailable`, or `disabled`.
- Future modules may use `not_implemented` until Phase 2 decides whether to normalize them.
- Diagnostics carry endpoint/http/raw-provider details; primary fields do not.

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
- News status/list.
- Source/cache/diagnostics metadata.

Source ownership:

- `latest_price`, daily close, chart-compatible OHLCV: SSI DailyOhlc.
- Reference, ceiling/floor, matched/put-through, latest foreign flow: SSI DailyStockPrice.
- Intraday: SSI IntradayOhlc.
- Realtime snapshot and trade tape: SSI live contracts when confirmed.
- News: disabled now; future separate provider.

Null/empty rules:

- `intraday_pulse = null` when unavailable/stale.
- `intraday_candles = []` when unavailable/stale/no usable rows.
- `realtime_snapshot = null` when unavailable.
- `trade_tape = []` when unavailable/no rows.
- `news = []` while disabled.

Current known caveats from handoff snapshots:

- Watchlist/company trade tape can still expose a wrapper object with inner `trades: []`; Phase 2 target is public `trade_tape = []`.
- Realtime/trade-tape status messages can still contain endpoint details; Phase 2 target is short public message plus diagnostics.
- DailyOhlc and DailyStockPrice can disagree on same ticker/date.

Future changes:

- Phase 1: add Data Quality Summary fields or a derived summary for mismatches and missingness.
- Phase 2: normalize live public contract and diagnostics split.
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
- Foreign flow.
- Technical snapshot.
- Intraday.
- Realtime.
- Trade tape.
- News/financials/events future modules.
- Source coverage and diagnostics.

Source ownership:

- Daily core values should align with SSI DailyOhlc canonical source unless a section is explicitly labeled as SSI DailyStockPrice-specific.
- Trading stats/reference/limits/foreign flow use SSI DailyStockPrice.
- Profile metadata uses SSI Securities/SecuritiesDetails when available.

Null/empty rules:

- `intraday.candles = []` and target `intraday.pulse = null` when intraday is unavailable. Handoff snapshot showed current `pulse = {}`; Phase 2 should clean this.
- `realtime_snapshot = null` when unavailable.
- `trade_tape = []` when unavailable/no rows.
- Future module lists stay empty while not implemented/unavailable.

Current known caveats from handoff snapshots:

- Company intraday currently can report `status = unavailable`, `candles = []`, and `pulse = {}`; target is `pulse = null`.
- Profile can have `name = null` and `industry = null` while provider status is `ok`; docs define this as provider OK plus profile completeness `partial`.
- Company price can report `source = SSI DailyStockPrice`; Phase 1 must decide whether company price aligns with DailyOhlc canonical latest price or remains DailyStockPrice-specific with explicit label.
- News/financials/events can use `not_implemented`; this is allowed for future modules, not live-provider statuses.

Future changes:

- Phase 1: add Data Quality Summary above detailed cards.
- Phase 2: clean null/list contracts and diagnostics split.
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
- Unavailable status and diagnostics when SSI does not return rows.

Source ownership:

- SSI IndexComponents owns component rows when available.
- No Mozyfin/KBS fallback.

Null/empty rules:

- Component lists should be `[]` when no usable SSI rows exist.
- Status should be `unavailable` when provider request fails or returns no usable rows.

Current known caveats from handoff snapshots:

- VN30 components can be unavailable in the current SSI environment.
- The UI should show a concise unavailable state, not hardcoded members.

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

- Corporate actions remain unavailable or not implemented until a verified structured source exists.
- Missing event lists return `[]`.
- Do not infer dividends, rights, splits, or adjustment events from price/reference gaps.

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
- SSI realtime is not confirmed live in the handoff context; endpoint/http details belong in diagnostics.
- Legacy KBS may exist behind explicit development flags, but it is not a normal VN runtime fallback.

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
- SSI trade tape is not confirmed live in the handoff context; endpoint/http details belong in diagnostics.
- Legacy KBS may exist behind explicit development flags, but it is not a normal VN runtime fallback.
