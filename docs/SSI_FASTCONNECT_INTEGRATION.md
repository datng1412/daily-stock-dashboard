# SSI FastConnect Integration

## Scope

This document covers the Vietnam dashboard SSI FastConnect transition foundation.

Current phase:

* FC Data only.
* Provider skeleton and secure configuration.
* AccessToken authentication handling.
* REST normalization for selected market-data APIs.
* Strict SSI ownership for supported Vietnam REST market data.
* No Mozyfin or KBS fallback for SSI-owned daily OHLCV, chart OHLCV, DailyStockPrice, reference/ceiling/floor, foreign flow, DailyIndex, realtime snapshot, or trade tape.
* Mocked tests and an optional local smoke script.
* Dashboard detail rendering for SSI DailyStockPrice fields when SSI provides them.
* SSI IntradayOhlc candles for compact watchlist/company intraday pulse.
* SSI realtime snapshot and trade-tape contracts for dashboard/company realtime blocks.
* SSI live API plus backend cache/TTL; local DB market-data storage is deferred.

Out of scope:

* FC Trading.
* Order placement.
* Account actions.
* Cash transfer.
* Stock transfer.
* Portfolio trading actions.
* UI source switcher or comparison card.
* Provider comparison endpoint.
* Buy/sell/hold or recommendation wording.

## Provider roles

SSI FastConnect is the preferred future official market-data provider for:

* Daily OHLCV.
* Daily stock price.
* Reference, ceiling, and floor.
* Foreign flow.
* Daily index.
* Index components.
* Symbol metadata.
* Intraday OHLCV.
* Realtime streaming later.

Mozyfin is disabled for VN dashboard runtime. It must not be used for VN news/social, OHLCV, chart, reference, foreign-flow, index, metadata, intraday, or fallback behavior. Future news should be implemented through a separate NewsProvider contract.

KBS is disabled by default and retained only as an explicit legacy development provider:

* `VN_ALLOW_LEGACY_KBS_PROVIDER=true`
* `KBS_ENABLED=true`

KBS must not be used as silent fallback for SSI realtime snapshot, SSI trade tape, or any SSI-owned market-data field.

SSI is now the strict owner for supported VN REST market data. If SSI is disabled, credentials are missing, or a request fails, SSI-owned sections return an unavailable state instead of falling back to Mozyfin or KBS.

External providers are still required for BCTC/KQKD, financial statements, financial ratios, corporate action event lists, dividends, rights, splits, and macro context such as Fed, oil, USD, and gold. These domains are outside current SSI REST market-data ownership.

## Provider capability matrix

| Capability | Owner | Current implementation status | Dashboard rule |
| --- | --- | --- | --- |
| AccessToken | SSI FastConnect Data REST | Implemented | Authenticate with env/secret-manager credentials only |
| Securities | SSI FastConnect Data REST | Implemented and wired as same-provider metadata fallback | Use for symbol metadata when SecuritiesDetails does not return a usable row |
| SecuritiesDetails | SSI FastConnect Data REST | Implemented and wired | Use for exchange, security type, listed info, and issuer/name fields |
| IndexComponents | SSI FastConnect Data REST | Provider/service/API coverage added; live availability needs SSI endpoint/permission confirmation | Use for index membership only when SSI returns component rows |
| IndexList | SSI FastConnect Data REST | Implemented and exposed through backend API | Discover official index identifiers before DailyIndex calls |
| DailyOhlc | SSI FastConnect Data REST | Implemented and wired | Use for watchlist daily close, chart candles, and internal MA/RSI/Bollinger calculations |
| IntradayOhlc | SSI FastConnect Data REST | Implemented and wired for compact intraday pulse | Use as strict VN intraday candle source; do not treat as realtime matched quote |
| DailyIndex | SSI FastConnect Data REST | Implemented with 29-day chunking | Use for daily index value/change/breadth/liquidity when wired |
| DailyStockPrice | SSI FastConnect Data REST | Implemented and wired | Use for reference, ceiling/floor, adjusted close, matched, put-through, and foreign flow |
| Realtime snapshot and trade tape | SSI FastConnect Data/streaming | Provider/service/API/UI contract added; live endpoint names and permissions need confirmation | Show SSI unavailable when no usable rows return; no KBS fallback |
| Realtime best bid/ask, matched data, foreign room, index stream, realtime bars/OHLC | SSI streaming/protocol hardening later | Partially covered by realtime contract; streaming not fully validated | Keep semantics explicit and unavailable until SSI behavior is proven stable |
| News | Future NewsProvider | Disabled/not implemented | Do not call Mozyfin; keep separate from SSI-owned market data |
| BCTC/KQKD, financial statements, ratios | External provider | Unsupported/future provider | Do not infer fundamentals from price fields |
| Corporate actions, dividends, rights, splits | External provider | Stub/unavailable | Do not infer events from reference or adjusted-close gaps |
| Macro/Fed/oil/USD/gold | External provider | Unsupported/future provider | Keep outside FC Data market-price ownership |

Decision rule:

```text
If data is official market price/volume/index/symbol and SSI has endpoint: use SSI.
If data is derived indicator from price/volume: calculate internally from SSI.
If data is realtime snapshot or trade tape and SSI is unavailable: show unavailable, do not silently fallback.
If data is news/fundamentals/corporate actions/macro: use external provider.
If SSI-owned data is unavailable: show unavailable, do not silently fallback.
```

## Configuration

SSI is disabled by default.

```env
SSI_FASTCONNECT_ENABLED=false
SSI_FASTCONNECT_BASE_URL=https://fc-data.ssi.com.vn/api/v2/Market
SSI_FASTCONNECT_CONSUMER_ID=
SSI_FASTCONNECT_CONSUMER_SECRET=
SSI_FASTCONNECT_TIMEOUT_SECONDS=10
SSI_FASTCONNECT_CACHE_TTL_SECONDS=300
SSI_FASTCONNECT_TOKEN_TTL_SECONDS=900
SSI_FASTCONNECT_INTRADAY_ENABLED=true
SSI_FASTCONNECT_REALTIME_ENABLED=true
SSI_FASTCONNECT_TRADE_TAPE_ENABLED=true

VN_DAILY_DATA_PROVIDER=ssi
VN_CHART_DATA_PROVIDER=ssi
VN_DAILY_STOCK_PRICE_PROVIDER=ssi
VN_INDEX_DATA_PROVIDER=ssi
VN_INTRADAY_DATA_PROVIDER=ssi
VN_REALTIME_DATA_PROVIDER=ssi
VN_TRADE_TAPE_PROVIDER=ssi
VN_PROVIDER_COMPARISON_ENABLED=false
MOZYFIN_ENABLED=false
MOZYFIN_NEWS_ENABLED=false
VN_NEWS_PROVIDER=disabled
VN_ALLOW_LEGACY_MOZYFIN_PROVIDER=false
KBS_ENABLED=false
VN_ALLOW_LEGACY_KBS_PROVIDER=false
```

Keep the base URL configurable because SSI documentation may reference another versioned path such as `/v2.0/Market`.

Credentials must only come from local environment variables or a secret manager. Never commit real values.

The provider variables are intentionally strict for supported VN REST market data. Public env parsing accepts `ssi` for daily, chart, DailyStockPrice, and index provider values; invalid values fall back to `ssi`. `VN_PROVIDER_COMPARISON_ENABLED` remains `false`, and no provider comparison endpoint or card is exposed in this phase.

## Security rules

* Do not hardcode SSI credentials.
* Do not print tokens, consumer IDs, consumer secrets, private keys, account IDs, or authorization headers.
* Do not include real credentials in tests, docs, fixtures, examples, changelog, logs, or errors.
* Missing credentials must return a clean unavailable state and must not crash the app.
* AccessToken responses are cached in memory, but tokens are not returned to dashboard payloads.
* Request failures are normalized to secret-free unavailable objects.

## Implemented APIs

The foundation provider supports:

* `POST /Market/AccessToken`
* `GET /Market/IndexList`
* `GET /Market/IndexComponents`
* `GET /Market/Securities`
* `GET /Market/SecuritiesDetails`
* `GET /Market/DailyOhlc`
* `GET /Market/IntradayOhlc`
* `GET /Market/DailyStockPrice`
* `GET /Market/DailyIndex`

The current implementation lives in:

```text
data_provider/ssi_fastconnect_fetcher.py
```

## Dashboard integration

Strict daily/chart behavior:

* `VN_DAILY_DATA_PROVIDER=ssi` uses SSI `DailyOhlc` for the watchlist daily OHLCV dataframe.
* `VN_CHART_DATA_PROVIDER=ssi` uses SSI `DailyOhlc` for `/api/v1/stocks/vn/chart`.
* If SSI DailyOhlc is unavailable, watchlist rows and chart responses return `status: "unavailable"` with `fallback_used: false`.
* Mozyfin is not called as OHLCV or chart fallback for SSI-owned data.
* Chart responses include `source`, `primary_source`, `actual_source`, `fallback_used`, `fallback_reason`, `points`, and a compatibility `candles` alias.
* Watchlist rows include the same provider metadata. `latest_price` and `daily_close` use the SSI daily close when SSI supplied the daily OHLCV row, and `latest_price_source` is tagged as `SSI`.
* Vite local development proxies `/api` to `http://127.0.0.1:8000` by default. Set `VITE_API_PROXY_TARGET=http://127.0.0.1:<port>` when testing a backend on a non-default port.
* Primary row-level `Data unavailable` UI state is tied to required SSI DailyOhlc validity and SSI DailyOhlc cache errors. Optional quote, metadata, corporate-action, news, intraday, SSI realtime, SSI trade-tape, and SSI index-component states are caveats or separate source statuses, not fatal SSI daily-data failures.
* Dashboard status copy should say `Daily source SSI`, `SSI realtime unavailable`, `SSI trade tape unavailable`, and `News disabled` for those specific states. Concise primary banners should state that daily SSI data is still available; attempted endpoints, HTTP status, and other sanitized technical details belong in diagnostics.

Strict DailyStockPrice behavior:

* `VN_DAILY_STOCK_PRICE_PROVIDER=ssi` owns reference, ceiling, floor, adjusted close, matched volume/value, put-through volume/value, and foreign buy/sell/net volume/value fields.
* If SSI DailyStockPrice is unavailable, these fields return unavailable/null states.
* Mozyfin quote and KBS reference are not used as fallback for SSI-owned reference or foreign-flow fields.
* The enrichment does not mutate OHLCV rows.
* The enrichment does not infer corporate actions.
* Source labels are explicit through `reference_source` and `foreign_flow_source`.
* The selected ticker detail surfaces SSI reference, ceiling/floor, foreign net volume/value, matched volume/value, put-through volume/value, and adjusted close when present.
* Successful watchlist enrichments set `daily_stock_price.status` to `ok` and expose the same values as optional `ssi_*` convenience fields for UI compatibility.
* Legacy Mozyfin foreign-history caveats such as stale foreign date and insufficient 5D/20D foreign rows are suppressed when SSI DailyStockPrice is available.

Strict IntradayOhlc behavior:

* `VN_INTRADAY_DATA_PROVIDER=ssi` and `SSI_FASTCONNECT_INTRADAY_ENABLED=true` route VN intraday candles through SSI FastConnect `IntradayOhlc`.
* Watchlist rows expose `intraday_source=SSI` and `intraday_status.status=ok` when SSI returns normalized candles.
* If SSI IntradayOhlc is disabled, fails, or returns no candles, the intraday block returns `disabled` or `unavailable` while the SSI DailyOhlc row remains valid when daily data is present.
* The service validates latest intraday candle date against the latest SSI daily trading date. If the dates mismatch, intraday is marked unavailable and no intraday pulse labels are derived from stale candles.
* Returned candle cadence is detected from timestamps when possible and labeled as provider-returned granularity. `intraday_requested_timeframe` records the request hint, while `intraday_actual_granularity` and `intraday_actual_granularity_seconds` record detected returned cadence. The compatibility field `intraday_timeframe` must be read as the requested timeframe, not the actual candle interval.
* The dashboard should use neutral labels such as latest intraday close and intraday change instead of assuming the requested timeframe describes the returned rows.
* Intraday candles are not realtime matched quotes and must remain separate from SSI realtime snapshot, SSI trade tape, and official SSI DailyOhlc close.
* Mozyfin and KBS are not used as intraday candle fallback providers.

SSI request parameters:

* DailyOhlc uses `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, and `ascending`.
* IntradayOhlc uses `symbol`, `fromDate`, `toDate`, `pageIndex`, `pageSize`, `ascending`, and an optional `timeFrame` value for the requested dashboard timeframe.
* DailyStockPrice uses `symbol`, `market`, documented `Fromdate`, `Todate`, `pageIndex`, and `pageSize`.
* DailyIndex uses `indexID`, documented `Fromdate`, `Todate`, `pageIndex`, and `pageSize`.
* The provider retries alternate SSI casing such as `Symbol`, `Market`, `fromDate`, `toDate`, and `IndexId` only when the first same-provider response returns no meaningful rows.
* Status/message-only SSI responses are diagnostic responses, not data rows; they are not counted as normalized DailyStockPrice or DailyIndex records.

SSI range limits:

* DailyOhlc currently supports the direct 1Y query used by the chart path.
* DailyStockPrice and DailyIndex reject broad ranges with a max-range message, so the provider splits those endpoints into 29-calendar-day inclusive windows.
* Chunked DailyStockPrice windows use `symbol`, `market`, `Fromdate`, `Todate`, `pageIndex=1`, and `pageSize=1000`.
* Chunked DailyIndex windows use `indexID`, `Fromdate`, `Todate`, `pageIndex=1`, and `pageSize=1000`.
* Chunked responses are normalized, status/message-only bodies are filtered, duplicate dates are removed, and rows are returned in ascending chronological order.
* Pagination is bounded by `totalRecord`, empty pages, and a safe max-page guard.
* Selected ticker quick facts request only a recent 29-day DailyStockPrice window; the local smoke script opts into pacing when validating full-year chunked counts.

Strict DailyIndex behavior:

* `VN_INDEX_DATA_PROVIDER=ssi` enables SSI DailyIndex fetches for future market breadth work.
* If SSI DailyIndex is unavailable, index data returns unavailable.
* No dashboard card consumes SSI DailyIndex yet.

Strict index metadata behavior:

* `/api/v1/stocks/vn/index-list` exposes SSI IndexList rows with `source=SSI` and `fallback_used=false`.
* `/api/v1/stocks/vn/index-components?index_code=...` exposes SSI IndexComponents rows when SSI returns them, or a clean unavailable state when SSI returns no meaningful component rows.
* The web dashboard calls both endpoints for compact diagnostics and keeps the section visible even when VN30 components are unavailable from SSI.
* IndexComponents requests use `indexID`, `pageIndex=1`, and `pageSize=1000`, and retry safe same-provider parameter variants only when SSI returns no meaningful rows.
* Status/message-only SSI responses are not counted as index component rows.
* SSI provider error/status payloads for IndexComponents are parsed with case-insensitive `code`, `errorCode`, `status`, and `Status` handling and must become sanitized unavailable responses, not backend 500s.
* Mozyfin and KBS are not used as fallback providers for SSI-owned index list, index component, or daily index data.

Company research Phase 1 behavior:

* `/api/v1/stocks/vn/company/{ticker}` exposes a company research snapshot contract for one VN ticker.
* The endpoint reuses the SSI-backed watchlist row for profile, price, trading stats, foreign flow, and derived technical blocks.
* Source coverage is explicit for Daily OHLCV, DailyStockPrice, Profile, News, Financials, and Corporate actions.
* News, financials, and corporate-action events remain `not_implemented` placeholders in this phase.
* The endpoint does not scrape Mozyfin, call FC Trading, infer corporate actions, or use Mozyfin/KBS fallback for SSI-owned market-data blocks.

## Normalized outputs

`DailyOhlc` rows normalize to:

```json
{
  "date": "2026-06-17",
  "open": 123.4,
  "high": 125.0,
  "low": 122.8,
  "close": 124.6,
  "volume": 1234567,
  "value": 123456789000,
  "source": "SSI"
}
```

`IntradayOhlc` rows normalize to:

```json
{
  "timestamp": 1781161200,
  "date_time": "2026-06-17T10:00:00+07:00",
  "open": 123.4,
  "high": 125.0,
  "low": 122.8,
  "close": 124.6,
  "volume": 1234567,
  "ticker": "FPT",
  "source": "SSI"
}
```

`DailyStockPrice` rows normalize reference, ceiling, floor, OHLC, adjusted close, matched volume/value, put-through volume/value, total volume/value, and foreign buy/sell/net volume/value fields. Mapping is tolerant of common SSI field variants such as `TradingDate`, `RefPrice`, `ReferencePrice`, `BasicPrice`, `Ceiling`, `Floor`, `MatchedVolume`, `PutThroughValue`, `ForeignBuyVol`, `ForeignSellVol`, and `BuyForeignQuantity`/`SellForeignQuantity`.

`DailyIndex` rows normalize index value, change, change percent, total volume/value, matched volume/value, put-through volume/value, breadth fields, trading session, and exchange when present.

`IndexList` rows normalize `index_id`, `index_code`, `index_name`, `exchange`, `market`, and `source`.

`IndexComponents` rows normalize `index_code`, `symbol`, `exchange`, `market`, `weight`, `name`, and `source` when SSI returns component rows. Missing optional component fields remain null.

`Securities` and `SecuritiesDetails` rows normalize symbol metadata such as symbol, exchange, market, security type, names, issuer, lot size, listed shares, and listed date when present.

VN watchlist/detail responses now expose SSI metadata through `symbol_metadata` plus compatibility fields such as `company_name`, `security_type`, `metadata_source`, `issuer`, `lot_size`, `listed_shares`, and `listed_date`. The service queries `SecuritiesDetails` first and may use `Securities` only as an SSI same-provider metadata fallback. Mozyfin is not used for SSI-owned symbol metadata.

## Unavailable behavior

Disabled provider:

```json
{
  "status": "unavailable",
  "source": "SSI",
  "reason": "SSI FastConnect disabled"
}
```

Missing credentials:

```json
{
  "status": "unavailable",
  "source": "SSI",
  "reason": "SSI FastConnect credentials missing"
}
```

Network, auth, HTTP, provider-status, or JSON parsing failure:

```json
{
  "status": "unavailable",
  "source": "SSI",
  "reason": "SSI FastConnect request failed"
}
```

## Optional smoke check

The smoke script is local-only and not required in CI:

```powershell
python scripts\ssi_fastconnect_smoke.py
```

For endpoint diagnostics, the smoke script also supports a safe probe mode:

```powershell
python scripts\ssi_fastconnect_smoke.py --probe
```

Probe mode tests both documented FC Data base URL shapes and prints only endpoint names, base URL labels, parameter keys, HTTP status, top-level response keys, status/message metadata, counts, and row keys. The normal smoke path validates full-year chunked DailyStockPrice and DailyIndex counts and prints chunk counts plus first/last dates. It prints only safe status and row counts. It does not print tokens, credentials, headers, or full provider bodies.

## Known limitations / operational notes

* SSI metadata coverage may be limited. A live metadata row can be `status=ok` while only returning symbol, exchange, market, and source; optional name, issuer, type, lot-size, listed-shares, and listed-date fields may remain null.
* Live IndexList validation works in the current SSI environment, but `market=HOSE` can still return cross-market-looking index codes such as `HNX30`, `HNXINDEX`, and `HNXUPCOMINDEX`; use SSI-returned rows instead of assuming the request market filter is strict.
* Live IndexComponents validation for `VN30`, with and without `market=HOSE`, returned a clean unavailable state in the current SSI environment. This may be endpoint permission, endpoint path, SSI data availability, or undocumented parameter shape. Do not hardcode VN30 members or fallback to Mozyfin/KBS.
* Quote fields are not currently a reliable REST latest-price source. Watchlist payloads can have `quote_cache=missing`, `quote=null`, `quote_price_date=null`, and `quote_price_raw_field=null`; `latest_price` uses SSI DailyOhlc close when SSI daily rows are available.
* DailyStockPrice and DailyIndex require <=29/30-day request windows. Provider chunking is available for smoke/debug/internal validation, but broad automatic UI requests should be avoided unless deliberately designed.
* Local market-data DB storage is deferred. Current mode remains SSI live API plus backend cache/TTL.
* SSI IntradayOhlc is implemented for compact dashboard/company pulse, but live availability still depends on SSI endpoint permission and response shape. If unavailable, show the SSI intraday state without fallback.
* SSI IntradayOhlc live rows may be stale relative to SSI DailyOhlc or have a different cadence than the requested dashboard timeframe. Keep daily rows OK, mark stale intraday unavailable, and surface the sanitized date/granularity diagnostics.
* SSI realtime snapshot and trade-tape contracts are wired through the existing realtime endpoints and dashboard/company UI blocks. Live SSI endpoint names, permissions, and row shapes still require validation; unavailable results should remain neutral SSI unavailable states.
* SSI realtime/trade-tape unavailable states should include sanitized attempted-endpoint diagnostics when possible. Do not print or return tokens, credentials, auth headers, signed URLs, or raw provider bodies.
* Observability keeps `mozyfin` as a minimal disabled legacy block. Generic VN request/cache/single-flight counters live under `dashboard_runtime`; do not interpret those counters as Mozyfin activity. SSI status is split into explicit `ssi_core`, `ssi_intraday`, `ssi_realtime`, and `ssi_trade_tape` blocks.
* VN news/social is disabled because Mozyfin free-tier API access is no longer available for the dashboard. Future news should use a separate NewsProvider contract, not Mozyfin scraping.
* Strict VN runtime must not construct `MozyfinFetcher` for watchlist, company, realtime, index, corporate-action, or observability paths while Mozyfin legacy flags are disabled. Corporate actions remain explicit unavailable placeholders until a verified external event provider is configured.
* News rendering is independent from SSI index, quote, metadata, finality, intraday, and realtime caveats. If a future NewsProvider supplies rows, the selected ticker news block should remain visible and clearly separate from SSI market data.
* Keep DailyOhlc and DailyStockPrice labels separate: daily close/chart candles come from SSI DailyOhlc; reference/limits/foreign/matched/put-through fields come from SSI DailyStockPrice.
* Keep primary cache labels scoped to SSI DailyOhlc. Quote/news/intraday/realtime cache or availability issues should remain in diagnostics or caveats so they do not imply official daily market data is unavailable.

## Current limitations

* SSI FastConnect credentials are not bundled; with default placeholder config, SSI-owned sections are unavailable.
* Mozyfin is disabled for VN dashboard runtime; news/social returns disabled or `not_implemented`.
* SSI realtime snapshot and trade tape remain separate from daily close and intraday candles.
* KBS is disabled by default and legacy-only behind explicit development flags.
* Local DB market-data storage is deferred while current call volume remains low and backend cache/TTL is sufficient.
* No UI source switcher or comparison card exists.
* No provider comparison endpoint exists in this strict-default phase.
* SSI streaming/protocol hardening remains a later phase; this phase wires the dashboard contract and safe unavailable states.
* IndexComponents provider/service/API coverage exists, but live component rows remain unconfirmed under the current SSI environment.
* Fundamentals, corporate actions, dividends, rights, splits, and macro data require external providers.
* FC Trading remains out of scope.

## Next phase

Use the roadmap priority order: continue with SSI realtime/streaming protocol hardening, then external fundamentals/corporate-actions/news provider work. Do not introduce FC Trading or Mozyfin/KBS fallback for SSI-owned market data in any phase.
