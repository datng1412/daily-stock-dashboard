# Vietstock

## Purpose

Reference notes for evaluating Vietstock as a possible Vietnam stock news source.

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
- Market/category tags
- Company event or financial data fields, if available

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
- Ticker/company mapping quality
- Encoding and Vietnamese diacritics behavior
- Source terms, license, and rate limits

## Implementation Notes

- Do not add API calls without a plan.
- Do not scrape websites.
- Current Mozyfin news behavior remains unchanged unless approved.

## Paste API docs here

Paste sanitized Vietstock news docs, URL patterns, sample requests, and sample responses below this line.
