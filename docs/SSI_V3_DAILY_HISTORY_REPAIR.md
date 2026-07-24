# SSI V3 Daily History Repair

Date: 2026-07-23

Outcome: `DAILY_HISTORY_PAGINATION_REPAIRED`

## Problem and root cause

FPT daily history ended on `2026-03-05` with exactly 252 sessions while SSI V3 DailyStockPrice and streaming data were dated `2026-07-23`. The daily adapter requested a long range and could stop after a bounded ascending provider result. Trimming that normalized result retained the oldest sessions, which then entered the process-local cache as successful history.

The missing recent period was present when the same V3 `securitiesSummary` contract was retrieved through bounded recent windows. This rules out provider capability, fixture lineage, and date-field normalization as the root cause.

## Repair contract

- Split long ranges into bounded recent-first windows.
- Exhaust every page declared by the provider before accepting a window.
- Record sanitized page row counts and date bounds.
- Deduplicate by trading date deterministically.
- Sort by trading date ascending and retain the newest requested sessions.
- Do not synthesize sessions or forward-fill candles.
- Treat incomplete or materially stale history as partial/unavailable.
- Do not cache incomplete history as a complete success or replace a valid cache entry with it.
- Calculate RSI, MA, Bollinger, and other daily-history indicators only from history that passes freshness validation.

The public legacy labels `SSI DailyOhlc` and `SSI DailyStockPrice` remain readable, while payload provenance identifies `provider_version=v3`, `endpoint=securitiesSummary`, and `adapter=SsiFastConnectV3Adapter`.

## Canonical-price rule

Fresh V3 daily OHLC remains canonical. A daily max date materially behind a newer SSI DailyStockPrice date is not canonical and cannot produce successful technical status. In that degradation case, the row is partial and the newer DailyStockPrice close may be exposed as the explicitly labeled canonical SSI provider value. Stale history may remain visible only with stale provenance; no external or legacy fallback is used.

## Adjacent findings

- Missing foreign-flow values remain null; they are not coerced to zero. The guarded live acceptance classified all six latest gross/net foreign fields for FPT (and the other four symbols) as explicit provider-backed zero values, not absent/null aliases, so no foreign scale or derivation change was made.
- Persisted streaming snapshots and trade rows return stale/after-hours status rather than plain live `ok`.
- `latest_trade_timestamp` is the maximum returned provider timestamp, independent of local receive order.
- The narrow intraday validation defect was `interval=<dashboard timeframe>` sent to the V3 one-minute contract. The service now sends `interval=1m` and separately reports requested versus observed cadence.

## Bounded live acceptance

The acceptance ran in a fresh Python process with no service-cache reuse. It required both the CLI live flag and `SSI_V3_LIVE_ACCEPTANCE_ENABLED=true`, used one authenticated adapter lifecycle, and emitted no credentials or raw payloads.

| Symbol | Operations | Pages/windows | Provider rows | Normalized rows | Date bounds | DailyStockPrice date | Match | Freshness | Latest OHLC |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| FPT | 2 | 3 | 357 | 260 | 2025-07-09 to 2026-07-23 | 2026-07-23 | yes | fresh | 65,000 / 65,700 / 64,200 / 64,700 |
| SSI | 2 | 3 | 357 | 260 | 2025-07-09 to 2026-07-23 | 2026-07-23 | yes | fresh | 22,550 / 24,000 / 22,200 / 23,550 |
| VCB | 2 | 3 | 357 | 260 | 2025-07-09 to 2026-07-23 | 2026-07-23 | yes | fresh | 54,100 / 54,900 / 52,600 / 54,000 |
| SHS | 2 | 3 | 357 | 260 | 2025-07-09 to 2026-07-23 | 2026-07-23 | yes | fresh | 15,200 / 16,500 / 13,900 / 16,100 |
| ACV | 2 | 3 | 357 | 260 | 2025-07-09 to 2026-07-23 | 2026-07-23 | yes | fresh | 39,100 / 39,100 / 38,000 / 39,100 |

`Operations` counts one daily-history and one DailyStockPrice operation per symbol. `Latest OHLC` is open/high/low/close in provider units. Cache source was `provider` for every row.

## Validation

- V3 daily, service freshness, cache, intraday, streaming persistence, and realtime focused gate: 170 passed.
- Additional profile metadata, intraday-chart, foreign-flow API, Docker entrypoint, and legacy Mozyfin-era group: 95 passed, 2 skipped, 31 legacy Mozyfin-era failures. The failures assert removed Mozyfin routing, old generic source labels, and pre-V3 cache/provider behavior; they were not changed or masked in this phase.
- Production image `stock-dashboard:ssi-v3-m2-2` built successfully.
- A fresh container with an isolated empty cache reached health `ok`; public FPT 1Y chart returned 251 points from `2025-07-22` through `2026-07-23`, latest close `64,700`, `provider_version=v3`, and `endpoint=securitiesSummary`. Its forced-refresh watchlist row was `ok`, dated `2026-07-23`, used `latest_price_source=SSI DailyOhlc`, and populated technical indicators.

## Rollback

Revert the M2.2 adapter, freshness/arbitration, streaming truthfulness, intraday parameter, schema, test, script, and documentation changes together. Rolling back restores the known stale-history risk; do not compensate with fixtures, V2, Mozyfin, or an external fallback.
