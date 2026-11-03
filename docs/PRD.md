# StockClock Product Requirements Document

## 1. Product overview

StockClock is a personal investment decision-support workspace for a Vietnam equity investor. Today it helps the investor inspect market conditions, monitor relevant tickers, and research historical price and participation using source-aware data. The long-term direction is to help the same person understand portfolio risk and review their own investment decisions and trading discipline. Those journeys are proposals. [Capability status and acceptance](PROJECT_STATE.md) · [Active roadmap](VN_DASHBOARD_ROADMAP.md)

## 2. Problem statement

General market views help answer what moved. A personal workflow also needs to answer what matters to the investor's watchlist, whether a move is broad or concentrated, and whether the evidence is fresh and complete enough to investigate further. Comparing disconnected screens and rechecking unavailable inputs makes that workflow harder. StockClock should help the investor choose what to inspect, which conclusions to qualify, and which configured changes merit a closer look. These are product assumptions to validate through use.

## 3. Target users

The primary user is an individual investor who follows Vietnamese equities and operates StockClock for personal use. They bring their own watchlist, investment judgment, and research process. The maintainer is a secondary audience for operational and technical documentation. Product scope is defined around the personal workflow. [Vietnamese product overview](VN_PRODUCT_OFFERING.md) · [Operations runbook](RUNBOOK_VN.md)

## 4. Value proposition

- **Personal relevance** comes from a saved list of relevant symbols, selected-stock context, and explicit alert rules.
- **Explainability and data trust** come from showing provider session, freshness, finality, and coverage alongside interpretable signals.
- **Less repeated checking** comes from one daily scan and completed-session alerts the user has chosen to enable.
- **Better decision review** is a proposed outcome of recording the evidence and rationale behind decisions and revisiting them later.

## 5. Primary use cases

| Journey | User outcome | Current entry or boundary |
| --- | --- | --- |
| Daily market review | Assess the latest usable session, participation, and foreign activity before drilling into tickers. | `/vietnam` and `/foreign-flow` |
| Personal watchlist monitoring | Load a saved list or SSI-derived VN30, sort and filter the scan, and configure relevant completed-session conditions. | `/vietnam` and `/alerts`. Custom VN lists are browser-local. Alert evaluation requires the scheduled worker. |
| Individual stock research | Inspect daily price, indicators, available issuer context, foreign flow, and relative performance with coverage visible. | Selected ticker on `/vietnam` and `/vietnam/company/:ticker`. Fundamentals and events are gated. |
| Market participation analysis | Inspect breadth, sector differences, and which members contributed to the view. | Current VN30 and current SSI ICB cohorts. Broader market coverage remains partial. |
| Historical exploration | Inspect daily chart history, supported 1m sessions, and accepted foreign-flow windows. | `/vietnam` and `/foreign-flow`. Historical scenario comparison is proposed. |
| Portfolio risk review | Understand concentration, drawdown, and missing valuation coverage for personal holdings. | Proposed VN workflow. |
| Trading journal and discipline | Record the decision, evidence, plan, and outcome, then revisit rule adherence. | Proposed VN workflow. |

[UI states](UI_STATES.md) · [API catalog](API_CATALOG.md)

## 6. Current capabilities

**VERIFIED CURRENT** means the implementation and applicable evidence support the stated scope. **PARTIAL** means an implemented surface has material coverage, performance, or acceptance limits. **PROPOSED** means a candidate needs a scope decision. **BLOCKED** means an identified prerequisite is missing. **DEFERRED** means existing roadmap guidance parks the work. These labels summarize [Project State](PROJECT_STATE.md), which owns capability status. Retained runtime observations extend through 2026-08-12. Current deployment and provider availability were outside this review.

| Capability | Classification | Evidence and boundary |
| --- | --- | --- |
| VN watchlist, daily charts, and technical context | VERIFIED CURRENT | Browser-local custom list and selected-symbol views. SSI daily price and Wilder/RMA RSI14, moving averages, Bollinger Bands, and liquidity context where inputs support them. Full-watchlist cold hydration remains a latency limitation. [Dashboard](../apps/dsa-web/src/pages/VietnamDashboardPage.tsx) · [Daily service](../src/services/vietnam_market_service.py) |
| Completed Foreign Flow | VERIFIED CURRENT | Symbol history, accepted-session signals, rankings, and current-membership VN30/Industry decomposition. Anomaly sessions are quarantined and historical constituent membership is unavailable. [Foreign Flow service](../src/services/vietnam_foreign_flow_service.py) · [Data contract](VN_DATA_CONTRACT.md) |
| Current Foreign Flow | VERIFIED CURRENT | Bounded 2026-08-10 symbol and current VN30/Industry acceptance. Current snapshots stay provisional and separate from completed history and alerts. Freshness depends on the shared stream. [Acceptance record](PROJECT_STATE.md#current-milestone-and-next-phase-boundary) |
| VN30 breadth, sector context, and selected-stock relative performance | VERIFIED CURRENT | Retained 2026-08-11 acceptance for VN30 breadth, current VN30/ICB groups, and exact-session VNINDEX/VN30 or same-ICB peer comparisons. Peer or window coverage can be partial or unavailable. [Acceptance record](PROJECT_STATE.md#historical-implementation-record) |
| Completed-session watchlist intelligence | VERIFIED CURRENT | Explicit foreign-flow, breadth, sector, and relative-strength rules use complete inputs and session deduplication. Retained 2026-08-12 acceptance covers one live completed-flow trigger and an unavailable relative-strength skip, with other rule cases covered by deterministic evidence. [Alert rules](alerts.md) · [Tests](../tests/test_vietnam_watchlist_alerts.py) |
| Company research, intraday, index history, and optional streaming | PARTIAL | Company research has SSI-backed blocks and explicit domain gaps. Today’s 1m bars are delayed and sparse. X-TRADE is a bounded event buffer. VNINDEX/DailyIndex completeness and optional X quotes, X-QUOTE order book, and MI advance/decline still have acceptance or coverage limits. [Company service](../src/services/vietnam_company_research_service.py) · [Data contract](VN_DATA_CONTRACT.md) |
| VN30 futures/basis, automated proprietary data, HOSE-wide breadth, and unsupported fundamentals/actions | BLOCKED | Provider or legal contracts, entitlement, and scalable authoritative universe acquisition remain gates as applicable. [Roadmap classifications](VN_DASHBOARD_ROADMAP.md#backlog-classification) |
| Proprietary expansion, broader stock-detail polish, macro/risk assets, and optional news expansion | DEFERRED | Manual verified proprietary EOD infrastructure is experimental with no accepted real financial row. Optional personal/local news has separate enablement and terms gates. [Project State](PROJECT_STATE.md) · [Decisions](DECISIONS.md) |

The repository also retains A-share, HK, and US workflows such as AI reports, portfolio, and backtest screens. Their presence is separate from VN product acceptance. The portfolio account API explicitly supports `cn`, `hk`, and `us`. [Inherited application overview](../README.md) · [Portfolio schema](../api/v1/schemas/portfolio.py)

## 7. Product scope and boundaries

- **A. Current product** covers personal VN market inspection and the scoped monitoring and research journeys above.
- **B. Near-term product** follows the active roadmap. Its six named milestones are completed and `NEXT` is unassigned. Eventual risk-mode synthesis is `LATER`. The approved direction is to operate within accepted data and runtime boundaries while the owner selects the next phase.
- **C. Product opportunities** are evaluated below as candidates. Approval requires a bounded user outcome, data and coverage evidence, and acceptance criteria.

Automatic trading, broker account actions, prescriptive buy/sell/hold calls, unverified predictions, fabricated market data, unsupported fundamentals, and unverified provider-derived metrics are out of scope. Public redistribution and commercial-scale requirements would need an evidenced need, provider rights, and a separate decision. [Active roadmap](VN_DASHBOARD_ROADMAP.md#active-roadmap) · [Product and provider decisions](DECISIONS.md)

## 8. Non-functional requirements

| Area | Requirement |
| --- | --- |
| Trust and explainability | Show source, provider session, freshness, finality, and coverage where applicable. Use neutral descriptions and preserve missing versus accepted zero. Keep delayed candles, streamed context, provisional flow, and completed history distinguishable. |
| Resilience | Preserve usable daily or completed views during optional capability failures. Expose stale or unavailable inputs and suppress incomplete or provisional completed-session alerts. |
| Performance | Bound provider fan-out, reuse validated caches, and measure cold and warm loads separately before setting a latency target. Keep daily scan and drill-down usable on desktop and mobile. |
| Security and maintenance | Keep credentials server-side, use sanitized diagnostics, and keep day-to-day operation and recovery manageable by one operator. Evaluate ongoing acquisition and retention costs before expanding scope. |

[Data contract](VN_DATA_CONTRACT.md) · [UI states](UI_STATES.md) · [Security and secrets](SECURITY_AND_SECRETS.md)

## 9. Product success metrics

The following are proposed acceptance measures for a representative personal workflow. Baselines, performance thresholds, and KPI results have yet to be established.

| Goal | Measure or acceptance check |
| --- | --- |
| Useful daily review | Record time, external lookups, and repeated manual refreshes from opening the workspace to identifying a watchlist item worth inspecting. Compare against the investor's own current workflow. |
| Understandable evidence | In a sampled review, the investor can identify each signal's source, session, whether it is provisional, and why coverage is partial. Every sampled unavailable metric remains distinct from a numeric zero. |
| Dependable monitoring | Replay an eligible completed-session match twice and observe one trigger for the same rule, scope, and session. Observe zero firings for provisional or incomplete inputs. With optional streaming or news unavailable, a separately usable daily view remains usable. |
| Sustainable operation | Record cold and warm latency, provider requests per journey, startup/recovery time, and operator time spent maintaining the workspace. Set budgets after observing the baseline. |
| Better decision review, if approved | Measure the share of reviewed decisions that link to their original evidence, rationale, and later outcome. |

[Test strategy](TEST_STRATEGY.md) · [Acceptance history](PROJECT_STATE.md)

## 10. Constraints and dependencies

SSI FastConnect V3 is the sole production VN market-data provider. Credentials, entitlement, session timing, and reachable transport determine availability. Completed historical aggregates and peer comparisons inherit current-cohort bias. Portfolio and historical simulation concepts need their own coverage and adjustment rules. Alert scheduling is operationally separate from serving the web UI, and coherent current flow assumes one backend worker. [SSI integration](SSI_FASTCONNECT_INTEGRATION.md) · [Architecture](ARCHITECTURE.md)

## 11. Proposed opportunities

All rows are **PROPOSED**. Value, complexity, and maintenance assessments are qualitative judgments for personal use. Existing prerequisites and roadmap blocks still apply.

| Candidate | Personal value | Available inputs | New data or evidence required | Complexity and reliability risk | Maintenance |
| --- | --- | --- | --- | --- | --- |
| Personal Portfolio Risk Engine | See concentration, exposure, and drawdown across owned positions. | VN daily prices and current cohort metadata. | VN holdings, cash and trades, valuation coverage, and corporate-action/adjustment rules. | High. Incomplete positions or stale marks can understate risk. | High. Reconciliation and valuation support. |
| Smart Watchlist Alerts | Reduce repeated checking of personally relevant conditions. | Existing four completed-session rule families, history, and deduplication. | User-defined priority, suppression policy, and evidence for any new trigger input. | Medium if limited to accepted signals. Noise, duplicate delivery, and partial inputs require explicit handling. | Medium. Rule and delivery upkeep. |
| Trading Journal & Behavioral Analytics | Review rationale and discipline alongside outcomes. | Ticker/session context and alert history can be linked. | User-authored decision records, outcomes, review rubric, and private retention/export policy. | Medium. Sparse self-reports can bias summaries. | Medium. Taxonomy and private record management. |
| Historical Scenario Explorer | Compare prior market conditions and subsequent observations. | SSI daily history, accepted flow, and exact-session comparisons. | Verified history depth and point-in-time membership or a clearly limited cohort methodology. | Medium to high. Survivorship, missing sessions, and adjustment lineage limit interpretation. | Medium. Coverage and provenance reviews. |
| Market Breadth & Regime | Add interpretable market context to the daily scan. | Accepted VN30 breadth, current ICB groups, and relative performance. | Regime definition, review cases, and a proven universe/acquisition path for any HOSE-wide view. | Medium for VN30; high for broader coverage. Threshold drift and incomplete denominators can mislead. | Medium to high. Calibration and universe quality. |
| Personal Opportunity Scanner | Surface a short research list from user-selected conditions. | Watchlist filters, daily indicators, and accepted participation measures. | User rules, explicit scan universe, and availability/performance evidence for its size. | Medium on a bounded watchlist. Selection bias and cold fan-out rise with scope. | Medium. Criteria and provider budget. |
| Strategy Backtesting | Study the historical behavior of explicit rules. | VN daily bars and indicators, plus separate inherited backtest code. | Point-in-time universe and adjusted histories, execution assumptions, fees, and reproducible evaluation rules. | High. Look-ahead, survivorship, and execution bias. | High. Data quality and methodology. |
| Portfolio vs Benchmark | Explain relative performance over aligned periods. | Exact-session SSI VNINDEX/VN30 points for supported comparisons. | VN NAV and cash-flow history, benchmark return convention, and adequate historical coverage. | High. Cash-flow timing and price versus total-return mismatch distort attribution. | High. Valuation and benchmark reconciliation. |

## 12. Open questions

- Which journey currently costs the investor the most time, and what would count as a material improvement?
- Which alert conditions and delivery frequency would warrant attention during an ordinary week?
- What portfolio or journal data can the investor supply reliably, and what privacy, retention, and export controls would they need?
- What point-in-time history, benchmark coverage, and corporate-action evidence can the operator substantiate within the provider budget?
- Which deployment will be operated day to day, and what cold-load, alert cadence, and recovery targets are practical there?
