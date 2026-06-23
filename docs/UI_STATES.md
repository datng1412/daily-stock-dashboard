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

## State Matrix

| State | API condition | Primary UI copy | Metric rows allowed | Must not show | Diagnostics behavior | Tests to add/update later |
| --- | --- | --- | --- | --- | --- | --- |
| Daily OK + realtime unavailable | Required daily row is usable; `realtime_status.status = unavailable` or `disabled`; `realtime_snapshot = null` | `SSI realtime unavailable. Daily SSI data is still available.` | Daily close, daily OHLCV, DailyStockPrice fields that exist | Snapshot price, realtime change, session volume, or placeholder `-` rows from `realtime_snapshot` | Endpoint/http/raw provider details under status diagnostics or diagnostics-only structures | Watchlist/company UI tests assert realtime unavailable copy and no realtime metric rows |
| Daily OK + intraday stale | Daily row is usable; `intraday_status.status = unavailable`; `intraday_candles = []`; `intraday_pulse = null`; diagnostics show stale/mismatched date | `SSI intraday unavailable for the latest daily date.` | Daily and DailyStockPrice fields only | Intraday pulse cards, stale intraday close/change/volume metric rows | Put latest intraday date, daily date, and date match under intraday status/diagnostics | Contract test for stale intraday returns `pulse = null`; UI test hides pulse metrics |
| Daily OK + trade tape empty | Daily row is usable; `trade_tape_status.status = unavailable` or `disabled`; watchlist `trade_tape = []`; company `trade_tape.trades = []` | `SSI trade tape unavailable.` | Daily and DailyStockPrice fields only | Trade rows, latest trade, wrapper-object fields, or placeholder trade metrics | Endpoint/http/raw provider details under status diagnostics or diagnostics-only structures | Contract test asserts public watchlist `trade_tape` is a list; UI test hides trade rows |
| News disabled | `news = []`; `news_status.status = disabled` | `News disabled.` | None from news | News cards, fake news items, stale news placeholders | Optional reason can appear in collapsed source coverage | UI test asserts disabled copy and no news item cards |
| News not implemented | Future module uses `not_implemented` while no provider exists | `News not implemented.` | None from news | Fake news items or Mozyfin dependency copy | Keep implementation reason short; no endpoint diagnostics unless a provider exists | Company page test groups future module state with financials/events |
| Financials not implemented | Financial module status is `not_implemented` | `Financials not implemented.` | None | Ratios, statements, or valuation fields | No provider diagnostics until a provider exists | Company page future-module grouping test |
| Events/corporate actions not implemented | Events/corporate actions status is `not_implemented` or unavailable due to no explicit source | `Corporate actions not implemented.` | None | Inferred dividends, rights, splits, or event markers from price gaps | No provider diagnostics until a provider exists | Company page test asserts no inferred events |
| Profile partial | Provider response is usable but important fields such as name or industry are null; `profile.status` may be `ok`; completeness is `partial` | `Profile partial. Some metadata is unavailable.` | Symbol, exchange, market, source, and fields that exist | Empty rows for missing name/industry, or treating partial profile as daily-data failure | Missing-field list belongs in profile quality or diagnostics | Contract test for profile quality; UI test hides null metadata rows |
| DailyOhlc vs DailyStockPrice mismatch | Same ticker/date has different DailyOhlc close/volume and DailyStockPrice close/matched volume | `Daily source mismatch detected.` | Both values may be shown if clearly source-labeled | Silent overwrite, blended value, or unlabeled comparison | Data Quality Summary lists sources, dates, values, and canonical source | Phase 1 tests assert mismatch summary appears |
| `final_close_status = unknown` | Daily finality cannot be confirmed | `Final close status unknown.` | Daily data with finality caveat | Copy that implies final close is confirmed | Diagnostics may include session/calendar/source limitations | Unit test for unknown finality copy |
| `final_close_status = provisional` | Daily candle may still change | `Daily close may still be provisional.` | Daily data with provisional badge | Copy that says final/official if source does not confirm | Diagnostics may include VN session context | Unit/UI test for provisional badge |
| `final_close_status = final` | System has defensible final-close signal | `Final close confirmed.` | Daily data and finality badge | Overstated precision beyond available source metadata | Diagnostics optional; no raw source body | Unit/UI test for final badge |
| `adjusted_price_status = unknown` | Adjustment metadata is absent or unconfirmed | `Adjusted price status unknown.` | Raw daily and DailyStockPrice values with source labels | Corporate-action inference or adjusted-event claims | Diagnostics may explain missing structured event source | UI test for conservative adjusted-price copy |
| Index components unavailable | IndexComponents request fails or returns no usable rows | `SSI index components unavailable.` | IndexList or component count only if real rows exist | Hardcoded VN30 constituents or fallback provider members | Endpoint/http details under index diagnostics | API/UI test for clean unavailable state |
| Fixture mode | Fixture/test mode is explicitly enabled by runtime config or test fixture | `Fixture data mode.` | Fixture-backed fields only with source/fixture labels | Treating fixture output as live SSI data | Diagnostics identify fixture source without secrets | Smoke/test asserts fixture labels are explicit |
| Cache stale | Cached block is older than expected for its source, or stale flag is set | `Cached data may be stale.` | Existing values if source/date/fetched_at remain visible | Claiming stale data is current, or mixing cache error with provider unavailable | Cache age, source block, and fetched time in diagnostics | Cache-state UI test and observability contract test |

## Copy Rules

- Use source-aware labels: `SSI DailyOhlc`, `SSI DailyStockPrice`, `SSI IntradayOhlc`, `SSI realtime`, `SSI trade tape`.
- Prefer section-level unavailable copy over per-field placeholders.
- Keep primary copy short. Put technical details in diagnostics.
- Do not use raw provider error text in primary cards.

## Implementation Notes For Phase 1-3

- Phase 1 adds the Data Quality Summary that surfaces mismatch, finality, adjusted-price, stale intraday, unavailable live data, and profile partial states.
- Phase 2 cleans public contract shapes and moves provider/debug details to diagnostics.
- Phase 3 applies these states to the company detail layout so the page reads like a data-quality report rather than a debug board.
