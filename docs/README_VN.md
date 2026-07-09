# Vietnam Dashboard Setup

This page is the current entry point for VN dashboard setup. The active runtime is strict SSI FastConnect mode.

## Current Runtime

- Daily OHLCV, daily chart candles, and canonical `latest_price` come from SSI `DailyOhlc` close when DailyOhlc rows exist.
- SSI `DailyStockPrice` is enrichment only: reference prices, ceiling/floor, adjusted close when present, matched/put-through fields, and foreign-flow fields. It must not overwrite `latest_price`.
- Intraday candles come from SSI `IntradayOhlc`.
- Realtime snapshots come from the optional SSI `X:{symbol}` live contract and stay separate from daily prices.
- Trade tape comes from the optional SSI `X-TRADE:{symbol}` latest-event stream context and stays separate from daily prices.
- Foreign room comes from the optional SSI `R:{symbol}` live context when a usable streaming cache row exists and stays separate from DailyStockPrice daily foreign flow.
- Market-index pulse comes from the optional SSI `MI:{index_code}` live context when usable streaming cache rows exist and stays separate from REST DailyIndex and stock rows.
- VN30/index components are SSI-backed where available.
- News, fundamentals, financial statements, ratios, macro data, research reports, and corporate actions/dividends/rights/splits are disabled / `not_implemented` until a separate qualified provider is added for those gaps.
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

## Legacy / Historical Notes

Older VN dashboard notes and runbooks may mention Mozyfin or KBS because previous phases used Mozyfin for VN daily/intraday experiments and vnstock/KBS for optional snapshot experiments. Those notes are superseded for normal runtime. They are retained only for historical context or explicitly gated development paths and must not be treated as active fallback guidance.

Source: https://github.com/ZhuLinsen/daily_stock_analysis
