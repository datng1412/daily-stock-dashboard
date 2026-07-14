# SSI FastConnect Integration

## Scope

This document covers the Vietnam dashboard SSI FastConnect transition foundation.

Current phase:

* FC Data only.
* Provider skeleton and secure configuration.
* AccessToken authentication handling.
* REST normalization for selected market-data APIs.
* Strict SSI ownership for supported Vietnam REST market data.
* No Mozyfin or KBS fallback for SSI-owned daily OHLCV, chart OHLCV, DailyStockPrice, reference/ceiling/floor, foreign flow, DailyIndex, realtime snapshot, or trade tape.
* Mocked tests and an optional local smoke script.
* Dashboard detail rendering for SSI DailyStockPrice fields when SSI provides them.
* SSI IntradayOhlc candles for compact watchlist/company intraday pulse.
* SSI IntradayOhlc provider-rate-limit cooldown guardrails.
* SSI realtime snapshot and trade-tape contracts for dashboard/company realtime blocks.
* SSI realtime REST endpoint discovery concluded that no supported FastConnect realtime snapshot endpoint is identified in this repository.
* SSI streaming realtime parser coverage for buffered `X`, `X-QUOTE`, `X-TRADE`, `F`, `R`, and `MI` messages.
* Config-disabled SSI streaming manager/cache skeleton for future background runtime work.
* Official `ssi-fc-data` Python client adapter behind the disabled streaming runtime flag.
* FastAPI startup bootstrap for SSI streaming realtime when explicitly enabled and given a small bootstrap symbol list.
* Realtime endpoint response-cache bypass and frontend quote polling tuned for the process-local streaming cache.
* SSI `X-QUOTE:{symbol}` order-book backend/API support as a separate optional watchlist context.
* SSI `R:{symbol}` foreign-room backend/API support as a separate optional watchlist context.
* SSI `MI:{index_code}` market-index pulse backend/API support as a separate optional index context.
* SSI live API plus backend cache/TTL; local DB market-data storage is deferred.

Out of scope:

* FC Trading.
* Order placement.
* Account actions.
* Cash transfer.
* Stock transfer.
* Portfolio trading actions.
* UI source switcher or comparison card.
* Provider comparison endpoint.
* Trading-instruction, price-target, or recommendation wording.

## Provider roles

SSI FastConnect is the preferred future official market-data provider for:

* Daily OHLCV.
* Daily stock price.
* Reference, ceiling, and floor.
* Foreign flow.
* Daily index.
* Index components.
* Symbol metadata.
* Intraday OHLCV.
* Realtime streaming later.

Mozyfin is disabled for VN dashboard runtime. It must not be used for VN news/social, OHLCV, chart, reference, foreign-flow, index, metadata, intraday, or fallback behavior. Future news should be implemented through a separate NewsProvider contract.

KBS is disabled by default and retained only as an explicit legacy development provider:

* `VN_ALLOW_LEGACY_KBS_PROVIDER=true`
* `KBS_ENABLED=true`

KBS must not be used as silent fallback for SSI realtime snapshot, SSI trade tape, or any SSI-owned market-data field.

SSI is now the strict owner for supported VN REST market data. If SSI is disabled, credentials are missing, or a request fails, SSI-owned sections return an unavailable state instead of falling back to Mozyfin or KBS.

External providers are still required for BCTC/KQKD, financial statements, financial ratios, corporate action event lists, dividends, rights, splits, and macro context such as Fed, oil, USD, and gold. These domains are outside current SSI REST market-data ownership.

## Provider capability matrix

| Capability | Owner | Current implementation status | Dashboard rule |
| --- | --- | --- | --- |
| AccessToken | SSI FastConnect Data REST | Implemented | Authenticate with env/secret-manager credentials only |
| Securities | SSI FastConnect Data REST | Implemented and wired as same-provider metadata fallback | Use for symbol metadata when SecuritiesDetails does not return a usable row |
| SecuritiesDetails | SSI FastConnect Data REST | Implemented and wired | Use for exchange, security type, listed info, and issuer/name fields |
| IndexComponents | SSI FastConnect Data REST | Provider/service/API coverage plus exact VN30 live discovery added | Use for index membership only when SSI returns exact component rows |
| IndexList | SSI FastConnect Data REST | Implemented and exposed through backend API | Discover official index identifiers before DailyIndex calls |
| DailyOhlc | SSI FastConnect Data REST | Implemented and wired | Use for watchlist daily close, chart candles, and internal MA/RSI/Bollinger calculations |
| IntradayOhlc | SSI FastConnect Data REST | Implemented and wired for compact intraday pulse | Use as strict VN intraday candle source; do not treat as realtime matched quote |
| DailyIndex | SSI FastConnect Data REST | Implemented with 29-day chunking and wired to optional dashboard context | Use only after exact IndexList identifier resolution |
| DailyStockPrice | SSI FastConnect Data REST | Implemented and wired | Use for reference, ceiling/floor, adjusted close, matched, put-through, latest foreign flow, and bounded recent 5D/20D foreign net volume when enough rows exist |
| Realtime snapshot | SSI FastConnect Data streaming | Provider/service/API/UI contract added for `X:{symbol}` rows; config-disabled background manager/cache skeleton added; official client adapter is available only behind `SSI_STREAMING_REALTIME_ENABLED=true`; FastAPI startup can start a process-local manager only when `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS` is non-empty; default channel template is `X:{symbol}` | Show SSI unavailable until the backend lifecycle cache safely populates current rows; no request-handler streaming and no KBS fallback |
| Order book | SSI FastConnect Data streaming `X-QUOTE:{symbol}` | Phase 4.8H adds a dedicated latest order-book cache, watchlist fields, and diagnostics | Keep bid/ask ladder separate from realtime snapshot, trade tape, session/status, DailyOhlc, DailyStockPrice, and `latest_price`; UI productization waits for live proof |
| Foreign room | SSI FastConnect Data streaming `R:{symbol}` | Phase 4.8I adds a dedicated latest foreign-room cache, watchlist fields, and diagnostics | Keep foreign room separate from DailyStockPrice daily foreign flow, realtime snapshot, trade tape, order book, session/status, DailyOhlc, and `latest_price`; value-unit proof and UI productization wait for live evidence |
| Market index pulse | SSI FastConnect Data streaming `MI:{index_code}` | Phase 4.8J adds a dedicated latest market-index cache, separate market-index pulse API response, and diagnostics | Keep MI separate from stock watchlist rows, REST DailyIndex, realtime snapshot, trade tape, order book, foreign room, session/status, DailyOhlc, and `latest_price`; channel/field proof and UI productization wait for live evidence |
| Trade tape | SSI FastConnect Data streaming or future verified trade contract | Provider/service/API/UI contract added; live history/list semantics still need confirmation | Keep separate from realtime latest-trade messages and official daily OHLCV |
| Realtime bars/OHLC | SSI streaming/protocol hardening later | Candidate stream type is documented but not wired | Phase 4.8F documents `B` as an SSI-owned candidate that needs runtime proof before exposure |
| News | Future NewsProvider | Disabled/not implemented | Do not call Mozyfin; keep separate from SSI-owned market data |
| BCTC/KQKD, financial statements, ratios | External provider | Unsupported/future provider | Do not infer fundamentals from price fields |
| Corporate actions, dividends, rights, splits | External provider through future `CorporateActionsProvider` | Disabled/not configured by default; contract proof only | Do not infer events from reference or adjusted-close gaps |
| Macro/Fed/oil/USD/gold | External provider | Unsupported/future provider | Keep outside FC Data market-price ownership |

## Current endpoint/source mapping

| Feature | SSI source/endpoint | Current status | Notes |
| --- | --- | --- | --- |
| DailyOhlc | `GET /Market/DailyOhlc` | OK | Canonical dashboard `latest_price` currently uses this close. Also owns chart candles and internal indicators. |
| DailyStockPrice | `GET /Market/DailyStockPrice` | OK | Owns reference, ceiling/floor, matched/put-through, adjusted close if provided, latest foreign-flow fields, and bounded latest-available 5D/20D foreign net volume indicators from the existing per-symbol recent window. Phase 4.5C live API smoke populated 20 recent rows and non-null 5D/20D foreign-net summaries for FPT/HPG/SSI while `latest_price_source` stayed `SSI DailyOhlc`. Earlier smoke found same-day DailyOhlc versus DailyStockPrice close/volume mismatch for FPT on `2026-06-22`. |
| IndexList | `GET /Market/IndexList` | OK | Use SSI-returned index codes instead of hardcoded assumptions. |
| DailyIndex | `GET /Market/DailyIndex` | Partial: `indexID=VN30` returns rows, while exact `VNINDEX` remains unresolved and non-positive or missing index levels are null | Requires exact IndexList resolution and returns no placeholder row when SSI has no usable data. Phase 4.5C live API smoke returned a VN30 row dated 2026-06-29 but the public row still lacked a usable `index_value` and `exchange`. |
| IndexComponents | `GET /Market/IndexComponents` | Usable for exact VN30 nested rows; unavailable cases remain `rows=[]` | Phase 4.4B proved `indexCode=VN30` returns an exact VN30 outer row with 30 nested members. Phase 4.5C live API smoke re-confirmed 30 VN30 component rows. Missing identifiers, mismatched outer rows, empty nested lists, or provider failures remain unavailable without hardcoded members. |
| IntradayOhlc | `GET /Market/IntradayOhlc` | Contract exists; returned rows may be stale/mismatched or provider-throttled | Freshness must be validated against SSI DailyOhlc date before rendering intraday metrics; failures expose only sanitized diagnostics. |
| Realtime snapshot | SSI FastConnect streaming data type `X` | Parser covered; config-disabled manager/cache skeleton exists; official client adapter is config-gated; FastAPI startup bootstrap is config-gated and symbol-list gated | Phase 4.0C verified the route/service/fetcher wiring and config gate. Phase 4.0C-2 found no supported SSI REST realtime endpoint, SDK method, enum, or hidden repo contract. Phase 4.0C-3 confirmed the realtime direction is streaming. Phase 4.0C-5 added a request-safe cache read path that stays disabled by default. Phase 4.0C-6 added a lazy official-client adapter. Phase 4.0C-7E changed the default channel to the live-verified no-space form `X:{symbol}`; spaced forms are retained only for diagnostics/custom overrides. Phase 4.0C-8 added FastAPI lifecycle bootstrap that starts the process-local manager only when `SSI_STREAMING_REALTIME_ENABLED=true` and explicit bootstrap symbols are configured. Phase 4.0C-9 makes the realtime endpoint bypass the generic backend response cache so fresh process-local stream-cache rows can surface immediately. Previous candidate names `RealtimeQuote`, `RealtimePrice`, `RealtimeSnapshot`, and `SecuritiesRealtime` are discovery evidence only and are no longer probed at runtime. The dashboard must not claim realtime is live unless `realtime_snapshot` is non-null and `realtime_status.status = ok`. |
| Order book | SSI streaming `X-QUOTE:{symbol}` latest ladder cache | Phase 4.8H adds backend/API watchlist fields `order_book_source`, `order_book`, and `order_book_status`, with technical details under `diagnostics.order_book` | Request handlers only read the process-local cache. Parsed levels require positive price and non-negative volume. Stale usable ladders remain visible with stale status/age diagnostics; empty/malformed books return explicit unavailable state. No fake rows or `latest_price` substitution. |
| Trade tape | SSI streaming `X-TRADE` event buffer; future verified REST/history contract if SSI documents one | Phase 4.7C adds a bounded process-local per-symbol X-TRADE buffer populated only by the background streaming manager. Phase 4.8E subscribes the startup-owned manager to `X-TRADE:{symbol}` alongside `X:{symbol}` when trade tape is enabled. Phase 4.8E-2 returns buffered rows even when stream freshness is stale. Phase 4.8E-3 normalizes explicit X-TRADE side/aggressor fields to `buy`/`sell`/null and adds reference-based `change`/`change_pct`. Phase 4.8E-4 maps observed raw SSI side codes `BU=buy` and `SD=sell` while preserving `side_if_available`. Watchlist/company unavailable rows remain `trade_tape=[]` plus separate `trade_tape_status` only when no usable rows exist. | Returns rows only for configured/bootstrap symbols with parsed X-TRADE events carrying price, volume, and timestamp. Request handlers only read the buffer and never start streams, subscribe dynamically, or probe previous REST candidates. B/S must not be inferred from price color or change. Historical time-and-sales history remains unverified. |
| Securities/SecuritiesDetails | `GET /Market/Securities`, `GET /Market/SecuritiesDetails` | Partial metadata | Optional company name, issuer, security type, lot size, listed shares, and listed date may remain null. |
| SSI remaining data audit | `docs/SSI_REMAINING_DATA_AUDIT.md` | Docs-only Phase 4.8F audit | Recommended runtime-proof order: `F` trading session/status, `X-QUOTE` order book, `R` foreign room, `MI` realtime market index, DailyStockPrice unused fields, SecuritiesDetails extended metadata, then `B` bars and instrument modules. |
| News | Not SSI | Disabled until separate provider exists | Mozyfin is not used for VN runtime news. |
| FC Trading/order/account APIs | Not used | Not supported | No order placement, account actions, cash transfer, stock transfer, or portfolio trading actions are in scope. |

Decision rule:

```text
If data is official market price/volume/index/symbol and SSI has endpoint: use SSI.
If data is derived indicator from price/volume: calculate internally from SSI.
If data is realtime snapshot or trade tape and SSI is unavailable: show unavailable, do not silently fallback.
If data is news/fundamentals/corporate actions/macro: use external provider.
If SSI-owned data is unavailable: show unavailable, do not silently fallback.
```

## Phase 4.8F Remaining SSI Data Capability Audit

Phase 4.8F adds `docs/SSI_REMAINING_DATA_AUDIT.md` as the current docs-only backlog for SSI-owned capabilities that are not fully exposed yet.

Highest-value missing SSI-backed candidates:

1. Trading session/status from SSI `F`, if runtime proof confirms stable channel, code mappings, scope, timestamp, and finality semantics.
2. `X-QUOTE` order book live proof and UI productization, after Phase 4.8H backend/API support and current-market payloads confirm field coverage and level counts.
3. Realtime foreign room from SSI `R`, separate from DailyStockPrice daily foreign-flow fields; backend/API support exists and live/UI proof remains deferred.
4. Realtime market index pulse from SSI `MI`, separate from stock watchlist rows and optional DailyIndex REST context; backend/API support exists and live/UI proof remains deferred.
5. DailyStockPrice unused fields such as average price, total buy/sell trade counts, total buy/sell volume, and foreign current room only after field-key and unit proof.
6. SecuritiesDetails extended metadata for derivatives, covered warrants, ETF/fund, and bond instruments as separate instrument metadata tracks.
7. Realtime OHLCV bars from SSI `B` later, after streaming lifecycle and bar interval/correction semantics are proven.

These are SSI-owned candidates. They must not be filled by external providers while SSI can provide or derive them. External providers remain limited to true gaps such as news, corporate actions/dividends/rights/splits, financial statements, ratios/fundamentals, macro, research reports, ownership/shareholder data when not SSI-backed, and approved source-labeled metadata only for SSI-null fields.

## Phase 4.5C Live Gate Findings

Phase 4.5C ran deterministic tests before live SSI checks and used only sanitized smoke output. No raw provider payloads, credentials, auth headers, tokens, account IDs, or raw auth responses were recorded.

Live SSI results on 2026-06-29:

* AccessToken succeeded with configured local credentials.
* DailyOhlc FPT returned 249 rows for the 2025-06-30 to 2026-06-29 smoke range.
* DailyStockPrice FPT returned 249 chunked rows for the same smoke range. The local API smoke populated 20 recent DailyStockPrice foreign-flow rows for FPT, HPG, and SSI and produced non-null latest-available 5D/20D foreign-net summaries.
* Watchlist rows for FPT, HPG, and SSI stayed `status=ok`, `fallback_used=false`, and `latest_price_source=SSI DailyOhlc`.
* DailyIndex VN30 returned a dated row but remained `partial` because the public row lacked a usable `index_value` and `exchange`; exact `VNINDEX` remained unresolved by exact SSI identifier matching.
* IndexComponents VN30 returned 30 component rows.
* IntradayOhlc, realtime snapshot, and trade tape were unavailable in the local API smoke and remained non-fatal optional sections.

No evidence-backed fix was made for DailyIndex level parsing, VNINDEX identifier resolution, true trade-tape history, or final close/session confirmation. Those capabilities remain provider/identifier/entitlement dependent and must not be guessed from other SSI fields.

SSI realtime and trade tape are not confirmed reliable in production runtime. Phase 4.0C found the realtime snapshot route and service wiring correct, with the live backend returning unavailable, 0 quote rows, and a 404 from an SSI realtime REST candidate path for FPT. Phase 4.0C-2 searched the repository for FastConnect realtime REST endpoint contracts, SDK methods, enums, docs references, and configuration but did not identify a supported SSI realtime snapshot endpoint. Phase 4.0C-3 confirmed the correct SSI direction is streaming and added parser coverage for buffered `X`, `X-QUOTE`, and `X-TRADE` envelopes. Phase 4.0C-5 added a config-disabled background manager/cache skeleton. Phase 4.0C-6 added the official-client adapter behind the same disabled runtime flag. Phase 4.0C-7E records that live verifier runs receive callbacks with no-space channels such as `X:FPT`, `X-QUOTE:FPT`, and `X-TRADE:FPT`, while old spaced forms such as `X: FPT` can start transport but do not receive callbacks. Phase 4.0C-8 wires FastAPI startup/shutdown to the existing manager when `SSI_STREAMING_REALTIME_ENABLED=true` and `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS` is non-empty. Phase 4.0C-9 keeps request handlers as cache readers but bypasses the generic endpoint response cache for `/api/v1/stocks/vn/realtime`, adds no-store response headers, and lets the frontend poll quote snapshots separately from watchlist/chart refresh. Phase 4.8E makes the backend runtime subscribe to both `X:{symbol}` and `X-TRADE:{symbol}` when trade tape is enabled; diagnostics now distinguish not-subscribed from subscribed-empty/stale buffer states. Runtime still does not start streams from request handlers or on module import. The dashboard must not use daily close or intraday candles as a realtime substitute, and it must not claim realtime is live unless the realtime snapshot object exists and its public status is `ok`.

## Intraday Failure Diagnostics

Phase 4.0B-2 inspected the live IntradayOhlc failure path after the paging fix was already in place. The company and watchlist paths still call:

```text
VietnamCompanyResearchService -> VietnamMarketService.build_watchlist(include_intraday=True) -> SsiFastConnectFetcher.get_intraday_ohlcv -> GET /Market/IntradayOhlc
```

The request shape remains symbol-scoped and paged internally:

```text
endpoint = IntradayOhlc
symbol = FPT
timeFrame = 1h
pageIndex = 1
pageSize = 1000
ascending = true
```

Live evidence on 2026-06-25 showed SSI returning HTTP 200 with provider code `429` for IntradayOhlc, which is classified as `rate_limited`. This is a provider-side throttle/error response, not a route, parser, public limit, or stale-row filtering failure. Intraday therefore remains unavailable for that response, with `intraday_candles=[]` and `intraday_pulse=null`.

Phase 4.0B-3 added a per-process, thread-safe cooldown for SSI IntradayOhlc after a `rate_limited` classification. The cooldown key is symbol plus requested timeframe, so `FPT` `1h` throttling does not suppress another symbol or another timeframe. While active, the fetcher returns unavailable before requesting a token or calling `GET /Market/IntradayOhlc`, including when a caller force-refreshes the watchlist/company path. The guard only applies to IntradayOhlc; DailyOhlc and DailyStockPrice remain independent. The default window is configured by `SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS=60`, and `0` disables the cooldown.

Sanitized intraday diagnostics may include:

* `failure_class`, such as `rate_limited`, `bad_request_params`, `auth_failed`, `permission_denied`, `timeout`, `network_error`, `parse_failed`, `provider_unavailable`, or `empty_response`.
* `endpoint=IntradayOhlc`.
* `http_status`.
* `provider_code`.
* `error_type`.
* symbol, date range, requested timeframe, page size, public limit, and ascending flag.
* cooldown fields such as `cooldown_active`, `cooldown_recorded`, `cooldown_seconds`, `cooldown_remaining_seconds`, and `cooldown_until`.

Diagnostics must not include raw response bodies, tokens, auth headers, account IDs, consumer IDs, consumer secrets, or raw auth responses.

## Phase 4.11B Historical Intraday Contract Audit

Current paths are intentionally distinct:

| Context | Current path | Production use | Cache/error behavior |
| --- | --- | --- | --- |
| Daily D1 history/chart | `DailyOhlc -> VietnamMarketService.build_chart -> /vn/chart` | Production daily chart | Daily cache; SSI DailyOhlc owns close/OHLCV |
| Compact intraday pulse | `IntradayOhlc -> build_watchlist/include_intraday -> company/watchlist fields` | Optional production adjunct | 7-day request, latest 8 public rows, 60-second cache, stale/date mismatch becomes unavailable |
| Historical intraday chart | None | Not implemented | Phase 4.11C design only |
| Realtime snapshot | background `X:{symbol}` cache | Optional live context | Never a candle |
| Order book | background `X-QUOTE:{symbol}` cache | Optional live context | Never a candle |
| Trade stream | background `X-TRADE:{symbol}` buffer | Optional latest events | No OHLC aggregation |
| Persisted last-known streaming | Phase 4.8S snapshot store | Optional stale context | Never chart history |

The installed `ssi_fc_data` 2.2.2 model declares `intraday_ohlc(symbol, fromDate, toDate, pageIndex, pageSize, ascending, resolution)` and defaults `resolution` to integer `1`. The installed package contains no interval constants, validation, response model, pagination loop, or resolution explanation; its GET wrapper serializes the dataclass with `asdict` and returns raw decoded JSON. The [official package repository sample](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/test_Req_Res.py#L31-L32) uses `DD/MM/YYYY` dates and `resolution=1`. By contrast, the current repository adapter first sends `timeFrame=<request hint>` and can try `interval`, `resolution`, `timeframe`, and case variants. Those variants are compatibility probes, not verified provider interval mappings, and must not be carried into the production chart endpoint once an exact shape is proven.

Existing deterministic tests cover sorted mapping, combined TradingDate/Time input, pagination, latest-row limiting, sanitized provider failures, cooldown, and detected 1m/5m/1h cadence. They use synthetic rows. Historical live notes show minute-like returned spacing even when the request hint was `1h`, plus later provider code `429`; neither proves a supported `1m` or `1h` query parameter.

Phase 4.11B-2 diagnosed the earlier `network_error` as the local sandbox denying the provider socket: an approved credential-free check resolved DNS and completed TLS 1.3 successfully. Six of seven allowed IntradayOhlc calls were then used for FPT on the repository-confirmed completed `2026-06-24` session. An ISO-date request reached SSI but returned HTTP 200/provider code `Error`; the official `24/06/2026` shape succeeded with `resolution=1`, 226 rows, and `totalRecord=226`. No page-2 call was needed.

The successful raw fields were `TradingDate`, `Time`, `Open`, `High`, `Low`, `Close`, `Volume`, `Value`, and `Symbol`. All timestamps parsed, all OHLC rows passed consistency checks, and there were no duplicate or out-of-order timestamps. Raw times ran from `09:15:58` to `14:45:00`; most-common spacing was 60 seconds, minimum 33 seconds, maximum 5,462 seconds, and only 27.68% of same-session deltas were exactly 60 seconds. `resolution=1` is therefore partially verified minute-like data, not yet an approved `1m` contract.

Direct `resolution=5`, `15`, `30`, and `60` calls were accepted but each returned the same 226-row minute-like summary, first/last timestamps, and fields. None produced its numeric cadence, so those numeric mappings are unsupported for production use. The response `Volume` values were numeric strings with no missing/zero/negative entries and 118 decreases; this is inconsistent with a monotonically cumulative-session field, but exact units and final per-bar semantics remain unverified.

The verified live timestamp is separate timezone-free `TradingDate=DD/MM/YYYY` plus `Time=HH:MM:SS`. The future chart contract must interpret those SSI wall-clock values in `Asia/Ho_Chi_Minh`, then emit Unix seconds representing actual instants. The current helper assigns UTC to a naive parsed datetime, so its derived `timestamp` must not be treated as canonical until corrected in a later implementation phase.

The repository's session classifier is HOSE-like and holiday-unaware: ATO 09:00-09:15, continuous morning 09:15-11:30, lunch 11:30-13:00, continuous afternoon 13:00-14:30, ATC 14:30-14:45, and post-close until 15:00. The one completed FPT response observed no 09:00 row, began at 09:15:58, resumed at 13:00 after the large lunch gap, and ended at 14:45:00. The last timestamp is ambiguous rather than proof of how SSI aggregates ATC. Post-close/negotiated rows, final-bar timing, suspended symbols, half sessions, holidays, and HNX/UPCOM differences remain unknown.

## Official Python Streaming Client Inspection

Phase 4.0C-4 installed and inspected the official Python FC Data package locally:

```text
pip package: ssi-fc-data
import module: ssi_fc_data
version: 2.2.2
home page: https://github.com/SSI-Securities-Corporation/python-fcdata
```

Relevant installed modules:

* `ssi_fc_data.fc_md_client`
* `ssi_fc_data.fc_md_stream`
* `ssi_fc_data.model.api`
* `ssi_fc_data.signalr._connection`
* `ssi_fc_data.signalr.transports._transport`

The official client exposes streaming connection/subscription primitives:

* `MarketDataClient(config)` loads an access token through `api/v2/Market/AccessToken`.
* The installed package metadata config sample uses `auth_type`, `consumerID`, `consumerSecret`, `url`, and `stream_url`. No `PrivateKey` reference was found in the installed `ssi_fc_data 2.2.2` package source.
* `MarketDataStream(config, client, on_close=None, on_open=None)` is the stream wrapper.
* `MarketDataStream.start(on_message, on_error, selected_channel)` gets an access token, adds an `Authorization` header, connects to `config.stream_url + "v2.0/signalr"`, registers SignalR hub `FcMarketDataV2Hub`, attaches `Broadcast` and `Error` handlers, invokes `SwitchChannels(selected_channel)` when opened, and starts a daemon websocket thread.
* `MarketDataStream.swith_channel(channel)` invokes `SwitchChannels(channel)` after start. The method name is misspelled as `swith_channel` in the installed package.

The subscription argument is a caller-provided channel string. For symbol-scoped runtime work, use no-space channels such as `X:FPT`, `X-QUOTE:FPT`, `R:FPT`, or `X-TRADE:FPT`; for the bounded market-index pulse path, use no-space index channels such as `MI:VNINDEX`. Do not use `X:ALL`, `MI:ALL`, or any `ALL` subscription. Live verification showed that spaced forms such as `X: FPT` can start transport but do not receive callbacks; `MI:{index_code}` still needs market-hours live proof.

Safety blockers before runtime use:

* The official package does not expose a documented bounded receive/wait API for one-shot calls.
* The websocket transport starts a daemon thread and does not expose a documented join/timeout lifecycle.
* The SignalR negotiation code contains `print(self.headers)`, which would print the `Authorization` header if used directly.
* `Connection.close()` calls `self.__transport.close()`, but the transport implementation exposes `stop()`. A wrapper must handle shutdown through the actual transport before production use.

Adapter direction:

* Do not run the official stream inside FastAPI request handlers.
* Do not start streams on module import.
* Keep runtime subscriptions symbol-scoped, for example `X:FPT`; never use `X:ALL` in normal runtime code.
* Keep the background manager disabled by default through `SSI_STREAMING_REALTIME_ENABLED=false`.
* Build a background runtime adapter only after wrapping or patching the official client so it cannot print auth headers.
* Keep a thread-safe latest snapshot cache keyed by symbol, with TTL and stale-cache unavailable states.
* Feed buffered messages through `SsiFastConnectFetcher.normalize_streaming_realtime_messages`.
* Let `get_realtime_snapshot()` read cache state only when streaming runtime is explicitly enabled and the manager is running.
Phase 4.0C-6 adds `OfficialSsiRealtimeStreamClient`, a small wrapper around `MarketDataClient` and `MarketDataStream`:

* The wrapper is constructed only by `SsiFastConnectFetcher` when `SSI_STREAMING_REALTIME_ENABLED=true`.
* The official package is imported lazily during wrapper `start()`, so disabled runtime does not require `ssi-fc-data`.
* The official market-data client is instantiated only during wrapper `start()`, after required streaming credentials/config are present.
* `MarketDataStream.start(on_message, on_error, selected_channel)` is called with symbol-scoped channels produced by the background manager, never `X: ALL`.
* The wrapper scopes stdout suppression around the official `start()` call to prevent the bundled `print(self.headers)` negotiation path from writing authorization headers.
* Shutdown uses the bundled transport `stop()` method when available and treats the official broken `Connection.close()` path defensively.
* Tests use mocked official modules/clients only; they do not open a websocket or require live SSI.

This is a background-service adapter, not a one-shot request path. If `SSI_STREAMING_REALTIME_ENABLED=true` but credentials are incomplete, the package is unavailable, bootstrap symbols are empty, the manager is not running, the cache is empty, or the cache is stale, realtime remains unavailable with sanitized diagnostics.

## Backend Streaming Bootstrap

### Bounded persisted last-known rows

Phase 4.8S optionally persists one small versioned JSON file of already-normalized, user-safe X, X-QUOTE, X-TRADE, R, MI, and F cache rows. `SSI_STREAMING_SNAPSHOT_ENABLED=false` remains the default. This is operational restart continuity, not historical storage, a provider fallback, or a source of canonical daily prices. The lifecycle restores the file once before the existing bounded streaming manager starts, then live SSI rows supersede restored rows independently by context. Restored rows are always `persisted_stale`; corrupt, expired, or unsupported files do not block startup. Writes are bounded, debounced, atomically replaced, and may perform one final flush during orderly shutdown. Request handlers never restore, write, start, or subscribe.

Phase 4.0C-8 adds FastAPI startup/shutdown wiring for the existing SSI streaming realtime manager. It remains disabled by default:

```text
SSI_STREAMING_REALTIME_ENABLED=false
SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS=
SSI_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS=45
SSI_STREAMING_REALTIME_RECONNECT_ENABLED=true
SSI_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS=2
SSI_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS=30
SSI_STREAMING_REALTIME_RECONNECT_MAX_ATTEMPTS=0
```

When `SSI_STREAMING_REALTIME_ENABLED=true` and `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS` contains a small explicit comma-separated list, backend startup creates the process-local manager, subscribes to symbol-scoped channels such as `X:FPT`, and also subscribes the bounded market-index channels `MI:VNINDEX`, `MI:VN30`, `MI:HNX`, and `MI:UPCOM`. Parsed rows are stored in dedicated caches. Shutdown stops the manager if startup started it.

Important runtime boundaries:

* Bootstrap symbols default empty; enabled streaming with an empty list returns short public cache-miss copy and diagnostics/classification identifying the empty bootstrap configuration. It does not instantiate the official client.
* `ALL`, wildcard, malformed, and duplicate bootstrap symbols are rejected or ignored before channel creation.
* `/api/v1/stocks/vn/realtime` reads the existing process-local cache and manager status only. It does not start a stream, add subscriptions, wait for callbacks, or subscribe dynamically for requested tickers.
* `/api/v1/stocks/vn/realtime` bypasses the generic VN response cache and sends `Cache-Control: no-store`; the streaming manager cache TTL still controls quote freshness and stale states.
* A request for a ticker outside the bootstrap list remains a cache miss unless that ticker was already configured at startup.
* The cache is process-local. Multi-worker deployments have one manager/cache per worker process; use a small explicit symbol list and do not assume cross-worker cache sharing.
* Config OFF has highest precedence. If `SSI_STREAMING_REALTIME_ENABLED=false`, realtime remains unavailable even if a stale process cache exists.
* The dashboard polls the realtime quote endpoint separately from watchlist, chart, and company requests. The default quote polling interval is 3 seconds; trade-tape polling remains a separate opt-in loop.
* UI freshness labels use backend `age_seconds` and `cache_ttl_seconds` when present, then fall back to parsed timestamps. ISO timestamps with microsecond fractions such as `2026-06-26T04:21:01.561821+00:00` are displayed in Vietnam time.

## Streaming Runtime Hardening

Phase 4.0C-10 adds runtime hardening for the process-local SSI streaming manager:

* The manager tracks `stream_health`, `messages_observed`, `parser_rows_observed`, `last_message_at`, `last_message_age_seconds`, sanitized error state, idle state, reconnect counters, subscription counts, next reconnect time, current backoff, and `runtime_status`.
* `runtime_status=running_idle` means the process-local stream has been quiet beyond `SSI_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS`. It does not mean SSI DailyOhlc, DailyStockPrice, intraday, or trade-tape failed.
* Phase 4.8R makes idle/stale runtime state actionable for the manager-owned lifecycle monitor. When lifecycle still wants streaming and the running stream has no recent message, the monitor classifies `last_reconnect_reason=stream_stale`, schedules a debounced reconnect, stops the previous client, and resubscribes the preserved bootstrap channels. Request handlers still only read cache/status and do not start streams or add subscriptions.
* Reconnect is eligible for start failure, stream error callback, stale running stream, and unexpected stopped/errored lifecycle state while the lifecycle still wants streaming.
* Reconnect uses bounded exponential backoff. The first delay is `SSI_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS`, the delay doubles until `SSI_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS`, and `SSI_STREAMING_REALTIME_RECONNECT_MAX_ATTEMPTS=0` means unlimited attempts while the backend is running.
* Reconnect attempts are counted after the initial startup call. The initial bootstrap start is not counted as a reconnect attempt.
* Before reconnecting, the manager stops the current stream client when one exists, then starts a new stream for the preserved bootstrap symbols. Repeated monitor ticks before the scheduled time do not create parallel streams, and successful reconnects preserve process-local latest caches and bounded buffers where safe.
* Phase 4.8R adds a backend Vietnam session classifier for stream health. It is weekday/session-window based and holiday-unaware. Active windows are ATO, continuous morning/afternoon, and ATC; pre-open, lunch, post-close, after-hours, and weekends are inactive.
* Outside active windows, missing/stale `X:{symbol}`, `X-QUOTE:{symbol}`, or `X-TRADE:{symbol}` rows classify as `market_closed`, `idle_market_closed`, or `after_hours_stale` rather than stream failure. The manager must not reconnect solely because quote/order-book/trade counters stop increasing after hours. Real last-known rows remain visible with `Market closed — showing last known data.` copy when the cache/buffer still has rows.
* The lifecycle monitor starts only when streaming is enabled and a safe non-empty bootstrap symbol list exists. Shutdown cancels the monitor, marks the manager as shutdown, stops the stream, and prevents later monitor ticks from reviving streaming.
* Diagnostics remain sanitized: no raw callbacks, raw payloads, auth headers, tokens, consumer IDs, consumer secrets, account IDs, raw auth responses, stdout/stderr, or official package output are exposed.

Phase 4.8R-Live after-hours proof on 2026-07-10 observed the actual classifier in `post_close` with `stream_health=market_closed` and per-context `after_hours_stale` labels. A bounded normal API sequence kept `subscription_count` equal to `expected_subscription_count` (154) and `reconnect_count=0` while messages and selected optional-context counters still advanced. Cached X-QUOTE ladders remained visible as stale last-known data; MI returned only the SSI-published subset. A duplicate-backend bind failure also exposed a late-start race: a background client could finish starting after lifecycle shutdown began. The manager now stops that late client and retains `runtime_status=shutdown`, with a focused regression test. This proves the after-hours no-reconnect classification, not active-session health or a live reconnect; those remain pending a future active-market window.

## Local Streaming Verification

Phase 4.0C-7B added a dev-only verifier, Phase 4.0C-7C hardened it with callback/channel diagnostics, and Phase 4.0C-7D adds direct official-client handshake/subscription inspection:

```powershell
python .\scripts\verify_ssi_streaming_realtime.py --symbols FPT,HPG,SSI,VPB --wait-seconds 60
```

The script runs in its own Python process. It manually creates a `SsiStreamingRealtimeManager`, passes `SsiFastConnectFetcher.normalize_streaming_realtime_messages` as the parser, starts the official streaming adapter only through the manager client factory, polls the script-local cache for a bounded wait, and stops the manager in `finally`.

Important boundaries:

* The script cache is not the FastAPI backend cache.
* The script does not start the backend.
* The script does not call `/api/v1/stocks/vn/realtime`.
* The script does not add a public start/stop API.
* The script does not add production auto-start.
* The script prints only sanitized summary fields, not raw callbacks, auth responses, headers, tokens, consumer IDs, or consumer secrets.
* The script refuses `ALL` symbols and channel templates that would produce `X: ALL`.
* The script can record bounded callback diagnostics without storing raw callback payloads or full `Content`.
* The script can test multiple channel templates sequentially, not concurrently.

Use config-only mode to validate local environment and channel safety without constructing the manager or official client:

```powershell
python .\scripts\verify_ssi_streaming_realtime.py --symbols FPT,HPG --check-config-only
```

Config-only output includes normalized symbols, planned channels, config completeness booleans, and the stream URL host only. It does not print raw env values. Add `--check-package` to report whether `ssi_fc_data` is importable without starting a stream.

Use safe verbose diagnostics when investigating a stream that starts but observes no messages:

```powershell
python .\scripts\verify_ssi_streaming_realtime.py --symbols FPT,HPG,SSI,VPB --channel-templates "X:{symbol};X-QUOTE:{symbol};X-TRADE:{symbol}" --wait-seconds 90 --verbose-safe --suppress-insecure-warning
```

`--verbose-safe` keeps the final output as one JSON object. It adds bounded samples such as top-level callback keys, detected `DataType`/`RType`, content key names, content type, payload lengths, manager status samples, and safe client state class/count/boolean information. It does not store or print full raw messages, full `Content`, auth headers, tokens, consumer IDs, consumer secrets, raw auth responses, or websocket frames.

Diagnostic classifications:

* `cache_hit`: the script-local cache produced parsed snapshot rows.
* `manager_start_failed`: manager start did not reach running state.
* `manager_error`: manager entered an errored state.
* `callback_never_called`: callback attachment could not be confirmed and no callback evidence appeared.
* `callback_called_parser_zero_rows`: the message callback ran but parser output was empty.
* `on_error_called`: the official stream error callback was invoked.
* `no_message_after_start`: manager stayed running with no callback/error evidence during the bounded wait.
* `config_invalid`: required local verification config was missing.
* `unsafe_channel_rejected`: symbol or channel template safety validation failed.
* `unknown`: fallback for states that do not match the above.

After market close, a safe run can report `manager_state=running`, symbol-scoped channels, zero observed messages, and an empty cache. That is not a live-realtime proof. During HOSE market hours, live confidence requires observed messages, parser rows, and script-local quote rows. Phase 4.0C-7E verified that no-space channel formats produce callbacks and cache hits in the verifier. Phase 4.0C-8 adds backend lifecycle bootstrap, but production reliability still depends on process-local cache hits from live startup subscriptions.

Phase 4.0C-7D adds package and direct official-client diagnostics for the case where manager mode starts and exposes websocket transport state but no callback is invoked.

Package inspection:

```powershell
python .\scripts\verify_ssi_streaming_realtime.py --inspect-package-source
```

This mode imports the installed `ssi_fc_data` modules and reports only safe metadata: module file paths, package version, `MarketDataStream` constructor/start signatures, public method names, and class-level capability booleans. It does not construct the official client, start streaming, print source snippets, or print credentials, headers, tokens, auth responses, or raw provider data.

Direct official mode:

```powershell
python .\scripts\verify_ssi_streaming_realtime.py --direct-official --symbols FPT --channel-format-variants --wait-seconds 30 --verbose-safe --suppress-insecure-warning
```

This mode bypasses the manager, cache, and parser. It constructs `MarketDataClient` and `MarketDataStream` directly, calls `MarketDataStream.start(on_message, on_error, selected_channel)`, captures official stdout/stderr, counts direct callbacks, samples only safe envelope metadata, and defensively stops the stream transport. Captured stdout/stderr are never printed raw; if they look header/token-like, the output reports only `captured_output_secret_like_detected=true`.

Direct mode classifications:

* `direct_callback_hit`: the direct `on_message` callback ran.
* `direct_no_message_after_start`: direct start returned, callback/error did not fire during the bounded wait.
* `direct_on_error_called`: the direct official `on_error` callback ran.
* `direct_start_failed`: direct start raised before a usable wait.
* `package_unavailable`: `ssi_fc_data` import failed.
* `unsupported_selected_channel_shape`: selected-channel shape validation failed.
* `unsafe_channel_rejected`: symbol/channel safety validation failed before start.

Channel-format variants are symbol-scoped only and run sequentially:

```text
X: {symbol}
X:{symbol}
X-QUOTE: {symbol}
X-QUOTE:{symbol}
X-TRADE: {symbol}
X-TRADE:{symbol}
```

Selected-channel shape diagnostics support `--selected-channel-shape string|list|comma`. The default `string` preserves the known official sample shape. `list` and `comma` exist only for local diagnostics and must still use symbol-scoped channels. None of these modes uses `X: ALL`.

Direct callback proof is verification evidence only. It does not make realtime production-reliable and does not populate the backend cache. Backend bootstrap is unblocked by no-space manager-mode proof but remains a separate lifecycle/startup phase.

## Configuration

SSI is disabled by default.

```env
SSI_FASTCONNECT_ENABLED=false
SSI_FASTCONNECT_BASE_URL=https://fc-data.ssi.com.vn/api/v2/Market
SSI_FASTCONNECT_CONSUMER_ID=
SSI_FASTCONNECT_CONSUMER_SECRET=
SSI_FASTCONNECT_TIMEOUT_SECONDS=10
SSI_FASTCONNECT_CACHE_TTL_SECONDS=300
SSI_FASTCONNECT_TOKEN_TTL_SECONDS=900
SSI_FASTCONNECT_INTRADAY_ENABLED=true
SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS=60
SSI_FASTCONNECT_REALTIME_ENABLED=true
SSI_FASTCONNECT_TRADE_TAPE_ENABLED=true
SSI_STREAMING_REALTIME_ENABLED=false
SSI_STREAMING_REALTIME_CACHE_TTL_SECONDS=15
SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE=X:{symbol}
SSI_STREAMING_REALTIME_STREAM_URL=https://fc-datahub.ssi.com.vn/
SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS=
SSI_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS=45
SSI_STREAMING_REALTIME_RECONNECT_ENABLED=true
SSI_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS=2
SSI_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS=30
SSI_STREAMING_REALTIME_RECONNECT_MAX_ATTEMPTS=0

VN_DAILY_DATA_PROVIDER=ssi
VN_CHART_DATA_PROVIDER=ssi
VN_DAILY_STOCK_PRICE_PROVIDER=ssi
VN_INDEX_DATA_PROVIDER=ssi
VN_INTRADAY_DATA_PROVIDER=ssi
VN_REALTIME_DATA_PROVIDER=ssi
VN_TRADE_TAPE_PROVIDER=ssi
VN_PROVIDER_COMPARISON_ENABLED=false
MOZYFIN_ENABLED=false
MOZYFIN_NEWS_ENABLED=false
VN_NEWS_PROVIDER=disabled
VN_ALLOW_LEGACY_MOZYFIN_PROVIDER=false
KBS_ENABLED=false
VN_ALLOW_LEGACY_KBS_PROVIDER=false
```

Keep the base URL configurable because SSI documentation may reference another versioned path such as `/v2.0/Market`.

Credentials must only come from local environment variables or a secret manager. Never commit real values.

The provider variables are intentionally strict for supported VN REST market data. Public env parsing accepts `ssi` for daily, chart, DailyStockPrice, and index provider values; invalid values fall back to `ssi`. `VN_PROVIDER_COMPARISON_ENABLED` remains `false`, and no provider comparison endpoint or card is exposed in this phase.

## Security rules

* Do not hardcode SSI credentials.
* Do not print tokens, consumer IDs, consumer secrets, private keys, account IDs, or authorization headers.
* Do not include real credentials in tests, docs, fixtures, examples, changelog, logs, or errors.
* Missing credentials must return a clean unavailable state and must not crash the app.
* AccessToken responses are cached in memory, but tokens are not returned to dashboard payloads.
* Request failures are normalized to secret-free unavailable objects.

## Implemented APIs

The foundation provider supports:

* `POST /Market/AccessToken`
* `GET /Market/IndexList`
* `GET /Market/IndexComponents`
* `GET /Market/Securities`
* `GET /Market/SecuritiesDetails`
* `GET /Market/DailyOhlc`
* `GET /Market/IntradayOhlc`
* `GET /Market/DailyStockPrice`
* `GET /Market/DailyIndex`

The current implementation lives in:

```text
data_provider/ssi_fastconnect_fetcher.py
```

## Dashboard integration

Strict daily/chart behavior:

* `VN_DAILY_DATA_PROVIDER=ssi` uses SSI `DailyOhlc` for the watchlist daily OHLCV dataframe.
* `VN_CHART_DATA_PROVIDER=ssi` uses SSI `DailyOhlc` for `/api/v1/stocks/vn/chart`.
* If SSI DailyOhlc is unavailable, watchlist rows and chart responses return `status: "unavailable"` with `fallback_used: false`.
* Unavailable or empty DailyOhlc refreshes are not stored as successful daily cache values. If a prior valid DailyOhlc cache entry exists, the service can keep serving that stale entry with an explicit cache error; otherwise the row stays unavailable.
* Mozyfin is not called as OHLCV or chart fallback for SSI-owned data.
* Chart responses include `source`, `primary_source`, `actual_source`, `fallback_used`, `fallback_reason`, `points`, and a compatibility `candles` alias.
* Watchlist rows include the same provider metadata. `latest_price` and `daily_close` use the SSI daily close when SSI supplied the daily OHLCV row, and `latest_price_source` is tagged as `SSI`.
* Vite local development proxies `/api` to `http://127.0.0.1:8000` by default. Set `VITE_API_PROXY_TARGET=http://127.0.0.1:<port>` when testing a backend on a non-default port.
* Primary row-level `Data unavailable` UI state is tied to required SSI DailyOhlc validity and SSI DailyOhlc cache errors. Optional quote, metadata, corporate-action, news, intraday, SSI realtime, SSI trade-tape, and SSI index-component states are caveats or separate source statuses, not fatal SSI daily-data failures.
* Dashboard status copy should say `Daily source SSI`, `SSI realtime unavailable`, `SSI trade tape unavailable`, and `News disabled` for those specific states. Concise primary banners should state that daily SSI data is still available; attempted endpoints, HTTP status, and other sanitized technical details belong in diagnostics.
* Live-section contract: object data is `null` when unavailable, list data is `[]` when unavailable, and public statuses stay simple (`ok`, `unavailable`, or `disabled`), with `order_book_status.status=stale` allowed when a real last-known X-QUOTE ladder remains visible. Provider endpoint attempts, HTTP status, stale dates, retryability, and raw provider error summaries belong in diagnostics/logs rather than primary metric fields.

Strict DailyStockPrice behavior:

* `VN_DAILY_STOCK_PRICE_PROVIDER=ssi` owns reference, ceiling, floor, adjusted close, matched volume/value, put-through volume/value, and foreign buy/sell/net volume/value fields.
* If SSI DailyStockPrice is unavailable, these fields return unavailable/null states.
* If SSI DailyOhlc is unavailable but DailyStockPrice returns usable enrichment, the row remains unavailable for canonical daily price/OHLCV, keeps `latest_price=null`, and exposes only source-labeled DailyStockPrice reference/limit/foreign/matched/put-through fields.
* Unavailable DailyStockPrice refreshes are not stored as successful enrichment cache values.
* Mozyfin quote and KBS reference are not used as fallback for SSI-owned reference or foreign-flow fields.
* The enrichment does not mutate OHLCV rows.
* The enrichment does not infer corporate actions.
* Source labels are explicit through `reference_source` and `foreign_flow_source`.
* The selected ticker detail surfaces SSI reference, ceiling/floor, foreign net volume/value, matched volume/value, put-through volume/value, and adjusted close when present.
* Successful watchlist enrichments set `daily_stock_price.status` to `ok` and expose the same values as optional `ssi_*` convenience fields for UI compatibility.
* The service preserves up to 20 recent per-symbol DailyStockPrice foreign-flow rows from the same bounded request used for latest enrichment. It computes `indicators.foreign_net_5d_latest_available` and `indicators.foreign_net_20d_latest_available` only from returned `foreign_net_volume` rows; insufficient history stays null with `foreign_net_history_count`.
* Legacy Mozyfin foreign-history caveats are not used for SSI ownership. SSI history is DailyStockPrice-only, row-count bounded, and non-fatal.
* Normalized rows are publicly labeled `SSI DailyStockPrice`; the generic provider label `SSI` is not used for the enrichment block.
* `quality_status`, `date_match`, `staleness_reason`, `missing_fields`, `field_coverage`, present-value-only `units`, and sanitized diagnostics make partial or mismatched enrichment explicit without changing DailyOhlc validity.
* Date match is `matched`, `mismatched`, `unknown`, or `unavailable`. A mismatched or missing date never changes canonical `latest_price`, which remains SSI DailyOhlc close.
* Volume fields use shares and value/price fields use VND. Missing fields stay null; SSI-provided zero remains zero.
* Diagnostics are allowlisted to endpoint, symbol/date range, row count, selected date, DailyOhlc date, match state, foreign-history row counts/date span/status, coverage, and failure class. Raw payloads and authentication/account values are excluded.

Strict IntradayOhlc behavior:

* `VN_INTRADAY_DATA_PROVIDER=ssi` and `SSI_FASTCONNECT_INTRADAY_ENABLED=true` route VN intraday candles through SSI FastConnect `IntradayOhlc`.
* Watchlist rows expose `intraday_source=SSI` and `intraday_status.status=ok` when SSI returns normalized candles.
* If SSI IntradayOhlc is disabled, fails, or returns no candles, the intraday block returns `disabled` or `unavailable` while the SSI DailyOhlc row remains valid when daily data is present.
* After SSI returns a rate-limit signal for a symbol/timeframe, `SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS` suppresses repeat IntradayOhlc provider calls for that same symbol/timeframe and returns sanitized cooldown diagnostics instead.
* The service validates latest intraday candle date against the latest SSI daily trading date. If the dates mismatch, intraday is marked unavailable and no intraday pulse labels are derived from stale candles.
* Returned candle cadence is detected from sorted provider timestamps when possible and labeled as provider-returned granularity. `intraday_requested_timeframe` records the request hint, while `intraday_actual_granularity`, `intraday_actual_granularity_seconds`, and `intraday_cadence_status` record detected returned cadence and whether it matched the request. The compatibility field `intraday_timeframe` must be read as the requested timeframe, not the actual candle interval.
* `intraday_cadence_status` values are `matched`, `different_from_requested`, `irregular`, `unknown`, and `unavailable`. Duplicate timestamps are ignored for spacing; single-row, missing-timestamp, or malformed rows are classified conservatively instead of producing fake precision.
* The dashboard should use neutral labels such as latest intraday close and intraday change instead of assuming the requested timeframe describes the returned rows.
* Intraday candles are not realtime matched quotes and must remain separate from SSI realtime snapshot, SSI trade tape, and official SSI DailyOhlc close.
* Mozyfin and KBS are not used as intraday candle fallback providers.
* Unavailable live sections must not be filled with placeholder metrics. Use `intraday_pulse=null` with `intraday_candles=[]` for unavailable/stale intraday, `realtime_snapshot=null` for unavailable realtime snapshot, and empty trade lists for unavailable trade tape. Primary UI should show concise unavailable states; attempted endpoints, HTTP status, and sanitized provider diagnostics belong in details/logs.
* Phase 4.7B live cleanup keeps public realtime/trade-tape messages short and moves technical detail to sectioned diagnostics such as `diagnostics.realtime` and `diagnostics.trade_tape`. Watchlist and company trade tape both use list-shaped `trade_tape=[]` when unavailable, with company status in `trade_tape_status`.

SSI request parameters:

* DailyOhlc uses `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, and `ascending`.
* IntradayOhlc uses `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, `ascending`, and an optional `timeFrame` value for the requested dashboard timeframe.
* DailyStockPrice uses `symbol`, `market`, documented `Fromdate`, `Todate`, `pageIndex`, and `pageSize`.
* DailyIndex uses `indexID`, documented `Fromdate`, `Todate`, `pageIndex`, and `pageSize`.
* For DailyOhlc, DailyStockPrice, and DailyIndex only, the provider may retry alternate SSI casing such as `Symbol`, `Market`, `fromDate`, `toDate`, and `IndexId` when the first same-provider response returns no meaningful rows. IndexComponents intentionally uses only the verified `indexCode` request shape.
* Status/message-only SSI responses are diagnostic responses, not data rows; they are not counted as normalized DailyStockPrice or DailyIndex records.

SSI range limits:

* DailyOhlc currently supports the direct 1Y query used by the chart path.
* DailyStockPrice and DailyIndex reject broad ranges with a max-range message, so the provider splits those endpoints into 29-calendar-day inclusive windows.
* Chunked DailyStockPrice windows use `symbol`, `market`, `Fromdate`, `Todate`, `pageIndex=1`, and `pageSize=1000`.
* Chunked DailyIndex windows use `indexID`, `Fromdate`, `Todate`, `pageIndex=1`, and `pageSize=1000`.
* Chunked responses are normalized, status/message-only bodies are filtered, duplicate dates are removed, and rows are returned in ascending chronological order.
* Pagination is bounded by `totalRecord`, empty pages, and a safe max-page guard.
* Selected ticker quick facts request only a recent 29-day DailyStockPrice window; the service reuses those rows for bounded 5D/20D foreign-flow summaries. The local smoke script opts into pacing when validating full-year chunked counts.

Strict DailyIndex behavior:

* `VN_INDEX_DATA_PROVIDER=ssi` enables SSI DailyIndex fetches for optional index context.
* If SSI DailyIndex is unavailable, index data returns unavailable.
* `/api/v1/stocks/vn/daily-index` requests a bounded recent window and returns only latest usable rows for requested indexes.
* DailyIndex still requires exact IndexList resolution. An explicit IndexComponents `index_code` is attempted directly and is not blocked by IndexList unavailability.

Strict index metadata behavior:

* `/api/v1/stocks/vn/index-list` exposes SSI IndexList rows with `source=SSI IndexList`, field coverage, sanitized diagnostics, and `fallback_used=false`.
* `/api/v1/stocks/vn/index-components?index_code=...` exposes SSI IndexComponents rows when SSI returns them, or a clean unavailable state when SSI returns no meaningful component rows.
* The web dashboard calls IndexList, DailyIndex, and IndexComponents independently and keeps optional index context visible when one source is unavailable.
* The dashboard VN30 filter uses SSI IndexComponents component symbols when `status=ok` and component rows exist. If VN30 components are unavailable, the filter keeps the current watchlist visible instead of falling back to hardcoded constituents.
* IndexComponents requests use only the live-verified `indexCode`, `pageIndex=1`, and `pageSize=1000` shape, plus optional normalized market. Empty or unavailable responses do not trigger speculative parameter probes.
* Status/message-only SSI responses are not counted as index component rows.
* SSI provider error/status payloads for IndexComponents are parsed with case-insensitive `code`, `errorCode`, `status`, and `Status` handling and must become sanitized unavailable responses, not backend 500s.
* Mozyfin and KBS are not used as fallback providers for SSI-owned index list, index component, or daily index data.

Company research current behavior:

* `/api/v1/stocks/vn/company/{ticker}` exposes a company research snapshot contract for one VN ticker.
* The endpoint reuses the SSI-backed watchlist row for profile, price, trading stats, foreign flow, and derived technical blocks.
* Source coverage is explicit for Daily OHLCV, DailyStockPrice, Profile, News, Financials, and Corporate actions.
* News, financials, and corporate-action events remain `not_implemented` placeholders in this phase.
* The endpoint does not scrape Mozyfin, call FC Trading, infer corporate actions, or use Mozyfin/KBS fallback for SSI-owned market-data blocks.

## Normalized outputs

`DailyOhlc` rows normalize to:

```json
{
  "date": "2026-06-17",
  "open": 123.4,
  "high": 125.0,
  "low": 122.8,
  "close": 124.6,
  "volume": 1234567,
  "value": 123456789000,
  "source": "SSI"
}
```

`IntradayOhlc` rows normalize to:

```json
{
  "timestamp": 1781161200,
  "date_time": "2026-06-17T10:00:00+07:00",
  "open": 123.4,
  "high": 125.0,
  "low": 122.8,
  "close": 124.6,
  "volume": 1234567,
  "ticker": "FPT",
  "source": "SSI"
}
```

`DailyStockPrice` rows normalize reference, ceiling, floor, OHLC, adjusted close, matched volume/value, put-through volume/value, total volume/value, and foreign buy/sell/net volume/value fields. Mapping is tolerant of common SSI field variants such as `TradingDate`, `RefPrice`, `ReferencePrice`, `BasicPrice`, `Ceiling`, `Floor`, `MatchedVolume`, `PutThroughValue`, `ForeignBuyVol`, `ForeignSellVol`, and `BuyForeignQuantity`/`SellForeignQuantity`.

`DailyIndex` rows normalize index value, change, change percent, total volume/value, matched volume/value, put-through volume/value, breadth fields, trading session, and exchange when present. Public rows add exact IndexList-resolved codes, source, date alignment, missing fields, and field coverage.

`IndexList` rows normalize `index_id`, `index_code`, `index_name`, `exchange`, `market`, and `source`.

`IndexComponents` rows normalize `index_code`, `symbol`, `exchange`, `market`, `weight`, `name`, and `source` when SSI returns component rows. The service sends the caller's explicit normalized code directly through the verified SSI `indexCode` parameter; IndexList remains independent discovery/diagnostic context. Empty/provider-failed responses remain unavailable with `rows=[]`. Responses include sanitized diagnostics for the requested index, selected identifier, identifier source, row count, field coverage, failure class, and process-cache state. Missing optional component fields remain null.

`Securities` and `SecuritiesDetails` rows normalize symbol metadata such as symbol, exchange, market, security type, names, industry, sector, issuer, lot size, listed shares, and listed date when present. Aliases are limited to field names already observed in provider fixtures/tests; absent fields remain null.

VN watchlist/detail responses expose SSI metadata through `symbol_metadata` plus compatibility fields such as `company_name`, `industry`, `sector`, `security_type`, `metadata_source`, `issuer`, `lot_size`, `listed_shares`, and `listed_date`. The service queries `SecuritiesDetails` first and may use `Securities` only as an SSI same-provider metadata fallback. Selection requires an exact normalized symbol match. A single mismatched or symbol-less row is not accepted. Mozyfin is not used for SSI-owned symbol metadata.

Metadata availability and completeness are separate. `status` is `ok` or `unavailable`; `quality_status` is `complete`, `partial`, `unknown`, or `unavailable`. `completeness`, `missing_fields`, and `field_coverage` make partial coverage explicit. Sanitized diagnostics contain attempted endpoint names, normalized row counts, selected endpoint, coverage, and failure class; they never contain tokens, auth headers, or raw provider payloads.

## Unavailable behavior

Disabled provider:

```json
{
  "status": "unavailable",
  "source": "SSI",
  "reason": "SSI FastConnect disabled"
}
```

Missing credentials:

```json
{
  "status": "unavailable",
  "source": "SSI",
  "reason": "SSI FastConnect credentials missing"
}
```

Network, auth, HTTP, provider-status, or JSON parsing failure:

```json
{
  "status": "unavailable",
  "source": "SSI",
  "reason": "SSI FastConnect request failed"
}
```

## Optional smoke check

The smoke script is local-only and not required in CI:

```powershell
python scripts\ssi_fastconnect_smoke.py
```

For endpoint diagnostics, the smoke script also supports a safe probe mode:

```powershell
python scripts\ssi_fastconnect_smoke.py --probe
```

Probe mode tests both documented FC Data base URL shapes and prints only endpoint names, base URL labels, parameter keys, HTTP status, top-level response keys, status/message metadata, counts, and row keys. The normal smoke path validates full-year chunked DailyStockPrice and DailyIndex counts and prints chunk counts plus first/last dates. It prints only safe status and row counts. It does not print tokens, credentials, headers, or full provider bodies.

Phase 4.4B index identifier discovery is a separate manual-only probe:

```powershell
python scripts\probe_ssi_index_capability.py --market HOSE --candidates VN30,VNINDEX --days 7,29
```

It requests IndexList sequentially without a market, with `HOSE`, and with `HNX`; derives at most 10 exact/name-matched candidates from normalized provider rows; tests at most two recent windows capped at 29 days; and tests at most two component market variants per candidate. Output is limited to normalized IndexList metadata and whitelisted status/count/date/failure summaries. It does not print raw responses, messages, credentials, tokens, headers, or account data, and it is not part of application startup or default audit/smoke execution.

## Known limitations / operational notes

* SSI metadata coverage may be limited. A live metadata row can be `status=ok` and `quality_status=partial` while only returning symbol, exchange, market, and source; optional name, industry, sector, issuer, type, lot-size, listed-shares, and listed-date fields may remain null. This does not invalidate SSI DailyOhlc or DailyStockPrice.
* Phase 4.4A live IndexList smoke with `market=HOSE` returned 10 rows spanning HNX and HOSE, included `VN30`, and did not include an exact `VNINDEX`. Treat this as provider evidence: the request market is not a strict response filter, and missing identifiers must remain unavailable.
* Phase 4.4A live DailyIndex smoke returned no usable VNINDEX/VN30 rows after exact identifier handling. VN30 IndexComponents also remained cleanly unavailable. These optional failures did not affect FPT/HPG/SSI DailyOhlc watchlist rows.
* Phase 4.4B supersedes the Phase 4.4A availability finding for VN30. Bounded live discovery on 2026-06-29 proved that DailyIndex uses `indexID=VN30`: it returned 5 rows in the 7-day window and 22 rows in the 29-day window, latest date 2026-06-29. `indexCode=VN30` remained unavailable for DailyIndex.
* Because the no-market IndexList request remained unavailable, the daily-index service performs its prerequisite exact-identifier lookup with the verified `market=HOSE` request. This is only a discovery request hint: returned identifiers remain authoritative, cross-market rows remain possible, and missing exact identifiers are not guessed.
* SSI index REST requests are paced at a 1.15-second interval within one fetcher. Live service diagnostics showed that an immediate DailyIndex call after IndexList was classified `rate_limited`; the narrow interval applies only to IndexList, DailyIndex, and IndexComponents. Explicit IndexComponents uses one verified parameter shape rather than variant probes.
* The live 2026-06-29 VN30 DailyIndex row returned `IndexValue=0` while change and liquidity fields were populated. The mapper treats non-positive index levels as missing, so the optional row remains partial with `index_value=null` instead of presenting zero as a real market level.
* Phase 4.4B proved that IndexComponents has the inverse parameter shape and a nested response: `indexCode=VN30` returned an exact outer VN30 row containing 30 `IndexComponent` members, while `indexID=VN30` returned mismatched HNX outer rows. Production now sends only `indexCode` and flattens nested `StockSymbol` members only after exact outer-index matching. It therefore never substitutes HNX constituents for VN30.
* IndexComponents returned the same exact VN30 count with market omitted and with `market=HOSE`; do not interpret that as proof that market filtering is strict. IndexList with `HOSE` and `HNX` also returned the same 10 cross-market rows, and IndexList without a market remained unavailable.
* Live IndexList validation works in the current SSI environment, but `market=HOSE` can still return cross-market-looking index codes such as `HNX30`, `HNXINDEX`, and `HNXUPCOMINDEX`; use SSI-returned rows instead of assuming the request market filter is strict.
* VN30 components are now live-verified only through the exact SSI nested response. Continue to return `components=[]` when an exact outer index row or usable nested members are absent. Do not hardcode members or fallback to Mozyfin/KBS.
* Quote fields are not currently a reliable REST latest-price source. Watchlist payloads can have `quote_cache=missing`, `quote=null`, `quote_price_date=null`, and `quote_price_raw_field=null`; `latest_price` uses SSI DailyOhlc close when SSI daily rows are available.
* Phase 4.6F-Recovery-2 live diagnostics on 2026-07-06 found that configured credentials and `api/v2` access could fetch DailyStockPrice and VN30 IndexComponents, while DailyOhlc returned sanitized provider `code=Exception` for the documented `symbol/fromDate/toDate/pageIndex/pageSize/ascending` shape. This is DailyOhlc endpoint/provider behavior, not proof that realtime, IndexComponents, or DailyStockPrice are broken. Keep rows unavailable rather than substituting DailyStockPrice close or realtime values for DailyOhlc.
* Phase 4.6F-Recovery-3 keeps the existing SSI DailyOhlc alternate parameter casing retry for non-rate-limit provider errors and treats all-empty DailyOhlc responses as unavailable. Provider `429`/rate-limited responses are not variant-probed further, to avoid worsening SSI throttling.
* Phase 4.6F-Recovery-4 adds `scripts/diagnose_ssi_daily_ohlc.py` for manual, bounded, secret-safe DailyOhlc capability checks. A 5-day FPT live run on 2026-07-06 returned sanitized provider `code=Exception` for the primary `symbol/fromDate/toDate` request shape and `code=429` for the existing alternate casing, with no normalized DailyOhlc rows. Further DailyOhlc probing was stopped after the rate-limit response. The diagnostic does not print credentials, headers, tokens, account IDs, raw provider bodies, or fallback data.
* Phase 4.6G adds a DailyOhlc-specific process-local rate-limit cooldown. `SSI_DAILY_OHLC_RATE_LIMIT_COOLDOWN_SECONDS` defaults to 300 seconds and `0` disables the guard. HTTP 429, provider `code=429`/`errorCode=429`, or an already normalized `rate_limited` DailyOhlc failure records cooldown by normalized SSI base URL plus ticker. While active, the fetcher returns `failure_class=rate_limited` with sanitized cooldown timing diagnostics before requesting AccessToken or `/Market/DailyOhlc`; force refresh does not bypass it. Provider `code=Exception`, empty rows, auth failures, and generic provider failures do not start the cooldown. A failed refresh is never cached as successful DailyOhlc data, and the service may continue serving a prior valid stale DailyOhlc cache entry with the cooldown reason in cache errors.
* DailyStockPrice and DailyIndex require <=29/30-day request windows. Provider chunking is available for smoke/debug/internal validation, but broad automatic UI requests should be avoided unless deliberately designed. Phase 4.5B did not add broad market scans; it reuses the existing selected-ticker/watchlist per-symbol recent window.
* Local market-data DB storage is deferred. Current mode remains SSI live API plus backend cache/TTL.
* SSI IntradayOhlc is implemented for compact dashboard/company pulse, but live availability still depends on SSI endpoint permission and response shape. If unavailable, show the SSI intraday state without fallback.
* SSI IntradayOhlc live rows may be stale relative to SSI DailyOhlc or have a different cadence than the requested dashboard timeframe. Keep daily rows OK, mark stale intraday unavailable, and surface the sanitized date/granularity diagnostics.
* Optional live status blocks now carry a broad `status` plus safe `reason_code`/`classification` fields. Intraday reasons distinguish cadence mismatch, date mismatch, no usable rows, rate limit, provider error, disabled, and unknown states without changing DailyOhlc ownership.
* SSI realtime snapshot, trade-tape, order-book, session/status, and foreign-room contracts are wired through the existing optional live backend/API paths. Realtime now has a disabled-by-default background manager/cache skeleton; live official-client streaming, entitlements, and row shapes still require validation. Unavailable results should remain neutral SSI unavailable states with specific reasons such as `config_disabled`, `not_started`, `bootstrap_symbols_empty`, `ticker_not_bootstrapped`, `running_idle`, `cache_empty`, `cache_stale`, `connection_error`, `auth_or_entitlement_failure`, `network_or_tls_failure`, `rate_limited`, or `unknown`.
* SSI realtime diagnostics should distinguish streaming disabled, manager not started, cache empty, cache stale, cache hit, manager error, live adapter not enabled, running-idle/stale state, market-closed state, and reconnecting state. Do not print or return tokens, credentials, auth headers, signed URLs, or raw provider bodies. A running-idle, stale, market-closed, after-hours-stale, reconnecting, or cache-empty realtime state means the event-driven stream has no usable fresh cached tick for the ticker; it is not evidence that DailyOhlc or DailyStockPrice failed.
* Observability keeps `mozyfin` as a minimal disabled legacy block. Generic VN request/cache/single-flight counters live under `dashboard_runtime`; do not interpret those counters as Mozyfin activity. SSI status is split into explicit `ssi_core`, `ssi_intraday`, `ssi_realtime`, and `ssi_trade_tape` blocks.
* VN news/social is disabled because Mozyfin free-tier API access is no longer available for the dashboard. Future news should use a separate NewsProvider contract, not Mozyfin scraping.
* Strict VN runtime must not construct `MozyfinFetcher` for watchlist, company, realtime, index, corporate-action, or observability paths while Mozyfin legacy flags are disabled. Corporate actions remain explicit unavailable placeholders until a verified external event provider is configured.
* News rendering is independent from SSI index, quote, metadata, finality, intraday, and realtime caveats. If a future NewsProvider supplies rows, the selected ticker news block should remain visible and clearly separate from SSI market data.
* Keep DailyOhlc and DailyStockPrice labels separate: daily close/chart candles come from SSI DailyOhlc; reference/limits/foreign/matched/put-through fields come from SSI DailyStockPrice.
* Keep primary cache labels scoped to SSI DailyOhlc. Quote/news/intraday/realtime cache or availability issues should remain in diagnostics or caveats so they do not imply official daily market data is unavailable.
* Latest smoke found a same-date FPT mismatch on `2026-06-22`: SSI DailyOhlc/dashboard close fields were `70,700`, while SSI DailyStockPrice close/adjusted close were `70,800`; DailyOhlc volume was `3,642,400`, while DailyStockPrice matched volume was `3,643,500`. Keep SSI DailyOhlc as canonical `latest_price` until canonical source and final/provisional semantics are explicitly designed.
* Trade-tape public data remains `trade_tape=[]` unless the process-local X-TRADE buffer has parsed event rows for the requested bootstrapped symbol. Startup-owned streaming now registers `X-TRADE:{symbol}` when trade tape is enabled; diagnostics distinguish `xtrade_not_subscribed`, disabled, subscribed-empty, stale, cache-hit, and buffered-row-available states. X-TRADE rows are latest-event tape rows only, not historical time-and-sales history. Explicit SSI side/aggressor fields are normalized to `buy`, `sell`, or null; observed raw `BU`/`SD` map to Buy/Sell and remain preserved in `side_if_available`. Unknown side remains null and must not be inferred from price color or change direction. `change` and `change_pct` are calculated against SSI DailyStockPrice reference when available.
* Phase 4.8G adds SSI `F:{symbol}` trading session/status runtime-proof support through the same startup-owned streaming lifecycle. Parsed `F` rows populate a dedicated session/status cache and optional watchlist fields only; they are not realtime quotes, trade-tape rows, DailyOhlc rows, DailyStockPrice enrichment, or price sources. Safe public fields preserve raw `trading_session` and `trading_status` values, but the backend does not map SSI codes to open/closed/halted/final meanings until live evidence proves them.
* Phase 4.8I adds SSI `R:{symbol}` foreign-room backend/API support through the same startup-owned streaming lifecycle. Parsed `R` rows populate a dedicated foreign-room cache and optional watchlist fields only; they are not realtime quotes, trade-tape rows, order-book rows, session/status rows, DailyOhlc rows, DailyStockPrice enrichment, or price sources. Safe public fields include explicit total/current room and foreign buy/sell volume/value metrics when valid; value-unit and approximate-value meanings remain `needs_semantics_proof` until live evidence proves them.
* Phase 4.8J adds SSI `MI:{index_code}` market-index pulse backend/API support through the same startup-owned streaming lifecycle. Parsed `MI` rows populate a dedicated market-index cache and the separate market-index pulse API only; they are not stock watchlist rows, realtime quotes, REST DailyIndex rows, DailyOhlc rows, DailyStockPrice enrichment, or price sources. Safe public fields include explicit index value/change/activity/breadth metrics when valid; channel format and value/breadth meanings remain `needs_live_proof` until live evidence proves them.
* Realtime and trade-tape unavailable messages should be short and user-safe. Streaming manager/cache state and sanitized provider error summaries should move to diagnostics. When `trade_tape` rows exist, the UI should render those timestamped rows even if diagnostics say stream/cache freshness is stale; when the stream is not enabled, not started, not bootstrapped, or empty, classify trade tape with stream-specific unavailable reasons instead of implying a working historical time-and-sales feed.
* REST realtime candidate probing is disabled; do not reintroduce repeated speculative realtime endpoint probes.

## Current limitations

* SSI FastConnect credentials are not bundled; with default placeholder config, SSI-owned sections are unavailable.
* Mozyfin is disabled for VN dashboard runtime; news/social returns disabled or `not_implemented`.
* SSI realtime snapshot, trade tape, `X-QUOTE:{symbol}` order book, `R:{symbol}` foreign room, `MI:{index_code}` market-index pulse, and `F:{symbol}` session/status context remain separate from daily close and intraday candles.
* KBS is disabled by default and legacy-only behind explicit development flags.
* Local DB market-data storage is deferred while current call volume remains low and backend cache/TTL is sufficient.
* No UI source switcher or comparison card exists.
* No provider comparison endpoint exists in this strict-default phase.
* SSI streaming/protocol hardening remains a later phase; this phase wires the dashboard contract, disabled background manager/cache skeleton, and safe unavailable states.
* Exact VN30 IndexComponents rows are live-verified through `indexCode=VN30`; any missing, mismatched, empty, or provider-failed component response still returns `rows=[]`.
* Phase 4.6F-4 makes explicit component codes independent from IndexList and adds a process-level cache across request-scoped services: usable rows cache for 300 seconds; unavailable, rate-limited, and no-row responses cache for 60 seconds. The key is SSI provider + IndexComponents endpoint + normalized index code + optional market. `force_refresh=true` bypasses it.
* Phase 4.6D bounded timing on 2026-06-29 measured exact VN30 IndexComponents at 1.66 seconds, versus 95.99 seconds for the first normal-cache 30-symbol watchlist and 52.21 seconds for an immediate repeat. The member request is not the long path; watchlist construction is sequential and can perform per-symbol DailyOhlc, metadata, bounded DailyStockPrice, optional live-section, and indicator work.
* `VietnamMarketService` is currently created per API request and its lazily created `SsiFastConnectFetcher` owns an instance-local provider cache. Module-level service caches still reduce some repeated work, but the fetcher cache is not shared across separate watchlist requests. Do not introduce broad provider parallelism as a shortcut; shared fetcher/cache lifetime, thread safety, token lifecycle, streaming-manager attachment, and SSI pacing need a dedicated performance design and tests.
* Phase 4.6E keeps that backend/provider behavior unchanged and improves perceived VN30 readiness in the web client: exact SSI IndexComponents membership renders as ordered shells, then normal-cache watchlist requests run sequentially in groups of five. A failed group remains explicit and retryable without clearing completed groups. This is ordinary HTTP batching, not streaming, provider parallelism, fallback data, or a change to DailyOhlc price ownership.
* Phase 4.6F profiling on 2026-07-02 measured cold 1/5/10 ticker watchlists at 3.559/15.984/32.145 seconds. For 10 tickers, provider-stage totals were DailyOhlc 10.861s, metadata 7.529s, optional intraday 5.953s, optional trade tape 4.102s, and DailyStockPrice/history 3.385s; TA took 0.279s and JSON serialization 0.0013s. The path is provider-I/O bound and approximately linear, so backend concurrency remains deferred.
* The same profile proved a cache-lifetime gap: request-scoped fetchers caused bounded DailyStockPrice enrichment/history to refetch while process-level DailyOhlc, metadata, and optional caches could hit. The combined latest-enrichment/history tuple now uses the existing thread-safe service cache for 300 seconds, keyed by symbol, market, provider, current Vietnam date, lookback, and limit. Explicit force refresh bypasses it. A five-ticker immediate repeat improved from 3.564s to 2.293s and all five DailyStockPrice entries were cache hits; DailyOhlc remained canonical.
* `scripts/profile_vn_watchlist_hydration.py` is a manual-only profiler for fixed 1/5/10 cases or an explicit bounded custom list. It emits aggregate stage/cache/status/source timings only, caps normal custom input at 10, requires `--allow-thirty` for up to 30, and never prints exception messages or provider payloads.
* Fundamentals, corporate actions, dividends, rights, splits, and macro data require external providers.
* FC Trading remains out of scope.

## Provider-dependent product phases

The full VN product phase plan is in `docs/VN_DASHBOARD_ROADMAP.md`. SSI-dependent phases are:

| Phase | SSI dependency | Integration rule |
| --- | --- | --- |
| Phase 0 - SSI Provider Milestone Freeze | DailyOhlc, DailyStockPrice, IntradayOhlc contract, realtime/trade-tape contracts, metadata, index diagnostics | Freeze current SSI-first source ownership and unavailable-state behavior. |
| Phase 1 - Data Quality Summary | DailyOhlc, DailyStockPrice, IntradayOhlc, realtime status, trade-tape status, Securities/SecuritiesDetails | Surface source mismatch, stale live sections, partial metadata, and finality uncertainty without hiding daily data. |
| Phase 2 - Clean Public Contract and Diagnostics Split | IntradayOhlc, realtime endpoint candidates, trade-tape endpoint candidates | Normalize `null`/`[]` public data and move endpoint/http/raw provider details to diagnostics. |
| Phase 3 - Progressive Dashboard Workspace | Same SSI-backed watchlist/company snapshot contract | Keep daily scan first; add readiness states, selected ticker progressive disclosure, request orchestration, local filters, and chart UX without changing SSI ownership. |
| Phase 4.0 - SSI Realtime and Trade-Tape Investigation | Realtime/trade-tape endpoint candidates and entitlements | Confirm endpoint names, permissions, row shapes, error classes, and backoff; do not claim live support until data exists with status `ok`. |
| Phase 4.1 - Intraday Cadence Clarity | IntradayOhlc returned candle spacing and status metadata | Detect actual returned cadence and label stale/unavailable intraday clearly. |
| Phase 4.5A - SSI Remaining Capability Completion | All current SSI FastConnect market-data endpoints and optional live contracts | Keep SSI-owned domains first, separate partial/unknown SSI gaps from external-provider-required domains, and do not implement VNStocks/FiinGroup runtime. |
| Phase 5.0 - External Provider Architecture | None; external domains are not SSI-owned market data | Define separate NewsProvider, FundamentalsProvider, CorporateActionsProvider, and MacroProvider contracts before implementation. |
| Phase 5.1 - NewsProvider | None; news is not SSI-owned | Keep news disabled until a separate provider exists. |
| Phase 5.2 - Corporate Actions and Dividends | None unless SSI exposes explicit structured sources later | Use only explicit structured event sources; do not infer events from market-data gaps. |
| Phase 6.0 - Backend Performance and Caching | DailyOhlc, DailyStockPrice, metadata, diagnostics if performance evidence justifies storage | Persist source/date/fetched_at only if durable storage is introduced; keep stale-data semantics explicit. |
| Phase 7.0 - Product Packaging | SSI source/freshness status as validation inputs | Clean runbooks, startup scripts, smoke/test/release checklist, and deprecated docs without changing provider semantics. |

## Next phase

Use the roadmap phase order. Phase 0 freezes the current SSI milestone; Phase 1 and Phase 2 make data quality and public contracts clearer; Phase 3.2-3.6 make `/vietnam` a progressive workspace before Phase 4.0 realtime/trade-tape investigation and later external provider work. Do not introduce FC Trading or Mozyfin/KBS fallback for SSI-owned market data in any phase.
