# Vietnam External Provider Capability Strategy

Last verified: 2026-06-29

## Purpose

This document records the Phase 5.0A decision for Vietnam data domains that SSI FastConnect does not own. It is a provider-selection artifact, not authorization to call, scrape, or redistribute data from any candidate.

The current application contract remains unchanged:

* SSI owns daily OHLCV, DailyStockPrice enrichment including bounded recent foreign-flow history, intraday candles, optional realtime, IndexList, DailyIndex where valid, IndexComponents, and SSI-returned metadata.
* External providers must use separate source labels and must not overwrite SSI-owned fields.
* `latest_price` remains SSI DailyOhlc close when SSI daily rows exist.
* External-provider failures must not break SSI daily rows.
* Missing objects remain `null`; missing lists remain `[]`.
* No corporate action, dividend, news, financial, macro, metadata, or index value may be inferred or fabricated.

## Phase 4.5A SSI-First Candidate Boundary

Phase 4.5A completes the SSI capability audit before any external implementation. For this phase, VNStocks and FiinGroup are recorded only as future external candidates:

| Provider | Phase 4.5A classification | Verification state | Runtime use |
| --- | --- | --- | --- |
| VNStocks | `candidate_external_provider` | `needs_verification` for auth, rate limits, timestamp semantics, price/data semantics, storage/display rights, redistribution rights, and ticker coverage | None; do not call, scrape, configure, or fallback to VNStocks |
| FiinGroup API Datafeed | `candidate_external_provider` | `needs_verification` for commercial entitlement, auth, rate limits, timestamp semantics, price/data semantics, storage/display rights, redistribution rights, and contracted exchange coverage | None; do not call, configure, or fallback to FiinGroup until a later qualification phase passes |

This boundary does not invalidate the Phase 5.0A provider-selection work below; it only records that no external provider is authorized or implemented during the SSI-first Phase 4.5A pass.

## Phase 5.0A Decision

### Implement next

**Domain:** corporate actions, dividends, rights, bonus shares, and splits.

**Preferred automated candidate:** FiinGroup API Datafeed, subject to written commercial entitlement and dashboard display/redistribution approval.

**Fallback strategy:** a user-supplied, provenance-required manual import through a future `CorporateActionsProvider` contract. Manual rows must retain source name, source URL or document reference, import timestamp, and event dates. Manual import is not permission to scrape official portals.

Why this domain is first:

* Corporate actions directly affect price interpretation, event markers, dividend context, and user trust.
* The current application deliberately refuses to infer adjustment events from price gaps.
* FiinGroup publishes a structured event schema with event title, publication date, record date, ex-right date, execution/payment date, event code, ratio, value, attachment, and source URL.
* VSDC public notices confirm that the underlying official records contain ticker, ISIN, exchange, record date, cash amount, payment date, rights ratio, issue price, and subscription dates.
* The existing `/api/v1/stocks/vn/corporate-actions` unavailable contract and company `events.items=[]` placeholder provide a safe integration boundary without changing SSI market-data semantics.

### Verify before implementation

Phase 5.0B/5.1A must obtain and record all of the following before a live adapter is written:

1. FiinGroup product entitlement covering corporate events for HOSE, HNX, and UPCoM, or mark each exchange coverage answer as `needs_verification`.
2. VNStocks entitlement, source terms, automation terms, storage/display rights, redistribution rights, rate limits, and event-field coverage, or keep VNStocks as `needs_verification`.
3. Authentication flow, production base URL, pagination, date filters, timeout expectations, retry rules, rate limits, pricing, and support/SLA.
4. Historical depth, update cadence, correction/cancellation behavior, duplicate event identifiers, and provider backfill guarantees.
5. Contractual permission to store normalized rows, display them in this dashboard, and retain source URLs/documents.
6. Contractual permission, or prohibition, for redistribution to other users/deployments.
7. Permission, or prohibition, for raw provider payload storage. If not granted, store only normalized fields plus provenance.
8. Source provenance guarantees, especially when `SourceUrl`, attachments, or document references are empty.
9. Symbol mapping rules between provider identifiers such as FiinGroup `OrganCode`, VNStocks ticker fields if applicable, and SSI symbols, including renamed, delisted, and transferred securities.
10. Event type coverage for cash dividends, stock dividends, bonus shares, rights issues, stock splits, meetings, listing changes, corrections/cancellations, and unknown/other events.
11. Event date semantics for announcement/publication, ex-date, record date, payment/execution date, effective date, provider-created time, and provider-updated time.
12. Privacy and security constraints for credentials, account identifiers, audit logs, provider documents, and any user-supplied manual files.
13. A sanitized one-ticker fixture covering cash dividend, stock dividend/bonus, rights issue, correction/cancellation, duplicate handling, source URL/document availability, and missing optional dates.
14. A written enablement proof showing the provider returns normalized `events`, with legacy `items` derived by the service/API and never maintained as a divergent provider list.

No production FiinGroup call is authorized until those gates pass.

### Defer

1. Financial statements.
2. Financial ratios and valuation.
3. Metadata fallback.
4. News.
5. Macro context.
6. Explicit VNINDEX fallback.
7. Broker-connected holdings or cost basis.

Portfolio management is not an unimplemented provider domain in this repository. A separate user-owned portfolio subsystem already supports accounts, manual entries, corporate-action entries, CSV import, snapshots, and risk views. Broker connectivity and automatic holdings synchronization remain separate security/product work.

### Do not pursue now

* Scraping VSDC, HOSE, HNX, SSC, company disclosure pages, or third-party finance sites.
* Undocumented broker or public-web endpoints.
* Mozyfin or KBS as normal VN fallbacks.
* A global macro bundle before each series' ownership and display terms are reviewed.
* A VNINDEX fallback that is silently presented as SSI.
* News summarization before source access, timestamp, ticker matching, duplicate handling, and display rights are solved.

## Classification

Provider/domain recommendations use these values:

* `implement_next`: access and legal gates are sufficient for the next scoped implementation.
* `candidate_after_verification`: data shape is promising, but access, legal, or operational facts remain unresolved.
* `needs_paid_provider`: an official or vendor feed exists but requires a commercial agreement.
* `manual_import_candidate`: safe only for user-supplied, provenance-retaining files.
* `not_recommended_now`: feasible in principle but lower priority or architecturally premature.
* `blocked`: current access or terms do not support implementation.

Public visibility is not treated as permission for automated collection, storage, display, or redistribution.

## Provider Capability Matrix

`needs_verification` means the reviewed official pages did not establish the fact.

| Domain | Current status | Candidate provider/source | Coverage | Access/auth | Cost/pricing known? | Rate limits known? | Legal/terms confidence | Data fields available | Integration complexity | Main risk | Recommendation | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Corporate actions | `not_implemented` / `events=[]` | [FiinGroup Events API](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/event-calendar/events) and [Stock Issuance API](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/event-calendar/stock-issuance) | Listed-company event examples and corporate event APIs are verified; exact contracted exchange universe is `needs_verification` | `needs_verification` | Commercial contact is published; price is not public in reviewed docs | `needs_verification` | Low until contract confirms storage/display/redistribution | Event title/code, public/record/ex-right/execution dates, ratio, value, issue terms, attachment, source URL | Medium | Entitlement and provenance fields may vary or be empty | `candidate_after_verification` | Obtain commercial and legal answers, then run a one-ticker fixture proof |
| Corporate actions | `not_implemented` | [VSDC rights notices](https://www.vsd.vn/vi/ad/189718) | Official notices cover listed and registered securities; public examples contain cash dividends and rights terms | Public web pages; no reviewed public API | Public page access; automation cost unknown | `needs_verification` | Low for automation/redistribution; no reviewed API/license | Ticker, ISIN, exchange, record date, cash amount, payment date, rights ratio, issue price, subscription dates | High for automation; low for manual import | HTML/PDF variation, corrections, no stable API contract | `manual_import_candidate` | Define provenance-required CSV/JSON input; do not scrape |
| Corporate actions / HNX disclosures | `not_implemented` | [HNX commercial information packages](https://owa.hnx.vn/ftp/PORTALNEW/FileContent/HNX_Danh%20muc%20goi%20tin%20va%20bang%20gia%20dich%20vu%20CCTT%2820260105_145538_848%29.pdf) | HNX/UPCoM packages describe rights, dividends, issuance, and disclosure data | Commercial InfoFile delivery | Paid schedule is published; applicable package quote still required | Delivery cadence is described per package; request limits are not applicable/verified | Medium only after contract review | Rights/dividend notices, issuance and disclosure files depending on package | Medium | Partial exchange coverage and file normalization | `needs_paid_provider` | Request package scope, sample files, license, and redistribution terms |
| News / disclosures | Disabled / `news=[]` | [HNX official RSS](https://conds.hnx.vn/rss.html) | HNX channels for exchange, member, and issuer disclosures are verified | Public RSS | No fee shown | `needs_verification` | Medium-low; RSS exists for syndication, but retention/display terms were not found | Title, link, publication time, channel; ticker matching may require parsing | Low-medium | HNX-only coverage, relevance noise, symbol evidence | `candidate_after_verification` | Verify feed URLs, terms, retention, and ticker matching with a fixture-only proof |
| News | Disabled / `news=[]` | [FiinGroup News API](https://datafeed.fiingroup.vn/api-datafeed-en/api-news/news/news) | Economic, finance, macro, industry, and corporate news schema with ticker examples | `needs_verification` | Commercial contact; public price not found | `needs_verification` | Low until content display/storage rights are explicit | Ticker, title, short/full content, categories and friendly identifiers; URL/timestamp semantics need proof | Medium | Content copyright and redistribution | `candidate_after_verification` | Defer until corporate-actions entitlement discussion includes news rights |
| Financial statements | `not_implemented` / `financials=[]` | [FiinGroup Financial Statements API](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/financial-statements/separated-financial-statements-of-production/separated-cash-flow-statements-of-production) | Separate/consolidated and sector-specific schemas are documented | `needs_verification` | Commercial contact; public price not found | `needs_verification` | Low until contract review | Ticker, fiscal period, start/end dates, publication date, audit flag, source, statement line codes | High | Sector-specific schemas, restatements, unit/period normalization | `candidate_after_verification` | Implement only after corporate-actions provider proves shared auth/provenance patterns |
| Financial statements | `not_implemented` | HNX commercial information packages | HNX/UPCoM financial-statement file packages are listed | Commercial InfoFile delivery | Paid schedule published | Not applicable/`needs_verification` | Medium only after contract review | Original/structured statement files depending on package | High | Partial market coverage and document extraction | `needs_paid_provider` | Use only if a cross-market vendor agreement is unavailable |
| Financial ratios / valuation | `not_implemented` | [FiinGroup Corporate Ratios API](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/corporate-financial-ratios/corporate-financial-ratios/year-ratio) | Extensive company-type-specific ratios are documented | `needs_verification` | Commercial contact; public price not found | `needs_verification` | Low until contract review | ROE, ROA, margins, leverage, growth, banking ratios, fiscal period and calculation date | High | Opaque coded fields, provider methodology, sector comparability | `candidate_after_verification` | Follow raw statements; do not mix provider ratios with locally derived ratios silently |
| Metadata fallback | SSI partial | [FiinGroup Organization API](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/business-profile/business-profile/overview-of-organization) | Listed-company organization examples include exchange grouping and identifiers | `needs_verification` | Commercial contact; public price not found | `needs_verification` | Low until contract review | Ticker, names, ICB, company type, listed/outstanding shares, listing date, charter capital | Medium-low | Source priority and stale/conflicting fields | `candidate_after_verification` | Add only for SSI-null fields with per-field source labels after license approval |
| Macro | No provider block | [FiinGroup Macro API](https://datafeed.fiingroup.vn/api-kinh-te-vi-mo) | Vietnam rates, monetary policy, GDP, CPI, production, trade, investment, and domestic commodities are listed | `needs_verification` | Commercial contact; public price not found | `needs_verification` | Low until contract review | Dataset-specific period, publication date, value, source organization | High | Mixed frequencies, revisions, units, broad scope | `not_recommended_now` | Define a small indicator set only after company data domains |
| Macro | No provider block | [FRED API](https://fred.stlouisfed.org/docs/api/fred/overview.html), [EIA Open Data](https://www.eia.gov/opendata/), and official Vietnamese publications | US macro/rates and energy are available through separate official APIs; SBV publishes official daily exchange-rate information | FRED and EIA require API keys; Vietnamese machine-readable access is `needs_verification` | API registration is available; series-specific cost is generally not stated | Limits may change; exact production limits are `needs_verification` | Medium-low: FRED explicitly retains third-party series restrictions and requires notices | Series observations, release dates, revisions, energy prices; DXY/gold/USD-VND still need source selection | High | Multiple licenses, timestamps, revisions, and source owners | `not_recommended_now` | Review each selected series and owner separately; do not create a generic unrestricted macro feed |
| VNINDEX / broad index fallback | SSI unresolved | [FiinGroup HOSE Index API](https://datafeed.fiingroup.vn/api-giao-dich/co-phieu/co-phieu/hose-index) | `VNINDEX` example with index level, OHLC, change, breadth, volume/value is documented | `needs_verification` | Commercial contact; public price not found | `needs_verification` | Low until exchange-data display/redistribution rights are explicit | Index value/OHLC, change, breadth, volume/value, trading date | Medium | External exchange data must never be labeled SSI; potential market-data redistribution restrictions | `candidate_after_verification` | Defer behind corporate/company domains; require explicit source-labeled fallback contract |
| Portfolio / holdings | Existing separate subsystem | User-owned entries and current CSV import | User/account dependent | Local authenticated application flows | No new provider cost | Not applicable | High for user-owned input; broker integration is unreviewed | Accounts, trades, cash ledger, corporate-action entries, snapshots, cost methods, risk | Already implemented; broker sync would be high | Privacy, authentication, broker authorization | `not_recommended_now` for external integration | Keep separate; do not add broker APIs in this phase |

### Historical depth, update, timestamp, and symbol assessment

| Candidate/source | Historical depth | Update frequency | Timestamp/date semantics | Symbol mapping quality |
| --- | --- | --- | --- | --- |
| FiinGroup corporate/company/news/financial APIs | `needs_verification`; public examples are not entitlement or completeness evidence | `needs_verification`; schemas expose create/update or publication dates | Corporate schemas distinguish public, record, ex-right, issue/execution, create, and update dates; financial schemas distinguish fiscal and publication dates | Ticker and `OrganCode` exist, but exact SSI-to-Fiin mapping, renamed symbols, delistings, and exchange transfers require a master-data proof |
| VSDC public notices | Public archives exist, but complete historical depth and correction linkage are `needs_verification` | Notices expose page update times; machine-readable cadence is not established | Official examples distinguish notice update, record, payment, rights-effective, transfer, and subscription dates | Strong individual-notice evidence through ticker and ISIN; bulk completeness is unverified |
| HNX RSS/public disclosures | Feed/archive depth and retention are `needs_verification` | Publication times are visible; polling expectations and limits are unverified | Publication timestamp is distinct from the event date embedded in a title/document | Some issuer disclosures expose tickers; robust ticker evidence and renamed-symbol handling need proof |
| HNX commercial InfoFile | Contract/sample required | Package schedule describes delivery timing | File-specific dates require sample validation | Expected exchange identifiers, but cross-market mapping is incomplete by design |
| FRED/EIA/official macro sources | Often long history, but must be verified per selected series | Daily to annual depending on series; releases can be revised | Observation period, release date, vintage/revision date, and retrieval time must remain distinct | Not applicable to equity tickers; use explicit series IDs and source owners |
| User-supplied corporate-action import | Limited to supplied files | Manual | Import time must not replace announcement, ex, record, or payment date | Require normalized ticker plus source reference; optional ISIN improves mapping confidence |

## Domain Scoring

Scores are 1 to 5:

* Higher user value, correctness impact, availability likelihood, and integration fit are better.
* Higher implementation difficulty, legal/terms risk, and maintenance burden are worse.
* Scores are architecture estimates, not vendor claims.

| Domain/source strategy | User value | Correctness impact | Availability likelihood | Difficulty | Legal risk | Maintenance | Integration fit | Classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Corporate actions via FiinGroup | 5 | 5 | 3 | 3 | 5 | 3 | 5 | `candidate_after_verification` |
| Corporate actions via provenance-required manual import | 4 | 5 | 4 | 2 | 2 | 4 | 5 | `manual_import_candidate` |
| Financial statements via FiinGroup | 5 | 4 | 3 | 5 | 5 | 4 | 4 | `candidate_after_verification` |
| Financial ratios via FiinGroup | 4 | 3 | 3 | 4 | 5 | 4 | 4 | `candidate_after_verification` |
| Metadata fallback via FiinGroup | 3 | 3 | 3 | 2 | 5 | 2 | 5 | `candidate_after_verification` |
| News via HNX RSS plus later licensed HOSE coverage | 4 | 2 | 3 | 3 | 3 | 4 | 4 | `candidate_after_verification` |
| Macro via multiple official APIs | 3 | 2 | 4 | 4 | 4 | 5 | 3 | `not_recommended_now` |
| Explicit VNINDEX fallback via licensed vendor | 4 | 4 | 3 | 2 | 5 | 2 | 3 | `candidate_after_verification` |
| External broker/portfolio integration | 3 | 2 | 2 | 5 | 5 | 5 | 2 | `not_recommended_now` |

No automated candidate is classified `implement_next` yet because the legal/access gate is unresolved. The next implementation phase is therefore a bounded provider qualification and contract proof, not production rollout.

## Recommended Implementation Order

1. Corporate actions/dividends/rights/splits.
2. Raw financial statements.
3. Metadata fallback for SSI-null fields.
4. Provider ratios/valuation, kept distinct from raw statements and local derivations.
5. News/disclosures.
6. Small, explicitly selected macro series.
7. Explicit source-labeled VNINDEX fallback.
8. Broker-connected holdings/cost basis, only under a separate privacy/security project.

## Phase 5.0B Contract Proof

Status: contract proof implemented on 2026-06-29; commercial/legal qualification remains unresolved.

Deliverables:

* Added a disabled-by-default `CorporateActionsProvider` contract boundary.
* Added configuration placeholders that default to disabled and do not authorize external calls.
* Added normalized event fields for dates, ratios, cash dividends, provenance, provider IDs, and missing-field tracking.
* Kept `events=[]` and legacy `items=[]` compatibility when no provider rows exist.
* Added sanitized diagnostics limited to provider, request domain, status, row count, failure class, last checked time, and request size.
* Added deterministic tests for disabled default behavior, future provider names with no import/call, provider failure sanitization, normalized event provenance, and schema compatibility.
* Updated the frontend to show corporate actions as a disabled/unavailable future module instead of implying an empty verified event calendar.

Suggested normalized event fields:

```text
ticker
event_type
announcement_date
ex_date
record_date
payment_date
cash_dividend_per_share
stock_dividend_ratio
bonus_ratio
rights_ratio
rights_price
split_ratio
currency
source
source_url
source_document
provider_event_id
updated_at
```

Required status behavior:

```text
disabled/not_configured/not_implemented -> events=[]
enabled provider failure -> status=error or unavailable, events=[]
usable provider rows -> status=ok, events=[...]
```

Diagnostics must be limited to provider name, request domain, status, row count, failure class, and last fetched time. Raw provider bodies, tokens, headers, account IDs, and commercial credentials must never be returned.

This proof does not implement VNStocks, FiinGroup, scraping, broker APIs, production external-provider runtime, fallback providers, fake events, or changes to SSI DailyOhlc/DailyStockPrice ownership. `latest_price` remains SSI DailyOhlc.

Before a live adapter is written, Phase 5.1A must still obtain and record all access, entitlement, rate-limit, historical-depth, correction, storage, display, redistribution, provenance, and symbol-mapping answers listed above.

## Verified Facts and Remaining Unknowns

Verified from official sources:

* FiinGroup publishes structured API schemas for corporate events, stock issuance, company metadata, news, financial statements, ratios, macro data, and HOSE index data.
* FiinGroup event examples distinguish publication, record, ex-right, and execution dates and include ratio/value fields.
* VSDC publishes official rights notices with detailed dividend and subscription terms.
* HNX publishes RSS channels and a commercial information-service package schedule.
* FRED and EIA expose official APIs; both require API keys for normal API use.
* FRED terms state that third-party series can retain separate copyright restrictions and require application notices.

`needs_verification`:

* FiinGroup authentication, production endpoint, rate limits, support SLA, historical depth, correction semantics, price, storage rights, display rights, and redistribution rights.
* Whether FiinGroup `SourceUrl`/attachment provenance is consistently populated.
* HNX RSS retention, display, and redistribution terms and whether equivalent licensed HOSE coverage is available.
* Stable public API access for VSDC, HOSE, SSC, and SBV.
* Any right to automate public disclosure pages.
* Series-by-series rights for FRED, EIA, gold, DXY, USD/VND, yields, and other macro sources.

## Source Review Notes

Official pages reviewed on 2026-06-29:

* [FiinGroup API Datafeed contact](https://datafeed.fiingroup.vn/lien-he)
* [FiinGroup Events API](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/event-calendar/events)
* [FiinGroup Financial Statements API example](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/financial-statements/separated-financial-statements-of-production/separated-cash-flow-statements-of-production)
* [FiinGroup Corporate Ratios API](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/corporate-financial-ratios/corporate-financial-ratios/year-ratio)
* [FiinGroup Organization API](https://datafeed.fiingroup.vn/api-datafeed-en/api-corporate/business-profile/business-profile/overview-of-organization)
* [FiinGroup News API](https://datafeed.fiingroup.vn/api-datafeed-en/api-news/news/news)
* [FiinGroup Macro API](https://datafeed.fiingroup.vn/api-kinh-te-vi-mo)
* [FiinGroup HOSE Index API](https://datafeed.fiingroup.vn/api-giao-dich/co-phieu/co-phieu/hose-index)
* [VSDC public rights notice example](https://www.vsd.vn/vi/ad/189718)
* [HNX official RSS page](https://conds.hnx.vn/rss.html)
* [HNX 2026 information-service package schedule](https://owa.hnx.vn/ftp/PORTALNEW/FileContent/HNX_Danh%20muc%20goi%20tin%20va%20bang%20gia%20dich%20vu%20CCTT%2820260105_145538_848%29.pdf)
* [FRED API overview](https://fred.stlouisfed.org/docs/api/fred/overview.html)
* [FRED API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html)
* [EIA Open Data](https://www.eia.gov/opendata/)

This review did not inspect or authorize repository `docs/resources/` providers.
