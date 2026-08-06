# Vietnam Proprietary-Flow Provider Gate

Last updated: 2026-08-06

## Outcome

Phase VN-PROPRIETARY-P0 FiinQuantX continuation result:
`VN_PROPRIETARY_FIINQUANT_ENTITLEMENT_REQUIRED`.

The installed `FiinQuantX==0.1.62` package contains a public candidate
operation and an explicit proprietary gross-field registry. A direct manual
proof loaded credentials from the repository `.env`, authenticated with
`FiinSession(...).login()`, and observed `is_login=true`. Authenticated
`get_value_by_investor()` requests for FPT, SSI, HPG, VPB, VIC, VNINDEX, VN30,
and HOSE each printed the narrow permission-denied marker and returned an empty
DataFrame. The empty frames are swallowed entitlement failures, not valid zero
or ordinary empty data.

P1 was not entered, and the existing truthful unsupported Proprietary API/UI
remains unchanged. The probe mutated no production cache, retained no output
artifact, and exposed no credential value. Dataset entitlement plus a future
active-session observation remain mandatory before any current
proprietary-flow integration. Runtime schemas, values, publication cadence,
and realtime behavior remain unobserved.

## Candidate evidence

### FiinQuantX

Installed package: `FiinQuantX==0.1.62`.

Public candidate operation:
`FiinSession.PriceStatistics().get_value_by_investor(tickers, from_date, to_date)`.
The installed package's `PriceStatistics.fields["ValueByInvestor"]` registry
declares these proprietary fields:

- total: `proprietaryTotalBuyTradeVolume`,
  `proprietaryTotalSellTradeVolume`, `proprietaryTotalBuyTradeValue`, and
  `proprietaryTotalSellTradeValue`;
- matched: `proprietaryTotalMatchBuyTradeVolume`,
  `proprietaryTotalMatchSellTradeVolume`,
  `proprietaryTotalMatchBuyTradeValue`, and
  `proprietaryTotalMatchSellTradeValue`;
- deal: `proprietaryTotalDealBuyTradeVolume`,
  `proprietaryTotalDealSellTradeVolume`,
  `proprietaryTotalDealBuyTradeValue`, and
  `proprietaryTotalDealSellTradeValue`.

This is a genuine candidate contract, distinct from the generic historical
fields `bu`, `sd`, `fb`, `fs`, `fn`, price, volume, turnover, room, foreign
room, and order imbalance. None of those generic fields is reinterpreted as
proprietary flow.

Corrected evidence and current acceptance boundary:

- The earlier diagnostic used dotenv loading equivalent to `override=False`,
  which could silently select stale process-environment credentials instead of
  the repository `.env`.
- The corrected diagnostic reads `.env` with `dotenv_values()`, never mutates
  `os.environ`, and requires an explicit choice when complete process and
  dotenv credentials conflict.
- The direct manual proof authenticated from repository `.env` and then
  observed one permission-denied message plus one empty DataFrame per requested
  symbol or aggregate candidate. This establishes
  `authentication_success + proprietary_dataset_entitlement_denied`.
- Declared registry fields are not runtime-observed fields. No denied empty
  frame is converted to zero.
- One bounded automated correction run on 2026-08-06 selected the dotenv source
  but returned `is_login=false` before any dataset request. It completed in
  under five seconds and did not retry. This non-reproduction does not erase
  the direct entitlement proof, but current authentication availability must be
  reconfirmed after entitlement is granted.

The package also exposes FiinGroup gateway-backed research helpers, but no
installed evidence proves that FiinQuantX credentials authorize the separate
FiinGroup DataFeed `/Financial/GetProprietaryTradingStock` contract. That
DataFeed operation was not called.

### FiinGroup API Datafeed

Official operation:
[`/Financial/GetProprietaryTradingStock`](https://datafeed.fiingroup.vn/api-giao-dich/tu-doanh/tu-doanh/giao-dich-tu-doanh).

The official public schema includes symbol and trading-date identity, total
gross buy/sell volume and value, matched gross buy/sell volume and value,
negotiated-deal gross buy/sell volume and value, plus `CreateDate` and
`UpdateDate`. Those timestamps describe record creation/update; they do not by
themselves prove intraday publication.

Local gate:

- No official FiinGroup DataFeed client/package is installed.
- No FiinGroup DataFeed configuration key name was found.
- Existing `FIINQUANT_*` names belong to FiinQuantX and must not be reused or
  treated as FiinGroup DataFeed authorization.
- Authentication shape, entitlement, production base URL, rate limits,
  publication cadence, corrections, and application/redistribution rights are
  not proven locally.
- Classification: `UNAVAILABLE` / `CONFIGURATION_REQUIRED`.

### Vnstock Data

Official Sponsor operations:

- [`Market().equity(symbol).proprietary_flow()`](https://vnstocks.com/docs/vnstock-data/market-layer-v3)
- [`Insights().flow.proprietary(exchange="HOSE", group_by="stock")`](https://vnstocks.com/docs/vnstock-data/insights-layer-v3)

The official architecture identifies VCI as the routed source for equity
`proprietary_flow()`. The published Insights schema exposes rolling net
`volume_1d`/`value_1d` and longer-window fields, not proven gross buy/sell
families. It therefore cannot satisfy the StockClock gross-field contract from
documentation alone. The actual Market-layer raw schema still requires a
licensed runtime observation.

Local gate:

- Free `vnstock==4.0.4` is installed.
- Sponsor `vnstock_data` is not installed and cannot be replaced by the free
  package.
- Official documentation says Sponsor installation uses a separate installer
  and membership, with tier limits of 180-600 requests/minute. Those limits do
  not prove a useful proprietary publication cadence.
- No Vnstock Data configuration key name was found locally.
- Runtime route, current-date availability, gross-field completeness,
  provider timestamps, update semantics, corrections, and licence suitability
  were not observed.
- Classification: `UNAVAILABLE` / `PROVIDER_PACKAGE_MISSING`.

## P0 contract

The manual diagnostic is
`scripts/diagnose_vn_proprietary_capability.py`. It:

- tests FPT, SSI, HPG, VPB, and VIC by default;
- audits field presence before normalization;
- distinguishes explicit zero, null, absent, missing row, and parse failure;
- derives net only from complete gross pairs;
- treats changing REST snapshots as `NEAR_REALTIME_POLLING`, never streaming;
- requires direct push evidence for `REALTIME`;
- owns one Sponsor client lifecycle inside a hard-bounded child process;
- inspects the FiinQuantX public contract offline and, with `--live`, owns a
  separate 60-second authentication/request child process;
- discards provider stdout/stderr and exposes only typed authentication,
  package, request-count, schema-presence, and freshness evidence;
- emits sanitized JSON and CSV under `.tmp`;
- supports cleanup and graceful interruption;
- reports process/dotenv credential presence and equality only, never values;
- supports diagnostic-only `auto`, `dotenv`, and `process` source policies;
- captures package stdout/stderr only long enough to recognize the narrow
  permission-denied marker, then discards it;
- stops after the first entitlement failure and makes at most two dataset calls;
- never writes application cache or enables a production provider.

Only after `get_value_by_investor()` entitlement succeeds, use this bounded
active-session command:

```powershell
python scripts\diagnose_vn_proprietary_capability.py `
  --live `
  --credential-source dotenv `
  --symbols FPT,SSI,HPG,VPB,VIC `
  --duration-seconds 1200 `
  --interval-seconds 15 `
  --output-dir .tmp\vn-proprietary-p0 `
  --cleanup
```

Do not run that 20-minute probe while entitlement remains denied. A 15-second
product cadence is not authorized until a configured provider demonstrates
repeated active-session changes and sufficient rate-limit headroom.

## P1 gate

P1 may begin only after one candidate proves all required active-session
conditions: current Vietnam date, gross buy and sell fields, repeatable value
changes, advancing provider publication evidence, clear cumulative/delta
semantics, safe request headroom, and suitable application rights.

Until then:

- SSI continues to own price, foreign flow, and VN30 membership only.
- SSI `indexSummary` is not proprietary flow.
- No alternative-provider runtime or fallback is selected.
- No current proprietary row, aggregate, polling owner, durable history, or
  frontend capability is added.
- Missing proprietary values remain unavailable, never zero-filled.
