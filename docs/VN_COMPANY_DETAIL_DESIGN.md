# VN Company Detail Design

## Goal

Turn the company detail page into a product-quality data-quality report. The page should explain what daily SSI data exists, which source produced each value, which optional live/future modules are unavailable, and which diagnostics explain missing or mismatched data.

The page is not an advisor and must not contain recommendation wording.

## Target Layout

### 1. Header / Hero

Primary fields:

- Ticker.
- Exchange/market.
- Latest price.
- Price date.
- Canonical source.
- Overall data status.

Badges:

- Daily OK.
- Profile partial.
- Live unavailable.
- News disabled or not implemented.
- No recommendation.

Rules:

- Latest price should align with dashboard canonical source (`SSI DailyOhlc`) unless Phase 1 deliberately documents the company price block as SSI DailyStockPrice-specific.
- Missing profile name/industry should not leave empty rows in the hero.

### 2. Data Quality Summary

Purpose:

- Put important data caveats above detailed cards.
- Let users see mismatches and missingness without manually comparing sections.

Items:

- DailyOhlc versus DailyStockPrice mismatch.
- Canonical latest price source.
- Final close status.
- Adjusted price status.
- Intraday stale/mismatched/unavailable.
- Realtime unavailable.
- Trade tape unavailable.
- Metadata partial.

Copy rules:

- Use neutral labels such as `Source mismatch`, `Finality unknown`, `Profile partial`, and `Live unavailable`.
- Show both sources and values when there is a mismatch.
- Do not use raw endpoint errors in this section.

### 3. Daily Core Data

Blocks:

- Price Summary: canonical daily source and finality caveat.
- Trading Stats: source-specific DailyStockPrice values such as matched volume/value, reference, ceiling, and floor.
- Foreign Flow: SSI DailyStockPrice latest foreign-flow fields and rolling-window status.
- Technical Snapshot: indicators derived from SSI DailyOhlc.

Rules:

- Daily core data is dominant on the page.
- Source labels must stay visible.
- DailyOhlc and DailyStockPrice values must not be silently blended.

### 4. Live Data Availability

Blocks:

- Intraday.
- Realtime.
- Trade tape.

Unavailable rules:

- Intraday unavailable: `pulse = null`, `candles = []`, concise unavailable copy.
- Realtime unavailable: `realtime_snapshot = null`, no snapshot metric rows.
- Trade tape unavailable: `trade_tape = []`, no wrapper-object metric rows.

Live sections should be lower prominence than daily core data until SSI live endpoints are confirmed.

### 5. Future Modules

Group future modules together:

- News: disabled or not implemented.
- Financials: not implemented.
- Events/corporate actions: not implemented/unavailable.

Rules:

- No fake module rows.
- No inferred corporate actions from price gaps.
- `not_implemented` is acceptable for future modules while live-provider statuses stay `ok`, `unavailable`, or `disabled`.

### 6. Diagnostics

Diagnostics should be collapsible.

Allowed content:

- Source coverage.
- Endpoint diagnostics.
- HTTP status.
- Retryable flag.
- Stale-date mismatch.
- Cache metadata.
- Sanitized raw details.

Forbidden content:

- Tokens.
- Auth headers.
- Account IDs.
- Raw auth responses.
- Full raw provider payloads.

## Profile Partial Behavior

Current handoff finding:

- Company profile can have `name = null` and `industry = null` while provider status is `ok`.

Target:

- Treat `profile.status = ok` as provider response status only.
- Add or derive `profile_quality` / `profile.completeness = partial` when key fields are missing.
- UI shows `Profile partial` badge and hides null metadata rows.

## Source Mismatch Behavior

Current handoff finding:

- Company price can report `source = SSI DailyStockPrice`, while broader dashboard canonical `latest_price` uses SSI DailyOhlc close.

Phase 1 decision point:

- Either align company price with DailyOhlc canonical source.
- Or explicitly label company price as DailyStockPrice-specific and keep canonical daily price elsewhere in the header.

Until resolved:

- Data Quality Summary should flag DailyOhlc versus DailyStockPrice mismatch when present.
- UI must not silently overwrite one source with the other.

## Forbidden UI Patterns

- Placeholder metric rows such as `Snapshot price -`.
- Raw endpoint dumps in primary UI.
- Fake news, financials, or corporate actions.
- Hardcoded index constituents.
- Daily close labeled as realtime.
- KBS or Mozyfin fallback presented as normal runtime behavior.
- Recommendation wording.

## Acceptance Criteria

- Page reads like a data-quality report.
- Daily core data is visually dominant.
- Data-quality warnings appear above detailed cards.
- Profile partial is visible when key metadata is missing.
- Future modules are grouped.
- Diagnostics are collapsible.
- Primary UI contains no endpoint dumps or raw provider errors.
- Unavailable live sections do not render fake metric rows.
