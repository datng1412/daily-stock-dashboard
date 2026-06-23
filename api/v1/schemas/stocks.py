# -*- coding: utf-8 -*-
"""
===================================
股票数据相关模型
===================================

职责：
1. 定义股票实时行情模型
2. 定义历史 K 线数据模型
"""

from typing import Any, Dict, Optional, List

from pydantic import BaseModel, ConfigDict, Field


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
    reason: Optional[str] = None
    date: Optional[str] = None
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


class VietnamSymbolMetadata(BaseModel):
    """SSI Securities/SecuritiesDetails metadata for Vietnam dashboard symbols."""

    status: Optional[str] = None
    reason: Optional[str] = None
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    security_type: Optional[str] = None
    name: Optional[str] = None
    name_en: Optional[str] = None
    issuer: Optional[str] = None
    lot_size: Optional[int] = None
    listed_shares: Optional[int] = None
    listed_date: Optional[str] = None
    source: Optional[str] = None


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
    trade_tape_source: Optional[str] = None
    trade_tape: Dict[str, Any] = Field(default_factory=dict)
    trade_tape_status: Dict[str, Any] = Field(default_factory=dict)
    cache_status: Dict[str, Any] = Field(default_factory=dict)
    cache_last_fetched_at: Dict[str, Any] = Field(default_factory=dict)
    cache_next_refresh_at: Dict[str, Any] = Field(default_factory=dict)
    cache_errors: Dict[str, Any] = Field(default_factory=dict)
    data_quality_summary: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class VietnamWatchlistResponse(BaseModel):
    """Vietnam watchlist dashboard response."""

    market: str = "VN"
    source: str = "SSI live"
    fixture_mode: bool = False
    last_refresh_time: Optional[str] = None
    units: Dict[str, str] = Field(default_factory=dict)
    data_quality: Dict[str, Any] = Field(default_factory=dict)
    cache_metadata: Dict[str, Any] = Field(default_factory=dict)
    watchlist: List[VietnamWatchItem] = Field(default_factory=list)
    rule_metadata: Dict[str, Any] = Field(default_factory=dict)
    formulas: Dict[str, str] = Field(default_factory=dict)


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


class VietnamIndexInfo(BaseModel):
    """SSI IndexList row for Vietnam index metadata."""

    index_id: Optional[str] = None
    index_code: Optional[str] = None
    index_name: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    source: Optional[str] = None


class VietnamIndexListResponse(BaseModel):
    """SSI IndexList response for Vietnam dashboard index discovery."""

    status: str = "ok"
    source: str = "SSI IndexList"
    reason: Optional[str] = None
    market: Optional[str] = None
    rows: List[VietnamIndexInfo] = Field(default_factory=list)
    count: int = 0
    fallback_used: bool = False


class VietnamIndexComponent(BaseModel):
    """SSI IndexComponents row for Vietnam index membership."""

    index_code: Optional[str] = None
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    weight: Optional[float] = None
    name: Optional[str] = None
    source: Optional[str] = None


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


class VietnamCompanyProfile(BaseModel):
    """Company profile block for the Vietnam company research page."""

    ticker: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    status: str = "missing"


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
    source: Optional[str] = None
    status: str = "missing"


class VietnamCompanyTechnical(BaseModel):
    """Technical snapshot derived from SSI daily OHLCV."""

    ma20: Optional[float] = None
    ma50: Optional[float] = None
    rsi14: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    source: Optional[str] = None
    status: str = "missing"


class VietnamCompanyIntraday(BaseModel):
    """Intraday snapshot derived from SSI IntradayOhlc."""

    candles: List[Dict[str, Any]] = Field(default_factory=list)
    pulse: Dict[str, Any] = Field(default_factory=dict)
    requested_timeframe: Optional[str] = None
    granularity: Optional[str] = None
    actual_granularity: Optional[str] = None
    granularity_seconds: Optional[float] = None
    actual_granularity_seconds: Optional[float] = None
    granularity_label: Optional[str] = None
    latest_date: Optional[str] = None
    daily_price_date: Optional[str] = None
    date_match: Optional[str] = None
    source: Optional[str] = None
    status: str = "unavailable"
    message: Optional[str] = None


class VietnamCompanyRealtime(BaseModel):
    """Realtime snapshot block for the Vietnam company research page."""

    snapshot: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    status: str = "unavailable"
    message: Optional[str] = None


class VietnamCompanyTradeTape(BaseModel):
    """Trade tape block for the Vietnam company research page."""

    trades: List[Dict[str, Any]] = Field(default_factory=list)
    source: Optional[str] = None
    status: str = "unavailable"
    message: Optional[str] = None


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
    foreign_flow: VietnamCompanyForeignFlow
    technical: VietnamCompanyTechnical
    intraday: VietnamCompanyIntraday = Field(default_factory=VietnamCompanyIntraday)
    realtime: VietnamCompanyRealtime = Field(default_factory=VietnamCompanyRealtime)
    trade_tape: VietnamCompanyTradeTape = Field(default_factory=VietnamCompanyTradeTape)
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
    last_refresh_time: Optional[str] = None
    units: Dict[str, str] = Field(default_factory=dict)
    cache_metadata: Dict[str, Any] = Field(default_factory=dict)


class VietnamCorporateActionEvent(BaseModel):
    """Vietnam corporate-action calendar/history event."""

    ticker: str
    event_type: str = "unknown"
    status: str = "past"
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payment_date: Optional[str] = None
    cash_dividend_per_share: Optional[float] = None
    stock_dividend_ratio: Optional[str] = None
    rights_ratio: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    last_checked_at: Optional[str] = None


class VietnamCorporateActionsResponse(BaseModel):
    """Vietnam corporate-action calendar/history response."""

    market: str = "VN"
    status: str = "unavailable"
    source: Optional[str] = None
    last_checked_at: Optional[str] = None
    requested_tickers: List[str] = Field(default_factory=list)
    months_back: int = 6
    items: List[VietnamCorporateActionEvent] = Field(default_factory=list)
    error: Optional[str] = None
    error_detail: Optional[str] = None


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
    requested_tickers: List[str] = Field(default_factory=list)
    quotes: List[VietnamRealtimeQuote] = Field(default_factory=list)
    cache: Dict[str, Any] = Field(default_factory=dict)


class VietnamRealtimeTrade(BaseModel):
    """Vietnam optional realtime trade tape row."""

    time: Optional[str] = None
    price: Optional[float] = None
    volume: Optional[float] = None
    value: Optional[float] = None
    side_if_available: Optional[str] = None
    sequence_if_available: Optional[str] = None
    match_type: Optional[str] = None
    id: Optional[str] = None
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
    trades: List[VietnamRealtimeTrade] = Field(default_factory=list)
    note: Optional[str] = None
    cache: Dict[str, Any] = Field(default_factory=dict)


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
