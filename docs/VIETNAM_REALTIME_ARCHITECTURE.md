# Vietnam Realtime Snapshot Architecture

Last updated: 2026-06-11

## Purpose

This document defines the current optional Vietnam KBS/vnstock snapshot and trade tape architecture.

The KBS layer is additive. It does not replace Mozyfin, does not change `latest_price`, does not write into Mozyfin caches, and does not change `/api/v1/stocks/vn/watchlist` or `/api/v1/stocks/vn/watchlist/overview` semantics.

## Current Daily And Intraday Semantics

The Vietnam dashboard data semantics remain intentionally conservative:

- `latest_price` equals the Mozyfin daily OHLCV close.
- `intraday_pulse` is derived from Mozyfin 1H OHLCV candles.
- Mozyfin quote and foreign output remain metadata unless a source is proven to expose reliable matched-price semantics.
- Quote and foreign metadata rules remain unchanged.
- The dashboard displays neutral condition labels only and does not emit trading recommendations.

Daily OHLCV close, 1H candles, KBS board snapshot, and KBS trade tape have different freshness and meaning, so they are displayed separately.

## Current KBS Snapshot Endpoint

Endpoint:

```text
GET /api/v1/stocks/vn/realtime?tickers=FPT,ACB,VCB
```

Provider:

- Uses `Trading(source="KBS").price_board(tickers)` through vnstock when `vnstock` is installed.
- Returns unavailable rows instead of crashing app startup when vnstock is missing or unavailable.
- Requires no app credentials.
- Must not mutate Mozyfin OHLCV, quote/foreign, intraday, overview, or detail caches.

Quote fields include:

- `symbol`
- `realtime_price`
- `realtime_time`
- `realtime_time_display`
- `snapshot_price`
- `snapshot_time`
- `snapshot_time_display`
- `snapshot_note`
- `reference_price`
- `open_price`
- `high_price`
- `low_price`
- `average_price`
- `price_change`
- `percent_change`
- `volume_accumulated`
- `total_value`
- `bid_price_1`
- `bid_vol_1`
- `ask_price_1`
- `ask_vol_1`
- `foreign_buy_volume`
- `foreign_sell_volume`
- `foreign_room`
- `age_seconds`
- `is_stale`
- `stale_reason`
- `source`
- `status`
- `error`

`close_price` from the KBS board is mapped to both `realtime_price` and `snapshot_price` for compatibility and clarity. It must not be copied into Mozyfin `latest_price`.

## Staleness Rules

KBS timestamps are normalized conservatively:

- Epoch milliseconds are parsed as provider timestamps.
- Datetime strings are parsed as Vietnam-local timestamps where applicable.
- Missing or unparseable timestamps do not crash the endpoint.
- Unparseable timestamps return `is_stale=null` and `stale_reason="timestamp_unparseable"`.
- During a trading session, age greater than 60 seconds is stale.
- Age less than or equal to 60 seconds is fresh.

These backend fields are raw technical freshness metadata. The dashboard keeps
`age_seconds`, `is_stale`, and `stale_reason` visible, then derives a separate
phase-aware display state from the VN market phase:

- Active trading phases show live, delayed, or `KBS snapshot stale during trading`.
- Lunch break, post-close, closed, and weekend phases show the old snapshot as the last available KBS snapshot instead of active-trading stale.
- Unavailable/error provider status remains unavailable.
- Missing age on an otherwise available quote is shown as unknown.

The dashboard should show phase-aware stale or unavailable status without erasing Mozyfin rows.

## Current KBS Trade Tape Endpoint

Endpoint:

```text
GET /api/v1/stocks/vn/realtime/trades?symbol=FPT&limit=100
```

Provider:

- Uses `Market().equity(symbol).trades()` through vnstock when available.
- Returns latest trade tape rows only.
- Does not synthesize auction or ATC rows from quote data.
- Must not be used as daily OHLCV close.

Trade fields include:

- `time`
- `price`
- `volume`
- `match_type`
- `id`
- `source`

Important caveat: KBS trade tape may exclude auction or ATC prints depending on provider output. KBS board snapshot is the better source for current or closing board state.

## Frontend Display

The Vietnam dashboard currently shows:

- Daily close: existing Mozyfin `latest_price`.
- KBS snapshot: KBS board snapshot price, time, change, volume, stale/unavailable state.
- KBS snapshot display state: phase-aware live/delayed/stale/last-available status, with raw age and stale reason kept compactly visible.
- Latest trade tape: selected ticker trade tape rows with time, price, volume, match type, and source.
- Data status panel: Mozyfin source/fixture state, KBS status, stale/unavailable counts, selected ticker status, last KBS quote/trade refresh times, and auto-refresh state.
- VN market phase label: normal-weekday phase in `Asia/Ho_Chi_Minh`.

KBS failures should display compact warnings and keep existing Mozyfin overview/detail rows intact.

## Refresh Behavior

Manual refresh:

- `Refresh KBS` refreshes KBS quote rows for the active watchlist and KBS trade tape for the selected ticker.
- It does not call Mozyfin `/watchlist` or `/watchlist/overview`.

Auto refresh:

- `Auto-refresh KBS` is off by default.
- KBS quotes interval options: 10s, 15s, 30s. Default: 15s.
- Latest trade tape interval options: 5s, 10s, 15s. Default: 10s.
- Quote refresh and trade refresh have independent in-flight guards.
- Browser hidden tabs pause both refresh loops and resume safely when visible.

## Cache Rules

KBS caches are process-local and separate from Mozyfin caches:

```text
vnstock_realtime:<ticker_list>
vnstock_trades:<symbol>
```

Rules:

- KBS snapshot TTL should remain in the 10-15 second range unless provider limits require a slower interval.
- KBS trade tape TTL is 5 seconds so a 5 second UI interval is meaningful.
- Do not write KBS data into OHLCV daily cache.
- Do not write KBS data into Mozyfin quote/foreign cache.
- Do not write KBS data into intraday OHLCV cache.
- `force_refresh=true` for watchlist remains scoped to Mozyfin watchlist calls.

## VN Market Phase Labels

Frontend market phase labels use `Intl.DateTimeFormat` with `Asia/Ho_Chi_Minh`; do not manually add UTC offsets.

Normal weekday labels:

- before 09:00: `Pre-open`
- 09:00-09:15: `ATO opening auction`
- 09:15-11:30: `Continuous morning`
- 11:30-13:00: `Lunch break`
- 13:00-14:30: `Continuous afternoon`
- 14:30-14:45: `ATC closing auction`
- 14:45-15:00: `Post-close`
- after 15:00: `Closed`
- Saturday/Sunday: `Weekend / closed`

Holiday calendars are not implemented. The utility reports `holidayAware=false`.

## Deployment

Runtime deployment now includes `vnstock==4.0.4`.

Docker/Render notes:

- vnstock/KBS needs no extra credentials.
- Render live mode still needs `MOZYFIN_API_KEY` for Mozyfin daily/intraday data.
- Do not set `MOZYFIN_FIXTURE_DIR` in production.
- If KBS endpoints return unavailable, check container logs and `python -m pip show vnstock`.
- Public deployment must review vnstock/KBS license, terms of use, rate limits, and redistribution constraints.

## Validation Status

The current implementation has been validated with:

- `python -m pytest tests/test_vnstock_realtime_fetcher.py -q`
- `python -m pytest tests/test_mozyfin_vn_adapter.py -q`
- frontend Vietnam dashboard tests
- `npm.cmd run build`
- Docker build
- Docker compose startup
- Docker health endpoint smoke checks
- KBS snapshot and trade endpoint smoke checks in container

## Risks

- vnstock/KBS license and usage terms may limit public deployment, commercial use, or redistribution.
- KBS snapshot is polling/snapshot data and is not guaranteed official exchange realtime.
- KBS trade tape may exclude auction or ATC prints.
- Holiday calendar support is not implemented.
- Provider behavior on public Render deployments should be checked separately from local Docker validation.
