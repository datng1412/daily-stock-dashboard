from __future__ import annotations

import sys

from api.v1.schemas.stocks import VietnamCorporateActionsResponse
from data_provider.corporate_actions_provider import CorporateActionEvent
from src.services.vietnam_market_service import VietnamDashboardConfig, VietnamMarketService


class ExplodingCorporateActionsProvider:
    provider_name = "fixture"

    def fetch_corporate_actions(self, tickers, *, months_back):  # pragma: no cover - failure path under test
        raise RuntimeError(
            "Authorization: Bearer live-token; accountId=acct-123; secret=raw-secret; "
            "raw provider payload should not escape"
        )


class DivergentItemsCorporateActionsProvider:
    provider_name = "fixture"

    def fetch_corporate_actions(self, tickers, *, months_back):
        del tickers, months_back
        return {
            "market": "VN",
            "status": "ok",
            "source": "CorporateActionsProvider",
            "provider": self.provider_name,
            "last_checked_at": "2026-06-29T00:00:00+00:00",
            "requested_tickers": ["FPT"],
            "months_back": 6,
            "events": [
                {
                    "ticker": "FPT",
                    "event_type": "cash_dividend",
                    "status": "upcoming",
                    "announcement_date": "2026-06-01",
                    "source": "fixture",
                    "provider_event_id": "canonical-event",
                }
            ],
            "items": [
                {
                    "ticker": "HPG",
                    "event_type": "meeting",
                    "status": "past",
                    "source": "fixture",
                    "provider_event_id": "legacy-item",
                }
            ],
            "diagnostics": {
                "provider": self.provider_name,
                "request_domain": "corporate_actions",
                "status": "ok",
                "row_count": 1,
                "failure_class": "ok",
                "last_checked_at": "2026-06-29T00:00:00+00:00",
            },
        }


def _service(**config_overrides) -> VietnamMarketService:
    return VietnamMarketService(
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
            allow_legacy_mozyfin_provider=False,
            allow_legacy_kbs_provider=False,
            **config_overrides,
        )
    )


def test_corporate_actions_disabled_by_default_returns_empty_lists():
    payload = _service().build_corporate_actions(["FPT", "HPG"], months_back=6)

    assert payload["status"] == "disabled"
    assert payload["source"] == "CorporateActionsProvider disabled"
    assert payload["provider"] == "disabled"
    assert payload["requested_tickers"] == ["FPT", "HPG"]
    assert payload["months_back"] == 6
    assert payload["events"] == []
    assert payload["items"] == []
    assert payload["diagnostics"]["request_domain"] == "corporate_actions"
    assert payload["diagnostics"]["failure_class"] == "provider_disabled"
    assert "inferred" in payload["error_detail"]
    assert "VNStocks" not in str(payload)
    assert "FiinGroup" not in str(payload)


def test_future_provider_name_is_classified_not_configured_without_import_or_call():
    sys.modules.pop("vnstocks", None)
    payload = _service(
        corporate_actions_provider_enabled=True,
        corporate_actions_provider="vnstocks",
    ).build_corporate_actions(["FPT"], months_back=3)

    assert payload["status"] == "not_configured"
    assert payload["provider"] == "vnstocks"
    assert payload["events"] == []
    assert payload["items"] == []
    assert payload["diagnostics"]["failure_class"] == "provider_not_configured"
    assert "No external provider was called." in payload["error_detail"]
    assert "vnstocks" not in sys.modules


def test_provider_failure_is_sanitized_and_optional():
    service = _service(
        corporate_actions_provider_enabled=True,
        corporate_actions_provider="manual",
    )
    service._corporate_actions_provider = ExplodingCorporateActionsProvider()

    payload = service.build_corporate_actions(["FPT"], months_back=6)
    rendered = str(payload)

    assert payload["status"] == "error"
    assert payload["events"] == []
    assert payload["items"] == []
    assert payload["diagnostics"]["failure_class"] == "provider_error"
    assert "live-token" not in rendered
    assert "acct-123" not in rendered
    assert "raw-secret" not in rendered
    assert "Corporate actions provider failed; SSI daily data remains independent." == payload["error_detail"]


def test_service_derives_legacy_items_from_canonical_events_when_provider_diverges():
    service = _service(
        corporate_actions_provider_enabled=True,
        corporate_actions_provider="manual",
    )
    service._corporate_actions_provider = DivergentItemsCorporateActionsProvider()

    payload = service.build_corporate_actions(["FPT"], months_back=6)

    assert payload["status"] == "ok"
    assert payload["events"] == payload["items"]
    assert payload["events"][0]["provider_event_id"] == "canonical-event"
    assert "legacy-item" not in str(payload)
    assert payload["diagnostics"]["row_count"] == 1


def test_normalized_event_contract_preserves_provenance_and_missing_fields():
    row = CorporateActionEvent(
        ticker="fpt",
        event_id="manual:FPT:2026-cash",
        event_type="dividend",
        title="Cash dividend approved",
        announcement_date="2026-06-01",
        ex_date="2026-06-20",
        record_date="2026-06-23",
        payment_date="2026-07-10",
        cash_dividend_per_share=1000.0,
        cash_dividend_currency="VND",
        source="manual import",
        source_url="https://example.test/source",
        provider="manual",
        provider_event_id="source-row-1",
        raw_available=False,
        confidence=0.9,
        status="upcoming",
        missing_fields=["source_document_url"],
    ).to_dict()

    assert row["ticker"] == "FPT"
    assert row["event_type"] == "cash_dividend"
    assert row["description"] == "Cash dividend approved"
    assert row["source_url"] == "https://example.test/source"
    assert row["missing_fields"] == ["source_document_url"]
    assert row["cash_dividend_per_share"] == 1000.0


def test_api_schema_accepts_events_and_legacy_items_alias_together():
    response = VietnamCorporateActionsResponse(
        status="disabled",
        source="CorporateActionsProvider disabled",
        provider="disabled",
        requested_tickers=["FPT"],
        months_back=6,
        events=[],
        items=[],
        diagnostics={"provider": "disabled", "row_count": 0},
    )

    assert response.status == "disabled"
    assert response.events == []
    assert response.items == []
    assert response.diagnostics["provider"] == "disabled"


def test_api_schema_derives_legacy_items_from_canonical_events():
    response = VietnamCorporateActionsResponse(
        status="ok",
        source="CorporateActionsProvider",
        provider="fixture",
        requested_tickers=["FPT"],
        months_back=6,
        events=[
            {
                "ticker": "FPT",
                "event_type": "cash_dividend",
                "status": "upcoming",
                "source": "fixture",
                "provider_event_id": "canonical-event",
            }
        ],
        items=[
            {
                "ticker": "HPG",
                "event_type": "meeting",
                "status": "past",
                "source": "fixture",
                "provider_event_id": "legacy-item",
            }
        ],
    )

    assert response.items == response.events
    assert response.events[0].provider_event_id == "canonical-event"
