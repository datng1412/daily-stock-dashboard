# Vietnam Realtime Data Resources

This directory stores reference resources for possible Vietnam realtime stock data providers.

These files are reference-only. Do not implement a provider, add new API calls, scrape websites, or change dashboard behavior from these notes unless the user explicitly approves a scoped implementation task first.

Rules for every resource in this directory:

- Do not store secrets, API keys, account IDs, tokens, cookies, or private credentials in docs.
- Sanitize sample responses before committing them.
- Respect provider terms, license boundaries, and rate limits.
- Confirm timestamp timezone before using any data.
- Confirm price semantics before using any price field, including whether it is a realtime matched price, delayed price, OHLCV candle value, bid, ask, or indicative value.
- Current decision records supersede older provider notes: the VN dashboard uses strict SSI mode for supported market data, Mozyfin is disabled for VN runtime, and KBS is legacy optional only behind explicit flags.
- Any future implementation must summarize auth, rate limits, timestamp semantics, and price/data semantics before code changes.

Paste provider-specific API docs into the matching provider file under the `Paste API docs here` section.
