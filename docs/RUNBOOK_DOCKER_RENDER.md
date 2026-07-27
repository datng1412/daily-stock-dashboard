# Docker and Render Runbook

> Current deployment guidance for the SSI FastConnect V3-only Vietnam runtime.
> Mozyfin is disabled for VN runtime, and KBS is legacy-only behind explicit
> development flags. See `docs/RUNBOOK_VN.md` and
> `docs/SSI_FASTCONNECT_INTEGRATION.md` for provider-specific operations.

This runbook covers local Docker startup and Render.com-style Docker deployment for the Vietnam stock dashboard.

Do not commit runtime secrets. Pass `SSI_V3_API_KEY` and
`SSI_V3_API_SECRET` through environment variables or a private host secret
store.

## Current Runtime Shape

- The backend entry point is `python main.py --webui-only`.
- The web UI binds to `0.0.0.0` in container mode.
- The runtime port is read from `PORT`; when absent, it defaults to `8000`.
- The final image runs as non-root user `dsa` (`1000:1000`) with `HOME=/home/dsa`.
- `/home/dsa/.longbridge`, `/app/data/cache`, `/app/logs`, and `/app/reports` are created and owned during the image build; the entrypoint fails clearly if a runtime mount makes one unwritable.
- Startup readiness uses the local, provider-independent `http://127.0.0.1:$PORT/api/health` endpoint and the same resolved port used by Uvicorn.
- Pre-bind startup does not import the optional LiteLLM analyzer path. Logs emit one bounded `fastapi_startup stage=...` sequence from `FASTAPI_THREAD_ENTERED` through `UVICORN_SOCKET_READY`; a timeout reports `last_lifecycle_stage` so app import, required local initialization, and optional background scheduling can be distinguished.
- The Vite frontend is built inside the Docker image and copied to `static/`.
- FastAPI serves `static/index.html` and `/assets/*` through the existing web UI flow.
- Vietnam market-data routes use the official `ssi-sdk==3.0.5` V3 REST and
  WebSocket implementation only. REST is lazy and does not block health.
- `SSI_V3_REST_ENABLED=true`, `SSI_V3_API_KEY`, and `SSI_V3_API_SECRET`
  enable REST. `SSI_V3_CLIENT_ID` is optional for Market Data REST.
- Streaming is a separate opt-in. A streaming authorization or connection
  failure does not disable REST foreign-flow history.
- No Mozyfin, VNStocks, FiinGroup, KBS, fixture, or fabricated fallback may
  populate SSI-owned Vietnam market data.

## Local Docker Build

Run from the repository root:

```powershell
cd D:\stock-dashboard
docker build -f docker/Dockerfile -t vietnam-dashboard:local .
```

## Local Docker Run

Live mode with the SSI V3 secrets already present in your PowerShell session:

```powershell
cd D:\stock-dashboard

docker run --rm `
  -p 8000:8000 `
  -e PYTHONUTF8=1 `
  -e MARKET=VN `
  -e STOCK_LIST=FPT,VPB,MSB,SCS,ACV,ACB `
  -e PORT=8000 `
  -e SSI_V3_REST_ENABLED=true `
  -e SSI_V3_API_KEY=$env:SSI_V3_API_KEY `
  -e SSI_V3_API_SECRET=$env:SSI_V3_API_SECRET `
  vietnam-dashboard:local
```

Dashboard:

```text
http://127.0.0.1:8000/vietnam
```

Health check:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/health"
```

Expected live indicators:

```text
source: SSI FastConnect V3
provider_version: v3
```

Bounded foreign-flow check:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/stocks/vn/foreign-flow/symbol/FPT?limit=20" |
  ConvertTo-Json -Depth 8
```

An unavailable provider response must remain typed and must not activate
another provider or synthesize rows.

## Docker Compose

Make the SSI V3 variables available through the private Compose environment,
then start the service:

```powershell
cd D:\stock-dashboard
docker compose up --build
```

Stop it:

```powershell
docker compose down
```

The Compose configuration does not enable a Vietnam fallback provider.

## Deterministic Tests

Legacy provider fixtures are test-only and are excluded from the production
Vietnam runtime. Do not mount a fixture directory into a live container and do
not present fixture rows as SSI data.

## Render Deployment

Create a new Render Web Service using the repository and Docker runtime.

Recommended settings:

- Environment: Docker
- Dockerfile path: `docker/Dockerfile`
- Docker context: repository root
- Health check path: `/api/health`

Required environment variables:

```text
SSI_V3_REST_ENABLED=true
SSI_V3_API_KEY=<set in Render secret env>
SSI_V3_API_SECRET=<set in Render secret env>
PYTHONUTF8=1
MARKET=VN
STOCK_LIST=FPT,VPB,MSB,SCS,ACV,ACB
DATA_CACHE_DIR=/tmp/dsa-cache
```

Optional environment variable:

```text
SSI_V3_CLIENT_ID=
SSI_V3_API_URL=https://api.ssi.com.vn/api/v3
SSI_V3_REQUEST_TIMEOUT=10
PORT=8000
```

Render normally injects `PORT` automatically. Do not set a legacy VN fixture
or fallback provider on Render.

Use `DATA_CACHE_DIR=/tmp/dsa-cache` for an ephemeral Render cache when no persistent disk is mounted. If a persistent disk is mounted at `/app/data`, use `DATA_CACHE_DIR=/app/data/cache`. The final image starts as non-root `dsa`; any mounted host or persistent-disk path must therefore already permit UID/GID `1000:1000` to write. The entrypoint validates access but does not elevate privileges or rewrite mount ownership.

The repository has no checked-in `render.yaml`, so secret values and the
deployed service's actual variable inventory cannot be verified from source.
The names above match `.env.example`, `src/config.py`, and the production
Docker dependency set.

After deploy:

```text
https://<your-render-service>.onrender.com/vietnam
https://<your-render-service>.onrender.com/api/health
https://<your-render-service>.onrender.com/api/v1/stocks/vn/foreign-flow/symbol/FPT?limit=20
```

Verify live mode:

```text
source: SSI FastConnect V3
provider_version: v3
```

## Common Render Issues

- App starts but Render cannot connect: confirm the backend binds to `0.0.0.0`, not `127.0.0.1`.
- Wrong port: confirm the service uses Render's `PORT` environment variable or local fallback `8000`.
- Missing credentials: set `SSI_V3_REST_ENABLED=true`,
  `SSI_V3_API_KEY`, and `SSI_V3_API_SECRET` in Render's secret environment.
  Client ID remains optional for Market Data REST.
- Build fails during frontend install/build: check `npm ci` and `npm run build` logs in the Render build output.
- DNS/TLS/auth troubleshooting: use the bounded, secret-safe
  `scripts/diagnose_vn_foreign_flow_connectivity.py --live` utility once.
  Do not disable TLS verification or print provider payloads.
- Provider unavailable: retain the typed unavailable response. Do not enable
  Mozyfin, KBS, VNStocks, FiinGroup, or fixture fallback for SSI-owned fields.
- Large watchlists time out: the full watchlist endpoint loads many tickers and can exceed free-tier host/request time limits.

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
