# Vietnam News Source Resources

This directory stores reference resources for possible Vietnam stock news sources.

These files are reference-only. Do not implement a provider, add new API calls, scrape websites, or change dashboard behavior from these notes unless the user explicitly approves a scoped implementation task first.

Rules for every resource in this directory:

- Do not store secrets, API keys, account IDs, tokens, cookies, or private credentials in docs.
- Sanitize sample responses before committing them.
- Respect source terms, license boundaries, robots policies, and rate limits.
- Confirm published-time format and timezone before using any article timestamp.
- Confirm ticker mapping and company-name matching behavior before using any source for ticker news.
- Mozyfin remains the active Vietnam dashboard provider unless changed by a decision record.
- Current Mozyfin news behavior remains unchanged until an approved implementation task changes it.
- Any future implementation must summarize auth, rate limits, timestamp semantics, and data semantics before code changes.

Paste source-specific API docs or notes into the matching source file under the `Paste API docs here` section.
