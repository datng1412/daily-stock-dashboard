# SSI iBoard

## Purpose

Reference notes for evaluating SSI iBoard as a possible Vietnam realtime market data resource.

## Source

- Known docs/source URL: https://guide.ssi.com.vn/ssi-products
- Auth/API status: unknown
- Implementation status: reference only
- Decision status: reference only
- Warning: do not implement without explicit user approval.

## Likely Useful Fields

- Realtime or delayed quote fields, if documented
- Matched price and matched volume, if documented
- Bid/ask levels, if documented
- Session status, if documented
- Foreign buy/sell/net fields, if documented
- Reference, ceiling, and floor prices, if documented

## Suitability

| Capability | Looks suitable? | Notes |
| --- | --- | --- |
| Realtime price | unknown | Timestamp and matched-price semantics must be verified. |
| Historical OHLCV | unknown | Confirm whether historical candles are available. |
| Foreign flow | unknown | Confirm units and date/session alignment. |
| Financial data | unknown | Confirm whether structured financial fields exist. |
| News | unknown | Confirm whether news is part of the product. |

## Semantics To Verify

- Timestamp timezone
- Whether price fields are realtime matched, delayed, bid/ask, or derived
- Whether intraday updates are tick, snapshot, or candle based
- Market session behavior and final close behavior
- Provider terms, license, and rate limits

## Implementation Notes

- Do not add API calls without a plan.
- Do not scrape websites.
- Mozyfin remains the active provider unless changed by a decision record.

## Paste API docs here

Paste sanitized SSI iBoard API docs, sample requests, and sample responses below this line.
