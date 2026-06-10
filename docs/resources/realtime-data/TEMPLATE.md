# <Provider Name>

## Reference Status

- Implementation status: reference only
- Decision status: reference only / candidate / approved / rejected
- Warning: do not implement without explicit user approval.

## Source

- Provider name:
- Official docs/source URL:
- Base URL:
- Auth/API status: unknown / public / paid / private

## Authentication

- Auth method:
- Required env vars:
- Secret handling notes:

## Endpoints

| Endpoint | Method | Purpose | Notes |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

## Rate Limits

- Documented limits:
- Burst behavior:
- Retry/backoff guidance:

## Sample Request

```text
Sanitized sample request goes here.
```

## Sanitized Sample Response

```json
{
  "sample": "Paste sanitized sample response here"
}
```

## Field Mapping

| Provider field | DSA field | Type | Notes |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

## Likely Useful Fields

- Realtime price:
- Historical OHLCV:
- Foreign flow:
- Financial data:
- News:

## Suitability

| Capability | Suitability | Notes |
| --- | --- | --- |
| Realtime price | unknown | Verify semantics first. |
| Historical OHLCV | unknown | Verify availability and adjustment behavior. |
| Foreign flow | unknown | Verify unit and date alignment. |
| Financial data | unknown | Verify coverage and refresh cadence. |
| News | unknown | Verify source and terms. |

## Price Semantics

- Realtime matched price?
- Delayed price?
- OHLCV candle?
- Bid/ask?
- Other indicative fields:

## Timestamp And Session Semantics

- Timestamp timezone:
- Market session behavior:
- Trading halt behavior:
- End-of-day/final candle behavior:

## Known Limitations

- TBD

## Implementation Notes

- Do not add API calls without a plan.
- Do not scrape websites.
- Confirm auth, rate limits, timestamp semantics, and price semantics before implementation.

## Paste API docs here

Paste sanitized provider docs, examples, and field notes below this line.
