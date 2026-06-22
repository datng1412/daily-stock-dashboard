# Vietnam Dashboard Runbook

Last updated: 2026-06-22

## Goal

Run and debug the Vietnam dashboard in strict SSI FastConnect mode. Mozyfin is disabled for VN runtime, KBS is legacy optional only, and news is disabled until a separate NewsProvider is implemented.

## Live SSI Mode

Use live SSI mode when validating current market data. Do not print SSI credentials, tokens, account IDs, or auth headers.

```powershell
cd D:\stock-dashboard

$env:PYTHONUTF8 = "1"
$env:MARKET = "VN"
$env:STOCK_LIST = "FPT,VPB,MSB,SCS,ACV,ACB"

$env:SSI_FASTCONNECT_ENABLED = "true"
$env:SSI_FASTCONNECT_BASE_URL = "https://fc-data.ssi.com.vn/api/v2/Market"
$env:VN_DAILY_DATA_PROVIDER = "ssi"
$env:VN_CHART_DATA_PROVIDER = "ssi"
$env:VN_DAILY_STOCK_PRICE_PROVIDER = "ssi"
$env:VN_INDEX_DATA_PROVIDER = "ssi"
$env:VN_INTRADAY_DATA_PROVIDER = "ssi"
$env:VN_REALTIME_DATA_PROVIDER = "ssi"
$env:VN_TRADE_TAPE_PROVIDER = "ssi"
$env:VN_NEWS_PROVIDER = "disabled"
$env:MOZYFIN_ENABLED = "false"
$env:MOZYFIN_NEWS_ENABLED = "false"
$env:VN_ALLOW_LEGACY_MOZYFIN_PROVIDER = "false"
$env:KBS_ENABLED = "false"
$env:VN_ALLOW_LEGACY_KBS_PROVIDER = "false"

# Set SSI_FASTCONNECT_CONSUMER_ID and SSI_FASTCONNECT_CONSUMER_SECRET
# from a local secret source only. Do not echo them.

python main.py --serve-only --host 127.0.0.1 --port 8000
```

For local frontend development, run the web app separately after starting the backend:

```powershell
cd D:\stock-dashboard\apps\dsa-web
npm.cmd ci
npm.cmd run dev
```

Use the URL printed by Vite for frontend development. The built frontend is served by the backend when using `--serve-only` with current build artifacts.

Open:

```text
http://127.0.0.1:8000/vietnam
http://127.0.0.1:8000/vietnam/company/FPT
```

Expected watchlist behavior:

```text
source: SSI
actual_source: SSI
fallback_used: false
news_status.status: disabled
```

## Safe SSI Smoke

Run the smoke script when local SSI credentials are configured. It prints safe status/count/key information only.

```powershell
python scripts\ssi_fastconnect_smoke.py
```

Expected high-level result in a healthy SSI environment:

```text
SSI enabled: true
AccessToken: OK
DailyOhlc FPT rows: around 250
DailyStockPrice FPT rows: around 250
DailyIndex VN30 rows: around 250
```

Use probe mode only for endpoint diagnostics. It must not print tokens, credentials, auth headers, or full provider bodies.

```powershell
python scripts\ssi_fastconnect_smoke.py --probe
```

## Force Refresh API

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/watchlist?tickers=FPT,VPB,MSB&force_refresh=true&include_intraday=true" |
  ConvertTo-Json -Depth 12
```

For each ticker, inspect:

- `source`
- `actual_source`
- `fallback_used`
- `latest_price`
- `latest_price_source`
- `latest_price_date`
- `ohlcv_date`
- `daily_stock_price.status`
- `reference_price`
- `ceiling_price`
- `floor_price`
- `foreign_net_volume`
- `foreign_net_value`
- `intraday_status`
- `intraday_candles`
- `intraday_pulse`
- `realtime_status`
- `realtime_snapshot`
- `trade_tape_status`
- `trade_tape`
- `news_status`
- `cache_status`

Use `ConvertTo-Json -Depth 12`; shallow JSON depth can stringify nested objects as `@{...}` and mislead debugging.

## Smoke Endpoints

Use these endpoints for a focused docs/runtime smoke. They should not print credentials or raw auth responses.

```text
GET http://127.0.0.1:8000/api/v1/stocks/vn/watchlist?tickers=FPT&force_refresh=true
GET http://127.0.0.1:8000/api/v1/stocks/vn/index-components?index_code=VN30
GET http://127.0.0.1:8000/api/v1/stocks/vn/observability
GET http://127.0.0.1:8000/vietnam
GET http://127.0.0.1:8000/vietnam/company/FPT
```

Expected smoke behavior:

* Daily SSI data is visible when credentials and DailyOhlc are available.
* `news_status.status` is `disabled`.
* Missing realtime and trade tape render unavailable states.
* Intraday is unavailable if stale or date-mismatched.
* Optional live sections do not render fake metric rows.
* Mozyfin and KBS are not normal-mode fallbacks.

## Live Section Contract Checks

The live-section contract is strict:

- No object data: `null`
- No list data: `[]`
- Public status: `ok`, `unavailable`, or `disabled`
- Technical details: diagnostics/logs, not primary metric fields

Expected unavailable examples:

```text
realtime_snapshot: null
intraday_pulse: null
intraday_candles: []
trade rows: []
```

The UI should show concise states such as:

```text
SSI intraday unavailable.
SSI realtime unavailable. Daily SSI data is still available.
SSI trade tape unavailable.
News disabled.
```

Do not treat unavailable intraday, realtime, trade tape, index components, or news as daily SSI row failure when SSI DailyOhlc is valid.

## Current Data-Quality Checks

### DailyOhlc vs DailyStockPrice

If SSI DailyOhlc and SSI DailyStockPrice disagree for the same ticker/date, do not silently overwrite one source with the other. First check:

1. Same trading date.
2. Cache freshness.
3. Old backend process.
4. Chart/watchlist TTL mismatch.
5. Whether the provider has provisional versus final values.

Current dashboard rule: `latest_price` uses SSI DailyOhlc close as canonical dashboard price. DailyStockPrice provides reference/limits/foreign/matched/put-through fields unless a future design explicitly changes canonical source semantics.

### Intraday Freshness

If latest SSI intraday candle date does not match latest SSI daily trading date:

- Keep daily SSI row `ok` when DailyOhlc is valid.
- Mark intraday unavailable.
- Keep `intraday_pulse = null`.
- Keep `intraday_candles = []` for the usable public section.
- Put stale-date diagnostics in status/diagnostics.

### Realtime And Trade Tape

SSI realtime snapshot and SSI trade tape are separate optional live contracts. If live endpoints return unavailable or no usable rows:

- Keep daily SSI row `ok` when DailyOhlc is valid.
- Keep public status concise.
- Put attempted endpoint, HTTP status, retryability, and provider-error details in diagnostics.
- Do not use KBS unless explicit legacy diagnostics flags are enabled.

## Stale Data Diagnosis

Use this order:

1. Multiple backend processes or old port listener.
2. Wrong frontend/backend port.
3. SSI credentials missing or provider disabled.
4. SSI DailyOhlc cache returning stale data.
5. SSI DailyStockPrice cache returning a different date/window.
6. Browser or frontend build cache.
7. Optional live-section endpoint unavailable; this is not a daily-data failure.

Useful process check:

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    ($_.CommandLine -like '*main.py --webui-only*' -or
     $_.CommandLine -like '*main.py --serve-only*') -and
    $_.Name -like 'python*'
  } |
  Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine
```

Stop a stale matching PID only after confirming it belongs to this workspace:

```powershell
Stop-Process -Id <PID> -Force
```

Check port 8000:

```powershell
netstat -ano | findstr ":8000"
```

## TEMP/TMP And npm Cache When C: Is Full

If Windows temporary storage or the npm cache on `C:` is full, redirect temporary paths for the current PowerShell session before running frontend install/build commands:

```powershell
New-Item -ItemType Directory -Force D:\stock-dashboard\.tmp | Out-Null
New-Item -ItemType Directory -Force D:\stock-dashboard\.npm-cache | Out-Null
$env:TEMP = "D:\stock-dashboard\.tmp"
$env:TMP = "D:\stock-dashboard\.tmp"
$env:npm_config_cache = "D:\stock-dashboard\.npm-cache"
```

These settings only affect the current shell session. They do not change SSI provider ownership or dashboard data semantics.

## Docker / Render Notes

Docker and Render should use SSI environment variables and must not require Mozyfin API keys for VN dashboard runtime.

Required secret values:

```text
SSI_FASTCONNECT_CONSUMER_ID=<set in secret env>
SSI_FASTCONNECT_CONSUMER_SECRET=<set in secret env>
```

Required non-secret provider defaults:

```text
SSI_FASTCONNECT_ENABLED=true
VN_DAILY_DATA_PROVIDER=ssi
VN_CHART_DATA_PROVIDER=ssi
VN_DAILY_STOCK_PRICE_PROVIDER=ssi
VN_INDEX_DATA_PROVIDER=ssi
VN_INTRADAY_DATA_PROVIDER=ssi
VN_REALTIME_DATA_PROVIDER=ssi
VN_TRADE_TAPE_PROVIDER=ssi
VN_NEWS_PROVIDER=disabled
MOZYFIN_ENABLED=false
MOZYFIN_NEWS_ENABLED=false
KBS_ENABLED=false
```

Use `/tmp/dsa-cache` when the deployment service does not have a persistent disk. Cache behavior must not change SSI/Mozyfin/KBS source ownership.

## Data Semantics Reminder

- `latest_price` uses SSI DailyOhlc close when SSI daily data is available.
- SSI DailyStockPrice supplies reference/limits, matched/put-through, and latest foreign-flow fields.
- SSI IntradayOhlc is not a realtime matched quote.
- SSI realtime snapshot and trade tape are separate optional live contracts.
- News is disabled until a separate provider is implemented.
- RSI14 uses Wilder/RMA.
- Labels are neutral condition tags only.
- VN dashboard visible times should use Vietnam time.
