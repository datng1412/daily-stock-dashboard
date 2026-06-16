# Docker and Render Runbook

This runbook covers local Docker startup and Render.com-style Docker deployment for the Vietnam stock dashboard.

Do not commit runtime secrets. Pass `MOZYFIN_API_KEY` through environment variables or a private host secret store.

## Current Runtime Shape

- The backend entry point is `python main.py --webui-only`.
- The web UI binds to `0.0.0.0` in container mode.
- The runtime port is read from `PORT`; when absent, it defaults to `8000`.
- The Vite frontend is built inside the Docker image and copied to `static/`.
- FastAPI serves `static/index.html` and `/assets/*` through the existing web UI flow.
- Live Vietnam data uses Mozyfin. Fixture mode is local testing only.
- The image installs `vnstock==4.0.4` for optional KBS snapshot/trades endpoints. KBS data is separate from Mozyfin daily close and does not replace `latest_price`.
- KBS snapshot/trade tape endpoints were validated in Docker, but public deployment should still be reviewed against vnstock/KBS license and provider behavior.

## Local Docker Build

Run from the repository root:

```powershell
cd D:\daily-dashboard\daily-stock-dashboard
docker build -t vietnam-dashboard:local .
```

## Local Docker Run

Live mode with the key already present in your PowerShell session:

```powershell
cd D:\daily-dashboard\daily-stock-dashboard
$env:MOZYFIN_API_KEY = "<YOUR_MOZYFIN_KEY>"

docker run --rm `
  -p 8000:8000 `
  -e PYTHONUTF8=1 `
  -e MARKET=VN `
  -e STOCK_LIST=FPT,VPB,MSB,SCS,ACV,ACB `
  -e PORT=8000 `
  -e MOZYFIN_API_KEY=$env:MOZYFIN_API_KEY `
  vietnam-dashboard:local
```

Dashboard:

```text
http://127.0.0.1:8000/vietnam
```

Health check:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/watchlist/health"
```

Expected live indicators:

```text
source: Mozyfin live
fixture_mode: false
```

KBS snapshot check:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/realtime?tickers=FPT,ACB,VCB" |
  ConvertTo-Json -Depth 8

Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/realtime/trades?symbol=FPT&limit=10" |
  ConvertTo-Json -Depth 8
```

KBS does not require extra credentials. Before public deployment, confirm vnstock/KBS license and usage terms fit the deployment.

Expected KBS indicators when vnstock/KBS is available:

```text
source: vnstock_kbs
status: ok
```

If KBS is unavailable, Mozyfin endpoints should still run or fail independently based on Mozyfin auth/config.

## Docker Compose

Set the key in PowerShell, then start the service:

```powershell
cd D:\daily-dashboard\daily-stock-dashboard
$env:MOZYFIN_API_KEY = "<YOUR_MOZYFIN_KEY>"
docker compose up --build
```

Stop it:

```powershell
docker compose down
```

The root `docker-compose.yml` does not enable `MOZYFIN_FIXTURE_DIR` by default.

## Local Fixture Mode

Fixture mode is only for deterministic local testing. It uses sample or stale fixture data and is not live market data.

Example one-off run:

```powershell
cd D:\daily-dashboard\daily-stock-dashboard

docker run --rm `
  -p 8000:8000 `
  -e PYTHONUTF8=1 `
  -e MARKET=VN `
  -e STOCK_LIST=FPT,VPB,MSB,SCS,ACV,ACB `
  -e PORT=8000 `
  -e MOZYFIN_FIXTURE_DIR=/app/tests/fixtures/mozyfin `
  -v ${PWD}\tests\fixtures\mozyfin:/app/tests/fixtures/mozyfin:ro `
  vietnam-dashboard:local
```

Expected fixture indicators:

```text
source: Mozyfin fixture
fixture_mode: true
```

## Render Deployment

Create a new Render Web Service using the repository and Docker runtime.

Recommended settings:

- Environment: Docker
- Dockerfile path: `docker/Dockerfile`
- Docker context: repository root
- Health check path: `/api/v1/stocks/vn/watchlist/health`

Required environment variables:

```text
MOZYFIN_API_KEY=<set in Render secret env>
PYTHONUTF8=1
MARKET=VN
STOCK_LIST=FPT,VPB,MSB,SCS,ACV,ACB
DATA_CACHE_DIR=/tmp/dsa-cache
```

Optional environment variable:

```text
PORT=8000
```

Render normally injects `PORT` automatically. Do not set `MOZYFIN_FIXTURE_DIR` on Render.

Use `DATA_CACHE_DIR=/tmp/dsa-cache` for an ephemeral Render cache when no persistent disk is mounted. If a persistent disk is mounted at `/app/data`, use `DATA_CACHE_DIR=/app/data/cache`; the Docker entrypoint creates and repairs that directory before the app drops to the non-root runtime user when the platform permits the entrypoint to start as root.

No vnstock-specific environment variables are required for the KBS snapshot/trades endpoints. The KBS layer is optional and does not write to Mozyfin daily OHLCV, quote/foreign, intraday, overview, or detail caches.

After deploy:

```text
https://<your-render-service>.onrender.com/vietnam
https://<your-render-service>.onrender.com/api/v1/stocks/vn/watchlist/health
https://<your-render-service>.onrender.com/api/v1/stocks/vn/realtime?tickers=FPT,ACB,VCB
https://<your-render-service>.onrender.com/api/v1/stocks/vn/realtime/trades?symbol=FPT&limit=10
```

Verify live mode:

```text
source: Mozyfin live
fixture_mode: false
```

## Common Render Issues

- App starts but Render cannot connect: confirm the backend binds to `0.0.0.0`, not `127.0.0.1`.
- Wrong port: confirm the service uses Render's `PORT` environment variable or local fallback `8000`.
- Missing API key: set `MOZYFIN_API_KEY` in Render environment variables, or the live Mozyfin path cannot authenticate.
- Build fails during frontend install/build: check `npm ci` and `npm run build` logs in the Render build output.
- Mozyfin CLI unavailable: the Docker image installs `mozyfin-cli`; if installation fails, live VN endpoints cannot fetch Mozyfin data.
- KBS endpoint returns unavailable: confirm `vnstock` installed in the image, for example by checking container logs or running `python -m pip show vnstock` inside the container.
- Source says fixture: `MOZYFIN_FIXTURE_DIR` is set; remove it for live data.
- Large watchlists time out: the full watchlist endpoint loads many tickers and can exceed free-tier host/request time limits.
- Public KBS usage: verify vnstock/KBS license and usage limits before exposing the endpoint on a public deployment.

## Local Port Cleanup

If port `8000` is occupied:

```powershell
netstat -ano | findstr :8000
Stop-Process -Id <PID> -Force
```

Check local Python or Node processes:

```powershell
Get-Process python,node -ErrorAction SilentlyContinue
```
