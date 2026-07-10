"""Vnstock News experimental connector modes.

The Vnstock News documentation describes RSS and historical crawler APIs, but
current Vnstock licensing requires written approval before commercial product
integration.  The production ``vnstock_news`` mode therefore remains a no-fetch
terms gate.  ``vnstock_news_personal`` is a separate local research mode that
imports the optional package lazily and only uses the documented RSS Crawler.
"""

from __future__ import annotations

import importlib
import inspect
import re
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


VNSTOCK_NEWS_PROVIDER = "vnstock_news"
VNSTOCK_NEWS_PERSONAL_PROVIDER = "vnstock_news_personal"
VNSTOCK_NEWS_SOURCE = "Vnstock News"
VNSTOCK_NEWS_RIGHTS_STATUS = "blocked_pending_terms"
VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS = "personal_research_only"
VNSTOCK_NEWS_PERSONAL_MODE = "local_personal_research_only"
VNSTOCK_NEWS_BLOCKED_MESSAGE = (
    "Vnstock News is unavailable pending written commercial and source-owner terms."
)
VNSTOCK_NEWS_PERSONAL_DISABLED_MESSAGE = (
    "Vnstock News personal mode requires VNSTOCK_NEWS_PERSONAL_ENABLED=true."
)
VNSTOCK_NEWS_PACKAGE_MISSING_MESSAGE = (
    "Optional package vnstock_news is not installed; personal news mode cannot fetch articles."
)
VNSTOCK_NEWS_DEFAULT_SITES = ("vnexpress", "cafef")
VNSTOCK_NEWS_MAX_LIMIT_PER_SITE = 20


class VnstockNewsProvider:
    """Expose Vnstock News legal gate and optional local personal RSS mode."""

    def __init__(
        self,
        *,
        provider: str = VNSTOCK_NEWS_PROVIDER,
        personal_enabled: bool = False,
        sites: Optional[Sequence[str] | str] = None,
        limit_per_site: int = 5,
        timeout_seconds: int = 10,
        include_content: bool = False,
    ) -> None:
        self.provider = str(provider or VNSTOCK_NEWS_PROVIDER).strip().lower()
        self.personal_enabled = bool(personal_enabled)
        self.sites = _normalize_sites(sites)
        self.limit_per_site = _bounded_int(limit_per_site, 1, VNSTOCK_NEWS_MAX_LIMIT_PER_SITE, 5)
        self.timeout_seconds = _bounded_int(timeout_seconds, 1, 60, 10)
        self.include_content = bool(include_content)

    @staticmethod
    def blocked_status() -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "source": VNSTOCK_NEWS_SOURCE,
            "provider": VNSTOCK_NEWS_PROVIDER,
            "items": [],
            "message": VNSTOCK_NEWS_BLOCKED_MESSAGE,
            "reason_code": VNSTOCK_NEWS_RIGHTS_STATUS,
            "rights_status": VNSTOCK_NEWS_RIGHTS_STATUS,
            "provenance": "Vnstock News RSS/feed documentation; no runtime request made.",
        }

    @staticmethod
    def personal_disabled_status() -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "source": VNSTOCK_NEWS_SOURCE,
            "provider": VNSTOCK_NEWS_PERSONAL_PROVIDER,
            "provider_mode": VNSTOCK_NEWS_PERSONAL_MODE,
            "items": [],
            "message": VNSTOCK_NEWS_PERSONAL_DISABLED_MESSAGE,
            "reason_code": "local_personal_research_disabled",
            "rights_status": VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
            "provenance": "Vnstock News personal mode was selected but not explicitly enabled.",
        }

    @staticmethod
    def package_missing_status() -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "source": VNSTOCK_NEWS_SOURCE,
            "provider": VNSTOCK_NEWS_PERSONAL_PROVIDER,
            "provider_mode": VNSTOCK_NEWS_PERSONAL_MODE,
            "items": [],
            "message": VNSTOCK_NEWS_PACKAGE_MISSING_MESSAGE,
            "reason_code": "provider_package_missing",
            "rights_status": VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
        }

    def fetch_recent_news(
        self,
        *,
        tickers: Optional[Iterable[str]] = None,
        limit_per_site: Optional[int] = None,
        sites: Optional[Sequence[str] | str] = None,
        include_content: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Fetch bounded recent RSS/feed articles only for explicit personal mode."""
        if self.provider != VNSTOCK_NEWS_PERSONAL_PROVIDER:
            return self.blocked_status()
        if not self.personal_enabled:
            return self.personal_disabled_status()

        effective_sites = _normalize_sites(sites) if sites is not None else self.sites
        effective_limit = _bounded_int(
            limit_per_site if limit_per_site is not None else self.limit_per_site,
            1,
            VNSTOCK_NEWS_MAX_LIMIT_PER_SITE,
            self.limit_per_site,
        )
        effective_include_content = self.include_content if include_content is None else bool(include_content)

        try:
            vnstock_news = importlib.import_module("vnstock_news")
        except ModuleNotFoundError:
            return self.package_missing_status()
        except Exception as exc:  # noqa: BLE001 - optional connector must fail closed.
            return _unavailable_status("provider_import_error", f"Vnstock News import failed: {_safe_error(exc)}")

        crawler_cls = getattr(vnstock_news, "Crawler", None)
        if crawler_cls is None:
            return _unavailable_status("provider_package_missing", "vnstock_news.Crawler is unavailable.")

        fetched_at = datetime.now(timezone.utc).isoformat()
        raw_articles: List[Mapping[str, Any]] = []
        site_errors: List[Dict[str, str]] = []
        for site_name in effective_sites:
            try:
                raw_articles.extend(
                    self._fetch_site_articles(
                        crawler_cls,
                        site_name=site_name,
                        limit_per_feed=effective_limit,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - keep per-site failures non-fatal.
                site_errors.append({"site": site_name, "error": _safe_error(exc)})

        if not raw_articles:
            if site_errors:
                return _unavailable_status(
                    "provider_error",
                    "Vnstock News personal fetch failed for all configured sites.",
                    diagnostics={"site_errors": site_errors[:3]},
                )
            return _unavailable_status(
                "provider_no_items",
                "Vnstock News personal feed returned no recent articles.",
            )

        items = normalize_vnstock_news_items(
            raw_articles,
            source=VNSTOCK_NEWS_SOURCE,
            limit=effective_limit * max(1, len(effective_sites)),
            fetched_at=fetched_at,
            include_content=effective_include_content,
            provider_mode=VNSTOCK_NEWS_PERSONAL_MODE,
            rights_status=VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
            tickers=tickers,
        )
        if not items:
            message = "No recent Vnstock News articles matched the requested ticker in title or summary."
            return {
                "status": "ok",
                "source": VNSTOCK_NEWS_SOURCE,
                "provider": VNSTOCK_NEWS_PERSONAL_PROVIDER,
                "provider_mode": VNSTOCK_NEWS_PERSONAL_MODE,
                "items": [],
                "message": message,
                "reason_code": "ticker_no_weak_match",
                "rights_status": VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
                "count": 0,
                "provider_items_count": len(raw_articles),
                "fetched_at": fetched_at,
            }

        return {
            "status": "ok",
            "source": VNSTOCK_NEWS_SOURCE,
            "provider": VNSTOCK_NEWS_PERSONAL_PROVIDER,
            "provider_mode": VNSTOCK_NEWS_PERSONAL_MODE,
            "items": items,
            "message": "Vnstock News personal research feed loaded.",
            "reason_code": "local_personal_research_only",
            "rights_status": VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
            "count": len(items),
            "provider_items_count": len(raw_articles),
            "fetched_at": fetched_at,
            "sites": list(effective_sites),
            "diagnostics": {"site_error_count": len(site_errors)},
        }

    def _fetch_site_articles(
        self,
        crawler_cls: Any,
        *,
        site_name: str,
        limit_per_feed: int,
    ) -> List[Mapping[str, Any]]:
        crawler_kwargs: Dict[str, Any] = {"site_name": site_name}
        if _callable_accepts(crawler_cls, "timeout"):
            crawler_kwargs["timeout"] = self.timeout_seconds
        crawler = crawler_cls(**crawler_kwargs)
        feed_method = getattr(crawler, "get_articles_from_feed")
        if _callable_accepts(feed_method, "limit_per_feed"):
            payload = feed_method(limit_per_feed=limit_per_feed)
        else:
            payload = feed_method(limit_per_feed)
        articles = _coerce_articles(payload)
        tagged_articles = []
        for article in articles:
            tagged = dict(article)
            tagged.setdefault("__site_name", site_name)
            tagged_articles.append(tagged)
        return tagged_articles


def normalize_vnstock_news_item(
    article: Mapping[str, Any],
    *,
    source: str,
    fetched_at: Optional[str] = None,
    include_content: bool = False,
    provider_mode: str = VNSTOCK_NEWS_PERSONAL_MODE,
    rights_status: str = VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
    tickers: Optional[Iterable[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Normalize a documented Vnstock article shape without fetching it.

    This is a contract proof for mocked/offline inputs.  Runtime display remains
    blocked, and ``content`` stays omitted unless a future approved internal
    mode explicitly permits it.
    """
    title = _text(article.get("title"))
    url = _text(article.get("url"))
    if not title or not url:
        return None

    published_at = _text(article.get("publish_time"))
    content = _text(article.get("content"))
    ticker_relevance = _weak_ticker_relevance(article, tickers)
    if tickers is not None and ticker_relevance is None:
        return None

    provider_id = (
        VNSTOCK_NEWS_PERSONAL_PROVIDER
        if provider_mode == VNSTOCK_NEWS_PERSONAL_MODE
        else VNSTOCK_NEWS_PROVIDER
    )
    article_source = _text(article.get("source") or article.get("source_name") or article.get("__site_name"))
    identity = "|".join((provider_id, url, title, published_at or ""))
    item: Dict[str, Any] = {
        "id": f"{provider_id}:{sha256(identity.encode('utf-8')).hexdigest()[:24]}",
        "ticker": None,
        "source": _text(source) or VNSTOCK_NEWS_SOURCE,
        "provider": provider_id,
        "provider_mode": provider_mode,
        "source_name": article_source,
        "source_url": url,
        "title": title,
        "summary": _text(article.get("short_description")),
        "url": url,
        "published_at": published_at,
        "author": _text(article.get("author")),
        "category": _text(article.get("category")),
        "image_url": _text(article.get("image_url")),
        "content_available": bool(content),
        "content": content if include_content else None,
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
        "provenance": {"provider": provider_id, "source_url": url, "source_name": article_source},
        "rights_status": rights_status,
        "ticker_relevance": ticker_relevance,
    }
    return item


def normalize_vnstock_news_items(
    articles: Iterable[Mapping[str, Any]],
    *,
    source: str,
    limit: int,
    fetched_at: Optional[str] = None,
    include_content: bool = False,
    provider_mode: str = VNSTOCK_NEWS_PERSONAL_MODE,
    rights_status: str = VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
    tickers: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Return at most ``limit`` usable normalized rows from offline inputs."""
    bounded_limit = max(0, int(limit))
    if bounded_limit == 0:
        return []
    items: List[Dict[str, Any]] = []
    for article in articles:
        if not isinstance(article, Mapping):
            continue
        item = normalize_vnstock_news_item(
            article,
            source=source,
            fetched_at=fetched_at,
            include_content=include_content,
            provider_mode=provider_mode,
            rights_status=rights_status,
            tickers=tickers,
        )
        if item is not None:
            items.append(item)
        if len(items) >= bounded_limit:
            break
    return items


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _normalize_sites(values: Optional[Sequence[str] | str]) -> List[str]:
    if values is None:
        return list(VNSTOCK_NEWS_DEFAULT_SITES)
    raw_values: Iterable[Any]
    if isinstance(values, str):
        raw_values = values.split(",")
    else:
        raw_values = values
    sites: List[str] = []
    seen = set()
    for value in raw_values:
        site = re.sub(r"[^a-z0-9_-]", "", str(value or "").strip().lower())
        if not site or site in seen:
            continue
        seen.add(site)
        sites.append(site)
    return sites or list(VNSTOCK_NEWS_DEFAULT_SITES)


def _bounded_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(minimum, min(maximum, parsed))


def _callable_accepts(target: Any, parameter_name: str) -> bool:
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return False
    return parameter_name in signature.parameters


def _coerce_articles(payload: Any) -> List[Mapping[str, Any]]:
    if payload is None:
        return []
    if hasattr(payload, "to_dict"):
        try:
            records = payload.to_dict("records")
            return [row for row in records if isinstance(row, Mapping)]
        except Exception:  # noqa: BLE001 - tolerate third-party object quirks.
            return []
    if isinstance(payload, Mapping):
        for key in ("articles", "items", "data", "rows"):
            value = payload.get(key)
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
                return [row for row in value if isinstance(row, Mapping)]
        return [payload]
    if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
        return [row for row in payload if isinstance(row, Mapping)]
    return []


def _weak_ticker_relevance(
    article: Mapping[str, Any],
    tickers: Optional[Iterable[str]],
) -> Optional[Dict[str, Any]]:
    normalized = [
        str(ticker or "").strip().upper().removesuffix(".VN")
        for ticker in tickers or []
        if str(ticker or "").strip()
    ]
    if not normalized:
        return None
    text = " ".join(
        str(article.get(key) or "")
        for key in ("title", "short_description")
    ).upper()
    matches = [
        ticker
        for ticker in normalized
        if re.search(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])", text)
    ]
    if not matches:
        return None
    return {
        "method": "weak_exact_symbol_match",
        "confidence": "weak",
        "tickers": matches,
    }


def _safe_error(exc: Exception) -> str:
    text = str(exc or "").strip() or exc.__class__.__name__
    lowered = text.lower()
    if any(marker in lowered for marker in ("token", "secret", "authorization", "bearer", "cookie", "account")):
        return exc.__class__.__name__
    return text[:160]


def _unavailable_status(
    reason_code: str,
    message: str,
    *,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "status": "unavailable",
        "source": VNSTOCK_NEWS_SOURCE,
        "provider": VNSTOCK_NEWS_PERSONAL_PROVIDER,
        "provider_mode": VNSTOCK_NEWS_PERSONAL_MODE,
        "items": [],
        "message": message,
        "reason_code": reason_code,
        "rights_status": VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
    }
    if diagnostics:
        payload["diagnostics"] = diagnostics
    return payload
