# FiinTrade

## Purpose

Reference notes for evaluating FiinTrade as a possible Vietnam realtime market data and analytics resource.

## Source

- Official docs/source URL: TBD
- Auth/API status: unknown
- Implementation status: reference only
- Decision status: reference only
- Warning: do not implement without explicit user approval.

## Likely Useful Fields

- Realtime or delayed market data fields, if documented
- Historical OHLCV fields, if documented
- Foreign flow fields, if documented
- Financial statement or ratio fields, if documented
- Sector/industry classification fields, if documented
- News/event fields, if documented

## Suitability

| Capability | Looks suitable? | Notes |
| --- | --- | --- |
| Realtime price | unknown | Timestamp and price semantics must be verified. |
| Historical OHLCV | unknown | Confirm history depth and adjustment rules. |
| Foreign flow | unknown | Confirm units and whether values are same-day or historical. |
| Financial data | unknown | Likely candidate, but docs and terms must be verified. |
| News | unknown | Confirm availability and source rights. |

## Semantics To Verify

- Timestamp timezone
- Realtime vs delayed price semantics
- Financial data period/date semantics
- Market session behavior
- Rate limits and auth requirements

## Implementation Notes

- Do not add API calls without a plan.
- Do not scrape websites.
- Mozyfin remains the active provider unless changed by a decision record.

## Paste API docs here

Paste sanitized FiinTrade API docs, sample requests, and sample responses below this line.
