# Decisions

Last updated: 2026-06-11

This file records current product and engineering decisions that should not be re-litigated without explicit user direction.

## Vietnam Dashboard Data Source

Decision: use Mozyfin as the Vietnam daily OHLCV, overview, selected detail, news, and intraday 1H adapter, with a fixture mode for local deterministic testing.

Rationale:

- Live market data requires authentication and network access.
- Fixture mode makes local UI/API development deterministic.
- The API must clearly expose whether it is using live or fixture data.

Operational rule:

- `MOZYFIN_FIXTURE_DIR` must be unset for live mode.
- `MOZYFIN_API_KEY` must be present or the Mozyfin CLI must have usable stored auth for live mode.
- Do not mask fixture mode as live mode.
- KBS/vnstock snapshot and trade tape endpoints are optional separate layers. They must not replace Mozyfin daily or intraday fields.

## External Realtime And News Resources

Decision: external realtime and news resource docs may exist under `docs/resources/`, but they are reference-only until explicitly approved.

Operational rule:

- Mozyfin remains the active Vietnam dashboard provider unless changed by a decision record.
- No provider replacement should happen implicitly.
- Resource docs must not trigger implementation, new API calls, scraping, or dashboard behavior changes by themselves.
- Any future provider implementation must first summarize auth, rate limits, timestamp semantics, and data/price semantics.

## Vietnam KBS Snapshot Layer

Decision: vnstock/KBS snapshot support is an implemented optional data layer, not a replacement for daily OHLCV close.

Rationale:

- Current `latest_price` semantics are auditable because they use Mozyfin daily OHLCV close.
- KBS snapshot data has different licensing, timestamp, delay, cache, and provider semantics.
- Users must be able to distinguish daily close, 1H intraday pulse, KBS board snapshot, and trade tape at a glance.

Operational rule:

- Do not overwrite `latest_price` with KBS snapshot price.
- Do not label daily close as realtime.
- Do not write KBS snapshot or trade tape data into OHLCV, Mozyfin quote/foreign, or intraday OHLCV caches.
- KBS snapshot fields should remain separate, including `realtime_price`, `snapshot_price`, normalized timestamp display, age, stale, and error/unavailable state.
- `GET /api/v1/stocks/vn/realtime?tickers=FPT,ACB,VCB` returns KBS board snapshot rows when vnstock is available.
- `GET /api/v1/stocks/vn/realtime/trades?symbol=FPT&limit=100` returns KBS trade tape rows when vnstock is available.
- Existing `/api/v1/stocks/vn/watchlist` and `/api/v1/stocks/vn/watchlist/overview` semantics must remain unchanged.
- Architecture reference: `docs/VIETNAM_REALTIME_ARCHITECTURE.md`.

## KBS Trade Tape Semantics

Decision: KBS `trades()` output is shown as latest trade tape only.

Rationale:

- Trade tape output may exclude auction or ATC prints depending on provider behavior.
- KBS `price_board()` is the better source for board snapshot or closing board state.
- The dashboard should explain this difference without synthesizing missing auction rows.

Operational rule:

- Do not fake 14:45 ATC trade rows from snapshot data.
- Do not use trade tape as Mozyfin daily OHLCV close.
- Label the section `Latest trade tape` and keep it separate from Daily close and KBS snapshot.

## Latest Price Semantics

Decision: `latest_price` uses the latest daily OHLCV close unless Mozyfin quote output provides a reliable latest matched price.

Rationale:

- Current quote output does not expose a reliable realtime matched price field.
- The daily OHLCV close is stable and auditable.
- The UI should disclose that the displayed latest price may be an OHLCV close.

Implication:

- During trading hours, the latest daily candle may still be in progress.
- After market close, it may represent final close, but finality still depends on source metadata.

## Quote Semantics

Decision: quote output is not currently treated as the reliable latest matched price source.

Rationale:

- Current quote output is valuable for foreign flow quantities and related fields.
- Price freshness and match semantics are not reliable enough to label it as realtime matched price.

## Intraday Semantics

Decision: intraday pulse is based on 1H OHLCV candles, not realtime quote ticks.

Rationale:

- Mozyfin 1H candles provide a clear, reproducible pulse view.
- The dashboard should not imply tick-level or matched realtime behavior.

## RSI Method

Decision: RSI14 uses Wilder/RMA smoothing.

Rationale:

- Wilder/RMA is the expected market convention for RSI.
- A simple rolling RSI debug comparison may exist, but the user-facing RSI method is Wilder/RMA.

## Status Labels

Decision: Vietnam dashboard labels are neutral condition tags only.

Rationale:

- The dashboard is a monitoring surface.
- It must not emit buy/sell recommendations.

Forbidden behavior:

- Do not add labels such as `Buy`, `Sell`, `Accumulate`, `Take profit`, or equivalent recommendation language unless the product requirement explicitly changes.

## Cache TTLs

Decision: current Vietnam process-local TTLs are:

| Data type | TTL |
| --- | ---: |
| OHLCV daily | 300 seconds |
| Quote | 60 seconds |
| Intraday OHLCV | 60 seconds |
| News | 1800 seconds |
| KBS snapshot quotes | 10-15 seconds |
| KBS trade tape | 5 seconds |

Rationale:

- Daily OHLCV can be cached longer than quote or intraday data.
- News changes less frequently.
- Quote TTL can be revisited if quote becomes the reliable price source.
- KBS quote and trade tape caches are separate from Mozyfin caches so KBS refresh does not reload overview/detail data.

## KBS Refresh Behavior

Decision: KBS UI refresh is independent from Mozyfin overview/detail refresh.

Operational rule:

- Manual `Refresh KBS` refreshes only KBS quotes and selected ticker trade tape.
- `Auto-refresh KBS` is off by default.
- KBS quote interval options are 10s, 15s, and 30s, with default 15s.
- Latest trade tape interval options are 5s, 10s, and 15s, with default 10s.
- KBS refresh must not call `/watchlist` or `/watchlist/overview`.

## Time Formatting

Decision: VN dashboard times should be formatted for Vietnam users.

Rationale:

- Operators reading the VN dashboard need local market context.
- Avoid mixing UTC timestamps into visible UI unless the field is explicitly technical/debug.

## VN Market Phase Labels

Decision: the VN dashboard shows frontend-derived normal-weekday market phase labels in `Asia/Ho_Chi_Minh`.

Operational rule:

- Supported labels are `Pre-open`, `ATO opening auction`, `Continuous morning`, `Lunch break`, `Continuous afternoon`, `ATC closing auction`, `Post-close`, `Closed`, and `Weekend / closed`.
- Holiday calendars are not implemented; the utility reports `holidayAware=false`.
- Market phase labels are explanatory context only. They do not change data source semantics.
