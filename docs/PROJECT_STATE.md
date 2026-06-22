# Project State

Last updated: 2026-06-22

## Purpose

This document gives Codex and other agents enough context to resume project work without rediscovering the current Vietnam dashboard behavior. The detailed source-of-truth roadmap remains `docs/VN_DASHBOARD_ROADMAP.md`.

## Repository Shape

- Backend entrypoint: `main.py`
- FastAPI app: `api/app.py`
- Stock endpoints: `api/v1/endpoints/stocks.py`
- Vietnam market service: `src/services/vietnam_market_service.py`
- SSI FastConnect provider: `data_provider/ssi_fastconnect_fetcher.py`
- Legacy Mozyfin provider code: `data_provider/mozyfin_fetcher.py`
- Legacy KBS/vnstock adapter: `data_provider/vnstock_realtime_fetcher.py`
- Web frontend: `apps/dsa-web/`
- Vietnam dashboard page: `apps/dsa-web/src/pages/VietnamDashboardPage.tsx`
- Vietnam company research page: `apps/dsa-web/src/pages/VietnamCompanyResearchPage.tsx`
- Vietnam time utilities: `apps/dsa-web/src/utils/vietnamTime.ts`
- Vietnam market phase utilities: `apps/dsa-web/src/utils/vietnamMarketPhase.ts`
- VN roadmap: `docs/VN_DASHBOARD_ROADMAP.md`
- SSI integration notes: `docs/SSI_FASTCONNECT_INTEGRATION.md`
- Future provider reference docs:
  - `docs/resources/realtime-data/`
  - `docs/resources/news-sources/`

## Vietnam Dashboard Current State

- SSI FastConnect is the strict primary VN market-data provider for supported fields.
- SSI owns daily OHLCV, chart candles, DailyStockPrice, reference/ceiling/floor, latest foreign-flow row, index list, index components when available, symbol metadata when available, intraday candles, realtime snapshot contract, and trade-tape contract.
- `latest_price` currently uses SSI DailyOhlc close as the canonical dashboard price when SSI daily rows are available.
- Mozyfin is disabled for VN dashboard runtime. Do not use it for news, social, OHLCV, chart, reference, foreign flow, index, metadata, intraday, realtime, trade tape, or fallback behavior.
- KBS is legacy optional only and disabled by default. It must require explicit legacy flags before any diagnostic use and must not silently replace SSI-owned data.
- VN news is disabled until a separate NewsProvider is implemented.
- The default VN watchlist is `FPT,VPB,MSB,SCS,ACV,ACB`.
- The `/vietnam` page is served by the built frontend through the FastAPI backend when running `python main.py --webui-only` or `python main.py --serve-only`.
- The dashboard uses neutral condition labels only and must not add trading instruction wording.
- Docs under `docs/resources/` are for future evaluation only and must not be treated as approved providers without explicit approval.

## Data Semantics

- Daily close and chart candles come from SSI DailyOhlc.
- Reference, ceiling/floor, adjusted close if provided, matched volume/value, put-through volume/value, and latest foreign buy/sell/net volume/value come from SSI DailyStockPrice.
- Internal MA/RSI/Bollinger indicators are derived from SSI DailyOhlc data.
- SSI IntradayOhlc is a compact intraday candle source. It is not a realtime matched quote and is separate from official daily close.
- SSI realtime snapshot is a separate realtime contract. It must not overwrite `latest_price` or SSI DailyOhlc close.
- SSI trade tape is a separate trade-list contract. It must not be used as official daily close.
- Company metadata from SSI Securities/SecuritiesDetails may be limited to symbol/exchange/market/source; optional company name, issuer, security type, lot size, listed shares, and listed date can remain null.
- Corporate actions, financial statements, ratios, dividends/rights/splits, and macro data require explicit external providers. Do not infer those events from price gaps.
- Dates and times shown in the VN dashboard should use Vietnam time formatting.
- RSI14 uses Wilder/RMA smoothing.

## Live Section Contract

- Missing object data should be represented as `null`.
- Missing list data should be represented as `[]`.
- Public live-section statuses should stay simple: `ok`, `unavailable`, or `disabled`.
- Technical provider details such as attempted endpoints, HTTP status, stale dates, retryability, and raw provider error summaries belong in diagnostics/logs, not primary metric fields.
- When no usable SSI realtime snapshot exists, `realtime_snapshot` should be `null`.
- When intraday is unavailable, stale, or mismatched, `intraday_pulse` should be `null` and `intraday_candles` should be `[]`.
- When no trade rows exist, trade rows should be `[]`.
- UI availability must depend on section status plus null/empty checks, not on units metadata or cached diagnostic fields.
- The UI should not render fake metric rows with `-` or `Unavailable` as if they were values for unavailable live sections.

## Cache State

Vietnam cache TTLs are process-local and should be interpreted per source block:

| Data type | Current behavior |
| --- | --- |
| SSI DailyOhlc | Backend cache/TTL, strict source for daily rows and chart |
| SSI DailyStockPrice | Recent-window fetch for quick facts; chunking exists for wider validation |
| SSI IntradayOhlc | Backend cache/TTL; unavailable/stale states should not affect daily row validity |
| SSI realtime snapshot | Separate realtime contract; unavailable state should not affect daily row validity |
| SSI trade tape | Separate trade-tape contract; unavailable state should not affect daily row validity |
| News | Disabled until a separate provider is implemented |

`force_refresh=true` bypasses normal cache freshness checks for the requested watchlist call. Provider 404/unavailable is not the same as cache failure.

## Runtime Notes

- SSI credentials must come from local environment variables or a secret manager only.
- Do not print SSI `consumerID`, `consumerSecret`, access tokens, account IDs, auth headers, or raw auth responses.
- Do not print legacy Mozyfin secrets if present in a developer environment.
- Do not add FC Trading, order placement, account actions, cash transfer, stock transfer, or portfolio trading actions.
- Mozyfin CLI/key/fixture configuration is not required for normal VN dashboard runtime.
- KBS/vnstock is not required for normal VN dashboard runtime.
- News/social is disabled until a separate NewsProvider exists.

## Verification Endpoints

- Health: `GET /api/v1/stocks/vn/watchlist/health`
- Watchlist: `GET /api/v1/stocks/vn/watchlist?tickers=FPT,VPB,MSB&force_refresh=true&include_intraday=true`
- Chart: `GET /api/v1/stocks/vn/chart?symbol=FPT&range=6M`
- Realtime snapshot contract: `GET /api/v1/stocks/vn/realtime?tickers=FPT,ACB,VCB`
- Trade tape contract: `GET /api/v1/stocks/vn/realtime/trades?symbol=FPT&limit=100`
- Company snapshot: `GET /api/v1/stocks/vn/company/FPT?force_refresh=true`
- Index list: `GET /api/v1/stocks/vn/index-list?market=HOSE`
- Index components: `GET /api/v1/stocks/vn/index-components?index_code=VN30`

Expected strict SSI watchlist behavior:

```text
source: SSI
actual_source: SSI
fallback_used: false
news_status.status: disabled
```

Optional SSI intraday/realtime/trade-tape sections may be unavailable while daily SSI rows remain OK.
