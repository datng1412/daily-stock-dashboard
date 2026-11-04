# VN Dashboard Roadmap

## Active roadmap

Documentation reviewed: 2026-11-02 against baseline `0bf5f90f`. Retained runtime evidence remains dated; no live acceptance was repeated by this review. No next product implementation phase is assigned.

This capability-oriented roadmap is the current source of truth. Dated phase
records later in this file are historical evidence and do not determine what
is next.

### 1. VN-FF-LIVE-1 — Current Foreign Flow Production Acceptance (completed 2026-08-10)

- **Goal:** retain end-to-end active-session evidence from
  `ForeignRoomMessage` through the process-shared manager, symbol current,
  current-VN30 aggregate, current-Industry aggregate, FastAPI, and browser.
- **Why now:** completed Foreign Flow is mature, while current-session data is
  the remaining production trust boundary.
- **User value:** current foreign accumulation/distribution is either visibly
  fresh and provisional or truthfully unavailable for a precise provider
  reason.
- **Data dependencies:** V3 streaming credentials/entitlement, active Vietnam
  session, provider timestamp/session progression, and known deployment config.
- **Reuse:** existing stream lifecycle, current routes, aggregations, finality
  selector, 15-second HTTP polling, and browser visibility recovery.
- **Main risks:** provider authorization/entitlement/network failure and
  process/deployment configuration drift.
- **Explicit exclusions:** no new feature, fallback, request-handler-owned
  connection, dynamic full-market subscription, guessed value, or signal.
- **Exit criteria:** one manager and one polling owner deliver fresh symbol,
  VN30, and Industry values without duplicates; reconnect is bounded;
  completed history stays independent. A proven external failure may exit as
  `BLOCKED_PROVIDER` without forcing application changes. After this exit, the
  R6A-R6E naming series stays closed unless a concrete regression requires a
  historical reference.
- **Acceptance evidence:** a bounded active-session run authenticated and
  subscribed one official two-symbol room cohort, received provider-dated FPT
  and SSI messages with raw `bq/sq/bv/sv` present, and retained normalized
  replacement snapshots. The owned FastAPI runtime returned a usable symbol
  snapshot plus a 30/30 current-VN30 aggregate and 13 current-Industry groups;
  included item/group arithmetic reconciled and a later provider observation
  advanced aggregate values without local accumulation. The real desktop and
  mobile browser retained provisional current data through manual refresh with
  no page-level overflow or console errors. Stale retained rows remained
  labelled disconnected rather than being cleared. Completed DailyStockPrice
  history and persistence remained independent. Render deployment was
  `NOT_OBSERVED`; coherent current state assumes one backend worker.
- **Launch-time repeat:** at 11:10-11:18 Vietnam time, SSI advanced the observed
  provider timestamp from 11:10 to 11:11, the owned application returned 30/30
  current-VN30 coverage and 13 reconciled Industry groups, and the real browser
  retained one FPT provisional row above completed 2026-08-07 history through
  refresh and a hidden-to-visible cycle. Cold readiness took 36.2 seconds; the
  bounded diagnostic readiness allowance is therefore 45 seconds.

### 2. VN-FF-SIGNAL-1 — Explainable Foreign Flow Signals (completed 2026-08-10)

- **Goal:** add formula-backed 1D/5D/20D accumulation/distribution,
  acceleration/deceleration, reversal, and unusual-flow summaries.
- **Why now:** accepted completed history, windows, streaks, rankings, and
  unusual-flow statistics already exist.
- **User value:** explain whether foreign activity is strengthening, weakening,
  or reversing without requiring manual table comparison.
- **Data dependencies:** accepted complete DailyStockPrice rows; current data is
  eligible only after VN-FF-LIVE-1 passes.
- **Reuse:** existing coverage, percentile/z-score, rolling-window, anomaly,
  finality, and frontend view-state models.
- **Main risks:** partial windows and wording that overstates descriptive data.
- **Explicit exclusions:** no AI/ML score, prediction, recommendation, target
  price, or reconstruction of anomaly sessions.
- **Exit criteria:** every signal exposes formula basis, coverage, source,
  session/finality, and neutral unavailable behavior.
- **Acceptance evidence:** one backend-owned additive contract derives value
  signals from the existing completed analytics. Direction requires complete
  accepted 1/5/20-session windows; momentum compares two non-overlapping
  five-session averages and requires ten complete sessions; intensity reuses
  the existing absolute percentile/z-score rule. Symbol detail and VN30
  Overview reuse their loaded responses with no request or polling fan-out.
  Current provisional rows remain separate. Quarantined anomaly rows remain
  numeric null and cannot complete windows. Focused backend/frontend tests,
  Python compile, TypeScript, ESLint, and Vite build pass.

### 3. VN-BREADTH-1 — VN30 Market Breadth Core (production-ready)

- **Goal:** calculate advance, decline, unchanged, participation ratio, percent
  above MA20, and percent above MA50 for current authoritative SSI VN30
  membership. Add up/down volume or value only when field ownership and
  completeness support them truthfully.
- **Why now:** it directly answers whether VN30 movement has broad or narrow
  participation using implemented membership and daily metrics.
- **User value:** concise participation context rather than another isolated
  stock table.
- **Data dependencies:** exact current VN30 membership and bounded, performant
  DailyOhlc histories.
- **Reuse:** IndexComponents, DailyOhlc, MA20/MA50, caches, and coverage states.
- **Main risks:** watchlist latency, missing members, and current-membership
  historical bias.
- **Explicit exclusions:** no HOSE-wide breadth, no missing-to-zero coercion,
  and no official index-contribution claim.
- **Exit criteria:** requested, observed, usable, missing, and classified counts
  reconcile; latency is measured before any universe expansion.
- **Implementation:** `GET /api/v1/stocks/vn/market-breadth` resolves exact
  current SSI VN30 membership, reads only 55 DailyOhlc rows per member with a
  four-worker cap and the existing cache/single-flight path, aligns on one
  provider session, and reuses canonical SMA20/SMA50 calculations. The
  `/vietnam` page owns one aggregate request and shows counts plus independent
  coverage denominators.
- **Acceptance:** positive runtime acceptance completed on 2026-08-11. SSI
  returned exactly 30 normalized unique members; all 30 histories aligned to
  completed provider session 2026-08-10 with 24 advances, 4 declines, 2
  unchanged, 25/30 above MA20, 15/30 above MA50, and 93.33% participation.
  Cold HTTP/service latency was 12.59/12.58 seconds with 30 provider calls and
  concurrency four; the immediate warm request was 0.52/0.51 seconds with 30
  cache hits and no provider calls. Desktop/mobile browser acceptance proved
  one page-owned aggregate request and one bounded manual refresh with retained
  values, no overflow or console errors, and no fallback.

### 4. VN-SECTOR-1 — Sector Strength & Rotation (production-ready)

- **Goal:** combine SSI ICB membership, price performance, breadth, and
  completed Foreign Flow to explain current sector strengthening/weakening.
- **Why now:** VN-BREADTH-1 supplies reusable participation primitives and
  current-VN30 ICB/flow grouping already exists.
- **User value:** identify which current VN30 industries are gaining or losing
  participation and flow support.
- **Data dependencies:** current ICB membership, accepted DailyOhlc, breadth,
  and completed foreign-flow sessions.
- **Reuse:** Industry Flow service, ICB metadata, VN30 cohort, and flow UI.
- **Main risks:** small cohorts and historical composition bias.
- **Explicit exclusions:** current-cohort returns are not official sector-index
  returns; no predictive rotation score.
- **Exit criteria:** ranks expose return, breadth, flow, coverage, session, and
  current-cohort basis with full member reconciliation.
- **Implementation:** `GET /api/v1/stocks/vn/sector-strength` supports the
  current VN30 cohort only. It reuses the shared breadth result and DailyOhlc
  cache/single-flight path, keeps SSI ICB-null members unclassified, computes
  equal-weight 1D member-close returns, and aggregates only accepted completed
  DailyStockPrice foreign net value over 1/5/20 provider sessions. The compact
  `/vietnam` table has one page request owner and request-free local sorting.
- **Acceptance:** positive SSI acceptance on 2026-08-11 classified all 30
  current members into 13 ICB groups for completed price session 2026-08-10;
  completed foreign flow also ended 2026-08-10. Cold sector latency was 25.63
  seconds with 30 DailyOhlc and 30 completed-flow provider calls. Warm latency
  was 1.10 seconds with 30 DailyOhlc plus 30 flow cache hits and zero provider
  calls. A breadth refresh followed by sector used zero additional DailyOhlc
  provider calls. Desktop/mobile rendering, local sorting, retained refresh,
  local table overflow, and group reconciliation passed without fallback.

### 5. VN-RS-1 — Relative Strength (production-ready)

- **Goal:** compare a stock with VNINDEX, VN30, and its current industry cohort.
- **Why now:** sector and breadth phases establish the context needed for
  meaningful comparisons.
- **User value:** show whether a stock is outperforming or underperforming its
  market and peers over explicit windows.
- **Data dependencies:** proven benchmark-history contract and exact session
  alignment; partial DailyIndex is not sufficient by itself.
- **Reuse:** DailyOhlc histories, index services, ICB membership, and chart
  session utilities.
- **Main risks:** benchmark gaps, date mismatch, and presenting a proxy as an
  official index.
- **Explicit exclusions:** no synthetic series labelled VNINDEX/VN30, beta, or
  recommendation language.
- **Exit criteria:** every comparison uses aligned provider dates and explicit
  benchmark/cohort provenance with missing sessions left missing.
- **Implementation:** `GET /api/v1/stocks/vn/relative-strength/{ticker}` uses
  SSI DailyOhlc for the selected stock and current same-ICB VN30 peers, and
  exact-date SSI `indexSummary.indexValue` for VNINDEX/VN30. Independent
  1/5/20-session windows use exact mutual provider sessions. The Industry
  comparison is equal-weight, excludes the selected ticker, and is explicitly
  current-membership, historically incorrect, and not an official index.
- **Acceptance:** bounded 2026-08-11 runtime proof returned usable FPT
  VNINDEX/VN30 windows through 2026-08-10 and truthfully unavailable Industry
  windows because the current software cohort had no other VN30 peer. VCB
  returned ready VNINDEX, VN30, and bank-peer windows. FPT cold/warm HTTP
  latency was 8.99/0.05 seconds with 42/0 benchmark provider calls; the
  breadth-to-sector-to-RS path added no RS provider calls after cache warm-up.
  A cold breadth-to-sector-to-VCB sequence reused 12/12 peer histories and the
  selected history from cache, with zero redundant DailyOhlc provider calls;
  its only cold RS reads were 42 exact-date index points.
  Real desktop/mobile rendering issued exactly one request for each selected
  ticker, used local table overflow, and produced no console errors.

### 6. VN-ALERT-1 — Watchlist Intelligence

- **Status:** `PRODUCTION_READY`; final network-capable completed-data, worker,
  API, and browser acceptance passed on 2026-08-12.
- **Goal:** reuse the generic alert platform for validated VN flow, breadth,
  sector, and relative-strength conditions after their contracts exist.
- **Why now:** alert transport and UI exist, but the VN signal inputs do not.
- **User value:** surface meaningful watchlist changes without continuous
  manual scanning.
- **Data dependencies:** accepted outputs from the earlier roadmap phases.
- **Reuse:** AlertService, worker, notification channels, Alerts page, and VN
  deep links.
- **Main risks:** noise, duplicate alerts, stale inputs, and advice-like copy.
- **Explicit exclusions:** no automatic trading, opaque composite score, or
  alert based on unavailable/provisional data outside its approved contract.
- **Exit criteria:** each notification carries rule, observed value,
  session/date, source, freshness/finality, cooldown identity, and deep link.
- **Implemented contract:** `vn_market` rules support completed symbol foreign
  flow (`net_value` or direction state), VN30 breadth, current-VN30 SSI ICB
  sector metrics, and selected-stock relative strength. Numeric rules use an
  explicit operator and threshold. Relative strength also requires a 1/5/20
  session window and `vnindex`, `vn30`, or `industry` benchmark.
- **Evaluation boundary:** only enabled stored rules create work. Expensive
  identical family/scope reads share the existing worker-cycle cache. No
  watchlist expansion, implicit RS fan-out, scheduler, polling loop, or
  provisional ForeignRoom read was added.
- **Truthfulness:** incomplete coverage, unavailable/null values, quarantined
  foreign-flow anomalies, provisional finality, and missing ICB groups are
  non-evaluable and cannot fire. Trigger diagnostics carry source, endpoint,
  session, finality, coverage, cache state, dedup identity, and deep link.
- **Dedup:** persisted trigger identity remains
  `rule_id + target + data_source + data_timestamp`; VN rules also suppress a
  duplicate notification for that same completed provider session even when a
  zero-second generic cooldown is configured. A later completed session is
  independently eligible.
- **2026-08-11 acceptance:** a bounded four-service probe completed in 0.79s.
  FPT completed foreign-flow history was retained through 2026-08-10 but the
  refresh reported `network_error`/stale; breadth, sector, and relative strength
  were unavailable without completed provider sessions. No live rule was fired
  from stale/unavailable input. Deterministic four-family evaluators, worker
  persistence/dedup, Alert API, and desktop/mobile UI passed. Outcome:
  `IMPLEMENTED_RUNTIME_BLOCKED` until a network-available completed-data run.
- **2026-08-12 final acceptance:** a network-capable run superseded the prior
  environment block. SSI auth and 30-member VN30 membership succeeded; FPT
  completed one-session flow for provider session `2026-08-11` was
  `distributing` with `foreign_net_value=-104,650,853,200` VND. The real worker
  persisted one trigger, suppressed its same-session repeat, skipped naturally
  unavailable industry relative strength, and loaded zero rules after disable.
  Generic API CRUD/history plus real 1366x768 and 390x844 browser create,
  toggle, trigger-history, selected-FPT deep-link, and delete flows passed.
  Trigger JSON/deep-link serialization and mobile intrinsic-width overflow were
  repaired and regression-checked during acceptance.

### Phase 9 — VN Holdings Concentration Snapshot MVP

The frontend implementation follows the [approved holdings scope](PROJECT_STATE.md#bounded-implementation-scope-after-go).
The [Phase 9 capability record](PROJECT_STATE.md#vn-holdings-concentration-snapshot-mvp)
tracks deterministic and browser validation separately from dated chart-route
feasibility. Live application acceptance and the personal five-review pilot are
pending. A fresh live run requires separate authorization.

## Backlog classification

| Class | Items |
| --- | --- |
| `NEXT` | Unassigned beyond Phase 9 implementation and acceptance |
| `LATER` | eventual risk-mode synthesis |
| `BLOCKED` | VN30 futures/F1M/basis/open interest/futures volume; automated proprietary source; HOSE-wide breadth until an authoritative scalable universe is proven; fundamentals/corporate actions without a provider/legal contract |
| `DEFERRED` | Proprietary product expansion; broader stock-detail polish; macro/risk asset integration; optional news-provider expansion |
| `DROP / DO NOT PLAN` | Hardcoded five-symbol defaults; guessed anomaly repair; raw-table-only feature phases; AI/ML investment scoring; automatic recommendations; dynamic request-handler subscriptions; unsupported SSI-field reinterpretation; new fallback providers for SSI-owned fields without explicit approval |

## Known provider and data-quality limitations

- `2026-06-29` and `2026-06-30` remain
  `unresolved_provider_anomaly` (`Bất thường dữ liệu`). All 30 retained VN30
  constituents returned explicit zero for the four audited foreign fields, but
  those zero-shaped aggregates are not accepted as valid zero sessions.
  Public numbers remain null and the dates stay excluded from complete-only
  windows, rankings, analytics, chart numeric points, and numeric CSV cells.
  Audit evidence is retained; no repair is guessed or inferred.
- Completed VN30/Industry history uses current membership and must expose that
  bias rather than claim historically effective constituents.
- Futures/basis and automated proprietary data are provider-blocked.
- HOSE breadth is outside VN-BREADTH-1 until universe authority and acquisition
  performance are proven.

## Fix-when-touched technical debt

Large Vietnam dashboard page decomposition, VN30 hydration optimization,
obsolete migration prose, current-price documentation maintenance, unrelated
test-baseline failures, and broad historical-document compression are not
active phases. Address them only within a scoped feature or correctness change.

## Historical phase archive

The [original VN_DASHBOARD_ROADMAP.md](https://github.com/datng1412/daily-stock-dashboard/blob/0e6a00af9033b05e2e0946727cc23126e79cc7b3/docs/VN_DASHBOARD_ROADMAP.md) records the prior phase plans and their dated outcomes, including SSI V3 cutover, data authenticity, delayed 1m charting, VN30 hydration, and the external-provider and proprietary EOD gates. Some entries describe superseded provider paths or interim blocked outcomes.

Use [Project State](PROJECT_STATE.md#historical-implementation-record) for retained implementation and acceptance evidence. Use the [documentation index](DOCS_INDEX.md#evidence-and-history) to locate detailed source investigations.
