# VN Security And Secrets

## Purpose

VN dashboard work touches authenticated SSI FastConnect data. Documentation, diagnostics, tests, and handoff packages must never expose secrets or raw auth material.

## SSI FastConnect Secret Handling

SSI credentials must come from environment variables or a secret manager only:

- `SSI_FASTCONNECT_CONSUMER_ID`
- `SSI_FASTCONNECT_CONSUMER_SECRET`

Never print, commit, copy into docs, or include in test fixtures:

- Consumer IDs or consumer secrets.
- Access tokens.
- Auth headers.
- Account IDs.
- Raw auth responses.
- Signed URLs or provider payloads containing private auth/account fields.

## Forbidden Files And Artifacts

Do not include:

- `.env`
- local secret files
- npm cache
- temp cache
- provider auth logs
- raw API dumps that contain secrets
- raw auth responses
- account/order/trading outputs

No SSI FC Trading, order, account, cash transfer, stock transfer, or portfolio trading APIs are supported by the VN dashboard.

## Allowed Diagnostics

Allowed in docs/logs/handoff:

- Provider name.
- Endpoint label.
- HTTP status.
- Sanitized error summary.
- Retryable flag.
- Stale-date mismatch.
- Row counts.
- Normalized field names.

Examples:

```text
SSI realtime unavailable. HTTP 404. retryable=false.
SSI intraday stale. latest_intraday_date=2026-06-15 daily_price_date=2026-06-22.
```

## Redaction Examples

Use placeholders:

```text
SSI_FASTCONNECT_CONSUMER_ID=<set in secret env>
SSI_FASTCONNECT_CONSUMER_SECRET=<set in secret env>
Authorization=<redacted>
access_token=<redacted>
```

Do not use realistic-looking fake secrets. They can be copied accidentally.

## Handoff Package Safety Checklist

Before zipping or sharing `.handoff`:

1. Confirm `.env` is not copied.
2. Confirm API snapshots do not contain auth headers, account IDs, tokens, or raw auth responses.
3. Confirm security scan hits are placeholders or guardrail wording only.
4. Delete or redact any file with real values.
5. Keep `security_scan_hits.txt` in the handoff package so reviewers can audit the scan.

Recommended scan:

```powershell
Get-ChildItem .handoff -Recurse -File |
  Select-String -Pattern "token|secret|authorization|bearer|consumer|password|apikey|api_key|access_token|private_key" -CaseSensitive:$false |
  Out-String -Width 240 > .handoff\security_scan_hits.txt
```

Docs-only scan:

```powershell
Select-String -Path docs\*.md -Pattern "token|secret|authorization|bearer|consumer|password|apikey|api_key|access_token|private_key" -CaseSensitive:$false
```

## Raw Auth Response Rule

Raw auth responses are never allowed in docs, tests, fixtures, handoff packages, or screenshots. If a response shape must be documented, use a synthetic minimal example with all values redacted.
