# VN Error And Status Taxonomy

## Purpose

The VN dashboard uses two related vocabularies:

- Provider/public statuses: whether a data block is usable, unavailable, or intentionally disabled.
- Data-quality classifications: whether returned data is partial, stale, mismatched, insufficient, unknown, or erroneous.

Do not mix them into a single UI badge without source context.

## Provider/Public Statuses

| Status | Meaning | Use for | UI rule |
| --- | --- | --- | --- |
| `ok` | Provider/section returned usable data for its purpose | Daily row, DailyStockPrice, intraday, realtime, trade tape, index components, profile provider response | Render actual fields that exist. |
| `unavailable` | Provider/section is enabled but no usable data is available | SSI realtime 404, trade tape no rows, stale intraday, IndexComponents failure | Render concise unavailable state; keep daily data visible if daily is valid. |
| `disabled` | Section is intentionally off | News disabled, legacy providers disabled, configured-off live section | Render disabled state; do not treat as failure. |
| `not_implemented` | Future module has no provider/implementation yet | News/financials/events placeholders in company response | Allowed for future modules; not a live-provider status. Phase 2 may normalize or preserve this explicitly. |

## Data-Quality Classifications

| Classification | Meaning | Example | UI rule |
| --- | --- | --- | --- |
| `partial` | Provider responded, but important optional fields are missing | Profile provider status is `ok` but `name` or `industry` is null | Show profile partial/completeness badge; do not fail daily data. |
| `stale` | Data exists but is too old for the current section | Intraday latest date is older than daily price date | Hide live metrics; put stale dates in status/diagnostics. |
| `mismatched` | Two same-ticker/date sources disagree | DailyOhlc close differs from DailyStockPrice close | Surface in Data Quality Summary with both source labels. |
| `insufficient_history` | Not enough historical rows to compute a rolling field | `foreign_net_5d` or `foreign_net_20d` cannot be computed | Show insufficient history, not zero. |
| `unknown` | System cannot determine a semantic status | `final_close_status = unknown` or `adjusted_price_status = unknown` | Show conservative caveat; do not infer. |
| `error` | Unexpected processing or provider error | Parser failure, schema mismatch, unhandled provider response | Prefer sanitized unavailable public status plus detailed diagnostics/logs. |

## Phase 2.1 Public Contract Cleanup

- Company intraday unavailable shape is visible with `pulse = null`, `candles = []`, and status/message fields.
- Watchlist trade tape public data is list-shaped: `trade_tape = []` when unavailable/no rows. Company detail keeps a nested block with `trade_tape.trades = []`.
- Realtime/trade-tape public messages are short and user-safe; sanitized provider details move to status diagnostics or other diagnostics-only structures.
- Profile provider status can be `ok` while profile completeness is `partial`.

## Diagnostics Rules

- Public message: short, user-safe, no endpoint dump.
- Diagnostics: attempted endpoint, last endpoint, HTTP status, retryable flag, stale-date mismatch, sanitized provider error summary. Watchlist live status objects may carry these in a nested `diagnostics` field.
- Forbidden everywhere: credentials, tokens, auth headers, account IDs, raw auth responses.
