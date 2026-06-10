# CafeF

## Purpose

Reference notes for evaluating CafeF as a possible Vietnam stock news source.

## Source

- Official docs/source URL: TBD
- Auth/API status: unknown
- Implementation status: reference only
- Decision status: reference only
- Warning: do not implement without explicit user approval.

## Likely Useful Fields

- Article title
- Summary/description
- Published time
- Source URL
- Ticker/company tags, if available
- Category/topic
- Related financial data, if available

## Suitability

| Capability | Looks suitable? | Notes |
| --- | --- | --- |
| Ticker news | unknown | Ticker mapping must be verified. |
| Market news | unknown | Category and freshness semantics must be verified. |
| Macro news | unknown | Category coverage must be verified. |
| Company events | unknown | Event labels and source quality must be verified. |
| Financial data | unknown | Structured fields and terms must be verified. |

## Semantics To Verify

- Published-time format and timezone
- Update-time vs original-published-time behavior
- Ticker/company mapping quality
- Encoding and Vietnamese diacritics behavior
- Source terms, license, and rate limits

## Implementation Notes

- Do not add API calls without a plan.
- Do not scrape websites.
- Current Mozyfin news behavior remains unchanged unless approved.

## Paste API docs here

Paste sanitized CafeF news docs, URL patterns, sample requests, and sample responses below this line.
