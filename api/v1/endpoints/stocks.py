# -*- coding: utf-8 -*-
"""
===================================
股票数据接口
===================================

职责：
1. POST /api/v1/stocks/extract-from-image 从图片提取股票代码
2. POST /api/v1/stocks/parse-import 解析 CSV/Excel/剪贴板
3. GET /api/v1/stocks/{code}/quote 实时行情接口
4. GET /api/v1/stocks/{code}/history 历史行情接口
"""

import logging
import asyncio
from typing import Optional
import re

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile, Depends

from api.deps import get_system_config_service

from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    KLineData,
    StockHistoryResponse,
    StockQuote,
    VietnamChartResponse,
    VietnamCompanyNewsResponse,
    VietnamCompanyResearchResponse,
    VietnamCorporateActionsResponse,
    VietnamDailyIndexResponse,
    VietnamIndexComponentsResponse,
    VietnamIndexListResponse,
    VietnamMarketIndexPulseResponse,
    VietnamObservabilityResponse,
    VietnamRealtimeResponse,
    VietnamRealtimeTradesResponse,
    VietnamWatchlistHealthResponse,
    VietnamWatchlistResponse,
)
from api.v1.schemas.history import WatchlistRequest, WatchlistResponse
from api.v1.schemas.common import ErrorResponse
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.stock_service import StockService
from src.services.system_config_service import SystemConfigService
from src.services.vietnam_company_research_service import VietnamCompanyResearchService
from src.services.vietnam_market_service import VietnamMarketService
from src.services.vietnam_observability import vietnam_observability_snapshot
from data_provider.base import normalize_stock_code
from data_provider.vnstock_realtime_fetcher import VnstockRealtimeFetcher

logger = logging.getLogger(__name__)

router = APIRouter()

# 须在 /{stock_code} 路由之前定义
ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)


def _read_watchlist_codes(service: SystemConfigService) -> list:
    """Read STOCK_LIST codes as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    stock_list_str = ""
    for item in config_data.get("items", []):
        if item.get("key") == "STOCK_LIST":
            stock_list_str = str(item.get("value", ""))
            break
    return [c.strip() for c in stock_list_str.split(",") if c.strip()]


def _write_watchlist_codes(service: SystemConfigService, codes: list) -> None:
    """Persist stock codes to STOCK_LIST as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    config_version = config_data.get("config_version", "")
    service.update(
        config_version=config_version,
        items=[{"key": "STOCK_LIST", "value": ",".join(codes)}],
        mask_token="******",
        reload_now=True,
    )


# Stock code validation patterns (aligned with frontend validateStockCode)
_STOCK_CODE_RE = re.compile(
    r"^(?:\d{6}"                              # A-share 6-digit
    r"|(?:SH|SZ|BJ)\d{6}"                     # exchange-prefixed A-share
    r"|\d{6}\.(?:SH|SZ|SS|BJ)"                # exchange-suffixed A-share
    r"|\d{1,5}\.HK"                           # HK suffix format
    r"|HK\d{1,5}"                             # HK prefix format
    r"|\d{5}"                                 # bare 5-digit HK code
    r"|[A-Z]{1,5}(?:\.(?:US|[A-Z]))?"         # US ticker
    r")$",
    re.IGNORECASE,
)


def _validate_and_normalize_stock_code(code: str) -> str:
    """Validate stock code format and return canonical form.

    Raises HTTPException(400) if the code does not match supported formats.
    """
    stripped = code.strip()
    if not stripped:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_stock_code", "message": "股票代码不能为空"},
        )
    if not _STOCK_CODE_RE.match(stripped):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_stock_code",
                "message": f"'{stripped}' 不是合法的股票代码格式",
            },
        )
    return normalize_stock_code(stripped)


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "提取的股票代码"},
        400: {"description": "图片无效", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="从图片提取股票代码",
    description="上传截图/图片，通过 Vision LLM 提取股票代码。支持 JPEG、PNG、WebP、GIF，最大 5MB。",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="图片文件（表单字段名 file）"),
    include_raw: bool = Query(False, description="是否在结果中包含原始 LLM 响应"),
) -> ExtractFromImageResponse:
    """
    从上传的图片中提取股票代码（使用 Vision LLM）。

    表单字段请使用 file 上传图片。优先级：Gemini / Anthropic / OpenAI（首个可用）。
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "未提供文件，请使用表单字段 file 上传图片"},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"不支持的类型: {content_type}。允许: {ALLOWED_MIME_STR}",
            },
        )

    try:
        # 先读取限定大小，再检查是否还有剩余（语义清晰：超出则拒绝）
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"图片超过 {MAX_SIZE_BYTES // (1024 * 1024)}MB 限制",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"读取上传文件失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "读取上传文件失败"},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [
            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items
        ]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error(f"图片提取失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "图片提取失败"},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "解析结果"},
        400: {"description": "未提供数据或解析失败", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="解析 CSV/Excel/剪贴板",
    description="上传 CSV/Excel 文件或粘贴文本，自动解析股票代码。文件上限 2MB，文本上限 100KB。",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """
    解析 CSV/Excel 文件或剪贴板文本。

    - multipart/form-data + file: 上传文件
    - application/json + {"text": "..."}: 粘贴文本
    - 优先使用 file，若同时提供则忽略 text
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] JSON parse failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"JSON 解析失败: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "未提供 text，请使用 {\"text\": \"...\"}"},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            text_bytes = len(text.encode("utf-8"))
            logger.warning(
                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",
                text_bytes,
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "未提供文件，请使用表单字段 file"},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 限制",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 限制",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            size = getattr(file, "size", None)
            logger.warning(
                "[parse_import] file read failed: filename=%r, size=%s, error=%s",
                filename,
                size,
                e,
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "读取文件失败"},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes failed: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "请使用 multipart/form-data 上传文件，或 application/json 提交 {\"text\": \"...\"}",
            },
        )

    extract_items = [
        ExtractItem(code=code, name=name, confidence=conf)
        for code, name, conf in items
    ]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.get(
    "/watchlist",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "当前自选队列"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取自选队列",
    description="返回当前 STOCK_LIST 配置中的所有股票代码。",
)
def get_watchlist(
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        codes = _read_watchlist_codes(service)
        return WatchlistResponse(stock_codes=codes, message=f"当前自选 {len(codes)} 只股票")
    except Exception as e:
        logger.error(f"获取自选队列失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"获取自选队列失败: {str(e)}"},
        )


@router.post(
    "/watchlist/add",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "已加入自选"},
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="加入自选队列",
    description="将指定股票代码加入 STOCK_LIST。",
)
def add_to_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        normalized_existing = [normalize_stock_code(c) for c in codes]
        if validated not in normalized_existing:
            codes.append(request.stock_code.strip())
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"已加入 {request.stock_code.strip()}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"加入自选失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"加入自选失败: {str(e)}"},
        )


@router.post(
    "/watchlist/remove",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "已从自选删除"},
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="从自选队列删除",
    description="从 STOCK_LIST 中移除指定股票代码。",
)
def remove_from_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        normalized_existing = [normalize_stock_code(c) for c in codes]
        if validated in normalized_existing:
            idx = normalized_existing.index(validated)
            removed = codes.pop(idx)
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"已移除 {request.stock_code.strip()}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从自选删除失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"从自选删除失败: {str(e)}"},
        )


@router.get(
    "/vn/watchlist/health",
    response_model=VietnamWatchlistHealthResponse,
    summary="Vietnam watchlist data health",
    description="Return data-quality metadata for the Vietnam watchlist.",
)
def get_vietnam_watchlist_health(
    tickers: Optional[str] = Query(None, description="Comma-separated VN tickers. Defaults to FPT,VPB,MSB,SCS,ACV,ACB"),
) -> VietnamWatchlistHealthResponse:
    try:
        symbols = [item.strip().upper() for item in tickers.split(",") if item.strip()] if tickers else None
        payload = VietnamMarketService().build_health(symbols)
        return VietnamWatchlistHealthResponse(**payload)
    except Exception as e:
        logger.error("Vietnam watchlist health failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_watchlist_health_failed", "message": str(e)},
        )


@router.get(
    "/vn/watchlist",
    response_model=VietnamWatchlistResponse,
    summary="Vietnam watchlist dashboard",
    description="Return Vietnam watchlist monitoring data from SSI-backed VN market data. News is disabled by default; the production Vnstock selector returns a terms-gated unavailable status, while personal Vnstock mode is local-only and optional.",
)
def get_vietnam_watchlist(
    tickers: Optional[str] = Query(None, description="Comma-separated VN tickers. Defaults to FPT,VPB,MSB,SCS,ACV,ACB"),
    force_refresh: bool = Query(False, description="Bypass VN in-memory cache and refresh configured VN provider data"),
    include_intraday: bool = Query(True, description="Include current intraday candle pulse data when available"),
    intraday_timeframe: str = Query("1h", description="Requested SSI IntradayOhlc timeframe hint. Actual returned granularity is reported separately."),
    intraday_limit: int = Query(8, ge=1, le=48, description="Number of latest intraday candles to load"),
) -> VietnamWatchlistResponse:
    try:
        symbols = [item.strip().upper() for item in tickers.split(",") if item.strip()] if tickers else None
        payload = VietnamMarketService().build_watchlist(
            symbols,
            force_refresh=force_refresh,
            include_intraday=include_intraday,
            intraday_timeframe=intraday_timeframe,
            intraday_limit=intraday_limit,
        )
        return VietnamWatchlistResponse(**payload)
    except Exception as e:
        logger.error("Vietnam watchlist failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_watchlist_failed", "message": str(e)},
        )


@router.get(
    "/vn/company/{ticker}",
    response_model=VietnamCompanyResearchResponse,
    summary="Vietnam company research snapshot",
    description="Return a source-aware company research page skeleton for one VN ticker using SSI market data and explicit unavailable or not-implemented future-module states.",
)
def get_vietnam_company_research(
    ticker: str,
    force_refresh: bool = Query(False, description="Bypass VN in-memory cache and refresh configured VN provider data"),
) -> VietnamCompanyResearchResponse:
    try:
        payload = VietnamCompanyResearchService().get_company_research_snapshot(
            ticker,
            force_refresh=force_refresh,
        )
        return VietnamCompanyResearchResponse(**payload)
    except Exception as e:
        logger.error("Vietnam company research failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_company_research_failed", "message": str(e)},
        )


@router.get(
    "/vn/chart",
    response_model=VietnamChartResponse,
    summary="Vietnam selected ticker daily chart",
    description="Return selected-symbol daily OHLCV chart data from the configured Vietnam chart provider.",
)
def get_vietnam_chart(
    symbol: str = Query(..., description="VN ticker symbol, for example FPT or FPT.VN"),
    range_label: str = Query("6M", alias="range", pattern="^(1M|3M|6M|1Y)$", description="Chart range"),
) -> VietnamChartResponse:
    try:
        payload = VietnamMarketService().build_chart(symbol, range_label=range_label)
        if "candles" not in payload:
            payload["candles"] = payload.get("points", [])
        return VietnamChartResponse(**payload)
    except Exception as e:
        logger.error("Vietnam chart failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_chart_failed", "message": str(e)},
        )


@router.get(
    "/vn/index-list",
    response_model=VietnamIndexListResponse,
    summary="Vietnam SSI index list",
    description="Return SSI FastConnect index identifiers for Vietnam index metadata discovery.",
)
def get_vietnam_index_list(
    market: Optional[str] = Query(None, description="Optional market/exchange filter such as HOSE, HNX, or UPCOM"),
    force_refresh: bool = Query(False, description="Bypass the process-local SSI IndexList cache."),
) -> VietnamIndexListResponse:
    try:
        payload = VietnamMarketService().build_index_list(market=market, force_refresh=force_refresh)
        return VietnamIndexListResponse(**payload)
    except Exception as e:
        logger.error("Vietnam index list failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_index_list_failed", "message": str(e)},
        )


@router.get(
    "/vn/company-news",
    response_model=VietnamCompanyNewsResponse,
    summary="Vietnam selected-company news",
    description="Return optional local/personal company news for one explicit ticker. This endpoint never changes SSI market-data fields.",
)
def get_vietnam_company_news(
    ticker: str = Query(..., description="VN ticker, for example FPT"),
) -> VietnamCompanyNewsResponse:
    try:
        payload = VietnamMarketService().get_company_news(ticker)
        return VietnamCompanyNewsResponse(**payload)
    except Exception as e:
        logger.error("Vietnam company news failed: %s", e, exc_info=True)
        return VietnamCompanyNewsResponse(
            ticker=ticker.strip().upper() or None,
            status="unavailable",
            source="Vnstock Community",
            provider="vnstock_community",
            provider_mode="community_free_ticker_news",
            reason_code="provider_error",
            rights_status="personal_research_only",
            message="Company news is temporarily unavailable.",
        )


@router.get(
    "/vn/daily-index",
    response_model=VietnamDailyIndexResponse,
    summary="Vietnam SSI daily index context",
    description="Return latest SSI DailyIndex rows for IndexList-confirmed Vietnam index identifiers.",
)
def get_vietnam_daily_index(
    index_codes: str = Query("VNINDEX,VN30", description="Comma-separated SSI index codes to resolve through IndexList."),
    from_date: Optional[str] = Query(None, description="Optional inclusive date in YYYY-MM-DD format."),
    to_date: Optional[str] = Query(None, description="Optional inclusive date in YYYY-MM-DD format."),
    limit: int = Query(40, ge=1, le=260, description="Maximum provider rows retained per requested index."),
    force_refresh: bool = Query(False, description="Bypass process-local SSI IndexList and DailyIndex caches."),
) -> VietnamDailyIndexResponse:
    try:
        requested_codes = [
            value.strip().upper()
            for value in index_codes.split(",")
            if value.strip()
        ]
        payload = VietnamMarketService().build_daily_indexes(
            requested_codes,
            limit=limit,
            from_date=from_date,
            to_date=to_date,
            force_refresh=force_refresh,
        )
        return VietnamDailyIndexResponse(**payload)
    except Exception as e:
        logger.error("Vietnam daily index failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_daily_index_failed", "message": str(e)},
        )


@router.get(
    "/vn/market-index-pulse",
    response_model=VietnamMarketIndexPulseResponse,
    summary="Vietnam SSI realtime market-index pulse",
    description="Return optional SSI MI market-index pulse rows from the background streaming cache. Does not replace SSI DailyIndex or stock daily close semantics.",
)
def get_vietnam_market_index_pulse(
    index_codes: str = Query("VNINDEX,VN30,HNX,UPCOM", description="Comma-separated SSI MI index codes to read from the streaming cache."),
) -> VietnamMarketIndexPulseResponse:
    try:
        requested_codes = [
            value.strip().upper()
            for value in index_codes.split(",")
            if value.strip()
        ]
        payload = VietnamMarketService().build_market_index_pulse(requested_codes)
        return VietnamMarketIndexPulseResponse(**payload)
    except Exception as e:
        logger.error("Vietnam market index pulse failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_market_index_pulse_failed", "message": str(e)},
        )


@router.get(
    "/vn/index-components",
    response_model=VietnamIndexComponentsResponse,
    summary="Vietnam SSI index components",
    description="Return SSI FastConnect component rows for one Vietnam index code.",
)
def get_vietnam_index_components(
    index_code: Optional[str] = Query(None, description="Explicit SSI index code, for example VN30"),
    index_alias: Optional[str] = Query(None, alias="index", include_in_schema=False),
    market: Optional[str] = Query(None, description="Optional market/exchange filter such as HOSE, HNX, or UPCOM"),
    force_refresh: bool = Query(False, description="Bypass the process-local SSI IndexComponents cache."),
) -> VietnamIndexComponentsResponse:
    try:
        requested_index = index_code or index_alias
        if not requested_index:
            raise HTTPException(
                status_code=422,
                detail={"error": "missing_index_code", "message": "index_code is required."},
            )
        payload = VietnamMarketService().build_index_components(
            index_code=requested_index,
            market=market,
            force_refresh=force_refresh,
        )
        return VietnamIndexComponentsResponse(**payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Vietnam index components failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_index_components_failed", "message": str(e)},
        )


@router.get(
    "/vn/observability",
    response_model=VietnamObservabilityResponse,
    summary="Vietnam dashboard fetch observability",
    description="Return process-local Vietnam provider counters without triggering provider requests.",
)
def get_vietnam_observability() -> VietnamObservabilityResponse:
    return VietnamObservabilityResponse(**vietnam_observability_snapshot())


@router.get(
    "/vn/corporate-actions",
    response_model=VietnamCorporateActionsResponse,
    summary="Vietnam corporate-action calendar/history",
    description="Return explicitly sourced Vietnam corporate-action events when a verified provider is configured.",
)
def get_vietnam_corporate_actions(
    tickers: Optional[str] = Query(None, description="Comma-separated VN tickers. Defaults to FPT,VPB,MSB,SCS,ACV,ACB"),
    months_back: int = Query(6, ge=1, le=24, description="Recent historical window in months"),
) -> VietnamCorporateActionsResponse:
    try:
        symbols = [item.strip().upper() for item in tickers.split(",") if item.strip()] if tickers else None
        payload = VietnamMarketService().build_corporate_actions(symbols, months_back=months_back)
        return VietnamCorporateActionsResponse(**payload)
    except Exception as e:
        logger.error("Vietnam corporate actions failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "vn_corporate_actions_failed", "message": str(e)},
        )


@router.get(
    "/vn/realtime",
    response_model=VietnamRealtimeResponse,
    summary="Vietnam realtime snapshot quotes",
    description="Return SSI realtime/snapshot quote rows or an explicit SSI unavailable/disabled state. Does not modify daily close semantics.",
)
def get_vietnam_realtime_quotes(
    response: Response,
    tickers: str = Query(..., description="Comma-separated VN tickers, for example FPT,ACB,VCB"),
) -> VietnamRealtimeResponse:
    response.headers["Cache-Control"] = "no-store, no-cache, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return _get_vietnam_realtime_quotes_impl(tickers)


def _get_vietnam_realtime_quotes_impl(tickers: str) -> VietnamRealtimeResponse:
    symbols = [item.strip().upper() for item in tickers.split(",") if item.strip()]
    service = VietnamMarketService()
    try:
        if service.config.allow_legacy_kbs_provider and service.config.kbs_enabled:
            payload = VnstockRealtimeFetcher().fetch_quotes(symbols)
        else:
            payload = service.build_realtime_snapshot(symbols)
        return VietnamRealtimeResponse(**payload)
    except asyncio.CancelledError as e:
        logger.info("Vietnam realtime quotes cancelled: %s", e)
        return VietnamRealtimeResponse(
            market="VN",
            source="SSI",
            status="unavailable",
            error="SSI realtime request cancelled",
            error_detail="The SSI realtime request was cancelled before the provider response completed.",
            requested_tickers=symbols,
            quotes=[],
            cache={"cache_status": "unavailable"},
        )
    except Exception as e:
        logger.warning("Vietnam realtime quotes unavailable: %s", e, exc_info=True)
        return VietnamRealtimeResponse(
            market="VN",
            source="SSI realtime contract",
            status="unavailable",
            error="SSI realtime unavailable.",
            error_detail="Optional SSI realtime is unavailable. Daily SSI data is still available.",
            requested_tickers=symbols,
            quotes=[],
            cache={"cache_status": "unavailable"},
            diagnostics={"runtime_status": "unavailable"},
        )


@router.get(
    "/vn/realtime/trades",
    response_model=VietnamRealtimeTradesResponse,
    summary="Vietnam realtime trade tape",
    description="Return SSI trade tape rows or an explicit SSI unavailable/disabled state.",
)
def get_vietnam_realtime_trades(
    symbol: str = Query(..., description="VN ticker, for example FPT"),
    limit: int = Query(100, ge=1, le=500, description="Maximum trade rows to return"),
) -> VietnamRealtimeTradesResponse:
    service = VietnamMarketService()
    try:
        if service.config.allow_legacy_kbs_provider and service.config.kbs_enabled:
            payload = VnstockRealtimeFetcher().fetch_trades(symbol.strip().upper(), limit=limit)
        else:
            payload = service.build_trade_tape(symbol.strip().upper(), limit=limit)
        return VietnamRealtimeTradesResponse(**payload)
    except asyncio.CancelledError as e:
        logger.info("Vietnam realtime trades cancelled: %s", e)
        return VietnamRealtimeTradesResponse(
            market="VN",
            source="SSI",
            symbol=symbol.strip().upper(),
            status="unavailable",
            error="SSI trade tape request cancelled",
            error_detail="The SSI trade tape request was cancelled before the provider response completed.",
            trades=[],
            note="SSI trade tape is separate from official daily OHLCV.",
            cache={"cache_status": "unavailable"},
        )
    except Exception as e:
        logger.error("Vietnam realtime trades failed: %s", e, exc_info=True)
        return VietnamRealtimeTradesResponse(
            market="VN",
            source="SSI trade-tape contract",
            symbol=symbol.strip().upper(),
            status="unavailable",
            error="SSI trade tape unavailable.",
            error_detail="SSI trade tape unavailable.",
            reason_code="unavailable_provider_error",
            classification="unavailable_provider_error",
            status_message="SSI trade tape unavailable.",
            trades=[],
            note="SSI trade tape is separate from official daily OHLCV.",
            cache={"cache_status": "unavailable"},
            diagnostics={
                "failure_class": "provider_unavailable",
                "retryable": True,
                "exception_type": type(e).__name__,
            },
        )


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "行情数据"},
        404: {"description": "股票不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票实时行情",
    description="获取指定股票的最新行情数据"
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """
    获取股票实时行情
    
    获取指定股票的最新行情数据
    
    Args:
        stock_code: 股票代码（如 600519、00700、AAPL）
        
    Returns:
        StockQuote: 实时行情数据
        
    Raises:
        HTTPException: 404 - 股票不存在
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_realtime_quote(stock_code)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"未找到股票 {stock_code} 的行情数据"
                }
            )
        
        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取实时行情失败: {str(e)}"
            }
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "历史行情数据"},
        422: {"description": "不支持的周期参数", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票历史行情",
    description="获取指定股票的历史 K 线数据"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="K 线周期", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="获取天数")
) -> StockHistoryResponse:
    """
    获取股票历史行情
    
    获取指定股票的历史 K 线数据
    
    Args:
        stock_code: 股票代码
        period: K 线周期 (daily/weekly/monthly)
        days: 获取天数
        
    Returns:
        StockHistoryResponse: 历史行情数据
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_history_data(
            stock_code=stock_code,
            period=period,
            days=days
        )
        
        # 转换为响应模型
        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent")
            )
            for item in result.get("data", [])
        ]
        
        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            data=data
        )
    
    except ValueError as e:
        # period 参数不支持的错误（如 weekly/monthly）
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_period",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"获取历史行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取历史行情失败: {str(e)}"
            }
        )
