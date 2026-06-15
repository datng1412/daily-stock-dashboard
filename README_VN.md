# Vietnam Market Setup

This repo now supports an initial Vietnam market adapter through `mozyfin-cli`.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
cd apps/dsa-web
npm install
```

2. Install or enable Mozyfin:

```bash
npm install -g mozyfin-cli
mozyfin login --api-key <mozyfin-api-key>
```

You can also skip global install and let the adapter call `npx mozyfin-cli`.
For authenticated live data, either log in with `mozyfin-cli` or set:

```bash
MOZYFIN_API_KEY=<mozyfin-api-key>
```

Do not set `MOZYFIN_FIXTURE_DIR` for live data. Set it only when you intentionally want fixture/test mode.

3. Enable Vietnam market routing:

```bash
MARKET=VN
STOCK_LIST=FPT,VPB,MSB,SCS,ACV,ACB
```

4. Run the backend and web UI:

```bash
python main.py --webui-only
```

Open `http://127.0.0.1:8000/vietnam`.

For fixture-only local testing:

```bash
MARKET=VN
MOZYFIN_FIXTURE_DIR=tests/fixtures/mozyfin
python main.py --webui-only
```

## Architecture Map

- Market data adapters: `data_provider/`, especially `data_provider/base.py` and `data_provider/mozyfin_fetcher.py`.
- Stock OHLCV flow: `DataFetcherManager.get_daily_data()` returns the existing standard dataframe columns: `date`, `open`, `high`, `low`, `close`, `volume`, `amount`, `pct_chg`.
- Stock data API: `src/services/stock_service.py` and `api/v1/endpoints/stocks.py`. The VN dashboard does not currently use Mozyfin quote as a reliable realtime matched price source.
- Optional KBS snapshot/trade tape layer: `data_provider/vnstock_realtime_fetcher.py` and the `/api/v1/stocks/vn/realtime*` endpoints.
- News flow: existing global search is in `src/search_service.py`; VN dashboard news uses `MozyfinFetcher.get_news()` when Mozy output is available.
- Indicators/core analysis: `src/stock_analyzer.py` computes MA, bias, volume, MACD, RSI, and signal score. This was not changed.
- Dashboard output: `src/services/vietnam_market_service.py`, `api/v1/endpoints/stocks.py`, and `apps/dsa-web/src/pages/VietnamDashboardPage.tsx`.

## Supported Tickers

Initial watchlist: `FPT`, `VPB`, `MSB`, `SCS`, `ACV`, `ACB`.

Known exchange mapping is in `data_provider/mozyfin_fetcher.py`:

- HOSE: `FPT`, `VPB`, `MSB`, `SCS`
- HNX: `ACB`
- UPCoM: `ACV`

## Mozy Field Mapping

The adapter accepts CSV fields from `mozyfin ohlcv <ticker>.VN --timeframe 1d --limit N --csv file`.

- Trading date: `date`, `trading_date`, `time`, `timestamp`, or `datetime` -> `date`
- OHLC: `open/high/low/close` or `o/h/l/c`
- Volume: `volume`, `vol`, or `v` -> `volume`
- Amount/value: `amount`, `value`, `turnover`, or `trading_value` -> `amount`
- Percent change: `pct_chg`, `change_percent`, `change_pct`, or `pct_change` -> `pct_chg`
- Market index: derived from exchange: HOSE -> `VNINDEX.VN`, HNX -> `HNXINDEX.VN`, UPCoM -> `UPCOMINDEX.VN`
- Foreign trading: `foreign_buy`, `foreign_sell`, `foreign_net` when available
- Ex-dividend/adjusted warning: `adjusted`, `is_adjusted`, `ex_dividend`, or `corporate_action`

Current live Mozyfin quote output exposes foreign flow through quantity fields:

- `buy_foreign_quantity` -> `foreign.buy`
- `sell_foreign_quantity` -> `foreign.sell`
- `buy_foreign_quantity - sell_foreign_quantity` -> `foreign.net`

These foreign flow values are share quantities, not VND value. Price fields are VND and volume fields are shares.

Current Mozyfin quote output does not expose a reliable latest/matched/current price for the VN dashboard. `latest_price` uses the OHLCV daily close. Intraday Pulse uses Mozyfin OHLCV `1h` candles; those candles are not realtime matched quotes.

## Optional KBS Snapshot Layer

The dashboard can also display optional vnstock/KBS snapshot data as a separate layer. This does not replace Mozyfin and does not change `latest_price`.

Endpoints:

```text
GET /api/v1/stocks/vn/realtime?tickers=FPT,ACB,VCB
GET /api/v1/stocks/vn/realtime/trades?symbol=FPT&limit=100
```

KBS snapshot fields include:

- `realtime_price`
- `realtime_time`
- `realtime_time_display`
- `snapshot_price`
- `snapshot_time`
- `snapshot_time_display`
- `snapshot_note`
- `age_seconds`
- `is_stale`
- `stale_reason`

KBS trade tape fields include `time`, `price`, `volume`, `match_type`, `id`, and `source`. Trade tape may exclude auction or ATC prints depending on provider output, so the dashboard keeps it separate from the KBS board snapshot.

Runtime notes:

- `vnstock==4.0.4` is installed in Docker/Render runtime dependencies.
- vnstock/KBS requires no extra app credentials.
- If vnstock is unavailable, the endpoints should return unavailable status instead of crashing the app.
- Before public deployment, confirm vnstock/KBS license, usage, and redistribution terms.

Dashboard behavior:

- Daily close remains Mozyfin `latest_price`.
- KBS snapshot is shown separately from Daily close.
- Latest trade tape is shown separately for the selected ticker.
- `Refresh KBS` refreshes only KBS quote/trade endpoints.
- `Auto-refresh KBS` is off by default.
- KBS quotes refresh options are 10s, 15s, and 30s; default 15s.
- Latest trade tape refresh options are 5s, 10s, and 15s; default 10s.
- KBS refresh does not reload Mozyfin overview/detail data.
- The Data status panel shows Mozyfin source/fixture state, KBS status, stale/unavailable counts, selected ticker status, and refresh timing.
- VN market phase labels are frontend-derived for normal weekdays: `Pre-open`, `ATO opening auction`, `Continuous morning`, `Lunch break`, `Continuous afternoon`, `ATC closing auction`, `Post-close`, `Closed`, and `Weekend / closed`. Holiday calendar support is not implemented and reports `holidayAware=false`.

## Data Quality

The VN dashboard includes a data-quality panel backed by:

```text
GET /api/v1/stocks/vn/watchlist/health
```

The endpoint returns:

- `source`: `Mozyfin live` or `Mozyfin fixture`
- `fixture_mode`: whether `MOZYFIN_FIXTURE_DIR` is active
- `symbols_loaded`: number of symbols that returned data
- `last_trading_date`: latest valid trading date across loaded symbols
- `missing_fields`: per-symbol missing fields
- `errors`: per-symbol validation errors

In live mode, health should show:

```text
source: Mozyfin live
fixture_mode: false
```

Validation rules are implemented in `src/services/vietnam_market_service.py`:

- `close` must be greater than `0`
- `volume` must be greater than or equal to `0`
- `date` must parse as a valid trading date
- `foreign_net` may be positive, negative, or zero
- missing fields are shown as warnings instead of crashing the dashboard

## Dashboard Formulas

- Price change percent: `(close - previous_close) / previous_close * 100`.
- Liquidity score: `min(100, avg_volume_20d / 1,000,000 * 100)`.
- MA20: 20-day simple moving average of close.
- MA50: 50-day simple moving average of close.
- RSI14: Wilder/RMA RSI using the first 14 periods as the seed average, then recursive smoothing.
- Bollinger Band 20,2:
  - middle: `MA20`
  - upper: `MA20 + 2 * standard_deviation_20`
  - lower: `MA20 - 2 * standard_deviation_20`
- 20-day average volume: average of the latest 20 `volume` rows.
- Volume ratio: `today_volume / avg_volume_20d`.
- 20-day high/low: rolling 20-day max of `high` and rolling 20-day min of `low`.
- Distance to 20-day high: `(close - high_20d) / high_20d * 100`.
- Distance to 20-day low: `(close - low_20d) / low_20d * 100`.
- Foreign net 5D/20D: sum of `foreign_net` over the latest 5 or 20 rows when historical foreign net is available.
- Foreign net same-day status: same-day only when `foreign_date_match == "matched"`; otherwise treat it as stale, unavailable, or not aligned with the OHLCV date.
- Price limit bands:
  - HOSE: `previous_close * (1 +/- 7%)`
  - HNX: `previous_close * (1 +/- 10%)`
  - UPCoM: `previous_close * (1 +/- 15%)`
- Price-limit distance: `min(abs(ceiling - close), abs(close - floor)) / previous_close * 100`.
- Near-limit warning: true when price-limit distance is `<= 0.5%`.
- Foreign signal:
  - `net_buy` when `foreign_net > 0`
  - `net_sell` when `foreign_net < 0`
  - `neutral_or_unavailable` otherwise

Neutral status labels are rule-based descriptors, not buy/sell recommendations:

- `Watch`: default when no other status rule applies.
- `Stronger than market`: close is above MA20, MA20 is above MA50, and daily change is not negative.
- `Weak short-term`: close is below MA20 and daily change is negative.
- `Near support`: close is within 3% above the 20-day low.
- `Near resistance`: close is within 3% below the 20-day high.
- `Breakout candidate`: close is within 0.5% of the 20-day high and volume ratio is at least 1.2.
- `Overextended`: RSI14 is at least 70.

## Where To Adjust Formulas

- Liquidity target volume: `LIQUIDITY_TARGET_AVG_VOLUME` in `src/services/vietnam_market_service.py`.
- Liquidity calculation: `calculate_liquidity_score()` in `src/services/vietnam_market_service.py`.
- Price-limit percentages and exchange mapping: `VN_PRICE_LIMIT_PCT` and `VN_EXCHANGE_MAP` in `data_provider/mozyfin_fetcher.py`.
- Near-limit threshold: `calculate_price_limit_state()` in `src/services/vietnam_market_service.py`.
- Indicator calculations: `calculate_vietnam_indicators()` in `src/services/vietnam_market_service.py`.
- Neutral status labels: `derive_neutral_status_labels()` in `src/services/vietnam_market_service.py`.

## Troubleshooting Old Fixture Data

If the dashboard shows old fixture data:

1. Stop old backend processes that are running `main.py --webui-only`, `main.py --serve-only`, or serving port `8000`.
2. Confirm `MOZYFIN_FIXTURE_DIR` is unset for live mode.
3. Confirm Mozyfin authentication is available through `mozyfin-cli login` or `MOZYFIN_API_KEY`.
4. Call `GET /api/v1/stocks/vn/watchlist/health` and check `source` and `fixture_mode`.
5. Force a live refresh:

```text
GET /api/v1/stocks/vn/watchlist?tickers=FPT,VPB,MSB&force_refresh=true&include_intraday=true
```

Interpretation:

- `source: Mozyfin fixture` or `fixture_mode: true`: fixture mode is active.
- Direct CLI data old and API data old: Mozyfin source is stale.
- Direct CLI data fresh but API data old: backend process or cache issue.
- API data fresh but UI data old: frontend/backend port or browser cache issue.

Source: https://github.com/ZhuLinsen/daily_stock_analysis