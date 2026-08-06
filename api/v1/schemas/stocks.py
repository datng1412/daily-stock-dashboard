# -*- coding: utf-8 -*-
"""
===================================
股票数据相关模型
===================================

职责：
1. 定义股票实时行情模型
2. 定义历史 K 线数据模型
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StockQuote(BaseModel):
    """股票实时行情"""
    
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    current_price: float = Field(..., description="当前价格")
    change: Optional[float] = Field(None, description="涨跌额")
    change_percent: Optional[float] = Field(None, description="涨跌幅 (%)")
    open: Optional[float] = Field(None, description="开盘价")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    prev_close: Optional[float] = Field(None, description="昨收价")
    volume: Optional[float] = Field(None, description="成交量（股）")
    amount: Optional[float] = Field(None, description="成交额（元）")
    update_time: Optional[str] = Field(None, description="更新时间")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "current_price": 1800.00,
            "change": 15.00,
            "change_percent": 0.84,
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "prev_close": 1785.00,
            "volume": 10000000,
            "amount": 18000000000,
            "update_time": "2024-01-01T15:00:00"
        }
    })


class KLineData(BaseModel):
    """K 线数据点"""
    
    date: str = Field(..., description="日期")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    close: float = Field(..., description="收盘价")
    volume: Optional[float] = Field(None, description="成交量")
    amount: Optional[float] = Field(None, description="成交额")
    change_percent: Optional[float] = Field(None, description="涨跌幅 (%)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "2024-01-01",
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "close": 1800.00,
            "volume": 10000000,
            "amount": 18000000000,
            "change_percent": 0.84
        }
    })


class ExtractItem(BaseModel):
    """单条提取结果（代码、名称、置信度）"""

    code: Optional[str] = Field(None, description="股票代码，None 表示解析失败")
    name: Optional[str] = Field(None, description="股票名称（如有）")
    confidence: str = Field("medium", description="置信度：high/medium/low")


class ExtractFromImageResponse(BaseModel):
    """图片股票代码提取响应"""

    codes: List[str] = Field(..., description="提取的股票代码（已去重，向后兼容）")
    items: List[ExtractItem] = Field(default_factory=list, description="提取结果明细（代码+名称+置信度）")
    raw_text: Optional[str] = Field(None, description="原始 LLM 响应（调试用）")


class StockHistoryResponse(BaseModel):
    """股票历史行情响应"""
    
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    period: str = Field(..., description="K 线周期")
    data: List[KLineData] = Field(default_factory=list, description="K 线数据列表")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "period": "daily",
            "data": []
        }
    })


class VietnamChartPoint(BaseModel):
    """Daily OHLCV point for Vietnam inspect chart."""

    date: Optional[str] = None
    time: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    volume_ma20: Optional[float] = None
    volume_ma50: Optional[float] = None
    ma20: Optional[float] = None
    ma50: Optional[float] = None
    rsi14: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_mid: Optional[float] = None
    bb_lower: Optional[float] = None


class VietnamDailyStockPriceCapabilities(BaseModel):
    """Independent SSI DailyStockPrice capability readiness."""

    price_limits_status: Literal["ready", "partial", "unavailable"] = "unavailable"
    matched_stats_status: Literal["ready", "partial", "unavailable"] = "unavailable"
    put_through_status: Literal["ready", "partial", "unavailable"] = "unavailable"
    foreign_flow_status: Literal["ready", "partial", "unavailable"] = "unavailable"
    session_metadata_status: Literal["ready", "partial", "unavailable"] = "unavailable"
    overall_status: Literal["ready", "partial", "unavailable"] = "unavailable"


class VietnamDailyStockPrice(BaseModel):
    """SSI DailyStockPrice enrichment row for Vietnam dashboard detail fields."""

    status: Optional[str] = None
    quality_status: Optional[str] = None
    reason: Optional[str] = None
    date: Optional[str] = None
    data_date: Optional[str] = None
    requested_date: Optional[str] = None
    provider_session_date: Optional[str] = None
    freshness_status: Optional[str] = None
    is_current_session: Optional[bool] = None
    is_provisional: Optional[bool] = None
    is_completed_session: Optional[bool] = None
    is_stale: Optional[bool] = None
    session_lag: Optional[int] = Field(default=None, ge=0)
    provider_version: Optional[str] = None
    endpoint: Optional[str] = None
    current_market_session: Optional[str] = None
    date_match: Optional[str] = None
    staleness_reason: Optional[str] = None
    reference_price: Optional[float] = None
    ceiling_price: Optional[float] = None
    floor_price: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    adjusted_close: Optional[float] = None
    matched_volume: Optional[float] = None
    matched_value: Optional[float] = None
    put_through_volume: Optional[float] = None
    put_through_value: Optional[float] = None
    total_volume: Optional[float] = None
    total_value: Optional[float] = None
    foreign_buy_volume: Optional[float] = None
    foreign_sell_volume: Optional[float] = None
    foreign_net_volume: Optional[float] = None
    foreign_buy_value: Optional[float] = None
    foreign_sell_value: Optional[float] = None
    foreign_net_value: Optional[float] = None
    source: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    field_coverage: Dict[str, bool] = Field(default_factory=dict)
    units: Dict[str, str] = Field(default_factory=dict)
    foreign_field_presence: Dict[str, str] = Field(default_factory=dict)
    foreign_field_aliases: Dict[str, str] = Field(default_factory=dict)
    normalization_issues: List[Dict[str, str]] = Field(default_factory=list)
    foreign_flow_value_state: Literal[
        "explicit_zero", "nonzero", "partial", "unavailable"
    ] = "unavailable"
    capabilities: VietnamDailyStockPriceCapabilities = Field(
        default_factory=VietnamDailyStockPriceCapabilities
    )
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamSymbolMetadata(BaseModel):
    """SSI Securities/SecuritiesDetails metadata for Vietnam dashboard symbols."""

    status: Optional[str] = None
    quality_status: Optional[str] = None
    completeness: Optional[float] = None
    reason: Optional[str] = None
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    security_type: Optional[str] = None
    name: Optional[str] = None
    name_en: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    issuer: Optional[str] = None
    lot_size: Optional[int] = None
    listed_shares: Optional[int] = None
    listed_date: Optional[str] = None
    source: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    field_coverage: Dict[str, bool] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamWatchItem(BaseModel):
    """Vietnam watchlist dashboard row."""

    ticker: str
    status: str = "ok"
    reason: Optional[str] = None
    name: Optional[str] = None
    company_name: Optional[str] = None
    entity: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    security_type: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    metadata_source: Optional[str] = None
    symbol_metadata: VietnamSymbolMetadata = Field(default_factory=VietnamSymbolMetadata)
    issuer: Optional[str] = None
    lot_size: Optional[int] = None
    listed_shares: Optional[int] = None
    listed_date: Optional[str] = None
    market_index: Optional[str] = None
    source: Optional[str] = None
    primary_source: Optional[str] = None
    actual_source: Optional[str] = None
    provider_version: Optional[str] = None
    endpoint: Optional[str] = None
    adapter: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    reference_source: Optional[str] = None
    foreign_flow_source: Optional[str] = None
    rows_loaded: Optional[int] = None
    date: Optional[str] = None
    latest_price: Optional[float] = None
    latest_price_source: Optional[str] = None
    latest_price_raw_field: Optional[str] = None
    latest_price_date: Optional[str] = None
    quote_price_date: Optional[str] = None
    quote_price_raw_field: Optional[str] = None
    price_source_warning: Optional[str] = None
    ohlcv_close: Optional[float] = None
    daily_close: Optional[float] = None
    price_date: Optional[str] = None
    ohlcv_date: Optional[str] = None
    daily_stock_price_date: Optional[str] = None
    daily_stock_price_date_match: Optional[str] = None
    daily_stock_price_staleness_reason: Optional[str] = None
    quote_date: Optional[str] = None
    foreign_net_date: Optional[str] = None
    foreign_date_match: Optional[str] = None
    candle_status: Optional[str] = None
    final_close_status: Optional[str] = None
    price_adjustment_status: Optional[str] = None
    adjusted_price_status: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    previous_close: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    liquidity: Dict[str, Any] = Field(default_factory=dict)
    price_limit: Dict[str, Any] = Field(default_factory=dict)
    daily_stock_price: VietnamDailyStockPrice = Field(default_factory=VietnamDailyStockPrice)
    ssi_reference_price: Optional[float] = None
    ssi_ceiling_price: Optional[float] = None
    ssi_floor_price: Optional[float] = None
    ssi_adjusted_close: Optional[float] = None
    ssi_foreign_net_volume: Optional[float] = None
    ssi_foreign_net_value: Optional[float] = None
    ssi_matched_volume: Optional[float] = None
    ssi_matched_value: Optional[float] = None
    ssi_put_through_volume: Optional[float] = None
    ssi_put_through_value: Optional[float] = None
    corporate_action: Dict[str, Any] = Field(default_factory=dict)
    foreign: Dict[str, Any] = Field(default_factory=dict)
    foreign_net_unit: Optional[str] = None
    foreign_buy_raw_field: Optional[str] = None
    foreign_sell_raw_field: Optional[str] = None
    indicators: Dict[str, Any] = Field(default_factory=dict)
    status_labels: List[str] = Field(default_factory=list)
    status_details: List[Dict[str, Any]] = Field(default_factory=list)
    validation: Dict[str, Any] = Field(default_factory=dict)
    trend: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    news: List[Dict[str, Any]] = Field(default_factory=list)
    news_status: Dict[str, Any] = Field(default_factory=dict)
    intraday_timeframe: Optional[str] = None
    intraday_requested_timeframe: Optional[str] = None
    intraday_granularity: Optional[str] = None
    intraday_actual_granularity: Optional[str] = None
    intraday_granularity_seconds: Optional[float] = None
    intraday_actual_granularity_seconds: Optional[float] = None
    intraday_granularity_label: Optional[str] = None
    intraday_cadence_status: Optional[str] = None
    intraday_latest_date: Optional[str] = None
    daily_price_date: Optional[str] = None
    date_match: Optional[str] = None
    intraday_source: Optional[str] = None
    intraday_is_realtime_quote: bool = False
    intraday_warning: Optional[str] = None
    intraday_candles: List[Dict[str, Any]] = Field(default_factory=list)
    intraday_pulse: Optional[Dict[str, Any]] = None
    intraday_labels: List[str] = Field(default_factory=list)
    intraday_details: List[Dict[str, Any]] = Field(default_factory=list)
    intraday_status: Dict[str, Any] = Field(default_factory=dict)
    realtime_source: Optional[str] = None
    realtime_snapshot: Optional[Dict[str, Any]] = None
    realtime_status: Dict[str, Any] = Field(default_factory=dict)
    order_book_source: Optional[str] = None
    order_book: Optional[Dict[str, Any]] = None
    order_book_status: Dict[str, Any] = Field(default_factory=dict)
    foreign_room_source: Optional[str] = None
    foreign_room: Optional[Dict[str, Any]] = None
    foreign_room_status: Dict[str, Any] = Field(default_factory=dict)
    trade_tape_source: Optional[str] = None
    trade_tape: List[Dict[str, Any]] = Field(default_factory=list)
    trade_tape_status: Dict[str, Any] = Field(default_factory=dict)
    session_status_source: Optional[str] = None
    session_status: Optional[Dict[str, Any]] = None
    session_status_status: Dict[str, Any] = Field(default_factory=dict)
    cache_status: Dict[str, Any] = Field(default_factory=dict)
    cache_last_fetched_at: Dict[str, Any] = Field(default_factory=dict)
    cache_next_refresh_at: Dict[str, Any] = Field(default_factory=dict)
    cache_errors: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    data_quality_summary: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class VietnamWatchlistResponse(BaseModel):
    """Vietnam watchlist dashboard response."""

    market: str = "VN"
    source: str = "SSI live"
    fixture_mode: bool = False
    last_refresh_time: Optional[str] = None
    units: Dict[str, str] = Field(default_factory=dict)
    requested_tickers_count: Optional[int] = None
    returned_rows_count: Optional[int] = None
    missing_tickers: List[str] = Field(default_factory=list)
    data_quality: Dict[str, Any] = Field(default_factory=dict)
    cache_metadata: Dict[str, Any] = Field(default_factory=dict)
    watchlist: List[VietnamWatchItem] = Field(default_factory=list)
    rule_metadata: Dict[str, Any] = Field(default_factory=dict)
    formulas: Dict[str, str] = Field(default_factory=dict)


class VietnamCompanyNewsResponse(BaseModel):
    """Optional source-labeled company news for one explicit VN ticker."""

    ticker: Optional[str] = None
    status: str = "disabled"
    source: Optional[str] = None
    provider: Optional[str] = None
    provider_mode: Optional[str] = None
    reason_code: Optional[str] = None
    rights_status: Optional[str] = None
    message: Optional[str] = None
    fetched_at: Optional[str] = None
    cache: Dict[str, Any] = Field(default_factory=dict)
    news: List[Dict[str, Any]] = Field(default_factory=list)


class VietnamChartResponse(BaseModel):
    """Selected Vietnam symbol daily chart response."""

    symbol: str
    status: str = "ok"
    reason: Optional[str] = None
    source: str = "SSI DailyOhlc"
    primary_source: Optional[str] = None
    actual_source: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    provider_version: Optional[str] = None
    endpoint: Optional[str] = None
    adapter: Optional[str] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    timeframe: str = "1d"
    range: str = "6M"
    latest_date: Optional[str] = None
    points: List[VietnamChartPoint] = Field(default_factory=list)
    candles: List[VietnamChartPoint] = Field(default_factory=list)


class VietnamIntradayChartResponse(BaseModel):
    """One completed or current Vietnam date of SSI one-minute chart history."""

    ticker: str
    interval: str = "1m"
    trading_date: str
    timezone: str = "Asia/Ho_Chi_Minh"
    status: str = "ready"
    reason: Optional[str] = None
    session_state: Literal[
        "completed", "pre_open", "continuous_morning", "lunch", "continuous_afternoon", "atc", "closed", "unknown"
    ] = "closed"
    freshness: Literal["updating", "delayed", "stale", "completed", "unavailable"] = "unavailable"
    last_provider_refresh_at: Optional[str] = None
    newest_bar_age_seconds: Optional[int] = None
    provider_snapshot_age_seconds: Optional[int] = None
    current_bar_state: Literal["provisional", "inferred_final", "completed", "none"] = "none"
    bars: List[VietnamChartPoint] = Field(default_factory=list)
    source: Dict[str, Any] = Field(default_factory=dict)
    cache: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamIntradayHealthProcessScope(BaseModel):
    metrics_scope: Literal["process_local"] = "process_local"
    resets_on_restart: bool = True


class VietnamIntradayHealthCache(BaseModel):
    entries: int = Field(0, ge=0)
    current_date_entries: int = Field(0, ge=0)
    completed_date_entries: int = Field(0, ge=0)
    in_flight_fetches: int = Field(0, ge=0)


class VietnamIntradayHealthRequests(BaseModel):
    total: int = Field(0, ge=0)
    current_date: int = Field(0, ge=0)
    completed_date: int = Field(0, ge=0)
    force_refresh: int = Field(0, ge=0)
    coalesced: int = Field(0, ge=0)


class VietnamIntradayHealthLatency(BaseModel):
    count: int = Field(0, ge=0)
    min: Optional[int] = Field(None, ge=0)
    max: Optional[int] = Field(None, ge=0)
    average: Optional[float] = Field(None, ge=0)
    last: Optional[int] = Field(None, ge=0)


class VietnamIntradayHealthProvider(BaseModel):
    calls: int = Field(0, ge=0)
    successes: int = Field(0, ge=0)
    no_data: int = Field(0, ge=0)
    unavailable: int = Field(0, ge=0)
    failures: int = Field(0, ge=0)
    last_successful_fetch_at: Optional[str] = None
    latency_ms: VietnamIntradayHealthLatency = Field(default_factory=VietnamIntradayHealthLatency)


class VietnamIntradayHealthCacheActivity(BaseModel):
    hits: int = Field(0, ge=0)
    misses: int = Field(0, ge=0)
    refreshes: int = Field(0, ge=0)
    empty_hits: int = Field(0, ge=0)
    negative_hits: int = Field(0, ge=0)
    stale_recoveries: int = Field(0, ge=0)
    stale_recovery_rejected_too_old: int = Field(0, ge=0)


class VietnamIntradayHealthDataQuality(BaseModel):
    last_returned_row_count: int = Field(0, ge=0)
    last_usable_bar_count: int = Field(0, ge=0)
    last_rejected_row_count: int = Field(0, ge=0)
    last_duplicate_minute_count: int = Field(0, ge=0)
    last_newest_bar_age_seconds: Optional[int] = Field(None, ge=0)
    last_freshness: Optional[Literal["updating", "delayed", "stale", "completed", "unavailable"]] = None


class VietnamIntradayHealthConcurrency(BaseModel):
    current_same_key_waiters: int = Field(0, ge=0)
    coalesced_waiters: int = Field(0, ge=0)
    maximum_same_key_waiters: int = Field(0, ge=0)


class VietnamIntradayHealthLastProviderResult(BaseModel):
    result: Literal["success", "no_data", "unavailable", "failure"]
    date_kind: Literal["current", "completed"]
    trading_date: str
    session_state: str
    latency_ms: int = Field(ge=0)
    returned_row_count: int = Field(ge=0)
    usable_bar_count: int = Field(ge=0)
    rejected_row_count: int = Field(ge=0)
    duplicate_minute_count: int = Field(ge=0)
    newest_bar_age_seconds: Optional[int] = Field(None, ge=0)
    freshness: Optional[Literal["updating", "delayed", "stale", "completed", "unavailable"]] = None
    stale_recovery: bool = False
    failure_class: Optional[str] = None
    at: str


class VietnamIntradayChartHealthResponse(BaseModel):
    """Sanitized worker-local health for the SSI intraday chart path."""

    status: Literal["ok", "degraded", "unknown"]
    timezone: Literal["Asia/Ho_Chi_Minh"] = "Asia/Ho_Chi_Minh"
    current_vietnam_time: str
    scheduled_session_state: Literal[
        "pre_open", "continuous_morning", "lunch", "continuous_afternoon", "atc", "closed"
    ]
    process_scope: VietnamIntradayHealthProcessScope
    cache: VietnamIntradayHealthCache
    requests: VietnamIntradayHealthRequests
    provider: VietnamIntradayHealthProvider
    cache_activity: VietnamIntradayHealthCacheActivity
    data_quality: VietnamIntradayHealthDataQuality
    concurrency: VietnamIntradayHealthConcurrency
    last_provider_result: Optional[VietnamIntradayHealthLastProviderResult] = None


class VietnamIndexInfo(BaseModel):
    """SSI IndexList row for Vietnam index metadata."""

    index_id: Optional[str] = None
    index_code: Optional[str] = None
    index_name: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    source: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    field_coverage: Dict[str, bool] = Field(default_factory=dict)


class VietnamIndexListResponse(BaseModel):
    """SSI IndexList response for Vietnam dashboard index discovery."""

    status: str = "ok"
    source: str = "SSI IndexList"
    reason: Optional[str] = None
    market: Optional[str] = None
    rows: List[VietnamIndexInfo] = Field(default_factory=list)
    count: int = 0
    fallback_used: bool = False
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamDailyIndexRow(BaseModel):
    """Latest normalized SSI DailyIndex row for one confirmed index identifier."""

    status: str = "ok"
    quality_status: Optional[str] = None
    index_code: str
    date: Optional[str] = None
    date_match: str = "unknown"
    index_value: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    total_volume: Optional[int] = None
    total_value: Optional[float] = None
    matched_volume: Optional[int] = None
    matched_value: Optional[float] = None
    put_through_volume: Optional[int] = None
    put_through_value: Optional[float] = None
    advances: Optional[int] = None
    unchanged: Optional[int] = None
    declines: Optional[int] = None
    ceiling: Optional[int] = None
    floor: Optional[int] = None
    trading_session: Optional[str] = None
    exchange: Optional[str] = None
    source: str = "SSI DailyIndex"
    missing_fields: List[str] = Field(default_factory=list)
    field_coverage: Dict[str, bool] = Field(default_factory=dict)


class VietnamDailyIndexResponse(BaseModel):
    """Optional SSI DailyIndex context for requested IndexList-confirmed indexes."""

    status: str = "unavailable"
    source: str = "SSI DailyIndex"
    reason: Optional[str] = None
    requested_index_codes: List[str] = Field(default_factory=list)
    latest_date: Optional[str] = None
    rows: List[VietnamDailyIndexRow] = Field(default_factory=list)
    count: int = 0
    fallback_used: bool = False
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamMarketIndexPulseRow(BaseModel):
    """Latest normalized SSI MI market-index pulse row."""

    index_code: str
    exchange: Optional[str] = None
    index_value: Optional[float] = None
    estimated_index_value: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    total_trades: Optional[int] = None
    total_volume: Optional[int] = None
    total_value: Optional[float] = None
    advances: Optional[int] = None
    unchanged: Optional[int] = None
    declines: Optional[int] = None
    trading_date: Optional[str] = None
    time: Optional[str] = None
    stream_timestamp: Optional[str] = None
    stream_data_type: str = "MI"
    r_type: Optional[str] = None
    source: str = "SSI MI market-index stream"
    received_at: Optional[str] = None
    cached_at: Optional[str] = None
    cache_ttl_seconds: Optional[int] = None
    age_seconds: Optional[int] = None
    is_stale: bool = False
    stale_reason: Optional[str] = None
    channel_format_status: Optional[str] = "needs_live_proof"
    value_semantics_status: Optional[str] = "needs_live_proof"


class VietnamMarketIndexPulseResponse(BaseModel):
    """Optional SSI MI market-index pulse response from the streaming cache."""

    status: str = "unavailable"
    source: str = "SSI MI market-index stream"
    reason: Optional[str] = None
    market_index_pulse_source: Optional[str] = "SSI MI market-index stream"
    requested_index_codes: List[str] = Field(default_factory=list)
    market_index_pulse: List[VietnamMarketIndexPulseRow] = Field(default_factory=list)
    market_index_pulse_status: Dict[str, Any] = Field(default_factory=dict)
    count: int = 0
    fallback_used: bool = False
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamIndexComponent(BaseModel):
    """SSI IndexComponents row for Vietnam index membership."""

    index_code: Optional[str] = None
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    weight: Optional[float] = None
    name: Optional[str] = None
    source: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    field_coverage: Dict[str, bool] = Field(default_factory=dict)


class VietnamIndexComponentsResponse(BaseModel):
    """SSI IndexComponents response for Vietnam dashboard index membership."""

    status: str = "ok"
    source: str = "SSI IndexComponents"
    reason: Optional[str] = None
    index_code: str
    market: Optional[str] = None
    rows: List[VietnamIndexComponent] = Field(default_factory=list)
    count: int = 0
    fallback_used: bool = False
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamCompanyProfile(BaseModel):
    """Company profile block for the Vietnam company research page."""

    ticker: str
    name: Optional[str] = None
    name_en: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    security_type: Optional[str] = None
    issuer: Optional[str] = None
    lot_size: Optional[int] = None
    listed_shares: Optional[int] = None
    listed_date: Optional[str] = None
    source: Optional[str] = None
    source_endpoint: Optional[str] = None
    provider_version: Optional[str] = None
    fetched_at: Optional[str] = None
    cache_status: Optional[str] = None
    data_state: Literal["ready", "partial", "unavailable"] = "unavailable"
    failure_class: Optional[str] = None
    status: str = "missing"
    quality_status: Optional[str] = None
    completeness: Optional[float] = None
    missing_fields: List[str] = Field(default_factory=list)
    field_coverage: Dict[str, bool] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    core_profile_status: Literal["ready", "unavailable"] = "unavailable"
    optional_metadata_status: Literal["complete", "incomplete"] = "incomplete"
    classification_source: Optional[str] = None


class VietnamCompanyPrice(BaseModel):
    """Daily price and limit summary for the Vietnam company research page."""

    latest_price: Optional[float] = None
    daily_close: Optional[float] = None
    reference_price: Optional[float] = None
    ceiling_price: Optional[float] = None
    floor_price: Optional[float] = None
    price_date: Optional[str] = None
    source: Optional[str] = None
    canonical_source: Optional[str] = None
    reference_source: Optional[str] = None
    reference_price_source: Optional[str] = None
    ceiling_price_source: Optional[str] = None
    floor_price_source: Optional[str] = None
    completed_session_date: Optional[str] = None
    final_close_status: Literal["completed", "provisional", "unknown", "not_applicable"] = "unknown"
    adjustment_status: Literal["adjusted", "unadjusted", "not_provided", "unknown"] = "unknown"
    source_freshness: Literal["current", "latest_completed", "publication_lag", "stale", "unknown"] = "unknown"
    status: str = "missing"


class VietnamCompanyTradingStats(BaseModel):
    """Trading stats block for the Vietnam company research page."""

    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    value: Optional[float] = None
    source: Optional[str] = None
    status: str = "missing"


class VietnamCompanyForeignFlow(BaseModel):
    """Foreign-flow block for the Vietnam company research page."""

    foreign_buy_volume: Optional[float] = None
    foreign_sell_volume: Optional[float] = None
    foreign_net_volume: Optional[float] = None
    foreign_buy_value: Optional[float] = None
    foreign_sell_value: Optional[float] = None
    foreign_net_value: Optional[float] = None
    date: Optional[str] = None
    date_match: Optional[str] = None
    volume_unit: Optional[str] = None
    value_unit: Optional[str] = None
    source: Optional[str] = None
    status: str = "missing"
    capability_status: Literal["ready", "partial", "unavailable"] = "unavailable"
    value_state: Literal[
        "explicit_zero", "nonzero", "partial", "unavailable"
    ] = "unavailable"
    field_presence: Dict[str, str] = Field(default_factory=dict)
    field_aliases: Dict[str, str] = Field(default_factory=dict)
    normalization_issues: List[Dict[str, str]] = Field(default_factory=list)


class VietnamCompanyTechnical(BaseModel):
    """Technical and SSI-derived metrics from SSI DailyOhlc/DailyStockPrice."""

    ma20: Optional[float] = None
    ma50: Optional[float] = None
    rsi14: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    high_52w: Optional[float] = None
    high_52w_date: Optional[str] = None
    low_52w: Optional[float] = None
    low_52w_date: Optional[str] = None
    high_low_52w_history_count: Optional[int] = None
    high_low_52w_coverage_status: Optional[str] = None
    avg_volume_10d: Optional[float] = None
    avg_volume_10d_history_count: Optional[int] = None
    avg_volume_10d_coverage_status: Optional[str] = None
    avg_volume_3m: Optional[float] = None
    avg_volume_3m_history_count: Optional[int] = None
    avg_volume_3m_coverage_status: Optional[str] = None
    price_vs_reference_pct: Optional[float] = None
    price_vs_reference_status: Optional[str] = None
    daily_range_pct: Optional[float] = None
    daily_range_status: Optional[str] = None
    ssi_derived_metrics_status: Optional[str] = None
    ssi_derived_metrics_source: Optional[str] = None
    source: Optional[str] = None
    status: str = "missing"


class VietnamCompanyIntraday(BaseModel):
    """Intraday snapshot derived from SSI IntradayOhlc."""

    candles: List[Dict[str, Any]] = Field(default_factory=list)
    pulse: Optional[Dict[str, Any]] = None
    requested_timeframe: Optional[str] = None
    granularity: Optional[str] = None
    actual_granularity: Optional[str] = None
    granularity_seconds: Optional[float] = None
    actual_granularity_seconds: Optional[float] = None
    granularity_label: Optional[str] = None
    cadence_status: Optional[str] = None
    capability_status: Literal[
        "ready", "partial", "no_data", "unavailable", "error"
    ] = "unavailable"
    latest_date: Optional[str] = None
    daily_price_date: Optional[str] = None
    target_session_date: Optional[str] = None
    session_basis: Optional[str] = None
    date_match: Optional[str] = None
    source: Optional[str] = None
    status: str = "unavailable"
    message: Optional[str] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamCompanySourceCoverageItem(BaseModel):
    """Per-block source coverage row for Vietnam company research."""

    block: str
    group: Optional[str] = None
    source: Optional[str] = None
    status: str


class VietnamCompanyPlaceholderBlock(BaseModel):
    """Placeholder block for future company research providers."""

    items: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "not_implemented"
    source: Optional[str] = None
    message: Optional[str] = None


class VietnamCompanyResearchResponse(BaseModel):
    """Phase 1 Vietnam company research snapshot response."""

    ticker: str
    status: str = "partial"
    session_context: Dict[str, Any] = Field(default_factory=dict)
    live_market: Dict[str, Any] = Field(default_factory=dict)
    profile: VietnamCompanyProfile
    price: VietnamCompanyPrice
    trading_stats: VietnamCompanyTradingStats
    daily_stock_price: VietnamDailyStockPrice = Field(default_factory=VietnamDailyStockPrice)
    foreign_flow: VietnamCompanyForeignFlow
    technical: VietnamCompanyTechnical
    intraday: VietnamCompanyIntraday = Field(default_factory=VietnamCompanyIntraday)
    realtime_snapshot: Optional[Dict[str, Any]] = None
    realtime_status: Dict[str, Any] = Field(default_factory=dict)
    trade_tape: List[Dict[str, Any]] = Field(default_factory=list)
    trade_tape_status: Dict[str, Any] = Field(default_factory=dict)
    order_book_source: Optional[str] = None
    order_book: Optional[Dict[str, Any]] = None
    order_book_status: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    source_coverage: List[VietnamCompanySourceCoverageItem] = Field(default_factory=list)
    news: VietnamCompanyPlaceholderBlock
    financials: VietnamCompanyPlaceholderBlock
    events: VietnamCompanyPlaceholderBlock
    data_quality_summary: Dict[str, Any] = Field(default_factory=dict)
    quality_summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: Dict[str, Any] = Field(default_factory=dict)


class VietnamWatchlistHealthResponse(BaseModel):
    """Vietnam watchlist data-quality health response."""

    source: str = "SSI live"
    fixture_mode: bool = False
    symbols_loaded: int = 0
    last_trading_date: Optional[str] = None
    missing_fields: Dict[str, List[str]] = Field(default_factory=dict)
    errors: Dict[str, List[str]] = Field(default_factory=dict)
    requested_tickers_count: Optional[int] = None
    returned_rows_count: Optional[int] = None
    missing_tickers: List[str] = Field(default_factory=list)
    last_refresh_time: Optional[str] = None
    units: Dict[str, str] = Field(default_factory=dict)
    cache_metadata: Dict[str, Any] = Field(default_factory=dict)


class VietnamCorporateActionEvent(BaseModel):
    """Vietnam corporate-action calendar/history event."""

    ticker: str
    event_id: Optional[str] = None
    event_type: str = "unknown"
    event_subtype: Optional[str] = None
    title: Optional[str] = None
    status: str = "past"
    announcement_date: Optional[str] = None
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payment_date: Optional[str] = None
    effective_date: Optional[str] = None
    cash_dividend_per_share: Optional[float] = None
    cash_dividend_currency: Optional[str] = None
    stock_dividend_ratio: Optional[str] = None
    bonus_share_ratio: Optional[str] = None
    rights_issue_ratio: Optional[str] = None
    rights_issue_price: Optional[float] = None
    split_ratio: Optional[str] = None
    rights_ratio: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    source_document_url: Optional[str] = None
    provider: Optional[str] = None
    provider_event_id: Optional[str] = None
    last_updated: Optional[str] = None
    raw_available: Optional[bool] = None
    confidence: Optional[float] = None
    missing_fields: List[str] = Field(default_factory=list)
    last_checked_at: Optional[str] = None


class VietnamCorporateActionsResponse(BaseModel):
    """Vietnam corporate-action calendar/history response."""

    market: str = "VN"
    status: str = "unavailable"
    source: Optional[str] = None
    provider: Optional[str] = None
    last_checked_at: Optional[str] = None
    requested_tickers: List[str] = Field(default_factory=list)
    months_back: int = 6
    events: List[VietnamCorporateActionEvent] = Field(default_factory=list)
    items: List[VietnamCorporateActionEvent] = Field(default_factory=list)
    error: Optional[str] = None
    error_detail: Optional[str] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def keep_legacy_items_mirrored(self) -> "VietnamCorporateActionsResponse":
        """Keep ``events`` canonical and ``items`` as a compatibility alias."""
        if self.events != self.items:
            self.items = list(self.events)
        return self


class VietnamRealtimeQuote(BaseModel):
    """Vietnam optional realtime/snapshot quote row."""

    symbol: str
    ticker: Optional[str] = None
    fetched_at: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    ceiling_price: Optional[float] = None
    floor_price: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    value: Optional[float] = None
    bid_levels: List[Dict[str, Any]] = Field(default_factory=list)
    ask_levels: List[Dict[str, Any]] = Field(default_factory=list)
    realtime_price: Optional[float] = None
    realtime_time: Optional[str] = None
    realtime_time_display: Optional[str] = None
    snapshot_price: Optional[float] = None
    snapshot_time: Optional[str] = None
    snapshot_time_display: Optional[str] = None
    snapshot_note: Optional[str] = None
    age_seconds: Optional[int] = None
    is_stale: Optional[bool] = None
    stale_reason: Optional[str] = None
    cached_at: Optional[str] = None
    cache_ttl_seconds: Optional[int] = None
    reference_price: Optional[float] = None
    reference_price_source: Optional[str] = None
    price_vs_reference: Optional[float] = None
    price_vs_reference_pct: Optional[float] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    average_price: Optional[float] = None
    price_change: Optional[float] = None
    percent_change: Optional[float] = None
    volume_accumulated: Optional[float] = None
    total_value: Optional[float] = None
    bid_price_1: Optional[float] = None
    bid_vol_1: Optional[float] = None
    ask_price_1: Optional[float] = None
    ask_vol_1: Optional[float] = None
    foreign_buy_volume: Optional[float] = None
    foreign_sell_volume: Optional[float] = None
    foreign_room: Optional[float] = None
    source: str = "SSI realtime contract"
    status: str = "ok"
    error: Optional[str] = None
    error_detail: Optional[str] = None
    raw_error: Optional[str] = None
    event_market_session: Optional[str] = None


class VietnamRealtimeResponse(BaseModel):
    """Vietnam optional realtime/snapshot quote response."""

    market: str = "VN"
    source: str = "SSI realtime contract"
    status: str = "ok"
    error: Optional[str] = None
    error_detail: Optional[str] = None
    raw_error: Optional[str] = None
    reason_code: Optional[str] = None
    classification: Optional[str] = None
    status_message: Optional[str] = None
    requested_tickers: List[str] = Field(default_factory=list)
    quotes: List[VietnamRealtimeQuote] = Field(default_factory=list)
    cache: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    streaming_status: Optional[str] = None
    manager_state: Optional[str] = None
    runtime_status: Optional[str] = None
    cache_status: Optional[str] = None
    parsed_streaming_rows: Optional[int] = None
    stream_state: Optional[Literal["ready", "recovering", "stale", "unavailable", "closed", "failed", "awaiting_subscription", "disabled"]] = None
    last_event_at: Optional[str] = None
    event_age_seconds: Optional[int] = Field(default=None, ge=0)
    generation: Optional[int] = Field(default=None, ge=0)
    transport_health: Optional[str] = None
    parser_health: Optional[str] = None
    symbol_data_health: Optional[str] = None
    response_market_session: Optional[str] = None
    current_market_session: Optional[str] = None
    last_valid_trade_at: Optional[str] = None
    dropped_invalid_row_count: Optional[int] = Field(default=None, ge=0)


class VietnamRealtimeTrade(BaseModel):
    """Vietnam optional realtime trade tape row."""

    ticker: Optional[str] = None
    symbol: Optional[str] = None
    time: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_display: Optional[str] = None
    price: Optional[float] = None
    volume: Optional[float] = None
    value: Optional[float] = None
    side: Optional[str] = None
    side_label: Optional[str] = None
    side_if_available: Optional[str] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    sequence: Optional[str] = None
    sequence_if_available: Optional[str] = None
    match_type: Optional[str] = None
    id: Optional[str] = None
    raw_type: Optional[str] = None
    source: str = "SSI trade-tape contract"
    event_market_session: Optional[str] = None


class VietnamRealtimeTradesResponse(BaseModel):
    """Vietnam optional realtime trade tape response."""

    market: str = "VN"
    source: str = "SSI trade-tape contract"
    symbol: str
    status: str = "ok"
    error: Optional[str] = None
    error_detail: Optional[str] = None
    raw_error: Optional[str] = None
    reason_code: Optional[str] = None
    classification: Optional[str] = None
    status_message: Optional[str] = None
    trades: List[VietnamRealtimeTrade] = Field(default_factory=list)
    note: Optional[str] = None
    cache: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    stream_state: Optional[Literal["ready", "recovering", "stale", "unavailable", "closed", "failed", "awaiting_subscription", "disabled"]] = None
    last_event_at: Optional[str] = None
    event_age_seconds: Optional[int] = Field(default=None, ge=0)
    generation: Optional[int] = Field(default=None, ge=0)
    transport_health: Optional[str] = None
    parser_health: Optional[str] = None
    symbol_data_health: Optional[str] = None
    response_market_session: Optional[str] = None
    current_market_session: Optional[str] = None
    last_valid_trade_at: Optional[str] = None
    dropped_invalid_row_count: Optional[int] = Field(default=None, ge=0)


class VietnamForeignFlowRow(BaseModel):
    """One accepted SSI DailyStockPrice trading session."""

    trading_date: str
    foreign_buy_volume: Optional[int] = None
    foreign_sell_volume: Optional[int] = None
    foreign_net_volume: Optional[int] = None
    foreign_buy_value: Optional[int] = None
    foreign_sell_value: Optional[int] = None
    foreign_net_value: Optional[int] = None
    field_presence: Dict[str, str] = Field(default_factory=dict)
    missing_foreign_fields: List[str] = Field(default_factory=list, max_length=4)
    data_quality: Literal["complete", "incomplete"] = "incomplete"
    complete: bool = False
    usable_for_volume_net: bool = False
    usable_for_value_net: bool = False
    suspicious_zero_session: bool = False
    anomaly_code: Optional[str] = None


class VietnamForeignFlowWindow(BaseModel):
    requested_sessions: int = Field(ge=1, le=120)
    covered_sessions: int = Field(ge=0, le=120)
    complete: bool
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    cumulative_foreign_net_volume: Optional[int] = None
    cumulative_foreign_net_value: Optional[int] = None
    net_volume_contributing_sessions: int = Field(ge=0, le=120)
    net_value_contributing_sessions: int = Field(ge=0, le=120)
    positive_net_volume_sessions: int = Field(ge=0, le=120)
    negative_net_volume_sessions: int = Field(ge=0, le=120)
    zero_net_volume_sessions: int = Field(ge=0, le=120)
    null_net_volume_sessions: int = Field(ge=0, le=120)
    positive_net_value_sessions: int = Field(ge=0, le=120)
    negative_net_value_sessions: int = Field(ge=0, le=120)
    zero_net_value_sessions: int = Field(ge=0, le=120)
    null_net_value_sessions: int = Field(ge=0, le=120)


class VietnamForeignFlowRequested(BaseModel):
    mode: Literal["recent_sessions", "date_range"]
    requested_limit: Optional[int] = Field(default=None, ge=1, le=120)
    requested_from_date: Optional[str] = None
    requested_to_date: Optional[str] = None
    returned_session_count: int = Field(ge=0, le=120)


class VietnamForeignFlowCoverage(BaseModel):
    requested_sessions: Optional[int] = Field(default=None, ge=1, le=120)
    covered_sessions: int = Field(ge=0, le=120)
    complete: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class VietnamForeignFlowAnalyticsEvent(BaseModel):
    value: int
    trading_date: str


class VietnamForeignFlowAnalyticsLatest(BaseModel):
    value: Optional[int] = None
    trading_date: str


class VietnamForeignFlowAnalyticsWindow(BaseModel):
    requested_sessions: Literal[5, 20, 60]
    observed_sessions: int = Field(ge=0, le=60)
    covered_sessions: int = Field(ge=0, le=60)
    complete: bool
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    net_sum: Optional[int] = None
    average_net: Optional[float] = None
    average_absolute_net: Optional[float] = None
    net_buy_session_count: int = Field(ge=0, le=60)
    net_sell_session_count: int = Field(ge=0, le=60)
    zero_session_count: int = Field(ge=0, le=60)
    unavailable_session_count: int = Field(ge=0, le=60)
    max_net_buy: Optional[VietnamForeignFlowAnalyticsEvent] = None
    max_net_sell: Optional[VietnamForeignFlowAnalyticsEvent] = None


class VietnamForeignFlowAnalyticsStreak(BaseModel):
    direction: Literal["net_buy", "net_sell", "none", "unavailable"]
    sessions: int = Field(ge=0, le=60)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    basis: Literal["accepted_provider_rows"] = "accepted_provider_rows"


class VietnamForeignFlowAnalyticsReversal(BaseModel):
    from_direction: Literal["net_buy", "net_sell"]
    to_direction: Literal["net_buy", "net_sell"]
    trading_date: str
    previous_trading_date: str
    current_value: int
    previous_value: int


class VietnamForeignFlowAnalyticsComparison(BaseModel):
    latest_value: Optional[int] = None
    sample_count_20d: int = Field(ge=0, le=20)
    sample_count_60d: int = Field(ge=0, le=60)
    average_net_20d: Optional[float] = None
    average_absolute_net_20d: Optional[float] = None
    average_net_60d: Optional[float] = None
    average_absolute_net_60d: Optional[float] = None
    signed_percentile_20d: Optional[float] = Field(default=None, ge=0, le=100)
    signed_percentile_60d: Optional[float] = Field(default=None, ge=0, le=100)
    absolute_percentile_20d: Optional[float] = Field(default=None, ge=0, le=100)
    absolute_percentile_60d: Optional[float] = Field(default=None, ge=0, le=100)
    z_score_20d: Optional[float] = None
    z_score_60d: Optional[float] = None
    unusual_flow_state: Literal["unavailable", "normal", "elevated"]
    unusual_flow_basis: List[str] = Field(default_factory=list, max_length=2)


class VietnamForeignFlowAnalyticsFamily(BaseModel):
    latest: Optional[VietnamForeignFlowAnalyticsLatest] = None
    windows: Dict[Literal["5", "20", "60"], VietnamForeignFlowAnalyticsWindow]
    current_streak: VietnamForeignFlowAnalyticsStreak
    latest_reversal: Optional[VietnamForeignFlowAnalyticsReversal] = None
    comparison: VietnamForeignFlowAnalyticsComparison


class VietnamForeignFlowAnalyticsRollingRow(BaseModel):
    trading_date: str
    rolling_net_5d_value: Optional[int] = None
    rolling_net_20d_value: Optional[int] = None
    rolling_net_5d_volume: Optional[int] = None
    rolling_net_20d_volume: Optional[int] = None


class VietnamForeignFlowSymbolAnalytics(BaseModel):
    basis: Literal["accepted_provider_rows"] = "accepted_provider_rows"
    max_sessions: Literal[60] = 60
    observed_sessions: int = Field(ge=0, le=60)
    value: VietnamForeignFlowAnalyticsFamily
    volume: VietnamForeignFlowAnalyticsFamily
    rolling_series: List[VietnamForeignFlowAnalyticsRollingRow] = Field(default_factory=list, max_length=60)


class VietnamForeignFlowSymbolHistoryResponse(BaseModel):
    """Bounded one-symbol historical foreign-flow response."""

    ticker: str
    source: Literal["ssi_fastconnect"] = "ssi_fastconnect"
    source_endpoint: Literal["daily_stock_price"] = "daily_stock_price"
    volume_unit: Literal["shares"] = "shares"
    value_unit: Literal["VND"] = "VND"
    finality: Literal["daily_available"] = "daily_available"
    data_state: Literal["ready", "empty", "stale", "unavailable"]
    freshness: Literal["fresh", "stale", "empty", "unavailable"]
    rows: List[VietnamForeignFlowRow] = Field(default_factory=list, max_length=120)
    windows: Dict[Literal["5", "20", "60"], VietnamForeignFlowWindow]
    analytics: Optional[VietnamForeignFlowSymbolAnalytics] = None
    latest_row: Optional[VietnamForeignFlowRow] = None
    requested: VietnamForeignFlowRequested
    coverage: VietnamForeignFlowCoverage
    fetched_at: str
    stale_reason: Optional[str] = None
    failure_class: Optional[str] = None
    provider_version: Literal["v3"] = "v3"
    cache_state: Literal["hit", "miss", "refresh", "stale_hit", "unavailable"] = "unavailable"
    cache_age_seconds: Optional[float] = Field(default=None, ge=0)
    response_regressive: bool = False
    preserved_latest_completed: Optional[str] = None
    provider_latest_returned: Optional[str] = None
    cached_latest_retained: bool = False


class VietnamForeignFlowBatchRequest(BaseModel):
    """Bounded daily foreign-flow request for a selected symbol set."""

    tickers: List[str] = Field(min_length=1, max_length=120)
    top_n: int = Field(default=5, ge=1, le=10)
    force_refresh: bool = False


class VietnamForeignFlowBatchSymbol(BaseModel):
    ticker: str
    data_state: Literal["ready", "empty", "stale", "unavailable"]
    freshness: Literal["fresh", "stale", "empty", "unavailable"]
    failure_class: Optional[str] = None
    stale_reason: Optional[str] = None
    latest_trading_date: Optional[str] = None
    foreign_buy_volume: Optional[int] = None
    foreign_sell_volume: Optional[int] = None
    foreign_net_volume: Optional[int] = None
    foreign_buy_value: Optional[int] = None
    foreign_sell_value: Optional[int] = None
    foreign_net_value: Optional[int] = None
    foreign_net_volume_5d: Optional[int] = None
    foreign_net_value_5d: Optional[int] = None
    foreign_net_volume_20d: Optional[int] = None
    foreign_net_value_20d: Optional[int] = None
    covered_sessions_5d: int = Field(ge=0, le=20)
    complete_5d: bool
    window_end_date_5d: Optional[str] = None
    covered_sessions_20d: int = Field(ge=0, le=20)
    complete_20d: bool
    window_end_date_20d: Optional[str] = None
    source: Literal["ssi_fastconnect"] = "ssi_fastconnect"
    source_endpoint: Literal["daily_stock_price"] = "daily_stock_price"
    volume_unit: Literal["shares"] = "shares"
    value_unit: Literal["VND"] = "VND"
    finality: Literal["daily_available"] = "daily_available"
    fetched_at: str


class VietnamForeignFlowRankingEntry(BaseModel):
    ticker: str
    value: int
    trading_date: Optional[str] = None
    covered_sessions: int = Field(ge=1, le=20)
    complete: bool
    data_state: Literal["ready", "stale"]


class VietnamForeignFlowRankingPair(BaseModel):
    top_buy: List[VietnamForeignFlowRankingEntry] = Field(default_factory=list, max_length=10)
    top_sell: List[VietnamForeignFlowRankingEntry] = Field(default_factory=list, max_length=10)


class VietnamForeignFlowRankings(BaseModel):
    latest_net_value: VietnamForeignFlowRankingPair
    net_value_5d: VietnamForeignFlowRankingPair
    net_value_20d: VietnamForeignFlowRankingPair


class VietnamForeignFlowBatchResponse(BaseModel):
    """Bounded watchlist-scoped daily foreign-flow summaries and rankings."""

    source: Literal["ssi_fastconnect"] = "ssi_fastconnect"
    source_endpoint: Literal["daily_stock_price"] = "daily_stock_price"
    volume_unit: Literal["shares"] = "shares"
    value_unit: Literal["VND"] = "VND"
    finality: Literal["daily_available"] = "daily_available"
    requested_tickers: List[str] = Field(max_length=120)
    normalized_tickers: List[str] = Field(max_length=30)
    requested_count: int = Field(ge=1, le=120)
    normalized_count: int = Field(ge=1, le=30)
    returned_count: int = Field(ge=1, le=30)
    usable_count: int = Field(ge=0, le=30)
    fresh_count: int = Field(ge=0, le=30)
    stale_count: int = Field(ge=0, le=30)
    empty_count: int = Field(ge=0, le=30)
    unavailable_count: int = Field(ge=0, le=30)
    coverage_ratio: float = Field(ge=0, le=1)
    complete: bool
    data_state: Literal["ready", "partial", "stale", "empty", "unavailable"]
    rows: List[VietnamForeignFlowBatchSymbol] = Field(max_length=30)
    rankings: VietnamForeignFlowRankings
    fetched_at: str


VietnamForeignFlowAvailability = Literal["ready", "partial", "unavailable"]
VietnamForeignFlowSourceFreshness = Literal["current", "latest_completed", "stale", "unknown"]
VietnamForeignFlowCacheState = Literal["hit", "miss", "refresh", "stale_hit", "unavailable"]
VietnamForeignFlowFailureClass = Literal[
    "validation",
    "authentication",
    "authorization",
    "timeout",
    "provider_unavailable",
    "package_unavailable",
    "unsupported",
    "unknown",
]


class VietnamForeignFlowWatchlistItem(BaseModel):
    """One truthful, completed-session watchlist screener row."""

    ticker: str
    availability: VietnamForeignFlowAvailability
    data_state: VietnamForeignFlowAvailability
    failure_class: Optional[VietnamForeignFlowFailureClass] = None
    latest_session: Optional[str] = None
    source_freshness: VietnamForeignFlowSourceFreshness
    source_session_lag: Optional[int] = Field(default=None, ge=0)
    fetched_at: str
    cache_state: VietnamForeignFlowCacheState
    cache_age_seconds: Optional[float] = Field(default=None, ge=0)
    actual_session_count: int = Field(ge=0, le=60)
    requested_session_count: Literal[1, 5, 20, 60]
    complete: bool
    buy_value_1d: Optional[int] = None
    sell_value_1d: Optional[int] = None
    net_value_1d: Optional[int] = None
    buy_value_5d: Optional[int] = None
    sell_value_5d: Optional[int] = None
    net_value_5d: Optional[int] = None
    buy_value_20d: Optional[int] = None
    sell_value_20d: Optional[int] = None
    net_value_20d: Optional[int] = None
    buy_value_60d: Optional[int] = None
    sell_value_60d: Optional[int] = None
    net_value_60d: Optional[int] = None
    buy_volume_1d: Optional[int] = None
    sell_volume_1d: Optional[int] = None
    net_volume_1d: Optional[int] = None
    buy_volume_5d: Optional[int] = None
    sell_volume_5d: Optional[int] = None
    net_volume_5d: Optional[int] = None
    buy_volume_20d: Optional[int] = None
    sell_volume_20d: Optional[int] = None
    net_volume_20d: Optional[int] = None
    buy_volume_60d: Optional[int] = None
    sell_volume_60d: Optional[int] = None
    net_volume_60d: Optional[int] = None
    buy_streak: Optional[int] = Field(default=None, ge=0, le=60)
    sell_streak: Optional[int] = Field(default=None, ge=0, le=60)
    streak_metric_basis: Literal["foreign_net_value"]
    contains_provider_anomaly: bool
    anomaly_sessions: List[str] = Field(default_factory=list, max_length=60)
    anomaly_count: int = Field(ge=0, le=60)
    source: Literal["ssi_fastconnect"] = "ssi_fastconnect"
    source_endpoint: Literal["daily_stock_price"] = "daily_stock_price"


class VietnamForeignFlowWatchlistResponse(BaseModel):
    """Bounded 1–30 symbol foreign-flow screener contract."""

    status: VietnamForeignFlowAvailability
    data_state: VietnamForeignFlowAvailability
    usable: bool
    requested_tickers: List[str] = Field(min_length=1, max_length=120)
    normalized_tickers: List[str] = Field(min_length=1, max_length=30)
    duplicate_tickers_removed: int = Field(ge=0, le=119)
    expected_symbol_count: int = Field(ge=1, le=30)
    ready_symbol_count: int = Field(ge=0, le=30)
    partial_symbol_count: int = Field(ge=0, le=30)
    unavailable_symbol_count: int = Field(ge=0, le=30)
    requested_session_count: Literal[1, 5, 20, 60]
    fetched_at: str
    provider: Literal["ssi_fastconnect"] = "ssi_fastconnect"
    provider_version: Literal["v3"] = "v3"
    cache_state: Literal["hit", "miss", "refresh", "stale_hit", "unavailable", "mixed"]
    cache_age_seconds: Optional[float] = Field(default=None, ge=0)
    failure_class: Optional[VietnamForeignFlowFailureClass] = None
    items: List[VietnamForeignFlowWatchlistItem] = Field(min_length=1, max_length=30)


class VietnamVn30ForeignFlowMembership(BaseModel):
    status: Literal["ready", "unavailable"]
    index_code: Literal["VN30"] = "VN30"
    source: Literal["SSI IndexComponents"] = "SSI IndexComponents"
    member_count: int = Field(ge=0, le=30)
    component_count: int = Field(ge=0, le=30)
    member_tickers: List[str] = Field(default_factory=list, max_length=30)
    cache_status: Optional[str] = None
    failure_class: Optional[str] = None
    reason: Optional[str] = None
    fetched_at: str
    resolved_at: str
    retained: bool = False
    age_seconds: Optional[int] = Field(default=None, ge=0)
    refresh_failure_class: Optional[str] = None
    validated_at: Optional[str] = None
    provider_effective_date: Optional[str] = None
    negative_cache_bypassed: bool = False
    recovery_scheduled: bool = False
    recovery_status: Optional[str] = None


class VietnamVn30ForeignFlowCoverage(BaseModel):
    covered_components: int = Field(ge=0, le=30)
    expected_components: int = Field(ge=0, le=30)
    coverage_ratio: float = Field(ge=0, le=1)
    complete: bool


class VietnamVn30ForeignFlowBreadth(BaseModel):
    net_buy_count: int = Field(ge=0, le=30)
    net_sell_count: int = Field(ge=0, le=30)
    zero_count: int = Field(ge=0, le=30)
    unavailable_count: int = Field(ge=0, le=30)


class VietnamVn30ForeignFlowDaily(BaseModel):
    trading_date: str
    foreign_buy_volume: Optional[int] = None
    foreign_sell_volume: Optional[int] = None
    foreign_net_volume: Optional[int] = None
    foreign_buy_value: Optional[int] = None
    foreign_sell_value: Optional[int] = None
    foreign_net_value: Optional[int] = None
    volume_coverage_count: Optional[int] = Field(None, ge=0, le=30)
    volume_coverage_ratio: Optional[float] = Field(None, ge=0, le=1)
    value_coverage_count: Optional[int] = Field(None, ge=0, le=30)
    value_coverage_ratio: Optional[float] = Field(None, ge=0, le=1)
    volume_coverage: Optional[VietnamVn30ForeignFlowCoverage] = None
    value_coverage: Optional[VietnamVn30ForeignFlowCoverage] = None
    volume_breadth: Optional[VietnamVn30ForeignFlowBreadth] = None
    value_breadth: Optional[VietnamVn30ForeignFlowBreadth] = None
    positive_components: Optional[int] = Field(None, ge=0, le=30)
    negative_components: Optional[int] = Field(None, ge=0, le=30)
    zero_components: Optional[int] = Field(None, ge=0, le=30)
    missing_components: Optional[int] = Field(None, ge=0, le=30)
    coverage_mode: Optional[str] = None
    constituent_coverage: Optional[str] = None
    valid_session: Optional[bool] = None
    suspicious_zero_session: bool = False
    anomaly: Optional[str] = None
    anomaly_code: Optional[str] = None
    anomaly_status: Optional[str] = None
    complete: Optional[bool] = None
    data_quality: Optional[Literal["complete", "incomplete", "anomalous"]] = None
    usable_for_windows: Optional[bool] = None
    usable_for_rankings: Optional[bool] = None
    usable_for_analytics: Optional[bool] = None
    recovery_attempted: bool = False
    recovery_succeeded: bool = False
    repair_status: Optional[str] = None
    repair_source: Optional[str] = None
    repair_failure_class: Optional[str] = None
    repair_diagnostics: Dict[str, Any] = Field(default_factory=dict)
    explicit_zero_component_count: int = Field(0, ge=0, le=30)
    missing_field_component_count: int = Field(0, ge=0, le=30)
    missing_field_count: int = 0
    explicit_zero_field_count: int = 0
    source: Optional[str] = None
    provider_version: Optional[str] = None
    endpoint: Optional[str] = None
    freshness: Optional[str] = None
    finality: Optional[str] = None
    data_state: Literal["ready", "partial", "stale", "unavailable"]
    state: Literal["ready", "partial", "stale", "unavailable"]


class VietnamVn30ForeignFlowWindow(BaseModel):
    requested_sessions: Literal[5, 20, 60]
    covered_sessions: int = Field(ge=0, le=60)
    complete: bool
    valid_sessions: Optional[int] = Field(None, ge=0, le=60)
    partial_sessions: Optional[int] = Field(None, ge=0, le=60)
    suspicious_sessions: Optional[int] = Field(None, ge=0, le=60)
    contains_provider_anomaly: bool = False
    anomaly_sessions: List[str] = Field(default_factory=list, max_length=60)
    anomaly_count: int = Field(0, ge=0, le=60)
    missing_sessions: Optional[int] = Field(None, ge=0, le=60)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    foreign_buy_volume: Optional[int] = None
    foreign_sell_volume: Optional[int] = None
    foreign_net_volume: Optional[int] = None
    foreign_buy_value: Optional[int] = None
    foreign_sell_value: Optional[int] = None
    foreign_net_value: Optional[int] = None
    volume_component_sessions: Optional[int] = Field(None, ge=0, le=1800)
    volume_coverage_ratio: Optional[float] = Field(None, ge=0, le=1)
    volume_complete: Optional[bool] = None
    value_component_sessions: Optional[int] = Field(None, ge=0, le=1800)
    value_coverage_ratio: Optional[float] = Field(None, ge=0, le=1)
    value_complete: Optional[bool] = None
    positive_component_sessions: Optional[int] = Field(None, ge=0, le=1800)
    negative_component_sessions: Optional[int] = Field(None, ge=0, le=1800)
    zero_component_sessions: Optional[int] = Field(None, ge=0, le=1800)
    missing_component_sessions: Optional[int] = Field(None, ge=0, le=1800)
    coverage_mode: Optional[str] = None
    constituent_coverage: Optional[str] = None


class VietnamVn30ForeignFlowComponent(BaseModel):
    ticker: str
    data_state: Literal["ready", "stale", "empty", "unavailable"]
    freshness: Literal["fresh", "stale", "empty", "unavailable"]
    source_freshness: Optional[str] = None
    failure_class: Optional[str] = None
    stale_reason: Optional[str] = None
    latest_trading_date: Optional[str] = None
    aggregate_latest_date: Optional[str] = None
    foreign_buy_volume: Optional[int] = None
    foreign_sell_volume: Optional[int] = None
    foreign_net_volume: Optional[int] = None
    foreign_buy_value: Optional[int] = None
    foreign_sell_value: Optional[int] = None
    foreign_net_value: Optional[int] = None
    foreign_buy_volume_5d: Optional[int] = None
    foreign_sell_volume_5d: Optional[int] = None
    foreign_net_volume_5d: Optional[int] = None
    foreign_buy_value_5d: Optional[int] = None
    foreign_sell_value_5d: Optional[int] = None
    foreign_net_value_5d: Optional[int] = None
    foreign_buy_volume_20d: Optional[int] = None
    foreign_sell_volume_20d: Optional[int] = None
    foreign_net_volume_20d: Optional[int] = None
    foreign_buy_value_20d: Optional[int] = None
    foreign_sell_value_20d: Optional[int] = None
    foreign_net_value_20d: Optional[int] = None
    foreign_buy_volume_60d: Optional[int] = None
    foreign_sell_volume_60d: Optional[int] = None
    foreign_net_volume_60d: Optional[int] = None
    foreign_buy_value_60d: Optional[int] = None
    foreign_sell_value_60d: Optional[int] = None
    foreign_net_value_60d: Optional[int] = None
    volume_covered_sessions_5d: int = Field(ge=0, le=5)
    volume_complete_5d: bool
    value_covered_sessions_5d: int = Field(ge=0, le=5)
    value_complete_5d: bool
    window_end_date_5d: Optional[str] = None
    volume_covered_sessions_20d: int = Field(ge=0, le=20)
    volume_complete_20d: bool
    value_covered_sessions_20d: int = Field(ge=0, le=20)
    value_complete_20d: bool
    window_end_date_20d: Optional[str] = None
    volume_covered_sessions_60d: int = Field(0, ge=0, le=60)
    volume_complete_60d: bool = False
    value_covered_sessions_60d: int = Field(0, ge=0, le=60)
    value_complete_60d: bool = False
    window_end_date_60d: Optional[str] = None


class VietnamVn30ForeignFlowRankingEntry(BaseModel):
    ticker: str
    value: int
    trading_date: Optional[str] = None
    data_state: Literal["ready", "stale"]


class VietnamVn30ForeignFlowRankingPair(BaseModel):
    top_buy: List[VietnamVn30ForeignFlowRankingEntry] = Field(default_factory=list, max_length=10)
    top_sell: List[VietnamVn30ForeignFlowRankingEntry] = Field(default_factory=list, max_length=10)


class VietnamVn30ForeignFlowRankings(BaseModel):
    latest_net_value: VietnamVn30ForeignFlowRankingPair
    latest_net_volume: VietnamVn30ForeignFlowRankingPair
    net_value_5d: VietnamVn30ForeignFlowRankingPair
    net_volume_5d: VietnamVn30ForeignFlowRankingPair
    net_value_20d: VietnamVn30ForeignFlowRankingPair
    net_volume_20d: VietnamVn30ForeignFlowRankingPair
    net_value_60d: VietnamVn30ForeignFlowRankingPair = Field(default_factory=VietnamVn30ForeignFlowRankingPair)
    net_volume_60d: VietnamVn30ForeignFlowRankingPair = Field(default_factory=VietnamVn30ForeignFlowRankingPair)


class VietnamVn30ForeignFlowComponentCounts(BaseModel):
    usable: int = Field(ge=0, le=30)
    stale: int = Field(ge=0, le=30)
    empty: int = Field(ge=0, le=30)
    unavailable: int = Field(ge=0, le=30)


class VietnamVn30ForeignFlowCache(BaseModel):
    status: str
    coalesced: bool
    age_seconds: int = Field(ge=0)
    ttl_seconds: int = Field(ge=1)
    negative: bool


class VietnamVn30ForeignFlowTiming(BaseModel):
    membership_ms: int = Field(ge=0)
    component_histories_ms: int = Field(ge=0)
    aggregate_build_ms: int = Field(ge=0)
    total_ms: int = Field(ge=0)
    direct_index_ms: int = Field(0, ge=0)


class VietnamVn30ForeignFlowResponse(BaseModel):
    """Current-membership decomposition with optional direct SSI VN30 totals."""

    scope: Literal["vn30"] = "vn30"
    index_code: Literal["VN30"] = "VN30"
    source: Literal["ssi_fastconnect"] = "ssi_fastconnect"
    source_endpoint: Literal["securitiesSummary?index=", "daily_stock_price"]
    membership_source: Literal["SSI IndexComponents"] = "SSI IndexComponents"
    volume_unit: Literal["shares"] = "shares"
    value_unit: Literal["VND"] = "VND"
    finality: Literal["daily_available"] = "daily_available"
    aggregation_basis: Literal[
        "direct_index_provider_aggregate", "current_vn30_membership"
    ]
    historical_constituent_correct: Literal[False] = False
    status: Literal["ready", "partial", "stale", "unavailable"]
    usable: bool
    capability_status: str
    primary_data_mode: Literal[
        "direct_index_canonical", "current_membership_decomposition"
    ]
    source_coverage: List[Dict[str, Any]] = Field(default_factory=list)
    canonical_source: str
    canonical_provider_version: Literal["v3"] = "v3"
    canonical_endpoint: str
    canonical_aggregation_mode: Literal["DIRECT_INDEX_CANONICAL"]
    canonical_trading_date: Optional[str] = None
    decomposition_aggregation_mode: Literal["CURRENT_MEMBERSHIP_DECOMPOSITION"]
    decomposition_universe: Literal["current_vn30_membership"]
    decomposition_date: Optional[str] = None
    data_state: Literal["ready", "partial", "stale", "unavailable"]
    membership: VietnamVn30ForeignFlowMembership
    aggregate_session_dates: List[str] = Field(default_factory=list, max_length=60)
    latest: Optional[VietnamVn30ForeignFlowDaily] = None
    windows: Dict[Literal["5", "20", "60"], VietnamVn30ForeignFlowWindow]
    series: List[VietnamVn30ForeignFlowDaily] = Field(default_factory=list, max_length=60)
    components: List[VietnamVn30ForeignFlowComponent] = Field(default_factory=list, max_length=30)
    component_counts: VietnamVn30ForeignFlowComponentCounts
    rankings: VietnamVn30ForeignFlowRankings
    canonical: Dict[str, Any]
    decomposition: Dict[str, Any]
    cache_key_dimensions: Dict[str, Any] = Field(default_factory=dict)
    cache: VietnamVn30ForeignFlowCache
    timing: VietnamVn30ForeignFlowTiming
    fetched_at: str


class VietnamForeignFlowObservability(BaseModel):
    """Sanitized process-local historical foreign-flow counters."""

    scope: Literal["process_local"] = "process_local"
    endpoint_requests: int = Field(0, ge=0)
    recent_session_requests: int = Field(0, ge=0)
    date_range_requests: int = Field(0, ge=0)
    force_refresh_requests: int = Field(0, ge=0)
    cache_hits: int = Field(0, ge=0)
    cache_misses: int = Field(0, ge=0)
    empty_cache_hits: int = Field(0, ge=0)
    negative_cache_hits: int = Field(0, ge=0)
    stale_recoveries: int = Field(0, ge=0)
    provider_calls: int = Field(0, ge=0)
    provider_successes: int = Field(0, ge=0)
    provider_empty_results: int = Field(0, ge=0)
    provider_failures: int = Field(0, ge=0)
    provider_latency_count: int = Field(0, ge=0)
    provider_latency_total_ms: int = Field(0, ge=0)
    provider_latency_max_ms: int = Field(0, ge=0)
    normalized_rows: int = Field(0, ge=0)
    rejected_rows: int = Field(0, ge=0)
    duplicate_date_count: int = Field(0, ge=0)
    net_volume_fallback_count: int = Field(0, ge=0)
    net_value_fallback_count: int = Field(0, ge=0)
    net_volume_mismatch_count: int = Field(0, ge=0)
    net_value_mismatch_count: int = Field(0, ge=0)
    active_in_flight: int = Field(0, ge=0)
    coalesced_waiters: int = Field(0, ge=0)
    max_coalesced_waiters: int = Field(0, ge=0)
    unavailable_results: int = Field(0, ge=0)
    last_success_at: Optional[str] = None
    last_failure_class: Optional[str] = None
    batch_requests: int = Field(0, ge=0)
    batch_force_refresh_requests: int = Field(0, ge=0)
    batch_requested_symbols: int = Field(0, ge=0)
    batch_normalized_symbols: int = Field(0, ge=0)
    batch_usable_symbols: int = Field(0, ge=0)
    batch_stale_symbols: int = Field(0, ge=0)
    batch_empty_symbols: int = Field(0, ge=0)
    batch_unavailable_symbols: int = Field(0, ge=0)
    batch_ready_results: int = Field(0, ge=0)
    batch_partial_results: int = Field(0, ge=0)
    batch_stale_results: int = Field(0, ge=0)
    batch_empty_results: int = Field(0, ge=0)
    batch_unavailable_results: int = Field(0, ge=0)
    batch_latency_count: int = Field(0, ge=0)
    batch_latency_total_ms: int = Field(0, ge=0)
    batch_latency_max_ms: int = Field(0, ge=0)
    batch_active_requests: int = Field(0, ge=0)
    batch_max_active_requests: int = Field(0, ge=0)
    ranking_build_count: int = Field(0, ge=0)
    ranking_eligible_values: int = Field(0, ge=0)
    ranking_excluded_null_values: int = Field(0, ge=0)
    ranking_excluded_zero_values: int = Field(0, ge=0)
    vn30_requests: int = Field(0, ge=0)
    vn30_force_refresh_requests: int = Field(0, ge=0)
    vn30_membership_unavailable_results: int = Field(0, ge=0)
    vn30_cache_hits: int = Field(0, ge=0)
    vn30_cache_misses: int = Field(0, ge=0)
    vn30_negative_cache_hits: int = Field(0, ge=0)
    vn30_coalesced_waiters: int = Field(0, ge=0)
    vn30_active_in_flight: int = Field(0, ge=0)
    vn30_component_histories: int = Field(0, ge=0)
    vn30_usable_components: int = Field(0, ge=0)
    vn30_stale_components: int = Field(0, ge=0)
    vn30_empty_components: int = Field(0, ge=0)
    vn30_unavailable_components: int = Field(0, ge=0)
    vn30_ready_results: int = Field(0, ge=0)
    vn30_partial_results: int = Field(0, ge=0)
    vn30_stale_results: int = Field(0, ge=0)
    vn30_unavailable_results: int = Field(0, ge=0)
    vn30_latency_count: int = Field(0, ge=0)
    vn30_latency_total_ms: int = Field(0, ge=0)
    vn30_latency_max_ms: int = Field(0, ge=0)
    anomaly_repair_requests: int = Field(0, ge=0)
    anomaly_repair_provider_calls: int = Field(0, ge=0)
    anomaly_repair_cache_hits: int = Field(0, ge=0)
    anomaly_repair_manual_bypasses: int = Field(0, ge=0)
    anomaly_repair_coalesced_waiters: int = Field(0, ge=0)
    anomaly_repair_successes: int = Field(0, ge=0)
    anomaly_repair_failures: int = Field(0, ge=0)


class VietnamMozyfinObservability(BaseModel):
    """Legacy Mozyfin counter block retained for API compatibility."""

    status: str = "disabled"
    source: str = "legacy"
    reason: Optional[str] = None


class VietnamDashboardRuntimeObservability(BaseModel):
    """Provider-neutral process-local VN dashboard runtime counters."""

    watchlist_requests_total: int = 0
    watchlist_cache_hits_total: int = 0
    watchlist_cache_misses_total: int = 0
    singleflight_waits_total: int = 0
    last_watchlist_request_at: Optional[str] = None
    last_fetch_at: Optional[str] = None
    last_cache_key: Optional[str] = None
    last_tickers_count: int = 0
    last_fetch_duration_ms: Optional[int] = None


class VietnamKbsObservability(BaseModel):
    """Process-local KBS fetch counters for the Vietnam dashboard."""

    status: str = "disabled"
    source: str = "legacy_optional"
    reason: Optional[str] = None
    legacy_allowed: bool = False
    enabled: bool = False
    quote_requests_total: int = 0
    quote_success_total: int = 0
    quote_unavailable_total: int = 0
    trade_requests_total: int = 0
    trade_success_total: int = 0
    trade_unavailable_total: int = 0
    last_quote_request_at: Optional[str] = None
    last_trade_request_at: Optional[str] = None
    last_quote_tickers_count: int = 0
    last_trade_symbol: Optional[str] = None
    last_error: Optional[str] = None
    last_raw_error_present: bool = False


class VietnamProviderRuntimeStatus(BaseModel):
    """Runtime status for a VN provider-owned data block."""

    status: str = "not_implemented"
    source: Optional[str] = "SSI"
    reason: Optional[str] = None
    enabled: Optional[bool] = None


class VietnamStreamingTransportObservability(BaseModel):
    """Sanitized process-local SSI channel-cohort lifecycle state."""

    name: str
    state: Literal["stopped", "connecting", "connected", "reconnecting", "closing", "closed", "failed"]
    connected: bool = False
    generation: int = Field(default=0, ge=0)
    start_count: int = Field(default=0, ge=0)
    connect_count: int = Field(default=0, ge=0)
    disconnect_count: int = Field(default=0, ge=0)
    reconnect_scheduled_count: int = Field(default=0, ge=0)
    reconnect_task_count: int = Field(default=0, ge=0)
    reconnect_attempt_count: int = Field(default=0, ge=0)
    reconnect_success_count: int = Field(default=0, ge=0)
    reconnect_failure_count: int = Field(default=0, ge=0)
    stale_generation_callbacks_ignored: int = Field(default=0, ge=0)
    subscription_restore_attempt_count: int = Field(default=0, ge=0)
    subscription_restore_success_count: int = Field(default=0, ge=0)
    subscription_restore_failure_count: int = Field(default=0, ge=0)
    readiness_transition_count: int = Field(default=0, ge=0)
    shutdown_count: int = Field(default=0, ge=0)
    physical_transport_count: int = Field(default=0, ge=0)
    subscription_count: int = Field(default=0, ge=0)
    last_connected_at: Optional[str] = None
    last_disconnected_at: Optional[str] = None
    last_transition_at: Optional[str] = None
    last_error_class: Optional[str] = None
    reconnect_attempt_number: int = Field(default=0, ge=0)
    next_retry_at: Optional[str] = None
    in_flight_reconnect: bool = False
    shutdown_requested: bool = False


class VietnamStreamingContextObservability(BaseModel):
    """Freshness/readiness state for one existing SSI stream context."""

    state: Literal["disabled", "awaiting_subscription", "recovering", "ready", "stale", "unavailable", "closed", "failed"]
    enabled: bool = False
    subscribed_generation: Optional[int] = Field(default=None, ge=0)
    last_event_generation: Optional[int] = Field(default=None, ge=0)
    last_event_at: Optional[str] = None
    last_fresh_event_at: Optional[str] = None
    event_age_seconds: Optional[int] = Field(default=None, ge=0)
    accepted_event_count: int = Field(default=0, ge=0)
    ignored_old_generation_event_count: int = Field(default=0, ge=0)
    subscription_restoration_count: int = Field(default=0, ge=0)
    subscription_failure_count: int = Field(default=0, ge=0)
    stale_reason: Optional[str] = None
    last_error_class: Optional[str] = None


class VietnamStreamingObservability(BaseModel):
    """Read-only worker-local SSI stream lifecycle snapshot."""

    scope: Literal["process_local"] = "process_local"
    overall_state: Literal["unknown", "connecting", "ready", "recovering", "degraded", "closed", "failed"] = "unknown"
    transports: List[VietnamStreamingTransportObservability] = Field(default_factory=list)
    contexts: Dict[str, VietnamStreamingContextObservability] = Field(default_factory=dict)
    session: Dict[str, Any] = Field(default_factory=dict)
    multi_worker_note: str = "Each worker owns an independent SSI connection cohort and process-local metrics."


class VietnamObservabilityResponse(BaseModel):
    """Vietnam dashboard in-memory observability response."""

    market: str = "VN"
    status: str = "ok"
    mozyfin: VietnamMozyfinObservability = Field(default_factory=VietnamMozyfinObservability)
    dashboard_runtime: VietnamDashboardRuntimeObservability = Field(default_factory=VietnamDashboardRuntimeObservability)
    kbs: VietnamKbsObservability = Field(default_factory=VietnamKbsObservability)
    ssi_core: VietnamProviderRuntimeStatus = Field(default_factory=VietnamProviderRuntimeStatus)
    ssi_intraday: VietnamProviderRuntimeStatus = Field(default_factory=VietnamProviderRuntimeStatus)
    ssi_realtime: VietnamProviderRuntimeStatus = Field(default_factory=VietnamProviderRuntimeStatus)
    ssi_trade_tape: VietnamProviderRuntimeStatus = Field(default_factory=VietnamProviderRuntimeStatus)
    foreign_flow: VietnamForeignFlowObservability = Field(default_factory=VietnamForeignFlowObservability)
    streaming: VietnamStreamingObservability = Field(default_factory=VietnamStreamingObservability)


class VietnamForeignIndexFlowResponse(BaseModel):
    """Provider-neutral historical foreign-flow aggregate for one SSI index."""

    status: Literal["ok", "partial", "unavailable"]
    capability_status: Optional[
        Literal["available", "unsupported", "unavailable", "inconclusive"]
    ] = None
    failure_class: Optional[str] = None
    scope: Literal["index"] = "index"
    identifier: str
    requested_from_date: Optional[str] = None
    requested_to_date: Optional[str] = None
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    source: str
    provider_version: str
    endpoint: str
    usable_session_count: Optional[int] = Field(None, ge=0)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamCurrentForeignFlowResponse(BaseModel):
    """Best available current-session foreign flow without REST/stream blending."""

    status: Literal["ok", "partial", "unavailable"]
    data_state: Literal[
        "waiting", "ready", "partial", "stale", "market_closed", "unavailable", "error"
    ] = "unavailable"
    usable: bool = False
    failure_class: Optional[str] = None
    symbol: str
    trading_date: Optional[str] = None
    freshness_status: str
    is_current_session: bool = False
    is_provisional: bool = False
    current: Optional[Dict[str, Any]] = None
    latest_completed_comparison: Optional[Dict[str, Any]] = None
    stream_status: str
    stream_reason: str
    source: str
    provider_version: str
    endpoint: str
    finality: Optional[Literal["current_session_provisional"]] = None
    update_semantics: Optional[Literal["cumulative_replacement_snapshot"]] = None
    cache: Dict[str, Any] = Field(default_factory=dict)
    market_session: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamCurrentForeignFlowAggregateResponse(BaseModel):
    """Display-only current foreign-flow aggregate from the shared R cache."""

    status: Literal["ok", "partial", "unavailable"]
    data_state: Literal[
        "waiting", "ready", "partial", "stale", "market_closed", "unavailable", "error"
    ] = "unavailable"
    usable: bool = False
    failure_class: Optional[str] = None
    scope: Literal["current_foreign_flow_aggregate"]
    universe: str
    provider_session_date: Optional[str] = None
    is_provisional: bool = False
    finality: Optional[Literal["current_session_provisional"]] = None
    source: str
    provider_version: Literal["v3"] = "v3"
    endpoint: Literal["room.{symbol}"] = "room.{symbol}"
    update_semantics: Literal["cumulative_replacement_snapshot"]
    aggregate: Optional[Dict[str, Any]] = None
    display_series: List[Dict[str, Any]] = Field(default_factory=list, max_length=60)
    display_windows: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    rankings: Dict[str, Dict[str, List[Dict[str, Any]]]] = Field(
        default_factory=dict
    )
    items: List[Dict[str, Any]] = Field(default_factory=list, max_length=30)
    groups: List[Dict[str, Any]] = Field(default_factory=list, max_length=30)
    coverage: Dict[str, Any] = Field(default_factory=dict)
    market_session: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamProprietaryFlowResponse(BaseModel):
    """Truthful SSI V3 proprietary capability result."""

    status: Literal["ok", "partial", "unavailable"]
    data_state: Literal["ready", "partial", "unavailable"] = "unavailable"
    usable: bool = False
    failure_class: Optional[str] = None
    capability_status: Literal["unsupported"] = "unsupported"
    scope: Literal["board", "index"]
    identifier: str
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    source: str
    provider_version: str
    endpoint: str
    unsupported_scopes: List[str] = Field(default_factory=list)
    requested_from_date: Optional[str] = None
    requested_to_date: Optional[str] = None
    fetched_at: Optional[str] = None
    cache: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamIndustryFlowRequest(BaseModel):
    """Bounded explicit-universe ICB industry history request."""

    symbols: Optional[List[str]] = None
    index_code: Optional[str] = None
    from_date: str
    to_date: str


class VietnamIndustryFlowResponse(BaseModel):
    """Provider-backed ICB industry foreign flow and matched turnover."""

    status: Literal["ok", "partial", "unavailable"]
    data_state: Literal["ready", "partial", "unavailable"] = "unavailable"
    usable: bool = False
    failure_class: Optional[str] = None
    universe: str
    requested_symbol_count: int = Field(ge=0)
    classified_symbol_count: int = Field(ge=0)
    unclassified_symbol_count: int = Field(ge=0)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    current_session_status: str
    proprietary_industry_status: Literal["unsupported"] = "unsupported"
    source: str
    provider_version: str
    requested_from_date: Optional[str] = None
    requested_to_date: Optional[str] = None
    fetched_at: Optional[str] = None
    cache: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
