# VN Dashboard UI States

## Purpose

This file defines user-facing states for the VN dashboard and company detail page. It is the UI companion to `docs/VN_DATA_CONTRACT.md` and `docs/VN_COMPANY_DETAIL_DESIGN.md`.

Rules that apply to every state:

- Daily SSI data remains visible when required SSI DailyOhlc fields are valid.
- Optional live sections render only when real data exists.
- Missing object data renders as `null`.
- Missing list data renders as `[]`.

## R6E historical anomaly repair and Industry current states

When every retained VN30 constituent reports all four foreign-flow fields as
explicit zero for one completed session, that aggregate is not presented as a
normal zero-flow session. The backend performs one cooldown-bound exact-date
SSI verification. Until real provider-backed values are recovered, the date
remains visible as an unresolved data anomaly with empty numeric cells and is
excluded from charts, complete windows, rankings, analytics, and numeric CSV
cells. A successful repair restores the provider values and normal completed
status; a failed repair remains inspectable and does not poll on every refresh.

Industry current detail accepts usable `ready`, `partial`, `stale`, and
`market_closed` aggregates. It uses the canonical current aggregate for the
detail row and current groups for rankings. A complete accepted same-date row
suppresses the provisional row. An incomplete or anomalous same-date shell is
replaced by the provisional row so exactly one session date remains visible.

## R6D missing, Proprietary, and Industry states

An accepted completed foreign-flow date may still be incomplete. Missing gross
fields render `—` and the row status is `Thiếu dữ liệu`; an explicitly supplied
provider zero renders `0` and may be `Đủ` when all required gross fields are
present. Incomplete rows stay visible in detail tables but do not create zero
chart points or enter complete-only calculations and rankings. CSV leaves
missing cells empty.

The Proprietary mode means securities-company own-account trading. Because the
current SSI integration has no proven proprietary buy/sell fields, the mode
shows a concise unsupported state, no Clean/zero summary, no chart, no detail
rows, and disabled export/refresh actions. It does not reinterpret
`indexSummary`, room capacity, foreign flow, price, or turnover.

Industry rankings continue to use current-VN30 Industry groups. The current
Industry detail row uses the canonical aggregate returned with those groups:
`Đang diễn ra` when ready, `Mất kết nối` when stale, and `Tạm tính` after close.
It never becomes `Đủ`; accepted same-date history replaces it, and an
unavailable canonical aggregate creates no placeholder row.

## R6C idle authentication recovery

Backgrounding the page does not clear completed or current foreign-flow rows.
One hidden-to-visible transition schedules one bounded refresh while the
existing values remain visible. A retryable failure marks retained current data
as disconnected; completed DailyStockPrice rows remain usable. Force Refresh
uses the same guarded recovery owner, ignores repeated clicks while in flight,
and never creates a browser-side provider connection.

`Overview unavailable` is reserved for the cold state where neither accepted
completed history nor a retained current snapshot is usable. Membership age,
refresh failure, cache bypass, and recovery state stay in Data Details rather
than primary cards. Null current fields remain em dashes and are not rendered
as zero.

## R6B current finality and Industry diagnostics

Finality takes precedence over completeness. Only accepted DailyStockPrice rows
display `Đủ`. A current provisional row displays `Đang diễn ra` when connected,
`Mất kết nối` when stale or disconnected, `Tạm tính` after market close,
`Chờ dữ liệu` while waiting, and `Không khả dụng` without a usable snapshot.
Complete numeric fields and 30/30 coverage do not change that status.

Data Details labels latest completed, latest display, and current provider
sessions separately. Current Industry capability is shown as `ready`, `partial`,
`stale`, `waiting`, or `unavailable`, with the bounded current-VN30 universe and
coverage. Completed Industry content remains visible if current data is waiting
or unavailable. R6D supersedes the earlier Proprietary zero presentation with
an explicit unsupported capability state.

## R6A restart and system-browser acceptance

Reloading the frontend or restarting the backend must not remove a newer
accepted completed session merely because the next DailyStockPrice response is
older, empty, or unavailable. A newer provisional current row remains visually
first and concise; accepted same-date data suppresses it. Coverage remains
readable, missing current values remain em dashes rather than zero, and explicit
provider zero remains `0`.

The system-Chrome gate accepted 18 deterministic states at 1366x768 and
390x844, including current/completed ordering, post-close provisional display,
full/partial/missing coverage, explicit zero, unavailable current with completed
history retained, regressive refresh, same-date precedence, 20-plus-current
history, chart/ranking/watchlist reach, and CSV finality/coverage. It found no
page-level horizontal overflow; intentional table scrollers remained local.

## Symbol foreign-flow inspection

- **Closed:** ticker selection only highlights the workspace; zero history requests and no hidden loading state.
- **Loading:** after `Mở phân tích chi tiết`, show the ticker-specific loading copy without numeric placeholders.
- **Updating:** retain the same-ticker successful result while an explicit retry/force refresh runs.
- **Ready/partial/stale:** show usable rows, exact coverage, incomplete-window labels, source/finality, and stale disclosure. Null remains unavailable.
- **Empty:** distinguish a valid empty result from failure and do not render fake summaries or chart points.
- **Unavailable:** show a retry action and no numeric analytics.

Panel URL state uses `ticker`, `inspect`, `symbolMetric`, `symbolWindow`, `symbolRange`, and `symbolChart`. Metric, window, 20/40/60 range, chart mode, and table sorting are local presentation controls and make zero additional requests. Signed positive/negative/zero/null states use green/red/neutral/unavailable styling plus numeric/text labels; color is not the only cue.

Foreign-flow numeric text is locale-independent: decimal points use `.`, grouped integers use `,`, VND values of at least one billion use exactly two decimals plus `Tỷ` without a space, lower VND values and all share volumes remain complete grouped integers, percentages use exactly two decimals, zero renders as `0`, and unavailable/non-finite values render as `—`. Formatting never changes the raw values used for calculations, sorting, filtering, or requests.
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
| `disabled` | A future or optional module is intentionally off. | Default VN news state; future external modules before provider selection. |
| `failed` | Required section cannot load and the user cannot inspect its data. | Daily scan fails with no previous rows or company daily data cannot load. |
| `empty-start` | No watchlist has been committed yet, so no provider data should be requested for hardcoded symbols. | Fresh `/vietnam` browser session with no saved custom list; prompt user to choose a preset or enter tickers. |

Clarification:

- `success` is internal request-state vocabulary for frontend orchestration.
- `ready` is the preferred user-facing section state label.
- Do not introduce `success` as visible UI copy unless an existing screen already uses it that way.

Chart control and RSI rules:

- Present `Timeframe` (`1D`, `1m`) separately from the D1-only `Range` (`1M`, `3M`, `6M`, `1Y`) group.
- In 1m, hide the daily range group and show Today plus available completed dates from loaded D1 history.
- RSI uses its own pane, canonical 0–100 numeric scale, and 30/70 guides. It must not inherit the board-price formatter.
- The RSI pane owns its pane-scoped visible right scale; chart-wide price formatting must not override its numeric formatter. One-minute axis ticks use Vietnam `HH:mm`, and the native crosshair label and HTML tooltip use the same `Asia/Ho_Chi_Minh` instant. Daily ticks remain library-formatted `BusinessDay` dates.

## Severity Model

Daily SSI data availability is more important than optional live or future-module availability:

- Daily data unavailable is serious because it blocks the core scan.
- Realtime unavailable is optional/minor when DailyOhlc is valid.
- Trade tape unavailable is optional/minor when DailyOhlc is valid.
- News disabled is expected by default. If the production Vnstock selector is explicitly chosen before written terms are approved, show `News unavailable` with its concise `blocked_pending_terms` message; do not show fake articles or a provider-error stack.
- If local personal Vnstock News mode is explicitly enabled, show returned rows with `Vnstock News` and `Personal research` labels. Package-missing/fetch failures should show concise unavailable messages and must not affect SSI daily rows.
- Optional live/future states should not erase valid daily scan data.
- Realtime polling or visibility changes must not clear valid watchlist rows, selected ticker detail, or chart state.
- A `partial` dashboard or ticker state can mean optional sections are unavailable; it must not imply daily SSI data failed when required DailyOhlc fields are valid.

Provider endpoint details, HTTP status, retryability, and raw provider summaries belong in diagnostics, not primary UI.

## State Matrix

| State | API condition | Primary UI copy | Metric rows allowed | Must not show | Diagnostics behavior | Tests to add/update later |
| --- | --- | --- | --- | --- | --- | --- |
| Daily OK + realtime unavailable | Required daily row is usable; `realtime_status.status = unavailable` or `disabled`; `realtime_snapshot = null`; optional `reason_code` may be `running_idle`, `cache_empty`, `ticker_not_bootstrapped`, `config_disabled`, etc. | Short copy such as `SSI realtime unavailable. Daily SSI data is still available.`, `SSI realtime cache miss.`, or `SSI realtime stale.` | Daily close, daily OHLCV, DailyStockPrice fields that exist | Snapshot price, realtime change, session volume, or placeholder `-` rows from `realtime_snapshot` | Endpoint/http/raw provider details under `diagnostics.realtime`; safe manager/cache reason may be visible | Watchlist/company UI tests assert unavailable copy and no realtime metric rows |
| Daily OK + intraday stale/no rows | Daily row is usable; `intraday_status.status = unavailable`; `intraday_candles = []`; `intraday_pulse = null`; `reason_code` distinguishes date mismatch, no rows, rate limit, or provider error | Reason-aware short copy such as `SSI IntradayOhlc latest candle date does not match the latest daily trading date.` or `SSI IntradayOhlc returned no usable candles.` | Daily and DailyStockPrice fields only; a neutral provider-cadence note if available | Intraday pulse cards, stale intraday close/change/volume metric rows, or requested timeframe as actual interval | Put latest intraday date, daily date, date match, cadence status, and failure class under intraday status/diagnostics | Contract test for stale intraday returns `pulse = null`; UI test hides pulse metrics and avoids `1H intraday` wording |
| Daily OK + intraday cadence mismatch | Daily row is usable; `intraday_status.status = ok`; `intraday_status.reason_code = cadence_mismatch`; real candles exist but returned cadence differs from request | `SSI intraday cadence differs from the requested timeframe.` | Real intraday rows and pulse metrics with provider-returned cadence labels | Copy implying requested timeframe is actual cadence | Requested timeframe and detected actual granularity remain visible | Backend/UI tests classify data-quality check as partial without changing DailyOhlc price |
| Daily OK + trade tape empty | Daily row is usable; `trade_tape_status.status = unavailable` or `disabled`; watchlist/company `trade_tape = []`; `reason_code` can be `stream_not_started`, `stream_not_bootstrapped`, `stream_cache_empty`, `xtrade_not_subscribed`, or `xtrade_disabled` | `Loading SSI trade tape...` for short-lived startup/cache-empty states; otherwise `SSI trade tape unavailable.` or another short safe unavailable reason | Daily and DailyStockPrice fields only | Trade rows, wrapper-object fields, placeholder trade metrics, historical tape inferred from daily/realtime data, or dynamic subscriptions | Streaming manager/buffer details under `diagnostics.trade_tape` | Contract test asserts public watchlist/company `trade_tape` is a list; backend tests assert request handlers only read the X-TRADE buffer |
| Daily OK + trade tape rows | Daily row is usable; `trade_tape_status.status = ok`; watchlist/company `trade_tape` has buffered X-TRADE event rows. Diagnostics may still report `cache_stale`. | Show SSI-style matched-order columns `Time`, `B/S`, `Vol`, `Price`, `+/-`, and `+/-(%)`; do not show `Loading`, `Stale`, or lunch-break empty copy when rows exist | Real buffered X-TRADE rows with price, volume, timestamp, optional explicit B/S side, and source. Trade prices use SSI board colors; ceiling maps to `text-ceiling-purple`; volume remains neutral; change columns are trade price versus SSI reference. | Official daily close substitution, historical time-and-sales claims, rows inferred from DailyOhlc/DailyStockPrice/realtime snapshots, or Buy/Sell inferred from price color | Buffer row count, returned row count, latest timestamp, age, channel type, and stale/cache status under `diagnostics.trade_tape` | Backend tests assert X-QUOTE/X snapshot rows do not create trade tape and stale buffered rows stay visible |
| Daily OK + order book unavailable | Daily row is usable; `order_book_status.status = unavailable` or `disabled`; `order_book = null`; `reason_code` can be `stream_not_started`, `stream_not_bootstrapped`, `stream_cache_empty`, `xquote_not_subscribed`, or `xquote_disabled` | `SSI order book unavailable.` or a short status-specific copy | Daily, DailyStockPrice, realtime snapshot, trade tape, and session/status fields that exist independently | Fake bid/ask rows, placeholder levels, latest price from bid/ask, trade rows inferred from quote levels, or dynamic subscriptions | Streaming manager/cache details under `diagnostics.order_book` | Backend tests assert optional unavailable state does not affect DailyOhlc latest price |
| Daily OK + order book rows | Daily row is usable; `order_book_status.status = ok` or stale-but-row-present; watchlist/company `order_book` has a cached SSI X-QUOTE row with at least one valid bid or ask level | Show `Order Book — SSI X-QUOTE` with dynamic `Bid Vol`, `Bid Price`, `Ask Price`, and `Ask Vol` rows; show a stale badge/copy if status or row freshness says stale | Real X-QUOTE levels with positive price and nonnegative volume, source, and freshness. Prices use board-style thousand-VND formatting and SSI board colors when SSI reference/ceiling/floor are available; volumes show full shares with thousands separators. | Fake levels, fixed-depth claims, best-price claims if no valid level exists, market-specific level-count claims, replacing realtime/trade-tape/session contexts, or using bid/ask as `latest_price` | Bid/ask level counts, channel type, row counter, latest timestamp, age, and stale/cache status under `diagnostics.order_book` | Frontend tests assert dynamic levels, source label, board colors, stale/unavailable states, no fake rows, no F/R/MI UI, and unchanged daily latest price |
| Daily OK + foreign room unavailable | Daily row is usable; `foreign_room_status.status = unavailable` or `disabled`; `foreign_room = null`; `reason_code` can be `stream_not_started`, `stream_not_bootstrapped`, `stream_cache_empty`, `stream_cache_stale`, `r_not_subscribed`, or `r_disabled` | `SSI foreign room unavailable.` or a short status-specific copy | Daily, DailyStockPrice, realtime snapshot, trade tape, order book, and session/status fields that exist independently | Fake room values, inferred room ratios, DailyStockPrice daily foreign-flow substitution, latest price changes, or dynamic subscriptions | Streaming manager/cache details under `diagnostics.foreign_room` | Backend tests assert optional unavailable state does not affect DailyOhlc latest price |
| Daily OK + foreign room row | Daily row is usable; `foreign_room_status.status = ok`; watchlist `foreign_room` has a cached SSI R row with at least one valid room/foreign metric | Future UI may show foreign-room context after live payload evidence proves units/value semantics | Real R fields such as total/current room and foreign buy/sell volume/value, source, freshness, and `value_semantics_status` | Fake values, values inferred from DailyStockPrice/realtime/order book/trade tape, or replacing DailyStockPrice daily foreign flow | Channel type, row counter, latest timestamp, age, value-semantics caveat, and stale/cache status under `diagnostics.foreign_room` | Backend tests assert R rows use a dedicated cache and do not create realtime snapshot, order-book, trade-tape, or session/status rows |
| Daily OK + session/status unavailable | Daily row is usable; `session_status_status.status = unavailable` or `disabled`; `session_status = null`; `reason_code` can be `stream_not_started`, `stream_not_bootstrapped`, `stream_cache_empty`, `stream_cache_stale`, `f_not_subscribed`, or `f_disabled` | `SSI trading session/status unavailable.` or a short status-specific copy | Daily and DailyStockPrice fields only | Fake session labels, final-close claims, halt/suspend/closed labels, or placeholder session metrics | Streaming manager/cache details under `diagnostics.session_status` | Backend tests assert optional unavailable state does not affect DailyOhlc latest price |
| Daily OK + raw session/status row | Daily row is usable; `session_status_status.status = ok`; `session_status` has a cached SSI `F` row | Future UI may show raw provider session/status context with source and freshness if productized | Raw `trading_session`, raw `trading_status`, trading date/time, exchange, source, and freshness | Mapped business meanings such as open/closed/halted/final unless proven separately; price, trade-tape, or realtime substitutions | Cache age, channel type, row counter, and channel list under `diagnostics.session_status` | Backend tests assert `F` rows use a dedicated cache and do not create realtime quote/trade-tape rows |
| Market index pulse unavailable | `market_index_pulse_status.status = unavailable` or `disabled`; `market_index_pulse = []`; `reason_code` can be `stream_not_started`, `stream_not_bootstrapped`, `stream_cache_empty`, `stream_cache_stale`, `mi_not_subscribed`, or `mi_disabled` | Future UI may show `SSI market-index pulse unavailable.` after live proof and productization | REST DailyIndex rows and stock daily rows remain independent | Fake index values, inferred breadth from watchlist rows, replacing REST DailyIndex, or dynamic subscriptions | Streaming manager/cache details under `diagnostics.market_index_pulse` | Backend tests assert MI uses a dedicated cache and endpoint |
| Market index pulse rows | `market_index_pulse_status.status = ok` or `partial`; `market_index_pulse` has cached SSI MI rows | Future UI may show market pulse after live payload evidence proves channel/field semantics | Real MI index rows with value/change/activity/breadth fields, source, freshness, and `needs_live_proof` caveats | Fake values, trading recommendation labels, stock row price substitution, or replacing DailyIndex | Channel type, row counter, latest timestamp, age, requested index codes, and stale/cache status under `diagnostics.market_index_pulse` | Backend tests assert MI rows do not create realtime snapshot, trade-tape, order-book, foreign-room, or session/status rows |
| News disabled | `news = []`; `news_status.status = disabled` | `News disabled.` | None from news | News cards, fake news items, stale news placeholders | Optional reason can appear in collapsed source coverage | UI test asserts disabled copy and no news item cards |
| Vnstock personal research news | `news_status.provider = vnstock_news_personal`; rows preserve URL/provenance; `rights_status = personal_research_only` | `Personal research` badge with title/summary/source link | Article title, summary, source/category/time if present | Full article content by default, production/provider-licensed claims, fake ticker relevance | Ticker relevance is weak exact symbol match only | UI test asserts badge and no full content |
| Vnstock Community company news | `news_status.provider = vnstock_community`; selected/company ticker only; max three rows; `rights_status = personal_research_only` | `Vnstock Community` and `Personal research`; `No company news was returned for this ticker.` when empty | Title, published time, and only a verified absolute link | Summary/source/category/author/image, full content, guessed links, watchlist-wide news calls | Relative `raw_url` is not clickable; valid absolute links open separately with `noopener noreferrer`; `head` remains unshown until semantics are verified | UI tests assert three-row cap and relative/unsafe titles without links |
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

- Use source-aware labels: `SSI DailyOhlc`, `SSI DailyStockPrice`, `SSI IntradayOhlc`, `SSI realtime`, `SSI trade tape`, `SSI X-QUOTE order book`, `SSI R foreign room`, `SSI F trading session/status stream`, and `SSI MI market-index stream`.
- Prefer section-level unavailable copy over per-field placeholders.
- Keep primary copy short. Put technical details in diagnostics.
- Do not use raw provider error text in primary cards.
- Keep compact numeric display source-neutral and truthful: raw VND/share price fields render as board-style thousand-VND values with two decimals and no suffix, share volumes use `K`/`M`, VND trading values use `K`/`M`/`B`/`T`, and unavailable values remain explicit missing states rather than fake zeros.
- Price direction color follows the SSI stock-board convention and is UI-only: reference/equal is dedicated yellow (`text-reference-yellow`), ceiling is purple/magenta, floor is blue/cyan, above reference is green, below reference is red, and missing or non-positive inputs stay neutral gray. Dynamic daily/latest price coloring uses SSI DailyOhlc close against SSI DailyStockPrice reference/ceiling/floor with priority `ceiling > floor > reference > above reference > below reference > neutral`. Realtime price must not drive daily price coloring.
- Trade-tape rendering is rows-first. If `trade_tape` rows exist, dashboard/company UI renders the table even when status or diagnostics mention stale cache, buffered rows, or old startup state. If rows are empty and diagnostics indicate startup/not-started/subscribed-empty/cache-empty, the UI may refetch the selected ticker trade tape every few seconds for a bounded warm-up window, then stop after rows arrive, ticker change, terminal disabled/unsupported state, timeout, or unmount.
- Trade-tape B/S color is independent from price color: explicit `buy` displays green `Buy`, explicit `sell` displays red `Sell`, and unknown side displays muted `—`. Observed SSI `X-TRADE` raw side codes `BU` and `SD` map to Buy/Sell, but do not infer side from green/red/yellow/purple/cyan price color or from positive/negative change.
- Trade-tape `+/-` and `+/-(%)` use sign color only: positive green, negative red, and zero/equal-to-reference dedicated yellow. This does not affect raw API values or B/S side.
- X-QUOTE order-book rendering is selected-ticker only on the dashboard and company page. It uses existing watchlist/company refresh responses, not dynamic subscriptions, all-market subscriptions, or a new endpoint. Rows are matched by `level`; missing bid or ask sides render muted `—` cells with accessible missing-state labels. Stale last-known ladders remain visible with stale badge/copy and age metadata. The selected ticker live context may refresh every few seconds while the tab is visible so short-TTL cache updates can surface without waiting for full dashboard refresh.
- Phase 4.8R keeps selected live context refresh paused while the tab is hidden and triggers an immediate selected-ticker refresh when visibility returns. This applies to dashboard and company live context only; it does not refresh daily rows as realtime prices and does not start streams or subscriptions from the browser.
- Streaming lifecycle diagnostics may show `Stream stale — reconnecting...`, `Last update: <time>`, or `Showing last known rows` when available. Outside active Vietnam trading/auction windows, stale last-known X, X-QUOTE, or X-TRADE rows should use `Market closed — showing last known data.` instead of generic unavailable/failure copy. Stale X-QUOTE ladders remain visibly stale rather than fresh, and optional stream failure copy must not imply SSI DailyOhlc failed.
- Phase 4.8S restored streaming rows use a compact `Last known` state, never `Live` or `Ready`. During active hours the copy is `Waiting for live SSI updates — showing last known data.`; after close it is `Market closed — showing last known data.` The same stale/provenance rule applies independently to realtime, order book, bounded trade tape, foreign room, MI, and F contexts without adding requests or changing daily cards.

## Implementation Notes For Progressive Workspace Phases

- Phase 1 adds the Data Quality Summary that surfaces mismatch, finality, adjusted-price, stale intraday, unavailable live data, and profile partial states.
- Phase 2 cleans public contract shapes and moves provider/debug details to diagnostics.
- Phase 4.7B frontend rendering consumes normalized `null`/`[]` live-section shapes and keeps sectioned live diagnostics in collapsed diagnostics panels on dashboard and company detail views.
- Phase 3.2A adds a visual Data Readiness strip on `/vietnam` using user-facing labels such as `Ready`, `Partial`, `Unavailable`, and `Disabled`. It derives from existing loaded frontend data and status objects; it does not introduce API contract fields or request-state behavior.
- Phase 3.2B adds lightweight tooltip/accessibility explanations for Data Readiness strip items. The explanations are frontend-only, source/status-oriented, and keep endpoint details, HTTP status, retryability, and raw provider summaries out of primary UI.
- Phase 3.2C keeps previous successful `/vietnam` watchlist rows visible during refresh or pending list changes. First load still uses the normal loading state; refresh uses `Updating...`; request-level failure uses `Last update failed` while preserving previous rows/list/preset/selection. Per-ticker unavailable rows remain row-level states and do not block committing a successful response.
- Phase 3.2D applies section-level states across existing `/vietnam` sections. The indicator table shows a serious `Daily data unavailable` state only when no daily rows are loaded; selected ticker and stock-detail sections show concise unavailable states when no valid row exists; chart/intraday/realtime/trade-tape sections show compact `Ready`, `Loading`, `Unavailable`, `Disabled`, or `Failed` badges as appropriate. Optional live or future unavailable states remain visually minor when valid daily SSI rows exist, diagnostics remain lower priority, and Phase 3.2C previous-data refresh behavior is preserved.
- Phase 3.3A applies progressive disclosure to the selected ticker so the compact header remains a daily explanation surface while Price context, Flow context, Technical context, Live context, Source coverage, News context, and Diagnostics carry secondary detail. Price context may be open by default; optional live, source, news, and diagnostics groups remain lower priority. Raw fields, cache internals, endpoint/provider diagnostics, and rule inputs stay out of primary cards.
- Phase 3.3B keeps the same selected ticker disclosure structure but shortens labels, reduces repeated source wording, and keeps optional unavailable copy calm. Source coverage remains available at section level, News context uses `News available`, `News disabled`, or `News not implemented`, and raw provider/cache/rule details remain Diagnostics-only.
- Phase 3.5A adds client-side indicator-table filters. The filtered empty state uses `No rows match current filters.` and must remain distinct from serious daily-data failure. Filter result counts are client-derived. Resetting filters changes only ticker search and filter selects, not the active preset, active watchlist, custom watchlist input, committed rows, or selected ticker. If filters hide the selected ticker row while its data still exists, keep the selected ticker summary visible and show `Selected ticker is hidden by filters.` Optional live unavailable filters remain neutral and do not make daily data unavailable.
- Phase 4.6B hardens watchlist preset interaction. The VN30 preset uses real SSI IndexComponents component rows when those rows are available; it must not emit a hardcoded VN30 membership list as data output. While a non-VN30 preset/custom/clear request is pending, the exact pending action is disabled, the pending filter shows a small loading state, repeated clicks on that same action are ignored, and previous successful rows remain visible. Phase 4.6E/4.6F-3C allow switching to another preset without allowing stale responses to overwrite the newer selection.
- Phase 4.6B also adds compact watchlist-table reason disclosure. Missing numeric cells render as `—` with a title/ARIA reason such as insufficient DailyOhlc history, missing DailyStockPrice, or unavailable foreign-flow values. `Partial`, `Unavailable`, and realtime badges expose short reason titles, including `Realtime disabled`, `Not bootstrapped`, `Realtime cache miss`, and `Realtime stale` when the backend provides those states.
- Phase 4.9A adds compact Support and Resistance columns to the daily indicator table. Headers show `D1 · 60 sessions` with description-only tooltips. Rows show at most two `S1`/`S2` or `R1`/`R2` price ranges; unavailable DailyOhlc-derived zones render `—`, never a synthetic price, source label, ATR value, strength score, or recommendation.
- Phase 4.9B-1 keeps the selected ticker's daily inspect-chart S/R overlay optional and default-off. When enabled, at most S1/S2/R1/R2 reuse Phase 4.9A values as faint clipped bands and midpoint lines on the existing candle scale. S1/R1 use right-edge range labels; S2/R2 use secondary rank markers with full ranges in their titles. The toggle makes no request, and unavailable zones leave the chart functional without bands.
- Phase 4.10L uses Lightweight Charts 5.2 as the sole VN daily-chart renderer. Loading and unavailable overlays remain explicit, daily bars use SSI DailyOhlc `BusinessDay` dates, volume and RSI use native panes, and MA20/MA50/Bollinger use native line series. S/R remains default-off; when enabled, its passive primitive uses the existing backend `shortTermZones` ranges and native right-price-axis views. Native zoom, pan, crosshair, indicator toggles, S/R toggling, and expand/collapse do not fetch market data. The former SVG renderer and migration flag are no longer runtime states.
- Phase 4.11A keeps one active chart in compact or expanded mode, uses stable 68/14/18 compact and 70/12/18 expanded pane proportions, and keeps the native right scale at a 148 px minimum whether S/R is off or on. Ticker and range-preset changes show an owned loading state with no old chart and deliberately fit the new series; expand/collapse restores the current logical range without a request. Tooltip output remains inside the chart, is visually suppressed during loading/unavailable or ticker mismatch, and repeated same-bar movement updates position without rerendering the dashboard.
- Phase 4.11D-2 extends the restricted `1m` control alongside default `1D`. Its selector defaults to Today and lists completed dates from loaded D1 history. Initial ticker/date changes clear unrelated bars; scheduled current-session refreshes retain matching usable bars and show a restrained `Refreshing` note. Matching ticker + interval + date + request ID remains mandatory, so stale responses cannot win. Missing minutes remain chart gaps, intraday timestamps display in Vietnam time, active indicators use active bars, and daily backend S/R reads `Daily S/R`. 5m/15m/30m/1h, stream-built bars, aggregation, and fallback remain unavailable.
- Current-day labels are `Pre-open`, `Updating`, `Delayed`, `Lunch break`, `Stale`, `Closed`, or `No data yet`; prior dates show `Completed`. Never use `Live` or `Reconnecting` for this polling-only chart. Polling uses one minute-aligned timer only in morning/afternoon/ATC, one lunch wake-up, and one post-close reconciliation. D1, completed dates, hidden tabs, pre-open, and closed periods have no recurring market-data poll. Last provider update and newest raw-bar age are shown when present.
- Phase 4.6C makes VN30 component availability retryable. `unknown` leaves VN30 enabled, `loading` temporarily disables only the VN30 action, `ok` applies normalized unique SSI component symbols, and `unavailable`/`error` shows a retry affordance while preserving current rows. If another filter is selected during a component request, the older VN30 result cannot overwrite that newer intent.
- Phase 4.6C replaces the comma-separated custom input with a search and multi-select picker. Options come only from loaded SSI VN30 components, current response rows, and saved custom symbols. Selected symbols render as removable chips. A syntactically valid exact symbol not in loaded options must be explicitly selected as `Validate on apply`; the existing watchlist response must then return the requested row or the previous snapshot remains visible. Apply is bounded to 30 normalized unique symbols, the exact pending custom action is disabled, and duplicate apply clicks are ignored.
- Phase 4.6D presents VN30 loading as two distinct stages. The component stage uses `Loading VN30 members...`; after usable symbols resolve, that spinner stops and the filter status uses `Loading N VN30 rows`. Previous rows remain visible throughout. After 3 seconds the row state becomes `Still loading`; after 8 seconds it becomes `Taking longer than expected` and explains that the filter can be selected again if the request fails. No automatic timeout or duplicate request is started.
- Phase 4.6E renders SSI-derived VN30 membership as ordered shell rows as soon as the member list resolves, then hydrates ordinary watchlist data through sequential bounded requests with `force_refresh=false`. Phase 4.6F names the strategy: default 5, minimum 3, maximum 10 tickers per batch. Shell numeric cells use `Loading...` or `—` and never synthetic values. Progress reports `Loaded X/N`, the pending batch, and resolved batch size; 3-second and 8-second messages retain the current loaded count. A failed batch leaves earlier rows intact, marks its ticker shells `Unavailable` with the request reason, and exposes `Retry failed rows` without refetching successful rows.
- During Phase 4.6E hydration, another preset or clear action may supersede VN30. Remaining older batch responses are ignored and cannot replace the newer filter. The active VN30 button is disabled while its batch run is pending, so repeated clicks do not create duplicate hydration. Phase 4.6F-3F makes member resolution terminal: a later SSI component retry that returns unavailable/no rows, fails, or times out clears `Loading VN30 members...`, shows Retry VN30/unavailable, and does not hydrate from a fallback or last-successful member list.
- Phase 4.6F-2 separates initial watchlist membership from hydration batch size. Fresh `/vietnam` sessions with empty localStorage show an empty-start prompt (`Choose a preset or enter tickers to start.`), keep `selectedTicker=null`, disable ordinary watchlist refresh, and do not call the watchlist endpoint with omitted `tickers`. Saved custom watchlists still restore and load automatically. Batch size controls only hydration chunking; it must not create, cap, replace, or imply the active watchlist membership.
- Phase 4.6F-3A keeps VN30 member state preset-local. Any VN30 member loading/unavailable state must not render active watchlist hydration progress or previous-row copy. `current rows stay visible` / `Showing previous data` copy appears only when committed watchlist rows already exist.
- Phase 4.6F-3B makes VN30 member loading lazy and user-driven. Fresh empty-start sessions do not call SSI IndexComponents and show the VN30 action as idle until the user selects it. While the user-driven component request is pending, only the VN30 action shows `Loading VN30 members...`; if it fails or times out, the state settles to retryable `Retry VN30` without starting watchlist hydration or creating hardcoded rows.
- Phase 4.6F-3C keeps empty-start preset and custom controls interactive. No preset is disabled merely because there are no committed rows. Only the exact pending preset/custom action is disabled for duplicate-click protection; another preset may supersede it, and older responses are ignored by the existing stale-response guard. Non-VN30 presets do not depend on VN30 member loading, failure, or unavailability.
- Phase 4.6F-3D keeps IndexList/DailyIndex coverage diagnostics separate from VN30 member state. Background index coverage loading, unavailability, or rate limits must not label VN30 as loading/unavailable, must not disable local presets, and must not block custom input. VN30 component failure remains a VN30 preset retry state and does not become the generic index coverage error.
- Phase 4.6F-3E treats non-VN30 presets as direct watchlist actions. Banks, Securities, Real estate, Consumer, Logistics, Tech, Oil & gas, and Electricity use only their static local ticker lists and do not depend on custom picker selections/options, current rows, active watchlist state, VN30 components, IndexList, or DailyIndex. VN30 component requests are request-id owned; unavailable/no-row/failure/timeout responses clear `Loading VN30 members...` and settle to Retry VN30 without starting hydration or creating fallback members.
- Phase 4.6F-3F defines VN30 member states as `not_loaded`, `loading`, `ready`, `unavailable`, `failed`, or `timeout`. Only the latest user-driven VN30 request may show `Loading VN30 members...`; every terminal non-ready state shows Retry VN30/unavailable, keeps local presets/custom usable, and starts no watchlist hydration.

## Phase 4.11E Current-Session 1m States

The selected-ticker chart keeps one market-data timeout, one request-free countdown timeout, and one visibility listener. `Next update in Ns` appears only for visible Today views with an active minute-poll target; it derives from the absolute `:07` target and never fetches. D1, fixed completed dates, pre-open, lunch, closed, initial loading, and views without a scheduled minute fetch show no countdown. Existing bars remain mounted during scheduled/manual refresh.

Primary status priority is `Completed`, `Loading`, `Pre-open`, `Lunch break`, `Closed`, `Stale`, `SSI data unavailable`, `No data yet`, `Delayed`, then `Updating`. Today metadata uses Vietnam time and distinguishes `Updated`, `Latest bar`, provider snapshot age, and newest provider bar age. Lunch retains morning bars without minute polling; 13:00:07 uses one authoritative refresh; ATC remains bounded; about 14:45:20 runs at most one automatic reconciliation per ticker/date. Hidden tabs clear owned timers/requests, visibility restoration performs at most one active-session refresh, and semantic Today moves at Vietnam midnight without carrying old bars or automatically calling SSI overnight. No state says `Live`.

## Phase 4.11F stream-backed panel states

- `ready`: use the existing current/updating presentation only after a fresh current-generation event.
- `recovering` or `awaiting_subscription`: show `Reconnecting — showing last known data when available.` and retain usable cached values.
- `stale`: show `Stale — showing last known data.` without claiming realtime freshness.
- `closed`: show `Market closed — showing last known data.` and retain bounded last-known values.
- `unavailable` or `failed` without usable data: keep the existing concise unavailable state; raw provider exception text is not shown.

These states apply only to existing X/X-QUOTE/X-TRADE/F/R/MI consumers. They do not change D1/1m chart loading, polling, labels, or data ownership, and they do not add a frontend WebSocket or higher polling frequency.

## SSI-V3-M2.6B current symbol flow states

- `waiting`: show that the bounded subscription is awaiting its first usable
  current-session room update; show no metric-shaped zeros.
- `ready`: show the provisional cumulative snapshot with the short
  `Đang diễn ra` status.
- `stale`: retain received values with stale wording and cache age when
  available.
- `market_closed`: retain a usable same-session snapshot with the short
  `Tạm tính` status; otherwise show a calm unavailable/no-message state without
  fabricating values.
- `unavailable`: show disabled/not-started/not-bootstrapped/not-subscribed
  context without affecting completed daily history.
- `error`: show a concise typed failure; do not expose raw provider text.

M2.6B-R3 gives Foreign Flow ticker mode and Company Research one unified
`Foreign flow` card. It compares the provider-backed current-flow
`tradingDate` with the latest accepted DailyStockPrice date: a newer current
date wins, while a newer or same-date completed row wins. If no safe current
date exists, the accepted DailyStockPrice session remains visible. The
separate `Current-session foreign flow` card is removed.

In Foreign Flow ticker mode, a provider-dated current session is also shown as
the first display-only row in `Chi tiết phiên` using the same page-owned
response. It is not inserted into the historical chart, rankings, analytics,
export, or rolling calculations.

The display-only current row uses `Đang diễn ra`, `Tạm tính`, `Chờ dữ liệu`,
`Mất kết nối`, or `Không khả dụng`. `Tạm tính` means a usable provider-dated
current snapshot is retained after market close. Missing values and both
rolling columns show `—`; an explicit provider zero remains `0`. If an accepted
DailyStockPrice row already exists for that trading date, the accepted row
wins and the provisional row is omitted. Completed-row status labels remain
unchanged.

The unified card shows buy, sell, and net value plus buy, sell, and net volume
only when provider fields are usable. Room-capacity fields remain outside the
trading-flow presentation. Provider event time and local receipt time are
separate. Both pages poll the HTTP cache every 15 seconds
with one in-flight request, abort cleanup, and stale-response rejection;
manual refresh performs one no-store cache read. React Strict Mode must still
produce one effective initial polling request.

M2.6B-R4 adds one hidden-to-visible current-flow refresh to Foreign Flow ticker
mode and Company Research. Hidden polling remains paused; returning visible
does not clear the current card or completed data, does not create a second
timer, and repeated visible events do not duplicate the resume request. While
recovery is pending or fails, a usable prior current snapshot shows
`Máº¥t káº¿t ná»‘i`; with no usable current snapshot, only the current capability
shows `KhÃ´ng kháº£ dá»¥ng`. Completed DailyStockPrice content remains visible and
the Overview does not become wholly unavailable because of stream health.

M2.6B-R5 keeps the latest usable provider-dated snapshot in the shared unified
card and the display-only detail row after market close. Market close changes
its short label to `Tạm tính`; it does not erase the snapshot. Accepted
DailyStockPrice for the same date replaces the provisional presentation and
prevents a duplicate date. No polling, chart, rolling, ranking, analytics,
export, aggregation, or persistence input changes.

R1 visually accepted all six states plus explicit zero, partial volume-only,
retained error data, room present/missing, and provider time present/absent at
1366x768 and 390x844 on both pages. No page or card horizontal overflow was
observed. The active live route remains blocked by SSI streaming authorization,
which renders as a typed unavailable/error state without changing completed
daily data.

R3 visually accepted eight Company Research and five Foreign Flow ticker
fixtures at both 1366x768 and 390x844. Each fixture rendered exactly one
`Foreign flow` card, no duplicate current-session heading, a visible provider
session date and concise state, no card clipping, and no page-level horizontal
overflow. The 20-row ticker fixture retained the existing table scroller and
21 display rows when the newer provisional row was eligible.

## Phase 4.12 Foreign Flow States

Phase 4.12D-1 implements the daily watchlist batch subset below. Current-session provisional states and market aggregates remain planned.

| State | Display behavior | Preserve | Never show |
| --- | --- | --- | --- |
| Loading | Keep the prior successful foreign-flow view and show a local updating state | Unrelated daily/watchlist data | Full-page blanking or zero placeholders |
| Current provisional | Show verified cumulative current fields with `Provisional` and update time | Latest historical final for comparison | `Final`, room-derived flow, or estimated value |
| Historical final | Show the official daily row and complete-window trends | Source/date/finality metadata | A provisional row silently promoted to final |
| Partial | Show valid fields or covered aggregate subset plus missing fields/components and coverage | Correct zeros and independent volume/value paths | Complete-market wording or extrapolation |
| Stale | Keep last-known values with age and reason | Last verified source/finality | Current/ready wording |
| Unavailable | Show concise reason and no metric-shaped placeholder | DailyOhlc price/chart and other independent sections | Null formatted as zero or fallback data |
| Market closed | Prefer latest historical final; optionally show stale last-known provisional data with after-hours label | Final history and explicit age | Missing current data classified as provider failure |

For the implemented watchlist batch, loading keeps the previous successful same-scope data visible; partial lists valid rows with coverage; stale rows show a stale marker; empty means the provider returned no accepted daily rows and does not display zero; unavailable shows a concise retry state. `NN ròng` and `NN 5P` use em dashes for null values, and Today/5/20 rankings are explicitly labeled `Trong watchlist`. A membership change cancels or ignores the older request so rankings from different scopes cannot mix.

The dedicated `/foreign-flow` workspace uses the same states and request owner. An empty saved watchlist shows a link back to `/vietnam` and makes no batch request. Initial loading uses local skeletons; updating or failed same-scope refresh keeps the previous usable view. `Phiên gần nhất` is the visible latest-window label while `window=today` remains URL-compatible. Summary, ranking, and scanner state follow the selected window: a latest-ready row with no selected 5/20 value is not labelled ready for that window. Null/non-finite values render `—` without coverage; an available incomplete value may show only valid `covered/requested phiên`. Explicit zero stays zero, units are visible, and sortable scanner headers expose the active direction through `aria-sort`. More than 30 locally stored unique symbols shows `30/N` and requests only the first 30; omitted symbols are not labelled provider failures. Technical `daily_available` remains contract/tooltip context rather than a primary chip, and daily rows remain valid outside market hours because the page adds no current-session or streaming claim.

Phase 4.12E-1-R2 keeps these states while adding visual summaries from the same response. Breadth counts selected-window buy, sell, explicit-zero, and unavailable symbols; stale and incomplete usable rows retain their sign plus textual state. Concentration and treemap omit zero/unavailable rows and show an explicit empty state when no eligible flow exists. Treemap cells remain keyboard focusable and use dashed borders plus text for stale/incomplete state, while sign color is never the only label. Buy/sell bars use one shared magnitude scale and preserve compact one-sided empty states. `view=overview|detailed` changes scanner density locally and does not alter loading, refresh, or request behavior.

Phase 4.12E-1-R2A browser acceptance verified the unavailable branch with five requested symbols. The summary retained em dashes, breadth exposed `0/5` usable and five unavailable symbols, concentration reported insufficient data, treemap and buy/sell bars displayed explicit no-eligible-data copy, and the scanner preserved five unavailable rows. Window, metric, view, filter, and sort remained local and produced no batch refetch. Desktop and mobile layouts remained readable with no console error or malformed numeric text. This is provider/network unavailability, not an empty result and not a reason to synthesize zeros.

Phase 4.12E-2 adds `scope=vn30`. The VN30 scope owns one aggregate request and disables the watchlist batch owner. Loading retains prior same-scope data; membership unavailable states say that SSI IndexComponents is unavailable and never substitute members. Ready, partial, stale, and unavailable aggregate states remain distinct. The page discloses that history uses current VN30 membership, and local window/metric/chart/view/sort/filter/ticker changes do not refetch. Net, buy/sell, cumulative-net, and breadth charts use 5/10/20 slices of the returned maximum-20-date series; null dates/values remain gaps rather than zero. Signed foreign-flow net values use green when positive, red when negative, neutral foreground styling at zero, and existing unavailable styling for null/non-finite values; visible signs and labels remain the non-color cue.

Foreign-room capacity remains semantically separate and is not mapped into the unified foreign-flow summary. Price reaction copy is descriptive (`Flow and price moved in the same direction`, `Foreign buying occurred while price declined`, or `Foreign selling occurred while price increased`) and does not present an instruction or forecast.

### Latest-session foreign-flow states

Foreign Flow Overview, Stocks, Industries, Watchlist, Data Details, charts, and displayed-series exports may include one newer provider-dated current row above accepted completed history. Active current data is `Đang diễn ra`; a retained post-close snapshot is `Tạm tính`; a usable snapshot during an active disconnect is `Mất kết nối`; expected data without a snapshot is `Chờ dữ liệu`; unavailable capability is `Không khả dụng`. Coverage is shown independently, for example `Đang diễn ra · 27/30`.

Current totals and windows are marked provisional when they include the current row. Missing symbols or fields render `—` and are not treated as zero; explicit provider zero renders `0`. Accepted DailyStockPrice for the same date suppresses the provisional duplicate and becomes `Đủ`. Completed content stays visible when the current stream is waiting or unavailable. Industry wording identifies the current VN30 membership universe, and watchlist requests remain limited to user-selected symbols.
