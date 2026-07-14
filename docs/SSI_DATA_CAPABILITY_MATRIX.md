# SSI Data Capability Matrix

## Purpose

This matrix is an audit and planning aid for the VN dashboard. It is not a new API contract and does not replace `docs/VN_DATA_CONTRACT.md`.

Statuses are conservative and should be refreshed when provider behavior, endpoint permissions, or response shapes change. A `strong` or `usable` status is repository and current-evidence scoped; it is not a permanent provider guarantee.

Use `scripts/audit_vn_data_capability.ps1` to refresh local evidence from existing app endpoints before adding new dashboard fields or UI modules.

Last local audit baseline: 2026-06-24, using `FPT,VPB,ACB,SSI,GMD,GAS,POW,VNM` and selected ticker `FPT` against `http://127.0.0.1:8000`.

Latest bounded live gate: 2026-06-29, using sanitized SSI smoke output plus local API smoke. SSI DailyStockPrice history populated 20 recent foreign-flow rows for FPT/HPG/SSI; VN30 DailyIndex remained partial because the public row lacked a usable positive `index_value` and `exchange`; exact `VNINDEX` remained unresolved; VN30 IndexComponents returned 30 rows.

## Status Vocabulary

| Status | Meaning |
| --- | --- |
| `strong` | Implemented, source-owned, covered by deterministic tests, and supported by current repo/live evidence for the public contract. |
| `usable` | Implemented and safe to expose when rows exist, but coverage, optional fields, or provider behavior remains bounded. |
| `partial` | Some usable SSI fields or paths exist, but freshness, cadence, completeness, identifier coverage, or row validity remains incomplete. |
| `optional_live_dependent` | Implemented as an optional live/cache contract; data appears only when the live runtime is explicitly enabled and current rows exist. |
| `unavailable_parameter_unknown` | A current repo path or candidate endpoint exists, but the correct identifier/parameter/row semantics are not proven. |
| `unavailable_permission_or_entitlement` | SSI may expose the domain only under account permission or entitlement not proven in the current environment. |
| `external_provider_required` | No SSI-owned endpoint or repo evidence supports the domain; a separate provider contract is required. |
| `not_implemented` | A placeholder or contract may exist, but no provider implementation is present. |
| `not_implemented_runtime_proof_required` | SSI appears to have a plausible API/stream family, but StockClock has no runtime contract yet; field keys, units, identifiers, timestamps, and unavailable behavior must be proven before exposure. |
| `deferred` | Valid future work, intentionally out of scope for the current SSI-first phase. |
| `deferred_runtime_proof_required` | Valid SSI-backed future work, but lower priority than nearer runtime-proof items and still blocked on field/semantics evidence. |
| `implemented_ssi_derived` | Implemented internally from SSI-owned inputs with null/coverage semantics. |
| `computable_from_ssi_daily_ohlc` | Not implemented yet, but the inputs should come from SSI DailyOhlc and should be calculated internally. |
| `computable_from_ssi_daily_ohlc_and_daily_stock_price` | Not implemented yet, but the inputs should come from SSI DailyOhlc plus SSI DailyStockPrice and should be calculated internally. |
| `deferred_pending_ssi_index_methodology` | Deferred until SSI index data and a documented beta/statistics methodology are verified; not an external-provider default. |
| `deferred_pending_share_basis_verification` | Deferred until listed/outstanding/free-float share-count semantics and ownership are verified; do not compute from ambiguous metadata. |

## SSI-first Data Ownership Rule

If SSI can provide a market-data field, SSI owns it. If a metric can be calculated from SSI-owned data, calculate it internally from SSI data. External providers are allowed only for domains SSI cannot provide or cannot support with verified semantics and legal rights.

External providers must be source-labeled and domain-scoped. They must not overwrite SSI DailyOhlc, SSI DailyStockPrice, SSI IntradayOhlc, SSI streaming realtime, SSI X-TRADE trade tape, SSI index data, SSI metadata, or SSI-derived technical indicators. External-provider failures must not change valid SSI daily rows, and no fallback provider may silently replace SSI-owned fields.

## SSI Ownership and Derived Metric Matrix

This is the canonical SSI-first ownership matrix for future VN dashboard work. Public contracts may reference this table instead of duplicating it.

| Data field or metric | Ownership class | Owner / derivation | Current status | Rule |
| --- | --- | --- | --- | --- |
| Daily OHLCV | SSI-owned | SSI DailyOhlc | `strong` | Canonical daily OHLCV. |
| `latest_price` | SSI-owned | SSI DailyOhlc close | `strong` | Must not be overwritten by DailyStockPrice, realtime, trade tape, or external providers. |
| Chart candles | SSI-owned | SSI DailyOhlc | `strong` | Chart source remains DailyOhlc. |
| Reference price | SSI-owned | SSI DailyStockPrice | `strong` | Source-specific enrichment, not canonical close. |
| Ceiling/floor | SSI-owned | SSI DailyStockPrice | `strong` | Use only when SSI returns values. |
| Matched volume/value | SSI-owned | SSI DailyStockPrice | `strong` | Do not substitute DailyOhlc volume/value. |
| Put-through volume/value | SSI-owned | SSI DailyStockPrice | `strong` | Null when SSI does not provide it; provider zero remains zero. |
| Foreign buy/sell/net volume/value | SSI-owned | SSI DailyStockPrice | `strong` | Latest enrichment comes from DailyStockPrice. |
| Intraday candles | SSI-owned | SSI IntradayOhlc | `partial` | Optional; unavailable intraday does not affect daily rows. |
| Realtime snapshot | SSI-owned optional live | SSI streaming `X:{symbol}` cache | `optional_live_dependent` | Background cache only; no request-handler stream start. |
| Trade tape / latest trade events | SSI-owned optional live | SSI streaming `X-TRADE:{symbol}` event buffer when verified | `partial` | Latest-event tape only; not full historical time-and-sales. |
| Order book / bid-ask ladder | SSI-owned optional live context | SSI streaming `X-QUOTE:{symbol}` latest cache | `partial_runtime_proof` | Dedicated ladder/best bid-ask stays separate from `latest_price`, realtime snapshot, trade tape, and session/status. |
| Trading session/status | SSI-owned candidate | SSI streaming `F` if proven | `not_implemented_runtime_proof_required` | Candidate source for session/halt/finality labels; do not guess code mappings. |
| Realtime foreign room | SSI-owned candidate | SSI streaming `R` if proven | `not_implemented_runtime_proof_required` | Separate from DailyStockPrice daily foreign-flow enrichment. |
| Realtime market index pulse | SSI-owned optional live context | SSI streaming `MI:{index_code}` latest cache | `partial_runtime_proof` | Separate from stock watchlist rows and optional DailyIndex REST context. |
| Realtime OHLCV bars | SSI-owned candidate | SSI streaming `B` if proven | `deferred_runtime_proof_required` | Candidate intraday bar source; must not replace DailyOhlc daily candles or `latest_price`. |
| IndexList | SSI-owned | SSI IndexList | `usable` | Use SSI-returned identifiers. |
| VN30 components | SSI-owned | SSI IndexComponents | `usable` | Use exact SSI component rows; no hardcoded constituents. |
| DailyIndex | SSI-owned optional index context | SSI DailyIndex where identifiers/rows are verified | `partial` | Optional; unresolved broad VNINDEX may need source-labeled external context later. |
| Symbol metadata | SSI-owned where present | SSI SecuritiesDetails, then SSI Securities same-provider fallback | `partial` | Missing optional metadata stays null; external fallback only for SSI-null fields after approval. |
| Extended instrument metadata | SSI-owned candidate where returned | SSI SecuritiesDetails/Securities by instrument type | `not_implemented_runtime_proof_required` | Derivatives, covered warrants, ETF/fund, and bond metadata need sanitized row-key evidence and separate product treatment. |
| MA20 / MA50 | SSI-derived internal | SSI DailyOhlc history | implemented internal indicator | Keep internal/source-labeled; no external provider. |
| RSI14 | SSI-derived internal | SSI DailyOhlc history, Wilder/RMA | implemented internal indicator | Keep internal/source-labeled; no external provider. |
| Bollinger 20,2 | SSI-derived internal | SSI DailyOhlc history | implemented internal indicator | Keep internal/source-labeled; no external provider. |
| 20D average volume | SSI-derived internal | SSI DailyOhlc volume history | implemented internal indicator | Existing 20-day indicator remains SSI-derived. |
| 20D high/low | SSI-derived internal | SSI DailyOhlc high/low history | implemented internal indicator | Existing 20-day indicator remains SSI-derived. |
| Volume ratio | SSI-derived internal | SSI DailyOhlc volume and SSI-derived average volume | implemented internal indicator | Null/unavailable when inputs are insufficient. |
| Foreign net 5D/20D | SSI-derived internal | SSI DailyStockPrice recent `foreign_net_volume` history | implemented bounded enrichment | Null when returned SSI history is insufficient. |
| 52W high/low | SSI-derived internal | SSI DailyOhlc high/low history | `implemented_ssi_derived` | Uses latest 252 returned DailyOhlc rows; values and dates are null when fewer than 120 rows have valid dates and positive numeric high/low values. |
| Avg volume 10D | SSI-derived internal | SSI DailyOhlc volume history | `implemented_ssi_derived` | Requires 10 usable volume rows. |
| Avg volume 3M | SSI-derived internal | SSI DailyOhlc volume history | `implemented_ssi_derived` | Uses latest 63 usable volume rows; `complete` at >=60, `partial` at >=30, null below 30. |
| Price vs reference % | SSI-derived internal | SSI DailyOhlc close + SSI DailyStockPrice reference | `implemented_ssi_derived` | Null when DailyOhlc close is unavailable or DailyStockPrice reference is missing/non-positive. |
| Daily range % | SSI-derived internal | SSI DailyOhlc high/low/close | `implemented_ssi_derived` | Formula is `(high - low) / close * 100`; null when high/low/close are incomplete. |
| Short-term D1 support/resistance zones | SSI-derived internal | Latest 60 valid unique SSI DailyOhlc sessions | `implemented_ssi_derived` | ATR14 Wilder/RMA plus two-before/two-after pivots; public zones contain only lower/upper bounds, exclude the latest close, and remain unavailable instead of guessed when inputs are insufficient. |
| Beta | Deferred SSI-derived/statistical metric | SSI DailyOhlc plus verified SSI index data and documented methodology | `deferred_pending_ssi_index_methodology` | Do not default to external provider; require index/methodology proof first. |
| Market cap | Deferred share-basis metric | SSI or verified external share-count semantics plus canonical price rule | `deferred_pending_share_basis_verification` | Do not compute from ambiguous `listed_shares`; require share-basis proof. |
| Corporate actions | External-provider-only | Future CorporateActionsProvider / licensed source | `external_provider_required` | First external domain; no inference from price gaps. |
| Dividends | External-provider-only | Future CorporateActionsProvider / licensed source | `external_provider_required` | Requires explicit event rows and provenance. |
| Rights | External-provider-only | Future CorporateActionsProvider / licensed source | `external_provider_required` | Requires explicit event rows and provenance. |
| Splits | External-provider-only | Future CorporateActionsProvider / licensed source | `external_provider_required` | Requires explicit event rows and provenance. |
| Financial statements / BCTC / KQKD | External-provider-only | Future licensed fundamentals provider | `external_provider_required` | No SSI evidence in repo. |
| EPS TTM | External-provider-only | Future statements/ratios provider | `external_provider_required` | Do not infer from price data. |
| P/E TTM | External-provider-only | Future statements/ratios provider | `external_provider_required` | Do not compute without EPS methodology/source. |
| P/B | External-provider-only | Future statements/ratios provider | `external_provider_required` | Requires book-value source/methodology. |
| ROE / ROA | External-provider-only | Future financial statements/ratios provider | `external_provider_required` | Requires financial statements/ratio provider. |
| News | External-provider-only | Future NewsProvider / licensed source | `external_provider_required` | No Mozyfin/KBS fallback. |
| Macro | External-provider-only | Future licensed/provider-specific source | `external_provider_required` | Defer until series ownership and rights are verified. |
| Rich metadata SSI cannot provide | External-provider-only for SSI-null fields | Future source-labeled metadata provider | `external_provider_required` | May fill only SSI-null fields after per-field priority and rights proof. |
| Explicit external VNINDEX/index context | External-provider-only if SSI remains unresolved | Future licensed source-labeled index provider | `deferred` | Must never be labeled SSI or replace SSI index rows. |

## Capability Matrix

| Data domain | Current status | Category | Current endpoint/provider | Current public contract | Evidence summary | Next action | External provider required? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Securities | `partial` | SSI available and implemented | `GET /Market/Securities`; `get_securities`; same-provider fallback for metadata | `symbol_metadata`, company `profile`, source coverage fields when exact ticker row is found | Phase 4.3A added exact-symbol selection, sanitized diagnostics, and same-SSI fallback after `SecuritiesDetails`; optional fields remain null | Keep as SSI fallback only; add aliases only after sanitized live row-key evidence | No for base symbol metadata; richer fallback is deferred external work |
| SecuritiesDetails | `partial` | SSI available and implemented | `GET /Market/SecuritiesDetails`; `get_securities_details` | Preferred source for symbol metadata/profile fields | Phase 4.3A verified null-safe metadata quality/completeness and no effect on DailyOhlc/DailyStockPrice | Keep optional fields null when absent; do not infer company details | No for SSI-returned fields |
| Supported market metadata | `usable` | SSI available and implemented | `Securities`, `SecuritiesDetails`, `IndexList` | Source-labeled symbol/index metadata; missing fields are null | Current repo has explicit metadata quality, field coverage, and diagnostics | Keep metadata source-specific and non-fatal | No for SSI-returned fields; external fallback deferred |
| DailyOhlc | `strong` | SSI available and implemented | `GET /Market/DailyOhlc`; watchlist/chart loaders | Canonical daily OHLCV, chart candles, `latest_price`, internal indicators | Deterministic tests and live smoke evidence keep `latest_price_source=SSI DailyOhlc`; latest price ownership unchanged | Preserve canonical ownership; investigate finality separately, not by overwriting fields | No |
| DailyStockPrice | `strong` | SSI available and implemented | `GET /Market/DailyStockPrice`; 29-day chunking; latest-row enrichment and bounded recent foreign-flow history | Reference, ceiling/floor, adjusted close if present, matched/put-through volume/value, latest foreign buy/sell/net volume/value, and latest-available 5D/20D foreign net volume when enough recent rows exist | Phase 4.2A covered date alignment, partial coverage, units, null/zero behavior, and unchanged DailyOhlc close; Phase 4.5B reuses the existing per-symbol recent window to preserve up to 20 DailyStockPrice foreign-flow rows for indicators; Phase 4.5C live API smoke populated 20 recent rows and non-null 5D/20D foreign-net summaries for FPT/HPG/SSI while `latest_price_source` stayed `SSI DailyOhlc` | Keep bounded per-symbol history only; do not add broad full-market scans or value/volume unit mixing | No for latest enrichment or bounded recent foreign-flow history |
| DailyIndex | `partial` | SSI available but live result partial | `GET /Market/DailyIndex`; `indexID` after exact `IndexList` resolution | Optional index rows with `rows=[]` when unavailable; non-positive index levels normalize to null | Phase 4.4B proved `indexID=VN30` returns rows; Phase 4.5C live API smoke returned a VN30 row dated 2026-06-29 but public `index_value` and `exchange` remained missing; exact `VNINDEX` remains unresolved | Keep VN30 optional and partial; do not guess VNINDEX or render zero as an index level | External fallback only for explicit source-labeled VNINDEX, deferred |
| IndexList | `usable` | SSI available and implemented | `GET /Market/IndexList` with market-qualified requests | Authoritative SSI-returned identifiers for DailyIndex and index discovery; explicit IndexComponents codes are direct | Phase 4.4B returned 10 cross-market rows for HOSE/HNX, exact `VN30`, no exact `VNINDEX`; no-market request unavailable | Continue resolving DailyIndex through market-qualified `IndexList`; treat market filters as non-strict | No for returned identifiers |
| IndexComponents | `usable` | SSI available and implemented for VN30 | `GET /Market/IndexComponents`; `indexCode` first; exact nested row flattening | Optional component rows/counts with `rows=[]` when unavailable | Phase 4.4B proved exact VN30 nested `IndexComponent`/`StockSymbol` rows with 30 members; Phase 4.5C live API smoke re-confirmed 30 VN30 component rows; no hardcoded constituents | Use only real SSI component rows; do not infer breadth or membership when absent | No for VN30 rows; other index coverage unknown |
| IntradayOhlc | `partial` | SSI available but live result partial/unavailable | `GET /Market/IntradayOhlc` | Optional `intraday_candles` and `intraday_pulse` only when rows are current and matched; otherwise `[]`/`null` | Phase 4.0B fixed paging/order; Phase 4.0B-2/3 classified provider code `429` and added cooldown; Phase 4.1A added actual cadence detection | Keep rate-limit-aware optional behavior; do not present as realtime quote | No |
| Realtime streaming snapshot | `optional_live_dependent` | SSI available but live runtime-dependent | SSI streaming data type `X`; background manager/cache only | `realtime_snapshot=null` unless explicit streaming runtime is enabled, manager is running, and cache row is fresh | Parser, official-client adapter, lifecycle bootstrap, cache bypass, and safe diagnostics exist; default runtime remains disabled | Keep background-only cache contract; no request-handler streaming, no WebSocket/SSE productization | No for SSI snapshot, but live entitlement/runtime must be proven per environment |
| Trade tape / `X-TRADE` semantics | `partial` | SSI streaming latest-event tape is usable only when background stream/cache is enabled, symbol bootstrapped, and fresh X-TRADE events arrive; true trade-history semantics remain unproven | `X-TRADE` streaming latest-trade event buffer; candidate REST trade endpoints remain unverified and are not probed at runtime | Public trade tape stays `[]` unless fresh buffered X-TRADE rows with price, volume, and timestamp exist | Parser and manager now separate latest-event trade rows from realtime snapshot rows; no verified historical time-and-sales rows exist | Do not call this historical trade tape; do not infer rows from DailyOhlc, DailyStockPrice, or realtime snapshot | Possibly, if SSI true historical trade tape is not entitled/available |
| `X-QUOTE` order book | `partial_runtime_proof` | SSI streaming latest ladder context is cache-backed when background stream/cache is enabled, symbol bootstrapped, and usable X-QUOTE events arrive | `X-QUOTE:{symbol}` streaming order-book cache | Optional watchlist `order_book` fields preserve only real bid/ask levels; unavailable state remains null/status-only | Phase 4.8H adds parser routing, dedicated cache, watchlist fields, and diagnostics without frontend productization | Prove live field keys, price/volume units, timestamp behavior, market-specific level counts, and stale/empty semantics before UI | No if SSI proves ladder semantics |
| `F` trading session/status | `partial_runtime_proof` | SSI streaming latest status context is cache-backed when background stream/cache is enabled, symbol bootstrapped, and usable F events arrive | `F:{symbol}` streaming session/status cache | Optional watchlist `session_status` fields preserve raw `trading_session` / `trading_status` values; unavailable state remains null/status-only | Phase 4.8G adds parser, dedicated cache, watchlist fields, and diagnostics without frontend productization or code mapping | Prove live code meanings, scope, timestamp behavior, and final-close semantics before mapping labels or driving UI state | No if SSI proves code semantics |
| `R` foreign room | `not_implemented_runtime_proof_required` | SSI streaming candidate | `R` stream family if live docs/payloads prove it | Realtime `foreign_room` schema placeholder exists, but current SSI mapping does not populate it | Candidate source for total/current room and intraday foreign buy/sell context | Prove fields, units, approximate value semantics, and relationship to DailyStockPrice daily foreign flow | No if SSI proves it |
| `MI` realtime market index | `partial_runtime_proof` | SSI streaming latest index context is cache-backed when background stream/cache is enabled and usable MI events arrive | `MI:{index_code}` streaming market-index cache | Separate `market_index_pulse` API response preserves real index value/change/activity/breadth rows; unavailable state remains empty-list/status-only | Phase 4.8J adds parser routing, dedicated cache, API response, and diagnostics without frontend productization | Prove live channel format, index identifiers, index value/change, breadth, total value/volume, units, and freshness before UI | No if SSI proves it |
| `B` realtime OHLCV bars | `deferred_runtime_proof_required` | SSI streaming candidate | `B` stream family if live docs/payloads prove it | No public realtime bar rows yet | Candidate after streaming lifecycle is stable | Prove interval, session boundaries, correction semantics, and relationship to IntradayOhlc/DailyOhlc | No if SSI proves it |
| Extended instrument metadata | `not_implemented_runtime_proof_required` | SSI metadata candidate | Securities/SecuritiesDetails for DER/futures, covered warrants, ETF/fund, bond rows if SSI returns exact fields | Current metadata contract exposes common symbol/profile fields only | Candidate for separate instrument metadata modules, not core stock fields | Prove exact row keys such as underlying, maturity, multiplier, exercise price/ratio, issuer, and instrument type semantics | No for SSI-returned metadata |
| Unsupported fundamentals | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | No SSI-owned public contract | Current implementation exposes no SSI fundamentals endpoint | Keep unavailable/not implemented until a provider is selected | Yes |
| Unsupported financial statements | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | Company `financials` placeholder | Current company research service returns `not_implemented`; no SSI statement endpoint in repo evidence | Defer behind external-provider gate | Yes |
| Unsupported ratios | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | No ratio provider block | No SSI ratios endpoint in repo evidence | Defer; keep provider ratios separate from local derivations | Yes |
| Unsupported corporate actions | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | `CorporateActionsProvider` disabled-by-default contract only | `/vn/corporate-actions` returns `events=[]` and legacy `items=[]` until a verified provider is configured; company `events=[]` placeholder remains separate from SSI market data | Service explicitly refuses to infer events from price/reference/adjusted gaps; Phase 5.0B proves disabled/not-configured/error contract and sanitized diagnostics only | Resolve commercial/legal gate before live adapter; no provider runtime yet | Yes |
| Unsupported dividends/rights/splits | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | Same event/corporate-action boundary | No explicit SSI event source in current repo evidence | Use only explicit future event rows; no inference from price gaps | Yes |
| Unsupported news | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None; Mozyfin disabled | Watchlist `news=[]`, `news_status.status=disabled`; company `news.status=not_implemented` | Current runtime has no SSI or Mozyfin news path. Phase 5.1A/5.1A-2 research classifies FiinGroup API Datafeed News as `preferred_after_entitlement`, Vietstock DataFeed as `candidate_after_entitlement`, WiGroup WiFeed/WiData as candidates after commercial/API/rights review, and Vnstock/VNStock as `prototype_only`. Public docs/schema access is not legal/runtime access. | Future NewsProvider only after access, ticker-tagging, source URL, storage/display, redistribution, rate-limit, and licensed-fixture proof | Yes |
| Unsupported macro | `external_provider_required` | SSI endpoint not found in current repo/docs/evidence | None | No macro block | No SSI macro evidence in current repo | Defer until specific source/series contracts exist | Yes |

## Stock Detail Metrics Audit

Phase 4.7A-docs inspected the current backend schemas, SSI fetcher mappings, service normalization, frontend types, and dashboard rendering for common stock-detail panel labels. The result is documentation-only:

* Available today from SSI DailyOhlc / DailyStockPrice when provider rows contain values: daily open, matched value, put-through value, put-through volume, foreign buy volume, and foreign sell volume.
* Available today as source-specific metadata but not safe to relabel without confirmation: `listed_shares` from SSI SecuritiesDetails/Securities. Do not present it as exact outstanding quantity until provider semantics are confirmed.
* Ambiguous optional realtime placeholders: average price and foreign room have schema/type fields under the realtime snapshot contract, but current SSI mapping does not populate them as stock-detail metrics.
* Implemented SSI-derived metrics: 52-week high/low, 10-day average volume, 3-month average volume, price-vs-reference %, and daily range %. Values remain null or status-labeled when SSI history/reference/OHLC inputs are insufficient.
* Deferred pending methodology/semantics: beta requires verified SSI index data plus a documented calculation method before implementation; market cap requires verified share-count semantics before any calculation.
* Future-provider required: EPS TTM, P/E TTM, P/B, dividend ratio/date, ROE, and ROA. Corporate-action contract fields exist only behind the disabled/not-configured future provider boundary and return empty lists when no verified rows exist.

Do not infer missing stock-detail values from price gaps, `latest_price`, DailyStockPrice close, optional realtime rows, Mozyfin, KBS, or hardcoded ticker data.

## Phase 4.5A SSI Gap Separation

* SSI available and implemented: Securities, SecuritiesDetails, DailyOhlc, DailyStockPrice, IndexList, VN30 IndexComponents, VN30 DailyIndex rows, IntradayOhlc, and the optional streaming realtime snapshot contract.
* SSI available but implementation or live result remains partial: IntradayOhlc freshness/rate-limit behavior, DailyIndex level validity for VN30, and exact broad `VNINDEX` identifier discovery. DailyStockPrice multi-session foreign-flow history is now implemented only as a bounded, per-symbol, latest-available 5D/20D indicator path.
* SSI endpoint exists but parameter or entitlement remains unknown: REST trade-tape candidate names such as `TradeTape`, `MatchedTrades`, and `SecuritiesTrades`; any true historical trade-tape source; any SSI broad-index alias not returned by `IndexList`.
* SSI endpoint not found in current repo/docs/evidence: fundamentals, financial statements, ratios, corporate actions, dividends, rights, splits, news, and macro.
* External-provider-only under current evidence: corporate actions/dividends/rights/splits, financial statements, ratios, news, macro, and explicit source-labeled `VNINDEX` fallback if SSI remains unresolved.

Phase 4.5B added no runtime providers, fallback providers, scraping, fake rows, WebSocket/SSE delivery, FC Trading calls, or changes to `latest_price`.

## Phase 5.0D External Provider Qualification Summary

Phase 5.0D refreshed the external-provider qualification matrix in `docs/VN_EXTERNAL_PROVIDER_STRATEGY.md` without changing runtime behavior:

* Vnstock / VNStock / Vnstock Data is `prototype_only` for research/manual comparison until commercial license, source-owner terms, storage/display rights, redistribution rights, rate limits, and provenance are explicitly resolved. It must not be wired into StockClock runtime as a production NewsProvider or market-data fallback.
* FiinQuant is `candidate_after_entitlement` for licensed realtime, tick, orderbook, historical, financial-statement, and valuation workflows. It is not an automatic replacement for SSI realtime, trade tape, DailyOhlc, or DailyStockPrice.
* FiinGroup API Datafeed is `preferred_after_entitlement` for automated corporate actions/dividends/rights/splits first, then financial statements, ratios, news, metadata fallback, macro, and source-labeled external index context. For news specifically, FiinGroup API Datafeed News is the preferred first licensed target after entitlement; Vietstock DataFeed is the backup candidate after entitlement.
* Manual/provenance-required import remains the offline fallback for corporate actions and dividends; it must retain source references and must not scrape public portals.

No external provider is authorized, configured, called, or allowed as fallback. SSI DailyOhlc remains canonical for `latest_price`, SSI DailyStockPrice remains the enrichment owner, and unsupported external domains remain `external_provider_required` until their legal/access gates pass.

## Phase 4.5C Live Capability Gate

* DailyStockPrice remains `strong`: live smoke returned chunked FPT yearly rows and local API smoke populated 20 recent foreign-flow rows for FPT, HPG, and SSI with non-null latest-available 5D/20D foreign-net summaries.
* DailyIndex remains `partial`: VN30 can resolve and return a dated row, but the public row still lacks usable `index_value` and `exchange`; `VNINDEX` remains unresolved by exact SSI IndexList matching.
* IndexComponents remains `usable` for exact VN30: live API smoke returned 30 component rows and preserved `rows=[]` semantics for unavailable cases.
* Phase 4.6F-4 sends explicit IndexComponents codes directly through the verified `indexCode` shape. IndexList failure no longer blocks that request; successful rows cache for 300 seconds and unavailable/rate-limited/no-row results are negatively cached for 60 seconds.
* IntradayOhlc, realtime snapshot, and trade tape remain optional/unavailable in the local API smoke and must not affect valid DailyOhlc/DailyStockPrice rows.
* True trade-tape history and final close/session confirmation remain unproven. Do not infer either from DailyOhlc, DailyStockPrice, intraday rows, or realtime snapshots. Fresh `X-TRADE` messages may populate only the bounded latest-event trade-tape buffer.

## Phase 4.11B Intraday Chart Capability Audit

Phase 4.11B inspected the production adapter, deterministic fixtures, installed `ssi_fc_data` 2.2.2 package, existing sanitized live evidence, and current daily chart contract. The endpoint itself is real, but no candidate query interval is verified for a production chart allowlist.

| Candidate | Capability status | Evidence | Provider method/parameter | Live verification | Limits/session/finality | Implementation |
| --- | --- | --- | --- | --- | --- | --- |
| `1m` | `partially_verified` | SDK exposes integer `resolution=1`; old returned rows showed minute-like spacing, but not from a verified `1m` request | `IntradayOhlc`; likely `resolution`, units unproven | 2026-07-14 bounded call blocked by `network_error` | Unknown; no final flag or session contract | Do not expose; verify in 4.11C |
| `5m` | `unverified` | StockClock accepts/detects 5-minute fixtures only | Provider value unresolved | Not run after network blocker | Unknown | Do not expose |
| `15m` | `unverified` | Cadence detector recognizes 15 minutes; no provider proof | Provider value unresolved | Not run | Unknown | Do not expose |
| `30m` | `unverified` | Cadence detector recognizes 30 minutes; no provider proof | Provider value unresolved | Not run | Unknown | Do not expose |
| `1h` | `unverified` | Current adapter sends a `timeFrame=1h` hint, but prior SSI output differed from that hint | `resolution=60`, `60m`, and `1h` mappings all unresolved | Prior request was throttled or returned minute-like cadence | Unknown | Do not expose |

Installed SDK evidence proves `GET /api/v2/Market/IntradayOhlc`, symbol/date/page parameters, ascending order, and an integer `resolution` member with default `1`. It does not define units, an enum, supported values, maximum range, maximum pages, exchange coverage, timestamps, auction behavior, lunch gaps, or final bars. Repository fixtures prove normalization and failure handling only. They are not provider-response certification.

The current compact pulse remains `partial`: it uses a 7-calendar-day request, an internal page size of 1,000 (maximum 20 pages in the generic fetcher), a public default of 8 latest rows, a 60-second service cache, and a 60-second symbol/timeframe rate-limit cooldown. This existing behavior is not the future chart history contract.

Phase 4.11C may implement a separate bounded history endpoint only after at least one interval is live-verified. Phase 4.11D separately owns any realtime last-bar design.

## Phase 4.0B Intraday Root-Cause Result

Phase 4.0B did not find a company-route wiring failure. The existing backend calls the SSI IntradayOhlc provider through the current SSI auth/cache path and maps provider-returned cadence fields.

The root cause was inside the SSI fetcher request behavior. The dashboard requested a 7-day range with the public `intraday_limit` as SSI `pageSize` and `ascending=true`. With the default public limit of 8, SSI returned only the oldest first-page minute rows from the start of the window, so the service saw `2026-06-17` as the latest intraday date while SSI DailyOhlc was already `2026-06-24`.

The fix keeps the public response limit but fetches IntradayOhlc pages internally with `pageSize=1000`, sorts normalized rows, and then returns the latest public limit. Direct patched-fetcher verification returned 8 rows using 2 pages, from `2026-06-24T14:23:56` to `2026-06-24T14:45:00`.

An isolated patched-backend force-refresh audit on 2026-06-24 reported:

- `intraday_status.status=ok` for FPT and `unavailable` for some other audit tickers
- `usable current pulse rows=1/8`
- `intraday_latest_date=2026-06-24`
- `daily_price_date=2026-06-24`
- `date_match=matched` for the usable FPT row
- `intraday_requested_timeframe=1h`
- `intraday_actual_granularity=1m`
- `intraday_actual_granularity_seconds=61`
- `intraday_candles` public count 8 for the usable FPT row
- `intraday_pulse` non-null for the usable FPT row

The implementation also keeps malformed normalized intraday rows unavailable instead of exposing an `ok` pulse from null-only rows. Intraday remains a partial capability until current-date coverage is observed across the broader ticker set; unavailable rows still return `intraday_candles=[]` and `intraday_pulse=null`.

## Phase 4.0B-2 Intraday Live Request Failure Diagnostics

Phase 4.0B-2 inspected the current live failure path after the Phase 4.0B paging fix. The request path remained the expected SSI path:

```text
company endpoint -> watchlist builder -> SSI fetcher -> IntradayOhlc
```

The fetcher still requests IntradayOhlc with symbol-scoped parameters, `timeFrame=1h`, `pageIndex=1`, internal `pageSize=1000`, and `ascending=true`; the public candle limit is applied only after rows are fetched and sorted.

The live FPT probe returned a provider error payload with HTTP status `200` and SSI provider code `429`. The backend now classifies this as `failure_class=rate_limited` and exposes only sanitized diagnostics under `intraday_status.diagnostics` and company `intraday.diagnostics`. No raw provider body, auth header, token, account ID, consumer ID, or consumer secret is exposed.

This phase did not change canonical `latest_price` ownership, did not use intraday as realtime, did not add fallback providers, and did not alter DailyOhlc/DailyStockPrice behavior.

## Phase 4.0B-3 Intraday Rate-Limit Guardrails

Phase 4.0B-3 added an in-memory, per-process cooldown for SSI `IntradayOhlc` after the fetcher classifies a response as `rate_limited`. Both HTTP `429` and SSI provider code `429` start the cooldown. The key is normalized ticker plus requested timeframe, so one throttled ticker/timeframe does not suppress other tickers or other timeframe requests.

During an active cooldown, `SsiFastConnectFetcher.get_intraday_ohlcv` returns:

```text
status = unavailable
failure_class = rate_limited
reason = SSI IntradayOhlc rate limit cooldown active.
rows = []
count = 0
```

The fetcher returns this before requesting an access token or calling `GET /Market/IntradayOhlc`, even if the service caller is force-refreshing. Sanitized diagnostics include `cooldown_active`, `cooldown_recorded`, `cooldown_seconds`, `cooldown_remaining_seconds`, `cooldown_until`, endpoint, symbol, requested timeframe, page size, and public limit. Raw provider bodies, auth headers, tokens, account IDs, consumer IDs, and consumer secrets remain excluded.

The default cooldown is `SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS=60`; `0` disables the guard. This does not change DailyOhlc, DailyStockPrice, canonical `latest_price`, realtime snapshot, or trade-tape ownership. Intraday remains `partial` until current usable rows are observed broadly.

## Phase 4.0C Realtime Snapshot Root-Cause Result

Phase 4.0C did not find a route, service, config-gate, symbol-normalization, batch, or parser bug that explains the current SSI realtime snapshot unavailability.

Observed baseline against the already-running local backend on 2026-06-24:

- `GET /api/v1/stocks/vn/realtime?tickers=FPT` returned `status=unavailable`.
- Endpoint quote row count was `0`.
- A force-refresh FPT audit reported `watchlist usable snapshots=0/1`.
- The live endpoint detail reported a 404 from the SSI realtime REST candidate path.
- The same audit kept daily OHLCV, DailyStockPrice, foreign flow, technical indicators, and FPT intraday pulse reliable.

Code inspection found the public route calls `VietnamMarketService.build_realtime_snapshot`, which calls `SsiFastConnectFetcher.get_realtime_snapshot`. In Phase 4.0C this path still tried one-symbol calls for SSI realtime REST candidate endpoints and only mapped rows with meaningful quote fields. Phase 4.0C-2 supersedes that runtime probing behavior because the candidate names were not verified as a supported SSI contract.

Conclusion: in the current environment, realtime remains a provider/endpoint availability issue, not a data substitution opportunity. The dashboard must keep realtime unavailable with `realtime_snapshot=null` until a current SSI response returns usable quote rows with `status=ok`.

## Phase 4.0C-2 SSI Realtime Endpoint Discovery

The discovery artifact is `ssi_realtime_endpoint_discovery.txt`, produced from repository text files under the requested scope plus existing SSI notes. The search inspected these files or file groups for SSI realtime endpoint contracts, SDK wrappers, method names, enums, configuration, and documentation references:

- `data_provider/ssi_fastconnect_fetcher.py`
- `scripts/ssi_fastconnect_smoke.py`
- `src/config.py`
- `src/core/config_registry.py`
- `src/services/vietnam_market_service.py`
- `.env.example`
- `requirements.txt`
- `pyproject.toml`
- `setup.cfg`
- `docs/SSI_FASTCONNECT_INTEGRATION.md`
- `docs/SSI_DATA_CAPABILITY_MATRIX.md`
- `docs/VN_DASHBOARD_ROADMAP.md`
- `docs/RUNBOOK_VN.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `docs/resources/realtime-data/ssi-iboard.md`

Candidate endpoints/methods found:

- Runtime speculative REST candidates from the existing fetcher: `RealtimeQuote`, `RealtimePrice`, `RealtimeSnapshot`, and `SecuritiesRealtime`.
- Internal project method: `SsiFastConnectFetcher.get_realtime_snapshot`.
- Public project API: `GET /api/v1/stocks/vn/realtime`.
- Smoke-script SSI FC Data base URLs: `https://fc-data.ssi.com.vn/api/v2/Market` and `https://fc-data.ssi.com.vn/v2.0/Market`.

No verified SSI FastConnect SDK package, wrapper, enum, or documented method named `GetRealtime`, `GetQuote`, `RealtimeQuote`, `StockQuote`, `MarketData`, `TradingData`, or equivalent was found. The iBoard note in `docs/resources/realtime-data/ssi-iboard.md` is reference-only and has unknown authentication, API contract, rate-limit, timestamp, and price semantics; it is not wired into the dashboard.

Conclusion: a supported SSI REST realtime endpoint is not identified in this repository. Phase 4.0C-3 supersedes REST probing with the SSI streaming direction. Daily OHLCV, DailyStockPrice, and IntradayOhlc behavior is unchanged.

## Phase 4.0C-3 SSI Streaming Realtime Adapter Direction

Official SSI FastConnect Data docs describe realtime as a streaming feed, not a REST quote endpoint. The documented realtime stream message families relevant to dashboard quote semantics are:

- `X`: combined quote/trade context.
- `X-QUOTE`: order-book/bid-ask ladder context only.
- `X-TRADE`: latest matched trade context.
- `F`: trading session/status context only.
- `R`: foreign-room/foreign-flow context only.

The current implementation adds deterministic parser coverage for buffered SSI streaming envelopes shaped like:

```text
DataType = X, X-QUOTE, X-TRADE, F, R, or MI
Content = JSON object or JSON string containing RType, Symbol, and stream fields
```

Parser rules:

- Ignore malformed envelopes and unsupported data types.
- Ignore symbols outside the requested ticker set.
- Normalize ticker symbols before returning rows.
- Parse `Content` safely when SSI sends it as a JSON string.
- Preserve provider timestamps from `TradingDate` and `Time` when present.
- Treat `X-QUOTE` as order-book context. Do not synthesize `LastPrice`, realtime snapshot price, or matched trade rows from bid/ask fields.
- Treat `MI` as market-index pulse context. Do not synthesize stock rows, REST DailyIndex rows, or watchlist price fields from index stream rows.
- Treat `X` and `X-TRADE` as latest-trade snapshot candidates only when `LastPrice` is present.
- Do not describe the bounded `X-TRADE` event buffer as full trade-tape history.
- Treat `F` as session/status context only. Preserve raw `TradingSession` / `TradingStatus` fields in a dedicated cache; do not put `F` rows in realtime quote snapshots or trade-tape rows, and do not infer code meanings.
- Treat `R` as foreign-room context only. Preserve explicit `TotalRoom`, `CurrentRoom`, `FBuyVol`, `FSellVol`, `FBuyVal`, and `FSellVal`-style fields in a dedicated cache; do not put `R` rows in realtime quote snapshots, trade-tape rows, order-book rows, session/status rows, DailyStockPrice enrichment, or `latest_price`.

Runtime state remained unavailable at the end of Phase 4.0C-3 because the repository did not implement a bounded SSI streaming client, subscription lifecycle, reconnection/backoff policy, or request-safe cache handoff. `SsiFastConnectFetcher.get_realtime_snapshot()` did not open a streaming connection and did not probe REST realtime candidates. It returned:

```text
status = unavailable
reason = SSI realtime requires FastConnect streaming adapter; connection semantics not implemented.
rest_status = unsupported
streaming_status = not_implemented
```

Phase 4.0C-5 adds the first request-safe cache handoff skeleton. Phase 4.0C-6 adds the official SSI client adapter behind the disabled streaming runtime flag. Streaming still runs outside request handlers, subscribes only to requested symbol scopes, avoids `X: ALL` in runtime, and surfaces rows only after current stream messages are parsed and cached fresh in the existing public realtime response shape.

## Phase 4.0C-4 Official Python Client Inspection

The official Python package was installed in the local development environment for inspection:

```text
package name: ssi-fc-data
import module: ssi_fc_data
installed version: 2.2.2
home page: https://github.com/SSI-Securities-Corporation/python-fcdata
dependencies: requests, websocket-client
```

Import/module discovery found these relevant official modules:

- `ssi_fc_data.fc_md_client`
- `ssi_fc_data.fc_md_stream`
- `ssi_fc_data.model.api`
- `ssi_fc_data.signalr._connection`
- `ssi_fc_data.signalr.transports._transport`

Official streaming API surface found:

- `MarketDataClient(config)` retrieves and caches an access token from `config.url + api/v2/Market/AccessToken`.
- The installed package metadata config sample uses `auth_type`, `consumerID`, `consumerSecret`, `url`, and `stream_url`. No `PrivateKey` reference was found in the installed `ssi_fc_data 2.2.2` package source.
- `MarketDataStream(config, MarketDataClient(config), on_close=None, on_open=None)` owns the streaming connection.
- `MarketDataStream.start(on_message, on_error, selected_channel)`:
  - calls the market-data client access-token path;
  - creates an `Authorization` header from `config.auth_type` plus the access token;
  - connects to `config.stream_url + v2.0/signalr`;
  - registers hub `FcMarketDataV2Hub`;
  - subscribes client handlers for `Broadcast` and `Error`;
  - invokes hub method `SwitchChannels` with the selected channel on open;
  - starts the websocket transport on a daemon thread.
- `MarketDataStream.swith_channel(channel)` invokes `SwitchChannels` again. The method name is spelled `swith_channel` in the installed package.

Official sample metadata shows the subscription value is a plain channel string supplied by the caller. That matches the documented channel shape such as `X-TRADE: ACB`, `X-QUOTE: ACB`, or `X: ACB`. Runtime code must not subscribe to `X: ALL`.

Safe bounded one-shot adapter feasibility:

- Not implemented in this phase.
- The official client exposes connection and subscription primitives, but not a public bounded receive/wait API.
- The transport starts a background daemon websocket thread and does not expose a documented join/timeout lifecycle.
- The bundled SignalR negotiation path contains a `print(self.headers)` statement, which would print the `Authorization` header if used directly. Runtime code must not use it without a wrapper or patch that prevents secret output.
- `Connection.close()` calls `self.__transport.close()`, while the bundled transport exposes `stop()`; this needs wrapper-level close handling before runtime use.

Conclusion: a minimal future adapter is feasible only as a background service, not inside request handlers. It should wrap the official client, subscribe to symbol-scoped channels only, collect messages into a thread-safe cache, call the parser added in Phase 4.0C-3, suppress or patch header printing, and provide an explicit stop path that uses the transport `stop()` method if the official `close()` path is not functional. `get_realtime_snapshot()` remains unavailable until that adapter is implemented and validated.

## Phase 4.0C-5 Safe Streaming Manager Skeleton

Phase 4.0C-5 added the internal architecture for future SSI streaming realtime without enabling live streaming:

- `SSI_STREAMING_REALTIME_ENABLED=false` by default.
- `SSI_STREAMING_REALTIME_CACHE_TTL_SECONDS=15` by default.
- `SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE=X:{symbol}` by default.
- `SsiStreamingRealtimeManager` owns explicit lifecycle states: `disabled`, `stopped`, `starting`, `running`, and `errored`.
- `RealtimeSnapshotCache` stores latest normalized snapshot candidates per symbol and marks empty or stale cache reads unavailable.
- `SsiFastConnectFetcher.get_realtime_snapshot()` reads only the manager/cache path when streaming runtime is enabled; it does not open a websocket and does not probe REST realtime candidates.
- Request handlers do not start streams. Module imports do not start streams.
- Runtime channel construction rejects `ALL` subscriptions.
- A single `X-TRADE` message may update the realtime snapshot candidate and, after Phase 4.7C, may populate the bounded latest-event trade-tape buffer. It still must not be described as full historical time-and-sales or used to mark true trade-history support reliable.

Default runtime response remains unavailable:

```text
status = unavailable
reason = SSI streaming realtime manager disabled.
rest_status = unsupported
streaming_status = disabled
manager_state = disabled
cache_status = disabled
```

When streaming runtime is explicitly enabled but the background manager is not running, has an empty cache, has stale cache rows, or has errored, realtime remains unavailable with sanitized diagnostics for `streaming_manager_not_started`, `streaming_cache_empty`, `streaming_cache_stale`, or `streaming_manager_error`. A cache hit is only a realtime snapshot candidate; live reliability still requires current stream evidence.

## Phase 4.0C-6 Official Adapter Behind Config

Phase 4.0C-6 adds the official SSI Python client adapter without enabling live realtime by default:

- `SSI_STREAMING_REALTIME_ENABLED=false` remains the default and has highest precedence.
- `SSI_STREAMING_REALTIME_STREAM_URL=https://fc-datahub.ssi.com.vn/` is the default stream root.
- The official `ssi_fc_data` package is imported lazily only when the adapter starts.
- The official market-data client is instantiated only when streaming is enabled, required config is present, and the background manager is explicitly started.
- Missing streaming config returns `SSI streaming realtime configuration incomplete.`
- Missing `ssi_fc_data` returns `SSI streaming realtime package unavailable.`
- The adapter suppresses the official header-printing path during stream start and uses the transport `stop()` method when available.
- Tests use mocked official modules and prove no header-like secret text is emitted.

This phase does not prove live reliability. Under the Phase 4.5A vocabulary, realtime is `optional_live_dependent` until current live stream rows are observed through the manager/cache path.

## Phase 4.0C-7E Streaming Channel Template Fix

Live diagnostics proved the official SSI stream requires no-space channel strings. Working verifier channels include `X:FPT`, `X-QUOTE:FPT`, and `X-TRADE:FPT`; Phase 4.8I uses the same no-space shape for `R:FPT`. Old spaced forms such as `X: FPT`, `X-QUOTE: FPT`, and `X-TRADE: FPT` can start transport but did not receive callbacks in live verification.

The project default is now `SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE=X:{symbol}`. Explicit custom overrides remain respected for diagnostics, and the verifier still supports channel-format variants with both spaced and no-space forms. This change does not add backend auto-start, does not mark realtime production reliable, does not alter `latest_price`, and does not implement trade tape.

## Required Guardrails

- This matrix is an audit/planning aid, not a new API contract.
- `docs/VN_DATA_CONTRACT.md` remains the contract source for public status, null, empty-list, and source-ownership semantics.
- SSI DailyOhlc owns canonical daily close/OHLCV/chart fields.
- SSI DailyStockPrice owns reference/ceiling/floor, matched stats, and foreign-flow fields.
- Indicators are derived from SSI DailyOhlc.
- Realtime, trade tape, order book, session/status, and foreign room are optional live contexts and must not be called reliable unless the current audit observes `ok` status and usable data.
- News, fundamentals, corporate actions, dividends, and macro need future provider contracts.
- Corporate actions and dividends must not be inferred from price gaps.
- Mozyfin/KBS fallback must not be reintroduced.
- KBS remains legacy-only and disabled by default.

## Local Refresh Command

Run from the repository root with the backend already started:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit_vn_data_capability.ps1
```

Use cache bypass only when the audit explicitly needs current provider fetches:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit_vn_data_capability.ps1 -ForceRefresh
```
