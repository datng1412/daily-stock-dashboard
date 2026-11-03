# AlphaSift integration

AlphaSift supplies inherited A-share screening strategies, calculation, and optional LLM reranking through `alphasift.dsa_adapter`. StockClock owns enablement, calls, and presentation. Enable `ALPHASIFT_ENABLED` explicitly after making the adapter available in the backend Python environment. Docker and desktop packages build in the pinned adapter. The [config registry](../src/core/config_registry.py) and [.env.example](../.env.example) own the default source and settings.

The adapter exposes these functions and can return the following shapes.

```python
def get_status() -> dict: ...
def list_strategies() -> list[dict]: ...
def screen(strategy: str, *, market: str = "cn", max_results: int = 20, use_llm: bool = True) -> dict: ...
```

```json
{
  "available": true,
  "contract_version": "1",
  "version": "0.2.0",
  "strategy_count": 8,
  "supported_markets": ["cn"]
}
```

```json
{
  "run_id": "20260531-...",
  "strategy": "dual_low",
  "market": "cn",
  "snapshot_count": 100,
  "after_filter_count": 5,
  "llm_ranked": true,
  "llm_coverage": 1.0,
  "warnings": [],
  "source_errors": [],
  "candidates": []
}
```

Strategy items need an `id` and may include names, descriptions, categories, tags, and market scope. Candidates can include price, score, rationale, factor scores, risk flags, and LLM score, confidence, thesis, catalysts, risks, and watch items.

## Application boundary

- [Status, strategies, and screening](../api/v1/endpoints/alphasift.py) use the existing adapter. Status reports unavailable for a missing optional package and exposes sanitized diagnostics for unexpected adapter failures. It omits the full installation spec.
- The controlled install endpoint requires an administrator session and the trusted default source. Enabling the feature in Settings checks the adapter and does not invoke installation.
- The Web page exposes market `cn`, uses a longer screening timeout, and shows run metadata, LLM coverage, and candidate details. Screening requests use `use_llm=True` through the adapter. The backend supports the legacy `max_output` argument where needed.
- AlphaSift reuses the backend LLM settings, including `LLM_CHANNELS`, `LITELLM_CONFIG`, and `LLM_TIMEOUT_SEC`. See the [LLM guide](LLM_CONFIG_GUIDE_EN.md) for routing and saved configuration behavior.

A disabled feature returns 403. A missing or failed adapter returns 424 on screening. Invalid market or strategy input returns 400 or 422. Turn off `ALPHASIFT_ENABLED` to disable screening. The [API tests](../tests/test_alphasift_api.py) cover compatibility and control boundaries.
