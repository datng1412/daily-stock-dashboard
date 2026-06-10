# Decisions

Last updated: 2026-06-06

This file records current product and engineering decisions that should not be re-litigated without explicit user direction.

## Vietnam Dashboard Data Source

Decision: use Mozyfin as the Vietnam market data adapter, with a fixture mode for local deterministic testing.

Rationale:

- Live market data requires authentication and network access.
- Fixture mode makes local UI/API development deterministic.
- The API must clearly expose whether it is using live or fixture data.

Operational rule:

- `MOZYFIN_FIXTURE_DIR` must be unset for live mode.
- `MOZYFIN_API_KEY` must be present or the Mozyfin CLI must have usable stored auth for live mode.
- Do not mask fixture mode as live mode.

## External Realtime And News Resources

Decision: external realtime and news resource docs may exist under `docs/resources/`, but they are reference-only until explicitly approved.

Operational rule:

- Mozyfin remains the active Vietnam dashboard provider unless changed by a decision record.
- No provider replacement should happen implicitly.
- Resource docs must not trigger implementation, new API calls, scraping, or dashboard behavior changes by themselves.
- Any future provider implementation must first summarize auth, rate limits, timestamp semantics, and data/price semantics.

## Latest Price Semantics

Decision: `latest_price` uses the latest daily OHLCV close unless Mozyfin quote output provides a reliable latest matched price.

Rationale:

- Current quote output does not expose a reliable realtime matched price field.
- The daily OHLCV close is stable and auditable.
- The UI should disclose that the displayed latest price may be an OHLCV close.

Implication:

- During trading hours, the latest daily candle may still be in progress.
- After market close, it may represent final close, but finality still depends on source metadata.

## Quote Semantics

Decision: quote output is not currently treated as the reliable latest matched price source.

Rationale:

- Current quote output is valuable for foreign flow quantities and related fields.
- Price freshness and match semantics are not reliable enough to label it as realtime matched price.

## Intraday Semantics

Decision: intraday pulse is based on 1H OHLCV candles, not realtime quote ticks.

Rationale:

- Mozyfin 1H candles provide a clear, reproducible pulse view.
- The dashboard should not imply tick-level or matched realtime behavior.

## RSI Method

Decision: RSI14 uses Wilder/RMA smoothing.

Rationale:

- Wilder/RMA is the expected market convention for RSI.
- A simple rolling RSI debug comparison may exist, but the user-facing RSI method is Wilder/RMA.

## Status Labels

Decision: Vietnam dashboard labels are neutral condition tags only.

Rationale:

- The dashboard is a monitoring surface.
- It must not emit buy/sell recommendations.

Forbidden behavior:

- Do not add labels such as `Buy`, `Sell`, `Accumulate`, `Take profit`, or equivalent recommendation language unless the product requirement explicitly changes.

## Cache TTLs

Decision: current Vietnam process-local TTLs are:

| Data type | TTL |
| --- | ---: |
| OHLCV daily | 300 seconds |
| Quote | 60 seconds |
| Intraday OHLCV | 60 seconds |
| News | 1800 seconds |

Rationale:

- Daily OHLCV can be cached longer than quote or intraday data.
- News changes less frequently.
- Quote TTL can be revisited if quote becomes the reliable price source.

## Time Formatting

Decision: VN dashboard times should be formatted for Vietnam users.

Rationale:

- Operators reading the VN dashboard need local market context.
- Avoid mixing UTC timestamps into visible UI unless the field is explicitly technical/debug.
