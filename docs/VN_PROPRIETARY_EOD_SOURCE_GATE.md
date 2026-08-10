# Vietnam Proprietary EOD Source Gate

Last updated: 2026-08-06

## Outcome

`VN_PROPRIETARY_EOD_SOURCE_SAMPLE_REQUIRED`

## EOD-1 selected manual workflow (2026-08-06)

The EOD-0 spreadsheet source gate remains accurate for automated structured
ingestion: no free source-originated HOSE spreadsheet contract was proven.
EOD-1 therefore selects a narrower personal-use workflow that does not claim a
spreadsheet contract or parse the observed official PDF. A user manually reads
the official HOSE publication and enters required gross buy/sell value through
`scripts/record_vn_proprietary_eod.py`; gross volume is optional.

The CLI validates integer VND/share pairs and reconciliation, requires a source
URL plus explicit user verification, hashes an optional signature-valid PDF,
and otherwise requires `--source-file-unavailable`. It never downloads, parses,
OCRs, copies, or commits the PDF. Accepted rows persist atomically in the
separate `DATA_CACHE_DIR/vietnam_proprietary_flow_eod.v1.json` store. Conflicts
require explicit replacement and reason, and evidence cannot be weakened.
Read-only latest/history APIs and the EOD-only Proprietary tab expose this
manual dataset without polling or realtime claims. No real official row was
entered in EOD-1, so live manual acceptance remains pending.

This phase narrows the product requirement to completed end-of-day HOSE total
proprietary flow: gross buy/sell volume and value, with net values derived only
from complete gross pairs. Symbol UI, VN30/industry aggregation, intraday,
realtime streaming, polling, and top-symbol products are excluded.

No suitable real `.xlsx`, `.xls`, or `.csv` sample was found in the permitted
local locations. Public research found daily HOSE proprietary publications with
PDF attachments, plus authenticated/paid financial portals, but did not prove a
free source-originated spreadsheet contract. A PDF, screenshot, news summary,
or manually transcribed/converted table is not accepted by this gate. Therefore
no provider schema, header alias, unit, safe aggregation rule, or redistribution
right is classified as proven.

## Candidate assessment

| Candidate | Category | Access | Coverage and frequency | Gross fields | Format/access evidence | API/auth/payment | Automation and redistribution | Confidence |
|---|---|---|---|---|---|---|---|---|
| HOSE daily proprietary-trading publication, observed through a Vietstock mirror | `OFFICIAL_EXCHANGE` source identity; mirror is `PUBLIC_FINANCIAL_PORTAL` | `FREE_MANUAL_DOWNLOAD` for the observed attachment | HOSE, completed daily notices with historical pages | Attachment title indicates proprietary statistics; gross schema was not parsed because the observed file is PDF | Public notice and PDF attachment, not an allowed spreadsheet | No documented free API observed; no login observed for the mirrored attachment | `UNKNOWN`; public viewing/download does not establish automation or redistribution rights | Medium source identity; low spreadsheet-contract confidence |
| HNX official daily proprietary-by-symbol publication | `OFFICIAL_EXCHANGE` | `FREE_MANUAL_DOWNLOAD` | HNX/UPCoM rather than HOSE; completed daily files | Public page describes gross buy/sell volume and value by symbol | Official PDF attachment; unsupported for this HOSE spreadsheet gate | No documented spreadsheet API observed; public manual attachment | `UNKNOWN` | High for HNX schema, unusable for HOSE scope |
| FiinTrade platform export | `OFFICIAL_PROVIDER` | `PAID` | Multi-exchange platform with historical/end-of-day features | Platform documentation mentions investor-class data and proprietary views, but no inspected export schema | Documentation states tables can be exported to Excel | Account/subscription required; no free documented API established | Terms prohibit automated collection/reuse without prior written permission; redistribution rights not established | Medium candidate, fails free-access gate |
| FiinGroup DataFeed / FiinQuantX | `OFFICIAL_PROVIDER` | `PAID` | Historical provider operations | Installed registry declares gross proprietary families | Structured provider contract, but runtime dataset access is entitlement-denied | Authentication exists; proprietary entitlement/payment required | Contract-specific and unresolved for this application | High contract confidence, fails free-access gate |
| Broker/news market reports | `NEWS_SUMMARY` | `FREE_VIEW_ONLY` | Usually a daily net summary or top-symbol commentary | Commonly net value only; gross volume/value completeness not proven | HTML or PDF report | No suitable documented data API | `UNKNOWN` | Low; insufficient gross fields |

Reviewed public pages:

- [HOSE daily proprietary notice mirrored by Vietstock](https://vietstock.vn/2025/08/hose-thong-ke-giao-dich-tu-doanh-ngay-20-08-2025-830-1343936.htm)
- [Official HNX proprietary-by-symbol notice](https://www.hnx.vn/m-tin-tuc-hnx/Ket%20qua%20giao%20dich%20tu%20doanh%20theo%20ma%20chung%20khoan%20ngay%2021022024-60018302-1.html)
- [FiinTrade overview and Excel-export description](https://web.fiintrade.vn/nhom-trang-tinh-nang/tong-quan)
- [FiinTrade pricing](https://web.fiintrade.vn/en/pricing/)
- [FiinTrade terms](https://web.fiintrade.vn/quy-dinh-va-dieu-khoan)

No undocumented endpoint, browser-network call, HTML-table scrape,
authentication bypass, protected download, PDF parser, OCR, or provider file
download was used.

## Local sample search

The read-only search was limited to the allowed locations:

- `D:\Downloads`
- repository `.tmp`
- repository `data`
- repository `sample_data` (directory absent)

It searched only `.xlsx`, `.xls`, and `.csv` filenames containing conservative
proprietary/trading/HOSE terms. No candidate file was found. No unrelated
personal directory or file was inspected.

## Offline diagnostic contract

`scripts/diagnose_vn_proprietary_eod_source.py` is a manual, network-free file
schema diagnostic. It supports:

- `.csv`, `.xls`, and `.xlsx` input; PDF and images are rejected without OCR;
- bounded CSV encoding/delimiter detection;
- workbook sheets, hidden sheets, merged cells, formulas, header candidates,
  raw columns, row ranges, blanks, note/subtotal/detail/total/component counts;
- candidate canonical-field reporting without declaring provider aliases proven;
- HIGH/MEDIUM/LOW/UNKNOWN trading-date evidence, never filesystem mtime;
- separate volume/value unit proof and multipliers, never magnitude inference;
- HOSE total/detail/multi-exchange scope classification;
- total-versus-detail and total-versus-matched/deal reconciliation;
- `FIELD_PRESENT_VALUE`, `FIELD_PRESENT_ZERO`, `FIELD_NULL`, `FIELD_BLANK`,
  `FIELD_ABSENT`, and `PARSE_FAILURE` distinctions;
- derived net only from complete gross pairs;
- sanitized schema reports and a maximum five-row presence-only preview;
- strict mode and complete temporary-report cleanup.

Example after an acceptable source-originated sample is obtained:

```powershell
python scripts\diagnose_vn_proprietary_eod_source.py `
  --file "D:\Downloads\<source-sample>.xlsx" `
  --exchange HOSE `
  --output-dir .tmp\vn-proprietary-eod0 `
  --cleanup `
  --json `
  --strict
```

The tool does not write application history, mutate production cache, call an
API, upload/copy the input file, or retain real rows when cleanup is requested.

## Required real sample

The next gate needs one recent completed-session, source-originated `.xlsx`,
`.xls`, or `.csv` file obtained through a documented free manual-download path.
It must retain the provider's original headers, notes, units, date evidence,
exchange identity, total/detail/component row labels, and any formulas. It must
contain either:

1. one authoritative HOSE total with gross buy/sell volume and value; or
2. complete HOSE symbol details with explicit exchange classification and safe
   total/subtotal/matched/deal exclusion.

Do not supply a PDF conversion, screenshot extraction, copied HTML table, news
summary, or hand-built spreadsheet. The real file remains local and must not be
committed.

## Gate status

- Trading date: unproven; no sample.
- HOSE scope: unproven at spreadsheet level.
- Gross volume/value fields: unproven at spreadsheet level.
- Units: unproven.
- Total/detail reconciliation: not comparable.
- Missing-versus-zero behavior: enforced by the diagnostic, unobserved for a
  real provider file.
- Source quality: `INVALID_SCHEMA` / no sample.
- Schema proof: failed because the required real sample is absent.
- Production importer/API/UI: not entered.

The next permitted phase is a repeat of this schema gate with the exact real
sample above. Production integration may begin only after the source, free
access path, units, date, HOSE scope, gross families, reconciliation, and usage
rights all pass.
