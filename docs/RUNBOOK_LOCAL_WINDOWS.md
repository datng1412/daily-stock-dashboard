# Local Windows Quick Runbook

This runbook assumes the PC is already set up: repo cloned, Python venv created, Python dependencies installed, frontend dependencies installed, and frontend built.

Use this repo path:

```powershell
D:\daily-dashboard\daily-stock-dashboard
```

Do not print real Mozyfin keys. The app supports `MOZYFIN_API_KEY` directly; it does not currently read a Mozyfin config directory env var by itself. If you keep the key in a local file, load it into `MOZYFIN_API_KEY` from PowerShell as shown below.

## Run Live Mode

Set `$MozyfinKeyFile` to your local secret file. The file should contain only the Mozyfin API key.

```powershell
cd D:\daily-dashboard\daily-stock-dashboard
.\.venv\Scripts\Activate.ps1

$MozyfinKeyFile = "$env:USERPROFILE\.mozyfin\api_key.txt"
$MOZYFIN_KEY = (Get-Content -Raw $MozyfinKeyFile).Trim()

Remove-Item Env:MOZYFIN_FIXTURE_DIR -ErrorAction SilentlyContinue
Remove-Item Env:MOZYFIN_API_KEY -ErrorAction SilentlyContinue
$env:PYTHONUTF8 = "1"
$env:MARKET = "VN"
$env:STOCK_LIST = "FPT,VPB,MSB,SCS,ACV,ACB"
$env:MOZYFIN_API_KEY = $MOZYFIN_KEY

Write-Host "Open dashboard: http://127.0.0.1:8000/vietnam"
python main.py --webui-only
```

If you prefer Mozyfin CLI stored login instead of a key file, omit the `$MozyfinKeyFile`, `$MOZYFIN_KEY`, and `$env:MOZYFIN_API_KEY` lines after confirming:

```powershell
mozyfin-cli.cmd doctor
```

## Verify Live Mode

Run in a second PowerShell window:

```powershell
$health = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/watchlist/health"
$health | Select-Object source, fixture_mode, symbols_loaded, last_trading_date
```

Expected:

```text
source: Mozyfin live
fixture_mode: false
```

Check watchlist data:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/watchlist?tickers=FPT,VPB&include_intraday=true" |
  Select-Object source, fixture_mode
```

## Run Fixture Mode

Fixture mode uses sample/stale data only. It is not live data.

```powershell
cd D:\daily-dashboard\daily-stock-dashboard
.\.venv\Scripts\Activate.ps1

$env:PYTHONUTF8 = "1"
$env:MARKET = "VN"
$env:STOCK_LIST = "FPT,VPB,MSB,SCS,ACV,ACB"
$env:MOZYFIN_FIXTURE_DIR = "tests\fixtures\mozyfin"


Write-Host "Open dashboard: http://127.0.0.1:8000/vietnam"
python main.py --webui-only
```

Expected health:

```text
source: Mozyfin fixture
fixture_mode: true
```

## Stop Old Backend Process

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    ($_.CommandLine -like '*main.py --webui-only*' -or
     $_.CommandLine -like '*main.py --serve-only*') -and
    $_.Name -like 'python*'
  } |
  Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine

Stop-Process -Id <PID> -Force
```

## Fix Port 8000 Occupied

```powershell
netstat -ano | findstr :8000
Stop-Process -Id <PID> -Force
```

## Rebuild Frontend If UI Is Stale

```powershell
cd D:\daily-dashboard\daily-stock-dashboard\apps\dsa-web
npm.cmd run build
```

Then restart the backend.

## Run Tests

Backend:

```powershell
cd D:\daily-dashboard\daily-stock-dashboard
.\.venv\Scripts\python.exe -m pytest tests\test_mozyfin_vn_adapter.py -q
```

Frontend:

```powershell
cd D:\daily-dashboard\daily-stock-dashboard\apps\dsa-web
npm.cmd test -- vietnamWatchlist.test.ts
npm.cmd test -- vietnamTime.test.ts
npm.cmd test -- vietnamConditionSummary.test.ts
npm.cmd run build
```
