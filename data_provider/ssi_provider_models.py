"""Provider-neutral normalized row contracts for SSI REST market data.

These types codify the dictionaries already returned by the production V2
fetcher.  They intentionally do not model provider request objects or raw
PascalCase response fields.  Foreign-flow services consume
``DailySecuritySummaryRow`` directly so the provider layer does not duplicate
rolling-window or aggregation business logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class SecurityRow(TypedDict, total=False):
    symbol: Optional[str]
    exchange: Optional[str]
    security_type: Optional[str]
    name: Optional[str]
    name_en: Optional[str]
    industry: Optional[str]
    sector: Optional[str]
    issuer: Optional[str]
    lot_size: Optional[int]
    listed_shares: Optional[int]
    listed_date: Optional[str]
    market: Optional[str]
    source: str


SecurityMetadataRow = SecurityRow


class OhlcvRow(TypedDict, total=False):
    date: Optional[str]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]
    value: Optional[float]
    source: str


class IntradayOhlcvRow(TypedDict, total=False):
    timestamp: Optional[int]
    date_time: Optional[str]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]
    ticker: str
    source: str


class DailySecuritySummaryRow(TypedDict, total=False):
    date: Optional[str]
    reference_price: Optional[float]
    ceiling_price: Optional[float]
    floor_price: Optional[float]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    adjusted_close: Optional[float]
    matched_volume: Optional[int]
    matched_value: Optional[float]
    put_through_volume: Optional[int]
    put_through_value: Optional[float]
    total_volume: Optional[int]
    total_value: Optional[float]
    foreign_buy_volume: Optional[int]
    foreign_sell_volume: Optional[int]
    foreign_net_volume: Optional[int]
    foreign_buy_value: Optional[float]
    foreign_sell_value: Optional[float]
    foreign_net_value: Optional[float]
    source: str


# Foreign-flow services intentionally reuse the daily summary contract.  This
# alias does not create another normalization or provider-call path.
ForeignFlowRow = DailySecuritySummaryRow


class IndexDefinitionRow(TypedDict, total=False):
    index_id: Optional[str]
    index_code: Optional[str]
    index_name: Optional[str]
    exchange: Optional[str]
    market: Optional[str]
    source: str


class IndexSummaryRow(TypedDict, total=False):
    date: Optional[str]
    index_code: Optional[str]
    index_value: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    total_volume: Optional[int]
    total_value: Optional[float]
    matched_volume: Optional[int]
    matched_value: Optional[float]
    put_through_volume: Optional[int]
    put_through_value: Optional[float]
    advances: Optional[int]
    unchanged: Optional[int]
    declines: Optional[int]
    ceiling: Optional[int]
    floor: Optional[int]
    trading_session: Optional[str]
    exchange: Optional[str]
    source: str


class IndexMembershipRow(TypedDict, total=False):
    index_code: str
    symbol: Optional[str]
    exchange: Optional[str]
    market: Optional[str]
    weight: Optional[float]
    name: Optional[str]
    source: str


class ProviderDiagnostics(TypedDict, total=False):
    capability: Optional[str]
    selected_provider: str
    selected_version: str
    routing_reason: str
    fallback_used: bool


class ProviderResult(TypedDict, total=False):
    """Common envelope fields preserved from the existing V2 fetcher."""

    status: str
    source: str
    reason: Optional[str]
    rows: List[Dict[str, Any]]
    count: int
    cached: bool
    fetched_at: str
    failure_class: Optional[str]
    pages_used: int
    duplicate_date_count: int

