import apiClient from './index';
import { normalizeVietnamTicker, VIETNAM_WATCHLIST_MAX_SIZE } from '../utils/vietnamWatchlist';

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
    session?: Record<string, unknown> | null;
    adjustment?: Record<string, unknown> | null;
    liveChannels?: Record<string, unknown> | null;
    dailyStockPriceCapabilities?: Record<string, unknown> | null;
    foreignFlow?: Record<string, unknown> | null;
    intraday?: Record<string, unknown> | null;
    profile?: Record<string, unknown> | null;
    qualityIssues?: Array<Record<string, unknown>> | null;
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
  dataDate?: string | null;
  requestedDate?: string | null;
  providerSessionDate?: string | null;
  freshnessStatus?: 'current_session_provisional' | 'latest_completed_session' | 'previous_session_during_live_market' | 'stale_history' | 'unavailable' | string | null;
  isCurrentSession?: boolean | null;
  isProvisional?: boolean | null;
  isCompletedSession?: boolean | null;
  isStale?: boolean | null;
  sessionLag?: number | null;
  providerVersion?: string | null;
  endpoint?: string | null;
  currentMarketSession?: string | null;
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
  foreignFieldPresence?: Record<string, string>;
  foreignFieldAliases?: Record<string, string>;
  normalizationIssues?: Array<{ field?: string; issue?: string }>;
  foreignFlowValueState?: 'explicit_zero' | 'nonzero' | 'partial' | 'unavailable';
  capabilities?: VietnamDailyStockPriceCapabilities;
  diagnostics?: Record<string, unknown>;
};

export type VietnamDailyStockPriceCapabilities = {
  priceLimitsStatus: 'ready' | 'partial' | 'unavailable';
  matchedStatsStatus: 'ready' | 'partial' | 'unavailable';
  putThroughStatus: 'ready' | 'partial' | 'unavailable';
  foreignFlowStatus: 'ready' | 'partial' | 'unavailable';
  sessionMetadataStatus: 'ready' | 'partial' | 'unavailable';
  overallStatus: 'ready' | 'partial' | 'unavailable';
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

export type VietnamForeignFlowDataState = 'ready' | 'partial' | 'stale' | 'empty' | 'unavailable';

export type VietnamForeignFlowHistoryRow = {
  tradingDate: string;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
};

export type VietnamForeignFlowHistoryWindow = {
  requestedSessions: number;
  coveredSessions: number;
  complete: boolean;
  startDate?: string | null;
  endDate?: string | null;
  cumulativeForeignNetVolume?: number | null;
  cumulativeForeignNetValue?: number | null;
  netVolumeContributingSessions: number;
  netValueContributingSessions: number;
  positiveNetVolumeSessions: number;
  negativeNetVolumeSessions: number;
  zeroNetVolumeSessions: number;
  nullNetVolumeSessions: number;
  positiveNetValueSessions: number;
  negativeNetValueSessions: number;
  zeroNetValueSessions: number;
  nullNetValueSessions: number;
};

export type VietnamForeignFlowAnalyticsEvent = { value: number; tradingDate: string };
export type VietnamForeignFlowAnalyticsWindow = {
  requestedSessions: 5 | 20 | 60;
  observedSessions: number;
  coveredSessions: number;
  complete: boolean;
  startDate?: string | null;
  endDate?: string | null;
  netSum?: number | null;
  averageNet?: number | null;
  averageAbsoluteNet?: number | null;
  netBuySessionCount: number;
  netSellSessionCount: number;
  zeroSessionCount: number;
  unavailableSessionCount: number;
  maxNetBuy?: VietnamForeignFlowAnalyticsEvent | null;
  maxNetSell?: VietnamForeignFlowAnalyticsEvent | null;
};
export type VietnamForeignFlowAnalyticsFamily = {
  latest?: { value?: number | null; tradingDate: string } | null;
  windows: Record<'5' | '20' | '60', VietnamForeignFlowAnalyticsWindow>;
  currentStreak: {
    direction: 'net_buy' | 'net_sell' | 'none' | 'unavailable';
    sessions: number;
    startDate?: string | null;
    endDate?: string | null;
    basis: 'accepted_provider_rows';
  };
  latestReversal?: {
    fromDirection: 'net_buy' | 'net_sell';
    toDirection: 'net_buy' | 'net_sell';
    tradingDate: string;
    previousTradingDate: string;
    currentValue: number;
    previousValue: number;
  } | null;
  comparison: {
    latestValue?: number | null;
    sampleCount20d: number;
    sampleCount60d: number;
    averageNet20d?: number | null;
    averageAbsoluteNet20d?: number | null;
    averageNet60d?: number | null;
    averageAbsoluteNet60d?: number | null;
    signedPercentile20d?: number | null;
    signedPercentile60d?: number | null;
    absolutePercentile20d?: number | null;
    absolutePercentile60d?: number | null;
    zScore20d?: number | null;
    zScore60d?: number | null;
    unusualFlowState: 'unavailable' | 'normal' | 'elevated';
    unusualFlowBasis: string[];
  };
};
export type VietnamForeignFlowSymbolAnalytics = {
  basis: 'accepted_provider_rows';
  maxSessions: 60;
  observedSessions: number;
  value: VietnamForeignFlowAnalyticsFamily;
  volume: VietnamForeignFlowAnalyticsFamily;
  rollingSeries: Array<{
    tradingDate: string;
    rollingNet5dValue?: number | null;
    rollingNet20dValue?: number | null;
    rollingNet5dVolume?: number | null;
    rollingNet20dVolume?: number | null;
  }>;
};
export type VietnamForeignFlowSymbolHistoryResponse = {
  ticker: string;
  source: 'ssi_fastconnect';
  sourceEndpoint: 'daily_stock_price';
  volumeUnit: 'shares';
  valueUnit: 'VND';
  finality: 'daily_available';
  dataState: 'ready' | 'empty' | 'stale' | 'unavailable';
  freshness: 'fresh' | 'stale' | 'empty' | 'unavailable';
  rows: VietnamForeignFlowHistoryRow[];
  windows: Record<'5' | '20' | '60', VietnamForeignFlowHistoryWindow>;
  analytics?: VietnamForeignFlowSymbolAnalytics | null;
  latestRow?: VietnamForeignFlowHistoryRow | null;
  requested: {
    mode: 'recent_sessions' | 'date_range';
    requestedLimit?: number | null;
    requestedFromDate?: string | null;
    requestedToDate?: string | null;
    returnedSessionCount: number;
  };
  coverage: {
    requestedSessions?: number | null;
    coveredSessions: number;
    complete?: boolean | null;
    startDate?: string | null;
    endDate?: string | null;
  };
  fetchedAt: string;
  staleReason?: string | null;
  failureClass?: string | null;
  providerVersion?: 'v3';
  cacheState?: 'hit' | 'miss' | 'refresh' | 'stale_hit' | 'unavailable';
  cacheAgeSeconds?: number | null;
};

type VietnamForeignFlowSymbolHistoryCamelResponse = Omit<VietnamForeignFlowSymbolHistoryResponse, 'analytics'> & {
  analytics?: Record<string, unknown> | null;
};

const normalizeForeignFlowAnalyticsFamily = (raw: unknown): VietnamForeignFlowAnalyticsFamily => {
  const family = (raw ?? {}) as VietnamForeignFlowAnalyticsFamily & {
    comparison?: Record<string, unknown>;
  };
  const comparison = (family.comparison ?? {}) as Record<string, unknown>;
  return {
    ...family,
    comparison: {
      ...family.comparison,
      sampleCount20d: Number(comparison.sampleCount20D ?? comparison.sampleCount20d ?? 0),
      sampleCount60d: Number(comparison.sampleCount60D ?? comparison.sampleCount60d ?? 0),
      averageNet20d: (comparison.averageNet20D as number | null | undefined) ?? (comparison.averageNet20d as number | null | undefined) ?? null,
      averageAbsoluteNet20d: (comparison.averageAbsoluteNet20D as number | null | undefined) ?? (comparison.averageAbsoluteNet20d as number | null | undefined) ?? null,
      averageNet60d: (comparison.averageNet60D as number | null | undefined) ?? (comparison.averageNet60d as number | null | undefined) ?? null,
      averageAbsoluteNet60d: (comparison.averageAbsoluteNet60D as number | null | undefined) ?? (comparison.averageAbsoluteNet60d as number | null | undefined) ?? null,
      signedPercentile20d: (comparison.signedPercentile20D as number | null | undefined) ?? (comparison.signedPercentile20d as number | null | undefined) ?? null,
      signedPercentile60d: (comparison.signedPercentile60D as number | null | undefined) ?? (comparison.signedPercentile60d as number | null | undefined) ?? null,
      absolutePercentile20d: (comparison.absolutePercentile20D as number | null | undefined) ?? (comparison.absolutePercentile20d as number | null | undefined) ?? null,
      absolutePercentile60d: (comparison.absolutePercentile60D as number | null | undefined) ?? (comparison.absolutePercentile60d as number | null | undefined) ?? null,
      zScore20d: (comparison.zScore20D as number | null | undefined) ?? (comparison.zScore20d as number | null | undefined) ?? null,
      zScore60d: (comparison.zScore60D as number | null | undefined) ?? (comparison.zScore60d as number | null | undefined) ?? null,
    } as VietnamForeignFlowAnalyticsFamily['comparison'],
  };
};

export const normalizeVietnamForeignFlowSymbolHistoryResponse = (
  data: VietnamForeignFlowSymbolHistoryCamelResponse,
): VietnamForeignFlowSymbolHistoryResponse => ({
  ...data,
  analytics: data.analytics ? (() => {
    const analytics = data.analytics as Record<string, unknown>;
    const rollingSeries = (analytics.rollingSeries ?? []) as Array<Record<string, number | string | null | undefined>>;
    return {
    ...analytics,
    value: normalizeForeignFlowAnalyticsFamily(analytics.value),
    volume: normalizeForeignFlowAnalyticsFamily(analytics.volume),
    rollingSeries: rollingSeries.map((row) => ({
      tradingDate: String(row.tradingDate ?? ''),
      rollingNet5dValue: (row.rollingNet5DValue as number | null | undefined) ?? (row.rollingNet5dValue as number | null | undefined) ?? null,
      rollingNet20dValue: (row.rollingNet20DValue as number | null | undefined) ?? (row.rollingNet20dValue as number | null | undefined) ?? null,
      rollingNet5dVolume: (row.rollingNet5DVolume as number | null | undefined) ?? (row.rollingNet5dVolume as number | null | undefined) ?? null,
      rollingNet20dVolume: (row.rollingNet20DVolume as number | null | undefined) ?? (row.rollingNet20dVolume as number | null | undefined) ?? null,
    })),
  } as VietnamForeignFlowSymbolAnalytics;
  })() : null,
});

export type VietnamForeignFlowBatchSymbol = {
  ticker: string;
  dataState: Exclude<VietnamForeignFlowDataState, 'partial'>;
  freshness: 'fresh' | 'stale' | 'empty' | 'unavailable';
  failureClass?: string | null;
  staleReason?: string | null;
  latestTradingDate?: string | null;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
  foreignNetVolume5d?: number | null;
  foreignNetValue5d?: number | null;
  foreignNetVolume20d?: number | null;
  foreignNetValue20d?: number | null;
  coveredSessions5d: number;
  complete5d: boolean;
  windowEndDate5d?: string | null;
  coveredSessions20d: number;
  complete20d: boolean;
  windowEndDate20d?: string | null;
  source: 'ssi_fastconnect';
  sourceEndpoint: 'daily_stock_price';
  volumeUnit: 'shares';
  valueUnit: 'VND';
  finality: 'daily_available';
  fetchedAt: string;
};

export type VietnamForeignFlowRankingEntry = {
  ticker: string;
  value: number;
  tradingDate?: string | null;
  coveredSessions: number;
  complete: boolean;
  dataState: 'ready' | 'stale';
};

export type VietnamForeignFlowRankingPair = {
  topBuy: VietnamForeignFlowRankingEntry[];
  topSell: VietnamForeignFlowRankingEntry[];
};

export type VietnamForeignFlowBatchResponse = {
  source: 'ssi_fastconnect';
  sourceEndpoint: 'daily_stock_price';
  volumeUnit: 'shares';
  valueUnit: 'VND';
  finality: 'daily_available';
  requestedTickers: string[];
  normalizedTickers: string[];
  requestedCount: number;
  normalizedCount: number;
  returnedCount: number;
  usableCount: number;
  freshCount: number;
  staleCount: number;
  emptyCount: number;
  unavailableCount: number;
  coverageRatio: number;
  complete: boolean;
  dataState: VietnamForeignFlowDataState;
  rows: VietnamForeignFlowBatchSymbol[];
  rankings: {
    latestNetValue: VietnamForeignFlowRankingPair;
    netValue5d: VietnamForeignFlowRankingPair;
    netValue20d: VietnamForeignFlowRankingPair;
  };
  fetchedAt: string;
};

export type VietnamForeignFlowWatchlistAvailability = 'ready' | 'partial' | 'unavailable';
export type VietnamForeignFlowWatchlistWindow = 1 | 5 | 20 | 60;

export type VietnamForeignFlowWatchlistItem = {
  ticker: string;
  availability: VietnamForeignFlowWatchlistAvailability;
  dataState: VietnamForeignFlowWatchlistAvailability;
  failureClass?: string | null;
  latestSession?: string | null;
  sourceFreshness: 'current' | 'latest_completed' | 'stale' | 'unknown';
  sourceSessionLag?: number | null;
  fetchedAt: string;
  cacheState: 'hit' | 'miss' | 'refresh' | 'stale_hit' | 'unavailable';
  cacheAgeSeconds?: number | null;
  actualSessionCount: number;
  requestedSessionCount: VietnamForeignFlowWatchlistWindow;
  complete: boolean;
  buyValue1d?: number | null;
  sellValue1d?: number | null;
  netValue1d?: number | null;
  buyValue5d?: number | null;
  sellValue5d?: number | null;
  netValue5d?: number | null;
  buyValue20d?: number | null;
  sellValue20d?: number | null;
  netValue20d?: number | null;
  buyValue60d?: number | null;
  sellValue60d?: number | null;
  netValue60d?: number | null;
  buyVolume1d?: number | null;
  sellVolume1d?: number | null;
  netVolume1d?: number | null;
  buyVolume5d?: number | null;
  sellVolume5d?: number | null;
  netVolume5d?: number | null;
  buyVolume20d?: number | null;
  sellVolume20d?: number | null;
  netVolume20d?: number | null;
  buyVolume60d?: number | null;
  sellVolume60d?: number | null;
  netVolume60d?: number | null;
  buyStreak?: number | null;
  sellStreak?: number | null;
  streakMetricBasis: 'foreign_net_value';
  containsProviderAnomaly: boolean;
  anomalySessions: string[];
  anomalyCount: number;
  source: 'ssi_fastconnect';
  sourceEndpoint: 'daily_stock_price';
  displayFinality?: 'current_session_provisional' | 'completed_accepted';
  displayStatus?: string | null;
  displayCoverage?: string | null;
};

export type VietnamForeignFlowWatchlistResponse = {
  status: VietnamForeignFlowWatchlistAvailability;
  dataState: VietnamForeignFlowWatchlistAvailability;
  usable: boolean;
  requestedTickers: string[];
  normalizedTickers: string[];
  duplicateTickersRemoved: number;
  expectedSymbolCount: number;
  readySymbolCount: number;
  partialSymbolCount: number;
  unavailableSymbolCount: number;
  requestedSessionCount: VietnamForeignFlowWatchlistWindow;
  fetchedAt: string;
  provider: 'ssi_fastconnect';
  providerVersion: 'v3';
  cacheState: 'hit' | 'miss' | 'refresh' | 'stale_hit' | 'unavailable' | 'mixed';
  cacheAgeSeconds?: number | null;
  failureClass?: string | null;
  items: VietnamForeignFlowWatchlistItem[];
};

type VietnamForeignFlowWatchlistRawItem = Omit<
  VietnamForeignFlowWatchlistItem,
  | 'buyValue1d' | 'sellValue1d' | 'netValue1d'
  | 'buyValue5d' | 'sellValue5d' | 'netValue5d'
  | 'buyValue20d' | 'sellValue20d' | 'netValue20d'
  | 'buyValue60d' | 'sellValue60d' | 'netValue60d'
  | 'buyVolume1d' | 'sellVolume1d' | 'netVolume1d'
  | 'buyVolume5d' | 'sellVolume5d' | 'netVolume5d'
  | 'buyVolume20d' | 'sellVolume20d' | 'netVolume20d'
  | 'buyVolume60d' | 'sellVolume60d' | 'netVolume60d'
> & Record<string, unknown>;

const normalizeForeignFlowWatchlistItem = (
  row: VietnamForeignFlowWatchlistRawItem,
): VietnamForeignFlowWatchlistItem => {
  const value = (key: string) => typeof row[key] === 'number' ? row[key] as number : null;
  return {
    ...row,
    buyValue1d: value('buyValue1D'),
    sellValue1d: value('sellValue1D'),
    netValue1d: value('netValue1D'),
    buyValue5d: value('buyValue5D'),
    sellValue5d: value('sellValue5D'),
    netValue5d: value('netValue5D'),
    buyValue20d: value('buyValue20D'),
    sellValue20d: value('sellValue20D'),
    netValue20d: value('netValue20D'),
    buyValue60d: value('buyValue60D'),
    sellValue60d: value('sellValue60D'),
    netValue60d: value('netValue60D'),
    buyVolume1d: value('buyVolume1D'),
    sellVolume1d: value('sellVolume1D'),
    netVolume1d: value('netVolume1D'),
    buyVolume5d: value('buyVolume5D'),
    sellVolume5d: value('sellVolume5D'),
    netVolume5d: value('netVolume5D'),
    buyVolume20d: value('buyVolume20D'),
    sellVolume20d: value('sellVolume20D'),
    netVolume20d: value('netVolume20D'),
    buyVolume60d: value('buyVolume60D'),
    sellVolume60d: value('sellVolume60D'),
    netVolume60d: value('netVolume60D'),
  };
};

type VietnamForeignFlowCamelCaseBatchSymbol = Omit<
  VietnamForeignFlowBatchSymbol,
  | 'foreignNetVolume5d'
  | 'foreignNetValue5d'
  | 'foreignNetVolume20d'
  | 'foreignNetValue20d'
  | 'coveredSessions5d'
  | 'complete5d'
  | 'windowEndDate5d'
  | 'coveredSessions20d'
  | 'complete20d'
  | 'windowEndDate20d'
> & {
  foreignNetVolume5D?: number | null;
  foreignNetValue5D?: number | null;
  foreignNetVolume20D?: number | null;
  foreignNetValue20D?: number | null;
  coveredSessions5D?: number | null;
  complete5D?: boolean | null;
  windowEndDate5D?: string | null;
  coveredSessions20D?: number | null;
  complete20D?: boolean | null;
  windowEndDate20D?: string | null;
};

type VietnamForeignFlowCamelCaseBatchResponse = Omit<VietnamForeignFlowBatchResponse, 'rows' | 'rankings'> & {
  rows?: VietnamForeignFlowCamelCaseBatchSymbol[];
  rankings?: {
    latestNetValue: VietnamForeignFlowRankingPair;
    netValue5D?: VietnamForeignFlowRankingPair;
    netValue20D?: VietnamForeignFlowRankingPair;
  };
};

const emptyForeignFlowRankingPair = (): VietnamForeignFlowRankingPair => ({ topBuy: [], topSell: [] });

const normalizeVietnamForeignFlowBatchResponse = (
  data: VietnamForeignFlowCamelCaseBatchResponse,
): VietnamForeignFlowBatchResponse => ({
  ...data,
  rows: (data.rows ?? []).map((row) => ({
    ...row,
    foreignNetVolume5d: row.foreignNetVolume5D ?? null,
    foreignNetValue5d: row.foreignNetValue5D ?? null,
    foreignNetVolume20d: row.foreignNetVolume20D ?? null,
    foreignNetValue20d: row.foreignNetValue20D ?? null,
    coveredSessions5d: row.coveredSessions5D ?? 0,
    complete5d: row.complete5D ?? false,
    windowEndDate5d: row.windowEndDate5D ?? null,
    coveredSessions20d: row.coveredSessions20D ?? 0,
    complete20d: row.complete20D ?? false,
    windowEndDate20d: row.windowEndDate20D ?? null,
  })),
  rankings: {
    latestNetValue: data.rankings?.latestNetValue ?? emptyForeignFlowRankingPair(),
    netValue5d: data.rankings?.netValue5D ?? emptyForeignFlowRankingPair(),
    netValue20d: data.rankings?.netValue20D ?? emptyForeignFlowRankingPair(),
  },
});

export type VietnamVn30ForeignFlowDaily = {
  tradingDate: string;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
  volumeCoverageCount?: number | null;
  volumeCoverageRatio?: number | null;
  valueCoverageCount?: number | null;
  valueCoverageRatio?: number | null;
  volumeCoverage?: { coveredComponents: number; expectedComponents: number; coverageRatio: number; complete: boolean } | null;
  valueCoverage?: { coveredComponents: number; expectedComponents: number; coverageRatio: number; complete: boolean } | null;
  volumeBreadth?: { netBuyCount: number; netSellCount: number; zeroCount: number; unavailableCount: number } | null;
  valueBreadth?: { netBuyCount: number; netSellCount: number; zeroCount: number; unavailableCount: number } | null;
  positiveComponents?: number | null;
  negativeComponents?: number | null;
  zeroComponents?: number | null;
  missingComponents?: number | null;
  coverageMode?: string | null;
  constituentCoverage?: string | null;
  suspiciousZeroSession?: boolean;
  anomaly?: string | null;
  anomalyCode?: string | null;
  anomalyStatus?: string | null;
  explicitZeroComponentCount?: number;
  missingFieldComponentCount?: number;
  freshness?: string | null;
  dataState: 'ready' | 'partial' | 'stale' | 'unavailable';
  state: 'ready' | 'partial' | 'stale' | 'unavailable';
};

export type VietnamVn30ForeignFlowWindow = {
  requestedSessions: 5 | 20 | 60;
  coveredSessions: number;
  complete: boolean;
  validSessions?: number | null;
  partialSessions?: number | null;
  suspiciousSessions?: number | null;
  containsProviderAnomaly?: boolean;
  anomalySessions?: string[];
  anomalyCount?: number;
  missingSessions?: number | null;
  startDate?: string | null;
  endDate?: string | null;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
  volumeComponentSessions?: number | null;
  volumeCoverageRatio?: number | null;
  volumeComplete?: boolean | null;
  valueComponentSessions?: number | null;
  valueCoverageRatio?: number | null;
  valueComplete?: boolean | null;
  positiveComponentSessions?: number | null;
  negativeComponentSessions?: number | null;
  zeroComponentSessions?: number | null;
  missingComponentSessions?: number | null;
  coverageMode?: string | null;
  constituentCoverage?: string | null;
};

export type VietnamVn30ForeignFlowComponent = Omit<
  VietnamForeignFlowBatchSymbol,
  'source' | 'sourceEndpoint' | 'volumeUnit' | 'valueUnit' | 'finality' | 'fetchedAt' | 'coveredSessions5d' | 'complete5d' | 'coveredSessions20d' | 'complete20d'
> & {
  aggregateLatestDate?: string | null;
  foreignBuyVolume5d?: number | null;
  foreignSellVolume5d?: number | null;
  foreignBuyValue5d?: number | null;
  foreignSellValue5d?: number | null;
  foreignBuyVolume20d?: number | null;
  foreignSellVolume20d?: number | null;
  foreignBuyValue20d?: number | null;
  foreignSellValue20d?: number | null;
  foreignBuyVolume60d?: number | null;
  foreignSellVolume60d?: number | null;
  foreignNetVolume60d?: number | null;
  foreignBuyValue60d?: number | null;
  foreignSellValue60d?: number | null;
  foreignNetValue60d?: number | null;
  volumeCoveredSessions5d: number;
  volumeComplete5d: boolean;
  valueCoveredSessions5d: number;
  valueComplete5d: boolean;
  volumeCoveredSessions20d: number;
  volumeComplete20d: boolean;
  valueCoveredSessions20d: number;
  valueComplete20d: boolean;
  volumeCoveredSessions60d?: number;
  volumeComplete60d?: boolean;
  valueCoveredSessions60d?: number;
  valueComplete60d?: boolean;
  windowEndDate60d?: string | null;
};

export type VietnamVn30ForeignFlowResponse = {
  scope: 'vn30';
  indexCode: 'VN30';
  source: 'ssi_fastconnect';
  sourceEndpoint: 'securitiesSummary?index=' | 'daily_stock_price';
  membershipSource: 'SSI IndexComponents';
  volumeUnit: 'shares';
  valueUnit: 'VND';
  finality: 'daily_available';
  aggregationBasis: 'direct_index_provider_aggregate' | 'current_vn30_membership';
  historicalConstituentCorrect: false;
  status: 'ready' | 'partial' | 'stale' | 'unavailable';
  usable: boolean;
  capabilityStatus: string;
  primaryDataMode: 'direct_index_canonical' | 'current_membership_decomposition';
  sourceCoverage: Array<{
    source: string;
    capabilityStatus: string;
    usable: boolean;
    failureClass?: string | null;
  }>;
  canonicalSource: string;
  canonicalProviderVersion: 'v3';
  canonicalEndpoint: string;
  canonicalAggregationMode: 'DIRECT_INDEX_CANONICAL';
  canonicalTradingDate?: string | null;
  decompositionAggregationMode: 'CURRENT_MEMBERSHIP_DECOMPOSITION';
  decompositionUniverse: 'current_vn30_membership';
  decompositionDate?: string | null;
  dataState: Exclude<VietnamForeignFlowDataState, 'empty'>;
  membership: {
    status: 'ready' | 'unavailable';
    indexCode: 'VN30';
    source: 'SSI IndexComponents';
    memberCount: number;
    componentCount: number;
    memberTickers: string[];
    cacheStatus?: string | null;
    failureClass?: string | null;
    reason?: string | null;
    fetchedAt: string;
    resolvedAt: string;
  };
  aggregateSessionDates: string[];
  latest?: VietnamVn30ForeignFlowDaily | null;
  windows: { '5': VietnamVn30ForeignFlowWindow; '20': VietnamVn30ForeignFlowWindow; '60'?: VietnamVn30ForeignFlowWindow };
  series: VietnamVn30ForeignFlowDaily[];
  components: VietnamVn30ForeignFlowComponent[];
  componentCounts: { usable: number; stale: number; empty: number; unavailable: number };
  rankings: Record<string, VietnamForeignFlowRankingPair>;
  canonical: {
    status: 'ready' | 'stale' | 'unavailable';
    capabilityStatus: 'available' | 'unsupported' | 'unavailable';
    failureClass?: string | null;
    usable: boolean;
    latest?: VietnamVn30ForeignFlowDaily | null;
    windows: { '5': VietnamVn30ForeignFlowWindow; '20': VietnamVn30ForeignFlowWindow; '60'?: VietnamVn30ForeignFlowWindow };
    series: VietnamVn30ForeignFlowDaily[];
    diagnostics: Record<string, unknown>;
  };
  decomposition: {
    status: string;
    dataState: 'ready' | 'partial' | 'stale' | 'unavailable';
    usable: boolean;
    aggregationMode: 'CURRENT_MEMBERSHIP_DECOMPOSITION';
    aggregationBasis: 'current_vn30_membership';
    membershipSource: 'SSI IndexComponents';
    memberCount: number;
    latestCompletedSession?: string | null;
    historicalConstituentCorrect: false;
    source: 'ssi_fastconnect';
    providerVersion: 'v3';
    date?: string | null;
    series: VietnamVn30ForeignFlowDaily[];
    latest?: VietnamVn30ForeignFlowDaily | null;
    windows: { '5': VietnamVn30ForeignFlowWindow; '20': VietnamVn30ForeignFlowWindow; '60'?: VietnamVn30ForeignFlowWindow };
    reconciliation: Record<string, unknown>;
    anomalySessions: string[];
    anomalyCount: number;
  };
  cache: { status: string; coalesced: boolean; ageSeconds: number; ttlSeconds: number; negative: boolean };
  timing: { membershipMs: number; componentHistoriesMs: number; aggregateBuildMs: number; totalMs: number };
  fetchedAt: string;
};

type VietnamVn30ForeignFlowCamelComponent = Omit<VietnamVn30ForeignFlowComponent,
  | 'foreignNetVolume5d' | 'foreignNetValue5d' | 'foreignNetVolume20d' | 'foreignNetValue20d'
  | 'foreignBuyVolume5d' | 'foreignSellVolume5d' | 'foreignBuyValue5d' | 'foreignSellValue5d'
  | 'foreignBuyVolume20d' | 'foreignSellVolume20d' | 'foreignBuyValue20d' | 'foreignSellValue20d'
  | 'foreignNetVolume60d' | 'foreignNetValue60d'
  | 'foreignBuyVolume60d' | 'foreignSellVolume60d' | 'foreignBuyValue60d' | 'foreignSellValue60d'
  | 'volumeCoveredSessions5d' | 'volumeComplete5d' | 'valueCoveredSessions5d' | 'valueComplete5d'
  | 'volumeCoveredSessions20d' | 'volumeComplete20d' | 'valueCoveredSessions20d' | 'valueComplete20d'
  | 'volumeCoveredSessions60d' | 'volumeComplete60d' | 'valueCoveredSessions60d' | 'valueComplete60d'
  | 'windowEndDate5d' | 'windowEndDate20d' | 'windowEndDate60d'
> & Record<string, unknown>;

type VietnamVn30ForeignFlowCamelResponse = Omit<VietnamVn30ForeignFlowResponse, 'components' | 'rankings'> & {
  components?: VietnamVn30ForeignFlowCamelComponent[];
  rankings?: Record<string, VietnamForeignFlowRankingPair>;
};

const normalizeVietnamVn30ForeignFlowResponse = (
  data: VietnamVn30ForeignFlowCamelResponse,
): VietnamVn30ForeignFlowResponse => ({
  ...data,
  components: (data.components ?? []).map((raw) => {
    const row = raw as VietnamVn30ForeignFlowCamelComponent & Record<string, number | boolean | string | null | undefined>;
    return {
      ...row,
      foreignBuyVolume5d: row.foreignBuyVolume5D ?? null,
      foreignSellVolume5d: row.foreignSellVolume5D ?? null,
      foreignNetVolume5d: row.foreignNetVolume5D ?? null,
      foreignBuyValue5d: row.foreignBuyValue5D ?? null,
      foreignSellValue5d: row.foreignSellValue5D ?? null,
      foreignNetValue5d: row.foreignNetValue5D ?? null,
      foreignBuyVolume20d: row.foreignBuyVolume20D ?? null,
      foreignSellVolume20d: row.foreignSellVolume20D ?? null,
      foreignNetVolume20d: row.foreignNetVolume20D ?? null,
      foreignBuyValue20d: row.foreignBuyValue20D ?? null,
      foreignSellValue20d: row.foreignSellValue20D ?? null,
      foreignNetValue20d: row.foreignNetValue20D ?? null,
      foreignBuyVolume60d: row.foreignBuyVolume60D ?? null,
      foreignSellVolume60d: row.foreignSellVolume60D ?? null,
      foreignNetVolume60d: row.foreignNetVolume60D ?? null,
      foreignBuyValue60d: row.foreignBuyValue60D ?? null,
      foreignSellValue60d: row.foreignSellValue60D ?? null,
      foreignNetValue60d: row.foreignNetValue60D ?? null,
      volumeCoveredSessions5d: Number(row.volumeCoveredSessions5D ?? 0),
      volumeComplete5d: Boolean(row.volumeComplete5D),
      valueCoveredSessions5d: Number(row.valueCoveredSessions5D ?? 0),
      valueComplete5d: Boolean(row.valueComplete5D),
      volumeCoveredSessions20d: Number(row.volumeCoveredSessions20D ?? 0),
      volumeComplete20d: Boolean(row.volumeComplete20D),
      valueCoveredSessions20d: Number(row.valueCoveredSessions20D ?? 0),
      valueComplete20d: Boolean(row.valueComplete20D),
      volumeCoveredSessions60d: Number(row.volumeCoveredSessions60D ?? 0),
      volumeComplete60d: Boolean(row.volumeComplete60D),
      valueCoveredSessions60d: Number(row.valueCoveredSessions60D ?? 0),
      valueComplete60d: Boolean(row.valueComplete60D),
      windowEndDate5d: (row.windowEndDate5D as string | null | undefined) ?? null,
      windowEndDate20d: (row.windowEndDate20D as string | null | undefined) ?? null,
      windowEndDate60d: (row.windowEndDate60D as string | null | undefined) ?? null,
    } as VietnamVn30ForeignFlowComponent;
  }),
  rankings: data.rankings ?? {},
});

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
  eventMarketSession?: string | null;
};

export type VietnamRealtimeResponse = {
  market: 'VN';
  source: string;
  status: 'ok' | 'disabled' | 'not_implemented' | 'unavailable' | 'error' | 'stale' | string;
  error?: string | null;
  errorDetail?: string | null;
  rawError?: string | null;
  eventMarketSession?: string | null;
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
  streamState?: 'ready' | 'recovering' | 'stale' | 'unavailable' | 'closed' | 'failed' | 'awaiting_subscription' | 'disabled' | string | null;
  lastEventAt?: string | null;
  eventAgeSeconds?: number | null;
  generation?: number | null;
  transportHealth?: string | null;
  parserHealth?: string | null;
  symbolDataHealth?: string | null;
  responseMarketSession?: string | null;
  currentMarketSession?: string | null;
  lastValidTradeAt?: string | null;
  droppedInvalidRowCount?: number | null;
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
  eventMarketSession?: string | null;
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
  streamState?: 'ready' | 'recovering' | 'stale' | 'unavailable' | 'closed' | 'failed' | 'awaiting_subscription' | 'disabled' | string | null;
  lastEventAt?: string | null;
  eventAgeSeconds?: number | null;
  generation?: number | null;
  transportHealth?: string | null;
  parserHealth?: string | null;
  symbolDataHealth?: string | null;
  responseMarketSession?: string | null;
  currentMarketSession?: string | null;
  lastValidTradeAt?: string | null;
  droppedInvalidRowCount?: number | null;
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
  providerSnapshotAgeSeconds?: number | null;
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
  sourceEndpoint?: string | null;
  providerVersion?: string | null;
  fetchedAt?: string | null;
  cacheStatus?: string | null;
  dataState?: 'ready' | 'partial' | 'unavailable' | string | null;
  failureClass?: string | null;
  status: 'ok' | 'unavailable' | 'missing' | string;
  qualityStatus?: 'complete' | 'partial' | 'unavailable' | 'unknown' | string | null;
  completeness?: number | null;
  missingFields?: string[];
  fieldCoverage?: Record<string, boolean>;
  diagnostics?: Record<string, unknown>;
  coreProfileStatus?: 'ready' | 'unavailable';
  optionalMetadataStatus?: 'complete' | 'incomplete';
  classificationSource?: string | null;
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
  referencePriceSource?: string | null;
  ceilingPriceSource?: string | null;
  floorPriceSource?: string | null;
  completedSessionDate?: string | null;
  finalCloseStatus?: 'completed' | 'provisional' | 'unknown' | 'not_applicable';
  adjustmentStatus?: 'adjusted' | 'unadjusted' | 'not_provided' | 'unknown';
  sourceFreshness?: 'current' | 'latest_completed' | 'publication_lag' | 'stale' | 'unknown';
  status: 'ok' | 'missing' | string;
};

export type VietnamCompanySessionContext = {
  completedSessionDate?: string | null;
  liveSessionDate?: string | null;
  providerEventTime?: string | null;
  fetchedAt?: string | null;
  cacheAgeSeconds?: number | null;
  sessionPhase?: string | null;
  sessionPhaseLabel?: string | null;
  marketSessionActive?: boolean;
  holidayAware?: boolean;
  sourceFreshness?: 'current' | 'latest_completed' | 'publication_lag' | 'stale' | 'unknown' | string;
};

export type VietnamCompanyChannelState =
  | 'ready'
  | 'partial'
  | 'reconnecting'
  | 'no_data'
  | 'stale'
  | 'unavailable'
  | 'disabled'
  | 'error';

export type VietnamCompanyLiveMarket = {
  status: 'ready' | 'partial' | 'unavailable';
  channels: {
    lastPrice: VietnamCompanyChannelState;
    orderBook: VietnamCompanyChannelState;
    tradeTape: VietnamCompanyChannelState;
    intraday: VietnamCompanyChannelState;
  };
  usableChannelCount?: number;
  sessionDate?: string | null;
  providerEventTime?: string | null;
};

export type VietnamCompanyQualitySummary = {
  overallStatus?: 'ready' | 'partial' | 'unavailable' | string;
  groups: Array<{
    key: 'daily_data' | 'live_market' | 'company_metadata' | string;
    label: string;
    status: string;
    detail?: string | null;
  }>;
  issueCodes?: string[];
  primaryIssues?: VietnamDataQualityIssue[];
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
  capabilityStatus?: 'ready' | 'partial' | 'unavailable';
  valueState?: 'explicit_zero' | 'nonzero' | 'partial' | 'unavailable';
  fieldPresence?: Record<string, string>;
  fieldAliases?: Record<string, string>;
  normalizationIssues?: Array<{ field?: string; issue?: string }>;
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

export type VietnamFlowDataResponse = {
  status: 'ok' | 'partial' | 'unavailable';
  dataState?: 'ready' | 'partial' | 'unavailable';
  usable?: boolean;
  failureClass?: string | null;
  source: string;
  providerVersion: string;
  scope?: string | null;
  identifier?: string | null;
  universe?: string | null;
  endpoint?: string | null;
  requestedFromDate?: string | null;
  requestedToDate?: string | null;
  fetchedAt?: string | null;
  cache?: { status?: string | null; ageSeconds?: number | null };
  unsupportedScopes?: string[];
  requestedSymbolCount?: number | null;
  classifiedSymbolCount?: number | null;
  unclassifiedSymbolCount?: number | null;
  currentSessionStatus?: string | null;
  rows?: Array<Record<string, unknown>>;
  diagnostics?: Record<string, unknown>;
};

export type VietnamCurrentForeignFlowDataState =
  | 'waiting'
  | 'ready'
  | 'stale'
  | 'market_closed'
  | 'unavailable'
  | 'error';

export type VietnamCurrentForeignFlowSourceKind = 'current' | 'completed';
export type VietnamCurrentForeignFlowFinality =
  | 'current_session_provisional'
  | 'completed_accepted';

export type VietnamCurrentForeignFlowResponse = Omit<VietnamFlowDataResponse, 'dataState'> & {
  dataState: VietnamCurrentForeignFlowDataState;
  usable: boolean;
  failureClass?: string | null;
  symbol: string;
  tradingDate?: string | null;
  freshnessStatus: string;
  isCurrentSession: boolean;
  isProvisional: boolean;
  current?: Record<string, unknown> | null;
  latestCompletedComparison?: Record<string, unknown> | null;
  streamStatus: string;
  streamReason: string;
  finality?: Extract<VietnamCurrentForeignFlowFinality, 'current_session_provisional'> | null;
  updateSemantics?: 'cumulative_replacement_snapshot' | null;
  marketSession?: {
    marketSession?: string | null;
    marketSessionLabel?: string | null;
    marketSessionActive?: boolean | null;
  };
  diagnostics?: Record<string, unknown>;
};

export type VietnamCurrentForeignFlowAggregateItem = {
  symbol: string;
  providerSessionDate?: string | null;
  dataState: VietnamCurrentForeignFlowDataState;
  usable: boolean;
  isStale: boolean;
  streamStatus: string;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
  providerTime?: string | null;
  receivedAt?: string | null;
  icbCode?: string | null;
  icbName?: string | null;
  displayLatest?: VietnamCurrentForeignFlowDisplayRow | null;
  displayWindows?: Record<string, Record<string, unknown>>;
};

export type VietnamCurrentForeignFlowDisplayRow = Record<string, unknown> & {
  tradingDate?: string | null;
  providerSessionDate?: string | null;
  sourceKind?: VietnamCurrentForeignFlowSourceKind | null;
  source?: string | null;
  finality?: VietnamCurrentForeignFlowFinality | null;
  currentState?: VietnamCurrentForeignFlowDataState | null;
  dataState?: VietnamCurrentForeignFlowDataState | null;
  providerStatus?: string | null;
  status?: string | null;
  displayStatus?: string | null;
  isCurrent?: boolean;
  isCompleted?: boolean;
  isPartial?: boolean;
  isStale?: boolean;
  requestedCount?: number | null;
  observedCount?: number | null;
  completeValueCount?: number | null;
  completeVolumeCount?: number | null;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
  providerTime?: string | null;
  receivedAt?: string | null;
  icbCode?: string | null;
  icbName?: string | null;
};

export type VietnamCurrentForeignFlowAggregateResponse = {
  status: 'ok' | 'partial' | 'unavailable';
  dataState: VietnamCurrentForeignFlowDataState;
  usable: boolean;
  failureClass?: string | null;
  scope: 'current_foreign_flow_aggregate';
  universe: string;
  providerSessionDate?: string | null;
  isProvisional: boolean;
  finality?: Extract<VietnamCurrentForeignFlowFinality, 'current_session_provisional'> | null;
  source: string;
  providerVersion: 'v3';
  endpoint: 'room.{symbol}';
  updateSemantics: 'cumulative_replacement_snapshot';
  aggregate?: Record<string, unknown> | null;
  displaySeries: VietnamCurrentForeignFlowDisplayRow[];
  displayWindows: Record<string, Record<string, unknown>>;
  rankings: Record<string, {
    topBuy: Array<Record<string, unknown>>;
    topSell: Array<Record<string, unknown>>;
  }>;
  items: VietnamCurrentForeignFlowAggregateItem[];
  groups: VietnamCurrentForeignFlowDisplayRow[];
  coverage: {
    requestedSymbolCount: number;
    classifiedSymbolCount: number;
    subscribedSymbolCount: number;
    observedSymbolCount: number;
    completeVolumeCount: number;
    completeValueCount: number;
    missingSymbols: string[];
    staleSymbolCount: number;
  };
  marketSession?: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
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
    intradayChangeBaseline?: 'first_session_candle_open' | string | null;
    intradayChangeBaselineValue?: number | null;
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
  capabilityStatus?: 'ready' | 'partial' | 'no_data' | 'unavailable' | 'error';
  latestDate?: string | null;
  dailyPriceDate?: string | null;
  targetSessionDate?: string | null;
  sessionBasis?: 'current_live_session' | 'latest_completed_session' | string | null;
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
  group?: string | null;
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
  sessionContext?: VietnamCompanySessionContext;
  liveMarket?: VietnamCompanyLiveMarket;
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
    session?: Record<string, unknown> | null;
    adjustment?: Record<string, unknown> | null;
    liveChannels?: Record<string, unknown> | null;
    dailyStockPriceCapabilities?: Record<string, unknown> | null;
    foreignFlow?: Record<string, unknown> | null;
    intraday?: Record<string, unknown> | null;
    profile?: Record<string, unknown> | null;
    qualityIssues?: Array<Record<string, unknown>> | null;
    realtime?: Record<string, unknown> | null;
    tradeTape?: Record<string, unknown> | null;
    orderBook?: Record<string, unknown> | null;
  };
  dataQualitySummary?: VietnamDataQualitySummary;
  qualitySummary?: VietnamCompanyQualitySummary;
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

  async getVietnamForeignFlowBatch(
    tickers: string[],
    options?: { topN?: number; forceRefresh?: boolean; signal?: AbortSignal },
  ): Promise<VietnamForeignFlowBatchResponse> {
    const normalizedTickers: string[] = [];
    const seen = new Set<string>();
    for (const raw of tickers) {
      const ticker = normalizeVietnamTicker(raw);
      if (!/^[A-Z0-9]{1,10}$/.test(ticker) || ticker === 'ALL') {
        throw new Error(`Invalid Vietnam ticker: ${raw}`);
      }
      if (seen.has(ticker)) continue;
      seen.add(ticker);
      normalizedTickers.push(ticker);
      if (normalizedTickers.length === VIETNAM_WATCHLIST_MAX_SIZE) break;
    }
    if (!normalizedTickers.length) throw new Error('At least one Vietnam ticker is required.');
    const response = await apiClient.post('/api/v1/stocks/vn/foreign-flow/batch', {
      tickers: normalizedTickers,
      top_n: options?.topN ?? 5,
      force_refresh: options?.forceRefresh ?? false,
    }, {
      timeout: 120000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    return normalizeVietnamForeignFlowBatchResponse(
      toCamelCase<VietnamForeignFlowCamelCaseBatchResponse>(response.data),
    );
  },

  async getVietnamForeignFlowWatchlist(
    tickers: string[],
    options?: {
      sessions?: VietnamForeignFlowWatchlistWindow;
      forceRefresh?: boolean;
      signal?: AbortSignal;
    },
  ): Promise<VietnamForeignFlowWatchlistResponse> {
    const normalizedTickers: string[] = [];
    const seen = new Set<string>();
    for (const raw of tickers) {
      const ticker = normalizeVietnamTicker(raw);
      if (!/^[A-Z0-9]{1,10}$/.test(ticker) || ticker === 'ALL') {
        throw new Error(`Invalid Vietnam ticker: ${raw}`);
      }
      if (seen.has(ticker)) continue;
      seen.add(ticker);
      normalizedTickers.push(ticker);
    }
    if (!normalizedTickers.length) throw new Error('At least one Vietnam ticker is required.');
    if (normalizedTickers.length > VIETNAM_WATCHLIST_MAX_SIZE) {
      throw new Error(`Watchlist is limited to ${VIETNAM_WATCHLIST_MAX_SIZE} tickers.`);
    }
    const response = await apiClient.get('/api/v1/stocks/vn/foreign-flow/watchlist', {
      params: {
        tickers: normalizedTickers.join(','),
        sessions: options?.sessions ?? 60,
        force_refresh: options?.forceRefresh ?? false,
      },
      timeout: 90000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    const data = toCamelCase<Omit<VietnamForeignFlowWatchlistResponse, 'items'> & {
      items?: VietnamForeignFlowWatchlistRawItem[];
    }>(response.data);
    return {
      ...data,
      items: (data.items ?? []).map(normalizeForeignFlowWatchlistItem),
    };
  },

  async getVietnamVn30ForeignFlow(
    options?: {
      topN?: number;
      forceRefresh?: boolean;
      forceCapabilityRefresh?: boolean;
      signal?: AbortSignal;
    },
  ): Promise<VietnamVn30ForeignFlowResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/foreign-flow/vn30', {
      params: {
        top_n: options?.topN ?? 10,
        force_refresh: options?.forceRefresh ?? false,
        force_capability_refresh: options?.forceCapabilityRefresh ?? false,
      },
      timeout: 180000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    return normalizeVietnamVn30ForeignFlowResponse(
      toCamelCase<VietnamVn30ForeignFlowCamelResponse>(response.data),
    );
  },

  async getVietnamForeignFlowSymbolHistory(
    rawTicker: string,
    options?: {
      limit?: number;
      fromDate?: string;
      toDate?: string;
      forceRefresh?: boolean;
      signal?: AbortSignal;
    },
  ): Promise<VietnamForeignFlowSymbolHistoryResponse> {
    const ticker = normalizeVietnamTicker(rawTicker);
    if (!/^[A-Z0-9]{1,10}$/.test(ticker) || ticker === 'ALL') {
      throw new Error(`Invalid Vietnam ticker: ${rawTicker}`);
    }
    const limit = Math.min(120, Math.max(1, Math.trunc(options?.limit ?? 60)));
    const hasDateBounds = Boolean(options?.fromDate && options?.toDate);
    const response = await apiClient.get(`/api/v1/stocks/vn/foreign-flow/symbol/${ticker}`, {
      params: {
        ...(hasDateBounds
          ? { from_date: options?.fromDate, to_date: options?.toDate }
          : { limit }),
        ...(options?.forceRefresh ? { force_refresh: true } : {}),
      },
      timeout: 120000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    return normalizeVietnamForeignFlowSymbolHistoryResponse(
      toCamelCase<VietnamForeignFlowSymbolHistoryCamelResponse>(response.data),
    );
  },

  async getVietnamForeignFlowByIndex(
    indexCode: string,
    fromDate: string,
    toDate: string,
    options?: { limit?: number; signal?: AbortSignal },
  ): Promise<VietnamFlowDataResponse> {
    const response = await apiClient.get(
      `/api/v1/stocks/vn/foreign-flow/index/${encodeURIComponent(indexCode.trim().toUpperCase())}`,
      {
        params: { from_date: fromDate, to_date: toDate, limit: options?.limit ?? 260 },
        timeout: 180000,
        signal: options?.signal,
      },
    );
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamFlowDataResponse>(response.data);
  },

  async getVietnamCurrentForeignFlow(
    rawTicker: string,
    options?: { forceRefresh?: boolean; signal?: AbortSignal },
  ): Promise<VietnamCurrentForeignFlowResponse> {
    const ticker = normalizeVietnamTicker(rawTicker);
    if (!/^[A-Z0-9]{1,10}$/.test(ticker) || ticker === 'ALL') {
      throw new Error(`Invalid Vietnam ticker: ${rawTicker}`);
    }
    const response = await apiClient.get(`/api/v1/stocks/vn/foreign-flow/current/${ticker}`, {
      timeout: 120000,
      signal: options?.signal,
      params: options?.forceRefresh ? { force_refresh: true } : undefined,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamCurrentForeignFlowResponse>(response.data);
  },

  async getVietnamCurrentForeignFlowAggregate(
    options: {
      scope: 'vn30' | 'watchlist';
      tickers?: string[];
      includeIndustries?: boolean;
      forceRefresh?: boolean;
      signal?: AbortSignal;
    },
  ): Promise<VietnamCurrentForeignFlowAggregateResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/foreign-flow/current-aggregate', {
      timeout: 120000,
      signal: options.signal,
      params: {
        scope: options.scope,
        ...(options.tickers?.length ? { tickers: options.tickers.join(',') } : {}),
        include_industries: options.includeIndustries ?? options.scope === 'vn30',
        ...(options.forceRefresh ? { force_refresh: true } : {}),
      },
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamCurrentForeignFlowAggregateResponse>(response.data);
  },

  async getVietnamProprietaryFlow(
    scope: 'board' | 'index',
    identifier: string,
    options?: { fromDate?: string; toDate?: string; forceRefresh?: boolean; signal?: AbortSignal },
  ): Promise<VietnamFlowDataResponse> {
    const response = await apiClient.get('/api/v1/stocks/vn/proprietary-flow', {
      params: {
        scope,
        identifier: identifier.trim().toUpperCase(),
        ...(options?.fromDate ? { from_date: options.fromDate } : {}),
        ...(options?.toDate ? { to_date: options.toDate } : {}),
        ...(options?.forceRefresh ? { force_refresh: true } : {}),
      },
      timeout: 180000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamFlowDataResponse>(response.data);
  },

  async getVietnamIndustryFlow(
    request: { symbols?: string[]; indexCode?: string; fromDate: string; toDate: string },
    options?: { signal?: AbortSignal },
  ): Promise<VietnamFlowDataResponse> {
    const response = await apiClient.post('/api/v1/stocks/vn/industry-flow', {
      ...(request.symbols ? { symbols: request.symbols } : {}),
      ...(request.indexCode ? { index_code: request.indexCode } : {}),
      from_date: request.fromDate,
      to_date: request.toDate,
    }, {
      timeout: 180000,
      signal: options?.signal,
    });
    const { toCamelCase } = await import('./utils');
    return toCamelCase<VietnamFlowDataResponse>(response.data);
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
