# SSI V3 Daily OHLC Lineage Audit

Status: `DAILY_OHLC_PROVIDER_BACKED` (offline call-path proof; live provider access not invoked).

## Scope

This audit traces only daily OHLCV fields: symbol, trading date, open, high,
low, close, volume, value, source, provider timestamp, and cache state. It
does not re-certify other market-data capabilities.

## Production call graph

| Public route | Handler | Service | Provider | Raw V3 operation | Cache |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v1/stocks/vn/chart` | `get_vietnam_chart` | `VietnamMarketService.build_chart` | `SsiRestProviderRouter.get_daily_ohlcv` | `SsiFastConnectV3Adapter.get_daily_ohlcv` -> `GET /api/v3/data/securitiesSummary` | process-local `_VN_CACHE`, V3 key |
| `GET /api/v1/stocks/vn/watchlist` | `get_vietnam_watchlist` | `VietnamMarketService._build_symbol` | same | same | same |
| `GET /api/v1/stocks/vn/company/{ticker}` | company-research service through the market service | same daily frame | same | same | same |

The V3 adapter requests `securitiesSummary` through the official SDK public
REST transport with `symbol`, `from`, `to`, `pageIndex`, and `pageSize`. It
normalizes `tradingDate`, `open`, `high`, `low`, `close`, `totalMatch`, and
`totalMatchValue` into the daily candle contract. The service converts only
those returned rows into a dataframe and derives TA/chart values from it.

## Runtime and provenance evidence

An injected V3-bound provider spy was used because the live acceptance guard
was not enabled. A force-refresh daily request invoked one daily-provider
operation; the adapter-level contract tests prove this operation issues the
`securitiesSummary` request and authenticates once per lazy lifecycle. The
controlled response propagated its two candle rows through the public chart
normalization without file reads or fallback.

`source`, `primary_source`, and `actual_source` are the truthful public SSI
provider-family labels. The V3-specific provenance is fixed by the sole V3
router and the `provider_version=v3` daily-cache key. Daily V3 summary rows
do not expose a provider event timestamp beyond their trading date; therefore
no provider timestamp is invented. Cache timestamps are local fetch/expiry
times, not provider timestamps.

## Cache behavior

| State | Result |
| --- | --- |
| Empty cache + V3 unavailable/empty result | chart: `status=unavailable` with empty candles; watchlist: `status=unavailable`, `rows_loaded=0`, and no fallback |
| Fresh V3-backed entry | cache hit; existing V3 rows are returned |
| Expired V3-backed entry + failed refresh | the prior V3-backed rows are returned as `stale`; no new unavailable value replaces them |
| Force refresh | invokes the V3 provider; it does not bypass a valid stale-preservation rule |

The cache is in-process memory only. There is no disk/Redis/SQLite daily-OHLC
cache, startup seed, fixture loader, or test-cache namespace shared with a
production process.

During this audit, a disabled-V3 image probe exposed a generic outer watchlist
exception path that omitted `status`; the response schema therefore supplied
its default `ok` despite zero rows. The fallback now sets `status=unavailable`
and a neutral reason explicitly. This is a status-truthfulness fix only: it
does not add, alter, or recover daily OHLC rows.

## Fixture classification

| ID | Fixture/source | Loaded by | Production reachable | Classification | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | `tests/fixtures/mozyfin/*_ohlcv.csv` | legacy `mozyfin_fetcher.py` tests | No | `TEST_ONLY_ISOLATED` | V3 daily/chart configuration accepts only `ssi`; the M2 provider manager has no legacy VN source; Docker excludes the fixture directory. |
| F2 | `local/mozyfin-quote-inspect/*_ohlcv_1h.csv` | manual legacy inspection only | No | `TEST_ONLY_ISOLATED` | not imported by the daily route or copied into the image. |
| F3 | injected dictionaries in `tests/test_ssi_v3_adapter.py` and service tests | deterministic tests | No | `TEST_ONLY_ISOLATED` | production modules have no imports from `tests` or test-fixture path literals. |
| F4 | frontend chart mocks | Vitest only | No | `TEST_ONLY_ISOLATED` | the chart consumes `stocksApi.getVietnamChart`; empty API points show the existing unavailable state. |

No `PRODUCTION_PRIMARY_FIXTURE`, `PRODUCTION_FALLBACK_FIXTURE`,
`CACHE_SEEDED_FIXTURE`, `FRONTEND_FALLBACK_FIXTURE`, `EMBEDDED_STATIC_OHLC`,
or `UNKNOWN_REACHABILITY` entries were found.

## Fixture comparison

No V3 runtime response was queried: the live guard remained off. Consequently
there is no claim of live FPT/SSI/VCB/SHS/ACV values or row-hash matches. The
repository fixture CSVs cover legacy Mozyfin symbols only (FPT, VPB, MSB, SCS,
ACV, and ACB), while the controlled V3 response test has no fixture-file read.
This is sufficient to rule out repository-fixture execution, but it is not a
live SSI data-parity claim.

## Regression coverage

`tests/test_vietnam_daily_ohlc_lineage.py` proves that a legacy fixture
environment variable cannot enter the SSI chart path, empty cache plus
unavailable V3 returns no candles and cannot yield a successful watchlist row,
stale reuse requires a prior provider-backed write, force refresh invokes the
provider, and core runtime modules contain no test-fixture path references.
Existing adapter coverage proves the exact V3 REST operation and its
normalization; existing chart tests cover the frontend no-data state.
