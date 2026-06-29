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
* SSI streaming realtime parser coverage for buffered `X`, `X-QUOTE`, and `X-TRADE` messages.
* Config-disabled SSI streaming manager/cache skeleton for future background runtime work.
* Official `ssi-fc-data` Python client adapter behind the disabled streaming runtime flag.
* FastAPI startup bootstrap for SSI streaming realtime when explicitly enabled and given a small bootstrap symbol list.
* Realtime endpoint response-cache bypass and frontend quote polling tuned for the process-local streaming cache.
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
| Realtime snapshot | SSI FastConnect Data streaming | Provider/service/API/UI contract added; parser coverage for buffered `X`, `X-QUOTE`, and `X-TRADE`; config-disabled background manager/cache skeleton added; official client adapter is available only behind `SSI_STREAMING_REALTIME_ENABLED=true`; FastAPI startup can start a process-local manager only when `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS` is non-empty; default channel template is `X:{symbol}` | Show SSI unavailable until the backend lifecycle cache safely populates current rows; no request-handler streaming and no KBS fallback |
| Trade tape | SSI FastConnect Data streaming or future verified trade contract | Provider/service/API/UI contract added; live history/list semantics still need confirmation | Keep separate from realtime latest-trade messages and official daily OHLCV |
| Realtime best bid/ask, matched data, foreign room, index stream, realtime bars/OHLC | SSI streaming/protocol hardening later | Parser/cache skeleton exists only for realtime quote/trade snapshot messages; live official stream is not connected | Keep semantics explicit and unavailable until SSI behavior is proven stable |
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
| Realtime snapshot | SSI FastConnect streaming data types `X`, `X-QUOTE`, `X-TRADE` | Parser covered; config-disabled manager/cache skeleton exists; official client adapter is config-gated; FastAPI startup bootstrap is config-gated and symbol-list gated | Phase 4.0C verified the route/service/fetcher wiring and config gate. Phase 4.0C-2 found no supported SSI REST realtime endpoint, SDK method, enum, or hidden repo contract. Phase 4.0C-3 confirmed the realtime direction is streaming. Phase 4.0C-5 added a request-safe cache read path that stays disabled by default. Phase 4.0C-6 added a lazy official-client adapter. Phase 4.0C-7E changed the default channel to the live-verified no-space form `X:{symbol}`; spaced forms are retained only for diagnostics/custom overrides. Phase 4.0C-8 added FastAPI lifecycle bootstrap that starts the process-local manager only when `SSI_STREAMING_REALTIME_ENABLED=true` and explicit bootstrap symbols are configured. Phase 4.0C-9 makes the realtime endpoint bypass the generic backend response cache so fresh process-local stream-cache rows can surface immediately. Previous candidate names `RealtimeQuote`, `RealtimePrice`, `RealtimeSnapshot`, and `SecuritiesRealtime` are discovery evidence only and are no longer probed at runtime. The dashboard must not claim realtime is live unless `realtime_snapshot` is non-null and `realtime_status.status = ok`. |
| Trade tape | SSI trade-tape endpoint candidates or future verified stream/list contract | Contract exists; unavailable in Phase 4.5C local API smoke | Not confirmed live. Desired unavailable contract is `trade_tape=[]` plus `trade_tape_status`, with endpoint/http details in diagnostics. `X-TRADE` remains latest-trade stream context and is not evidence of historical trade-tape rows. |
| Securities/SecuritiesDetails | `GET /Market/Securities`, `GET /Market/SecuritiesDetails` | Partial metadata | Optional company name, issuer, security type, lot size, listed shares, and listed date may remain null. |
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

SSI realtime and trade tape are not confirmed reliable in production runtime. Phase 4.0C found the realtime snapshot route and service wiring correct, with the live backend returning unavailable, 0 quote rows, and a 404 from an SSI realtime REST candidate path for FPT. Phase 4.0C-2 searched the repository for FastConnect realtime REST endpoint contracts, SDK methods, enums, docs references, and configuration but did not identify a supported SSI realtime snapshot endpoint. Phase 4.0C-3 confirmed the correct SSI direction is streaming and added parser coverage for buffered `X`, `X-QUOTE`, and `X-TRADE` envelopes. Phase 4.0C-5 added a config-disabled background manager/cache skeleton. Phase 4.0C-6 added the official-client adapter behind the same disabled runtime flag. Phase 4.0C-7E records that live verifier runs receive callbacks with no-space channels such as `X:FPT`, while old spaced forms such as `X: FPT` can start transport but do not receive callbacks. Phase 4.0C-8 wires FastAPI startup/shutdown to the existing manager when `SSI_STREAMING_REALTIME_ENABLED=true` and `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS` is non-empty. Phase 4.0C-9 keeps request handlers as cache readers but bypasses the generic endpoint response cache for `/api/v1/stocks/vn/realtime`, adds no-store response headers, and lets the frontend poll quote snapshots separately from watchlist/chart refresh. Runtime still does not start streams from request handlers or on module import. The dashboard must not use daily close or intraday candles as a realtime substitute, and it must not claim realtime is live unless the realtime snapshot object exists and its public status is `ok`.

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

The subscription argument is a caller-provided channel string. For symbol-scoped runtime work, use no-space channels such as `X:FPT`, `X-QUOTE:FPT`, or `X-TRADE:FPT`; do not use `X:ALL` or any `ALL` subscription. Live verification showed that spaced forms such as `X: FPT` can start transport but do not receive callbacks.

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

When `SSI_STREAMING_REALTIME_ENABLED=true` and `SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS` contains a small explicit comma-separated list, backend startup creates the process-local manager, subscribes to symbol-scoped channels such as `X:FPT`, and stores parsed snapshots in the manager cache. Shutdown stops the manager if startup started it.

Important runtime boundaries:

* Bootstrap symbols default empty; enabled streaming with an empty list returns `SSI streaming realtime bootstrap symbols empty.` and does not instantiate the official client.
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

* The manager tracks `messages_observed`, `parser_rows_observed`, `last_message_at`, sanitized error state, idle state, reconnect counters, next reconnect time, current backoff, and `runtime_status`.
* `runtime_status=running_idle` means the process-local stream has been quiet beyond `SSI_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS`. It does not mean SSI DailyOhlc, DailyStockPrice, intraday, or trade-tape failed.
* Because this repository does not currently have a backend market-hours/session utility, idle state is diagnostic-only for reconnect decisions. The monitor does not reconnect endlessly just because no messages arrive in an unknown or likely inactive window.
* Reconnect is eligible for start failure, stream error callback, and unexpected stopped/errored lifecycle state while the lifecycle still wants streaming.
* Reconnect uses bounded exponential backoff. The first delay is `SSI_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS`, the delay doubles until `SSI_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS`, and `SSI_STREAMING_REALTIME_RECONNECT_MAX_ATTEMPTS=0` means unlimited attempts while the backend is running.
* Reconnect attempts are counted after the initial startup call. The initial bootstrap start is not counted as a reconnect attempt.
* Before reconnecting, the manager stops the current stream client when one exists, then starts a new stream for the preserved bootstrap symbols. Repeated monitor ticks before the scheduled time do not create parallel streams.
* The lifecycle monitor starts only when streaming is enabled and a safe non-empty bootstrap symbol list exists. Shutdown cancels the monitor, marks the manager as shutdown, stops the stream, and prevents later monitor ticks from reviving streaming.
* Diagnostics remain sanitized: no raw callbacks, raw payloads, auth headers, tokens, consumer IDs, consumer secrets, account IDs, raw auth responses, stdout/stderr, or official package output are exposed.

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
* Mozyfin is not called as OHLCV or chart fallback for SSI-owned data.
* Chart responses include `source`, `primary_source`, `actual_source`, `fallback_used`, `fallback_reason`, `points`, and a compatibility `candles` alias.
* Watchlist rows include the same provider metadata. `latest_price` and `daily_close` use the SSI daily close when SSI supplied the daily OHLCV row, and `latest_price_source` is tagged as `SSI`.
* Vite local development proxies `/api` to `http://127.0.0.1:8000` by default. Set `VITE_API_PROXY_TARGET=http://127.0.0.1:<port>` when testing a backend on a non-default port.
* Primary row-level `Data unavailable` UI state is tied to required SSI DailyOhlc validity and SSI DailyOhlc cache errors. Optional quote, metadata, corporate-action, news, intraday, SSI realtime, SSI trade-tape, and SSI index-component states are caveats or separate source statuses, not fatal SSI daily-data failures.
* Dashboard status copy should say `Daily source SSI`, `SSI realtime unavailable`, `SSI trade tape unavailable`, and `News disabled` for those specific states. Concise primary banners should state that daily SSI data is still available; attempted endpoints, HTTP status, and other sanitized technical details belong in diagnostics.
* Live-section contract: object data is `null` when unavailable, list data is `[]` when unavailable, and public statuses stay simple (`ok`, `unavailable`, or `disabled`). Provider endpoint attempts, HTTP status, stale dates, retryability, and raw provider error summaries belong in diagnostics/logs rather than primary metric fields.

Strict DailyStockPrice behavior:

* `VN_DAILY_STOCK_PRICE_PROVIDER=ssi` owns reference, ceiling, floor, adjusted close, matched volume/value, put-through volume/value, and foreign buy/sell/net volume/value fields.
* If SSI DailyStockPrice is unavailable, these fields return unavailable/null states.
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

SSI request parameters:

* DailyOhlc uses `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, and `ascending`.
* IntradayOhlc uses `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, `ascending`, and an optional `timeFrame` value for the requested dashboard timeframe.
* DailyStockPrice uses `symbol`, `market`, documented `Fromdate`, `Todate`, `pageIndex`, and `pageSize`.
* DailyIndex uses `indexID`, documented `Fromdate`, `Todate`, `pageIndex`, and `pageSize`.
* The provider retries alternate SSI casing such as `Symbol`, `Market`, `fromDate`, `toDate`, and `IndexId` only when the first same-provider response returns no meaningful rows.
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
* DailyIndex and IndexComponents are not called when IndexList cannot confirm the requested identifier.

Strict index metadata behavior:

* `/api/v1/stocks/vn/index-list` exposes SSI IndexList rows with `source=SSI IndexList`, field coverage, sanitized diagnostics, and `fallback_used=false`.
* `/api/v1/stocks/vn/index-components?index_code=...` exposes SSI IndexComponents rows when SSI returns them, or a clean unavailable state when SSI returns no meaningful component rows.
* The web dashboard calls IndexList, DailyIndex, and IndexComponents independently and keeps optional index context visible when one source is unavailable.
* The dashboard VN30 filter uses SSI IndexComponents component symbols when `status=ok` and component rows exist. If VN30 components are unavailable, the filter keeps the current watchlist visible instead of falling back to hardcoded constituents.
* IndexComponents requests use `indexCode`, `pageIndex=1`, and `pageSize=1000` first, and retry safe same-provider parameter variants only when SSI returns no meaningful rows.
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

`IndexComponents` rows normalize `index_code`, `symbol`, `exchange`, `market`, `weight`, `name`, and `source` when SSI returns component rows. The service first requires an exact `IndexList` match, then calls `IndexComponents` with that identifier. Missing identifiers and empty/provider-failed responses remain unavailable with `rows=[]`. Responses include sanitized diagnostics for the requested index, selected identifier, identifier source, row count, field coverage, and failure class. Missing optional component fields remain null.

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
* SSI index REST requests are paced at a 1.15-second interval within one fetcher. Live service diagnostics showed that an immediate DailyIndex call after IndexList was classified `rate_limited`; the narrow interval applies only to IndexList, DailyIndex, and IndexComponents and also spaces their chunks/parameter variants.
* The live 2026-06-29 VN30 DailyIndex row returned `IndexValue=0` while change and liquidity fields were populated. The mapper treats non-positive index levels as missing, so the optional row remains partial with `index_value=null` instead of presenting zero as a real market level.
* Phase 4.4B proved that IndexComponents has the inverse parameter shape and a nested response: `indexCode=VN30` returned an exact outer VN30 row containing 30 `IndexComponent` members, while `indexID=VN30` returned mismatched HNX outer rows. The fetcher sends `indexCode` first to avoid rate-limiting the working shape behind a failed request, then flattens nested `StockSymbol` members only after exact outer-index matching. It therefore never substitutes HNX constituents for VN30.
* IndexComponents returned the same exact VN30 count with market omitted and with `market=HOSE`; do not interpret that as proof that market filtering is strict. IndexList with `HOSE` and `HNX` also returned the same 10 cross-market rows, and IndexList without a market remained unavailable.
* Live IndexList validation works in the current SSI environment, but `market=HOSE` can still return cross-market-looking index codes such as `HNX30`, `HNXINDEX`, and `HNXUPCOMINDEX`; use SSI-returned rows instead of assuming the request market filter is strict.
* VN30 components are now live-verified only through the exact SSI nested response. Continue to return `components=[]` when an exact outer index row or usable nested members are absent. Do not hardcode members or fallback to Mozyfin/KBS.
* Quote fields are not currently a reliable REST latest-price source. Watchlist payloads can have `quote_cache=missing`, `quote=null`, `quote_price_date=null`, and `quote_price_raw_field=null`; `latest_price` uses SSI DailyOhlc close when SSI daily rows are available.
* DailyStockPrice and DailyIndex require <=29/30-day request windows. Provider chunking is available for smoke/debug/internal validation, but broad automatic UI requests should be avoided unless deliberately designed. Phase 4.5B did not add broad market scans; it reuses the existing selected-ticker/watchlist per-symbol recent window.
* Local market-data DB storage is deferred. Current mode remains SSI live API plus backend cache/TTL.
* SSI IntradayOhlc is implemented for compact dashboard/company pulse, but live availability still depends on SSI endpoint permission and response shape. If unavailable, show the SSI intraday state without fallback.
* SSI IntradayOhlc live rows may be stale relative to SSI DailyOhlc or have a different cadence than the requested dashboard timeframe. Keep daily rows OK, mark stale intraday unavailable, and surface the sanitized date/granularity diagnostics.
* Optional live status blocks now carry a broad `status` plus safe `reason_code`/`classification` fields. Intraday reasons distinguish cadence mismatch, date mismatch, no usable rows, rate limit, provider error, disabled, and unknown states without changing DailyOhlc ownership.
* SSI realtime snapshot and trade-tape contracts are wired through the existing realtime endpoints and dashboard/company UI blocks. Realtime now has a disabled-by-default background manager/cache skeleton; live official-client streaming, entitlements, and row shapes still require validation. Unavailable results should remain neutral SSI unavailable states with specific reasons such as `config_disabled`, `not_started`, `bootstrap_symbols_empty`, `ticker_not_bootstrapped`, `running_idle`, `cache_empty`, `cache_stale`, `connection_error`, `auth_or_entitlement_failure`, `network_or_tls_failure`, `rate_limited`, or `unknown`.
* SSI realtime diagnostics should distinguish streaming disabled, manager not started, cache empty, cache stale, cache hit, manager error, live adapter not enabled, and running-idle state. Do not print or return tokens, credentials, auth headers, signed URLs, or raw provider bodies. A running-idle or cache-empty realtime state means the event-driven stream has no usable cached tick for the ticker; it is not evidence that DailyOhlc or DailyStockPrice failed.
* Observability keeps `mozyfin` as a minimal disabled legacy block. Generic VN request/cache/single-flight counters live under `dashboard_runtime`; do not interpret those counters as Mozyfin activity. SSI status is split into explicit `ssi_core`, `ssi_intraday`, `ssi_realtime`, and `ssi_trade_tape` blocks.
* VN news/social is disabled because Mozyfin free-tier API access is no longer available for the dashboard. Future news should use a separate NewsProvider contract, not Mozyfin scraping.
* Strict VN runtime must not construct `MozyfinFetcher` for watchlist, company, realtime, index, corporate-action, or observability paths while Mozyfin legacy flags are disabled. Corporate actions remain explicit unavailable placeholders until a verified external event provider is configured.
* News rendering is independent from SSI index, quote, metadata, finality, intraday, and realtime caveats. If a future NewsProvider supplies rows, the selected ticker news block should remain visible and clearly separate from SSI market data.
* Keep DailyOhlc and DailyStockPrice labels separate: daily close/chart candles come from SSI DailyOhlc; reference/limits/foreign/matched/put-through fields come from SSI DailyStockPrice.
* Keep primary cache labels scoped to SSI DailyOhlc. Quote/news/intraday/realtime cache or availability issues should remain in diagnostics or caveats so they do not imply official daily market data is unavailable.
* Latest smoke found a same-date FPT mismatch on `2026-06-22`: SSI DailyOhlc/dashboard close fields were `70,700`, while SSI DailyStockPrice close/adjusted close were `70,800`; DailyOhlc volume was `3,642,400`, while DailyStockPrice matched volume was `3,643,500`. Keep SSI DailyOhlc as canonical `latest_price` until canonical source and final/provisional semantics are explicitly designed.
* Trade-tape public data remains `trade_tape=[]` unless a verified REST list/history source returns rows. `X-TRADE` streaming messages are latest-trade snapshot context only and must not be treated as historical tape rows.
* Realtime and trade-tape unavailable messages should be short and user-safe. Streaming manager/cache state and sanitized provider error summaries should move to diagnostics. When historical trade tape is unavailable but only `X-TRADE` latest-trade stream context is proven, classify the public trade-tape state as `latest_trade_stream_only` instead of implying a working historical time-and-sales feed.
* REST realtime candidate probing is disabled; do not reintroduce repeated speculative realtime endpoint probes.

## Current limitations

* SSI FastConnect credentials are not bundled; with default placeholder config, SSI-owned sections are unavailable.
* Mozyfin is disabled for VN dashboard runtime; news/social returns disabled or `not_implemented`.
* SSI realtime snapshot and trade tape remain separate from daily close and intraday candles.
* KBS is disabled by default and legacy-only behind explicit development flags.
* Local DB market-data storage is deferred while current call volume remains low and backend cache/TTL is sufficient.
* No UI source switcher or comparison card exists.
* No provider comparison endpoint exists in this strict-default phase.
* SSI streaming/protocol hardening remains a later phase; this phase wires the dashboard contract, disabled background manager/cache skeleton, and safe unavailable states.
* Exact VN30 IndexComponents rows are live-verified through `indexCode=VN30`; any missing, mismatched, empty, or provider-failed component response still returns `rows=[]`.
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
