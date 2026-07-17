# Vietnam Dashboard Setup

This page is the current entry point for VN dashboard setup. The active runtime is strict SSI FastConnect mode.

## Current Runtime

- Daily OHLCV, daily chart candles, and canonical `latest_price` come from SSI `DailyOhlc` close when DailyOhlc rows exist.
- SSI `DailyStockPrice` is enrichment only: reference prices, ceiling/floor, adjusted close when present, matched/put-through fields, and foreign-flow fields. It must not overwrite `latest_price`.
- The optional compact intraday pulse is sourced only from SSI `IntradayOhlc` when usable. Separately, the selected-ticker chart offers `1m` for Today or an available completed date through `/api/v1/stocks/vn/intraday-chart`; it uses sparse SSI resolution-1 bars, strict Vietnam timestamps, a dedicated bounded cache, and no realtime substitution. Today is delayed polling, never a live/tick chart. 5m/15m/30m/1h, aggregation, page 2, and fallback remain unavailable.
- Realtime snapshots come from the optional SSI `X:{symbol}` live contract and stay separate from daily prices.
- Optional local streaming snapshots can retain already-normalized last-known X/X-QUOTE/X-TRADE/R/MI/F rows across a backend restart. They are bounded, stale, explicitly labeled, and never replace SSI DailyOhlc daily price data.
- Trade tape comes from the optional SSI `X-TRADE:{symbol}` latest-event stream context and stays separate from daily prices.
- Foreign room comes from the optional SSI `R:{symbol}` live context when a usable streaming cache row exists and stays separate from DailyStockPrice daily foreign flow.
- Market-index pulse comes from the optional SSI `MI:{index_code}` live context when usable streaming cache rows exist and stays separate from REST DailyIndex and stock rows.
- VN30/index components are SSI-backed where available.
- News, fundamentals, financial statements, ratios, macro data, research reports, and corporate actions/dividends/rights/splits are disabled / `not_implemented` until a separate qualified provider is added for those gaps. `VN_NEWS_PROVIDER=vnstock_news` reports an explicit unavailable terms gate only. `VN_NEWS_PROVIDER=vnstock_news_personal` is local/personal research only, requires an explicit enable flag, and must not be used for hosted/public/commercial deployment. `VN_NEWS_PROVIDER=vnstock_community` is a separate local/personal selected-company headline mode, capped at three cached rows and never used for SSI market data. Its original article path remains provenance-only unless a validated absolute HTTP(S) URL is available; the UI never guesses a hostname.
- Missing object data is represented as `null`; missing list data is represented as `[]`.

Mozyfin owns no normal VN dashboard runtime path. KBS is legacy-only, disabled by default, and should appear only in explicitly labeled legacy diagnostics or historical notes.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
cd apps/dsa-web
npm install
```

2. Configure SSI FastConnect credentials through environment variables or the existing local secret-management path. Do not print or commit secret values.

3. Enable Vietnam market routing:

```bash
MARKET=VN
STOCK_LIST=FPT,VPB,MSB,SCS,ACV,ACB
```

`STOCK_LIST` remains general runtime/watchlist configuration for the broader app. The `/vietnam` frontend no longer auto-loads this or any hardcoded ticker group on a fresh browser session; it starts from a saved custom list when present, otherwise from an empty prompt where the user chooses a preset or enters tickers.

4. Run the backend and web UI:

```bash
python main.py --webui-only
```

Open `http://127.0.0.1:8000/vietnam`.

For the current operational runbook, use `docs/RUNBOOK_VN.md`. For SSI-specific source, status, and caveat details, use `docs/SSI_FASTCONNECT_INTEGRATION.md`.

## Current UI Labels

The active dashboard uses source-specific labels:

- `Daily OHLCV volume` for SSI `DailyOhlc` daily volume.
- `Foreign net volume` with `SSI DailyStockPrice · shares` for share-volume foreign flow.
- `Matched volume` for SSI `DailyStockPrice` matched quantity.
- `Realtime snapshot` / `SSI realtime` for realtime board snapshot data.
- `Trade tape` for the selected ticker trade-tape rows.
- `Order book` / `SSI X-QUOTE order book` for optional bid/ask ladder context when backend/API data exists.
- `Foreign room` / `SSI R foreign room` for optional foreign-room context when backend/API data exists.
- `Market index pulse` / `SSI MI market-index stream` for optional realtime index context when backend/API data exists.

The dashboard must not present SSI realtime, trade-tape, order-book, or foreign-room features as KBS, and must not mix DailyOhlc and DailyStockPrice labels into a single source.

Board-style price formatting and SSI price-color convention are implemented: price-like VND/share values display in thousand-VND units with two decimals, reference/equal prices use yellow, ceiling uses purple, floor uses blue/cyan, above-reference uses green, and below-reference uses red.

## Current Stock Detail Data

The current strict SSI runtime can already show these stock-detail metrics when provider rows contain values:

- Daily open/high/low/close, daily volume, daily trading value, and chart OHLCV from SSI `DailyOhlc`.
- Reference, ceiling, floor, adjusted close when present, matched value/volume, put-through value/volume, and foreign buy/sell/net volume/value from SSI `DailyStockPrice`.
- SSI-derived metrics from current SSI inputs: 52W high/low, 10D average volume, 3M average volume, price-vs-reference percent, and daily range percent. These remain null/status-labeled when SSI inputs are insufficient and do not change `latest_price` ownership.
- Compact short-term support/resistance zones from the latest 60 valid SSI DailyOhlc daily sessions. They are locally derived with ATR14 Wilder/RMA and swing pivots, show only nearest lower/upper ranges, and remain unavailable rather than guessed when history is insufficient. The selected ticker's daily inspect chart has an optional, default-off `S/R` overlay: S1/R1 have compact right-edge range labels, while S2/R2 remain secondary rank markers with full ranges in their titles. It adds no request, changes no chart scale, and uses no live data.
- The VN inspect chart uses official open-source Lightweight Charts 5.2 for native candlesticks, stable price/volume/RSI panes, MA/Bollinger lines, interaction, and backend-owned S/R price-axis labels. `Timeframe` (`1D`, `1m`) is separate from the D1-only `Range` presets; 1m shows Today plus loaded completed dates. Today refreshes from SSI at bounded minute-aligned points only during eligible scheduled sessions, pauses for lunch/hidden tabs, and performs one post-close reconciliation. RSI keeps a dedicated numeric 0–100 scale with 30/70 guides. One-minute axis, crosshair, and tooltip times use `Asia/Ho_Chi_Minh`, while D1 keeps `BusinessDay` dates. Visible TradingView attribution identifies the rendering library; SSI remains the market-data source, and no TradingView market data is requested.
- Limited symbol metadata such as exchange, market, security type, issuer, lot size, listed shares, and listed date when SSI `SecuritiesDetails` or `Securities` returns exact ticker fields.
- VN30/index component lists from SSI IndexComponents where available.
- Backend/API and selected-ticker frontend support for optional SSI `X-QUOTE:{symbol}` order-book context when the background stream has a usable cache row. Public rows may expose `order_book_source`, `order_book`, `order_book_status`, and sanitized `diagnostics.order_book`.
- Backend/API support for optional SSI `R:{symbol}` foreign-room context when the background stream has a usable cache row. Public rows may expose `foreign_room_source`, `foreign_room`, `foreign_room_status`, and sanitized `diagnostics.foreign_room`.
- Backend/API support for optional SSI `MI:{index_code}` market-index pulse context when the background stream has usable cache rows. Public responses may expose `market_index_pulse_source`, `market_index_pulse`, `market_index_pulse_status`, and sanitized `diagnostics.market_index_pulse`.

`X-QUOTE` order book is a separate optional live context. It does not affect `latest_price`, does not replace DailyOhlc or DailyStockPrice, and does not replace realtime `X:{symbol}` snapshots, trade tape `X-TRADE:{symbol}`, or session/status `F:{symbol}`. Malformed bid/ask levels are dropped, no fake order-book rows are synthesized, and empty/unavailable state is explicit through status/diagnostics. The dashboard and company selected-ticker panels can render a source-labeled `Order Book — SSI X-QUOTE` ladder with dynamic levels when cached rows exist, including stale last-known rows with visible stale copy and age metadata.

SSI streaming health is lifecycle-owned. Phase 4.8R adds diagnostics for message age, holiday-unaware Vietnam market session, stream health, reconnect reason/timing, subscription counts, and context counters. A stale running stream can reconnect and resubscribe the existing bootstrap channels with debounce during active trading/auction windows, while after-hours silence is classified as market closed/after-hours stale and preserves last-known rows with clear labels. Request handlers and UI refreshes remain cache readers only. Dashboard and company selected live context refresh immediately when a hidden tab becomes visible again, without changing DailyOhlc `latest_price` ownership.

`R` foreign room is a separate optional live context. It does not affect `latest_price`, does not replace DailyOhlc or DailyStockPrice daily foreign flow, and does not replace realtime `X:{symbol}` snapshots, trade tape `X-TRADE:{symbol}`, order book `X-QUOTE:{symbol}`, or session/status `F:{symbol}`. Malformed or negative room/volume/value fields are dropped/null, no fake foreign-room values are synthesized, and empty/unavailable state is explicit through status/diagnostics. Live value-unit proof and frontend foreign-room UI are still deferred.

`MI` market-index pulse is a separate optional index context. It does not affect `latest_price`, does not replace DailyOhlc, DailyStockPrice, or REST DailyIndex, and does not create stock watchlist rows. Malformed index/activity/breadth fields are dropped/null, no fake index values are synthesized, and empty/unavailable state is explicit through status/diagnostics. Live channel/field proof and frontend market-pulse UI are still deferred.

Remaining SSI-backed candidates or deferred productization need further proof before exposure:

- `F` trading session/status live market proof and UI, including possible `TradingSession` / `TradingStatus` labels after payload proof.
- Further X-QUOTE market-specific depth/level semantics after more live payload evidence; the current frontend renders dynamic cached levels without fixed-depth claims.
- `R` realtime foreign-room live proof and frontend UI; backend/API support exists.
- `MI` realtime market-index pulse live proof and frontend UI; backend/API support exists.
- `B` realtime bars.
- Unused SSI `DailyStockPrice` fields after field-key, unit, and date-alignment proof.
- Extended SSI `SecuritiesDetails` metadata after exact-field proof.

See `docs/SSI_REMAINING_DATA_AUDIT.md` for the remaining SSI-backed data backlog.

SSI-owned data must not be externalized or silently overwritten: prices, daily OHLCV, SSI-backed intraday OHLCV, realtime price snapshots, trade tape, SSI X-QUOTE order book, reference/ceiling/floor, SSI-backed foreign flow/foreign room, SSI-backed index components/realtime index pulse, and SSI-backed instrument metadata.

`external-provider-required` gaps are limited to domains SSI does not provide or cannot support sufficiently, such as news, corporate actions/dividends/rights/splits, financial statements, EPS/P/E/P/B/ROE/ROA, macro data, research reports, and ownership/shareholder data when not SSI-backed or insufficient. These fields must remain unavailable until a qualified provider contract exists.

## Data Quality

The VN dashboard is data-quality-first. The API and UI distinguish:

- Public status message: concise user-facing availability state.
- Diagnostics: provider detail, cache status, stale counts, attempted lower-level details, and legacy-provider diagnostics.

Diagnostics belong in diagnostic panels/logs, not primary metric cards.

## Phase 4.11D-1 Current-Session Audit

Phase 4.11D-1 audited current-session chart sources. Phase 4.11D-2 now implements the approved delayed-only path: SSI IntradayOhlc remains authoritative, the current bucket is `provisional` only while its normalized minute matches the active Vietnam minute, older current-day buckets are `inferred_final`, and bounded replacement polling runs without stream aggregation. X-TRADE aggregation remains blocked because observed events lack stable identity/sequence and include indistinguishable duplicates. TradingView supplies rendering only, never market data. Holidays, halts, half sessions, HNX, and UPCOM session differences remain unresolved.

Phase 4.11E adds operational hardening without changing that source boundary. Backend workers expose canonical intraday health at `/api/v1/stocks/vn/intraday-chart/health`; the separate `/api/v1/stocks/vn/observability` route remains broader dashboard diagnostics. Both are no-fetch contracts. Intraday health uses bounded process-local metrics and same-key request coalescing; values reset on restart and are independent across multiple workers. Candle timestamps stay at Vietnam minute start, newest-bar age uses the accepted raw SSI time, and provider-snapshot age uses the successful fetch time. The Today view uses one market-data timeout plus one request-free `Next update` countdown, retains bars while refreshing, avoids expected lunch staleness, performs one post-close reconciliation, and rolls Today using Vietnam time. `Force Refresh` remains explicit. This remains delayed polling and never uses X-TRADE, another provider, or a TradingView datafeed.

## Legacy / Historical Notes

Older VN dashboard notes and runbooks may mention Mozyfin or KBS because previous phases used Mozyfin for VN daily/intraday experiments and vnstock/KBS for optional snapshot experiments. Those notes are superseded for normal runtime. They are retained only for historical context or explicitly gated development paths and must not be treated as active fallback guidance.

Source: https://github.com/ZhuLinsen/daily_stock_analysis

Phase 4.11F adds generation-owned recovery for the existing optional SSI stream contexts. Disconnects retain last-known data as stale/recovering, approved subscriptions restore through the startup-owned manager, and a context becomes ready only after a fresh event from the new generation. Existing panels show concise Reconnecting, Stale, or Market closed states. The broad observability route reports worker-local lifecycle state; it does not start streams, and continuity across a disconnect is not guaranteed. DailyOhlc remains the sole D1/latest-price source and IntradayOhlc remains the sole 1m source.

Phase 4.11F-A attempted active-session runtime acceptance on 2026-07-17. Deterministic lifecycle coverage remained green, but the bounded local backend launches did not become HTTP-ready, so current SSI transport, authorization, subscription, and fresh-event readiness were not claimed. No intentional disconnect or runtime behavior change was introduced; live acceptance remains pending.

Phase 4.11F-R1 corrected the startup diagnosis: HTTP startup was not blocked by SSI. Direct and normal launch paths reached Uvicorn readiness in about five seconds while streaming continued independently. The normal launcher now waits for actual readiness and reports startup failure instead of claiming success from thread creation. This does not establish live SSI event or reconnect continuity; the bounded Phase 4.11F-A retry remains pending.
