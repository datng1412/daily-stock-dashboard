# VN Dashboard UI States

## Purpose

This file defines user-facing states for the VN dashboard and company detail page. It is the UI companion to `docs/VN_DATA_CONTRACT.md` and `docs/VN_COMPANY_DETAIL_DESIGN.md`.

Rules that apply to every state:

- Daily SSI data remains visible when required SSI DailyOhlc fields are valid.
- Optional live sections render only when real data exists.
- Missing object data renders as `null`.
- Missing list data renders as `[]`.
- Endpoint attempts, HTTP status, raw provider error summaries, stale-date details, and retryability belong in diagnostics, not primary metric rows.
- User-facing copy must stay neutral and must not become investment advice.

## Section-Level State Vocabulary

Use section-level states to describe what the user can do with each block without turning optional failures into full-page failures.

| State | User-facing meaning | Typical use |
| --- | --- | --- |
| `ready` | Section has usable data and can be inspected. | Daily scan table, selected ticker summary, chart, or source-labeled detail block. |
| `loading` | First request is in progress and no previous data exists for this section. | Initial watchlist load or first company-detail load. |
| `refreshing` | A new request is in progress while previous successful data remains visible. | Preset switch, manual refresh, or retry where stale UI should not blank. |
| `partial` | Core data exists, but one or more optional or quality checks have caveats. | Daily SSI data present while profile, live, index, or future modules are unavailable. |
| `unavailable` | A section was attempted but has no usable data. | SSI realtime unavailable, trade tape unavailable, stale intraday, or index components unavailable. |
| `disabled` | A future or optional module is intentionally off. | News until NewsProvider exists; future external modules before provider selection. |
| `failed` | Required section cannot load and the user cannot inspect its data. | Daily scan fails with no previous rows or company daily data cannot load. |

Clarification:

- `success` is internal request-state vocabulary for frontend orchestration.
- `ready` is the preferred user-facing section state label.
- Do not introduce `success` as visible UI copy unless an existing screen already uses it that way.

## Severity Model

Daily SSI data availability is more important than optional live or future-module availability:

- Daily data unavailable is serious because it blocks the core scan.
- Realtime unavailable is optional/minor when DailyOhlc is valid.
- Trade tape unavailable is optional/minor when DailyOhlc is valid.
- News disabled is expected until a NewsProvider exists.
- Optional live/future states should not erase valid daily scan data.
- Realtime polling or visibility changes must not clear valid watchlist rows, selected ticker detail, or chart state.
- A `partial` dashboard or ticker state can mean optional sections are unavailable; it must not imply daily SSI data failed when required DailyOhlc fields are valid.

Provider endpoint details, HTTP status, retryability, and raw provider summaries belong in diagnostics, not primary UI.

## State Matrix

| State | API condition | Primary UI copy | Metric rows allowed | Must not show | Diagnostics behavior | Tests to add/update later |
| --- | --- | --- | --- | --- | --- | --- |
| Daily OK + realtime unavailable | Required daily row is usable; `realtime_status.status = unavailable` or `disabled`; `realtime_snapshot = null`; optional `reason_code` may be `running_idle`, `cache_empty`, `ticker_not_bootstrapped`, `config_disabled`, etc. | Reason-aware short copy such as `SSI stream is running but no recent tick is cached for this ticker. Daily SSI data is still available.` | Daily close, daily OHLCV, DailyStockPrice fields that exist | Snapshot price, realtime change, session volume, or placeholder `-` rows from `realtime_snapshot` | Endpoint/http/raw provider details under status diagnostics or diagnostics-only structures; safe manager/cache reason may be visible | Watchlist/company UI tests assert reason-aware unavailable copy and no realtime metric rows |
| Daily OK + intraday stale/no rows | Daily row is usable; `intraday_status.status = unavailable`; `intraday_candles = []`; `intraday_pulse = null`; `reason_code` distinguishes date mismatch, no rows, rate limit, or provider error | Reason-aware short copy such as `SSI IntradayOhlc latest candle date does not match the latest daily trading date.` or `SSI IntradayOhlc returned no usable candles.` | Daily and DailyStockPrice fields only; a neutral provider-cadence note if available | Intraday pulse cards, stale intraday close/change/volume metric rows, or requested timeframe as actual interval | Put latest intraday date, daily date, date match, cadence status, and failure class under intraday status/diagnostics | Contract test for stale intraday returns `pulse = null`; UI test hides pulse metrics and avoids `1H intraday` wording |
| Daily OK + intraday cadence mismatch | Daily row is usable; `intraday_status.status = ok`; `intraday_status.reason_code = cadence_mismatch`; real candles exist but returned cadence differs from request | `SSI intraday cadence differs from the requested timeframe.` | Real intraday rows and pulse metrics with provider-returned cadence labels | Copy implying requested timeframe is actual cadence | Requested timeframe and detected actual granularity remain visible | Backend/UI tests classify data-quality check as partial without changing DailyOhlc price |
| Daily OK + trade tape empty | Daily row is usable; `trade_tape_status.status = unavailable` or `disabled`; watchlist `trade_tape = []`; company `trade_tape.trades = []`; `reason_code` can be `latest_trade_stream_only` when only X-TRADE latest context is proven | `Historical trade tape is unavailable. X-TRADE is latest-trade stream context only.` or another short safe unavailable reason | Daily and DailyStockPrice fields only | Trade rows, latest trade, wrapper-object fields, placeholder trade metrics, or historical tape inferred from latest stream messages | Endpoint/http/raw provider details under status diagnostics or diagnostics-only structures | Contract test asserts public watchlist `trade_tape` is a list; UI test hides trade rows and keeps X-TRADE separate |
| News disabled | `news = []`; `news_status.status = disabled` | `News disabled.` | None from news | News cards, fake news items, stale news placeholders | Optional reason can appear in collapsed source coverage | UI test asserts disabled copy and no news item cards |
| News not implemented | Future module uses `not_implemented` while no provider exists | `News not implemented.` | None from news | Fake news items or Mozyfin dependency copy | Keep implementation reason short; no endpoint diagnostics unless a provider exists | Company page test groups future module state with financials/events |
| Financials not implemented | Financial module status is `not_implemented` | `Financials not implemented.` | None | Ratios, statements, or valuation fields | No provider diagnostics until a provider exists | Company page future-module grouping test |
| Events/corporate actions disabled/not configured | Events/corporate actions status is `disabled`, `not_configured`, `not_implemented`, `unavailable`, or `error`, with `events=[]`/`items=[]` | `Corporate actions unavailable.` or `Corporate actions not implemented.` | None | Inferred dividends, rights, splits, event markers from price gaps, or copy implying verified absence of events | Sanitized provider, request domain, status, row count, failure class, and last checked time may appear only in diagnostics | Contract and UI tests assert no inferred events and no fake event rows |
| Profile partial | Provider response is usable but important fields such as name or industry are null; `profile.status` may be `ok`; completeness is `partial` | `Profile partial. Some metadata is unavailable.` | Symbol, exchange, market, source, and fields that exist | Empty rows for missing name/industry, or treating partial profile as daily-data failure | Missing-field list belongs in profile quality or diagnostics | Contract test for profile quality; UI test hides null metadata rows |
| Profile unavailable | SSI metadata endpoints return no exact symbol match or fail; `profile.status = unavailable`; completeness is `unavailable` | `Profile unavailable. Daily SSI data is still available.` | Ticker plus independent daily and DailyStockPrice fields | Invented company name/industry/issuer, placeholder metadata rows, or daily-data failure | Sanitized attempted endpoints, row counts, and failure class remain collapsed | Backend/UI tests preserve daily sections and hide missing metadata rows |
| Daily OK + DailyStockPrice partial | DailyOhlc row is usable; `daily_stock_price.status = ok`; `quality_status = partial` due to missing enrichment fields or unknown alignment | `DailyStockPrice enrichment partial.` | Existing source-labeled enrichment fields only, with shares/VND units | Null fields as zero, placeholder `-` metric rows, or clearing daily rows/chart | Missing-field coverage and sanitized request metadata stay in source coverage/diagnostics | Backend and UI tests assert null preservation and hidden optional metrics |
| Daily OK + bounded DailyStockPrice foreign history | DailyOhlc row is usable; recent DailyStockPrice rows include enough `foreign_net_volume` values for 5D or 20D summaries | Show `Foreign net 5D` / `Foreign net 20D` only from real values, or show an insufficient-row note when the existing short-history block is visible | Source-labeled DailyStockPrice latest fields plus latest-available 5D/20D summaries in shares | Mixing value and volume units, inferring missing rows from calendar days, broad scans, or hiding valid daily rows when history is short | `daily_stock_price.diagnostics` may include foreign-history row count/date span/status | Backend tests cover 20-row sums, partial history, zero preservation, and one bounded per-symbol call |
| Daily OK + DailyStockPrice date mismatch | DailyOhlc row is usable; `daily_stock_price.date_match = mismatched`; enrichment quality is partial | `DailyStockPrice date differs from DailyOhlc.` | Existing source-labeled values with explicit date caveat | DailyStockPrice close replacing daily close, silent blend, or clearing selected ticker/chart | DailyOhlc date, DailyStockPrice date, match state, and source labels in data quality/diagnostics | Backend and UI tests assert canonical DailyOhlc price remains unchanged |
| DailyOhlc vs DailyStockPrice mismatch | Same ticker/date has different DailyOhlc close/volume and DailyStockPrice close/matched volume | `Daily source mismatch detected.` | Both values may be shown if clearly source-labeled | Silent overwrite, blended value, or unlabeled comparison | Data Quality Summary lists sources, dates, values, and canonical source | Phase 1 tests assert mismatch summary appears |
| `final_close_status = unknown` | Daily finality cannot be confirmed | `Final close status unknown.` | Daily data with finality caveat | Copy that implies final close is confirmed | Diagnostics may include session/calendar/source limitations | Unit test for unknown finality copy |
| `final_close_status = provisional` | Daily candle may still change | `Daily close may still be provisional.` | Daily data with provisional badge | Copy that says final/official if source does not confirm | Diagnostics may include VN session context | Unit/UI test for provisional badge |
| `final_close_status = final` | System has defensible final-close signal | `Final close confirmed.` | Daily data and finality badge | Overstated precision beyond available source metadata | Diagnostics optional; no raw source body | Unit/UI test for final badge |
| `adjusted_price_status = unknown` | Adjustment metadata is absent or unconfirmed | `Adjusted price status unknown.` | Raw daily and DailyStockPrice values with source labels | Corporate-action inference or adjusted-event claims | Diagnostics may explain missing structured event source | UI test for conservative adjusted-price copy |
| Index components unavailable | IndexComponents request fails or returns no usable rows | `SSI index components unavailable.` | IndexList or component count only if real rows exist | Hardcoded VN30 constituents or fallback provider members | Endpoint/http details under index diagnostics | API/UI test for clean unavailable state |
| Daily OK + index data unavailable | Watchlist DailyOhlc rows are usable; DailyIndex and/or IndexComponents return unavailable with empty rows | `SSI daily index unavailable.` / `SSI index components unavailable.` | Watchlist, selected ticker, chart, and any real independent index rows | Fake index values, zero converted from null, inferred breadth, or daily-data failure | Index endpoint/code/date/coverage/failure details remain in diagnostics | UI tests preserve watchlist/selection/chart while index context degrades independently |
| Fixture mode | Fixture/test mode is explicitly enabled by runtime config or test fixture | `Fixture data mode.` | Fixture-backed fields only with source/fixture labels | Treating fixture output as live SSI data | Diagnostics identify fixture source without secrets | Smoke/test asserts fixture labels are explicit |
| Cache stale | Cached block is older than expected for its source, or stale flag is set | `Cached data may be stale.` | Existing values if source/date/fetched_at remain visible | Claiming stale data is current, or mixing cache error with provider unavailable | Cache age, source block, and fetched time in diagnostics | Cache-state UI test and observability contract test |

## Copy Rules

- Use source-aware labels: `SSI DailyOhlc`, `SSI DailyStockPrice`, `SSI IntradayOhlc`, `SSI realtime`, `SSI trade tape`.
- Prefer section-level unavailable copy over per-field placeholders.
- Keep primary copy short. Put technical details in diagnostics.
- Do not use raw provider error text in primary cards.

## Implementation Notes For Progressive Workspace Phases

- Phase 1 adds the Data Quality Summary that surfaces mismatch, finality, adjusted-price, stale intraday, unavailable live data, and profile partial states.
- Phase 2 cleans public contract shapes and moves provider/debug details to diagnostics.
- Phase 2.2 frontend rendering consumes normalized `null`/`[]` live-section shapes and keeps live status diagnostics in collapsed diagnostics panels on dashboard and company detail views.
- Phase 3.2A adds a visual Data Readiness strip on `/vietnam` using user-facing labels such as `Ready`, `Partial`, `Unavailable`, and `Disabled`. It derives from existing loaded frontend data and status objects; it does not introduce API contract fields or request-state behavior.
- Phase 3.2B adds lightweight tooltip/accessibility explanations for Data Readiness strip items. The explanations are frontend-only, source/status-oriented, and keep endpoint details, HTTP status, retryability, and raw provider summaries out of primary UI.
- Phase 3.2C keeps previous successful `/vietnam` watchlist rows visible during refresh or pending list changes. First load still uses the normal loading state; refresh uses `Updating...`; request-level failure uses `Last update failed` while preserving previous rows/list/preset/selection. Per-ticker unavailable rows remain row-level states and do not block committing a successful response.
- Phase 3.2D applies section-level states across existing `/vietnam` sections. The indicator table shows a serious `Daily data unavailable` state only when no daily rows are loaded; selected ticker and stock-detail sections show concise unavailable states when no valid row exists; chart/intraday/realtime/trade-tape sections show compact `Ready`, `Loading`, `Unavailable`, `Disabled`, or `Failed` badges as appropriate. Optional live or future unavailable states remain visually minor when valid daily SSI rows exist, diagnostics remain lower priority, and Phase 3.2C previous-data refresh behavior is preserved.
- Phase 3.3A applies progressive disclosure to the selected ticker so the compact header remains a daily explanation surface while Price context, Flow context, Technical context, Live context, Source coverage, News context, and Diagnostics carry secondary detail. Price context may be open by default; optional live, source, news, and diagnostics groups remain lower priority. Raw fields, cache internals, endpoint/provider diagnostics, and rule inputs stay out of primary cards.
- Phase 3.3B keeps the same selected ticker disclosure structure but shortens labels, reduces repeated source wording, and keeps optional unavailable copy calm. Source coverage remains available at section level, News context uses `News available`, `News disabled`, or `News not implemented`, and raw provider/cache/rule details remain Diagnostics-only.
- Phase 3.5A adds client-side indicator-table filters. The filtered empty state uses `No rows match current filters.` and must remain distinct from serious daily-data failure. Filter result counts are client-derived. Resetting filters changes only ticker search and filter selects, not the active preset, active watchlist, custom watchlist input, committed rows, or selected ticker. If filters hide the selected ticker row while its data still exists, keep the selected ticker summary visible and show `Selected ticker is hidden by filters.` Optional live unavailable filters remain neutral and do not make daily data unavailable.
