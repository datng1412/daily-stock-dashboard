# Vietstock Datafeed

## Purpose

Reference notes for evaluating Vietstock Datafeed as a possible Vietnam realtime, historical, financial, or news data resource.

## Source

- Official docs/source URL: TBD
- Auth/API status: unknown
- Implementation status: reference only
- Decision status: reference only
- Warning: do not implement without explicit user approval.

## Likely Useful Fields

- Realtime or delayed quote fields, if documented
- Historical OHLCV fields, if documented
- Foreign trading fields, if documented
- Financial statement and ratio fields, if documented
- Corporate action fields, if documented
- News/event fields, if documented

## Suitability

| Capability | Looks suitable? | Notes |
| --- | --- | --- |
| Realtime price | unknown | Timestamp and price semantics must be verified. |
| Historical OHLCV | unknown | Confirm adjustment and corporate action handling. |
| Foreign flow | unknown | Confirm units and trading-date alignment. |
| Financial data | unknown | Confirm coverage and update cadence. |
| News | unknown | Confirm article terms and metadata. |

## Semantics To Verify

- Timestamp timezone
- Realtime matched vs delayed vs OHLCV-derived price fields
- Corporate action adjustment behavior
- Market session behavior
- Rate limits and auth requirements

## Implementation Notes

- Do not add API calls without a plan.
- Do not scrape websites.
- Mozyfin remains the active provider unless changed by a decision record.

## Paste API docs here

Paste sanitized Vietstock Datafeed API docs, sample requests, and sample responses below this line.
