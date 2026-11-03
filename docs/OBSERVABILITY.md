# VN Observability

## Endpoint Purpose

`GET /api/v1/stocks/vn/observability` exposes runtime/provider/cache status for the VN dashboard. It is a diagnostics endpoint, not a user-facing market-data source.

Use it to answer:

- Is SSI configured and reachable for core daily data?
- Are optional SSI intraday/realtime/trade-tape sections unavailable, disabled, or healthy?
- Are legacy providers disabled as expected?
- Are cache/runtime counters behaving separately from provider availability?

## Expected Sections

The exact response shape may evolve, but it should keep these responsibilities separate:

- `ssi_core`: SSI authentication/core daily provider status.
- `ssi_intraday`: SSI IntradayOhlc status.
- `ssi_realtime`: SSI realtime snapshot status.
- `ssi_trade_tape`: SSI trade-tape status.
- `mozyfin`: disabled legacy block in strict VN runtime.
- `kbs`: legacy optional block, disabled unless explicit legacy flags are enabled.
- `dashboard_runtime`: generic request/cache/single-flight counters.
- Cache/source diagnostics by source block.

## Provider Statuses

Live-provider statuses should stay:

- `ok`
- `unavailable`
- `disabled`

Future module status `not_implemented` is allowed for product modules such as news, financials, and events, but observability should not treat it as a live-provider health status unless the endpoint contract explicitly adds such a section.

## Cache Counters

Cache counters should be scoped to the source block:

- DailyOhlc cache state.
- DailyStockPrice cache state.
- Intraday cache state.
- Realtime cache state.
- Trade-tape cache state.

Provider unavailable is not the same as cache error. A 404 from an optional SSI realtime endpoint should not imply daily SSI cache failure.

## Disabled Provider Behavior

When Mozyfin is disabled for VN runtime:

- The Mozyfin block should be minimal.
- It should not contain active SSI runtime counters.
- It should not imply Mozyfin fallback is available.

When KBS is disabled:

- KBS should be clearly legacy optional.
- KBS should not silently replace SSI realtime or trade-tape contracts.

## Diagnostics Rules

Allowed diagnostics:

- Provider/source name.
- Endpoint label or sanitized path label.
- HTTP status.
- Retryable flag.
- Stale date mismatch.
- Sanitized provider error summary.
- Cache age or fetched time.

Forbidden diagnostics:

- Credentials.
- Tokens.
- Auth headers.
- Account IDs.
- Raw auth responses.
- Full raw provider payloads containing private data.

## Known Current Caveat

Handoff snapshots showed SSI realtime and trade tape can be unavailable in observability. This is expected until Phase 4 confirms endpoint names, entitlements, response shapes, and retry/backoff behavior.

## Review Checklist

- Daily SSI availability is readable separately from optional live-section failures.
- Disabled Mozyfin/KBS state is explicit.
- Provider unavailable and cache errors are not conflated.
- No secret-bearing fields appear.
- Technical details remain diagnostics, not primary UI copy.

## Inherited analysis report diagnostics

The inherited analysis pipeline correlates an async task with its `task_id` and a synchronous run with its `query_id` through `trace_id`. Provider attempts capture the operation, source, success, timing, sanitized errors, fallback, and record count where available. Diagnostics are best-effort and remain separate from provider selection, analysis completion, and history persistence. See [diagnostic assembly](../src/services/run_diagnostics.py).

`GET /api/v1/history/{record_id}/diagnostics` accepts a history ID or query ID and returns a summary and sanitized `copy_text`. Missing historical evidence stays `unknown`. Treat report status and data diagnostics as separate signals. The [history route](../api/v1/endpoints/history.py) and [report diagnostics component](../apps/dsa-web/src/components/report/ReportDiagnostics.tsx) own the API and UI boundaries.

The Phase 0–3 records are available in Git history for [0e6a00af](https://github.com/datng1412/daily-stock-dashboard/tree/0e6a00af9033b05e2e0946727cc23126e79cc7b3/docs/).
