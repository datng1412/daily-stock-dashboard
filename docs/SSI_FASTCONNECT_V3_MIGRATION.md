# SSI FastConnect V3 Capability and Migration Gate

Status: Phase SSI-V3-A1 complete as an existing-key compatibility and change-impact audit. Production remains on FastConnect V2.

## Decision

**Primary outcome: D — EXISTING CREDENTIALS REJECTED BY V3.**

The repository has an installed V2 `ssi-fc-data` 2.2.2 dependency and V2-only production configuration. The official Python V3 package is `ssi-sdk` with the `ssi_sdk` namespace and documented version `3.0.5`; it was inspected from official documentation/package metadata and was not installed locally. On 2026-07-21, the audit mapped the existing `SSI_FASTCONNECT_CONSUMER_ID` and `SSI_FASTCONNECT_CONSUMER_SECRET` values in memory to the documented V3 raw REST `apiKey` and `apiSecret` fields. The single authorized `POST /api/v3/auth/token` sequence returned HTTP 401 in 1,388 ms. It produced no access token, refresh token, expiry field, or rate-limit header.

This result is an explicit V3 rejection of the tested current-value/raw-field mapping, not a network failure and not proof that V2 credentials have stopped working. No market-data, index, file, or WebSocket parity request followed. Only a future A or B outcome may open SSI-V3-B. Outcome D keeps V2 unchanged and requires SSI to confirm V3 account activation and the exact mapping of application/client identifier, API key, and API secret before another live attempt.

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
| Migration adapter viability | Blocked | Outcome D forbids adapter implementation; authentication and contract parity must be established first. |

## Proposed migration architecture — not implemented

Phase SSI-V3-B may propose a provider-neutral internal surface only after outcome A or B. The design target is a small fact-preserving interface, not a V2/V3 automatic fallback:

```text
security_master_page(board | index | symbol)
symbol_metadata(symbol, market)
daily_ohlcv(symbol, date_range, page)
daily_foreign_flow(symbol, date_range, page)
index_catalog()
index_membership(index_code)
realtime_snapshot(symbol)  # cache read only; lifecycle owns the stream
```

Each result would carry provider/version, request identity, source timestamp, paging/freshness, units, finality, and explicit missing/error state. V2 stays primary. V3 could only run in a separate, bounded shadow path with no product response ownership and no fallback. Compare raw normalized values, never formatted strings:

- symbol and market/index identity;
- trading date; open/high/low/close; volume;
- foreign buy/sell volume and value, including units/finality;
- current index components only;
- realtime source timestamps and message sequence where available.

No full historical parity, broad WebSocket topic, database persistence, scheduler, polling loop, V2 removal, production route change, or configuration migration is authorized by this document.

## SSI account/credential follow-up

The recommended next phase is a narrow **SSI V3 account and credential-contract resolution**, not adapter implementation:

1. Ask SSI to confirm whether the current account is V3-enabled and whether V2 `ConsumerID` is the V3 `apiKey`, the SDK `client_id`, both, or neither. Do not request or rotate a key speculatively.
2. Confirm the exact data-only V3 API key/secret mapping and whether a separate client identifier is assigned.
3. After SSI provides a concrete correction/activation, authorize one new bounded auth evidence phase; do not retry the rejected mapping unchanged.
4. Only after auth succeeds, use one provider-derived symbol for the bounded securities/history/index comparisons.
5. Resolve streaming separately because official SDK documentation requires OTP for Stream and the documented stream URLs differ.
6. Re-evaluate the migration gate. Do not begin SSI-V3-B unless the result becomes A or B.

No credential, token, header, raw provider payload, SDK archive, historical file, or live audit artifact was committed by SSI-V3-A1.
