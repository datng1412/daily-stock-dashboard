# SSI FastConnect Integration

## Current production contract

SSI FastConnect V3 is the sole production SSI REST and streaming
implementation. The active runtime uses `ssi-sdk==3.0.5`; V2 packages,
consumer credentials, base URLs, selectors, and fallback paths are migration
history only and are not active configuration.

Completed Foreign Flow is mature: accepted DailyStockPrice history, durable
restart restoration, current/completed merge rules, anomaly quarantine,
rankings, coverage, analytics, and deterministic frontend states are
implemented. Current Foreign Flow is `PRODUCTION_READY`: bounded active-session
evidence now covers official `ForeignRoomMessage` publication through the
process-shared manager, symbol current route, current-VN30/current-Industry
aggregation, FastAPI, and a real desktop/mobile browser. Current values remain
provisional and non-persistent; stale transport state retains last-known values
with an explicit stale/disconnected status.

VN-BREADTH-1 reuses the sole V3 provider through exact current
IndexComponents membership and a minimal 55-row DailyOhlc history reader. The
reader keeps the existing process cache/single-flight behavior, adds a
purpose-specific cache key, requests a bounded 120-calendar-day window, and
fans out with at most four workers. No V2, fallback provider, full watchlist
hydration, MI breadth, or foreign-flow substitution is involved. The bounded
2026-08-11 positive acceptance resolved exactly 30 normalized unique members
and 30 aligned DailyOhlc histories for completed provider session 2026-08-10.
The API reconciled 24 advances, 4 declines, 2 unchanged, 25/30 above MA20,
15/30 above MA50, and 93.33% participation with no missing or mismatched
symbols. Cold HTTP/service latency was 12.59/12.58 seconds with 30 provider
calls and maximum concurrency four; the immediate warm request was 0.52/0.51
seconds with 30 cache hits and zero provider calls. Real desktop/mobile browser
acceptance used one page-owned request and one manual refresh, retained values
during refresh, and showed no breadth console error, horizontal overflow, or
fallback.

## VN-FF-LIVE-1 acceptance boundary

`VN-FF-LIVE-1 — Current Foreign Flow Production Acceptance` was accepted on
2026-08-10. Its proven chain is:

`ForeignRoomMessage` -> process-shared stream manager -> symbol current -> VN30
current aggregate -> Industry current aggregate -> FastAPI routes -> real
browser/runtime.

A bounded two-symbol diagnostic authenticated, subscribed one provider cohort,
and received provider-dated FPT and SSI room messages with all raw
`bq/sq/bv/sv` aliases present before typed normalization. Application runtime
evidence retained provider/receipt times, returned usable symbol current data,
classified all 30 current SSI IndexComponents members, reconciled the VN30
aggregate and 13 Industry groups, and advanced aggregate values after a newer
provider observation without summing cumulative snapshots. Repeated reads and
manual refresh reused the lifecycle-owned manager/subscriptions. The browser
retained provisional current data and completed history across refresh at
desktop/mobile widths without overflow or console errors. Current snapshots
were not written into accepted completed history.

The 11:10-11:18 Vietnam-time repeat observed SSI progression from 11:10 to
11:11, including equal cumulative SSI counters at the newer timestamp and a
fresh FPT snapshot. The owned application classified 30/30 members, reconciled
13 Industry groups, and progressed aggregate values between observations. Its
cold health readiness took 36.2 seconds; the manual acceptance harness now
allows 45 bounded seconds before classifying readiness failure. This changes
diagnostic timing only, not FastAPI startup or provider semantics.

The maintained raw diagnostic now accepts the observed SSI provider timestamp
shape `YYYY/MM/DD HH:MM:SS`; this is diagnostic evidence handling only and does
not change production parsing or data semantics. Docker pins `ssi-sdk==3.0.5`.
The process-local stream/cache contract requires one backend worker for coherent
current state. Render deployment was not directly observed in this acceptance.
Do not extend the R6A-R6E naming sequence unless a concrete regression needs a
historical reference.

## M2.6B-R6E historical anomaly repair and Industry current runtime

An all-constituent explicit-zero VN30 session now triggers a bounded exact-date
DailyStockPrice verification using the shared V3 REST provider, at most four
concurrent symbol calls, one single-flight owner per session, a one-hour
cooldown, and one manual refresh bypass per cooldown episode. Raw aliases are
classified before typed defaults. Stronger same-date evidence is monotonic:
an exact-date nonzero or durably accepted complete row cannot be overwritten by
a broad-range zero or partial row. Successful corrections persist atomically
and invalidate only affected symbol/VN30 caches.

If exact-date symbol calls still return explicit zero, missing rows, null
fields, or errors, the session remains an unresolved provider anomaly. Public
aggregate numbers are null and it is excluded from complete windows, rankings,
analytics, charts, and numeric CSV cells. `securitiesSummary?index=VN30` was
also inspected but does not provide a proven symbol-level historical repair
contract; index summaries, room capacity, and unretained streaming snapshots
are not reinterpreted.

Industry detail now accepts usable `ready`, `partial`, `stale`, and
`market_closed` current aggregates and reads the canonical `aggregate`; current
`groups` remain ranking data. Only a complete, non-anomalous accepted same-date
row suppresses current. An incomplete/anomalous shell does not, and the display
still emits exactly one row per session date.

Deterministic acceptance passes 73 focused backend and 69 focused frontend
tests, compile/TypeScript/ESLint/Vite, the 3,405-test backend tree with the
unchanged 69-failure/4-skip baseline, and 14 system-Chrome fixtures at desktop
and mobile sizes. A bounded application smoke reached health but current
Industry remained typed `unavailable`/`network_error` while streaming
subscription restoration reported authorization failures under bounded
backoff. Fresh live Industry publication therefore remains pending.

## M2.6B-R6D missing-field and capability integrity

DailyStockPrice foreign fields are read from the authenticated raw V3 REST
mapping before any typed SDK default can be mistaken for provider data.
`FIELD_ABSENT`, `FIELD_NULL`, `PARSE_FAILURE`, and
`PROVIDER_ROW_MISSING` force the corresponding normalized gross field to
`null`; net is available only from a valid gross pair. Explicit provider zero
remains numeric zero. Accepted incomplete dates remain visible and durable with
`data_quality=incomplete`, `complete=false`, and `missing_foreign_fields`, but
complete-only calculations omit them.

The installed/current SSI integration does not prove securities-company
own-account buy/sell value or volume fields. The Proprietary capability is
therefore `unsupported`, performs no provider operation, returns no rows, and
offers no chart or CSV. SSI `indexSummary` remains available only for its
legitimate index-market purpose and is not a proprietary-flow source.

Current Industry groups and the canonical current-VN30 aggregate are derived
once from the same process-owned `ForeignRoomMessage` symbol snapshots. Groups
remain available for rankings; the detail series uses the canonical aggregate
with the provider session date and `current_session_provisional` finality.
Accepted DailyStockPrice retains same-date precedence. No current Industry
aggregate is persisted.

R6D deterministic validation passed 126 focused backend and 65 focused
frontend tests. Python compile, TypeScript, ESLint, and the Vite production
build passed. The full backend tree reported 3,326 passes with the established
69 failures and four skips. System Chrome accepted all 13 required fixtures at
1366x768 and 390x844 (26 assertions) in 40.971 seconds with no horizontal
overflow or owned process, temporary artifact, or port leak. Validation
finished after the active Vietnam provider session, so a fresh live Industry
replacement message remains pending.

## M2.6B-R6C idle authentication recovery

The first collapse occurred after the five-minute current VN30 universe cache
expired: an SSI membership authentication failure returned before retained
stream snapshots or durable accepted DailyStockPrice history were read. The
completed VN30 service had the same membership-first boundary. A separate REST
adapter defect retained an authenticated client after an operation-level 401/
403, so subsequent calls could reuse a poisoned client.

R6C adds one process-local last-known-good SSI IndexComponents membership cache
shared by the completed and current aggregate services. Failed, empty, or
malformed refreshes keep the validated cohort with explicit retained/age/
failure diagnostics. Durable accepted history and process-owned current
snapshots remain eligible; a cold process with no validated cohort remains
truthfully unavailable.

The shared V3 REST adapter now invalidates its client after retryable
authentication failure and exposes one single-flight, cooldown-bound bypass per
failure generation. Route touches do not bypass the cooldown. Visibility resume
and manual refresh request the bounded recovery but do not authenticate,
connect, subscribe, or own streaming transport from the request handler.
Explicit provider entitlement rejection remains non-retryable. No provisional
snapshot or aggregate is persisted.

Deterministic validation passed 173 focused backend tests and 123 affected
frontend tests. System Chrome accepted 14 idle/recovery fixtures at 1366x768
and 390x844 (28 assertions) in 56.879 seconds with no horizontal overflow or
owned process/port leak. The full backend tree retained the known 69 failures
and four skips, with 3,324 passes. No live request was made after the active
Vietnam provider window, so fresh replacement publication remains pending.

## M2.6B-R6B finality propagation and diagnostics

The current aggregate API was already preserving provider-backed session date,
`current_session_provisional`, `data_state`, values, and coverage. The loss
occurred after the frontend merged the rows: session aggregation retained only
numeric values and inferred `Đủ` from complete fields. The shared display model
now retains source/finality, current and provider state, stale/partial flags,
coverage counts, and provider/receipt timestamps. A 30/30 complete current row
therefore remains provisional and renders `Mất kết nối` when stale.

Current Industry diagnostics are derived from the same aggregate as
`ready`, `partial`, `stale`, `waiting`, or `unavailable`. They disclose the
provider session, finality, state, `index:VN30` universe, requested/classified/
observed/complete/stale/missing counts, and group count. This does not claim
full-HOSE industry coverage. No provider request, stream connection,
subscription, aggregation math, accepted-history persistence, or Proprietary
semantics changed.

System Chrome accepted 16 R6B fixtures at 1366x768 and 390x844 in
45.776 seconds, including connected/stale/post-close current rows, full and
partial coverage, accepted same-date precedence, completed-only fallback,
Industry capability states, long history, explicit zero, and missing values.
No already-running local backend was available for the permitted bounded live
check, so a fresh provider replacement message remains unverified.

## M2.6B-R6A durable-history and acceptance result

Completed DailyStockPrice foreign-flow preservation now survives application
restart through `DATA_CACHE_DIR/vietnam_foreign_flow_accepted.v1.json` (default
repository-ignored `data/cache/`). Startup validates schema version, provider,
endpoint, scope, per-symbol dates, numeric/null fields, accepted
source/finality, and bounded size before rehydrating memory. Invalid/corrupt
files are ignored without blocking startup. Writes flush a same-directory
temporary file before atomic replacement; a failed replacement leaves the
previous valid file intact. Only accepted completed rows are persisted.
`ForeignRoomMessage` and current aggregates remain process-owned provisional
state.

System Chrome 150.0.7871.187 was launched by repository-local Playwright through
an explicit executable path. The 18-fixture desktop/mobile matrix completed in
48.631 seconds, Vite became ready in 735 ms, no page-level overflow was found,
and the owned browser/Vite trees, temporary logs, and dynamic port were cleaned.
No browser package was installed or downloaded.

One bounded room-only diagnostic was started during the 2026-07-30 active
morning window. Its final tool output was truncated and no sanitized evidence
file was produced; the process exited and was not retried. Therefore this phase
does not claim authentication, room publication, current VN30 aggregation,
current industry aggregation, current watchlist aggregation, or duplicate-
connection acceptance. Those live checks remain pending.

## M2.4C-R3 foreign-flow connectivity result

One bounded, secret-safe run on 2026-07-27 separated the provider layers without
printing credentials, tokens, headers, or raw responses:

- The configured V3 REST host is `https://api.ssi.com.vn` with `/api/v3`
  endpoint paths. DNS returned IPv4, TCP/443 connected, and the default Python
  trust path verified a TLS 1.3 certificate. No proxy or custom CA environment
  variable was active.
- V3 authentication succeeded with the configured API key/secret; Client ID
  remained empty and optional. Exact FPT metadata returned one row, FPT
  DailyStockPrice returned 20 completed-session rows through 2026-07-24, SSI
  VN30 membership returned 30 rows, and direct VN30 securities summary returned
  20 rows through 2026-07-24.
- The single `indexSummary` diagnostic request targeted Sunday 2026-07-26 and
  normalized as `malformed_response` with no usable row. It was not retried.
  The maintained diagnostic now chooses the latest completed weekday for future
  runs; this is a diagnostic correction, not evidence that proprietary data
  recovered.
- The earlier generic local `network_error` is not reproducible in the approved
  network context and is not evidence of a repository base-URL, credential,
  proxy, TLS, auth, or shared-client defect. REST remains independent from the
  unprobed streaming host.

Use `python scripts/diagnose_vn_foreign_flow_connectivity.py --live` only as a
single bounded operational check. It uses zero SDK retries, one authentication
lifecycle, and at most one request per documented capability.

A separate direct-process application smoke reached lifespan completion,
Uvicorn socket readiness, and an internal `/api/health` HTTP 200 in about four
seconds. The parent smoke harness nevertheless failed to observe readiness
before 45 seconds, terminated its exact child tree, and verified port release.
It made no Foreign Flow route calls, so no application-route recovery is
claimed from that run.

## M2.4C watchlist foreign-flow screener

The screener adds `GET /api/v1/stocks/vn/foreign-flow/watchlist` on top of the existing V3 DailyStockPrice symbol-history service. One request accepts 1–30 normalized unique tickers and returns both value and volume families for 1/5/20/60 completed sessions. The frontend requests 60 sessions once; presentation changes do not refetch.

The service reuses the process-local raw-history cache and coalescing path. Watchlist concurrency is capped at four, per-ticker classification is bounded to 20 seconds, total response time is bounded to 45 seconds, and output order follows normalized input order. One timeout or provider failure yields an unavailable item while completed symbols remain usable. Authentication/authorization/provider failures are not labelled unsupported, and no error detail, credential, or raw provider payload enters the response.

This phase does not enable current-session foreign flow, infer room-stream deltas, add another provider, alter DailyOhlc price ownership, or automatically load a fixed ticker/VN30 list.

## M2.4 Vietnam product mapping and Explorer contract

Company profile metadata is read through the exact-symbol V3 `securitiesByBoard?symbol=` adapter contract. Only returned name, board/exchange, ICB, lot-size, listing-date, and listed-share fields are eligible; unsupported security type, issuer, description, estimates, financials, and events are not inferred. The public profile includes provider endpoint/version, fetched time, cache status, data state, and sanitized failure class.

Company order book is the optional SSI X-QUOTE snapshot already normalized by the streaming layer. Bid prices/quantities remain paired independently from ask prices/quantities, sparse levels stay null, and the company service passes the snapshot through without merging it with a different daily quote. Canonical daily price labels follow the market service's actual SSI source selection.

Compact intraday normalization sorts chronologically and never fills gaps. Provider event/sequence IDs are the preferred deduplication key; without one, only an identical timestamp plus complete OHLCV tuple is collapsed. Equal-time rows with different provider values remain. Non-positive OHLC, negative volume, malformed time, previous-session/current-session classification, provider-session time, and cache read time retain separate handling.

Foreign Flow Explorer v1 reuses the existing V3 completed-session contracts:

- ticker history from `daily_stock_price`;
- current-membership VN30 decomposition from SSI IndexComponents plus symbol histories;
- current-VN30 ICB aggregation and turnover from the bounded industry service;
- historical proprietary VNINDEX/VN30/HOSE exploration through `indexSummary`;
  this interpretation was later superseded and removed because the current SSI
  contract does not prove securities-company proprietary buy/sell fields.

The UI selects the latest 1, 5, 20, or 60 distinct returned provider sessions, or an inclusive custom range bounded to 120 calendar days. It does not divide by calendar days or convert missing values to zero. Source session, fetched time, cache state/age, source freshness, coverage, and anomaly state are displayed separately. Force refresh is scoped to the active capability; value/volume changes reuse the loaded payload. CSV export uses only the selected loaded rows and raw numbers. Direct VN30 unsupported remains secondary, `historical_constituent_correct=false`, and current-session foreign/industry flow remains unavailable pending independent semantics proof.

## V3 foreign-session and auction integrity

DailyStockPrice keeps its actual `data_date` and adds `requested_date`, `provider_session_date`, `freshness_status`, current/provisional/completed/stale flags, provider-session lag, provider version, and endpoint provenance. A prior completed-session row during active trading is valid historical provider data but is `partial`, not current or live. Outside active trading, the newest provider-backed completed row may be `latest_completed_session`; older returned-session history remains explicitly stale.

The retained V3 stream maps `trade.*` to realtime/X-TRADE only when symbol and provider timestamp are valid and price and executed volume are finite and positive. Zero/empty ATO or ATC callbacks are classified as auction no-match/control evidence and counted without entering caches. A connected stream can therefore be transport-healthy and parser-healthy while symbol data is `auction_waiting_for_match`. Valid auction executions, including nullable-side executions, are retained. Provider sequence/id is the only safe replay key; equal unsequenced executions are not collapsed.

Persisted streaming schema version 2 validates the same eligibility rules during write and restore, so incompatible zero rows from version 1 cannot return as live data. Current response session and event session are separate; old events keep their provider timestamp and event-session provenance.

At M2.3, current-session foreign-flow capability remained unproven beyond a same-date `securitiesSummary` row and the retained V3 WebSocket enabled only trade and quote topics. M2.5 supersedes that narrow topic set by restoring bounded room observation, while still prohibiting total-market-trade inference, forward-fill, V2, external providers, and fallback.

## V3 daily-history completeness and freshness

V3 daily OHLC is normalized from `securitiesSummary`. Long requests are retrieved through bounded recent-first date windows and all declared pages are exhausted. Rows are deduplicated by trading date, sorted ascending, and trimmed to the newest requested sessions. No session is synthesized or forward-filled.

Daily history marked complete exposes sanitized diagnostics including `requested_from`, `requested_to`, `page_count`, provider/normalized row counts, `min_date`, `max_date`, `latest_completed_session`, `freshness_status`, `cache_hit`, and `cache_source`. An incomplete or materially stale response is not a successful cache replacement, is not canonical when a newer SSI DailyStockPrice row exists, and does not feed technical indicators.

The retained V3 intraday service request uses the supported `interval=1m`; requested dashboard cadence remains separate and is compared with observed provider cadence.

## SSI-V3-M1-R2 production status (2026-07-23)

SSI FastConnect V3 is now the sole production REST and realtime implementation. Production uses `ssi-sdk==3.0.5`; the V2 `ssi-fc-data` package, V2 fetcher/adapter/stream wrapper, Consumer ID/Secret configuration, global REST selector, fallback paths, and obsolete V2 diagnostics/tests are removed.

FastAPI startup remains provider-lazy and non-blocking. Missing V3 configuration returns explicit unavailable provider states without blocking `/api/health`. Required REST variables are `SSI_V3_REST_ENABLED=true`, `SSI_V3_API_KEY`, and `SSI_V3_API_SECRET`; `SSI_V3_CLIENT_ID` is optional. Streaming is separately opt-in and uses a bounded bootstrap list.

The final Python 3.11 image passed repeated credential-free bind/health/shutdown tests and a bounded credential-at-runtime V3 request. The retained V3 manager owns one connection, heartbeat, reconnect/backoff, resubscription, generation safety, bounded deduplication, TTL caches, stale/after-hours states, and idempotent shutdown. A release rollback must restore the prior V2-only image; hybrid V2/V3 runtime and automatic fallback remain forbidden.

All V2-specific sections and commands below this production status are historical evidence unless they explicitly describe the current V3 adapter. Deleted V2 diagnostic scripts must not be used as current runbook commands.

## Historical: SSI-V3-M1-R1 operational status (2026-07-23)

The V3 opt-in now has complete retained REST and streaming implementations: raw `securitiesSummary` daily/foreign fields, matched-trading daily candles, exact metadata, current/completed one-minute OHLC, index identity/membership/latest summary, and one-connection `trade.*`/`quote.*` streaming. V3 startup is background/non-blocking; the stream adapter owns the connection heartbeat, while the shared manager owns reconnect/backoff, resubscription, generation rejection, thread-safe TTL caches, snapshot persistence boundaries, and idempotent shutdown. No token or raw provider row is persisted.

R1 validated StockClock operational foreign-value scales separately: HOSE `1`, HNX `1,000`, and UPCOM `1,000`. Across FPT/SSI/VCB/SHS/ACV, every eligible foreign buy/sell row was price-range-plausible at its accepted scale and no competing named scale passed. Two reads of each 20-session range were stable, with no duplicate dates or incomplete gross pairs.

Current-date and latest completed provider-session rows are provisional. Older returned sessions are completed-history candidates after repeated-read stability. The rank is based on distinct returned trading dates, not weekdays, so weekends and holidays do not advance finality. SSI does not expose a revision identifier or final flag; `foreign_provider_finality_guaranteed` therefore remains false.

Production is V3-only after SSI-V3-M1-R2; no V2 selector or automatic fallback
remains. SSI-V3-M2 additionally removed guessed exchange/index facts, generated
provider event timestamps, null-to-zero summaries, bundled VN30 membership, and
legacy Mozyfin fixture activation. Exact-symbol V3 metadata owns board identity;
fetch/receipt time remains separate from provider event time; missing values
remain null/empty. See `docs/SSI_FASTCONNECT_V3_MIGRATION.md` for migration
history and `docs/SSI_V3_DATA_AUTHENTICITY_AUDIT.md` for the authenticity trace.

## Historical integration scope

This scope records the earlier transition foundation. Current production is
the V3-only contract at the top of this document; V2 endpoint names and package
references below are retained only as migration history.

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
* A separate completed-session chart path calls `IntradayOhlc` once with `symbol`, equal `fromDate`/`toDate`, `pageIndex=1`, `pageSize=1000`, `ascending=true`, and `resolution=1`. It does not reuse the compact pulse request variants or cache.

### Completed-session 1m cache and normalization

Phase 4.11C uses a separate process-local LRU capped at 500 entries. Successful and provider-confirmed empty dates cache for 86,400 seconds; unavailable results cache for 60 seconds; usable history may recover stale for at most seven days without being overwritten by an unavailable refresh. Provider dates/times are parsed strictly in `Asia/Ho_Chi_Minh`; duplicate minute buckets keep the latest raw timestamp and then last stable occurrence. Gaps are never filled. The path supports completed dates only and does not add current-session bars, higher intervals, aggregation, page 2, DailyOhlc substitution, streaming candles, or fallback providers.
* SSI realtime snapshot and trade-tape contracts for dashboard/company realtime blocks.
* SSI realtime REST endpoint discovery concluded that no supported FastConnect realtime snapshot endpoint is identified in this repository.
* SSI streaming realtime parser coverage for buffered `X`, `X-QUOTE`, `X-TRADE`, `F`, `R`, and `MI` messages.
* Config-disabled SSI streaming manager/cache skeleton for future background runtime work.
* Official `ssi-sdk==3.0.5` V3 REST/WebSocket adapter with lazy initialization.
* FastAPI startup bootstrap for SSI streaming realtime when explicitly enabled and given a small bootstrap symbol list.
* Realtime endpoint response-cache bypass and frontend quote polling tuned for the process-local streaming cache.
* Docker/Render install only the official V3 `ssi-sdk==3.0.5`; `ssi-fc-data` is not part of the production image.
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

## Historical/superseded FastConnect V3 migration gates

The migration-gate entries below record decisions before the V3-only cutover.
They do not describe current provider selection or current configuration.

Phase SSI-V3-A1 is audit-only. The SSI customer notice supplied to this project records V2 maintenance through 30/06/2027 and official V3 replacement from 01/07/2027. It does not change V2 runtime, configuration, traffic, or source ownership. The official V3 Python candidate (`ssi-sdk` / `ssi_sdk`) and V3 REST/WebSocket contracts are documented. One authorized auth sequence mapped the current V2 identifier/secret values to V3 raw `apiKey`/`apiSecret`; V3 returned HTTP 401, with no token, retry, data call, stream, or file request. The current decision is **D — existing credentials rejected by V3 for that exact mapping**. SSI must confirm V3 account activation and `client_id`/API-key mapping before another bounded attempt. See `docs/SSI_FASTCONNECT_V3_MIGRATION.md` for the complete change-impact matrix and exit criteria.

Phase SSI-V3-CONTRACT-DIFF adds a documentation-only URL/parameter table to that migration document. It confirms that all compared URLs change, while REST methods remain POST for auth and GET for market data. Important name changes are `market`/`exchange` → `board`, `fromDate`/`toDate` → `from`/`to`, `indexId`/`indexCode` → `index`, and IntradayOhlc `resolution` → common V3 OHLC `timeFrame`. V3 retains `pageIndex`/`pageSize` only for summary/OHLC candidates, with a documented default size of 10 rather than the V2 model's 100. This comparison makes no credential, entitlement, unit, finality, runtime, or data-parity claim.

Phase SSI-V3-B2 adds the pinned official `ssi-sdk==3.0.5` and a disabled-by-default synchronous V3 REST adapter for securities by board/symbol/index, daily OHLC, completed historical 1-minute OHLC, index list, and index summary. The adapter imports and authenticates lazily, shares one lock-protected `Auth`/`Data` lifecycle, stores no token, closes idempotently, and uses one-based bounded pagination (page size 1,000; 20 pages; 5,000 rows). Missing/empty/`v2` still selects V2. Explicit `v3` requires the enable flag plus dedicated V3 API key and secret; Client ID is optional for Market Data REST. Supported capabilities then select V3, while DailyStockPrice/foreign flow, extended SecuritiesDetails, current-session intraday, production IndexComponents, and realtime remain explicitly V2-owned. V3 errors never fall back to V2. B2 used deterministic fakes only: no V3 credential was tested, no live call or shadow traffic ran, and no public API/frontend/startup behavior changed. The complete contract and parity matrix are in `docs/SSI_FASTCONNECT_V3_MIGRATION.md`.

Phase SSI-V3-B3 adds offline-only V3 `securitiesSummary` normalization through the existing lazy lifecycle and the SDK's public authenticated REST transport. This path is necessary because the pinned high-level SDK model omits the official four gross foreign fields and does not expose summary pagination. Symbol history and same-shape index normalization preserve null versus explicit zero, parse integral counts without float rounding, derive net volume/value independently only from complete gross pairs, and apply no scaling. Units, daily finality, credentials, entitlement, and live V2/V3 parity remain unverified. Production DailyStockPrice, all foreign-flow APIs/history/analytics/VN30 inputs, and caches remain V2-owned; the V3 summary path is `implemented_disabled`, with no fallback, shadow traffic, live request, public API, frontend, startup, or realtime change.

Phase SSI-V3-B3.1 aligns REST authentication with the official Market Data token contract: API key and secret are required, while Client ID is optional; private key and OTP remain unused. The installed SDK confirms this exact request construction. A new guarded diagnostic defaults to zero network and permits only one authentication lifecycle plus four bounded FPT/HOSE operations when `--live`, `SSI_FASTCONNECT_REST_VERSION=v3`, and `SSI_V3_LIVE_ACCEPTANCE_ENABLED=true` are present. On 2026-07-22 the selector remained V2 and the environment guard was disabled, so outcome G/NOT_RUN recorded zero authentication and zero data calls. A Client ID was present by configuration, so no empty-Client-ID live proof occurred. V2 production ownership and all no-fallback boundaries remain unchanged.

## Provider roles

SSI FastConnect V3 is the current sole production SSI market-data provider for:

* Daily OHLCV.
* Daily stock price.
* Reference, ceiling, and floor.
* Foreign flow.
* Daily index.
* Index components.
* Symbol metadata.
* Intraday OHLCV.
* Realtime streaming later.

Mozyfin is disabled for VN dashboard runtime. It must not be used for VN news/social, OHLCV, chart, reference, foreign-flow, index, metadata, intraday, or fallback behavior. VN news is disabled by default; optional local/personal `vnstock_news_personal` and `vnstock_community` implementations exist under separate terms and enablement gates and are not universal hosted production providers.

KBS is disabled by default and retained only as an explicit legacy development provider:

* `VN_ALLOW_LEGACY_KBS_PROVIDER=true`
* `KBS_ENABLED=true`

KBS must not be used as silent fallback for SSI realtime snapshot, SSI trade tape, or any SSI-owned market-data field.

SSI is now the strict owner for supported VN REST market data. If SSI is disabled, credentials are missing, or a request fails, SSI-owned sections return an unavailable state instead of falling back to Mozyfin or KBS.

External providers are still required for BCTC/KQKD, financial statements, financial ratios, corporate action event lists, dividends, rights, splits, and macro context such as Fed, oil, USD, and gold. These domains are outside current SSI REST market-data ownership.

## Historical provider capability matrix

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
| DailyStockPrice | SSI FastConnect Data REST | Implemented and wired | Use for reference, ceiling/floor, adjusted close, matched, put-through, latest foreign flow, bounded watchlist 5D/20D net volume, and the Phase 4.12B one-symbol 5/20/60-session history API |
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

## Historical endpoint/source mapping

The table below preserves older endpoint-oriented discovery and product-source
notes. Its V2 `/Market/...` paths are not active configuration. Current calls
are routed only through `SsiRestProviderRouter` to the V3 adapter; current
canonical-price selection follows `docs/VN_DATA_CONTRACT.md`.

| Feature | SSI source/endpoint | Current status | Notes |
| --- | --- | --- | --- |
| DailyOhlc | V3 `securitiesSummary` daily-history normalization | OK | Owns chart candles, daily OHLCV, and technical inputs. Its close is the normal `latest_price` fallback, but the current service may select a newer dated DailyStockPrice close when this history is materially stale or a reliable normalized quote when available. |
| DailyStockPrice | V3 `securitiesSummary` daily-summary normalization | OK | Owns reference, ceiling/floor, matched/put-through, adjusted close if provided, latest foreign-flow fields, and bounded latest-available 5D/20D foreign net volume indicators. Its dated usable close becomes `latest_price` only when DailyOhlc is materially stale; this does not synthesize OHLCV or technical inputs. |
| IndexList | `GET /Market/IndexList` | OK | Use SSI-returned index codes instead of hardcoded assumptions. |
| DailyIndex | `GET /Market/DailyIndex` | Partial: `indexID=VN30` returns rows, while exact `VNINDEX` remains unresolved and non-positive or missing index levels are null | Requires exact IndexList resolution and returns no placeholder row when SSI has no usable data. Phase 4.5C live API smoke returned a VN30 row dated 2026-06-29 but the public row still lacked a usable `index_value` and `exchange`. |
| IndexComponents | `GET /Market/IndexComponents` | Usable for exact VN30 nested rows; unavailable cases remain `rows=[]` | Phase 4.4B proved `indexCode=VN30` returns an exact VN30 outer row with 30 nested members. Phase 4.5C live API smoke re-confirmed 30 VN30 component rows. Missing identifiers, mismatched outer rows, empty nested lists, or provider failures remain unavailable without hardcoded members. |
| IntradayOhlc | `GET /Market/IntradayOhlc` | Contract exists; returned rows may be stale/mismatched or provider-throttled | Freshness must be validated against SSI DailyOhlc date before rendering intraday metrics; failures expose only sanitized diagnostics. |
| Realtime snapshot | SSI FastConnect streaming data type `X` | Parser covered; config-disabled manager/cache skeleton exists; official client adapter is config-gated; FastAPI startup bootstrap is config-gated and symbol-list gated | Phase 4.0C verified the route/service/fetcher wiring and config gate. Phase 4.0C-2 found no supported SSI REST realtime endpoint, SDK method, enum, or hidden repo contract. Phase 4.0C-3 confirmed the realtime direction is streaming. Phase 4.0C-5 added a request-safe cache read path that stays disabled by default. Phase 4.0C-6 added a lazy official-client adapter. Phase 4.0C-7E changed the default channel to the live-verified no-space form `X:{symbol}`; spaced forms are retained only for diagnostics/custom overrides. Phase 4.0C-8 added FastAPI lifecycle bootstrap that starts the process-local manager only when `SSI_STREAMING_REALTIME_ENABLED=true` and explicit bootstrap symbols are configured. Phase 4.0C-9 makes the realtime endpoint bypass the generic backend response cache so fresh process-local stream-cache rows can surface immediately. Previous candidate names `RealtimeQuote`, `RealtimePrice`, `RealtimeSnapshot`, and `SecuritiesRealtime` are discovery evidence only and are no longer probed at runtime. The dashboard must not claim realtime is live unless `realtime_snapshot` is non-null and `realtime_status.status = ok`. |
| Order book | SSI streaming `X-QUOTE:{symbol}` latest ladder cache | Phase 4.8H adds backend/API watchlist fields `order_book_source`, `order_book`, and `order_book_status`, with technical details under `diagnostics.order_book` | Request handlers only read the process-local cache. Parsed levels require positive price and non-negative volume. Stale usable ladders remain visible with stale status/age diagnostics; empty/malformed books return explicit unavailable state. No fake rows or `latest_price` substitution. |
| Trade tape | SSI streaming `X-TRADE` event buffer; future verified REST/history contract if SSI documents one | Phase 4.7C adds a bounded process-local per-symbol X-TRADE buffer populated only by the background streaming manager. Phase 4.8E subscribes the startup-owned manager to `X-TRADE:{symbol}` alongside `X:{symbol}` when trade tape is enabled. Phase 4.8E-2 returns buffered rows even when stream freshness is stale. Phase 4.8E-3 normalizes explicit X-TRADE side/aggressor fields to `buy`/`sell`/null and adds reference-based `change`/`change_pct`. Phase 4.8E-4 maps observed raw SSI side codes `BU=buy` and `SD=sell` while preserving `side_if_available`. Watchlist/company unavailable rows remain `trade_tape=[]` plus separate `trade_tape_status` only when no usable rows exist. | Returns rows only for configured/bootstrap symbols with parsed X-TRADE events carrying price, volume, and timestamp. Request handlers only read the buffer and never start streams, subscribe dynamically, or probe previous REST candidates. B/S must not be inferred from price color or change. Historical time-and-sales history remains unverified. |
| Securities/SecuritiesDetails | `GET /Market/Securities`, `GET /Market/SecuritiesDetails` | Partial metadata | Optional company name, issuer, security type, lot size, listed shares, and listed date may remain null. |
| SSI remaining data audit | `docs/SSI_REMAINING_DATA_AUDIT.md` | Docs-only Phase 4.8F audit | Recommended runtime-proof order: `F` trading session/status, `X-QUOTE` order book, `R` foreign room, `MI` realtime market index, DailyStockPrice unused fields, SecuritiesDetails extended metadata, then `B` bars and instrument modules. |
| News | Not SSI | Disabled by default; optional local/personal providers exist | `vnstock_news_personal` and `vnstock_community` use separate enablement/terms boundaries. Mozyfin is not used for VN runtime news. |
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

## Phase 4.11B / 4.11B-3 Historical Intraday Contract Audit

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

Phase 4.11B-2 diagnosed the earlier `network_error` as the local sandbox denying the provider socket: an approved credential-free check resolved DNS and completed TLS 1.3 successfully. It established that SSI requires `DD/MM/YYYY`, that `resolution=1` returns minute-like data, and that values 5/15/30/60 do not select their apparent cadence.

Phase 4.11B-3 used four paced `IntradayOhlc` and four matching `DailyOhlc` calls for FPT and HPG on completed HOSE sessions 2026-06-23 and 2026-06-24. All calls succeeded. Each intraday response contained 226 rows/records with the same `TradingDate`, `Time`, `Open`, `High`, `Low`, `Close`, `Volume`, `Value`, and `Symbol` shape. Across all four sessions there were no invalid timestamps, raw/bucket duplicates, or ordering errors.

Raw-second variance is not cadence variance: 225 of 226 raw timestamps per session had nonzero seconds, but flooring the Vietnam wall time produced 226 unique minute buckets. Continuous-session buckets covered 09:15-11:29 and 13:00-14:29 with 100% of within-segment transitions at 60 seconds; the lunch break was excluded and the separate final row was 14:45. Raw `Time` is classified `likely_last_trade_time_but_not_fully_verified`; the future chart timestamp floors that local time to minute start before Unix-second conversion. This preserves OHLCV and removes server/browser timezone dependence.

For every sample, first open, maximum high, minimum low, and final close exactly matched DailyOhlc. Intraday `Volume` was positive, non-cumulative, and summed exactly to DailyOhlc volume (ratio 1.0 for all four sessions), supporting `likely_per_bar_shares`; the public label remains `Volume` because SSI's inspected materials do not explicitly define the unit. The 09:15 open and 14:45 close reconcile, but exact ATO/ATC aggregation remains ambiguous. Do not synthesize absent buckets or forward-fill OHLCV.

Direct `resolution=5`, `15`, `30`, and `60` calls from Phase 4.11B-2 were accepted but each returned the same 226-row minute-like summary. Values 5, 15, 30, and 60 were accepted by the endpoint but did not select corresponding output cadence in tested SSI behavior, so those mappings remain unexposed.

The verified live timestamp is separate timezone-free `TradingDate=DD/MM/YYYY` plus `Time=HH:MM:SS`. Phase 4.11C must interpret those SSI wall-clock values in `Asia/Ho_Chi_Minh`, floor to minute start, then emit Unix seconds. The current helper assigns UTC to a naive parsed datetime, so its derived `timestamp` must not be reused as canonical.

The repository's session classifier is HOSE-like and holiday-unaware. The restricted gate therefore accepts only one date strictly before the current Vietnam date, `interval=1m`, and at most 1,000 rows from page 1. All tested sessions fit one page (`totalRecord=226`), but pagination is not verified. Current sessions, multi-day ranges, realtime updates, higher-timeframe aggregation, HNX/UPCOM generalization, and fallback remain deferred. The current runtime allowlist stays empty until Phase 4.11C implements this separate contract.

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

SSI V3 is the only supported SSI production implementation. REST and streaming
remain disabled until their explicit enable flags and credentials are supplied;
disabled configuration produces typed unavailable states and does not select
V2.

```env
SSI_V3_REST_ENABLED=false
SSI_V3_CLIENT_ID=
SSI_V3_API_KEY=
SSI_V3_API_SECRET=
SSI_V3_API_URL=https://api.ssi.com.vn/api/v3
SSI_V3_REQUEST_TIMEOUT=10
SSI_V3_MAX_RETRIES=2
SSI_V3_RETRY_DELAY=1
SSI_V3_RATE_LIMIT_PER_SECOND=5
SSI_V3_LIVE_ACCEPTANCE_ENABLED=false

SSI_FASTCONNECT_INTRADAY_ENABLED=true
SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS=60
SSI_FASTCONNECT_REALTIME_ENABLED=true
SSI_FASTCONNECT_TRADE_TAPE_ENABLED=true

SSI_STREAMING_REALTIME_ENABLED=false
SSI_STREAMING_REALTIME_CACHE_TTL_SECONDS=15
SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE=X:{symbol}
SSI_STREAMING_REALTIME_BOOTSTRAP_SYMBOLS=
SSI_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS=45
SSI_STREAMING_REALTIME_RECONNECT_ENABLED=true
SSI_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS=2
SSI_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS=30
SSI_STREAMING_REALTIME_RECONNECT_MAX_ATTEMPTS=0
SSI_STREAMING_SNAPSHOT_ENABLED=false
SSI_STREAMING_SNAPSHOT_PATH=runtime/ssi_streaming_last_known.v1.json
SSI_STREAMING_SNAPSHOT_WRITE_INTERVAL_SECONDS=5
SSI_STREAMING_SNAPSHOT_TRADE_LIMIT=50
SSI_STREAMING_SNAPSHOT_MAX_SYMBOLS=128
SSI_STREAMING_SNAPSHOT_MAX_AGE_DAYS=7

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

The V3 API URL remains configurable for documented SSI deployment changes; no
V2 base URL, consumer credential, or version selector is active. Credentials
must only come from local environment variables or a secret manager. Never
commit real values. V3 configuration is env-only and hidden from the web
configuration registry; disabled or missing API key/secret returns setting
names only. `SSI_V3_LIVE_ACCEPTANCE_ENABLED` is a second manual-script guard,
not a production route switch. V3 initialization remains lazy and health
readiness does not require a provider call.

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
* The watchlist service preserves up to 20 recent per-symbol DailyStockPrice foreign-flow rows from the same bounded request used for latest enrichment. It computes `indicators.foreign_net_5d_latest_available` and `indicators.foreign_net_20d_latest_available` only from returned `foreign_net_volume` rows; insufficient history stays null with `foreign_net_history_count`.
* Phase 4.12B separately exposes `GET /api/v1/stocks/vn/foreign-flow/symbol/{ticker}`. Recent mode defaults to 20 and caps at 120 accepted sessions; paired date-range mode caps at 168 calendar days. Direct net wins, both-sides-only fallback is allowed, dates are ascending/unique with last valid duplicate winning, and 5/20/60-session summaries are null-aware. Dedicated cache TTLs are 300 seconds current positive, 3,600 seconds completed-range positive, 60 seconds empty, 30 seconds unavailable, and 86,400 seconds maximum stale recovery. Identical active keys coalesce process-locally. No frontend, current-session, ranking, aggregate, fallback, or DailyOhlc price-source change is part of this endpoint.
* Phase 4.12B-R1 used the normal launcher and reached HTTP readiness in 6.226 seconds. The local environment classified each bounded FPT history fetch as sanitized `network_error`; HTTP responses remained typed unavailable rather than ready-empty or zero-filled. An identical 20-session repeat used the 30-second negative cache with no additional provider call, broad observability remained read-only/no-store, and in-flight count returned to zero. Live usable-row and positive-cache acceptance remain pending network availability; no provider/configuration workaround was added.
* Phase 4.12D-1 exposes `POST /api/v1/stocks/vn/foreign-flow/batch` for 1-30 normalized unique watchlist symbols. It reuses the Phase 4.12B `limit=20` service, caps worker concurrency at four, preserves request order, isolates unavailable symbols, returns summary fields without history arrays, and builds latest/5-session/20-session net-value rankings without another provider fetch. The frontend makes one cancellable batch request per non-empty watchlist and retains same-scope successful data during an unavailable refresh. This adds no current-session source, VN30/HOSE aggregate, fallback provider, or DailyOhlc ownership change.
* The Phase 4.12D-1 port-8012 smoke returned five typed unavailable rows under current SSI network unavailability. Repeating the same batch reused five negative-cache entries with unchanged provider-call count and zero active work. A production-handler mismatch initially converted custom Pydantic ticker-validation errors to HTTP 500 because the error context was not JSON serializable; validation now runs before batch-service construction and returns sanitized HTTP 422. No SSI/provider/configuration workaround was added.
* Legacy Mozyfin foreign-history caveats are not used for SSI ownership. SSI history is DailyStockPrice-only, row-count bounded, and non-fatal.
* Normalized rows are publicly labeled `SSI DailyStockPrice`; the generic provider label `SSI` is not used for the enrichment block.
* `quality_status`, `date_match`, `staleness_reason`, `missing_fields`, `field_coverage`, present-value-only `units`, and sanitized diagnostics make partial or mismatched enrichment explicit without changing DailyOhlc validity.
* Date match is `matched`, `mismatched`, `unknown`, or `unavailable`. A
  mismatch is an input to the documented canonical selection: only a materially
  stale DailyOhlc history plus a dated usable DailyStockPrice close activates
  the DailyStockPrice branch.
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
* DailyStockPrice capabilities are independent: price limits, matched statistics, put-through statistics, foreign flow, and session metadata each use ready/partial/unavailable state, while an additive overall state summarizes the family. Missing reference/ceiling/floor values do not invalidate other usable capabilities and are never inferred.
* V3 foreign gross aliases are `totalForeignBuy`, `totalForeignSell`, `totalForeignBuyValue`, and `totalForeignSellValue`. Numeric zero remains zero; null/absent/blank/malformed values remain null; malformed audited values retain a typed issue. Net volume/value derive only from complete gross pairs, with presence, alias, raw-type class, and derived lineage kept secret-safe. One bounded FPT `2026-07-28` read observed all four gross aliases as explicit-zero strings and both net fields as derived zero.
* Completed DailyOhlc session context is separate from current provider event context. Previous-session EOD data during the next active session is `latest_completed`; cache age does not make it stale.
* Live state is channel-specific for last-price snapshot, X-QUOTE order book, X-TRADE tape, and IntradayOhlc. A ready order book keeps the live block partial/usable when another optional channel is empty or unavailable.
* Active-session IntradayOhlc freshness targets the current Vietnam date. Outside active windows it targets the latest completed daily session. This classifier is holiday-unaware and does not fabricate missing bars.
* Intraday capability is ready only when usable cadence matches the request; usable irregular or request-mismatched cadence is partial. Company intraday change is latest close minus first session candle open and exposes that baseline explicitly; a missing baseline remains null and an equal valid baseline remains real zero.
* V3 securities summary currently normalizes reference, ceiling, and floor as null. The company contract uses only explicit DailyStockPrice compatibility fields for those values and never uses the exchange-derived `price_limit` calculation, daily close, bid, or ask as a substitute.
* Source coverage is grouped as Prices, Live market, Company, and News. Core profile readiness is separate from optional metadata completeness; provider-only Sector and Industry stay null when absent.
* Technical coverage, history counts, price-versus-reference state/value, and calculation provenance remain available in a collapsed details disclosure and diagnostics rather than occupying primary metric tiles.
* News, financials, and corporate-action events retain their existing gating/placeholder behavior.
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

## Phase 4.11D-1 Current-Session Source Inventory

| Source | Existing code path and acquisition | Relevant fields | Cache/reconnect behavior | Candle decision |
| --- | --- | --- | --- | --- |
| SSI IntradayOhlc | `SsiFastConnectFetcher.get_completed_intraday_1m` -> fixed `IntradayOhlc` request; `VietnamMarketService.build_intraday_chart` accepts completed or current Vietnam date | `TradingDate`, `Time`, OHLC, `Volume`, `Value`, `Symbol`; no finality flag | Separate completed and short current-date LRU/stale policy | Sole authoritative 1m history source |
| X snapshot | startup-owned `SsiStreamingRealtimeManager`, `X:{symbol}` | last price/snapshot fields, provider time, optional last volume | latest process-local cache, debounced reconnect in active sessions | never a candle |
| X-QUOTE | `X-QUOTE:{symbol}` -> dedicated order-book cache | bid/ask levels and provider time | latest-row cache; preserved stale/after-hours | never a candle |
| X-TRADE | `X-TRADE:{symbol}` -> parser -> bounded `TradeTapeEventCache` | `LastPrice`, `LastVol`, `TotalVol`, `Side`, provider date/time; observed stream has no ID/sequence | receive-order insert, no event dedup; preserved bounded snapshots; manager reconnect cannot detect trade gaps | provisional current bucket candidate only; currently blocked |
| F | `F:{symbol}` -> session-status cache | trading session/status/date/time | latest-row cache and manager reconnect | never a candle |
| Compact intraday pulse | `get_intraday_ohlcv` -> watchlist/company pulse | provider-returned OHLCV subset and derived summary | ordinary fetcher/service cache | not chart history |
| Phase 4.8S | lifecycle-owned `SsiStreamingSnapshotStore` | allowlisted normalized X/X-QUOTE/X-TRADE/R/MI/F rows | persisted rows always restore stale and are replaced by live rows | never chart history |

Live proof on 2026-07-16 used eight current-date FPT IntradayOhlc calls from 09:12-09:20 Vietnam time. `NoDataFound` persisted through 09:15:05; at 09:16:05 the response contained a 09:15:59 row and a changing 09:16 provisional row. Same-minute OHLCV and raw `Time` revised, and a newer bucket appeared by the 09:17:10 observation. Provider-response latency was 0.423-1.116 seconds (median 0.615, eight calls). Previous-bucket finality is inferred only when a newer bucket appears and must be reconciled with SSI.

The bounded X-TRADE observation used only `X-TRADE:FPT`, two 30-second windows, and one controlled reconnect. It observed 206 events without error but no provider sequence/trade/message ID. Duplicate visible tuples were common, so receive order cannot support authoritative close selection or safe volume summation. After reconnect, missed/replayed events and sequence gaps were unknowable. Future reconnect handling must discard trust in provisional aggregation and refresh SSI IntradayOhlc before resuming. No raw payload or credential was stored.

### Phase 4.11D-2 runtime contract

Current-date requests use the same one-call fixed SSI mapping as completed dates. Valid rows keep minute-start Unix timestamps; the newest accepted raw `TradingDate + Time` is retained only for non-negative age metadata. A current-minute bucket is `provisional` only during a scheduled active session; older current-day buckets are `inferred_final`. Freshness is `updating` for the current/immediately previous bucket under a fresh provider snapshot, `delayed` when further behind, `stale` after bounded recovery or provider-refresh age above 90 seconds, and `unavailable` without usable rows.

Current-date cache policy is positive 15 seconds, provider-confirmed empty 5 seconds, negative 10 seconds, and stale-if-error no longer than five minutes. Completed dates retain 86,400-second positive/empty, 60-second negative, and seven-day stale recovery. Policy identity is checked against the current Vietnam date so a current-session entry is not reused as a completed entry after rollover. The backend does not poll or retry in the background.

The dashboard owns one request and one one-shot timer. Pre-open may schedule one 09:15:07 opening baseline, active morning/afternoon/ATC polling targets the minute boundary plus seven seconds, lunch schedules one 13:00:07 baseline, and the ATC transition schedules one 14:45:20 reconciliation. Hidden tabs, D1, completed dates, pre-open, and closed periods have no recurring chart request. SSI arrays replace authoritatively; no X-TRADE/X/X-QUOTE/DailyStockPrice/TradingView data becomes a candle.

The official-client observation emitted an SDK/urllib3 certificate-verification warning. This audit did not disable TLS, change proxy behavior, or modify transport configuration; transport trust verification remains a separate operational follow-up.

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
| Historical Phase 5.1 - NewsProvider | None; news is not SSI-owned | News remains disabled by default; optional local/personal providers now exist behind separate gates. |
| Phase 5.2 - Corporate Actions and Dividends | None unless SSI exposes explicit structured sources later | Use only explicit structured event sources; do not infer events from market-data gaps. |
| Phase 6.0 - Backend Performance and Caching | DailyOhlc, DailyStockPrice, metadata, diagnostics if performance evidence justifies storage | Persist source/date/fetched_at only if durable storage is introduced; keep stale-data semantics explicit. |
| Phase 7.0 - Product Packaging | SSI source/freshness status as validation inputs | Clean runbooks, startup scripts, smoke/test/release checklist, and deprecated docs without changing provider semantics. |

## Phase 4.11E Intraday Production Operations

The SSI `IntradayOhlc` chart path records bounded scalar metrics and one sanitized last-result snapshot per backend worker. `GET /api/v1/stocks/vn/intraday-chart/health` reads that state only, sets `Cache-Control: no-store`, and performs no SSI request or cache refresh. Metrics reset on restart and are not deployment-global when Render runs multiple workers. Each actual provider request emits one `vn_intraday_provider_fetch` event with ticker/date/session, force/cache action, latency, row-quality counts, freshness/age, stale-recovery use, and a normalized failure class; raw rows, exception messages, headers, tokens, accounts, cookies, and credentials are excluded.

Route inspection confirms this intraday-specific health path and the established dashboard-wide `GET /api/v1/stocks/vn/observability` path are separate operations with separate typed schemas, not aliases. Raw-time regression coverage also confirms the duplicate-minute winner retains its latest accepted SSI timestamp for age while its public candle timestamp stays floored to minute start.

The 2026-07-16 bounded runtime smoke confirmed HTTP 200/no-store health reads, separate endpoint/provider-call accounting, positive negative-cache hits, forced-refresh accounting, and five-way same-key coalescing (five requests, one provider call, four waiters, zero retained in-flight entries). The local SSI call returned only sanitized `network_error`, so the health snapshot correctly became `degraded`; this run does not prove live current-session or completed-session bars.

Exact SSI chart keys include provider/dataset, ticker, `1m`, date, page 1, and page size 1,000. Same-key normal/force overlaps share one worker-local provider call; other ticker/date keys stay independent. This uses no Redis or distributed lock. Current snapshots publish both newest raw-bar age and successful-provider-snapshot age. Active-session freshness uses 30 seconds for `updating` eligibility and 90 seconds for stale provider snapshots; expected lunch inactivity does not by itself become stale. SSI IntradayOhlc remains authoritative and X-TRADE aggregation remains blocked.

## Next phase

With `VN-FF-LIVE-1` accepted, the immediate phase is `VN-FF-SIGNAL-1 —
Explainable Foreign Flow Signals`. The ordered follow-up roadmap is
`VN-BREADTH-1`, `VN-SECTOR-1`, `VN-RS-1`, and `VN-ALERT-1`. Do not introduce
FC Trading, request-handler subscriptions, or Mozyfin/KBS fallback for
SSI-owned market data in any phase.

## Historical: Phase 4.11F streaming topology and recovery

The runtime has one FastAPI lifespan owner, one process-local `SsiStreamingRealtimeManager`, one reconnect monitor, and one official adapter instance per generation. The adapter creates one SSI `MarketDataStream`, SignalR `Connection`, `WebsocketTransport`, and daemon socket thread for each approved channel. X, X-QUOTE, X-TRADE, F, R, and MI therefore share manager/cache/persistence ownership but not one physical socket. Request handlers only read state and never start or subscribe.

Inspection of installed `ssi_fc_data` 2.2.2 shows `MarketDataStream.start()` constructs a `Connection` without a `ReconnectionHandler`. Its socket error/close path invokes close evidence, while channel restoration remains the SDK `SwitchChannels` callback on socket open. StockClock therefore owns bounded whole-cohort restart; there is no competing SDK reconnect loop in the configured path. The adapter chains connection-open evidence after `SwitchChannels` without editing site-packages.

Each logical attempt has a monotonically increasing generation. Callback closures capture it, and only the current generation may change transport/context state, caches, last-event timestamps, reconnect scheduling, or persistence dirtiness. Subscription success is not readiness: each context stays recovering until a current-generation event matching its approved ownership arrives. One failed channel marks only its context failed; other contexts can remain recovering/ready. Old cache and bounded persisted rows remain stale/last-known during recovery. X-TRADE continuity across a disconnect is not guaranteed and is never reconstructed.

Retry uses one manager-owned schedule with base delays 2, 5, 10, 20, and 30 seconds, capped by configuration and jittered within 20 percent. Network-close, timeout, transient DNS/TLS, and SDK errors are retryable during active morning/afternoon/ATC windows. Explicit authentication, authorization, configuration, and subscription failures do not retry indefinitely. Lunch and closed-session event silence are not transport failures; ATC is active and does not suppress recovery. Session classification is Asia/Ho_Chi_Minh schedule-derived, holiday-unaware, and does not prove provider intent, exchange halts, or half sessions.

The V3 adapter uses one physical transport and one cohort subscription. A pre-open authentication or authorization failure emits one cohort subscription-failure notification before the manager records the transport error and blocks retry; it is not replayed once for every requested channel. This keeps the existing typed unavailable behavior while avoiding a startup warning burst proportional to the channel count.

`GET /api/v1/stocks/vn/observability` exposes a sanitized typed `streaming` block with one logical cohort transport plus per-context readiness/freshness. It returns `Cache-Control: no-store`, performs no connect/reconnect/subscribe/cache refresh, omits full channels/symbols and raw errors, and represents only the worker serving the request. Multi-worker coordination, Redis, and distributed locking are not implemented.

A bounded after-hours local smoke on 2026-07-16 reached the observability, realtime, and trade routes. SSI startup classified as `authorization` at generation 1, no transport opened, and reconnect scheduled/attempt counters stayed zero; optional realtime and trade responses remained unavailable. The authorization/entitlement condition was not guessed around or retried. This proves fail-fast classification and clean optional degradation only, not active-session recovery or continuity.

Phase 4.11F-A attempted a bounded active-session acceptance on 2026-07-17 during continuous morning (09:19-09:32 ICT). The focused deterministic gate passed 146 tests. Normal-entrypoint launches (including one Web UI auto-build-disabled diagnostic retry) and direct single-worker Uvicorn remained pre-listener within their bounded windows, so no HTTP observability snapshot, SSI provider result, transport/subscription evidence, or current-generation event could be recorded. The diagnostic retry consumed one more substantive process launch than the intended two-start cap; no further server or SSI lifecycle was started. `api.app` import and `SystemConfigService` construction completed independently, but the exact runtime blocker was not isolated. No credential change, forced disconnect, additional reconnect attempt, or production patch was made. This run does not supersede the earlier after-hours authorization observation and does not prove current entitlement state.

Phase 4.11F-R1 showed that SSI bootstrap was not a lifespan readiness blocker: it is scheduled once and run in the threadpool after lifespan entry. Direct Uvicorn returned no-store observability in 5.69 seconds with streaming still `connecting`, and the normal launcher bound in about five seconds before the configured stream channels reported authorization failures. The actual repair is confined to the older launcher: wait for Uvicorn's readiness flag, propagate background startup failure/timeout, and keep `--serve-only` from idling after a failed server start. Streaming generation, reconnect, subscription restoration, context readiness, snapshots, and X/X-QUOTE/X-TRADE/F/R/MI ownership are unchanged. Active-session fresh-event and natural-reconnect proof remains pending.

Phase 4.11F-A2 reran the normal entry point during the scheduled continuous morning on 2026-07-17. HTTP readiness was observed after 4.66 seconds, and `/api/v1/stocks/vn/observability` plus `/api/v1/stocks/vn/intraday-chart/health` returned HTTP 200 with `Cache-Control: no-store`. Generation 1 planned 154 restorations (30 each for X, X-QUOTE, X-TRADE, F, and R; 4 for MI), but SSI classified all 154 as `authorization`. No physical transport opened, no context accepted a current-generation event, and reconnect scheduled/attempt counters remained zero, as required for fail-fast authorization failures. Three spaced observability samples and reads of realtime, trades, and MI endpoints left lifecycle counts unchanged and returned sanitized unavailable/empty optional data. The scheduled session classifier is holiday-unaware and does not prove exchange activity, but the explicit provider authorization classification is sufficient to stop this retry. No connected transport existed, so natural disconnect, subscription restoration, and post-reconnect freshness remain unverified rather than failed.

Phase 4.11G proved that A2 did not establish missing streaming entitlement. The same environment and installed `ssi_fc_data` 2.2.2 package opened an official minimal `X:FPT` stream and received current callbacks; sequential minimal F, MI, X-QUOTE, X-TRADE, and R runs also received their matching event types. The StockClock X-only manager populated cache for 1, 5, 10, and 30 channels. A normal full-registry run reached connected state and accepted 449 events before the fix, while the post-fix run reached 130 opened transports and 1,494 accepted events within its bounded observation; both had zero subscription failures and zero reconnects. The earlier sanitized error remains a transient forbidden/authorization response whose exact external trigger cannot be reconstructed from deliberately discarded raw provider text. It must not be relabeled as entitlement denial.

The installed SDK sequence is: construct `MarketDataClient` and obtain/cache an access token; construct `MarketDataStream`; call `start`; synchronously negotiate SignalR; create the websocket thread; on socket open invoke `SwitchChannels`; then deliver callbacks. StockClock follows that sequence once per channel-specific transport, but now shares one `MarketDataClient` across all streams in a generation. Previously it constructed a client per channel, causing up to 154 duplicate access-token requests. `physical_transport_count` remains the number of current-generation channels whose websocket open callback has fired; it intentionally stays zero during client construction, token acquisition, and negotiation and is separate from planned subscriptions. The standalone verifier now disables optional contexts unless explicitly selected and forwards the manager's generation keyword, preventing false `no_message_after_start` reports.
## SSI-V3-M2.5 flow-data contract

The retained V3 REST contract now exposes three provider-backed flow surfaces:

| Capability | SSI V3 source | Historical | Current session | Classification |
| --- | --- | --- | --- | --- |
| Foreign flow by symbol | Securities Summary | yes | best-effort current REST only | `DIRECT_REST` |
| Foreign flow by index | Securities Summary by index | yes | best-effort current REST only | `DIRECT_REST` |
| Foreign flow by board | per-symbol explicit board universe | bounded only | not exposed as an implicit full-market request | `PROVIDER_BACKED_AGGREGATE` |
| Foreign flow by ICB industry | Securities Summary joined to Securities Info | yes, explicit universe | blocked until same-session symbol flow is proven | `PROVIDER_BACKED_AGGREGATE` |
| Proprietary flow by symbol | no retained field | no | no | `UNSUPPORTED_BY_RETAINED_V3` |
| Proprietary flow by index | Index Summary | bounded date retrieval | current summary | `DIRECT_REST` |
| Proprietary flow by board | Board Summary | bounded date retrieval | current summary | `DIRECT_REST` |
| Proprietary flow by ICB industry | no per-symbol proprietary field | no | no | `UNSUPPORTED_BY_RETAINED_V3` |
| Matched turnover by industry | Securities Summary `totalMatch`/`totalMatchValue` joined to SSI ICB metadata | yes, explicit universe | best-effort REST only | `PROVIDER_BACKED_AGGREGATE` |
| Foreign ownership room | `room.<symbol>` / `ForeignRoomMessage` | no | yes, bounded bootstrap symbols | `DIRECT_STREAM` |

Official SSI documents the current/historical index and board summaries, current/historical Securities Summary by symbol/index, and Securities Info by symbol/index/board in the [Python SDK service contract](https://developers.ssi.com.vn/docs/sdk/python/service-classes). The official model reference documents proprietary fields on `MarketIndexSummary`, exact `IcbCode`/`IcbName` on `SecuritiesInfo`, and `TotalRoom`, `CurrentRoom`, `BuyQuantity`, `BuyValue`, `SellQuantity`, and `SellValue` on `ForeignRoomMessage` in the [SSI SDK model contract](https://developers.ssi.com.vn/docs/sdk/go/utilities).

### SSI-V3-M2.6B provisional current foreign flow

The public SDK operation is `subscribe_symbol_room(symbol)`. The repository
conceptual topic is `room.{symbol}`, while observed provider/wire diagnostics
use `R:{symbol}`; both name layers refer to the same `ForeignRoomMessage`
subscription path. The production V3 stream cohort subscribes for the bounded
bootstrap universe and can idempotently extend the already connected cohort
for one current-flow request symbol. Raw
`bq`/`sq`/`bv`/`sv` presence is classified before typed
`ForeignRoomMessage` defaults are trusted. Only an explicitly present numeric
value can become a public metric; missing, null, blank, and malformed fields
remain null, while provider zero remains zero. `tr`/`cr` are ownership-room
capacity and never become trading flow.

Each accepted message is a cumulative replacement snapshot for one
symbol/session. The cache replaces the prior snapshot and never sums messages.
Session identity uses provider market-status/trading-date context when that
cache is available, otherwise it requires a provider event date. A time-only
room message without provider market-status date is not assigned the local
calendar date and is not exposed as a dated current snapshot. Date rollover
prevents the prior session snapshot from being exposed as current.

`GET /api/v1/stocks/vn/foreign-flow/current/{ticker}` idempotently records the
symbol lease on the lifecycle-owned manager, then reads its process-shared
cache and reports one of `waiting`, `ready`, `stale`, `market_closed`,
`unavailable`, or `error`. If the shared transport is retryably failed, the
touch may schedule one monitor-owned client rebuild; it never creates, owns,
or closes a request-scoped stream. Repeated polls and `force_refresh=true`
share the same single-flight recovery and cooldown and do not create another
provider subscription. `current` remains null until a complete volume or
value buy/sell pair has arrived. The independent
`latest_completed_comparison` comes only from an earlier DailyStockPrice
session. Current provisional values are not inserted into completed history,
analytics windows, rankings, or exports.

R4 classifies authentication/authorization failures as retryable lifecycle
failures rather than permanent process poison. Configuration, proven
subscription-contract rejection, and explicitly proven entitlement rejection
remain non-retryable. A valid snapshot survives disconnect/recovery as stale;
successful transport open clears the prior retryable failure and the next
valid replacement message refreshes the snapshot. The recovery monitor owns
stop/rebuild/subscription restoration and applies one in-flight attempt plus a
short cooldown. Current-stream failure state is scoped to the current
capability and never clears completed DailyStockPrice or VN30 decomposition
caches.

Foreign Flow ticker mode and Company Research show this source as a compact
independent section. DailyStockPrice remains the completed-session authority.
A bounded room-only active-session check authenticated, subscribed `R:FPT`,
received one message with complete nonzero volume/value pairs, and closed
cleanly. Provider time arrived as `YYYY/MM/DD HH:MM:SS`; the production parser
now accepts that observed shape and derives the session date from it. R1
deterministically proves the complete production route and stable subscription
counts, and its desktop/mobile browser gate passes all required states. The
bounded active-session application retry reached HTTP readiness and exposed
one FPT foreign-room subscription inside a stable four-channel cohort, but the
provider returned the sanitized streaming failure class `authorization`
before any room message. Current entitlement/credential resolution,
multi-sample delay/replacement, replay, reset, and post-close reconciliation
remain pending.

### SSI-V3-M2.6A-R1 foreign-room current-flow candidate

The installed and production-pinned package remains `ssi-sdk==3.0.5`. Its
public `MarketDataService` has OHLC, index/board summary, securities info, and
securities summary methods; it has no dedicated foreign-flow method. Its typed
`SecuritiesSummary` model omits foreign fields even though the repository's
authenticated raw transport has previously exposed the four audited aliases
`totalForeignBuy`, `totalForeignSell`, `totalForeignBuyValue`, and
`totalForeignSellValue`. That accepted raw mapping remains historical
DailyStockPrice authority, but it does not prove current-session publication,
event timestamp, cumulative behavior, corrections, or reset.

The official streaming contract documents:

- `trade.*` as `TradeMessage` with time, symbol, price, quantity, side, and
  total volume; no foreign participant field exists.
- `quote.*` as bid/ask `QuoteMessage`; order-book liquidity is not flow.
- `room.*` as `ForeignRoomMessage`. The installed decoder maps `tr`/`cr` to
  room capacity and independently maps `bq`/`bv`/`sq`/`sv` to
  `buy_quantity`/`buy_value`/`sell_quantity`/`sell_value`. The explicit
  buy/sell group is a current-flow candidate; `TotalRoom` and `CurrentRoom`
  never create flow. Production still keeps the row in `ForeignRoomCache`
  because active publication, replay, reset, and reconciliation are not yet
  accepted.
- `market.*` as `MarketStatusMessage` with market/status/trading date; it can
  support context but supplies no flow values.
- Index/board summaries as market/proprietary context; documented proprietary
  fields do not establish a ticker-level foreign aggregate.

M2.6A/R1 added only
`scripts/diagnose_vn_current_foreign_flow.py` and offline tests. The script
uses one owned V3 room-only streaming client solely after explicit
`--allow-live` and an active Vietnam window, bounds symbols/messages/runtime,
stops after one authorization/subscription failure, emits sanitized audited
fields only, and closes the client in `finally`. It never calls undocumented
paths, starts a production manager, or changes a request handler.

The R1 eligibility check at 2026-07-29 08:54 Vietnam time returned pre-open,
so it made no provider call. The primary outcome remains
`M2_6A_R1_V3_FOREIGN_ROOM_CANDIDATE_FOUND_ACTIVE_SESSION_PENDING` until one
bounded active-session observation completes. Counter correction,
next-session reset, reconnect/replay, and same-session post-close
reconciliation remain pending. A zero-only future sample remains
inconclusive.

A subsequent FPT/SSI active-window room-only run terminated after
approximately 87 seconds of its 90-second bound, left no diagnostic process,
and created no sanitized evidence file. Evidence saving is conditional on a
normalized room message, so the observation contained zero normalized rows.
The caller did not retain the final JSON acknowledgement; authentication and
subscription status therefore remain unclaimed, and the provider call was not
repeated. Active-session publication remains pending.

Repository normalization retains raw Securities Summary aliases
`totalForeignBuy`, `totalForeignBuyValue`, `totalForeignSell`, and
`totalForeignSellValue`. Public fields remain provider-neutral:
`foreign_buy_volume`, `foreign_sell_volume`, `foreign_net_volume`,
`foreign_buy_value`, `foreign_sell_value`, and `foreign_net_value`. Net is
calculated only when both corresponding gross sides exist; a provider zero
remains zero and a missing gross side remains null. The established board
normalization remains HOSE scale `1` and HNX/UPCOM scale `1,000`; that REST
policy is not reused for streaming values.

The V3 room subscription is restored for the existing bounded bootstrap
universe so ownership-room rows can be observed. It does not subscribe the
whole market. The parser maps the documented raw keys `tr`, `cr`, `bq`, `bv`,
`sq`, and `sv`, preserves zero, and requires symbol and provider time. Official
[V2 Data Streaming documentation](https://fc-data.ssi.com.vn/Help/NavigateDataStreamPage)
describes equivalent `FBuyVol`, `FSellVol`, `FBuyVal`, and `FSellVal` fields
as totals from market open to report time. That supports a V3
`cumulative_snapshot_candidate`, but does not prove V3 replay/reset parity.
Every diagnostic message therefore replaces the prior candidate and is never
locally accumulated. M2.6B subsequently promoted this exact replacement rule
to a provisional, per-symbol/session production cache and public state machine;
it did not make the stream canonical history. DailyStockPrice remains
completed-session authority, and active publication/replay/reset acceptance
remains pending.

VN-FF-SIGNAL-1 keeps that provider boundary unchanged. Explainable direction,
momentum, reversal, and unusual-intensity states are derived only from accepted
completed DailyStockPrice `foreign_net_value` rows. They reuse the existing
coverage and percentile/z-score analytics; `ForeignRoomMessage` snapshots stay
separate and provisional and never enter completed signal windows. The
2026-06-29/30 unresolved provider anomalies remain numeric null and excluded.
No SSI request, subscription, fallback, or polling lifecycle was added.

Active-session acceptance on 2026-07-24 connected and subscribed only
FPT/SSI/VCB, but observed zero room rows in 25 seconds. This proves transport
and subscription readiness, not buy/sell update semantics. Bounded REST
acceptance returned 17 complete sessions (2026-07-01 through 2026-07-23) for
FPT/SSI/VCB/SHS/ACV; VNINDEX, VN30, and HOSE returned all four proprietary
gross fields dated 2026-07-23. SSI returned 30/30 VN30 members with ICB
classification. The direct by-index Securities Summary shape was one
`symbol=VN30` aggregate row per date, not constituent rows, so industry
aggregation uses the SSI member list plus bounded per-symbol summaries. The
one-session VN30 run produced 13 industries, 100% foreign coverage, and exact
foreign-buy, foreign-sell, and matched-value reconciliation.

New bounded API surfaces:

- `GET /api/v1/stocks/vn/foreign-flow/index/{index_code}?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD`
- `GET /api/v1/stocks/vn/foreign-flow/current/{ticker}`
- `GET /api/v1/stocks/vn/proprietary-flow?scope=board|index&identifier=...`
- `POST /api/v1/stocks/vn/industry-flow` with either explicit `symbols` or one `index_code`

Industry aggregates always identify their universe, preserve SSI ICB code/name
without inferring a hierarchy, exclude and count unclassified symbols, and
report coverage. Matched turnover is labeled liquidity/turnover, never net
cash flow. Proprietary-by-symbol and proprietary-by-ICB-industry remain
explicitly unsupported; market-wide proprietary totals are never allocated to
industries.
### SSI-V3-M2.5-R2 VN30 canonical foreign-flow contract

- `GET /api/v1/stocks/vn/foreign-flow/vn30` uses SSI V3 `securitiesSummary?index=VN30` rows with `symbol=VN30` as the canonical latest value, history, and 5/20-session windows.
- Current VN30 membership from SSI IndexComponents is a separate `CURRENT_MEMBERSHIP_DECOMPOSITION` path for component ranking, breadth, contribution, coverage, and industry analysis. It is not a historically constituent-correct VN30 total.
- Canonical provider aggregates use `coverage_mode=provider_aggregate` and `constituent_coverage=not_applicable`; `30/30` coverage belongs only to decomposition output.
- An active current-session row is provisional. The latest provider session before it is eligible as `latest_completed_session`; cache age is reported separately and cannot make an older provider date source-fresh.
- Gross-field presence is retained as explicit zero, nonzero, absent, or null. All-explicit-zero sessions are preserved and marked suspicious; absent/null fields remain unavailable and reduce completeness.
- Canonical and decomposition cache identities are mode-, date-, session-count-, provider-version-, schema-version-, and membership-aware. Expected-session advancement prevents an old date-bounded response from remaining source-fresh.
- Live acceptance on 2026-07-24 found 44 direct `symbol=VN30` rows from 2026-05-25 through 2026-07-23, but `foreign_buy_volume`, `foreign_sell_volume`, `foreign_buy_value`, and `foreign_sell_value` were null on every direct row. The direct canonical contract is therefore `unavailable` under the observed response; StockClock does not replace it with the current-member decomposition.
- The same bounded decomposition read reached 2026-07-23 with 30/30 same-date value coverage. On both 2026-06-29 and 2026-06-30, all 30 members had all four gross fields explicitly present as zero, with no missing fields. R6E exact-date verification again received provider-backed explicit zeros, so the dates remain diagnostic unresolved anomalies with null public aggregate numbers and are excluded from complete-only calculations; no replacement values are inferred.

### SSI-V3-M2.5-R3 VN30 decomposition fallback contract

- The observed direct SSI V3 capability is `UNSUPPORTED_BY_CURRENT_SSI_V3_RESPONSE`: a successful `securitiesSummary?index=VN30` response contained index rows, but no usable value in `totalForeignBuy`, `totalForeignSell`, `totalForeignBuyValue`, or `totalForeignSellValue`.
- This field-level classification uses failure class `DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED`. It is not an outage, auth failure, timeout, or statement that future SSI versions cannot add the fields.
- A process-local negative capability cache prevents normal dashboard refreshes from repeating the known unsupported probe. Its key includes provider, provider version, capability, index code, and schema version; TTL is 86,400 seconds. `force_capability_refresh=true` explicitly bypasses it. Authentication failures, timeouts, malformed/empty responses, and other provider failures are not cached as unsupported.
- `GET /api/v1/stocks/vn/foreign-flow/vn30` returns `status=partial`, `data_state=partial`, `usable=true`, and `capability_status=decomposition_ready_canonical_unsupported` when current-member data is usable. Compatibility `latest`, `windows`, and `series` then mirror `decomposition` and declare `primary_data_mode=current_membership_decomposition` plus `aggregation_basis=current_vn30_membership`.
- The usable dataset is current VN30 basket historical decomposition: SSI IndexComponents supplies the current membership, and SSI V3 per-symbol foreign rows supply values. It supports latest completed session, 5/20-session windows, series, components, rankings, breadth, contribution, and industry views. It is not a direct SSI VN30 aggregate and is never historically constituent-correct.
- Source coverage separates the unsupported direct index fields from available symbol foreign data and available SSI VN30 membership. The optional unsupported source does not create a whole-feature outage while decomposition remains usable.
- Provider-backed all-zero sessions remain valid values. Series rows expose `anomaly_code=all_constituents_explicit_zero`, `anomaly_status=provider_backed_suspect`, explicit-zero and missing-field counts; windows expose `contains_provider_anomaly`, dates, and count. Completeness remains based on field/session coverage, not on whether the values appear economically unusual.
- Completed-session rules are unchanged. Latest prior provider data remains usable; no current-session or realtime foreign-flow claim is made without proven same-session symbol rows or separately proven room-stream semantics.

## SSI-V3-M2.4C-R3.1 Application Route Acceptance

The R3.1 diagnostic corrected the parent readiness path without changing FastAPI
startup. It now owns one direct `subprocess.Popen` child, removes inherited bind
variables, passes explicit loopback host/port arguments, probes the exact port
with direct local HTTP, requires HTTP 200 plus `status=ok`, retains bounded
redacted stdout/stderr tails, and always terminates the owned Windows process
tree. Readiness is capped at 20 seconds, each route call at 15 seconds, and the
whole run at 120 seconds.

The single accepted run used provider session 2026-07-24. FPT history returned
20 ready rows, the current-membership VN30 decomposition was partial and usable,
the direct VN30 foreign-field capability remained the negatively cached
`DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED`, and the three-symbol watchlist
remained partial and usable. A separate one-shot `indexSummary?index=` request
returned one 2026-07-24 row with all six normalized proprietary fields.

Industry and Proprietary were unavailable in that same application run because
the preceding direct-index service closed the process-shared V3 adapter and
later request-scoped routers reused the closed instance. Factory-created
routers are now non-owning references to the shared adapter; explicitly
injected providers retain close-on-router-close behavior. Index proprietary
flow also uses the same direct `get_index_summary` adapter operation proven by
the one-shot provider check. The live budget was intentionally not repeated
after these fixes, so their post-fix application results are offline-tested but
not yet live-confirmed.

## SSI-V3-M2.4C-R3.1B Post-Fix Application Smoke

The one permitted post-fix run started one directly owned Python child on a
dynamic loopback port, required a typed healthy response, issued each acceptance
request once with provider retries disabled, and terminated the exact Windows
process tree in `finally`. Readiness completed in 3.28 seconds, the entire run
completed in 23.62 seconds, and the port was confirmed released.

The application results live-confirm both R3.1 repairs. Industry returned HTTP
200 with ready/usable data: 806 industry-session rows, 13 industries, and all 30
current VN30 members classified, with no closed-adapter or false 422 failure.
Historical/superseded evidence: Proprietary returned HTTP 200 from the former
direct `indexSummary` interpretation with one 2026-07-24 row. R6D later removed
that interpretation because the current SSI contract does not prove
securities-company proprietary buy/sell fields; the present capability route
is unsupported.

The surrounding contracts remained stable. FPT returned 20 ready sessions
through 2026-07-24; current-membership VN30 decomposition returned 60
partial/usable sessions; the three-symbol watchlist returned three ready items;
and the direct VN30 foreign-field capability remained the secondary negatively
cached `DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED`. The latest provider session
observed by both FPT and VN30 was 2026-07-24. Because the provider had not
published a newer completed session, the remaining gap is classified as
provider publication lag rather than an application outage. No current-session,
historically exact membership, fallback-provider, or direct canonical VN30
foreign-flow claim is added.

## SSI-V3-M2.6B-R6 latest-session foreign-flow aggregation

The startup-owned V3 streaming manager now leases a normalized symbol cohort in one bounded subscription extension and keeps one process-owned provider connection. `ForeignRoomMessage` `bq/sq/bv/sv` fields remain replacement cumulative snapshots keyed by symbol and provider-backed session date; they are never locally accumulated, derived from price, or inferred from `tr/cr` room capacity.

The current aggregate route supports the current SSI VN30 basket and a bounded user-selected watchlist. It aggregates only the newest common provider-backed date, reports complete-side and missing/stale symbol coverage, and may group current VN30 members by the existing ICB classification. Missing fields do not become zero. A current aggregate is display-only and provisional; it can extend charts, tables, windows, rankings, and displayed-series exports, but never overwrites or persists accepted DailyStockPrice history. Same-date accepted DailyStockPrice suppresses the provisional row.

Completed history now retains accepted symbol/date rows across request shapes and force refreshes. If a later DailyStockPrice response ends before the accepted latest date, the service keeps the newer row and marks the response regressive/stale. Active-session provider publication for the aggregate remains pending; deterministic raw-message, subscription, aggregation, cache-integrity, API, and UI paths are covered offline.
