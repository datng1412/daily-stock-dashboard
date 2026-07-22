# SSI FastConnect V3 Migration Architecture and Gate

Status: Phase SSI-V3-B2 is implemented offline. The official `ssi-sdk==3.0.5` dependency, separate V3 configuration, and a lazy disabled-by-default REST adapter now exist for the bounded B2 capability set. FastConnect V2 remains the default and deployed production REST/realtime provider; no V3 live request, shadow traffic, production cutover, public API change, or frontend change occurred.

## Current migration gate

FastConnect V3 migration architecture and implementation phases are documented. SSI FastConnect V2 remains the sole deployed production REST and realtime provider. The prior SSI-V3-A1 result remains outcome D for the exact credential-field mapping tested; B2 did not retest it. It continues to block live V3 acceptance, shadow traffic, and capability cutover until SSI resolves V3 activation and identifier/key mapping.

SSI-V3-B2 retains missing, empty, `v2`, and case-normalized `V2` as V2. Explicit `v3` is accepted only when `SSI_V3_REST_ENABLED=true` and all three dedicated V3 credential names are populated. In that opt-in configuration, only B2-supported capabilities select V3; explicitly V2-pinned capabilities continue to select V2 by ownership, not fallback. Any V3 authentication, timeout, malformed-response, rate-limit, or provider failure remains a V3 failure and never invokes V2. Unknown versions fail configuration.

## Decision

**Primary outcome: D — EXISTING CREDENTIALS REJECTED BY V3.**

The repository retains the V2 `ssi-fc-data` 2.2.2 dependency and now also pins the official `ssi-sdk==3.0.5` package with the `ssi_sdk` namespace. Package metadata requires Python 3.10 or newer and points to the official SSI repository; B2 inspected it locally on Python 3.13.1. This dependency does not enable V3. On 2026-07-21, the earlier audit mapped the existing `SSI_FASTCONNECT_CONSUMER_ID` and `SSI_FASTCONNECT_CONSUMER_SECRET` values in memory to the documented V3 raw REST `apiKey` and `apiSecret` fields. The single authorized `POST /api/v3/auth/token` sequence returned HTTP 401 in 1,388 ms. It produced no access token, refresh token, expiry field, or rate-limit header.

This result is an explicit V3 rejection of the tested current-value/raw-field mapping, not a network failure and not proof that V2 credentials have stopped working. No market-data, index, file, or WebSocket parity request followed. Outcome D keeps V2 production ownership unchanged and requires SSI to confirm V3 account activation and the exact mapping of application/client identifier, API key, and API secret before another live attempt. B2 uses only dedicated V3 names and deterministic SDK fakes; it neither aliases V2 credentials nor changes that live gate.

## SSI customer notice and lifecycle

The SSI customer notice supplied to this project states:

| Milestone | Date | Project treatment |
| --- | --- | --- |
| FastConnect V2 maintained through | 30/06/2027 | Keep the existing V2 runtime unchanged while V3 is proven. |
| FastConnect V3 officially replaces V2 from | 01/07/2027 | A migration deadline to plan against, not a current runtime cutover. |

The official V3 pages reviewed document the V3 API and SDK, but did not state a conflicting V2 retirement date. The customer notice is therefore the recorded lifecycle authority for this repository.

## Evidence boundary

This gate uses official SSI Developer Portal/API/SDK material, the official SSI tutorial repository, public official-package metadata, and current repository inspection. It does not treat an inferred endpoint, an unauthenticated response, or a local mock as V3 production proof.

- [SSI Developer Portal](https://developers.ssi.com.vn/)
- [V3 API overview](https://developers.ssi.com.vn/docs/api-reference)
- [V3 SDK overview](https://developers.ssi.com.vn/docs/sdk/overview)
- [Official Python package metadata](https://pypi.org/project/ssi-sdk/)
- [Official SSI V3 tutorials](https://github.com/SSI-Securities-Inc/ssi-fastconnect-v3-tutorials)

The audit script, `scripts/audit_ssi_fastconnect_v3_capability.py`, keeps that distinction explicit: `documented`, `locally_inspected`, `live_verified`, `projected`, `unavailable`, and `inconclusive` are separate result states. It is import-safe and default-config-only. `--mode change-impact --allow-live` permits at most one existing-key authentication sequence; it does not retry or perform parity calls after rejection. The sanitized evidence contained only presence booleans, HTTP status, failure class, rate headers, and elapsed time; it was written atomically to an ignored path, reviewed for secret/token leakage, then deleted.

## SSI-V3-CONTRACT-DIFF — URL and parameter comparison

This is a documentation-only wire-contract comparison. V2 evidence comes from the installed `ssi-fc-data` 2.2.2 request models, package URL constants, current `SsiFastConnectFetcher` calls, and deterministic tests. V3 evidence comes only from the official SSI Developer Portal pages linked per row. No credential, provider request, SDK installation, unit/finality comparison, entitlement analysis, or semantic/data-parity conclusion belongs to this table.

V2 REST base: `https://fc-data.ssi.com.vn/api/v2/Market`. V3 REST base: `https://api.ssi.com.vn/api/v3`. V2 streaming connects through `https://fc-datahub.ssi.com.vn/v2.0/signalr`; the V3 portal documents `wss://stream.ssi.com.vn`.

| Capability | V2 method | V2 URL | V2 parameters | V3 method | V3 URL | V3 parameters | Added | Removed | Renamed | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Authentication | `POST` | `https://fc-data.ssi.com.vn/api/v2/Market/AccessToken` | JSON: `consumerID`, `consumerSecret` | `POST` | `https://api.ssi.com.vn/api/v3/auth/token` | JSON: `apiKey`, `apiSecret`, optional `otp` | `otp` | None at request-position level | `consumerID` → `apiKey`; `consumerSecret` → `apiSecret` | **URL_AND_PARAMS_CHANGED.** V2 main response is `status`, `message`, `data.accessToken`; V3 documents top-level `tokenType`, `accessToken`, `refreshToken`, `expiresAt`, `refreshExpiresAt`. Name-position comparison only; it does not prove credential-value equivalence. [V3 auth](https://developers.ssi.com.vn/docs/api-reference/auth-token) |
| Securities | `GET` | `https://fc-data.ssi.com.vn/api/v2/Market/Securities` | Current call: optional `market`, `pageIndex`, `pageSize`; installed model has the same fields | `GET` | `https://api.ssi.com.vn/api/v3/data/securitiesByBoard` | Exactly one filter from `symbol`, `board`, `index` | `symbol`, `index` filter alternatives | `pageIndex`, `pageSize` | `market` → `board` | **URL_AND_PARAMS_CHANGED.** V2 main rows use names such as `Market`, `Symbol`, `StockName`, `StockEnName`; V3 uses `board`, `symbol`, `symbolNameVi`, `symbolNameEn`, `lotSize`, `listedShare`, and other lower-camel fields. [V3 securities](https://developers.ssi.com.vn/docs/api-reference/data-securitiesByBoard) |
| SecuritiesDetails | `GET` | `https://fc-data.ssi.com.vn/api/v2/Market/SecuritiesDetails` | Optional `market`, `symbol`, `pageIndex`, `pageSize` | `GET` candidate only | `https://api.ssi.com.vn/api/v3/data/securitiesByBoard?symbol=...` | `symbol` only for the exact-symbol candidate | None | `market`, `pageIndex`, `pageSize`; dedicated endpoint | None for `symbol` | **NO_DIRECT_V3_EQUIVALENT.** `securitiesByBoard?symbol=` is a possible lookup, not a documented V3 `SecuritiesDetails` replacement. Its lower-camel response fields differ from V2 metadata names and coverage. [V3 securities](https://developers.ssi.com.vn/docs/api-reference/data-securitiesByBoard) |
| DailyStockPrice | `GET` | `https://fc-data.ssi.com.vn/api/v2/Market/DailyStockPrice` | `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, optional `market` | `GET` | `https://api.ssi.com.vn/api/v3/data/securitiesSummary` | One of `symbol` or `index`; required `from`, `to`; optional `pageIndex`, `pageSize` | `index` alternative | `market` | `fromDate` → `from`; `toDate` → `to` | **URL_AND_PARAMS_CHANGED.** `symbol`, `pageIndex`, `pageSize` keep their names. V2 fields such as `TradingDate`, `RefPrice`, `TotalMatchVol`, `ForeignBuyVolTotal` change to V3 names such as `tradingDate`, `totalMatch`, `totalForeignBuy`, `totalForeignBuyValue`; V3 summary does not document V2 `RefPrice`/ceiling/floor names. [V3 summary](https://developers.ssi.com.vn/docs/api-reference/data-securitiesSummary) |
| DailyOhlc | `GET` | `https://fc-data.ssi.com.vn/api/v2/Market/DailyOhlc` | `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, `ascending` | `GET` | `https://api.ssi.com.vn/api/v3/data/ohlc` | `symbol`, required `from`, `to`; optional `timeFrame`, `pageIndex`, `pageSize` | `timeFrame` (`1d` selects daily; default is `1d`) | `ascending` | `fromDate` → `from`; `toDate` → `to` | **URL_AND_PARAMS_CHANGED.** Main row names move from V2 PascalCase aliases (`TradingDate`, `Open`, `High`, `Low`, `Close`, `Volume`, `Value`) to V3 lower-camel names (`tradingDate`, `open`, `high`, `low`, `close`, `volume`, `value`). [V3 OHLC](https://developers.ssi.com.vn/docs/api-reference/data-ohlc) |
| IntradayOhlc | `GET` | `https://fc-data.ssi.com.vn/api/v2/Market/IntradayOhlc` | Installed model: `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, `ascending`, `resolution`; the compact StockClock path also has documented compatibility probes | `GET` | `https://api.ssi.com.vn/api/v3/data/ohlc` | `symbol`, required `from`, `to`; optional `timeFrame`, `pageIndex`, `pageSize` | Unified timeframe values (`1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `1d`) | `ascending`; separate intraday endpoint | `fromDate` → `from`; `toDate` → `to`; `resolution` → `timeFrame` | **URL_AND_PARAMS_CHANGED.** V2 can expose separate `TradingDate` and `Time`; V3 documents one `tradingDate` field in the common OHLC row. This is only a field-name/shape observation. [V3 OHLC](https://developers.ssi.com.vn/docs/api-reference/data-ohlc) |
| IndexList | `GET` | `https://fc-data.ssi.com.vn/api/v2/Market/IndexList` | Current call: optional `market`; installed model: `exchange`, `pageIndex`, `pageSize` | `GET` | `https://api.ssi.com.vn/api/v3/data/indexList` | Optional `board` | None | V2-model `pageIndex`, `pageSize` | Current `market` / model `exchange` → `board` | **URL_AND_PARAMS_CHANGED.** V2 normalizes `IndexID`/`IndexCode`, `IndexName`, `Exchange`/`Market`; V3 documents `index`, `indexName`, `board`. [V3 index list](https://developers.ssi.com.vn/docs/api-reference/data-indexList) |
| DailyIndex | `GET` | `https://fc-data.ssi.com.vn/api/v2/Market/DailyIndex` | `requestId`, `indexId`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, `orderBy`, `order` | `GET` | `https://api.ssi.com.vn/api/v3/data/indexSummary` | Required `board`; optional `index`, `tradingDate` | Required `board` | `requestId`, range fields, paging, ordering | `indexId` → `index`; date range replaced by single `tradingDate` | **URL_AND_PARAMS_CHANGED.** V2 main aliases include `TradingDate`, `IndexValue`, `Change`/`RatioChange`, `TotalVol`, breadth fields; V3 documents `tradingDate`, `indexValue`, `indexChange`, `indexChangePercentage`, `totalTrade`, and `total*Stock`. [V3 index summary](https://developers.ssi.com.vn/docs/api-reference/data-indexSummary) |
| IndexComponents | `GET` | `https://fc-data.ssi.com.vn/api/v2/Market/IndexComponents` | `indexCode`, `pageIndex`, `pageSize`; StockClock can also send optional `market` | `GET` candidate | `https://api.ssi.com.vn/api/v3/data/securitiesByBoard?index=...` | `index` only for component lookup | None | `pageIndex`, `pageSize`, optional `market`; dedicated endpoint | `indexCode` → `index` | **URL_AND_PARAMS_CHANGED.** V2 currently flattens `IndexComponent[].StockSymbol` under an outer index row; V3 returns flat securities rows with `symbol` and board/security fields. Similar membership intent does not prove response parity. [V3 securities by index](https://developers.ssi.com.vn/docs/api-reference/data-securitiesByBoard) |
| Realtime/WebSocket | SignalR/WebSocket transport; invoke hub method | `https://fc-datahub.ssi.com.vn/v2.0/signalr`; hub `FcMarketDataV2Hub` | `SwitchChannels(selected_channel)` with a V2 channel string such as `X:FPT` | WebSocket messages | `wss://stream.ssi.com.vn` | JSON: `method`, `channel`, `topics`; methods include `SUBSCRIBE`, `UNSUBSCRIBE`, `LIST_SUBSCRIPTION`, `PING`, `PONG`; market-data channel is `DATA` | `method`, `channel`, topic list and explicit subscription operations | SignalR hub/method invocation and one `selected_channel` string | `SwitchChannels` structure → `SUBSCRIBE`/`UNSUBSCRIBE` message structure | **URL_AND_PARAMS_CHANGED.** V3 topic patterns include `trade.*`, `quote.*`, `room.*`, `market.*`, `put.*`, and `oddlot.*`; event fields use `eventType` and compact keys such as `s`, `t`, `p`, `q`, `si`. Documentation comparison only. [V3 connection](https://developers.ssi.com.vn/docs/api-reference/connectWebSocket), [V3 subscriptions](https://developers.ssi.com.vn/docs/api-reference/subscribeUnsubscribeMarketData) |

### Parameters unchanged

- REST HTTP methods remain `POST` for authentication and `GET` for all compared market-data endpoints.
- `symbol` keeps the same spelling on DailyStockPrice/securitiesSummary and V2/V3 OHLC requests.
- `pageIndex` and `pageSize` keep their names on DailyStockPrice → securitiesSummary and DailyOhlc/IntradayOhlc → V3 OHLC.
- Pagination defaults are not unchanged: the V2 2.2.2 models default to page 1/size 100, while the V3 summary/OHLC pages document page 1/size 10. StockClock often supplies explicit sizes, so this is a contract-default difference, not a runtime result.

### Parameters renamed

- `consumerID` → `apiKey`; `consumerSecret` → `apiSecret` at the documented auth request positions. This does not claim the same values are valid.
- `market` or V2 model `exchange` → V3 `board` for the corresponding board filters.
- `fromDate` → `from`; `toDate` → `to`.
- `indexId` or `indexCode` → `index` on the corresponding V3 query.
- V2 IntradayOhlc `resolution` → common V3 OHLC `timeFrame`.
- V2 `SwitchChannels(selected_channel)` is structurally replaced by V3 `{method, channel, topics}` messages; this is not a one-field rename.

### Parameters added

- Authentication: optional `otp`.
- `securitiesByBoard`: alternative `symbol` and `index` filters alongside `board`.
- `securitiesSummary`: alternative `index` query.
- Common V3 OHLC: `timeFrame` selects daily or intraday cadence.
- V3 index summary: required `board` and optional single `tradingDate`.
- V3 WebSocket: explicit `method`, `channel`, and `topics` array.

### Parameters removed

- `Securities`/`SecuritiesDetails`/`IndexComponents` paging is not documented on `securitiesByBoard`.
- DailyStockPrice `market` is not documented on `securitiesSummary`.
- DailyOhlc/IntradayOhlc `ascending` is not documented on V3 OHLC.
- V2 DailyIndex `requestId`, range pagination, and ordering fields are absent from V3 `indexSummary`.
- V2 IndexList paging is absent from V3 `indexList`.
- V2 SignalR hub and `SwitchChannels` parameters are absent from the V3 WebSocket request structure.

### Date and response-name changes

- StockClock formats V2 REST dates as `DD/MM/YYYY`. V3 summary/daily OHLC/index summary document `YYYY/MM/DD`; V3 intraday OHLC documents `YYYY/MM/DD HH:mm:ss`.
- V2 DailyIndex uses `fromDate`/`toDate`; V3 index summary uses one optional `tradingDate`.
- V3 responses generally use lower-camel names and different envelopes/field names. Matching words or different casing do not establish semantic or data parity.

### No direct V3 equivalent

- No dedicated V3 `SecuritiesDetails` endpoint is documented. `securitiesByBoard?symbol=` is only a candidate exact-symbol lookup with a different documented row contract.
- No other row is labelled `NO_DIRECT_V3_EQUIVALENT`: the table records candidate replacements for comparison without claiming parity.

## Existing credential mapping and live result

| Current concept/name | V2 meaning | V3 raw REST meaning | V3 SDK meaning | Status | Result |
| --- | --- | --- | --- | --- | --- |
| `SSI_FASTCONNECT_CONSUMER_ID` | V2 `ConsumerID` | Candidate `apiKey` | Candidate `api_key`; separate `client_id` remains unresolved | `reuse_with_name_mapping` | Value reused in memory; V3 returned 401. |
| `SSI_FASTCONNECT_CONSUMER_SECRET` | V2 `ConsumerSecret` | Candidate `apiSecret` | `api_secret` | `reuse_with_name_mapping` | Value reused in memory; V3 returned 401. |
| Separate SDK client identifier | No separate current production name | Not required by documented raw auth | `client_id` | `unresolved` | Do not duplicate or guess an existing value. |
| Private key | Not used by current market-data adapter | Not required for documented market-data token request | V3 SDK/trading configuration | `V3_only` | Not introduced. |
| OTP/two-factor data | Not used by current market-data adapter | Optional; omission grants market-data-only token when auth succeeds | Required for documented Trading/Stream SDK flows | `not_required_for_market_data` | Not requested or stored. |
| V2 access token | V2 runtime output | Not accepted as a V3 credential | Not reusable | `V2_only` | No cross-version token reuse. |
| V3 access/refresh token | No current value | V3 auth output | V3 Auth-managed output | `V3_only` | No token was returned or persisted. |

The same **values were tested**, but credential-value reuse, configuration-name reuse, authentication-flow reuse, token-format reuse, and client reuse are separate decisions. This audit proves only that the tested two-field raw REST mapping was explicitly rejected. It does not identify whether the account needs V3 activation, whether SSI assigns a distinct API key, or how the SDK's separate `client_id` maps to the current V2 identifier.

## Complete V2-to-V3 change-impact matrix

| Capability | Current V2 implementation | V3 equivalent | Reuse unchanged | Required change | Keep V2 temporarily | New in V3 | Exit criterion | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Authentication | `get_access_token`; V2 `AccessToken` | `POST /api/v3/auth/token`; `Auth` | No | Request fields, token/refresh lifecycle, expiry, error/rate handling | Yes | Refresh-token lifecycle | V3 shadow auth/refresh/error acceptance after SSI resolves 401 and identifier mapping | Repo + official auth contract + retained sanitized 401 summary |
| Securities | `get_securities`; V2 `Securities` | `securitiesByBoard?board=` | Business consumers only | Query, envelope, pagination, type normalization | Dual-run | Board/index/symbol query model | Bounded coverage and instrument-type authority parity | Official contract; no live row |
| SecuritiesDetails | `get_securities_details` | `securitiesByBoard?symbol=` subset | No | Field-by-field metadata normalizer | Yes | None proven | Every consumed exact-symbol field is mapped or truthfully null | Official contract only |
| DailyOhlc | `get_daily_ohlcv`; canonical `latest_price` | `/data/ohlc?timeFrame=1d` | Daily business contract | Dates, paging, envelope, price/volume/value normalization | Dual-run | Additional intervals | Completed-session price, unit, ordering, pagination, and finality parity | Official contract only |
| Completed-session intraday | `get_intraday_ohlcv` / `get_completed_intraday_1m` | `/data/ohlc?timeFrame=1m` | Chart business contract | Timestamp/timezone/bucket/volume normalizer | Dual-run | 3m/5m/15m/30m candidates | Same-session bar/time/volume parity | Official contract only |
| Current-session delayed 1m | V2 IntradayOhlc/X-TRADE-backed paths | V3 OHLC or Stream, unresolved | No | Source selection and active-session finality | Yes | Potential stream source | Market-hours newest-bar/finality acceptance | Unresolved |
| DailyStockPrice | `get_daily_stock_price` | `/data/securitiesSummary` | No | Envelope and complete field mapping | Yes | Daily summary endpoint | Completed-session null/zero/unit/finality parity | Fields documented; no live row |
| Foreign-flow history | DailyStockPrice via `vietnam_foreign_flow_service` | `/data/securitiesSummary` foreign totals | Analytics only | Provider adapter; units/finality/direct-net proof | Yes | None beyond replacement | Same-symbol/date values match or a deterministic conversion is proven | Fields documented; units unverified |
| Foreign-flow analytics | Coverage, sign, ranking, summaries | Same normalized rows | Yes | Provider input adapter only | No | No | Existing domain tests plus adapter parity | Version-neutral business logic |
| IndexList | `get_index_list` | `/data/indexList` | Consumers only | Identifier/envelope mapping | Migrate later | No | Identity/code coverage parity | Official contract only |
| DailyIndex | `get_daily_index` | `/data/indexSummary` | Index consumers only | Identifier/date/OHLC/breadth/value/volume normalizer | Dual-run | No | Same-index/date normalized units and finality parity | Official contract only |
| IndexComponents / VN30 | `get_index_components(indexCode=VN30)` | `securitiesByBoard?index=VN30` | VN30 aggregation logic | Component/effective-time normalizer | Yes | Index-scoped security rows | Symbols/count/weights/effective-time comparison | Official contract only |
| Realtime quote | V2 SignalR `X` | V3 Stream quote topic | Last-known product semantics only | Stream manager, auth, URL, topic, heartbeat, reconnect, fields | Yes | Unified stream client | Market-hours one-symbol shadow proves lifecycle and freshness | Official model/protocol only |
| Realtime trade | V2 SignalR `X-TRADE` | V3 Stream trade topic | Tape product semantics only | Side/sequence/dedupe/timestamp mapping | Yes | Unified stream client | Bounded market-hours trade parity and reconnect proof | Official model/protocol only |
| Order book | V2 SignalR `X-QUOTE` | V3 Stream quote/order-book topic | Last-known UI contract only | Snapshot/delta/depth reconstruction | Yes | Unified stream client | Full ladder and reconnect snapshot recovery | Unresolved live semantics |
| Foreign room | V2 SignalR `R` | V3 Stream foreign-room model/topic | Daily-vs-realtime separation | Topic, unit, snapshot normalization | Yes | Unified stream model | One-symbol units/null/zero/after-hours proof | Documented model; no live topic proof |
| Session/status | V2 SignalR `F` | No direct equivalent proven | No | Replacement contract required | Yes | None proven | Official V3 equivalent or retained live evidence | Inconclusive |
| Market/index stream | V2 SignalR `MI` | V3 market/index topics | Product separation only | Topic/field/unit/lifecycle mapping | Yes | Unified stream client | Bounded index shadow and after-hours proof | Official protocol only |
| Cache/single-flight | Existing service/fetcher policy | Provider-version-isolated shadow keys | Business policy | Separate V3 key namespace/metrics | No | V3 rate metadata | Shadow isolation and rate-budget acceptance | Repository design |
| Public API/frontend | Normalized VN payloads | Same normalized payloads | Yes | None if adapter preserves contract | No | No | Existing API/frontend tests remain green | Repository contract |
| Historical market file | Not used | `/data/file` temporary link | No | New bounded ingestion/download design | No | Yes, optional | Entitlement, expiry, size, units, safety proven | Official contract only |
| Rate-limit metadata | V2 internal guardrails | V3 headers + SDK limiter | Business throttling goals | New V3 header/SDK interpretation | No | Yes, optional | Live header/reset semantics proven | Header names documented |
| V2 package/import/config assets | `ssi-fc-data`, V2 models and names | `ssi-sdk` future candidate | No | Dependency/import/config/deployment replacement | Until full cutover | No | All capabilities accepted plus rollback window completed | Projected removal only |
| Instrument-type authority | Incomplete V2 authority | V3 security rows | No | Official type mapping/field | No migration decision possible | No | Official mapping or authoritative retained live field | Inconclusive |

Each capability has exactly one primary migration decision in the machine-readable `change-impact` report. The detailed report also records request/response/field/unit/finality, cache, error, test, frontend, evidence, and blocking-gap fields for every row.

## Required migration groups

### What can remain unchanged

- `REUSE_UNCHANGED`: foreign-flow analytics; public API/frontend contracts.
- `REUSE_BUSINESS_LOGIC_WITH_ADAPTER`: current-membership VN30 aggregation; cache/single-flight business policy.

### What must be changed

- `MIGRATE_TO_V3_FIRST`: a disabled V3 shadow-auth foundation, only after an A/B gate.
- `MIGRATE_TO_V3_LATER`: IndexList after identifier parity.
- `DUAL_RUN_FOR_PARITY`: Securities, DailyOhlc, completed-session intraday OHLCV, and DailyIndex.
- Authentication client/token lifecycle, request models, pagination, response extraction, field normalization, rate handling, and the stream manager are adapter/runtime changes; they are not business-rule changes.

### What stays on V2 for now

V2 authentication, SecuritiesDetails, current-session 1m, DailyStockPrice, foreign-flow history, IndexComponents, quote, trade, order book, foreign room, session/status, and market/index stream remain primary. Every retained row has a concrete exit criterion in the matrix/audit output. Immediate migration risks unverified units, finality, component effective time, metadata loss, stream gaps, or cache/lifecycle regressions.

### What V3 adds

Optional, not implemented: historical market files, extra candle intervals, V3 rate-limit headers/SDK limiting, SDK retry, and token refresh. Trading/account capabilities are outside StockClock's market-data scope and are not migration recommendations.

### What will be removed after cutover

Only after per-capability acceptance and a rollback window: V2-only package/imports, V2 request models/normalizers, V2 token handling, V2 credential aliases, V2-only cache keys/error mapping/tests, and V2 Docker dependency installation. None were removed in A1.

### What remains unresolved

The V3 SDK `client_id` mapping, reason for the 401/account activation state, instrument-type/HOSE common-stock authority, full SecuritiesDetails parity, foreign-flow units/finality, component effective dates/weights, stream URL/OTP/entitlement/topic semantics, F-channel replacement, and all bounded market-data parity remain unresolved.

## Current V2 baseline and coupling

The current runtime uses the official V2 package `ssi-fc-data` 2.2.2 (`ssi_fc_data`) declared in `requirements.txt`. V2 remains coupled through:

- `data_provider/ssi_fastconnect_fetcher.py`: `Securities`, `SecuritiesDetails`, `DailyOhlc`, `DailyStockPrice`, `IndexList`, and `IndexComponents` normalization and caching.
- `data_provider/ssi_streaming_realtime.py`: V2 SignalR/background streaming lifecycle.
- `src/services/vietnam_market_service.py` and `src/services/vietnam_foreign_flow_service.py`: V2-backed daily, metadata, index, and foreign-flow service construction.
- `src/config.py` and `.env.example`: V2 base URL and consumer-ID/secret configuration only.

`latest_price` remains the V2 SSI `DailyOhlc` close. V2 SSI `DailyStockPrice` remains the separate enrichment owner for reference/limits, matched/put-through data, and completed-session foreign-flow fields. Its current foreign-flow contract is `daily_available`, shares for volume, VND for value, nullable missing fields, and direct provider net precedence. No V3 result changes any of these rules.

Phase 4.12F-A2's bounded V2 `SecuritiesDetails` evidence remains outcome F because the live response was not retained. SSI-V3-A does not reopen that V2 probe.

## Official V3 SDK, authentication, and URLs

| Topic | Documented V3 finding | Migration state |
| --- | --- | --- |
| Python SDK | `ssi-sdk`, imported as `ssi_sdk`; the official PyPI metadata reviewed on 2026-07-21 lists version `3.0.5`, Python `>=3.10`, and SDK names `Config`, `Auth`, `Data`, and `Stream`. | Official candidate identified; not locally installed or imported by production. |
| REST base/version | `https://api.ssi.com.vn/api/v3/...` | Documented, not live-verified. |
| Authentication | `POST /api/v3/auth/token` accepts `apiKey`, `apiSecret`, and optional `otp`; portal states market data does not require OTP while trading permission does. | Existing V2 values mapped to the two raw fields were explicitly rejected with HTTP 401; cause/account mapping remains SSI-owned. |
| Tokens | Response documents access/refresh token fields and expiries. | Values are never logged, written, or committed by this audit. |
| Rate limits | `X-RATELIMIT-LIMIT`, `X-RATELIMIT-REMAINING`, and `X-RATELIMIT-RESET` are documented response headers. | Contract verified; no live values observed. |
| Stream URL | Portal documents `wss://stream.ssi.com.vn`; Python SDK metadata documents `wss://api.ssi.com.vn/ws/v3`; official Go examples show `wss://stream.ssi.com.vn/ws/v3`. | Inconclusive; resolve with one bounded authenticated V3 connection, not a guessed production change. |

Relevant official references: [auth token](https://developers.ssi.com.vn/docs/api-reference/auth-token), [WebSocket connection](https://developers.ssi.com.vn/docs/api-reference/connectWebSocket), and [official Go SDK examples](https://github.com/SSI-Securities-Inc/ssi-sdk-go).

The earlier Phase A `live-smoke` mode retains separate audit-only V3 names for a future explicitly provisioned V3 credential/symbol probe. A1 does not require or create them: `change-impact` maps the current V2 identifier and secret to the raw V3 auth request only when `--allow-live` is explicit. Neither path enables production V3 traffic or modifies `.env`.

## V2-to-V3 capability map

| Current V2 use | Official V3 candidate | Parity status | Limitation before migration |
| --- | --- | --- | --- |
| `Securities` | [`GET /api/v3/data/securitiesByBoard`](https://developers.ssi.com.vn/docs/api-reference/data-securitiesByBoard), one of `symbol`, `board`, or `index` | Partial | V3 documents symbol/name/board and selected security fields, not an authoritative instrument type. |
| `SecuritiesDetails` | `securitiesByBoard` exact symbol row | Partial | No direct documented V2-details-equivalent field contract. |
| `DailyOhlc` | [`GET /api/v3/data/ohlc`](https://developers.ssi.com.vn/docs/api-reference/data-ohlc) | Transformed partial | Symbol/date/timeframe/pagination are documented; exact price/date/volume normalization needs live proof. |
| `DailyStockPrice` | [`GET /api/v3/data/securitiesSummary`](https://developers.ssi.com.vn/docs/api-reference/data-securitiesSummary) | Transformed partial | Historical foreign buy/sell totals and value totals are documented, but units, finality, direct net fields, and all V2 field semantics are not yet proven. |
| `IndexList` | `GET /api/v3/data/indexList` | Partial | Documented only; exact identifier rows need live proof. |
| `IndexComponents` | `securitiesByBoard?index=<index>` | Transformed partial | Current component rows are documented; historical membership is not. |
| V2 streaming realtime | V3 WebSocket `SUBSCRIBE`/`UNSUBSCRIBE`, `DATA`/`TRADING`/`HEARTBEAT`, scoped quote/trade/room/market topics | Partial | Entitlement/OTP behavior, endpoint choice, message semantics, and V2-to-V3 timestamp/price parity need live proof. |

V3 pagination is documented as one-based `pageIndex` plus `pageSize`; `securitiesSummary` documents `pageSize`, `pageIndex`, `pagesCount`, `itemsCount`, and `data`. V3 OHLC similarly documents bounded page controls. There is no official evidence in this gate for broad-market or multi-symbol daily-history retrieval; those remain **unsupported** rather than inferred from paged single-symbol paths.

The documented [`/api/v3/data/file`](https://developers.ssi.com.vn/docs/api-reference/data-marketFile) requires a symbol and returns a temporary `dataLink` for CSV-style OHLCV data. It does not document ZIP output, broad-market history, or a replacement for DailyStockPrice foreign-flow history. No link was followed and no file was downloaded.

## Security master and HOSE authority

`securitiesByBoard` can retrieve one exact symbol, one board, or one index. Its documented fields include symbol, names, board, lot size, selected dates, listed share, ICB fields, and other security-specific attributes. The documented contract does not establish a raw security/instrument-type field or an official mapping of coded values to common stock, ETF, covered warrant, fund, bond, or preferred stock.

Therefore:

- exact symbol/board identity is a **partial** V3 capability;
- instrument-type authority is **inconclusive**;
- HOSE common-stock authority is **inconclusive**;
- a HOSE board result, a numeric code, or a partial sample must not be relabelled as common stock;
- V3 does not yet resolve the V2 HOSE authority blocker.

The audit accepts an instrument class only from an explicit label or an explicitly documented mapping. It rejects unknown numeric codes and conflicting type fields. A future V3 live sample must remain bounded and exact; it cannot establish full-universe authority merely by returning a few records.

## Historical and foreign-flow semantics

V3 `securitiesSummary` documents `totalForeignBuy`, `totalForeignBuyValue`, `totalForeignSell`, and `totalForeignSellValue` alongside daily summary fields. The current documentation reviewed does not prove:

- whether those amounts use StockClock's current shares/VND units;
- that they are final completed-session values;
- direct foreign-net volume/value fields and their precedence over derived net;
- correction timing;
- multi-symbol/market-wide availability.

The audit maps missing direct net to `null`, preserves a documented explicit zero as zero, keeps value and volume separate, and labels units/finality `unknown_pending_live_proof`. It does not calculate or expose V3 foreign flow to the application. The current V2 DailyStockPrice fan-out remains the only implementation.

## Index and realtime capability

V3 API overview documents index list and summary endpoints. `securitiesByBoard?index=<index>` is the candidate for current components. Historical index membership is not documented and remains unavailable/inconclusive.

V3 streaming documentation uses a single connection model with `SUBSCRIBE`/`UNSUBSCRIBE` messages, scoped topics, heartbeat, and re-subscription after reconnect. It describes quote/trade/room/market topic families; it does not let this phase claim V2 parity or current-session foreign-flow semantics. The audit plan allows at most one connection, one scoped subscription, and ten seconds only after explicit live authorization. It rejects full-market subscriptions and implements no reconnect loop.

The documented cash-market candidates are the scoped trade, quote, and room topics; the documented index/market candidate is the scoped market topic. No separate derivative-channel contract was verified in this gate. The SDK documentation names a foreign-room message with buy/sell quantity/value fields, but that does not prove current-session daily foreign-flow units, finality, or reconciliation semantics, so it remains separate from the DailyStockPrice migration path.

## Capability sub-gates

| Sub-gate | Current status | Basis |
| --- | --- | --- |
| Official SDK/package | Verified | Official `ssi-sdk`/`ssi_sdk` identified; package absent locally. |
| Authentication | Rejected | One existing-key/raw-field mapping received HTTP 401; no retry or data request followed. |
| API base URL/versioning | Verified | Official V3 REST path documented. |
| Security master | Partial | `securitiesByBoard` documented; full authority unproven. |
| Exact-symbol metadata | Partial | Symbol lookup documented; V2-details parity unproven. |
| Instrument-type authority | Inconclusive | No documented authoritative type field/mapping. |
| HOSE common-stock authority | Inconclusive | No V3 full-universe type proof. |
| Daily historical price | Partial | OHLC/summary contracts documented only. |
| Foreign buy/sell history | Partial | Fields documented; units/finality/net semantics unproven. |
| Broad/multi-symbol history | Unsupported | No documented contract found. |
| Historical file/ZIP access | Partial | Symbol-file `dataLink` documented; ZIP/broad history absent. |
| Index list | Partial | Documented, not live-proven. |
| Index components | Partial | Current index query documented; membership history unresolved. |
| Realtime quote | Partial | Scoped topics documented; no retained live messages. |
| Index/market stream | Partial | Market topics documented; no retained live messages. |
| WebSocket model | Partial | Protocol documented; endpoint/entitlement behavior unresolved. |
| Rate-limit contract | Verified | Header names documented. |
| Pagination | Verified | One-based history paging documented. |
| Side-by-side operation | Blocked | Feasible only after SSI resolves V3 activation/credential mapping and a later A/B gate opens shadow work. |
| V3 adapter/live viability | Blocked | Outcome D forbids V3 authentication, shadow, and cutover work; authentication and contract parity must be established first. The V2-only B1 adapter is permitted. |

## Proposed migration architecture — not implemented

Phase SSI-V3-B0 now freezes this provider-neutral internal surface, and the V2-only B1 implementation may proceed under outcome D. V3 adapter authentication, shadow, and cutover work still require the relevant open gates. The design target is a small fact-preserving interface, not a V2/V3 automatic fallback:

```text
security_master_page(board | index | symbol)
symbol_metadata(symbol, market)
daily_ohlcv(symbol, date_range, page)
daily_foreign_flow(symbol, date_range, page)
index_catalog()
index_membership(index_code)
```

The B1 protocol is REST-only; realtime cache reads remain on the existing V2 streaming boundary until SSI-V3-C. Each REST result would carry provider/version, request identity, source timestamp, paging/freshness, units, finality, and explicit missing/error state. V2 stays primary. V3 could only run in a separate, bounded shadow path with no product response ownership and no fallback. Compare raw normalized values, never formatted strings:

- symbol and market/index identity;
- trading date; open/high/low/close; volume;
- foreign buy/sell volume and value, including units/finality;
- current index components only;
- realtime source timestamps and message sequence where available.

No full historical parity, broad WebSocket topic, database persistence, scheduler, polling loop, V2 removal, production route change, or configuration migration is authorized by this document.

## SSI account/credential follow-up

SSI V3 account and credential-contract resolution is a parallel prerequisite for B2 live acceptance and all B4/B5 work. It is not required for the V2-only B1 contract and adapter:

1. Ask SSI to confirm whether the current account is V3-enabled and whether V2 `ConsumerID` is the V3 `apiKey`, the SDK `client_id`, both, or neither. Do not request or rotate a key speculatively.
2. Confirm the exact data-only V3 API key/secret mapping and whether a separate client identifier is assigned.
3. After SSI provides a concrete correction/activation, authorize one new bounded auth evidence phase; do not retry the rejected mapping unchanged.
4. Only after auth succeeds, use one provider-derived symbol for the bounded securities/history/index comparisons.
5. Resolve streaming separately because official SDK documentation requires OTP for Stream and the documented stream URLs differ.
6. Re-evaluate the migration gate. Do not begin V3 authentication, shadow traffic, or capability cutover unless the result becomes A or B; B1 remains V2-only.

No credential, token, header, raw provider payload, SDK archive, historical file, or live audit artifact was committed by SSI-V3-A1.

## SSI-V3-B0 implementation contract freeze

### Purpose

This section freezes how StockClock may implement the V2-to-V3 migration. It is a plan, not authorization to install, authenticate, send V3 traffic, or change a public response. Earlier sections retain the official wire-contract comparison and the SSI-V3-A1 evidence boundary.

### Current production baseline and V2 call graph

The production dependency remains official `ssi-fc-data` from the `python-fcdata` tag `v2.2.2`, imported through `ssi_fc_data`. Docker installs it from `requirements.txt`; no V3 package is installed. Current production configuration is V2-only: `SSI_FASTCONNECT_BASE_URL`, `SSI_FASTCONNECT_CONSUMER_ID`, and `SSI_FASTCONNECT_CONSUMER_SECRET` feed `SsiFastConnectFetcher`.

```text
FastAPI /api/v1/stocks/vn/* routes
  -> VietnamMarketService / VietnamCompanyResearchService
  |    -> lazy SsiFastConnectFetcher
  |         -> AccessToken
  |         -> DailyOhlc / IntradayOhlc / DailyStockPrice
  |         -> Securities / SecuritiesDetails
  |         -> IndexList / DailyIndex / IndexComponents
  |         -> V2 streaming-manager cache reads
  -> VietnamForeignFlowService / Batch / Vn30
       -> SsiFastConnectFetcher.get_daily_stock_price
       -> normalized daily rows
       -> rolling windows, rankings, coverage, VN30 aggregation

FastAPI lifespan
  -> schedules the existing V2 SSI streaming manager in the background
  -> shutdown owns cancellation and best-effort stream cleanup
```

| Current path | Importance | Production role | Migration treatment |
| --- | --- | --- | --- |
| V2 token and DailyOhlc | Production-critical | Canonical daily OHLCV and `latest_price` | V2 until daily OHLC gate passes |
| DailyStockPrice | Production-critical for foreign-flow workspace; production-important elsewhere | Reference/limits, matched/put-through fields, daily foreign flow | V2 until field, unit, null/zero, pagination, and finality gates pass |
| Securities / SecuritiesDetails | Production-important | Symbol identity and partial metadata | Board/basic identity may migrate first; extended metadata stays V2 |
| IndexList / DailyIndex / IndexComponents | Production-important | Index identifiers, optional summaries, current VN30 membership | Separate gates; membership stays V2 until effective-time parity |
| IntradayOhlc | Optional product capability | Completed/current-session delayed 1m chart data | Completed history may shadow; current-session stays V2 |
| X, X-TRADE, X-QUOTE, R, F, MI streaming | Optional and non-fatal | Quote, trades, order book, room, status, market pulse | V2 throughout REST migration; future SSI-V3-C only |
| Cache, single-flight, analytics, API schemas, frontend | Production-critical business policy | Stability, truthful states, calculations, presentation | Reuse behind provider-neutral inputs |
| V3 audit script and tests | Audit-only | Contract inventory and bounded evidence | Never treated as production routing |
| V3 market file / extra intervals | Unused | No current public product owner | Optional future capability only after a separate gate |

### Official V3 contract baseline

Only these official authorities inform this plan:

- [SSI Developer Portal](https://developers.ssi.com.vn/)
- [V3 API reference](https://developers.ssi.com.vn/docs/api-reference)
- [V3 SDK overview](https://developers.ssi.com.vn/docs/sdk/overview)
- [Official SSI V3 tutorials](https://github.com/SSI-Securities-Inc/ssi-fastconnect-v3-tutorials)
- [Official Python package metadata](https://pypi.org/project/ssi-sdk/)

The portal documents `Config -> Auth -> Data / Trading / Stream`, market-data REST without OTP, and OTP for trading and streaming. It documents the `ssi-sdk` package and `ssi_sdk` namespace, but B2 must recheck and pin an exact version at implementation time. The current documented endpoint candidates are the URL/parameter table above. Similar names establish candidates only, not units, completeness, finality, or parity.

### Frozen migration principles

1. V2 remains production until the specific capability's V3 acceptance gate passes.
2. Cutover is capability-specific, never an all-at-once provider replacement.
3. Existing StockClock APIs and frontend payload/state semantics remain stable.
4. Business logic consumes normalized provider-independent rows.
5. V2/V3 request objects and response envelopes stay inside their adapters.
6. A V3 error never triggers an automatic V2 request or response substitution.
7. Any intentional V2 ownership under V3 mode is declared by capability and observable.
8. Rollback is configuration-driven; global V2 rollback is always available.
9. REST and streaming migrations are separate projects.
10. Realtime remains V2 through B1-B5.
11. Foreign-flow analytics and VN30 aggregation are reused when normalized inputs remain stable.
12. Missing stays `null`; explicit provider zero stays zero.
13. Similar field names never prove unit, finality, or semantic parity.
14. Future shadow traffic is disabled by default, bounded, cancellable where practical, and rate-limit-aware.
15. Trading, accounts, orders, transfers, and portfolio actions are outside this migration.

### B1 architecture

The narrowest design consistent with current code is a structural `Protocol`, not an abstract base class. The repository already uses `Protocol` for SSI streaming and corporate-action providers, and current services are constructor-injectable. A protocol avoids inheritance and lets deterministic fakes and the existing fetcher satisfy the contract without changing runtime representation.

```text
data_provider/
  ssi_fastconnect_fetcher.py       # existing V2 implementation, retained
  ssi_provider_models.py           # normalized TypedDict/value contracts
  ssi_provider_protocol.py         # REST-only structural Protocol
  ssi_v2_adapter.py                # delegating wrapper; no behavior rewrite
  ssi_provider_router.py           # V2-default selector + central capability router
  ssi_fastconnect_v3_fetcher.py    # future disabled V3 REST adapter

services
  -> resolve one provider-neutral capability router lazily
  -> keep business calculations, public schemas, and state semantics

V2 streaming lifecycle
  -> remains separate and unchanged through B1-B5
```

Responsibilities are frozen as follows:

| Layer | Responsibility |
| --- | --- |
| Normalized models | Provider-independent identity, dates/times, numerics, null/zero, source/version, completeness/finality |
| REST protocol | Only capabilities consumed by current services; no streaming or trading methods |
| V2 adapter | Delegate to `SsiFastConnectFetcher`; preserve returned normalized values and errors exactly |
| V3 adapter | Construct V3 requests, own Auth/Data clients and close lifecycle, normalize V3 responses; disabled until configured |
| Capability router | Resolve the declared provider before a call; never catch a V3 error and invoke V2 |
| Cache owner | Provider adapter owns raw/provider cache; services own business/public cache; both keys include provider version |
| Shadow comparator | Separate bounded observer; V2 response remains authoritative and V3 never writes production cache |
| Service/API | Business rules, public status semantics, response schemas, and frontend contract |

### Provider routing decision

Use central capability routing in `ssi_provider_router.py`, then inject or lazily resolve the router in market and foreign-flow services. Per-service version branching is rejected because it would duplicate hybrid rules, cache identity, diagnostics, and no-fallback enforcement.

| Option | Benefit | Cost/risk | Decision |
| --- | --- | --- | --- |
| Central capability router | One manifest for intentional V2 retention, one no-fallback boundary, consistent cache/version diagnostics | Adds one small routing module and injection seam | **Recommended** |
| Provider injection/version branching per service | Keeps each service locally explicit | Duplicates hybrid decisions across market, metadata, index, and foreign-flow paths; easier to drift or fall back accidentally | Rejected for version selection; services still receive the central router by injection |

B1 selector:

```text
SSI_FASTCONNECT_REST_VERSION=v2|v3
```

| Value | B1 behavior |
| --- | --- |
| Missing or empty | Preserve current V2 production behavior |
| `v2` | Route every REST capability to V2 |
| `v3` | Configuration error: `SSI FastConnect V3 REST adapter is not implemented in phase B1` |
| Unknown | Fail configuration validation with a clear secret-free message before provider work |

The router chooses a provider before execution. `v3 -> error -> v2` is forbidden. B1 does not introduce per-capability environment overrides. B5 may add one bounded V3 capability allow-list only if operations needs independent rollback without deployment; until then, the accepted-capability manifest is versioned in the router and global `v2` is the guaranteed rollback. `SSI_FASTCONNECT_REST_VERSION` never controls streaming.

### Planned configuration contract

`SSI_FASTCONNECT_REST_VERSION` is implemented in B1 and documented in `.env.example`. The V3 names below remain documentation only and must not be added to `.env.example`, Render, Docker, or configuration code before B2.

| Name | Classification | Planned use | Resolution requirement |
| --- | --- | --- | --- |
| `SSI_FASTCONNECT_REST_VERSION` | Non-secret; default `v2` | Explicit REST selector | B1; unknown values are errors |
| `SSI_V3_CLIENT_ID` | Secret-adjacent identifier | Official SDK `Config.client_id` | Authoritative source/mapping unresolved; blocks B2 auth acceptance |
| `SSI_V3_API_KEY` | Secret | V3 REST/SDK market-data authentication | Must be SSI-issued/confirmed |
| `SSI_V3_API_SECRET` | Secret | V3 REST/SDK market-data authentication | Must be SSI-issued/confirmed |
| `SSI_V3_API_URL` | Defaultable non-secret | V3 REST base URL | Default only from official contract |
| `SSI_V3_REQUEST_TIMEOUT` | Defaultable non-secret | Finite REST timeout | B2 deterministic bounds |
| `SSI_V3_MAX_RETRIES` | Defaultable non-secret | Contract-safe retry ceiling | Must exclude auth/validation/non-retryable errors |
| `SSI_V3_RETRY_DELAY` | Defaultable non-secret | Bounded backoff | Coordinate with rate-limit headers |
| `SSI_V3_RATE_LIMIT_PER_SECOND` | Defaultable non-secret | Local upper bound | Must not exceed official entitlement; exact limit unresolved |
| `SSI_V3_PRIVATE_KEY` | Secret, trading-oriented | SDK signing only if an approved future scope proves it necessary | Not required by the documented raw market-data token request; out of current scope |
| `SSI_V3_OTP` | Ephemeral secret, trading/streaming | Future trading or streaming authentication | Never required or stored for B1-B5 REST market data |
| `SSI_V3_STREAMING_URL` | Non-secret | Future SSI-V3-C only | Authoritative URL remains unresolved |

Do not alias V2 names to V3 in code. If SSI later confirms identical underlying values, deployment may point the separate V2 and V3 secret names at the same secret-manager object; logs, docs, and diagnostics still expose names/presence only. V2 access tokens are never reused as V3 tokens.

### Public contract freeze

Provider migration occurs behind existing public contracts. The following `/api/v1/stocks/vn` routes, methods, query/body names, bounds, response schemas, error/status behavior, and cache headers remain compatible:

- `GET /watchlist/health?tickers=`
- `GET /watchlist?tickers=&force_refresh=&include_intraday=&intraday_timeframe=&intraday_limit=`
- `GET /company/{ticker}?force_refresh=`
- `GET /chart?symbol=&range=`
- `GET /index-list?market=&force_refresh=`
- `GET /intraday-chart/health`
- `GET /intraday-chart?ticker=&interval=&date=&force_refresh=`
- `GET /company-news?ticker=`; this non-SSI provider route is unaffected
- `GET /daily-index?index_codes=&from_date=&to_date=&limit=&force_refresh=`
- `GET /market-index-pulse?index_codes=`; remains V2 streaming-cache owned
- `GET /index-components?index_code=&market=&force_refresh=` including the hidden compatibility alias `index`
- `GET /foreign-flow/symbol/{ticker}?limit=&from_date=&to_date=&force_refresh=`
- `POST /foreign-flow/batch`
- `GET /foreign-flow/vn30?top_n=&force_refresh=`
- `GET /observability`
- `GET /corporate-actions?tickers=&months_back=`; unaffected external-provider contract
- `GET /realtime?tickers=` and `GET /realtime/trades?symbol=&limit=`; remain V2 streaming-cache owned

Their current Pydantic contracts remain `VietnamWatchlistHealthResponse`, `VietnamWatchlistResponse`, `VietnamCompanyResearchResponse`, `VietnamChartResponse`, `VietnamIndexListResponse`, `VietnamIntradayChartHealthResponse`, `VietnamIntradayChartResponse`, `VietnamCompanyNewsResponse`, `VietnamDailyIndexResponse`, `VietnamMarketIndexPulseResponse`, `VietnamIndexComponentsResponse`, `VietnamForeignFlowSymbolHistoryResponse`, `VietnamForeignFlowBatchRequest`/`VietnamForeignFlowBatchResponse`, `VietnamVn30ForeignFlowResponse`, `VietnamObservabilityResponse`, `VietnamCorporateActionsResponse`, `VietnamRealtimeResponse`, and `VietnamRealtimeTradesResponse`.

The frontend routes `/vietnam`, `/vietnam/company/:ticker`, and `/foreign-flow`, their controls, number formatting, loading/empty/partial/stale/unavailable states, and request ownership do not branch by provider version.

Public invariants:

- `latest_price` continues to use the normalized daily OHLC close; no summary or stream source overwrites it.
- Existing `source`, `actual_source`, `latest_price_source`, `source_endpoint`, cache-status, freshness, coverage, and error classifications retain their compatibility meaning.
- Missing object data remains `null`; missing list data remains `[]`; explicit zero is never converted to missing.
- Optional intraday/realtime/stream failures do not make valid daily rows fail.
- Any provider/version diagnostic is optional, additive, backward compatible, documented, and excluded from UI branching.
- Existing legacy endpoint labels such as `DailyStockPrice` remain compatibility fields. Before a V3 cutover, B3/B5 must add a truthful optional actual-provider/version diagnostic rather than silently relabel or misrepresent the upstream endpoint.

### Normalized provider models

Dates use ISO `YYYY-MM-DD` after normalization. Intraday timestamps use timezone-aware ISO 8601 with `Asia/Ho_Chi_Minh` semantics. Decimal/float conversion must reject non-finite values; counts and volumes use integers when provider precision permits. Every result carries `source=SSI`, `source_version=v2|v3`, and bounded provider diagnostics outside public domain values.

| Model | Required normalized fields | Optional fields | Validity, null, zero, and finality rules |
| --- | --- | --- | --- |
| Security row | `symbol`, `source`, `source_version` | `board`, VI/EN names, lot size, listed shares, dates, ICB fields, instrument type | Uppercase unique symbol; unknown optional metadata is null; no inferred instrument type |
| Exact-symbol metadata | `symbol`, `source`, `source_version`, `status` | board, names, profile fields, listed shares, security attributes | Exact symbol match required; partial fields stay null; provider empty is not a fabricated row |
| Daily OHLCV | `symbol`, `trading_date`, OHLC, `source`, `source_version` | volume, value, completeness/finality | Ordered unique sessions; finite numerics; zero preserved; canonical close only after row validation |
| Intraday OHLCV | `symbol`, `timestamp`, `timeframe`, OHLC, `source`, `source_version` | volume, value, raw timestamp, finality | Vietnam-time bucket semantics proven per timeframe; gaps remain gaps; current/completed finality explicit |
| Daily securities summary | `symbol`, `trading_date`, `source`, `source_version` | close/average, match/deal totals, reference/limits, foreign totals/room, completeness | No field substitution by name similarity; each missing optional field is null; zero preserved |
| Foreign-flow row | `trading_date`, `symbol`, gross buy/sell volume/value, net volume/value, `source`, `source_version` | finality, correction/completeness metadata | Direct net only when semantics are documented; otherwise derive only when both gross sides are usable; missing side makes derived net null |
| Index definition | `index_code`, `source`, `source_version` | index name, board | Provider identifier preserved; aliases require explicit mapping |
| Index summary | `index_code`, `trading_date`, `source`, `source_version` | value, change/percent, trade volume/value, breadth, proprietary totals, finality | Same identifier/date validation; missing breadth stays null; no OHLC synthesis |
| Index membership | `index_code`, `symbol`, `source`, `source_version` | board, weight, effective from/to | Uppercase unique symbols; mismatched outer index rejected; weight/effective time null until documented |
| Provider diagnostics/error | `provider`, `provider_version`, `capability`, `status` | error category, HTTP/provider code, retryable, duration, paging, rate-limit metadata, cache state | Secret-safe and bounded; no token/header/raw payload; diagnostics never replace domain nulls |

Foreign-flow minimum contract is therefore:

```text
trading_date, symbol,
foreign_buy_volume, foreign_sell_volume,
foreign_buy_value, foreign_sell_value,
foreign_net_volume, foreign_net_value,
source, source_version
```

The V2 direct-net precedence remains until a V3 direct-net field is officially documented and accepted. V3 gross-side derivation may be accepted only after units, zero/missing, date, correction, and finality gates pass.

### Capability migration matrix

Each row has exactly one primary category. “First implementation” means B1/B2 ownership, not production V3 acceptance.

| Capability | Primary category | Current StockClock use | Current V2 implementation | V3 candidate | Normalized contract | Planned provider in first implementation | Migration phase | Validation gate | V2 exit criterion | Rollback behavior | Open risks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Authentication/token | `IMPLEMENT_V3_DISABLED` | Required for all SSI REST calls | `get_access_token`, cached V2 token | `/auth/token`, refresh lifecycle, SDK `Auth` | Provider auth result/error only; tokens private | V2 production; V3 client disabled | B2, B4 | SSI-confirmed IDs; auth, refresh, expiry, error and rate handling | V3 auth accepted under bounded shadow and operational token lifecycle proven | Global selector `v2` | Prior field mapping returned 401; SDK `client_id` unresolved |
| Securities by board | `MIGRATE_TO_V3_FIRST` | Symbol universe/basic identity | `get_securities(market)` | `securitiesByBoard?board=` | Security row | V2 | B2, B4, B5 | Coverage, identity, duplicates, board and type-null behavior | Bounded board parity and missing-row classification pass | Route capability to V2 or global `v2` | No paging documented; type authority absent |
| Exact-symbol basic information | `DUAL_RUN_FOR_PARITY` | Metadata fallback and profile basics | Securities/SecuritiesDetails lookup | `securitiesByBoard?symbol=` | Exact-symbol metadata | V2 | B2, B4, B5 | Exact identity and every consumed basic field compared | Candidate supplies accepted basic subset without fabricated extended fields | Route capability to V2 | Candidate is not full SecuritiesDetails parity |
| SecuritiesDetails extended metadata | `KEEP_V2_TEMPORARILY` | Optional profile/listing enrichment | `get_securities_details` | No direct documented equivalent | Exact-symbol metadata | V2 | B5 or later | Field-by-field authoritative replacement | Every consumed field mapped or truthfully null with product approval | Remain explicitly V2 | Extended fields and instrument type unresolved |
| Daily OHLC | `DUAL_RUN_FOR_PARITY` | Canonical D1 chart and `latest_price` | `get_daily_ohlcv` / DailyOhlc | `/data/ohlc?timeFrame=1d` | Daily OHLCV | V2 | B2, B4, B5 | Same symbol/date, ordering, paging, OHLC, volume/value, finality | Completed-session parity and unchanged downstream indicators | Route daily OHLC to V2/global `v2` | Units, corrections, paging defaults, finality |
| Completed-session intraday OHLC | `DUAL_RUN_FOR_PARITY` | Completed-date 1m charts | fixed V2 IntradayOhlc request | `/data/ohlc?timeFrame=1m` | Intraday OHLCV | V2 | B2, B4, B5 | Timestamp, timezone, minute bucket, gaps, volume, completed finality | Same-session normalized bar parity | Route completed intraday to V2 | One-year limit, timestamp and volume semantics |
| Current-session intraday OHLC | `KEEP_V2_TEMPORARILY` | Delayed Today 1m chart | V2 IntradayOhlc with freshness scheduling | V3 OHLC or stream, unresolved | Intraday OHLCV plus current finality | V2 | B5 later | Active-session newest-bar, delay, correction and close reconciliation | Market-hours and post-close acceptance proves source/finality | Remain V2 | Snapshot versus forming bar behavior unknown |
| DailyStockPrice/securities summary | `DUAL_RUN_FOR_PARITY` | Reference/limits, matched/deal totals, daily enrichment | `get_daily_stock_price` | `/data/securitiesSummary` | Daily securities summary | V2 | B3, B4, B5 | All consumed fields, pagination, null/zero, units, finality | Accepted replacement for each public field or explicit retained V2 split | Route summary to V2 | V3 omits documented V2 reference/limit names |
| Foreign buy/sell value | `KEEP_V2_TEMPORARILY` | Historical/value analytics and rankings | DailyStockPrice gross/direct net values | securitiesSummary gross foreign values | Foreign-flow row | V2 | B3, B4, B5 last | Same date/symbol, VND unit, zero/missing, finality, corrections | Units/finality and deterministic net rule proven | Remain V2/global `v2` | Unit and direct-net semantics unproven |
| Foreign buy/sell volume | `KEEP_V2_TEMPORARILY` | Historical/volume analytics and rankings | DailyStockPrice gross/direct net volumes | securitiesSummary gross foreign totals | Foreign-flow row | V2 | B3, B4, B5 last | Same date/symbol, share unit, zero/missing, finality, pagination | Units/finality and deterministic net rule proven | Remain V2/global `v2` | Unit and lot/share semantics unproven |
| Foreign-flow analytics | `REUSE_UNCHANGED` | 5/20/60 windows, streak/reversal, breadth, concentration, rankings | Service calculations over normalized rows | Same calculations over accepted rows | Foreign-flow rows to analytics outputs | Existing business logic | B1, B3, B5 | Existing deterministic analytics tests on V2 and V3 fixtures | No V2-specific input remains after foreign-flow gate | Input route rollback only | Legacy `source_endpoint` compatibility metadata |
| Index list | `MIGRATE_TO_V3_LATER` | Resolve official index identifiers | `get_index_list` | `/data/indexList` | Index definition | V2 | B2, B4, B5 | Board/code/name coverage and aliases | Accepted identifier set and error behavior | Route index list to V2 | Identifier coverage not live-proven |
| Index summary | `DUAL_RUN_FOR_PARITY` | Optional daily index context | `get_daily_index` | `/data/indexSummary` | Index summary | V2 | B2, B4, B5 | Index/date/value, volume/value, breadth, finality | Same-index/date normalized parity for consumed fields | Route summary to V2 | Single-date versus range contract; missing OHLC fields |
| Index components/current membership | `KEEP_V2_TEMPORARILY` | VN30 membership and filter source | `get_index_components(indexCode)` | `securitiesByBoard?index=` | Index membership | V2 | B2 candidate, B4, B5 | Symbol set/count, outer identity, board, weights, effective time | Current membership parity plus explicit effective-time treatment | Remain V2 | No historical/effective-date or weight contract |
| VN30 aggregation | `REUSE_BUSINESS_LOGIC_WITH_ADAPTER` | Coverage-aware foreign-flow aggregate | Current SSI membership + normalized DailyStockPrice histories | Same logic over accepted inputs | Membership + foreign-flow rows | Existing business logic on V2 | B1, B5 | Existing aggregate tests and input-provider diagnostics | Both membership and foreign-flow inputs accepted, or explicit hybrid remains | Roll back either input capability | Mixed provider/date/source observability |
| Realtime quote | `KEEP_V2_TEMPORARILY` | Optional latest streaming snapshot | V2 SignalR `X` cache | V3 quote topics | Future stream snapshot contract | V2 streaming | SSI-V3-C | Auth, topic, timestamp, snapshot/delta, freshness, reconnect | Market-hours shadow and after-hours persistence accepted | V2 stream selector in future C | Endpoint/OTP/topic semantics |
| Realtime trade | `KEEP_V2_TEMPORARILY` | Optional bounded trade tape | V2 `X-TRADE` buffer | V3 trade topic | Future trade event contract | V2 streaming | SSI-V3-C | Side, sequence, dedupe, timestamp, reconnect continuity | Bounded tape parity and recovery proof | V2 stream selector | Side and sequence semantics |
| Order book | `KEEP_V2_TEMPORARILY` | Optional ladder | V2 `X-QUOTE` cache | V3 quote/order-book topic | Future ladder snapshot/delta | V2 streaming | SSI-V3-C | Depth, snapshot/delta, sequence and recovery | Full ladder reconstruction/reconnect accepted | V2 stream selector | Topic may be delta-based |
| Foreign room | `KEEP_V2_TEMPORARILY` | Optional live room context | V2 `R` cache | V3 room topic/model | Future room snapshot | V2 streaming | SSI-V3-C | Units, null/zero, session reset, after-hours | One-symbol live and persisted-state acceptance | V2 stream selector | Not daily foreign-flow authority |
| Session/status | `INCONCLUSIVE` | Optional market/session context | V2 `F` cache | No direct V3 equivalent proven | Future session/status contract | V2 streaming | SSI-V3-C or later | Official replacement and code mapping | Official or accepted derived source replaces all consumed status semantics | Keep V2 | Direct replacement absent |
| Market/index stream | `KEEP_V2_TEMPORARILY` | Optional MI pulse | V2 `MI` cache | V3 market topics | Future market/index event | V2 streaming | SSI-V3-C | Index identity, units, sequence, freshness, reconnect | Bounded index shadow and after-hours proof | V2 stream selector | Topic/field semantics unproven |
| Historical market file | `V3_NEW_OPTIONAL_CAPABILITY` | Not used | None | `/data/file` temporary link | New bounded file manifest, not existing rows | None | B2 foundation; separate product gate | Entitlement, expiry, size, content, download safety, units | Not a V2 exit dependency | Disable capability | Async preparation, temporary URL, no public owner |
| Additional candle intervals | `V3_NEW_OPTIONAL_CAPABILITY` | Not used; UI supports D1/verified 1m only | None beyond existing V2 paths | V3 `3m/5m/15m/30m/1h` | Intraday OHLCV per accepted timeframe | None | B2 foundation; later product gate | Bucket/time/volume semantics per interval | Not a V2 exit dependency | Disable interval | No UI/product contract or aggregation proof |
| Rate-limit metadata | `IMPLEMENT_V3_DISABLED` | Diagnostics and provider pacing | V2 internal cooldown/delay | V3 rate headers and SDK limiter | Provider diagnostics | V2 policy; disabled V3 capture | B2, B4 | Header parsing, reset units, concurrency and retry budget | V3 route observes safe budget without storms | Route to V2 | Entitlement-specific limits unknown |
| Cache and single-flight | `REUSE_BUSINESS_LOGIC_WITH_ADAPTER` | Provider/service caching and coalescing | V2 fetcher cache plus service keys | Version-isolated V3/shadow keys | Provider-version request identity | Existing V2 | B1, B4 | Collision, negative/stale, poison, and fan-out tests | Provider-version isolation proven in shadow | Global `v2`; V3 cache ignored | Existing keys do not uniformly encode version |
| Public API/frontend contract | `REUSE_UNCHANGED` | All VN product routes and UI states | Pydantic schemas + TS normalization/rendering | Same public contract | Existing schemas | Unchanged | B1-B5 | API snapshots/regressions; frontend only if shared schema changes | All accepted capabilities remain contract-compatible | Global `v2` | Endpoint-specific legacy source literals |
| Provider lifecycle/shutdown | `REUSE_BUSINESS_LOGIC_WITH_ADAPTER` | Lazy REST clients; background V2 stream cleanup | `requests.Session`, token cache, FastAPI stream lifespan | V3 Auth/Data context managers | Provider-neutral `close()` ownership | V2 | B1, B2 | Idempotent close, no pre-bind I/O, startup independence | V3 REST client closes cleanly and never blocks health | Select V2/restart | SDK sync/async ownership and refresh threads |
| Source/version diagnostics | `REUSE_BUSINESS_LOGIC_WITH_ADAPTER` | Truthful source/cache/error observability | SSI endpoint labels and counters | Add internal `provider_version` | Provider diagnostics | Existing V2 labels | B1, B2, B4 | Additive, optional, secret-safe, no frontend branch | V3 calls are distinguishable without breaking payloads | Global `v2` | Compatibility labels versus actual endpoint |
| V2 REST dependency/request layer | `REMOVE_AFTER_V3_CUTOVER` | Supplies all current V2 REST and stream models | `ssi-fc-data` 2.2.2 and V2 imports/config | Replaced only after full acceptance | Not a domain row | Retained | SSI-V3-D | All required REST and future stream gates plus rollback window | No required capability, audit, or rollback depends on V2 | Revert retirement release during window | V2 package also owns current streaming transport |

Category index:

- `REUSE_UNCHANGED`: foreign-flow analytics; public API/frontend contract.
- `REUSE_BUSINESS_LOGIC_WITH_ADAPTER`: VN30 aggregation; cache/single-flight; provider lifecycle/shutdown; source/version diagnostics.
- `IMPLEMENT_V3_DISABLED`: authentication/token; rate-limit metadata.
- `DUAL_RUN_FOR_PARITY`: exact-symbol basic information; daily OHLC; completed intraday; DailyStockPrice summary; index summary.
- `MIGRATE_TO_V3_FIRST`: securities by board.
- `MIGRATE_TO_V3_LATER`: index list.
- `KEEP_V2_TEMPORARILY`: extended metadata; current-session intraday; foreign value/volume; components; quote; trade; order book; room; market/index stream.
- `V3_NEW_OPTIONAL_CAPABILITY`: historical market file; additional candle intervals.
- `REMOVE_AFTER_V3_CUTOVER`: V2 REST dependency/request layer.
- `INCONCLUSIVE`: session/status replacement.

### Cache and single-flight isolation

Provider identity is part of every future cache and in-flight key. A normalized key is:

```text
(provider_version, capability, normalized identity,
 date/time range, timeframe, page identity, normalization contract version)
```

Rules:

- V2 and V3 positive, negative, stale, token, and rate-limit entries never collide.
- Shadow V3 writes only a shadow namespace and never overwrites V2 production cache.
- V3 failures cannot poison, evict, extend, or mark stale a V2 entry; the inverse also applies.
- Single-flight coalescing includes provider version and shadow/production mode.
- Shadow is not launched by each waiter; one bounded owner may compare one normalized request.
- `force_refresh` applies only to the explicitly routed provider; it never means “try the other version.”
- Service-level business cache keys must add provider/version when results may differ; compatibility caches that contain only provider-neutral derived values must retain source/version metadata in the cached payload.
- Switching back to V2 ignores V3 cache entries. Process restart is the conservative rollback default; no cross-version cache purge is required for correctness.

### Error normalization

Provider adapters normalize errors before services classify public availability. A configured V3 capability returns an explicit V3 unavailable/error state; it does not silently return V2 data.

| Category | Retryable | Public behavior | Cache impact | Shadow behavior | Log level | V2 routing/rollback |
| --- | --- | --- | --- | --- | --- | --- |
| `configuration_error` | No | Clear unavailable/configuration state; health remains provider-independent | No provider cache write | Skip and count configuration failure | Error at activation, then bounded | Explicit V2 route is allowed only by configuration; rollback required if capability was cut over |
| `authentication_failed` | No until credentials change | Capability unavailable | No domain cache; invalidate only V3 token state | Stop sample; no retry | Warning/error, secret-safe | Retained V2 capability may stay routed; cut-over capability triggers rollback decision |
| `entitlement_unavailable` | No until entitlement changes | Capability unavailable | Provider-specific negative cache may be bounded | Stop capability sample | Warning | Explicit V2 retention allowed; no automatic fallback |
| `rate_limited` | Yes after documented reset | Unavailable or provider-specific stale state under existing public policy | V3 cooldown/negative entry only | Stop sample; respect reset/budget | Warning, deduplicated | Repeated production limits trigger rollback review |
| `request_timeout` | Yes only within bounded policy | Unavailable; existing valid provider-specific stale data may remain truthful | Never overwrite positive cache | Record timeout; no retry storm | Warning | Rollback after threshold/incident policy, not per-request fallback |
| `network_error` | Yes only within bounded policy | Unavailable/stale by existing contract | Provider-specific negative state | Record and stop bounded sample | Warning | Operational rollback if cut over |
| `provider_unavailable` | Policy-dependent | Unavailable/stale | Provider-specific only | Record sanitized code | Warning | Explicit route remains; rollback by config if needed |
| `malformed_response` | No | Unavailable/incomplete, never partial fabricated values | Do not cache as positive | Preserve structural diff only | Error | Cutover blocked or rolled back |
| `unsupported_capability` | No | Explicit unavailable/not supported | Optional long provider-specific negative cache | Do not sample repeatedly | Info/warning | Capability must remain V2 or absent |
| `incomplete_data` | No automatic retry | Partial/unavailable using current schema rules | Never replace complete positive data | Compare missing-field set | Warning | Cutover gate fails; V2 remains explicitly routed |
| `validation_error` | No | Existing 4xx/request-validation behavior | No provider call/cache mutation | Not sampled | Info | Not a provider fallback condition |
| `internal_error` | No automatic retry | Sanitized unavailable/500 per current boundary | No cross-provider mutation | Stop sample | Error with stack server-side | Rollback if introduced by cutover |

No category authorizes implicit V2 fallback. “V2 may remain explicitly routed” means the capability router selected V2 before the request because the migration manifest says so.

### Bounded shadow comparison

Future B4 shadow mode is default-off and V2-response-owned. Planned names, not yet configuration:

```text
SSI_V3_SHADOW_ENABLED=false
SSI_V3_SHADOW_SAMPLE_RATE
SSI_V3_SHADOW_MAX_CONCURRENCY
SSI_V3_SHADOW_TIMEOUT
SSI_V3_SHADOW_CAPABILITIES
```

Frozen behavior:

1. Route and execute the normal V2 request first; it remains the only public response source.
2. Sample only an approved capability/request identity and provider-derived symbol/index.
3. Execute V3 in a separate timeout, concurrency, cache, single-flight, and rate-budget namespace.
4. Bound symbols, indexes, pages, date range, and total calls; prohibit full-market fan-out.
5. Compare normalized values, not provider envelopes or formatted UI strings.
6. Never persist raw payloads, tokens, headers, URLs containing credentials, or full response bodies.
7. Emit bounded counters/distributions and field-presence differences; cancel with the owning request where practical.
8. Do not retry authentication, entitlement, validation, or malformed-response failures; do not create retry storms for transient failures.

Comparison categories are identity; trading date; OHLCV; foreign buy/sell volume/value; null versus zero; index membership symbol set/count; effective timestamps; provider error category; duration; pagination; and rate-limit observation. Exact equality is required for identity/date/null/zero/member-set checks. Numeric tolerances are **not frozen** without paired evidence: B4 must record absolute/relative differences first, then a later review may approve a field-specific tolerance based on documented unit/rounding/finality behavior.

Acceptance thresholds are evidence-derived, not invented. Before B4 traffic, each capability must define its expected sample size, allowable missing rows, timing budget, and whether equality or an approved tolerance applies. No aggregate “parity score” can conceal a required-field failure.

### Capability cutover gates

| Gate | Required evidence before V3 ownership |
| --- | --- |
| Securities | Board query succeeds; symbol identity/coverage understood; duplicates/missing rows classified; board and instrument-type unknowns remain honest; cache behavior proven |
| Exact symbol | Exact match stable; every consumed basic field mapped; unsupported extended fields remain null or explicitly V2-owned |
| Daily OHLC | Same symbol/date range; date/order/paging proven; OHLC, volume, value and missing sessions checked; completed-session finality proven; indicators consume unchanged rows |
| Completed intraday | Timezone, bucket, cadence, ordering, gaps, volume and completed-session finality proven for `1m` independently |
| Daily summary | Every public enrichment field mapped or retained on V2; paging, date, null/zero, units, finality and corrections proven |
| Foreign flow | Gross buy/sell volume/value, units, direct/derived net, zero/missing, date, pagination, finality and corrections proven; existing analytics regressions pass |
| Index list/summary | Identifier/board mapping, date/value/volume/breadth fields, missing behavior and finality proven |
| Index membership | Exact index, current member symbols/count, effective time and optional weights handled; no hardcoded VN30 data |
| Realtime, future C only | Authoritative URL/auth/topic; heartbeat/reconnect/resubscribe; snapshot/delta; sequence/dedupe; quote/trade/book/room/status/index normalization; bounded market-hours shadow |

Capabilities fail independently. A passing daily OHLC gate does not approve DailyStockPrice, foreign flow, components, current-session bars, or streaming.

### Configuration-only rollback

Global rollback is always:

```text
SSI_FASTCONNECT_REST_VERSION=v2
```

Rollback triggers include authentication/entitlement regression, malformed or incomplete rows, unit/finality breach, rate-budget breach, cache collision, lifecycle leak, public-contract regression, or unexplained parity drift above the capability's accepted policy.

Procedure:

1. Change the selector to `v2` in the secret/configuration manager; do not change credential values.
2. Restart the process so provider instances, tokens, and in-flight work are recreated deterministically.
3. V3 cache entries remain isolated and ignored; do not copy them into V2 keys.
4. Verify health remains independent, provider/version diagnostics say V2, and one bounded route per affected capability returns the established V2 contract.
5. Confirm no V3 request counters advance after restart and existing V2 cache/status semantics resume.
6. Record the incident and block that capability's V3 manifest entry until a new gate passes.

B1 uses global rollback only. If B5 proves operational need for independent rollback, add one allow-list of accepted V3 capabilities rather than many environment variables. Removing one capability from that allow-list and restarting is the per-capability rollback. The router still selects once before a request and never falls back on error.

### Frozen implementation phases

#### SSI-V3-B1 — Provider Contract and V2 Adapter — complete

Goal: introduce provider-neutral normalized type contracts and REST `Protocol`; wrap the current V2 fetcher; centralize explicit provider selection defaulting to V2; inject it into existing services.

Allowed scope: protocol/models, delegating V2 adapter, factory/router, V2-default configuration parsing, focused tests, and documentation. No V3 package, V3 configuration, V3 request, shadow execution, public schema, frontend, or stream change.

Acceptance: all existing V2 tests pass; representative normalized/public payloads are unchanged; missing/empty selector means V2; explicit `v2` means V2; unknown means configuration error; no automatic fallback exists; default/rollback behavior is deterministic.

Implemented files are `ssi_provider_models.py`, `ssi_provider_protocol.py`, `ssi_v2_adapter.py`, and `ssi_provider_router.py`. The adapter returns the existing fetcher dictionaries directly and adds no cache, single-flight, retry, normalization, or provider call. Market and foreign-flow services reuse the same lazy V2 fetcher instance through the router. Streaming continues to call the existing fetcher directly.

##### B1 behavior-parity evidence

| Capability | Old call path | New call path | Provider calls before | Provider calls after | Output parity | Cache parity | Error parity | Lifecycle parity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Securities | Service -> V2 fetcher | Service -> router -> V2 adapter -> same fetcher | 1 | 1 | Same dictionary | Same fetcher cache | Same exception/result | Same fetcher instance |
| SecuritiesDetails | Service -> V2 fetcher | Service -> router -> V2 adapter metadata capability -> same fetcher | 1, then optional Securities call | 1, then same optional Securities call | Same dictionary and SSI-only metadata fallback | Same fetcher/service cache | Same exception/result | Same fetcher instance |
| DailyOhlc | Service -> V2 fetcher | Service -> router -> V2 adapter -> same fetcher | 1 | 1 | Same dictionary; `latest_price` remains DailyOhlc | Same fetcher and service caches | Same exception/result/cooldown | Same token/session owner |
| IntradayOhlc | Service -> V2 fetcher | Service -> router -> V2 adapter -> same fetcher | 1 | 1 | Same compact/completed-session rows | Same fetcher and chart caches | Same exception/result/cooldown | Same fetcher instance |
| DailyStockPrice | Service -> V2 fetcher | Service -> router -> V2 adapter -> same fetcher | 1 per bounded attempt | 1 per bounded attempt | Same summary/foreign fields, including null versus zero | Same fetcher and service caches | Same exception/result | Same token/session owner |
| IndexList | Service -> V2 fetcher | Service -> router -> V2 adapter -> same fetcher | 1 | 1 | Same rows/order | Same fetcher/service cache | Same exception/result | Same fetcher instance |
| DailyIndex | Service -> V2 fetcher | Service -> router -> V2 adapter -> same fetcher | 1 | 1 | Same rows/order | Same fetcher/service cache | Same exception/result | Same fetcher instance |
| IndexComponents | Service -> V2 fetcher | Service -> router -> V2 adapter -> same fetcher | 1 | 1 | Same symbols/order | Same fetcher and negative/service caches | Same exception/result | Same fetcher instance |
| Foreign-flow service | Service -> V2 DailyStockPrice | Service -> router -> V2 adapter -> same DailyStockPrice | Existing bounded attempts | Same bounded attempts | Same history, analytics, units, and null/zero rules | Existing service single-flight/cache unchanged | Existing stale/error policy unchanged | One lazy V2 fetcher per service |
| VN30 aggregation | IndexComponents + foreign-flow services | Same services through V2 router | Existing bounded membership/symbol calls | Same bounded membership/symbol calls | Same current-membership aggregate | Existing membership/history caches unchanged | Per-row/service errors unchanged | No new client or worker |

Deterministic evidence is in `tests/test_ssi_provider_routing.py` plus the existing fetcher, market, foreign-flow, index, cache/single-flight, startup, and offline realtime suites. The router exposes secret-free internal diagnostics (`capability`, selected provider/version, routing reason, `fallback_used=false`) but adds nothing to public API payloads.

#### SSI-V3-B2 — V3 REST Adapter Foundation — complete offline

Implemented scope: pinned official `ssi-sdk==3.0.5`; separate secret-safe V3 configuration; lazy lock-protected `Auth`/`Data` lifecycle; disabled securities-by-board, exact-symbol basic information, securities-by-index normalization, daily OHLC, completed historical 1-minute OHLC, index list, and index summary; bounded pagination; normalized errors and routing diagnostics. No market-file, securities-summary, foreign-flow, current-session intraday, production IndexComponents, streaming, or trading capability was added.

The synchronous SDK is used because the provider protocol and current services are synchronous and already execute provider work outside the FastAPI event loop. Construction and imports are pure. The first explicitly selected supported V3 call creates one shared `Auth` and `Data` lifecycle under a lock and calls `Auth.authenticate()` without OTP. The SDK remains responsible for token refresh; StockClock stores no token. Close is idempotent: a close-capable data fake/future public client is closed before `Auth`, while the pinned SDK's `Data` has no close method and `Auth` owns the shared transport.

Configuration is `SSI_V3_REST_ENABLED=false`, `SSI_V3_CLIENT_ID`, `SSI_V3_API_KEY`, `SSI_V3_API_SECRET`, `SSI_V3_API_URL`, `SSI_V3_REQUEST_TIMEOUT`, `SSI_V3_MAX_RETRIES`, `SSI_V3_RETRY_DELAY`, and `SSI_V3_RATE_LIMIT_PER_SECOND`. V2 credentials are never reused. Missing V3 configuration is ignored while V2 is selected; explicit V3 selection fails with variable names only when disabled or incomplete. The documented full V3 API URL is normalized to the SDK transport root because the pinned SDK endpoint constants already contain `/api/v3`.

The inspected synchronous signatures used by the adapter are:

- `Config(client_id='', api_url='https://api.ssi.com.vn', streaming_url='wss://stream.ssi.com.vn/ws/v3', api_key='', api_secret='', private_key='', timeout=60, max_retries=5, retry_delay=2, rate_limit_per_second=10, log_level='INFO', proxy=None)`.
- `Auth(config: Config | None = None, **kwargs)` and `TokenManager.authenticate(otp: str | None = None) -> Token`; B2 supplies no OTP.
- `Data(auth: Auth)`.
- `get_securities_info_by_board(board)`, `get_securities_info(symbol)`, and `get_securities_info_by_index(index)`.
- `get_ohlc_1day_historical(symbol, from_date, to_date, page=1, size=1000)` and `get_ohlc_1minute_historical(symbol, from_date, to_date, page=1, size=1000)`.
- `get_indexes()` and `get_indexes_by_board(board)`.

The official index-summary REST contract requires `board` and permits optional `index` and `tradingDate`, while the pinned SDK's high-level summary helpers cannot express the combined query. The adapter therefore uses the public authenticated `Auth.rest_client.get('/api/v3/data/indexSummary', params=...)` path for that one capability rather than a private SDK implementation detail.

Pagination is one-based with a requested page size capped at 1,000, at most 20 pages, and at most 5,000 normalized rows. Empty/short pages stop traversal, repeated pages fail safely, and provider order is preserved. Missing values remain null and explicit zero remains zero when the public SDK result preserves that distinction; non-finite numerics and malformed dates are rejected. The SDK's model parsing may itself collapse some absent raw numeric fields to zero before the adapter receives them, so raw missing-versus-zero parity remains a live B4 acceptance question.

Errors normalize internally to `configuration_error`, `authentication_failed`, `entitlement_unavailable`, `request_timeout`, `network_error`, `rate_limited`, `provider_unavailable`, `malformed_response`, `validation_error`, or `internal_error`. Rate-limit `retry_after` is retained when the public exception exposes it. Limit, remaining, and reset stay null because the public SDK result does not expose response headers; no private transport inspection was added.

Deterministic coverage is in `tests/test_ssi_v3_adapter.py` and `tests/test_ssi_provider_routing.py`. It uses SDK-shaped fakes only and proves import/thread safety, lazy concurrent lifecycle ownership, request/date/page construction, normalization, null/zero handling, bounds, error mapping, provider-version cache isolation, explicit V2-pinned ownership, and no fallback. No live V2 or V3 request or credential test ran in B2.

#### SSI-V3-B3 — Securities Summary and Foreign Flow

Goal: normalize V3 securities summary and gross foreign buy/sell value/volume into the existing provider-independent daily/foreign-flow rows while retaining V2 as production owner.

Allowed scope: V3 summary request/normalizer and offline fixtures/tests. Preserve analytics, net rules, cache policy, APIs, UI, and `latest_price` ownership.

Acceptance: date/pagination/null/zero/finite-number behavior passes; direct net is not invented; units/finality remain unknown until evidence; legacy source metadata has a truthful additive provider/version diagnostic; no production cutover.

#### SSI-V3-B4 — Bounded Shadow Comparison

Goal: execute selected V3 REST capabilities as an observer while V2 remains the response source; collect sanitized normalized comparisons and rate/timing evidence.

Allowed scope: default-off sampler, bounds, isolated cache/single-flight, metrics, cancellation, fixtures/tests, and an explicit bounded live acceptance procedure after authorization.

Acceptance: no V3 result reaches public payload; no raw payload persistence; no hidden fallback; concurrency/date/symbol/page/rate budgets enforced; comparisons identify field-level evidence sufficient for a cutover decision.

#### SSI-V3-B5 — REST Capability Cutover

Goal: activate only accepted V3 capabilities independently, retain documented V2-only paths, preserve public behavior, and prove rollback.

Cutover order: securities/basic identity; daily OHLC; completed intraday; index list/summary; current membership only after its gate; DailyStockPrice/foreign flow last. Current-session and extended metadata remain V2 unless separately accepted.

Acceptance: capability-specific gate passes; diagnostics identify actual provider/version; caches are isolated; global and any justified per-capability rollback drills pass; no error-triggered fallback; existing backend and affected frontend contract checks pass.

#### SSI-V3-C — Realtime/WebSocket Migration

Separate future project: build a V3 stream adapter and selector; retain V2 SignalR until V3 quote, trade, book, room, status, and market/index contexts pass independent shadow gates. Resolve authoritative URL, OTP/auth, topics, snapshot/delta, heartbeat, reconnect, resubscribe, sequence, dedupe, after-hours, and persisted-state semantics. No B1-B5 REST selector controls this phase.

#### SSI-V3-D — V2 Retirement

Remove V2 only after all required REST capabilities, all required streaming capabilities, production monitoring, rollback drills, and a defined rollback window pass. Retirement includes the V2 package, request models, adapters, credentials aliases, cache/error branches, stream transport, tests, and docs only when nothing production-critical or rollback-related still depends on them.

### File-level implementation map

| Phase | File | Current responsibility | Planned change | Business logic impact | Public API impact | Tests | Rollback impact |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 | `data_provider/ssi_provider_models.py` | Implemented | Typed provider-neutral normalized rows/results | Codifies existing values only | None | Type/fixture contract | Shared by V2 route after rollback |
| B1 | `data_provider/ssi_provider_protocol.py` | Implemented | REST structural `Protocol`; no streams/trading | None | None | Conformance/fakes | Stable interface for V2 |
| B1 | `data_provider/ssi_v2_adapter.py` | Implemented | Delegates to current fetcher without renormalizing | None | None | Golden V2 behavior | Primary rollback adapter |
| B1/B2 | `data_provider/ssi_provider_router.py` | Implemented | Defaults to V2; selects the disabled B2 V3 adapter only for its explicit capability set; keeps pinned capabilities on V2 | Selection only | None | default/v2/v3/unknown/pinned/no-fallback | Global `v2` owner |
| B1 | `data_provider/ssi_fastconnect_fetcher.py` | Concrete V2 REST + stream cache facade | Prefer no behavioral change; only compatibility hooks if proven necessary | None | None | Existing fetcher suite | Remains source of truth |
| B1/B2 | `src/config.py`, `src/core/config_registry.py`, `.env.example` | Implemented V2 selector and separate V3 REST settings | V3 remains disabled and env-only; secret values are excluded from repr | None | None | Parsing/error/redaction tests | Missing/`v2` restore V2 |
| B1 | `src/services/vietnam_market_service.py` | Direct lazy V2 construction | Inject neutral router; preserve method outputs | None | None | Existing market regressions | Router selects V2 |
| B1 | `src/services/vietnam_foreign_flow_service.py` | Direct V2 construction and domain calculations | Inject neutral router; retain calculations/cache | None | None | Existing foreign-flow/VN30 regressions | Router selects V2 |
| B2 | `requirements.txt`, Docker install path | Implemented | Pins `ssi-sdk==3.0.5` beside V2; the existing image installs `requirements.txt` | None | None | import/version/Docker-path guards | V2 dependency retained |
| B2 | `data_provider/ssi_v3_adapter.py` | Implemented | Disabled lazy Auth/Data/request/normalization/lifecycle foundation | Adapter only | None | mocked auth/request/normalization/close | Not selected under V2 |
| B2 | provider models/protocol/router | Implemented | Adds compatible diagnostics/methods and explicit B2-supported versus V2-pinned routing | None | None | supported/pinned/error/no-fallback routing | Global V2 |
| B3 | V3 fetcher/provider models | No summary/foreign normalizer | Add securities-summary and foreign gross fields | Reuse existing analytics | No field removal/change | null/zero/unit/finality fixtures | V2 stays primary |
| B3 | API schemas only if needed | Literal legacy source metadata | Prefer no change; optional actual-provider/version diagnostic only if required | None | Additive optional only | compatibility snapshots | V2 values unchanged |
| B4 | proposed `src/services/ssi_v3_shadow_service.py` | Does not exist | Bounded sampling/comparison/metrics | None | No result exposure | bounds, cancellation, isolation, non-exposure | Disable shadow/global V2 |
| B4 | provider router/cache helpers/observability | Production-only requests | Add shadow namespace and sanitized counters | None | Optional diagnostics only | key/rate/fan-out tests | Shadow off |
| B5 | provider factory/router manifest | V2 primary | Activate accepted capability entries | Existing business logic unchanged | Stable | per-capability regression/rollback | global/per-capability explicit route |
| B5 | market/foreign-flow services | Consume router | Only changes required for truthful provider/version metadata | None | Optional additive diagnostics | API snapshots and domain regressions | V2 route |
| C | `data_provider/ssi_streaming_realtime.py` and lifecycle modules | V2 SignalR manager/cache | Separate V3 adapter/selector after REST acceptance | Preserve cache product semantics | Stable stream-backed APIs | lifecycle/reconnect/parity | V2 stream selector |
| D | requirements, V2 fetcher/adapter/config/tests/docs | V2 runtime and rollback | Remove after all exits/window | None intended | Stable | full suite and retirement audit | Last release before removal |

Expected unchanged through B0-B4: frontend production files; public API route and schema fields except an explicitly approved optional diagnostic; foreign-flow analytics formulas; VN30 aggregation formulas; Vietnam number-formatting utilities; non-SSI providers; `main.py`, `api/app.py`, Docker/Render entrypoint and startup/readiness code; database, Redis, scheduler, and worker architecture.

### Test strategy by phase

Normal pytest remains offline and deterministic.

1. Provider protocol/model contract tests.
2. V2 adapter golden behavior-preservation tests.
3. Selector default, `v2`, `v3`, unknown, hybrid manifest, and no-fallback tests.
4. V3 request construction and response-envelope tests.
5. V3 authentication, refresh, expiry, redaction, retry classification, and lifecycle tests.
6. Pagination and ordering tests, including V3 default-size differences.
7. Date/time/timezone/bucket normalization tests.
8. Finite numeric and null-versus-explicit-zero tests.
9. Foreign-flow direct-net/derived-net/no-partial-derivation tests.
10. Provider-version cache, negative/stale, force-refresh, and single-flight isolation tests.
11. Shadow sampling, concurrency, timeout, cancellation, rate budget, and no-public-exposure tests.
12. Error taxonomy and unsupported-capability tests.
13. Idempotent client close and no-startup-I/O tests.
14. Existing `test_ssi_fastconnect_fetcher.py`, Vietnam market, intraday, index, foreign-flow, VN30, API, and observability regressions.
15. Frontend tests/build only if a later phase touches shared schema/type normalization; no provider-specific UI tests or branches.

Every retained V2 row requires a test that proves the router selects V2 intentionally under V3 mode. Every cut-over row requires a test that a V3 error remains a V3 error and does not invoke the V2 fake.

### Future runtime acceptance

Live checks occur only in separately authorized phase gates, never normal pytest or B0:

- Post-B2 live acceptance: one authentication sequence; one provider-derived securities query; one exact-symbol OHLC query; one index query; one summary query; sanitized rate-header observation; no unrestricted market request.
- B4 shadow: bounded approved symbols/indexes/date ranges/pages/concurrency/timeouts; no unsafe retry; V2 response ownership; no raw payload persistence or frontend exposure.
- B5 cutover: provider/version diagnostics, provider-independent health/startup, isolated caches, one bounded request per activated capability, public contract checks, and rollback drill.
- C streaming: one scoped topic family at a time during an eligible market window, plus reconnect/resubscribe and after-hours last-known semantics.

Runtime acceptance must verify that optional SSI availability never blocks FastAPI pre-bind startup or `/api/health`. This plan adds no live command and authorizes no provider call.

### Open questions register

| Question | Impacted capability | Current evidence | Implementation impact | Resolve by | Blocker level |
| --- | --- | --- | --- | --- | --- |
| What is the authoritative V3 `client_id` source? | Auth/SDK | SDK config documents it; raw token endpoint does not | Offline configuration exists, but live values remain unapproved | Before post-B2 auth acceptance | `blocks_shadow` |
| Do V2 identifier/secret values map to V3 keys? | Auth | Exact two-field mapping returned 401 | Separate V3 secrets remain required/unresolved | Before B2 live gate | `blocks_shadow` |
| Is this account entitled/activated for V3? | All V3 | Prior 401 proves rejection, not cause | No V3 traffic can be accepted | Before B4 | `blocks_shadow` |
| Which exact official `ssi-sdk` version is pinned? | Dependency/lifecycle | `ssi-sdk==3.0.5` inspected and pinned in B2 | Reinspect before any future upgrade; do not drift silently | Resolved for B2 | `resolved_offline` |
| What are V3 foreign volume/value units? | Foreign flow | Field names documented only | Blocks normalized unit labels/net comparison | Before B4 foreign sample | `blocks_cutover` |
| When is V3 summary foreign flow final/corrected? | Foreign flow | No accepted live evidence | Blocks completed-session ownership | Before B5 foreign cutover | `blocks_cutover` |
| How are explicit zero and missing represented? | Summary/foreign/OHLC | Examples use strings; no paired live rows | Blocks null/zero normalizer acceptance | B3/B4 | `blocks_cutover` |
| What are summary page limits and stable ordering? | Summary/foreign | One-based paging/default 10 documented | Need full bounded history traversal | B2/B3 | `blocks_shadow` |
| Does V3 OHLC expose forming current-session bars and corrections? | Current intraday | Common endpoint documented, runtime semantics absent | Keep current-session on V2 | Before any current-session cutover | `blocks_cutover` |
| What are membership effective-time semantics? | Index components/VN30 | Current index filter documented only | Cannot establish historical/current boundary | B4 index gate | `blocks_cutover` |
| Are component weights available and what do they mean? | Index components/VN30 | Not in documented securities row | Weight remains null; aggregation stays unweighted/current | Before weighted product or V2 exit | `blocks_V2_removal` |
| What field authoritatively classifies instrument type? | Securities/HOSE | V2 and V3 documented rows do not prove it | No common-stock authority claim | Before universe/type product | `blocks_V2_removal` |
| How are consumed SecuritiesDetails fields replaced? | Extended metadata | No direct V3 endpoint documented | Explicit hybrid V2 ownership required | Before V2 retirement | `blocks_V2_removal` |
| What are account-specific V3 REST rate limits/reset units? | All REST | Header names documented, values not observed | Bounds/retry budget provisional | Before B4 | `blocks_shadow` |
| Which V3 WebSocket URL is authoritative? | Streaming | Portal/SDK/tutorial evidence differs | No stream connection configuration | SSI-V3-C | `blocks_V2_removal` |
| What are exact stream topics and snapshot/delta semantics? | Quote/trade/book/room/index | Families documented; runtime parity absent | Cannot normalize/reconstruct state | SSI-V3-C | `blocks_V2_removal` |
| How do reconnect and resubscription preserve sequence/snapshots? | Streaming lifecycle | Tutorials describe reconnect; StockClock parity absent | Requires separate manager acceptance | SSI-V3-C | `blocks_V2_removal` |
| What replaces V2 `F` session/status? | Session/status | No direct V3 equivalent proven | Keep V2 or define approved derived contract | SSI-V3-C or later | `blocks_V2_removal` |
| Can legacy endpoint-specific public source literals remain truthful? | Source diagnostics/API | Current fields include `DailyStockPrice` literals | Add optional actual provider/version diagnostics before cutover | B3/B5 | `blocks_cutover` |

### Explicit exclusions

Phase B2 implements only the pinned SDK dependency, separate V3 REST settings, disabled adapter, explicit capability routing, minimal provider-version service cache isolation, offline tests, and documentation described above. It implements no credential values or alias, live provider request, production enablement, shadow mode, public API/schema, frontend, securities summary, foreign-flow V3 input, production IndexComponents cutover, current-session intraday cutover, stream, trading, database, Redis, scheduler, worker, Docker, Render, or startup change. It does not confirm V3 credentials, entitlement, parity, units, finality, production readiness, or permission to remove V2.

### Next implementation phase

**SSI-V3-B3 — Securities Summary and Foreign-Flow Normalization** is the next implementation phase. It may add only offline V3 summary/foreign normalization while V2 remains production owner. Any live acceptance, shadow traffic, or production cutover still requires a separately authorized later gate.
