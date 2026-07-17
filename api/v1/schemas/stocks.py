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


class VietnamDailyStockPrice(BaseModel):
    """SSI DailyStockPrice enrichment row for Vietnam dashboard detail fields."""

    status: Optional[str] = None
    quality_status: Optional[str] = None
    reason: Optional[str] = None
    date: Optional[str] = None
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
    status: str = "missing"
    quality_status: Optional[str] = None
    completeness: Optional[float] = None
    missing_fields: List[str] = Field(default_factory=list)
    field_coverage: Dict[str, bool] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


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
    latest_date: Optional[str] = None
    daily_price_date: Optional[str] = None
    date_match: Optional[str] = None
    source: Optional[str] = None
    status: str = "unavailable"
    message: Optional[str] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VietnamCompanySourceCoverageItem(BaseModel):
    """Per-block source coverage row for Vietnam company research."""

    block: str
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
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    source_coverage: List[VietnamCompanySourceCoverageItem] = Field(default_factory=list)
    news: VietnamCompanyPlaceholderBlock
    financials: VietnamCompanyPlaceholderBlock
    events: VietnamCompanyPlaceholderBlock
    data_quality_summary: Dict[str, Any] = Field(default_factory=dict)
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


class VietnamForeignFlowRow(BaseModel):
    """One accepted SSI DailyStockPrice trading session."""

    trading_date: str
    foreign_buy_volume: Optional[int] = None
    foreign_sell_volume: Optional[int] = None
    foreign_net_volume: Optional[int] = None
    foreign_buy_value: Optional[int] = None
    foreign_sell_value: Optional[int] = None
    foreign_net_value: Optional[int] = None


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
    latest_row: Optional[VietnamForeignFlowRow] = None
    requested: VietnamForeignFlowRequested
    coverage: VietnamForeignFlowCoverage
    fetched_at: str
    stale_reason: Optional[str] = None
    failure_class: Optional[str] = None


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
