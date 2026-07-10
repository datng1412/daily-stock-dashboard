"""Offline contract tests for Vnstock News experimental modes."""

import sys
from types import SimpleNamespace

from data_provider.vnstock_news_provider import (
    VNSTOCK_NEWS_BLOCKED_MESSAGE,
    VNSTOCK_NEWS_PERSONAL_PROVIDER,
    VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS,
    VNSTOCK_NEWS_RIGHTS_STATUS,
    VnstockNewsProvider,
    normalize_vnstock_news_items,
)


def test_vnstock_news_gate_never_fetches_when_terms_are_unapproved():
    payload = VnstockNewsProvider().fetch_recent_news(limit_per_site=10)

    assert payload["status"] == "unavailable"
    assert payload["reason_code"] == VNSTOCK_NEWS_RIGHTS_STATUS
    assert payload["items"] == []
    assert payload["message"] == VNSTOCK_NEWS_BLOCKED_MESSAGE


def test_normalizer_preserves_provenance_and_omits_full_content_by_default():
    items = normalize_vnstock_news_items(
        [
            {
                "url": "https://example.test/article-1",
                "title": "Vietnam market update",
                "short_description": "A bounded summary.",
                "content": "Full article body must not be displayed by default.",
                "publish_time": "2026-07-10T09:00:00+07:00",
                "author": "Example author",
                "category": "market",
                "image_url": "https://example.test/image.jpg",
            }
        ],
        source="Example publisher",
        limit=1,
        fetched_at="2026-07-10T02:00:00+00:00",
    )

    assert len(items) == 1
    item = items[0]
    assert item["url"] == "https://example.test/article-1"
    assert item["provenance"]["source_url"] == item["url"]
    assert item["content_available"] is True
    assert item["content"] is None
    assert item["rights_status"] == VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS
    assert item["provider"] == VNSTOCK_NEWS_PERSONAL_PROVIDER


def test_normalizer_is_bounded_and_discards_unusable_rows():
    items = normalize_vnstock_news_items(
        [
            {"url": "https://example.test/missing-title"},
            {"url": "https://example.test/one", "title": "One"},
            {"url": "https://example.test/two", "title": "Two"},
        ],
        source="Example publisher",
        limit=1,
        fetched_at="2026-07-10T02:00:00+00:00",
    )

    assert [item["title"] for item in items] == ["One"]


def test_personal_mode_requires_explicit_enablement():
    payload = VnstockNewsProvider(provider=VNSTOCK_NEWS_PERSONAL_PROVIDER).fetch_recent_news()

    assert payload["status"] == "unavailable"
    assert payload["reason_code"] == "local_personal_research_disabled"
    assert payload["items"] == []


def test_personal_mode_reports_missing_optional_package(monkeypatch):
    monkeypatch.delitem(sys.modules, "vnstock_news", raising=False)

    payload = VnstockNewsProvider(
        provider=VNSTOCK_NEWS_PERSONAL_PROVIDER,
        personal_enabled=True,
    ).fetch_recent_news()

    assert payload["status"] == "unavailable"
    assert payload["reason_code"] == "provider_package_missing"
    assert payload["items"] == []


def test_personal_mode_normalizes_mocked_crawler_success(monkeypatch):
    class FakeCrawler:
        def __init__(self, site_name):
            self.site_name = site_name

        def get_articles_from_feed(self, limit_per_feed):
            return [
                {
                    "url": f"https://example.test/{self.site_name}/fpt",
                    "title": "FPT reports technology update",
                    "short_description": "FPT expands cloud services.",
                    "content": "Full article body should stay hidden.",
                    "publish_time": "2026-07-10T09:00:00+07:00",
                    "author": "Example",
                    "category": "business",
                    "image_url": "https://example.test/image.jpg",
                },
                {
                    "url": f"https://example.test/{self.site_name}/market",
                    "title": "Market update",
                    "short_description": "No requested symbol here.",
                },
            ][:limit_per_feed]

    monkeypatch.setitem(sys.modules, "vnstock_news", SimpleNamespace(Crawler=FakeCrawler))

    payload = VnstockNewsProvider(
        provider=VNSTOCK_NEWS_PERSONAL_PROVIDER,
        personal_enabled=True,
        sites="vnexpress",
        limit_per_site=2,
    ).fetch_recent_news(tickers=["FPT"])

    assert payload["status"] == "ok"
    assert payload["reason_code"] == "local_personal_research_only"
    assert payload["rights_status"] == VNSTOCK_NEWS_PERSONAL_RIGHTS_STATUS
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["title"] == "FPT reports technology update"
    assert item["source"] == "Vnstock News"
    assert item["source_name"] == "vnexpress"
    assert item["content_available"] is True
    assert item["content"] is None
    assert item["ticker_relevance"]["confidence"] == "weak"


def test_personal_mode_fetch_failure_is_unavailable(monkeypatch):
    class FailingCrawler:
        def __init__(self, site_name):
            self.site_name = site_name

        def get_articles_from_feed(self, limit_per_feed):
            raise RuntimeError("network unavailable")

    monkeypatch.setitem(sys.modules, "vnstock_news", SimpleNamespace(Crawler=FailingCrawler))

    payload = VnstockNewsProvider(
        provider=VNSTOCK_NEWS_PERSONAL_PROVIDER,
        personal_enabled=True,
        sites="vnexpress",
    ).fetch_recent_news()

    assert payload["status"] == "unavailable"
    assert payload["reason_code"] == "provider_error"
    assert payload["items"] == []
