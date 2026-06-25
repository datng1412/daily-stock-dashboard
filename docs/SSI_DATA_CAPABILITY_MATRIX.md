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
| Intraday OHLCV / intraday pulse | SSI IntradayOhlc | `intraday_status`, `intraday_candles`, `intraday_pulse`, company `intraday` | `partial` | `intraday_candles`, `intraday_pulse`, granularity fields only when status is `ok` and dates match | Stale, disabled, mismatched, empty, malformed, rate-limited, cooldown-active, or request-failed rows remain unavailable/disabled | Provider-returned cadence; freshness must match daily trading date | Optional live layer only | Phase 4.0B fixed the fetcher page-size/order bug by paging internally with `pageSize=1000`, sorting rows, and returning the latest public limit. Phase 4.0B-2 observed a live FPT IntradayOhlc failure where SSI returned HTTP 200 with provider code `429`; this is classified as `rate_limited` and remains unavailable with `intraday_candles=[]` and `intraday_pulse=null`. Phase 4.0B-3 added a symbol/timeframe-scoped cooldown after rate-limit signals so repeat calls return unavailable without hitting SSI. |
| Realtime snapshot | SSI FastConnect streaming realtime contract | `GET /api/v1/stocks/vn/realtime`, `realtime_status`, `realtime_snapshot` | `unknown-needs-verification` | Deterministic parser coverage for buffered `X`, `X-QUOTE`, and `X-TRADE` envelopes; config-disabled manager/cache skeleton; config-gated official-client adapter; snapshot fields only with `status=ok` and non-null snapshot | Default runtime remains unavailable because SSI streaming realtime is disabled; config or package failures also fail closed | Realtime cadence not proven until current stream messages are connected, parsed, cached, and surfaced safely | Optional live layer only | Phase 4.0C-6 added the official-client wrapper behind `SSI_STREAMING_REALTIME_ENABLED`, but mocked adapter tests do not make realtime reliable. The default fetcher keeps `get_realtime_snapshot()` unavailable with reason `SSI streaming realtime manager disabled.` Keep `realtime_snapshot=null`; do not infer from daily OHLCV or intraday. |
| Trade tape | SSI trade-tape contract | `GET /api/v1/stocks/vn/realtime/trades`, `trade_tape_status`, `trade_tape` | `unavailable` | Trade rows only with `status=ok` and non-empty rows | Endpoint permissions, row shape, and live availability can be unavailable | Trade-list cadence not proven until current `ok` response exists | Optional live layer only | Baseline observed endpoint `unavailable`, 0 trade rows, and 0/8 usable watchlist trade rows. |
| Index data / index components | SSI IndexList / SSI IndexComponents | `GET /api/v1/stocks/vn/index-list`, `GET /api/v1/stocks/vn/index-components`, `build_index_list`, `build_index_components` | `partial` | SSI-returned index identifiers and component rows | VN30 components can be unavailable depending on endpoint/permission | SSI endpoint response cadence; not tied to watchlist daily validity | Diagnostics and future index context | Service resolves provider index identifiers from IndexList before calling IndexComponents and reports sanitized identifier diagnostics. Baseline observed IndexList `ok` with 10 rows and VN30 components `unavailable` with 0 rows. |
| Profile / securities metadata | SSI Securities / SSI SecuritiesDetails | `symbol_metadata`, company `profile`, `source_coverage` | `partial` | Ticker, exchange, market, name, industry, issuer, security type, lot size, listed shares/date when present | Optional fields can remain null while provider status is `ok` | Metadata cadence is provider-specific and not daily price cadence | Header/profile/source coverage | Industry now maps through when SSI returns an industry/sector alias. Baseline company profile status was `ok`, but only 1 of name/exchange/industry was present. |
| News | NewsProvider future; current runtime disabled | Watchlist `news_status`, company `news` placeholder | `disabled` | None today | `news=[]`, `news_status.status=disabled`, company placeholder | No news freshness contract today | Disabled/unavailable state only | Baseline observed disabled watchlist news and company `not_implemented`; Mozyfin owns no VN runtime news path. |
| Financials | External provider future | Company `financials` placeholder | `future-provider` | None today | Placeholder items remain empty | No cadence until provider contract exists | Future external data layer | Baseline company financials status was `not_implemented`; requires explicit provider contract. |
| Corporate actions / dividends | External provider future | Company `events` placeholder; corporate-action route is unavailable until a verified source exists | `future-provider` | None today | Placeholder items remain empty | No cadence until provider contract exists | Future external data layer | Baseline company events status was `not_implemented`; do not infer corporate actions or dividends from price gaps. |
| Macro/events | External provider future | No current SSI-owned dashboard data block | `future-provider` | None today | No current usable macro/events rows | No cadence until provider contract exists | Future external data layer | Baseline observed no macro provider block in current dashboard/company responses. |

## Phase 4.0B Intraday Root-Cause Result

Phase 4.0B did not find a company-route wiring failure. The existing backend calls the SSI IntradayOhlc provider through the current SSI auth/cache path and maps provider-returned cadence fields.

The root cause was inside the SSI fetcher request behavior. The dashboard requested a 7-day range with the public `intraday_limit` as SSI `pageSize` and `ascending=true`. With the default public limit of 8, SSI returned only the oldest first-page minute rows from the start of the window, so the service saw `2026-06-17` as the latest intraday date while SSI DailyOhlc was already `2026-06-24`.

The fix keeps the public response limit but fetches IntradayOhlc pages internally with `pageSize=1000`, sorts normalized rows, and then returns the latest public limit. Direct patched-fetcher verification returned 8 rows using 2 pages, from `2026-06-24T14:23:56` to `2026-06-24T14:45:00`.

An isolated patched-backend force-refresh audit on 2026-06-24 reported:

- `intraday_status.status=ok` for FPT and `unavailable` for some other audit tickers
- `usable current pulse rows=1/8`
- `intraday_latest_date=2026-06-24`
- `daily_price_date=2026-06-24`
- `date_match=matched` for the usable FPT row
- `intraday_requested_timeframe=1h`
- `intraday_actual_granularity=1m`
- `intraday_actual_granularity_seconds=61`
- `intraday_candles` public count 8 for the usable FPT row
- `intraday_pulse` non-null for the usable FPT row

The implementation also keeps malformed normalized intraday rows unavailable instead of exposing an `ok` pulse from null-only rows. Intraday remains a partial capability until current-date coverage is observed across the broader ticker set; unavailable rows still return `intraday_candles=[]` and `intraday_pulse=null`.

## Phase 4.0B-2 Intraday Live Request Failure Diagnostics

Phase 4.0B-2 inspected the current live failure path after the Phase 4.0B paging fix. The request path remained the expected SSI path:

```text
company endpoint -> watchlist builder -> SSI fetcher -> IntradayOhlc
```

The fetcher still requests IntradayOhlc with symbol-scoped parameters, `timeFrame=1h`, `pageIndex=1`, internal `pageSize=1000`, and `ascending=true`; the public candle limit is applied only after rows are fetched and sorted.

The live FPT probe returned a provider error payload with HTTP status `200` and SSI provider code `429`. The backend now classifies this as `failure_class=rate_limited` and exposes only sanitized diagnostics under `intraday_status.diagnostics` and company `intraday.diagnostics`. No raw provider body, auth header, token, account ID, consumer ID, or consumer secret is exposed.

This phase did not change canonical `latest_price` ownership, did not use intraday as realtime, did not add fallback providers, and did not alter DailyOhlc/DailyStockPrice behavior.

## Phase 4.0B-3 Intraday Rate-Limit Guardrails

Phase 4.0B-3 added an in-memory, per-process cooldown for SSI `IntradayOhlc` after the fetcher classifies a response as `rate_limited`. Both HTTP `429` and SSI provider code `429` start the cooldown. The key is normalized ticker plus requested timeframe, so one throttled ticker/timeframe does not suppress other tickers or other timeframe requests.

During an active cooldown, `SsiFastConnectFetcher.get_intraday_ohlcv` returns:

```text
status = unavailable
failure_class = rate_limited
reason = SSI IntradayOhlc rate limit cooldown active.
rows = []
count = 0
```

The fetcher returns this before requesting an access token or calling `GET /Market/IntradayOhlc`, even if the service caller is force-refreshing. Sanitized diagnostics include `cooldown_active`, `cooldown_recorded`, `cooldown_seconds`, `cooldown_remaining_seconds`, `cooldown_until`, endpoint, symbol, requested timeframe, page size, and public limit. Raw provider bodies, auth headers, tokens, account IDs, consumer IDs, and consumer secrets remain excluded.

The default cooldown is `SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS=60`; `0` disables the guard. This does not change DailyOhlc, DailyStockPrice, canonical `latest_price`, realtime snapshot, or trade-tape ownership. Intraday remains `partial` until current usable rows are observed broadly.

## Phase 4.0C Realtime Snapshot Root-Cause Result

Phase 4.0C did not find a route, service, config-gate, symbol-normalization, batch, or parser bug that explains the current SSI realtime snapshot unavailability.

Observed baseline against the already-running local backend on 2026-06-24:

- `GET /api/v1/stocks/vn/realtime?tickers=FPT` returned `status=unavailable`.
- Endpoint quote row count was `0`.
- A force-refresh FPT audit reported `watchlist usable snapshots=0/1`.
- The live endpoint detail reported a 404 from the SSI realtime REST candidate path.
- The same audit kept daily OHLCV, DailyStockPrice, foreign flow, technical indicators, and FPT intraday pulse reliable.

Code inspection found the public route calls `VietnamMarketService.build_realtime_snapshot`, which calls `SsiFastConnectFetcher.get_realtime_snapshot`. In Phase 4.0C this path still tried one-symbol calls for SSI realtime REST candidate endpoints and only mapped rows with meaningful quote fields. Phase 4.0C-2 supersedes that runtime probing behavior because the candidate names were not verified as a supported SSI contract.

Conclusion: in the current environment, realtime remains a provider/endpoint availability issue, not a data substitution opportunity. The dashboard must keep realtime unavailable with `realtime_snapshot=null` until a current SSI response returns usable quote rows with `status=ok`.

## Phase 4.0C-2 SSI Realtime Endpoint Discovery

The discovery artifact is `ssi_realtime_endpoint_discovery.txt`, produced from repository text files under the requested scope plus existing SSI notes. The search inspected these files or file groups for SSI realtime endpoint contracts, SDK wrappers, method names, enums, configuration, and documentation references:

- `data_provider/ssi_fastconnect_fetcher.py`
- `scripts/ssi_fastconnect_smoke.py`
- `src/config.py`
- `src/core/config_registry.py`
- `src/services/vietnam_market_service.py`
- `.env.example`
- `requirements.txt`
- `pyproject.toml`
- `setup.cfg`
- `docs/SSI_FASTCONNECT_INTEGRATION.md`
- `docs/SSI_DATA_CAPABILITY_MATRIX.md`
- `docs/VN_DASHBOARD_ROADMAP.md`
- `docs/RUNBOOK_VN.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `docs/resources/realtime-data/ssi-iboard.md`

Candidate endpoints/methods found:

- Runtime speculative REST candidates from the existing fetcher: `RealtimeQuote`, `RealtimePrice`, `RealtimeSnapshot`, and `SecuritiesRealtime`.
- Internal project method: `SsiFastConnectFetcher.get_realtime_snapshot`.
- Public project API: `GET /api/v1/stocks/vn/realtime`.
- Smoke-script SSI FC Data base URLs: `https://fc-data.ssi.com.vn/api/v2/Market` and `https://fc-data.ssi.com.vn/v2.0/Market`.

No verified SSI FastConnect SDK package, wrapper, enum, or documented method named `GetRealtime`, `GetQuote`, `RealtimeQuote`, `StockQuote`, `MarketData`, `TradingData`, or equivalent was found. The iBoard note in `docs/resources/realtime-data/ssi-iboard.md` is reference-only and has unknown authentication, API contract, rate-limit, timestamp, and price semantics; it is not wired into the dashboard.

Conclusion: a supported SSI REST realtime endpoint is not identified in this repository. Phase 4.0C-3 supersedes REST probing with the SSI streaming direction. Daily OHLCV, DailyStockPrice, and IntradayOhlc behavior is unchanged.

## Phase 4.0C-3 SSI Streaming Realtime Adapter Direction

Official SSI FastConnect Data docs describe realtime as a streaming feed, not a REST quote endpoint. The documented realtime stream message families relevant to dashboard quote semantics are:

- `X`: combined quote/trade context.
- `X-QUOTE`: best bid/ask and quote context only.
- `X-TRADE`: latest matched trade context.

The current implementation adds deterministic parser coverage for buffered SSI streaming envelopes shaped like:

```text
DataType = X, X-QUOTE, or X-TRADE
Content = JSON object or JSON string containing RType, Symbol, and stream fields
```

Parser rules:

- Ignore malformed envelopes and unsupported data types.
- Ignore symbols outside the requested ticker set.
- Normalize ticker symbols before returning rows.
- Parse `Content` safely when SSI sends it as a JSON string.
- Preserve provider timestamps from `TradingDate` and `Time` when present.
- Treat `X-QUOTE` as quote-only context. Do not synthesize `LastPrice` or a matched trade from bid/ask fields.
- Treat `X` and `X-TRADE` as latest-trade snapshot candidates only when `LastPrice` is present.
- Do not turn a single `X-TRADE` message into full trade-tape history.

Runtime state remained unavailable at the end of Phase 4.0C-3 because the repository did not implement a bounded SSI streaming client, subscription lifecycle, reconnection/backoff policy, or request-safe cache handoff. `SsiFastConnectFetcher.get_realtime_snapshot()` did not open a streaming connection and did not probe REST realtime candidates. It returned:

```text
status = unavailable
reason = SSI realtime requires FastConnect streaming adapter; connection semantics not implemented.
rest_status = unsupported
streaming_status = not_implemented
```

Phase 4.0C-5 adds the first request-safe cache handoff skeleton. Phase 4.0C-6 adds the official SSI client adapter behind the disabled streaming runtime flag. Streaming still runs outside request handlers, subscribes only to requested symbol scopes, avoids `X: ALL` in runtime, and surfaces rows only after current stream messages are parsed and cached fresh in the existing public realtime response shape.

## Phase 4.0C-4 Official Python Client Inspection

The official Python package was installed in the local development environment for inspection:

```text
package name: ssi-fc-data
import module: ssi_fc_data
installed version: 2.2.2
home page: https://github.com/SSI-Securities-Corporation/python-fcdata
dependencies: requests, websocket-client
```

Import/module discovery found these relevant official modules:

- `ssi_fc_data.fc_md_client`
- `ssi_fc_data.fc_md_stream`
- `ssi_fc_data.model.api`
- `ssi_fc_data.signalr._connection`
- `ssi_fc_data.signalr.transports._transport`

Official streaming API surface found:

- `MarketDataClient(config)` retrieves and caches an access token from `config.url + api/v2/Market/AccessToken`.
- The installed package metadata config sample uses `auth_type`, `consumerID`, `consumerSecret`, `url`, and `stream_url`. No `PrivateKey` reference was found in the installed `ssi_fc_data 2.2.2` package source.
- `MarketDataStream(config, MarketDataClient(config), on_close=None, on_open=None)` owns the streaming connection.
- `MarketDataStream.start(on_message, on_error, selected_channel)`:
  - calls the market-data client access-token path;
  - creates an `Authorization` header from `config.auth_type` plus the access token;
  - connects to `config.stream_url + v2.0/signalr`;
  - registers hub `FcMarketDataV2Hub`;
  - subscribes client handlers for `Broadcast` and `Error`;
  - invokes hub method `SwitchChannels` with the selected channel on open;
  - starts the websocket transport on a daemon thread.
- `MarketDataStream.swith_channel(channel)` invokes `SwitchChannels` again. The method name is spelled `swith_channel` in the installed package.

Official sample metadata shows the subscription value is a plain channel string supplied by the caller. That matches the documented channel shape such as `X-TRADE: ACB`, `X-QUOTE: ACB`, or `X: ACB`. Runtime code must not subscribe to `X: ALL`.

Safe bounded one-shot adapter feasibility:

- Not implemented in this phase.
- The official client exposes connection and subscription primitives, but not a public bounded receive/wait API.
- The transport starts a background daemon websocket thread and does not expose a documented join/timeout lifecycle.
- The bundled SignalR negotiation path contains a `print(self.headers)` statement, which would print the `Authorization` header if used directly. Runtime code must not use it without a wrapper or patch that prevents secret output.
- `Connection.close()` calls `self.__transport.close()`, while the bundled transport exposes `stop()`; this needs wrapper-level close handling before runtime use.

Conclusion: a minimal future adapter is feasible only as a background service, not inside request handlers. It should wrap the official client, subscribe to symbol-scoped channels only, collect messages into a thread-safe cache, call the parser added in Phase 4.0C-3, suppress or patch header printing, and provide an explicit stop path that uses the transport `stop()` method if the official `close()` path is not functional. `get_realtime_snapshot()` remains unavailable until that adapter is implemented and validated.

## Phase 4.0C-5 Safe Streaming Manager Skeleton

Phase 4.0C-5 added the internal architecture for future SSI streaming realtime without enabling live streaming:

- `SSI_STREAMING_REALTIME_ENABLED=false` by default.
- `SSI_STREAMING_REALTIME_CACHE_TTL_SECONDS=15` by default.
- `SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE=X: {symbol}` by default.
- `SsiStreamingRealtimeManager` owns explicit lifecycle states: `disabled`, `stopped`, `starting`, `running`, and `errored`.
- `RealtimeSnapshotCache` stores latest normalized snapshot candidates per symbol and marks empty or stale cache reads unavailable.
- `SsiFastConnectFetcher.get_realtime_snapshot()` reads only the manager/cache path when streaming runtime is enabled; it does not open a websocket and does not probe REST realtime candidates.
- Request handlers do not start streams. Module imports do not start streams.
- Runtime channel construction rejects `ALL` subscriptions.
- A single `X-TRADE` message may update the realtime snapshot candidate, but it must not create trade-tape history or mark trade tape reliable.

Default runtime response remains unavailable:

```text
status = unavailable
reason = SSI streaming realtime manager disabled.
rest_status = unsupported
streaming_status = disabled
manager_state = disabled
cache_status = disabled
```

When streaming runtime is explicitly enabled but the background manager is not running, has an empty cache, has stale cache rows, or has errored, realtime remains unavailable with sanitized diagnostics for `streaming_manager_not_started`, `streaming_cache_empty`, `streaming_cache_stale`, or `streaming_manager_error`. A cache hit is only a realtime snapshot candidate; live reliability still requires current stream evidence.

## Phase 4.0C-6 Official Adapter Behind Config

Phase 4.0C-6 adds the official SSI Python client adapter without enabling live realtime by default:

- `SSI_STREAMING_REALTIME_ENABLED=false` remains the default and has highest precedence.
- `SSI_STREAMING_REALTIME_STREAM_URL=https://fc-datahub.ssi.com.vn/` is the default stream root.
- The official `ssi_fc_data` package is imported lazily only when the adapter starts.
- The official market-data client is instantiated only when streaming is enabled, required config is present, and the background manager is explicitly started.
- Missing streaming config returns `SSI streaming realtime configuration incomplete.`
- Missing `ssi_fc_data` returns `SSI streaming realtime package unavailable.`
- The adapter suppresses the official header-printing path during stream start and uses the transport `stop()` method when available.
- Tests use mocked official modules and prove no header-like secret text is emitted.

This phase does not prove live reliability. Realtime stays `unknown-needs-verification` until current live stream rows are observed through the manager/cache path.

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
