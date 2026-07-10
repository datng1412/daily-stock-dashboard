"""Offline tests for the bounded Vnstock Community company-news adapter."""

from __future__ import annotations

import sys
import time
from types import SimpleNamespace

import pandas as pd
import pytest

from data_provider import vnstock_community_news_provider as community


@pytest.fixture(autouse=True)
def _clear_cache():
    community.clear_vnstock_community_news_cache()
    yield
    community.clear_vnstock_community_news_cache()


def _install_reference(monkeypatch, rows, calls=None):
    class FakeCompany:
        def __init__(self, ticker):
            self.ticker = ticker

        def news(self):
            if calls is not None:
                calls.append(self.ticker)
            return pd.DataFrame(rows[self.ticker] if isinstance(rows, dict) else rows)

    class FakeReference:
        def company(self, ticker):
            return FakeCompany(ticker)

    monkeypatch.setitem(sys.modules, "vnstock", SimpleNamespace(Reference=FakeReference))


def test_invalid_ticker_is_safe_and_does_not_import_package(monkeypatch):
    monkeypatch.setattr(community.importlib, "import_module", lambda _name: pytest.fail("must not import"))

    result = community.VnstockCommunityNewsProvider().get_company_news("bad ticker")

    assert result["status"] == "unavailable"
    assert result["reason_code"] == "invalid_ticker"
    assert result["items"] == []


def test_normalizes_sorts_deduplicates_and_clamps_to_three(monkeypatch):
    _install_reference(monkeypatch, [
        {"article_id": "old", "title": "Old", "publish_time": "2026-07-08T09:00:00+07:00", "url": "/old"},
        {"article_id": "new", "title": "Newest", "publish_time": "2026-07-10T09:00:00+07:00", "url": "https://example.test/new"},
        {"article_id": "new", "title": "Newest duplicate", "publish_time": "2026-07-10T08:00:00+07:00", "url": "/duplicate"},
        {"article_id": "middle", "title": "Middle", "publish_time": "2026-07-09T09:00:00+07:00", "url": "/middle"},
        {"article_id": "fourth", "title": "Fourth", "publish_time": "2026-07-07T09:00:00+07:00", "url": "/fourth"},
        {"article_id": "skip", "title": "", "publish_time": "2026-07-11T09:00:00+07:00", "url": "/skip"},
    ])

    result = community.VnstockCommunityNewsProvider(limit_per_ticker=99).get_company_news("fpt", limit=99)

    assert result["status"] == "ok"
    assert result["reason_code"] == "community_news_ready"
    assert result["count"] == 3
    assert [item["title"] for item in result["items"]] == ["Newest", "Middle", "Old"]
    assert result["items"][0]["id"] == "new"
    assert result["items"][0]["url"] == "https://example.test/new"
    assert result["items"][1]["url"] is None
    assert result["items"][1]["raw_url"] == "/middle"
    assert result["items"][0]["summary"] is None
    assert result["items"][0]["source_name"] is None
    assert result["items"][0]["provenance"]["ticker"] == "FPT"


def test_missing_article_id_uses_a_stable_fallback_id(monkeypatch):
    rows = [{"title": "Fallback identity", "publish_time": "2026-07-10T09:00:00+07:00", "url": "/article"}]
    _install_reference(monkeypatch, rows)

    first = community.normalize_vnstock_community_news_items(rows, ticker="FPT", fetched_at="2026-07-10T02:00:00+00:00")
    second = community.normalize_vnstock_community_news_items(rows, ticker="FPT", fetched_at="2026-07-10T02:00:00+00:00")

    assert first[0]["id"] == second[0]["id"]
    assert first[0]["id"].startswith("vnstock_community:")


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        ("https://publisher.example/article", "https://publisher.example/article"),
        ("http://publisher.example/article", "http://publisher.example/article"),
        (" javascript:alert(1) ", None),
        ("data:text/html,unsafe", None),
        ("file:///C:/news.html", None),
        ("ftp://publisher.example/article", None),
        (r"C:\\news.html", None),
        ("//evil.example/article", None),
        ("https://user:pass@publisher.example/article", None),
        ("https://bad host/article", None),
        ("/relative-article", None),
    ],
)
def test_article_url_policy_accepts_only_safe_absolute_urls_until_a_source_base_is_verified(raw_url, expected):
    assert community.resolve_vnstock_community_article_url(raw_url, source_key="kbs") == expected


def test_unverified_source_relative_url_is_preserved_without_a_clickable_url():
    items = community.normalize_vnstock_community_news_items(
        [{"article_id": "relative", "title": "Relative article", "publish_time": "2026-07-10T09:00:00+07:00", "url": " article/path "}],
        ticker="FPT",
    )

    assert items[0]["raw_url"] == "article/path"
    assert items[0]["url"] is None


def test_package_missing_and_empty_frame_have_deterministic_statuses(monkeypatch):
    monkeypatch.setattr(community.importlib, "import_module", lambda _name: (_ for _ in ()).throw(ModuleNotFoundError()))
    missing = community.VnstockCommunityNewsProvider().get_company_news("FPT")
    assert missing["reason_code"] == "provider_package_missing"

    monkeypatch.undo()
    community.clear_vnstock_community_news_cache()
    _install_reference(monkeypatch, [])
    empty = community.VnstockCommunityNewsProvider().get_company_news("FPT")
    assert empty["status"] == "unavailable"
    assert empty["reason_code"] == "provider_no_items"


def test_provider_error_timeout_and_cache_are_nonfatal_and_isolated(monkeypatch):
    class BrokenReference:
        def company(self, _ticker):
            return self

        def news(self):
            raise RuntimeError("network unavailable")

    monkeypatch.setitem(sys.modules, "vnstock", SimpleNamespace(Reference=BrokenReference))
    failed = community.VnstockCommunityNewsProvider().get_company_news("FPT")
    assert failed["reason_code"] == "provider_error"

    class SlowReference:
        def company(self, _ticker):
            return self

        def news(self):
            time.sleep(1.1)
            return pd.DataFrame([])

    monkeypatch.setitem(sys.modules, "vnstock", SimpleNamespace(Reference=SlowReference))
    timeout = community.VnstockCommunityNewsProvider(timeout_seconds=1).get_company_news("HPG")
    assert timeout["reason_code"] == "provider_timeout"

    community.clear_vnstock_community_news_cache()
    calls: list[str] = []
    _install_reference(monkeypatch, {
        "FPT": [{"article_id": "fpt-1", "title": "FPT title", "publish_time": "2026-07-10T09:00:00+07:00", "url": "/fpt"}],
        "HPG": [{"article_id": "hpg-1", "title": "HPG title", "publish_time": "2026-07-10T09:00:00+07:00", "url": "/hpg"}],
    }, calls)
    provider = community.VnstockCommunityNewsProvider()
    assert provider.get_company_news("FPT")["cache_status"] == "miss"
    assert provider.get_company_news("FPT")["cache_status"] == "hit"
    assert provider.get_company_news("HPG")["cache_status"] == "miss"
    assert calls == ["FPT", "HPG"]
