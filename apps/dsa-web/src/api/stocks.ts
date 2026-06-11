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
  liquidity: { avgVolume20d?: number | null; score?: number | null };
  priceLimit: {
    limitPct?: number | null;
    ceilingPrice?: number | null;
    floorPrice?: number | null;
    distanceToLimitPct?: number | null;
    nearLimit?: boolean;
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
    avgVolume20d?: number | null;
    volumeRatio?: number | null;
    high20d?: number | null;
    low20d?: number | null;
    distanceTo20dHighPct?: number | null;
    distanceTo20dLowPct?: number | null;
    foreignNet5d?: number | null;
    foreignNet20d?: number | null;
    foreignNetLatest?: number | null;
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
    sessionHighFrom1h?: number | null;
    sessionLowFrom1h?: number | null;
    cumulative1hVolume?: number | null;
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
  referencePrice?: number | null;
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
};

export type VietnamRealtimeResponse = {
  market: 'VN';
  source: 'vnstock_kbs';
  status: 'ok' | 'unavailable' | 'error' | 'stale';
  error?: string | null;
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
  trades: VietnamRealtimeTrade[];
  cache: Record<string, unknown>;
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
    throw new Error('请提供文件或粘贴文本');
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
};
