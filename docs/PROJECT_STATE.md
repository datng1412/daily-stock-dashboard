# Project State

## Current repository-grounded capability state

Documentation reviewed: 2026-11-02 against baseline commit `0bf5f90f` (main). Last retained runtime acceptance: 2026-08-12; this documentation audit did not retest live SSI or a deployed service.

Current production SSI market-data routing is V3-only through the sole provider
router. The historical migration notes later in this file describe conditions
at their original dates and do not override this section.

| Capability group | Status | Current boundary |
| --- | --- | --- |
| Daily market data and technical analysis | `PRODUCTION_READY` | Canonical daily OHLCV, SSI-derived VN30 membership/components, MA20/MA50, Wilder RSI14, Bollinger Bands, volume averages/ratio, and other coverage-gated daily metrics are implemented. |
| Completed Foreign Flow | `PRODUCTION_READY` | Symbol history, durable restart restoration, accepted/current merge semantics, anomaly quarantine, rankings, coverage, completed analytics, and deterministic frontend presentation are mature. |
| Current Foreign Flow | `PRODUCTION_READY` | Active-session `ForeignRoomMessage` publication is accepted through the process-shared manager, symbol current route, current-VN30/current-Industry aggregation, FastAPI, and browser. Values stay provisional and separate from completed history. The [optional streaming snapshot](VN_DATA_CONTRACT.md#persisted-last-known-streaming-metadata) can retain normalized room rows for stale restart display. Current aggregates stay process-local. |
| Optional SSI live surfaces | `IMPLEMENTED_NEEDS_LIVE_ACCEPTANCE` | Realtime X quote, X-QUOTE order book, and MI advance/decline semantics remain dependent on live runtime/provider proof. |
| Partial market capabilities | `PARTIAL` | Current-session 1-minute chart, X-TRADE event buffer, VNINDEX/DailyIndex completeness, full-watchlist latency, current-membership VN30 historical decomposition, and current-membership Industry history retain documented limitations. |
| Market participation analytics | `PARTIAL` | VN30 current-membership breadth, current-ICB sector context, selected-stock relative performance, and completed-session VN intelligence alerts are production-ready. The broader group remains partial because HOSE breadth, new-high/new-low breadth, and VN risk mode do not yet exist. |
| Futures and automated proprietary sources | `BLOCKED_PROVIDER` | VN30 futures/F1M/basis/open-interest/volume contracts are unproven; automated proprietary data remains blocked by source and entitlement readiness. |
| Proprietary product expansion | `DEFERRED` | Manual verified EOD infrastructure is experimental and has no accepted real financial row; it is not an active product priority. |

## Current milestone and next-phase boundary

`VN-ALERT-1 — Watchlist Intelligence` is `PRODUCTION_READY`. It reuses the generic
AlertService, worker, storage, notification routes, Alerts page, and trigger
history for four explicitly configured rule families: accepted completed
foreign flow, VN30 breadth, current-VN30 ICB sector context, and selected-stock
relative strength. Rules are demand-driven; incomplete or provisional inputs
cannot fire; same-rule/scope/session notifications are deduplicated. Current
ForeignRoomMessage snapshots remain excluded.

Final network-capable production acceptance passed on 2026-08-12. SSI V3 auth,
30-member VN30 membership, and completed analytics were available through
2026-08-11. An acceptance-only FPT `vn_foreign_flow` rule matched the real
one-session `distributing` state (`foreign_net_value=-104,650,853,200` VND),
persisted one trigger through `AlertWorker`, and remained one trigger on the
same-session repeat. A naturally unavailable FPT industry-relative-strength
rule wrote only `skipped`; disabling both rules resulted in zero evaluations.
The real Alert API CRUD/history flow and desktop/mobile Alerts UI passed,
including the FPT Foreign Flow deep link. The acceptance also repaired invalid
truncated trigger-diagnostics JSON and mobile grid intrinsic-width overflow.
All temporary rules, state, processes, and ports were removed after validation.

The next phase is not assigned by this implementation.
VN-RS-1 is production-ready for selected-stock 1/5/20-session relative
performance versus provider VNINDEX, provider VN30, and equal-weight current
VN30 same-ICB peers. Positive runtime acceptance on 2026-08-11 proved exact
SSI sessions through 2026-08-10, a usable FPT partial response, a complete VCB
bank-peer response, bounded cold/warm cache behavior, and real desktop/mobile
rendering without fallback or frontend fan-out.

`VN-FF-SIGNAL-1` is complete. The existing completed symbol analytics now own
an additive value-based signal contract for 1/5/20-session direction,
non-overlapping recent/previous five-session momentum, adjacent nonzero
reversal, and existing percentile/z-score intensity. Symbol detail and VN30
Overview render the same backend states without new requests or polling. The
VN30 signal is explicitly current-membership decomposition; current
`ForeignRoomMessage` values remain separate, provisional, and excluded from
completed signals. Missing values and the quarantined 2026-06-29/30 sessions
cannot complete a signal window; explicit accepted zero remains neutral.

`VN-FF-LIVE-1` was accepted on 2026-08-10. A bounded active-session run received
official `room.FPT` and `room.SSI` messages with raw `bq/sq/bv/sv` present,
retained provider/receipt timestamps, and produced usable symbol, 30/30 VN30,
and 13-group Industry application responses. A later observation advanced the
process-owned aggregate without accumulating snapshots or creating duplicate
logical rows. The real desktop/mobile browser retained provisional current data
through manual refresh with no page-level overflow or console errors. Completed
DailyStockPrice history stayed authoritative and independent. Render itself was
not observed; deployment still requires one backend worker for coherent
process-local current state.

A launch-time repeat at 11:10-11:18 Vietnam time confirmed SSI provider
progression from 11:10 to 11:11 for SSI, a fresh 11:11 FPT snapshot, 30/30
current-VN30 coverage, 13 reconciled Industry groups, and one provisional FPT
row above completed 2026-08-07 history in the real browser. Cold application
startup took 36.2 seconds, so the manual runtime diagnostic now uses the
established bounded 45-second readiness deadline rather than 20 seconds.

## Current data-quality limitations

- On `2026-06-29` and `2026-06-30`, all retained VN30 constituents returned
  explicit zero values for all four audited SSI foreign fields. Both sessions
  remain `unresolved_provider_anomaly` (`Bất thường dữ liệu`): public aggregate
  numbers are null and the sessions are excluded from complete-only windows,
  rankings, analytics, chart numeric points, and numeric CSV cells. No value is
  reconstructed, inferred, or accepted as a valid zero session.
- Completed VN30 and Industry decomposition uses current authoritative VN30
  membership and is not historically constituent-correct.
- HOSE-wide breadth is blocked until an authoritative scalable universe and a
  measured acquisition path are proven.
- VN30 futures/basis remains blocked pending a provider contract for instrument
  identity, price, expiry, multiplier, volume, and open interest.
- VN-SECTOR-1 uses the current VN30 cohort and current SSI ICB classification;
  it is not historically constituent-correct and does not claim official
  sector-index returns. Small one-member groups remain visible rather than
  being assigned an inferred confidence or composite score.
- VN-RS-1 Industry is an equal-weight proxy made from current same-ICB VN30
  peers, excludes the selected ticker, is not historically constituent-correct,
  and is not an official industry index. A current group with no other member,
  such as FPT's observed software group, remains unavailable.

## VN Holdings Concentration Snapshot feasibility (2026-11-03)

Phase 8.1 is `NEEDS_VALIDATION`. An offline probe at `6cc44dca` exercised the
daily chart route with eight synthetic positions and SSI-shaped fixtures.
All eight reconciled on one observed prior date. A holiday-shaped gap, a
current-day candle, and unusable or wrong-date marks demonstrated why the
snapshot needs an observed reference date and full exact-date coverage.
Eight cold chart requests produced 24 simulated SSI page reads. Eight
immediate warm requests produced zero. The
[daily chart caveats](SSI_FASTCONNECT_INTEGRATION.md#v3-daily-history-completeness-and-freshness)
describe the finality and stale-cache limits.

The 113 focused backend tests passed. Live SSI is `NOT_VERIFIED`. Live
valuation coverage, same-date price and share-basis reconciliation, latency at
the proposed eight-position cap, and the investor's five-review workflow are
pending. `NEXT` remains unassigned.

## Fix-when-touched technical debt

Large Vietnam dashboard page decomposition, VN30 hydration performance,
obsolete migration prose, current-price documentation maintenance, unrelated
test-baseline failures, and broad historical-document compression are
fix-when-touched work. None is an active standalone cleanup phase.

## Historical implementation record

The dated entries below preserve implementation and validation history. Any
then-current V2 ownership, proprietary `indexSummary` interpretation, current
Foreign Flow limitation, or next-phase statement is superseded by the current
capability state above.

- VN-RS-1 adds `GET /api/v1/stocks/vn/relative-strength/{ticker}` and one
  selected-ticker dashboard card. SSI DailyOhlc owns stock and peer closes;
  exact-date SSI `indexSummary.indexValue` owns VNINDEX/VN30. Each independent
  1/5/20-session window uses exact provider-session intersections and no
  forward-fill. Industry is the equal-weight current-VN30 same-ICB peer cohort
  excluding the selected ticker. FPT runtime was partial because its current
  software group had no other VN30 peer; VCB was ready across all three
  comparisons. FPT cold/warm HTTP latency was 8.99/0.05 seconds with 42/0
  benchmark calls; breadth-to-sector-to-RS reused all stock, membership, and
  benchmark inputs. A separate cold breadth-to-sector-to-VCB sequence reused
  the selected history plus all 12 peer histories from cache with zero peer
  DailyOhlc calls; only the 42 independent index points were cold.
  Desktop/mobile browser acceptance made exactly one request per selected
  ticker and had no console errors or page overflow.

- VN-SECTOR-1 adds a current-VN30 ICB sector comparison API and compact
  `/vietnam` table. It reuses the accepted breadth/DailyOhlc cache and completed
  DailyStockPrice history, preserves independent price/flow dates and missing
  coverage, and introduces no official index, composite score, recommendation,
  or fallback. Positive 2026-08-11 acceptance classified 30/30 members into 13
  groups. Cold/warm sector latency was 25.63/1.10 seconds; warm and
  breadth-to-sector paths made zero additional DailyOhlc provider calls. Real
  desktop/mobile rendering passed after correcting the digit-adjacent API key
  normalization from `return_1d` to frontend `return1D`.

- VN-BREADTH-1 adds `GET /api/v1/stocks/vn/market-breadth?index_code=VN30` and a compact `/vietnam` card. Exact 30-member SSI IndexComponents membership gates a four-worker minimal DailyOhlc fan-out; the full watchlist path is not used. The modal latest provider date (latest date on ties) is the single session basis, mismatched members are excluded without forward-fill, and existing `calculate_vietnam_indicators` supplies SMA20/SMA50. Direction, MA20, and MA50 denominators remain independent; participation is `(advances + declines) / direction_usable_count`. Positive acceptance on 2026-08-11 resolved 30 exact members and 30 aligned completed-session histories for 2026-08-10: 24 advances, 4 declines, 2 unchanged; 25/30 above MA20; 15/30 above MA50; participation 93.33%; no missing or mismatched symbols. Cold HTTP/service timing was 12.59/12.58 seconds with 30 provider calls and maximum concurrency four; immediate warm timing was 0.52/0.51 seconds with 30 cache hits and zero provider calls. The real desktop/mobile page used one page-owned aggregate request, retained values through one manual refresh, and had no breadth console error, malformed numeric text, horizontal overflow, or fallback. Focused validation passed 10 backend and 224 frontend tests plus TypeScript, ESLint, and Vite.

- VN-PROPRIETARY-EOD-1 implements the verified manual HOSE aggregate MVP without weakening the EOD-0 source gate. `scripts/record_vn_proprietary_eod.py` requires official URL, explicit user verification, gross buy/sell integer VND values, exact net reconciliation, and optional paired gross share volume. An optional signature-valid PDF is SHA-256 hashed without parsing/OCR/copying; persistence without a file requires an explicit lower-strength acknowledgement. Accepted rows use a separate atomic schema-v1 store under `DATA_CACHE_DIR`, deterministic idempotency/conflict/replacement rules, and no public write route. Read-only latest/history APIs and the dedicated `Dữ liệu tự doanh HOSE cuối ngày` tab preserve null versus zero, source evidence, completed finality, manual-only refresh, stale-response rejection, and last-known-good display without proprietary polling. Validation passes 103 focused/shared backend tests, 36 focused frontend tests, compile, TypeScript, ESLint, Vite, and 28 system-Chrome desktop/mobile visual checks. The full backend baseline remains 69 failed and 4 skipped with 3,463 passes; the full frontend run has 1,076 passes, 2 skips, and eight unrelated existing failures while all affected tests pass. No real financial row was persisted, so live manual entry remains pending.

- VN-PROPRIETARY-EOD-0 narrows the unresolved proprietary product to completed daily HOSE total gross buy/sell volume and value. A conservative read-only search of `D:\Downloads`, repository `.tmp`, `data`, and `sample_data` found no relevant XLSX/XLS/CSV sample. Public research found HOSE daily proprietary notices with PDF attachments, official HNX gross-field PDFs for the wrong exchange, paid/authenticated FiinTrade Excel export, entitlement-blocked FiinQuantX, and net-oriented news reports; none proves a free source-originated HOSE spreadsheet contract or automation/redistribution rights. The outcome is `VN_PROPRIETARY_EOD_SOURCE_SAMPLE_REQUIRED`. A new offline diagnostic inspects user-supplied CSV/XLS/XLSX schema, dates, units, exchange scope, totals/components, reconciliation, and missing-versus-zero lineage without network or production writes; 45 synthetic focused tests pass. No real provider file, importer, backend API, frontend UI, polling, or realtime behavior was added.

- VN-PROPRIETARY-P0-C1 corrects FiinQuantX authentication and entitlement classification without entering P1. The earlier diagnostic could prefer stale process credentials because dotenv loading did not override them. The diagnostic now uses explicit `auto|dotenv|process` selection, reports only credential-source presence/equality, logs in once, captures and discards provider output, recognizes only the observed permission marker, and stops after the first entitlement result within a two-call cap. Direct repository-`.env` proof authenticated successfully and authenticated FPT/SSI/HPG/VPB/VIC plus VNINDEX/VN30/HOSE requests returned permission-marked empty DataFrames, establishing `VN_PROPRIETARY_FIINQUANT_ENTITLEMENT_REQUIRED`; these are not valid empty or zero rows. The installed registry still declares 12 total/matched/deal gross fields, but runtime-observed proprietary fields remain empty. A single corrected automated rerun selected dotenv but did not reproduce login success and made zero dataset requests, so current availability remains to be reconfirmed after entitlement. P1 backend/frontend integration remains closed, FiinQuantX/DataFeed credentials are not conflated, SSI fields are not repurposed, and 54 focused offline tests pass.

- SSI-V3-M2.6B-R6E verifies suspicious all-constituent explicit-zero VN30 sessions through bounded exact-date SSI V3 DailyStockPrice calls using one shared provider, four-call concurrency, per-session single-flight, a one-hour cooldown, and one manual bypass. Stronger same-date evidence is monotonic and successful nonzero repairs persist atomically; weaker broad-range zero or partial rows cannot overwrite it. Exact-date live verification for 2026-06-29 and 2026-06-30 found all four raw foreign aliases explicitly zero for all 30 retained VN30 members, with the first zero-producing layer at the raw SSI V3 `securitiesSummary?symbol=` payload. `securitiesSummary?index=VN30` did not provide a proven symbol-level alternative, so both dates remain visible as unresolved provider anomalies with null public aggregate values and exclusion from complete-only windows, rankings, analytics, charts, and numeric CSV cells. Industry detail now consumes canonical `current.aggregate`, uses `current.groups` only for rankings, accepts usable ready/partial/stale/market-closed states, and allows only a complete non-anomalous accepted same-date row to suppress the provisional current row.

R6E validation passes 73 focused backend and 69 focused frontend tests,
compile/TypeScript/ESLint/Vite, and the full backend tree at 3,332 passed,
69 failed, and 4 skipped: six additional passes with no new failure or skip.
System Chrome passes 14 fixtures at 1366x768 and 390x844 (28 assertions) in
45.488 seconds without horizontal overflow or owned process/port leaks. The
bounded current-Industry application smoke reached health but returned typed
`unavailable`/`network_error`; stream subscription restoration reported
authorization failures under bounded backoff, so fresh live Industry
publication remains pending and no provider behavior was guessed.

- SSI-V3-M2.6B-R6D preserves raw DailyStockPrice foreign-field presence through normalization, API, durable accepted history, and the Foreign Flow UI. Missing fields remain null and accepted incomplete rows display `Thiếu dữ liệu`; explicit provider zero remains zero; incomplete rows stay visible but are excluded from complete-only windows, analytics, rankings, and chart points. The prior Proprietary `indexSummary` reinterpretation is removed because SSI exposes no proven securities-company own-account flow fields in the current integration; the route/UI now report unsupported with no rows, fake zero summary, chart, or export. Current Industry detail now consumes the canonical current-VN30 aggregate returned beside unchanged group rankings, preserving provider date, provisional finality, ready/stale/post-close state, same-date accepted precedence, and no placeholder row.

R6D validation passes 126 focused backend and 65 focused frontend tests,
compile/TypeScript/ESLint/Vite, and the full backend baseline at 3,326 passed,
69 failed, and 4 skipped. System Chrome passes 13 fixtures at 1366x768 and
390x844 (26 assertions) without overflow or owned process/port leaks. Fresh
active-session Industry publication remains pending.

Last updated: 2026-08-05

- SSI-V3-M2.6B-R6C repairs the idle/background authentication collapse. A failed or malformed VN30 membership refresh now retains the last validated SSI IndexComponents cohort, so accepted DailyStockPrice history and existing process-owned `ForeignRoomMessage` snapshots remain eligible instead of collapsing to zero requested symbols. Retryable V3 REST authentication invalidates the poisoned shared client and allows one single-flight, 30-second-cooldown bypass per failure episode for visibility resume or manual refresh; a failed recovery re-enters cooldown instead of granting another immediate bypass, and request handlers still do not own provider connections. The frontend keeps one polling owner, preserves values while hidden or recovering, suppresses repeated Force Refresh, and exposes recovery metadata only in Data Details. Focused backend tests pass 173/173, affected frontend tests pass 123/123, compile/TypeScript/ESLint/Vite pass, and system Chrome accepts all 14 required fixtures at desktop/mobile sizes (28 assertions) in 56.879 seconds with no overflow or owned-process/port leak. The full backend tree is 3,324 passed, 69 failed, 4 skipped: failure/skip counts match the R6A baseline and five R6C tests increase passes. Live acceptance was not run at 15:30 Vietnam time because the active provider window had ended; a fresh replacement message remains pending.

- SSI-V3-M2.6B-R6B repairs the frontend metadata-loss boundary that rebuilt current aggregate rows from numbers alone and consequently rendered a stale, fully covered provisional session as `Đủ`. The unified display model now carries source kind, finality, current/provider state, stale/partial flags, coverage counts, and provider timestamps into tables and other status-bearing views. Coverage and numeric completeness remain independent of finality. Data Details separates latest completed, latest display, and current provider sessions; current Industry diagnostics derive `ready`, `partial`, `stale`, `waiting`, or `unavailable` from the bounded current-VN30 aggregate instead of displaying `CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS`. Focused tests pass 58/58, the broader affected frontend set passes 167/167, TypeScript/ESLint/Vite build pass, and system Chrome accepts 16 fixtures at desktop and mobile sizes (32 assertions) in 45.776 seconds with no overflow or owned-process/port leak. No backend was already listening for the permitted bounded live check, so fresh provider replacement acceptance remains pending. Backend response shape, aggregation math, accepted-history persistence, 15-second polling, connection ownership, subscriptions, and Proprietary semantics are unchanged.

- SSI-V3-M2.6B-R6A closes the backend-restart and local visual gaps for continuous foreign flow. Accepted completed SSI DailyStockPrice rows now persist atomically under `DATA_CACHE_DIR` with schema-v1 validation, bounded symbol/session size, startup rehydration, monotonic weaker-refresh behavior, and same-date correction. Provisional `ForeignRoomMessage` snapshots and current VN30/industry/watchlist aggregates remain non-persistent. Seven new durable-cache tests pass; the backend tree is 3,319 passed, 69 failed, 4 skipped, matching the prior failure/skip baseline. System Chrome 150.0.7871.187 accepted 18 fixtures at desktop and mobile sizes in 48.631 seconds with no overflow, surviving owned process, or occupied port. The single active-window diagnostic result was truncated and not retained, so live provider authentication/publication and current aggregate acceptance remain pending and are not claimed.

- SSI-V3-M2.6B-R6 keeps completed foreign-flow history monotonic by accepted symbol/date and extends display-only VN30, current-VN30 industry, and selected-watchlist views through the newest provider-dated `ForeignRoomMessage` session. A weaker or truncated DailyStockPrice refresh cannot remove a newer accepted completed session; API metadata reports the regressive response and retained latest date. Current aggregates use one process-owned stream and bounded symbol cohorts, exclude missing fields rather than converting them to zero, preserve explicit provider zero, disclose observed/requested coverage, and remain provisional in windows, rankings, charts, tables, and exports. Accepted DailyStockPrice for the same date suppresses the provisional row. Current aggregates are never persisted as completed history, and Proprietary remains separate. Deterministic backend/frontend validation is complete; live active-session aggregate publication remains pending because this phase finished outside an active Vietnam market window.

- SSI-V3-M2.6B-R5 keeps an already observed, provider-dated current foreign-flow snapshot visible after the market closes. The shared frontend selector now labels a usable `market_closed` snapshot `Tạm tính`; the newer provisional session remains the unified card session and the first display-only `Chi tiết phiên` row until accepted DailyStockPrice for the same date takes precedence. The backend already retained and returned the snapshot, so no backend lifecycle, API, schema, polling, or request-ownership change was required. Provisional 5P/20P remain dashes, and the row remains excluded from accepted history, charts, rolling windows, rankings, analytics, export, aggregation, and persistence.

- SSI-V3-M2.6B-R4 makes retryable SSI V3 stream authentication/session failures recoverable without moving connection ownership into requests. A failed process-shared client is rebuilt by the lifecycle monitor under one scheduled attempt and a five-second-or-configured-backoff cooldown; route/manual/visibility touches only request that recovery. Existing symbol leases are restored, a successful connection clears the prior retryable failure, and a valid ForeignRoomMessage snapshot remains visible as stale while recovery is pending or fails. Foreign Flow and Company Research each issue one current-flow refresh on a hidden-to-visible transition while retaining displayed values and their existing 15-second polling owner. Completed DailyStockPrice history, VN30 current-membership decomposition, charts, windows, rankings, analytics, and exports remain independent of current-stream health. Time-only room messages are not assigned a local provider date. No current VN30/HOSE/industry aggregation, fallback, new provider, or browser WebSocket was added.

- SSI-V3-M2.6B-R3 consolidates Company Research and Foreign Flow ticker mode into one latest-session `Foreign flow` card. A shared frontend selector compares provider-backed current `tradingDate` with the latest accepted DailyStockPrice date: current wins only when newer, while completed data wins when newer or on the same date. The duplicate current-session card is removed; short current states, null-versus-zero behavior, and one 15-second page-owned request lifecycle remain. The ticker detail row still presents a newer current session first but stays outside completed history, charts, 5P/20P windows, rankings, analytics, persistence, and export. Focused validation passes 88 tests, and a bounded browser gate accepts 26 desktop/mobile fixtures with one card, date/status readability, current-row precedence, no clipping, and no page-level overflow. Streaming authorization remains a separate limitation.

- SSI-V3-M2.6B-R2 adds the provider-dated current session as the first display-only row in Foreign Flow ticker mode's `Chi tiết phiên` table. The existing current-flow card and table share one 15-second polling owner; local row mapping and sorting make no additional current-flow request. Ready, waiting, stale/error-with-prior-data, and unavailable/error-without-data use the short labels `Đang diễn ra`, `Chờ dữ liệu`, `Mất kết nối`, and `Không khả dụng`; missing values and provisional 5P/20P remain dashes while explicit zero stays zero. A completed DailyStockPrice row with the same date wins and suppresses the provisional row. The merged row is presentation-only and remains outside historical arrays, charts, rankings, analytics, exports, and rolling calculations. Focused validation passed 31 tests, and a bounded 16-fixture desktop/mobile browser gate confirmed first-row ordering, status readability, accepted-row precedence, no page-level overflow, and the existing mobile table scroller.

- SSI-V3-M2.6B-R1 closes the deterministic production route and browser gates for bounded per-symbol current-session foreign flow. A raw SSI-shaped `room.FPT` message now has an application-level proof through raw alias auditing, `ForeignRoomMessage` normalization, the process-shared replacement cache, service, FastAPI schema/JSON, frontend mapping, and both product pages. The HTTP route may idempotently extend the already running lifecycle-owned stream cohort for one requested symbol; it never creates, owns, reconnects, or closes the provider transport, and repeated polling or force refresh does not duplicate subscriptions. Current cards expose six nullable flow metrics, visually separate room capacity, and separate provider/receipt times. A React Strict Mode polling deadlock found on Company Research was fixed with a cleanup-owned deferred initial request. Deterministic validation passed 153 backend tests and 62 frontend tests; an owned Chrome/Vite gate accepted 60 state/page/viewport combinations without overflow. The active-session application smoke reached HTTP readiness and a stable single FPT room subscription, but the SSI stream returned typed `authorization` failure before any room message, so live route publication could not be accepted. Completed DailyStockPrice remains authoritative and unchanged. Outcome: `M2_6B_R1_BLOCKED_PROVIDER_ENTITLEMENT`; exact credential-versus-entitlement cause is not distinguishable from sanitized provider evidence.

  Full regression validation returned 3,302 passes with the established 69 failures and 4 skips; TypeScript, ESLint, and the Vite production build passed.

- SSI-V3-M2.6A-R1 corrects the current-session source inventory. Installed `ssi-sdk==3.0.5` decodes `room.{symbol}` into `ForeignRoomMessage` with independent room capacity (`total_room`, `current_room`) and explicit foreign trading counters (`buy_quantity`, `sell_quantity`, `buy_value`, `sell_value`). Official V2 migration evidence describes the equivalent flow fields as session-to-report totals, supporting a V3 cumulative-snapshot candidate but not proving V3 replay/reset parity. The corrected manual diagnostic owns one room-only client, permits two symbols and up to eight messages per symbol within 120 seconds, never derives flow from room capacity or accumulates messages, retains strict null/zero/net semantics, and closes in `finally`. The deterministic suite passes 94 tests. A pre-open eligibility check made no provider call. One later FPT/SSI active-window run consumed approximately 87 seconds of its 90-second bound, left no process, and created no sanitized evidence file, proving zero normalized room rows; the caller did not retain final acknowledgement JSON, so authentication/subscription status is not claimed and the call was not repeated. The outcome is `M2_6A_R1_V3_FOREIGN_ROOM_CANDIDATE_FOUND_ACTIVE_SESSION_PENDING`; active publication/delay, post-close reconciliation, and next-session reset remain pending. Accepted `DailyStockPrice` stays final authority. No production service, API/schema, frontend, cache, persistence, provider, or current-session product behavior changed.

- SSI-V3-M2.5D makes Company Research capability- and lineage-aware without changing SSI V3 ownership or DailyOhlc canonical price. DailyStockPrice now reports independent price-limit, matched, put-through, foreign-flow, and session-metadata states; explicit foreign zero stays zero, missing/blank/malformed values stay null, and net values derive only from complete gross pairs. A single FPT `2026-07-28` read confirmed four explicit-zero gross fields and two derived-zero net fields. Usable irregular intraday cadence is partial, change uses the explicit first-session-candle-open baseline, and missing baselines remain null. Technical coverage and price-versus-reference detail moved behind a disclosure while the three-group quality summary remains intact. Focused backend coverage passed 140 tests; Company Research passed 36 frontend tests plus TypeScript, ESLint, and Vite. The full backend tree returned the established 69 failures and 4 skips with no new regression. A 21.93-second owned Vite/Chrome gate accepted eight fixtures at 1366x768 and 390x844 with no overflow, surviving process, or occupied port.

- SSI-V3-M2.5C makes `/vietnam` a scan-first market overview without changing backend, API, provider, or canonical price ownership. The page now leads with one compact market/session strip and the keyboard-selectable watchlist table, followed by a selected-ticker hero, the existing canonical chart, four quick-fact groups, and independently classified live channels. Detailed refresh controls, watchlist management, data quality, supporting watchlist modules, formulas, and diagnostics remain available in collapsed disclosures. URL watchlists take precedence over saved local state without overwriting it; a query-selected ticker can load transiently while the active watchlist remains empty. Company Research and Foreign Flow remain dedicated deep-link destinations, null remains distinct from zero, and opening local disclosures adds no provider requests. M2.5C-R1 gives Trade Tape one 20-second startup lifecycle per ticker/subscription generation: polling does not reset its deadline, typed unavailable/disabled/error states override request loading, and same-symbol prior rows survive empty or failed refreshes as stale/reconnecting data. A 40.58-second owned Vite/Chrome acceptance retained completed daily facts and the chart while Trade Tape remained truthfully unavailable at 0, 25, and 30 seconds on 1366x768 and 390x844, with no overflow, disclosure-triggered requests, surviving child processes, or occupied port. The M2.5C scan-first phase is ready.

- SSI-V3-M2.5B cleans up Company Research availability without changing SSI V3 ownership or canonical prices. DailyOhlc completed-session finality is separate from current X-QUOTE/X-TRADE event context; last price, order book, trade tape, and intraday have independent channel states; and a ready order book prevents a false global live-unavailable state. Trade-tape warmup is bounded, active-session intraday targets the current Vietnam date, price-limit fields remain provider-only/null, core profile readiness is separate from optional metadata, and the primary quality summary is limited to Daily data, Live market, and Company metadata.
- SSI-V3-M2.5A makes Overview the default Foreign Flow experience without changing any backend, provider, or response contract. The page now presents four primary signals (net 1D/5D/20D and breadth), one completed-session chart, compact stock/industry/watchlist summaries, and separate Stocks, Industries, Watchlist, Proprietary, and Data Details modes. Technical provenance, cache, coverage, anomaly, direct-index, and historical-membership diagnostics remain accessible in Data Details; partial and unavailable sections remain explicit, null remains distinct from zero, and no fixed watchlist or current-session claim was introduced. The affected Foreign Flow set passed 67 tests, TypeScript, ESLint, and Vite. A single bounded Vite/Playwright harness visually accepted 1366x768, 1024x768, and 390x844 with no page-level horizontal overflow and terminated its owned process trees.

- SSI-V3-M2.4C-R3.1B completed the single permitted post-fix application smoke and accepted the Foreign Flow routes with provider publication lag. The owned backend child became ready in 3.28 seconds and completed health plus six product-route requests in 23.62 seconds before exact process-tree termination and port release. FPT returned 20 ready sessions through 2026-07-24; current-membership VN30 decomposition remained partial/usable with 60 sessions while direct VN30 remained the secondary negatively cached `DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED`; Industry returned 806 industry-session rows across 13 industries with all 30 current VN30 members classified; Proprietary returned one 2026-07-24 `indexSummary` row with all six required normalized fields; and the FPT/SSI/HPG watchlist returned three ready rows. The observed latest completed provider session was 2026-07-24, so current-date absence is classified as provider publication lag rather than application failure. No production repair was required after this smoke; the diagnostic summary/order and its offline tests were tightened, with 9 focused tests passing. The full backend suite was not repeated because product code did not change in R3.1B; the existing baseline remains 3,182 passed, 69 failed, and 4 skipped.

- SSI-V3-M2.4C-R3.1 repaired the existing bounded application acceptance harness rather than adding another diagnostic architecture. A direct loopback HTTP probe observed the explicitly requested `127.0.0.1:60722` child after 2.79 seconds, required health `status=ok`, and completed all six Foreign Flow route calls before killing owned PID 11740 and confirming port release in 16.55 seconds. FPT returned 20 ready sessions through 2026-07-24; VN30 decomposition returned partial/usable with 60 sessions; direct VN30 remained correctly secondary as `DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED`; and the three-row watchlist was partial/usable with FPT retained. The one corrected provider `indexSummary` request for 2026-07-24 returned one row with all six proprietary fields, but the application run exposed that the direct-index route closed a process-shared V3 adapter before Industry and Proprietary ran. Factory routers no longer own that shared lifecycle, explicitly injected routers still close their providers, and index proprietary flow now uses the proven direct `get_index_summary` path. The one-shot live budget was not repeated after the fix, so post-fix Industry and Proprietary application responses remain to be confirmed in a later bounded acceptance. Focused validation passed 128 tests; the 3,255-test backend tree retained the known 69 failures and 4 skips with 3,182 passes.

- SSI-V3-M2.4C-R3 narrowed the earlier local `network_error` with one secret-safe, zero-retry connectivity run. `api.ssi.com.vn` resolved over IPv4, accepted TCP/443, and completed verified TLS 1.3; V3 authentication then succeeded. Exact FPT metadata returned one row, FPT DailyStockPrice returned 20 rows through 2026-07-24, VN30 membership returned 30 rows, and direct VN30 securities summary returned 20 rows through 2026-07-24. The diagnostic's sole `indexSummary` request used Sunday 2026-07-26 and normalized as malformed/no usable row; the maintained diagnostic now selects the latest completed weekday, but the live request was not repeated. No provider/config/service behavior changed. A separate bounded application smoke reached Uvicorn lifespan completion and an internal HTTP 200 health probe in about four seconds, but the parent harness did not observe readiness before its 45-second deadline, terminated the exact process tree, and released the port; no product route result is claimed from that smoke.

- SSI-V3-M2.4C-R2 separates Industry request validation from SSI membership/provider unavailability, adds typed Industry usability fields, and normalizes Foreign Flow frontend availability across all modes. Typed unavailable responses no longer render empty charts, each mode retains its usable state and error independently, failed refresh preserves same-scope data, and explicit CLI host/port now override environment bind values while no-CLI deployment behavior is unchanged.

- SSI-V3-M2.4C adds a user-controlled Foreign Flow Watchlist mode and bounded 1–30 symbol GET screener contract. One 60-session V3 DailyStockPrice batch supplies value/volume 1/5/20/60 metrics, per-symbol state/freshness/cache/failure/anomaly metadata, neutral streaks, local filters/sort/search, CSV, and Explorer deep links. The list starts empty unless URL/local state exists; SSI VN30 is explicit only. No current-session claim, provider fallback, alerts, recommendations, or price-source change.

## Related authorities

- [Architecture](ARCHITECTURE.md) owns the runtime and persistence map.
- [VN data contract](VN_DATA_CONTRACT.md) owns source, freshness, and availability semantics.
- [SSI integration](SSI_FASTCONNECT_INTEGRATION.md#current-production-contract) owns provider settings, caveats, and request budgets.
- [Vietnam runbook](RUNBOOK_VN.md) owns setup and verification commands. [API catalog](API_CATALOG.md) owns the route map.

The [original PROJECT_STATE.md](https://github.com/datng1412/daily-stock-dashboard/blob/0e6a00af9033b05e2e0946727cc23126e79cc7b3/docs/PROJECT_STATE.md) retains older implementation snapshots, probe outcomes, and phase-specific operational notes.
