# Vietnam Dashboard Runbook

Documentation reviewed: 2026-11-02. Commands below were inspected, not executed by this documentation audit.

## Goal

Run and debug the Vietnam dashboard in strict SSI FastConnect V3 mode. News defaults to disabled; optional local/personal news adapters have separate enablement and terms gates. Use [DOCS_INDEX](DOCS_INDEX.md) for current authority and [PROJECT_STATE](PROJECT_STATE.md) for dated acceptance and limitations.

## Operational boundaries

- The production Docker/Render path is documented in [RUNBOOK_DOCKER_RENDER](RUNBOOK_DOCKER_RENDER.md). The existing Compose file still forwards a legacy Mozyfin variable and does not forward SSI V3 credentials; it is not a complete current SSI deployment template. This documentation task does not change that file.
- REST enablement/credentials, optional streaming, local news, and scheduled alert evaluation are separate. `--serve-only` serves API/UI; it does not start scheduled AlertWorker evaluation. The existing `--schedule` path owns periodic evaluation when enabled.
- For automated server acceptance, choose a free port, own the exact child process, enforce readiness (45s), per-request (15s), and total-lifetime (120s) deadlines, then terminate the owned tree in `finally` and verify port release. Never wait for a web server to exit naturally.
- A local outbound TCP permission failure is an execution-environment block, not provider evidence. Live calls require an authorized network-capable context. `/api/health` proves application readiness only.
- Use one backend worker for coherent process-local current-flow state. Accepted completed foreign-flow history has durable cache restoration; provisional room values and current aggregates do not become completed history.

## Live SSI Mode

Use live SSI mode when validating current market data. Do not print SSI credentials, tokens, account IDs, or auth headers.

```powershell
cd D:\stock-dashboard

$env:PYTHONUTF8 = "1"
$env:MARKET = "VN"
$env:STOCK_LIST = "FPT,VPB,MSB,SCS,ACV,ACB"

$env:SSI_V3_REST_ENABLED = "true"
$env:VN_DAILY_DATA_PROVIDER = "ssi"
$env:VN_CHART_DATA_PROVIDER = "ssi"
$env:VN_DAILY_STOCK_PRICE_PROVIDER = "ssi"
$env:VN_INDEX_DATA_PROVIDER = "ssi"
$env:VN_INTRADAY_DATA_PROVIDER = "ssi"
$env:VN_REALTIME_DATA_PROVIDER = "ssi"
$env:VN_TRADE_TAPE_PROVIDER = "ssi"
$env:VN_NEWS_PROVIDER = "disabled"

# Set SSI_V3_API_KEY and SSI_V3_API_SECRET from a local secret source only.
# SSI_V3_CLIENT_ID is optional. Do not echo any credential.

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

Run the guarded V3 REST acceptance when local SSI credentials are configured. It prints only sanitized status/count/timing information.

```powershell
$env:SSI_V3_LIVE_ACCEPTANCE_ENABLED = "true"
python scripts\verify_ssi_v3_rest_access.py --live
```

Expected high-level result in a healthy SSI environment:

```text
outcome: REST_ACCESS_CONFIRMED
authentication: ok
operations: 4
```

The guard defaults to zero network. It must not print tokens, credentials, auth headers, or provider rows/bodies.

## VN Dashboard Contract Smoke

Use the Phase 2.3 smoke harness after starting the local backend. It validates the public VN dashboard contract without adding API calls, provider fallback, retries, or browser automation.

Start backend from the repo root in one PowerShell window:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_backend_local.ps1
```

Start the frontend in a second PowerShell window when you want to inspect the UI:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_web_local.ps1
```

Run the smoke harness from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_vn_dashboard.ps1 -SkipFrontendOpen
```

Force backend refresh only when you intentionally want to bypass cache:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_vn_dashboard.ps1 -SkipFrontendOpen -ForceRefresh
```

The smoke harness checks:

- `/api/v1/stocks/vn/watchlist` returns requested tickers with daily SSI fields when rows are usable.
- `ssi_foreign_net_volume` exists and the expected top-card aggregate is computed only from that field.
- Watchlist `trade_tape` is list data, with status in `trade_tape_status`.
- Missing live objects remain `null` and missing live lists remain `[]`.
- `/api/v1/stocks/vn/company/{ticker}` keeps company price/trading fields on SSI DailyOhlc and reference/foreign flow on SSI DailyStockPrice.
- News, financials, and events are not SSI-labeled.
- Public live-section messages stay short while diagnostics can retain attempted endpoints, HTTP status, retryability, and sanitized provider context.

Expected frontend URLs printed by the script:

```text
http://127.0.0.1:5173/vietnam
http://127.0.0.1:5173/vietnam/company/FPT
```

The script prints safe target URLs, tickers, PASS/FAIL status, failed checks, API status summary, and expected frontend URLs. It must not print SSI credentials, tokens, account IDs, auth headers, or raw auth responses.

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

## Bounded dashboard smoke

Use these endpoints only within an authorized bounded smoke. They should not print credentials or raw auth responses. Current priorities live in the active section of `VN_DASHBOARD_ROADMAP.md`.

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
trade_tape: []
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

Current dashboard rule: validated daily OHLC normally owns `latest_price`. The existing service may expose a newer DailyStockPrice price as explicitly partial when daily history fails freshness/completeness; history-derived indicators remain unavailable. Check source/date/quality together. This is existing same-provider degradation, not an invitation to blend same-date mismatches.

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
SSI_V3_API_KEY=<set in secret env>
SSI_V3_API_SECRET=<set in secret env>
SSI_V3_CLIENT_ID=<optional secret env>
```

REST example defaults (streaming remains separately optional):

```text
SSI_V3_REST_ENABLED=true
SSI_STREAMING_REALTIME_ENABLED=false
VN_DAILY_DATA_PROVIDER=ssi
VN_CHART_DATA_PROVIDER=ssi
VN_DAILY_STOCK_PRICE_PROVIDER=ssi
VN_INDEX_DATA_PROVIDER=ssi
VN_INTRADAY_DATA_PROVIDER=ssi
VN_REALTIME_DATA_PROVIDER=ssi
VN_TRADE_TAPE_PROVIDER=ssi
VN_NEWS_PROVIDER=disabled
```

Use `/tmp/dsa-cache` when the deployment service does not have a persistent disk. Cache behavior must not change SSI/Mozyfin/KBS source ownership.

The Docker image installs the pinned official `ssi-sdk==3.0.5` from `requirements.txt`. A missing SDK is a dependency/image issue; diagnose it separately from transport or entitlement. Removed V2 packages and channel templates must not be restored from historical notes.

## Data Semantics Reminder

- `latest_price` uses SSI DailyOhlc close when SSI daily data is available.
- SSI DailyStockPrice supplies reference/limits, matched/put-through, and latest foreign-flow fields.
- SSI IntradayOhlc is not a realtime matched quote.
- SSI realtime snapshot and trade tape are separate optional live contracts.
- News defaults to disabled; implemented personal/local adapters require their explicit configuration and terms gates.
- RSI14 uses Wilder/RMA.
- Labels are neutral condition tags only.
- VN dashboard visible times should use Vietnam time.
