# Project State

Last updated: 2026-06-11

## Purpose

This document gives Codex and other agents enough context to resume project work without rediscovering the current Vietnam dashboard behavior.

## Repository Shape

- Backend entrypoint: `main.py`
- FastAPI app: `api/app.py`
- Stock endpoints: `api/v1/endpoints/stocks.py`
- Vietnam market service: `src/services/vietnam_market_service.py`
- Vietnam data adapter: `data_provider/mozyfin_fetcher.py`
- Vietnam KBS snapshot adapter: `data_provider/vnstock_realtime_fetcher.py`
- Web frontend: `apps/dsa-web/`
- Vietnam dashboard page: `apps/dsa-web/src/pages/VietnamDashboardPage.tsx`
- Vietnam time utilities: `apps/dsa-web/src/utils/vietnamTime.ts`
- Vietnam market phase utilities: `apps/dsa-web/src/utils/vietnamMarketPhase.ts`
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
- Current active daily/intraday provider remains Mozyfin.
- Optional vnstock/KBS snapshot support is implemented as a separate layer through `/api/v1/stocks/vn/realtime`.
- Optional vnstock/KBS trade tape support is implemented through `/api/v1/stocks/vn/realtime/trades`.
- KBS snapshot and trade tape data must not replace `latest_price`, Mozyfin daily OHLCV, or Mozyfin 1H intraday semantics.
- The dashboard displays Daily close, KBS snapshot, and Latest trade tape separately.
- The dashboard has a compact Data status panel, manual `Refresh KBS`, an `Auto-refresh KBS` toggle, split KBS refresh intervals, and VN market phase labels.
- News provider integration beyond current Mozyfin news behavior is not implemented.
- Docs under `docs/resources/` are for future evaluation only and must not be treated as approved providers.

## Data Semantics

- `latest_price` currently uses the latest daily OHLCV close when Mozyfin quote output does not expose a reliable realtime matched price.
- Mozyfin quote output is currently useful for foreign flow fields, but not treated as a reliable latest matched price source.
- Intraday pulse uses Mozyfin 1H OHLCV candles. It is not a realtime matched quote.
- KBS/vnstock snapshot is displayed separately from daily close and carries source, timestamp, age, stale, and unavailable/error status.
- KBS snapshot fields include `realtime_price`, `realtime_time`, `realtime_time_display`, `snapshot_price`, `snapshot_time`, `snapshot_time_display`, `snapshot_note`, `age_seconds`, `is_stale`, and `stale_reason`.
- KBS trade tape is separate from KBS snapshot and may exclude auction/ATC prints depending on provider output. Trade fields include `time`, `price`, `volume`, `match_type`, `id`, and `source`.
- Quote and foreign metadata rules remain unchanged.
- The frontend displays warnings for quote reliability, final daily candle uncertainty, adjustment uncertainty, and intraday not being a realtime quote.
- RSI14 uses Wilder/RMA smoothing, with a simple RSI debug comparison available in service output.
- Dates and times shown in the VN dashboard should use Vietnam time formatting.
- VN market phase labels are frontend-derived for normal weekdays in `Asia/Ho_Chi_Minh`: `Pre-open`, `ATO opening auction`, `Continuous morning`, `Lunch break`, `Continuous afternoon`, `ATC closing auction`, `Post-close`, `Closed`, and `Weekend / closed`. Holiday calendar support is not implemented and reports `holidayAware=false`.

## Cache State

Vietnam cache TTLs are process-local:

| Data type | TTL |
| --- | ---: |
| OHLCV daily | 300 seconds |
| Quote | 60 seconds |
| Intraday OHLCV | 60 seconds |
| News | 1800 seconds |
| KBS snapshot quotes | 10-15 seconds |
| KBS trade tape | 5 seconds |

`force_refresh=true` bypasses normal cache freshness checks for the requested watchlist call.

Frontend KBS auto-refresh is separate from Mozyfin refresh:

- KBS quotes: 10s / 15s / 30s, default 15s.
- Latest trade tape: 5s / 10s / 15s, default 10s.
- KBS refresh does not reload `/watchlist` or `/watchlist/overview`.

## Runtime Notes

- The Mozyfin CLI may be installed at `C:\Users\admin.DESKTOP-RFN8S67\AppData\Roaming\npm\mozyfin-cli.cmd`.
- That directory may not be in `PATH`; use the full path or prepend it to `PATH` in the launch shell.
- Do not print `MOZYFIN_API_KEY`. Report presence only.
- If direct Mozyfin CLI fails with `Missing API key`, do not assume application code is stale. Fix auth/session config first.
- If the dashboard shows `fixture_mode: true`, the first thing to check is whether an old backend process was started with `MOZYFIN_FIXTURE_DIR`.
- `vnstock==4.0.4` is a runtime dependency for Docker/Render KBS snapshot and trade tape support.
- vnstock/KBS requires no app credentials, but public deployment needs license, usage, and provider behavior review.
- KBS snapshot is polling/snapshot data and should not be described as guaranteed official exchange realtime.

## Verification Endpoints

- Health: `GET /api/v1/stocks/vn/watchlist/health`
- Watchlist: `GET /api/v1/stocks/vn/watchlist?tickers=FPT,VPB,MSB&force_refresh=true&include_intraday=true`
- KBS snapshot: `GET /api/v1/stocks/vn/realtime?tickers=FPT,ACB,VCB`
- KBS trade tape: `GET /api/v1/stocks/vn/realtime/trades?symbol=FPT&limit=100`

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
