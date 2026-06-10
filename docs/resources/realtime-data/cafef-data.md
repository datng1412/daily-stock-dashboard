# CafeF Data

## Purpose

Reference notes for evaluating CafeF data resources as possible Vietnam market data, financial data, or news references.

## Source

- Official docs/source URL: TBD
- Auth/API status: unknown
- Implementation status: reference only
- Decision status: reference only
- Warning: do not implement without explicit user approval.

## Likely Useful Fields

- Price and volume fields, if documented
- Historical OHLCV fields, if documented
- Financial statement and ratio fields, if documented
- Corporate event fields, if documented
- News fields, if documented

## Suitability

| Capability | Looks suitable? | Notes |
| --- | --- | --- |
| Realtime price | unknown | Timestamp and price semantics must be verified. |
| Historical OHLCV | unknown | Confirm coverage and adjustment behavior. |
| Foreign flow | unknown | Confirm availability, units, and date alignment. |
| Financial data | unknown | Confirm structured field availability. |
| News | unknown | Confirm source terms and article metadata. |

## Semantics To Verify

- Timestamp timezone
- Realtime vs delayed vs historical price semantics
- Financial period semantics
- Market session behavior
- Rate limits and auth requirements

## Implementation Notes

- Do not add API calls without a plan.
- Do not scrape websites.
- Mozyfin remains the active provider unless changed by a decision record.

## Paste API docs here

Paste sanitized CafeF data docs, sample requests, and sample responses below this line.
