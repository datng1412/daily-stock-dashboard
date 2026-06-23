# Vietnam Dashboard Setup

This page is the current entry point for VN dashboard setup. The active runtime is strict SSI FastConnect mode.

## Current Runtime

- Daily OHLCV, canonical daily close, and daily chart data come from SSI `DailyOhlc`.
- Reference prices, price limits, matched/put-through fields, and foreign-flow fields come from SSI `DailyStockPrice`.
- Intraday candles come from SSI `IntradayOhlc`.
- Realtime snapshots come from the SSI realtime contract.
- Trade tape comes from the SSI trade-tape contract.
- News is disabled / `not_implemented` until a separate VN news provider is added.
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

The dashboard must not present SSI realtime or trade-tape features as KBS, and must not mix DailyOhlc and DailyStockPrice labels into a single source.

## Data Quality

The VN dashboard is data-quality-first. The API and UI distinguish:

- Public status message: concise user-facing availability state.
- Diagnostics: provider detail, cache status, stale counts, attempted lower-level details, and legacy-provider diagnostics.

Diagnostics belong in diagnostic panels/logs, not primary metric cards.

## Legacy / Historical Notes

Older VN dashboard notes and runbooks may mention Mozyfin or KBS because previous phases used Mozyfin for VN daily/intraday experiments and vnstock/KBS for optional snapshot experiments. Those notes are superseded for normal runtime. They are retained only for historical context or explicitly gated development paths and must not be treated as active fallback guidance.

Source: https://github.com/ZhuLinsen/daily_stock_analysis
