# Vietnam Dashboard Data Contract

## Purpose

This document defines the public data contract for the VN dashboard and company research page. It is intentionally data-quality-first: valid daily SSI data should remain visible even when optional live or enrichment sections are unavailable.

## Verified manual HOSE proprietary-flow EOD

The Proprietary product is a separate completed-session aggregate sourced by a
user who reads an official HOSE publication and supplies required gross buy and
sell values to `scripts/record_vn_proprietary_eod.py`. The application does not
download, parse, OCR, or scrape that publication. If a PDF is supplied, it is
only signature-checked and SHA-256 hashed; only its sanitized basename, hash,
and byte size are retained.

Canonical values are integer VND and net equals gross buy minus gross sell.
Optional gross volumes are integer shares and must be supplied as a pair; their
net is derived. Missing volume remains null and explicit zero remains zero.
Rows require user verification, an official HTTP(S) source URL, and either
hashed-PDF evidence or an explicit file-unavailable acknowledgement. The
schema-v1 atomic store is
`DATA_CACHE_DIR/vietnam_proprietary_flow_eod.v1.json`, keyed by `HOSE` and
trading date and isolated from accepted SSI foreign-flow history.

Same canonical input is idempotent. Conflicting same-date input is rejected
unless explicit replacement and reason are supplied; evidence cannot be
downgraded, and replacement audit metadata is retained. Public writes are not
exposed. Latest/history GET responses use `ready`, `no_data`, `incomplete`,
`suspicious`, or `storage_error`. The frontend reads at selection/reload/manual
refresh only, retains last-known-good data after refresh failure, and never
polls or labels these rows as current-session data.

## Idle recovery and last-known-good aggregates (Phase SSI-V3-M2.6B-R6C)

Retryable SSI authentication, authorization, timeout, empty, or malformed
membership refreshes do not replace a previously validated VN30 cohort. The
process retains the last-known-good normalized SSI IndexComponents membership
and reports its age, source, retention state, and refresh failure. A cold
process with no validated membership remains unavailable and does not invent
members.

Accepted DailyStockPrice rows remain the completed-session authority and can
rebuild a usable completed VN30 display after a current refresh fails. Existing
provider-dated `ForeignRoomMessage` snapshots may remain visible as stale, but
are never added together locally, persisted as completed history, or converted
to zero. Missing current data remains null/empty.

`recovery_trigger=route_touch|visibility_resume|manual_refresh` is additive on
the VN30, current-symbol, and current-aggregate routes. Visibility resume and
manual refresh may bypass the current negative authentication cache once per
failure generation. Authentication recovery is process-shared, single-flight,
and cooldown-bound; it does not make request handlers own the stream.

## Current aggregate finality propagation (Phase SSI-V3-M2.6B-R6B)

Every merged current/completed display row retains its trading date, source
kind, source, finality, current/provider state, display status, current/
completed/partial/stale flags, requested/observed/complete coverage, six
foreign-flow values, and provider/receipt timestamps when supplied. Accepted
same-date DailyStockPrice continues to suppress a provisional current row
without mutating completed input history.

Finality is independent of numeric completeness and symbol coverage. Only
`completed_accepted` maps to `Đủ`; `current_session_provisional` maps from the
current state to `Đang diễn ra`, `Mất kết nối`, `Tạm tính`, `Chờ dữ liệu`, or
`Không khả dụng`. An unknown current state never defaults to `Đủ`.

VN30 provenance exposes latest completed, latest display, and provider-backed
current sessions separately. Current Industry diagnostics use
`ready`/`partial`/`stale`/`waiting`/`unavailable` and disclose the bounded
current-VN30 universe plus requested, classified, observed, complete-value,
complete-volume, stale, missing, and group counts. This is not full-market
industry coverage.

## VN-ALERT-1 completed-session rule contract

The generic Alert API additively accepts `target_scope=vn_market` with
`vn_foreign_flow`, `vn_breadth`, `vn_sector`, or `vn_relative_strength`.
Parameters are strictly normalized combinations of `metric`, optional 1/5/20
`window`, numeric `operator` plus finite `threshold`, or a supported completed
foreign-flow `expected_state`; relative strength also requires `benchmark`.
No VN-specific CRUD route or storage table is added.

Evaluation uses only accepted completed source contracts. DailyStockPrice
foreign flow must have a complete accepted window; breadth requires completed
DailyOhlc and the full metric denominator; sector price/MA/flow uses its own
completed source and complete group coverage; relative strength requires a
complete exact-aligned window. Missing, null, anomalous, partial-required, or
provisional data is non-evaluable and never coerced to zero. Current
`ForeignRoomMessage` flow is excluded.

The existing trigger record stores the provider session in `data_timestamp`.
Sanitized diagnostics carry family, scope, metric, window, condition, observed
value/state, source/endpoint, finality, coverage, cache use, dedup identity, and
an existing `/foreign-flow` or `/vietnam` deep link. Same rule, target, source,
and completed session is persisted/notified once; a later session is eligible.
The API serializes structured trigger diagnostics as valid compact JSON rather
than truncating an object mid-token; only an allowlisted, sanitized field set is
returned, and oversized coverage is omitted before the deep link is lost.

Final production acceptance on 2026-08-12 used completed SSI session
`2026-08-11`: FPT one-session flow was `distributing` with
`foreign_net_value=-104,650,853,200` VND. The real worker persisted one trigger,
suppressed the same-session repeat, evaluated no disabled rule, and retained a
naturally unavailable industry-relative-strength input as non-triggering.

## Durable accepted foreign-flow history (Phase SSI-V3-M2.6B-R6A)

Accepted completed SSI DailyStockPrice foreign-flow rows are keyed by normalized
symbol and provider trading date. They are rehydrated from the schema-v1 file
under `DATA_CACHE_DIR` at application startup and merged monotonically with
fresh accepted rows. A weaker, empty, failed, or force-refresh response cannot
delete a newer accepted date; a valid same-date provider correction replaces
that date without creating a duplicate.

The durable document contains only the six accepted buy/sell/net value and
volume fields plus accepted source/finality, field-presence/anomaly coverage,
and persistence metadata. It contains no raw provider message or credential.
Current `ForeignRoomMessage` values, stale current snapshots, VN30 current
aggregates, industry current aggregates, and watchlist current aggregates are
display-only and never enter completed storage. Public API fields are unchanged.

## Company Research capability and zero-lineage contract (Phase SSI-V3-M2.5D)

`daily_stock_price.capabilities` classifies `price_limits_status`, `matched_stats_status`, `put_through_status`, `foreign_flow_status`, `session_metadata_status`, and `overall_status` independently as `ready`, `partial`, or `unavailable`. An unavailable optional price-limit family can make the overall enrichment partial, but it does not invalidate provider-backed matched statistics, put-through statistics, foreign flow, or session metadata. Reference, ceiling, and floor remain null unless SSI supplies them.

Foreign-flow normalization preserves provider meaning across the adapter, service, schema, JSON, and UI. Provider numeric zero remains numeric zero; null, absent, blank, and malformed fields remain null. Malformed audited fields add a typed normalization issue. Net volume/value are derived only when both corresponding gross inputs are present. `foreign_flow_value_state` distinguishes `explicit_zero`, `nonzero`, `partial`, and `unavailable`; field presence and raw aliases remain in sanitized diagnostics. A single bounded FPT read for completed session `2026-07-28` confirmed the four V3 gross fields were present strings containing numeric zero; the two net fields were derived zero from those complete pairs.

Company intraday has a separate `capability_status`. Usable candles with matched cadence are ready; usable irregular or request-mismatched cadence is partial; empty or invalid data does not become ready. `intraday_change` and `intraday_change_percent` use `first_session_candle_open` only when `intraday_change_baseline` and its numeric value are available. A missing baseline produces null, while equal valid values produce real zero. No candle is resampled, synthesized, or gap-filled.

The primary Technical Snapshot retains MA20, MA50, RSI14, Bollinger values, 52-week high/low, average-volume context, and daily range. Coverage counts/states, price-versus-reference state/value, and calculation provenance remain available in the collapsed technical-details disclosure and diagnostics. The compact quality summary remains limited to Daily data, Live market, and Company metadata.

## Company Research session and availability contract (Phase SSI-V3-M2.5B)

`GET /api/v1/stocks/vn/company/{ticker}` additively separates completed daily and live-event context. `session_context.completed_session_date` identifies the provider-backed DailyOhlc session; `live_session_date` is populated only from provider event provenance such as X-QUOTE trading date or a parseable stream timestamp. These dates may differ normally. `source_freshness` uses `current`, `latest_completed`, `publication_lag`, `stale`, or `unknown`; cache age remains a separate transport/cache observation and never determines source freshness by itself. The market-session helper is explicitly holiday-unaware.

Daily finality uses `completed`, `provisional`, `unknown`, or `not_applicable`. A prior dated daily row is completed, while a same-date daily row during an active Vietnam session is provisional. Adjustment lineage uses `adjusted`, `unadjusted`, `not_provided`, or `unknown`; V3 DailyOhlc currently maps absent adjustment lineage to informational `not_provided`, not a page warning.

`live_market.channels` independently classifies `last_price`, `order_book`, `trade_tape`, and `intraday` as `ready`, `partial`, `reconnecting`, `no_data`, `stale`, `unavailable`, `disabled`, or `error`. Overall live state is ready only when all visible channels are usable, partial when at least one is usable, and unavailable when none are usable. A ready X-QUOTE order book therefore prevents a false global unavailable state.

Company profile exposes `core_profile_status` separately from `optional_metadata_status`. Sector and Industry come only from provider metadata and remain null when absent. DailyStockPrice diagnostics independently classify price limits, matched/put-through statistics, foreign flow, and session metadata. Reference, ceiling, and floor values retain per-field DailyStockPrice lineage; exchange-limit calculations, daily close, bids, and asks are never substituted.

The primary Company Research quality summary contains at most Daily data, Live market, and Company metadata. Detailed issue codes, finality, adjustment lineage, per-channel state, cache/source details, missing optional fields, and provider endpoints remain in diagnostics. Duplicate issues are removed by code. Missing values stay null and provider zero stays zero.

## Foreign Flow Explorer Runtime States (Phase SSI-V3-M2.4C-R2)

Ticker, current-VN30, Industry, Proprietary, and Watchlist payloads are normalized by one frontend view-state contract: availability (`ready`, `partial`, `unavailable`), usability, source freshness, data quality, failure class, and row presence remain separate. Partial usable responses render their available content with a warning. Provider-unavailable responses render an explicit unavailable state and never an empty chart or table. A successful provider response with zero completed-session records remains a distinct empty-data state.

`POST /api/v1/stocks/vn/industry-flow` additively returns `data_state`, `usable`, and `failure_class`. Invalid dates, identifiers, or mutually exclusive universe inputs remain HTTP 422. Membership, authorization, network, timeout, or other provider unavailability returns HTTP 200 with `status=data_state=unavailable`, `usable=false`, empty rows, and sanitized provenance. Unsupported is used only for a capability absence proven by a successful provider request. Unexpected service failures return a sanitized HTTP 500 response and are not labelled as user validation.

Explorer modes retain their own last usable response and error. Switching tabs does not erase another mode, revisiting an unchanged usable scope does not refetch solely because of the tab switch, and a failed force refresh preserves the previous same-scope usable response. Abort and request-generation guards continue to prevent obsolete responses from replacing current state.

## Watchlist Foreign Flow Screener (Phase SSI-V3-M2.4C)

`GET /api/v1/stocks/vn/foreign-flow/watchlist` is the user-controlled 1–30 symbol completed-session screener contract. The frontend loads one 60-session batch and derives Value/Volume display, 1D/5D/20D/60D selection, search, filtering, sorting, and CSV locally. It never creates one frontend history request per ticker. The existing raw symbol-history cache remains authoritative and its key retains provider/schema version, ticker, session capacity/date bounds, and source endpoint.

Each window requires the stated number of actual accepted provider sessions and complete non-null values for the requested field; incomplete window metrics remain null. Calendar gaps are not filled. Streaks use daily `foreign_net_value`, count backward from the latest accepted completed session, stop at null, and break at zero. They describe historical flow only and are not recommendations. Explicit provider zero remains zero and may carry anomaly metadata independently of availability.

Top-level and per-symbol availability use `ready`, `partial`, and `unavailable`. Source freshness (`latest_completed`, `stale`, `unknown`), cache state (`hit`, `miss`, `refresh`, `stale_hit`, `unavailable`), data quality, and failure class remain independent. `source_session_lag` is an observed-date rank within the returned batch, not a fabricated holiday-aware trading calendar. Different latest dates render as `mixed source sessions`; monetary totals are not presented as one common-date aggregate.

The versioned browser key `stockclock.vn.foreignFlowWatchlist.v1` stores only normalized symbols and safe UI preferences. It stores no provider response. URL tickers take precedence, then local state, then an empty list. SSI-derived VN30 membership loads only after explicit user action.

## On-demand symbol foreign-flow analytics (Phase 4.12E-3)

`GET /api/v1/stocks/vn/foreign-flow/symbol/{ticker}?limit=60` keeps its existing rows, windows, latest, request, coverage, source, finality, freshness, and failure fields and additively exposes optional `analytics`. Analytics use only the last 60 normalized accepted SSI DailyStockPrice rows and keep value and volume families separate. Each family contains latest, 5/20/60 windows, accepted-row current streak, latest adjacent nonzero reversal, 20/60 comparison statistics, and extrema; `rolling_series` contains null-aware 5/20 sums.

Missing net values remain `null`: they do not become zero, complete a window, extend a streak, form a reversal, or fill a rolling window. Percentile is inclusive rank, `100 * count(sample <= latest) / N`, separately for signed and absolute values. Z-score is `(latest - mean) / population_standard_deviation`; both require at least five finite observations and zero deviation returns `null`. `unusual_flow_state=elevated` requires absolute 60-session percentile `>=90` or absolute 60-session z-score `>=2`. The contract is completed-session `daily_available` inspection only; it makes no current-session, price/flow, liquidity, alert, or predictive claim.

### Explainable completed Foreign Flow signals (VN-FF-SIGNAL-1)

`analytics.signals` is the single machine-readable signal owner and uses
`basis=foreign_net_value`, VND, SSI DailyStockPrice, and
`finality=daily_available`. `direction_1d`, `direction_5d`, and
`direction_20d` classify only complete accepted net-value windows: positive is
`accumulating`, negative is `distributing`, exact zero is `neutral`, and any
missing/incomplete window is `unavailable`. Each direction returns requested,
observed, and covered sessions plus dates, completeness, and the numeric net
value only when complete.

`momentum` requires ten complete accepted sessions. `recent_5_average` covers
T-4 through T and `previous_5_average` covers T-9 through T-5. A direct
nonzero sign change is `reversal`; otherwise a larger absolute recent average
is `accelerating`, a smaller one is `decelerating`, equality is `stable`, and
a transition through exact zero is conservatively `stable`. No epsilon or
calendar-day filling is used. `reversal` reuses the existing adjacent nonzero
completed-row event. `intensity` reuses the existing 60-session absolute
percentile `>=90` or absolute z-score `>=2` rule and its existing five-finite-
observation minimum; it adds no score.

The same helper may describe VN30 current-membership decomposition history and
is labelled `historical_constituent_correct=false`. Current-session
`ForeignRoomMessage` data remains separately labelled provisional and is not
inserted into direction, momentum, reversal, percentile, or z-score inputs.
The unresolved 2026-06-29/30 anomaly rows remain excluded and cannot complete
a window. The frontend maps server states only and introduces no signal
request or polling lifecycle.

Frontend foreign-flow formatting is a display-only contract: VND values with `abs(value) >= 1,000,000,000` render as the value divided by one billion with two decimal places and the suffix `Tỷ`; lower VND values and share volumes render as complete grouped integers. Decimal and thousands separators are always `.` and `,` respectively and do not depend on browser locale. API numbers remain unchanged.

## Completed-session 1-minute chart history (Phase 4.11C)

`GET /api/v1/stocks/vn/intraday-chart?ticker=FPT&interval=1m&date=YYYY-MM-DD` returns one completed or current Vietnam date from SSI `IntradayOhlc`. Only `1m` is accepted; dates after the current `Asia/Ho_Chi_Minh` date return the endpoint-specific 422 contract. `ready` contains usable sparse bars; a current date without usable bars is `unavailable`; `failed` means a nonempty response had no usable bars. Stale-if-error data remains `ready` and is disclosed by `cache.is_stale=true` plus `freshness=stale`.

Unsupported intervals are validated by this endpoint before SSI is called and return HTTP 422 with `error=vn_intraday_chart_invalid_request` and `message=Only interval=1m is supported`. Invalid current/future dates use the same error code with the completed-date message. The broader global request-validation copy does not own these intraday allowlist errors.

Provider `DD/MM/YYYY` plus `HH:MM:SS` values are interpreted in `Asia/Ho_Chi_Minh`, floored to minute start, and returned as Unix seconds. OHLC must be finite and positive, volume finite and non-negative, and invalid or wrong-date rows are rejected. If multiple rows normalize to one minute, the latest original provider timestamp wins; identical timestamps keep the last stable occurrence. Missing minutes remain gaps. D1 remains SSI `DailyOhlc`; current-session candles, higher intervals, aggregation, pagination beyond page 1, realtime candle substitution, and provider fallback are not supported.

## Status Enum

Public section statuses should use:

```text
ok
unavailable
disabled
```

Use `ok` only when the section has usable data for its purpose. Use `unavailable` when the source is enabled but no usable data is available. Use `disabled` when the section is intentionally off.

Technical sub-statuses, provider codes, HTTP status, retryability, and endpoint attempts belong in diagnostics.

Profile completeness labels such as `partial` are data-quality classifications, not provider status enum values. Provider/live-section statuses should remain `ok`, `unavailable`, or `disabled`.

Future modules that are already exposed in placeholder API sections may use `not_implemented` until Phase 2 normalizes or removes those sections. Do not use `not_implemented` for live provider probes that were attempted; those remain `unavailable` when enabled but no usable data exists.

## Missing Data Rules

Use these rules consistently across backend responses and frontend rendering:

* Missing object data: `null`.
* Missing list data: `[]`.
* Do not emit placeholder objects for unavailable sections.
* Do not create metric rows from unavailable sections.
* Do not show `-` or `Unavailable` as if it were a metric value.
* Keep diagnostics separate from primary metric fields.

## Daily Data Contract

Daily data is the primary public contract for the VN dashboard.

Required daily fields when the watchlist row is usable:

* `latest_price`: selected by the conditional SSI source algorithm below.
* `latest_price_source`: identifies the actual selected source, including `SSI DailyOhlc`, `SSI DailyStockPrice`, a reliable normalized quote source, or `unknown`.
* OHLCV fields: `open`, `high`, `low`, `close`, `daily_close`, `ohlcv_close`, `volume`, and value/amount fields when SSI provides them.
* Price date fields: `latest_price_date`, `ohlcv_date`, or the current normalized daily trading date.
* Source fields: `source`, `actual_source`, `fallback_used`, and block-specific source labels.
* Finality fields: `final_close_status` or equivalent final/provisional/unknown field when available.

Daily finality must stay explicit:

* `final` means the system has a defensible final-close signal.
* `provisional` or `in_progress` means the daily candle may still change.
* `unknown` means the dashboard has no reliable finality signal.

The current canonical selection algorithm is conditional, not a static source
priority:

1. When DailyOhlc history is materially stale and a dated usable
   DailyStockPrice close exists, select that newer close and label
   `latest_price_source=SSI DailyStockPrice`.
2. Otherwise, when the normalized SSI quote context provides a positive latest
   price plus its audited raw-field identity, select that quote and expose its
   source/date as current optional market data.
3. Otherwise, use the normalized DailyOhlc close and label it
   `latest_price_source=SSI DailyOhlc` when present.
4. If none of those branches supplies a usable value, `latest_price` remains
   null and the source is `unknown`/unavailable. No external or legacy provider
   fills it.

Selecting a newer DailyStockPrice close does not synthesize OHLCV fields and
does not make stale DailyOhlc technical indicators usable. A current quote is
provisional/live context and does not become a completed daily close. The
selected source, raw field, and provider date remain visible separately so
finality follows the selected source/session rather than the display label.
`daily_close`, chart candles, daily open/high/low/volume, and technical inputs
remain DailyOhlc-owned and may be null/unavailable independently.

Company detail aligns `latest_price` and its canonical source with the same
watchlist selection algorithm. `price.reference_source` continues to identify
SSI DailyStockPrice for reference, ceiling, and floor. Foreign-flow, matched,
put-through, adjusted-close, and other source-specific fields remain explicitly
DailyStockPrice-owned.

## Stock Detail Metrics Availability

This matrix maps common stock-detail panel labels to the current repository contract. It documents only fields that already exist today; it does not authorize new API fields, parser mappings, computed metrics, or provider integrations.

Status values:

* `Available now`: already exposed by the current strict SSI runtime/API/schema/frontend data model when the source returns the field.
* `Present internally, not exposed`: normalized internally but not part of the current public contract.
* `SSI-derived implemented`: calculated internally from SSI-owned fields with null/coverage semantics.
* `SSI-derived later, not implemented`: can be derived from SSI-owned data, but the current code does not compute this exact metric.
* `Deferred pending methodology/semantics`: should not be treated as external-provider-required until SSI inputs, share-count semantics, or methodology are verified.
* `Not available / future provider required`: requires a future fundamentals, corporate-actions, or other external provider contract.
* `Ambiguous, needs provider confirmation`: a related field exists, but its semantics or population path are not confirmed enough to present under the screenshot label.

| UI label | Meaning | Current status | Current source | Current API/schema field | Notes / future work |
| --- | --- | --- | --- | --- | --- |
| Open | Daily/session open price | Available now | SSI DailyOhlc for canonical daily rows; SSI DailyStockPrice may also expose an enrichment `open` | Watchlist `open`; company `trading_stats.open`; chart `points[].open`; nested `daily_stock_price.open` when present | Treat as daily candle/session open, not realtime open, unless a future realtime-detail design explicitly uses realtime data. |
| Average | Average trading price | Ambiguous, needs provider confirmation | Optional SSI realtime schema placeholder only | `realtime_snapshot.average_price` / realtime quote `average_price` exists in schema/types but current provider mapping does not populate it | Do not show as available stock-detail data until SSI realtime payload semantics and mapping are verified. |
| Matched val | Matched trading value | Available now | SSI DailyStockPrice | `daily_stock_price.matched_value`; compatibility `ssi_matched_value` | Do not fill from DailyOhlc `amount`/`value`; source label must remain DailyStockPrice. |
| PT val | Put-through trading value | Available now | SSI DailyStockPrice | `daily_stock_price.put_through_value`; compatibility `ssi_put_through_value` | Null means SSI did not provide the field; zero remains a real provider value. |
| High 52W | 52-week high | SSI-derived implemented | SSI DailyOhlc high history | `indicators.high_52w`; company `technical.high_52w`; date `high_52w_date` | Uses the latest 252 returned DailyOhlc rows; null when fewer than 120 usable high/low rows are available. |
| Avg. vol. 3M | Three-month average volume | SSI-derived implemented | SSI DailyOhlc volume history | `indicators.avg_volume_3m`; company `technical.avg_volume_3m` | Uses up to 63 latest usable volume rows; `complete` at >=60, `partial` at >=30, null below 30. |
| Avg. vol. 10D | Ten-day average volume | SSI-derived implemented | SSI DailyOhlc volume history | `indicators.avg_volume_10d`; company `technical.avg_volume_10d` | Requires 10 usable volume rows; null below 10. |
| EPS (TTM) | Trailing-twelve-month earnings per share | Not available / future provider required | Future fundamentals provider | No current EPS field | Not implemented in SSI runtime; do not infer from price data. |
| P/E (TTM) | Price-to-earnings ratio | Not available / future provider required | Future fundamentals/ratios provider | No current P/E field | Do not compute from missing EPS. |
| P/B | Price-to-book ratio | Not available / future provider required | Future fundamentals/ratios provider | No current P/B field | Requires book-value/fundamentals source. |
| Beta | Market beta | Deferred pending methodology/semantics | SSI DailyOhlc plus verified SSI index data and documented beta methodology, or future source-labeled provider only if SSI cannot support it | No current beta field | Do not default to external provider; verify SSI index input and methodology first. |
| FR. buy vol | Foreign buy volume | Available now | SSI DailyStockPrice | `daily_stock_price.foreign_buy_volume`; `foreign.buy`; raw-field marker `foreign_buy_raw_field` | Unit is shares when quantity fields exist. |
| FR. sell vol | Foreign sell volume | Available now | SSI DailyStockPrice | `daily_stock_price.foreign_sell_volume`; `foreign.sell`; raw-field marker `foreign_sell_raw_field` | Unit is shares when quantity fields exist. |
| FR. room | Foreign ownership room/remaining room | Optional backend/API live context | SSI `R:{symbol}` streaming cache | Watchlist `foreign_room_source`, `foreign_room`, `foreign_room_status`, and `diagnostics.foreign_room` | Separate from DailyStockPrice daily foreign flow. Value-unit and approximate-value semantics remain `needs_semantics_proof` until live provider evidence confirms them. |
| PT vol | Put-through trading volume | Available now | SSI DailyStockPrice | `daily_stock_price.put_through_volume`; compatibility `ssi_put_through_volume` | Do not substitute DailyOhlc volume or matched volume. |
| Low 52W | 52-week low | SSI-derived implemented | SSI DailyOhlc low history | `indicators.low_52w`; company `technical.low_52w`; date `low_52w_date` | Uses the latest 252 returned DailyOhlc rows; null when fewer than 120 usable high/low rows are available. |
| Outs. qty | Outstanding quantity / share count | Ambiguous, needs provider confirmation | SSI SecuritiesDetails/Securities metadata when provider returns share-count fields | `symbol_metadata.listed_shares`; watchlist/company `listed_shares`; profile `listed_shares` | Exposed field is listed shares / provider share-count metadata. Do not label it as exact outstanding quantity until SSI semantics are confirmed. |
| Market cap | Equity market capitalization | Deferred pending methodology/semantics | SSI or verified external share-count semantics plus canonical price rule | No current market-cap field | Do not compute from `latest_price * listed_shares` until share-count basis and product behavior are verified. |
| Dividend ratio | Cash/stock dividend ratio | Not available / future provider required | Future CorporateActionsProvider | Future contract fields may include `cash_dividend_per_share` and `stock_dividend_ratio`, but default provider returns empty lists | Corporate actions are disabled/not configured by default and must not be inferred from price gaps. |
| Next div. date | Next dividend/ex-date/payment date | Not available / future provider required | Future CorporateActionsProvider | Future event fields may include `ex_date`, `record_date`, and `payment_date`, but no live provider exists | `events=[]` means no verified rows are available, not confirmed absence of dividends. |
| ROE | Return on equity | Not available / future provider required | Future fundamentals/financial statements provider | No current ROE field | Not implemented. |
| ROA | Return on assets | Not available / future provider required | Future fundamentals/financial statements provider | No current ROA field | Not implemented. |

## Data Quality Summary Contract

Watchlist rows and company detail responses expose `data_quality_summary` as a Phase 1 summary layer. This field is additive and must not change canonical price behavior.

Required rules:

* `canonical_price_source` reports the source selected by the conditional
  algorithm in the Daily Data Contract; it is not hardcoded to DailyOhlc.
* `overall_status` uses `ok`, `partial`, or `unavailable` for summary quality only.
* `issues` contains short user-safe messages and source-labeled fields.
* `issues` must not contain endpoint names, HTTP status, attempted endpoints, raw provider errors, credentials, tokens, account IDs, or raw auth responses.
* `checks` records section quality for daily OHLCV, DailyStockPrice, final close, adjusted price, intraday, realtime, order book, foreign room, trade tape, profile, and news.
* Optional live-section unavailable states may make the summary `partial`, but they must not make valid daily SSI data unavailable.

Watchlist responses may also expose additive request-completeness counters:

```text
requested_tickers_count = normalized unique ticker count requested by the watchlist path
returned_rows_count = number of rows returned in the response
missing_tickers = requested normalized tickers not represented by a row
```

The same counters may appear under `data_quality` for diagnostics. A complete response should include one row per normalized requested ticker. If a row is partial or unavailable, it should stay visible and explain why through `data_quality_summary.issues` rather than disappearing.

## SSI-Derived Metrics Contract

Phase 4.8A adds these additive fields under watchlist `indicators` and company `technical`. They are calculated internally and never change row status or canonical `latest_price`.

| Field | Formula / source | Null and coverage behavior |
| --- | --- | --- |
| `high_52w`, `low_52w` | Max high / min low from the latest 252 returned SSI DailyOhlc rows | `high_low_52w_coverage_status` is `complete` at >=240 usable high/low rows, `partial` at >=120, and `insufficient` below 120. A usable row requires a valid date plus positive numeric high and low. Values and dates are both null when insufficient. Dates are `high_52w_date` and `low_52w_date`. |
| `avg_volume_10d` | Average volume from the latest 10 usable SSI DailyOhlc volume rows | Requires 10 usable rows; otherwise null with `avg_volume_10d_coverage_status=insufficient`. A usable volume row is numeric and >=0. |
| `avg_volume_3m` | Average volume from up to the latest 63 usable SSI DailyOhlc volume rows | `avg_volume_3m_coverage_status` is `complete` at >=60 rows, `partial` at >=30, and `insufficient` below 30. Value is null when insufficient. A usable volume row is numeric and >=0. |
| `price_vs_reference_pct` | `(DailyOhlc close - DailyStockPrice reference_price) / reference_price * 100` | Requires positive DailyOhlc close and positive DailyStockPrice reference. Status is `ok`, `daily_close_unavailable`, or `reference_unavailable`. |
| `daily_range_pct` | `(DailyOhlc high - DailyOhlc low) / DailyOhlc close * 100` | Requires numeric DailyOhlc high/low, positive close, and high >= low. Status is `ok` or `insufficient`. |
| `short_term_zones` | Compact D1 support/resistance zones | Object with `status`, `reason_code`, `source`, `timeframe`, `lookback_sessions`, `support[]`, and `resistance[]`. Source is `derived from SSI DailyOhlc`; timeframe is `D1`; lookback is 60 valid unique sessions. Each public zone contains only numeric `lower` and `upper`. ATR14 Wilder/RMA plus two-before/two-after swing pivots define local zones. Zones crossing the latest daily close are excluded; support is nearest-first below, resistance nearest-first above, at most two each. Insufficient valid history or ATR returns `status=unavailable` and empty lists. The selected ticker's optional daily-chart overlay reuses these ranges as at most S1/S2/R1/R2 clipped bands without a new request or y-domain change. No provider call, realtime input, fallback, or `latest_price` change is allowed. |
| `ssi_derived_metrics_status`, `ssi_derived_metrics_source` | Aggregate source/status for the fields above | Source is `SSI DailyOhlc + SSI DailyStockPrice`; status is `ok`, `partial`, or `insufficient`. |

Reason codes used for row-level partial/missing explanations include:

* `daily_ohlcv_missing`
* `daily_stock_price_missing`
* `ta_insufficient_history`
* `rsi_missing`
* `ma_state_insufficient_data`
* `foreign_flow_missing`
* `metadata_partial` / `profile_partial`
* `realtime_ticker_not_bootstrapped`
* `realtime_config_disabled`
* `realtime_cache_empty`
* `realtime_cache_stale`
* `intraday_unavailable_no_rows`
* `provider_empty`
* `provider_error`

These codes describe data availability only. They must not synthesize values,
hide rows, or independently change the conditional `latest_price` selection
algorithm.

## Live Section Contract

### Persisted last-known streaming metadata

When the optional lifecycle snapshot is enabled, normalized restored live rows may add `snapshot_source="persisted"`, `snapshot_captured_at`, `snapshot_trading_date`, `snapshot_schema_version=1`, `is_stale=true`, and `cache_status="persisted_stale"`. These fields are additive diagnostics/freshness metadata only. They never make X current/live, never replace `latest_price` or DailyOhlc, and never change empty/null contracts when no persisted row exists. During active sessions the user-facing state is waiting for live SSI updates; after close it is last-known stale data.

This is the Phase 2 public contract. Missing live objects and lists must not be represented by placeholder objects or fake metric rows.

### Intraday

When SSI IntradayOhlc is usable:

```text
intraday_status.status = ok
intraday_status.reason_code = ok or cadence_mismatch
intraday_source = SSI IntradayOhlc
intraday_requested_timeframe = request hint, for example 1h
intraday_actual_granularity = detected provider-returned cadence, for example 1m or 1h
intraday_actual_granularity_seconds = detected cadence in seconds when regular
intraday_cadence_status = matched, different_from_requested, irregular, unknown, or unavailable
intraday_candles = [ ... ]
intraday_pulse = { ... }
```

When intraday is unavailable, stale, disabled, or date-mismatched:

```text
intraday_status.status = unavailable or disabled
intraday_status.reason_code = disabled, unavailable_no_rows, unavailable_date_mismatch, unavailable_rate_limited, unavailable_provider_error, unavailable_unknown, or unknown
intraday_source = SSI IntradayOhlc
intraday_cadence_status = unavailable or unknown
intraday_candles = []
intraday_pulse = null
```

Stale latest-date metadata, date-match details, and cadence diagnostics should move to `intraday_status` or diagnostics when there is no usable intraday section. `intraday_timeframe` is a compatibility request hint and must not be treated as the actual provider interval unless `intraday_cadence_status = matched`.

The company endpoint follows the same missing-object rule. When nested company `intraday.status = unavailable`, `intraday.candles = []` and `intraday.pulse = null`. Company `intraday.cadence_status` mirrors the watchlist cadence classification, and `intraday.diagnostics` may carry sanitized failure details such as `failure_class`, `endpoint`, `http_status`, and provider code.

### Realtime Snapshot

When SSI realtime snapshot is usable:

```text
realtime_status.status = ok
realtime_status.reason_code = cache_hit
realtime_snapshot = { ... }
```

When no usable SSI realtime snapshot exists:

```text
realtime_status.status = unavailable or disabled
realtime_status.reason_code = disabled, config_disabled, not_started, bootstrap_symbols_empty, ticker_not_bootstrapped, running_idle, cache_empty, cache_stale, connection_error, auth_or_entitlement_failure, network_or_tls_failure, rate_limited, or unknown
realtime_snapshot = null
```

`realtime_status.message` is short user-facing copy such as `SSI realtime unavailable.`, `SSI realtime cache miss.`, `SSI realtime manager disabled.`, or `SSI realtime stale.` Technical state is not embedded in this message. Sanitized provider/runtime details live under `diagnostics.realtime`.

The primary UI should not render snapshot price, snapshot time, change, or session-volume metric rows when `realtime_snapshot` is `null`.

SSI realtime is streaming-backed. The service may read from a background manager/cache only when `SSI_STREAMING_REALTIME_ENABLED=true`, lifecycle bootstrap symbols are configured, the manager is running, and the cache row is fresh. Request handlers must not open streams, stop streams, reconnect streams, or subscribe requested tickers dynamically. The lifecycle monitor may reconnect preserved bootstrap channels when a running stream becomes stale during active holiday-unaware Vietnam trading/auction windows; that recovery remains manager-owned and debounced. Outside active windows, missing or stale X/X-QUOTE/X-TRADE rows classify as market-closed/after-hours state and must not trigger reconnect solely because row counters stop advancing. When streaming runtime is disabled, bootstrap symbols are empty, config/package setup is incomplete, the manager is not started, cache is empty/stale, runtime is idle/stale/reconnecting/market-closed, or the manager is errored, the public object remains `null` and diagnostics carry the safe reason.

`GET /api/v1/stocks/vn/realtime` bypasses the generic VN response cache so each poll can reflect the latest process-local streaming cache. The streaming cache remains authoritative for freshness through optional fields such as `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, and `cache_ttl_seconds`. Frontend polling for this endpoint is separate from watchlist, company, chart, and trade-tape refresh. Unexpected realtime request errors should fail open as a normal optional unavailable realtime response, not as a daily dashboard failure.

`GET /api/v1/stocks/vn/realtime` also exposes compatible top-level `reason_code`, `classification`, and `status_message` fields. These fields classify the optional realtime state only; they must not replace `latest_price` and must not mark DailyOhlc or DailyStockPrice unavailable.

Sanitized realtime diagnostics may include `stream_health`, holiday-unaware `market_session` fields, `runtime_status`, `manager_state`, `bootstrap_status`, `channels`, `subscription_count`, `expected_subscription_count`, `bootstrap_symbols`, `bootstrap_rejected_symbols`, `messages_observed`, `parser_rows_observed`, per-context observed-row counters, `last_message_at`, `last_message_age_seconds`, `latest_error`, `last_error_at`, `idle_timeout_seconds`, `is_idle`, `idle_since`, `reconnect_enabled`, `reconnect_attempt_count`, `reconnect_count`, `last_reconnect_at`, `next_reconnect_at`, `reconnect_backoff_seconds`, `last_reconnect_reason`, and `last_reconnect_error`. `runtime_status=running_idle` or `stream_health=stale|reconnecting|failed|market_closed|idle_market_closed|after_hours_stale` is an optional realtime runtime state only; it must not mark DailyOhlc or DailyStockPrice unavailable.

### Trade Tape

When SSI trade tape has usable rows:

```text
trade_tape_status.status = ok
trade_tape_status.reason_code = buffered_rows_available, streaming_trade_tape_supported, or historical_trade_tape_supported
trade_tape = [ ... ]
```

Buffered SSI `X-TRADE:{symbol}` rows remain visible even when stream freshness is stale. In that case, diagnostics can still report `streaming_status=cache_stale`, `cache_status=stale`, `latest_trade_age_seconds`, `trade_tape_buffer_row_count`, and `trade_tape_returned_row_count`, but stale freshness is not a visibility gate because every trade row carries its own traded timestamp.

Usable trade rows expose the current matched-order fields:

* `timestamp` and `timestamp_display`
* `side` as `buy`, `sell`, or `null`
* `side_label` as `Buy`, `Sell`, or `null`
* `price`
* `volume`
* `change`
* `change_pct`
* `source`

`side` is normalized only from explicit SSI `X-TRADE` side/aggressor fields such as `Side`, `MatchType`, or `BuySell`. Observed SSI raw codes include `BU = buy` and `SD = sell`; legacy/localized explicit codes such as `B`, `BUY`, `MUA`, `1`, `S`, `SELL`, `BAN`, `BÁN`, and `2` remain supported. Unknown side values remain `null`, and the raw candidate is preserved in `side_if_available` for audit. The backend and UI must not infer Buy/Sell from SSI board price color or positive/negative `change`; a `sell` row can still have positive price-vs-reference change. `change` and `change_pct` are calculated from trade price versus positive SSI DailyStockPrice `reference_price`; they remain null when reference is missing or non-positive.

When no trade rows exist:

```text
trade_tape_status.status = unavailable or disabled
trade_tape_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, stream_cache_stale, latest_trade_stream_only, unavailable_no_rows, unavailable_provider_error, unavailable_unknown, not_implemented, or unknown
trade_tape = []
```

`trade_tape_status.message` is short user-facing copy such as `SSI trade tape unavailable.`, `SSI trade tape disabled.`, or `No SSI trade rows available.` Technical details are not embedded in this message.

The watchlist and company public contracts both use a list for `trade_tape`; company status is separate in `trade_tape_status`. Company realtime follows the same split with `realtime_snapshot` and `realtime_status`. Phase 4.7C allows only process-local, streaming-backed `X-TRADE` events to populate `trade_tape` when the background SSI streaming manager is enabled, running, symbol-bootstrapped, and the per-symbol buffer contains parsed trade events. Phase 4.8E registers `X-TRADE:{symbol}` at startup alongside realtime `X:{symbol}` when trade tape is enabled and exposes diagnostics for not-subscribed, subscribed-empty, stale, and cache-hit states. Phase 4.8E-2 makes freshness diagnostic-only when buffered rows exist. Request handlers only read this buffer; they must not start streams, add subscriptions, or use `X:ALL`.

Each streaming trade row is latest-event tape data, not historical time-and-sales history. Public rows may include `ticker`, `price`, `volume`, `value`, `side`, `timestamp`, `timestamp_display`, `source`, `sequence`, and `raw_type`, plus compatibility aliases such as `time`, `side_if_available`, and `sequence_if_available`. Price, volume, and timestamp are required; rows missing any of those fields are dropped. `X-QUOTE` and `X` snapshot messages do not create trade-tape rows. `GET /api/v1/stocks/vn/realtime/trades` retains its top-level `trades` list plus short `status_message`; sanitized technical detail lives in its `diagnostics` object.

### Order Book / Bid-Ask Ladder

SSI `X-QUOTE:{symbol}` order-book context is an optional live watchlist block. It is produced only by the background streaming lifecycle and a dedicated process-local latest-row cache.

When SSI `X-QUOTE` has a usable fresh cached row:

```text
order_book_status.status = ok
order_book_status.reason_code = cache_hit
order_book = { ... }
```

When SSI `X-QUOTE` has a stale but usable cached row:

```text
order_book_status.status = stale
order_book_status.reason_code = stream_cache_stale
order_book = { ... is_stale=true ... }
```

The `order_book` object may include `ticker`, `symbol`, `exchange`, `bids`, `asks`, `trading_date`, `time`, `stream_timestamp`, `stream_data_type=X-QUOTE`, `r_type`, `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, and `cache_ttl_seconds`. Each `bids[]` / `asks[]` level may include `level`, `price`, and `volume`. A usable level requires positive `price` and nonnegative `volume`; malformed or empty levels are dropped and never replaced with fake placeholders.

When no usable row exists:

```text
order_book_status.status = unavailable or disabled
order_book_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, xquote_not_subscribed, xquote_disabled, unavailable_unknown, or unknown
order_book = null
```

`X-QUOTE` rows must not populate `latest_price`, `realtime_snapshot`, `trade_tape`, `session_status`, `foreign_room`, DailyOhlc, DailyStockPrice, or indicators. Request handlers must not start streams, add dynamic subscriptions, or use all-market channels. Price/volume units, market-specific level counts, empty-book behavior, and UI product rendering still require live evidence before stronger product claims.

### Foreign Room

SSI `R:{symbol}` foreign-room context is an optional live watchlist block. It is produced only by the background streaming lifecycle and a dedicated process-local latest-row cache.

When SSI `R` has a usable cached row:

```text
foreign_room_status.status = ok
foreign_room_status.reason_code = cache_hit
foreign_room = { ... }
```

The `foreign_room` object may include `ticker`, `symbol`, `exchange`, `total_room`, `current_room`, `foreign_buy_volume`, `foreign_sell_volume`, `foreign_buy_value`, `foreign_sell_value`, `trading_date`, `time`, `stream_timestamp`, `stream_data_type=R`, `r_type`, `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, `cache_ttl_seconds`, and `value_semantics_status`. Numeric room/volume/value fields must be valid nonnegative numbers when present; malformed fields are set null/dropped and rows with no usable R metric are unavailable.

When no usable row exists:

```text
foreign_room_status.status = unavailable or disabled
foreign_room_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, stream_cache_stale, r_not_subscribed, r_disabled, unavailable_unknown, or unknown
foreign_room = null
```

`R` rows must not populate `latest_price`, `realtime_snapshot`, `trade_tape`, `order_book`, `session_status`, DailyOhlc, DailyStockPrice, or indicators. They also do not replace DailyStockPrice daily foreign buy/sell/net enrichment. Request handlers must not start streams, add dynamic subscriptions, or use all-market channels. Foreign buy/sell value units and any exchange-specific approximate-value semantics remain `needs_semantics_proof` until live payload evidence confirms them.

### Trading Session / Status

SSI `F:{symbol}` session/status context is an optional live watchlist block. It is produced only by the background streaming lifecycle and a dedicated process-local cache.

When SSI `F` has a usable cached row:

```text
session_status_status.status = ok
session_status_status.reason_code = cache_hit
session_status = { ... }
```

The `session_status` object may include `ticker`, `symbol`, `exchange`, `trading_date`, `time`, `trading_session`, `trading_status`, `stream_timestamp`, `stream_data_type=F`, `r_type`, `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, and `cache_ttl_seconds`.

When no usable row exists:

```text
session_status_status.status = unavailable or disabled
session_status_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, stream_cache_stale, f_not_subscribed, f_disabled, unavailable_unknown, or unknown
session_status = null
```

`trading_session` and `trading_status` preserve raw SSI-observed values. The public contract does not map them to business labels such as open, closed, halted, suspended, lunch break, or final until live payload evidence proves exact meanings. `F` rows must not populate `latest_price`, `realtime_snapshot`, `trade_tape`, DailyOhlc, DailyStockPrice, or indicators. Request handlers must not start streams, add dynamic subscriptions, or use all-market channels.

### Market Index Pulse

SSI `MI:{index_code}` market-index pulse is an optional live index block. It is produced only by the background streaming lifecycle and a dedicated process-local market-index cache.

When SSI `MI` has usable cached rows:

```text
market_index_pulse_status.status = ok or partial
market_index_pulse_status.reason_code = cache_hit
market_index_pulse = [ ... ]
```

Each `market_index_pulse[]` row may include `index_code`, `exchange`, `index_value`, `estimated_index_value`, `change`, `change_pct`, `total_trades`, `total_volume`, `total_value`, `advances`, `unchanged`, `declines`, `trading_date`, `time`, `stream_timestamp`, `stream_data_type=MI`, `r_type`, `age_seconds`, `is_stale`, `stale_reason`, `cached_at`, `cache_ttl_seconds`, `channel_format_status`, and `value_semantics_status`. Positive index values and nonnegative totals/breadth counts are required when present; malformed numeric fields are set null/dropped, and rows with no usable MI metric are unavailable.

When no usable row exists:

```text
market_index_pulse_status.status = unavailable or disabled
market_index_pulse_status.reason_code = disabled, stream_not_started, stream_not_bootstrapped, stream_cache_empty, stream_cache_stale, mi_not_subscribed, mi_disabled, unavailable_unknown, or unknown
market_index_pulse = []
```

`MI` rows are exposed through the separate market-index pulse endpoint. They must not populate stock watchlist rows, `latest_price`, `realtime_snapshot`, `trade_tape`, `order_book`, `foreign_room`, `session_status`, DailyOhlc, DailyStockPrice, or REST DailyIndex rows. Request handlers must not start streams, add dynamic subscriptions, or use all-market channels. The `MI:{index_code}` channel format and value/breadth units remain `needs_live_proof` until market-hours live payload evidence confirms exact SSI semantics.

### Diagnostics

Diagnostics may include:

* Attempted endpoint names.
* Last endpoint.
* HTTP status.
* Provider status code.
* Retryable flag.
* Failure classification.
* Cooldown or reconnect backoff timing.
* A bounded sanitized provider-error summary.

Watchlist/company live diagnostics use:

```text
diagnostics.realtime = { ... }
diagnostics.trade_tape = { ... }
diagnostics.session_status = { ... }
diagnostics.order_book = { ... }
```

Status blocks do not carry endpoint dumps or raw provider messages. Diagnostics must not contain tokens, Authorization headers, cookies, account IDs, consumer credentials, full provider bodies, or stack traces. Secret-like diagnostic strings are redacted and URLs in provider summaries are collapsed.
* Stale-date details.
* Row counts.
* Normalized keys.
* Realtime failure mode such as `rest_unsupported`, `streaming_disabled`, `streaming_manager_not_started`, `streaming_cache_empty`, `streaming_cache_stale`, `streaming_manager_error`, `live_adapter_not_enabled`, or `streaming_parsed_rows`.
* Realtime manager/cache fields such as `streaming_status`, `manager_state`, `cache_status`, `parsed_streaming_rows`, and cache age or stale reason.
* Intraday failure mode such as `rate_limited`, `bad_request_params`, `auth_failed`, `permission_denied`, `timeout`, `network_error`, `parse_failed`, `provider_unavailable`, or `empty_response`.
* Intraday request diagnostics such as `endpoint=IntradayOhlc`, HTTP status, provider code, requested timeframe, internal request page size, and public candle limit.
* Sanitized provider error summaries.

Diagnostics must not include:

* SSI credentials.
* Tokens.
* Auth headers.
* Account IDs.
* Raw auth responses.
* Full raw provider payloads.

## News Contract

VN news is disabled by default. The `vnstock_news` selection remains a
legal/terms gate, not a crawler. Optional `vnstock_news_personal` and
`vnstock_community` modes exist only for local/personal research under their
separate enablement and source boundaries; neither is a universal hosted
production provider.

Current public shape:

```text
news = []
news_status.status = disabled
news_status.source = disabled
```

When `VN_NEWS_PROVIDER=vnstock_news` is explicitly selected before written commercial and source-owner terms are recorded:

```text
news = []
news_status.status = unavailable
news_status.source = Vnstock News
news_status.provider = vnstock_news
news_status.reason_code = blocked_pending_terms
news_status.rights_status = blocked_pending_terms
```

When `VN_NEWS_PROVIDER=vnstock_news_personal` and `VNSTOCK_NEWS_PERSONAL_ENABLED=true` are selected locally, the service may lazily import the optional `vnstock_news` package and use only the documented RSS `Crawler.get_articles_from_feed` path with bounded sites, per-site limits, and process-local TTL cache. If the package is missing or fetch fails, `news=[]` and `news_status.status=unavailable` with `provider_package_missing`, `provider_error`, or `provider_no_items`.

`VN_NEWS_PROVIDER=vnstock_community` is a separate local/personal ticker-news mode using the installed free `vnstock` Community package. It may call only `Reference().company(ticker).news()` for an explicit selected/company ticker, never for every watchlist row. It returns at most three rows and uses a bounded 30-minute per-ticker cache. Success is `status=ok`, `reason_code=community_news_ready`; unavailable states include `invalid_ticker`, `provider_package_missing`, `provider_timeout`, `provider_error`, and `provider_no_items`. General force refresh does not bypass this news cache.

Personal-mode rows must include source URL/provenance and carry:

```text
news_status.provider = vnstock_news_personal
news_status.provider_mode = local_personal_research_only
news_status.rights_status = personal_research_only
```

Full article `content` is omitted by default. Ticker relevance is weak exact-symbol matching in title/summary only for the Sponsor RSS mode; it is not official ticker tagging. Community rows are already requested for the explicit ticker, but do not fabricate ticker metadata beyond that request context. Community `head` is unverified and is not exposed as a summary/source. A relative Community URL remains `raw_url`; `url=null` until a verified provider-specific article origin exists. An absolute `url` is exposed only after HTTP(S), hostname, and credential validation; the UI never uses `raw_url` as a link target.

News disabled/unavailable state must not be treated as a daily market-data failure. Mozyfin is not a VN runtime news fallback.

Phase 5.1B adds the explicit Vnstock status gate and offline normalization contract. Phase 5.1B-Local adds only an optional local personal RSS mode. Phase 5.1C adds a separate bounded Community ticker-news adapter. None of these modes adds credentials, market-data provider behavior, fallback provider, hosted production approval, or SSI ownership changes.

Future normalized news rows should include:

| Field | Rule |
| --- | --- |
| `id` | Stable dashboard item ID derived from provider namespace and item identity. |
| `title` | Required for a usable row. |
| `summary` | Nullable; only populated when supplied and licensed for display. |
| `source` | Publisher/source label. |
| `source_url` | Nullable but preferred for attribution and deduplication. |
| `published_at` | Provider publication timestamp; ingestion time must not replace it. |
| `tickers` | Normalized ticker list; empty list is allowed for market-wide news. |
| `market` | Market label such as `VN` when applicable. |
| `category` | Normalized category such as company, market, macro, industry, policy, earnings, corporate actions, disclosure, or other. |
| `language` | Provider language code when available. |
| `provider` | Provider adapter label. |
| `provider_item_id` | Provider-native ID when available. |
| `ingested_at` | Dashboard ingestion timestamp. |
| `sentiment` | Null unless the provider supplies a licensed methodology. |
| `importance` | Null unless the provider supplies a licensed methodology. |

Before any live news adapter is implemented, the provider must have written entitlement, production API/auth details, rate limits/SLA, display/storage/redistribution rights, full-text versus headline/summary/link rules, attribution requirements, source URL/provenance behavior, ticker mapping, historical depth, incremental update filters, Vietnamese encoding/timezone handling, and a sanitized licensed fixture.

## Future Module Contract

Future enrichment modules such as financials, corporate actions, events, ownership, and richer profile details may remain typed compatibility fields while implementation is pending. Fundamentally unsupported empty cards are hidden from the company page. If a future module is exposed, its status may be:

```text
disabled
not_configured
not_implemented
unavailable
partial
ok
error
```

Rules:

* `not_implemented` means no provider integration exists yet.
* `not_configured` means a future provider name was selected but no authorized adapter is wired.
* `disabled` means the feature exists but is intentionally off.
* `unavailable` means the feature is enabled or attempted but no usable data was returned.
* Placeholder future sections must use `null` for missing objects and `[]` for missing lists.
* Future-module placeholders must not be rendered as provider failures or daily-data failures.

### CorporateActionsProvider Contract

Phase 5.0B adds a contract proof only. It does not add a live external provider.

`GET /api/v1/stocks/vn/corporate-actions` returns:

* `status`: `disabled`, `not_configured`, `not_implemented`, `unavailable`, `partial`, `ok`, or `error`.
* `source`: `CorporateActionsProvider disabled` when the default disabled provider is used, otherwise the future provider contract source.
* `provider`: a sanitized provider label such as `disabled` or a future configured provider name.
* `events`: canonical normalized corporate-action rows, or `[]` when no verified rows exist.
* `items`: backward-compatible alias derived from `events`.
* `diagnostics`: sanitized provider diagnostics only.

Normalized event rows may include `ticker`, `event_id`, `event_type`, `event_subtype`, `title`, `announcement_date`, `ex_date`, `record_date`, `payment_date`, `effective_date`, `cash_dividend_per_share`, `cash_dividend_currency`, `stock_dividend_ratio`, `bonus_share_ratio`, `rights_issue_ratio`, `rights_issue_price`, `split_ratio`, `source`, `source_url`, `source_document_url`, `provider`, `provider_event_id`, `last_updated`, `raw_available`, `confidence`, `status`, and `missing_fields`. Compatibility aliases `rights_ratio`, `description`, and `last_checked_at` may remain while existing UI code migrates.

Corporate-action diagnostics may include provider, request domain, status, row count, failure class, last checked time, and requested ticker count. They must not include raw provider bodies, tokens, auth headers, API keys, account IDs, commercial credentials, or raw auth responses.

Disabled, not-configured, unavailable, and provider-error states must keep `events=[]` and `items=[]`. They must not imply the ticker has no corporate actions; they mean no verified provider rows are available to this dashboard.

Future adapters must treat `events` as the only canonical event list. If an adapter or legacy caller provides both `events` and `items`, the service/API keeps `events` and derives `items` from it so the two lists cannot diverge.

## Source Ownership

The SSI-first rule is: if SSI can provide a market-data field, SSI owns it; if a metric can be calculated from SSI-owned data, calculate it internally and label it as SSI-derived/internal. External providers are limited to domains SSI cannot provide or cannot legally/technically support with verified semantics. The canonical ownership matrix lives in `docs/SSI_DATA_CAPABILITY_MATRIX.md`.

| Data block | Owner | Public rule |
| --- | --- | --- |
| Daily OHLCV | SSI DailyOhlc | Canonical daily close and chart candles |
| `latest_price` | Conditional SSI canonical selection | Newer dated DailyStockPrice close when DailyOhlc is materially stale; otherwise a reliable normalized quote when present; otherwise DailyOhlc close. Null when none is usable. The source/date/finality remain explicit. |
| Reference/ceiling/floor | SSI DailyStockPrice | Use when available |
| Matched volume/value | SSI DailyStockPrice | Use when available |
| Put-through volume/value | SSI DailyStockPrice | Use when available |
| Latest foreign flow | SSI DailyStockPrice | Use latest matched-date row when available |
| Foreign 5D/20D flow | SSI DailyStockPrice | Compute only from returned recent DailyStockPrice `foreign_net_volume` rows; null when history is insufficient |
| Technical indicators and SSI-derived metrics | SSI-derived internal | MA20/MA50, RSI14, Bollinger 20,2, 20D average volume, 20D high/low, volume ratio, 52W high/low, 10D average volume, 3M average volume, price-vs-reference %, daily range %, and short-term D1 zones are derived from SSI DailyOhlc and DailyStockPrice inputs where applicable and must not use external provider substitutes |
| Deferred beta / market cap | SSI-derived or source-labeled after proof | Beta requires verified SSI index data and methodology; market cap requires verified share-count semantics before calculation |
| Index list | SSI IndexList | Use SSI-returned index codes and identifiers |
| Daily index | SSI DailyIndex | Optional index value/change/liquidity/breadth rows only after exact IndexList resolution |
| Index components | SSI IndexComponents | Use an explicit normalized index code directly; expose rows only when SSI returns exact usable members |
| Symbol metadata | SSI SecuritiesDetails, then SSI Securities fallback | Optional fields remain null; metadata availability/quality never changes daily validity |
| Intraday candles | SSI IntradayOhlc | Strict source; no fallback |
| Realtime snapshot | SSI FastConnect streaming realtime contract | Parser, manager/cache, official-client adapter, and FastAPI startup bootstrap exist behind disabled-by-default config; request handlers read process-local cache only |
| Trade tape / latest trade events | SSI streaming X-TRADE event buffer | Fresh bootstrapped X-TRADE rows may populate latest-event tape; full historical time-and-sales remains unverified |
| SSI `X-QUOTE` stream | SSI streaming runtime proof | Order-book context may appear in watchlist `order_book`; level-count/unit proof and UI remain deferred and must not affect price ownership |
| SSI `R` stream | SSI streaming runtime proof | Foreign-room context may appear in watchlist `foreign_room`; value-unit/approximation proof and UI remain deferred and must not replace DailyStockPrice foreign flow |
| SSI `F` stream | SSI streaming runtime proof | Raw trading session/status context may appear in watchlist `session_status`; code meanings and finality labels remain deferred and must not affect price ownership |
| SSI `MI` stream | SSI streaming runtime proof | Market-index pulse may appear in `market_index_pulse`; channel/field live proof and UI remain deferred and must not replace DailyIndex or affect price ownership |
| Future SSI `B` stream | SSI streaming after runtime proof | Realtime bars must remain separate source-labeled blocks; no fake placeholders and no request-handler stream starts |
| Future SSI extended instrument metadata | SSI SecuritiesDetails/Securities after runtime proof | Derivative, covered warrant, ETF/fund, and bond fields require exact row-key evidence and instrument-specific semantics before exposure |
| News | Separate optional NewsProvider boundary | Disabled by default; `vnstock_news` is unavailable with `blocked_pending_terms`; `vnstock_news_personal` and `vnstock_community` are optional local/personal implementations with separate gates and are not universal hosted production providers |
| Financials | Future external provider | Not implemented |
| Corporate actions | `CorporateActionsProvider` future external boundary | Disabled/not configured by default; no inference |
| Mozyfin | Disabled for VN runtime | No fallback |
| KBS | Legacy optional only | Disabled by default |

Compatibility aliases must stay within the same source owner. The only
DailyStockPrice close promotion permitted for `latest_price` is the documented
service branch where DailyOhlc is materially stale and the DailyStockPrice row
is dated and usable. Do not use DailyOhlc volume to fill matched volume, and do
not use trade-tape, Mozyfin, or KBS values to fill daily fields.

Future SSI-backed fields from Phase 4.8F must be additive and explicit. Public rows need source labels, availability status, missing-field/null semantics, and sanitized diagnostics. Missing streaming data must stay `null` or `[]` rather than placeholder metrics, and external providers must not fill order book, trading status, foreign room, market-index pulse, realtime bars, or SSI-returned instrument metadata while SSI can provide those fields.

## Index Data Contract

Index data is optional and independent of watchlist/company daily validity:

* IndexList unavailable: `rows=[]`, `status=unavailable`.
* DailyIndex unavailable: `rows=[]`, `status=unavailable`.
* IndexComponents unavailable: `rows=[]`, `status=unavailable`.
* Missing optional index fields remain `null`; provider zero values remain zero.
* DailyIndex `date_match` compares requested indexes with the newest DailyIndex date in the same response. It does not assert exchange-session finality.
* Exact SSI IndexList identifiers remain required for DailyIndex discovery. An explicit IndexComponents `index_code` is attempted directly through SSI `indexCode`; IndexList failure does not block that request.
* Diagnostics may include endpoint, requested market/code, selected identifier, IndexList status (`not_required` for explicit IndexComponents), normalized row count, field coverage, missing fields, failure class, and sanitized process-cache status/TTL/key fields. Raw provider payloads and authentication data are excluded.

## Symbol Metadata Contract

`symbol_metadata.status` describes provider availability and remains `ok` or `unavailable`. `quality_status` separately describes field completeness as `complete`, `partial`, `unknown`, or `unavailable`.

The metadata block exposes nullable `symbol`, `exchange`, `market`, `name`, `name_en`, `industry`, `sector`, `security_type`, `issuer`, `lot_size`, `listed_shares`, and `listed_date`, plus:

* `completeness`: covered-field ratio from `0` to `1`.
* `missing_fields`: normalized optional fields with no SSI value.
* `field_coverage`: per-field boolean coverage.
* `source`: the selected SSI provider label.
* `source_endpoint`, `provider_version`, `fetched_at`, `cache_status`, `data_state`, and `failure_class`: sanitized exact-symbol provenance and availability.
* `diagnostics`: sanitized endpoint attempts, row counts, selection source, and failure class.

V3 exact-symbol `securitiesByBoard?symbol=` is the metadata source. A row is usable only when its normalized symbol exactly matches the requested ticker. Do not infer missing names, industry, sector, issuer, or listing fields from the ticker, exchange, prices, or another provider.

### DailyStockPrice Enrichment Contract

`daily_stock_price.status` records provider-row availability. `daily_stock_price.quality_status` is `ok`, `partial`, or `unavailable`; it does not downgrade a usable SSI DailyOhlc row.

Date alignment is exposed through `daily_stock_price.date`, `daily_stock_price.date_match`, and the compatibility fields `daily_stock_price_date`, `daily_stock_price_date_match`, and `daily_stock_price_staleness_reason`. Date-match values are `matched`, `mismatched`, `unknown`, or `unavailable`. Missing dates are `unknown`; failed or empty DailyStockPrice requests are `unavailable`.

`missing_fields` and `field_coverage` describe normalized enrichment completeness. `units` includes only fields whose values exist, so units metadata is not evidence that a null field is available. Price/value fields use VND; volume fields use shares. Zero returned by SSI remains zero, while missing values remain null.

The watchlist indicators expose bounded recent foreign-flow summaries as `foreign_net_5d_latest_available`, `foreign_net_20d_latest_available`, `foreign_net_latest_available_date`, and `foreign_net_history_count`. These values are derived only from the existing per-symbol recent DailyStockPrice rows and `foreign_net_volume` in shares. They stay null when fewer than the required 5 or 20 returned rows have usable net volume; they do not mix value and volume units.

Sanitized `daily_stock_price.diagnostics` may include endpoint name, requested symbol/date range, normalized row count, selected row date, DailyOhlc date, date match, DailyStockPrice foreign-history row counts/date span/status, missing fields, field coverage, and failure class. It must not include raw provider payloads, credentials, tokens, auth headers, account identifiers, or raw auth responses.

### Foreign Flow Contract (Phase 4.12)

Phase 4.12A-Lite verifies the SSI DailyStockPrice **symbol daily** slice. Phase 4.12B implements the dedicated historical symbol API; frontend, current-session, ranking, and aggregate designs remain planned and not implemented. The full design and evidence matrix are in `docs/VN_FOREIGN_FLOW_PLAN.md`.

The verified canonical fields are `foreign_buy_volume`, `foreign_sell_volume`, `foreign_net_volume`, `foreign_buy_value`, `foreign_sell_value`, and `foreign_net_value`. Raw SSI fields are `ForeignBuyVolTotal`, `ForeignSellVolTotal`, `NetBuySellVol`, `ForeignBuyValTotal`, `ForeignSellValTotal`, and `NetBuySellVal`. Volume is shares and value is VND; StockClock parses the raw numeric strings without scaling. Direct SSI net is preferred. Net may be calculated as official buy minus official sell only when direct net is absent and both inputs have the same symbol, trading date, source, unit, and finality; otherwise it remains null. Missing value must not be estimated from volume and price.

`TradingDate` is the authoritative row date. Existing 5D/20D fields are rolling sums over the latest five/twenty distinct dated rows with usable `foreign_net_volume`; they are not provider-supplied aggregates. The latest provider date participates in those windows when usable. Official date-range/paging parameters make a bounded 60-session implementation feasible, but the current service still requests 28 calendar days and retains at most 20 history rows.

Foreign-flow results separate these dimensions:

- `availability_status`: `loading`, `ready`, `partial`, `stale`, or `unavailable`.
- `finality`: `daily_available` for the verified DailyStockPrice slice; future `current_provisional` or stronger final labels require separate evidence; null when no authoritative row exists.
- `market_state`: `active`, `market_closed`, or `unknown`.
- `freshness_status`: `fresh`, `stale`, or `unknown`.
- `aggregation_status`: `complete`, `partial`, `unavailable`, or null for non-aggregates.

Zero means the provider explicitly reported zero or two compatible official inputs produced a zero net. Null means absent, unverified, incompatible, or unavailable. A missing row is not a zero-flow session. Partial aggregates retain their covered subset but must expose `aggregation_basis`, expected/covered/missing component counts, missing symbols, and `coverage_ratio`; they are never extrapolated.

`GET /api/v1/stocks/vn/foreign-flow/symbol/{ticker}` implements only the verified historical symbol slice. It accepts either recent sessions (`limit`, default 20, maximum 120) or a paired inclusive `from_date`/`to_date` range (maximum 168 calendar days); mixing the modes is HTTP 422. Responses identify `ssi_fastconnect`, `daily_stock_price`, shares, VND, and `daily_available`; return ascending unique provider trading dates, `latest_row`, request/coverage metadata, and null-aware 5/20/60-session windows. Direct net wins over any side-derived mismatch. Fallback net is calculated only when both buy and sell are non-null. Missing trading dates are not synthesized, and date-range completeness is not inferred from calendar days.

The endpoint uses a dedicated bounded process-local cache and same-key coalescing. Positive current/completed, empty, and unavailable entries have distinct TTL classes; failed refresh may preserve a usable bounded stale positive result without changing its original fetch timestamp. The broad observability route exposes sanitized counters and no rows. Current-session flow, reconciliation, VN30/HOSE aggregation, and persistence remain unimplemented. SSI `R` remains a separate foreign-room contract and cannot populate foreign flow. Current provisional data cannot silently replace an accepted daily row.

`POST /api/v1/stocks/vn/foreign-flow/batch` implements the Phase 4.12D-1 daily watchlist slice. It accepts 1-30 normalized unique tickers, `top_n` from 1-10, and optional force refresh. It calls the Phase 4.12B symbol service with a 20-session target, preserves normalized request order, isolates each symbol failure, and returns no history arrays. Each result exposes the latest daily buy/sell/net volume and value, 5-session/20-session cumulative net volume/value, coverage/completeness, data state, freshness, source, and `daily_available` finality.

`GET /api/v1/stocks/vn/foreign-flow/vn30` implements the current-membership VN30 decomposition. Membership is exact, ordered, normalized SSI IndexComponents `VN30`; unavailable, empty, or mismatched membership returns no component history calls, rows, series, or rankings. Usable component histories are resolved with concurrency at most four and aligned to the union of provider trading dates capped to the latest 60. Missing component-date rows do not contribute and reduce coverage; explicit zero contributes and is neutral breadth. Latest/5/20/60 windows use that same date axis. Buy, sell, and net fields are summed independently for value and volume; value is never inferred from volume and price. Daily `value_coverage`/`volume_coverage` and `value_breadth`/`volume_breadth` are separate. The basis is `current_vn30_membership`, `historical_constituent_correct=false`, finality is `daily_available`, values are VND, and volumes are shares. A proven direct-index unsupported capability remains secondary rather than blanking usable decomposition.

### VN30 price breadth

`GET /api/v1/stocks/vn/market-breadth?index_code=VN30` is derived only from exact current SSI IndexComponents membership and SSI DailyOhlc. Membership must normalize to exactly 30 unique symbols; otherwise the response is unavailable and no member histories are fetched. Histories request 55 rows over a bounded 120-calendar-day lookback, reuse the DailyOhlc cache/single-flight path, and use at most four workers. The canonical breadth date is the modal latest provider date across observed members, choosing the latest date on a tie. Older/latest-mismatched members are excluded without forward-fill.

Direction compares the canonical-session finite positive close with the immediately previous usable provider-session close. MA20/MA50 reuse `calculate_vietnam_indicators`, so each test is `close > SMA(close, N)` and equality is not above. Direction, MA20, and MA50 each own an independent usable denominator. Percent above is `above / usable * 100`; participation is `(advances + declines) / direction_usable_count`. A zero denominator returns null. Coverage exposes observed, aligned, usable, missing, and session-mismatch counts/symbols. Finality follows the provider session relative to the adapter's latest completed session; cache freshness remains separate. This is a current-membership cohort and `historical_constituent_correct=false`. No full watchlist hydration, provider fallback, MI/foreign-flow substitution, volume/value breadth, or HOSE universe is part of this contract.

Positive runtime acceptance on 2026-08-11 returned 30 exact current members and 30 aligned histories for completed provider session 2026-08-10. Direction reconciled as 24 advance + 4 decline + 2 unchanged = 30 usable; MA20 reconciled as 25 above + 5 not above = 30 usable; MA50 reconciled as 15 above + 15 not above = 30 usable; participation was `(24 + 4) / 30 = 93.33%`. Missing and session-mismatch counts were zero. The cold request used 30 DailyOhlc provider calls at maximum concurrency four; the immediate warm request used 30 cache hits and no provider calls. No fallback was used.

### Current-VN30 sector strength

`GET /api/v1/stocks/vn/sector-strength?index_code=VN30` composes existing
normalized primitives. Exact current VN30 membership gates all work. Provider
ICB code/name classifies each symbol into at most one group; missing metadata is
reported as unclassified and never invented. Group member counts plus
unclassified members must reconcile to 30.

The only price return in VN-SECTOR-1 is
`mean(current_close / previous_close - 1)` across usable, session-aligned
breadth members. It is equal-weight, current-cohort, and not an official sector
index. Direction and MA20/MA50 reuse breadth classifications with independent
denominators. Completed foreign net value uses accepted DailyStockPrice rows
over exactly 1, 5, or 20 returned sessions per member. A member contributes to
a window only when it has the complete requested accepted rows; no partial
member value is extrapolated. Valid explicit zero contributes zero, while
missing/incomplete and unresolved anomaly rows remain excluded. Provisional
current ForeignRoomMessage never enters these windows or historical rows.

Price session/finality and latest completed foreign-flow date are independent
provenance fields. The response remains usable when those publication dates
differ. Shared breadth, IndexComponents, DailyOhlc, completed-flow cache, and
single-flight paths are reused; there is no full watchlist hydration, fallback,
or frontend member/sector fan-out.

### Selected-stock relative performance

`GET /api/v1/stocks/vn/relative-strength/{ticker}` compares one normalized
selected ticker over independent 1, 5, and 20 provider-session windows. Stock
and peer closes come only from SSI DailyOhlc. VNINDEX and VN30 values come only
from exact-date SSI V3 `indexSummary.indexValue`; a missing provider point
remains missing and is not replaced by a synthetic, reconstructed, or external
series.

For each market benchmark, the service intersects the stock and benchmark
provider dates, selects the latest `N + 1` exact common sessions, and calculates
`return_pct = (end / start - 1) * 100`. Relative performance is the transparent
percentage-point difference `stock_return_pct - benchmark_return_pct`. There
is no forward-fill, interpolation, calendar-day substitution, beta, alpha,
composite score, or recommendation.

Industry uses current SSI VN30 IndexComponents classification. Peers are the
other current VN30 members with the same non-empty provider ICB code, excluding
the selected ticker. Each usable peer must have both of the selected stock's
exact start/end provider sessions; the benchmark return is their equal-weight
arithmetic mean. Missing peers reduce coverage and produce partial state. No
usable peer produces unavailable state, not zero. This proxy is
`historical_constituent_correct=false`, `official_sector_index_return=false`,
and must never be labelled an official industry index.

The response exposes comparison/window states, exact start/end sessions,
underlying stock and benchmark returns, relative percentage points, peer
membership/coverage, provenance, bounded timing, and sanitized provider/cache
counters. Index points use a 300-second positive and 60-second negative
process cache with same-key single-flight; symbol histories and membership
reuse their existing caches. `force_refresh=true` intentionally bypasses fresh
entries. Missing metrics are null. `latest_price` ownership is unchanged.

Foreign Flow Explorer v1 applies a shared completed-session selection contract to ticker, current VN30 basket, current-VN30 ICB industry, and supported proprietary VNINDEX/VN30/HOSE scopes. 1D/5D/20D/60D select distinct returned provider sessions; custom bounds are inclusive and limited to 120 calendar days. Metric selection is presentation-only and does not refetch when both value and volume already exist. Source session, fetched time, cache state/age, freshness, coverage, and anomaly are separate. CSV contains only selected loaded rows with raw numeric values. Current-session foreign/industry flow remains unavailable.

Top-level `fresh_count`, `stale_count`, `empty_count`, and `unavailable_count` partition normalized symbols. `usable_count` is fresh plus stale; `coverage_ratio=usable_count/normalized_count`. State precedence is: all fresh usable is `ready`; all usable stale is `stale`; all empty is `empty`; mixed usable/non-usable is `partial`; otherwise provider failure is `unavailable`. Rankings are limited to the requested watchlist and contain latest/5-session/20-session top buys and sells. Null and zero values are excluded; signed net value determines direction; ticker breaks ties; stale or incomplete eligible rows remain marked rather than being dropped. No batch field changes SSI DailyOhlc ownership of `latest_price`.

## External Provider Boundary

Phase 4.5A/5.0A do not add a live external provider. Phase 5.0B adds only a disabled-by-default `CorporateActionsProvider` contract proof. Corporate actions are the first selected domain for provider qualification, but they remain `disabled`, `not_configured`, or unavailable until the access and legal gates in `docs/VN_EXTERNAL_PROVIDER_STRATEGY.md` pass. VNStocks and FiinGroup are candidate external providers only, both `needs_verification`; they are not runtime sources, fallback providers, or implementation sources in the current contract.

External provider rules:

* External rows must carry their own provider/source labels and provenance.
* External providers must not overwrite SSI-owned daily, DailyStockPrice, intraday, realtime, index, or metadata fields silently.
* External-provider failure must preserve valid SSI watchlist/company data.
* Disabled or not-implemented list domains return `[]`; missing objects return `null`.
* Public disclosure pages are not an automation contract and must not be scraped without explicit approval and verified terms.
* A future metadata fallback may fill only SSI-null fields under explicit per-field priority and source rules.
* A future external VNINDEX value must be explicitly labeled as external and must never be presented as SSI.

## UI Rendering Rules

### Daily Data

Render daily data when the row has valid SSI DailyOhlc fields and daily status is OK. Optional section failures should not hide daily close, chart, or DailyStockPrice fields.

Frontend compact numeric formatting is presentation-only. API price fields remain raw VND/share values, but VN price-like values are displayed in board-style thousand-VND units with two decimals and no suffix, for example `72,100` becomes `72.10`. Share volumes may use `K`/`M`; VND trading values may use `K`/`M`/`B`/`T`. This formatting must not change `latest_price`, source labels, API payloads, or missing-data semantics.

The dashboard top summary `Foreign net volume` aggregates `ssi_foreign_net_volume` from the latest successful complete watchlist response and labels the unit as shares. It must not aggregate legacy `foreign_net` fallbacks, incomplete refresh rows, auxiliary realtime/trade/index/corporate-action responses, or mix volume with `ssi_foreign_net_value` in VND.

Daily volume labels should identify SSI DailyOhlc ownership, for example `Daily OHLCV volume`. Active realtime and trade-tape controls should use `Realtime snapshot`, `SSI realtime`, or `Trade tape`; KBS and Mozyfin names are allowed only in legacy diagnostics or superseded historical docs.

### Optional Live Metrics

Render optional live metrics only when actual data exists:

* Intraday metrics require `intraday_status.status = ok`, non-empty `intraday_candles`, and non-null `intraday_pulse`.
* Realtime metrics require `realtime_status.status = ok` and non-null `realtime_snapshot`.
* Trade tape requires `trade_tape_status.status = ok` and non-empty `trade_tape`.

Otherwise render concise states:

```text
SSI intraday unavailable.
SSI realtime unavailable. Daily SSI data is still available.
SSI trade tape unavailable.
```

### Diagnostics Panel

The diagnostics/data-quality panel may show endpoint details, HTTP status, retryability, and stale-date metadata. Primary cards should not show raw endpoint attempts or provider error text.

### Units Metadata

Units metadata does not prove data availability. UI availability must depend on status plus null/empty checks.

### Cache Errors

Cache errors and provider unavailable states are separate concepts. A provider 404 or unavailable live endpoint should not be shown as a daily SSI cache failure.

`cache_status.daily_stock_price_cache` may report `hit`, `miss`, `refresh`, or
`stale` for the bounded recent DailyStockPrice enrichment/history result. Its
process-local TTL is 300 seconds. `force_refresh=true` bypasses this freshness
check. Cache state alone never selects the canonical price; the documented
DailyOhlc freshness comparison and dated usable DailyStockPrice row control the
DailyStockPrice promotion branch.

IndexComponents diagnostics may report `cache_status`, `cache_ttl_seconds`, `cache_negative`, and a sanitized key containing only provider, endpoint, normalized index code, and optional market. Usable rows use a 300-second TTL. Unavailable, rate-limited, and no-row responses use a 60-second negative TTL. `force_refresh=true` bypasses this cache.

## Recently Completed Contract Cleanup

* Phase 4.7B completed: unavailable watchlist/company `trade_tape` is `[]`, status stays in `trade_tape_status`, realtime data/status stay split, and sanitized provider details live under sectioned `diagnostics` instead of status messages.
* Phase 2.1 completed: unavailable company `intraday.pulse` is `null`, not `{}`.
* Phase 4.7B completed: frontend rendering treats unavailable live objects as `null`, missing watchlist/company trade tape as `[]`, and sectioned diagnostics as diagnostics-only UI content.

## Phase 4.11B / 4.11B-3 Future Intraday Chart Contract

Phase 4.11B is documentation-only. The current watchlist/company `intraday_candles` pulse remains an optional compact SSI block; it is not the production history contract for Lightweight Charts. No intraday chart endpoint or timeframe UI exists yet.

### Evidence boundary and interval vocabulary

The installed `ssi_fc_data` 2.2.2 package defines `IntradayOhlc` and an integer `resolution` field with default `1`, but it provides no interval enum, unit definition, supported-value list, query-range limit, final-bar field, or session semantics. Its official repository sample supplies `DD/MM/YYYY` dates and `resolution=1`; the installed package itself contains no resolution mapping. The repository adapter currently accepts arbitrary request strings and has deterministic cadence fixtures for `1m`, `5m`, and `1h`; those fixtures verify StockClock normalization only, not SSI interval support.

Phase 4.11B-3 completed the evidence gate for a deliberately restricted completed-session interval. Phase 4.11C has since implemented the production public interval allowlist as exactly `1m` for one completed Vietnam date through the separate endpoint and UI.

| Public candidate | Provider candidate | Status | Rule |
| --- | --- | --- | --- |
| `1m` | `resolution=1` | `verified` for one completed HOSE session per request | Four FPT/HPG sessions produced one unique floored minute bucket per row, exact continuous-session minute cadence, exact DailyOhlc OHLC/volume reconciliation, and fewer than 1,000 rows. |
| `5m` | `resolution=5` | `unsupported_mapping` | Accepted but returned the same 226-row minute-like cadence; 0% of deltas matched 300 seconds. |
| `15m` | `resolution=15` | `unsupported_mapping` | Accepted but returned the same 226-row minute-like cadence; 0% of deltas matched 900 seconds. |
| `30m` | `resolution=30` | `unsupported_mapping` | Accepted but returned the same 226-row minute-like cadence; 0% of deltas matched 1,800 seconds. |
| `1h` | `resolution=60` | `unsupported_mapping` | Accepted but returned the same 226-row minute-like cadence; 0% of deltas matched 3,600 seconds. Existing `timeFrame=1h` hints remain non-authoritative. |

Phase 4.11B-2 used six of seven allowed provider calls to establish the request shape and reject unsupported higher-resolution mappings. Phase 4.11B-3 then used four `IntradayOhlc` and four matching `DailyOhlc` calls: FPT and HPG on completed HOSE sessions `2026-06-23` and `2026-06-24`. Every intraday request used one ticker/date, `resolution=1`, `pageIndex=1`, `pageSize=1000`, and `ascending=true`; every call succeeded with 226 rows and `totalRecord=226`. All four sessions had the identical raw fields `TradingDate`, `Time`, `Open`, `High`, `Low`, `Close`, `Volume`, `Value`, and `Symbol`.

Raw timestamps remain timezone-free `TradingDate=DD/MM/YYYY` plus `Time=HH:MM:SS`. In each sample, 225 of 226 rows had nonzero seconds, while flooring in `Asia/Ho_Chi_Minh` produced 226 unique, ascending minute buckets with no duplicate bucket, invalid timestamp, or out-of-order row. The continuous buckets were `09:15` through `11:29` and `13:00` through `14:29`; all 223 within-segment transitions were exactly 60 seconds. The apparent 11:30 and 14:30 boundary omissions are half-open session boundaries, not unexplained missing bars. A separate final `14:45:00` row was present in every sample.

The raw `Time` value is classified `likely_last_trade_time_but_not_fully_verified`: its seconds vary within the minute and consistently land near the minute end, but neither the SDK nor official sample defines it and no trade-level comparison was performed. The canonical chart timestamp is therefore the raw Vietnam wall time floored to minute start, then converted to Unix seconds. Flooring changes only placement, never OHLCV. Invalid timestamps are rejected; the four live samples had no duplicate normalized bucket, while a future duplicate uses stable last-provider-row-wins handling with a diagnostic count. The current adapter's naive-as-UTC helper is not canonical and must be corrected in Phase 4.11C.

All 904 intraday OHLC rows passed consistency validation. For every ticker/date, first open, maximum high, minimum low, and final close exactly matched the same-date SSI DailyOhlc row (zero absolute and percentage difference). The first 09:15 row also matched DailyOhlc open, and the final 14:45 row matched DailyOhlc close. This is observed reconciliation, but the exact ATO/ATC aggregation mechanism and the locations of session extrema remain ambiguous.

`Volume` was numeric, positive, non-missing, and non-cumulative in all four sessions. Per-session intraday sums exactly equalled DailyOhlc volume: FPT `5,737,500` and `5,968,500`, HPG `29,071,800` and `12,927,300`, each ratio `1.0`. This supports `likely_per_bar_shares`; because SSI's inspected materials do not explicitly define the unit, the first UI must label it neutrally as `Volume`, not assert `shares`. No missing candles are synthesized or forward-filled; Lightweight Charts must display sparse normalized timestamps as gaps. These findings are limited to FPT/HPG on HOSE and do not generalize to HNX, UPCOM, holidays, half sessions, halts, or post-close/negotiated behavior.

Phase 4.11C implements only one-date, completed-session `1m` history. Current-session bars, multiple days, pagination, higher intervals, realtime updates, aggregation, and fallback remain outside the runtime allowlist.

Aliases are case-sensitive and rejected unless added to the verified allowlist. `60m`, `1H`, numeric strings, and provider-specific spellings must not be accepted silently.

### Endpoint selection and request bounds

Phase 4.11C implements a separate endpoint rather than widening the daily endpoint:

```text
GET /api/v1/stocks/vn/intraday-chart
  ?ticker=FPT
  &interval=1m
  &date=2026-06-24
```

`/vn/chart` remains D1-only and SSI DailyOhlc-owned. The separate endpoint makes cache, source, timestamp, and diagnostics explicit without breaking the existing daily client; it has no provisional-bar behavior.

Request rules for the first implementation are deliberately narrower than the earlier range proposal:

* Public `ticker` is required, normalized uppercase, and validated with the existing VN ticker rules. The SSI provider request continues to use its own `symbol` field.
* `interval` is required and its only accepted value is `1m`; 5m/15m/30m/1h are rejected before any SSI call.
* `date` is one ISO `YYYY-MM-DD` Vietnam trading date. The backend converts it to SSI `DD/MM/YYYY` and requests only that date.
* The date must be strictly earlier than the current date in `Asia/Ho_Chi_Minh`. Current-day and future dates are rejected; same-day closed-session support remains deferred because holiday/session finality is not yet authoritative.
* The response is capped at 1,000 usable bars. One provider page uses `pageSize=1000`; multi-page behavior is not part of the first scope.
* The current process-wide provider timeout is 10 seconds per attempt.
* Intraday provider concurrency is one per process initially. Identical requests use single-flight ownership. No parameter-variant fan-out is allowed after the verified request shape is selected.
* Automatic retry count is zero in the first implementation. SSI/HTTP `429`, auth, permission, and invalid-parameter failures are never retried; the existing 60-second rate-limit cooldown remains applicable. `force_refresh=true` bypasses usable positive/negative cache lookup but not validation, single-flight, pacing, cooldown, or stale-recovery safeguards.

### Canonical response

```json
{
  "ticker": "FPT",
  "exchange": "HOSE",
  "interval": "1m",
  "timezone": "Asia/Ho_Chi_Minh",
  "status": "ready",
  "reason_code": null,
  "bars": [
    {"time": 1719800100, "open": 128000, "high": 128500, "low": 127800, "close": 128300, "volume": 125400}
  ],
  "source": {"provider": "ssi_fastconnect", "dataset": "IntradayOhlc"},
  "cache": {"status": "miss", "is_stale": false, "captured_at": "...", "expires_at": "..."},
  "diagnostics": {"requested_date": "2026-06-24", "returned_bars": 1, "rejected_rows": 0, "duplicate_timestamps": 0}
}
```

`time` is a Unix timestamp in seconds representing the floored minute start. Verified SSI fields are separate timezone-free `TradingDate` (`DD/MM/YYYY`) and `Time` (`HH:MM:SS`). They must be interpreted as `Asia/Ho_Chi_Minh` wall time, floored to the minute, and then converted; never treat them as UTC or parse them in the browser. Bars are sorted ascending and unique by `(ticker, interval, time)`. For duplicates, the last provider row in stable provider order wins and the discarded count is diagnostic.

OHLC values remain raw VND/share. Volume remains the non-negative SSI `Volume` value and is labelled `Volume`; `likely_per_bar_shares` is evidence, not a public unit guarantee. A usable row requires finite positive OHLC, `high >= max(open, close, low)`, `low <= min(open, close, high)`, and finite non-negative volume. Malformed rows are rejected individually. A response may remain `ready` when usable rows remain, with `reason_code=partial_rows_rejected`; if no usable row remains after a non-empty provider response, return `failed`, not an empty success. `is_final` is absent because completed dates are the only accepted scope.

Top-level statuses are `ready`, `unavailable`, and `failed`. Staleness belongs under `cache.is_stale` rather than a fourth top-level status:

* Explicit provider success with no rows: HTTP 200, `ready`, `bars=[]`, `reason_code=no_data`.
* Provider unavailable/rate-limited/permission failure with no usable cache: HTTP 200, `unavailable`, `bars=[]`, sanitized `reason_code`.
* Provider failure with a bounded usable stale entry: HTTP 200, `ready`, preserved bars, `cache.status=stale`, `cache.is_stale=true`, `reason_code=stale_cache_recovery`.
* Unsupported interval, current/future date, invalid date, or invalid symbol syntax: HTTP 422; do not call SSI.
* Malformed provider success with no usable bars: HTTP 502, `failed`, `bars=[]`.

### Cache and freshness design

Cache the completed provider day under an independent identity such as `intraday_chart:{ticker}:1m:{vn_trading_date}:page:1`. Do not reuse DailyOhlc cache entries, the existing compact-pulse key, or Phase 4.8S streaming snapshot persistence.

Treat completed history as immutable for the initial contract: positive entries use a 86,400-second TTL, unavailable/no-data entries use 60 seconds, usable expired history may be served stale for up to seven days after an SSI failure, and the process-local cache is capped at 500 LRU keys. There is no active/lunch/current-day cache policy in Phase 4.11C.

The existing Vietnam market-phase helper is HOSE-like and holiday-unaware. Phase 4.11C avoids that ambiguity by accepting only dates strictly before the current Vietnam date. SSI ATO/ATC mechanics, post-close/negotiated rows, suspensions, half sessions, holidays, HNX, and UPCOM remain unverified and must not be encoded as provider facts.

### Frontend ownership and source split

The future dashboard owns selected ticker, selected interval, selected completed date, request key, request ID, loading/unavailable state, and stale-response rejection. Ticker, interval, or date change invalidates the old request and clears the old presentation; only a matching `(ticker, interval, date, request_id)` response may apply. The chart component receives normalized bars and metadata and performs no request.

`1D` continues to call `/vn/chart` and use SSI DailyOhlc. The implemented `1m` option calls `/vn/intraday-chart` for Today or an available completed date and uses only SSI IntradayOhlc; current-day data is delayed bounded polling, not realtime data. DailyStockPrice, X, X-QUOTE, X-TRADE, and persisted streaming snapshots never become candles. Indicators use the active timeframe bars; Phase 4.9A zones remain daily and read `Daily S/R` over intraday history.

### Observability requirements

Phase 4.11C should count requests by public interval, provider latency, cache hit/miss/refresh/stale outcomes, returned bars, rejected rows, duplicate timestamps, provider-unavailable responses, unsupported intervals, stale recoveries, invalid/current-date rejections, and frontend ownership discards. Diagnostics may expose sanitized requested date, provider page count, returned/rejected counts, and cache age. Logs and responses must never include credentials, access tokens, authorization headers, full provider payloads, account IDs, consumer IDs, or consumer secrets.

## Phase 4.11D-1 Current-Session Source Audit

Phase 4.11D-1 is evidence and contract work only. It does not enable the current date, add polling, add a provisional schema field, aggregate X-TRADE, or change the completed-session endpoint.

On 2026-07-16, eight bounded FPT `IntradayOhlc` calls used the current Vietnam date, `resolution=1`, page 1, page size 1,000, and ascending order. Calls at 09:12:34 and 09:15:05 returned HTTP 200 with provider code `NoDataFound`. At 09:16:05, SSI returned the 09:15:59 opening row plus a 09:16:05 row for the still-open minute. Repeated calls at 09:16:30 and 09:16:55 changed that row's raw `Time`, OHLC, and volume. At 09:17:10 a newer normalized bucket existed and the prior row had advanced through 09:16:58; it remained unchanged at 09:17:30 and 09:20:05. The final sample returned six valid unique buckets, zero rejected rows, and zero duplicate normalized buckets.

SSI current-session behavior is therefore classified `provisional_current_bar`. The raw `Time` is the newest provider event time within the bucket, not its canonical bucket start. Previous-bucket finality is `inferred_finality_with_reconciliation`: a prior bucket may be treated as provisionally closed when a newer normalized bucket appears, but SSI exposes no provider finality flag and SSI remains authoritative on every refresh. `provider_finality_verified` is not claimed.

Provider-response latency was 0.423-1.116 seconds (median 0.615, sample count 8, including two valid `NoDataFound` responses). For the five repeated current-bucket observations, observation time minus normalized bucket start was approximately 5, 30, 55, 10.8, and 30 seconds (minimum 5, median 30, maximum 55, sample count 5). The first new 09:17 bucket was observed at 09:17:10 with raw time 09:17:04. This is a bounded opening-session sample, not a full-day latency SLA.

Phase 4.11D-2 implements the delayed-only gate. Current responses add `session_state`, `freshness`, `last_provider_refresh_at`, `newest_bar_age_seconds`, and `current_bar_state`. The backend uses 15-second positive, 5-second empty, 10-second negative, and five-minute stale-if-error current-date bounds; completed dates retain 24-hour/60-second/seven-day policy. The dashboard schedules one 09:15:07 opening wake-up when Today remains selected from pre-open, one absolute-time request near each eligible minute boundary plus seven seconds, one 13:00:07 afternoon baseline after lunch, and one 14:45:20 post-close reconciliation. It uses `Updating`, `Delayed`, `Stale`, `Pre-open`, `Lunch break`, `Closed`, `Completed`, or `No data yet`, never `Live`; hidden tabs and completed/D1 views do not poll.

Phase 4.11E adds `provider_snapshot_age_seconds` without replacing `newest_bar_age_seconds`. The former is current Vietnam time minus the successful fetch timestamp that produced the cached snapshot; cache hits increase it, and stale recovery preserves the original timestamp. The latter remains current Vietnam time minus the newest accepted raw SSI `TradingDate + Time`. During an active scheduled window, `updating` requires a snapshot age no greater than 30 seconds and a newest normalized bucket in the current or immediately previous minute. `stale` applies to stale-if-error data or an active-session provider snapshot older than 90 seconds. A recent snapshot with an older bucket is `delayed`; lunch does not become stale solely because no candle is expected. No current-date stale entry crosses Vietnam midnight.

The cache identity is provider-owned and contains SSI FastConnect/`IntradayOhlc`, normalized ticker, `1m`, Vietnam trading date, page 1, and page size 1,000. Concurrent requests for the exact same key share one process-local provider fetch, including normal/force overlap; a waiter never cancels the shared fetch and the in-flight entry is removed after success or failure. `force_refresh=true` still bypasses a fresh cache when no same-key fetch is active. This is worker-local coalescing, not a distributed lock.

`GET /api/v1/stocks/vn/intraday-chart/health` performs no SSI call and no cache refresh. It returns bounded worker-local request/cache/provider/data-quality/concurrency counters, latency aggregates, current Vietnam session state, and one sanitized last-provider-result snapshot; it never returns bars, cache keys, raw provider rows, exception messages, headers, accounts, or credentials. `status=unknown` means no provider attempt in that worker, `ok` means the most recent meaningful result was usable or expected no-data, and `degraded` means the latest attempt failed/was unavailable or required stale recovery. Market closed, lunch, and pre-open do not by themselves make health degraded. Metrics reset at process restart and each Render worker has independent values.

This is the canonical Phase 4.11E intraday-chart operational route. `GET /api/v1/stocks/vn/observability` remains a separate established dashboard-wide provider/cache status contract with `VietnamObservabilityResponse`; it is not an alias for intraday-chart health. OpenAPI exposes both paths with distinct response schemas, and neither route starts an SSI fetch.

A live `X-TRADE:FPT` audit observed 124 events in 30 seconds, performed one controlled disconnect/reconnect, then observed 82 events in the next 30 seconds without transport errors. Every event exposed `Symbol`, `TradingDate`, `Time`, `LastPrice`, `LastVol`, `TotalVol`, `Side`, `TradingSession`, and `TradingStatus`; none exposed a trade ID, sequence, message ID, channel sequence, correction flag, or cancel flag. Visible `(ticker,date,time,price,last-volume,side)` tuples collided 109 times across the two windows. `TotalVol` behaved as a cumulative session total and `LastVol` matched the increment when the total advanced, but repeated deliveries with unchanged `TotalVol` make raw summation unsafe. Volume is classified `likely_incremental`; ordering is `receive_order_only`; deduplication is `unsafe`; replay/gap/correction behavior is `unavailable`.

Phase 4.11D-3 is `blocked`. X-TRADE must not create or update chart candles until stable identity or ordering, replay/gap detection, correction semantics, and safe deduplication are verified. A reconnect cannot currently prove missed or replayed events, so the conservative future rule remains: suspend provisional trust, fetch a fresh SSI IntradayOhlc baseline, replace/reconcile the latest bars, then resume only after the stream is healthy. SSI wins every mismatch. X snapshot, X-QUOTE, F, R, MI, the compact pulse, DailyStockPrice, and persisted streaming snapshots are not candle sources.

Scheduled HOSE classification is clock-derived in `Asia/Ho_Chi_Minh`: pre-open before 09:15, morning 09:15-11:30, lunch 11:30-13:00, afternoon 13:00-14:30, ATC 14:30-14:45, and closed afterward or on weekends. This does not prove an exchange holiday, halt, half session, HNX, or UPCOM schedule. No bar exists without an SSI row, morning bars are never extended through lunch, successful refreshes authoritatively replace the array, and date/ticker/timeframe/request-ID ownership prevents stale responses from winning.

Late-event policy remains closed while X-TRADE is blocked. A future stream overlay may revise only the current bucket and, if later evidence supports it, the immediately previous bucket for a short measured grace period. It must bucket by provider exchange date/time in `Asia/Ho_Chi_Minh`, never receive time; never span lunch; never reopen unlimited history; and discard provisional state whenever SSI differs, omits the provisional bucket, reconnects, or changes session/date. Until a provider-backed identity/order key exists, no composite visible-field key is safe enough to accept or reject a late event.

Future current-session metadata may include `session_state`, `freshness`, `last_provider_refresh_at`, `newest_bar_age_seconds`, and `current_bar_state`, but no field is added by this audit. Recommended UI states are `Completed`, `Updating`, `Delayed`, `Reconnecting`, `Stale`, and `Closed`; `Live` remains unapproved. Future observability must count SSI requests/latency/revisions/newest-bar age, X-TRADE events/duplicates/out-of-order/sequence gaps/reconnects, reconciliation mismatches, provisional replacements, stale transitions, and current-session unavailability without logging raw payloads or credentials.

## SSI-V3-M2.6B current foreign-flow contract

`GET /api/v1/stocks/vn/foreign-flow/current/{ticker}` is an independent
provisional stream-cache read. `data_state` is `waiting`, `ready`, `stale`,
`market_closed`, `unavailable`, or `error`. `current` is null until the current
symbol/session has at least one complete buy/sell volume or value pair from an
audited `ForeignRoomMessage`.

The read may idempotently record a ticker lease on the lifecycle-owned manager.
If the shared transport is retryably failed, it may request one monitor-owned
recovery attempt; it cannot create, own, or close the provider stream.
Repeated polling, visibility resume, reload, and `force_refresh=true` preserve
the same provider cohort and share one scheduled attempt plus cooldown.
Responses set `Cache-Control: no-store, no-cache, max-age=0` and
`Pragma: no-cache`.

Each message replaces the prior symbol/session snapshot. Values are never
locally added, missing raw fields never become typed-default zero, and room
capacity never becomes flow. `latest_completed_comparison` may contain an
earlier DailyStockPrice row with completed-session finality. The provisional
row is never appended to historical daily rows or used in completed windows,
rankings, aggregates, or exports.

Completed and current foreign flow are independent capabilities. A current
stream failure with a prior valid snapshot returns that snapshot as `stale`;
without a prior snapshot, only current flow is unavailable. Neither state may
clear or downgrade usable DailyStockPrice symbol history, VN30
current-membership decomposition, completed charts/windows, rankings,
analytics, or exports. Successful connection clears the retryable stream
failure and only a newer valid provider message replaces the snapshot.

Provider session dates must come from provider market-status/trading-date
context or the provider event timestamp. A time-only event without such
context is not assigned the local calendar date.

A usable provider-dated `market_closed` snapshot remains eligible for the
presentation-only latest-session selector after the active window ends. When
its date is newer than the latest accepted DailyStockPrice date, the unified
card and ticker detail row label it `Tạm tính`. Accepted DailyStockPrice for
the same date has precedence and suppresses the provisional duplicate. This
selection does not append the provisional row to historical API data, charts,
5P/20P calculations, rankings, analytics, exports, aggregates, or persistence,
and it never derives a date from browser or server local time.

## Known Contract TODOs

### P0

* Phase 1: investigate SSI DailyOhlc vs DailyStockPrice same-date mismatch. Latest smoke observed FPT on `2026-06-22` with DailyOhlc/dashboard close fields at `70,700`, DailyStockPrice close/adjusted close at `70,800`, DailyOhlc volume at `3,642,400`, and DailyStockPrice matched volume at `3,643,500`.
### P1

* Phase 2: deprecate top-level `intraday_timeframe`.
* Phase 2: move stale intraday latest-date/date-match metadata into status/diagnostics when no usable intraday data exists.
* Phase 2 and Phase 4.0: add backoff or longer TTL for non-retryable SSI realtime/trade-tape 404 responses.

### P2

* Future selected-ticker/source-coverage work: add aliases only after sanitized SSI row-key evidence; unsupported metadata stays null.
* Future DailyStockPrice history or caching work: consider durable caching only if measured latency/rate-limit evidence requires it. The current contract already supports bounded in-memory latest-available 5D/20D foreign net volume from recent SSI DailyStockPrice rows.
* Phase 1 and Phase 2: clean quote metadata semantics when quote is disabled or unreliable.
* Phase 1: improve `final_close_status` using VN session/calendar rules.

### P3

* Phase 2 and Phase 6.0: clarify cache errors versus provider unavailable.
* Phase 2: clarify units metadata versus data availability.

### SSI streaming lifecycle status

Stream-backed responses may add `stream_state`, `last_event_at`, `event_age_seconds`, and `generation`. `stream_state` is one of `disabled`, `awaiting_subscription`, `recovering`, `ready`, `stale`, `unavailable`, `closed`, or `failed`. These fields are freshness/operations metadata only. A connected transport or successful channel switch is not ready; readiness requires an accepted current-generation event for that context. Stale/recovering rows retain their original event timestamp and must not be presented as current.

The broad `/api/v1/stocks/vn/observability` response adds `streaming.scope=process_local`, deterministic `overall_state`, one sanitized logical channel-cohort transport summary, per-context state for X/X-QUOTE/X-TRADE/F/R/MI, schedule-derived Vietnam session context, and a multi-worker limitation note. The endpoint is read-only/no-store and does not expose full subscriptions, payloads, URLs, exception text, headers, or credentials. `/intraday-chart/health` remains unchanged and contains only REST SSI IntradayOhlc worker health.

## Completed foreign-flow field integrity

Completed SSI DailyStockPrice field presence is authoritative. `FIELD_ABSENT`,
`FIELD_NULL`, `PARSE_FAILURE`, and `PROVIDER_ROW_MISSING` remain `null` even
when an SDK/model default is numeric zero. `FIELD_PRESENT_EXPLICIT_ZERO`
remains zero. A completed row with any missing gross foreign-flow field is
`data_quality=incomplete`, `complete=false`, and displays `Thiếu dữ liệu`;
it remains inspectable but is excluded from complete-only charts, rolling
windows, analytics, and rankings. CSV output leaves missing values empty.

An all-constituent explicit-zero VN30 aggregate is a separate cross-symbol
anomaly, not a legitimate completed zero session. It triggers a bounded
exact-date `securitiesSummary?symbol=` verification through the shared SSI V3
REST provider. Same-date evidence uses deterministic strength ordering, and a
weaker broad-range zero or partial row cannot overwrite a stronger repaired or
durably accepted row. Successful exact-date repairs persist atomically with
repair provenance. If SSI still returns zero, no row, null fields, or an error,
the aggregate remains `data_quality=anomalous`, `complete=false`, and
`valid_session=false`, with all `usable_for_*` flags false and public aggregate
numbers null. Repair results are single-flight, cooldown-bound, and permit one
manual Force Refresh bypass per cooldown episode.

The Proprietary mode is an explicit unsupported capability until an official
SSI contract exposes proven securities-company own-account flow fields.
`indexSummary` is market-index summary data and must not be reinterpreted as
proprietary flow. Unsupported responses contain no rows, coverage, chart,
ranking, or export data.

Industry current detail uses the canonical `current-aggregate.aggregate` row.
`current-aggregate.groups` remains the group-level ranking source. Both use the
same provider session date and same-date accepted completed data has precedence,
so the detail series contains exactly one row per session. Only a complete,
non-anomalous accepted row suppresses current data; an incomplete or anomalous
same-date shell does not. Usable `ready`, `partial`, `stale`, and
`market_closed` current aggregates remain display eligible and provisional.

## Continuous foreign flow through the latest session

Completed foreign-flow history is an accepted SSI DailyStockPrice set keyed by symbol and `trading_date`. Accepted dates are monotonic within the running process: a later response that is empty, partial, differently ranged, failed, or older cannot delete a newer accepted row. Symbol-history responses may expose `response_regressive`, `preserved_latest_completed`, `provider_latest_returned`, and `cached_latest_retained`; a regressive response is stale/partial evidence, not a replacement for accepted history.

`GET /api/v1/stocks/vn/foreign-flow/current-aggregate` returns a display-only current aggregate for `scope=vn30` or a bounded `scope=watchlist`. It uses provider-dated SSI V3 `ForeignRoomMessage` replacement snapshots from the process-owned stream. VN30 membership and ICB grouping come from the current SSI IndexComponents classification. The response separates status/finality from coverage and reports requested, classified, subscribed, observed, complete-volume, complete-value, missing, and stale symbol counts.

Only snapshots sharing the newest provider-backed session date are aggregated. Missing fields remain `null` and do not contribute zero; explicit audited provider zero remains numeric zero. Gross buy/sell pairs derive net independently only when valid. Room-capacity fields do not participate. A newer current row may extend display-only 1/5/20/60-session windows, rankings, charts, tables, and displayed-series CSV. It is `current_session_provisional`; active, post-close, and active-disconnect labels are `Đang diễn ra`, `Tạm tính`, and `Mất kết nối`. Accepted DailyStockPrice has same-date precedence, leaving exactly one display row. Provisional rows and aggregates are not appended to historical storage or accepted analytics. Proprietary flow is unrelated and excluded.
