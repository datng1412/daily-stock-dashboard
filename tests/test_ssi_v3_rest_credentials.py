"""Offline proof for the SSI V3 Market Data REST credential contract."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import os
import pytest

from ssi_sdk import Config as SdkConfig
from ssi_sdk.services.token_manager import _build_auth_request

from data_provider.ssi_v3_adapter import (
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
    _default_auth_factory,
    validate_v3_selection,
)
from src.config import Config


def test_installed_sdk_market_data_token_body_needs_only_key_and_secret() -> None:
    body = _build_auth_request(
        SdkConfig(
            client_id="",
            api_key="<api-key>",
            api_secret="<api-secret>",
            private_key="",
        )
    )

    assert set(body) == {"apiKey", "apiSecret"}
    assert "clientId" not in body
    assert "privateKey" not in body
    assert "otp" not in body


@pytest.mark.parametrize("client_id", [None, ""])
def test_v3_selection_accepts_empty_client_id_but_not_missing_key_or_secret(
    client_id: str | None,
) -> None:
    settings = SsiV3RestSettings(
        enabled=True,
        client_id=client_id,
        api_key="<api-key>",
        api_secret="<api-secret>",
    )

    assert settings.missing_required_names == ()
    validate_v3_selection(settings)

    incomplete = SsiV3RestSettings(enabled=True, client_id=None)
    assert incomplete.missing_required_names == (
        "SSI_V3_API_KEY",
        "SSI_V3_API_SECRET",
    )


@patch("src.config.setup_env")
@patch.object(Config, "_parse_litellm_yaml", return_value=[])
def test_removed_v2_credentials_are_ignored(
    _mock_parse_yaml: object,
    _mock_setup_env: object,
) -> None:
    with patch.dict(
        os.environ,
        {
            "SSI_FASTCONNECT_CONSUMER_ID": "<v2-id>",
            "SSI_FASTCONNECT_CONSUMER_SECRET": "<v2-secret>",
        },
        clear=True,
    ):
        loaded = Config._load_from_env()

    assert not hasattr(loaded, "ssi_fastconnect_consumer_id")
    assert not hasattr(loaded, "ssi_fastconnect_consumer_secret")
    assert loaded.ssi_v3_client_id is None
    assert loaded.ssi_v3_api_key is None
    assert loaded.ssi_v3_api_secret is None


def test_auth_factory_passes_empty_optional_sdk_fields_without_otp() -> None:
    settings = SsiV3RestSettings(
        enabled=True,
        client_id=None,
        api_key="<api-key>",
        api_secret="<api-secret>",
    )
    fake_auth = SimpleNamespace()

    with patch("ssi_sdk.Auth", return_value=fake_auth) as auth_class:
        assert _default_auth_factory(settings) is fake_auth

    sdk_config = auth_class.call_args.args[0]
    assert sdk_config.client_id == ""
    assert sdk_config.private_key == ""
    assert sdk_config.api_key == "<api-key>"
    assert sdk_config.api_secret == "<api-secret>"


def test_structured_config_validation_treats_client_id_as_optional() -> None:
    config = Config(
        ssi_v3_rest_enabled=True,
        ssi_v3_client_id=None,
        ssi_v3_api_key="<api-key>",
        ssi_v3_api_secret="<api-secret>",
    )

    matching = [
        issue
        for issue in config.validate_structured()
        if issue.field and issue.field.startswith("SSI_V3_")
    ]
    assert matching == []


def test_public_initialization_method_reuses_one_auth_data_lifecycle() -> None:
    class FakeAuth:
        def __init__(self) -> None:
            self.authenticate_calls = 0
            self.close_calls = 0

        def authenticate(self) -> None:
            self.authenticate_calls += 1

        def close(self) -> None:
            self.close_calls += 1

    auth = FakeAuth()
    data = SimpleNamespace()
    adapter = SsiFastConnectV3Adapter(
        SsiV3RestSettings(
            enabled=True,
            client_id=None,
            api_key="<api-key>",
            api_secret="<api-secret>",
        ),
        auth_factory=lambda _settings: auth,
        data_factory=lambda _auth: data,
    )

    first = adapter.initialize_rest_access()
    second = adapter.initialize_rest_access()

    assert first["status"] == second["status"] == "ok"
    assert first["diagnostics"]["client_id_supplied"] is False
    assert auth.authenticate_calls == 1
    adapter.close()
    assert auth.close_calls == 1
