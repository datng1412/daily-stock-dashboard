# Decisions

Last updated: 2026-06-24

This file records current product and engineering decisions that should not be re-litigated without explicit user direction.

## Vietnam Dashboard Product Boundary

Decision: the VN dashboard is a data-quality-first market-data dashboard, not an AI stock advisor.

Rationale:

- The product should help users inspect source coverage, daily data availability, stale or unavailable optional sections, and diagnostics.
- Recommendation wording can blur source facts with investment advice and make missing-data states look more certain than they are.

Operational rule:

- Do not add buy/sell/hold labels, target-price language, trading instructions, account actions, or portfolio actions.
- Separate facts, source status, diagnostics, and neutral interpretation.
- Prefer neutral labels such as `Strong`, `Improving`, `Neutral`, `Weakening`, `Risk elevated`, and `Data unavailable`.

## VN Product Phase Plan

Decision: after Phase 3.5A, the VN dashboard pivots from additional UI refinement to data-first implementation. Phase 4.0A is the next recommended task.

Rationale:

- The product needs to move beyond the SSI migration milestone without blurring current behavior and future work.
- The dashboard now has enough scan, readiness, refresh, filtering, and progressive-disclosure UI structure to support data investigation.
- Later work should establish data capability, reliability, freshness, and provider correctness before adding more visual refinement.
- The core product priority is daily scan first, ticker explanation second, live/diagnostics third, and external/future data last.

Operational rule:

- Phase 0 freezes the current SSI provider milestone.
- Phase 1 and Phase 2 prioritize data-quality visibility and contract cleanup before broader provider expansion.
- Phase 3.2 through Phase 3.5A establish readiness states, refresh preservation, selected-ticker disclosure, sorting, and local filtering.
- Additional table-filter polish, saved filter views, selected-ticker copy polish, layout changes, chart UX polish, and new visual badges are deferred until priority data capability and reliability work is complete.
- Phase 4.0A adds a local capability audit and data-domain matrix without production behavior changes.
- Phase 4.0B verifies SSI realtime/trade-tape endpoints, permissions, payloads, and statuses; live support must not be claimed until usable rows exist with status `ok`.
- Phase 4.1A through Phase 4.4A verify intraday freshness, DailyStockPrice enrichment, profile metadata, and index capability.
- Phase 5.0A through Phase 5.2A require separate explicit provider contracts before news, financials, corporate actions, dividends, or macro implementation.
- Phase 6.0A backend performance/caching work requires measured rate-limit or latency evidence after data reliability work.
- Phase 7.0 packaging work cleans runbooks, startup scripts, validation checklists, and deprecated docs without changing provider semantics.

## Vietnam Dashboard Data Source

Decision: SSI FastConnect is the strict primary VN market-data provider for supported dashboard fields.

Rationale:

- SSI is the official provider path for supported VN market data.
- Current dashboard behavior must be source-auditable and must not silently replace SSI-owned data with legacy providers.
- Unsupported domains should be disabled or explicitly marked as future external-provider work.

Operational rule:

- SSI owns VN daily OHLCV, chart candles, DailyStockPrice/reference/ceiling/floor, latest foreign-flow row, index list, index components when available, symbol metadata when available, intraday candles, realtime snapshot contract, and trade-tape contract.
- `latest_price` uses SSI DailyOhlc close as the canonical dashboard price when SSI daily rows are available.
- Mozyfin is disabled for VN runtime and must not be used as fallback for SSI-owned fields.
- KBS is legacy optional only, disabled by default, and must require explicit legacy flags before diagnostic use.
- News is disabled until a separate NewsProvider is implemented.

## External Realtime And News Resources

Decision: external realtime and news resource docs may exist under `docs/resources/`, but they are reference-only until explicitly approved.

Operational rule:

- Resource docs must not trigger implementation, new API calls, scraping, or dashboard behavior changes by themselves.
- Any future provider implementation must first summarize auth, rate limits, timestamp semantics, and data/price semantics.
- Future news should use a separate NewsProvider contract, not Mozyfin free-tier news/social paths or scraping.

## SSI Realtime And Trade Tape Semantics

Decision: SSI realtime snapshot and SSI trade tape are separate optional live contracts, not replacements for SSI DailyOhlc close.

Rationale:

- Daily OHLCV, realtime snapshot, and trade tape have different timestamp, finality, and row-shape semantics.
- Users must be able to distinguish daily close, intraday candles, realtime snapshot, and trade tape at a glance.
- Live SSI realtime/trade-tape endpoint names, permissions, and row shapes still need environment-specific validation.

Operational rule:

- Do not overwrite `latest_price` with realtime snapshot price.
- Do not label daily close as realtime.
- Do not use trade tape as official daily close.
- Do not use KBS fallback unless explicit legacy diagnostics flags are enabled.
- If SSI realtime or trade tape is unavailable, show unavailable and keep valid daily SSI rows OK.
- Public statuses should stay simple: `ok`, `unavailable`, or `disabled`.
- Endpoint attempts, HTTP status, retryability, and provider-error details belong in diagnostics/logs, not primary metric fields.

## Latest Price Semantics

Decision: `latest_price` uses SSI DailyOhlc close when SSI daily data is available.

Rationale:

- SSI DailyOhlc is the strict daily OHLCV source for the dashboard.
- Current same-date DailyOhlc versus DailyStockPrice mismatches need investigation before changing canonical price semantics.
- The UI should disclose finality/provisional uncertainty separately from the value itself.

Implication:

- During trading hours, the latest daily candle may still be in progress.
- After market close, it may represent final close, but finality still depends on source metadata.
- DailyStockPrice supplies reference/limits, matched/put-through, and latest foreign-flow fields unless a future decision explicitly changes canonical close behavior.

## Intraday Semantics

Decision: SSI IntradayOhlc is a compact intraday candle source, not a realtime matched quote.

Rationale:

- Intraday candle cadence can differ from requested dashboard timeframe.
- Intraday data may be stale relative to SSI DailyOhlc and must be freshness-checked.
- Intraday must remain separate from official daily close and SSI realtime snapshot.

Operational rule:

- Use `intraday_requested_timeframe` for the request hint and `intraday_actual_granularity` for detected returned cadence.
- Do not interpret compatibility `intraday_timeframe` as a guaranteed candle interval.
- If intraday is unavailable, stale, or mismatched, keep `intraday_pulse = null` and `intraday_candles = []`.
- Do not derive intraday labels or metric rows from stale candles.

## Live Section Null/Empty Contract

Decision: unavailable optional live sections use null or empty data, not placeholder metrics.

Operational rule:

- Missing object data: `null`.
- Missing list data: `[]`.
- `realtime_snapshot` is `null` when no usable SSI realtime snapshot exists.
- `intraday_pulse` is `null` and `intraday_candles` is `[]` when intraday is unavailable, stale, or mismatched.
- Trade rows are `[]` when no trade tape rows exist.
- UI availability depends on status plus null/empty checks, not units metadata.
- Diagnostics may retain endpoint attempts, HTTP status, stale-date details, retryability, and provider-error summaries.

## Quote Semantics

Decision: quote metadata is not currently treated as the reliable latest matched price source.

Rationale:

- Current responses can expose quote metadata while `quote_price_date` and `quote_price_raw_field` remain null or unreliable.
- Actual dashboard price source is SSI DailyOhlc close when daily data is available.

## RSI Method

Decision: RSI14 uses Wilder/RMA smoothing.

Rationale:

- Wilder/RMA is the expected market convention for RSI.
- A simple rolling RSI debug comparison may exist, but the user-facing RSI method is Wilder/RMA.

## Status Labels

Decision: Vietnam dashboard labels are neutral condition tags only.

Rationale:

- The dashboard is an inspect-only monitoring surface.
- It must not emit recommendation wording.

Operational rule:

- Prefer neutral labels such as status, trend, momentum, liquidity, source, unavailable, and last updated.
- Do not add trading instruction labels unless the product requirement explicitly changes.

## Cache TTLs

Decision: Vietnam process-local cache TTLs are source-specific and must not blur provider availability.

Rationale:

- Daily OHLCV can be cached differently from intraday, realtime, trade tape, and metadata.
- Provider unavailable is not the same as cache failure.
- Non-retryable SSI realtime/trade-tape errors should eventually use longer TTL/backoff to avoid repeated endpoint probes.

Operational rule:

- Keep cache labels scoped to the source block.
- Do not turn optional live-section cache errors into daily SSI row failures.
- Do not treat units metadata as proof that a data block is available.

## Time Formatting

Decision: VN dashboard times should be formatted for Vietnam users.

Rationale:

- Operators reading the VN dashboard need local market context.
- Avoid mixing UTC timestamps into visible UI unless the field is explicitly technical/debug.

## VN Market Phase Labels

Decision: the VN dashboard shows frontend-derived normal-weekday market phase labels in `Asia/Ho_Chi_Minh`.

Operational rule:

- Supported labels are `Pre-open`, `ATO opening auction`, `Continuous morning`, `Lunch break`, `Continuous afternoon`, `ATC closing auction`, `Post-close`, `Closed`, and `Weekend / closed`.
- Holiday calendars are not implemented; the utility reports `holidayAware=false`.
- Market phase labels are explanatory context only. They do not change data source semantics.
