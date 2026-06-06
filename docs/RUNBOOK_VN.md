# Vietnam Dashboard Runbook

Last updated: 2026-06-06

## Goal

Run and debug the Vietnam dashboard in either live Mozyfin mode or fixture mode.

## Live Mode

Use live mode when validating current market data.

```powershell
cd D:\daily-dashboard\daily-stock-dashboard

Remove-Item Env:MOZYFIN_FIXTURE_DIR -ErrorAction SilentlyContinue

$env:PYTHONUTF8 = "1"
$env:MARKET = "VN"
$env:STOCK_LIST = "FPT,VPB,MSB,SCS,ACV,ACB"

# Do not print the key. Live mode requires either:
# - mozyfin-cli login
# - or MOZYFIN_API_KEY set from a secure local secret source.
# $env:MOZYFIN_API_KEY = "<mozyfin-api-key>"

.\.venv\Scripts\python.exe main.py --webui-only
```

Open:

```text
http://127.0.0.1:8000/vietnam
```

Expected health:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/watchlist/health" |
  Select-Object source, fixture_mode, symbols_loaded, last_trading_date
```

Expected:

```text
source: Mozyfin live
fixture_mode: False
```

## Fixture Mode

Use fixture mode only for deterministic local testing.

```powershell
cd D:\daily-dashboard\daily-stock-dashboard

$env:PYTHONUTF8 = "1"
$env:MARKET = "VN"
$env:STOCK_LIST = "FPT,VPB,MSB,SCS,ACV,ACB"
$env:MOZYFIN_FIXTURE_DIR = "tests/fixtures/mozyfin"

.\.venv\Scripts\python.exe main.py --webui-only
```

Expected:

```text
source: Mozyfin fixture
fixture_mode: True
```

## Stop Old Backend Processes

Before debugging stale data, stop old project Python processes.

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    ($_.CommandLine -like '*main.py --webui-only*' -or
     $_.CommandLine -like '*main.py --serve-only*') -and
    $_.Name -like 'python*'
  } |
  Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine
```

Stop the matching PIDs:

```powershell
Stop-Process -Id <PID> -Force
```

Check port 8000:

```powershell
netstat -ano | findstr ":8000"
```

## Check Mozyfin CLI

The CLI may not be in PATH. Check PATH first:

```powershell
where.exe mozyfin-cli
where.exe mozyfin
where.exe mozyfin-cli.cmd
where.exe mozyfin.cmd
```

If PATH lookup fails, use the full path from your npm global bin directory. Common Windows locations include:

```text
%APPDATA%\npm\mozyfin-cli.cmd
%APPDATA%\npm\mozyfin.cmd
```

Example full-path fallback:

```powershell
& "$env:APPDATA\npm\mozyfin-cli.cmd" --help
```

Run doctor without printing secrets, using either the PATH command or the full path fallback:

```powershell
mozyfin-cli.cmd doctor
# or:
& "$env:APPDATA\npm\mozyfin-cli.cmd" doctor
```

If doctor says `Missing API key`, set `MOZYFIN_API_KEY` or run login with a key supplied by the user. Never print the key.

## Direct Live Checks

```powershell
mozyfin-cli.cmd ohlcv FPT.VN --timeframe 1d --limit 3 --csv fpt_check.csv
mozyfin-cli.cmd ohlcv FPT.VN --timeframe 1h --limit 3 --csv fpt_1h_check.csv
mozyfin-cli.cmd quote FPT.VN --limit 1 --csv fpt_quote_check.csv

Get-Content fpt_check.csv
Get-Content fpt_1h_check.csv
Get-Content fpt_quote_check.csv
```

If PATH lookup fails, replace `mozyfin-cli.cmd` with the full path fallback, for example `& "$env:APPDATA\npm\mozyfin-cli.cmd"`.

Compare these dates to API and UI dates.

## Force Refresh API

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/watchlist?tickers=FPT,VPB,MSB&force_refresh=true&include_intraday=true"
```

For FPT, inspect:

- `latest_price`
- `latest_price_source`
- `latest_price_date`
- `ohlcv_date`
- `quote_date`
- `foreign_net_date`
- latest `intraday_candles[].date_time`
- `source`
- `fixture_mode`
- `cache_status`
- `warnings`

## Stale Data Diagnosis

Use this order:

1. Multiple backend processes or old port 8000 listener.
2. Wrong frontend/backend port.
3. `MOZYFIN_FIXTURE_DIR` set.
4. Mozyfin auth missing.
5. Direct Mozyfin CLI returning old data.
6. API cache returning stale data.
7. Browser or frontend build cache.

Interpretation:

- CLI old, API old: Mozyfin source is stale.
- CLI fresh, API old: backend/cache/process issue.
- API fresh, UI old: frontend/browser/port issue.
- `fixture_mode: true`: fixture mode issue.
- Multiple backend processes: process/port issue.

## Data Semantics Reminder

- `latest_price` currently uses OHLCV daily close if quote has no reliable latest matched price.
- Quote is not a reliable latest matched price source yet.
- Intraday pulse uses 1H OHLCV candles, not realtime quote.
- RSI14 uses Wilder/RMA.
- Labels are neutral condition tags only, not recommendations.
- VN dashboard visible times should use Vietnam time.
