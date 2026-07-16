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

export type VietnamOrderBookLevel = {
  level?: number | null;
  price?: number | null;
  volume?: number | null;
};

export type VietnamOrderBook = {
  ticker?: string | null;
  symbol?: string | null;
  source?: string | null;
  exchange?: string | null;
  bids?: VietnamOrderBookLevel[];
  asks?: VietnamOrderBookLevel[];
  tradingDate?: string | null;
  time?: string | null;
  receivedAt?: string | null;
  streamTimestamp?: string | null;
  streamDataType?: string | null;
  rType?: string | null;
  ageSeconds?: number | null;
  isStale?: boolean | null;
  staleReason?: string | null;
  cachedAt?: string | null;
  cacheTtlSeconds?: number | null;
  snapshotSource?: 'persisted' | string | null;
  snapshotCapturedAt?: string | null;
  snapshotTradingDate?: string | null;
  snapshotSchemaVersion?: number | null;
};

export type VietnamOptionalLiveStatus = {
  status?: string | null;
  source?: string | null;
  message?: string | null;
  reasonCode?: string | null;
  classification?: string | null;
  count?: number | null;
  fetchedAt?: string | null;
  diagnostics?: Record<string, unknown> | null;
};

export type VietnamWatchItem = {
  ticker: string;
  status?: 'ok' | 'unavailable' | string;
  reason?: string | null;
  name?: string | null;
  companyName?: string | null;
  entity?: string | null;
  exchange?: string | null;
  market?: string | null;
  securityType?: string | null;
  industry?: string | null;
  sector?: string | null;
  metadataSource?: string | null;
  symbolMetadata?: VietnamSymbolMetadata;
  issuer?: string | null;
  lotSize?: number | null;
  listedShares?: number | null;
  listedDate?: string | null;
  marketIndex?: string | null;
  source?: string | null;
  primarySource?: string | null;
  actualSource?: string | null;
  fallbackUsed?: boolean;
  fallbackReason?: string | null;
  referenceSource?: string | null;
  foreignFlowSource?: string | null;
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
  dailyClose?: number | null;
  priceDate?: string | null;
  ohlcvDate?: string | null;
  dailyStockPriceDate?: string | null;
  dailyStockPriceDateMatch?: 'matched' | 'mismatched' | 'unknown' | 'unavailable' | string | null;
  dailyStockPriceStalenessReason?: string | null;
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
    referencePrice?: number | null;
    ceilingPrice?: number | null;
    floorPrice?: number | null;
    distanceToLimitPct?: number | null;
    nearLimit?: boolean;
    source?: string | null;
    status?: string | null;
    referenceSource?: string | null;
  };
  dailyStockPrice?: VietnamDailyStockPrice;
  ssiReferencePrice?: number | null;
  ssiCeilingPrice?: number | null;
  ssiFloorPrice?: number | null;
  ssiAdjustedClose?: number | null;
  ssiForeignNetVolume?: number | null;
  ssiForeignNetValue?: number | null;
  ssiMatchedVolume?: number | null;
  ssiMatchedValue?: number | null;
  ssiPutThroughVolume?: number | null;
  ssiPutThroughValue?: number | null;
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
  foreign: {
    buy?: number | null;
    sell?: number | null;
    net?: number | null;
    buyValue?: number | null;
    sellValue?: number | null;
    netValue?: number | null;
    source?: string | null;
    status?: string | null;
    netUnit?: string | null;
    date?: string | null;
    dateMatch?: string | null;
    buyRawField?: string | null;
    sellRawField?: string | null;
    signal?: string | null;
  };
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
    high52w?: number | null;
    high52wDate?: string | null;
    low52w?: number | null;
    low52wDate?: string | null;
    highLow52wHistoryCount?: number | null;
    highLow52wCoverageStatus?: string | null;
    avgVolume10d?: number | null;
    avgVolume10dHistoryCount?: number | null;
    avgVolume10dCoverageStatus?: string | null;
    avgVolume3m?: number | null;
    avgVolume3mHistoryCount?: number | null;
    avgVolume3mCoverageStatus?: string | null;
    priceVsReferencePct?: number | null;
    priceVsReferenceStatus?: string | null;
    dailyRangePct?: number | null;
    dailyRangeStatus?: string | null;
    ssiDerivedMetricsStatus?: string | null;
    ssiDerivedMetricsSource?: string | null;
    foreignNet5D?: number | null;
    foreignNet20D?: number | null;
    foreignNetLatest?: number | null;
    foreignNet5dLatestAvailable?: number | null;
    foreignNet20dLatestAvailable?: number | null;
    foreignNetLatestAvailableDate?: string | null;
    foreignNetHistoryCount?: number | null;
    shortTermZones?: {
      status?: string | null;
      reasonCode?: string | null;
      source?: string | null;
      timeframe?: string | null;
      lookbackSessions?: number | null;
      support?: Array<{ lower?: number | null; upper?: number | null }>;
      resistance?: Array<{ lower?: number | null; upper?: number | null }>;
    } | null;
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
  news: Array<{
    title?: string;
    url?: string | null;
    rawUrl?: string | null;
    id?: string | null;
    ticker?: string | null;
    source?: string;
    provider?: string | null;
    providerMode?: string | null;
    sourceName?: string | null;
    sourceUrl?: string | null;
    publishedAt?: string | number | null;
    publishedDate?: string | number | null;
    publishedTime?: string | number | null;
    createdAt?: string | number | null;
    date?: string | number | null;
    time?: string | number | null;
    timestamp?: string | number | null;
    summary?: string;
    category?: string | null;
    author?: string | null;
    imageUrl?: string | null;
    contentAvailable?: boolean | null;
    content?: string | null;
    fetchedAt?: string | null;
    rightsStatus?: string | null;
    tickerRelevance?: Record<string, unknown> | null;
  }>;
  newsStatus?: {
    status?: string | null;
    source?: string | null;
    provider?: string | null;
    providerMode?: string | null;
    message?: string | null;
    reasonCode?: string | null;
    rightsStatus?: string | null;
    count?: number | null;
    providerItemsCount?: number | null;
    items?: unknown[];
  };
  intradayTimeframe?: string | null;
  intradayRequestedTimeframe?: string | null;
  intradayGranularity?: string | null;
  intradayActualGranularity?: string | null;
  intradayGranularitySeconds?: number | null;
  intradayActualGranularitySeconds?: number | null;
  intradayGranularityLabel?: string | null;
  intradayCadenceStatus?: string | null;
  intradayLatestDate?: string | null;
  dailyPriceDate?: string | null;
  dateMatch?: string | null;
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
    ticker?: string | null;
  }>;
  intradayPulse?: {
    latest1hClose?: number | null;
    latest1hOpen?: number | null;
    latest1hHigh?: number | null;
    latest1hLow?: number | null;
    latest1hVolume?: number | null;
    latest1hChange?: number | null;
    latest1hChangePercent?: number | null;
    latestIntradayClose?: number | null;
    latestIntradayOpen?: number | null;
    latestIntradayHigh?: number | null;
    latestIntradayLow?: number | null;
    latestIntradayVolume?: number | null;
    intradayChange?: number | null;
    intradayChangePercent?: number | null;
    sessionHighFrom1H?: number | null;
    sessionLowFrom1H?: number | null;
    sessionRangePctFrom1H?: number | null;
    sessionVolumeFrom1H?: number | null;
    sessionHighFromIntraday?: number | null;
    sessionLowFromIntraday?: number | null;
    sessionRangePctFromIntraday?: number | null;
    sessionVolumeFromIntraday?: number | null;
    sessionCandlesCount?: number | null;
    cumulative1hVolume?: number | null;
    loadedCandlesTotalVolume?: number | null;
    direction?: 'up' | 'down' | 'flat' | 'unknown' | null;
    rangePercent?: number | null;
    volumeVsAvg1h?: number | null;
    intradayVolumeVsAverage?: number | null;
    intradayGranularity?: string | null;
    intradayRequestedTimeframe?: string | null;
    intradayActualGranularity?: string | null;
    intradayGranularitySeconds?: number | null;
    intradayActualGranularitySeconds?: number | null;
    intradayGranularityLabel?: string | null;
    intradayCadenceStatus?: string | null;
    intradayLatestDate?: string | null;
    dailyPriceDate?: string | null;
    dateMatch?: string | null;
  } | null;
  intradayLabels?: string[];
  intradayDetails?: Array<{
    label: string;
    severity: 'info' | 'caution' | 'risk';
    reason: string;
    inputs?: Record<string, unknown>;
  }>;
  intradayStatus?: {
    status?: string | null;
    source?: string | null;
    message?: string | null;
    reasonCode?: string | null;
    classification?: string | null;
    count?: number | null;
    ticker?: string | null;
    intradayLatestDate?: string | null;
    dailyPriceDate?: string | null;
    dateMatch?: string | null;
    intradayGranularity?: string | null;
    intradayRequestedTimeframe?: string | null;
    intradayActualGranularity?: string | null;
    intradayGranularitySeconds?: number | null;
    intradayActualGranularitySeconds?: number | null;
    intradayGranularityLabel?: string | null;
    intradayCadenceStatus?: string | null;
    diagnostics?: Record<string, unknown> | null;
  };
  realtimeSource?: string | null;
  realtimeSnapshot?: VietnamRealtimeQuote | null;
  realtimeStatus?: {
    status?: string | null;
    source?: string | null;
    message?: string | null;
    reasonCode?: string | null;
    classification?: string | null;
    streamingStatus?: string | null;
    runtimeStatus?: string | null;
    managerState?: string | null;
    cacheStatus?: string | null;
    diagnostics?: Record<string, unknown> | null;
  };
  tradeTapeSource?: string | null;
  tradeTape?: VietnamRealtimeTrade[];
  tradeTapeStatus?: {
    status?: string | null;
    source?: string | null;
    message?: string | null;
    reasonCode?: string | null;
    classification?: string | null;
    count?: number | null;
    fetchedAt?: string | null;
    diagnostics?: Record<string, unknown> | null;
  };
  orderBookSource?: string | null;
  orderBook?: VietnamOrderBook | null;
  orderBookStatus?: VietnamOptionalLiveStatus;
  diagnostics?: {
    realtime?: Record<string, unknown> | null;
    tradeTape?: Record<string, unknown> | null;
    orderBook?: Record<string, unknown> | null;
  };
  dataQualitySummary?: VietnamDataQualitySummary;
  cacheStatus: Record<string, string>;
  cacheLastFetchedAt: Record<string, string | null>;
  cacheNextRefreshAt: Record<string, string | null>;
  cacheErrors: Record<string, string>;
  error?: string | null;
};

export type VietnamSymbolMetadata = {
  status?: 'ok' | 'unavailable' | string | null;
  qualityStatus?: 'complete' | 'partial' | 'unavailable' | 'unknown' | string | null;
  completeness?: number | null;
  reason?: string | null;
  symbol?: string | null;
  exchange?: string | null;
  market?: string | null;
  securityType?: string | null;
  name?: string | null;
  nameEn?: string | null;
  industry?: string | null;
  sector?: string | null;
  issuer?: string | null;
  lotSize?: number | null;
  listedShares?: number | null;
  listedDate?: string | null;
  source?: string | null;
  missingFields?: string[];
  fieldCoverage?: Record<string, boolean>;
  diagnostics?: Record<string, unknown>;
};

export type VietnamCompanyNewsResponse = {
  ticker?: string | null;
  status: 'ok' | 'disabled' | 'unavailable' | 'stale' | string;
  source?: string | null;
  provider?: string | null;
  providerMode?: string | null;
  reasonCode?: string | null;
  rightsStatus?: string | null;
  message?: string | null;
  fetchedAt?: string | null;
  cache?: {
    status?: string | null;
    lastFetchedAt?: string | null;
    nextRefreshAt?: string | null;
  };
  news: VietnamWatchItem['news'];
};

export type VietnamDailyStockPrice = {
  status?: 'ok' | 'unavailable' | string | null;
  qualityStatus?: 'ok' | 'partial' | 'unavailable' | string | null;
  reason?: string | null;
  date?: string | null;
  dateMatch?: 'matched' | 'mismatched' | 'unknown' | 'unavailable' | string | null;
  stalenessReason?: string | null;
  referencePrice?: number | null;
  ceilingPrice?: number | null;
  floorPrice?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  adjustedClose?: number | null;
  matchedVolume?: number | null;
  matchedValue?: number | null;
  putThroughVolume?: number | null;
  putThroughValue?: number | null;
  totalVolume?: number | null;
  totalValue?: number | null;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
  source?: string | null;
  missingFields?: string[];
  fieldCoverage?: Record<string, boolean>;
  units?: Record<string, string>;
  diagnostics?: Record<string, unknown>;
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
  requestedTickersCount?: number | null;
  returnedRowsCount?: number | null;
  missingTickers?: string[];
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
  requestedTickersCount?: number | null;
  returnedRowsCount?: number | null;
  missingTickers?: string[];
  dataQuality: VietnamWatchlistHealthResponse;
  cacheMetadata: VietnamCacheMetadata;
  watchlist: VietnamWatchItem[];
  ruleMetadata?: { ruleSetName?: string; ruleSetVersion?: string; noRecommendation?: boolean };
  formulas: Record<string, string>;
};

export type VietnamRealtimeQuote = {
  symbol?: string | null;
  ticker?: string | null;
  fetchedAt?: string | null;
  price?: number | null;
  change?: number | null;
  changePct?: number | null;
  ceilingPrice?: number | null;
  floorPrice?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
  value?: number | null;
  bidLevels?: Array<{ price?: number | null; volume?: number | null }>;
  askLevels?: Array<{ price?: number | null; volume?: number | null }>;
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
  cachedAt?: string | null;
  cacheTtlSeconds?: number | null;
  snapshotSource?: 'persisted' | string | null;
  snapshotCapturedAt?: string | null;
  snapshotTradingDate?: string | null;
  snapshotSchemaVersion?: number | null;
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
  source: string;
  status: 'ok' | 'disabled' | 'not_implemented' | 'unavailable' | 'error' | 'stale' | string;
  error?: string | null;
  errorDetail?: string | null;
  rawError?: string | null;
};

export type VietnamRealtimeResponse = {
  market: 'VN';
  source: string;
  status: 'ok' | 'disabled' | 'not_implemented' | 'unavailable' | 'error' | 'stale' | string;
  error?: string | null;
  errorDetail?: string | null;
  rawError?: string | null;
  reasonCode?: string | null;
  classification?: string | null;
  statusMessage?: string | null;
  requestedTickers: string[];
  quotes: VietnamRealtimeQuote[];
  cache: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
  streamingStatus?: string | null;
  managerState?: string | null;
  runtimeStatus?: string | null;
  cacheStatus?: string | null;
  parsedStreamingRows?: number | null;
};

export type VietnamRealtimeTrade = {
  ticker?: string | null;
  symbol?: string | null;
  time?: string | null;
  timestamp?: string | null;
  timestampDisplay?: string | null;
  price?: number | null;
  volume?: number | null;
  value?: number | null;
  side?: string | null;
  sideLabel?: string | null;
  sideIfAvailable?: string | null;
  change?: number | null;
  changePct?: number | null;
  sequence?: string | null;
  sequenceIfAvailable?: string | null;
  matchType?: string | null;
  id?: string | null;
  rawType?: string | null;
  source: string;
};

export type VietnamRealtimeTradesResponse = {
  market: 'VN';
  source: string;
  symbol: string;
  status: 'ok' | 'disabled' | 'not_implemented' | 'unavailable' | 'error' | 'stale' | string;
  error?: string | null;
  errorDetail?: string | null;
  rawError?: string | null;
  reasonCode?: string | null;
  classification?: string | null;
  statusMessage?: string | null;
  streamingStatus?: string | null;
  managerState?: string | null;
  runtimeStatus?: string | null;
  cacheStatus?: string | null;
  trades: VietnamRealtimeTrade[];
  note?: string | null;
  cache: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
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
  status?: 'ok' | 'unavailable' | string;
  reason?: string | null;
  source: string;
  primarySource?: string | null;
  actualSource?: string | null;
  fallbackUsed?: boolean;
  fallbackReason?: string | null;
  timeframe: string;
  range: '1M' | '3M' | '6M' | '1Y' | string;
  latestDate?: string | null;
  points: VietnamChartPoint[];
  candles?: VietnamChartPoint[];
};

export type VietnamIntradayChartResponse = {
  ticker: string;
  interval: '1m';
  tradingDate: string;
  timezone: 'Asia/Ho_Chi_Minh' | string;
  status: 'ready' | 'unavailable' | 'failed' | string;
  reason?: string | null;
  sessionState: 'completed' | 'pre_open' | 'continuous_morning' | 'lunch' | 'continuous_afternoon' | 'atc' | 'closed' | 'unknown';
  freshness: 'completed' | 'updating' | 'delayed' | 'stale' | 'unavailable';
  lastProviderRefreshAt?: string | null;
  newestBarAgeSeconds?: number | null;
  currentBarState: 'completed' | 'provisional' | 'inferred_final' | 'none';
  bars: VietnamChartPoint[];
  source: { provider?: string | null; dataset?: string | null };
  cache: {
    status?: 'hit' | 'miss' | 'refresh' | 'stale' | string | null;
    isStale?: boolean;
    fetchedAt?: string | null;
    expiresAt?: string | null;
  };
  diagnostics: {
    requestedDate?: string | null;
    providerDate?: string | null;
    returnedRows?: number | null;
    usableBars?: number | null;
    rejectedRows?: number | null;
    duplicateMinuteBuckets?: number | null;
    result?: string | null;
    recovery?: string | null;
    failureClass?: string | null;
  };
};

export type VietnamCompanyProfile = {
  ticker: string;
  name?: string | null;
  nameEn?: string | null;
  exchange?: string | null;
  market?: string | null;
  industry?: string | null;
  sector?: string | null;
  securityType?: string | null;
  issuer?: string | null;
  lotSize?: number | null;
  listedShares?: number | null;
  listedDate?: string | null;
  source?: string | null;
  status: 'ok' | 'unavailable' | 'missing' | string;
  qualityStatus?: 'complete' | 'partial' | 'unavailable' | 'unknown' | string | null;
  completeness?: number | null;
  missingFields?: string[];
  fieldCoverage?: Record<string, boolean>;
  diagnostics?: Record<string, unknown>;
};

export type VietnamCompanyPrice = {
  latestPrice?: number | null;
  dailyClose?: number | null;
  referencePrice?: number | null;
  ceilingPrice?: number | null;
  floorPrice?: number | null;
  priceDate?: string | null;
  source?: string | null;
  canonicalSource?: string | null;
  referenceSource?: string | null;
  status: 'ok' | 'missing' | string;
};

export type VietnamCompanyTradingStats = {
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
  value?: number | null;
  source?: string | null;
  status: 'ok' | 'missing' | string;
};

export type VietnamCompanyForeignFlow = {
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
  date?: string | null;
  dateMatch?: 'matched' | 'mismatched' | 'unknown' | 'unavailable' | string | null;
  volumeUnit?: string | null;
  valueUnit?: string | null;
  source?: string | null;
  status: 'ok' | 'missing' | string;
};

export type VietnamCompanyTechnical = {
  ma20?: number | null;
  ma50?: number | null;
  rsi14?: number | null;
  bollingerUpper?: number | null;
  bollingerMiddle?: number | null;
  bollingerLower?: number | null;
  high52w?: number | null;
  high52wDate?: string | null;
  low52w?: number | null;
  low52wDate?: string | null;
  highLow52wHistoryCount?: number | null;
  highLow52wCoverageStatus?: string | null;
  avgVolume10d?: number | null;
  avgVolume10dHistoryCount?: number | null;
  avgVolume10dCoverageStatus?: string | null;
  avgVolume3m?: number | null;
  avgVolume3mHistoryCount?: number | null;
  avgVolume3mCoverageStatus?: string | null;
  priceVsReferencePct?: number | null;
  priceVsReferenceStatus?: string | null;
  dailyRangePct?: number | null;
  dailyRangeStatus?: string | null;
  ssiDerivedMetricsStatus?: string | null;
  ssiDerivedMetricsSource?: string | null;
  source?: string | null;
  status: 'ok' | 'missing' | string;
};

export type VietnamCompanyIntraday = {
  candles?: Array<{
    timestamp?: number | null;
    dateTime?: string | null;
    open?: number | null;
    high?: number | null;
    low?: number | null;
    close?: number | null;
    volume?: number | null;
    ticker?: string | null;
  }>;
  pulse?: {
    latest1hClose?: number | null;
    latest1hChange?: number | null;
    latest1hChangePercent?: number | null;
    latest1hVolume?: number | null;
    sessionVolumeFrom1H?: number | null;
    latestIntradayClose?: number | null;
    intradayChange?: number | null;
    intradayChangePercent?: number | null;
    latestIntradayVolume?: number | null;
    sessionVolumeFromIntraday?: number | null;
    intradayRequestedTimeframe?: string | null;
    intradayActualGranularity?: string | null;
    intradayActualGranularitySeconds?: number | null;
    intradayCadenceStatus?: string | null;
    direction?: 'up' | 'down' | 'flat' | 'unknown' | null;
  } | null;
  requestedTimeframe?: string | null;
  granularity?: string | null;
  actualGranularity?: string | null;
  granularitySeconds?: number | null;
  actualGranularitySeconds?: number | null;
  granularityLabel?: string | null;
  cadenceStatus?: string | null;
  latestDate?: string | null;
  dailyPriceDate?: string | null;
  dateMatch?: string | null;
  source?: string | null;
  status: 'ok' | 'disabled' | 'unavailable' | 'error' | string;
  message?: string | null;
  diagnostics?: Record<string, unknown> | null;
};

export type VietnamDataQualityIssue = {
  code?: string | null;
  severity?: 'info' | 'warning' | 'error' | string | null;
  message?: string | null;
  fields?: Record<string, unknown>;
};

export type VietnamDataQualityChecks = {
  dailyOhlc?: string | null;
  dailyStockPrice?: string | null;
  finalCloseStatus?: string | null;
  adjustedPriceStatus?: string | null;
  intraday?: string | null;
  realtime?: string | null;
  tradeTape?: string | null;
  profile?: string | null;
  news?: string | null;
};

export type VietnamDataQualitySummary = {
  overallStatus?: 'ok' | 'partial' | 'unavailable' | string | null;
  canonicalPriceSource?: string | null;
  issues?: VietnamDataQualityIssue[];
  checks?: VietnamDataQualityChecks;
};

export type VietnamCompanySourceCoverageItem = {
  block: string;
  source?: string | null;
  status: string;
};

export type VietnamCompanyPlaceholderBlock = {
  items: Array<Record<string, unknown>>;
  status: 'not_implemented' | string;
  source?: string | null;
  message?: string | null;
};

export type VietnamCompanyResearchResponse = {
  ticker: string;
  status: 'ok' | 'partial' | 'unavailable' | string;
  profile: VietnamCompanyProfile;
  price: VietnamCompanyPrice;
  tradingStats: VietnamCompanyTradingStats;
  dailyStockPrice?: VietnamDailyStockPrice;
  foreignFlow: VietnamCompanyForeignFlow;
  technical: VietnamCompanyTechnical;
  intraday?: VietnamCompanyIntraday;
  realtimeSnapshot?: VietnamRealtimeQuote | null;
  realtimeStatus?: {
    status: 'ok' | 'disabled' | 'not_implemented' | 'unavailable' | 'error' | string;
    source?: string | null;
    message?: string | null;
    reasonCode?: string | null;
    classification?: string | null;
  };
  tradeTape?: VietnamRealtimeTrade[];
  tradeTapeStatus?: {
    status: 'ok' | 'disabled' | 'not_implemented' | 'unavailable' | 'error' | string;
    source?: string | null;
    message?: string | null;
    reasonCode?: string | null;
    classification?: string | null;
  };
  orderBookSource?: string | null;
  orderBook?: VietnamOrderBook | null;
  orderBookStatus?: VietnamOptionalLiveStatus;
  diagnostics?: {
    realtime?: Record<string, unknown> | null;
    tradeTape?: Record<string, unknown> | null;
    orderBook?: Record<string, unknown> | null;
  };
  dataQualitySummary?: VietnamDataQualitySummary;
  sourceCoverage: VietnamCompanySourceCoverageItem[];
  news: VietnamCompanyPlaceholderBlock;
  financials: VietnamCompanyPlaceholderBlock;
  events: VietnamCompanyPlaceholderBlock;
  warnings: string[];
  errors: Record<string, unknown>;
};

export type VietnamIndexInfo = {
  indexId?: string | null;
  indexCode?: string | null;
  indexName?: string | null;
  exchange?: string | null;
  market?: string | null;
  source?: string | null;
  missingFields?: string[];
  fieldCoverage?: Record<string, boolean>;
};

export type VietnamIndexListResponse = {
  status: 'ok' | 'unavailable' | string;
  source: string;
  reason?: string | null;
  market?: string | null;
  rows: VietnamIndexInfo[];
  count: number;
  fallbackUsed?: boolean;
  diagnostics?: Record<string, unknown>;
};

export type VietnamDailyIndexRow = {
  status: 'ok' | string;
  qualityStatus?: 'complete' | 'partial' | string | null;
  indexCode: string;
  date?: string | null;
  dateMatch?: 'matched' | 'mismatched' | 'unknown' | string;
  indexValue?: number | null;
  change?: number | null;
  changePct?: number | null;
  totalVolume?: number | null;
  totalValue?: number | null;
  matchedVolume?: number | null;
  matchedValue?: number | null;
  putThroughVolume?: number | null;
  putThroughValue?: number | null;
  advances?: number | null;
  unchanged?: number | null;
  declines?: number | null;
  ceiling?: number | null;
  floor?: number | null;
  tradingSession?: string | null;
  exchange?: string | null;
  source: string;
  missingFields?: string[];
  fieldCoverage?: Record<string, boolean>;
};

export type VietnamDailyIndexResponse = {
  status: 'ok' | 'partial' | 'unavailable' | string;
  source: string;
  reason?: string | null;
  requestedIndexCodes: string[];
  latestDate?: string | null;
  rows: VietnamDailyIndexRow[];
  count: number;
  fallbackUsed?: boolean;
  diagnostics?: Record<string, unknown>;
};

export type VietnamIndexComponent = {
  indexCode?: string | null;
  symbol?: string | null;
  exchange?: string | null;
  market?: string | null;
  weight?: number | null;
  name?: string | null;
  source?: string | null;
  missingFields?: string[];
  fieldCoverage?: Record<string, boolean>;
};

export type VietnamIndexComponentsResponse = {
  status: 'ok' | 'unavailable' | string;
  source: string;
  reason?: string | null;
  indexCode: string;
  market?: string | null;
  rows: VietnamIndexComponent[];
  count: number;
  fallbackUsed?: boolean;
  diagnostics?: Record<string, unknown>;
};

export type VietnamCorporateActionEvent = {
  ticker: string;
  eventId?: string | null;
  eventType: 'cash_dividend' | 'stock_dividend' | 'bonus_share' | 'rights_issue' | 'stock_split' | 'merger' | 'listing_change' | 'meeting' | 'other' | 'unknown' | string;
  eventSubtype?: string | null;
  title?: string | null;
  status: 'upcoming' | 'recent' | 'past' | string;
  announcementDate?: string | null;
  exDate?: string | null;
  recordDate?: string | null;
  paymentDate?: string | null;
  effectiveDate?: string | null;
  cashDividendPerShare?: number | null;
  cashDividendCurrency?: string | null;
  stockDividendRatio?: string | null;
  bonusShareRatio?: string | null;
  rightsIssueRatio?: string | null;
  rightsIssuePrice?: number | null;
  splitRatio?: string | null;
  rightsRatio?: string | null;
  description?: string | null;
  source?: string | null;
  sourceUrl?: string | null;
  sourceDocumentUrl?: string | null;
  provider?: string | null;
  providerEventId?: string | null;
  lastUpdated?: string | null;
  rawAvailable?: boolean | null;
  confidence?: number | null;
  missingFields?: string[];
  lastCheckedAt?: string | null;
};

export type VietnamCorporateActionsResponse = {
  market: 'VN';
  status: 'ok' | 'disabled' | 'not_configured' | 'not_implemented' | 'unavailable' | 'partial' | 'error' | string;
  source?: string | null;
  provider?: string | null;
  lastCheckedAt?: string | null;
  requestedTickers: string[];
  monthsBack: number;
  events?: VietnamCorporateActionEvent[];
  items: VietnamCorporateActionEvent[];
  error?: string | null;
  errorDetail?: string | null;
  diagnostics?: Record<string, unknown>;
};

export type VietnamObservabilityResponse = {
  market: 'VN';
  status: 'ok' | 'error';
  mozyfin: {
    status?: string | null;
    source?: string | null;
    reason?: string | null;
  };
  dashboardRuntime: {
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
    status?: string | null;
    source?: string | null;
    reason?: string | null;
    legacyAllowed?: boolean;
    enabled?: boolean;
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
  ssiRealtime?: {
    status?: string | null;
    source?: string | null;
    reason?: string | null;
    enabled?: boolean | null;
  };
  ssiCore?: {
    status?: string | null;
    source?: string | null;
    reason?: string | null;
    enabled?: boolean | null;
  };
  ssiIntraday?: {
    status?: string | null;
    source?: string | null;
    reason?: string | null;
    enabled?: boolean | null;
  };
  ssiTradeTape?: {
    status?: string | null;
    source?: string | null;
    reason?: string | null;
    enabled?: boolean | null;
  };
};

const normalizeVietnamSsiDerivedMetricKeys = <T extends Record<string, unknown> | null | undefined>(metrics: T): T => {
  if (!metrics) return metrics;
  const normalized = { ...metrics };
  const aliases: Array<[source: string, target: string]> = [
    ['high52W', 'high52w'],
    ['low52W', 'low52w'],
    ['avgVolume10D', 'avgVolume10d'],
    ['avgVolume3M', 'avgVolume3m'],
  ];

  aliases.forEach(([source, target]) => {
    if (normalized[target] === undefined && normalized[source] !== undefined) {
      normalized[target] = normalized[source];
    }
  });

  return normalized as T;
};

const normalizeVietnamWatchlistResponse = (response: VietnamWatchlistResponse): VietnamWatchlistResponse => ({
  ...response,
  watchlist: (response.watchlist ?? []).map((item) => ({
    ...item,
    indicators: normalizeVietnamSsiDerivedMetricKeys(
      item.indicators as unknown as Record<string, unknown>,
    ) as VietnamWatchItem['indicators'],
  })),
});

const normalizeVietnamCompanyResearchResponse = (
  response: VietnamCompanyResearchResponse,
): VietnamCompanyResearchResponse => ({
  ...response,
  technical: normalizeVietnamSsiDerivedMetricKeys(
    response.technical as unknown as Record<string, unknown>,
  ) as VietnamCompanyTechnical,
});

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
    return normalizeVietnamWatchlistResponse(toCamelCase<VietnamWatchlistResponse>(response.data));
  },

  async getVietnamWatchlistHealth(tickers?: string[]): Promise<VietnamWatchlistHealthResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/watchlist/health', {
      params: tickers?.length ? { tickers: tickers.join(',') } : undefined,
      timeout: 120000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamWatchlistHealthResponse>(response.data);
  },

  async getVietnamChart(
    symbol: string,
    range = '6M',
    options?: { signal?: AbortSignal },
  ): Promise<VietnamChartResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/chart', {
      params: { symbol, range },
      timeout: 120000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamChartResponse>(response.data);
  },

  async getVietnamIntradayChart(
    ticker: string,
    tradingDate: string,
    options?: { forceRefresh?: boolean; signal?: AbortSignal },
  ): Promise<VietnamIntradayChartResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/intraday-chart', {
      params: {
        ticker,
        interval: '1m',
        date: tradingDate,
        ...(options?.forceRefresh ? { force_refresh: true } : {}),
      },
      timeout: 120000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamIntradayChartResponse>(response.data);
  },

  async getVietnamCompanyResearch(ticker: string, forceRefresh = false): Promise<VietnamCompanyResearchResponse> {
    const response = await apiClient.get(`/api/v1/stocks/vn/company/${encodeURIComponent(ticker)}`, {
      params: forceRefresh ? { force_refresh: true } : undefined,
      timeout: 120000,
    });
    const { toCamelCase } = await import('./utils');
    return normalizeVietnamCompanyResearchResponse(toCamelCase<VietnamCompanyResearchResponse>(response.data));
  },

  async getVietnamCompanyNews(
    ticker: string,
    options?: { signal?: AbortSignal },
  ): Promise<VietnamCompanyNewsResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/company-news', {
      params: { ticker },
      timeout: 30000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamCompanyNewsResponse>(response.data);
  },

  async getVietnamIndexList(market = 'HOSE'): Promise<VietnamIndexListResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/index-list', {
      params: market ? { market } : undefined,
      timeout: 30000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamIndexListResponse>(response.data);
  },

  async getVietnamDailyIndex(indexCodes = ['VNINDEX', 'VN30']): Promise<VietnamDailyIndexResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/daily-index', {
      params: { index_codes: indexCodes.join(',') },
      timeout: 30000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamDailyIndexResponse>(response.data);
  },

  async getVietnamIndexComponents(indexCode = 'VN30', market?: string): Promise<VietnamIndexComponentsResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/index-components', {
      params: {
        index_code: indexCode,
        ...(market ? { market } : {}),
      },
      timeout: 30000,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamIndexComponentsResponse>(response.data);
  },

  async getVietnamRealtimeQuotes(tickers: string[], options?: { signal?: AbortSignal }): Promise<VietnamRealtimeResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/realtime', {
      params: { tickers: tickers.join(',') },
      timeout: 30000,
      signal: options?.signal,
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
