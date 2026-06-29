# SSI Data Capability Matrix

## Purpose

This matrix is an audit and planning aid for the VN dashboard. It is not a new API contract and does not replace `docs/VN_DATA_CONTRACT.md`.

Statuses are conservative and should be refreshed when provider behavior, endpoint permissions, or response shapes change. A `strong` or `usable` status is repository and current-evidence scoped; it is not a permanent provider guarantee.

Use `scripts/audit_vn_data_capability.ps1` to refresh local evidence from existing app endpoints before adding new dashboard fields or UI modules.

Last local audit baseline: 2026-06-24, using `FPT,VPB,ACB,SSI,GMD,GAS,POW,VNM` and selected ticker `FPT` against `http://127.0.0.1:8000`.

## Status Vocabulary

| Status | Meaning |
| --- | --- |
| `strong` | Implemented, source-owned, covered by deterministic tests, and supported by current repo/live evidence for the public contract. |
| `usable` | Implemented and safe to expose when rows exist, but coverage, optional fields, or provider behavior remains bounded. |
| `partial` | Some usable SSI fields or paths exist, but freshness, cadence, completeness, identifier coverage, or row validity remains incomplete. |
| `optional_live_dependent` | Implemented as an optional live/cache contract; data appears only when the live runtime is explicitly enabled and current rows exist. |
| `unavailable_parameter_unknown` | A current repo path or candidate endpoint exists, but the correct identifier/parameter/row semantics are not proven. |
| `unavailable_permission_or_entitlement` | SSI may expose the domain only under account permission or entitlement not proven in the current environment. |
| `external_provider_required` | No SSI-owned endpoint or repo evidence supports the domain; a separate provider contract is required. |
| `not_implemented` | A placeholder or contract may exist, but no provider implementation is present. |
| `deferred` | Valid future work, intentionally out of scope for the current SSI-first phase. |

## Capability Matrix

| Data domain | Phase 4.5A status | Category | Current endpoint/provider | Current public contract | Evidence summary | Next action | External provider required? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Securities | `partial` | SSI available and implemented | `GET /Market/Securities`; `get_securities`; same-provider fallback for metadata | `symbol_metadata`, company `profile`, source coverage fields when exact ticker row is found | Phase 4.3A added exact-symbol selection, sanitized diagnostics, and same-SSI fallback after `SecuritiesDetails`; optional fields remain null | Keep as SSI fallback only; add aliases only after sanitized live row-key evidence | No for base symbol metadata; richer fallback is deferred external work |
| SecuritiesDetails | `partial` | SSI available and implemented | `GET /Market/SecuritiesDetails`; `get_securities_details` | Preferred source for symbol metadata/profile fields | Phase 4.3A verified null-safe metadata quality/completeness and no effect on DailyOhlc/DailyStockPrice | Keep optional fields null when absent; do not infer company details | No for SSI-returned fields |
| Supported market metadata | `usable` | SSI available and implemented | `Securities`, `SecuritiesDetails`, `IndexList` | Source-labeled symbol/index metadata; missing fields are null | Current repo has explicit metadata quality, field coverage, and diagnostics | Keep metadata source-specific and non-fatal | No for SSI-returned fields; external fallback deferred |
| DailyOhlc | `strong` | SSI available and implemented | `GET /Market/DailyOhlc`; watchlist/chart loaders | Canonical daily OHLCV, chart candles, `latest_price`, internal indicators | Deterministic tests and live smoke evidence keep `latest_price_source=SSI DailyOhlc`; latest price ownership unchanged | Preserve canonical ownership; investigate finality separately, not by overwriting fields | No |
| DailyStockPrice | `strong` | SSI available and implemented | `GET /Market/DailyStockPrice`; 29-day chunking; latest-row enrichment | Reference, ceiling/floor, adjusted close if present, matched/put-through volume/value, latest foreign buy/sell/net volume/value | Phase 4.2A covered date alignment, partial coverage, units, null/zero behavior, and unchanged DailyOhlc close | Keep latest-row enrichment; 5D/20D foreign-flow history remains deferred until a bounded contract is designed | No for latest enrichment |
| DailyIndex | `partial` | SSI available but live result partial | `GET /Market/DailyIndex`; `indexID` after exact `IndexList` resolution | Optional index rows with `rows=[]` when unavailable; non-positive index levels normalize to null | Phase 4.4B proved `indexID=VN30` returns rows; latest provider `IndexValue=0` is treated as missing; exact `VNINDEX` remains unresolved | Keep VN30 optional and partial; do not guess VNINDEX or render zero as an index level | External fallback only for explicit source-labeled VNINDEX, deferred |
| IndexList | `usable` | SSI available and implemented | `GET /Market/IndexList` with market-qualified requests | Authoritative SSI-returned identifiers for DailyIndex and IndexComponents | Phase 4.4B returned 10 cross-market rows for HOSE/HNX, exact `VN30`, no exact `VNINDEX`; no-market request unavailable | Continue resolving through market-qualified `IndexList`; treat market filters as non-strict | No for returned identifiers |
| IndexComponents | `usable` | SSI available and implemented for VN30 | `GET /Market/IndexComponents`; `indexCode` first; exact nested row flattening | Optional component rows/counts with `rows=[]` when unavailable | Phase 4.4B proved exact VN30 nested `IndexComponent`/`StockSymbol` rows with 30 members; no hardcoded constituents | Use only real SSI component rows; do not infer breadth or membership when absent | No for VN30 rows; other index coverage unknown |
| IntradayOhlc | `partial` | SSI available but live result partial/unavailable | `GET /Market/IntradayOhlc` | Optional `intraday_candles` and `intraday_pulse` only when rows are current and matched; otherwise `[]`/`null` | Phase 4.0B fixed paging/order; Phase 4.0B-2/3 classified provider code `429` and added cooldown; Phase 4.1A added actual cadence detection | Keep rate-limit-aware optional behavior; do not present as realtime quote | No |
| Realtime streaming snapshot | `optional_live_dependent` | SSI available but live runtime-dependent | SSI streaming data types `X`, `X-QUOTE`, `X-TRADE`; background manager/cache only | `realtime_snapshot=null` unless explicit streaming runtime is enabled, manager is running, and cache row is fresh | Parser, official-client adapter, lifecycle bootstrap, cache bypass, and safe diagnostics exist; default runtime remains disabled | Keep background-only cache contract; no request-handler streaming, no WebSocket/SSE productization | No for SSI snapshot, but live entitlement/runtime must be proven per environment |
| Trade tape / `X-TRADE` semantics | `unavailable_parameter_unknown` | SSI candidate path exists but true trade-history semantics are unproven | `X-TRADE` streaming latest-trade event; candidate REST trade endpoints remain unverified | Public trade tape stays `[]` unless a true list/history source returns rows; `X-TRADE` may update realtime snapshot only | Parser differentiates `X-TRADE` latest-trade context from true trade history; no verified historical trade-tape rows exist | Do not productize trade-tape history until true rows, parameters, and permissions are proven | Possibly, if SSI true trade history is not entitled/available |
| Unsupported fundamentals | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | No SSI-owned public contract | Current implementation exposes no SSI fundamentals endpoint | Keep unavailable/not implemented until a provider is selected | Yes |
| Unsupported financial statements | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | Company `financials` placeholder | Current company research service returns `not_implemented`; no SSI statement endpoint in repo evidence | Defer behind external-provider gate | Yes |
| Unsupported ratios | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | No ratio provider block | No SSI ratios endpoint in repo evidence | Defer; keep provider ratios separate from local derivations | Yes |
| Unsupported corporate actions | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | `/vn/corporate-actions` unavailable contract; company `events=[]` placeholder | Service explicitly refuses to infer events from price/reference/adjusted gaps | Phase 5.0B qualification only; no provider runtime yet | Yes |
| Unsupported dividends/rights/splits | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | Same event/corporate-action boundary | No explicit SSI event source in current repo evidence | Use only explicit future event rows; no inference from price gaps | Yes |
| Unsupported news | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None; Mozyfin disabled | Watchlist `news=[]`, `news_status.status=disabled`; company `news.status=not_implemented` | Current runtime has no SSI or Mozyfin news path | Future NewsProvider only after access/rights proof | Yes |
| Unsupported macro | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | No macro block | No SSI macro evidence in current repo | Defer until specific source/series contracts exist | Yes |

## Phase 4.5A SSI Gap Separation

* SSI available and implemented: Securities, SecuritiesDetails, DailyOhlc, DailyStockPrice, IndexList, VN30 IndexComponents, VN30 DailyIndex rows, IntradayOhlc, and the optional streaming realtime snapshot contract.
* SSI available but implementation or live result remains partial: IntradayOhlc freshness/rate-limit behavior, DailyIndex level validity for VN30, exact broad `VNINDEX` identifier discovery, and DailyStockPrice multi-session foreign-flow history.
* SSI endpoint exists but parameter or entitlement remains unknown: REST trade-tape candidate names such as `TradeTape`, `MatchedTrades`, and `SecuritiesTrades`; any true historical trade-tape source; any SSI broad-index alias not returned by `IndexList`.
* SSI endpoint not found in current repo/docs/evidence: fundamentals, financial statements, ratios, corporate actions, dividends, rights, splits, news, and macro.
* External-provider-only under current evidence: corporate actions/dividends/rights/splits, financial statements, ratios, news, macro, and explicit source-labeled `VNINDEX` fallback if SSI remains unresolved.

Phase 4.5A did not add runtime providers, fallback providers, scraping, fake rows, WebSocket/SSE delivery, FC Trading calls, or changes to `latest_price`.

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
- `SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE=X:{symbol}` by default.
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

This phase does not prove live reliability. Under the Phase 4.5A vocabulary, realtime is `optional_live_dependent` until current live stream rows are observed through the manager/cache path.

## Phase 4.0C-7E Streaming Channel Template Fix

Live diagnostics proved the official SSI stream requires no-space channel strings. Working verifier channels include `X:FPT`, `X-QUOTE:FPT`, and `X-TRADE:FPT`. Old spaced forms such as `X: FPT`, `X-QUOTE: FPT`, and `X-TRADE: FPT` can start transport but did not receive callbacks in live verification.

The project default is now `SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE=X:{symbol}`. Explicit custom overrides remain respected for diagnostics, and the verifier still supports channel-format variants with both spaced and no-space forms. This change does not add backend auto-start, does not mark realtime production reliable, does not alter `latest_price`, and does not implement trade tape.

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
