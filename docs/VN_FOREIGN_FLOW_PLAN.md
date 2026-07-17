# Vietnam Foreign Flow Product, Data, and Delivery Plan

Status: Phase 4.12A-Lite verified the full SSI DailyStockPrice symbol-level daily contract; product APIs and UI are not yet implemented

Phase: 4.12-PLAN

Repository evidence reviewed: 2026-07-17

## Purpose

This document is the implementation plan for a Vietnam foreign-investor flow product in StockClock. It defines the user journey, product surfaces, normalized data contract, source gates, delivery phases, and operational safeguards. It does not authorize an SSI field that has not been verified and does not describe a production API that exists today.

The product journey is:

`scan -> compare -> inspect -> monitor`

Phase 4.12A-Lite completed the DailyStockPrice-only gate on 2026-07-17. The symbol-level daily fields, units, provider trading date, date-range history, and existing 5/20-row construction are verified. Current-session semantics, aggregates, bulk behavior, and the API/UI shapes below remain **planned, pending their separate gates, and not yet implemented**.

## Fixed source and interpretation boundaries

- Foreign flow is actual foreign buy/sell activity.
- Foreign room is remaining permitted foreign ownership capacity.
- Foreign ownership is a position or percentage. It is a future, separate domain.
- SSI `R:{symbol}` remains foreign-room context only. It is not a foreign-flow source.
- Missing value fields remain `null`. StockClock must not estimate them from volume and price.
- SSI DailyOhlc remains the sole D1 candle and canonical `latest_price` source.
- SSI IntradayOhlc remains the sole accepted SSI 1-minute candle source.
- `X`, `X-QUOTE`, `X-TRADE`, `F`, `R`, `MI`, and persisted stream snapshots retain their existing isolated ownership. No stream context becomes a candle source.
- X-TRADE candle aggregation remains blocked and missed trade history is not reconstructed.
- External providers, scraping, cross-provider rows, and provider fallback are outside this plan.
- Product copy is descriptive and neutral. Positive foreign flow does not predict a price increase, and negative foreign flow does not predict a price decline.

## Current repository baseline

### Available building blocks

- SSI DailyStockPrice currently maps nullable foreign buy/sell/net volume and value fields, with shares and VND units only when values exist.
- The service fetches a bounded recent DailyStockPrice window per symbol, retains up to 20 usable foreign-net-volume rows, and exposes latest-available 5-session and 20-session sums.
- The existing process cache reuses the bounded DailyStockPrice enrichment/history tuple for 300 seconds and explicit force refresh bypasses normal freshness.
- The watchlist exposes latest-available foreign net volume, a positive/negative/zero-or-missing filter, and explicit unavailable reasons.
- The selected-symbol and company pages expose source-labelled latest DailyStockPrice foreign-flow fields. The selected-symbol panel also exposes bounded 5-session and 20-session net-volume history when enough rows exist.
- SSI IndexComponents supplies the current VN30 membership list when available. Components are normalized, unique, ordered, and cache protected.
- SSI Securities/SecuritiesDetails can supply an HOSE candidate universe and sector/industry metadata, but completeness and authority for aggregation still require proof.
- A broad Vietnam observability route, process-local counters, cache patterns, stale-if-error examples, in-flight coalescing, SQLAlchemy storage, notification routing, and alert infrastructure already exist and can be reused after their phase gates pass.
- SSI `R` foreign-room data has a dedicated cache, API block, status, diagnostics, and persistence path. It remains separate from DailyStockPrice flow.

### Gaps that block the product

- No verified official SSI current-session foreign-flow authority exists in the product contract. The after-close DailyStockPrice proof does not establish active-session cumulative behavior.
- DailyStockPrice correction timing and bulk behavior are not yet proven. The daily field/date/history/value contract is verified, while production rows should use neutral `daily_available` finality until a stronger provider-final marker is established.
- No 60-session foreign-flow history or value-based 5/20/60 trend is implemented.
- No canonical foreign-flow finality, freshness, coverage, aggregate, reconciliation, or counter-reset model exists.
- No coverage-aware VN30 or HOSE foreign-flow aggregate exists.
- No foreign-flow ranking or concentration API exists.
- No dedicated symbol history endpoint or coherent batch product contract exists.
- Current watchlist hydration is provider-I/O bound and sequential; broad HOSE aggregation would be unsafe without a bulk or materialization strategy.
- Sector metadata is partial, so sector aggregation has no proven authoritative classification coverage.
- Existing alerts are not connected to foreign-flow states and cannot be enabled until finality, deduplication, and data-quality gates pass.

## Phase 4.12A-Lite DailyStockPrice contract confirmation

### Evidence boundary

- Installed package: official `ssi-fc-data` 2.2.2. Its `daily_stock_price` request model exposes `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, and `market`; it does not define a typed response model or finality flag.
- Official SSI [DailyStockPrice API documentation](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs) lists the daily row fields and a `TradingDate`-keyed sample. The live proof used only the existing `Market/DailyStockPrice` path.
- Symbols: FPT, VCB, HPG, and SSI. Window: 2026-06-18 through 2026-07-17. Each symbol returned 22 distinct, ascending trading-date rows with no duplicate normalized date.
- The verification ran after the scheduled Vietnam market window at 16:54 ICT. Two bounded reads returned the same latest 2026-07-17 values for all four symbols. This supports stable post-close daily rows, but does not prove an explicit provider-final marker or active-session cumulative behavior.
- Approved network work used two token requests and sixteen DailyStockPrice GETs: two date chunks per symbol on each of two reads. A preceding sandbox-blocked attempt produced no DailyStockPrice GET and no usable provider evidence. No raw payload was persisted or committed.

### Verified raw-to-normalized mapping

| Normalized field | Live/official raw field | StockClock treatment | Unit | Existing consumers |
| --- | --- | --- | --- | --- |
| `foreign_buy_volume` | `ForeignBuyVolTotal` | Direct provider field; integer normalization without scaling | shares | DailyStockPrice block, watchlist/company foreign block |
| `foreign_sell_volume` | `ForeignSellVolTotal` | Direct provider field; integer normalization without scaling | shares | DailyStockPrice block, watchlist/company foreign block |
| `foreign_net_volume` | `NetBuySellVol` | Direct provider field preferred; derives buy minus sell only when direct net is absent and both compatible inputs exist | shares | Latest foreign block and 5/20-row summaries |
| `foreign_buy_value` | `ForeignBuyValTotal` | Direct provider field; numeric normalization without scaling | VND | DailyStockPrice block, watchlist/company foreign block |
| `foreign_sell_value` | `ForeignSellValTotal` | Direct provider field; numeric normalization without scaling | VND | DailyStockPrice block, watchlist/company foreign block |
| `foreign_net_value` | `NetBuySellVal` | Direct provider field preferred; derives buy minus sell only when direct net is absent and both compatible inputs exist | VND | DailyStockPrice block, watchlist/company foreign block |
| `foreign_net_5d_latest_available` | none | Rolling sum of the latest five distinct dated normalized rows with usable `foreign_net_volume` | shares | Selected-symbol indicators |
| `foreign_net_20d_latest_available` | none | Rolling sum of the latest twenty distinct dated normalized rows with usable `foreign_net_volume` | shares | Selected-symbol indicators |

StockClock also accepts documented/case-compatible aliases, but the 2026-07-17 live rows used the six raw names above. Across 88 live rows, every direct volume net equalled buy volume minus sell volume and every direct value net equalled buy value minus sell value. Direct provider net remains authoritative when supplied; the arithmetic path is a null-safe compatibility rule, not a second source.

The unit decision is supported by the official field names/descriptions and sample scale, plus the live unchanged raw-to-normalized values. As a secondary check, FPT's latest foreign buy/sell value per share was approximately VND 67,622/VND 67,671 against a VND 67,000 close. StockClock performs no multiplication or division when storing these fields.

### History, date, and finality semantics

- `fromDate`/`toDate` are calendar-date bounds; returned `TradingDate` is the authoritative exchange trading date. StockClock does not create row dates from fetch time and does not synthesize weekend/holiday rows.
- The fetcher chunks broad calendar ranges, pages each chunk, sorts ascending, and deduplicates by normalized provider date. A same-date duplicate is replaced deterministically by the later encountered normalized row.
- The service currently requests a 28-calendar-day lookback, retains at most 20 foreign-history rows, and computes 5/20 sums from the latest rows with usable net volume. These are StockClock rolling aggregates, not SSI-supplied 5D/20D fields.
- The latest provider trading date is included whenever it has usable net volume. For FPT, the verified 5-row window was 2026-07-13 through 2026-07-17; the 20-row window was 2026-06-22 through 2026-07-17. Both included 2026-07-17.
- Daily history contains buy, sell, and net separately for both volume and value. The current public indicators aggregate only net volume; historical buy/sell/value rows are normalized internally but are not yet exposed through a dedicated history API.
- Sixty-session retrieval is **supported through the documented date range and paging shape**, but is not implemented in the current 28-day/20-row service path. Phase 4.12B must choose a bounded calendar lookback/page budget and require complete-session counts rather than assuming 60 calendar days equals 60 sessions.
- Production naming should be `daily_available`. The proof observed stable post-close rows, but neither the package nor response supplies an explicit finality flag. Do not publish `historical_final` or call the latest row realtime from this evidence alone.

### Zero, null, missing, and unavailable

- Official SSI documentation includes explicit zero strings for all six foreign fields; deterministic parsing preserves numeric zero as `0`/`0.0`.
- Omitted keys, null, empty strings, known null tokens, and unparsable values normalize to `null`. Net remains null when direct net is absent and either buy or sell is unavailable.
- A missing trading-date row remains absent. StockClock does not create a zero row for a non-trading day or missing provider record.
- Provider/network/status failure remains an `unavailable` result and is not added to rolling windows or rankings as zero.

### Gate decision

Primary outcome: **A - GO: FULL SYMBOL DAILY CONTRACT**.

The verified daily contract contains buy/sell/net volume and value, provider trading date, shares/VND units, usable multi-date rows, deterministic ordering/deduplication, and neutral `daily_available` finality semantics. Proceed to **Phase 4.12B - Historical Symbol Foreign-Flow API**. Keep current-session fields unavailable until a separate active-session proof establishes cumulative semantics, timestamps, reset behavior, and reconciliation.

## User questions

| Question | Required data | Preferred answer surface | Minimum useful answer | User action | Misleading interpretation to avoid |
| --- | --- | --- | --- | --- | --- |
| What are foreign investors doing now? | Official current cumulative buy/sell/net, time, finality | Summary cards | Direction, amount, source, age, provisional label | Continue to rankings or a symbol | Treating provisional counters as final |
| Where is activity concentrated? | Coverage-aware symbol values, basket membership | Ranked buyers/sellers and concentration | Top covered symbols plus aggregate coverage | Compare symbols | Ranking partial data as a complete market view |
| Is it persistent or temporary? | Ordered accepted daily history | 5/20/60 summaries and streak text | One-session value plus at least one trend window | Inspect history | Treating one session as a durable trend |
| Is it material relative to liquidity? | Official flow value and compatible official traded value | Ratio column/card | Ratio or explicit unavailable reason | Compare across liquidity levels | Estimating missing values or dividing by incompatible turnover |
| How is price reacting? | DailyOhlc close/change aligned to final flow date | Aligned price/flow chart or compact state | Date-aligned descriptive state | Inspect context | Presenting correlation as causation |
| Can the data be trusted? | Source, timestamps, state, coverage, failures | Compact trust strip with details on demand | Finality, age, source, covered/expected | Decide whether to rely on the view | Hiding missing components or stale data |
| What changed in my watchlist? | Bounded multi-symbol summary and previous final/current values | Sortable watchlist columns | Largest changes, reversals, unavailable rows | Open affected symbol or later create alert | One HTTP request per symbol or silently dropped rows |

## User segments

| Segment | Goal and workflow | Required metrics and filters | Acceptable latency and history | Likely later alerts | Non-essential initially |
| --- | --- | --- | --- | --- | --- |
| Market scanner | Open overview, scan rankings, compare VN30/HOSE, inspect a symbol | Net buy/sell, value if official, coverage, top/bottom, unusual activity | Current snapshot within the verified source cadence; 20 sessions for comparison | Aggregate reversal, top-rank entry | Export, advanced anomaly score, sector heatmap |
| Watchlist or portfolio monitor | Load followed symbols, sort/filter, inspect changes | Buy/sell/net, 5-session sum, materiality, trend, freshness | One bounded watchlist response; 20-60 final sessions | Threshold, reversal, streak, top-rank entry | Full-market history and reports |
| Single-symbol analyst | Open symbol, compare daily flow with price/liquidity, review room separately | Current and final flow, 5/20/60, streak, ratios, price reaction, trust | Fast cached latest result; 60 final sessions | Symbol threshold, reversal, unusual magnitude | Market-wide sector tooling |

## Product navigation and preserved state

1. **Scan:** `/vietnam` opens a foreign-flow summary and top buyers/sellers for the selected supported scope.
2. **Compare:** the user filters or sorts the existing watchlist table. Active preset/custom watchlist, sort, filters, and the last successful rows remain visible during refresh.
3. **Inspect:** selecting a row opens the symbol foreign-flow detail while retaining the originating scope and watchlist state. Foreign room is a separate collapsed context.
4. **Monitor:** a later alert links to the same symbol detail and preserves the scope/date encoded in the link. Returning restores the prior scan/filter state where the current frontend state model permits it.

No new route is required for the first UI release if the selected-symbol disclosure can host the detail. A dedicated route can be evaluated in Phase 4.13A if deep links and history navigation justify it.

## Product surfaces

### 1. Foreign-flow summary

The summary contains only verified scopes. P0 is VN30; HOSE follows in P1 after the scale gate.

- Covered-scope foreign buy, sell, and net volume.
- Buy, sell, and net value only when official values exist for the covered rows.
- Watchlist aggregate for the currently loaded watchlist.
- Last provider update, app fetch time, finality, availability, and coverage.
- A neutral market-closed state showing the latest accepted `daily_available` row or a stale last-known current snapshot with its label.

State behavior:

- `ready`: show metrics, source/finality, and complete coverage.
- `partial`: show the computed covered subset and `covered / expected`; never imply a complete aggregate.
- `stale`: preserve last-known metrics with age and reason.
- `unavailable`: show no metric-shaped placeholders and retain other dashboard data.
- `market_closed`: prefer the latest accepted daily aggregate when one is implemented; a retained provisional snapshot remains labelled stale/last known.
- Missing value fields: keep value cards absent or explicitly unavailable while valid volume remains visible.

### 2. Top buyers and sellers

- Two compact ranked lists, default top 10 and bounded maximum 50.
- Rank by verified `foreign_net_value` when the selected mode is value and coverage supports it; otherwise allow an explicit volume mode.
- Never mix value-ranked and volume-ranked rows.
- Include ticker, net metric, price change, state, and updated time.
- Concentration is `sum(abs(net metric) for top N) / sum(abs(net metric) for covered symbols)` and is P1.
- Partial coverage remains visible beside the list.

### 3. Watchlist foreign-flow table

Default columns:

`Symbol | Current price | Price change % | Foreign net | 5-session cumulative | State | Updated`

Optional desktop columns:

`Foreign buy | Foreign sell | Net flow / traded value | 20-session cumulative | 60-session cumulative | Streak | Price reaction | Source`

Rules:

- Current price and price change remain SSI DailyOhlc fields.
- Default net mode is value only if official value coverage is usable; otherwise volume with an explicit unit label.
- Sort: net value, net volume, materiality, 5/20/60 cumulative, freshness, symbol.
- Filters: net buy, net sell, high participation, reversal, persistent buy, persistent sell, unusual activity, partial/unavailable.
- Mobile shows symbol, net, 5-session trend, and state; secondary fields open in row detail.
- `null` renders as a reason-aware em dash, not zero. Stale values remain visible with a stale label.
- The frontend obtains all rows from the existing bounded watchlist response or one bounded batch response, never one HTTP request per symbol.

### 4. Symbol foreign-flow detail

The smallest P0 design is summary cards plus one aligned daily chart and a compact history table:

- Cards: latest final or current provisional buy/sell/net, 5/20/60 cumulative, source, state, and updated time.
- One chart: signed daily net bars with DailyOhlc close on an aligned second scale. The chart labels association only; it does not calculate or imply causation.
- History table: date, buy, sell, net, unit, finality, and quality.
- P1 additions: materiality, streak, reversal, unusual magnitude, and price-reaction state.
- Foreign room appears in a separate section with its own SSI `R` source/state and must not share a flow series.

### Alerts (Phase 4.13B)

| Alert | Inputs and threshold | Cooldown/dedup | Provisional/final rule | Required state | Neutral copy | Main false-positive risk |
| --- | --- | --- | --- | --- | --- | --- |
| Fixed net threshold | Official net value or volume crosses user threshold | Once per symbol, metric, direction, session, and threshold; configurable cooldown | Provisional notice may update; final notice deduped separately | Ready or partial with symbol data | `Foreign net flow crossed your configured threshold.` | Counter correction near threshold |
| Materiality threshold | `abs(foreign_net_value_ratio)` crosses threshold | Same session and threshold bucket | Only when compatible official denominator exists | Ready | `Foreign net flow reached X% of traded value.` | Low turnover distortion |
| Reversal | Current sign differs from prior final and passes minimum magnitude | Once per symbol/session/direction | Provisional labelled; final confirms or clears | Ready with two aligned sessions | `Foreign net flow changed from selling to buying.` | Small values near zero |
| Buy/sell streak | Consecutive final sessions reaches configured count | Once per new streak length | Final rows only | Historical final and complete window | `Foreign net buying has continued for N sessions.` | Missing session hidden as continuity |
| Unusual magnitude | Absolute net exceeds verified 20-session comparison rule | Once per symbol/session and severity bucket | Provisional labelled; daily row recomputed | Ready with 20 valid accepted daily rows | `Foreign net flow is large relative to its recent history.` | Outlier-dominated history |
| Top-rank entry | Symbol enters configured top N for a supported scope | Once per scope/symbol/session; cooldown on re-entry | Separate provisional/final events | Aggregate coverage above gate | `Ticker entered the covered-scope top foreign net buyers.` | Partial universe reshuffles rank |
| VN30 direction change | Aggregate net sign changes and minimum magnitude passes | Once per session/direction | Final confirmation can supersede provisional | Coverage gate passed | `Covered VN30 foreign net flow changed direction.` | Membership or missing-component changes |

The existing alert and notification infrastructure is reusable, but the alert-infrastructure gate must prove rule persistence, target semantics, cooldown, deduplication, and links before any foreign-flow rule is enabled.

## Canonical metric contract

The plan adopts current repository naming to avoid parallel aliases:

| Field | Unit | Sign/precision | Null rule | Planned authority |
| --- | --- | --- | --- | --- |
| `foreign_buy_volume` | shares | Nonnegative integer | Null when absent | Verified SSI DailyStockPrice daily source; current-session authority remains unproven |
| `foreign_sell_volume` | shares | Nonnegative integer | Null when absent | Same as buy volume |
| `foreign_net_volume` | shares | Signed integer; positive means net buy | Null unless official net exists or both official buy and sell volume exist | Same as buy/sell volume |
| `foreign_buy_value` | VND | Nonnegative provider precision; UI may compact | Null when absent | Verified official field only |
| `foreign_sell_value` | VND | Nonnegative provider precision; UI may compact | Null when absent | Verified official field only |
| `foreign_net_value` | VND | Signed provider precision; positive means net buy | Null unless official net exists or both official buy and sell value exist | Verified official field only |
| `traded_value` | VND | Nonnegative | Null until a compatible same-scope denominator is verified | Exact denominator scope remains pending a later implementation gate |

Deriving net as `buy - sell` is allowed only when both official fields for the same symbol, session, source, unit, and finality are present. A derived net must carry `calculation_basis=official_buy_minus_sell`; one-sided input remains null. API values remain raw units; display formatting is presentation only.

### Normalized metrics and priority

| Metric | Formula and lookback | Missing/quality guard | Liquidity/outlier behavior | Priority and use |
| --- | --- | --- | --- | --- |
| 5/20/60 cumulative net | Sum of valid ordered accepted-daily `foreign_net_value`; volume counterpart remains separately named | Null unless all required sessions are present; expose covered count | No outlier removal | P0 trend context |
| `foreign_net_value_ratio` | `foreign_net_value / traded_value` for one aligned row | Null unless numerator and compatible positive denominator exist | Mark low-liquidity caution under a verified threshold; never cap the raw ratio | P1 cross-symbol materiality |
| Buy participation | `foreign_buy_value / traded_value` | Same value/denominator gate | Same caution | P1 activity composition |
| Sell participation | `foreign_sell_value / traded_value` | Same value/denominator gate | Same caution | P1 activity composition |
| Net volume ratio | `foreign_net_volume / total_traded_volume` from compatible official fields | Null on missing/nonpositive denominator | Low-volume caution | P1 when value is unavailable |
| Current magnitude vs 20-session average | `abs(current net) / mean(abs(net))` over 20 accepted daily sessions | Null below 20 complete daily rows; retain direction separately | Expose outlier influence; do not winsorize silently | P1 unusual-activity explanation |
| Consecutive buy/sell sessions | Count backward over strictly positive or negative final net | Zero breaks streak; missing row makes the result partial | Not liquidity adjusted | P1 persistence |
| Positive-session count | Count `net > 0` in complete 5/20-session window | Null if the window is incomplete | Not liquidity adjusted | P1 trend balance |
| Reversal flag | Current sign differs from previous aligned final sign and passes verified minimum magnitude | Null on missing prior/current row | Magnitude guard prevents near-zero flips | P1 watchlist monitoring |
| Top-N concentration | Sum of absolute top-N net / total absolute net across covered components | Null if coverage gate fails or denominator is zero | Report N and scope coverage | P1 overview concentration |
| Recent percentile | Percentile rank of signed or absolute net in a documented 60-session window | Null below complete lookback | Display outliers without rewriting them | P2 advanced comparison |
| Recent z-score | `(current - mean) / standard deviation` over a documented 60-session window | Null below complete lookback or zero deviation | Show as statistical context only | P2 anomaly tooling |

Value and volume series are never combined into one cumulative or ranking metric. Every trend includes `metric_kind=value|volume`, `unit`, `window_sessions`, and coverage.

## Neutral price-reaction model

The model requires a foreign-flow row and DailyOhlc price change aligned to the same trading date.

| Flow | Price | Display state |
| --- | --- | --- |
| Net buy | Up | `Flow and price moved in the same positive direction.` |
| Net buy | Down | `Foreign buying occurred while price declined.` |
| Net sell | Down | `Flow and price moved in the same negative direction.` |
| Net sell | Up | `Foreign selling occurred while price increased.` |
| Zero | Any | `Provider reported zero net foreign flow.` |
| Missing or date mismatch | Any | `Price/flow comparison unavailable.` |

An optional note that other demand may have absorbed selling is an explicitly labelled inference, never a fact. The model does not produce an instruction, target, prediction, or confidence score.

## State model

Do not compress lifecycle, finality, aggregation, and market session into one field.

| Dimension | Values | Meaning |
| --- | --- | --- |
| `availability_status` | `loading`, `ready`, `partial`, `stale`, `unavailable` | Whether usable requested data is present |
| `finality` | `daily_available`, future `current_provisional`, null | DailyStockPrice has no explicit final flag; a provisional state requires separate active-session proof |
| `market_state` | `active`, `market_closed`, `unknown` | Calendar/session display context; not data availability |
| `freshness_status` | `fresh`, `stale`, `unknown` | Age against the source-specific policy |
| `aggregation_status` | `complete`, `partial`, `unavailable`, null | Component completeness for basket/market scopes |

`market_closed` does not make a valid `daily_available` row unavailable. A future stale current snapshot may remain visible after close only as last-known provisional data with a clear age; the accepted daily row replaces it when available.

### Zero, null, missing row, and partial

- `0`: the provider explicitly returned zero, or net was validly calculated from two official equal values.
- `null`: a field was not supplied, not verified, not compatible, or unavailable.
- Missing row: no source record exists for the requested symbol/date; it is not a zero-flow session.
- `partial`: a row has some valid fields or an aggregate lacks one or more expected components.
- The UI never formats null, missing row, or incomplete aggregate as zero.

## Trust metadata

Every row or aggregate exposes these directly or through a nested `data_quality` object:

- `source` and logical `source_endpoint` (never a raw URL).
- `provider_updated_at`, when supplied.
- `fetched_at` and `snapshot_age_seconds`.
- `availability_status`, `finality`, `freshness_status`, and `market_state`.
- `aggregation_basis`.
- `expected_components`, `covered_components`, `missing_components`, and `coverage_ratio` for aggregates.
- `stale_reason` and sanitized `last_failure_class`.
- `metric_kind`, `unit`, and calculation basis for derived values.

No raw payload, token, credential, auth header, signed URL, account identifier, or unsanitized provider error enters the public contract.

## Scope hierarchy

### P0 symbol scope

- One symbol, current official snapshot only if separately verified, accepted daily rows, buy/sell/net, value and volume, 5/20/60 windows, source/freshness/finality, and neutral price reaction.
- Current data is unavailable rather than substituted until a separate active-session authority gate passes.
- Historical final remains usable independently of current availability.

### P0 VN30 scope after symbol capability

Source order:

1. A verified official SSI VN30 foreign-flow aggregate.
2. Otherwise, the sum of official per-symbol flow over the current SSI IndexComponents VN30 membership.

Required metadata:

- `aggregation_basis=official_aggregate` or `current_membership_component_sum`.
- Current membership source and fetch time.
- Expected, covered, missing, and duplicate component counts plus explicit missing symbols.
- Current-membership historical backfill must be labelled `current_membership_backfill`, not historically constituent-correct.
- Historically constituent-correct aggregation remains P2 until an authoritative dated membership source exists.
- Duplicate symbols are normalized once; a missing component creates partial coverage rather than a zero row.

Recommended presentation gate: `coverage_ratio=1` for complete. Any lower ratio is visibly partial. A minimum publishable partial threshold is a Phase 4.12E evidence decision; below it the aggregate is unavailable, not extrapolated.

### P1 HOSE scope after VN30

Two strategies must be verified in order:

1. Official SSI market-wide foreign-flow aggregate.
2. Sum of symbol-level official flow over a verified SSI Securities HOSE universe.

HOSE component summation must not ship until Phase 4.12F proves universe authority, bulk-fetch behavior, provider budget, bounded concurrency, timeout, partial thresholds, suspended/no-data handling, and snapshot consistency. Without bulk capability, use scheduled/materialized daily rows or keep HOSE unavailable; do not issue an unbounded request fan-out.

### P1 sector scope

Sector aggregation is P1, not MVP. It uses only existing authoritative SSI sector/industry metadata when a defined coverage gate passes. If classification coverage or taxonomy stability is insufficient, the section stays deferred. This plan adds no classification provider.

## Remaining capability gates after Phase 4.12A-Lite

Phase 4.12A-Lite completed the DailyStockPrice daily-symbol gate as bounded diagnostic/documentation work. The following current-session, bulk, and aggregate questions remain separate future gates; they do not reopen the verified daily mapping.

### Questions by candidate source

| Candidate | Verify | Boundary |
| --- | --- | --- |
| DailyStockPrice | Bulk behavior, active-session updates, explicit final timing/corrections, larger-window performance, and rate limits | Verified `daily_available` symbol authority; current authority only if observed and documented |
| `X` | Whether explicit cumulative foreign fields exist, update cadence, reset/session behavior, timestamps | Quote snapshot only unless explicit official flow fields and semantics are proven; never a candle |
| `X-TRADE` | Whether foreign participant identity is explicitly present and stable | Recent trade events only; no inferred participant, history reconstruction, or candle aggregation |
| `R` | Confirm room fields, units, timestamp, and continued isolation | Foreign room only; never used as foreign flow |
| `MI` | Whether an explicit official index/market foreign aggregate exists and its scope | Market-index context only unless a separately named, documented aggregate is proven |
| Other installed FC Data endpoints | Enumerate official methods/signatures and identify documented foreign-flow candidates | No speculative runtime endpoint probing |

### Bounded evidence matrix

- Symbols: FPT plus a small second HOSE symbol; VN30 only after symbol proof.
- Dates: one recent completed session, a bounded 60-session request or provider maximum, and one active-session sample only during a real market window.
- Record: normalized field names, raw field-name whitelist, units, row counts, first/last dates, timestamps, status/finality observations, pagination, rate-limit/failure class, and whether values are explicit.
- Never print credentials, headers, tokens, raw payloads, raw URLs, or account data.
- Stop on rate limit or repeated authorization/network failure and report the gate as unresolved.

### Gate outcomes

- **Historical-source gate:** passed for bounded symbol `daily_available` rows; fields, units, date identity, and date-range/paging feasibility are verified. Explicit provider-final/correction semantics remain excluded from claims.
- **Current-session-source gate:** pass only when an official cumulative current source, timestamp, reset behavior, and session boundary are observed. Otherwise current remains unavailable.
- **Volume/value gate:** each metric passes independently. Missing value does not block verified volume product paths.
- **Bulk-fetch gate:** pass only with an official bounded bulk shape or a measured provider budget safe for the target scope.

## Source authority and reconciliation

### Historical authority

Planned authority is the verified official SSI DailyStockPrice daily row. Accepted rows are keyed by symbol and provider trading date, carry `daily_available`, retain source metadata, and are not replaced by stream snapshots.

### Current-session authority

Planned authority is a verified official cumulative current snapshot/stream field. It is labelled `current_provisional`. If no candidate passes the separate active-session gate, current fields are unavailable and the product shows the latest accepted daily row instead. `R`, inferred X-TRADE participation, and price-derived values are never substitutes.

### Post-close reconciliation

1. Retain the last provisional buy/sell/net snapshot and its timestamp.
2. Fetch the official accepted daily row under the normal provider/cooldown policy.
3. Compare like field, unit, symbol, and session date.
4. Record absolute and percentage differences, with percentage null when the final denominator is zero.
5. Promote the accepted daily row as authority while preserving bounded reconciliation diagnostics.
6. Increment reconciliation and mismatch counters; do not silently hide a threshold breach.

Planned diagnostics: provisional/daily buy and sell, absolute difference, percentage difference, configurable absolute/relative mismatch thresholds, last reconciliation time, mismatch count, and counter-reset count. Threshold defaults require future active-session evidence and are not fixed here.

### Cumulative counter reset

- Detect a decrease within the same source/symbol/session/field.
- Preserve the latest raw cumulative snapshot and previous accepted snapshot.
- Do not emit a negative interval value or add the pre-reset and post-reset counters.
- Mark `counter_reset_detected`, make current state partial or stale as appropriate, debounce further interpretation until stable observations arrive, and increment the reset counter once per episode.
- Reconcile against the accepted DailyStockPrice row after close.

## Planned domain model

All names are proposed, pending capability verification, and not yet implemented.

- `ForeignFlowRow`: one symbol or official aggregate for one session; raw metrics, traded denominator, metric units, source, timestamps, availability, finality, and quality.
- `ForeignFlowSnapshot`: future current provisional row plus session/market state and optional latest accepted daily row.
- `ForeignFlowAggregate`: scope code/type, summed official fields, coverage, membership/universe metadata, ranking basis, and aggregation state.
- `ForeignFlowCoverage`: expected/covered/missing counts, ratio, missing symbols, duplicate count, and threshold result.
- `ForeignFlowTrend`: metric kind, 5/20/60 cumulative fields, valid-session counts, streak, reversal, comparison metrics, and lookback date span.
- `ForeignFlowDataQuality`: availability, finality, freshness, date alignment, source/calculation basis, stale/reset/reconciliation flags, and sanitized failure class.

Proposed common fields:

```text
scope_type: symbol | basket | exchange | sector
scope_code: FPT | VN30 | HOSE | <verified sector code>
session_date
foreign_buy_volume / foreign_sell_volume / foreign_net_volume
foreign_buy_value / foreign_sell_value / foreign_net_value
traded_value
availability_status / finality / market_state / freshness_status
source / source_endpoint / provider_updated_at / fetched_at / snapshot_age_seconds
aggregation_basis
coverage
data_quality
```

## Minimal API plan

These APIs are **planned, pending capability verification, and not yet implemented**.

### Symbol

`GET /api/v1/stocks/vn/foreign-flow/symbol/{ticker}`

Parameters:

- `sessions=60`, minimum 1 and maximum 260.
- `include_current=true`.
- `force_refresh=false` with existing cooldown/rate-limit guards taking precedence.

Response: ticker, current snapshot or null, latest `daily_available` row, bounded ordered history, 5/20/60 trends, price reaction, trust metadata, and state. Invalid ticker is 422; supported ticker with no data returns 200 with explicit unavailable state and empty history.

### Overview and rankings

`GET /api/v1/stocks/vn/foreign-flow/overview`

Parameters:

- `scope=VN30|HOSE` (HOSE enabled only after its gate).
- `metric=value|volume`.
- `date` optional; default latest/current per authority rules.
- `ranking_limit=10`, range 1-50.
- `force_refresh=false`.

Response: aggregate, coverage, top buyers, top sellers, concentration when enabled, source/membership basis, and trust metadata. Unsupported or gated scope returns a typed unavailable result rather than an alternate provider.

### Watchlist integration

Preferred P0: add an optional `foreign_flow_summary` object to each existing `/vn/watchlist` row and response-level foreign-flow coverage metadata. Preserve existing `foreign`, `ssi_foreign_net_volume`, and indicator fields for compatibility during a documented transition.

If backend size/latency evidence rejects additive enrichment, use one alternative product API design, not one call per symbol:

`POST /api/v1/stocks/vn/foreign-flow/batch`

The request accepts at most the existing 30-symbol watchlist limit. Symbols are uppercase-normalized, deduplicated in first-seen order, invalid symbols are reported, and every valid requested symbol produces either a row or an explicit unavailable result. Partial provider failures do not fail successful symbols.

### N+1 and provider budget

- Frontend: one watchlist or batch HTTP request.
- Service: request-local memoization plus the shared process cache; identical in-flight keys coalesce.
- Provider: prefer an official bulk source. If absent, use bounded sequential or evidence-approved low concurrency, count calls, respect SSI cooldowns, and never broaden to HOSE until the scale gate passes.
- Cache keys include source, scope/symbol, session date, finality, metric kind, lookback, membership version, and provider parameters that affect identity.

## Cache and persistence plan

TTL values remain configurable and must be finalized against verified provider cadence. Initial classes align with existing repository patterns:

| Class | Starting policy | Stale/error behavior |
| --- | --- | --- |
| Accepted daily | Long-lived by symbol/date; latest correction window refreshable | Preserve prior daily row; a source correction creates an observed replacement, not silent provisional overwrite |
| Current positive | Short active-session TTL in the existing 5-15 second live/cache class | Serve last-known as stale with age on transient error |
| Current empty | Very short active-session TTL in the existing 5-second class | Do not hammer provider; remain explicit empty/unavailable |
| Current negative/unavailable | Short negative TTL in the existing 10-60 second class, respecting provider cooldown | No fallback; expose sanitized failure class |
| VN30 aggregate | Same or slightly longer than component current TTL; membership cached by existing 300/60 pattern | Preserve covered stale aggregate with old membership/time labels |
| HOSE aggregate | Evidence-based, longer than VN30 if computed | Never extrapolate partial coverage |
| Component/universe list | Reuse existing positive/negative list-cache conventions | Stale list only with visible version/time and no constituent-correct historical claim |

`force_refresh` bypasses ordinary freshness but not rate-limit cooldown, in-flight ownership, or safety limits. Final-row immutability is logical: corrections are versioned/observed and replace authority only with source evidence.

### Persistence decision framework

Phase 4.12A-C default to provider-on-demand plus bounded process cache; no new database is assumed.

- Choose on-demand/cache when SSI supplies adequate 60-session history and request budgets are safe.
- Consider a local durable daily store only if backfill cost, correction tracking, alert evaluation, or aggregate scale cannot meet requirements on demand.
- Consider a snapshot/event store only if a verified current cumulative source needs restart continuity; operational stream snapshots are not historical flow rows.
- Reuse the repository SQLAlchemy layer only after schema ownership, migration, retention, correction, multi-worker, and deployment persistence gates pass.
- Render's ephemeral filesystem means a local file alone cannot be assumed durable.

## Observability plan

Extend `GET /api/v1/stocks/vn/observability` conceptually with a bounded worker-local `foreign_flow` block:

```text
historical_status / current_status
provider_calls / cache_hits / cache_misses / coalesced_waiters
stale_recoveries / partial_aggregate_count
reconciliation_count / reconciliation_mismatch_count / counter_reset_count
last_success_at / last_failure_class
latest_vn30_coverage / latest_hose_coverage
```

Metrics are source- and scope-labelled, bounded, sanitized, and explicitly worker-local. Logs include operation, safe scope, symbol count, duration, row count, cache outcome, finality, coverage, and failure class. They exclude raw payloads and secrets.

## Priority and smallest useful MVP

### P0

- Verified symbol current buy/sell/net when an official current source exists.
- Historical final symbol flow and separate volume/value fields when official.
- 5/20/60 cumulative metrics with complete-window counts.
- Watchlist additive summary, explicit state, sorting, and no HTTP N+1.
- Top buyer/seller ranking.
- Coverage-aware VN30 aggregate.
- Source, finality, freshness, and coverage metadata.

### P1

- Materiality and participation ratios after denominator proof.
- Unusual magnitude, streaks, reversals, and price-flow comparison.
- HOSE aggregate after bulk/scale gate.
- Sector summary after classification gate.
- Foreign-flow alerts using existing infrastructure after its gate.

### P2

- Matched versus negotiated breakdown when official fields and semantics are verified.
- ETF/index-review context and historically constituent-correct VN30.
- Percentiles, z-scores, and advanced anomaly analysis.
- CSV export, periodic reports, and deeper ownership/room analysis.

### Four-block MVP acceptance

1. **Summary:** valid VN30 or watchlist aggregate with source/finality/coverage; loading does not blank unrelated daily data; unavailable has no fake metrics.
2. **Top buyers/sellers:** bounded, unit-consistent rankings with partial coverage visible.
3. **Watchlist table:** one frontend request, stable prior rows during refresh, explicit null/stale states, responsive core columns.
4. **Symbol detail:** latest/current distinction, 5/20/60 history, one aligned neutral chart, and separate foreign-room context.

Explicit exclusions: advanced alert engine, sector heatmap, historical membership reconstruction, negotiated split without proof, new database without need, prediction, external provider, provider fallback, and any stream-to-chart or X-TRADE candle path.

## Delivery roadmap

### Phase 4.12A-Lite - DailyStockPrice contract confirmation (completed)

- Outcome: full symbol daily contract verified for DailyStockPrice; no production backend or frontend changed.
- Verified: exact six foreign fields, shares/VND units, provider trading dates, multi-date buy/sell/net volume/value rows, direct-net agreement, 5/20 construction, latest-date inclusion, zero/null/missing/unavailable separation, and date-range/paging feasibility for a future 60-session request.
- Neutral boundary: use `daily_available`; active-session cumulative behavior, explicit provider finality/corrections, bulk behavior, and aggregates remain unresolved.
- Next: Phase 4.12B may implement only the verified historical symbol contract.

### Phase 4.12B - Historical symbol foreign-flow API (M)

- Goal/value: deliver source-aware `daily_available` rows and 5/20/60 trend for one symbol.
- Backend: normalized models/service/schema, one bounded symbol endpoint, cache and compatibility mapping.
- Frontend: none beyond API typing if needed for contract proof.
- Source: Phase 4.12A-Lite-approved SSI DailyStockPrice daily source.
- Likely files: `src/services/vietnam_foreign_flow_service.py`, `api/v1/schemas/stocks.py` or a scoped schema module, `api/v1/endpoints/stocks.py`, tests.
- Tests: mapping, units, zero/null, 60-session bounds, sign, missing rows, value absence, cache/stale-if-error, unchanged DailyOhlc price.
- Observability: historical calls/cache/duration/rows/failure.
- Risks: history limits and corrections.
- Exclusions: current session, aggregates, UI, alerts, database unless the gate requires it.
- Dependencies: historical-source and volume/value gates.
- Acceptance: endpoint returns ordered bounded `daily_available` rows and correct complete-window trends without fallback or price inference.

### Phase 4.12C - Current-session snapshot and final reconciliation (L)

- Goal/value: distinguish verified current provisional activity from final history.
- Backend: current source adapter/cache, state/freshness, counter-reset detection, post-close reconciliation, mismatch metrics.
- Frontend: API typing/status copy only if needed; full visualization remains later.
- Source: a separately approved active-session authority; phase is blocked if none exists.
- Likely files: foreign-flow service/schema/endpoints, startup-owned lifecycle only if the approved source is streaming, observability, focused tests.
- Tests: lifecycle/finality, no source path, reset, stale, market close, final delay/difference, reconciliation, no request-handler stream start.
- Observability: current health, age, reset, reconciliation and mismatch counters.
- Risks: cumulative semantics, restart continuity, and delayed accepted daily rows.
- Exclusions: R as flow, trade reconstruction, candle aggregation.
- Dependencies: current-session source gate and historical API.
- Acceptance: provisional never silently replaces final; reset cannot emit false negative intervals; unavailable current preserves final history.

### Phase 4.12D - Watchlist integration and rankings (L)

- Goal/value: compare followed symbols and find the largest covered flows in one request.
- Backend: additive watchlist summary or bounded batch alternative, rankings, request-local reuse/coalescing, response coverage.
- Frontend: columns, filters, sorting, stable refresh state, unit/finality/trust labels, responsive layout.
- Source: approved symbol historical/current service.
- Likely files: Vietnam service/schemas/endpoints, `apps/dsa-web/src/api/stocks.ts`, dashboard/components/tests.
- Tests: max 30, normalization, duplicates, invalid/missing rows, partial failure, no HTTP N+1, stale response protection, mobile states.
- Observability: batch size, provider budget, cache/coalescing, partial results.
- Risks: payload density and provider latency.
- Exclusions: HOSE, sector, alerts.
- Dependencies: Phase 4.12B; Phase 4.12C for current columns.
- Acceptance: all valid requested symbols are represented, previous rows survive refresh, and the frontend makes one logical data request.

### Phase 4.12E - VN30 aggregation with coverage (L)

- Goal/value: provide a trustworthy current-basket aggregate and rankings.
- Backend: official aggregate if verified, otherwise SSI IndexComponents plus symbol sums, coverage/membership basis, scoped cache.
- Frontend: VN30 summary/rankings and explicit complete/partial/unavailable states.
- Tests: membership identity, duplicates, missing components, coverage thresholds, current-membership backfill labels, unit consistency.
- Observability: membership version, component counts, coverage, aggregate duration/failures.
- Risks: partial data and historical membership misstatement.
- Exclusions: historically constituent-correct reconstruction and HOSE.
- Dependencies: symbol service, bulk gate, VN30 membership gate.
- Acceptance: no aggregate lacks coverage metadata; current-membership history is not labelled constituent-correct.

### Phase 4.12F - HOSE aggregation and scale hardening (XL)

- Goal/value: extend the proven model to market scope without unsafe call bursts.
- Backend: official aggregate or verified universe, bulk/materialized strategy, bounded scheduling/concurrency, timeouts, coverage and snapshot consistency.
- Frontend: HOSE scope switch and market partial/stale states.
- Tests: large universe bounds, suspended/no-row symbols, partial thresholds, rate limits, timeout, multi-worker/process cache assumptions.
- Observability: universe size/version, calls, duration, coverage, throttling, stale recovery.
- Risks: N+1 scale, rate limits, inconsistent capture times.
- Exclusions: sector and historical membership unless separately gated.
- Dependencies: HOSE universe, bulk/scale, persistence decisions.
- Acceptance: measured safe provider budget and coverage-aware result; otherwise HOSE remains unavailable.

### Phase 4.13A - Symbol and watchlist visualization (L)

- Goal/value: implement the four-block product with an aligned neutral chart.
- Backend: no new authority; consume 4.12 APIs.
- Frontend: summary, rankings, table, symbol chart/history, mobile layout and accessibility.
- Tests: loading/partial/stale/unavailable/closed, null not zero, source/finality, navigation/state preservation, chart alignment.
- Risks: density and overinterpretation.
- Exclusions: predictions, new data source, alert engine.
- Dependencies: 4.12D/E and stable schemas.
- Acceptance: users can scan, compare, inspect, and return without losing state; no more than four primary blocks.

### Phase 4.13B - Alerts and advanced analytics (XL)

- Goal/value: monitor meaningful changes with bounded noise.
- Backend/frontend: approved foreign-flow alert types, configuration UI, history/links, optional P1 analytics.
- Tests: threshold, cooldown, dedup, provisional/final correction, partial-state suppression, delivery failure isolation.
- Observability: evaluations, suppressions, triggers, corrections, delivery outcomes.
- Risks: false positives and notification fatigue.
- Exclusions: automatic trading and advice.
- Dependencies: stable current/final model and alert-infrastructure gate.
- Acceptance: alerts are reproducible, state-aware, deduplicated, and link to evidence.

## Decision gates

| Gate | Required evidence | Blocked work if unresolved |
| --- | --- | --- |
| Volume/value fields | Exact SSI fields, units, null/zero, net basis, multiple sample rows | Value UI/ratios/rankings; verified volume may continue |
| Historical source | Date/finality/correction, at least 60 sessions or backfill design | 4.12B onward |
| Current-session source | Active-window cumulative behavior, timestamp, reset/session boundary | 4.12C and current UI/alerts |
| Bulk fetch | Official shape or measured safe per-symbol budget | VN30/HOSE scale and rankings scope |
| VN30 membership | Exact SSI IndexComponents identity/version and missing behavior | 4.12E |
| HOSE scale | Authoritative universe, provider budget, timeout/concurrency, partial threshold | 4.12F |
| Persistence | History availability, correction/backfill cost, alert needs, durable deployment storage | Any new table/database |
| Alert infrastructure | Rule model compatibility, persistence, cooldown/dedup, links, delivery isolation | 4.13B |

## Risk register

| Risk | Severity | Likelihood | Detection | Mitigation | Phase owner |
| --- | --- | --- | --- | --- | --- |
| Field-name ambiguity | High | Medium | SDK/schema and sample comparison | Whitelist exact verified fields; fixture lock | 4.12A |
| Unit ambiguity | High | Medium | Cross-row magnitude and official documentation | Per-field units; block unclear field | 4.12A |
| Missing value fields | Medium | High | Coverage counters | Preserve null; volume-only mode | 4.12A/B |
| Provisional/final mismatch | High | Medium | Reconciliation differences | Final authority plus visible counters | 4.12C |
| Cumulative counter reset | High | Medium | Monotonicity check | Reset state; no interval emission; final reconcile | 4.12C |
| VN30 membership history | High | High | Compare dated/current membership availability | Label current-basket backfill; defer constituent-correct history | 4.12E |
| HOSE request scale | High | High | Profile calls/duration | Bulk/materialization or remain unavailable | 4.12F |
| No bulk endpoint | High | Medium | Installed SDK and bounded probe | Cache/coalesce/low concurrency; block HOSE fan-out | 4.12A/F |
| Rate limiting | High | Medium | Failure class/cooldown counters | Existing guards, pacing, no force-refresh bypass | All implementation phases |
| Snapshot inconsistency | High | Medium | Per-component provider times and capture span | Bounded capture window and visible basis | 4.12E/F |
| Low-liquidity ratio distortion | Medium | High | Denominator/quality rule | Caution or suppress ratio under verified guard | 4.12D/4.13A |
| Partial aggregate mistaken as complete | High | Medium | Coverage assertions | Always return/display coverage; no extrapolation | 4.12E/F |
| Authorization/network transient failure | Medium | Medium | Sanitized failure class | Stale-if-error, backoff, preserve accepted daily rows | All implementation phases |
| Zero/null confusion | High | Medium | Contract and UI tests | Typed null semantics and explicit zero tests | 4.12B/D |
| Stale shown as current | High | Medium | Age/freshness tests | Source-specific TTL and visible stale label | 4.12C onward |
| User overinterpretation | Medium | High | Copy review | Neutral descriptions, finality/source context | 4.13A/B |
| Table density | Medium | High | Responsive/UI tests | Default/optional columns and disclosure | 4.12D/4.13A |
| Mobile readability | Medium | Medium | Narrow viewport tests | Four core row fields and drill-down | 4.13A |

## Known limitations of this plan

- Current-session SSI foreign flow is not yet proven; this phase ran after close.
- DailyStockPrice has no explicit provider finality flag. Use `daily_available` even though the bounded post-close repeat was stable.
- Sixty-session access is feasible through official date ranges/paging but is not implemented or performance-profiled in the current 28-day/20-row service path.
- The four verified symbols had complete value fields, but production null handling remains mandatory because provider coverage can vary.
- VN30 official aggregate capability and HOSE aggregate/bulk capability are unknown.
- Sector classification coverage is insufficiently proven.
- Exact TTLs, mismatch thresholds, liquidity guards, and partial-coverage publish thresholds require capability and performance evidence.
- Natural SSI stream reconnect continuity is a separate existing acceptance item and is not redefined by this plan.

## Recommended next phase

Proceed with **Phase 4.12B - Historical Symbol Foreign-Flow API** using only the verified `daily_available` DailyStockPrice fields. Do not start the current-session adapter, aggregates, rankings, or UI until their independent current, bulk, membership, and scale gates have recorded evidence-backed outcomes.
