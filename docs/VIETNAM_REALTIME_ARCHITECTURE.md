# Vietnam Realtime Quote Architecture

Last updated: 2026-06-10

## Purpose

This document defines the planned architecture for adding Vietnam realtime quote support as a separate optional dashboard data layer.

This is a design document only. It does not approve a vendor, implement vendor calls, add scraping, add endpoints, or change existing Mozyfin daily/intraday behavior.

## Current Daily And Intraday Semantics

The current Vietnam dashboard semantics remain unchanged:

- `latest_price` equals the Mozyfin daily OHLCV close.
- `intraday_pulse` is derived from Mozyfin 1H OHLCV candles.
- Mozyfin quote and foreign output are metadata only unless a source is proven to expose reliable matched-price semantics.
- The dashboard displays neutral condition labels only and does not emit buy/sell recommendations.

The current data layers are intentionally conservative because daily OHLCV close, 1H candles, and quote/foreign metadata have different freshness and meaning.

## Realtime Principle

Realtime matched price must be modeled as a separate data layer from daily close.

Rules:

- Do not overwrite `latest_price` with realtime matched price.
- Do not relabel daily OHLCV close as realtime.
- Do not mix realtime fields into daily OHLCV, Mozyfin quote, or intraday OHLCV cache entries.
- Frontend should show daily close and realtime matched price as separate fields.
- Realtime values must include source, timestamp, and realtime/delayed/stale status.

## Proposed Backend Interface

Use a VN-specific DTO instead of reusing generic realtime quote types directly, so the dashboard can preserve matched-price semantics explicitly.

```python
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class VietnamRealtimeQuote:
    symbol: str
    matched_price: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    volume: Optional[float]
    value: Optional[float]
    bid1: Optional[float]
    ask1: Optional[float]
    bid_volume1: Optional[float]
    ask_volume1: Optional[float]
    timestamp: Optional[str]
    source: str
    is_realtime: bool
    delay_seconds: Optional[int]
    status: str
    error: Optional[str]


class RealtimeQuoteProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        ...

    def get_quotes(self, symbols: list[str]) -> dict[str, VietnamRealtimeQuote]:
        ...
```

Provider design should be batch-first. Realtime vendors commonly rate-limit by request/session, and watchlist refreshes should fetch `FPT,VPB,GMD` in one provider call when the vendor supports it.

Provider implementations should normalize all vendor-specific symbol formats, timestamps, realtime/delayed flags, and bid/ask levels before returning `VietnamRealtimeQuote`.

## Proposed Endpoint

Future endpoint:

```text
GET /api/v1/stocks/vn/realtime?tickers=FPT,VPB,GMD
```

Expected response shape:

```json
{
  "market": "VN",
  "source": "provider_name",
  "is_realtime": true,
  "delay_seconds": 0,
  "last_refresh_time": "2026-06-10T09:30:00+07:00",
  "ttl_seconds": 5,
  "quotes": [
    {
      "symbol": "FPT",
      "matched_price": 123400,
      "change": 1200,
      "change_pct": 0.98,
      "volume": 1234567,
      "value": 152000000000,
      "bid1": 123300,
      "ask1": 123500,
      "bid_volume1": 1000,
      "ask_volume1": 1500,
      "timestamp": "2026-06-10T09:30:00+07:00",
      "source": "provider_name",
      "is_realtime": true,
      "delay_seconds": 0,
      "status": "ok",
      "error": null
    }
  ],
  "errors": {}
}
```

The endpoint should be additive. It should not mutate or backfill `/api/v1/stocks/vn/watchlist` daily fields during initial rollout.

## Proposed Frontend Display

The Vietnam dashboard should keep the current daily and intraday sections and add a separate realtime quote strip or column.

Display elements:

- Daily close: current Mozyfin daily OHLCV close.
- Realtime matched price: separate value from the realtime endpoint.
- Timestamp: provider timestamp or fetched timestamp with clear label.
- Best bid/ask: `bid1` / `ask1`, plus sizes when available.
- Badge:
  - `Realtime`
  - `Delayed`
  - `Stale`
  - `Daily only`

The UI must never label daily close as realtime. If no realtime provider is configured or a quote fails, the dashboard should keep showing daily-only data and mark the realtime area as `Daily only` or unavailable.

## Cache Rules

Add a separate cache bucket:

```python
VN_CACHE_TTL_SECONDS["realtime_quote"] = 3
```

Rules:

- Realtime quote TTL should be 3-15 seconds depending on vendor license, rate limits, and deployment mode.
- Stale threshold should be explicit, for example `max(30 seconds, 3 * ttl_seconds)`.
- Stale quote data may be displayed only with a `Stale` badge.
- Do not write realtime data into OHLCV daily cache.
- Do not write realtime data into Mozyfin quote/foreign cache.
- Do not write realtime data into intraday OHLCV cache.
- `force_refresh=true` semantics for watchlist should remain scoped to the current watchlist layers unless a separate realtime refresh parameter is explicitly designed.

## Candidate Providers

Investigate only official or commercial channels:

- SSI FastConnect Data.
- FiinGroup / FiinQuant / FiinTrade.
- Vietstock DataFeed.
- FireAnt official/commercial API only.
- ICE consolidated feed as an enterprise option for HOSE/Vietnam coverage, subject to contract confirmation.

Do not scrape public websites. Do not add unofficial endpoints. Do not reverse engineer browser APIs.

## Risks

- Licensing: realtime exchange data may require paid licensing and explicit redistribution rights.
- Redistribution restrictions: public dashboard deployment may be prohibited or require a different license tier.
- Rate limits: provider limits may force batching, backoff, or lower refresh rates.
- Public cloud deployment restrictions: some vendors restrict IPs, regions, or server-side redistribution.
- Credentials: keys and tokens must be kept in environment/config only and must never be logged.
- Downtime: dashboard must display provider status and stale/unavailable states without breaking daily data.
- Delayed vs realtime ambiguity: source delay must be explicit; delayed data must never be labeled realtime.

## Future Implementation Plan

Phase 1: docs only.

Phase 2: provider interface/stub with fixture-only tests and no vendor calls.

Phase 3: implement one official provider after credentials, license, timestamp semantics, delay semantics, rate limits, and redistribution rules are confirmed.

Phase 4: frontend realtime display as a separate strip or column next to daily close.

Phase 5: cache/stale monitoring, provider health, and operational diagnostics.
