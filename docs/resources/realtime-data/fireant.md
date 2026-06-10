# FireAnt

## Purpose

Reference notes for evaluating FireAnt as a possible Vietnam realtime market data resource.

## Source

- Official docs/source URL: TBD
- Auth/API status: unknown
- Implementation status: reference only
- Decision status: reference only
- Warning: do not implement without explicit user approval.

## Likely Useful Fields

- Realtime or delayed price fields, if documented
- Matched volume and trading value, if documented
- Bid/ask levels, if documented
- Foreign trading fields, if documented
- Company financial fields, if documented
- News or event tags, if documented

## Suitability

| Capability | Looks suitable? | Notes |
| --- | --- | --- |
| Realtime price | unknown | Timestamp and price semantics must be verified. |
| Historical OHLCV | unknown | Confirm candle availability and adjustment behavior. |
| Foreign flow | unknown | Confirm share vs value units and date alignment. |
| Financial data | unknown | Confirm coverage and update cadence. |
| News | unknown | Confirm source terms and article metadata. |

## Semantics To Verify

- Timestamp timezone
- Whether price fields are realtime matched, delayed, bid/ask, or OHLCV-derived
- Market session behavior
- Rate limits and auth requirements

## Implementation Notes

- Do not add API calls without a plan.
- Do not scrape websites.
- Mozyfin remains the active provider unless changed by a decision record.

## Paste API docs here

Paste sanitized FireAnt API docs, sample requests, and sample responses below this line.
