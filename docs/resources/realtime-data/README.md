# Vietnam Realtime Data Resources

This directory stores reference resources for possible Vietnam realtime stock data providers.

These files are reference-only. Do not implement a provider, add new API calls, scrape websites, or change dashboard behavior from these notes unless the user explicitly approves a scoped implementation task first.

Rules for every resource in this directory:

- Do not store secrets, API keys, account IDs, tokens, cookies, or private credentials in docs.
- Sanitize sample responses before committing them.
- Respect provider terms, license boundaries, and rate limits.
- Confirm timestamp timezone before using any data.
- Confirm price semantics before using any price field, including whether it is a realtime matched price, delayed price, OHLCV candle value, bid, ask, or indicative value.
- Mozyfin remains the active Vietnam dashboard provider unless changed by a decision record.
- Any future implementation must summarize auth, rate limits, timestamp semantics, and price/data semantics before code changes.

Paste provider-specific API docs into the matching provider file under the `Paste API docs here` section.
