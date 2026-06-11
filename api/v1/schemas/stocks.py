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


class VietnamWatchItem(BaseModel):
    """Vietnam watchlist dashboard row."""

    ticker: str
    entity: Optional[str] = None
    exchange: Optional[str] = None
    market_index: Optional[str] = None
    source: Optional[str] = None
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
    intraday_timeframe: Optional[str] = None
    intraday_source: Optional[str] = None
    intraday_is_realtime_quote: bool = False
    intraday_warning: Optional[str] = None
    intraday_candles: List[Dict[str, Any]] = Field(default_factory=list)
    intraday_pulse: Dict[str, Any] = Field(default_factory=dict)
    intraday_labels: List[str] = Field(default_factory=list)
    intraday_details: List[Dict[str, Any]] = Field(default_factory=list)
    cache_status: Dict[str, Any] = Field(default_factory=dict)
    cache_last_fetched_at: Dict[str, Any] = Field(default_factory=dict)
    cache_next_refresh_at: Dict[str, Any] = Field(default_factory=dict)
    cache_errors: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class VietnamWatchlistResponse(BaseModel):
    """Vietnam watchlist dashboard response."""

    market: str = "VN"
    source: str = "Mozyfin live"
    fixture_mode: bool = False
    last_refresh_time: Optional[str] = None
    units: Dict[str, str] = Field(default_factory=dict)
    data_quality: Dict[str, Any] = Field(default_factory=dict)
    cache_metadata: Dict[str, Any] = Field(default_factory=dict)
    watchlist: List[VietnamWatchItem] = Field(default_factory=list)
    rule_metadata: Dict[str, Any] = Field(default_factory=dict)
    formulas: Dict[str, str] = Field(default_factory=dict)


class VietnamWatchlistHealthResponse(BaseModel):
    """Vietnam watchlist data-quality health response."""

    source: str = "Mozyfin live"
    fixture_mode: bool = False
    symbols_loaded: int = 0
    last_trading_date: Optional[str] = None
    missing_fields: Dict[str, List[str]] = Field(default_factory=dict)
    errors: Dict[str, List[str]] = Field(default_factory=dict)
    last_refresh_time: Optional[str] = None
    units: Dict[str, str] = Field(default_factory=dict)
    cache_metadata: Dict[str, Any] = Field(default_factory=dict)


class VietnamRealtimeQuote(BaseModel):
    """Vietnam optional realtime/snapshot quote row."""

    symbol: str
    realtime_price: Optional[float] = None
    realtime_time: Optional[str] = None
    reference_price: Optional[float] = None
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
    source: str = "vnstock_kbs"
    status: str = "ok"
    error: Optional[str] = None


class VietnamRealtimeResponse(BaseModel):
    """Vietnam optional realtime/snapshot quote response."""

    market: str = "VN"
    source: str = "vnstock_kbs"
    status: str = "ok"
    error: Optional[str] = None
    requested_tickers: List[str] = Field(default_factory=list)
    quotes: List[VietnamRealtimeQuote] = Field(default_factory=list)
    cache: Dict[str, Any] = Field(default_factory=dict)


class VietnamRealtimeTrade(BaseModel):
    """Vietnam optional realtime trade tape row."""

    time: Optional[str] = None
    price: Optional[float] = None
    volume: Optional[float] = None
    match_type: Optional[str] = None
    id: Optional[str] = None
    source: str = "vnstock_kbs"


class VietnamRealtimeTradesResponse(BaseModel):
    """Vietnam optional realtime trade tape response."""

    market: str = "VN"
    source: str = "vnstock_kbs"
    symbol: str
    status: str = "ok"
    error: Optional[str] = None
    trades: List[VietnamRealtimeTrade] = Field(default_factory=list)
    cache: Dict[str, Any] = Field(default_factory=dict)
