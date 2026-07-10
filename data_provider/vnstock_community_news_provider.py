"""Bounded local/personal company-news adapter for Vnstock Community.

This module deliberately uses only ``Reference().company(ticker).news()`` from
the installed ``vnstock`` Community package.  It is separate from the optional
Sponsor ``vnstock_news`` RSS package and never supplies market-data fields.
"""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib
import ipaddress
import re
from threading import RLock
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urljoin, urlparse


VNSTOCK_COMMUNITY_NEWS_PROVIDER = "vnstock_community"
VNSTOCK_COMMUNITY_NEWS_SOURCE = "Vnstock Community"
VNSTOCK_COMMUNITY_NEWS_MODE = "community_free_ticker_news"
VNSTOCK_COMMUNITY_NEWS_RIGHTS_STATUS = "personal_research_only"
VNSTOCK_COMMUNITY_NEWS_DEFAULT_LIMIT = 3
VNSTOCK_COMMUNITY_NEWS_MAX_LIMIT = 3
VNSTOCK_COMMUNITY_NEWS_CACHE_MAX_TICKERS = 128

# No relative URL base is registered yet.  The installed Vnstock KBS adapter
# proves its API host, but does not establish the public article-site origin
# for paths returned by ``Company.news()``.  Add an entry only after upstream
# source evidence proves that origin.
VERIFIED_NEWS_BASE_URLS: Mapping[str, str] = {}

_TICKER_PATTERN = re.compile(r"^[A-Z0-9]{2,10}$")
_COMMUNITY_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vnstock-community-news")
_CACHE_LOCK = RLock()


@dataclass(frozen=True)
class _CacheEntry:
    result: Dict[str, Any]
    fetched_at: datetime
    expires_at: datetime


_CACHE: "OrderedDict[str, _CacheEntry]" = OrderedDict()


def clear_vnstock_community_news_cache() -> None:
    """Clear the bounded process-local Community news cache for tests/diagnostics."""
    with _CACHE_LOCK:
        _CACHE.clear()


class VnstockCommunityNewsProvider:
    """Load at most three company-news headlines for one explicit ticker."""

    def __init__(
        self,
        *,
        limit_per_ticker: int = VNSTOCK_COMMUNITY_NEWS_DEFAULT_LIMIT,
        cache_ttl_seconds: int = 1800,
        timeout_seconds: int = 10,
    ) -> None:
        self.limit_per_ticker = _bounded_int(
            limit_per_ticker,
            1,
            VNSTOCK_COMMUNITY_NEWS_MAX_LIMIT,
            VNSTOCK_COMMUNITY_NEWS_DEFAULT_LIMIT,
        )
        self.cache_ttl_seconds = _bounded_int(cache_ttl_seconds, 60, 86_400, 1800)
        self.timeout_seconds = _bounded_int(timeout_seconds, 1, 60, 10)

    @staticmethod
    def disabled_status(ticker: Optional[str] = None) -> Dict[str, Any]:
        return _status(
            "disabled",
            "provider_disabled",
            "News disabled.",
            ticker=ticker,
        )

    def get_company_news(self, ticker: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Return a normalized, cached, ticker-specific Community news result."""
        normalized_ticker = _normalize_ticker(ticker)
        if normalized_ticker is None:
            return _status(
                "unavailable",
                "invalid_ticker",
                "Company news requires a valid Vietnam ticker.",
                ticker=_clean_ticker(ticker),
            )
        effective_limit = _bounded_int(
            limit if limit is not None else self.limit_per_ticker,
            1,
            VNSTOCK_COMMUNITY_NEWS_MAX_LIMIT,
            self.limit_per_ticker,
        )
        cached = _cache_get(normalized_ticker)
        if cached is not None and cached.expires_at > _utc_now():
            return _with_cache_metadata(cached.result, cache_status="hit", limit=effective_limit)

        try:
            future = _COMMUNITY_EXECUTOR.submit(self._fetch_uncached, normalized_ticker)
            result = future.result(timeout=self.timeout_seconds)
        except FutureTimeoutError:
            future.cancel()
            return _stale_or_unavailable(
                cached,
                ticker=normalized_ticker,
                reason_code="provider_timeout",
                message="Company news request timed out.",
                limit=effective_limit,
            )
        except ModuleNotFoundError:
            return _stale_or_unavailable(
                cached,
                ticker=normalized_ticker,
                reason_code="provider_package_missing",
                message="Vnstock Community package is not available in this backend environment.",
                limit=effective_limit,
            )
        except Exception:  # noqa: BLE001 - optional news must never break stock data.
            return _stale_or_unavailable(
                cached,
                ticker=normalized_ticker,
                reason_code="provider_error",
                message="Company news is temporarily unavailable.",
                limit=effective_limit,
            )

        if result.get("status") == "ok":
            _cache_put(normalized_ticker, result, self.cache_ttl_seconds)
        return _with_cache_metadata(result, cache_status="refresh" if cached else "miss", limit=effective_limit)

    @staticmethod
    def _fetch_uncached(ticker: str) -> Dict[str, Any]:
        module = importlib.import_module("vnstock")
        reference_cls = getattr(module, "Reference", None)
        if reference_cls is None:
            raise ModuleNotFoundError("vnstock.Reference is unavailable")
        frame = reference_cls().company(ticker).news()
        fetched_at = _utc_now().isoformat()
        items = normalize_vnstock_community_news_items(frame, ticker=ticker, fetched_at=fetched_at)
        if not items:
            return _status(
                "unavailable",
                "provider_no_items",
                "No company news was returned for this ticker.",
                ticker=ticker,
                fetched_at=fetched_at,
            )
        return {
            **_status(
                "ok",
                "community_news_ready",
                f"Vnstock Community company news loaded for {ticker}.",
                ticker=ticker,
                fetched_at=fetched_at,
            ),
            "items": items,
            "count": len(items),
        }


def normalize_vnstock_community_news_items(
    payload: Any,
    *,
    ticker: str,
    fetched_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Normalize an offline/mock Community DataFrame into at most three rows.

    ``head`` is deliberately not mapped: the installed package's source and
    current public documentation do not establish whether it is a headline,
    summary, or source label.  Relative URLs remain in ``raw_url`` only.
    """
    normalized_ticker = _normalize_ticker(ticker)
    if normalized_ticker is None:
        return []
    now = fetched_at or _utc_now().isoformat()
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in _records(payload):
        item = _normalize_item(row, ticker=normalized_ticker, fetched_at=now)
        if item is None:
            continue
        identity = f"id:{item['id']}" if _clean_text(row.get("article_id")) else (
            f"fallback:{_normalized_text(item['title'])}|{item.get('published_at') or ''}"
        )
        if identity in seen:
            continue
        seen.add(identity)
        items.append(item)
    items.sort(key=lambda item: _sort_timestamp(item.get("published_at")), reverse=True)
    return items[:VNSTOCK_COMMUNITY_NEWS_MAX_LIMIT]


def _normalize_item(row: Mapping[str, Any], *, ticker: str, fetched_at: str) -> Optional[Dict[str, Any]]:
    title = _clean_text(row.get("title"))
    if not title:
        return None
    raw_url = _clean_text(row.get("url"))
    published_at = _parse_timestamp(row.get("publish_time"))
    article_id = _clean_text(row.get("article_id"))
    identity = article_id or sha256(
        "|".join((ticker, title, published_at or "", raw_url or "")).encode("utf-8")
    ).hexdigest()[:24]
    item_id = article_id or f"{VNSTOCK_COMMUNITY_NEWS_PROVIDER}:{identity}"
    return {
        "id": item_id,
        "ticker": ticker,
        "source": VNSTOCK_COMMUNITY_NEWS_SOURCE,
        "provider": VNSTOCK_COMMUNITY_NEWS_SOURCE,
        "provider_mode": VNSTOCK_COMMUNITY_NEWS_MODE,
        "title": title,
        "published_at": published_at,
        "url": resolve_vnstock_community_article_url(raw_url),
        "raw_url": raw_url,
        "source_name": None,
        "summary": None,
        "category": None,
        "author": None,
        "image_url": None,
        "content": None,
        "content_available": False,
        "fetched_at": fetched_at,
        "provenance": {
            "provider": VNSTOCK_COMMUNITY_NEWS_SOURCE,
            "provider_method": "Reference().company(ticker).news()",
            "ticker": ticker,
            "article_id": article_id,
        },
        "rights_status": VNSTOCK_COMMUNITY_NEWS_RIGHTS_STATUS,
    }


def _records(payload: Any) -> Iterable[Mapping[str, Any]]:
    if payload is None:
        return []
    if hasattr(payload, "to_dict"):
        try:
            payload = payload.to_dict(orient="records")
        except TypeError:
            payload = payload.to_dict("records")
        except Exception:  # noqa: BLE001 - third-party DataFrame-like objects may be malformed.
            return []
    if isinstance(payload, Mapping):
        return [payload]
    if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
        return [row for row in payload if isinstance(row, Mapping)]
    return []


def _status(status: str, reason_code: str, message: str, *, ticker: Optional[str], fetched_at: Optional[str] = None) -> Dict[str, Any]:
    return {
        "status": status,
        "source": VNSTOCK_COMMUNITY_NEWS_SOURCE,
        "provider": VNSTOCK_COMMUNITY_NEWS_PROVIDER,
        "provider_mode": VNSTOCK_COMMUNITY_NEWS_MODE,
        "ticker": ticker,
        "items": [],
        "message": message,
        "reason_code": reason_code,
        "rights_status": VNSTOCK_COMMUNITY_NEWS_RIGHTS_STATUS,
        "fetched_at": fetched_at,
    }


def _stale_or_unavailable(
    cached: Optional[_CacheEntry],
    *,
    ticker: str,
    reason_code: str,
    message: str,
    limit: int,
) -> Dict[str, Any]:
    if cached is None or not cached.result.get("items"):
        return _with_cache_metadata(
            _status("unavailable", reason_code, message, ticker=ticker),
            cache_status="error",
            limit=limit,
        )
    stale = dict(cached.result)
    stale["status"] = "stale"
    stale["reason_code"] = reason_code
    stale["message"] = "Company news refresh failed; showing last known articles."
    return _with_cache_metadata(stale, cache_status="stale", limit=limit)


def _with_cache_metadata(result: Dict[str, Any], *, cache_status: str, limit: int) -> Dict[str, Any]:
    payload = dict(result)
    payload["items"] = [dict(item) for item in (result.get("items") or [])[:limit]]
    payload["count"] = len(payload["items"])
    payload["cache_status"] = cache_status
    return payload


def _cache_get(ticker: str) -> Optional[_CacheEntry]:
    with _CACHE_LOCK:
        entry = _CACHE.get(ticker)
        if entry is not None:
            _CACHE.move_to_end(ticker)
        return entry


def _cache_put(ticker: str, result: Dict[str, Any], ttl_seconds: int) -> None:
    now = _utc_now()
    entry = _CacheEntry(result=dict(result), fetched_at=now, expires_at=now + timedelta(seconds=ttl_seconds))
    with _CACHE_LOCK:
        _CACHE[ticker] = entry
        _CACHE.move_to_end(ticker)
        while len(_CACHE) > VNSTOCK_COMMUNITY_NEWS_CACHE_MAX_TICKERS:
            _CACHE.popitem(last=False)


def _normalize_ticker(value: Any) -> Optional[str]:
    ticker = _clean_ticker(value)
    return ticker if _TICKER_PATTERN.fullmatch(ticker or "") else None


def _clean_ticker(value: Any) -> Optional[str]:
    ticker = str(value or "").strip().upper()
    return ticker.removesuffix(".VN") or None


def _bounded_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _clean_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _parse_timestamp(value: Any) -> Optional[str]:
    text = _clean_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.isoformat()


def _sort_timestamp(value: Any) -> datetime:
    text = _parse_timestamp(value)
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def resolve_vnstock_community_article_url(
    raw_url: Optional[str],
    source_key: Optional[str] = None,
) -> Optional[str]:
    """Return a validated article URL without guessing an upstream origin.

    Absolute HTTP(S) URLs may be used as returned.  Relative paths can only be
    resolved through an explicitly verified provider-source base; unknown
    sources and protocol-relative inputs deliberately remain non-clickable.
    """
    candidate = _clean_text(raw_url)
    if not candidate or "\\" in candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme:
        return candidate if _is_safe_http_url(parsed) else None
    if candidate.startswith("//"):
        return None

    base_url = VERIFIED_NEWS_BASE_URLS.get((source_key or "").strip().lower())
    if not base_url:
        return None
    base = urlparse(base_url)
    resolved = urljoin(base_url, candidate)
    resolved_parsed = urlparse(resolved)
    if not _is_safe_http_url(resolved_parsed):
        return None
    if resolved_parsed.hostname != base.hostname:
        return None
    return resolved


def _is_safe_http_url(parsed: Any) -> bool:
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    hostname = parsed.hostname
    if not hostname or any(character.isspace() for character in hostname):
        return False
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    return all(
        label
        and not label.startswith("-")
        and not label.endswith("-")
        and re.fullmatch(r"[A-Za-z0-9-]+", label)
        for label in ascii_hostname.split(".")
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
