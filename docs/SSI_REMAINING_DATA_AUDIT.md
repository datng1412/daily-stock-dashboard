# SSI Remaining Data Capability Audit

Last updated: 2026-07-08

## Purpose

This document records Phase 4.8F - SSI Remaining Data Capability Audit for the Vietnam dashboard. It is a documentation-only audit. It does not authorize runtime changes, backend endpoints, frontend UI, schemas, tests, provider adapters, config/env changes, credentials, streaming subscriptions, fallback providers, fake data, scraping, RSS ingestion, or commit/push.

The goal is to separate:

1. SSI-owned data StockClock already uses.
2. SSI-owned data StockClock can likely use later but does not fully expose yet.
3. Data that still requires runtime proof before public API/UI exposure.
4. Data that remains external-provider-required because current repository evidence does not show SSI ownership.

Repository evidence used in this audit includes the current SSI fetcher mappings, Vietnam market service source labels, public schemas, tests, and the current VN docs. This audit does not use `docs/resources/` provider notes as authority.

## Current SSI-owned data already used

StockClock already uses SSI for these market-data domains:

| Capability | Current use | Ownership rule |
| --- | --- | --- |
| Daily OHLCV | Watchlist rows, company price block, daily chart candles, and canonical `latest_price`. | `latest_price` remains SSI `DailyOhlc` close when DailyOhlc rows exist. |
| DailyStockPrice | Reference, ceiling/floor, adjusted close when present, matched volume/value, put-through volume/value, latest foreign buy/sell/net volume/value, and bounded 5D/20D foreign-net summaries from recent rows. | Enrichment only; it must not overwrite DailyOhlc close. |
| IntradayOhlc | Optional compact intraday candles/pulse when rows are current and usable. | Separate from DailyOhlc and realtime; unavailable intraday must not hide daily rows. |
| SecuritiesDetails / Securities | Symbol metadata/profile fields when an exact ticker row is returned. | Optional metadata; missing fields stay null. |
| IndexList | SSI-returned index identifier discovery. | Use returned identifiers; do not guess missing aliases. |
| IndexComponents | VN30 membership when exact SSI `IndexComponents` rows are returned. | No hardcoded constituents or fallback provider members. |
| DailyIndex | Optional source-labeled index context where exact IndexList identifiers and usable rows exist. | Optional; non-positive index levels stay null. |
| Realtime `X:{symbol}` | Optional streaming-cache snapshot when background lifecycle is enabled, bootstrapped, and fresh rows exist. | Separate optional live layer; must not replace DailyOhlc. |
| Trade tape `X-TRADE:{symbol}` | Bounded latest-event buffer when background stream produces parsed rows with price, volume, and timestamp. | Latest-event tape only; not full historical time-and-sales. |
| SSI-derived metrics | MA/RSI/Bollinger, 20D volume/high/low, volume ratio, 52W high/low, 10D average volume, 3M average volume, price-vs-reference %, and daily range %. | Internal derivations from SSI inputs only; no external provider substitute. |

## SSI-owned data not fully used yet

These capabilities are SSI-owned candidates but not fully exposed as product features today:

| SSI capability | Source/API/stream | Current StockClock usage | Missing usage | Implementation priority | Runtime proof needed | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| DailyOhlc | REST `DailyOhlc` | Canonical daily OHLCV, charts, `latest_price`, technical inputs. | Finality/session status is not proven from DailyOhlc alone. | Keep existing behavior; do not expand before session proof. | Provider availability after recent `code=Exception`/429 diagnostics; final close semantics. | Never replace with DailyStockPrice, realtime, trade tape, or external data. |
| DailyStockPrice | REST `DailyStockPrice` | Reference, limits, matched/put-through, adjusted close if present, latest foreign flow, bounded 5D/20D net volume. | Average price, total buy/sell trade counts, total buy/sell volume, foreign current room, and any additional row fields not currently normalized/exposed. | Medium after live proof. | Field-key evidence, units, date alignment, zero/null behavior, and whether fields are daily totals or session-current values. | Enrichment only; keep separate from DailyOhlc. |
| IntradayOhlc | REST `IntradayOhlc` | Compact intraday pulse/candles with stale/rate-limit handling. | Broader cadence/productization remains partial. | Low-medium; maintain existing guardrails. | Current-date coverage, cadence stability, rate-limit behavior. | Not a realtime quote. |
| Securities | REST `Securities` | Same-provider metadata fallback after SecuritiesDetails. | Extended instrument metadata if rows include richer fields. | Medium for instrument metadata track. | Exact row keys by security type and exchange. | Same-provider fallback only; no external overwrite. |
| SecuritiesDetails | REST `SecuritiesDetails` | Preferred symbol metadata/profile source. | Listed shares semantics, issuer details, first trading date, lot size completeness, derivatives/covered warrant/fund/bond fields. | Medium for stock metadata; lower for separate instrument modules. | Live row-key evidence and per-field semantics. | Do not label listed shares as exact outstanding shares without proof. |
| IndexList | REST `IndexList` | Index discovery for DailyIndex; diagnostics. | Broader index catalog coverage and stable VNINDEX identifier remain unresolved. | Medium. | Market filter behavior, exact identifier coverage, rate-limit behavior. | Use SSI rows, not assumptions. |
| IndexComponents | REST `IndexComponents` | VN30 component rows from verified `indexCode=VN30`. | Other index components and weights if SSI returns them. | Medium. | Exact outer-index matching, symbol flattening, weight semantics. | No hardcoded constituents. |
| DailyIndex | REST `DailyIndex` | Optional VN30 index context where rows are usable. | Broader VNINDEX/HNX/UPCOM index values, breadth, liquidity, trading session. | Medium after identifier proof. | Exact identifiers, positive index values, exchange, breadth field semantics. | Optional index context; not a stock price source. |
| Realtime `X:{symbol}` | Streaming channel `X:{symbol}` | Optional snapshot cache through background manager. | Stronger public realtime board metrics only when current cache rows exist. | Maintain; no new expansion until stability proof. | Live entitlement, manager lifecycle, stale/idle classification, timestamp semantics. | Request handlers must only read cache. |
| Trade tape `X-TRADE:{symbol}` | Streaming channel `X-TRADE:{symbol}` | Bounded latest-event rows, B/S from explicit side codes, change versus SSI reference. | True historical time-and-sales remains unproven. | Maintain; defer history claims. | Continued live row evidence, side-code coverage, sequence semantics. | Do not infer trades from daily/realtime rows. |
| `X-QUOTE` order book | Streaming channel `X-QUOTE:{symbol}` | Parser can preserve quote-only context/bid-ask levels in realtime snapshot; no dedicated order-book product yet. | Dedicated bid/ask ladder, best bid/ask, level count by market. | High after `F`; likely Phase 4.8H. | Confirm field keys, price/volume units, 3-level HOSE and 10-level HNX/UPCOM/DER claims before UI/API exposure. | Separate from latest price and trade tape. |
| `F` trading session/status | SSI streaming session/status family, exact channel/fields not implemented. | Not wired. | Session label, halt/suspend/closed states, final close/finality support. | Highest missing SSI-backed candidate; likely Phase 4.8G. | Exact channel, code mapping, timestamp, market/ticker scope, and finality semantics. | Do not guess status-code meanings. |
| `R` foreign room | SSI realtime foreign-room/foreign-flow stream, exact channel/fields not implemented. | Not wired; realtime schema has placeholder `foreign_room` but current mapping does not populate it. | Total room, current room, realtime foreign buy/sell volume/value. | Medium-high after order book. | Exact fields such as current/total room, units, exchange-specific semantics, approximate value caveats. | Separate from DailyStockPrice end-of-day/daily foreign flow. |
| `MI` realtime market index | SSI realtime market index stream, exact channel/fields not implemented. | Not wired. | VNINDEX/VN30/HNX/UPCOM realtime index pulse, change/change %, value/volume, advances/unchanged/declines. | Medium. | Channel identifiers, index code mapping, field units, breadth semantics, timestamp/freshness. | Separate from stock watchlist rows. |
| `B` realtime OHLCV bars | SSI realtime OHLCV/bar stream, exact channel/fields not implemented. | Not wired. | Intraday bar updates or faster chart pulse. | Later. | Bar interval, session boundaries, correction semantics, and relationship to IntradayOhlc. | Must not replace DailyOhlc `latest_price`. |
| DER/futures metadata | Securities/SecuritiesDetails or SSI derivative metadata if returned. | Generic `security_type` only. | Contract multiplier, maturity/expiry, underlying, settlement, tick size. | Later separate instrument track. | Exact instrument rows and field semantics. | Not core stock dashboard unless a derivatives module is planned. |
| Covered warrant metadata | Securities/SecuritiesDetails or SSI covered-warrant fields if returned. | Generic `security_type` only. | Underlying, issuer, maturity date, exercise price, exercise ratio, warrant type. | Later separate instrument track. | Exact row-key evidence and rights/semantics. | Do not mix with equity stock fundamentals. |
| ETF/fund/bond metadata | Securities/SecuritiesDetails or related SSI metadata if returned. | Generic `security_type` only. | Fund/bond-specific issuer, maturity, NAV/reference metadata, listing/unit fields. | Later separate instrument track. | Exact row keys, instrument classification, display semantics. | Keep separate from common-stock profile. |

## Candidate implementation backlog

### A. `F` trading session/status

Potential value:

* Source-backed market/session status labels.
* Halted, suspended, closed, or final-close/finality support if SSI fields prove those states.
* Possible normalized `TradingSession` / `TradingStatus` fields only after SSI payloads prove exact meanings.
* Better distinction between normal market phase copy and provider-confirmed trading status.

Runtime proof required:

* Exact stream/channel name and subscription format.
* Complete status-code mapping from SSI evidence.
* Scope: market-wide, exchange-wide, index-level, or ticker-level.
* Timestamp/freshness semantics.
* Final-close meaning and whether it can safely support `final_close_status`.

Do not implement by guessing status codes from names or UI color conventions.

### B. `X-QUOTE` order book

Potential value:

* Bid/ask ladder and best bid/ask for selected ticker.
* Better separation between quote liquidity and matched trade data.
* Possible 3 levels for HOSE and 10 levels for HNX/UPCOM/DER only if current SSI payloads prove those limits.

Runtime proof required:

* Bid/ask field keys and level counts by market.
* Price and volume units.
* Timestamp and stale-cache rules.
* Empty-book and auction/halt behavior.

Order book rows must be separate from `latest_price`, DailyStockPrice, and trade tape.

### C. `R` foreign room

Potential value:

* Total room and current room.
* Realtime foreign buy/sell volume/value when present.
* Better intraday foreign ownership context than end-of-day DailyStockPrice fields.

Runtime proof required:

* Field keys for total room, current room, current-room ratio, buy/sell volume/value, and any approximate value fields, including whether SSI uses names such as `TotalRoom` or `CurrentRoom`.
* Unit semantics: shares, lots, VND, or provider-scaled values.
* Relationship to DailyStockPrice daily foreign buy/sell/net fields.

Realtime foreign room must not overwrite DailyStockPrice foreign-flow enrichment.

### D. `MI` realtime market index

Potential value:

* Live VNINDEX/VN30/HNX/UPCOM pulse if SSI supports those identifiers.
* Index value, change/change %, total volume/value, and market breadth.
* Cleaner market context for watchlist movement without using external index providers.

Runtime proof required:

* Channel identifiers for each index.
* Exact mapping from SSI index codes to public labels.
* Positive index values and field units.
* Breadth semantics for advances/unchanged/declines/ceiling/floor.

Index stream rows must be separate from stock watchlist rows and from optional DailyIndex REST rows.

### E. `B` realtime OHLCV bars

Potential value:

* Intraday bar updates with a streaming lifecycle.
* Possible chart pulse after streaming is stable.

Runtime proof required:

* Interval/cadence, bar open/high/low/close/volume units.
* Session-boundary behavior and correction/update semantics.
* Relationship to REST IntradayOhlc and DailyOhlc.

`B` bars must not replace DailyOhlc `latest_price` or official chart daily candles.

### F. DailyStockPrice unused fields

Potential value:

* Average price, total buy/sell trade counts, total buy/sell volume, total traded volume/value, adjusted close, and foreign current room when SSI rows expose them.
* More complete daily trading-stat panels without adding an external provider.

Current repository status:

* Mapped/exposed today: reference, ceiling, floor, OHLC enrichment fields, adjusted close when present, matched/put-through volume/value, total volume/value, foreign buy/sell/net volume/value.
* Not proven today: average price, total buy/sell trade count, total buy/sell volume, and foreign current room as stable DailyStockPrice fields.

Runtime proof required:

* Row-key evidence.
* Units and zero/null behavior.
* Date alignment with DailyOhlc.
* Whether each field is daily final, session-current, adjusted, or exchange-specific.

### G. SecuritiesDetails extended metadata

Potential value:

* Better profile metadata for common stocks when SSI returns it.
* Separate instrument metadata tracks for derivatives, covered warrants, ETF/fund, bond, and other securities.

Current repository status:

* Mapped today: symbol, exchange/market, security type, names, industry/sector, issuer, lot size, listed shares, and listed date.
* Not proven today: first trading date beyond listed date aliases, maturity date, underlying, contract multiplier, exercise price, exercise ratio, covered-warrant type, futures-specific fields, ETF/fund/bond-specific fields.

Runtime proof required:

* Sanitized exact row keys by instrument type.
* Field semantics and units.
* Whether fields are issuer metadata, exchange metadata, or instrument-contract metadata.

Do not turn instrument metadata into fundamentals, valuation, ownership, or market-cap calculations without a separate source-basis decision.

## Runtime-proof requirements

Before any missing SSI-backed field moves into API/UI:

1. Capture sanitized live or fixture-backed field-key evidence.
2. Prove the endpoint/stream/channel name and subscription format.
3. Prove symbol or index identifier mapping.
4. Prove timestamp and freshness semantics.
5. Prove units, scale, zero/null behavior, and date alignment.
6. Preserve null/empty-list behavior when unavailable.
7. Add source/status/diagnostics fields; do not expose raw provider payloads.
8. Keep request handlers as readers for streaming caches; do not start streams from request handlers.
9. Add deterministic tests around parser, normalization, missing fields, and no-fallback behavior.
10. Update user-facing docs and changelog.

## External-provider boundary

SSI-owned / do not externalize while SSI can provide or derive it:

* Daily prices, DailyOhlc OHLCV, and chart candles.
* DailyStockPrice reference, ceiling/floor, matched/put-through, adjusted close when present, total trading fields when proven, and foreign-flow fields.
* IntradayOhlc if SSI-backed.
* Realtime snapshot.
* `X-QUOTE` order book if proven.
* `X-TRADE` latest-event tape and any future SSI trade-history source if proven.
* `F` trading session/status if proven.
* `R` foreign room/foreign trading stream if proven.
* `MI` realtime market index if proven.
* `B` realtime OHLCV bars if proven.
* IndexList, IndexComponents, DailyIndex where SSI rows are usable.
* Securities/SecuritiesDetails metadata where SSI returns exact rows.
* SSI-derived technical/statistical metrics from SSI-owned inputs.

external-provider-required under current evidence:

* News and research reports.
* Corporate actions, dividends, rights, and splits unless SSI later exposes explicit structured event rows.
* Financial statements.
* EPS, P/E, P/B, ROE, ROA, and fundamentals/valuation ratios.
* Macro.
* Ownership/shareholder data when not SSI-backed or not semantically sufficient.
* Rich metadata only for SSI-null fields after explicit per-field source priority and rights proof.

External providers must use separate source labels and must not silently fill or overwrite SSI-owned fields.

## Recommended next implementation order

1. Phase 4.8F - SSI Remaining Data Capability Audit: docs-only; this document.
2. Phase 4.8G - Trading Session/Status from SSI `F`, only if runtime proof confirms stable fields and code mappings.
3. Phase 4.8H - `X-QUOTE` Order Book Ladder.
4. Phase 4.8I - Realtime Foreign Room from SSI `R`.
5. Phase 4.8J - Realtime Market Index Pulse from SSI `MI`.
6. Phase 4.8K - DailyStockPrice Unused Field Audit/Exposure.
7. Phase 4.8L - SecuritiesDetails Extended Metadata.
8. Later - Realtime OHLCV `B`, derivatives, covered warrants, ETF/fund, and bond modules.

No phase above changes `latest_price`; DailyOhlc remains canonical unless a future explicit source-ownership decision changes it.
