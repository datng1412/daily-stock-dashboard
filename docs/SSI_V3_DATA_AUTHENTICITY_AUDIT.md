# SSI V3 Runtime Market-Data Authenticity Audit

Status: `DATA_AUTHENTICITY_REMEDIATED`

Date: 2026-07-23  
Branch: `ssi-v3-migrate`  
Audited HEAD: `fd57c6a05244592715274e770342019a0e6fd41f`

## Scope and rule

This audit traced Vietnam market data from SSI V3 REST/WebSocket input through
normalization, caches, services, public API schemas, and the React dashboard.
Production values are accepted only when they are direct SSI V3 fields,
deterministic calculations from complete SSI V3 fields, explicitly stale SSI
V3 snapshots retaining source time, or clearly labeled product configuration.
Provider failure, empty data, and missing fields must remain unavailable,
empty, or null. Local fetch/receipt time must never replace provider event time.

## Production output map

| Public feature | Service | V3 provider input | Cache | Derived fields | Consumer |
| --- | --- | --- | --- | --- | --- |
| Watchlist/latest price/TA | `VietnamMarketService.build_watchlist` | daily OHLC, exact-symbol metadata, daily summary | daily/metadata/summary | change, RSI/MA, liquidity | VN dashboard |
| Daily chart | `build_chart` | daily OHLC | daily | indicators and S/R only | Lightweight Charts |
| Historical/current intraday | `build_intraday_chart` | V3 one-minute OHLC | separate historical/current | timestamps and indicators | Lightweight Charts |
| Foreign flow | `VietnamForeignFlowService` | summary gross fields | symbol/batch/VN30 | complete-pair net/windows | Foreign Flow workspace |
| VN30 membership | index service | securities-by-index | component cache | normalize/dedupe/sort | dashboard/foreign flow |
| Index list/state | index service | V3 index list/summary | index caches | identity normalization | index panels |
| Realtime/trades/order book | streaming manager/service | retained `trade.*`/`quote.*` events | bounded/persisted | compatibility aliases | live panels |
| Room/session/index pulse | streaming manager/service | retained V3 events | separate caches | field normalization | diagnostics/live panels |
| Observability | services/lifecycle | provider result/status | status snapshots | counts/ages | status panels |

## Suspicious-finding inventory

Repository-wide searches produced many keyword matches. Forty material
occurrence groups were call-path inspected and classified:

| Classification | Count | Result |
| --- | ---: | --- |
| `PROVIDER_BACKED` | 8 | retained |
| `DETERMINISTIC_DERIVED` | 5 | retained |
| `STALE_PROVIDER_CACHE` | 3 | retained |
| `LEGITIMATE_CONFIGURATION_CONSTANT` | 5 | retained |
| `EXPLICIT_USER_PRESET` | 4 | retained |
| `UI_PLACEHOLDER` | 2 | retained |
| `TEST_ONLY_FIXTURE` | 3 | retained; runtime activation blocked |
| `DOCUMENTATION_EXAMPLE` | 1 | retained |
| `RUNTIME_SYNTHETIC_MARKET_DATA` | 2 | remediated |
| `FALLBACK_MASKING_PROVIDER_FAILURE` | 1 | remediated |
| `STALE_RELABELED_AS_FRESH` | 0 | none found |
| `NULL_COERCED_TO_ZERO` | 3 | remediated |
| `HARDCODED_PROVIDER_UNIVERSE` | 1 | remediated |
| `GENERATED_PROVIDER_TIMESTAMP` | 1 | remediated |
| `RUNTIME_TEST_FIXTURE_LEAK` | 1 | remediated |
| `CONTRACT_UNCLEAR` | 0 | none remaining |

### Material finding matrix

| ID | File/method | Previous behavior | Reachable | Classification | Evidence/action |
| --- | --- | --- | --- | --- | --- |
| P1 | `ssi_v3_adapter.py` daily/summary | OHLC, matched values, foreign gross | yes | `PROVIDER_BACKED` | Direct V3 normalization retained. |
| P2 | V3 index methods | index rows/membership | yes | `PROVIDER_BACKED` | V3 index filters retained. |
| P3 | `ssi_v3_streaming.py` trade/quote | trades and sparse ladders | yes | `PROVIDER_BACKED` | Incomplete trades rejected; absent levels remain absent. |
| P4 | room/session/index streams | provider scalars | yes | `PROVIDER_BACKED` | No generated rows found. |
| D1 | V3 foreign normalization | net volume/value | yes | `DETERMINISTIC_DERIVED` | Complete gross pairs only. |
| D2 | Vietnam market service | change, RSI/MA, liquidity, S/R | yes | `DETERMINISTIC_DERIVED` | Provider candles only; missing inputs remain null. |
| D3 | foreign-flow service | sums, breadth, rankings | yes | `DETERMINISTIC_DERIVED` | Provider-returned sessions only. |
| C1 | stream snapshot caches | persisted last-known rows | yes | `STALE_PROVIDER_CACHE` | Original stream time retained; persisted rows forced stale. |
| C2 | daily/intraday caches | last successful result | yes | `STALE_PROVIDER_CACHE` | Fetch time separate; stale status explicit. |
| K1 | timeouts/TTLs/pages/retries | fixed limits | yes | `LEGITIMATE_CONFIGURATION_CONSTANT` | Not market observations. |
| K2 | board scales/price limits | exchange policy | yes | `LEGITIMATE_CONFIGURATION_CONSTANT` | Applied only after provider board. |
| U1 | route default/local sector buckets | fixed symbols | yes | `EXPLICIT_USER_PRESET` | Presented as local configuration, not membership. |
| U2 | `—`, loading/unavailable copy | visual placeholders | yes | `UI_PLACEHOLDER` | Retained. |
| T1 | tests and fixture files | sample rows | no | `TEST_ONLY_FIXTURE` | No production import from `tests/`/fixtures. |
| X1 | `VietnamMarketService` exchange map | six symbols plus unknown=`HOSE` | yes | `RUNTIME_SYNTHETIC_MARKET_DATA` | Removed; exact-symbol V3 metadata owns board. |
| X2 | OHLC frame/watch card | fixed `VNINDEX.VN` for every stock | yes | `RUNTIME_SYNTHETIC_MARKET_DATA` | Removed; remains null unless provider-backed. |
| F1 | unavailable rows/UI | missing data labeled `Watch` | yes | `FALLBACK_MASKING_PROVIDER_FAILURE` | Now `Data unavailable`. |
| N1 | liquidity helper | missing history became score zero | yes | `NULL_COERCED_TO_ZERO` | Missing score is null. |
| N2 | liquidity summary | missing scores averaged as zero | yes | `NULL_COERCED_TO_ZERO` | Finite scores only; all-missing is `—`. |
| N3 | foreign summary | all-missing net became zero | yes | `NULL_COERCED_TO_ZERO` | All-missing is null; real zero remains zero. |
| H1 | `vietnamWatchlist.ts` | bundled list named VN30 | shipped module | `HARDCODED_PROVIDER_UNIVERSE` | Removed; active VN30 is SSI-only. |
| G1 | realtime compatibility mapping | missing event time used local fetch time | yes | `GENERATED_PROVIDER_TIMESTAMP` | Provider-time fields remain null; fetch time separate. |
| L1 | `DataFetcherManager` VN branch and `docker/Dockerfile` | old flags could activate Mozyfin fixture; image bundled Mozyfin CLI | yes | `RUNTIME_TEST_FIXTURE_LEAK` | Legacy VN manager activates no provider and production image no longer installs the CLI. |

## Provider-to-public provenance

| Public field | Raw V3 source | Transformation | Cache behavior | Result |
| --- | --- | --- | --- | --- |
| symbol/exchange | exact-symbol security row | uppercase/board normalization | metadata cache | no guessed board |
| provider date/time | REST date/WebSocket event time | validation only | original retained | nullable provider time |
| OHLC/volume/value | `securitiesSummary` matched fields | numeric normalization | daily cache | SSI DailyOhlc compatibility label |
| latest price | latest real daily close | selection only | daily cache | `SSI DailyOhlc` |
| foreign gross | summary gross fields | board scale once | foreign caches | SSI DailyStockPrice compatibility label |
| foreign net | complete buy/sell pair | buy minus sell | derived row cached | null when incomplete |
| index/value | V3 index endpoints/events | identity normalization | index cache | SSI V3 |
| VN30 membership | V3 securities-by-index | normalize/dedupe/sort | component cache | no bundled fallback |
| trade/ladder | V3 trade/quote event | strict/sparse normalization | bounded/persisted | SSI V3 WebSocket |
| freshness | provider/cache state | sanitized classification | fetch/receipt separate | live/stale/unavailable |

## Failure, cache, and realtime behavior

- Authentication, entitlement, timeout, network, HTTP, malformed, empty, and
  symbol-not-found paths return unavailable/empty/null with sanitized reasons.
- No daily dates, intraday minutes, foreign-flow dates, trades, or ladder levels
  are generated. Negative cache entries contain no rows.
- Persisted realtime rows retain provider event time and are always stale. A
  cache read changes age/status only.
- No trade exists until a valid V3 trade event with provider time, price, and
  volume is received. Quote event time may be null; receipt time is separate.
- Heartbeats, reconnects, resubscriptions, and market-closed classification
  create no market events.
- Unknown exchange receives no guessed foreign scale. Null gross foreign values
  stay null, explicit zero stays zero, and net requires complete gross pairs.

## Frontend behavior

The UI no longer renders an up/green movement icon for missing change, a fixed
exchange/index badge, `0/100` liquidity, or a zero foreign aggregate when all
inputs are missing. VN30 membership is fetched from SSI IndexComponents only.

## Validation

- SSI/authenticity backend subset: `204 passed`.
- Legacy manager authenticity guards: `3 passed`.
- TypeScript: passed.
- Vite production build: passed.
- Vitest: started but returned no result and timed out after 120 seconds on the
  Windows host; no pass is claimed.
- Literal full-suite command: collection blocked by unreadable `.pytest_cache`
  (`WinError 5`).
- Full suite with `--ignore=.pytest_cache`: `3075 passed, 4 skipped, 69 failed`.
  Changed SSI/authenticity suites are green; failures remain in unrelated or
  obsolete configuration/localization/logging/storage/WebUI/Mozyfin-era areas.
- Safe live probe: `G/NOT_RUN`, zero authentication and zero data operations.
  The guard was disabled and Client ID was absent; no credential value printed.

The Python 3.11 production image rebuilt successfully without `mozyfin-cli` or
`ssi-fc-data`. A bounded container start reached `/api/health` with HTTP 200,
remained running, and stopped cleanly. No live market-data claim is made from
this audit.

## Outcome

All production-reachable synthetic values identified by this audit were
removed. The V3-only authenticity contract remains valid, subject to the
recorded live, Vitest, and repository-baseline validation limits.
No V2 fallback, external provider, fixture output, stage, commit, or push was
introduced.
