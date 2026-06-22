# Observability

## Endpoint

GET /api/v1/stocks/vn/observability

## Sections

- SSI status
- KBS legacy status
- Mozyfin disabled status
- cache counters
- provider diagnostics

## Rules

- Disabled provider section must not contain active runtime counters from other providers.
- Provider unavailable is not cache error.
- Raw secrets must never appear.