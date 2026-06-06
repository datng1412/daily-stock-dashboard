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
- API response still exposes `source` and `fixture_mode`.

## Vietnam Dashboard

- `Mozyfin live` and `Mozyfin fixture` modes remain explicit.
- `MOZYFIN_FIXTURE_DIR` is not set for live validation.
- `latest_price` semantics remain honest: daily OHLCV close is used when quote lacks a reliable latest matched price.
- Quote output is not presented as reliable realtime matched price unless source semantics change.
- Intraday pulse is described as 1H OHLCV, not realtime quote.
- RSI14 uses Wilder/RMA.
- Cache TTLs remain documented:
  - OHLCV daily: 300 seconds
  - Quote: 60 seconds
  - Intraday OHLCV: 60 seconds
  - News: 1800 seconds
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
- Run direct Mozyfin CLI checks when live data is in question.
- Compare direct CLI dates, API dates, and UI dates.

## Final Answer

- Changed files listed.
- Verification listed.
- Assumptions listed.
- Remaining risks or unverified items listed.
