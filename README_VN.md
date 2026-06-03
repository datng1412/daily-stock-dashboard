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
mozyfin login --api-key mozy_ak_xxx
```

You can also skip global install and let the adapter call `npx mozyfin-cli`.
For authenticated live data, set:

```bash
MOZYFIN_API_KEY=mozy_ak_xxx
```

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
- Realtime stock data API: `src/services/stock_service.py` and `api/v1/endpoints/stocks.py`.
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
- RSI14: `100 - 100 / (1 + average_gain_14 / average_loss_14)`.
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
