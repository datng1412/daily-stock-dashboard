# VN News Provider Research

Last verified: 2026-07-07

## Purpose

This document records Phase 5.1A - News Provider Research & Planning for the Vietnam dashboard. It is a documentation-only provider-selection artifact. It does not authorize runtime calls, credentials, scraping, fallback providers, public RSS ingestion, unofficial endpoint use, or any change to SSI-owned market-data fields.

Current repository rule:

* SSI remains the strict market-data owner for DailyOhlc, DailyStockPrice, intraday, realtime, trade tape, index data, and SSI-returned metadata.
* News is not SSI-owned in the current repository evidence.
* Future news rows must be source-labeled and domain-scoped. They must not overwrite SSI-owned or SSI-derived fields.
* `latest_price` remains SSI DailyOhlc.
* Missing news lists remain `[]`; missing news objects remain `null`.
* News provider failure must not affect valid SSI daily rows.

## Official sources reviewed

Reviewed official/current pages:

* FiinGroup:
  * [Stock Data Solutions / API Datafeed microsite](https://fiingroup.vn/en/stock-data-solutions-api-datafeed-microsite.html)
  * [API Datafeed root](https://datafeed.fiingroup.vn/)
  * [API News - News](https://datafeed.fiingroup.vn/api-datafeed-en/api-news/news/news)
  * [API News - Information announcement in Vietnamese](https://datafeed.fiingroup.vn/api-datafeed-en/api-news/news/information-announcement-in-vietnamese)
  * [API News - Information announcement in English](https://datafeed.fiingroup.vn/api-datafeed-en/api-news/news/information-announcement-in-english)
  * [API Datafeed contact](https://datafeed.fiingroup.vn/lien-he)
  * [FiinGroup home](https://fiingroup.vn/)
* Vietstock:
  * [Vietstock DataFeed - integrated economic and financial data](https://dichvu.vietstock.vn/du-lieu-tai-chinh/datafeed---du-lieu-tai-chinh-tich-hop-chuyen-nghiep?language=EN)
  * [Vietstock service center](https://dichvu.vietstock.vn/)
* Vnstock / VNStock:
  * [Vnstock docs](https://vnstocks.com/docs)
  * [Vnstock free library](https://vnstocks.com/docs/vnstock)
  * [Vnstock market data](https://vnstocks.com/docs/vnstock/du-lieu-thi-truong-market-data)
  * [Vnstock financial analysis](https://vnstocks.com/docs/vnstock/phan-tich-co-ban-fundamental)
  * [Vnstock disclaimer](https://vnstocks.com/onboard/mien-tru-trach-nhiem)
  * [Vnstock license](https://vnstocks.com/onboard/giay-phep-su-dung)
* WiGroup:
  * [WiFeed](https://www.wigroup.vn/san-pham/wifeed)
  * [WiData](https://www.wigroup.vn/san-pham/widata)
  * [WiFeed API document landing page](https://wifeed.vn/)
* Generic/global news APIs for lower-priority classification:
  * [NewsAPI documentation](https://newsapi.org/docs)
  * [GDELT project](https://www.gdeltproject.org/)
  * [GDELT data page](https://www.gdeltproject.org/data.html)

Repository `docs/resources/` provider notes were not used as authority in this phase. They remain reference-only and still require explicit approval before use.

## Current access status

Public docs/schema access is not legal/runtime API access.

| Provider | What we can access now | Runtime access now? | Production status |
| --- | --- | --- | --- |
| FiinGroup API Datafeed | Public docs/schema, especially API News fields such as `NewsId`, `OrganCode`, `Ticker`, `NewsTitle`, `NewsShortContent`, `NewsFullContent`, `NewsSource`, `NewsSourceLink`, `PublicDate`, `CreateDate`, `UpdateDate`, `NewsCategoryCode`, `IcbCode`, and `ComGroupCode`. | No. Runtime is blocked until written entitlement, credentials/auth, pricing/rate limits/SLA, display rights, storage/cache rights, redistribution rights, full-text versus summary/link permission, and a licensed fixture are available. | `preferred_after_entitlement` |
| Vietstock DataFeed | Public product/coverage page positioning DataFeed as API/Sync integration with market data, company data, financial statements, ratios, event calendar, macro, 24/7 news, and Vietnam/company/market news categories. | No. Runtime is blocked until item-level news schema, ticker-tagging proof, source URL/provenance fields, dedup keys, pricing, auth model, and legal display/storage/redistribution rights are available. | `candidate_after_entitlement` |
| Vnstock / VNStock | Python package/docs usable for local research, prototype exploration, and manual comparison across areas such as OHLCV, quote, trades, index data, financial statements, ratios, and company info. | No production runtime. Treat as a connector/tool, not a licensed StockClock app provider for display, cache, or redistribution. | `prototype_only` |

Phase 5.1A-2 records access status only. It does not authorize provider calls, adapters, scraping, credentials, config, API/schema changes, frontend UI, or fallback behavior.

## Future NewsProvider contract

Required normalized news item fields:

| Field | Required? | Rule |
| --- | --- | --- |
| `id` | yes | Stable dashboard item ID, preferably derived from provider item ID plus provider/source namespace. |
| `title` | yes | Human-readable title. Empty titles make the row unusable. |
| `summary` | nullable | Provider summary or short content. Null if not supplied or not licensed for display. |
| `source` | yes | Publisher/source label shown to users. |
| `source_url` | nullable but strongly preferred | Original article/source link when provider supplies it and rights allow display. |
| `published_at` | yes for usable rows | Provider publication timestamp. Must preserve timezone/date semantics. |
| `tickers` | list | Normalized SSI-style tickers linked by provider metadata or verified mapping. Empty list allowed for market-wide news. |
| `market` | nullable | `VN` when applicable; exchange may be separate metadata if supplied. |
| `category` | nullable | Normalized category such as company, market, macro, industry, policy, earnings, corporate actions, disclosure, or other. |
| `language` | nullable | Provider language code or inferred only when safe. |
| `provider` | yes | Provider adapter label, for example `fiingroup`, `vietstock`, or `wigroup`. |
| `provider_item_id` | nullable but preferred | Provider-native ID such as FiinGroup `NewsId` when supplied. |
| `ingested_at` | yes | Dashboard ingestion time. Must not replace `published_at`. |
| `sentiment` | nullable | Only populated when the provider supplies a licensed methodology; otherwise null. |
| `importance` | nullable | Only populated when the provider supplies a licensed methodology; otherwise null. |

Required provider capability gates:

* VN stock ticker-tagged company news.
* Market-wide Vietnam stock news.
* Corporate announcements / exchange filings if included in the licensed package.
* Categories covering company, market, macro, industry, policy, earnings, and corporate actions.
* Vietnamese language support; English is useful but secondary.
* Timestamp quality with publication/update semantics.
* Source attribution and source URL availability.
* Provider item IDs or equivalent deduplication keys.
* Historical lookup and incremental update filters.
* Rate limits, pacing, retry rules, and SLA.
* Legal display, storage, and redistribution rights.
* Permission to cache article metadata.
* Explicit rule for full article text versus headline/summary/link only.

## Provider comparison matrix

`needs_verification` means the official page did not establish the fact publicly. It is not a negative finding.

| Provider | Product/API | News coverage | Ticker tagging | Categories | Historical depth | Update frequency / latency | API access method | Auth model | Rate limits / SLA | Redistribution/display rights | Storage/caching rights | Full text vs headline/summary/link | Deduplication fields | Sentiment/importance support | Pricing/contact requirement | Production readiness | Implementation complexity | Legal risk | Recommended status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FiinGroup | API Datafeed, API News | Public docs expose news and information-announcement objects. | Strong public evidence: `Ticker` and `OrganCode` fields are documented. | Public docs expose `NewsCategoryCode`, `IcbCode`, `ComGroupCode`, keywords, and source fields; exact category taxonomy needs package proof. | `needs_verification` | Public schemas expose `PublicDate`, `CreateDate`, and `UpdateDate`; SLA/latency still `needs_verification`. | API Datafeed. | `needs_verification`; contact/consultation required. | `needs_verification` | `needs_commercial_review`; public docs do not grant app display/redistribution rights. | `needs_commercial_review`; raw payload and normalized metadata retention need written terms. | Public schema includes short and full content fields, source, and source link; display/storage permission is not established. | `NewsId`, `NewsSourceLink`, `NewsTitle`, `PublicDate`, `SourceCode`, plus title hash if needed. | Not found in reviewed public docs. Keep null unless licensed methodology exists. | Contact required. | Highest candidate after entitlement because the schema already matches ticker-tagged stock news needs. | Medium. | High until rights are written. | `preferred_after_entitlement` |
| Vietstock | DataFeed | Public page lists 24/7 news and Vietnam news categories. | `needs_verification`; DataFeed page does not publicly show item schema or ticker metadata for news. | Markets, companies, real estate, finance, commodities, industries, Vietnam economy are listed. | Public page claims historical/current data and 20+ years of market data, but news depth is `needs_verification`. | Public page says 24/7 news; API latency/SLA is `needs_verification`. | API or Sync Data. | `needs_verification`; commercial contact likely required. | Public page lists reliability but not API limits/SLA. | `needs_commercial_review`; public page is not a redistribution license. | `needs_commercial_review`. | `needs_verification`; no public news schema found. | `needs_verification`; likely requires provider IDs or title/source URL hash. | Not found in reviewed public docs. | Contact required; pricing not found in reviewed pages. | Serious alternative after commercial/API sample review. | Medium to high until schema/sample is obtained. | High until rights are written. | `candidate_after_entitlement` |
| WiGroup | WiFeed / WiData | WiFeed/WiData pages list news, company documents, company news, macro/industry news, and reports. | Partial public evidence: API examples use stock code fields in company/trading examples, but a news item schema with ticker metadata was not found. | Company, macro, industry, reports, announcements; exact normalized categories need API sample. | WiFeed landing page claims long history for broad data; news/report depth is `needs_verification`. | WiFeed states fast updates and realtime-updated news/report context; exact latency/SLA is `needs_verification`. | WiFeed API; WiData is Excel/add-in oriented and less suitable as the first runtime adapter. | WiFeed flow includes account, data package selection, payment, and API key. | Public page says packages are modular; exact rate limits/SLA are `needs_verification`. | Public page mentions official data copyright, but app display/redistribution rights need written contract terms. | `needs_commercial_review`. | `needs_verification`; no public news schema found in reviewed pages. | `needs_verification`; likely provider IDs or source/title/time hash after sample. | Not found in reviewed public docs. | Contact/payment required; WiData publishes package pricing for some data bundles, WiFeed pricing is package-specific. | Good candidate for macro/industry/report context; needs stronger proof for stock-ticker news feed. | Medium to high until news schema and terms are obtained. | High until rights are written. | `candidate_after_entitlement` |

## Provider findings

### FiinGroup API Datafeed

Evidence:

* FiinGroup's stock data solutions page positions API Datafeed for websites, trading boards, mobile applications, and algorithmic/research use.
* API Datafeed has a public API News section.
* The `News` schema documents fields directly aligned with a future NewsProvider: `NewsId`, `OrganCode`, `Ticker`, `NewsTitle`, `NewsShortContent`, `NewsFullContent`, `NewsSource`, `NewsSourceLink`, `NewsKeyword`, `PublicDate`, `CreateDate`, `UpdateDate`, `NewsCategoryCode`, `IcbCode`, `ComGroupCode`, and `SourceCode`.
* The information-announcement pages provide separate Vietnamese and English announcement APIs with similar fields.

Conservative assessment:

* FiinGroup is the best first automated candidate for VN stock/company news if entitlement confirms:
  * news package access;
  * ticker-tagged company news and announcements across HOSE/HNX/UPCoM;
  * display rights;
  * storage/cache rights;
  * redistribution rules;
  * full-text versus summary/link permission;
  * source URL availability;
  * rate limits/SLA and production auth.
* The reviewed public docs do not prove rights, pricing, rate limits, production credentials, or whether `NewsSourceLink` is always populated.

Recommended status: `preferred_after_entitlement`.

### Vietstock DataFeed

Evidence:

* Vietstock describes DataFeed as integrated economic and financial data delivered through APIs or Sync Data.
* The DataFeed page lists current and historical data, Vietnamese and English language support, 24/7 news, and Vietnam news categories including markets, companies, real estate, finance, commodities, industries, and Vietnam economy.
* The same page lists stock market data, company data, financial statements, ratios, financial plans, documents, event calendar, and macro data.

Conservative assessment:

* Vietstock is a serious candidate because it is a local financial-information provider and explicitly lists Vietnam news and API delivery.
* It may be strong for retail-facing market/company news, but this phase did not find a public item-level news schema proving ticker tagging, source URL fields, provider item IDs, incremental filters, or full-text rights.
* Production use depends on a commercial sample/API spec and legal display/storage/redistribution terms.

Recommended status: `candidate_after_entitlement`.

### Vnstock / VNStock

Evidence:

* Vnstock is the easiest candidate to try immediately for local developer research and manual comparison.
* Public docs cover or describe areas such as OHLCV, quote, trades, index data, financial statements, ratios, and company information.
* Vnstock documentation positions the project as a technical connector/tooling layer rather than a StockClock production data-license grant.

Conservative assessment:

* Vnstock can be useful for notebooks, one-off investigation, and comparing provider outputs during research.
* It must not be connected to StockClock app runtime unless legal/source-owner rights, automation terms, source provenance, rate limits, storage/cache rights, display rights, and redistribution rights are resolved.
* Treat Vnstock as a tool/connector, not a licensed data provider for app display, cache, or redistribution.

Recommended status: `prototype_only`.

### WiGroup WiFeed / WiData

Evidence:

* WiFeed is positioned as an API for integrating realtime economic and financial data into customer apps, websites, or digital platforms.
* WiFeed public pages list data domains including stock trading data, listed company information, financial statements, financial indicators, macro, commodities, news, and research reports.
* WiFeed says integration uses account registration, data package selection, payment, and API key usage.
* WiData is Excel/add-in oriented and publishes some package pricing, but it is less direct for app runtime integration than WiFeed.

Conservative assessment:

* WiGroup is a candidate after entitlement, especially for macro, industry, company documents, and report context.
* WiFeed could be a good API integration target, but the reviewed public pages did not expose a news item schema with ticker tagging, source URLs, provider item IDs, or update filters.
* WiData is not recommended as the first dashboard runtime integration because it is primarily an Excel workflow.

Recommended status: `candidate_after_entitlement`, likely secondary to FiinGroup for first stock-news adapter unless WiGroup provides better licensed news schema/terms.

## Lower-priority and blocked options

| Option | Classification | Reason |
| --- | --- | --- |
| Public RSS from CafeF, public Vietstock pages, VnExpress, VietnamBiz, NDH, SSI pages | `blocked_pending_terms` | Public availability is not a production data license. Terms, retention, display rights, redistribution, ticker mapping, and takedown/correction rules must be verified before ingestion. |
| Browser scraping and unofficial endpoints | `not_allowed_now` | The project has no approval to scrape, no verified terms, and no stable provider contract. This would create legal and maintenance risk. |
| NewsAPI | `secondary_macro_context_only` | Useful for broad web news search by keyword/source/language, but not a first target for VN ticker-tagged stock news. It requires an API key and does not establish local ticker metadata. |
| GDELT | `secondary_macro_context_only` | Strong global open research dataset and macro/geopolitical signal source, but not a direct licensed VN ticker-news feed. Ticker-level mapping and article display rights would remain separate problems. |

## Recommendation

Recommended first news-provider implementation target:

1. FiinGroup API Datafeed News, if entitlement confirms ticker-tagged VN stock/company news, source URLs, display/storage rights, redistribution rules, rate limits/SLA, production auth, and permitted content depth.
2. Vietstock DataFeed, if it provides a clearer or cheaper licensed stock-news API with ticker mapping, source links, and dashboard display/storage rights.
3. WiGroup WiFeed, if it provides a better app/API integration package for company news, macro/industry news, and reports with item-level ticker/category metadata.

Current Phase 5.1A-2 decision:

| Need | Best candidate |
| --- | --- |
| First licensed ticker-tagged VN stock news | FiinGroup API Datafeed News |
| Backup licensed local data/news provider | Vietstock DataFeed |
| Dev-only research/comparison | Vnstock |
| Canonical market data | SSI |

Do not choose a provider purely by brand. Rank by:

1. Legal right to display/cache news in the app.
2. Ticker-tagged VN stock coverage.
3. API availability and auth clarity.
4. Source URL/provenance quality.
5. Update frequency.
6. Historical depth.
7. Deduplication support.
8. Implementation simplicity.
9. Cost/contact friction.
10. Fit with future corporate-actions, financials, metadata, and macro provider planning.

## Phase 5.1B experimental Vnstock News gate

Phase 5.1B verified the current Vnstock News documentation and license. The documented package exposes `vnstock_news.Crawler` for bounded RSS/feed reads, while `BatchCrawler` and `AsyncBatchCrawler` are for sitemap/history collection and are not normal dashboard-runtime mechanisms. The documented normalized fields are `url`, `title`, `short_description`, `content`, `publish_time`, `author`, `category`, and `image_url`.

The current Vnstock license requires written approval for commercial product integration, and Vnstock states that it is a technical connector rather than the source-data owner. Therefore the runtime classification is `blocked_pending_terms`, not `experimental_enabled_by_config`:

* `VN_NEWS_PROVIDER=disabled` remains the default.
* `VN_NEWS_PROVIDER=vnstock_news` exposes `news_status.status=unavailable`, `reason_code=blocked_pending_terms`, and `source=Vnstock News` without importing `vnstock_news`, making a network request, or returning a news row.
* The repository contains an offline normalization contract proof only. It preserves URL/provenance and omits full content by default; it is not a crawler or a production adapter.
* No Vnstock News package dependency, credentials, RSS/sitemap call, batch/async crawler, request-time crawl, or fallback provider is enabled.

Before a runtime experiment can fetch even a bounded RSS feed, written commercial permission plus source-owner automation, display, cache/storage, attribution, redistribution, and full-text terms must be recorded. Production candidates remain FiinGroup, Vietstock, and WiGroup after entitlement.

## Phase 5.1B-Local personal research mode

Phase 5.1B-Local adds a separate opt-in local mode for the user's personal research dashboard:

```text
VN_NEWS_PROVIDER=vnstock_news_personal
VNSTOCK_NEWS_PERSONAL_ENABLED=true
```

This does not approve Vnstock News for hosted, public, commercial, or redistributed dashboard use. It is news-only and must not be used for SSI-owned market data, `latest_price`, OHLCV, realtime quotes, order book, trade tape, foreign room, market index, or metadata.

Runtime behavior:

* `VN_NEWS_PROVIDER=disabled` remains the default.
* `VN_NEWS_PROVIDER=vnstock_news` remains `blocked_pending_terms` and performs no import or crawl.
* `VN_NEWS_PROVIDER=vnstock_news_personal` requires `VNSTOCK_NEWS_PERSONAL_ENABLED=true`; otherwise it returns `local_personal_research_disabled`.
* The optional package is imported lazily only in personal mode. If it is missing, the API returns `provider_package_missing`.
* The only allowed runtime call is documented RSS/feed usage through `vnstock_news.Crawler(...).get_articles_from_feed(limit_per_feed=N)`.
* `BatchCrawler`, `AsyncBatchCrawler`, sitemap/history crawling, background crawler daemons, aggressive loops, credentials, and market-data calls are not part of the dashboard request path.
* Full article `content` is omitted by default with `VNSTOCK_NEWS_INCLUDE_CONTENT=false`.
* Returned rows preserve source URL/provenance and carry `rights_status=personal_research_only` and `provider_mode=local_personal_research_only`.
* Ticker relevance is weak only: exact symbol matching in title/summary. It is not official provider ticker tagging.

Configuration:

| Variable | Default | Meaning |
| --- | --- | --- |
| `VN_NEWS_PROVIDER` | `disabled` | `disabled`, `vnstock_news`, or local-only `vnstock_news_personal`. |
| `VNSTOCK_NEWS_PERSONAL_ENABLED` | `false` | Required explicit gate for local personal research mode. |
| `VNSTOCK_NEWS_SITES` | `vnexpress,cafef` | Bounded documented site names; exact full support list remains provider-doc dependent. |
| `VNSTOCK_NEWS_LIMIT_PER_SITE` | `5` | Bounded RSS articles per site. |
| `VNSTOCK_NEWS_TIMEOUT_SECONDS` | `10` | Best-effort package timeout value if the installed `Crawler` supports it. |
| `VNSTOCK_NEWS_CACHE_TTL_SECONDS` | `1800` | Process-local cache TTL for personal news results. |
| `VNSTOCK_NEWS_INCLUDE_CONTENT` | `false` | Keep full content out of API/UI by default. |

Production runtime news still requires an entitled provider such as FiinGroup, Vietstock, or WiGroup with written display, storage, attribution, and redistribution terms.

## Phase 5.1C Vnstock Community company news

`vnstock_community` is a separate local/personal research mode for ticker-specific company headlines from the installed free `vnstock` Community package. It is not the Sponsor `vnstock_news` RSS crawler and it is never a market-data provider or SSI fallback.

```text
VN_NEWS_PROVIDER=vnstock_community
VNSTOCK_COMMUNITY_NEWS_LIMIT_PER_TICKER=3
VNSTOCK_COMMUNITY_NEWS_CACHE_TTL_SECONDS=1800
VNSTOCK_COMMUNITY_NEWS_TIMEOUT_SECONDS=10
```

The adapter calls only `Reference().company(ticker).news()` for the currently selected dashboard ticker or the company-page ticker. It never fans out across watchlist/VN30 rows, and normal daily/realtime refreshes do not bypass its 30-minute per-ticker cache. The result is capped at three normalized headline rows.

Installed Community version `4.0.4` exposes a DataFrame with `head`, `article_id`, `title`, `publish_time`, and `url` in the observed local contract. `article_id`, title, and publication time are used when present. `head` is not displayed as a summary or source because its semantics are unverified. The KBS adapter proves its API host but does not establish a public article-site origin for its relative paths, so those values remain in `raw_url` and are not made clickable. `url` is retained only for validated absolute `http`/`https` URLs; no hostname is inferred from branding or the API endpoint.

This remains local/personal research only. Production/public display, cache, redistribution, source-owner rights, and automation terms require separate review. SSI remains the market-data owner and `latest_price` remains SSI DailyOhlc.

## Proposed first integration shape after entitlement

This is architecture planning only. Do not implement NewsProvider runtime yet. The next step is Phase 5.1B - NewsProvider Entitlement Pack, not licensed adapter implementation.

* `NewsProvider` interface with disabled-by-default provider selection.
* Provider-specific adapter such as `FiinGroupNewsProvider`, disabled unless explicit config and credentials are present.
* No fallback provider. Provider failure returns `news=[]` plus status/diagnostics and does not affect SSI daily rows.
* Source-labeled normalized rows with provider item ID and source URL when allowed.
* Cache TTL by use case:
  * market dashboard news: short TTL such as 5 to 15 minutes after entitlement confirms rate limits;
  * company news: short TTL plus per-ticker key;
  * historical backfill: separate bounded/manual job, not request-time broad scans.
* Deduplication by:
  * provider item ID when present;
  * source URL when present;
  * normalized title + source + published date hash as fallback.
* Future endpoints:
  * `GET /api/v1/stocks/vn/news?ticker=FPT`
  * `GET /api/v1/stocks/vn/news`
* Future UI:
  * company page news card;
  * dashboard market news card;
  * optional ticker-tagged watchlist highlight only when real rows exist.

## Legal and safety gates before runtime

No live adapter should be implemented until these are written down:

1. Written entitlement for the exact news package and covered exchanges.
2. Trial credential availability or another provider-approved test path.
3. API auth method and secret-handling plan.
4. Production endpoint docs or package access path.
5. Pricing, rate limits, pacing, retry rules, and SLA/update frequency.
6. Ticker-tagged company news coverage.
7. Source name availability.
8. Source URL/provenance availability.
9. Title, summary, and full-content permission boundaries.
10. Storage/cache rights for normalized metadata and any article text.
11. Display rights for the dashboard audience.
12. Redistribution rights or explicit redistribution prohibition.
13. Full-text versus headline/summary/link permission.
14. Attribution requirements.
15. Provider item ID or deduplication key.
16. Takedown/correction/delete handling.
17. Historical depth and incremental update filters.
18. Timezone and Vietnamese encoding handling.
19. Ticker mapping to SSI symbols, including renamed, delisted, and transferred securities.
20. Disabled-by-default config plan.
21. Secret handling plan.
22. Licensed sample fixture plan covering success, empty, duplicate, correction/deletion, missing source URL, missing optional summary, and mixed ticker/market-wide news.

## Future phases

* Phase 5.1C - NewsProvider Entitlement Pack: collect written provider terms, trial credential status, sample schema, licensed fixture, content-rights boundaries, and API/auth/rate-limit plan.
* Phase 5.1D - Licensed NewsProvider Adapter: implement a disabled-by-default adapter only after the entitlement pack passes.
* Phase 5.1D - News UI Cards: render source-labeled company and market news cards after licensed API rows exist.

Hosted/production runtime remains data-free after Phase 5.1B: `news=[]`; the default status is `disabled`, while the explicitly selected production Vnstock gate is `unavailable` with `blocked_pending_terms` until a later licensed provider adapter is implemented. Phase 5.1B-Local is a separate local/personal research option and is not a production provider approval.
