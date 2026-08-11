import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  stocksApi,
  type VietnamChartResponse,
  type VietnamIntradayChartResponse,
  type VietnamCorporateActionsResponse,
  type VietnamDailyIndexResponse,
  type VietnamForeignFlowBatchResponse,
  type VietnamIndexComponentsResponse,
  type VietnamIndexListResponse,
  type VietnamMarketBreadthResponse,
  type VietnamSectorStrengthResponse,
  type VietnamObservabilityResponse,
  type VietnamRealtimeResponse,
  type VietnamRealtimeTradesResponse,
  type VietnamWatchItem,
  type VietnamWatchlistResponse,
} from '../../api/stocks';
import {
  VN30_WATCHLIST_BATCH_SIZE_DEFAULT,
  VN30_WATCHLIST_BATCH_SIZE_MAX,
  VN30_WATCHLIST_BATCH_SIZE_MIN,
  chunkVietnamWatchlistTickers,
  resolveVietnamWatchlistBatchSize,
} from '../../utils/vietnamWatchlistBatching';
import { getVietnamScheduledSessionState, vietnamTodayIso } from '../../utils/vietnamIntradayPolling';
import VietnamDashboardPage from '../VietnamDashboardPage';

const mockedGetVietnamMarketPhase = vi.fn();

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getVietnamWatchlist: vi.fn(),
    getVietnamForeignFlowBatch: vi.fn(),
    getVietnamRealtimeQuotes: vi.fn(),
    getVietnamRealtimeTrades: vi.fn(),
    getVietnamCorporateActions: vi.fn(),
    getVietnamObservability: vi.fn(),
    getVietnamChart: vi.fn(),
    getVietnamIntradayChart: vi.fn(),
    getVietnamCompanyNews: vi.fn(),
    getVietnamIndexList: vi.fn(),
    getVietnamDailyIndex: vi.fn(),
    getVietnamIndexComponents: vi.fn(),
    getVietnamMarketBreadth: vi.fn(),
    getVietnamSectorStrength: vi.fn(),
  },
}));

vi.mock('../../utils/vietnamMarketPhase', () => ({
  getVietnamMarketPhase: () => mockedGetVietnamMarketPhase(),
}));

vi.mock('../../components/charts/VietnamLightweightChart', () => ({
  VietnamLightweightChart: ({
    ticker,
    points,
    shortTermZones,
    showMA20,
    showMA50,
    showBollinger,
    showShortTermZones,
    timeframe = '1D',
    requestKey = '',
    expanded = false,
    initialLogicalRange = null,
    onLogicalRangeChange,
  }: {
    ticker: string;
    points: Array<{ date?: string | null; close?: number | null }>;
    shortTermZones: Array<{ label: string; lower: number; upper: number }>;
    showMA20: boolean;
    showMA50: boolean;
    showBollinger: boolean;
    showShortTermZones: boolean;
    timeframe?: '1D' | '1m';
    requestKey?: string;
    expanded?: boolean;
    initialLogicalRange?: { from: number; to: number } | null;
    onLogicalRangeChange?: (range: { from: number; to: number } | null) => void;
  }) => (
    <div
      data-testid="vietnam-lightweight-chart"
      data-ticker={ticker}
      data-expanded={expanded ? 'true' : 'false'}
      data-points-count={String(points.length)}
      data-first-date={points[0]?.date ?? ''}
      data-last-date={points[points.length - 1]?.date ?? ''}
      data-first-close={String(points[0]?.close ?? '')}
      data-initial-logical-range={initialLogicalRange ? `${initialLogicalRange.from}:${initialLogicalRange.to}` : ''}
      data-ma20={String(showMA20)}
      data-ma50={String(showMA50)}
      data-bollinger={String(showBollinger)}
      data-short-term-zones={String(showShortTermZones)}
      data-timeframe={timeframe}
      data-request-key={requestKey}
      onClick={() => onLogicalRangeChange?.({ from: 10, to: 40 })}
    >
      {showShortTermZones
        ? shortTermZones.map((zone) => (
            <span key={zone.label} data-testid={`lightweight-zone-${zone.label}`}>
              {`${zone.label} ${zone.lower}-${zone.upper}`}
            </span>
          ))
        : null}
    </div>
  ),
}));

const defaultTickers = ['FPT', 'VPB', 'MSB', 'SCS', 'ACV', 'ACB'];
const vn30BatchSize = VN30_WATCHLIST_BATCH_SIZE_DEFAULT;
const customWatchlistStorageKey = 'vnDashboard.customWatchlist.v1';
const presetTickers = {
  VN30: ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB', 'VCB', 'VHM', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'],
  Banks: ['VCB', 'BID', 'CTG', 'MBB', 'TCB', 'ACB', 'VPB', 'HDB', 'STB', 'TPB', 'SHB', 'MSB', 'LPB', 'SSB', 'OCB', 'EIB'],
  Securities: ['SSI', 'VCI', 'VND', 'HCM', 'SHS', 'VIX', 'MBS', 'FTS', 'CTS', 'BSI', 'AGR', 'ORS'],
  'Real estate': ['VHM', 'VIC', 'VRE', 'NVL', 'PDR', 'KDH', 'NLG', 'DXG', 'DIG', 'CEO', 'HDC', 'CII', 'KBC', 'SZC'],
  Consumer: ['VNM', 'MSN', 'MWG', 'FRT', 'PNJ', 'SAB', 'BHN', 'QNS', 'DBC', 'HAG', 'BAF', 'ANV', 'FMC'],
  Logistics: ['GMD', 'HAH', 'VSC', 'VOS', 'VTO', 'VTP', 'SGP', 'PHP', 'DVP', 'SCS'],
  Tech: ['FPT', 'CMG', 'ELC', 'VGI', 'VTP', 'CTR'],
  'Oil & gas': ['GAS', 'PLX', 'PVD', 'PVS', 'BSR', 'OIL', 'PVC', 'PVT', 'PVB', 'POW'],
  Electricity: ['POW', 'NT2', 'REE', 'PC1', 'GEX', 'HDG', 'QTP', 'PPC', 'CHP', 'VSH', 'TTA', 'GEG'],
} as const;

const makeMarketPhase = (phase = 'Continuous afternoon', code = 'continuous_afternoon', isAuction = false) => ({
  phase,
  code,
  isTradingSession: code.includes('continuous') || isAuction,
  isAuction,
  isContinuous: code.includes('continuous'),
  holidayAware: false,
  nextLabel: isAuction ? 'Post-close' : 'ATC closing auction',
});

const makeChartData = () => Array.from({ length: 70 }, (_, index) => {
  const date = new Date(Date.UTC(2026, 3, 1 + index)).toISOString().slice(0, 10);
  const close = 100 + index;
  return {
    date,
    open: close - 1,
    high: close + 2,
    low: close - 2,
    close,
    volume: 1000 + index * 10,
    volumeMa20: index >= 19 ? 1100 + index * 5 : null,
    volumeMa50: index >= 49 ? 1250 + index * 5 : null,
    ma20: index >= 19 ? close - 2 : null,
    ma50: index >= 49 ? close - 5 : null,
    rsi14: index >= 14 ? 50 + (index % 10) : null,
    bbUpper: index >= 19 ? close + 10 : null,
    bbMid: index >= 19 ? close - 2 : null,
    bbLower: index >= 19 ? close - 14 : null,
  };
});

const makeChartResponse = (
  symbol = 'FPT',
  range = '6M',
  points = makeChartData(),
  overrides: Partial<VietnamChartResponse> = {},
): VietnamChartResponse => ({
  symbol,
  status: 'ok',
  source: 'SSI',
  timeframe: '1d',
  range,
  latestDate: points[points.length - 1]?.date ?? null,
  points,
  ...overrides,
});

const makeItem = (ticker: string): VietnamWatchItem => ({
  ticker,
  name: `${ticker} Listed Company`,
  entity: `${ticker}.VN`,
  exchange: 'HOSE',
  market: 'HOSE',
  securityType: 'stock',
  industry: 'Information Technology',
  sector: 'Technology',
  metadataSource: 'SSI SecuritiesDetails',
  symbolMetadata: {
    status: 'ok',
    qualityStatus: 'complete',
    completeness: 1,
    symbol: ticker,
    exchange: 'HOSE',
    market: 'HOSE',
    securityType: 'stock',
    name: `${ticker} Listed Company`,
    nameEn: `${ticker} Corporation`,
    industry: 'Information Technology',
    sector: 'Technology',
    issuer: `${ticker} issuer`,
    lotSize: 100,
    listedShares: 123456789,
    listedDate: '2006-12-13',
    source: 'SSI SecuritiesDetails',
    missingFields: [],
    fieldCoverage: {
      symbol: true,
      name: true,
      industry: true,
      sector: true,
    },
    diagnostics: {
      endpoint: 'SecuritiesDetails',
      requestedSymbol: ticker,
      normalizedRowCount: 1,
    },
  },
  issuer: `${ticker} issuer`,
  lotSize: 100,
  listedShares: 123456789,
  listedDate: '2006-12-13',
  marketIndex: 'VNINDEX.VN',
  source: 'SSI',
  primarySource: 'SSI',
  actualSource: 'SSI',
  rowsLoaded: 3,
  date: '2026-06-10',
  latestPrice: 100,
  latestPriceSource: 'SSI',
  latestPriceRawField: 'close',
  latestPriceDate: '2026-06-10',
  quotePriceDate: null,
  quotePriceRawField: null,
  priceSourceWarning: null,
  ohlcvClose: 100,
  dailyClose: 100,
  priceDate: '2026-06-10',
  ohlcvDate: '2026-06-10',
  quoteDate: '2026-06-10',
  foreignNetDate: '2026-06-10',
  foreignDateMatch: 'matched',
  candleStatus: 'unknown',
  finalCloseStatus: 'unknown',
  priceAdjustmentStatus: 'unknown',
  adjustedPriceStatus: 'unknown',
  open: 99,
  high: 101,
  low: 98,
  close: 100,
  previousClose: 99,
  changePct: 1,
  volume: 1000,
  amount: 100000,
  liquidity: { avgVolume20D: 1000, score: 80 },
  priceLimit: {
    limitPct: 7,
    referencePrice: 99,
    ceilingPrice: 106,
    floorPrice: 92,
    distanceToLimitPct: 5,
    nearLimit: false,
    source: 'SSI DailyStockPrice',
    status: 'ok',
  },
  dailyStockPrice: {
    status: 'ok',
    qualityStatus: 'ok',
    date: '2026-06-10',
    dateMatch: 'matched',
    referencePrice: 99,
    ceilingPrice: 106,
    floorPrice: 92,
    open: 99,
    high: 101,
    low: 98,
    close: 100,
    adjustedClose: 100,
    matchedVolume: 1234567,
    matchedValue: 123456789000,
    putThroughVolume: 1000,
    putThroughValue: 25000000,
    totalVolume: 1235567,
    totalValue: 123481789000,
    foreignBuyVolume: 10,
    foreignSellVolume: 5,
    foreignNetVolume: 5,
    foreignBuyValue: 1000000,
    foreignSellValue: 800000,
    foreignNetValue: 200000,
    source: 'SSI',
  },
  corporateAction: {
    status: 'unavailable',
    type: 'unknown',
    exDate: null,
    cashDividendPerShare: null,
    previousClose: 99,
    adjustedReferencePrice: null,
    adjustmentSource: 'manual_unavailable',
    priceVsAdjustedReference: null,
    priceVsAdjustedReferencePct: null,
    note: 'Corporate action data is unavailable; raw OHLCV close is unchanged.',
  },
  foreign: { buy: 10, sell: 5, net: 5, netValue: 200000, signal: 'foreign_net_positive' },
  foreignNetUnit: 'shares',
  ssiForeignNetVolume: 5,
  ssiForeignNetValue: 200000,
  foreignBuyRawField: 'foreign_buy',
  foreignSellRawField: 'foreign_sell',
  indicators: {
    close: 100,
    ma20: 99,
    ma50: 98,
    rsi14: 55,
    rsi14Wilder: 55,
    bollinger: { middle: 99, upper: 110, lower: 90 },
    avgVolume20D: 1000,
    volumeRatio: 1,
    high20d: 110,
    low20d: 90,
    distanceTo20dHighPct: -9,
    distanceTo20dLowPct: 11,
    foreignNet5D: 5,
    foreignNet20D: 10,
    foreignNetLatest: 5,
    foreignNet5dLatestAvailable: 15,
    foreignNet20dLatestAvailable: 30,
    foreignNetLatestAvailableDate: '2026-06-10',
    foreignNetHistoryCount: 20,
    high52w: 130000,
    high52wDate: '2026-06-01',
    low52w: 80000,
    low52wDate: '2025-12-01',
    highLow52wHistoryCount: 252,
    highLow52wCoverageStatus: 'complete',
    avgVolume10d: 1100,
    avgVolume10dHistoryCount: 10,
    avgVolume10dCoverageStatus: 'complete',
    avgVolume3m: 1050,
    avgVolume3mHistoryCount: 63,
    avgVolume3mCoverageStatus: 'complete',
    priceVsReferencePct: 1.01,
    priceVsReferenceStatus: 'ok',
    dailyRangePct: 3,
    dailyRangeStatus: 'ok',
    shortTermZones: {
      status: 'ok',
      reasonCode: 'short_term_zones_ready',
      source: 'derived from SSI DailyOhlc',
      timeframe: 'D1',
      lookbackSessions: 60,
      support: [{ lower: 70800, upper: 71300 }, { lower: 69200, upper: 69800 }],
      resistance: [{ lower: 73500, upper: 74100 }, { lower: 75400, upper: 76000 }],
    },
    ssiDerivedMetricsStatus: 'ok',
    ssiDerivedMetricsSource: 'SSI DailyOhlc + SSI DailyStockPrice',
  },
  statusLabels: ['Watch'],
  statusDetails: [],
  validation: { valid: true, tradingDate: '2026-06-10', missingFields: [], errors: [] },
  trend: {},
  warnings: [],
  news: [],
  newsStatus: { status: 'disabled', source: null, message: 'News provider disabled.' },
  intradayTimeframe: '1h',
  intradayRequestedTimeframe: '1h',
  intradayActualGranularity: 'unknown',
  intradayActualGranularitySeconds: null,
  intradayGranularityLabel: 'provider-returned',
  intradayCadenceStatus: 'unavailable',
  intradaySource: 'SSI',
  intradayIsRealtimeQuote: false,
  intradayWarning: 'SSI IntradayOhlc is disabled.',
  intradayCandles: [],
  intradayPulse: null,
  intradayLabels: ['Intraday data limited'],
  intradayDetails: [
    {
      label: 'Intraday data limited',
      severity: 'info',
      reason: 'SSI IntradayOhlc is disabled.',
    },
  ],
  intradayStatus: {
    status: 'disabled',
    source: 'SSI DailyStockPrice',
    message: 'SSI IntradayOhlc is disabled.',
    intradayCadenceStatus: 'unavailable',
  },
  dataQualitySummary: {
    overallStatus: 'ok',
    canonicalPriceSource: 'SSI DailyOhlc',
    issues: [],
    checks: {
      dailyOhlc: 'ok',
      dailyStockPrice: 'ok',
      finalCloseStatus: 'final',
      adjustedPriceStatus: 'unadjusted',
      intraday: 'disabled',
      realtime: 'ok',
      tradeTape: 'ok',
      profile: 'ok',
      news: 'disabled',
    },
  },
  cacheStatus: {
    ohlcvCache: 'miss',
    quoteCache: 'disabled',
    intradayCache: 'disabled',
    newsCache: 'disabled',
  },
  cacheLastFetchedAt: {
    ohlcv: '2026-06-10T08:00:00Z',
    quote: '2026-06-10T08:00:00Z',
    intradayOhlcv: '2026-06-10T08:00:00Z',
    news: '2026-06-10T08:00:00Z',
  },
  cacheNextRefreshAt: {},
  cacheErrors: {},
  error: null,
} as VietnamWatchItem);

const makeResponse = (tickers: string[], options: { fixtureMode?: boolean } = {}): VietnamWatchlistResponse => ({
  market: 'VN',
  source: options.fixtureMode ? 'SSI fixture' : 'SSI live',
  fixtureMode: options.fixtureMode ?? false,
  lastRefreshTime: '2026-06-10T08:00:00Z',
  units: { close: 'VND', volume: 'shares' },
  requestedTickersCount: tickers.length,
  returnedRowsCount: tickers.length,
  missingTickers: [],
  dataQuality: {
    source: options.fixtureMode ? 'SSI fixture' : 'SSI live',
    fixtureMode: options.fixtureMode ?? false,
    symbolsLoaded: tickers.length,
    lastTradingDate: '2026-06-10',
    missingFields: {},
    errors: {},
    requestedTickersCount: tickers.length,
    returnedRowsCount: tickers.length,
    missingTickers: [],
    lastRefreshTime: '2026-06-10T08:00:00Z',
    units: { close: 'VND', volume: 'shares' },
  },
  cacheMetadata: {
    cacheHitCount: 0,
    cacheMissCount: tickers.length,
    staleCacheUsedCount: 0,
    cacheTtlSeconds: { ohlcv: 300, quote: 60, intradayOhlcv: 60, news: 1800 },
    lastFetchedAt: {},
    nextRefreshAt: {},
    symbols: {},
  },
  watchlist: tickers.map(makeItem),
  ruleMetadata: { ruleSetName: 'Vietnam neutral technical labels', ruleSetVersion: 'v1', noRecommendation: true },
  formulas: { neutralStatusLabels: 'Rule-based neutral condition labels only; no trading recommendations are generated' },
});

const makeForeignFlowResponse = (tickers: string[]): VietnamForeignFlowBatchResponse => ({
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: 'shares',
  valueUnit: 'VND',
  finality: 'daily_available',
  requestedTickers: tickers,
  normalizedTickers: tickers,
  requestedCount: tickers.length,
  normalizedCount: tickers.length,
  returnedCount: tickers.length,
  usableCount: tickers.length,
  freshCount: tickers.length,
  staleCount: 0,
  emptyCount: 0,
  unavailableCount: 0,
  coverageRatio: tickers.length ? 1 : 0,
  complete: true,
  dataState: 'ready',
  rows: tickers.map((ticker, index) => ({
    ticker,
    dataState: 'ready',
    freshness: 'fresh',
    failureClass: null,
    staleReason: null,
    latestTradingDate: '2026-06-10',
    foreignBuyVolume: 100,
    foreignSellVolume: 40,
    foreignNetVolume: 60,
    foreignBuyValue: 3_000_000_000,
    foreignSellValue: 1_000_000_000,
    foreignNetValue: index % 2 ? -1_000_000_000 : 2_000_000_000,
    foreignNetVolume5d: 300,
    foreignNetValue5d: index % 2 ? -3_000_000_000 : 5_000_000_000,
    foreignNetVolume20d: 1_200,
    foreignNetValue20d: index % 2 ? -8_000_000_000 : 12_000_000_000,
    coveredSessions5d: 5,
    complete5d: true,
    windowEndDate5d: '2026-06-10',
    coveredSessions20d: 20,
    complete20d: true,
    windowEndDate20d: '2026-06-10',
    source: 'ssi_fastconnect',
    sourceEndpoint: 'daily_stock_price',
    volumeUnit: 'shares',
    valueUnit: 'VND',
    finality: 'daily_available',
    fetchedAt: '2026-06-10T08:00:00Z',
  })),
  rankings: {
    latestNetValue: {
      topBuy: tickers.length ? [{ ticker: tickers[0], value: 2_000_000_000, tradingDate: '2026-06-10', coveredSessions: 1, complete: true, dataState: 'ready' }] : [],
      topSell: tickers.length > 1 ? [{ ticker: tickers[1], value: -1_000_000_000, tradingDate: '2026-06-10', coveredSessions: 1, complete: true, dataState: 'ready' }] : [],
    },
    netValue5d: { topBuy: [], topSell: [] },
    netValue20d: { topBuy: [], topSell: [] },
  },
  fetchedAt: '2026-06-10T08:00:00Z',
});

const makeCurrentIntradayCandles = () => [
  {
    dateTime: '2026-06-10T10:00:00+07:00',
    timestamp: 1781074800,
    open: 100,
    high: 103,
    low: 99,
    close: 102,
    volume: 1234567,
  },
];

const mockedGetVietnamWatchlist = vi.mocked(stocksApi.getVietnamWatchlist);
const mockedGetVietnamForeignFlowBatch = vi.mocked(stocksApi.getVietnamForeignFlowBatch);
const mockedGetVietnamRealtimeQuotes = vi.mocked(stocksApi.getVietnamRealtimeQuotes);
const mockedGetVietnamRealtimeTrades = vi.mocked(stocksApi.getVietnamRealtimeTrades);
const mockedGetVietnamCorporateActions = vi.mocked(stocksApi.getVietnamCorporateActions);
const mockedGetVietnamObservability = vi.mocked(stocksApi.getVietnamObservability);
const mockedGetVietnamChart = vi.mocked(stocksApi.getVietnamChart);
const mockedGetVietnamIntradayChart = vi.mocked(stocksApi.getVietnamIntradayChart);
const mockedGetVietnamCompanyNews = vi.mocked(stocksApi.getVietnamCompanyNews);
const mockedGetVietnamIndexList = vi.mocked(stocksApi.getVietnamIndexList);
const mockedGetVietnamDailyIndex = vi.mocked(stocksApi.getVietnamDailyIndex);
const mockedGetVietnamIndexComponents = vi.mocked(stocksApi.getVietnamIndexComponents);
const mockedGetVietnamMarketBreadth = vi.mocked(stocksApi.getVietnamMarketBreadth);
const mockedGetVietnamSectorStrength = vi.mocked(stocksApi.getVietnamSectorStrength);

const makeIntradayChartResponse = (
  ticker = 'FPT',
  tradingDate = '2026-06-09',
  overrides: Partial<VietnamIntradayChartResponse> = {},
): VietnamIntradayChartResponse => ({
  ticker,
  interval: '1m',
  tradingDate,
  timezone: 'Asia/Ho_Chi_Minh',
  status: 'ready',
  sessionState: 'completed',
  freshness: 'completed',
  lastProviderRefreshAt: '2026-06-09T08:00:00Z',
  newestBarAgeSeconds: null,
  currentBarState: 'completed',
  bars: [
    { time: 1_780_980_600, open: 100, high: 102, low: 99, close: 101, volume: 1_000 },
    { time: 1_780_980_720, open: 101, high: 103, low: 100, close: 102, volume: 2_000 },
  ],
  source: { provider: 'ssi_fastconnect', dataset: 'IntradayOhlc' },
  cache: { status: 'miss', isStale: false },
  diagnostics: { requestedDate: tradingDate, providerDate: '09/06/2026', returnedRows: 2, usableBars: 2 },
  ...overrides,
});

const makeIndexListResponse = (overrides: Partial<VietnamIndexListResponse> = {}): VietnamIndexListResponse => ({
  status: 'ok',
  source: 'SSI',
  market: 'HOSE',
  rows: [
    { indexId: 'VN30', indexCode: 'VN30', indexName: 'VN30 Index', exchange: 'HOSE', market: 'HOSE', source: 'SSI' },
    { indexId: 'VNINDEX', indexCode: 'VNINDEX', indexName: 'VN Index', exchange: 'HOSE', market: 'HOSE', source: 'SSI' },
  ],
  count: 2,
  fallbackUsed: false,
  ...overrides,
});

const makeIndexComponentsResponse = (
  overrides: Partial<VietnamIndexComponentsResponse> = {},
): VietnamIndexComponentsResponse => ({
  status: 'unavailable',
  source: 'SSI',
  reason: 'SSI FastConnect request failed',
  indexCode: 'VN30',
  rows: [],
  count: 0,
  fallbackUsed: false,
  ...overrides,
});

const makeVn30ComponentsResponse = (
  tickers: readonly string[] = presetTickers.VN30,
): VietnamIndexComponentsResponse => makeIndexComponentsResponse({
  status: 'ok',
  source: 'SSI IndexComponents',
  reason: null,
  rows: tickers.map((symbol) => ({ indexCode: 'VN30', symbol, source: 'SSI IndexComponents' })),
  count: tickers.length,
});

const makeDailyIndexResponse = (
  overrides: Partial<VietnamDailyIndexResponse> = {},
): VietnamDailyIndexResponse => ({
  status: 'ok',
  source: 'SSI DailyIndex',
  requestedIndexCodes: ['VNINDEX', 'VN30'],
  latestDate: '2026-06-10',
  rows: [
    {
      status: 'ok',
      qualityStatus: 'partial',
      indexCode: 'VNINDEX',
      date: '2026-06-10',
      dateMatch: 'matched',
      indexValue: 1325.5,
      change: 5.25,
      changePct: 0.4,
      totalVolume: 123456789,
      advances: 210,
      unchanged: 60,
      declines: 175,
      source: 'SSI DailyIndex',
      missingFields: [],
      fieldCoverage: { indexValue: true, advances: true, declines: true },
    },
    {
      status: 'ok',
      qualityStatus: 'partial',
      indexCode: 'VN30',
      date: '2026-06-10',
      dateMatch: 'matched',
      indexValue: 1450.75,
      change: null,
      changePct: null,
      source: 'SSI DailyIndex',
      missingFields: ['change', 'change_pct'],
      fieldCoverage: { indexValue: true, change: false, changePct: false },
    },
  ],
  count: 2,
  fallbackUsed: false,
  ...overrides,
});

const makeMarketBreadthResponse = (
  overrides: Partial<VietnamMarketBreadthResponse> = {},
): VietnamMarketBreadthResponse => ({
  status: 'ready',
  dataState: 'ready',
  usable: true,
  indexCode: 'VN30',
  source: 'SSI',
  sourceEndpoint: 'securitiesSummary',
  aggregationBasis: 'current_vn30_membership_daily_ohlc',
  historicalConstituentCorrect: false,
  providerSessionDate: '2026-06-10',
  finality: 'completed_daily',
  freshness: 'fresh',
  membership: {
    status: 'ready',
    source: 'SSI IndexComponents',
    basis: 'current_vn30_membership',
    memberCount: 30,
    symbols: [...presetTickers.VN30],
    duplicateCount: 0,
    duplicateSymbols: [],
    invalidCount: 0,
  },
  direction: { advances: 18, declines: 10, unchanged: 2, usableCount: 30 },
  participation: { ratio: 28 / 30, formula: '(advances + declines) / direction_usable_count' },
  ma20: { aboveCount: 20, notAboveCount: 9, usableCount: 29, percentAbove: 68.9655, formula: 'close > SMA(close, 20)' },
  ma50: { aboveCount: 17, notAboveCount: 10, usableCount: 27, percentAbove: 62.963, formula: 'close > SMA(close, 50)' },
  coverage: {
    requestedCount: 30,
    membershipCount: 30,
    observedCount: 30,
    alignedCount: 30,
    directionUsableCount: 30,
    ma20UsableCount: 29,
    ma50UsableCount: 27,
    missingCount: 0,
    missingSymbols: [],
    sessionMismatchCount: 0,
    sessionMismatchSymbols: [],
  },
  timing: {},
  diagnostics: {},
  fetchedAt: '2026-06-10T09:00:00Z',
  ...overrides,
});

const makeSectorStrengthResponse = (): VietnamSectorStrengthResponse => ({
  status: 'partial', dataState: 'partial', usable: true, indexCode: 'VN30', universe: 'current_vn30_membership', source: 'SSI',
  membershipSource: 'SSI IndexComponents', classificationSource: 'SSI ICB', priceSource: 'SSI DailyOhlc', foreignFlowSource: 'SSI DailyStockPrice',
  aggregationBasis: 'current_vn30_icb_equal_weight', historicalConstituentCorrect: false, officialSectorIndexReturn: false,
  priceSessionDate: '2026-06-10', priceFinality: 'completed_daily', foreignFlowLatestCompletedDate: '2026-06-09',
  membership: { requestedCount: 30, memberCount: 30, classifiedCount: 30, unclassifiedCount: 0, unclassifiedSymbols: [], groupCount: 1, duplicateSymbols: [], symbols: [...presetTickers.VN30] },
  groups: [{
    icbCode: '8300', icbName: 'Banks', memberSymbols: ['ACB', 'VCB'], memberCount: 2, dataState: 'partial',
    return1D: { value: 0.01, usableCount: 2, missingCount: 0, method: 'equal_weight_mean_member_close_return' },
    direction: { advances: 2, declines: 0, unchanged: 0, usableCount: 2 },
    ma20: { aboveCount: 2, notAboveCount: 0, usableCount: 2, percentAbove: 100 },
    ma50: { aboveCount: 1, notAboveCount: 1, usableCount: 2, percentAbove: 50 },
    foreignFlow: { source: 'SSI DailyStockPrice', finality: 'completed_accepted', latestCompletedDate: '2026-06-09', windows: {
      '1': { requestedSessions: 1, requestedMemberCount: 2, usableMemberCount: 2, missingMemberCount: 0, usableSymbols: ['ACB', 'VCB'], coverageRatio: 1, complete: true, netValue: 1_000_000_000, observedStartDates: ['2026-06-09'], observedEndDates: ['2026-06-09'] },
      '5': { requestedSessions: 5, requestedMemberCount: 2, usableMemberCount: 2, missingMemberCount: 0, usableSymbols: ['ACB', 'VCB'], coverageRatio: 1, complete: true, netValue: 2_000_000_000, observedStartDates: ['2026-06-03'], observedEndDates: ['2026-06-09'] },
      '20': { requestedSessions: 20, requestedMemberCount: 2, usableMemberCount: 1, missingMemberCount: 1, usableSymbols: ['ACB'], coverageRatio: 0.5, complete: false, netValue: 3_000_000_000, observedStartDates: ['2026-05-12'], observedEndDates: ['2026-06-09'] },
    } },
  }],
  timing: {}, diagnostics: {}, fetchedAt: '2026-06-10T09:00:00Z',
});

const makeObservabilityResponse = (overrides: Partial<VietnamObservabilityResponse> = {}): VietnamObservabilityResponse => ({
  market: 'VN',
  status: 'ok',
  mozyfin: {
    status: 'disabled',
    source: 'legacy',
    reason: 'Mozyfin is disabled for VN dashboard runtime.',
  },
  dashboardRuntime: {
    watchlistRequestsTotal: 3,
    watchlistCacheHitsTotal: 40,
    watchlistCacheMissesTotal: 8,
    singleflightWaitsTotal: 1,
    lastWatchlistRequestAt: '2026-06-11T08:00:00Z',
    lastFetchAt: '2026-06-11T08:00:00Z',
    lastCacheKey: "('VN', 'ohlcv', 'FPT')",
    lastTickersCount: 6,
    lastFetchDurationMs: 120,
  },
  kbs: {
    status: 'disabled',
    source: 'legacy_optional',
    reason: 'KBS legacy provider is disabled for normal VN dashboard runtime.',
    legacyAllowed: false,
    enabled: false,
    quoteRequestsTotal: 12,
    quoteSuccessTotal: 10,
    quoteUnavailableTotal: 2,
    tradeRequestsTotal: 20,
    tradeSuccessTotal: 16,
    tradeUnavailableTotal: 4,
    lastQuoteRequestAt: '2026-06-11T08:00:00Z',
    lastTradeRequestAt: '2026-06-11T08:00:00Z',
    lastQuoteTickersCount: 6,
    lastTradeSymbol: 'FPT',
    lastError: 'SSI realtime provider timeout',
    lastRawErrorPresent: true,
  },
  ssiCore: {
    status: 'ok',
    source: 'SSI',
    reason: null,
    enabled: true,
  },
  ssiIntraday: {
    status: 'ok',
    source: 'SSI',
    reason: null,
    enabled: true,
  },
  ssiRealtime: {
    status: 'ok',
    source: 'SSI',
    reason: null,
    enabled: true,
  },
  ssiTradeTape: {
    status: 'ok',
    source: 'SSI',
    reason: null,
    enabled: true,
  },
  ...overrides,
});

const makeRealtimeResponse = (
  tickers: string[],
  options: {
    stale?: boolean;
    unavailable?: boolean;
    ageSeconds?: number;
    isStale?: boolean;
    timestamp?: string;
    cacheTtlSeconds?: number;
    error?: string | null;
    errorDetail?: string | null;
    rawError?: string | null;
  } = {},
): VietnamRealtimeResponse => ({
  market: 'VN',
  source: 'SSI',
  status: options.unavailable || options.error ? 'unavailable' : 'ok',
  error: options.error ?? (options.unavailable ? 'SSI realtime unavailable' : null),
  errorDetail: options.errorDetail ?? (options.unavailable ? 'Provider returned an unavailable state.' : null),
  rawError: options.rawError ?? (options.unavailable ? 'vnstock is not installed' : null),
  requestedTickers: tickers,
  quotes: tickers.map((ticker) => {
    const rawStale = options.isStale ?? options.stale ?? false;
    const ageSeconds = options.ageSeconds ?? (rawStale ? 600 : 20);
    const timestamp = options.timestamp ?? '2026-06-11T10:15:00+07:00';
    return ({
    symbol: ticker,
    realtimePrice: ticker === 'FPT' ? 101.5 : 100.5,
    realtimeTime: timestamp,
    realtimeTimeDisplay: timestamp,
    snapshotPrice: ticker === 'FPT' ? 101.5 : 100.5,
    snapshotTime: timestamp,
    snapshotTimeDisplay: timestamp,
    snapshotNote: 'SSI realtime snapshot; may differ from trade tape',
    ageSeconds,
    isStale: rawStale,
    staleReason: rawStale ? 'age_gt_60s' : null,
    cacheTtlSeconds: options.cacheTtlSeconds ?? 15,
    referencePrice: 100,
    referencePriceSource: 'ssi_realtime',
    priceVsReference: ticker === 'FPT' ? 1.5 : 0.5,
    priceVsReferencePct: ticker === 'FPT' ? 1.5 : 0.5,
    openPrice: 100,
    highPrice: 102,
    lowPrice: 99,
    averagePrice: 100.5,
    priceChange: 1.5,
    percentChange: 1.5,
    volumeAccumulated: 1000,
    totalValue: 100000,
    bidPrice1: 101.4,
    bidVol1: 100,
    askPrice1: 101.6,
    askVol1: 200,
    foreignBuyVolume: 10,
    foreignSellVolume: 5,
    foreignRoom: 100000,
    source: 'SSI',
    status: options.unavailable || options.error ? 'unavailable' : 'ok',
    error: options.error ?? (options.unavailable ? 'SSI realtime unavailable' : null),
    errorDetail: options.errorDetail ?? (options.unavailable ? 'Provider returned an unavailable state.' : null),
    rawError: options.rawError ?? (options.unavailable ? 'vnstock is not installed' : null),
  });
  }),
  cache: { cacheStatus: 'miss' },
});

const makeTradesResponse = (symbol: string): VietnamRealtimeTradesResponse => ({
  market: 'VN',
  source: 'SSI',
  symbol,
  status: 'ok',
  error: null,
  errorDetail: null,
  rawError: null,
  trades: [
    {
      time: '10:16:00',
      timestamp: '2026-06-11T10:16:00+07:00',
      timestampDisplay: '10:16:00',
      price: 101700,
      volume: 300,
      side: 'buy',
      sideLabel: 'Buy',
      sideIfAvailable: 'BU',
      change: 2700,
      changePct: 2.73,
      matchType: 'buy',
      rawType: 'X-TRADE',
      id: '1',
      source: 'SSI',
    },
  ],
  note: 'Trade tape may exclude auction/ATC prints depending on provider output',
  cache: { cacheStatus: 'miss' },
});

const makeCorporateActionsResponse = (
  tickers: string[],
  overrides: Partial<VietnamCorporateActionsResponse> = {},
): VietnamCorporateActionsResponse => ({
  market: 'VN',
  status: 'unavailable',
  source: null,
  lastCheckedAt: '2026-06-11T10:00:00+07:00',
  requestedTickers: tickers,
  monthsBack: 6,
  items: [],
  error: 'Corporate action history/calendar unavailable.',
  errorDetail: 'No verified Vietnam corporate-action event provider is configured.',
  ...overrides,
});

const clickTickerRow = (ticker: string) => {
  const indicatorTable = screen.getByRole('heading', { name: 'Indicator table' }).closest('section');
  if (!indicatorTable) throw new Error('Indicator table section not found');
  const row = within(indicatorTable).getByText(ticker).closest('tr');
  if (!row) throw new Error(`No table row found for ${ticker}`);
  fireEvent.click(row);
};

const indicatorTableSection = () => {
  const indicatorTable = screen.getByRole('heading', { name: 'Indicator table' }).closest('section');
  if (!indicatorTable) throw new Error('Indicator table section not found');
  return indicatorTable as HTMLElement;
};

const indicatorRowOrder = () => (
  Array.from(indicatorTableSection().querySelectorAll('tbody tr'))
    .map((row) => row.getAttribute('data-testid')?.replace('indicator-row-', '') ?? '')
);

const clickIndicatorSort = (name: RegExp | string) => {
  fireEvent.click(within(indicatorTableSection()).getByRole('button', { name }));
};

const indicatorFilters = () => within(screen.getByTestId('indicator-filter-controls'));

const changeIndicatorFilter = (label: string, value: string) => {
  fireEvent.change(indicatorFilters().getByLabelText(label), { target: { value } });
};

const dataStatusPanel = () => {
  const panel = screen.getByRole('heading', { name: 'Data status' }).closest('section');
  if (!panel) throw new Error('Data status panel not found');
  return within(panel);
};

const dataStatusDiagnostics = () => {
  const details = screen.getByText('Show diagnostics').closest('details');
  if (!details) throw new Error('Data status diagnostics not found');
  return details;
};

const selectedTickerHeader = () => {
  const header = screen.getByText('Selected ticker').closest('section');
  if (!header) throw new Error('Selected ticker header not found');
  return within(header);
};

const selectedDisclosure = (testId: string) => {
  const disclosure = screen.getByTestId(testId);
  return within(disclosure);
};

const dataReadinessStrip = () => {
  const strip = screen.getByTestId('data-readiness-strip');
  return within(strip);
};

const dataReadinessItem = (label: RegExp | string) => (
  dataReadinessStrip().getByRole('group', { name: label })
);

const inspectChartCard = () => {
  const chartCard = screen.getByTestId('inspect-chart-card');
  return within(chartCard);
};

const clickChartControl = async (element: Element) => {
  await act(async () => {
    fireEvent.click(element);
  });
};

const keyDownChartControl = async (target: Window | Document | Element, eventInit: KeyboardEventInit) => {
  await act(async () => {
    fireEvent.keyDown(target, eventInit);
  });
};

const foreignNetVolumeSummaryCard = () => within(screen.getByTestId('foreign-net-volume-summary-card'));

const withSsiForeignNetVolumes = (
  response: VietnamWatchlistResponse,
  values: Array<number | null | undefined>,
) => {
  response.watchlist = response.watchlist.map((item, index) => ({
    ...item,
    ssiForeignNetVolume: values[index],
    foreign: { ...item.foreign, net: 999_999_999 },
  }));
  return response;
};

const makeFilterResponse = () => {
  const response = makeResponse(defaultTickers);
  const quality: Record<string, 'ok' | 'partial' | 'unavailable'> = {
    FPT: 'ok',
    VPB: 'partial',
    MSB: 'unavailable',
    SCS: 'ok',
    ACV: 'partial',
    ACB: 'ok',
  };
  const foreignNet: Record<string, number | null> = {
    FPT: 5,
    VPB: -20,
    MSB: 0,
    SCS: -100,
    ACV: 15,
    ACB: null,
  };
  const volumeRatio: Record<string, number | null> = {
    FPT: 1,
    VPB: 2,
    MSB: null,
    SCS: 1.6,
    ACV: 0.5,
    ACB: null,
  };
  const rsi: Record<string, number | null> = {
    FPT: 55,
    VPB: 25,
    MSB: null,
    SCS: 75,
    ACV: 30,
    ACB: 70,
  };
  response.watchlist = response.watchlist.map((item) => ({
    ...item,
    status: quality[item.ticker],
    liquidity: {
      ...item.liquidity,
      avgVolume20D: volumeRatio[item.ticker] === null ? null : item.liquidity.avgVolume20D,
    },
    dataQualitySummary: { ...item.dataQualitySummary, overallStatus: quality[item.ticker] },
    ssiForeignNetVolume: foreignNet[item.ticker],
    dailyStockPrice: { ...item.dailyStockPrice, foreignNetVolume: foreignNet[item.ticker] },
    indicators: {
      ...item.indicators,
      avgVolume20D: volumeRatio[item.ticker] === null ? null : item.indicators.avgVolume20D,
      volumeRatio: volumeRatio[item.ticker],
      rsi14: rsi[item.ticker],
      rsi14Wilder: rsi[item.ticker],
    },
  }));
  return response;
};

const makeMixedRealtimeResponse = (tickers: string[]) => {
  const response = makeRealtimeResponse(tickers);
  response.quotes = response.quotes.map((quote) => {
    if (quote.symbol === 'VPB' || quote.symbol === 'SCS') {
      return {
        ...quote,
        status: 'unavailable',
        snapshotPrice: null,
        realtimePrice: null,
        price: null,
        error: 'SSI realtime unavailable',
      };
    }
    if (quote.symbol === 'MSB') {
      return {
        ...quote,
        status: 'disabled',
        snapshotPrice: null,
        realtimePrice: null,
        price: null,
        error: 'SSI realtime disabled',
      };
    }
    return quote;
  });
  return response;
};

describe('VietnamDashboardPage watchlist loading', () => {
  beforeEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    window.history.replaceState({}, '', '/vietnam');
    localStorage.clear();
    localStorage.setItem(customWatchlistStorageKey, JSON.stringify(defaultTickers));
    mockedGetVietnamWatchlist.mockReset();
    mockedGetVietnamForeignFlowBatch.mockReset();
    mockedGetVietnamRealtimeQuotes.mockReset();
    mockedGetVietnamRealtimeTrades.mockReset();
    mockedGetVietnamCorporateActions.mockReset();
    mockedGetVietnamObservability.mockReset();
    mockedGetVietnamChart.mockReset();
    mockedGetVietnamIntradayChart.mockReset();
    mockedGetVietnamCompanyNews.mockReset();
    mockedGetVietnamIndexList.mockReset();
    mockedGetVietnamDailyIndex.mockReset();
    mockedGetVietnamIndexComponents.mockReset();
    mockedGetVietnamMarketBreadth.mockReset();
    mockedGetVietnamSectorStrength.mockReset();
    mockedGetVietnamMarketPhase.mockReset();
    mockedGetVietnamMarketPhase.mockReturnValue(makeMarketPhase());
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => makeResponse(tickers?.length ? tickers : defaultTickers));
    mockedGetVietnamForeignFlowBatch.mockImplementation(async (tickers) => makeForeignFlowResponse(tickers));
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => makeTradesResponse(symbol));
    mockedGetVietnamCorporateActions.mockImplementation(async (tickers) => makeCorporateActionsResponse(tickers));
    mockedGetVietnamObservability.mockImplementation(async () => makeObservabilityResponse());
    mockedGetVietnamChart.mockImplementation(async (symbol, range = '6M') => makeChartResponse(symbol, range));
    mockedGetVietnamIntradayChart.mockImplementation(async (ticker, tradingDate) => makeIntradayChartResponse(ticker, tradingDate));
    mockedGetVietnamCompanyNews.mockImplementation(async (ticker) => ({
      ticker,
      status: 'disabled',
      source: null,
      message: 'News disabled.',
      news: [],
    }));
    mockedGetVietnamIndexList.mockImplementation(async () => makeIndexListResponse());
    mockedGetVietnamDailyIndex.mockImplementation(async () => makeDailyIndexResponse());
    mockedGetVietnamIndexComponents.mockImplementation(async () => makeIndexComponentsResponse());
    mockedGetVietnamMarketBreadth.mockImplementation(async () => makeMarketBreadthResponse());
    mockedGetVietnamSectorStrength.mockImplementation(async () => makeSectorStrengthResponse());
  });

  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
  });

  it('resolves VN30 watchlist batch size through named bounds and supports tuning', () => {
    const tickers = Array.from({ length: 12 }, (_, index) => `T${index + 1}`);

    expect(resolveVietnamWatchlistBatchSize(tickers.length)).toBe(vn30BatchSize);
    expect(resolveVietnamWatchlistBatchSize(tickers.length, 1)).toBe(VN30_WATCHLIST_BATCH_SIZE_MIN);
    expect(resolveVietnamWatchlistBatchSize(tickers.length, 99)).toBe(VN30_WATCHLIST_BATCH_SIZE_MAX);
    expect(chunkVietnamWatchlistTickers(tickers, 4).map((batch) => batch.length)).toEqual([4, 4, 4]);
    expect(chunkVietnamWatchlistTickers(tickers, 8).map((batch) => batch.length)).toEqual([8, 4]);
    expect(chunkVietnamWatchlistTickers(defaultTickers, vn30BatchSize).flat()).toEqual(defaultTickers);
  });

  it('owns one VN30 breadth request at page level and displays independent coverage', async () => {
    render(<VietnamDashboardPage />);

    expect(await screen.findByRole('heading', { name: 'Độ rộng VN30' })).toBeInTheDocument();
    expect(screen.getByText('18 tăng')).toBeInTheDocument();
    expect(screen.getByText('20 / 29')).toBeInTheDocument();
    expect(screen.getByText('17 / 27')).toBeInTheDocument();
    expect(mockedGetVietnamMarketBreadth).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamMarketBreadth.mock.calls[0]?.[0]?.forceRefresh).toBe(false);
  });

  it('owns one sector aggregate request at page level', async () => {
    render(<VietnamDashboardPage />);

    expect(await screen.findByRole('heading', { name: 'Sức mạnh ngành VN30' })).toBeInTheDocument();
    expect(within(screen.getByTestId('vn30-sector-strength')).getByText('Banks')).toBeInTheDocument();
    expect(mockedGetVietnamSectorStrength).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamSectorStrength.mock.calls[0]?.[0]?.forceRefresh).toBe(false);
  });

  it('starts fresh empty localStorage without loading hardcoded default symbols', async () => {
    localStorage.clear();

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());

    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
    expect(mockedGetVietnamForeignFlowBatch).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
    expect(mockedGetVietnamCorporateActions).not.toHaveBeenCalled();
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    expect(screen.getByTestId('watchlist-empty-start-state')).toHaveTextContent('Choose a preset or enter tickers to start.');
    expect(screen.getByTestId('selected-ticker-empty-state')).toHaveTextContent('No ticker selected');
    expect(screen.getByTestId('selected-ticker-empty-state')).toHaveTextContent('Choose a preset or enter tickers to start.');
    expect(screen.getByTestId('active-watchlist-empty-state')).toHaveTextContent('No active watchlist yet.');
  });

  it('gives an explicit URL watchlist precedence over the saved browser watchlist', async () => {
    window.history.replaceState({}, '', '/vietnam?watchlist=SSI,HPG&ticker=HPG');

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['SSI', 'HPG'], false));
    expect(screen.getByTestId('selected-ticker-hero')).toHaveTextContent('HPG');
    expect(JSON.parse(localStorage.getItem(customWatchlistStorageKey) ?? '[]')).toEqual(defaultTickers);
  });

  it('loads a query-selected ticker without inserting it into an empty watchlist', async () => {
    localStorage.clear();
    window.history.replaceState({}, '', '/vietnam?ticker=SSI');

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['SSI'], false));
    expect(screen.getByTestId('selected-ticker-hero')).toHaveTextContent('SSI');
    expect(screen.getByTestId('active-watchlist-empty-state')).toHaveTextContent('No active watchlist yet');
    expect(screen.getByTestId('watchlist-management-disclosure')).toHaveAttribute('open');
    expect(localStorage.getItem(customWatchlistStorageKey)).toBeNull();
  });

  it('keeps fresh empty start clean without preloading VN30 members', async () => {
    localStorage.clear();
    mockedGetVietnamIndexComponents.mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>(() => {
      // Would hang if fresh init still preloaded VN30 members.
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled();
    expect(screen.getByTestId('watchlist-empty-start-state')).toHaveTextContent('Choose a preset or enter tickers to start.');
    expect(screen.getByTestId('selected-ticker-empty-state')).toHaveTextContent('No ticker selected');
    expect(screen.queryByRole('button', { name: 'Loading VN30 members...' })).not.toBeInTheDocument();
    expect(screen.queryByText('Loading VN30 members. Presets and custom picker remain available.')).not.toBeInTheDocument();
    expect(screen.queryByText(/current rows (stay|remain) visible/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Loaded \d+\/\d+/)).not.toBeInTheDocument();
    expect(screen.queryByTestId('vn30-hydration-progress')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Banks' })).not.toBeDisabled();
    expect(screen.getByLabelText('Custom watchlist picker')).not.toBeDisabled();
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
  });

  it('keeps every preset and custom control clickable from a fresh empty start', async () => {
    localStorage.clear();

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    const presetGroup = within(screen.getByRole('group', { name: 'Preset groups' }));
    expect(presetGroup.getByRole('button', { name: 'VN30' })).not.toBeDisabled();
    expect(presetGroup.getByRole('button', { name: 'Banks' })).not.toBeDisabled();
    expect(presetGroup.getByRole('button', { name: 'Securities' })).not.toBeDisabled();
    expect(presetGroup.getByRole('button', { name: 'Real estate' })).not.toBeDisabled();
    expect(presetGroup.getByRole('button', { name: 'Consumer' })).not.toBeDisabled();
    expect(presetGroup.getByRole('button', { name: 'Logistics' })).not.toBeDisabled();
    expect(presetGroup.getByRole('button', { name: 'Tech' })).not.toBeDisabled();
    expect(presetGroup.getByRole('button', { name: 'Oil & gas' })).not.toBeDisabled();
    expect(presetGroup.getByRole('button', { name: 'Electricity' })).not.toBeDisabled();
    expect(screen.getByLabelText('Custom watchlist picker')).not.toBeDisabled();
    expect(screen.getByRole('button', { name: 'Apply custom watchlist' })).toBeDisabled();
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
  });

  it.each([
    ['Banks', presetTickers.Banks],
    ['Securities', presetTickers.Securities],
    ['Real estate', presetTickers['Real estate']],
    ['Consumer', presetTickers.Consumer],
    ['Logistics', presetTickers.Logistics],
    ['Tech', presetTickers.Tech],
    ['Oil & gas', presetTickers['Oil & gas']],
    ['Electricity', presetTickers.Electricity],
  ])('loads the %s local preset from a fresh empty start without VN30 members', async (label, tickers) => {
    localStorage.clear();

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    const presetButton = screen.getByRole('button', { name: label });
    expect(presetButton).not.toBeDisabled();

    fireEvent.click(presetButton);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...tickers], false));
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: label })).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps local preset clicks independent while index coverage is still loading', async () => {
    localStorage.clear();
    mockedGetVietnamIndexList.mockImplementationOnce(() => new Promise<VietnamIndexListResponse>(() => {
      // Pending background index diagnostics must not block local scan buckets.
    }));
    mockedGetVietnamDailyIndex.mockImplementationOnce(() => new Promise<VietnamDailyIndexResponse>(() => {
      // Pending background index diagnostics must not look like VN30 member loading.
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Loading VN30 members...' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Banks' })).not.toBeDisabled();
    expect(screen.getByLabelText('Custom watchlist picker')).not.toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
  });

  it('keeps IndexList and DailyIndex failures out of VN30 component status', async () => {
    mockedGetVietnamIndexList.mockRejectedValueOnce(new Error('SSI IndexList rate_limited'));
    mockedGetVietnamDailyIndex.mockRejectedValueOnce(new Error('SSI DailyIndex unavailable'));

    render(<VietnamDashboardPage />);

    expect(await screen.findByText('SSI index coverage request unavailable.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Retry VN30' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Loading VN30 members...' })).not.toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === 'SSI IndexComponents / not loaded / 0')).toBeInTheDocument();
    expect(screen.queryByText((_, element) => element?.textContent === 'SSI IndexComponents / unavailable / 0')).not.toBeInTheDocument();
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
  });

  it('settles user-driven VN30 member loading after a bounded timeout', async () => {
    localStorage.clear();
    mockedGetVietnamIndexComponents.mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>(() => {
      // Intentionally unresolved to prove the UI does not stay in member loading forever.
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled();
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();

    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    });

    expect(screen.getByRole('button', { name: 'Loading VN30 members...' })).toBeDisabled();
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('vn30-hydration-progress')).not.toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(15_000);
      await Promise.resolve();
    });

    expect(screen.getByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(screen.getByTestId('watchlist-empty-start-state')).toHaveTextContent('Choose a preset or enter tickers to start.');
    expect(screen.getAllByText('SSI VN30 components are unavailable. Select Retry VN30 to try again or choose another preset/custom watchlist.').length).toBeGreaterThan(0);
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
  });

  it('keeps fresh empty start usable when user-driven VN30 member loading is unavailable', async () => {
    localStorage.clear();
    mockedGetVietnamIndexComponents.mockRejectedValueOnce(new Error('SSI IndexComponents timeout'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    expect(await screen.findByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('watchlist-empty-start-state')).toHaveTextContent('Choose a preset or enter tickers to start.');
    expect(screen.getAllByText('SSI VN30 components are unavailable. Select Retry VN30 to try again or choose another preset/custom watchlist.').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Current rows were kept/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Loading VN30 members...' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-request-status')).not.toBeInTheDocument();
    expect(screen.queryByText(/current rows (stay|remain) visible/i)).not.toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);
    expect(selectedTickerHeader().getByRole('heading', { name: 'VCB' })).toBeInTheDocument();
  });

  it('settles VN30 member loading when SSI IndexComponents resolves unavailable with no rows', async () => {
    localStorage.clear();
    let resolveComponents: ((response: VietnamIndexComponentsResponse) => void) | undefined;
    mockedGetVietnamIndexComponents.mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>((resolve) => {
      resolveComponents = resolve;
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    expect(await screen.findByRole('button', { name: 'Loading VN30 members...' })).toBeDisabled();
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveComponents?.(makeIndexComponentsResponse({
        status: 'unavailable',
        source: 'SSI IndexComponents',
        reason: 'SSI FastConnect request failed',
        rows: [],
        count: 0,
        fallbackUsed: false,
        diagnostics: {
          requestedIndexCode: 'VN30',
          indexListStatus: 'unavailable',
          indexListReason: 'SSI FastConnect request failed',
          failureClass: 'index_list_unavailable',
          indexComponentsStatus: 'unavailable',
          normalizedRowCount: 0,
        },
      }));
    });

    expect(await screen.findByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Loading VN30 members...' })).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-empty-start-state')).toHaveTextContent('Choose a preset or enter tickers to start.');
    expect(screen.getAllByText('SSI VN30 components are unavailable. Select Retry VN30 to try again or choose another preset/custom watchlist.').length).toBeGreaterThan(0);
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
    await act(async () => {
      await Promise.resolve();
    });
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Securities' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Securities], false));
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);
    expect(selectedTickerHeader().getByRole('heading', { name: 'SSI' })).toBeInTheDocument();
  });

  it('settles unavailable VN30 member loading under React StrictMode', async () => {
    localStorage.clear();
    let resolveComponents: ((response: VietnamIndexComponentsResponse) => void) | undefined;
    mockedGetVietnamIndexComponents.mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>((resolve) => {
      resolveComponents = resolve;
    }));

    render(
      <StrictMode>
        <VietnamDashboardPage />
      </StrictMode>,
    );

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    expect(await screen.findByRole('button', { name: 'Loading VN30 members...' })).toBeDisabled();

    await act(async () => {
      resolveComponents?.(makeIndexComponentsResponse({
        status: 'unavailable',
        rows: [],
        count: 0,
        diagnostics: {
          indexListStatus: 'unavailable',
          indexComponentsStatus: 'unavailable',
          failureClass: 'index_list_unavailable',
          normalizedRowCount: 0,
        },
      }));
    });

    expect(await screen.findByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Loading VN30 members...' })).not.toBeInTheDocument();
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
  });

  it.each([
    [
      'ok status with zero rows',
      makeIndexComponentsResponse({
        status: 'ok',
        source: 'SSI IndexComponents',
        reason: null,
        rows: [],
        count: 0,
        fallbackUsed: false,
      }),
    ],
    [
      'failure diagnostics with no normalized rows',
      makeIndexComponentsResponse({
        status: 'ok',
        source: 'SSI IndexComponents',
        reason: null,
        rows: [],
        count: 0,
        fallbackUsed: false,
        diagnostics: {
          requestedIndexCode: 'VN30',
          indexListStatus: 'unavailable',
          failureClass: 'index_list_unavailable',
          indexComponentsStatus: 'unavailable',
          normalizedRowCount: 0,
        },
      }),
    ],
  ])('settles VN30 member loading for %s without hydration', async (_caseName, response) => {
    localStorage.clear();
    mockedGetVietnamIndexComponents.mockResolvedValueOnce(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    expect(await screen.findByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Loading VN30 members...' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('vn30-hydration-progress')).not.toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
    expect(screen.queryByTestId('indicator-row-ACB')).not.toBeInTheDocument();
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);
  });

  it('does not auto-retry VN30 after an unavailable terminal state and retries only on user click', async () => {
    localStorage.clear();
    let resolveRetry: ((response: VietnamIndexComponentsResponse) => void) | undefined;
    mockedGetVietnamIndexComponents
      .mockResolvedValueOnce(makeIndexComponentsResponse())
      .mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>((resolve) => {
        resolveRetry = resolve;
      }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    expect(await screen.findByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Retry VN30' }));
    expect(await screen.findByRole('button', { name: 'Loading VN30 members...' })).toBeDisabled();
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolveRetry?.(makeIndexComponentsResponse());
    });
    expect(await screen.findByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(2);
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
  });

  it('keeps user-driven VN30 component failure separate from index coverage errors', async () => {
    mockedGetVietnamIndexComponents.mockRejectedValueOnce(new Error('SSI IndexComponents unavailable'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    expect(await screen.findByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(screen.getAllByText(/SSI VN30 components are unavailable/).length).toBeGreaterThan(0);
    expect(screen.queryByText('SSI VN30 components request unavailable.')).not.toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === 'SSI IndexComponents / unavailable / 0')).toBeInTheDocument();
  });

  it('does not create a hardcoded watchlist when force refresh is clicked with no committed list', async () => {
    localStorage.clear();

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByTestId('watchlist-empty-start-state')).toBeInTheDocument());
    const forceRefresh = screen.getByRole('button', { name: 'Force live refresh' });
    expect(forceRefresh).toBeDisabled();
    fireEvent.click(forceRefresh);

    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
  });

  it('loads a preset from a fresh empty start and selects the first returned ticker', async () => {
    localStorage.clear();

    render(<VietnamDashboardPage />);

    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    expect(selectedTickerHeader().getByRole('heading', { name: 'VCB' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('lets a newer non-VN30 preset supersede an older pending preset from empty start', async () => {
    localStorage.clear();
    let resolveBanks: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamWatchlist
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveBanks = resolve;
      }))
      .mockResolvedValueOnce(makeResponse([...presetTickers.Securities]));

    render(<VietnamDashboardPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    expect(screen.getByRole('button', { name: 'Banks' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Securities' })).not.toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Securities' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Securities], false));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Securities' })).toHaveAttribute('aria-pressed', 'true'));
    expect(selectedTickerHeader().getByRole('heading', { name: 'SSI' })).toBeInTheDocument();

    await act(async () => {
      resolveBanks?.(makeResponse([...presetTickers.Banks]));
    });

    expect(screen.getByRole('button', { name: 'Securities' })).toHaveAttribute('aria-pressed', 'true');
    expect(selectedTickerHeader().getByRole('heading', { name: 'SSI' })).toBeInTheDocument();
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
  });

  it('keeps non-VN30 presets clickable while VN30 member loading is pending', async () => {
    localStorage.clear();
    let resolveVn30Members: ((response: VietnamIndexComponentsResponse) => void) | undefined;
    mockedGetVietnamIndexComponents.mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>((resolve) => {
      resolveVn30Members = resolve;
    }));

    render(<VietnamDashboardPage />);

    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    expect(await screen.findByRole('button', { name: 'Loading VN30 members...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Banks' })).not.toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true'));

    await act(async () => {
      resolveVn30Members?.(makeVn30ComponentsResponse());
    });

    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalledWith([...presetTickers.VN30.slice(0, vn30BatchSize)], false);
    expect(selectedTickerHeader().getByRole('heading', { name: 'VCB' })).toBeInTheDocument();
  });

  it('applies custom typed tickers from a fresh empty start', async () => {
    localStorage.clear();

    render(<VietnamDashboardPage />);

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'vpb' } });
    fireEvent.click(screen.getByRole('option', { name: /Add VPB.*Validate on apply/ }));
    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'acb' } });
    fireEvent.click(screen.getByRole('option', { name: /Add ACB.*Validate on apply/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply custom watchlist' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['VPB', 'ACB'], false));
    await waitFor(() => expect(selectedTickerHeader().getByRole('heading', { name: 'VPB' })).toBeInTheDocument());
    expect(JSON.parse(localStorage.getItem(customWatchlistStorageKey) ?? '[]')).toEqual(['VPB', 'ACB']);
  });

  it('renders the data readiness strip from loaded dashboard data', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));
    await screen.findByText('Trade tape ready');

    const strip = dataReadinessStrip();
    expect(strip.getByRole('heading', { name: 'Data readiness' })).toBeInTheDocument();
    expect(strip.getByText('Daily data')).toBeInTheDocument();
    expect(strip.getByText('Reference / foreign')).toBeInTheDocument();
    expect(strip.getByText('Indicators')).toBeInTheDocument();
    expect(strip.getByText('Intraday')).toBeInTheDocument();
    expect(strip.getByText('Realtime')).toBeInTheDocument();
    expect(strip.getByText('Trade tape')).toBeInTheDocument();
    expect(strip.getByText('News')).toBeInTheDocument();
    expect(strip.getByText('Daily data ready')).toBeInTheDocument();
    expect(strip.getByText('Foreign flow ready')).toBeInTheDocument();
    expect(strip.getByText('Indicators ready')).toBeInTheDocument();
    expect(strip.getByText('Intraday disabled')).toBeInTheDocument();
    expect(strip.getByText('Realtime ready')).toBeInTheDocument();
    expect(strip.getByText('Trade tape ready')).toBeInTheDocument();
    expect(strip.getByText('News disabled')).toBeInTheDocument();

    expect(dataReadinessItem(/Daily data: all current loaded rows include usable SSI DailyOhlc daily fields\./)).toHaveAttribute(
      'title',
      'Daily data: all current loaded rows include usable SSI DailyOhlc daily fields.',
    );
    expect(dataReadinessItem(/Reference \/ foreign: all current loaded rows include SSI DailyStockPrice reference or foreign-flow fields\./)).toHaveAttribute(
      'title',
      'Reference / foreign: all current loaded rows include SSI DailyStockPrice reference or foreign-flow fields.',
    );
    expect(dataReadinessItem(/Indicators: all current loaded rows include technical fields such as RSI14, moving averages, or volume ratio\./)).toHaveAttribute(
      'title',
      'Indicators: all current loaded rows include technical fields such as RSI14, moving averages, or volume ratio.',
    );
    expect(dataReadinessItem(/Intraday: existing intraday status is disabled\./)).toHaveAttribute(
      'title',
      'Intraday: existing intraday status is disabled.',
    );
    expect(dataReadinessItem(/Realtime: all current loaded rows show existing realtime status is ok and a usable realtime snapshot is present\./)).toHaveAttribute(
      'title',
      'Realtime: all current loaded rows show existing realtime status is ok and a usable realtime snapshot is present.',
    );
    expect(dataReadinessItem(/Trade tape: existing trade tape status is ok and usable trade rows are present\./)).toHaveAttribute(
      'title',
      'Trade tape: existing trade tape status is ok and usable trade rows are present.',
    );
    expect(dataReadinessItem(/News: news is disabled because live news data\/status is not implemented in this phase\./)).toHaveAttribute(
      'title',
      'News: news is disabled because live news data/status is not implemented in this phase.',
    );
  });

  it('shows daily data loading during the initial watchlist request', async () => {
    let resolveWatchlist: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamWatchlist.mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
      resolveWatchlist = resolve;
      return undefined;
    }));

    render(<VietnamDashboardPage />);

    expect(screen.getByText('Loading Vietnam watchlist...')).toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-request-status')).not.toBeInTheDocument();
    await waitFor(() => expect(dataReadinessStrip().getByText('Loading daily data')).toBeInTheDocument());
    expect(dataReadinessItem(/Daily data: current watchlist is loading and no usable daily rows are loaded yet\./)).toHaveAttribute(
      'title',
      'Daily data: current watchlist is loading and no usable daily rows are loaded yet.',
    );

    await act(async () => {
      resolveWatchlist?.(makeResponse(defaultTickers));
    });
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
  });

  it('shows partial reference and indicator readiness from row coverage', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist = response.watchlist.map((item, index) => {
      if (index < 3) return item;
      return {
        ...item,
        dailyStockPrice: {
          ...item.dailyStockPrice,
          status: 'unavailable',
          referencePrice: null,
          ceilingPrice: null,
          floorPrice: null,
          foreignBuyVolume: null,
          foreignSellVolume: null,
          foreignNetVolume: null,
          foreignBuyValue: null,
          foreignSellValue: null,
          foreignNetValue: null,
        },
        ssiReferencePrice: null,
        ssiCeilingPrice: null,
        ssiFloorPrice: null,
        ssiForeignNetVolume: null,
        ssiForeignNetValue: null,
        priceLimit: {
          ...item.priceLimit,
          referencePrice: null,
          ceilingPrice: null,
          floorPrice: null,
        },
        foreign: { ...item.foreign, buy: null, sell: null, net: null, netValue: null },
        indicators: {
          ...item.indicators,
          ma20: null,
          ma50: null,
          rsi14: null,
          rsi14Wilder: null,
          avgVolume20D: null,
          volumeRatio: null,
        },
        liquidity: { ...item.liquidity, avgVolume20D: null },
      };
    });
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const strip = dataReadinessStrip();
    expect(strip.getByText('Daily data ready')).toBeInTheDocument();
    expect(strip.getByText('Foreign flow partial')).toBeInTheDocument();
    expect(strip.getByText('Indicators partial')).toBeInTheDocument();
    expect(dataReadinessItem(/Reference \/ foreign: some current loaded rows include SSI DailyStockPrice reference or foreign-flow fields\./)).toHaveAttribute(
      'title',
      'Reference / foreign: some current loaded rows include SSI DailyStockPrice reference or foreign-flow fields.',
    );
    expect(dataReadinessItem(/Indicators: some current loaded rows include technical fields such as RSI14, moving averages, or volume ratio\./)).toHaveAttribute(
      'title',
      'Indicators: some current loaded rows include technical fields such as RSI14, moving averages, or volume ratio.',
    );
  });

  it('renders optional realtime and trade tape unavailable without endpoint diagnostics', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist = response.watchlist.map((item, index) => index === 0
      ? {
          ...item,
          realtimeStatus: {
            status: 'unavailable',
            source: 'SSI',
            message: 'SSI realtime unavailable.',
          },
          tradeTapeStatus: {
            status: 'unavailable',
            source: 'SSI',
            message: 'SSI trade tape unavailable.',
          },
          diagnostics: {
            realtime: {
              attemptedEndpoints: ['RealtimeQuote'],
              httpStatus: 404,
              rawProviderErrorSummary: 'raw provider message',
            },
            tradeTape: {
              attemptedEndpoints: ['TradeTape'],
              httpStatus: 404,
              rawProviderErrorSummary: 'raw provider message',
            },
          },
          tradeTape: [],
          dataQualitySummary: {
            ...item.dataQualitySummary,
            checks: {
              ...item.dataQualitySummary?.checks,
              realtime: 'unavailable',
              tradeTape: 'unavailable',
            },
          },
        }
      : item);
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockResolvedValue(makeRealtimeResponse(defaultTickers, {
      unavailable: true,
      error: 'SSI realtime unavailable',
      errorDetail: 'Attempted endpoints: RealtimeQuote',
      rawError: 'HTTP status 404',
    }));
    mockedGetVietnamRealtimeTrades.mockResolvedValue({
      ...makeTradesResponse('FPT'),
      status: 'unavailable',
      error: 'SSI trade tape unavailable',
      errorDetail: 'Attempted endpoints: TradeTape',
      rawError: 'HTTP status 404',
      trades: [],
    });

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));
    await screen.findByText('Trade tape unavailable');

    const strip = dataReadinessStrip();
    expect(strip.getByText('Daily data ready')).toBeInTheDocument();
    expect(strip.getByText('Realtime unavailable')).toBeInTheDocument();
    expect(strip.getByText('Trade tape unavailable')).toBeInTheDocument();
    expect(strip.getByText('News disabled')).toBeInTheDocument();
    expect(dataReadinessItem(/Realtime: existing realtime status is unavailable or no usable realtime snapshot is present\./)).toHaveAttribute(
      'title',
      'Realtime: existing realtime status is unavailable or no usable realtime snapshot is present.',
    );
    expect(dataReadinessItem(/Trade tape: existing status is unavailable or no usable trade rows are present in the current response\./)).toHaveAttribute(
      'title',
      'Trade tape: existing status is unavailable or no usable trade rows are present in the current response.',
    );
    expect(dataReadinessItem(/News: news is disabled because live news data\/status is not implemented in this phase\./)).toHaveAttribute(
      'title',
      'News: news is disabled because live news data/status is not implemented in this phase.',
    );
    expect(strip.queryByText(/Attempted endpoints|RealtimeQuote|TradeTape|HTTP status|raw provider/i)).not.toBeInTheDocument();
  });

  it('renders a serious daily data unavailable state when no daily rows are available', async () => {
    mockedGetVietnamWatchlist.mockResolvedValue(makeResponse([]));
    mockedGetVietnamRealtimeQuotes.mockResolvedValue(makeRealtimeResponse([]));
    mockedGetVietnamRealtimeTrades.mockResolvedValue({
      ...makeTradesResponse('FPT'),
      status: 'unavailable',
      trades: [],
    });

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(dataReadinessStrip().getByText('Daily data unavailable')).toBeInTheDocument();
    expect(screen.getByTestId('indicator-daily-unavailable-state')).toHaveTextContent('Daily data unavailable');
    expect(screen.getByTestId('indicator-daily-unavailable-state')).toHaveTextContent('No daily SSI rows are available for the active watchlist.');
    expect(screen.getByTestId('selected-ticker-empty-state')).toHaveTextContent('Selected ticker unavailable because no valid daily rows are loaded.');
    expect(screen.getByText('No selected ticker detail can be shown until daily watchlist rows load.')).toBeInTheDocument();
  });

  it('keeps optional live unavailable states minor while valid daily rows remain visible', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist = response.watchlist.map((item) => ({
      ...item,
      intradayStatus: { status: 'unavailable', source: 'SSI IntradayOhlc', message: 'SSI intraday unavailable.' },
      intradayCandles: [],
      intradayPulse: null,
      realtimeStatus: { status: 'unavailable', source: 'SSI realtime contract', message: 'SSI realtime unavailable.' },
      realtimeSnapshot: null,
      tradeTapeStatus: { status: 'unavailable', source: 'SSI trade-tape contract', message: 'SSI trade tape unavailable.' },
      tradeTape: [],
      dataQualitySummary: {
        ...item.dataQualitySummary,
        checks: {
          ...item.dataQualitySummary?.checks,
          intraday: 'unavailable',
          realtime: 'unavailable',
          tradeTape: 'unavailable',
          news: 'disabled',
        },
      },
    }));
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { unavailable: true }));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => ({
      ...makeTradesResponse(symbol),
      status: 'unavailable',
      error: null,
      errorDetail: 'Attempted endpoints: TradeTape',
      rawError: 'HTTP status 404',
      trades: [],
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();
    expect(indicatorTableSection()).toHaveTextContent('Ready');
    expect(indicatorTableSection()).toHaveTextContent('Realtime unavailable');
    expect(selectedTickerHeader().getByText('Daily close')).toBeInTheDocument();

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByText('SSI intraday unavailable.')).toBeInTheDocument();
    expect(detail.getByText('SSI realtime unavailable. Daily SSI data is still available.')).toBeInTheDocument();
    expect(detail.getByText('SSI trade tape unavailable.')).toBeInTheDocument();
    expect(detail.queryByText(/TradeTape|HTTP status|Attempted endpoints/i)).not.toBeInTheDocument();

    expect(screen.queryByText(/full-page failure/i)).not.toBeInTheDocument();
    expect(screen.queryByText('SSI unavailable')).not.toBeInTheDocument();
  });

  it('shows specific optional live availability reasons without hiding daily rows', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist = response.watchlist.map((item) => ({
      ...item,
      intradayStatus: {
        status: 'unavailable',
        source: 'SSI IntradayOhlc',
        message: 'SSI IntradayOhlc returned no usable candles.',
        reasonCode: 'unavailable_no_rows',
      },
      intradayCandles: [],
      intradayPulse: null,
      realtimeStatus: {
        status: 'unavailable',
        source: 'SSI realtime contract',
        message: 'SSI realtime cache miss.',
        reasonCode: 'running_idle',
        runtimeStatus: 'running_idle',
        cacheStatus: 'empty',
      },
      realtimeSnapshot: null,
      tradeTapeStatus: {
        status: 'unavailable',
        source: 'SSI trade-tape contract',
        message: 'SSI trade tape unavailable.',
        reasonCode: 'latest_trade_stream_only',
      },
      tradeTape: [],
      dataQualitySummary: {
        ...item.dataQualitySummary,
        issues: [
          { code: 'intraday_unavailable_no_rows', severity: 'info', message: 'SSI IntradayOhlc returned no usable candles.' },
          { code: 'realtime_running_idle', severity: 'info', message: 'SSI realtime cache miss.' },
          { code: 'trade_tape_latest_trade_stream_only', severity: 'info', message: 'SSI trade tape unavailable.' },
        ],
        checks: {
          ...item.dataQualitySummary?.checks,
          intraday: 'unavailable',
          realtime: 'unavailable',
          tradeTape: 'unavailable',
        },
      },
    }));
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers, { unavailable: true }),
      statusMessage: 'SSI realtime cache miss.',
      reasonCode: 'running_idle',
      quotes: [],
    }));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => ({
      ...makeTradesResponse(symbol),
      status: 'unavailable',
      statusMessage: 'SSI trade tape unavailable.',
      reasonCode: 'latest_trade_stream_only',
      error: null,
      errorDetail: null,
      rawError: null,
      trades: [],
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();
    expect(selectedTickerHeader().getByText('Daily close')).toBeInTheDocument();

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByText('SSI IntradayOhlc returned no usable candles.')).toBeInTheDocument();
    expect(detail.getByText('SSI realtime cache miss. Daily SSI data is still available.')).toBeInTheDocument();
    expect(detail.getByText('SSI trade tape unavailable.')).toBeInTheDocument();
    expect(detail.queryByText(/attempted endpoints|HTTP status|raw provider/i)).not.toBeInTheDocument();
    expect(detail.queryByText('Realtime price')).not.toBeInTheDocument();
    expect(detail.queryByRole('table')).not.toBeInTheDocument();
  });

  it('does not add API calls for the data readiness strip', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    await waitFor(() => expect(mockedGetVietnamCorporateActions).toHaveBeenCalledWith(['FPT'], 6));
    await waitFor(() => expect(mockedGetVietnamIndexList).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedGetVietnamDailyIndex).toHaveBeenCalledTimes(1));
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();

    const callCounts = {
      watchlist: mockedGetVietnamWatchlist.mock.calls.length,
      realtime: mockedGetVietnamRealtimeQuotes.mock.calls.length,
      tradeTape: mockedGetVietnamRealtimeTrades.mock.calls.length,
      corporateActions: mockedGetVietnamCorporateActions.mock.calls.length,
      indexList: mockedGetVietnamIndexList.mock.calls.length,
      dailyIndex: mockedGetVietnamDailyIndex.mock.calls.length,
      indexComponents: mockedGetVietnamIndexComponents.mock.calls.length,
    };
    expect(dataReadinessStrip().getByRole('heading', { name: 'Data readiness' })).toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(callCounts.watchlist);
    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(callCounts.realtime);
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(callCounts.tradeTape);
    expect(mockedGetVietnamCorporateActions).toHaveBeenCalledTimes(callCounts.corporateActions);
    expect(mockedGetVietnamIndexList).toHaveBeenCalledTimes(callCounts.indexList);
    expect(mockedGetVietnamDailyIndex).toHaveBeenCalledTimes(callCounts.dailyIndex);
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(callCounts.indexComponents);
  });

  it('does not use recommendation wording in the data readiness strip', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(dataReadinessStrip().queryByText(/\b(buy|sell|hold)\b|target[- ]price|recommendation/i)).not.toBeInTheDocument();
  });

  it('renders restored Custom preset controls', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByRole('button', { name: 'Custom' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Custom watchlist picker')).toHaveAttribute('placeholder', 'Search ticker...');
    expect(screen.getByRole('button', { name: 'Apply custom watchlist' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Clear' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Remove FPT' })).toBeInTheDocument();
  });

  it('searches loaded ticker options by symbol and company name without calling the watchlist endpoint', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'fpt listed' } });

    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(screen.getByRole('option', { name: /FPT/ })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /VPB/ })).not.toBeInTheDocument();
  });

  it('adds and removes multi-select ticker chips without duplicates', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'fpt' } });
    fireEvent.click(screen.getByRole('option', { name: /FPT/ }));
    expect(screen.getByRole('button', { name: 'Remove FPT' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /FPT/ })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'vpb' } });
    fireEvent.click(screen.getByRole('option', { name: /VPB/ }));
    expect(screen.getByRole('button', { name: 'Remove VPB' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Remove FPT' }));
    expect(screen.queryByRole('button', { name: 'Remove FPT' })).not.toBeInTheDocument();
  });

  it('does not silently accept an invalid typed ticker', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: '@@@' } });

    expect(screen.getByText(/No loaded ticker match/)).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /Add @@@/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Apply custom watchlist' })).toBeDisabled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('requires explicit selection before applying an exact typed ticker candidate', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'xyz' } });
    expect(screen.getByRole('option', { name: /Add XYZ.*Validate on apply/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Apply custom watchlist' })).toBeDisabled();

    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('applies normalized unique picker selections and selects the first ticker when needed', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'vpb' } });
    fireEvent.click(screen.getByRole('option', { name: /VPB/ }));
    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'acb' } });
    fireEvent.click(screen.getByRole('option', { name: /ACB/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply custom watchlist' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['VPB', 'ACB'], false));
    expect(selectedTickerHeader().getByRole('heading', { name: 'VPB' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Custom' })).toHaveAttribute('aria-pressed', 'true');
    expect(JSON.parse(localStorage.getItem(customWatchlistStorageKey) ?? '[]')).toEqual(['VPB', 'ACB']);
  });

  it('suppresses repeated custom apply clicks while keeping previous rows visible', async () => {
    let resolveCustom: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveCustom = resolve;
      }));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'vpb' } });
    fireEvent.click(screen.getByRole('option', { name: /VPB/ }));
    const applyButton = screen.getByRole('button', { name: 'Apply custom watchlist' });
    fireEvent.click(applyButton);
    fireEvent.click(applyButton);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('button', { name: 'Apply custom watchlist' })).toBeDisabled();
    expect(screen.getByLabelText('Custom watchlist picker')).toBeDisabled();
    expect(screen.getByText('Loading 1 custom watchlist rows; current rows remain visible.')).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();

    await act(async () => {
      resolveCustom?.(makeResponse(['VPB']));
    });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Custom' })).toHaveAttribute('aria-pressed', 'true'));
  });

  it('loads saved custom watchlist and uses it from the Custom preset', async () => {
    localStorage.setItem(customWatchlistStorageKey, JSON.stringify(['GMD', 'SCS']));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['GMD', 'SCS'], false));
    expect(screen.getByRole('button', { name: 'Remove GMD' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove SCS' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Custom' })).toHaveAttribute('aria-pressed', 'true');
    expect(selectedTickerHeader().getByRole('heading', { name: 'GMD' })).toBeInTheDocument();
  });

  it('clear removes saved picker selections without reloading the active watchlist', async () => {
    localStorage.setItem(customWatchlistStorageKey, JSON.stringify(['FPT', 'VPB']));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['FPT', 'VPB'], false));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));

    expect(localStorage.getItem(customWatchlistStorageKey)).toBeNull();
    expect(screen.getByText('No custom tickers selected.')).toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('renders all preset group buttons with exact names', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const presetGroup = within(screen.getByRole('group', { name: 'Preset groups' }));
    for (const presetName of Object.keys(presetTickers)) {
      expect(presetGroup.getByRole('button', { name: presetName === 'VN30' ? /VN30/ : presetName })).toBeInTheDocument();
    }
  });

  it('switches each preset through the expected watchlist ticker request', async () => {
    mockedGetVietnamIndexComponents.mockImplementation(async () => makeVn30ComponentsResponse());
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const presetGroup = within(screen.getByRole('group', { name: 'Preset groups' }));
    let expectedWatchlistCalls = 1;
    for (const [presetName, tickers] of Object.entries(presetTickers)) {
      fireEvent.click(presetGroup.getByRole('button', { name: presetName }));
      const expectedBatches = presetName === 'VN30'
        ? chunkVietnamWatchlistTickers([...tickers], vn30BatchSize)
        : [[...tickers]];
      expectedWatchlistCalls += expectedBatches.length;
      await waitFor(() => {
        expectedBatches.forEach((batch) => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(batch, false));
        expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(expectedWatchlistCalls);
      });
    }
  });

  it('keeps the selected ticker when it exists in the new preset', async () => {
    mockedGetVietnamIndexComponents.mockImplementation(async () => makeVn30ComponentsResponse());
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.VN30.slice(0, vn30BatchSize)], false));
    expect(selectedTickerHeader().getByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'VN30' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps VN30 retry enabled when SSI IndexComponents is unavailable and never applies hardcoded rows', async () => {
    mockedGetVietnamIndexComponents.mockResolvedValueOnce(makeIndexComponentsResponse());
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();

    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    const vn30Button = screen.getByRole('button', { name: 'VN30' });
    expect(vn30Button).not.toBeDisabled();
    expect(vn30Button).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(vn30Button);

    await waitFor(() => expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole('button', { name: 'Retry VN30' })).not.toBeDisabled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(screen.getAllByText(/SSI VN30 components are unavailable/).length).toBeGreaterThan(0);
    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();
  });

  it('splits VN30 member loading from the 30-row watchlist loading stage', async () => {
    const thirtySymbols = Array.from({ length: 30 }, (_, index) => `V${String(index + 1).padStart(2, '0')}`);
    let resolveRetry: ((response: VietnamIndexComponentsResponse) => void) | undefined;
    let resolveRows: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamIndexComponents.mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>((resolve) => {
      resolveRetry = resolve;
    }));
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveRows = resolve;
      }));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    expect(await screen.findByRole('button', { name: 'Loading VN30 members...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Banks' })).not.toBeDisabled();
    expect(screen.getByText('Loading VN30 members; current rows stay visible.')).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();

    await act(async () => {
      resolveRetry?.(makeVn30ComponentsResponse(thirtySymbols));
    });
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(thirtySymbols.slice(0, vn30BatchSize), false));
    expect(screen.queryByRole('button', { name: 'Loading VN30 members...' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'VN30' })).toBeDisabled();
    expect(screen.getByText(`Loaded 0/30 VN30 rows · Loading batch 1/6 (${vn30BatchSize} tickers per batch).`)).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-V01')).toHaveAttribute('data-hydration-state', 'loading');
    expect(screen.getAllByTestId(/indicator-row-V/)).toHaveLength(30);

    await act(async () => {
      resolveRows?.(makeResponse(thirtySymbols.slice(0, vn30BatchSize)));
    });
    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).toHaveAttribute('aria-pressed', 'true'));
    expect(screen.getByTestId('indicator-row-V01')).not.toHaveAttribute('data-hydration-state');
    expect(screen.getAllByTestId(/indicator-row-V/)).toHaveLength(30);
  });

  it('hydrates VN30 rows sequentially with the resolved default batch size without changing membership order', async () => {
    const symbols = Array.from({ length: 12 }, (_, index) => `B${String(index + 1).padStart(2, '0')}`);
    let resolveFirst: ((response: VietnamWatchlistResponse) => void) | undefined;
    let resolveSecond: ((response: VietnamWatchlistResponse) => void) | undefined;
    let resolveThird: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamIndexComponents.mockResolvedValue(makeVn30ComponentsResponse(symbols));
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveFirst = resolve;
      }))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveSecond = resolve;
      }))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveThird = resolve;
      }));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(symbols.slice(0, vn30BatchSize), false));
    expect(indicatorRowOrder()).toEqual(symbols);
    expect(screen.getByTestId('indicator-row-B01')).toHaveAttribute('data-hydration-state', 'loading');
    expect(screen.getByTestId('indicator-row-B12')).toHaveAttribute('data-hydration-state', 'loading');

    await act(async () => {
      resolveFirst?.(makeResponse(symbols.slice(0, vn30BatchSize)));
    });
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(symbols.slice(vn30BatchSize, vn30BatchSize * 2), false));
    expect(screen.getByText(`Loaded ${vn30BatchSize}/12 VN30 rows · Loading batch 2/3 (${vn30BatchSize} tickers per batch).`)).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-B01')).not.toHaveAttribute('data-hydration-state');
    expect(screen.getByTestId('indicator-row-B06')).toHaveAttribute('data-hydration-state', 'loading');
    expect(indicatorRowOrder()).toEqual(symbols);

    await act(async () => {
      resolveSecond?.(makeResponse(symbols.slice(vn30BatchSize, vn30BatchSize * 2)));
    });
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(symbols.slice(10), false));
    expect(screen.getByText(`Loaded ${vn30BatchSize * 2}/12 VN30 rows · Loading batch 3/3 (${vn30BatchSize} tickers per batch).`)).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-B06')).not.toHaveAttribute('data-hydration-state');
    expect(screen.getByTestId('indicator-row-B11')).toHaveAttribute('data-hydration-state', 'loading');
    expect(indicatorRowOrder()).toEqual(symbols);

    await act(async () => {
      resolveThird?.(makeResponse(symbols.slice(10)));
    });
    await waitFor(() => expect(screen.queryByTestId('vn30-hydration-progress')).not.toBeInTheDocument());
    expect(indicatorRowOrder()).toEqual(symbols);
    expect(screen.getByTestId('indicator-row-B12')).not.toHaveAttribute('data-hydration-state');
  });

  it('keeps successful VN30 batches and retries only failed rows', async () => {
    const symbols = ['R01', 'R02', 'R03', 'R04', 'R05', 'R06', 'R07'];
    mockedGetVietnamIndexComponents.mockResolvedValue(makeVn30ComponentsResponse(symbols));
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockResolvedValueOnce(makeResponse(symbols.slice(0, vn30BatchSize)))
      .mockRejectedValueOnce(new Error('SSI batch timeout'))
      .mockResolvedValueOnce(makeResponse(symbols.slice(vn30BatchSize)));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    const retry = await screen.findByRole('button', { name: 'Retry failed rows' });
    expect(screen.getByText(`Loaded ${vn30BatchSize}/7 VN30 rows; 2 unavailable.`)).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-R01')).not.toHaveAttribute('data-hydration-state');
    expect(screen.getByTestId('indicator-row-R06')).toHaveAttribute('data-hydration-state', 'failed');
    expect(within(screen.getByTestId('indicator-row-R06')).getAllByText('Unavailable')).toHaveLength(2);
    const callsBeforeRetry = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.click(retry);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(callsBeforeRetry + 1));
    expect(mockedGetVietnamWatchlist).toHaveBeenLastCalledWith(symbols.slice(vn30BatchSize), false);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Retry failed rows' })).not.toBeInTheDocument());
    expect(indicatorRowOrder()).toEqual(symbols);
    expect(screen.getByTestId('indicator-row-R06')).not.toHaveAttribute('data-hydration-state');
  });

  it('suppresses repeated VN30 clicks while the first batch is pending', async () => {
    const symbols = ['D01', 'D02', 'D03', 'D04', 'D05', 'D06'];
    mockedGetVietnamIndexComponents.mockResolvedValue(makeVn30ComponentsResponse(symbols));
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>(() => {
        // Keep batch one pending so duplicate click suppression is observable.
      }));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    const vn30Button = screen.getByRole('button', { name: 'VN30' });
    fireEvent.click(vn30Button);
    fireEvent.click(vn30Button);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(symbols.slice(0, vn30BatchSize), false));
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(2);
    expect(screen.getByRole('button', { name: 'VN30' })).toBeDisabled();
  });

  it('ignores a stale VN30 batch after switching to another preset', async () => {
    const symbols = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06'];
    let resolveVn30Batch: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamIndexComponents.mockResolvedValue(makeVn30ComponentsResponse(symbols));
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveVn30Batch = resolve;
      }));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(symbols.slice(0, vn30BatchSize), false));
    expect(screen.getByRole('button', { name: 'Banks' })).not.toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));

    await act(async () => {
      resolveVn30Batch?.(makeResponse(symbols.slice(0, vn30BatchSize)));
    });

    await waitFor(() => expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true'));
    expect(indicatorRowOrder()).toEqual([...presetTickers.Banks]);
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalledWith(symbols.slice(vn30BatchSize), false);
  });

  it('reuses loaded SSI VN30 components and keeps normal watchlist cache semantics', async () => {
    const ssiSymbols = ['FPT', 'HPG', 'SSI'];
    mockedGetVietnamIndexComponents.mockResolvedValue(makeVn30ComponentsResponse(ssiSymbols));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(ssiSymbols, false));
    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).toHaveAttribute('aria-pressed', 'true'));

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true'));
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(ssiSymbols, false));
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledWith('VN30');
  });

  it('keeps explicit force-refresh semantics after VN30 batch hydration completes', async () => {
    const symbols = ['FPT', 'HPG', 'SSI'];
    mockedGetVietnamIndexComponents.mockResolvedValue(makeVn30ComponentsResponse(symbols));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(symbols, false));
    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).toHaveAttribute('aria-pressed', 'true'));

    fireEvent.click(screen.getByRole('button', { name: 'Force live refresh' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(symbols, true));
  });

  it('shows staged long-loading copy while preserving previous VN30 rows', async () => {
    const thirtySymbols = Array.from({ length: 30 }, (_, index) => `V${String(index + 1).padStart(2, '0')}`);
    let resolveComponents: ((response: VietnamIndexComponentsResponse) => void) | undefined;
    mockedGetVietnamIndexComponents.mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>((resolve) => {
      resolveComponents = resolve;
    }));
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>(() => {
        // Intentionally unresolved so staged long-loading copy can be asserted.
      }));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
      await Promise.resolve();
    });

    expect(screen.getByRole('button', { name: 'Loading VN30 members...' })).toBeDisabled();
    await act(async () => {
      resolveComponents?.(makeVn30ComponentsResponse(thirtySymbols));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText(new RegExp(`Loaded 0/30 VN30 rows .* Loading batch 1/6 \\(${vn30BatchSize} tickers per batch\\)`, 'i'))).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-V01')).toHaveAttribute('data-hydration-state', 'loading');

    await act(async () => {
      vi.advanceTimersByTime(3_000);
      await Promise.resolve();
    });
    expect(screen.getByText('Still loading VN30 rows... Loaded 0/30.')).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await Promise.resolve();
    });
    expect(screen.getByText('Taking longer than expected. Loaded 0/30. You can keep using the current data.')).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-V01')).toHaveAttribute('data-hydration-state', 'loading');
  });

  it('retries unavailable VN30 components and applies only the returned SSI symbols', async () => {
    mockedGetVietnamIndexComponents
      .mockResolvedValueOnce(makeIndexComponentsResponse())
      .mockResolvedValueOnce(makeVn30ComponentsResponse(['ssi', 'fpt', 'SSI']));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry VN30' })).not.toBeDisabled());
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Retry VN30' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['SSI', 'FPT'], false));
    expect(screen.getByRole('button', { name: 'VN30' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('does not let an older VN30 retry overwrite a newer preset intent', async () => {
    let resolveRetry: ((response: VietnamIndexComponentsResponse) => void) | undefined;
    mockedGetVietnamIndexComponents.mockImplementationOnce(() => new Promise<VietnamIndexComponentsResponse>((resolve) => {
      resolveRetry = resolve;
    }));
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));
    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));

    await act(async () => {
      resolveRetry?.(makeVn30ComponentsResponse());
    });

    await waitFor(() => expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true'));
    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalledWith([...presetTickers.VN30], false);
  });

  it('falls back to the first preset ticker when the selected ticker is absent', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    expect(selectedTickerHeader().getByRole('heading', { name: 'VCB' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('does not add extra watchlist requests while switching a preset', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamIndexList).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedGetVietnamDailyIndex).toHaveBeenCalledTimes(1));
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    const indexListCalls = mockedGetVietnamIndexList.mock.calls.length;
    const dailyIndexCalls = mockedGetVietnamDailyIndex.mock.calls.length;
    const indexComponentCalls = mockedGetVietnamIndexComponents.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Consumer' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Consumer], false));
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls + 1);
    expect(mockedGetVietnamIndexList).toHaveBeenCalledTimes(indexListCalls);
    expect(mockedGetVietnamDailyIndex).toHaveBeenCalledTimes(dailyIndexCalls);
    expect(mockedGetVietnamIndexComponents).toHaveBeenCalledTimes(indexComponentCalls);
  });

  it('keeps SSI daily close, SSI realtime, and trade tape separate', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getAllByText(/Daily close/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/SSI realtime/i).length).toBeGreaterThan(0);
    expect(await screen.findByRole('heading', { name: 'Trade tape' })).toBeInTheDocument();
    expect(screen.getByText('Historical trade tape is separate from X-TRADE latest-trade stream context.')).toBeInTheDocument();
    expect(screen.getByText('SSI realtime snapshot; may differ from trade tape')).toBeInTheDocument();
    expect(screen.getAllByText(/OHLCV close 0\.10/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('0.10').length).toBeGreaterThan(0);
  });

  it('shows previous-session foreign freshness and hides zero auction trade facts', async () => {
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => ({
      ...makeResponse(tickers?.length ? tickers : defaultTickers),
      watchlist: (tickers?.length ? tickers : defaultTickers).map((ticker) => {
        const item = makeItem(ticker);
        return ticker === 'FPT'
          ? {
              ...item,
              dailyStockPrice: {
                ...item.dailyStockPrice,
                status: 'partial',
                dataDate: '2026-07-23',
                freshnessStatus: 'previous_session_during_live_market',
                isCurrentSession: false,
                isProvisional: false,
                isCompletedSession: true,
              },
              realtimeStatus: {
                ...item.realtimeStatus,
                status: 'unavailable',
                diagnostics: { symbolDataHealth: 'auction_waiting_for_match' },
              },
              tradeTape: [],
              tradeTapeStatus: {
                status: 'unavailable',
                source: 'SSI trade-tape contract',
                diagnostics: { symbolDataHealth: 'auction_waiting_for_match' },
              },
            }
          : item;
      }),
    }));
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers),
      status: 'unavailable',
      quotes: tickers.map((ticker) => ({
        ...makeRealtimeResponse([ticker]).quotes[0],
        price: 0,
        realtimePrice: 0,
        snapshotPrice: 0,
        status: 'ok',
      })),
    }));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => ({
      ...makeTradesResponse(symbol),
      status: 'unavailable',
      symbolDataHealth: 'auction_waiting_for_match',
      diagnostics: { symbolDataHealth: 'auction_waiting_for_match' },
      trades: [{
        ...makeTradesResponse(symbol).trades[0],
        price: 0,
        volume: 0,
      }],
    }));

    render(<VietnamDashboardPage />);

    const freshness = await screen.findByTestId('foreign-flow-freshness');
    expect(within(freshness).getByText('Previous completed session')).toBeInTheDocument();
    expect(within(freshness).getByText(/Data date: 2026-07-23/)).toBeInTheDocument();
    expect(screen.getByText('Waiting for auction match')).toBeInTheDocument();
    expect(screen.getByText('Waiting for auction match — no valid execution yet.')).toBeInTheDocument();
    expect(screen.queryByText('0.00')).not.toBeInTheDocument();
  });

  it('renders buffered X-TRADE rows even when trade tape diagnostics are stale', async () => {
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => {
      const response = makeTradesResponse(symbol);
      return {
      ...response,
      status: 'ok',
      reasonCode: 'buffered_rows_available',
      classification: 'buffered_rows_available',
      statusMessage: 'SSI trade tape ready.',
      trades: [
        ...response.trades,
        {
          time: '10:15:59',
          timestamp: '2026-06-11T10:15:59+07:00',
          timestampDisplay: '10:15:59',
          price: 92,
          volume: 1500,
          side: 'sell',
          sideLabel: 'Sell',
          sideIfAvailable: 'SD',
          change: 1500,
          changePct: 1.66,
          matchType: 'SD',
          rawType: 'X-TRADE',
          id: '2',
          source: 'SSI',
        },
        {
          time: '10:15:58',
          timestamp: '2026-06-11T10:15:58+07:00',
          timestampDisplay: '10:15:58',
          price: 99,
          volume: 4700,
          side: null,
          sideLabel: null,
          change: 0,
          changePct: 0,
          matchType: 'matched',
          rawType: 'X-TRADE',
          id: '3',
          source: 'SSI',
        },
      ],
      diagnostics: {
        streamingStatus: 'cache_stale',
        cacheStatus: 'stale',
        tradeTapeBufferRowCount: 50,
        tradeTapeReturnedRowCount: 3,
      },
    };
    });

    render(<VietnamDashboardPage />);

    const tradeHeading = await screen.findByRole('heading', { name: 'Trade tape' });
    const tradeCard = tradeHeading.closest('div.rounded-lg') as HTMLElement | null;
    if (!tradeCard) throw new Error('Trade tape card not found');
    const trade = within(tradeCard);

    expect(trade.getByText('10:16:00')).toBeInTheDocument();
    expect(trade.getByRole('columnheader', { name: 'Time' })).toBeInTheDocument();
    expect(trade.getByRole('columnheader', { name: 'B/S' })).toBeInTheDocument();
    expect(trade.getByRole('columnheader', { name: 'Vol' })).toBeInTheDocument();
    expect(trade.getByRole('columnheader', { name: 'Price' })).toBeInTheDocument();
    expect(trade.getByRole('columnheader', { name: '+/-' })).toBeInTheDocument();
    expect(trade.getByRole('columnheader', { name: '+/-(%)' })).toBeInTheDocument();
    const side = trade.getByText('Buy');
    expect(side).toBeInTheDocument();
    expect(side.className).toContain('text-success');
    expect(trade.getByText('Sell')).toHaveClass('text-danger');
    expect(trade.getAllByText('—').some((node) => node.className.includes('text-secondary-text'))).toBe(true);
    expect(trade.getByText('300')).toBeInTheDocument();
    const price = trade.getByText('101.70');
    expect(price).toBeInTheDocument();
    expect(price.className).toContain('text-success');
    expect(trade.getByText('0.09')).toHaveClass('text-cyan');
    expect(trade.getByText('0.10')).toHaveClass('text-reference-yellow');
    expect(trade.getByText('+2.70')).toHaveClass('text-success');
    expect(trade.getByText('+2.73')).toHaveClass('text-success');
    expect(trade.getByText('+1.50')).toHaveClass('text-success');
    expect(trade.getByText('+1.66')).toHaveClass('text-success');
    expect(trade.getAllByText('0.00').some((node) => node.className.includes('text-reference-yellow'))).toBe(true);
    expect(trade.queryByText('SSI trade tape unavailable.')).not.toBeInTheDocument();
    expect(trade.queryByText(/Loading/i)).not.toBeInTheDocument();
    expect(trade.queryByText(/Lunch break/i)).not.toBeInTheDocument();
    expect(trade.queryByText(/stale/i)).not.toBeInTheDocument();
  });

  it('renders dynamic SSI X-QUOTE order book levels with board price colors', async () => {
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => ({
      ...makeResponse(tickers?.length ? tickers : defaultTickers),
      watchlist: (tickers?.length ? tickers : defaultTickers).map((ticker) => {
        const item = makeItem(ticker);
        if (ticker !== 'FPT') return item;
        return {
          ...item,
          dailyStockPrice: {
            ...item.dailyStockPrice,
            referencePrice: 99_000,
            ceilingPrice: 106_000,
            floorPrice: 92_000,
          },
          priceLimit: {
            ...item.priceLimit,
            referencePrice: 99_000,
            ceilingPrice: 106_000,
            floorPrice: 92_000,
          },
          orderBookSource: 'SSI X-QUOTE',
          orderBookStatus: {
            status: 'ok',
            source: 'SSI X-QUOTE',
            message: 'SSI order book ready.',
          },
          orderBook: {
            ticker: 'FPT',
            symbol: 'FPT',
            source: 'SSI X-QUOTE',
            streamDataType: 'X-QUOTE',
            time: '09:41:23',
            ageSeconds: 2,
            bids: [
              { level: 1, price: 99_000, volume: 19_400 },
              { level: 2, price: 98_000, volume: 25_100 },
              { level: 4, price: 92_000, volume: 84_800 },
            ],
            asks: [
              { level: 1, price: 100_000, volume: 7_400 },
              { level: 2, price: 106_000, volume: 50_500 },
              { level: 3, price: 107_000, volume: 6_000 },
              { level: 4, price: 108_000, volume: 1_000 },
            ],
          },
          diagnostics: {
            ...item.diagnostics,
            orderBook: {
              orderBookRowsObserved: 55,
              orderBookSubscriptionStatus: 'subscribed',
            },
          },
        };
      }),
    }));

    render(<VietnamDashboardPage />);

    const heading = await screen.findByRole('heading', { name: 'Order Book — SSI X-QUOTE' });
    const card = heading.closest('section') as HTMLElement | null;
    if (!card) throw new Error('Order book card not found');
    const book = within(card);

    expect(book.getAllByText('SSI X-QUOTE').length).toBeGreaterThan(0);
    expect(book.getByRole('columnheader', { name: 'Bid Vol' })).toBeInTheDocument();
    expect(book.getByRole('columnheader', { name: 'Bid Price' })).toBeInTheDocument();
    expect(book.getByRole('columnheader', { name: 'Ask Price' })).toBeInTheDocument();
    expect(book.getByRole('columnheader', { name: 'Ask Vol' })).toBeInTheDocument();
    expect(book.getAllByRole('row')).toHaveLength(5);
    expect(book.getByText('19,400')).toBeInTheDocument();
    expect(book.getByText('7,400')).toBeInTheDocument();
    expect(book.getAllByText('99.00').some((node) => node.className.includes('text-reference-yellow'))).toBe(true);
    expect(book.getAllByText('92.00').some((node) => node.className.includes('text-cyan'))).toBe(true);
    expect(book.getAllByText('106.00').some((node) => node.className.includes('text-ceiling-purple'))).toBe(true);
    expect(book.getByText('100.00')).toHaveClass('text-success');
    expect(book.getByLabelText('Bid level 3 unavailable')).toBeInTheDocument();
    expect(book.getByText(/time 09:41:23/)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /foreign room/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /market index pulse/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /session status/i })).not.toBeInTheDocument();
    expect(selectedTickerHeader().getAllByText('0.10').length).toBeGreaterThan(0);
  });

  it('renders SSI X-QUOTE unavailable without fake order-book rows', async () => {
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => ({
      ...makeResponse(tickers?.length ? tickers : defaultTickers),
      watchlist: (tickers?.length ? tickers : defaultTickers).map((ticker) => {
        const item = makeItem(ticker);
        if (ticker !== 'FPT') return item;
        return {
          ...item,
          orderBookSource: 'SSI X-QUOTE',
          orderBook: null,
          orderBookStatus: {
            status: 'unavailable',
            source: 'SSI X-QUOTE',
            message: 'Order book unavailable.',
            reasonCode: 'stream_cache_empty',
          },
        };
      }),
    }));

    render(<VietnamDashboardPage />);

    const heading = await screen.findByRole('heading', { name: 'Order Book — SSI X-QUOTE' });
    const card = heading.closest('section') as HTMLElement | null;
    if (!card) throw new Error('Order book card not found');
    const book = within(card);

    expect(book.getByText('Order book unavailable.')).toBeInTheDocument();
    expect(book.queryByRole('columnheader', { name: 'Bid Vol' })).not.toBeInTheDocument();
    expect(book.queryByText('Bid Price')).not.toBeInTheDocument();
    expect(book.queryByText('Ask Price')).not.toBeInTheDocument();
  });

  it('renders stale SSI X-QUOTE rows distinctly when cached levels exist', async () => {
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => ({
      ...makeResponse(tickers?.length ? tickers : defaultTickers),
      watchlist: (tickers?.length ? tickers : defaultTickers).map((ticker) => {
        const item = makeItem(ticker);
        if (ticker !== 'FPT') return item;
        return {
          ...item,
          orderBookSource: 'SSI X-QUOTE',
          orderBookStatus: {
            status: 'stale',
            source: 'SSI X-QUOTE',
            message: 'X-QUOTE cache stale.',
            reasonCode: 'stale',
          },
          orderBook: {
            ticker: 'FPT',
            bids: [{ level: 1, price: 98_000, volume: 1_000 }],
            asks: [{ level: 1, price: 100_000, volume: 2_000 }],
            isStale: true,
            staleReason: 'market inactive or no recent tick',
          },
        };
      }),
    }));

    render(<VietnamDashboardPage />);

    const heading = await screen.findByRole('heading', { name: 'Order Book — SSI X-QUOTE' });
    const card = heading.closest('section') as HTMLElement | null;
    if (!card) throw new Error('Order book card not found');
    const book = within(card);

    expect(book.getByText('stale')).toBeInTheDocument();
    expect(book.getByText(/Last available order book is stale/)).toBeInTheDocument();
    expect(book.getByText('98.00')).toBeInTheDocument();
    expect(book.getByText('2,000')).toBeInTheDocument();
  });

  it('renders after-hours SSI X-QUOTE rows with market-closed last-known copy', async () => {
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => ({
      ...makeResponse(tickers?.length ? tickers : defaultTickers),
      watchlist: (tickers?.length ? tickers : defaultTickers).map((ticker) => {
        const item = makeItem(ticker);
        if (ticker !== 'FPT') return item;
        return {
          ...item,
          orderBookSource: 'SSI X-QUOTE',
          orderBookStatus: {
            status: 'stale',
            source: 'SSI X-QUOTE',
            message: 'Market closed — showing last known data.',
            reasonCode: 'after_hours_stale',
            classification: 'after_hours_stale',
          },
          orderBook: {
            ticker: 'FPT',
            bids: [{ level: 1, price: 98_000, volume: 1_000 }],
            asks: [{ level: 1, price: 100_000, volume: 2_000 }],
            isStale: true,
            staleReason: 'Market closed — showing last known data.',
          },
        };
      }),
    }));

    render(<VietnamDashboardPage />);

    const heading = await screen.findByRole('heading', { name: /Order Book.*SSI X-QUOTE/ });
    const card = heading.closest('section') as HTMLElement | null;
    if (!card) throw new Error('Order book card not found');
    const book = within(card);

    expect(book.getByText('stale')).toBeInTheDocument();
    expect(book.getByText('Last available order book is stale: Market closed — showing last known data.')).toBeInTheDocument();
    expect(book.queryByText('Order book unavailable.')).not.toBeInTheDocument();
    expect(book.getByText('98.00')).toBeInTheDocument();
  });

  it('refreshes selected ticker live context with a bounded one-ticker watchlist request', async () => {
    vi.useFakeTimers();
    let selectedRefreshCount = 0;
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => {
      const requestedTickers = tickers?.length ? tickers : defaultTickers;
      if (requestedTickers.length === 1 && requestedTickers[0] === 'FPT') {
        selectedRefreshCount += 1;
        const item = makeItem('FPT');
        return {
          ...makeResponse(['FPT']),
          watchlist: [{
            ...item,
            orderBookSource: 'SSI X-QUOTE',
            orderBookStatus: {
              status: 'ok',
              source: 'SSI X-QUOTE',
              reasonCode: 'cache_hit',
            },
            orderBook: {
              ticker: 'FPT',
              bids: [{ level: 1, price: 101_000, volume: 1_000 }],
              asks: [{ level: 1, price: 102_000, volume: 2_000 }],
              isStale: false,
            },
          }],
        };
      }
      return {
        ...makeResponse(requestedTickers),
        watchlist: requestedTickers.map((ticker) => ({
          ...makeItem(ticker),
          orderBookSource: 'SSI X-QUOTE',
          orderBook: null,
          orderBookStatus: {
            status: 'unavailable',
            source: 'SSI X-QUOTE',
            message: 'Order book unavailable.',
            reasonCode: 'stream_cache_empty',
          },
        })),
      };
    });

    render(<VietnamDashboardPage />);

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText('Order book unavailable.')).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(3_000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(selectedRefreshCount).toBe(1);
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['FPT'], false);
    expect(screen.getByText('101.00')).toBeInTheDocument();
  });

  it('pauses selected ticker live refresh while hidden and resumes immediately on focus', async () => {
    vi.useFakeTimers();
    let selectedRefreshCount = 0;
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => {
      const requestedTickers = tickers?.length ? tickers : defaultTickers;
      if (requestedTickers.length === 1 && requestedTickers[0] === 'FPT') {
        selectedRefreshCount += 1;
      }
      return makeResponse(requestedTickers);
    });

    render(<VietnamDashboardPage />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false);

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    await act(async () => {
      vi.advanceTimersByTime(6_000);
      await Promise.resolve();
    });
    expect(selectedRefreshCount).toBe(0);

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    fireEvent(document, new Event('visibilitychange'));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(selectedRefreshCount).toBe(1);
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['FPT'], false);
  });

  it('treats typed unavailable Trade Tape as terminal without startup refetch churn', async () => {
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => ({
      ...makeTradesResponse(symbol),
      status: 'unavailable',
      reasonCode: 'stream_cache_empty',
      classification: 'stream_cache_empty',
      statusMessage: 'No SSI trade rows available yet.',
      trades: [],
      diagnostics: {
        streamingStatus: 'running',
        managerState: 'running',
        tradeTapeSubscriptionStatus: 'subscribed',
        tradeTapeBufferRowCount: 0,
      },
    }));

    render(<VietnamDashboardPage />);

    const tradeHeading = await screen.findByRole('heading', { name: 'Trade tape' });
    const tradeCard = tradeHeading.closest('div.rounded-lg') as HTMLElement | null;
    if (!tradeCard) throw new Error('Trade tape card not found');
    const trade = within(tradeCard);

    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    expect(trade.getByText('SSI trade tape unavailable.')).toBeInTheDocument();
    expect(trade.queryByText('Loading SSI trade tape...')).not.toBeInTheDocument();
    expect(trade.queryByRole('table')).not.toBeInTheDocument();
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
  });

  it('renders a compact selected ticker header with distinct source labels', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    expect(header.getByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(header.getByText('FPT Listed Company')).toBeInTheDocument();
    expect(header.getByText('Daily close')).toBeInTheDocument();
    expect(screen.getAllByText('Daily OHLCV volume').length).toBeGreaterThan(0);
    expect(header.getByText('% change')).toBeInTheDocument();
    expect(header.getByText('Foreign net')).toBeInTheDocument();
    expect(header.getByText('Volume / 20D')).toBeInTheDocument();
    expect(header.getByText('RSI14 / MA state')).toBeInTheDocument();
    expect(header.getByText('Live')).toBeInTheDocument();
    expect(header.getAllByText('News disabled').length).toBeGreaterThan(0);
    expect(header.getByText('Daily source: SSI DailyOhlc')).toBeInTheDocument();
    expect(header.queryByText('Reference price')).not.toBeInTheDocument();
    expect(header.queryByText('Matched value')).not.toBeInTheDocument();
    expect(header.queryByText('Cache internals')).not.toBeInTheDocument();
    expect(header.queryByText(/HTTP status/i)).not.toBeInTheDocument();
    expect(header.queryByText('SSI unavailable')).not.toBeInTheDocument();
  });

  it('organizes selected ticker detail into progressive disclosure groups', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Price context')).toBeInTheDocument();
    expect(screen.getByText('Flow context')).toBeInTheDocument();
    expect(screen.getByText('Technical context')).toBeInTheDocument();
    expect(screen.getByText('Live context')).toBeInTheDocument();
    expect(screen.getByText('Source coverage')).toBeInTheDocument();
    expect(screen.getByText('Diagnostics')).toBeInTheDocument();

    expect(selectedDisclosure('selected-disclosure-price-context').getByText('Reference')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-price-context').getByText('Ceiling price')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-price-context').getByText('Floor price')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-flow-context').getByText('Matched value')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-flow-context').getByText('Foreign buy')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-flow-context').getByText('Foreign sell')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-technical-context').getByText('RSI14')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-live-context').getByText('SSI realtime')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-source-coverage').getByText('DailyStockPrice coverage')).toBeInTheDocument();
    expect(selectedDisclosure('selected-disclosure-news-context').getAllByText('News disabled').length).toBeGreaterThan(0);
    expect(selectedDisclosure('selected-disclosure-diagnostics').getByText((content) => content.includes('latest_price_raw_field: close'))).toBeInTheDocument();
  });

  it('sums the top foreign net volume card from SSI DailyStockPrice share volume', async () => {
    const response = makeResponse(defaultTickers);
    const sampleNetVolumes = [-2_920_457, -1_634_598, -818_100, -212_200, -2_600, -1_581_061];
    withSsiForeignNetVolumes(response, sampleNetVolumes);
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const foreignNetCard = foreignNetVolumeSummaryCard();
    expect(foreignNetCard.getByText('Foreign net volume')).toBeInTheDocument();
    expect(foreignNetCard.getByText('-7.17M')).toBeInTheDocument();
    expect(foreignNetCard.getByText('SSI DailyStockPrice · shares')).toBeInTheDocument();
  });

  it('ignores missing SSI foreign net volume values and does not fall back to legacy foreign net', async () => {
    const response = makeResponse(defaultTickers);
    const values = [null, undefined, 0, -10, null, undefined];
    withSsiForeignNetVolumes(response, values);
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const foreignNetCard = foreignNetVolumeSummaryCard();
    expect(foreignNetCard.getByText('-10')).toBeInTheDocument();
    expect(foreignNetCard.queryByText('999,999,999')).not.toBeInTheDocument();
  });

  it('renders unavailable market facts as missing instead of guessed labels or zero values', async () => {
    localStorage.setItem(customWatchlistStorageKey, JSON.stringify(['FPT']));
    const response = makeResponse(['FPT']);
    const item = response.watchlist[0];
    item.status = 'unavailable';
    item.exchange = null;
    item.marketIndex = null;
    item.changePct = null;
    item.latestPrice = null;
    item.close = null;
    item.dailyClose = null;
    item.ohlcvClose = null;
    item.liquidity = { avgVolume20D: null, score: null };
    item.ssiForeignNetVolume = null;
    item.statusLabels = [];
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['FPT'], false));

    const cardArticle = screen
      .getAllByRole('link', { name: 'Open FPT company research' })
      .map((link) => link.closest('article'))
      .find((article) => article && within(article as HTMLElement).queryByText('Data unavailable'));
    expect(cardArticle).toBeTruthy();
    const card = within(cardArticle as HTMLElement);
    expect(card.getByText('Data unavailable')).toBeInTheDocument();
    expect(card.queryByText('VNINDEX.VN')).not.toBeInTheDocument();
    expect(card.queryByText('VN')).not.toBeInTheDocument();
    expect(card.getByText('20D liquidity').nextElementSibling).toHaveTextContent('—');
    expect(foreignNetVolumeSummaryCard().getByText('-')).toBeInTheDocument();
  });

  it('keeps the previous successful aggregate when a refresh returns incomplete watchlist rows', async () => {
    const previous = withSsiForeignNetVolumes(makeResponse(defaultTickers), [10, 20, 30, 40, 50, 60]);
    const incomplete = withSsiForeignNetVolumes(makeResponse(['FPT']), [999_999]);
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(previous)
      .mockResolvedValueOnce(incomplete);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    expect(foreignNetVolumeSummaryCard().getByText('+210')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /force live refresh/i }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, true));
    expect(await screen.findByText('Last update failed')).toBeInTheDocument();
    expect(screen.getByText('Showing previous data')).toBeInTheDocument();
    expect(foreignNetVolumeSummaryCard().getByText('+210')).toBeInTheDocument();
    expect(foreignNetVolumeSummaryCard().queryByText('999,999')).not.toBeInTheDocument();
  });

  it('keeps previous rows visible while refresh is pending and preserves sorting', async () => {
    const previous = withSsiForeignNetVolumes(makeResponse(defaultTickers), [1, 2, 3, 4, 5, 6]);
    const latest = withSsiForeignNetVolumes(makeResponse(defaultTickers), [50, 50, 50, 50, 50, 50]);
    let resolveRefresh: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(previous)
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveRefresh = resolve;
      }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(foreignNetVolumeSummaryCard().getByText('+21')).toBeInTheDocument());
    clickIndicatorSort(/Sort by Ticker/i);
    expect(indicatorRowOrder()).toEqual(['ACB', 'ACV', 'FPT', 'MSB', 'SCS', 'VPB']);

    fireEvent.click(screen.getByRole('button', { name: /^refresh$/i }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText('Updating...').length).toBeGreaterThan(0);
    expect(screen.getByText('Showing previous data')).toBeInTheDocument();
    expect(foreignNetVolumeSummaryCard().getByText('+21')).toBeInTheDocument();
    expect(indicatorRowOrder()).toEqual(['ACB', 'ACV', 'FPT', 'MSB', 'SCS', 'VPB']);
    expect(dataReadinessStrip().getByRole('heading', { name: 'Data readiness' })).toBeInTheDocument();

    await act(async () => {
      resolveRefresh?.(latest);
    });

    await waitFor(() => expect(foreignNetVolumeSummaryCard().getByText('+300')).toBeInTheDocument());
    expect(screen.queryAllByText('Updating...')).toHaveLength(0);
    expect(indicatorRowOrder()).toEqual(['ACB', 'ACV', 'FPT', 'MSB', 'SCS', 'VPB']);
  });

  it('ignores an older slower watchlist response after a newer response updates the aggregate', async () => {
    const previous = withSsiForeignNetVolumes(makeResponse(defaultTickers), [1, 2, 3, 4, 5, 6]);
    const stale = withSsiForeignNetVolumes(makeResponse(defaultTickers), [-100, -100, -100, -100, -100, -100]);
    const latest = withSsiForeignNetVolumes(makeResponse(defaultTickers), [50, 50, 50, 50, 50, 50]);
    let resolveStale: ((response: VietnamWatchlistResponse) => void) | undefined;
    let resolveLatest: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(previous)
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveStale = resolve;
      }))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveLatest = resolve;
      }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(foreignNetVolumeSummaryCard().getByText('+21')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /force live refresh/i }));
    fireEvent.click(screen.getByRole('button', { name: /^refresh$/i }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(3));
    await act(async () => {
      resolveLatest?.(latest);
    });
    await waitFor(() => expect(foreignNetVolumeSummaryCard().getByText('+300')).toBeInTheDocument());

    await act(async () => {
      resolveStale?.(stale);
    });
    expect(foreignNetVolumeSummaryCard().getByText('+300')).toBeInTheDocument();
    expect(foreignNetVolumeSummaryCard().queryByText('-600')).not.toBeInTheDocument();
  });

  it('keeps the previous successful aggregate when force refresh fails', async () => {
    const previous = withSsiForeignNetVolumes(makeResponse(defaultTickers), [10, 20, 30, 40, 50, 60]);
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(previous)
      .mockRejectedValueOnce(new Error('watchlist timeout'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(foreignNetVolumeSummaryCard().getByText('+210')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /force live refresh/i }));

    expect(await screen.findByText('Last update failed')).toBeInTheDocument();
    expect(screen.getByText('Showing previous data')).toBeInTheDocument();
    expect(foreignNetVolumeSummaryCard().getByText('+210')).toBeInTheDocument();
  });

  it('keeps previous committed rows and selection when a preset request fails', async () => {
    let rejectPreset: ((error: Error) => void) | undefined;
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((_resolve, reject) => {
        rejectPreset = reject;
      }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    clickTickerRow('ACB');
    expect(selectedTickerHeader().getByRole('heading', { name: 'ACB' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    expect(screen.getAllByText('Updating...').length).toBeGreaterThan(0);
    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();

    await act(async () => {
      rejectPreset?.(new Error('preset timeout'));
    });

    expect(await screen.findByText('Last update failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();
    expect(selectedTickerHeader().getByRole('heading', { name: 'ACB' })).toBeInTheDocument();
  });

  it('keeps previous committed rows and selection when a custom apply request fails', async () => {
    let rejectCustom: ((error: Error) => void) | undefined;
    localStorage.clear();
    mockedGetVietnamWatchlist
      .mockImplementationOnce(async (tickers) => makeResponse(tickers ?? []))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((_resolve, reject) => {
        rejectCustom = reject;
      }));

    render(<VietnamDashboardPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    clickTickerRow('ACB');

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'vpb' } });
    fireEvent.click(screen.getByRole('option', { name: /VPB/ }));
    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'acb' } });
    fireEvent.click(screen.getByRole('option', { name: /ACB/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply custom watchlist' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['VPB', 'ACB'], false));
    expect(screen.getAllByText('Updating...').length).toBeGreaterThan(0);

    await act(async () => {
      rejectCustom?.(new Error('custom timeout'));
    });

    expect(await screen.findByText('Last update failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Custom' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('indicator-row-VCB')).toBeInTheDocument();
    expect(selectedTickerHeader().getByRole('heading', { name: 'ACB' })).toBeInTheDocument();
  });

  it('commits a successful preset response even when one requested ticker row is unavailable', async () => {
    const banksResponse = makeResponse([...presetTickers.Banks]);
    banksResponse.watchlist[0] = {
      ...banksResponse.watchlist[0],
      status: 'unavailable',
      error: 'Ticker temporarily unavailable',
      latestPrice: null,
      dailyClose: null,
      ohlcvClose: null,
      close: null,
    };
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockResolvedValueOnce(banksResponse);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true'));
    expect(screen.getByTestId('indicator-row-VCB')).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-VCB')).toHaveTextContent('Unavailable');
    expect(selectedTickerHeader().getByRole('heading', { name: 'VCB' })).toBeInTheDocument();
  });

  it('suppresses repeated same-preset clicks while allowing a newer preset intent', async () => {
    let resolveBanks: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveBanks = resolve;
      }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('button', { name: 'Banks' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Consumer' })).not.toBeDisabled();
    expect(screen.getByText(`Loading ${presetTickers.Banks.length} Banks rows; current rows remain visible.`)).toBeInTheDocument();
    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Consumer' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Consumer], false));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Consumer' })).toHaveAttribute('aria-pressed', 'true'));

    await act(async () => {
      resolveBanks?.(makeResponse([...presetTickers.Banks]));
    });

    expect(screen.getByRole('button', { name: 'Consumer' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('indicator-row-VNM')).toBeInTheDocument();
    expect(selectedTickerHeader().getByRole('heading', { name: 'VNM' })).toBeInTheDocument();
  });

  it('clicking an already active preset is a no-op', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true'));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('keeps previous rows visible and clears pending state when a preset request fails', async () => {
    let rejectBanks: ((error: Error) => void) | undefined;
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(makeResponse(defaultTickers))
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((_resolve, reject) => {
        rejectBanks = reject;
      }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));

    await act(async () => {
      rejectBanks?.(new Error('banks timeout'));
    });

    expect(await screen.findByText('Last update failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('indicator-row-MSB')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Consumer' })).not.toBeDisabled();
  });

  it('keeps the foreign aggregate stable when auxiliary requests fail', async () => {
    const previous = withSsiForeignNetVolumes(makeResponse(defaultTickers), [10, 20, 30, 40, 50, 60]);
    mockedGetVietnamWatchlist.mockResolvedValue(previous);
    mockedGetVietnamRealtimeQuotes.mockRejectedValue(new Error('realtime unavailable'));
    mockedGetVietnamRealtimeTrades.mockRejectedValue(new Error('trade tape unavailable'));
    mockedGetVietnamCorporateActions.mockRejectedValue(new Error('corporate actions unavailable'));
    mockedGetVietnamIndexList.mockRejectedValue(new Error('index list unavailable'));
    mockedGetVietnamDailyIndex.mockRejectedValue(new Error('daily index unavailable'));
    mockedGetVietnamIndexComponents.mockRejectedValue(new Error('index components unavailable'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(foreignNetVolumeSummaryCard().getByText('+210')).toBeInTheDocument());
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: /refresh realtime/i }));

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(2));
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(foreignNetVolumeSummaryCard().getByText('+210')).toBeInTheDocument();
  });

  it('renders selected ticker data quality summary when present', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    expect(header.getByRole('heading', { name: 'Data quality' })).toBeInTheDocument();
    expect(header.getByText('Data quality: ok')).toBeInTheDocument();
    expect(header.getByText('Canonical price source: SSI DailyOhlc')).toBeInTheDocument();
    expect(header.getByText('Daily source: SSI DailyOhlc')).toBeInTheDocument();
    expect(header.getByText('No issues detected.')).toBeInTheDocument();
    expect(header.getByText('Section checks')).toBeInTheDocument();
    expect(screen.getByText('Stock detail')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Indicator table' })).toBeInTheDocument();
  });

  it('places the indicator table above the selected ticker and diagnostics', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const indicator = screen.getByRole('heading', { name: 'Indicator table' }).closest('section') as HTMLElement;
    const selected = screen.getByText('Selected ticker').closest('section') as HTMLElement;
    const diagnostics = screen.getByRole('heading', { name: 'Data status' }).closest('section') as HTMLElement;

    expect(Boolean(indicator.compareDocumentPosition(selected) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(selected.compareDocumentPosition(diagnostics) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('renders the scan-first overview hierarchy with secondary controls collapsed', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const marketStrip = screen.getByTestId('vietnam-market-session-strip');
    const scan = screen.getByTestId('watchlist-scan-surface');
    const hero = screen.getByTestId('selected-ticker-hero');
    const chart = screen.getByTestId('inspect-chart-card');
    const live = screen.getByTestId('vietnam-live-market-summary');
    const diagnostics = screen.getByRole('heading', { name: 'Data status' }).closest('section') as HTMLElement;

    expect(marketStrip).toHaveTextContent('Latest completed');
    expect(Boolean(scan.compareDocumentPosition(hero) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(hero.compareDocumentPosition(chart) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(chart.compareDocumentPosition(live) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(live.compareDocumentPosition(diagnostics) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(screen.getByTestId('refresh-settings-disclosure')).not.toHaveAttribute('open');
    expect(screen.getByTestId('watchlist-management-disclosure')).not.toHaveAttribute('open');
    expect(screen.getByTestId('dashboard-supporting-modules')).not.toHaveAttribute('open');
    expect(screen.getByTestId('dashboard-formulas-disclosure')).not.toHaveAttribute('open');
    expect(dataStatusDiagnostics()).not.toHaveAttribute('open');
    expect(screen.getByTestId('selected-ticker-quick-facts').querySelectorAll(':scope > div')).toHaveLength(4);
  });

  it('preserves selected-ticker deep links when a scan row is selected', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    let hero = within(screen.getByTestId('selected-ticker-hero'));
    expect(hero.getByRole('link', { name: 'Open Company Research' })).toHaveAttribute('href', '/vietnam/company/FPT');
    expect(hero.getByRole('link', { name: 'Open Foreign Flow' })).toHaveAttribute('href', '/foreign-flow?mode=ticker&ticker=FPT');

    clickTickerRow('VPB');

    await waitFor(() => expect(screen.getByTestId('selected-ticker-hero')).toHaveTextContent('VPB'));
    hero = within(screen.getByTestId('selected-ticker-hero'));
    expect(hero.getByRole('link', { name: 'Open Company Research' })).toHaveAttribute('href', '/vietnam/company/VPB');
    expect(hero.getByRole('link', { name: 'Open Foreign Flow' })).toHaveAttribute('href', '/foreign-flow?mode=ticker&ticker=VPB');
  });

  it('selects a scan row with the keyboard and exposes its selected state', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const row = screen.getByTestId('indicator-row-VPB');

    fireEvent.keyDown(row, { key: 'Enter' });

    await waitFor(() => expect(row).toHaveAttribute('aria-selected', 'true'));
    expect(screen.getByTestId('selected-ticker-hero')).toHaveTextContent('VPB');
  });

  it('opens local overview disclosures without issuing new watchlist or chart requests', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    const chartCalls = mockedGetVietnamChart.mock.calls.length;

    fireEvent.click(within(screen.getByTestId('vietnam-live-market-summary')).getByRole('button', { name: 'Show live details' }));
    expect(screen.getByTestId('selected-disclosure-live-context')).toHaveAttribute('open');
    fireEvent.click(within(screen.getByTestId('indicator-filter-controls')).getByText('Filter and sort options'));
    fireEvent.click(within(screen.getByTestId('dashboard-supporting-modules')).getByText('Supporting watchlist context'));
    fireEvent.click(screen.getByTestId('dashboard-formulas-disclosure').querySelector('summary') as HTMLElement);
    fireEvent.click(dataStatusDiagnostics().querySelector('summary') as HTMLElement);

    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartCalls);
  });

  it('lets typed Trade Tape unavailable override an unresolved request without blanking daily data', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist = response.watchlist.map((item) => ({
      ...item,
      tradeTape: [],
      tradeTapeStatus: {
        status: 'unavailable',
        source: 'SSI X-TRADE',
        message: 'SSI trade tape unavailable.',
        reasonCode: 'unavailable_provider_error',
      },
      dataQualitySummary: {
        ...item.dataQualitySummary!,
        checks: {
          ...item.dataQualitySummary!.checks,
          tradeTape: 'unavailable',
        },
      },
    }));
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeTrades.mockImplementation(() => new Promise(() => undefined));

    render(<VietnamDashboardPage />);

    await screen.findByRole('heading', { name: 'Indicator table' });
    const liveSummary = screen.getByTestId('vietnam-live-market-summary');
    const tradeChannel = within(liveSummary).getByText('Trade tape').closest('div') as HTMLElement;
    expect(within(tradeChannel).getByText('unavailable')).toBeInTheDocument();
    expect(within(tradeChannel).getByText('SSI trade tape unavailable.')).toBeInTheDocument();
    expect(within(tradeChannel).queryByText('loading')).not.toBeInTheDocument();
    expect(await screen.findByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-points-count', '70');
    expect(screen.getAllByText('Daily close').length).toBeGreaterThan(0);
  });

  it('preserves ready Trade Tape rows and marks them stale when refresh returns unavailable', async () => {
    render(<VietnamDashboardPage />);

    await screen.findByText('10:16:00');
    mockedGetVietnamRealtimeTrades.mockResolvedValueOnce({
      ...makeTradesResponse('FPT'),
      status: 'unavailable',
      error: 'SSI trade tape unavailable',
      trades: [],
    });

    fireEvent.click(screen.getByRole('button', { name: /refresh realtime/i }));

    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(2));
    const liveSummary = screen.getByTestId('vietnam-live-market-summary');
    const tradeChannel = within(liveSummary).getByText('Trade tape').closest('div') as HTMLElement;
    expect(await within(tradeChannel).findByText('stale')).toBeInTheDocument();
    expect(within(tradeChannel).getByText('Showing last known trades')).toBeInTheDocument();
    expect(screen.getByText('10:16:00')).toBeInTheDocument();
  });

  it('preserves ready Trade Tape rows when refresh rejects', async () => {
    render(<VietnamDashboardPage />);

    await screen.findByText('10:16:00');
    mockedGetVietnamRealtimeTrades.mockRejectedValueOnce(new Error('provider request failed'));

    fireEvent.click(screen.getByRole('button', { name: /refresh realtime/i }));

    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(2));
    const liveSummary = screen.getByTestId('vietnam-live-market-summary');
    const tradeChannel = within(liveSummary).getByText('Trade tape').closest('div') as HTMLElement;
    expect(await within(tradeChannel).findByText('stale')).toBeInTheDocument();
    expect(screen.getByText('10:16:00')).toBeInTheDocument();
  });

  it('handles missing selected ticker data quality summary gracefully', async () => {
    const response = makeResponse(defaultTickers);
    delete (response.watchlist[0] as VietnamWatchItem & { dataQualitySummary?: unknown }).dataQualitySummary;
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    expect(header.queryByRole('heading', { name: 'Data quality' })).not.toBeInTheDocument();
    expect(header.getByText('Daily close')).toBeInTheDocument();
    expect(screen.getByText('Stock detail')).toBeInTheDocument();
  });

  it('handles normalized selected ticker live null and empty-list fields with diagnostics collapsed', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      intradayCandles: [],
      intradayPulse: null,
      realtimeSnapshot: null,
      tradeTape: [],
      intradayStatus: {
        status: 'unavailable',
        source: 'SSI IntradayOhlc',
        message: 'SSI intraday unavailable for the latest daily date.',
        diagnostics: {
          latestIntradayDate: '2026-06-12',
          dailyPriceDate: '2026-06-22',
          retryable: false,
        },
      },
      realtimeStatus: {
        status: 'unavailable',
        source: 'SSI realtime contract',
        message: 'SSI realtime unavailable.',
      },
      tradeTapeStatus: {
        status: 'unavailable',
        source: 'SSI trade-tape contract',
        message: 'SSI trade tape unavailable.',
        count: 0,
      },
      diagnostics: {
        realtime: {
          attemptedEndpoints: ['RealtimeQuote'],
          httpStatus: 404,
          retryable: false,
        },
        tradeTape: {
          attemptedEndpoints: ['TradeTape'],
          httpStatus: 404,
          retryable: false,
        },
      },
      dataQualitySummary: {
        overallStatus: 'partial',
        canonicalPriceSource: 'SSI DailyOhlc',
        issues: [
          { code: 'realtime_unavailable', severity: 'info', message: 'SSI realtime unavailable.' },
          { code: 'trade_tape_unavailable', severity: 'info', message: 'SSI trade tape unavailable.' },
        ],
        checks: {
          dailyOhlc: 'ok',
          intraday: 'unavailable',
          realtime: 'unavailable',
          tradeTape: 'unavailable',
          profile: 'ok',
          news: 'disabled',
        },
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { unavailable: true }));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => ({
      ...makeTradesResponse(symbol),
      status: 'unavailable',
      error: null,
      errorDetail: null,
      rawError: null,
      trades: [],
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    expect(header.getByText('Data quality: partial')).toBeInTheDocument();
    expect(header.getByText('Realtime: unavailable')).toBeInTheDocument();
    expect(header.getByText('Trade tape: unavailable')).toBeInTheDocument();
    expect(header.queryByText(/RealtimeQuote|TradeTape|HTTP status|attempted endpoints/i)).not.toBeInTheDocument();

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByText('SSI intraday unavailable for the latest daily date.')).toBeInTheDocument();
    expect(detail.getByText('SSI realtime unavailable. Daily SSI data is still available.')).toBeInTheDocument();
    expect(detail.getByText('SSI trade tape unavailable.')).toBeInTheDocument();
    expect(detail.queryByText('Intraday close')).not.toBeInTheDocument();
    expect(detail.queryByText('Realtime price')).not.toBeInTheDocument();
    expect(detail.queryByRole('table')).not.toBeInTheDocument();
    expect(detail.queryByText(/RealtimeQuote|TradeTape|HTTP status|attempted endpoints/i)).not.toBeInTheDocument();

    const panel = dataStatusPanel();
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText('Live status diagnostics')).toBeInTheDocument();
    expect(panel.getByText('SSI realtime status - Attempted endpoints')).toBeInTheDocument();
    expect(panel.getByText('RealtimeQuote')).toBeInTheDocument();
    expect(panel.getByText('SSI trade tape status - Attempted endpoints')).toBeInTheDocument();
    expect(panel.getByText('TradeTape')).toBeInTheDocument();
  });

  it('shows selected ticker mismatch, profile partial, and unavailable live states neutrally', async () => {
    const response = makeResponse(defaultTickers);
    (response.watchlist[0] as VietnamWatchItem & { dataQualitySummary?: unknown }).dataQualitySummary = {
      overallStatus: 'partial',
      canonicalPriceSource: 'SSI DailyOhlc',
      issues: [
        {
          code: 'daily_ohlc_vs_daily_stock_price_mismatch',
          severity: 'warning',
          message: 'SSI DailyOhlc close differs from SSI DailyStockPrice close for the same trading date.',
          fields: {
            dailyOhlcClose: 70_700,
            dailyStockPriceClose: 70_800,
            date: '2026-06-22',
          },
        },
        {
          code: 'profile_partial',
          severity: 'info',
          message: 'Profile partial. Some metadata is unavailable.',
          fields: { missingFields: ['industry'] },
        },
        {
          code: 'realtime_unavailable',
          severity: 'info',
          message: 'SSI realtime is unavailable.',
          fields: { status: 'unavailable' },
        },
        {
          code: 'trade_tape_unavailable',
          severity: 'info',
          message: 'SSI trade tape is unavailable.',
          fields: { status: 'unavailable' },
        },
      ],
      checks: {
        dailyOhlc: 'ok',
        dailyStockPrice: 'ok',
        intraday: 'unavailable',
        realtime: 'unavailable',
        tradeTape: 'unavailable',
        profile: 'partial',
        news: 'disabled',
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    expect(header.getByText('Data quality: partial')).toBeInTheDocument();
    expect(header.getByText('Daily source: SSI DailyOhlc')).toBeInTheDocument();
    expect(header.queryByText('Daily source unavailable')).not.toBeInTheDocument();
    expect(header.getByText('DailyOhlc differs from DailyStockPrice for the same date.')).toBeInTheDocument();
    expect(header.getByText('Profile partial. Some metadata is unavailable.')).toBeInTheDocument();
    expect(header.getByText('2 more data-quality issue(s) hidden.')).toBeInTheDocument();
    expect(header.getByText('Intraday: unavailable')).toBeInTheDocument();
    expect(header.getByText('Realtime: unavailable')).toBeInTheDocument();
    expect(header.getByText('Trade tape: unavailable')).toBeInTheDocument();
    expect(header.getByText('Profile: partial')).toBeInTheDocument();
  });

  it('does not show selected ticker daily source unavailable when daily close is present', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      status: 'unavailable',
      latestPrice: 70_600,
      dailyClose: 70_600,
      ohlcvClose: 70_600,
      volume: 9_260_100,
      latestPriceDate: '2026-06-22',
      latestPriceSource: 'SSI',
      dataQualitySummary: {
        overallStatus: 'partial',
        canonicalPriceSource: 'SSI DailyOhlc',
        issues: [
          {
            code: 'realtime_unavailable',
            severity: 'info',
            message: 'SSI realtime is unavailable.',
            fields: { status: 'unavailable' },
          },
        ],
        checks: {
          dailyOhlc: 'ok',
          intraday: 'unavailable',
          realtime: 'unavailable',
          tradeTape: 'unavailable',
          profile: 'partial',
          news: 'disabled',
        },
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    expect(header.getByText('Daily source: SSI DailyOhlc')).toBeInTheDocument();
    expect(header.getByText('Data quality: partial')).toBeInTheDocument();
    expect(header.getByText('Daily OHLCV: OK')).toBeInTheDocument();
    expect(header.queryByText('Daily source unavailable')).not.toBeInTheDocument();
  });

  it('does not render endpoint diagnostics in selected ticker data quality summary', async () => {
    const response = makeResponse(defaultTickers);
    (response.watchlist[0] as VietnamWatchItem & { dataQualitySummary?: unknown }).dataQualitySummary = {
      overallStatus: 'partial',
      canonicalPriceSource: 'SSI DailyOhlc',
      issues: [
        {
          code: 'provider_diagnostic_detail',
          severity: 'warning',
          message: 'attempted endpoints: RealtimeQuote; HTTP status 404; raw provider error.',
          fields: {
            endpoint: 'RealtimeQuote',
            httpStatus: 404,
            rawProviderError: 'Not found',
          },
        },
      ],
      checks: {
        dailyOhlc: 'ok',
        realtime: 'HTTP status 404 from RealtimeQuote',
        tradeTape: 'unavailable',
        profile: 'ok',
        news: 'disabled',
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    expect(header.getByText('Data quality issue detected.')).toBeInTheDocument();
    expect(header.queryByText(/RealtimeQuote|HTTP status|raw provider|attempted endpoints/i)).not.toBeInTheDocument();
  });

  it('does not use recommendation wording in selected ticker data quality summary', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    const summary = header.getByLabelText('Data Quality Summary');
    expect(summary.textContent).not.toMatch(/\b(buy|sell|hold)\b|target[- ]price|recommendation/i);
  });

  it('links watchlist ticker symbols to the company research page', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const links = await screen.findAllByRole('link', { name: 'Open FPT company research' });
    expect(links.length).toBeGreaterThan(0);
    expect(links[0]).toHaveAttribute('href', '/vietnam/company/FPT');
  });

  it('shows neutral watchlist scan states for faster table comparison', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist = response.watchlist.map((item) => {
      if (item.ticker === 'FPT') {
        return {
          ...item,
          statusLabels: ['Stronger than short-term average', 'Volume expansion', 'Foreign net positive'],
          liquidity: { ...item.liquidity, score: 82 },
        };
      }
      if (item.ticker === 'VPB') {
        return {
          ...item,
          changePct: -0.7,
          statusLabels: ['Weak short-term'],
        };
      }
      if (item.ticker === 'MSB') {
        return {
          ...item,
          statusLabels: ['Foreign data stale', 'Indicator caution', 'Price finality unknown', 'Adjusted price unknown'],
          statusDetails: [
            { label: 'Foreign data stale', severity: 'caution', reason: 'Foreign net date is missing or does not match the OHLCV date.' },
            { label: 'Indicator caution', severity: 'caution', reason: 'Indicator inputs include non-final, unknown-adjustment, or limited-history data.' },
            { label: 'Price finality unknown', severity: 'caution', reason: 'The dashboard cannot confirm whether the latest daily candle is final.' },
            { label: 'Adjusted price unknown', severity: 'caution', reason: 'The dashboard cannot confirm whether the OHLCV prices are adjusted or unadjusted.' },
          ],
          warnings: ['latest price uses OHLCV close because no reliable quote field is present'],
        };
      }
      if (item.ticker === 'SCS') {
        return {
          ...item,
          latestPrice: null,
          dailyClose: null,
          ohlcvClose: null,
          close: null,
          validation: { valid: false, tradingDate: '2026-06-10', missingFields: ['close'], errors: ['Missing daily close'] },
        };
      }
      if (item.ticker === 'ACB') {
        return item;
      }
      return {
        ...item,
        cacheStatus: { ...item.cacheStatus, ohlcvCache: 'error' },
      };
    });
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const scanSummary = within(screen.getByTestId('watchlist-scan-summary'));
    expect(scanSummary.getByRole('heading', { name: 'Watchlist scan' })).toBeInTheDocument();
    expect(scanSummary.getByText('Sector grouping unavailable')).toBeInTheDocument();
    expect(scanSummary.getByText('Strong').closest('div')).toHaveTextContent('1');
    expect(scanSummary.getByText('Neutral').closest('div')).toHaveTextContent('2');
    expect(scanSummary.getByText('Weakening').closest('div')).toHaveTextContent('1');
    expect(scanSummary.getByText('Risk elevated').closest('div')).toHaveTextContent('0');
    expect(scanSummary.getByText('Data unavailable').closest('div')).toHaveTextContent('2');
    expect(scanSummary.queryByText(/buy|sell|hold/i)).not.toBeInTheDocument();

    const indicatorTable = within(indicatorTableSection());
    expect(indicatorTable.getByRole('button', { name: /Sort by Ticker/i })).toBeInTheDocument();
    expect(indicatorTable.getByRole('button', { name: /Sort by Daily close/i })).toBeInTheDocument();
    expect(indicatorTable.getByRole('button', { name: /Sort by % change/i })).toBeInTheDocument();
    expect(indicatorTable.getByRole('button', { name: /Sort by RSI14/i })).toBeInTheDocument();
    expect(indicatorTable.getByText('MA state')).toBeInTheDocument();
    expect(indicatorTable.getByText('Support')).toBeInTheDocument();
    expect(indicatorTable.getByText('Resistance')).toBeInTheDocument();
    expect(indicatorTable.getAllByText('D1 · 60 sessions')).toHaveLength(2);
    fireEvent.mouseEnter(indicatorTable.getByLabelText('Support information').parentElement as HTMLElement);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'Recent price zones below the latest daily close, derived from swing lows in the last 60 daily sessions.',
    );
    fireEvent.mouseLeave(indicatorTable.getByLabelText('Support information').parentElement as HTMLElement);
    fireEvent.mouseEnter(indicatorTable.getByLabelText('Resistance information').parentElement as HTMLElement);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'Recent price zones above the latest daily close, derived from swing highs in the last 60 daily sessions.',
    );
    expect(indicatorTable.getByRole('button', { name: /Sort by Volume \/ 20D avg/i })).toBeInTheDocument();
    expect(indicatorTable.getByRole('button', { name: /Sort by Foreign net volume/i })).toBeInTheDocument();
    expect(indicatorTable.getByRole('button', { name: /Sort by Data quality/i })).toBeInTheDocument();
    expect(indicatorTable.getByText('Realtime / live status')).toBeInTheDocument();
    expect(indicatorTable.getByTestId('indicator-row-FPT')).toHaveTextContent('OK');
    expect(indicatorTable.getByTestId('indicator-row-FPT')).toHaveTextContent('Above MA20');
    expect(indicatorTable.getByTestId('indicator-row-SCS')).toHaveTextContent('Unavailable');
  });

  it('renders compact DailyOhlc-derived zones and keeps unavailable zones explicit', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[1] = {
      ...response.watchlist[1],
      indicators: {
        ...response.watchlist[1].indicators,
        shortTermZones: {
          status: 'unavailable',
          reasonCode: 'insufficient_daily_history',
          source: 'derived from SSI DailyOhlc',
          timeframe: 'D1',
          lookbackSessions: 60,
          support: [],
          resistance: [],
        },
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    const fptRow = await screen.findByTestId('indicator-row-FPT');
    expect(within(fptRow).getByText('S1')).toBeInTheDocument();
    expect(within(fptRow).getByText('R1')).toBeInTheDocument();
    expect(fptRow).toHaveTextContent('70.80–71.30');
    expect(fptRow).toHaveTextContent('73.50–74.10');

    const vpbRow = screen.getByTestId('indicator-row-VPB');
    expect(within(vpbRow).getByLabelText('VPB support unavailable')).toHaveTextContent('—');
    expect(within(vpbRow).getByLabelText('VPB resistance unavailable')).toHaveTextContent('—');
  });

  it('renders local scan filter controls and row count', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const filters = indicatorFilters();
    expect(filters.getByLabelText('Search ticker')).toBeInTheDocument();
    expect(filters.getByLabelText('Data quality')).toBeInTheDocument();
    expect(filters.getByLabelText('Live status')).toBeInTheDocument();
    expect(filters.getByLabelText('Foreign net')).toBeInTheDocument();
    expect(filters.getByLabelText('Volume / 20D')).toBeInTheDocument();
    expect(filters.getByLabelText('RSI14')).toBeInTheDocument();
    expect(filters.getByRole('button', { name: 'Reset filters' })).toBeInTheDocument();
    expect(within(indicatorTableSection()).getByText('Showing 6 of 6 rows')).toBeInTheDocument();
  });

  it('ticker search filters rows case-insensitively without calling the watchlist endpoint', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.change(indicatorFilters().getByLabelText('Search ticker'), { target: { value: 'ac' } });

    expect(indicatorRowOrder()).toEqual(['ACV', 'ACB']);
    expect(within(indicatorTableSection()).getByText('Showing 2 of 6 rows')).toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('exposes missing-cell and partial data-quality reasons in the watchlist table', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      status: 'partial',
      indicators: {
        ...response.watchlist[0].indicators,
        ma20: null,
        rsi14: null,
        rsi14Wilder: null,
        volumeRatio: null,
      },
      dailyStockPrice: {
        ...response.watchlist[0].dailyStockPrice,
        status: 'unavailable',
        foreignNetVolume: null,
      },
      ssiForeignNetVolume: null,
      dataQualitySummary: {
        ...response.watchlist[0].dataQualitySummary,
        overallStatus: 'partial',
        issues: [
          {
            code: 'rsi_missing',
            severity: 'info',
            message: 'RSI14 requires at least 15 close prices.',
            fields: { rowsLoaded: 10, requiredMinRows: 15 },
          },
          {
            code: 'ma_state_insufficient_data',
            severity: 'info',
            message: 'MA state requires a daily close and at least 20 close prices.',
            fields: { rowsLoaded: 10, requiredMinRows: 20 },
          },
          {
            code: 'daily_stock_price_missing',
            severity: 'info',
            message: 'SSI DailyStockPrice enrichment is unavailable.',
            fields: {},
          },
        ],
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    const row = await screen.findByTestId('indicator-row-FPT');
    expect(within(row).getByLabelText('RSI14 requires at least 15 close prices.')).toBeInTheDocument();
    expect(within(row).getByLabelText('Foreign-flow value unavailable from SSI DailyStockPrice.')).toBeInTheDocument();
    expect(within(row).getByLabelText(/MA state: Insufficient data/)).toHaveAttribute(
      'title',
      'MA state requires a daily close and at least 20 close prices.',
    );
    expect(within(row).getByLabelText(/Data quality: Partial/)).toHaveAttribute(
      'title',
      expect.stringContaining('RSI14 requires at least 15 close prices.'),
    );
  });

  it('distinguishes realtime not bootstrapped in the watchlist table', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      realtimeStatus: {
        status: 'unavailable',
        source: 'SSI realtime contract',
        message: 'SSI realtime cache miss.',
        reasonCode: 'ticker_not_bootstrapped',
        classification: 'ticker_not_bootstrapped',
      },
      dataQualitySummary: {
        ...response.watchlist[0].dataQualitySummary,
        checks: {
          ...response.watchlist[0].dataQualitySummary?.checks,
          realtime: 'unavailable',
        },
        issues: [
          {
            code: 'realtime_ticker_not_bootstrapped',
            severity: 'info',
            message: 'SSI realtime cache miss.',
            fields: {},
          },
        ],
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { unavailable: true }));

    render(<VietnamDashboardPage />);

    const row = await screen.findByTestId('indicator-row-FPT');
    expect(within(row).getByLabelText(/Realtime status: Not bootstrapped/)).toHaveAttribute(
      'title',
      expect.stringContaining('SSI realtime cache miss.'),
    );
  });

  it('filters rows by data quality and live status', async () => {
    mockedGetVietnamWatchlist.mockResolvedValue(makeFilterResponse());
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeMixedRealtimeResponse(tickers));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    changeIndicatorFilter('Data quality', 'partial');
    expect(indicatorRowOrder()).toEqual(['VPB', 'ACV']);

    changeIndicatorFilter('Data quality', 'all');
    changeIndicatorFilter('Live status', 'unavailable');
    expect(indicatorRowOrder()).toEqual(['VPB', 'SCS']);

    changeIndicatorFilter('Live status', 'disabled');
    expect(indicatorRowOrder()).toEqual(['MSB']);
  });

  it('filters rows by foreign net volume, volume ratio, and RSI ranges', async () => {
    mockedGetVietnamWatchlist.mockResolvedValue(makeFilterResponse());

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    changeIndicatorFilter('Foreign net', 'positive');
    expect(indicatorRowOrder()).toEqual(['FPT', 'ACV']);

    changeIndicatorFilter('Foreign net', 'negative');
    expect(indicatorRowOrder()).toEqual(['VPB', 'SCS']);

    changeIndicatorFilter('Foreign net', 'zero-missing');
    expect(indicatorRowOrder()).toEqual(['MSB', 'ACB']);

    changeIndicatorFilter('Foreign net', 'all');
    changeIndicatorFilter('Volume / 20D', 'elevated');
    expect(indicatorRowOrder()).toEqual(['VPB', 'SCS']);

    changeIndicatorFilter('Volume / 20D', 'normal');
    expect(indicatorRowOrder()).toEqual(['FPT', 'ACV']);

    changeIndicatorFilter('Volume / 20D', 'missing');
    expect(indicatorRowOrder()).toEqual(['MSB', 'ACB']);

    changeIndicatorFilter('Volume / 20D', 'all');
    changeIndicatorFilter('RSI14', 'lt30');
    expect(indicatorRowOrder()).toEqual(['VPB']);

    changeIndicatorFilter('RSI14', '30-70');
    expect(indicatorRowOrder()).toEqual(['FPT', 'ACV', 'ACB']);

    changeIndicatorFilter('RSI14', 'gt70');
    expect(indicatorRowOrder()).toEqual(['SCS']);

    changeIndicatorFilter('RSI14', 'missing');
    expect(indicatorRowOrder()).toEqual(['MSB']);
  });

  it('combines filters with AND logic and sorts filtered rows only', async () => {
    mockedGetVietnamWatchlist.mockResolvedValue(makeFilterResponse());

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    changeIndicatorFilter('Foreign net', 'negative');
    changeIndicatorFilter('Volume / 20D', 'elevated');
    expect(indicatorRowOrder()).toEqual(['VPB', 'SCS']);

    clickIndicatorSort(/Sort by RSI14/i);
    expect(indicatorRowOrder()).toEqual(['VPB', 'SCS']);

    clickIndicatorSort(/Sort by RSI14 asc/i);
    expect(indicatorRowOrder()).toEqual(['SCS', 'VPB']);
  });

  it('reset filters restores rows without clearing preset, active watchlist, custom picker, selected ticker, or calling the API', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith([...presetTickers.Banks], false));
    clickTickerRow('ACB');
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'fpt' } });
    fireEvent.click(screen.getByRole('option', { name: /FPT/ }));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    fireEvent.change(indicatorFilters().getByLabelText('Search ticker'), { target: { value: 'VCB' } });
    expect(indicatorRowOrder()).toEqual(['VCB']);

    fireEvent.click(indicatorFilters().getByRole('button', { name: 'Reset filters' }));

    expect(indicatorRowOrder()).toEqual([...presetTickers.Banks]);
    expect(screen.getByRole('button', { name: 'Banks' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Remove FPT' })).toBeInTheDocument();
    expect(selectedTickerHeader().getByRole('heading', { name: 'ACB' })).toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('shows an empty filtered state with reset action distinct from daily load failure', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    fireEvent.change(indicatorFilters().getByLabelText('Search ticker'), { target: { value: 'ZZZ' } });

    expect(screen.getByTestId('indicator-empty-filter-state')).toHaveTextContent('No rows match current filters.');
    expect(screen.queryByTestId('indicator-daily-unavailable-state')).not.toBeInTheDocument();

    fireEvent.click(within(screen.getByTestId('indicator-empty-filter-state')).getByRole('button', { name: 'Reset filters' }));
    expect(indicatorRowOrder()).toEqual(defaultTickers);
  });

  it('keeps selected ticker visible in the summary when filters hide its row', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    clickTickerRow('ACB');

    fireEvent.change(indicatorFilters().getByLabelText('Search ticker'), { target: { value: 'FPT' } });

    expect(indicatorRowOrder()).toEqual(['FPT']);
    expect(screen.getByText('Selected ticker is hidden by filters.')).toBeInTheDocument();
    expect(selectedTickerHeader().getByRole('heading', { name: 'ACB' })).toBeInTheDocument();
  });

  it('clicking a visible filtered row still updates the selected ticker', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    fireEvent.change(indicatorFilters().getByLabelText('Search ticker'), { target: { value: 'AC' } });
    clickTickerRow('ACB');

    expect(selectedTickerHeader().getByRole('heading', { name: 'ACB' })).toBeInTheDocument();
  });

  it('keeps active filters across refresh and applies them to refreshed rows', async () => {
    const previous = makeFilterResponse();
    const latest = makeFilterResponse();
    latest.watchlist = latest.watchlist.map((item) => ({
      ...item,
      dataQualitySummary: {
        ...item.dataQualitySummary,
        overallStatus: item.ticker === 'SCS' ? 'partial' : 'ok',
      },
      status: item.ticker === 'SCS' ? 'partial' : 'ok',
    }));
    let resolveRefresh: ((response: VietnamWatchlistResponse) => void) | undefined;
    mockedGetVietnamWatchlist
      .mockResolvedValueOnce(previous)
      .mockImplementationOnce(() => new Promise<VietnamWatchlistResponse>((resolve) => {
        resolveRefresh = resolve;
      }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    changeIndicatorFilter('Data quality', 'partial');
    expect(indicatorRowOrder()).toEqual(['VPB', 'ACV']);

    fireEvent.click(screen.getByRole('button', { name: /^refresh$/i }));
    await waitFor(() => expect(screen.getAllByText('Updating...').length).toBeGreaterThan(0));
    expect(indicatorRowOrder()).toEqual(['VPB', 'ACV']);

    await act(async () => {
      resolveRefresh?.(latest);
    });

    await waitFor(() => expect(screen.queryAllByText('Updating...')).toHaveLength(0));
    expect(indicatorRowOrder()).toEqual(['SCS']);
  });

  it('sorts the indicator table by ticker without reloading or changing selection', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    clickIndicatorSort(/Sort by Ticker/i);

    expect(indicatorRowOrder()).toEqual(['ACB', 'ACV', 'FPT', 'MSB', 'SCS', 'VPB']);
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(selectedTickerHeader().getByRole('heading', { name: 'FPT' })).toBeInTheDocument();

    clickIndicatorSort(/Sort by Ticker asc/i);

    expect(indicatorRowOrder()).toEqual(['VPB', 'SCS', 'MSB', 'FPT', 'ACV', 'ACB']);
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(selectedTickerHeader().getByRole('heading', { name: 'FPT' })).toBeInTheDocument();
  });

  it('sorts the indicator table by daily close with null values last', async () => {
    const response = makeResponse(defaultTickers);
    const prices: Record<string, number | null> = { FPT: 100, VPB: null, MSB: 50, SCS: 200, ACV: 75, ACB: null };
    response.watchlist = response.watchlist.map((item) => ({
      ...item,
      latestPrice: prices[item.ticker],
      dailyClose: prices[item.ticker],
      ohlcvClose: prices[item.ticker],
      close: prices[item.ticker],
      validation: prices[item.ticker] === null
        ? { valid: false, tradingDate: item.validation.tradingDate, missingFields: ['close'], errors: ['Missing daily close'] }
        : item.validation,
    }));
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    clickIndicatorSort(/Sort by Daily close/i);

    expect(indicatorRowOrder()).toEqual(['MSB', 'ACV', 'FPT', 'SCS', 'VPB', 'ACB']);

    clickIndicatorSort(/Sort by Daily close asc/i);

    expect(indicatorRowOrder()).toEqual(['SCS', 'FPT', 'ACV', 'MSB', 'VPB', 'ACB']);
  });

  it('sorts the indicator table by RSI14', async () => {
    const response = makeResponse(defaultTickers);
    const rsiValues: Record<string, number> = { FPT: 55, VPB: 25, MSB: 70, SCS: 45, ACV: 10, ACB: 60 };
    response.watchlist = response.watchlist.map((item) => ({
      ...item,
      indicators: { ...item.indicators, rsi14: rsiValues[item.ticker], rsi14Wilder: rsiValues[item.ticker] },
    }));
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    clickIndicatorSort(/Sort by RSI14/i);

    expect(indicatorRowOrder()).toEqual(['ACV', 'VPB', 'SCS', 'FPT', 'ACB', 'MSB']);
  });

  it('sorts the indicator table by foreign net volume', async () => {
    const response = makeResponse(defaultTickers);
    const foreignNet: Record<string, number | null> = { FPT: -5, VPB: 20, MSB: 0, SCS: -100, ACV: 15, ACB: null };
    response.watchlist = response.watchlist.map((item) => ({
      ...item,
      ssiForeignNetVolume: foreignNet[item.ticker],
      dailyStockPrice: { ...item.dailyStockPrice, foreignNetVolume: foreignNet[item.ticker] },
    }));
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    clickIndicatorSort(/Sort by Foreign net volume/i);

    expect(indicatorRowOrder()).toEqual(['SCS', 'FPT', 'MSB', 'ACV', 'VPB', 'ACB']);
  });

  it('sorts the indicator table by data quality', async () => {
    const response = makeResponse(defaultTickers);
    const quality: Record<string, 'ok' | 'partial' | 'unavailable'> = {
      FPT: 'partial',
      VPB: 'ok',
      MSB: 'unavailable',
      SCS: 'partial',
      ACV: 'ok',
      ACB: 'unavailable',
    };
    response.watchlist = response.watchlist.map((item) => ({
      ...item,
      dataQualitySummary: { ...item.dataQualitySummary, overallStatus: quality[item.ticker] },
    }));
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    clickIndicatorSort(/Sort by Data quality/i);

    expect(indicatorRowOrder()).toEqual(['VPB', 'ACV', 'FPT', 'SCS', 'MSB', 'ACB']);
  });

  it('selected ticker row click still updates selected ticker after table polish', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    clickTickerRow('ACB');

    expect(selectedTickerHeader().getByRole('heading', { name: 'ACB' })).toBeInTheDocument();
  });

  it('does not mark rows unavailable for missing optional quote metadata or corporate action fields', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      name: null,
      companyName: null,
      securityType: null,
      issuer: null,
      lotSize: null,
      listedShares: null,
      listedDate: null,
      symbolMetadata: {
        status: 'ok',
        symbol: 'FPT',
        exchange: 'HOSE',
        market: 'HOSE',
        source: 'SSI',
      },
      quotePriceDate: null,
      quotePriceRawField: null,
      finalCloseStatus: 'unknown',
      adjustedPriceStatus: 'unknown',
      corporateAction: { status: 'unavailable', type: 'unknown' },
      indicators: {
        ...response.watchlist[0].indicators,
        foreignNet5D: null,
        foreignNet20D: null,
        foreignNet5dLatestAvailable: null,
        foreignNet20dLatestAvailable: null,
      },
      cacheStatus: {
        ...response.watchlist[0].cacheStatus,
        ohlcvCache: 'hit',
        quoteCache: 'error',
        intradayCache: 'error',
        newsCache: 'error',
      },
      validation: {
        valid: false,
        tradingDate: '2026-06-10',
        missingFields: ['foreign_net'],
        errors: [],
      },
      warnings: [
        'Quote does not provide a reliable latest price field; latest price uses SSI DailyOhlc close.',
        'Final close status is unknown; daily candle may still be in progress.',
        'Adjusted/unadjusted price status is unknown.',
        'Intraday candle data is not a realtime matched quote.',
      ],
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const indicatorTable = within(screen.getByRole('heading', { name: 'Indicator table' }).closest('section') as HTMLElement);
    expect(indicatorTable.getByTestId('indicator-row-FPT')).not.toHaveTextContent('Unavailable');
    expect(indicatorTable.getByTestId('indicator-row-FPT')).toHaveTextContent('OK');
    expect(indicatorTable.queryByText('Data source error')).not.toBeInTheDocument();
  });

  it('renders news source with relative time', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      news: [
        {
          title: 'FPT reports cloud revenue growth',
          url: 'https://example.com/fpt-cloud',
          source: 'CafeF',
          publishedAt: '',
          publishedDate: new Date(Date.now() - 125 * 60 * 1000).toISOString(),
          summary: 'Cloud revenue increased in the latest update.',
        },
      ],
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    expect((await screen.findAllByText('FPT reports cloud revenue growth')).length).toBeGreaterThan(0);
    expect(screen.getByText('CafeF · 2 hours ago')).toBeInTheDocument();
    expect(screen.queryByText('Time unavailable')).not.toBeInTheDocument();
  });

  it('renders SSI index coverage without preloading VN30 components', async () => {
    mockedGetVietnamIndexList.mockResolvedValue(makeIndexListResponse({
      rows: [
        { indexId: 'VN30', indexCode: 'VN30', indexName: 'VN30 Index', exchange: 'HOSE', market: 'HOSE', source: 'SSI' },
        { indexId: 'VNINDEX', indexCode: 'VNINDEX', indexName: 'VN Index', exchange: 'HOSE', market: 'HOSE', source: 'SSI' },
        { indexId: 'HNX30', indexCode: 'HNX30', indexName: 'HNX30 Index', exchange: 'HNX', market: 'HNX', source: 'SSI' },
      ],
      count: 3,
    }));

    render(<VietnamDashboardPage />);

    expect(await screen.findByText('SSI index coverage')).toBeInTheDocument();
    expect(mockedGetVietnamIndexList).toHaveBeenCalledWith('HOSE');
    expect(mockedGetVietnamDailyIndex).toHaveBeenCalledWith(['VNINDEX', 'VN30']);
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    expect(screen.getByText('IndexList source/status/count')).toBeInTheDocument();
    expect(screen.getByText('DailyIndex source/status/count')).toBeInTheDocument();
    expect(screen.getByText('VN30 components source/status/count')).toBeInTheDocument();
    expect(screen.getAllByText('VN30').length).toBeGreaterThan(0);
    expect(screen.getAllByText('VNINDEX').length).toBeGreaterThan(0);
    expect(screen.getByText('HNX30')).toBeInTheDocument();
    expect(screen.getByText('VN30 components are loaded only after choosing the VN30 preset.')).toBeInTheDocument();
    expect(screen.getByText('VN30 components load after choosing the VN30 preset.')).toBeInTheDocument();

    const indicatorTable = within(screen.getByRole('heading', { name: 'Indicator table' }).closest('section') as HTMLElement);
    expect(indicatorTable.getByTestId('indicator-row-FPT')).not.toHaveTextContent('Unavailable');
  });

  it('renders real SSI DailyIndex context without blending ticker price sources', async () => {
    render(<VietnamDashboardPage />);

    const context = within(await screen.findByTestId('index-context'));
    expect(context.getByRole('heading', { name: 'Market index context' })).toBeInTheDocument();
    expect(context.getByRole('heading', { name: 'VNINDEX' })).toBeInTheDocument();
    expect(context.getByRole('heading', { name: 'VN30' })).toBeInTheDocument();
    expect(context.getAllByText('SSI DailyIndex')).toHaveLength(2);
    expect(context.getAllByText('matched')).toHaveLength(2);
    expect(context.getByText('1,326')).toBeInTheDocument();
    expect(context.getByText('Change +5.25')).toBeInTheDocument();
    expect(context.getByText('+0.4%')).toBeInTheDocument();
    expect(context.getByText('Breadth: advancing 210 · declining 175 · unchanged 60')).toBeInTheDocument();
    expect(context.getByText(/Ticker daily prices remain sourced from SSI DailyOhlc/)).toBeInTheDocument();
    expect(selectedTickerHeader().getByText('Daily source: SSI DailyOhlc')).toBeInTheDocument();
  });

  it('keeps watchlist, selected ticker, and chart when SSI index data is unavailable', async () => {
    mockedGetVietnamDailyIndex.mockResolvedValue(makeDailyIndexResponse({
      status: 'unavailable',
      reason: 'SSI daily index unavailable.',
      latestDate: null,
      rows: [],
      count: 0,
    }));

    render(<VietnamDashboardPage />);

    const context = within(await screen.findByTestId('index-context'));
    expect(context.getByText('SSI daily index unavailable.')).toBeInTheDocument();
    expect(context.getByText('VN30 components load after choosing the VN30 preset.')).toBeInTheDocument();
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    expect(screen.getByTestId('indicator-row-FPT')).toBeInTheDocument();
    expect(selectedTickerHeader().getByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(await screen.findByTestId('inspect-chart-card')).toBeInTheDocument();
    expect(context.queryByText('FPT')).not.toBeInTheDocument();
    expect(context.queryByText('ACB')).not.toBeInTheDocument();
  });

  it('shows VN30 component count only when SSI returns real component rows', async () => {
    mockedGetVietnamIndexComponents.mockResolvedValue(makeIndexComponentsResponse({
      status: 'ok',
      source: 'SSI IndexComponents',
      rows: [
        { indexCode: 'VN30', symbol: 'FPT', source: 'SSI IndexComponents' },
        { indexCode: 'VN30', symbol: 'ACB', source: 'SSI IndexComponents' },
      ],
      count: 2,
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'VN30' })).not.toBeDisabled());
    expect(mockedGetVietnamIndexComponents).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'VN30' }));

    const context = within(await screen.findByTestId('index-context'));
    expect(context.getByText('2 VN30 component rows returned by SSI IndexComponents.')).toBeInTheDocument();
    expect(context.queryByText('SSI index components unavailable.')).not.toBeInTheDocument();
    expect(context.queryByText('FPT')).not.toBeInTheDocument();
    expect(context.queryByText('ACB')).not.toBeInTheDocument();
  });

  it('keeps selected ticker news visible when quote and metadata are limited', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      name: null,
      companyName: null,
      securityType: null,
      issuer: null,
      lotSize: null,
      listedShares: null,
      listedDate: null,
      quotePriceDate: null,
      quotePriceRawField: null,
      symbolMetadata: {
        status: 'ok',
        symbol: 'FPT',
        exchange: 'HOSE',
        market: 'HOSE',
        source: 'SSI',
      },
      news: [
        {
          title: 'FPT expands data center capacity',
          url: 'https://example.com/fpt-data-center',
          source: 'News provider',
          publishedDate: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
          summary: 'Company update from the news provider.',
        },
      ],
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    expect((await screen.findAllByText('FPT expands data center capacity')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('News provider').length).toBeGreaterThan(0);
    const indicatorTable = within(screen.getByRole('heading', { name: 'Indicator table' }).closest('section') as HTMLElement);
    expect(indicatorTable.getByTestId('indicator-row-FPT')).not.toHaveTextContent('Unavailable');
  });

  it('renders disabled news placeholder without provider error text', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      news: [],
      newsStatus: { status: 'disabled', source: null, message: 'News provider disabled.' },
      quotePriceDate: null,
      symbolMetadata: {
        status: 'ok',
        symbol: 'FPT',
        exchange: 'HOSE',
        market: 'HOSE',
        source: 'SSI',
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    expect((await screen.findAllByText('News disabled')).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Mozyfin.*error/i)).not.toBeInTheDocument();
  });

  it('renders blocked experimental news as unavailable without articles', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      news: [],
      newsStatus: {
        status: 'unavailable',
        source: 'Vnstock News',
        provider: 'vnstock_news',
        reasonCode: 'blocked_pending_terms',
        message: 'Vnstock News is unavailable pending written commercial and source-owner terms.',
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    expect((await screen.findAllByText('News unavailable')).length).toBeGreaterThan(0);
    expect(screen.getByText('Vnstock News is unavailable pending written commercial and source-owner terms.')).toBeInTheDocument();
    expect(screen.queryByText('Untitled news')).not.toBeInTheDocument();
  });

  it('renders neutral SSI intraday unavailable state without Mozyfin text', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      intradaySource: 'SSI',
      intradayWarning: 'SSI intraday unavailable.',
      intradayCandles: [],
      intradayPulse: null,
      intradayStatus: { status: 'unavailable', source: 'SSI', message: 'SSI intraday unavailable.' },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    expect((await screen.findAllByText('SSI intraday unavailable.')).length).toBeGreaterThan(0);
    expect(screen.getByText('SSI intraday is unavailable or disabled; SSI realtime board and trade tape context remain separate.')).toBeInTheDocument();
    expect(screen.queryByText(/Mozyfin/i)).not.toBeInTheDocument();
  });

  it('renders stale SSI intraday date mismatch as unavailable without 1H wording', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      latestPriceDate: '2026-06-19',
      priceDate: '2026-06-19',
      intradaySource: 'SSI',
      intradayGranularity: '1m',
      intradayGranularityLabel: '1m',
      intradayActualGranularity: '1m',
      intradayActualGranularitySeconds: 60,
      intradayCadenceStatus: 'different_from_requested',
      intradayLatestDate: '2026-06-12',
      dailyPriceDate: '2026-06-19',
      dateMatch: 'mismatched',
      intradayWarning: 'SSI IntradayOhlc latest candle date does not match latest daily trading date.',
      intradayCandles: [],
      intradayPulse: null,
      intradayLabels: ['Intraday data limited'],
      intradayStatus: {
        status: 'unavailable',
        source: 'SSI',
        message: 'SSI IntradayOhlc latest candle date does not match latest daily trading date.',
        diagnostics: {
          intradayLatestDate: '2026-06-12',
          dailyPriceDate: '2026-06-19',
          dateMatch: 'mismatched',
          intradayCadenceStatus: 'different_from_requested',
        },
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    expect((await screen.findAllByText('SSI IntradayOhlc latest candle date does not match latest daily trading date.')).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Returned cadence differs from requested 1h: 1m/).length).toBeGreaterThan(0);
    expect(screen.queryByText('1H intraday')).not.toBeInTheDocument();
    expect(screen.queryByText('2026-06-12 / 2026-06-19')).not.toBeInTheDocument();
    expect(screen.queryByText('Intraday pulse (1m)')).not.toBeInTheDocument();
    expect(screen.queryByText(/1H close|Latest 1H|Session 1H/)).not.toBeInTheDocument();
  });

  it('shows SSI DailyStockPrice fields and corporate-action calendar unavailable state', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));
    await waitFor(() => expect(mockedGetVietnamCorporateActions).toHaveBeenCalledWith(['FPT'], 6));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByRole('heading', { name: 'DailyStockPrice coverage' })).toBeInTheDocument();
    expect(detail.getByText('Reference')).toBeInTheDocument();
    expect(detail.getByTestId('selected-reference-price')).toHaveClass('text-reference-yellow');
    expect(detail.getByTestId('selected-reference-price')).toHaveTextContent('0.10');
    expect(detail.getByText('Ceiling price')).toBeInTheDocument();
    expect(detail.getByTestId('selected-ceiling-price')).toHaveClass('text-ceiling-purple');
    expect(detail.getByTestId('selected-ceiling-price')).toHaveTextContent('0.11');
    expect(detail.getByText('Floor price')).toBeInTheDocument();
    expect(detail.getByTestId('selected-floor-price')).toHaveClass('text-cyan');
    expect(detail.getByTestId('selected-floor-price')).toHaveTextContent('0.09');
    expect(detail.getByText('Foreign net')).toBeInTheDocument();
    expect(within(detail.getByText('Foreign net').closest('div') as HTMLElement).getByText('+5')).toBeInTheDocument();
    expect(detail.getByText('Foreign net value')).toBeInTheDocument();
    expect(detail.getByText('+200K')).toBeInTheDocument();
    expect(detail.getByText('Matched value')).toBeInTheDocument();
    expect(detail.getByText('123.5B')).toBeInTheDocument();
    expect(detail.getByText('Put-through value')).toBeInTheDocument();
    expect(detail.getByText('25.0M')).toBeInTheDocument();
    expect(detail.getByText('Adjusted close')).toBeInTheDocument();
    expect(detail.getAllByText('0.10').length).toBeGreaterThan(0);
    expect(detail.getByText('Vs reference')).toBeInTheDocument();
    expect(detail.getByTestId('selected-price-vs-reference')).toHaveClass('text-success');
    expect(detail.getByTestId('selected-price-vs-reference')).toHaveTextContent('+1.01%');
    expect(detail.getByText('10D avg volume')).toBeInTheDocument();
    expect(within(detail.getByText('10D avg volume').closest('div') as HTMLElement).getByText('1.1K')).toBeInTheDocument();
    expect(detail.getByText('3M avg volume')).toBeInTheDocument();
    expect(within(detail.getByText('3M avg volume').closest('div') as HTMLElement).getByText('1.05K')).toBeInTheDocument();
    expect(detail.getByText('52W high / low')).toBeInTheDocument();
    expect(within(detail.getByText('52W high / low').closest('div') as HTMLElement).getByText('130.00 / 80.00')).toBeInTheDocument();
    expect(detail.getByText('Daily range')).toBeInTheDocument();
    expect(within(detail.getByText('Daily range').closest('div') as HTMLElement).getByText('3%')).toBeInTheDocument();
    expect(detail.getByTestId('selected-daily-range')).toHaveClass('text-foreground');
    expect(detail.getByTestId('selected-ma-values')).toHaveClass('text-foreground');
    expect(detail.getByTestId('selected-bollinger-values')).toHaveClass('text-foreground');
    expect(detail.getByTestId('selected-52w-high-low')).toHaveClass('text-foreground');
    expect(detail.getByText('Adjusted close is shown only when SSI provides it. Corporate actions are not inferred from reference or adjusted prices.')).toBeInTheDocument();
    expect(detail.getByText('Foreign net 5D')).toBeInTheDocument();
    expect(detail.getByText('Foreign net 20D')).toBeInTheDocument();
    expect(within(detail.getByText('Foreign net 5D').closest('div') as HTMLElement).getByText('+15')).toBeInTheDocument();
    expect(within(detail.getByText('Foreign net 20D').closest('div') as HTMLElement).getByText('+30')).toBeInTheDocument();
    expect(detail.queryByText('Need 5 foreign rows')).not.toBeInTheDocument();
    expect(detail.queryByText('Need 20 foreign rows')).not.toBeInTheDocument();
    expect(detail.getByRole('heading', { name: 'Corporate actions' })).toBeInTheDocument();
    expect(detail.getByText('Recent and upcoming events')).toBeInTheDocument();
    expect(detail.getByText('Corporate action history/calendar unavailable.')).toBeInTheDocument();
    expect(detail.getByText('No verified Vietnam corporate-action event provider is configured.')).toBeInTheDocument();
    expect(detail.getByText('Daily close')).toBeInTheDocument();
    expect(detail.getAllByText('0.10 / 0.10').length).toBeGreaterThan(0);
  });

  it('shows source-aware unavailable copy for null SSI-derived metrics', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      dailyStockPrice: {
        ...response.watchlist[0].dailyStockPrice,
        referencePrice: null,
      },
      indicators: {
        ...response.watchlist[0].indicators,
        high52w: null,
        low52w: null,
        highLow52wHistoryCount: 9,
        highLow52wCoverageStatus: 'insufficient',
        avgVolume10d: null,
        avgVolume10dHistoryCount: 9,
        avgVolume10dCoverageStatus: 'insufficient',
        avgVolume3m: null,
        avgVolume3mHistoryCount: 9,
        avgVolume3mCoverageStatus: 'insufficient',
        priceVsReferencePct: null,
        priceVsReferenceStatus: 'reference_unavailable',
        dailyRangePct: null,
        dailyRangeStatus: 'insufficient',
        ssiDerivedMetricsStatus: 'insufficient',
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(within(detail.getByText('Vs reference').closest('div') as HTMLElement).getByText('Reference unavailable')).toBeInTheDocument();
    expect(within(detail.getByText('10D avg volume').closest('div') as HTMLElement).getByText('Need 10 daily rows')).toBeInTheDocument();
    expect(within(detail.getByText('3M avg volume').closest('div') as HTMLElement).getByText('Need 30 daily rows')).toBeInTheDocument();
    expect(within(detail.getByText('52W high / low').closest('div') as HTMLElement).getByText('Need 120 daily rows')).toBeInTheDocument();
    expect(within(detail.getByText('Daily range').closest('div') as HTMLElement).getByText('Insufficient OHLC')).toBeInTheDocument();
  });

  it.each([
    { close: 100, referencePrice: 99, ceilingPrice: 106, floorPrice: 92, priceVsReferencePct: 1.01, expectedClass: 'text-success', expectedText: '+1.01%' },
    { close: 99, referencePrice: 99, ceilingPrice: 106, floorPrice: 92, priceVsReferencePct: 0, expectedClass: 'text-reference-yellow', expectedText: '0.00%' },
    { close: 106, referencePrice: 99, ceilingPrice: 106, floorPrice: 92, priceVsReferencePct: 7.07, expectedClass: 'text-ceiling-purple', expectedText: '+7.07%' },
    { close: 92, referencePrice: 99, ceilingPrice: 106, floorPrice: 92, priceVsReferencePct: -7.07, expectedClass: 'text-cyan', expectedText: '-7.07%' },
    { close: 98, referencePrice: 99, ceilingPrice: 106, floorPrice: 92, priceVsReferencePct: -1.01, expectedClass: 'text-danger', expectedText: '-1.01%' },
    { close: null, referencePrice: 99, ceilingPrice: 106, floorPrice: 92, priceVsReferencePct: null, expectedClass: 'text-secondary-text', expectedText: 'Daily close unavailable' },
    { close: 100, referencePrice: null, ceilingPrice: 106, floorPrice: 92, priceVsReferencePct: null, expectedClass: 'text-secondary-text', expectedText: 'Reference unavailable' },
  ])('colors selected daily price by SSI board convention %#', async ({ close, referencePrice, ceilingPrice, floorPrice, priceVsReferencePct, expectedClass, expectedText }) => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      latestPrice: close,
      ohlcvClose: close,
      dailyClose: close,
      close,
      dailyStockPrice: {
        ...response.watchlist[0].dailyStockPrice,
        referencePrice,
        ceilingPrice,
        floorPrice,
      },
      priceLimit: {
        ...response.watchlist[0].priceLimit,
        referencePrice,
        ceilingPrice,
        floorPrice,
      },
      indicators: {
        ...response.watchlist[0].indicators,
        priceVsReferencePct,
        priceVsReferenceStatus: close === null ? 'daily_close_unavailable' : referencePrice === null ? 'reference_unavailable' : 'ok',
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    const detail = within((await screen.findByText('Stock detail')).closest('section') as HTMLElement);
    expect(detail.getByTestId('selected-daily-close-price')).toHaveClass(expectedClass);
    expect(detail.getByTestId('selected-price-vs-reference')).toHaveClass(expectedClass);
    expect(detail.getByTestId('selected-price-vs-reference')).toHaveTextContent(expectedText);
  });

  it('renders SSI symbol metadata compactly when provided', async () => {
    render(<VietnamDashboardPage />);

    const header = within((await screen.findByText('Selected ticker')).closest('section') as HTMLElement);
    expect(header.getByText('FPT Listed Company')).toBeInTheDocument();
    expect(header.getByText('HOSE')).toBeInTheDocument();
    expect(header.queryByText('stock')).not.toBeInTheDocument();
    expect(header.queryByText('SSI metadata')).not.toBeInTheDocument();

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByRole('heading', { name: 'Symbol metadata' })).toBeInTheDocument();
    expect(detail.getByText('Vietnamese name')).toBeInTheDocument();
    expect(detail.getAllByText('FPT Listed Company').length).toBeGreaterThan(0);
    expect(detail.getByText('English name')).toBeInTheDocument();
    expect(detail.getByText('FPT Corporation')).toBeInTheDocument();
    expect(detail.getByText('Exchange / market')).toBeInTheDocument();
    expect(detail.getByText('HOSE')).toBeInTheDocument();
    expect(detail.getByText('Industry')).toBeInTheDocument();
    expect(detail.getByText('Information Technology')).toBeInTheDocument();
    expect(detail.getByText('Sector')).toBeInTheDocument();
    expect(detail.getByText('Technology')).toBeInTheDocument();
    expect(detail.getByText('Security type')).toBeInTheDocument();
    expect(detail.getByText('FPT issuer')).toBeInTheDocument();
    expect(detail.getByText('Lot size')).toBeInTheDocument();
    expect(detail.getByText('123,456,789')).toBeInTheDocument();
    expect(detail.getByText('2006-12-13')).toBeInTheDocument();
  });

  it('hides absent optional SSI symbol metadata rows', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      companyName: null,
      name: null,
      securityType: null,
      issuer: null,
      lotSize: null,
      listedShares: null,
      listedDate: null,
      symbolMetadata: {
        status: 'unavailable',
        qualityStatus: 'unavailable',
        completeness: 0,
        source: 'SSI SecuritiesDetails',
        reason: 'SSI FastConnect request failed',
        missingFields: ['name', 'industry', 'issuer'],
        fieldCoverage: {
          name: false,
          industry: false,
          issuer: false,
        },
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    const detail = within(await screen.findByText('Stock detail').then((node) => node.closest('section') as HTMLElement));
    expect(detail.getByRole('heading', { name: 'Symbol metadata' })).toBeInTheDocument();
    expect(detail.getByText('Profile unavailable. Daily SSI data is still available.')).toBeInTheDocument();
    expect(detail.queryByText('Vietnamese name')).not.toBeInTheDocument();
    expect(detail.queryByText('Listed shares')).not.toBeInTheDocument();
    expect(screen.queryByText('Company unavailable')).not.toBeInTheDocument();
    expect(detail.getByText('Daily close')).toBeInTheDocument();
  });

  it('hides absent optional SSI DailyStockPrice rows without blank detail fields', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      dailyStockPrice: {
        status: 'ok',
        date: '2026-06-10',
        referencePrice: 99,
        ceilingPrice: 106,
        floorPrice: 92,
        source: 'SSI',
      },
      foreign: {
        ...response.watchlist[0].foreign,
        netValue: null,
      },
      ssiForeignNetValue: null,
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByRole('heading', { name: 'DailyStockPrice coverage' })).toBeInTheDocument();
    expect(detail.getByText('Reference')).toBeInTheDocument();
    expect(detail.getByText('Ceiling price')).toBeInTheDocument();
    expect(detail.getByText('Floor price')).toBeInTheDocument();
    expect(detail.queryByText('Foreign net value')).not.toBeInTheDocument();
    expect(detail.queryByText('Matched value')).not.toBeInTheDocument();
    expect(detail.queryByText('Put-through value')).not.toBeInTheDocument();
    expect(detail.queryByText('Adjusted close')).not.toBeInTheDocument();
    expect(detail.queryByText('SSI DailyStockPrice fields are unavailable for this ticker.')).not.toBeInTheDocument();
  });

  it('shows explicit upcoming and recent corporate-action events without replacing raw close', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      latestPrice: 26500,
      dailyClose: 26500,
      ohlcvClose: 26500,
      close: 26500,
      previousClose: 27000,
      priceLimit: {
        ...response.watchlist[0].priceLimit,
        referencePrice: 26000,
        ceilingPrice: 27800,
        floorPrice: 24200,
      },
      dailyStockPrice: {
        ...response.watchlist[0].dailyStockPrice,
        referencePrice: 26000,
        ceilingPrice: 27800,
        floorPrice: 24200,
        close: 26500,
      },
      indicators: {
        ...response.watchlist[0].indicators,
        priceVsReferencePct: 1.92,
        priceVsReferenceStatus: 'ok',
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamCorporateActions.mockImplementation(async (tickers) => makeCorporateActionsResponse(tickers, {
      status: 'ok',
      source: 'provider_name',
      error: null,
      errorDetail: null,
      events: [
        {
          ticker: 'FPT',
          eventType: 'cash_dividend',
          status: 'upcoming',
          exDate: '2026-06-12',
          recordDate: '2026-06-13',
          paymentDate: '2026-06-30',
          cashDividendPerShare: 1000,
          description: 'Cash dividend 1,000 VND/share',
          source: 'provider_name',
          sourceUrl: null,
          lastCheckedAt: '2026-06-11T10:00:00+07:00',
        },
        {
          ticker: 'FPT',
          eventType: 'meeting',
          status: 'recent',
          exDate: null,
          recordDate: '2026-05-20',
          paymentDate: null,
          description: 'Annual general meeting',
          source: 'provider_name',
          sourceUrl: null,
          lastCheckedAt: '2026-06-11T10:00:00+07:00',
        },
      ],
      items: [
        {
          ticker: 'FPT',
          eventType: 'meeting',
          status: 'recent',
          exDate: null,
          recordDate: '2026-04-01',
          paymentDate: null,
          description: 'Legacy item should not render when canonical events exist',
          source: 'legacy_provider',
          sourceUrl: null,
          lastCheckedAt: '2026-06-11T10:00:00+07:00',
        },
      ],
    }));
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers),
      quotes: makeRealtimeResponse(tickers).quotes.map((quote) => ({
        ...quote,
        realtimePrice: quote.symbol === 'FPT' ? 26500 : quote.realtimePrice,
        snapshotPrice: quote.symbol === 'FPT' ? 26500 : quote.snapshotPrice,
        referencePrice: quote.symbol === 'FPT' ? 26000 : quote.referencePrice,
        priceVsReference: quote.symbol === 'FPT' ? 500 : quote.priceVsReference,
        priceVsReferencePct: quote.symbol === 'FPT' ? 1.92 : quote.priceVsReferencePct,
      })),
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamCorporateActions).toHaveBeenCalledWith(['FPT'], 6));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByText('Daily close')).toBeInTheDocument();
    expect(detail.getByText('26.50 / 26.50')).toBeInTheDocument();
    expect(within(detail.getByText('Reference').closest('div') as HTMLElement).getByText('26.00')).toBeInTheDocument();
    expect(within(detail.getByText('Vs reference').closest('div') as HTMLElement).getByText('+1.92%')).toBeInTheDocument();
    expect(detail.getByRole('heading', { name: 'Corporate actions' })).toBeInTheDocument();
    expect(detail.getByText('Recent and upcoming events')).toBeInTheDocument();
    expect(detail.getByText('Upcoming')).toBeInTheDocument();
    expect(detail.getByText('Recent, last 6 months')).toBeInTheDocument();
    expect(detail.getByText('cash dividend')).toBeInTheDocument();
    expect(detail.getAllByText('2026-06-12').length).toBeGreaterThan(0);
    expect(detail.getByText('Cash dividend')).toBeInTheDocument();
    expect(detail.getByText('1,000 VND/share')).toBeInTheDocument();
    expect(detail.getByText('meeting')).toBeInTheDocument();
    expect(detail.getByText('Annual general meeting')).toBeInTheDocument();
    expect(detail.getAllByText(/Source: provider_name/).length).toBeGreaterThan(0);
    expect(detail.queryByText('Legacy item should not render when canonical events exist')).not.toBeInTheDocument();
  });

  it('shows the OK-empty corporate-action state without inferring events', async () => {
    mockedGetVietnamCorporateActions.mockImplementation(async (tickers) => makeCorporateActionsResponse(tickers, {
      status: 'ok',
      source: 'provider_name',
      error: null,
      errorDetail: null,
      items: [],
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamCorporateActions).toHaveBeenCalledWith(['FPT'], 6));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByRole('heading', { name: 'Corporate actions' })).toBeInTheDocument();
    expect(detail.getByText('Recent and upcoming events')).toBeInTheDocument();
    expect(detail.getByText('No recent or upcoming corporate actions found.')).toBeInTheDocument();
  });

  it('renders the inspect chart with range controls, overlays, volume, and RSI', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();

    expect(chartCard.getByText('Daily OHLCV from SSI. SSI realtime remains separate.')).toBeInTheDocument();
    expect(chartCard.getByRole('group', { name: 'Timeframe' })).toBeInTheDocument();
    expect(chartCard.getByRole('group', { name: 'Daily range' })).toBeInTheDocument();
    expect(chartCard.getByText('Timeframe')).toBeInTheDocument();
    expect(chartCard.getByText('Range')).toBeInTheDocument();
    expect(within(chartCard.getByRole('group', { name: 'Timeframe' })).getAllByRole('button')).toHaveLength(2);
    expect(chartCard.getByRole('button', { name: '1M' })).toBeInTheDocument();
    expect(chartCard.getByRole('button', { name: '3M' })).toBeInTheDocument();
    expect(chartCard.getByRole('button', { name: '6M' })).toHaveAttribute('aria-pressed', 'true');
    expect(chartCard.getByRole('button', { name: '1Y' })).toBeInTheDocument();
    expect(chartCard.getByLabelText('MA20')).toBeChecked();
    expect(chartCard.getByLabelText('MA50')).toBeChecked();
    expect(chartCard.getByLabelText('Bollinger')).not.toBeChecked();
    expect(chartCard.getByRole('button', { name: 'Expand chart' })).toBeInTheDocument();
    const chart = chartCard.getByTestId('vietnam-lightweight-chart');
    expect(chart).toHaveAttribute('data-ticker', 'FPT');
    expect(chart).toHaveAttribute('data-points-count', '70');
    expect(chart).toHaveAttribute('data-first-date', '2026-04-01');
    expect(chart).toHaveAttribute('data-last-date', '2026-06-09');
    expect(chart).toHaveAttribute('data-ma20', 'true');
    expect(chart).toHaveAttribute('data-ma50', 'true');
    expect(chart).toHaveAttribute('data-bollinger', 'false');
    expect(chartCard.queryByTestId('inspect-candlestick-chart')).not.toBeInTheDocument();
    expect(chartCard.queryByRole('button', { name: 'Zoom in chart' })).not.toBeInTheDocument();
    expect(chartCard.getByTestId('inspect-legend-candles')).toHaveTextContent('Candlesticks');
    expect(chartCard.getByTestId('inspect-legend-ma20')).toBeInTheDocument();
    expect(chartCard.getByTestId('inspect-legend-ma50')).toBeInTheDocument();
    expect(chartCard.queryByTestId('inspect-legend-bollinger')).not.toBeInTheDocument();
    expect(chartCard.getByText('Daily volume MA20')).toBeInTheDocument();
    expect(chartCard.getByText('Daily volume MA50')).toBeInTheDocument();
    expect(chartCard.getAllByText('RSI14').length).toBeGreaterThan(0);
    expect(chartCard.getByText('RSI14 numeric guides: 30 and 70.')).toBeInTheDocument();
    expect(chartCard.getByText('Daily OHLCV source: SSI')).toBeInTheDocument();
    expect(chartCard.getByText('SSI realtime is separate and not used as daily close.')).toBeInTheDocument();
    expect(chartCard.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();
  });

  it('renders existing short-term daily zones only after enabling the master toggle, without additional requests', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        shortTermZones: {
          status: 'ok',
          timeframe: 'D1',
          lookbackSessions: 60,
          support: [{ lower: 120, upper: 121 }, { lower: 123, upper: 125 }, { lower: 127, upper: 128 }],
          resistance: [{ lower: 140, upper: 142 }, { lower: 150, upper: 155 }, { lower: 157, upper: 158 }],
        },
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    const zonesToggle = chartCard.getByLabelText('Show support and resistance zones');
    expect(zonesToggle).not.toBeChecked();
    expect(zonesToggle.closest('label')).not.toHaveAttribute('title');
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-short-term-zones', 'false');
    expect(chartCard.queryByTestId('lightweight-zone-S1')).not.toBeInTheDocument();

    const chartRequestsBeforeToggle = mockedGetVietnamChart.mock.calls.length;
    const watchlistRequestsBeforeToggle = mockedGetVietnamWatchlist.mock.calls.length;
    await clickChartControl(zonesToggle);

    expect(zonesToggle).toBeChecked();
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-short-term-zones', 'true');
    expect(chartCard.getByTestId('lightweight-zone-S1')).toHaveTextContent('S1 120-121');
    expect(chartCard.getByTestId('lightweight-zone-S2')).toHaveTextContent('S2 123-125');
    expect(chartCard.getByTestId('lightweight-zone-R1')).toHaveTextContent('R1 140-142');
    expect(chartCard.getByTestId('lightweight-zone-R2')).toHaveTextContent('R2 150-155');
    expect(chartCard.queryByTestId('lightweight-zone-S3')).not.toBeInTheDocument();
    expect(chartCard.queryByTestId('lightweight-zone-R3')).not.toBeInTheDocument();

    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartRequestsBeforeToggle);
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistRequestsBeforeToggle);

    await clickChartControl(chartCard.getByRole('button', { name: 'Expand chart' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Expanded inspect chart' }));
    expect(dialog.getByLabelText('Show support and resistance zones')).toBeChecked();
    expect(dialog.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-short-term-zones', 'true');
    expect(dialog.getByTestId('lightweight-zone-S1')).toBeInTheDocument();
    expect(dialog.getByTestId('lightweight-zone-R2')).toBeInTheDocument();
    await clickChartControl(dialog.getByLabelText('Show support and resistance zones'));
    expect(dialog.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-short-term-zones', 'false');
    expect(dialog.queryByTestId('lightweight-zone-S1')).not.toBeInTheDocument();
    await clickChartControl(dialog.getByRole('button', { name: 'Close expanded chart' }));
    expect(chartCard.getByLabelText('Show support and resistance zones')).not.toBeChecked();
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartRequestsBeforeToggle);
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistRequestsBeforeToggle);
  });

  it('ignores malformed or unavailable short-term zones without breaking the daily chart', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        shortTermZones: {
          status: 'ok',
          support: [{ lower: -1, upper: 121 }, { lower: 123, upper: 125 }],
          resistance: [{ lower: 150, upper: 140 }, { lower: Number.POSITIVE_INFINITY, upper: 160 }],
        },
      },
    };
    response.watchlist[1] = {
      ...response.watchlist[1],
      indicators: {
        ...response.watchlist[1].indicators,
        shortTermZones: { status: 'unavailable', support: [], resistance: [] },
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    expect(chartCard.queryByTestId('lightweight-zone-S1')).not.toBeInTheDocument();
    expect(chartCard.queryByTestId('lightweight-zone-S2')).not.toBeInTheDocument();
    await clickChartControl(chartCard.getByLabelText('Show support and resistance zones'));
    expect(chartCard.getByTestId('lightweight-zone-S2')).toBeInTheDocument();
    expect(chartCard.queryByTestId('lightweight-zone-R1')).not.toBeInTheDocument();
    expect(chartCard.queryByTestId('lightweight-zone-R2')).not.toBeInTheDocument();

    await act(async () => {
      clickTickerRow('VPB');
    });
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('VPB', '6M'));
    expect(chartCard.queryByTestId('lightweight-zone-S2')).not.toBeInTheDocument();
    expect(chartCard.getByLabelText('Show support and resistance zones')).toBeDisabled();
  });

  it('renders SSI as the inspect chart source when the chart payload uses SSI', async () => {
    mockedGetVietnamChart.mockResolvedValue(makeChartResponse('FPT', '6M', makeChartData(), { source: 'SSI' }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    expect(chartCard.getByText('Daily OHLCV from SSI. SSI realtime remains separate.')).toBeInTheDocument();
    expect(chartCard.getByText('Daily OHLCV source: SSI')).toBeInTheDocument();
    expect(chartCard.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();
  });

  it('renders an SSI unavailable source label for inspect chart payloads', async () => {
    mockedGetVietnamChart.mockResolvedValue(
      makeChartResponse('FPT', '6M', [], { status: 'unavailable', source: 'SSI', reason: 'SSI FastConnect unavailable' }),
    );

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    expect(chartCard.getByText('Daily OHLCV from SSI unavailable. SSI realtime remains separate.')).toBeInTheDocument();
    expect(chartCard.getByText('Daily OHLCV source: SSI unavailable')).toBeInTheDocument();
    expect(chartCard.getByText('Chart data unavailable')).toBeInTheDocument();
    expect(chartCard.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();
  });

  it('opens an expanded inspect chart with the same controls and closes it', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    fireEvent.click(chartCard.getByTestId('vietnam-lightweight-chart'));
    const chartRequestsBeforeExpand = mockedGetVietnamChart.mock.calls.length;
    await clickChartControl(chartCard.getByRole('button', { name: 'Expand chart' }));

    const dialogElement = screen.getByRole('dialog', { name: 'Expanded inspect chart' });
    const dialog = within(dialogElement);
    expect(dialog.getByText('Daily OHLCV from SSI. SSI realtime remains separate.')).toBeInTheDocument();
    expect(dialog.getByRole('button', { name: '6M' })).toHaveAttribute('aria-pressed', 'true');
    expect(dialog.getByLabelText('MA20')).toBeChecked();
    expect(dialog.getByLabelText('MA50')).toBeChecked();
    expect(dialog.getByLabelText('Bollinger')).not.toBeChecked();
    const expandedChart = dialog.getByTestId('vietnam-lightweight-chart');
    expect(expandedChart).toHaveAttribute('data-ticker', 'FPT');
    expect(expandedChart).toHaveAttribute('data-points-count', '70');
    expect(expandedChart).toHaveAttribute('data-expanded', 'true');
    expect(expandedChart).toHaveAttribute('data-initial-logical-range', '10:40');
    expect(screen.getAllByTestId('vietnam-lightweight-chart')).toHaveLength(1);
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartRequestsBeforeExpand);
    expect(dialog.queryByTestId('inspect-candlestick-chart')).not.toBeInTheDocument();

    await clickChartControl(dialog.getByLabelText('Bollinger'));
    expect(dialog.getByText('Bollinger upper/mid/lower')).toBeInTheDocument();
    expect(dialog.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-bollinger', 'true');
    expect(dialog.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();

    await clickChartControl(dialog.getByRole('button', { name: 'Close expanded chart' }));
    expect(screen.queryByRole('dialog', { name: 'Expanded inspect chart' })).not.toBeInTheDocument();
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-initial-logical-range', '10:40');
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartRequestsBeforeExpand);

    await clickChartControl(chartCard.getByRole('button', { name: 'Expand chart' }));
    expect(screen.getByRole('dialog', { name: 'Expanded inspect chart' })).toBeInTheDocument();
    await keyDownChartControl(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Expanded inspect chart' })).not.toBeInTheDocument();
  });

  it('shows Bollinger overlay only after enabling the chart toggle', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();

    expect(chartCard.queryByTestId('inspect-legend-bollinger')).not.toBeInTheDocument();
    await clickChartControl(chartCard.getByLabelText('Bollinger'));
    expect(chartCard.getByTestId('inspect-legend-bollinger')).toHaveTextContent('Bollinger upper/mid/lower');
  });

  it('requests the selected chart range when a range control changes', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();

    await clickChartControl(chartCard.getByRole('button', { name: '1Y' }));

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '1Y'));
    expect(chartCard.getByRole('button', { name: '1Y' })).toHaveAttribute('aria-pressed', 'true');
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-points-count', '70');
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-ticker', 'FPT');
    expect(chartCard.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();
  });

  it('loads foreign flow with one bounded request and renders watchlist columns and scoped rankings', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamForeignFlowBatch).toHaveBeenCalledTimes(1));

    expect(mockedGetVietnamForeignFlowBatch).toHaveBeenCalledWith(defaultTickers, expect.objectContaining({
      topN: 5,
      forceRefresh: false,
      signal: expect.any(AbortSignal),
    }));
    expect(screen.getByRole('button', { name: /^Sort by NN ròng/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Sort by NN 5P/ })).toBeInTheDocument();
    expect(screen.getByText('Top mua ròng trong watchlist')).toBeInTheDocument();
    expect(screen.getByText('Top bán ròng trong watchlist')).toBeInTheDocument();
    expect(screen.getByText('Trong watchlist')).toBeInTheDocument();
    expect(screen.queryByText(/market-wide ranking/i)).not.toBeInTheDocument();
  });

  it('sorts daily foreign net values deterministically with ticker tie-breaks', async () => {
    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamForeignFlowBatch).toHaveBeenCalledTimes(1));

    clickIndicatorSort(/Sort by NN ròng/i);
    expect(indicatorRowOrder()).toEqual(['ACB', 'SCS', 'VPB', 'ACV', 'FPT', 'MSB']);

    clickIndicatorSort(/Sort by NN ròng asc/i);
    expect(indicatorRowOrder()).toEqual(['ACV', 'FPT', 'MSB', 'ACB', 'SCS', 'VPB']);
  });

  it('keeps one foreign-flow request owner across a watchlist change and ignores the older response', async () => {
    let resolveInitial: ((value: VietnamForeignFlowBatchResponse) => void) | undefined;
    mockedGetVietnamForeignFlowBatch
      .mockImplementationOnce(() => new Promise((resolve) => { resolveInitial = resolve; }))
      .mockImplementationOnce(async (tickers) => makeForeignFlowResponse(tickers));

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamForeignFlowBatch).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'Banks' }));
    await waitFor(() => expect(mockedGetVietnamForeignFlowBatch).toHaveBeenCalledTimes(2));
    expect(mockedGetVietnamForeignFlowBatch.mock.calls[0][1]?.signal?.aborted).toBe(true);
    expect(mockedGetVietnamForeignFlowBatch.mock.calls[1][0]).toEqual([...presetTickers.Banks]);

    await act(async () => {
      resolveInitial?.(makeForeignFlowResponse(defaultTickers));
    });
    await waitFor(() => expect(screen.getByTestId('foreign-flow-rankings')).toHaveTextContent(`${presetTickers.Banks.length}/${presetTickers.Banks.length} mã có dữ liệu`));
    expect(screen.getByTestId('foreign-flow-rankings')).not.toHaveTextContent(`${defaultTickers.length}/${defaultTickers.length} mã có dữ liệu`);
  });

  it('retains the previous usable foreign-flow batch during and after an unavailable refresh', async () => {
    let resolveRefresh: ((value: VietnamForeignFlowBatchResponse) => void) | undefined;
    mockedGetVietnamForeignFlowBatch
      .mockImplementationOnce(async (tickers) => makeForeignFlowResponse(tickers))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveRefresh = resolve; }));

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(screen.getByTestId('foreign-flow-rankings')).toHaveTextContent('+2.0B'));

    fireEvent.click(screen.getByRole('button', { name: /^Refresh$/ }));
    await waitFor(() => expect(mockedGetVietnamForeignFlowBatch).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId('foreign-flow-rankings')).toHaveTextContent('Đang cập nhật; tiếp tục hiển thị dữ liệu gần nhất.');
    expect(screen.getByTestId('foreign-flow-rankings')).toHaveTextContent('+2.0B');

    const unavailable = makeForeignFlowResponse(defaultTickers);
    unavailable.usableCount = 0;
    unavailable.freshCount = 0;
    unavailable.unavailableCount = defaultTickers.length;
    unavailable.coverageRatio = 0;
    unavailable.complete = false;
    unavailable.dataState = 'unavailable';
    unavailable.rows = unavailable.rows.map((row) => ({
      ...row,
      dataState: 'unavailable',
      freshness: 'unavailable',
      foreignNetValue: null,
      foreignNetValue5d: null,
      foreignNetValue20d: null,
    }));
    unavailable.rankings = {
      latestNetValue: { topBuy: [], topSell: [] },
      netValue5d: { topBuy: [], topSell: [] },
      netValue20d: { topBuy: [], topSell: [] },
    };
    await act(async () => resolveRefresh?.(unavailable));

    await waitFor(() => expect(screen.getByTestId('foreign-flow-rankings')).toHaveTextContent('Cập nhật chưa khả dụng; đang giữ dữ liệu trước đó.'));
    expect(screen.getByTestId('foreign-flow-rankings')).toHaveTextContent('+2.0B');
  });

  it('shows reconnecting lifecycle copy without exposing transport errors', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      realtimeSnapshot: null,
      realtimeStatus: {
        status: 'unavailable',
        source: 'SSI realtime contract',
        diagnostics: { stream_state: 'recovering', last_error_class: 'network_closed' },
      },
      tradeTape: [],
      tradeTapeStatus: {
        status: 'unavailable',
        source: 'SSI trade-tape contract',
        diagnostics: { stream_state: 'recovering', last_error_class: 'network_closed' },
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockResolvedValue({
      ...makeRealtimeResponse(defaultTickers, { unavailable: true }),
      streamState: 'recovering',
      quotes: [],
    });
    mockedGetVietnamRealtimeTrades.mockResolvedValue({
      ...makeTradesResponse('FPT'),
      status: 'unavailable',
      streamState: 'recovering',
      trades: [],
    });

    render(<VietnamDashboardPage />);

    expect((await screen.findAllByText('Reconnecting — showing last known data when available.')).length).toBeGreaterThan(0);
    expect(screen.queryByText(/network_closed/i)).not.toBeInTheDocument();
  });

  it('defaults 1m to Today, keeps completed dates selectable, and keeps daily controls separate', async () => {
    const today = vietnamTodayIso();
    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();

    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledWith(
      'FPT',
      today,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));

    expect(chartCard.getByRole('button', { name: '1m' })).toHaveAttribute('aria-pressed', 'true');
    expect(chartCard.getByRole('group', { name: 'Timeframe' })).toBeInTheDocument();
    expect(chartCard.queryByRole('group', { name: 'Daily range' })).not.toBeInTheDocument();
    expect(chartCard.queryByRole('button', { name: '6M' })).not.toBeInTheDocument();
    expect(chartCard.getByLabelText('Intraday trading date')).toHaveValue(today);
    expect(chartCard.getByRole('option', { name: `Today — ${today.split('-').reverse().join('/')}` })).toBeInTheDocument();
    fireEvent.change(chartCard.getByLabelText('Intraday trading date'), { target: { value: '2026-06-09' } });
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledWith(
      'FPT',
      '2026-06-09',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));
    expect(chartCard.getByText('Daily S/R')).toBeInTheDocument();
    await waitFor(() => expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-timeframe', '1m'));
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute(
      'data-request-key',
      'intraday-chart:FPT:1m:2026-06-09',
    );
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(1);

    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(2);

    const intradayRequestsBeforeLocalActions = mockedGetVietnamIntradayChart.mock.calls.length;
    await clickChartControl(chartCard.getByLabelText('MA20'));
    await clickChartControl(chartCard.getByLabelText('Show support and resistance zones'));
    await clickChartControl(chartCard.getByRole('button', { name: 'Expand chart' }));
    expect(screen.getByRole('dialog', { name: 'Expanded inspect chart' })).toBeInTheDocument();
    expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(intradayRequestsBeforeLocalActions);
  });

  it('still requests explicit Today when no completed DailyOhlc date is available', async () => {
    const today = vietnamTodayIso();
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      date: null,
      latestPriceDate: null,
      ohlcvDate: null,
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamChart.mockResolvedValue(makeChartResponse('FPT', '6M', [], { latestDate: null }));

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));

    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledWith(
      'FPT',
      today,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));
    expect(chartCard.getByLabelText('Intraday trading date')).toHaveValue(today);
  });

  it('rejects a late 1m response after the selected completed date changes', async () => {
    const today = vietnamTodayIso();
    let resolveFirst: ((value: VietnamIntradayChartResponse) => void) | undefined;
    mockedGetVietnamIntradayChart.mockImplementation((ticker, tradingDate) => {
      if (tradingDate === today) {
        return new Promise((resolve) => { resolveFirst = resolve; });
      }
      return Promise.resolve(makeIntradayChartResponse(ticker, tradingDate, {
        bars: [{ time: 1_780_894_200, open: 200, high: 202, low: 199, close: 201, volume: 3_000 }],
      }));
    });

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1));
    fireEvent.change(chartCard.getByLabelText('Intraday trading date'), { target: { value: '2026-06-09' } });

    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledWith(
      'FPT',
      '2026-06-09',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));
    await waitFor(() => expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-first-close', '201'));
    await act(async () => {
      resolveFirst?.(makeIntradayChartResponse('FPT', today, {
        bars: [{ time: 1_780_980_600, open: 900, high: 902, low: 899, close: 901, volume: 4_000 }],
      }));
      await Promise.resolve();
    });
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-first-close', '201');
  });

  it('shows Updating and performs one minute-aligned Today refresh', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-07-16T02:16:05Z'));
    mockedGetVietnamIntradayChart.mockImplementation(async (ticker, tradingDate) => makeIntradayChartResponse(
      ticker,
      tradingDate,
      {
        sessionState: 'continuous_morning',
        freshness: 'updating',
        currentBarState: 'provisional',
        newestBarAgeSeconds: 5,
      },
    ));

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1));
    expect(chartCard.getByText('Updating')).toBeInTheDocument();

    mockedGetVietnamIntradayChart.mockClear();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1));
  });

  it('shows Lunch break for Today without a recurring minute request', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-07-16T05:00:00Z'));
    mockedGetVietnamIntradayChart.mockImplementation(async (ticker, tradingDate) => makeIntradayChartResponse(
      ticker,
      tradingDate,
      { sessionState: 'lunch', freshness: 'delayed', currentBarState: 'inferred_final' },
    ));

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1));
    expect(chartCard.getByText('Lunch break')).toBeInTheDocument();
    mockedGetVietnamIntradayChart.mockClear();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(59_000);
    });
    expect(mockedGetVietnamIntradayChart).not.toHaveBeenCalled();
  });

  it('shows a request-free countdown and sends force refresh only on user action', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-07-16T02:16:05Z'));
    mockedGetVietnamIntradayChart.mockImplementation(async (ticker, tradingDate) => makeIntradayChartResponse(
      ticker,
      tradingDate,
      {
        sessionState: 'continuous_morning',
        freshness: 'updating',
        currentBarState: 'provisional',
        providerSnapshotAgeSeconds: 2,
      },
    ));

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1));
    expect(chartCard.getByText('Next update in 2s')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1);
    expect(chartCard.getByText('Next update in 1s')).toBeInTheDocument();

    await clickChartControl(chartCard.getByRole('button', { name: 'Force refresh 1-minute chart' }));
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenLastCalledWith(
      'FPT',
      vietnamTodayIso(),
      expect.objectContaining({ forceRefresh: true, signal: expect.any(AbortSignal) }),
    ));
  });

  it('distinguishes provider unavailable from expected empty current-session data', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-07-16T02:16:05Z'));
    mockedGetVietnamIntradayChart.mockImplementation(async (ticker, tradingDate) => makeIntradayChartResponse(
      ticker,
      tradingDate,
      {
        status: 'unavailable',
        bars: [],
        sessionState: 'continuous_morning',
        freshness: 'unavailable',
        reason: 'SSI IntradayOhlc is unavailable.',
        diagnostics: { result: 'provider_unavailable', failureClass: 'network_error' },
      },
    ));

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    await waitFor(() => expect(chartCard.getAllByText('SSI data unavailable').length).toBeGreaterThan(0));
    expect(chartCard.queryByText('No data yet')).not.toBeInTheDocument();
  });

  it('runs the post-close automatic reconciliation once and does not repeat on visibility', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-07-16T07:44:50Z'));
    mockedGetVietnamIntradayChart.mockImplementation(async (ticker, tradingDate) => makeIntradayChartResponse(
      ticker,
      tradingDate,
      {
        sessionState: getVietnamScheduledSessionState(new Date()),
        freshness: 'delayed',
        currentBarState: 'inferred_final',
      },
    ));

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(2));
    expect(chartCard.getByText('Closed')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
      fireEvent(document, new Event('visibilitychange'));
      await Promise.resolve();
    });
    expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(2);
  });

  it('moves semantic Today at Vietnam midnight without fetching overnight', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-07-16T16:59:58Z'));
    render(<VietnamDashboardPage />);
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const chartCard = inspectChartCard();
    await clickChartControl(chartCard.getByRole('button', { name: '1m' }));
    await waitFor(() => expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(chartCard.getByLabelText('Intraday trading date')).toHaveValue('2026-07-17');
    expect(mockedGetVietnamIntradayChart).toHaveBeenCalledTimes(1);
  });

  it('replaces the chart bars when switching the selected range', async () => {
    mockedGetVietnamChart.mockImplementation(async (symbol, range = '6M') => {
      const points = range === '1M' ? makeChartData().slice(40) : makeChartData();
      return makeChartResponse(symbol, range, points);
    });

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-points-count', '70');
    fireEvent.click(chartCard.getByTestId('vietnam-lightweight-chart'));
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-initial-logical-range', '');

    await clickChartControl(chartCard.getByRole('button', { name: '1M' }));

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '1M'));
    await waitFor(() => expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-points-count', '30'));
    expect(chartCard.getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-initial-logical-range', '');
    expect(chartCard.getByRole('button', { name: '1M' })).toHaveAttribute('aria-pressed', 'true');
    expect(chartCard.queryByRole('button', { name: 'Reset chart zoom' })).not.toBeInTheDocument();
  });

  it('clears old chart state during rapid ticker switching and ignores late responses', async () => {
    let resolveVpb: ((value: VietnamChartResponse) => void) | undefined;
    let resolveMsb: ((value: VietnamChartResponse) => void) | undefined;
    let fptCalls = 0;
    mockedGetVietnamChart.mockImplementation((symbol, range = '6M') => {
      if (symbol === 'VPB') {
        return new Promise((resolve) => { resolveVpb = resolve; });
      }
      if (symbol === 'MSB') {
        return new Promise((resolve) => { resolveMsb = resolve; });
      }
      fptCalls += 1;
      const close = fptCalls === 1 ? 100 : 444;
      return Promise.resolve(makeChartResponse(symbol, range, [{ ...makeChartData()[0], close }]));
    });

    render(<VietnamDashboardPage />);
    await waitFor(() => expect(inspectChartCard().getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-ticker', 'FPT'));
    fireEvent.click(inspectChartCard().getByTestId('vietnam-lightweight-chart'));

    await act(async () => { clickTickerRow('VPB'); });
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('VPB', '6M'));
    expect(inspectChartCard().getByText('Loading chart data...')).toBeInTheDocument();
    expect(inspectChartCard().queryByTestId('vietnam-lightweight-chart')).not.toBeInTheDocument();

    await act(async () => { clickTickerRow('MSB'); });
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('MSB', '6M'));
    await act(async () => { clickTickerRow('FPT'); });
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledTimes(4));
    await waitFor(() => expect(inspectChartCard().getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-first-close', '444'));
    expect(inspectChartCard().getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-initial-logical-range', '');

    await act(async () => {
      resolveVpb?.(makeChartResponse('VPB', '6M', [{ ...makeChartData()[0], close: 222 }]));
      resolveMsb?.(makeChartResponse('MSB', '6M', [{ ...makeChartData()[0], close: 333 }]));
      await Promise.resolve();
    });
    expect(inspectChartCard().getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-ticker', 'FPT');
    expect(inspectChartCard().getByTestId('vietnam-lightweight-chart')).toHaveAttribute('data-first-close', '444');
  });

  it('renders chart data unavailable when selected ticker has no chart points', async () => {
    mockedGetVietnamChart.mockResolvedValue(makeChartResponse('FPT', '6M', []));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    expect(chartCard.getByText('Chart data unavailable')).toBeInTheDocument();
    expect(chartCard.queryByTestId('vietnam-lightweight-chart')).not.toBeInTheDocument();
    expect(chartCard.queryByTestId('inspect-candlestick-chart')).not.toBeInTheDocument();
  });

  it('keeps the watchlist rendered when the chart endpoint fails', async () => {
    mockedGetVietnamChart.mockRejectedValue(new Error('chart failed'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    expect(screen.getByRole('heading', { name: 'Indicator table' })).toBeInTheDocument();
    const chart = inspectChartCard();
    expect(chart.getByText('Chart data unavailable')).toBeInTheDocument();
    expect(chart.getByText('Chart endpoint unavailable: chart failed')).toBeInTheDocument();
  });

  it('renders SSI intraday pulse and SSI realtime volume labels while preserving numeric values', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: 4800000,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 4800000 },
      intradayCandles: [
        {
          dateTime: '2026-06-11T10:00:00+07:00',
          timestamp: 1781161200,
          open: 100,
          high: 103,
          low: 99,
          close: 102,
          volume: 1234567,
        },
      ],
      intradayRequestedTimeframe: '1h',
      intradayActualGranularity: '1m',
      intradayActualGranularitySeconds: 60,
      intradayGranularityLabel: '1m',
      intradayCadenceStatus: 'different_from_requested',
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: 103,
        sessionLowFrom1H: 99,
        sessionRangePctFrom1H: 4,
        sessionVolumeFrom1H: 1234567,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2345678,
        loadedCandlesTotalVolume: 2345678,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: 1.75,
        intradayRequestedTimeframe: '1h',
        intradayActualGranularity: '1m',
        intradayActualGranularitySeconds: 60,
        intradayCadenceStatus: 'different_from_requested',
      },
      intradayStatus: {
        status: 'ok',
        source: 'SSI',
        message: null,
        intradayCadenceStatus: 'different_from_requested',
      },
      intradayWarning: 'SSI IntradayOhlc candle data is not a realtime matched quote.',
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers),
      quotes: makeRealtimeResponse(tickers).quotes.map((quote) => ({
        ...quote,
        volumeAccumulated: quote.symbol === 'FPT' ? 3456000 : quote.volumeAccumulated,
      })),
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Intraday volume')).toBeInTheDocument();
    expect(screen.getByText('Session intraday volume')).toBeInTheDocument();
    expect(screen.getAllByText('Session / 20D').length).toBeGreaterThan(0);
    expect(screen.queryByText('Loaded intraday candles total volume (all loaded)')).not.toBeInTheDocument();
    expect(screen.queryByText('Volume ratio')).not.toBeInTheDocument();
    expect(screen.queryByText('Vol ratio')).not.toBeInTheDocument();
    expect(screen.getAllByText('Realtime volume').length).toBeGreaterThan(0);
    expect(screen.getByText('SSI IntradayOhlc candles are separate from SSI realtime board and trade tape context.')).toBeInTheDocument();
    expect(screen.getAllByText(/Returned cadence differs from requested 1h: 1m/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('1.23M').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('3.46M').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0.72x').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0.10 / 0.10').length).toBeGreaterThan(0);
    expect(screen.getByText('4%')).toBeInTheDocument();
    const sessionCandlesLabel = screen.getByText('Session candles');
    expect(within(sessionCandlesLabel.closest('div') as HTMLElement).getByText('5')).toBeInTheDocument();
    expect(screen.queryByText('Not enough session candles')).not.toBeInTheDocument();
    expect(screen.getByText('Volume vs average')).toBeInTheDocument();
    expect(screen.getByText('1.75x')).toBeInTheDocument();
  });

  it('falls back to intraday session volume when SSI realtime accumulated volume is stale', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: 4800000,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 4800000 },
      intradayCandles: makeCurrentIntradayCandles(),
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: 103,
        sessionLowFrom1H: 99,
        sessionRangePctFrom1H: 4,
        sessionVolumeFrom1H: 2400000,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2400000,
        loadedCandlesTotalVolume: 2400000,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: null,
      },
      intradayStatus: { status: 'ok', source: 'SSI', message: null },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers, { stale: true }),
      quotes: makeRealtimeResponse(tickers, { stale: true }).quotes.map((quote) => ({
        ...quote,
        volumeAccumulated: quote.symbol === 'FPT' ? 3456000 : quote.volumeAccumulated,
      })),
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getAllByText('Session / 20D').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0.5x').length).toBeGreaterThan(0);
    expect(screen.queryByText('0.72x')).not.toBeInTheDocument();
  });

  it('hides session volume ratio when daily average is unavailable', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: null,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: null },
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: 103,
        sessionLowFrom1H: 99,
        sessionRangePctFrom1H: 4,
        sessionVolumeFrom1H: 2400000,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2400000,
        loadedCandlesTotalVolume: 2400000,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: null,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.queryByText('20D avg unavailable')).not.toBeInTheDocument();
  });

  it('hides session volume metrics when neither SSI realtime nor intraday session volume is available', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: 4800000,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 4800000 },
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: 103,
        sessionLowFrom1H: 99,
        sessionRangePctFrom1H: 4,
        sessionVolumeFrom1H: null,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2400000,
        loadedCandlesTotalVolume: 2400000,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: null,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers, { unavailable: true }),
      quotes: makeRealtimeResponse(tickers, { unavailable: true }).quotes.map((quote) => ({
        ...quote,
        volumeAccumulated: null,
      })),
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.queryByText('Session volume unavailable')).not.toBeInTheDocument();
    expect(screen.queryByText('Session / 20D')).not.toBeInTheDocument();
  });

  it('shows explanatory intraday empty states instead of bare placeholders', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      intradayCandles: makeCurrentIntradayCandles(),
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: null,
        sessionLowFrom1H: null,
        sessionRangePctFrom1H: null,
        sessionVolumeFrom1H: null,
        sessionCandlesCount: 0,
        cumulative1hVolume: 2345678,
        loadedCandlesTotalVolume: 2345678,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: null,
      },
      intradayStatus: { status: 'ok', source: 'SSI', message: null },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const sessionHighLowLabel = screen.getByText('Session high / low from intraday');
    const sessionHighLowCard = sessionHighLowLabel.closest('div');
    expect(within(sessionHighLowCard as HTMLElement).getByText('Not enough session candles')).toHaveAttribute(
      'title',
      'Session high/low requires current-session intraday candles.',
    );
    expect(within(sessionHighLowCard as HTMLElement).queryByText('- / -')).not.toBeInTheDocument();

    const sessionVolumeLabel = screen.getByText('Session intraday volume');
    const sessionVolumeCard = sessionVolumeLabel.closest('div');
    expect(within(sessionVolumeCard as HTMLElement).getByText('Not enough session candles')).toHaveAttribute(
      'title',
      'Session volume requires current-session intraday candles.',
    );

    expect(screen.queryByText('Volume vs average')).not.toBeInTheDocument();
    expect(screen.queryByText('Avg unavailable')).not.toBeInTheDocument();
  });

  it('shows unavailable session values when session candles exist but metrics are missing', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      intradayCandles: makeCurrentIntradayCandles(),
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: null,
        sessionLowFrom1H: null,
        sessionRangePctFrom1H: null,
        sessionVolumeFrom1H: null,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2345678,
        loadedCandlesTotalVolume: 2345678,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: 1.75,
      },
      intradayStatus: { status: 'ok', source: 'SSI', message: null },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Session candles')).toBeInTheDocument();
    expect(screen.getAllByText('5').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Session value unavailable').length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText('Not enough session candles')).not.toBeInTheDocument();
  });

  it('displays 20D average volume from indicators', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: 1234567,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 7654321 },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getAllByText('20D avg volume').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1.23M').length).toBeGreaterThan(0);
  });

  it('falls back to liquidity 20D average volume when indicator value is missing', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: null,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 7654321 },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getAllByText('7.65M').length).toBeGreaterThan(0);
  });

  it('displays final close as not confirmed instead of unknown', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      finalCloseStatus: 'unknown',
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const finalCloseLabel = screen.getByText('Date / final close');
    const finalCloseCard = finalCloseLabel.closest('div');
    expect(within(finalCloseCard as HTMLElement).getByText('2026-06-10 / not confirmed')).toBeInTheDocument();
    expect(within(finalCloseCard as HTMLElement).queryByText(/unknown/)).not.toBeInTheDocument();
  });

  it('shows latest-available foreign net labels and mismatch note', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      dailyStockPrice: { status: 'unavailable', source: 'SSI DailyStockPrice' },
      ohlcvDate: '2026-06-12',
      foreignNetDate: '2026-06-11',
      foreignDateMatch: 'mismatched',
      indicators: {
        ...response.watchlist[0].indicators,
        foreignNet5dLatestAvailable: 12345,
        foreignNet20dLatestAvailable: -67890,
        foreignNetHistoryCount: 20,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Foreign net 5D')).toBeInTheDocument();
    expect(screen.getByText('Foreign net 20D')).toBeInTheDocument();
    expect(screen.getByText('+12.35K')).toBeInTheDocument();
    expect(screen.getByText('-67.89K')).toBeInTheDocument();
    expect(screen.getByText('Foreign data as of 2026-06-11; OHLCV date 2026-06-12.')).toBeInTheDocument();
  });

  it('shows latest-available foreign empty states when quote history is short', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      dailyStockPrice: { status: 'unavailable', source: 'SSI DailyStockPrice' },
      indicators: {
        ...response.watchlist[0].indicators,
        foreignNet5dLatestAvailable: null,
        foreignNet20dLatestAvailable: null,
        foreignNetHistoryCount: 4,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Need 5 foreign rows')).toBeInTheDocument();
    expect(screen.getByText('Need 20 foreign rows')).toBeInTheDocument();
  });

  it('renders data status with SSI source and fixture state', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const panel = dataStatusPanel();
    expect(panel.getByText('Data status')).toBeInTheDocument();
    expect(panel.getByText('Data status: OK')).toBeInTheDocument();
    expect(panel.getByText('Continuous afternoon')).toBeInTheDocument();
    expect(panel.getAllByText('holidayAware=false').length).toBeGreaterThan(0);
    expect(panel.getAllByText('SSI live').length).toBeGreaterThan(0);
    expect(dataStatusDiagnostics()).not.toHaveAttribute('open');
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(dataStatusDiagnostics()).toHaveAttribute('open');
    expect(panel.getByText('VN market phase')).toBeInTheDocument();
    expect(panel.getByText(/fixture_mode false/)).toBeInTheDocument();
    expect(panel.getByText('Overview refresh')).toBeInTheDocument();
    expect(panel.getByText('Selected detail')).toBeInTheDocument();
  });

  it('fetches observability on initial load', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
  });

  it('observability failure does not break dashboard rendering', async () => {
    mockedGetVietnamObservability.mockRejectedValue(new Error('observability down'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    expect(await screen.findByRole('heading', { name: 'Data status' })).toBeInTheDocument();
    expect(screen.getAllByText('FPT').length).toBeGreaterThan(0);
  });

  it('displays compact observability counters in data status', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());

    const panel = dataStatusPanel();
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText('VN data req')).toBeInTheDocument();
    expect(panel.getAllByText('3').length).toBeGreaterThan(0);
    expect(panel.getByText('Cache hit/miss')).toBeInTheDocument();
    expect(panel.getByText('40/8')).toBeInTheDocument();
    expect(panel.getByText('Single-flight waits')).toBeInTheDocument();
    expect(panel.getAllByText('1').length).toBeGreaterThan(0);
    expect(panel.getByText('SSI core status')).toBeInTheDocument();
    expect(panel.getByText('SSI intraday status')).toBeInTheDocument();
    expect(panel.getByText('SSI realtime status')).toBeInTheDocument();
    expect(panel.getByText('SSI trade tape status')).toBeInTheDocument();
    expect(panel.getByText('Legacy provider')).toBeInTheDocument();
    expect(panel.getByText('disabled')).toBeInTheDocument();
  });

  it('fetching observability does not call watchlist, realtime, or trades by itself', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    mockedGetVietnamWatchlist.mockClear();
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    await stocksApi.getVietnamObservability();

    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
  });

  it('shows auction helper copy during ATC phase', async () => {
    mockedGetVietnamMarketPhase.mockReturnValue(makeMarketPhase('ATC closing auction', 'atc', true));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const panel = dataStatusPanel();
    expect(panel.getByText('ATC closing auction')).toBeInTheDocument();
    expect(panel.getByText('Trade tape may differ during auction phases.')).toBeInTheDocument();
  });

  it('shows fixture warning in data status when fixture mode is active', async () => {
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => makeResponse(tickers?.length ? tickers : defaultTickers, { fixtureMode: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const panel = dataStatusPanel();
    expect(panel.getAllByText('SSI fixture').length).toBeGreaterThan(0);
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText(/fixture_mode true/)).toBeInTheDocument();
    expect(panel.getByText('Fixture mode is active; rows are sample data.')).toBeInTheDocument();
  });

  it('shows SSI realtime ok status when snapshot rows are fresh', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const panel = dataStatusPanel();
    expect(panel.getAllByText('SSI realtime live').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/updated 20s ago/).length).toBeGreaterThan(0);
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText('raw stale 0 | unavailable 0')).toBeInTheDocument();
  });

  it('realtime failure does not erase overview rows', async () => {
    mockedGetVietnamRealtimeQuotes.mockRejectedValueOnce(
      new Error('SSI FastConnect request failed in Realtime: attempted endpoints /api/v1/Trading/PriceBoard, /api/v1/Market/Realtime; HTTP 403'),
    );

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(await screen.findAllByText('SSI realtime unavailable. Daily SSI data is still available.')).not.toHaveLength(0);
    expect(screen.queryByText(/SSI realtime issue:.*attempted endpoints/)).not.toBeInTheDocument();
    const panel = dataStatusPanel();
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText(/attempted endpoints \/api\/v1\/Trading\/PriceBoard/)).toBeInTheDocument();
    expect(screen.getAllByText('FPT').length).toBeGreaterThan(0);
    expect(screen.getAllByText('ACB').length).toBeGreaterThan(0);
    expect(screen.queryByText('SSI unavailable')).not.toBeInTheDocument();
  });

  it('shows a concise DailyStockPrice date mismatch caveat without clearing daily detail', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      dailyStockPriceDate: '2026-06-09',
      dailyStockPriceDateMatch: 'mismatched',
      dailyStockPriceStalenessReason: 'DailyStockPrice date differs from DailyOhlc.',
      dailyStockPrice: {
        ...response.watchlist[0].dailyStockPrice,
        qualityStatus: 'partial',
        date: '2026-06-09',
        dateMatch: 'mismatched',
        stalenessReason: 'DailyStockPrice date differs from DailyOhlc.',
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    const detail = within(await screen.findByText('Stock detail').then((node) => node.closest('section') as HTMLElement));
    expect(detail.getByText('DailyStockPrice date differs from DailyOhlc.')).toBeInTheDocument();
    expect(detail.getByText('Daily close')).toBeInTheDocument();
    expect(detail.getAllByText('0.10 / 0.10').length).toBeGreaterThan(0);
    expect(detail.getByText('partial')).toBeInTheDocument();
    expect(detail.getByText('mismatched')).toBeInTheDocument();
  });

  it('realtime unavailable poll keeps the previous successful snapshot visible', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));
    expect(screen.getAllByText('0.10').length).toBeGreaterThan(0);
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    const chartCalls = mockedGetVietnamChart.mock.calls.length;
    const corporateActionsCalls = mockedGetVietnamCorporateActions.mock.calls.length;

    mockedGetVietnamRealtimeQuotes.mockResolvedValueOnce({
      ...makeRealtimeResponse(defaultTickers, { unavailable: true }),
      quotes: [],
    });

    fireEvent.click(screen.getByRole('button', { name: /refresh realtime/i }));

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText('0.10').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SSI realtime unavailable. Daily SSI data is still available.').length).toBeGreaterThan(0);
    expect(screen.queryByText('Last update failed')).not.toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartCalls);
    expect(mockedGetVietnamCorporateActions).toHaveBeenCalledTimes(corporateActionsCalls);
  });

  it('does not render fake realtime or trade tape metrics when SSI live sections are unavailable', async () => {
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, {
      unavailable: true,
      error: 'SSI FastConnect realtime snapshot unavailable (attempted endpoints: RealtimeQuote, RealtimePrice). Last error: HTTP 404',
    }));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => ({
      ...makeTradesResponse(symbol),
      status: 'unavailable',
      error: 'SSI FastConnect trade tape unavailable (attempted endpoints: TradeTape, MatchedTrades). Last error: HTTP 404',
      trades: [],
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const realtimeHeading = screen.getByRole('heading', { name: 'SSI realtime' });
    const realtimeCard = realtimeHeading.closest('div')?.parentElement as HTMLElement;
    expect(within(realtimeCard).getByText('SSI realtime unavailable. Daily SSI data is still available.')).toBeInTheDocument();
    expect(within(realtimeCard).queryByText('Realtime price')).not.toBeInTheDocument();
    expect(within(realtimeCard).queryByText('Realtime time')).not.toBeInTheDocument();
    expect(within(realtimeCard).queryByText('Realtime change')).not.toBeInTheDocument();
    expect(within(realtimeCard).queryByText('Realtime volume')).not.toBeInTheDocument();
    expect(within(realtimeCard).queryByText('SSI realtime snapshot; may differ from trade tape')).not.toBeInTheDocument();

    const tradeHeading = screen.getByRole('heading', { name: 'Trade tape' });
    const tradeCard = tradeHeading.closest('div')?.parentElement as HTMLElement;
    expect(within(tradeCard).getByText('SSI trade tape unavailable.')).toBeInTheDocument();
    expect(within(tradeCard).queryByText(/attempted endpoints/i)).not.toBeInTheDocument();
    expect(within(tradeCard).queryByRole('table')).not.toBeInTheDocument();
  });

  it('shows normalized SSI realtime timeout without raw provider text in warning banners', async () => {
    const rawTimeout = 'è¿žæŽ¥ä¸Šæ¸¸æœåŠ¡è¶…æ—¶: upstream timeout';
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, {
      error: 'SSI realtime provider timeout',
      errorDetail: 'The upstream SSI realtime provider did not respond in time.',
      rawError: rawTimeout,
    }));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => ({
      ...makeTradesResponse(symbol),
      status: 'unavailable',
      error: 'SSI realtime provider timeout',
      errorDetail: 'The upstream SSI realtime provider did not respond in time.',
      rawError: rawTimeout,
      trades: [],
    }));

    render(<VietnamDashboardPage />);

    expect(await screen.findAllByText('SSI realtime unavailable. Daily SSI data is still available.')).not.toHaveLength(0);
    expect(screen.getAllByText('SSI trade tape unavailable.').length).toBeGreaterThan(0);
    expect(screen.queryByText('Trade tape unavailable: SSI realtime provider timeout')).not.toBeInTheDocument();
    expect(screen.queryByText(/è¿žæŽ¥ä¸Šæ¸¸æœåŠ¡è¶…æ—¶/)).not.toBeInTheDocument();
  });

  it('shows active-trading stale warning when SSI realtime marks a snapshot stale during trading', async () => {
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { stale: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getAllByText('SSI realtime stale during trading').length).toBeGreaterThan(0);
    expect(screen.getAllByText('10:15:00 VN').length).toBeGreaterThan(0);
    expect(screen.getAllByText('stale >15s').length).toBeGreaterThan(0);
    const panel = dataStatusPanel();
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText(`raw stale ${defaultTickers.length} | unavailable 0`)).toBeInTheDocument();
    expect(panel.getByText('raw age 600s | raw stale true | reason age_gt_60s')).toBeInTheDocument();
    expect(screen.getAllByText('raw age 600s | raw stale true | reason age_gt_60s')).toHaveLength(1);
  });

  it('shows last available state after close without active-trading stale wording', async () => {
    mockedGetVietnamMarketPhase.mockReturnValue(makeMarketPhase('Closed', 'closed'));
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { stale: true, ageSeconds: 1200 }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getAllByText('Last available SSI realtime').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Market closed; snapshot may stop updating/).length).toBeGreaterThan(0);
    expect(screen.queryByText('SSI realtime stale during trading')).not.toBeInTheDocument();
    const panel = dataStatusPanel();
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText(`raw stale ${defaultTickers.length} | unavailable 0`)).toBeInTheDocument();
    expect(panel.getByText('raw age 1200s | raw stale true | reason age_gt_60s')).toBeInTheDocument();
    expect(screen.getAllByText('raw age 1200s | raw stale true | reason age_gt_60s')).toHaveLength(1);
  });

  it('shows SSI realtime unavailable count when snapshot rows are unavailable', async () => {
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { unavailable: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const panel = dataStatusPanel();
    expect(panel.getAllByText('SSI realtime unavailable').length).toBeGreaterThan(0);
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText(`raw stale 0 | unavailable ${defaultTickers.length}`)).toBeInTheDocument();
  });

  it('refresh realtime calls realtime endpoints only', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    const chartCalls = mockedGetVietnamChart.mock.calls.length;
    const corporateActionsCalls = mockedGetVietnamCorporateActions.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();
    mockedGetVietnamObservability.mockClear();

    fireEvent.click(screen.getByRole('button', { name: /refresh realtime/i }));

    await waitFor(() => {
      expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);
      expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100);
    });
    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartCalls);
    expect(mockedGetVietnamCorporateActions).toHaveBeenCalledTimes(corporateActionsCalls);
  });

  it('manual Refresh realtime does not create overlapping duplicate requests', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    let resolveQuotes: ((response: VietnamRealtimeResponse) => void) | undefined;
    let resolveTrades: ((response: VietnamRealtimeTradesResponse) => void) | undefined;
    mockedGetVietnamRealtimeQuotes.mockImplementation(() => new Promise((resolve) => {
      resolveQuotes = resolve;
    }));
    mockedGetVietnamRealtimeTrades.mockImplementation(() => new Promise((resolve) => {
      resolveTrades = resolve;
    }));

    fireEvent.click(screen.getByRole('button', { name: /refresh realtime/i }));

    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: /refreshing realtime/i })).toBeDisabled();

    await act(async () => {
      resolveQuotes?.(makeRealtimeResponse(defaultTickers));
      resolveTrades?.(makeTradesResponse('FPT'));
    });
  });

  it('shows SSI realtime auto-refresh controls', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' })).toBeChecked();
    expect(screen.getByLabelText('SSI realtime')).toHaveValue('3');
    expect([...screen.getByLabelText('SSI realtime').querySelectorAll('option')].map((option) => option.value)).toEqual(['2', '3', '5', '10', '15']);
    expect(screen.getByRole('checkbox', { name: 'Auto-refresh trade tape' })).not.toBeChecked();
    expect(screen.getByLabelText('Trade tape')).toHaveValue('10');
    expect([...screen.getByLabelText('Trade tape').querySelectorAll('option')].map((option) => option.value)).toEqual(['5', '10', '15']);
    expect(screen.queryByRole('button', { name: /KBS/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/KBS/i)).not.toBeInTheDocument();
  });

  it('auto-refresh realtime polls quotes every 3s without refreshing watchlist or trade tape', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    const chartCalls = mockedGetVietnamChart.mock.calls.length;
    const corporateActionsCalls = mockedGetVietnamCorporateActions.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();
    mockedGetVietnamObservability.mockClear();

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));

    await act(async () => {
      vi.advanceTimersByTime(3000);
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartCalls);
    expect(mockedGetVietnamCorporateActions).toHaveBeenCalledTimes(corporateActionsCalls);
    expect(mockedGetVietnamObservability).toHaveBeenCalled();

    expect(dataStatusPanel().getByText('on')).toBeInTheDocument();
    expect(dataStatusPanel().getByText('snapshot 3s | trade tape off')).toBeInTheDocument();
  });

  it('selected 5s trade tape interval calls only trades endpoint', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));
    await waitFor(() => expect(mockedGetVietnamCorporateActions).toHaveBeenCalledWith(['FPT'], 6));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    const chartCalls = mockedGetVietnamChart.mock.calls.length;
    const corporateActionsCalls = mockedGetVietnamCorporateActions.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    fireEvent.change(screen.getByLabelText('Trade tape'), { target: { value: '5' } });
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh trade tape' }));

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100);
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartCalls);
    expect(mockedGetVietnamCorporateActions).toHaveBeenCalledTimes(corporateActionsCalls);
  });

  it('changing SSI realtime intervals does not call watchlist endpoints', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    fireEvent.change(screen.getByLabelText('SSI realtime'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('Trade tape'), { target: { value: '5' } });

    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
  });

  it('auto-refresh realtime skips quote ticks while quote refresh is in flight', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    let resolveQuotes: ((response: VietnamRealtimeResponse) => void) | undefined;
    mockedGetVietnamRealtimeQuotes.mockImplementation(() => new Promise((resolve) => {
      resolveQuotes = resolve;
    }));

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));

    await act(async () => {
      vi.advanceTimersByTime(3000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();

    mockedGetVietnamRealtimeTrades.mockClear();
    await act(async () => {
      vi.advanceTimersByTime(3000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveQuotes?.(makeRealtimeResponse(defaultTickers));
    });
  });

  it('auto-refresh realtime skips trade ticks while trade refresh is in flight without blocking quotes', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    let resolveTrades: ((response: VietnamRealtimeTradesResponse) => void) | undefined;
    mockedGetVietnamRealtimeTrades.mockImplementation(() => new Promise((resolve) => {
      resolveTrades = resolve;
    }));

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh trade tape' }));

    await act(async () => {
      vi.advanceTimersByTime(10000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);

    await act(async () => {
      resolveTrades?.(makeTradesResponse('FPT'));
    });
  });

  it('auto-refresh realtime pauses while the document is hidden', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));

    await act(async () => {
      vi.advanceTimersByTime(15000);
    });

    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
  });

  it('visibility restore fires at most one quote request without trade tape auto-refresh', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    const chartCalls = mockedGetVietnamChart.mock.calls.length;
    const corporateActionsCalls = mockedGetVietnamCorporateActions.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh realtime' }));

    await act(async () => {
      vi.advanceTimersByTime(30000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    fireEvent(document, new Event('visibilitychange'));

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls + 1);
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['FPT'], false);
    expect(mockedGetVietnamChart).toHaveBeenCalledTimes(chartCalls);
    expect(mockedGetVietnamCorporateActions).toHaveBeenCalledTimes(corporateActionsCalls);
  });

  it('selecting ticker fetches latest trades without reloading the watchlist', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await screen.findByRole('heading', { name: 'Indicator table' });
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    clickTickerRow('ACB');

    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('ACB', 100));
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(await screen.findByText('10:16:00')).toBeInTheDocument();
  });

  it('selected ticker change does not overlap trade fetches and refreshes pending ticker', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeTrades.mockClear();

    let resolveFptTrades: ((response: VietnamRealtimeTradesResponse) => void) | undefined;
    mockedGetVietnamRealtimeTrades.mockImplementationOnce(() => new Promise((resolve) => {
      resolveFptTrades = resolve;
    }));

    fireEvent.click(screen.getByRole('button', { name: /refresh realtime/i }));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));

    clickTickerRow('ACB');

    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveFptTrades?.(makeTradesResponse('FPT'));
    });

    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('ACB', 100));
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('does not offer invalid exact tickers or issue another watchlist request', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));

    fireEvent.change(screen.getByLabelText('Custom watchlist picker'), { target: { value: 'FPT @@@ ACB' } });

    expect(await screen.findByText(/No loaded ticker match/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Apply custom watchlist' })).toBeDisabled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(1);
  });

  it('loads bounded Community news only for the selected ticker and renders only safe external links', async () => {
    mockedGetVietnamCompanyNews.mockImplementation(async (ticker) => ({
      ticker,
      status: 'ok',
      source: 'Vnstock Community',
      provider: 'vnstock_community',
      providerMode: 'community_free_ticker_news',
      rightsStatus: 'personal_research_only',
      message: `Vnstock Community company news loaded for ${ticker}.`,
      news: [
        { id: `${ticker}-1`, ticker, title: `${ticker} absolute article`, url: 'https://example.test/article', publishedAt: '2026-07-10T09:00:00+07:00', providerMode: 'community_free_ticker_news', rightsStatus: 'personal_research_only' },
        { id: `${ticker}-2`, ticker, title: `${ticker} relative article`, rawUrl: '/relative', url: null, publishedAt: '2026-07-09T09:00:00+07:00', providerMode: 'community_free_ticker_news', rightsStatus: 'personal_research_only' },
        { id: `${ticker}-3`, ticker, title: `${ticker} unsafe article`, rawUrl: 'javascript:alert(1)', url: 'javascript:alert(1)', publishedAt: '2026-07-08T09:00:00+07:00', providerMode: 'community_free_ticker_news', rightsStatus: 'personal_research_only' },
        { id: `${ticker}-4`, ticker, title: `${ticker} fourth article`, url: null, publishedAt: '2026-07-07T09:00:00+07:00', providerMode: 'community_free_ticker_news', rightsStatus: 'personal_research_only' },
      ],
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamCompanyNews).toHaveBeenCalledWith('FPT', expect.any(Object)));
    expect(await screen.findByText('News for FPT')).toBeInTheDocument();
    expect(screen.getByText('Vnstock Community')).toBeInTheDocument();
    expect(screen.getAllByText('Personal research').length).toBeGreaterThan(0);
    const safeLink = screen.getByRole('link', { name: 'FPT absolute article' });
    expect(safeLink).toHaveAttribute('href', 'https://example.test/article');
    expect(safeLink).toHaveAttribute('target', '_blank');
    expect(safeLink).toHaveAttribute('rel', expect.stringContaining('noopener'));
    expect(safeLink).toHaveAttribute('rel', expect.stringContaining('noreferrer'));
    expect(screen.queryByRole('link', { name: 'FPT relative article' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'FPT unsafe article' })).not.toBeInTheDocument();
    expect(screen.queryByText('FPT fourth article')).not.toBeInTheDocument();

    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    clickTickerRow('ACB');
    await waitFor(() => expect(mockedGetVietnamCompanyNews).toHaveBeenCalledWith('ACB', expect.any(Object)));
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('does not render recommendation wording', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.queryByText(/recommend/i)).not.toBeInTheDocument();
  });
});
