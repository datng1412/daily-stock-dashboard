# Review Checklist

Use this checklist for code review, docs review, and Codex handoff review.

## General

- Scope matches the user request.
- No unrelated refactors or formatting churn.
- No secrets, API keys, tokens, credentials, or private values are printed or committed.
- Existing user changes are preserved.
- No commit was created unless explicitly requested.
- New or changed commands match actual repo paths.

## Documentation

- Docs describe current behavior, not desired future behavior.
- Commands are runnable on Windows PowerShell when documented as PowerShell.
- Live and fixture modes are clearly separated.
- Any assumptions are stated.
- Cross references point to existing files.

## Backend/API

- Endpoint behavior is backward compatible unless the task explicitly changes API contract.
- Error paths do not crash the whole dashboard when one ticker fails.
- Cache behavior is explicit when investigating stale data.
- `force_refresh=true` behavior is verified when data freshness matters.
- Existing schema compatibility and source/finality/freshness fields are preserved; do not require obsolete fields on every route.

## Vietnam Dashboard

- SSI V3 is the sole production VN market-data route; offline test injection is separate from live evidence.
- `latest_price` follows validated daily history or the existing explicitly partial newer-DailyStockPrice degradation.
- Quote output is not presented as reliable realtime matched price unless source semantics change.
- Delayed sparse 1m chart candles, compact intraday context, quotes, and trade events retain their distinct source/cadence contracts.
- RSI14 uses Wilder/RMA.
- Cache TTLs match the specific service/configuration; source-session freshness remains separate from transport/cache age.
- Completed flow and alert inputs exclude provisional current flow and quarantined anomalies; missing values stay null and valid explicit zero stays zero.
- Labels remain neutral condition tags only.
- No buy/sell recommendations are introduced.
- VN visible times use Vietnam time formatting.

## Frontend

- UI text does not overstate data freshness.
- Browser cache or old build is ruled out when debugging stale UI.
- The frontend is verified against the backend port actually serving the page.
- If frontend code changed, run `npm run lint` and `npm run build` from `apps/dsa-web`.

## Runtime Debugging

- List backend Python processes with PID, command line, start time.
- Confirm the port serving the dashboard.
- Check env status without printing secrets.
- Use a bounded SSI diagnostic only when authorized. A local TCP permission failure does not prove provider failure.
- Automated server checks own the exact child, enforce readiness/request/global deadlines, and stop it in `finally`; never await natural web-server exit.
- Compare direct CLI dates, API dates, and UI dates.

## Final Answer

- Changed files listed.
- Verification listed.
- Assumptions listed.
- Remaining risks or unverified items listed.
