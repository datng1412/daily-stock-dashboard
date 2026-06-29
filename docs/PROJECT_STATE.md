# Project State

Last updated: 2026-06-29

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
- VN external provider strategy: `docs/VN_EXTERNAL_PROVIDER_STRATEGY.md`
- Future provider reference docs:
  - `docs/resources/realtime-data/`
  - `docs/resources/news-sources/`

## Vietnam Dashboard Current State

- SSI FastConnect is the strict primary VN market-data provider for supported fields.
- SSI owns daily OHLCV, chart candles, DailyStockPrice, reference/ceiling/floor, latest foreign-flow row, index list, index components when available, symbol metadata when available, intraday candles, realtime snapshot contract, and trade-tape contract.
- `latest_price` currently uses SSI DailyOhlc close as the canonical dashboard price when SSI daily rows are available.
- Phase 4.5B completed bounded SSI DailyStockPrice historical foreign-flow enrichment. DailyOhlc and DailyStockPrice are `strong`; IndexList, exact VN30 IndexComponents, and supported market metadata are `usable`; DailyIndex and IntradayOhlc are `partial`; true trade-tape history is `unavailable_parameter_unknown`; realtime snapshot is `optional_live_dependent`; unsupported fundamentals, statements, ratios, corporate actions, dividends/rights/splits, news, and macro are `external_provider_required`.
- Phase 4.5C live gate on 2026-06-29 confirmed DailyStockPrice 20-row recent foreign-flow history for FPT/HPG/SSI, re-confirmed VN30 IndexComponents with 30 rows, and kept `latest_price_source=SSI DailyOhlc`; VN30 DailyIndex remained partial because `index_value`/`exchange` were missing in the public row, exact `VNINDEX` stayed unresolved, and intraday/realtime/trade tape stayed optional unavailable.
- Mozyfin is disabled for VN dashboard runtime. Do not use it for news, social, OHLCV, chart, reference, foreign flow, index, metadata, intraday, realtime, trade tape, or fallback behavior.
- KBS is legacy optional only and disabled by default. It must require explicit legacy flags before any diagnostic use and must not silently replace SSI-owned data.
- VN news is disabled until a separate NewsProvider is implemented.
- The default VN watchlist is `FPT,VPB,MSB,SCS,ACV,ACB`.
- The `/vietnam` page is served by the built frontend through the FastAPI backend when running `python main.py --webui-only` or `python main.py --serve-only`.
- The dashboard uses neutral condition labels only and must not add trading instruction wording.
- Docs under `docs/resources/` are for future evaluation only and must not be treated as approved providers without explicit approval.

## External Provider State

- Phase 5.0A selected corporate actions/dividends/rights/splits as the first external VN domain to qualify.
- Phase 5.0B added only a disabled-by-default `CorporateActionsProvider` contract proof with normalized `events`/`items`, sanitized diagnostics, and no external provider calls.
- Phase 5.0C hardened that contract so `events` is canonical and legacy `items` is derived from it; provider access/legal qualification remains unresolved.
- Phase 4.5A records VNStocks and FiinGroup as `candidate_external_provider` with `needs_verification` only; neither provider is authorized, configured, called, or used as fallback.
- FiinGroup API Datafeed is the preferred automated candidate only after commercial access, rate-limit, storage, display, and redistribution terms are verified in writing.
- Provenance-required manual import is the fallback strategy; public VSDC/HOSE/HNX/SSC/company pages must not be scraped without explicit approval and verified terms.
- No external provider, credential, live adapter, fallback provider, scraping path, or production external-provider runtime is enabled yet.
- Financial statements, metadata fallback, ratios, news, macro, and explicit external VNINDEX remain deferred in the order recorded in `docs/VN_EXTERNAL_PROVIDER_STRATEGY.md`.
- The existing portfolio subsystem is user-owned and separate from VN external market-data provider selection.

## Data Semantics

- Daily close and chart candles come from SSI DailyOhlc.
- Reference, ceiling/floor, adjusted close if provided, matched volume/value, put-through volume/value, latest foreign buy/sell/net volume/value, and bounded recent 5D/20D foreign net volume summaries come from SSI DailyStockPrice.
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
| SSI DailyStockPrice | Recent-window fetch for quick facts and bounded 5D/20D foreign-flow summaries; chunking exists for wider validation |
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
