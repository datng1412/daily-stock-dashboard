# Test Strategy

## Required before milestone commit

Backend:
- tests/test_vietnam_observability.py
- tests/test_vietnam_market_service_no_mozyfin.py
- tests/test_vietnam_market_service_realtime.py
- tests/test_vietnam_market_service_intraday.py

Frontend:
Run from apps/dsa-web:
- npm run build
- VietnamDashboardPage.test.tsx
- VietnamCompanyResearchPage

## Contract tests protect

- No Mozyfin in strict VN runtime.
- Realtime snapshot null when unavailable.
- Intraday pulse null when stale.
- Trade tape empty list when unavailable.
- News disabled.
- KBS disabled by default.

## UI tests protect

- No fake metric rows.
- No endpoint dump in primary UI.
- Disabled news copy.
- Profile partial copy.