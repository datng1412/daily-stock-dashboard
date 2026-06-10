# Project State

Last updated: 2026-06-06

## Purpose

This document gives Codex and other agents enough context to resume project work without rediscovering the current Vietnam dashboard behavior.

## Repository Shape

- Backend entrypoint: `main.py`
- FastAPI app: `api/app.py`
- Stock endpoints: `api/v1/endpoints/stocks.py`
- Vietnam market service: `src/services/vietnam_market_service.py`
- Vietnam data adapter: `data_provider/mozyfin_fetcher.py`
- Web frontend: `apps/dsa-web/`
- Vietnam dashboard page: `apps/dsa-web/src/pages/VietnamDashboardPage.tsx`
- Vietnam time utilities: `apps/dsa-web/src/utils/vietnamTime.ts`
- VN setup reference: `README_VN.md`
- VN realtime quote architecture: `docs/VIETNAM_REALTIME_ARCHITECTURE.md`
- Future provider reference docs:
  - `docs/resources/realtime-data/`
  - `docs/resources/news-sources/`

## Vietnam Dashboard Current State

- The dashboard supports both Mozyfin live mode and fixture mode.
- Live mode source label is `Mozyfin live`.
- Fixture mode source label is `Mozyfin fixture`.
- Fixture mode is active when `MOZYFIN_FIXTURE_DIR` is set or when the Mozyfin fetcher has a valid fixture directory.
- The default VN watchlist is `FPT,VPB,MSB,SCS,ACV,ACB`.
- The `/vietnam` page is served by the built frontend through the FastAPI backend when running `python main.py --webui-only`.
- The dashboard does not generate buy or sell recommendations. It only displays neutral condition labels.
- Current active provider remains Mozyfin.
- Realtime provider integration beyond current Mozyfin behavior is not implemented.
- Realtime quote support is documented as a future separate optional layer; it must not replace `latest_price` or daily OHLCV semantics.
- News provider integration beyond current Mozyfin news behavior is not implemented.
- Docs under `docs/resources/` are for future evaluation only and must not be treated as approved providers.

## Data Semantics

- `latest_price` currently uses the latest daily OHLCV close when Mozyfin quote output does not expose a reliable realtime matched price.
- Mozyfin quote output is currently useful for foreign flow fields, but not treated as a reliable latest matched price source.
- Intraday pulse uses Mozyfin 1H OHLCV candles. It is not a realtime matched quote.
- Any future realtime matched price must be displayed separately from daily close and must carry source, timestamp, and realtime/delayed/stale status.
- The frontend displays warnings for quote reliability, final daily candle uncertainty, adjustment uncertainty, and intraday not being a realtime quote.
- RSI14 uses Wilder/RMA smoothing, with a simple RSI debug comparison available in service output.
- Dates and times shown in the VN dashboard should use Vietnam time formatting.

## Cache State

Vietnam cache TTLs are process-local:

| Data type | TTL |
| --- | ---: |
| OHLCV daily | 300 seconds |
| Quote | 60 seconds |
| Intraday OHLCV | 60 seconds |
| News | 1800 seconds |

`force_refresh=true` bypasses normal cache freshness checks for the requested watchlist call.

## Runtime Notes

- The Mozyfin CLI may be installed at `C:\Users\admin.DESKTOP-RFN8S67\AppData\Roaming\npm\mozyfin-cli.cmd`.
- That directory may not be in `PATH`; use the full path or prepend it to `PATH` in the launch shell.
- Do not print `MOZYFIN_API_KEY`. Report presence only.
- If direct Mozyfin CLI fails with `Missing API key`, do not assume application code is stale. Fix auth/session config first.
- If the dashboard shows `fixture_mode: true`, the first thing to check is whether an old backend process was started with `MOZYFIN_FIXTURE_DIR`.

## Verification Endpoints

- Health: `GET /api/v1/stocks/vn/watchlist/health`
- Watchlist: `GET /api/v1/stocks/vn/watchlist?tickers=FPT,VPB,MSB&force_refresh=true&include_intraday=true`

Expected live health:

```text
source: Mozyfin live
fixture_mode: false
```

Expected fixture health:

```text
source: Mozyfin fixture
fixture_mode: true
```
