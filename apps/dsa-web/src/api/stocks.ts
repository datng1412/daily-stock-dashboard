import apiClient from './index';

export type ExtractItem = {
  code?: string | null;
  name?: string | null;
  confidence: string;
};

export type ExtractFromImageResponse = {
  codes: string[];
  items?: ExtractItem[];
  rawText?: string;
};

export type VietnamWatchItem = {
  ticker: string;
  entity?: string | null;
  exchange?: string | null;
  marketIndex?: string | null;
  source?: string | null;
  rowsLoaded?: number | null;
  date?: string | null;
  latestPrice?: number | null;
  latestPriceSource?: string | null;
  latestPriceRawField?: string | null;
  latestPriceDate?: string | null;
  quotePriceDate?: string | null;
  quotePriceRawField?: string | null;
  priceSourceWarning?: string | null;
  ohlcvClose?: number | null;
  priceDate?: string | null;
  ohlcvDate?: string | null;
  quoteDate?: string | null;
  foreignNetDate?: string | null;
  foreignDateMatch?: string | null;
  candleStatus?: string | null;
  finalCloseStatus?: string | null;
  priceAdjustmentStatus?: string | null;
  adjustedPriceStatus?: string | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  previousClose?: number | null;
  changePct?: number | null;
  volume?: number | null;
  amount?: number | null;
  liquidity: { avgVolume20D?: number | null; score?: number | null };
  priceLimit: {
    limitPct?: number | null;
    ceilingPrice?: number | null;
    floorPrice?: number | null;
    distanceToLimitPct?: number | null;
    nearLimit?: boolean;
  };
  corporateAction?: {
    status?: 'none' | 'detected' | 'unavailable' | string | null;
    type?: 'cash_dividend' | 'stock_dividend' | 'rights' | 'unknown' | string | null;
    exDate?: string | null;
    cashDividendPerShare?: number | null;
    previousClose?: number | null;
    adjustedReferencePrice?: number | null;
    adjustmentSource?: 'kbs_reference' | 'provider_event' | 'manual_unavailable' | string | null;
    priceVsAdjustedReference?: number | null;
    priceVsAdjustedReferencePct?: number | null;
    note?: string | null;
  };
  foreign: { buy?: number | null; sell?: number | null; net?: number | null; signal?: string | null };
  foreignNetUnit?: string | null;
  foreignBuyRawField?: string | null;
  foreignSellRawField?: string | null;
  indicators: {
    close?: number | null;
    ma20?: number | null;
    ma50?: number | null;
    rsi14?: number | null;
    rsi14Wilder?: number | null;
    rsi14SimpleDebug?: number | null;
    rsiMethod?: string | null;
    bollinger?: { middle?: number | null; upper?: number | null; lower?: number | null };
    avgVolume20D?: number | null;
    volumeRatio?: number | null;
    high20d?: number | null;
    low20d?: number | null;
    distanceTo20dHighPct?: number | null;
    distanceTo20dLowPct?: number | null;
    foreignNet5D?: number | null;
    foreignNet20D?: number | null;
    foreignNetLatest?: number | null;
    foreignNet5dLatestAvailable?: number | null;
    foreignNet20dLatestAvailable?: number | null;
    foreignNetLatestAvailableDate?: string | null;
    foreignNetHistoryCount?: number | null;
  };
  statusLabels: string[];
  statusDetails?: Array<{
    label: string;
    severity: 'info' | 'caution' | 'risk';
    reason: string;
    inputs?: Record<string, unknown>;
  }>;
  validation: { valid?: boolean; tradingDate?: string | null; missingFields?: string[]; errors?: string[] };
  trend: { signalScore?: number; buySignal?: string; trendStatus?: string; volumeRatio5d?: number };
  warnings: string[];
  news: Array<{ title?: string; url?: string; source?: string; publishedAt?: string; summary?: string }>;
  intradayTimeframe?: string | null;
  intradaySource?: string | null;
  intradayIsRealtimeQuote?: boolean;
  intradayWarning?: string | null;
  intradayCandles?: Array<{
    timestamp?: number | null;
    dateTime?: string | null;
    open?: number | null;
    high?: number | null;
    low?: number | null;
    close?: number | null;
    volume?: number | null;
  }>;
  intradayPulse?: {
    latest1hClose?: number | null;
    latest1hOpen?: number | null;
    latest1hHigh?: number | null;
    latest1hLow?: number | null;
    latest1hVolume?: number | null;
    latest1hChange?: number | null;
    latest1hChangePercent?: number | null;
    sessionHighFrom1H?: number | null;
    sessionLowFrom1H?: number | null;
    sessionRangePctFrom1H?: number | null;
    sessionVolumeFrom1H?: number | null;
    sessionCandlesCount?: number | null;
    cumulative1hVolume?: number | null;
    loadedCandlesTotalVolume?: number | null;
    direction?: 'up' | 'down' | 'flat' | 'unknown' | null;
    rangePercent?: number | null;
    volumeVsAvg1h?: number | null;
  };
  intradayLabels?: string[];
  intradayDetails?: Array<{
    label: string;
    severity: 'info' | 'caution' | 'risk';
    reason: string;
    inputs?: Record<string, unknown>;
  }>;
  cacheStatus: Record<string, string>;
  cacheLastFetchedAt: Record<string, string | null>;
  cacheNextRefreshAt: Record<string, string | null>;
  cacheErrors: Record<string, string>;
  error?: string | null;
};

export type VietnamCacheMetadata = {
  cacheHitCount: number;
  cacheMissCount: number;
  staleCacheUsedCount: number;
  cacheTtlSeconds: Record<string, number>;
  lastFetchedAt: Record<string, Record<string, string | null>>;
  nextRefreshAt: Record<string, Record<string, string | null>>;
  symbols: Record<string, Record<string, string>>;
};

export type VietnamWatchlistHealthResponse = {
  source: string;
  fixtureMode: boolean;
  symbolsLoaded: number;
  lastTradingDate?: string | null;
  missingFields: Record<string, string[]>;
  errors: Record<string, string[]>;
  lastRefreshTime?: string | null;
  units: Record<string, string>;
  cacheMetadata?: VietnamCacheMetadata;
};

export type VietnamWatchlistResponse = {
  market: 'VN';
  source: string;
  fixtureMode: boolean;
  lastRefreshTime?: string | null;
  units: Record<string, string>;
  dataQuality: VietnamWatchlistHealthResponse;
  cacheMetadata: VietnamCacheMetadata;
  watchlist: VietnamWatchItem[];
  ruleMetadata?: { ruleSetName?: string; ruleSetVersion?: string; noRecommendation?: boolean };
  formulas: Record<string, string>;
};

export type VietnamRealtimeQuote = {
  symbol: string;
  realtimePrice?: number | null;
  realtimeTime?: string | null;
  realtimeTimeDisplay?: string | null;
  snapshotPrice?: number | null;
  snapshotTime?: string | null;
  snapshotTimeDisplay?: string | null;
  snapshotNote?: string | null;
  ageSeconds?: number | null;
  isStale?: boolean | null;
  staleReason?: string | null;
  referencePrice?: number | null;
  referencePriceSource?: string | null;
  priceVsReference?: number | null;
  priceVsReferencePct?: number | null;
  openPrice?: number | null;
  highPrice?: number | null;
  lowPrice?: number | null;
  averagePrice?: number | null;
  priceChange?: number | null;
  percentChange?: number | null;
  volumeAccumulated?: number | null;
  totalValue?: number | null;
  bidPrice1?: number | null;
  bidVol1?: number | null;
  askPrice1?: number | null;
  askVol1?: number | null;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignRoom?: number | null;
  source: 'vnstock_kbs';
  status: 'ok' | 'unavailable' | 'error' | 'stale';
  error?: string | null;
  errorDetail?: string | null;
  rawError?: string | null;
};

export type VietnamRealtimeResponse = {
  market: 'VN';
  source: 'vnstock_kbs';
  status: 'ok' | 'unavailable' | 'error' | 'stale';
  error?: string | null;
  errorDetail?: string | null;
  rawError?: string | null;
  requestedTickers: string[];
  quotes: VietnamRealtimeQuote[];
  cache: Record<string, unknown>;
};

export type VietnamRealtimeTrade = {
  time?: string | null;
  price?: number | null;
  volume?: number | null;
  matchType?: string | null;
  id?: string | null;
  source: 'vnstock_kbs';
};

export type VietnamRealtimeTradesResponse = {
  market: 'VN';
  source: 'vnstock_kbs';
  symbol: string;
  status: 'ok' | 'unavailable' | 'error' | 'stale';
  error?: string | null;
  errorDetail?: string | null;
  rawError?: string | null;
  trades: VietnamRealtimeTrade[];
  note?: string | null;
  cache: Record<string, unknown>;
};

export type VietnamChartPoint = {
  date?: string | null;
  time?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
  volumeMa20?: number | null;
  volumeMa50?: number | null;
  ma20?: number | null;
  ma50?: number | null;
  rsi14?: number | null;
  bbUpper?: number | null;
  bbMid?: number | null;
  bbLower?: number | null;
};

export type VietnamChartResponse = {
  symbol: string;
  source: string;
  timeframe: string;
  range: '1M' | '3M' | '6M' | '1Y' | string;
  latestDate?: string | null;
  points: VietnamChartPoint[];
};

export type VietnamCorporateActionEvent = {
  ticker: string;
  eventType: 'cash_dividend' | 'stock_dividend' | 'bonus_share' | 'rights_issue' | 'split' | 'meeting' | 'unknown' | string;
  status: 'upcoming' | 'recent' | 'past' | string;
  exDate?: string | null;
  recordDate?: string | null;
  paymentDate?: string | null;
  cashDividendPerShare?: number | null;
  stockDividendRatio?: string | null;
  rightsRatio?: string | null;
  description?: string | null;
  source?: string | null;
  sourceUrl?: string | null;
  lastCheckedAt?: string | null;
};

export type VietnamCorporateActionsResponse = {
  market: 'VN';
  status: 'ok' | 'unavailable' | 'error' | string;
  source?: string | null;
  lastCheckedAt?: string | null;
  requestedTickers: string[];
  monthsBack: number;
  items: VietnamCorporateActionEvent[];
  error?: string | null;
  errorDetail?: string | null;
};

export type VietnamObservabilityResponse = {
  market: 'VN';
  status: 'ok' | 'error';
  mozyfin: {
    watchlistRequestsTotal: number;
    watchlistCacheHitsTotal: number;
    watchlistCacheMissesTotal: number;
    singleflightWaitsTotal: number;
    lastWatchlistRequestAt?: string | null;
    lastFetchAt?: string | null;
    lastCacheKey?: string | null;
    lastTickersCount: number;
    lastFetchDurationMs?: number | null;
  };
  kbs: {
    quoteRequestsTotal: number;
    quoteSuccessTotal: number;
    quoteUnavailableTotal: number;
    tradeRequestsTotal: number;
    tradeSuccessTotal: number;
    tradeUnavailableTotal: number;
    lastQuoteRequestAt?: string | null;
    lastTradeRequestAt?: string | null;
    lastQuoteTickersCount: number;
    lastTradeSymbol?: string | null;
    lastError?: string | null;
    lastRawErrorPresent: boolean;
  };
};

export const stocksApi = {
  async extractFromImage(file: File): Promise<ExtractFromImageResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
    const response = await apiClient.post(
      '/api/v1/stocks/extract-from-image',
      formData,
      {
        headers,
        timeout: 60000, // Vision API can be slow; 60s
      },
    );

    const data = response.data as { codes?: string[]; items?: ExtractItem[]; raw_text?: string };
    return {
      codes: data.codes ?? [],
      items: data.items,
      rawText: data.raw_text,
    };
  },

  async parseImport(file?: File, text?: string): Promise<ExtractFromImageResponse> {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
      const response = await apiClient.post('/api/v1/stocks/parse-import', formData, { headers });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    if (text) {
      const response = await apiClient.post('/api/v1/stocks/parse-import', { text });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    throw new Error('Provide a file or pasted text');
  },

  async getVietnamWatchlist(
    tickers?: string[],
    forceRefresh = false,
    options?: { includeIntraday?: boolean; intradayTimeframe?: string; intradayLimit?: number },
  ): Promise<VietnamWatchlistResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/watchlist', {
      params: {
        ...(tickers?.length ? { tickers: tickers.join(',') } : {}),
        ...(forceRefresh ? { force_refresh: true } : {}),
        ...(options?.includeIntraday !== undefined ? { include_intraday: options.includeIntraday } : {}),
        ...(options?.intradayTimeframe ? { intraday_timeframe: options.intradayTimeframe } : {}),
        ...(options?.intradayLimit ? { intraday_limit: options.intradayLimit } : {}),
      },
      timeout: 120000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamWatchlistResponse>(response.data);
  },

  async getVietnamWatchlistHealth(tickers?: string[]): Promise<VietnamWatchlistHealthResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/watchlist/health', {
      params: tickers?.length ? { tickers: tickers.join(',') } : undefined,
      timeout: 120000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamWatchlistHealthResponse>(response.data);
  },

  async getVietnamChart(symbol: string, range = '6M'): Promise<VietnamChartResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/chart', {
      params: { symbol, range },
      timeout: 120000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamChartResponse>(response.data);
  },

  async getVietnamRealtimeQuotes(tickers: string[]): Promise<VietnamRealtimeResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/realtime', {
      params: { tickers: tickers.join(',') },
      timeout: 30000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamRealtimeResponse>(response.data);
  },

  async getVietnamRealtimeTrades(symbol: string, limit = 100): Promise<VietnamRealtimeTradesResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/realtime/trades', {
      params: { symbol, limit },
      timeout: 30000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamRealtimeTradesResponse>(response.data);
  },

  async getVietnamCorporateActions(tickers: string[], monthsBack = 6): Promise<VietnamCorporateActionsResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/corporate-actions', {
      params: {
        ...(tickers.length ? { tickers: tickers.join(',') } : {}),
        months_back: monthsBack,
      },
      timeout: 30000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamCorporateActionsResponse>(response.data);
  },

  async getVietnamObservability(): Promise<VietnamObservabilityResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/observability', {
      timeout: 10000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamObservabilityResponse>(response.data);
  },
};
