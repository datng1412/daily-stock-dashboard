import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Banknote, DatabaseZap, Maximize2, RefreshCw, RotateCcw, ShieldAlert, X } from 'lucide-react';
import {
  stocksApi,
  type VietnamChartPoint,
  type VietnamChartResponse,
  type VietnamCorporateActionEvent,
  type VietnamCorporateActionsResponse,
  type VietnamDailyIndexResponse,
  type VietnamIndexComponentsResponse,
  type VietnamIndexListResponse,
  type VietnamObservabilityResponse,
  type VietnamRealtimeQuote,
  type VietnamRealtimeTrade,
  type VietnamWatchItem,
  type VietnamWatchlistResponse,
} from '../api/stocks';
import { AppPage, Badge, Button, Loading } from '../components/common';
import { DataQualitySummary } from '../components/dashboard';
import { cn } from '../utils/cn';
import { buildVietnamConditionSummary, VIETNAM_CONDITION_SUMMARY_SUBTITLE } from '../utils/vietnamConditionSummary';
import { getRealtimeSnapshotDisplayState, type RealtimeSnapshotDisplayResult } from '../utils/realtimeSnapshotState';
import { getVietnamMarketPhase, type VietnamMarketPhase } from '../utils/vietnamMarketPhase';
import {
  formatAbsoluteDateTime,
  formatRelativeAge,
  formatRelativeTime,
  formatVietnamTime,
  parseMozyTimestamp,
} from '../utils/vietnamTime';
import {
  VIETNAM_WATCHLIST_MAX_SIZE,
  normalizeVietnamTicker,
  normalizeVietnamWatchlist,
} from '../utils/vietnamWatchlist';

const DEFAULT_TICKERS = ['FPT', 'VPB', 'MSB', 'SCS', 'ACV', 'ACB'];
const CUSTOM_WATCHLIST_STORAGE_KEY = 'vnDashboard.customWatchlist.v1';
const AUTO_REFRESH_INTERVALS = [60, 180, 300];
const REALTIME_SNAPSHOT_REFRESH_INTERVALS = [2, 3, 5, 10, 15];
const TRADE_TAPE_REFRESH_INTERVALS = [5, 10, 15];
const DEFAULT_WATCHLIST = normalizeVietnamWatchlist(DEFAULT_TICKERS) ?? DEFAULT_TICKERS;
const DETAIL_NEWS_LIMIT = 8;
const INSPECT_RANGES = [
  { label: '1M', days: 31 },
  { label: '3M', days: 93 },
  { label: '6M', days: 186 },
  { label: '1Y', days: 366 },
] as const;
type InspectRangeLabel = typeof INSPECT_RANGES[number]['label'];
type BadgeVariant = NonNullable<React.ComponentProps<typeof Badge>['variant']>;
type WatchlistScanLabel = 'Strong' | 'Improving' | 'Neutral' | 'Weakening' | 'Risk elevated' | 'Data unavailable';
type VietnamDashboardPresetId = 'vn30' | 'banks' | 'securities' | 'real-estate' | 'consumer' | 'logistics' | 'tech' | 'oil-gas' | 'electricity';
type VietnamDashboardActivePresetId = 'my' | 'custom' | VietnamDashboardPresetId;
type ReadinessState = 'Ready' | 'Partial' | 'Unavailable' | 'Disabled' | 'Loading' | 'Not implemented';
type SectionState = 'Ready' | 'Loading' | 'Updating...' | 'Partial' | 'Unavailable' | 'Disabled' | 'Failed';
type ReadinessItemKey = 'daily' | 'referenceForeign' | 'indicators' | 'intraday' | 'realtime' | 'tradeTape' | 'news';

interface WatchlistScanState {
  label: WatchlistScanLabel;
  variant: BadgeVariant;
  reason: string;
}

interface DataReadinessItem {
  key: ReadinessItemKey;
  label: string;
  state: ReadinessState;
  detail: string;
  explanation: string;
}

interface WatchlistCommitIntent {
  tickers: string[];
  presetId: VietnamDashboardActivePresetId;
  selectedTicker: string | null;
  customWatchlist?: string[];
  customWatchlistInput?: string;
  customNotice?: string | null;
}

const WATCHLIST_SCAN_ORDER: WatchlistScanLabel[] = ['Strong', 'Improving', 'Neutral', 'Weakening', 'Risk elevated', 'Data unavailable'];
const DATA_CAVEAT_LABELS = new Set(['Foreign data stale', 'Indicator caution', 'Price finality unknown', 'Adjusted price unknown']);
const VIETNAM_DASHBOARD_PRESETS: Array<{ id: VietnamDashboardPresetId; label: string; tickers: string[] }> = [
  {
    id: 'vn30',
    label: 'VN30',
    tickers: ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB', 'VCB', 'VHM', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'],
  },
  {
    id: 'banks',
    label: 'Banks',
    tickers: ['VCB', 'BID', 'CTG', 'MBB', 'TCB', 'ACB', 'VPB', 'HDB', 'STB', 'TPB', 'SHB', 'MSB', 'LPB', 'SSB', 'OCB', 'EIB'],
  },
  {
    id: 'securities',
    label: 'Securities',
    tickers: ['SSI', 'VCI', 'VND', 'HCM', 'SHS', 'VIX', 'MBS', 'FTS', 'CTS', 'BSI', 'AGR', 'ORS'],
  },
  {
    id: 'real-estate',
    label: 'Real estate',
    tickers: ['VHM', 'VIC', 'VRE', 'NVL', 'PDR', 'KDH', 'NLG', 'DXG', 'DIG', 'CEO', 'HDC', 'CII', 'KBC', 'SZC'],
  },
  {
    id: 'consumer',
    label: 'Consumer',
    tickers: ['VNM', 'MSN', 'MWG', 'FRT', 'PNJ', 'SAB', 'BHN', 'QNS', 'DBC', 'HAG', 'BAF', 'ANV', 'FMC'],
  },
  {
    id: 'logistics',
    label: 'Logistics',
    tickers: ['GMD', 'HAH', 'VSC', 'VOS', 'VTO', 'VTP', 'SGP', 'PHP', 'DVP', 'SCS'],
  },
  {
    id: 'tech',
    label: 'Tech',
    tickers: ['FPT', 'CMG', 'ELC', 'VGI', 'VTP', 'CTR'],
  },
  {
    id: 'oil-gas',
    label: 'Oil & gas',
    tickers: ['GAS', 'PLX', 'PVD', 'PVS', 'BSR', 'OIL', 'PVC', 'PVT', 'PVB', 'POW'],
  },
  {
    id: 'electricity',
    label: 'Electricity',
    tickers: ['POW', 'NT2', 'REE', 'PC1', 'GEX', 'HDG', 'QTP', 'PPC', 'CHP', 'VSH', 'TTA', 'GEG'],
  },
];

const formatNumber = (value?: number | null, maximumFractionDigits = 0) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits }).format(value);
};

const formatPrice = (value?: number | null) => formatNumber(value, 2);

const formatRatio = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return `${formatNumber(value, 2)}x`;
};

const formatSignedNumber = (value?: number | null, maximumFractionDigits = 2) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const formatted = formatNumber(Math.abs(value), maximumFractionDigits);
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
};

const finiteNumber = (value?: number | null) => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

const formatReferenceDelta = (value?: number | null, percent?: number | null) => {
  if (value === null || value === undefined || percent === null || percent === undefined) {
    return 'Unavailable';
  }
  return `${formatSignedNumber(value, 2)} / ${formatSignedNumber(percent, 2)}%`;
};

const hasDisplayValue = (value?: number | string | null) => (
  value !== null && value !== undefined && value !== '' && !(typeof value === 'number' && Number.isNaN(value))
);

type VietnamNewsItem = VietnamWatchItem['news'][number];

const firstNewsTimestamp = (...values: Array<string | number | null | undefined>) => (
  values.find((value) => value !== null && value !== undefined && String(value).trim() !== '')
);

const newsTimestamp = (news: VietnamNewsItem) => (
  firstNewsTimestamp(
    news.publishedAt,
    news.publishedDate,
    news.publishedTime,
    news.createdAt,
    news.date,
    news.time,
    news.timestamp,
  )
);

const neutralFormulaText = (value: string) => (
  /recommend/i.test(value) ? 'Rule-based neutral condition labels only.' : value
);

const formulaDisplayLabel = (key: string) => {
  if (key === 'volume_ratio') return 'Daily volume / 20D avg daily volume';
  return key.replaceAll('_', ' ');
};

const formatCountdown = (seconds?: number | null) => {
  if (seconds === null || seconds === undefined) return '-';
  const safeSeconds = Math.max(0, seconds);
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
};

const signalTone = (change?: number | null) => {
  if ((change ?? 0) > 0) return 'text-success';
  if ((change ?? 0) < 0) return 'text-danger';
  return 'text-secondary-text';
};

const liquidityVariant = (score?: number | null) => {
  if ((score ?? 0) >= 70) return 'success';
  if ((score ?? 0) >= 35) return 'warning';
  return 'danger';
};

const foreignLabel = (signal?: string | null) => {
  if (signal === 'foreign_net_positive') return 'Foreign net positive';
  if (signal === 'foreign_net_negative') return 'Foreign net negative';
  return 'Foreign unavailable';
};

const dateMatchVariant = (status?: string | null) => {
  if (status === 'matched') return 'success';
  if (status === 'mismatched') return 'warning';
  return 'default';
};

const priceSourceVariant = (source?: string | null) => {
  if (source === 'quote') return 'success';
  if (source === 'SSI' || source === 'ssi_ohlcv') return 'info';
  if (source === 'ohlcv') return 'warning';
  return 'default';
};

const isSsiDailyPriceSource = (source?: string | null) => source === 'SSI' || source === 'ssi_ohlcv';

const finalCloseDisplayLabel = (status?: string | null) => {
  if (!status || status === 'unknown' || status === 'not_confirmed') return 'not confirmed';
  return status.replaceAll('_', ' ');
};

const statusVariant = (label: string) => {
  if (['Stronger than short-term average', 'Near support', 'Near resistance', 'Volume expansion', 'Foreign net positive'].includes(label)) return 'info';
  if (['Breakout candidate', 'Weak short-term', 'Foreign data stale', 'Foreign net negative', 'Indicator caution', 'Price finality unknown', 'Adjusted price unknown'].includes(label)) return 'warning';
  if (['Overextended', 'Low liquidity'].includes(label)) return 'danger';
  return 'default';
};

const severityVariant = (severity?: string | null) => {
  if (severity === 'risk') return 'danger';
  if (severity === 'caution') return 'warning';
  return 'info';
};

const sectionStateVariant = (state: SectionState): BadgeVariant => {
  if (state === 'Ready') return 'success';
  if (state === 'Loading' || state === 'Updating...') return 'info';
  if (state === 'Partial') return 'warning';
  if (state === 'Failed') return 'danger';
  return 'default';
};

const intradayVariant = (label?: string | null) => {
  if (['Intraday up', 'Intraday flat', 'Intraday volume expansion'].includes(label ?? '')) return 'info';
  if (['Intraday down', 'Intraday wide range', 'Intraday data limited', 'Not realtime quote'].includes(label ?? '')) return 'warning';
  return 'default';
};

const cacheLabel = (status?: string | null) => status ?? 'missing';

const rawDateLabel = (value?: string | number | null) => (value === null || value === undefined || value === '' ? '—' : String(value));

const compactLabels = (labels?: string[], max = 4) => (labels ?? ['Watch']).slice(0, max);

const RECOMMENDATION_WORD_RE = /\b(buy|sell|hold|recommendation)\b/gi;

const neutralizeRecommendationText = (value?: string | null) => (
  value ? value.replace(RECOMMENDATION_WORD_RE, 'source term') : value
);

const neutralTradeType = (value?: string | null) => {
  const normalized = String(value ?? '').trim().toLowerCase();
  if (!normalized) return '-';
  if (normalized === 'buy') return 'Bid-side';
  if (normalized === 'sell') return 'Offer-side';
  if (normalized === 'unknown') return 'Unknown';
  return neutralizeRecommendationText(String(value)) ?? '-';
};

const hasEncodingArtifacts = (value?: string | null) => Boolean(value && /(?:Ã|Â|â€|�)/.test(value));

const marketStatusLabels = (item: VietnamWatchItem, max = 3) => {
  const labels = (item.statusLabels ?? []).filter((label) => !DATA_CAVEAT_LABELS.has(label));
  return compactLabels(labels.length ? labels : ['Watch'], max);
};

const hasAvailableSsiDailyStockPrice = (item: VietnamWatchItem) => {
  const daily = item.dailyStockPrice;
  if (daily?.status === 'ok') return true;
  if (daily?.status === 'unavailable') return false;
  return [
    daily?.date,
    daily?.referencePrice,
    daily?.ceilingPrice,
    daily?.floorPrice,
    item.ssiReferencePrice,
    item.ssiCeilingPrice,
    item.ssiFloorPrice,
  ].some(hasDisplayValue);
};

const dataCaveatDetails = (item: VietnamWatchItem) => {
  const suppressLegacyForeignCaveats = hasAvailableSsiDailyStockPrice(item);
  const details = (item.statusDetails ?? []).filter((detail) => (
    DATA_CAVEAT_LABELS.has(detail.label)
    && !(suppressLegacyForeignCaveats && detail.label === 'Foreign data stale')
  ));
  const detailLabels = new Set(details.map((detail) => detail.label));
  const syntheticDetails = (item.statusLabels ?? [])
    .filter((label) => (
      DATA_CAVEAT_LABELS.has(label)
      && !detailLabels.has(label)
      && !(suppressLegacyForeignCaveats && label === 'Foreign data stale')
    ))
    .map((label) => ({ label, severity: 'caution' as const, reason: 'Source metadata caveat returned by the Vietnam watchlist response.' }));
  return [...details, ...syntheticDetails];
};

const latestFetchedValue = (item: VietnamWatchItem) => {
  const values = [
    item.cacheLastFetchedAt?.ohlcv,
    item.cacheLastFetchedAt?.quote,
    item.cacheLastFetchedAt?.intradayOhlcv,
    item.cacheLastFetchedAt?.news,
  ]
    .map((value) => parseMozyTimestamp(value))
    .filter((value): value is Date => Boolean(value))
    .sort((left, right) => right.getTime() - left.getTime());
  return values[0]?.toISOString() ?? null;
};

const officialDailyCacheFreshness = (item: VietnamWatchItem) => {
  const status = item.cacheStatus?.ohlcvCache;
  if (status === 'error') return { label: 'daily error', variant: 'danger' as const };
  if (status === 'stale') return { label: 'daily stale', variant: 'warning' as const };
  if (status === 'miss' || status === 'refresh') return { label: 'daily refreshed', variant: 'info' as const };
  if (status === 'hit') return { label: 'daily cached', variant: 'success' as const };
  return { label: 'daily cache unknown', variant: 'default' as const };
};

const hasOfficialDailyData = (item: VietnamWatchItem) => {
  const close = item.dailyClose ?? item.ohlcvClose ?? item.latestPrice ?? item.close;
  const date = item.ohlcvDate ?? item.latestPriceDate ?? item.priceDate ?? item.date;
  return hasDisplayValue(close) && hasDisplayValue(date) && hasDisplayValue(item.volume);
};

const officialDailySourceLabel = (item: VietnamWatchItem) => {
  if (!hasOfficialDailyData(item)) return 'Daily source unavailable';
  const source = item.dataQualitySummary?.canonicalPriceSource
    ?? (isSsiDailyPriceSource(item.latestPriceSource) || isSsiDailyPriceSource(item.actualSource) || isSsiDailyPriceSource(item.source)
      ? 'SSI DailyOhlc'
      : item.latestPriceSource ?? item.actualSource ?? item.source);
  return source ? `Daily source: ${source}` : 'Daily OK';
};

const realtimeSnapshotStateVariant = (state: RealtimeSnapshotDisplayResult) => {
  if (state.severity === 'ok') return 'success' as const;
  if (state.severity === 'info') return 'info' as const;
  if (state.severity === 'warning') return 'warning' as const;
  if (state.severity === 'error') return 'danger' as const;
  return 'default' as const;
};

const realtimeSnapshotTimestamp = (quote?: VietnamRealtimeQuote | null) => (
  quote?.snapshotTimeDisplay
  ?? quote?.realtimeTimeDisplay
  ?? quote?.snapshotTime
  ?? quote?.realtimeTime
  ?? quote?.cachedAt
  ?? quote?.fetchedAt
  ?? null
);

const realtimeAgeSecondsFromTimestamp = (quote?: VietnamRealtimeQuote | null) => {
  const parsed = parseMozyTimestamp(realtimeSnapshotTimestamp(quote));
  if (!parsed) return null;
  return Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 1000));
};

const realtimeSnapshotState = (quote?: VietnamRealtimeQuote | null, marketPhaseCode?: string | null) =>
  getRealtimeSnapshotDisplayState({
    quoteStatus: quote?.status,
    ageSeconds: quote?.ageSeconds ?? realtimeAgeSecondsFromTimestamp(quote),
    isStale: quote?.isStale,
    staleReason: quote?.staleReason,
    marketPhaseCode,
    snapshotTimeDisplay: realtimeSnapshotTimestamp(quote),
  });

const usableRealtimeSessionVolume = (quote?: VietnamRealtimeQuote | null, state?: RealtimeSnapshotDisplayResult) => {
  if (quote?.volumeAccumulated === null || quote?.volumeAccumulated === undefined) return null;
  if (quote.status === 'error' || quote.status === 'unavailable') return null;
  if (quote.isStale === true || state?.severity === 'error' || state?.severity === 'warning') return null;
  return quote.volumeAccumulated;
};

const sessionVolumeToAvgDailyVolume = (
  item: VietnamWatchItem,
  realtimeQuote?: VietnamRealtimeQuote | null,
  state?: RealtimeSnapshotDisplayResult,
) => {
  const avgVolume20D = item.indicators.avgVolume20D ?? item.liquidity?.avgVolume20D;
  const sessionVolume = currentSessionVolume(item, realtimeQuote, state);
  if (avgVolume20D === null || avgVolume20D === undefined || avgVolume20D <= 0) return null;
  if (sessionVolume === null || sessionVolume === undefined) return null;
  return formatRatio(sessionVolume / avgVolume20D);
};

const intradayGranularityText = (item?: VietnamWatchItem | null) => (
  item?.intradayGranularityLabel
  ?? item?.intradayActualGranularity
  ?? item?.intradayGranularity
  ?? item?.intradayPulse?.intradayGranularityLabel
  ?? item?.intradayPulse?.intradayActualGranularity
  ?? item?.intradayPulse?.intradayGranularity
  ?? 'provider-returned'
);

const intradayCadenceStatus = (item?: VietnamWatchItem | null) => (
  item?.intradayCadenceStatus
  ?? item?.intradayStatus?.intradayCadenceStatus
  ?? item?.intradayPulse?.intradayCadenceStatus
  ?? 'unknown'
);

const intradayCadenceText = (item?: VietnamWatchItem | null) => {
  const cadence = intradayGranularityText(item);
  const requested = item?.intradayRequestedTimeframe ?? item?.intradayTimeframe ?? null;
  const status = intradayCadenceStatus(item);
  if (status === 'matched' && requested) return `Provider cadence: ${cadence}`;
  if (status === 'different_from_requested' && requested) return `Returned cadence differs from requested ${requested}: ${cadence}`;
  if (status === 'irregular') return 'Provider cadence irregular';
  if (status === 'unavailable') return 'Provider cadence unavailable';
  return cadence === 'unknown' || cadence === 'provider-returned' ? 'Provider cadence unknown' : `Provider cadence: ${cadence}`;
};

const intradayLatestClose = (item: VietnamWatchItem) => item.intradayPulse?.latestIntradayClose ?? item.intradayPulse?.latest1hClose ?? null;
const intradayLatestHigh = (item: VietnamWatchItem) => item.intradayPulse?.latestIntradayHigh ?? item.intradayPulse?.latest1hHigh ?? null;
const intradayLatestLow = (item: VietnamWatchItem) => item.intradayPulse?.latestIntradayLow ?? item.intradayPulse?.latest1hLow ?? null;
const intradayLatestVolume = (item: VietnamWatchItem) => item.intradayPulse?.latestIntradayVolume ?? item.intradayPulse?.latest1hVolume ?? null;
const intradayChange = (item: VietnamWatchItem) => item.intradayPulse?.intradayChange ?? item.intradayPulse?.latest1hChange ?? null;
const intradayChangePercent = (item: VietnamWatchItem) => item.intradayPulse?.intradayChangePercent ?? item.intradayPulse?.latest1hChangePercent ?? null;
const intradaySessionHigh = (item: VietnamWatchItem) => item.intradayPulse?.sessionHighFromIntraday ?? item.intradayPulse?.sessionHighFrom1H ?? null;
const intradaySessionLow = (item: VietnamWatchItem) => item.intradayPulse?.sessionLowFromIntraday ?? item.intradayPulse?.sessionLowFrom1H ?? null;
const intradaySessionRange = (item: VietnamWatchItem) => item.intradayPulse?.sessionRangePctFromIntraday ?? item.intradayPulse?.sessionRangePctFrom1H ?? null;
const intradaySessionVolume = (item: VietnamWatchItem) => item.intradayPulse?.sessionVolumeFromIntraday ?? item.intradayPulse?.sessionVolumeFrom1H ?? null;
const intradayVolumeVsAverage = (item: VietnamWatchItem) => item.intradayPulse?.intradayVolumeVsAverage ?? item.intradayPulse?.volumeVsAvg1h ?? null;

const hasCurrentIntradayData = (item?: VietnamWatchItem | null) => (
  item?.intradayStatus?.status === 'ok'
  && Boolean(item.intradayPulse)
  && (item.intradayCandles?.length ?? 0) > 0
  && item.dateMatch !== 'mismatched'
);

const hasRealtimeSnapshotData = (quote?: VietnamRealtimeQuote | null) => (
  quote?.status === 'ok'
  && hasDisplayValue(quote.snapshotPrice ?? quote.realtimePrice ?? quote.price)
);

const hasTradeTapeData = (rows?: VietnamRealtimeTrade[] | null) => (
  Array.isArray(rows) && rows.length > 0
);

const readinessFromCoverage = (
  total: number,
  readyCount: number,
  loading: boolean,
): ReadinessState => {
  if (loading && total === 0) return 'Loading';
  if (total === 0) return 'Unavailable';
  if (readyCount === total || readyCount / total >= 0.75) return 'Ready';
  if (readyCount > 0) return 'Partial';
  return 'Unavailable';
};

const normalizedStatus = (status?: string | null) => String(status ?? '').trim().toLowerCase();

const hasReferenceOrForeignData = (item: VietnamWatchItem) => (
  [
    item.dailyStockPrice?.referencePrice,
    item.dailyStockPrice?.ceilingPrice,
    item.dailyStockPrice?.floorPrice,
    item.dailyStockPrice?.foreignBuyVolume,
    item.dailyStockPrice?.foreignSellVolume,
    item.dailyStockPrice?.foreignNetVolume,
    item.dailyStockPrice?.foreignBuyValue,
    item.dailyStockPrice?.foreignSellValue,
    item.dailyStockPrice?.foreignNetValue,
    item.ssiReferencePrice,
    item.ssiCeilingPrice,
    item.ssiFloorPrice,
    item.ssiForeignNetVolume,
    item.ssiForeignNetValue,
    item.priceLimit?.referencePrice,
    item.foreign?.net,
    item.foreign?.netValue,
  ].some(hasDisplayValue)
);

const hasIndicatorData = (item: VietnamWatchItem) => (
  [
    rsi14Value(item),
    finiteNumber(item.indicators.ma20),
    finiteNumber(item.indicators.ma50),
    volumeRatioValue(item),
  ].some((value) => value !== null)
);

const readinessVariant = (item: DataReadinessItem): BadgeVariant => {
  if (item.state === 'Ready') return 'success';
  if (item.state === 'Partial') return 'warning';
  if (item.state === 'Loading') return 'info';
  if (item.state === 'Unavailable' && item.key === 'daily') return 'danger';
  return 'default';
};

const readinessText = (key: ReadinessItemKey, state: ReadinessState) => {
  const copy: Record<ReadinessItemKey, Record<ReadinessState, string>> = {
    daily: {
      Ready: 'Daily data ready',
      Partial: 'Daily data partial',
      Unavailable: 'Daily data unavailable',
      Disabled: 'Daily data disabled',
      Loading: 'Loading daily data',
      'Not implemented': 'Daily data not implemented',
    },
    referenceForeign: {
      Ready: 'Foreign flow ready',
      Partial: 'Foreign flow partial',
      Unavailable: 'Foreign flow unavailable',
      Disabled: 'Reference / foreign disabled',
      Loading: 'Loading reference / foreign',
      'Not implemented': 'Reference / foreign not implemented',
    },
    indicators: {
      Ready: 'Indicators ready',
      Partial: 'Indicators partial',
      Unavailable: 'Indicators unavailable',
      Disabled: 'Indicators disabled',
      Loading: 'Loading indicators',
      'Not implemented': 'Indicators not implemented',
    },
    intraday: {
      Ready: 'Intraday ready',
      Partial: 'Intraday partial',
      Unavailable: 'Intraday unavailable',
      Disabled: 'Intraday disabled',
      Loading: 'Loading intraday',
      'Not implemented': 'Intraday not implemented',
    },
    realtime: {
      Ready: 'Realtime ready',
      Partial: 'Realtime partial',
      Unavailable: 'Realtime unavailable',
      Disabled: 'Realtime disabled',
      Loading: 'Loading realtime',
      'Not implemented': 'Realtime not implemented',
    },
    tradeTape: {
      Ready: 'Trade tape ready',
      Partial: 'Trade tape partial',
      Unavailable: 'Trade tape unavailable',
      Disabled: 'Trade tape disabled',
      Loading: 'Loading trade tape',
      'Not implemented': 'Trade tape not implemented',
    },
    news: {
      Ready: 'News available',
      Partial: 'News partial',
      Unavailable: 'News unavailable',
      Disabled: 'News disabled',
      Loading: 'Loading news',
      'Not implemented': 'News not implemented',
    },
  };
  return copy[key][state];
};

const coverageExplanation = (
  key: Extract<ReadinessItemKey, 'daily' | 'referenceForeign' | 'indicators'>,
  state: ReadinessState,
  total: number,
  readyCount: number,
) => {
  const labels = {
    daily: 'Daily data',
    referenceForeign: 'Reference / foreign',
    indicators: 'Indicators',
  } as const;
  const readyCopy = {
    daily: 'usable SSI DailyOhlc daily fields',
    referenceForeign: 'SSI DailyStockPrice reference or foreign-flow fields',
    indicators: 'technical fields such as RSI14, moving averages, or volume ratio',
  } as const;
  const noRowsCopy = {
    daily: 'no usable daily rows are loaded yet',
    referenceForeign: 'no loaded rows include SSI DailyStockPrice reference or foreign-flow fields',
    indicators: 'no loaded rows include technical fields',
  } as const;
  const label = labels[key];
  if (state === 'Loading') return `${label}: current watchlist is loading and ${noRowsCopy[key]}.`;
  if (state === 'Ready') {
    return readyCount === total
      ? `${label}: all current loaded rows include ${readyCopy[key]}.`
      : `${label}: most current loaded rows include ${readyCopy[key]}.`;
  }
  if (state === 'Partial') return `${label}: some current loaded rows include ${readyCopy[key]}.`;
  return `${label}: ${noRowsCopy[key]} after the current load.`;
};

const statusExplanation = (
  key: Extract<ReadinessItemKey, 'intraday' | 'realtime' | 'news'>,
  state: ReadinessState,
  total: number,
  readyCount: number,
) => {
  const labels = {
    intraday: 'Intraday',
    realtime: 'Realtime',
    news: 'News',
  } as const;
  const readyCopy = {
    intraday: 'existing status/data indicates usable intraday data without assuming a fixed cadence',
    realtime: 'existing realtime status is ok and a usable realtime snapshot is present',
    news: 'existing frontend state includes news rows or ok news status',
  } as const;
  const unavailableCopy = {
    intraday: 'existing intraday status/data is unavailable or unusable in the current response',
    realtime: 'existing realtime status is unavailable or no usable realtime snapshot is present',
    news: 'news readiness is not backed by live news data/status in this phase',
  } as const;
  const disabledCopy = {
    intraday: 'existing intraday status is disabled',
    realtime: 'existing realtime status is disabled',
    news: 'news is disabled because live news data/status is not implemented in this phase',
  } as const;
  const notImplementedCopy = {
    intraday: 'intraday readiness is marked not implemented by the existing status',
    realtime: 'realtime readiness is marked not implemented by the existing status',
    news: 'news is not implemented and no fake news items are shown',
  } as const;
  const label = labels[key];
  if (state === 'Loading') return `${label}: current status is loading from existing frontend state.`;
  if (state === 'Ready') {
    return readyCount === total
      ? `${label}: all current loaded rows show ${readyCopy[key]}.`
      : `${label}: current loaded state shows ${readyCopy[key]}.`;
  }
  if (state === 'Partial') return `${label}: only some current loaded rows show ${readyCopy[key]}.`;
  if (state === 'Disabled') return `${label}: ${disabledCopy[key]}.`;
  if (state === 'Not implemented') return `${label}: ${notImplementedCopy[key]}.`;
  return `${label}: ${unavailableCopy[key]}.`;
};

const tradeTapeExplanation = (state: ReadinessState) => {
  if (state === 'Loading') return 'Trade tape: current trade tape status is loading from existing frontend state.';
  if (state === 'Ready') return 'Trade tape: existing trade tape status is ok and usable trade rows are present.';
  if (state === 'Disabled') return 'Trade tape: existing trade tape status is disabled.';
  if (state === 'Not implemented') return 'Trade tape: trade tape readiness is marked not implemented by the existing status.';
  return 'Trade tape: existing status is unavailable or no usable trade rows are present in the current response.';
};

const liveStateFromCounts = (
  total: number,
  readyCount: number,
  disabledCount: number,
  notImplementedCount: number,
  loading: boolean,
): ReadinessState => {
  if (loading && total === 0) return 'Loading';
  if (total === 0) return 'Unavailable';
  if (readyCount === total || readyCount / total >= 0.75) return 'Ready';
  if (readyCount > 0) return 'Partial';
  if (disabledCount === total) return 'Disabled';
  if (notImplementedCount === total) return 'Not implemented';
  return 'Unavailable';
};

const deriveDataReadiness = ({
  data,
  selectedItem,
  loading,
  realtimeQuotes,
  realtimeLoading,
  realtimeTrades,
  tradesLoading,
  tradesError,
  marketPhase,
}: {
  data?: VietnamWatchlistResponse | null;
  selectedItem?: VietnamWatchItem | null;
  loading: boolean;
  realtimeQuotes: Record<string, VietnamRealtimeQuote | undefined>;
  realtimeLoading: boolean;
  realtimeTrades: VietnamRealtimeTrade[];
  tradesLoading: boolean;
  tradesError?: string | null;
  marketPhase: VietnamMarketPhase;
}): DataReadinessItem[] => {
  const rows = data?.watchlist ?? [];
  const rowCount = rows.length;
  const dailyReadyCount = rows.filter(hasOfficialDailyData).length;
  const referenceForeignReadyCount = rows.filter(hasReferenceOrForeignData).length;
  const indicatorReadyCount = rows.filter(hasIndicatorData).length;
  const dailyState = readinessFromCoverage(rowCount, dailyReadyCount, loading);
  const referenceForeignState = readinessFromCoverage(rowCount, referenceForeignReadyCount, loading);
  const indicatorState = readinessFromCoverage(rowCount, indicatorReadyCount, loading);

  const intradayReadyCount = rows.filter(hasCurrentIntradayData).length;
  const intradayDisabledCount = rows.filter((item) => (
    normalizedStatus(item.intradayStatus?.status ?? item.dataQualitySummary?.checks?.intraday) === 'disabled'
  )).length;
  const intradayNotImplementedCount = rows.filter((item) => (
    normalizedStatus(item.intradayStatus?.status ?? item.dataQualitySummary?.checks?.intraday) === 'not_implemented'
  )).length;
  const intradayState = liveStateFromCounts(rowCount, intradayReadyCount, intradayDisabledCount, intradayNotImplementedCount, loading);

  const realtimeReadyCount = rows.filter((item) => {
    const quote = realtimeQuotes[item.ticker];
    const state = realtimeSnapshotState(quote ?? item.realtimeSnapshot, marketPhase.code);
    return (
      (hasRealtimeSnapshotData(quote) || hasRealtimeSnapshotData(item.realtimeSnapshot))
      && state.severity !== 'warning'
      && state.severity !== 'error'
    );
  }).length;
  const realtimeDisabledCount = rows.filter((item) => (
    normalizedStatus(realtimeQuotes[item.ticker]?.status ?? item.realtimeStatus?.status ?? item.dataQualitySummary?.checks?.realtime) === 'disabled'
  )).length;
  const realtimeNotImplementedCount = rows.filter((item) => (
    normalizedStatus(realtimeQuotes[item.ticker]?.status ?? item.realtimeStatus?.status ?? item.dataQualitySummary?.checks?.realtime) === 'not_implemented'
  )).length;
  const hasAnyRealtimeStatus = rows.some((item) => (
    realtimeQuotes[item.ticker]
    || item.realtimeStatus?.status
    || item.realtimeSnapshot
    || item.dataQualitySummary?.checks?.realtime
  ));
  const realtimeState = liveStateFromCounts(
    rowCount,
    realtimeReadyCount,
    realtimeDisabledCount,
    realtimeNotImplementedCount,
    realtimeLoading && !hasAnyRealtimeStatus,
  );

  const selectedTradeStatus = normalizedStatus(selectedItem?.tradeTapeStatus?.status ?? selectedItem?.dataQualitySummary?.checks?.tradeTape);
  const selectedTradeRows = selectedItem?.tradeTape ?? [];
  const tradeTapeState: ReadinessState = tradesLoading && !hasTradeTapeData(realtimeTrades) && !hasTradeTapeData(selectedTradeRows)
    ? 'Loading'
    : tradesError
      ? 'Unavailable'
      : hasTradeTapeData(realtimeTrades) || (selectedTradeStatus === 'ok' && hasTradeTapeData(selectedTradeRows))
        ? 'Ready'
        : selectedTradeStatus === 'disabled'
          ? 'Disabled'
          : selectedTradeStatus === 'not_implemented'
            ? 'Not implemented'
            : 'Unavailable';

  const newsReadyCount = rows.filter((item) => (item.news?.length ?? 0) > 0 || normalizedStatus(item.newsStatus?.status) === 'ok').length;
  const newsDisabledCount = rows.filter((item) => normalizedStatus(item.newsStatus?.status) === 'disabled').length;
  const newsNotImplementedCount = rows.filter((item) => normalizedStatus(item.newsStatus?.status) === 'not_implemented').length;
  const newsState = liveStateFromCounts(rowCount, newsReadyCount, newsDisabledCount, newsNotImplementedCount, loading);

  return [
    {
      key: 'daily',
      label: 'Daily data',
      state: dailyState,
      detail: readinessText('daily', dailyState),
      explanation: coverageExplanation('daily', dailyState, rowCount, dailyReadyCount),
    },
    {
      key: 'referenceForeign',
      label: 'Reference / foreign',
      state: referenceForeignState,
      detail: readinessText('referenceForeign', referenceForeignState),
      explanation: coverageExplanation('referenceForeign', referenceForeignState, rowCount, referenceForeignReadyCount),
    },
    {
      key: 'indicators',
      label: 'Indicators',
      state: indicatorState,
      detail: readinessText('indicators', indicatorState),
      explanation: coverageExplanation('indicators', indicatorState, rowCount, indicatorReadyCount),
    },
    {
      key: 'intraday',
      label: 'Intraday',
      state: intradayState,
      detail: readinessText('intraday', intradayState),
      explanation: statusExplanation('intraday', intradayState, rowCount, intradayReadyCount),
    },
    {
      key: 'realtime',
      label: 'Realtime',
      state: realtimeState,
      detail: readinessText('realtime', realtimeState),
      explanation: statusExplanation('realtime', realtimeState, rowCount, realtimeReadyCount),
    },
    {
      key: 'tradeTape',
      label: 'Trade tape',
      state: tradeTapeState,
      detail: readinessText('tradeTape', tradeTapeState),
      explanation: tradeTapeExplanation(tradeTapeState),
    },
    {
      key: 'news',
      label: 'News',
      state: newsState,
      detail: readinessText('news', newsState),
      explanation: statusExplanation('news', newsState, rowCount, newsReadyCount),
    },
  ];
};

const DataReadinessStrip: React.FC<{
  data?: VietnamWatchlistResponse | null;
  selectedItem?: VietnamWatchItem | null;
  loading: boolean;
  realtimeQuotes: Record<string, VietnamRealtimeQuote | undefined>;
  realtimeLoading: boolean;
  realtimeTrades: VietnamRealtimeTrade[];
  tradesLoading: boolean;
  tradesError?: string | null;
  marketPhase: VietnamMarketPhase;
}> = ({
  data,
  selectedItem,
  loading,
  realtimeQuotes,
  realtimeLoading,
  realtimeTrades,
  tradesLoading,
  tradesError,
  marketPhase,
}) => {
  const items = deriveDataReadiness({
    data,
    selectedItem,
    loading,
    realtimeQuotes,
    realtimeLoading,
    realtimeTrades,
    tradesLoading,
    tradesError,
    marketPhase,
  });

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" data-testid="data-readiness-strip">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-foreground">Data readiness</h2>
            <Badge variant="default">Visual only</Badge>
          </div>
          <p className="mt-1 text-xs text-secondary-text">
            Derived from loaded dashboard data. Provider diagnostics stay in Data status.
          </p>
        </div>
      </div>
      <dl className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {items.map((item) => (
          <div
            key={item.key}
            className="rounded-lg border border-border/50 bg-elevated/40 p-3"
            role="group"
            aria-label={item.explanation}
            title={item.explanation}
          >
            <dt className="flex items-center justify-between gap-2 text-xs font-medium text-secondary-text">
              <span>{item.label}</span>
              <Badge variant={readinessVariant(item)}>{item.state}</Badge>
            </dt>
            <dd className="mt-2 text-sm font-medium text-foreground">{item.detail}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
};

const currentSessionVolume = (
  item: VietnamWatchItem,
  realtimeQuote?: VietnamRealtimeQuote | null,
  state?: RealtimeSnapshotDisplayResult,
) => usableRealtimeSessionVolume(realtimeQuote, state) ?? (
  hasCurrentIntradayData(item) ? intradaySessionVolume(item) : null
);

const rawRealtimeFreshnessText = (quote?: VietnamRealtimeQuote | null) => (
  `raw age ${quote?.ageSeconds ?? '-'}s | raw stale ${quote?.isStale === null || quote?.isStale === undefined ? '-' : String(quote.isStale)} | reason ${quote?.staleReason ?? '-'}`
);

const formatRealtimeAge = (seconds: number) => {
  const safeSeconds = Math.max(0, Math.trunc(seconds));
  if (safeSeconds < 60) return `${safeSeconds}s`;
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
};

const realtimeSnapshotFreshnessText = (quote?: VietnamRealtimeQuote | null) => {
  if (!quote) return 'SSI realtime unavailable';
  const age = typeof quote.ageSeconds === 'number' && Number.isFinite(quote.ageSeconds)
    ? quote.ageSeconds
    : realtimeAgeSecondsFromTimestamp(quote);
  const ttl = typeof quote.cacheTtlSeconds === 'number' && Number.isFinite(quote.cacheTtlSeconds)
    ? Math.max(0, Math.trunc(quote.cacheTtlSeconds))
    : null;
  if (quote.isStale === true && ttl !== null) return `stale >${ttl}s`;
  if (age !== null && age !== undefined) return `updated ${formatRealtimeAge(age)} ago`;
  if (parseMozyTimestamp(realtimeSnapshotTimestamp(quote))) return `updated ${formatRelativeAge(realtimeSnapshotTimestamp(quote))}`;
  return 'SSI realtime time unknown';
};

const realtimeSnapshotTimeText = (quote?: VietnamRealtimeQuote | null) => {
  const timestamp = realtimeSnapshotTimestamp(quote);
  if (!parseMozyTimestamp(timestamp)) return 'SSI realtime time unknown';
  return formatVietnamTime(timestamp);
};

const companyDisplayName = (item?: VietnamWatchItem | null) => {
  if (!item) return null;
  const name = item.companyName ?? item.name ?? item.symbolMetadata?.name ?? item.entity;
  if (!name || name === item.ticker || name === item.entity) return null;
  return name;
};

const metadataValue = (item: VietnamWatchItem, key: 'exchange' | 'market' | 'securityType' | 'industry' | 'sector' | 'issuer' | 'lotSize' | 'listedShares' | 'listedDate') => (
  item.symbolMetadata?.[key] ?? item[key] ?? null
);

const sumSsiForeignNetVolume = (items: VietnamWatchItem[]) => (
  items.reduce((sum, item) => {
    const value = finiteNumber(item.ssiForeignNetVolume);
    return value === null ? sum : sum + value;
  }, 0)
);

const getDashboardPresetTickers = (presetId: VietnamDashboardPresetId) => {
  const preset = VIETNAM_DASHBOARD_PRESETS.find((item) => item.id === presetId);
  return preset ? normalizeVietnamWatchlist(preset.tickers) : null;
};

const formatCustomWatchlistInput = (tickers: string[]) => tickers.join(', ');

const parseCustomWatchlistInput = (value: string) => {
  const rawTokens = value
    .split(/[,\s;]+/)
    .map((ticker) => ticker.trim())
    .filter(Boolean);

  if (!rawTokens.length) {
    return { tickers: [] as string[], messages: [] as string[], error: 'Custom watchlist is empty.' };
  }

  const normalizedTokens = rawTokens.map((ticker) => normalizeVietnamTicker(ticker));
  const invalidTickers = normalizedTokens.filter((ticker) => !/^[A-Z0-9]{2,10}$/.test(ticker));
  if (invalidTickers.length) {
    return { tickers: [] as string[], messages: [] as string[], error: `Invalid tickers: ${Array.from(new Set(invalidTickers)).join(', ')}` };
  }

  const seen = new Set<string>();
  const deduped: string[] = [];
  let duplicateRemoved = false;
  for (const ticker of normalizedTokens) {
    if (seen.has(ticker)) {
      duplicateRemoved = true;
      continue;
    }
    seen.add(ticker);
    deduped.push(ticker);
  }

  const messages: string[] = [];
  if (duplicateRemoved) messages.push('Duplicate tickers removed.');
  const tickers = deduped.slice(0, VIETNAM_WATCHLIST_MAX_SIZE);
  if (deduped.length > VIETNAM_WATCHLIST_MAX_SIZE) messages.push('Only first 30 tickers kept.');

  return { tickers, messages, error: null };
};

const localStorageOrNull = () => {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

const readCustomWatchlist = () => {
  const storage = localStorageOrNull();
  if (!storage) return [] as string[];
  try {
    const raw = storage.getItem(CUSTOM_WATCHLIST_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.some((value) => typeof value !== 'string')) return [];
    const result = parseCustomWatchlistInput(parsed.join(','));
    return result.error ? [] : result.tickers;
  } catch {
    return [];
  }
};

const writeCustomWatchlist = (tickers: string[]) => {
  const storage = localStorageOrNull();
  if (!storage) return false;
  try {
    storage.setItem(CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(tickers));
    return true;
  } catch {
    return false;
  }
};

const clearCustomWatchlist = () => {
  const storage = localStorageOrNull();
  if (!storage) return false;
  try {
    storage.removeItem(CUSTOM_WATCHLIST_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
};

const isCompleteWatchlistResponse = (response: VietnamWatchlistResponse, requestedTickers: string[]) => {
  const expectedTickers = requestedTickers
    .map((ticker) => normalizeVietnamTicker(ticker))
    .filter(Boolean);
  if (!expectedTickers.length) return true;
  const actualTickers = new Set((response.watchlist ?? []).map((item) => normalizeVietnamTicker(item.ticker)));
  return expectedTickers.every((ticker) => actualTickers.has(ticker));
};

const newsUnavailableText = (item: VietnamWatchItem) => (
  item.newsStatus?.status === 'disabled'
    ? 'News disabled'
    : item.newsStatus?.message ?? 'News not implemented.'
);

const newsContextStatusLabel = (item: VietnamWatchItem, newsCount: number) => {
  if (newsCount > 0) return 'News available';
  if (item.newsStatus?.status === 'disabled') return 'News disabled';
  return 'News not implemented';
};

const realtimeErrorMessage = (error?: string | null) => {
  if (!error) return null;
  const lower = error.toLowerCase();
  if (lower.includes('timeout') || lower.includes('timed out') || error.includes('è¶…æ—¶')) return 'SSI realtime provider timeout';
  if (lower.includes('network') || lower.includes('proxy') || error.includes('ç½‘ç»œ') || error.includes('ä»£ç†')) {
    return 'SSI realtime network/proxy issue';
  }
  return error;
};

const realtimeIssueSummary = (realtimeError?: string | null, tradesError?: string | null) => {
  if (realtimeError) return 'SSI realtime unavailable. Daily SSI data is still available.';
  if (tradesError) return 'SSI trade tape unavailable. Daily SSI data is still available.';
  return null;
};

const LIVE_STATUS_DIAGNOSTIC_PATTERN = /(attempted endpoint|endpoint|http(?:\s*status)?\s*\d|http status|raw provider|raw error|token|authorization|access token|account)/i;

const safeLiveStatusString = (value: unknown) => {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  if (!text || LIVE_STATUS_DIAGNOSTIC_PATTERN.test(text)) return null;
  return text;
};

type DiagnosticRow = {
  section: string;
  label: string;
  value: string;
};

type OptionalLiveStatusBlock = {
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

const diagnosticLabel = (key: string) => {
  const knownLabels: Record<string, string> = {
    attemptedEndpoints: 'Attempted endpoints',
    attempted_endpoints: 'Attempted endpoints',
    lastEndpoint: 'Last endpoint',
    last_endpoint: 'Last endpoint',
    httpStatus: 'HTTP status',
    http_status: 'HTTP status',
    providerMessage: 'Provider message',
    provider_message: 'Provider message',
    rawProviderErrorSummary: 'Provider error summary',
    raw_provider_error_summary: 'Provider error summary',
    sanitizedErrorContext: 'Sanitized error context',
    sanitized_error_context: 'Sanitized error context',
    retryable: 'Retryable',
  };
  if (knownLabels[key]) return knownLabels[key];
  const words = key.replace(/([A-Z])/g, ' $1').replaceAll('_', ' ').trim();
  return words ? `${words.charAt(0).toUpperCase()}${words.slice(1)}` : key;
};

const diagnosticValueText = (value: unknown): string | null => {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    const values = value.map(diagnosticValueText).filter((entry): entry is string => Boolean(entry));
    return values.length ? values.join(', ') : null;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

const liveStatusDiagnosticRows = (
  section: string,
  diagnostics?: Record<string, unknown> | null,
): DiagnosticRow[] => (
  Object.entries(diagnostics ?? {})
    .map(([key, value]) => ({
      section,
      label: diagnosticLabel(key),
      value: diagnosticValueText(value),
    }))
    .filter((row): row is DiagnosticRow => Boolean(row.value))
);

const optionalStatusDiagnosticValue = (block: OptionalLiveStatusBlock | null | undefined, key: string): string | null => {
  const direct = (block as Record<string, unknown> | null | undefined)?.[key];
  const nested = block?.diagnostics?.[key];
  return safeLiveStatusString((direct ?? nested) as unknown);
};

const optionalLiveReasonCode = (block?: OptionalLiveStatusBlock | null) => (
  safeLiveStatusString(block?.reasonCode)
  ?? safeLiveStatusString(block?.classification)
  ?? optionalStatusDiagnosticValue(block, 'reasonCode')
  ?? optionalStatusDiagnosticValue(block, 'reason_code')
);

const optionalLiveMessage = (block?: OptionalLiveStatusBlock | null) => safeLiveStatusString(block?.message);

const optionalLiveStatusText = (
  section: 'intraday' | 'realtime' | 'tradeTape',
  block?: OptionalLiveStatusBlock | null,
) => {
  const status = normalizedStatus(block?.status);
  const reasonCode = optionalLiveReasonCode(block);
  const copyByReason: Record<string, string> = {
    cadence_mismatch: 'SSI IntradayOhlc cadence differs from the requested timeframe.',
    unavailable_rate_limited: 'SSI IntradayOhlc is rate-limited by the provider.',
    unavailable_date_mismatch: 'SSI IntradayOhlc latest candle date does not match the latest daily trading date.',
    unavailable_no_rows: section === 'tradeTape'
      ? 'SSI trade tape returned no trade rows.'
      : 'SSI IntradayOhlc returned no usable candles.',
    unavailable_provider_error: section === 'tradeTape'
      ? 'SSI trade tape provider unavailable.'
      : 'SSI IntradayOhlc provider unavailable.',
    config_disabled: 'SSI streaming realtime manager disabled.',
    disabled: section === 'intraday'
      ? 'SSI IntradayOhlc is disabled.'
      : section === 'realtime'
        ? 'SSI realtime is disabled.'
        : 'SSI trade tape is disabled.',
    not_started: 'SSI streaming realtime manager not started.',
    bootstrap_symbols_empty: 'SSI streaming realtime bootstrap symbols empty.',
    ticker_not_bootstrapped: 'Ticker is not in the configured SSI realtime bootstrap list.',
    running_idle: 'SSI stream is running but no recent tick is cached for this ticker.',
    cache_empty: 'SSI realtime stream cache is empty for this ticker.',
    cache_stale: 'SSI realtime stream cache is stale; realtime is event-driven and may stop updating outside active ticks.',
    connection_error: 'SSI realtime connection unavailable.',
    auth_or_entitlement_failure: 'SSI realtime authentication or entitlement failed.',
    network_or_tls_failure: 'SSI realtime network or TLS connection failed.',
    rate_limited: 'SSI realtime provider rate-limited the request.',
    latest_trade_stream_only: 'Historical trade tape is unavailable. X-TRADE is latest-trade stream context only.',
    not_implemented: section === 'tradeTape'
      ? 'Historical trade tape is not proven by current SSI evidence.'
      : 'This optional live section is not implemented.',
  };
  if (reasonCode && copyByReason[reasonCode]) return copyByReason[reasonCode];
  const safeMessage = optionalLiveMessage(block);
  if (safeMessage) return safeMessage;
  if (status === 'disabled') return copyByReason.disabled;
  if (section === 'realtime') return 'SSI realtime unavailable. Daily SSI data is still available.';
  if (section === 'tradeTape') return 'SSI trade tape unavailable.';
  return 'SSI intraday unavailable.';
};

const realtimeUnavailableStatusText = (block?: OptionalLiveStatusBlock | null) => {
  const text = optionalLiveStatusText('realtime', block);
  return /daily SSI data is still available/i.test(text) ? text : `${text} Daily SSI data is still available.`;
};

const realtimeStatusBadgeText = (status?: string | null) => (
  status === 'unavailable' || status === 'error' ? 'SSI realtime unavailable' : 'SSI realtime'
);

const tradeTapeStatusBadgeText = (status?: string | null) => (
  status === 'unavailable' || status === 'error' ? 'SSI trade tape unavailable' : 'SSI trade tape'
);

const realtimeSnapshotSummaryText = (quote: VietnamRealtimeQuote | null | undefined, state: RealtimeSnapshotDisplayResult) => {
  const cleanError = realtimeErrorMessage(quote?.error);
  if (cleanError) return cleanError;
  const freshness = realtimeSnapshotFreshnessText(quote);
  if (state.label === 'Last available SSI realtime') return `Last available - ${freshness}`;
  return `${state.label} - ${freshness}`;
};

const realtimeProviderStatus = (
  quotes: Record<string, VietnamRealtimeQuote | undefined>,
  activeTickers: string[],
  quoteError?: string | null,
  tradesError?: string | null,
) => {
  const activeQuotes = activeTickers.map((ticker) => quotes[ticker]).filter((quote): quote is VietnamRealtimeQuote => Boolean(quote));
  const staleCount = activeQuotes.filter((quote) => quote.isStale === true).length;
  const unavailableCount = activeQuotes.filter((quote) => quote.status === 'unavailable' || quote.status === 'error').length;
  if (activeQuotes.some((quote) => quote.status === 'error')) {
    return { label: 'error', variant: 'danger' as const, staleCount, unavailableCount };
  }
  if (unavailableCount > 0 || !activeQuotes.length) {
    return { label: 'unavailable', variant: 'warning' as const, staleCount, unavailableCount };
  }
  if (quoteError || tradesError) {
    return { label: 'error', variant: 'danger' as const, staleCount, unavailableCount };
  }
  if (staleCount > 0) {
    return { label: 'stale', variant: 'warning' as const, staleCount, unavailableCount };
  }
  return { label: 'ok', variant: 'success' as const, staleCount, unavailableCount };
};

const importantWarnings = (item: VietnamWatchItem) => {
  const suppressLegacyForeignCaveats = hasAvailableSsiDailyStockPrice(item);
  return (item.warnings ?? []).filter((warning) =>
    [
      'Quote does not provide a reliable latest price field',
      'latest price uses OHLCV close',
      'Foreign net date does not match',
      'Final close status is unknown',
      'Adjusted/unadjusted price status is unknown',
      'Intraday candle data is not a realtime matched quote',
      'stale cached data',
    ].some((needle) => warning.includes(needle)),
  ).filter((warning) => !(
    suppressLegacyForeignCaveats
    && (
      warning.includes('Foreign net date does not match')
      || warning.includes('Foreign net is not confirmed as same-day flow')
    )
  ));
};

const watchlistScanState = (
  item: VietnamWatchItem,
  realtimeQuote?: VietnamRealtimeQuote | null,
  marketPhaseCode?: string | null,
): WatchlistScanState => {
  const labels = marketStatusLabels(item, item.statusLabels?.length ?? 0).map((label) => label.toLowerCase());
  const realtimeState = realtimeSnapshotState(realtimeQuote, marketPhaseCode);
  const dailyFreshness = officialDailyCacheFreshness(item);

  if (item.status === 'unavailable' || item.error || !hasOfficialDailyData(item)) {
    return { label: 'Data unavailable', variant: 'default', reason: 'Missing required daily fields' };
  }
  if (dailyFreshness.variant === 'danger') {
    return { label: 'Data unavailable', variant: 'danger', reason: 'SSI DailyOhlc source error' };
  }
  if (
    realtimeState.severity === 'warning' ||
    realtimeState.severity === 'error' ||
    labels.some((label) =>
      ['weak', 'risk', 'caution', 'negative', 'low liquidity', 'overextended'].some((needle) => label.includes(needle)),
    )
  ) {
    return { label: 'Weakening', variant: 'warning', reason: realtimeState.severity === 'warning' || realtimeState.severity === 'error' ? 'SSI realtime needs context' : 'Neutral labels show caution' };
  }

  const constructiveLabelCount = labels.filter((label) =>
    ['stronger', 'expansion', 'positive', 'intraday up'].some((needle) => label.includes(needle)),
  ).length;
  if (constructiveLabelCount >= 2 && (item.liquidity.score ?? 0) >= 70) {
    return { label: 'Strong', variant: 'success', reason: 'Constructive labels with liquidity' };
  }
  if (constructiveLabelCount > 0) {
    return { label: 'Improving', variant: 'info', reason: 'Constructive neutral labels' };
  }
  return { label: 'Neutral', variant: 'default', reason: 'No strong directional condition' };
};

const scanTone = (label: WatchlistScanLabel) => {
  if (label === 'Strong') return 'text-success';
  if (label === 'Improving') return 'text-cyan';
  if (label === 'Weakening') return 'text-warning';
  if (label === 'Risk elevated') return 'text-danger';
  return 'text-secondary-text';
};

const DataCaveatDisclosure: React.FC<{ item: VietnamWatchItem; className?: string; testId?: string }> = ({ item, className, testId }) => {
  const caveats = dataCaveatDetails(item);
  const warnings = importantWarnings(item);
  const total = caveats.length + warnings.length;
  if (!total) return null;

  return (
    <details className={cn('rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text', className)} data-testid={testId}>
      <summary className="cursor-pointer font-medium text-foreground">
        Data caveats ({total})
      </summary>
      <div className="mt-3 space-y-2">
        {caveats.map((detail) => (
          <div key={`${item.ticker}-caveat-disclosure-${detail.label}`} className="flex gap-2">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
            <span><span className="text-foreground">{detail.label}:</span> {detail.reason}</span>
          </div>
        ))}
        {warnings.map((warning) => (
          <div key={`${item.ticker}-warning-disclosure-${warning}`} className="flex gap-2">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
            <span>{warning}</span>
          </div>
        ))}
      </div>
    </details>
  );
};

const WatchCard: React.FC<{ item: VietnamWatchItem; realtimeQuote?: VietnamRealtimeQuote | null; marketPhase: VietnamMarketPhase }> = ({ item, realtimeQuote, marketPhase }) => {
  const positive = (item.changePct ?? 0) >= 0;
  const TrendIcon = positive ? ArrowUpRight : ArrowDownRight;
  const lastFetched = latestFetchedValue(item);
  const realtimeState = realtimeSnapshotState(realtimeQuote, marketPhase.code);
  const sessionVolumeRatioText = sessionVolumeToAvgDailyVolume(item, realtimeQuote, realtimeState);
  const hasRealtimeSnapshot = hasRealtimeSnapshotData(realtimeQuote);
  const hasIntradayPulse = hasCurrentIntradayData(item);
  const newsItems = item.news ?? [];

  return (
    <article className="rounded-lg border border-border/70 bg-card p-4 shadow-soft-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-foreground">
              <a
                href={`/vietnam/company/${item.ticker}`}
                className="text-foreground hover:text-cyan"
                aria-label={`Open ${item.ticker} company research`}
              >
                {item.ticker}
              </a>
            </h2>
            <Badge variant="info">{item.exchange ?? 'VN'}</Badge>
            <Badge variant="default">{item.marketIndex ?? 'VNINDEX.VN'}</Badge>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {marketStatusLabels(item, 3).map((label) => (
              <Badge key={label} variant={statusVariant(label)}>{label}</Badge>
            ))}
            {marketStatusLabels(item, item.statusLabels?.length ?? 0).length > 3 ? <Badge variant="default">+{marketStatusLabels(item, item.statusLabels?.length ?? 0).length - 3}</Badge> : null}
          </div>
          <p className="mt-1 text-xs text-secondary-text">
            Price date {item.latestPriceDate ?? item.priceDate ?? '-'} | refreshed {formatRelativeAge(lastFetched)}
          </p>
        </div>
        <div className={cn('flex items-center gap-1 text-sm font-semibold', signalTone(item.changePct))}>
          <TrendIcon className="h-4 w-4" />
          {formatNumber(item.changePct, 2)}%
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-secondary-text">Official daily close (SSI DailyOhlc)</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <p className="text-lg font-semibold text-foreground">{formatPrice(item.latestPrice ?? item.close)}</p>
            <Badge variant={priceSourceVariant(item.latestPriceSource)}>{(item.latestPriceSource ?? 'unknown').toUpperCase()}</Badge>
          </div>
          <p className="text-xs text-secondary-text">OHLCV close {formatPrice(item.ohlcvClose ?? item.close)}</p>
        </div>
        {hasRealtimeSnapshot ? (
        <div>
          <p className="text-xs text-secondary-text">SSI realtime</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <p className="text-lg font-semibold text-foreground">{formatPrice(realtimeQuote?.realtimePrice)}</p>
            <Badge variant={realtimeSnapshotStateVariant(realtimeState)}>{realtimeState.label}</Badge>
          </div>
          <p className={cn('text-xs', signalTone(realtimeQuote?.priceChange))}>
            {formatPrice(realtimeQuote?.priceChange)} / {formatNumber(realtimeQuote?.percentChange, 2)}%
          </p>
          <p className="text-xs text-secondary-text">{realtimeSnapshotSummaryText(realtimeQuote, realtimeState)}</p>
        </div>
        ) : null}
        <div>
          <p className="text-xs text-secondary-text">Daily OHLCV volume</p>
          <p className="text-lg font-semibold text-foreground">{formatNumber(item.volume)}</p>
        </div>
        <div>
          <p className="text-xs text-secondary-text">20D liquidity</p>
          <Badge variant={liquidityVariant(item.liquidity.score)}>{item.liquidity.score ?? 0}/100</Badge>
        </div>
        <div>
          <p className="text-xs text-secondary-text">RSI14 Wilder/RMA</p>
          <p className="font-semibold text-foreground">{formatNumber(item.indicators.rsi14Wilder ?? item.indicators.rsi14, 2)}</p>
        </div>
        {sessionVolumeRatioText ? (
        <div>
          <p className="text-xs text-secondary-text">Session volume / 20D avg daily volume</p>
          <p className="font-semibold text-foreground">{sessionVolumeRatioText}</p>
        </div>
        ) : null}
        <div>
          <p className="text-xs text-secondary-text">Daily cache</p>
          <Badge variant={officialDailyCacheFreshness(item).variant}>{officialDailyCacheFreshness(item).label}</Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-2 rounded-lg border border-border/60 bg-elevated/40 p-3 text-xs">
        <div className="flex items-center justify-between gap-2">
          <span className="text-secondary-text">Limit band</span>
          <span className="text-foreground">
            +/-{formatNumber(item.priceLimit.limitPct, 1)}%, distance {formatNumber(item.priceLimit.distanceToLimitPct, 2)}%
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-secondary-text">{foreignLabel(item.foreign.signal)} ({item.foreignNetUnit ?? 'unknown'})</span>
          <span className={cn('font-medium', signalTone(item.foreign.net))}>{formatNumber(item.foreign.net)}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-secondary-text">Price / foreign dates</span>
          <span className="flex flex-wrap justify-end gap-1">
            <Badge variant="default">{item.latestPriceDate ?? item.priceDate ?? '-'}</Badge>
            <Badge variant={dateMatchVariant(item.foreignDateMatch)}>{item.foreignDateMatch ?? 'unknown'}</Badge>
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-secondary-text">Final close</span>
          <Badge variant={item.finalCloseStatus === 'final' ? 'success' : item.finalCloseStatus === 'not_final' ? 'warning' : 'default'}>
            {finalCloseDisplayLabel(item.finalCloseStatus)}
          </Badge>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-secondary-text">OHLC (VND)</span>
          <span className="text-foreground">
            {formatPrice(item.open)} / {formatPrice(item.high)} / {formatPrice(item.low)}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-secondary-text">Rows loaded</span>
          <span className="text-foreground">{formatNumber(item.rowsLoaded)}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-secondary-text">MA20 / MA50</span>
          <span className="text-foreground">{formatPrice(item.indicators.ma20)} / {formatPrice(item.indicators.ma50)}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-secondary-text">Latest source refresh</span>
          <span className="text-foreground">{formatVietnamTime(lastFetched)} ({formatRelativeAge(lastFetched)})</span>
        </div>
      </div>

      {hasIntradayPulse ? (
        <div className="mt-3 rounded-lg border border-border/60 bg-elevated/40 p-3 text-xs">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-foreground">Intraday pulse ({intradayGranularityText(item)})</span>
            <div className="flex flex-wrap gap-1">
              {(item.intradayLabels ?? []).slice(0, 2).map((label) => (
                <Badge key={`${item.ticker}-${label}`} variant={intradayVariant(label)}>{label}</Badge>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-secondary-text">
            <span>Intraday close {formatPrice(intradayLatestClose(item))}</span>
            <span className={signalTone(intradayChange(item))}>Change {formatPrice(intradayChange(item))} ({formatNumber(intradayChangePercent(item), 2)}%)</span>
            <span>Time {formatVietnamTime(item.intradayCandles?.at(-1)?.dateTime ?? item.intradayCandles?.at(-1)?.timestamp)}</span>
            <span>Range {formatNumber(item.intradayPulse?.rangePercent, 2)}%</span>
            <span>Latest intraday volume {formatNumber(intradayLatestVolume(item))}</span>
          </div>
        </div>
      ) : null}

      <DataCaveatDisclosure item={item} className="mt-3" />
      <details className="mt-3 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
        <summary className="cursor-pointer font-medium text-foreground">Advanced / Raw Data</summary>
        <div className="mt-3 grid gap-2">
          <div>Raw latest price field: {item.latestPriceRawField ?? '-'}</div>
          <div>Raw quote price field: {item.quotePriceRawField ?? '-'}</div>
          <div>Foreign raw fields: {item.foreignBuyRawField ?? '-'} / {item.foreignSellRawField ?? '-'}</div>
          <div>Raw latest price timestamp: {rawDateLabel(item.latestPriceDate)}</div>
          <div>Raw quote timestamp: {rawDateLabel(item.quoteDate)}</div>
          <div>Raw intraday timestamp: {rawDateLabel(item.intradayCandles?.at(-1)?.dateTime ?? item.intradayCandles?.at(-1)?.timestamp)}</div>
          <div>Cache status: {JSON.stringify(item.cacheStatus)}</div>
        </div>
      </details>

      {newsItems.length > 0 ? (
        <div className="mt-3 border-t border-border/60 pt-3">
          <p className="mb-2 text-xs font-medium text-secondary-text">Latest news</p>
          {newsItems.slice(0, 2).map((news, index) => {
            const timestamp = newsTimestamp(news);
            const absoluteTime = parseMozyTimestamp(timestamp) ? formatAbsoluteDateTime(timestamp) : undefined;
            return (
              <div key={`${news.title}-${news.url ?? index}`} className="min-w-0">
                <a
                  href={news.url || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="block truncate text-sm text-cyan hover:underline"
                >
                  {neutralizeRecommendationText(news.title) || 'Untitled news'}
                </a>
                <div className="truncate text-xs text-secondary-text" title={absoluteTime}>
                  {[news.source, formatRelativeTime(timestamp)].filter(Boolean).join(' · ')}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </article>
  );
};

const IndexCoveragePanel: React.FC<{
  dailyIndex?: VietnamDailyIndexResponse | null;
  indexList?: VietnamIndexListResponse | null;
  indexComponents?: VietnamIndexComponentsResponse | null;
  error?: string | null;
}> = ({ dailyIndex, indexList, indexComponents, error }) => {
  const sampleCodes = (indexList?.rows ?? [])
    .map((row) => row.indexCode)
    .filter((code): code is string => Boolean(code))
    .slice(0, 8);
  const listStatus = indexList?.status ?? (error ? 'unavailable' : 'loading');
  const componentStatus = indexComponents?.status ?? (error ? 'unavailable' : 'loading');
  const componentCount = indexComponents?.count ?? indexComponents?.rows?.length ?? 0;
  const componentUnavailable = componentStatus !== 'ok' || componentCount === 0;

  return (
    <div className="mt-3 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">SSI index coverage</p>
          <p className="mt-1">SSI IndexList, DailyIndex, and IndexComponents diagnostics. No alternate provider fallback is used for index data.</p>
        </div>
        <Badge variant="default">SSI</Badge>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <div className="rounded-lg bg-card/60 p-3">
          <dt className="text-xs text-secondary-text">IndexList source/status/count</dt>
          <dd className="mt-1 font-medium text-foreground">
            {indexList?.source ?? 'SSI IndexList'} / {listStatus} / {formatNumber(indexList?.count ?? indexList?.rows?.length ?? 0)}
          </dd>
          <dd className="mt-2 flex flex-wrap gap-1">
            {sampleCodes.length ? sampleCodes.map((code) => (
              <Badge key={code} variant="default">{code}</Badge>
            )) : (
              <span>Sample index codes unavailable</span>
            )}
          </dd>
        </div>
        <div className="rounded-lg bg-card/60 p-3">
          <dt className="text-xs text-secondary-text">DailyIndex source/status/count</dt>
          <dd className="mt-1 font-medium text-foreground">
            {dailyIndex?.source ?? 'SSI DailyIndex'} / {dailyIndex?.status ?? (error ? 'unavailable' : 'loading')} / {formatNumber(dailyIndex?.count ?? dailyIndex?.rows?.length ?? 0)}
          </dd>
          <dd className="mt-2">
            {dailyIndex?.latestDate ? `Latest row date ${dailyIndex.latestDate}` : 'Daily index rows unavailable'}
          </dd>
        </div>
        <div className="rounded-lg bg-card/60 p-3">
          <dt className="text-xs text-secondary-text">VN30 components source/status/count</dt>
          <dd className="mt-1 font-medium text-foreground">
            {indexComponents?.source ?? 'SSI IndexComponents'} / {componentStatus} / {formatNumber(componentCount)}
          </dd>
          <dd className="mt-2">
            {componentUnavailable
              ? 'VN30 components unavailable from SSI.'
              : `${formatNumber(componentCount)} component rows returned by SSI`}
          </dd>
        </div>
      </div>
      {error ? <p className="mt-2 text-warning">{error}</p> : null}
    </div>
  );
};

const IndexContextPanel: React.FC<{
  dailyIndex?: VietnamDailyIndexResponse | null;
  indexComponents?: VietnamIndexComponentsResponse | null;
}> = ({ dailyIndex, indexComponents }) => {
  const rows = dailyIndex?.status === 'ok' || dailyIndex?.status === 'partial'
    ? dailyIndex.rows.filter((row) => row.status === 'ok' && hasDisplayValue(row.indexValue))
    : [];
  const componentCount = indexComponents?.status === 'ok'
    ? indexComponents.rows.length
    : 0;

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" data-testid="index-context">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground">Market index context</h2>
          <p className="mt-1 text-xs text-secondary-text">Optional SSI index data. Ticker daily prices remain sourced from SSI DailyOhlc.</p>
        </div>
        <Badge variant={rows.length ? 'success' : dailyIndex ? 'warning' : 'default'}>
          {rows.length ? dailyIndex?.status ?? 'ok' : dailyIndex ? 'unavailable' : 'loading'}
        </Badge>
      </div>
      {rows.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {rows.map((row) => (
            <article key={row.indexCode} className="rounded-lg border border-border/60 bg-elevated/30 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold text-foreground">{row.indexCode}</h3>
                <div className="flex flex-wrap gap-1">
                  <Badge variant="default">{row.source || 'SSI DailyIndex'}</Badge>
                  <Badge variant={row.dateMatch === 'matched' ? 'success' : 'warning'}>
                    {row.dateMatch || 'unknown date'}
                  </Badge>
                </div>
              </div>
              <p className="mt-2 text-xl font-semibold text-foreground">{formatNumber(row.indexValue)}</p>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-secondary-text">
                {hasDisplayValue(row.change) ? <span>Change {formatSignedNumber(row.change, 2)}</span> : null}
                {hasDisplayValue(row.changePct) ? <span>{formatSignedNumber(row.changePct, 2)}%</span> : null}
                {row.date ? <span>Date {row.date}</span> : null}
              </div>
              {hasDisplayValue(row.advances) || hasDisplayValue(row.declines) || hasDisplayValue(row.unchanged) ? (
                <p className="mt-2 text-xs text-secondary-text">
                  Breadth: {[
                    hasDisplayValue(row.advances) ? `advancing ${formatNumber(row.advances)}` : null,
                    hasDisplayValue(row.declines) ? `declining ${formatNumber(row.declines)}` : null,
                    hasDisplayValue(row.unchanged) ? `unchanged ${formatNumber(row.unchanged)}` : null,
                  ].filter(Boolean).join(' · ')}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      ) : dailyIndex ? (
        <p className="mt-3 text-sm text-secondary-text">SSI daily index unavailable.</p>
      ) : (
        <p className="mt-3 text-sm text-secondary-text">Loading SSI daily index context...</p>
      )}
      <div className="mt-3 border-t border-border/60 pt-3 text-xs text-secondary-text">
        {componentCount > 0 ? (
          <span>{formatNumber(componentCount)} VN30 component rows returned by SSI IndexComponents.</span>
        ) : indexComponents ? (
          <span>SSI index components unavailable.</span>
        ) : (
          <span>Loading SSI index components...</span>
        )}
      </div>
    </section>
  );
};

const DataStatusPanel: React.FC<{
  data?: VietnamWatchlistResponse | null;
  selectedItem?: VietnamWatchItem | null;
  dailyIndex?: VietnamDailyIndexResponse | null;
  indexList?: VietnamIndexListResponse | null;
  indexComponents?: VietnamIndexComponentsResponse | null;
  indexCoverageError?: string | null;
  realtimeQuotes: Record<string, VietnamRealtimeQuote | undefined>;
  realtimeTrades: VietnamRealtimeTrade[];
  watchlist: string[];
  realtimeError?: string | null;
  tradesError?: string | null;
  lastRealtimeSnapshotRefreshAt?: string | null;
  lastTradeTapeRefreshAt?: string | null;
  lastRealtimeErrorAt?: string | null;
  realtimeAutoRefreshEnabled: boolean;
  tradeTapeAutoRefreshEnabled: boolean;
  realtimeSnapshotRefreshInterval: number;
  tradeTapeRefreshInterval: number;
  marketPhase: VietnamMarketPhase;
  observability?: VietnamObservabilityResponse | null;
}> = ({
  data,
  selectedItem,
  dailyIndex,
  indexList,
  indexComponents,
  indexCoverageError,
  realtimeQuotes,
  realtimeTrades,
  watchlist,
  realtimeError,
  tradesError,
  lastRealtimeSnapshotRefreshAt,
  lastTradeTapeRefreshAt,
  lastRealtimeErrorAt,
  realtimeAutoRefreshEnabled,
  tradeTapeAutoRefreshEnabled,
  realtimeSnapshotRefreshInterval,
  tradeTapeRefreshInterval,
  marketPhase,
  observability,
}) => {
  const status = realtimeProviderStatus(realtimeQuotes, watchlist, realtimeError, tradesError);
  const selectedQuote = selectedItem?.ticker ? realtimeQuotes[selectedItem.ticker] : undefined;
  const selectedRealtimeState = realtimeSnapshotState(selectedQuote, marketPhase.code);
  const latestTrade = realtimeTrades[0];
  const selectedLastFetched = selectedItem ? latestFetchedValue(selectedItem) : null;
  const selectedCacheStatus = selectedItem?.cacheStatus
    ? [
        `OHLCV ${cacheLabel(selectedItem.cacheStatus.ohlcvCache)}`,
        `Intraday ${cacheLabel(selectedItem.cacheStatus.intradayCache)}`,
        `news ${cacheLabel(selectedItem.cacheStatus.newsCache)}`,
      ].join(' | ')
    : '-';
  const hasDataQualityIssues = Boolean(
    Object.keys(data?.dataQuality.missingFields ?? {}).length || Object.keys(data?.dataQuality.errors ?? {}).length,
  );
  const dataStatusLabel = !data
    ? 'Unavailable'
    : realtimeError || tradesError || hasDataQualityIssues || status.label !== 'ok'
      ? 'Partial'
      : 'OK';
  const dataStatusVariant = dataStatusLabel === 'OK' ? 'success' : dataStatusLabel === 'Partial' ? 'warning' : 'danger';
  const metadata = data?.cacheMetadata;
  const issueSummary = realtimeIssueSummary(realtimeError, tradesError);
  const liveStatusDiagnostics = [
    ...liveStatusDiagnosticRows('SSI intraday status', selectedItem?.intradayStatus?.diagnostics),
    ...liveStatusDiagnosticRows('SSI realtime status', selectedItem?.realtimeStatus?.diagnostics),
    ...liveStatusDiagnosticRows('SSI trade tape status', selectedItem?.tradeTapeStatus?.diagnostics),
  ];
  const diagnosticsAvailable = Boolean(
    liveStatusDiagnostics.length
    || data
    || metadata
    || realtimeError
    || tradesError
    || observability
    || indexCoverageError,
  );

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <DatabaseZap className="h-5 w-5 text-cyan" />
            <h2 className="text-base font-semibold text-foreground">Data status</h2>
            <Badge variant={dataStatusVariant}>Data status: {dataStatusLabel}</Badge>
            {diagnosticsAvailable ? <Badge variant="default">Diagnostics available</Badge> : null}
          </div>
          <p className="mt-1 text-xs text-secondary-text">
            {marketPhase.phase} | core daily SSI data {data ? 'available' : 'pending'} | selected {selectedItem?.ticker ?? '-'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={data?.fixtureMode ? 'warning' : data ? 'success' : 'default'}>
            {data?.dataQuality.source ?? 'SSI pending'}
          </Badge>
          <Badge variant={realtimeSnapshotStateVariant(selectedRealtimeState)}>{selectedRealtimeState.label}</Badge>
          <Badge variant="default">{marketPhase.holidayAware ? 'Holiday calendar enabled' : 'holidayAware=false'}</Badge>
        </div>
      </div>
      {data?.fixtureMode ? (
        <div className="mt-3 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
          Fixture mode is active; rows are sample data.
        </div>
      ) : null}
      {marketPhase.isAuction ? (
        <div className="mt-3 rounded-lg border border-info/20 bg-info/10 p-2 text-xs text-info">
          Trade tape may differ during auction phases.
        </div>
      ) : null}
      {issueSummary ? (
        <div className="mt-3 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
          {issueSummary}
          <span className="ml-1 text-secondary-text">Optional realtime/index-component sections may be unavailable.</span>
        </div>
      ) : null}
      <IndexCoveragePanel
        dailyIndex={dailyIndex}
        indexList={indexList}
        indexComponents={indexComponents}
        error={indexCoverageError}
      />
      <details className="mt-3 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
        <summary className="cursor-pointer font-medium text-foreground">Show diagnostics</summary>
        <dl className="mt-4 grid gap-3 text-sm md:grid-cols-3 xl:grid-cols-7">
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">VN market phase</dt>
            <dd className="mt-1 font-medium text-foreground">{marketPhase.phase}</dd>
            <dd className="mt-1 text-xs text-secondary-text">
              {marketPhase.holidayAware ? 'Holiday calendar enabled' : 'holidayAware=false'}
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Market-data mode</dt>
            <dd className="mt-1 font-medium text-foreground">{data ? `SSI strict | fixture_mode ${String(data.fixtureMode)}` : '-'}</dd>
            <dd className="mt-1 text-xs text-secondary-text">{data?.dataQuality.source ?? '-'}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Overview refresh</dt>
            <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(data?.dataQuality.lastRefreshTime)}</dd>
            <dd className="mt-1 text-xs text-secondary-text">{formatRelativeAge(data?.dataQuality.lastRefreshTime)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Selected detail</dt>
            <dd className="mt-1 font-medium text-foreground">{selectedItem?.ticker ?? '-'}</dd>
            <dd className="mt-1 text-xs text-secondary-text">{formatVietnamTime(selectedLastFetched)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">SSI realtime</dt>
            <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(lastRealtimeSnapshotRefreshAt)}</dd>
            <dd className="mt-1 text-xs text-secondary-text">
              raw stale {status.staleCount} | unavailable {status.unavailableCount}
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">SSI trade tape</dt>
            <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(lastTradeTapeRefreshAt)}</dd>
            <dd className="mt-1 text-xs text-secondary-text">latest {latestTrade?.time ?? '-'}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Realtime auto-refresh</dt>
            <dd className="mt-1 font-medium text-foreground">{realtimeAutoRefreshEnabled ? 'on' : 'off'}</dd>
            <dd className="mt-1 text-xs text-secondary-text">snapshot {realtimeSnapshotRefreshInterval}s | trade tape {tradeTapeAutoRefreshEnabled ? `${tradeTapeRefreshInterval}s` : 'off'}</dd>
            <dd className="mt-1 text-xs text-secondary-text">{lastRealtimeErrorAt ? `last error ${formatVietnamTime(lastRealtimeErrorAt)}` : 'last error -'}</dd>
          </div>
        </dl>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <div className="rounded-lg border border-border/60 bg-card/50 p-3">
            <span className="font-medium text-foreground">Selected symbol</span> {selectedItem?.ticker ?? '-'} | daily close date {selectedItem?.latestPriceDate ?? selectedItem?.priceDate ?? '-'}
          </div>
          <div className="rounded-lg border border-border/60 bg-card/50 p-3">
            <span className="font-medium text-foreground">SSI realtime time</span> {realtimeSnapshotTimeText(selectedQuote)}
            <div className="mt-1">
              <Badge variant={realtimeSnapshotStateVariant(selectedRealtimeState)}>{selectedRealtimeState.label}</Badge>
            </div>
            <div className="mt-1">{selectedRealtimeState.reason}</div>
            <div className="mt-1">{realtimeSnapshotFreshnessText(selectedQuote)}</div>
            <div className="mt-1">{rawRealtimeFreshnessText(selectedQuote)}</div>
          </div>
          <div className="rounded-lg border border-border/60 bg-card/50 p-3">
            <span className="font-medium text-foreground">Cache status</span> {selectedCacheStatus}
          </div>
        </div>
        <div className="mt-3 grid gap-2 rounded-lg border border-border/60 bg-card/50 p-3 md:grid-cols-2">
          <div>
            <span className="font-medium text-foreground">SSI realtime diagnostic</span> {realtimeError ?? '-'}
          </div>
          <div>
            <span className="font-medium text-foreground">SSI trade tape diagnostic</span> {tradesError ?? '-'}
          </div>
        </div>
        {liveStatusDiagnostics.length ? (
          <div className="mt-3 rounded-lg border border-border/60 bg-card/50 p-3">
            <p className="font-medium text-foreground">Live status diagnostics</p>
            <dl className="mt-2 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {liveStatusDiagnostics.map((row) => (
                <div key={`${row.section}-${row.label}`}>
                  <dt>{row.section} - {row.label}</dt>
                  <dd className="mt-1 break-words font-medium text-foreground">{row.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}
        <div className="mt-3 grid gap-2 rounded-lg border border-border/60 bg-card/50 p-3 md:grid-cols-4 xl:grid-cols-8">
          <div>
            <span className="font-medium text-foreground">VN data req</span> {observability?.dashboardRuntime?.watchlistRequestsTotal ?? '-'}
          </div>
          <div>
            <span className="font-medium text-foreground">Cache hit/miss</span> {observability?.dashboardRuntime ? `${observability.dashboardRuntime.watchlistCacheHitsTotal}/${observability.dashboardRuntime.watchlistCacheMissesTotal}` : '-'}
          </div>
          <div>
            <span className="font-medium text-foreground">Single-flight waits</span> {observability?.dashboardRuntime?.singleflightWaitsTotal ?? '-'}
          </div>
          <div>
            <span className="font-medium text-foreground">SSI core status</span> {observability?.ssiCore?.status ?? '-'}
          </div>
          <div>
            <span className="font-medium text-foreground">SSI intraday status</span> {observability?.ssiIntraday?.status ?? '-'}
          </div>
          <div>
            <span className="font-medium text-foreground">SSI realtime status</span> {observability?.ssiRealtime?.status ?? '-'}
          </div>
          <div>
            <span className="font-medium text-foreground">SSI trade tape status</span> {observability?.ssiTradeTape?.status ?? '-'}
          </div>
          <div className="truncate">
            <span className="font-medium text-foreground">Legacy provider</span> {observability?.kbs.status ?? 'disabled'}
          </div>
        </div>
        {data ? (
          <div className="mt-3 grid gap-3">
            <div className="rounded-lg border border-border/60 bg-card/50 p-3">
              <p className="font-medium text-foreground">Provider diagnostics</p>
              <dl className="mt-2 grid gap-2 md:grid-cols-5">
                <div>
                  <dt>Data source</dt>
                  <dd className="font-medium text-foreground">{data.dataQuality.source}</dd>
                </div>
                <div>
                  <dt>Trading date</dt>
                  <dd className="font-medium text-foreground">{data.dataQuality.lastTradingDate ?? '-'}</dd>
                </div>
                <div>
                  <dt>Rows loaded</dt>
                  <dd className="font-medium text-foreground">{formatNumber(data.watchlist.reduce((total, item) => total + (item.rowsLoaded ?? 0), 0))}</dd>
                </div>
                <div>
                  <dt>Fixture active</dt>
                  <dd className="font-medium text-foreground">{data.dataQuality.fixtureMode ? 'Yes' : 'No'}</dd>
                </div>
                <div>
                  <dt>Last refresh</dt>
                  <dd className="font-medium text-foreground">{formatVietnamTime(data.dataQuality.lastRefreshTime)}</dd>
                </div>
              </dl>
              <p className="mt-3">
                Units: latest price and OHLCV fields are VND, volume is shares, and foreign net is labeled shares when SSI DailyStockPrice provides quantity fields. SSI realtime is separate and does not replace daily close.
              </p>
            </div>
            {Object.keys(data.dataQuality.missingFields).length || Object.keys(data.dataQuality.errors).length ? (
              <div className="grid gap-2">
                {Object.entries(data.dataQuality.missingFields).map(([ticker, fields]) => (
                  <div key={`missing-${ticker}`} className="rounded-lg border border-warning/20 bg-warning/10 p-2 text-warning">
                    {ticker}: missing {fields.join(', ')}
                  </div>
                ))}
                {Object.entries(data.dataQuality.errors).map(([ticker, errors]) => (
                  <div key={`error-${ticker}`} className="rounded-lg border border-danger/20 bg-danger/10 p-2 text-danger">
                    {ticker}: {errors.join('; ')}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {metadata ? (
          <div className="mt-3 rounded-lg border border-border/60 bg-card/50 p-3">
            <p className="font-medium text-foreground">Cache diagnostics</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant="default">hits {formatNumber(metadata.cacheHitCount)}</Badge>
              <Badge variant="default">misses {formatNumber(metadata.cacheMissCount)}</Badge>
              <Badge variant={metadata.staleCacheUsedCount ? 'warning' : 'default'}>stale used {formatNumber(metadata.staleCacheUsedCount)}</Badge>
              <Badge variant="default">OHLCV TTL {formatNumber(metadata.cacheTtlSeconds.ohlcv)}s</Badge>
              <Badge variant="default">Quote TTL {formatNumber(metadata.cacheTtlSeconds.quote)}s</Badge>
              <Badge variant="default">Intraday TTL {formatNumber(metadata.cacheTtlSeconds.intradayOhlcv)}s</Badge>
              <Badge variant="default">News TTL {formatNumber(metadata.cacheTtlSeconds.news)}s</Badge>
            </div>
          </div>
        ) : null}
      </details>
    </section>
  );
};

const SelectedTickerMetric: React.FC<{
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  valueClassName?: string;
}> = ({ label, value, detail, valueClassName }) => (
  <div className="min-w-0 rounded-lg border border-border/50 bg-elevated/35 p-3">
    <dt className="text-xs text-secondary-text">{label}</dt>
    <dd className={cn('mt-1 truncate text-sm font-semibold text-foreground', valueClassName)}>{value}</dd>
    {detail ? <dd className="mt-1 truncate text-xs text-secondary-text">{detail}</dd> : null}
  </div>
);

const SelectedTickerHeader: React.FC<{
  item?: VietnamWatchItem | null;
  realtimeQuote?: VietnamRealtimeQuote | null;
  marketPhase: VietnamMarketPhase;
}> = ({ item, realtimeQuote, marketPhase }) => {
  if (!item) {
    return (
      <section className="rounded-lg border border-border/70 bg-card p-4 shadow-soft-card" data-testid="selected-ticker-empty-state">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="label-uppercase text-cyan">Selected ticker</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">No ticker selected</h2>
            <p className="mt-2 text-sm text-secondary-text">Selected ticker unavailable because no valid daily rows are loaded.</p>
          </div>
          <Badge variant={sectionStateVariant('Unavailable')}>Unavailable</Badge>
        </div>
      </section>
    );
  }
  const realtimeState = realtimeSnapshotState(realtimeQuote, marketPhase.code);
  const avgVolume20D = item.indicators.avgVolume20D ?? item.liquidity?.avgVolume20D;
  const hasRealtimeSnapshot = hasRealtimeSnapshotData(realtimeQuote);
  const metadataExchange = metadataValue(item, 'exchange');
  const metadataMarket = metadataValue(item, 'market');
  const dailySourceLabel = officialDailySourceLabel(item);
  const dataQualitySummary = item.dataQualitySummary;
  const foreignNetVolume = item.dailyStockPrice?.foreignNetVolume ?? item.ssiForeignNetVolume ?? null;
  const dailyVolumeRatio = item.volume != null && avgVolume20D ? item.volume / avgVolume20D : null;
  const rsiValue = rsi14Value(item);
  const maState = maStateBadge(item);
  const realtimeStatus = realtimeQuote?.status ?? item.realtimeStatus?.status;
  const liveState = liveStatusBadge(item, realtimeQuote ?? undefined, marketPhase);
  const showRealtimeStatus = !hasRealtimeSnapshot || realtimeStatus === 'unavailable' || realtimeStatus === 'disabled' || realtimeStatus === 'error' || realtimeState.severity === 'warning' || realtimeState.severity === 'error';
  const tradeTapeStatus = item.tradeTapeStatus?.status;
  const showTradeTapeStatus = tradeTapeStatus === 'unavailable' || tradeTapeStatus === 'disabled' || tradeTapeStatus === 'error';
  const dailySectionState: SectionState = hasOfficialDailyData(item)
    ? dataQualityStatus(item) === 'partial'
      ? 'Partial'
      : 'Ready'
    : 'Unavailable';

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4 shadow-soft-card">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
        <div className="min-w-0">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <p className="label-uppercase text-cyan">Selected ticker</p>
              <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="text-2xl font-semibold text-foreground">{item.ticker}</h2>
                {companyDisplayName(item) ? (
                  <p className="min-w-0 text-sm text-secondary-text">{companyDisplayName(item)}</p>
                ) : null}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={sectionStateVariant(dailySectionState)}>{dailySectionState}</Badge>
              {metadataExchange ? <Badge variant="default">{metadataExchange}</Badge> : null}
              {metadataMarket && metadataMarket !== metadataExchange ? <Badge variant="default">{metadataMarket}</Badge> : null}
              <Badge variant="info">{dailySourceLabel}</Badge>
              {showRealtimeStatus ? (
                <Badge variant={realtimeSnapshotStateVariant(realtimeState)}>{realtimeStatusBadgeText(realtimeStatus)}</Badge>
              ) : null}
              {showTradeTapeStatus ? (
                <Badge variant="warning">{tradeTapeStatusBadgeText(tradeTapeStatus)}</Badge>
              ) : null}
              {item.newsStatus?.status === 'disabled' ? <Badge variant="default">News disabled</Badge> : null}
            </div>
          </div>

          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <SelectedTickerMetric
              label="Daily close"
              value={formatPrice(item.latestPrice ?? item.close)}
              detail={item.latestPriceDate ?? item.priceDate ?? '-'}
            />
            <SelectedTickerMetric
              label="% change"
              value={`${formatSignedNumber(item.changePct, 2)}%`}
              detail="SSI DailyOhlc"
              valueClassName={signalTone(item.changePct)}
            />
            <SelectedTickerMetric
              label="Foreign net"
              value={hasDisplayValue(foreignNetVolume) ? formatNumber(foreignNetVolume) : '-'}
              detail="shares"
              valueClassName={signalTone(foreignNetVolume)}
            />
            <SelectedTickerMetric
              label="Volume / 20D"
              value={`${formatNumber(item.volume)} / ${formatNumber(avgVolume20D)}`}
              detail={dailyVolumeRatio == null ? 'Ratio unavailable' : formatRatio(dailyVolumeRatio)}
            />
            <SelectedTickerMetric
              label="RSI14 / MA state"
              value={rsiValue == null ? '-' : formatNumber(rsiValue, 2)}
              detail={maState.label}
            />
            <SelectedTickerMetric
              label="Live"
              value={liveState.label}
              detail={realtimeStatusBadgeText(realtimeStatus)}
            />
          </dl>
        </div>

        <DataQualitySummary
          compact
          summary={dataQualitySummary}
          className="w-full border-cyan/10 bg-elevated/20"
        />
      </div>
    </section>
  );
};

const WatchlistScanSummary: React.FC<{
  items: VietnamWatchItem[];
  realtimeQuotes: Record<string, VietnamRealtimeQuote | undefined>;
  marketPhase: VietnamMarketPhase;
}> = ({ items, realtimeQuotes, marketPhase }) => {
  const states = items.map((item) => watchlistScanState(item, realtimeQuotes[item.ticker], marketPhase.code));
  const counts = WATCHLIST_SCAN_ORDER.reduce<Record<WatchlistScanLabel, number>>((acc, label) => {
    acc[label] = states.filter((state) => state.label === label).length;
    return acc;
  }, {
    Strong: 0,
    Improving: 0,
    Neutral: 0,
    Weakening: 0,
    'Risk elevated': 0,
    'Data unavailable': 0,
  });

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" data-testid="watchlist-scan-summary">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-foreground">Watchlist scan</h2>
            <Badge variant={sectionStateVariant(items.length ? 'Ready' : 'Unavailable')}>{items.length ? 'Ready' : 'Unavailable'}</Badge>
          </div>
          <p className="mt-1 text-xs text-secondary-text">
            Neutral ticker-level states derived from existing labels, SSI DailyOhlc cache freshness, and SSI realtime state. Warning counts remain secondary context in the table.
          </p>
        </div>
        <Badge variant="default">Sector grouping unavailable</Badge>
      </div>
      <dl className="mt-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {WATCHLIST_SCAN_ORDER.map((label) => (
          <div key={label} className="rounded-lg border border-border/50 bg-elevated/40 p-3">
            <dt className={cn('text-xs font-medium', scanTone(label))}>{label}</dt>
            <dd className="mt-1 text-xl font-semibold text-foreground">{counts[label]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
};

type IndicatorSortKey = 'ticker' | 'dailyClose' | 'changePct' | 'rsi14' | 'volumeRatio' | 'foreignNetVolume' | 'dataQuality';
type IndicatorSortDirection = 'asc' | 'desc';
type IndicatorSortState = { key: IndicatorSortKey; direction: IndicatorSortDirection } | null;
type IndicatorDataQualityFilter = 'all' | 'ready' | 'partial' | 'unavailable';
type IndicatorLiveStatusFilter = 'all' | 'ready' | 'unavailable' | 'disabled';
type IndicatorForeignNetFilter = 'all' | 'positive' | 'negative' | 'zero-missing';
type IndicatorVolumeRatioFilter = 'all' | 'elevated' | 'normal' | 'missing';
type IndicatorRsiRangeFilter = 'all' | 'lt30' | '30-70' | 'gt70' | 'missing';

interface IndicatorFilters {
  tickerSearch: string;
  dataQuality: IndicatorDataQualityFilter;
  liveStatus: IndicatorLiveStatusFilter;
  foreignNet: IndicatorForeignNetFilter;
  volumeRatio: IndicatorVolumeRatioFilter;
  rsiRange: IndicatorRsiRangeFilter;
}

const INITIAL_INDICATOR_FILTERS: IndicatorFilters = {
  tickerSearch: '',
  dataQuality: 'all',
  liveStatus: 'all',
  foreignNet: 'all',
  volumeRatio: 'all',
  rsiRange: 'all',
};

const dailyCloseValue = (item: VietnamWatchItem) => (
  finiteNumber(item.dailyClose)
  ?? finiteNumber(item.ohlcvClose)
  ?? finiteNumber(item.latestPrice)
  ?? finiteNumber(item.close)
);

const rsi14Value = (item: VietnamWatchItem) => (
  finiteNumber(item.indicators.rsi14Wilder) ?? finiteNumber(item.indicators.rsi14)
);

const volumeRatioValue = (item: VietnamWatchItem) => {
  const explicitRatio = finiteNumber(item.indicators.volumeRatio);
  if (explicitRatio !== null) return explicitRatio;
  const volume = finiteNumber(item.volume);
  const average = finiteNumber(item.indicators.avgVolume20D) ?? finiteNumber(item.liquidity?.avgVolume20D);
  if (volume === null || average === null || average === 0) return null;
  return volume / average;
};

const foreignNetVolumeValue = (item: VietnamWatchItem) => (
  finiteNumber(item.dailyStockPrice?.foreignNetVolume) ?? finiteNumber(item.ssiForeignNetVolume)
);

const normalizeStatusToken = (status?: string | null) => (
  String(status ?? '').trim().toLowerCase().replaceAll('_', '-')
);

const statusMapsToReady = (status?: string | null) => (
  ['ok', 'ready', 'success', 'available', 'enabled'].includes(normalizeStatusToken(status))
);

const statusMapsToPartial = (status?: string | null) => (
  ['partial', 'degraded', 'warning', 'caution', 'stale', 'provisional', 'limited'].includes(normalizeStatusToken(status))
);

const statusMapsToDisabled = (status?: string | null) => (
  ['disabled', 'not-implemented'].includes(normalizeStatusToken(status))
);

const statusMapsToUnavailable = (status?: string | null) => (
  ['unavailable', 'missing', 'unknown', 'failed', 'error', 'empty', 'not-found'].includes(normalizeStatusToken(status))
);

const dataQualityStatus = (item: VietnamWatchItem): 'ready' | 'partial' | 'unavailable' => {
  if (!hasOfficialDailyData(item)) return 'unavailable';
  const explicitStatus = item.dataQualitySummary?.overallStatus ?? item.status;
  if (statusMapsToReady(explicitStatus)) return 'ready';
  if (statusMapsToPartial(explicitStatus)) return 'partial';
  if (statusMapsToDisabled(explicitStatus) || statusMapsToUnavailable(explicitStatus)) return 'unavailable';
  if (item.validation?.valid === false && (item.validation.errors?.length ?? 0) > 0) return 'partial';
  if (item.validation?.valid === true) return 'ready';
  return 'ready';
};

const dataQualityRank = (item: VietnamWatchItem) => {
  const status = dataQualityStatus(item);
  if (status === 'ready') return 0;
  if (status === 'partial') return 1;
  return 2;
};

const dataQualityBadge = (item: VietnamWatchItem) => {
  const status = dataQualityStatus(item);
  if (status === 'ready') return { label: 'OK', variant: 'success' as BadgeVariant };
  if (status === 'partial') return { label: 'Partial', variant: 'warning' as BadgeVariant };
  return { label: 'Unavailable', variant: 'danger' as BadgeVariant };
};

const maStateBadge = (item: VietnamWatchItem) => {
  const close = dailyCloseValue(item);
  const ma20 = finiteNumber(item.indicators.ma20);
  const ma50 = finiteNumber(item.indicators.ma50);
  if (close === null || ma20 === null) {
    return { label: 'Insufficient data', variant: 'default' as BadgeVariant };
  }
  if (ma50 !== null && ((close >= ma20 && close < ma50) || (close < ma20 && close >= ma50))) {
    return { label: 'Mixed', variant: 'info' as BadgeVariant };
  }
  if (close >= ma20) return { label: 'Above MA20', variant: 'success' as BadgeVariant };
  return { label: 'Below MA20', variant: 'warning' as BadgeVariant };
};

const liveStatusBadge = (item: VietnamWatchItem, quote: VietnamRealtimeQuote | undefined, marketPhase: VietnamMarketPhase) => {
  const status = quote?.status ?? item.realtimeStatus?.status ?? item.dataQualitySummary?.checks?.realtime;
  const state = realtimeSnapshotState(quote, marketPhase.code);
  if (status === 'disabled') return { label: 'Realtime disabled', variant: 'default' as BadgeVariant };
  if (hasRealtimeSnapshotData(quote) && state.severity !== 'warning' && state.severity !== 'error') {
    return { label: 'Realtime ok', variant: 'success' as BadgeVariant };
  }
  return { label: 'Realtime unavailable', variant: 'warning' as BadgeVariant };
};

const liveStatusFilterValue = (
  item: VietnamWatchItem,
  quote: VietnamRealtimeQuote | undefined,
  marketPhase: VietnamMarketPhase,
): IndicatorLiveStatusFilter => {
  const status = quote?.status ?? item.realtimeStatus?.status ?? item.dataQualitySummary?.checks?.realtime;
  const state = realtimeSnapshotState(quote, marketPhase.code);
  if (statusMapsToDisabled(status)) return 'disabled';
  if (statusMapsToReady(status) && hasRealtimeSnapshotData(quote) && state.severity !== 'warning' && state.severity !== 'error') return 'ready';
  return 'unavailable';
};

const volumeRatioFilterValue = (item: VietnamWatchItem): Exclude<IndicatorVolumeRatioFilter, 'all'> => {
  const ratio = volumeRatioValue(item);
  if (ratio === null) return 'missing';
  return ratio >= 1.5 ? 'elevated' : 'normal';
};

const rsiRangeFilterValue = (item: VietnamWatchItem): Exclude<IndicatorRsiRangeFilter, 'all'> => {
  const rsi = rsi14Value(item);
  if (rsi === null) return 'missing';
  if (rsi < 30) return 'lt30';
  if (rsi > 70) return 'gt70';
  return '30-70';
};

const matchesIndicatorFilters = (
  item: VietnamWatchItem,
  filters: IndicatorFilters,
  realtimeQuotes: Record<string, VietnamRealtimeQuote | undefined>,
  marketPhase: VietnamMarketPhase,
) => {
  const search = filters.tickerSearch.trim().toUpperCase();
  if (search && !item.ticker.toUpperCase().includes(search)) return false;

  if (filters.dataQuality !== 'all' && dataQualityStatus(item) !== filters.dataQuality) return false;
  if (filters.liveStatus !== 'all' && liveStatusFilterValue(item, realtimeQuotes[item.ticker], marketPhase) !== filters.liveStatus) return false;

  const foreignNetVolume = foreignNetVolumeValue(item);
  if (filters.foreignNet === 'positive' && !(foreignNetVolume !== null && foreignNetVolume > 0)) return false;
  if (filters.foreignNet === 'negative' && !(foreignNetVolume !== null && foreignNetVolume < 0)) return false;
  if (filters.foreignNet === 'zero-missing' && !(foreignNetVolume === null || foreignNetVolume === 0)) return false;

  if (filters.volumeRatio !== 'all' && volumeRatioFilterValue(item) !== filters.volumeRatio) return false;
  if (filters.rsiRange !== 'all' && rsiRangeFilterValue(item) !== filters.rsiRange) return false;

  return true;
};

const sortValueForItem = (item: VietnamWatchItem, key: IndicatorSortKey): string | number | null => {
  switch (key) {
    case 'ticker':
      return item.ticker;
    case 'dailyClose':
      return dailyCloseValue(item);
    case 'changePct':
      return finiteNumber(item.changePct);
    case 'rsi14':
      return rsi14Value(item);
    case 'volumeRatio':
      return volumeRatioValue(item);
    case 'foreignNetVolume':
      return foreignNetVolumeValue(item);
    case 'dataQuality':
      return dataQualityRank(item);
    default:
      return null;
  }
};

const compareIndicatorSortValues = (
  left: string | number | null,
  right: string | number | null,
  direction: IndicatorSortDirection,
) => {
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  const result = typeof left === 'string' && typeof right === 'string'
    ? left.localeCompare(right)
    : Number(left) - Number(right);
  return direction === 'asc' ? result : -result;
};

const nextIndicatorSortState = (
  current: IndicatorSortState,
  key: IndicatorSortKey,
): IndicatorSortState => (
  current?.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: 'asc' }
);

const IndicatorTable: React.FC<{
  items: VietnamWatchItem[];
  realtimeQuotes: Record<string, VietnamRealtimeQuote | undefined>;
  realtimeLoading?: boolean;
  realtimeError?: string | null;
  isUpdating?: boolean;
  hasRequestFailure?: boolean;
  selectedTicker?: string | null;
  marketPhase: VietnamMarketPhase;
  onSelect: (ticker: string) => void;
}> = ({ items, realtimeQuotes, realtimeLoading = false, realtimeError, isUpdating = false, hasRequestFailure = false, selectedTicker, marketPhase, onSelect }) => {
  const [sortState, setSortState] = useState<IndicatorSortState>(null);
  const [filters, setFilters] = useState<IndicatorFilters>(INITIAL_INDICATOR_FILTERS);
  const sectionState: SectionState = isUpdating
    ? 'Updating...'
    : hasRequestFailure && items.length
      ? 'Partial'
      : items.length
        ? 'Ready'
        : hasRequestFailure
          ? 'Failed'
          : 'Unavailable';
  const filteredItems = useMemo(
    () => items.filter((item) => matchesIndicatorFilters(item, filters, realtimeQuotes, marketPhase)),
    [filters, items, marketPhase, realtimeQuotes],
  );
  const sortedItems = useMemo(() => {
    if (!sortState) return filteredItems;
    return filteredItems
      .map((item, index) => ({ item, index }))
      .sort((left, right) => {
        const result = compareIndicatorSortValues(
          sortValueForItem(left.item, sortState.key),
          sortValueForItem(right.item, sortState.key),
          sortState.direction,
        );
        return result || left.index - right.index;
      })
      .map(({ item }) => item);
  }, [filteredItems, sortState]);
  const selectedTickerHiddenByFilters = Boolean(
    selectedTicker
    && items.some((item) => item.ticker === selectedTicker)
    && !filteredItems.some((item) => item.ticker === selectedTicker),
  );
  const setFilter = <K extends keyof IndicatorFilters>(key: K, value: IndicatorFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };
  const sortDirectionLabel = (key: IndicatorSortKey) => (
    sortState?.key === key ? (sortState.direction === 'asc' ? ' asc' : ' desc') : ''
  );
  const sortButton = (key: IndicatorSortKey, label: string, className = '') => (
    <button
      type="button"
      className={cn('inline-flex items-center gap-1 text-left font-medium uppercase tracking-normal text-secondary-text hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/25', className)}
      onClick={() => setSortState((current) => nextIndicatorSortState(current, key))}
      aria-label={`Sort by ${label}${sortDirectionLabel(key)}`}
    >
      {label}
      {sortState?.key === key ? <span aria-hidden="true">{sortState.direction === 'asc' ? '↑' : '↓'}</span> : null}
    </button>
  );

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-foreground">Indicator table</h2>
            <Badge variant={sectionStateVariant(sectionState)}>{sectionState}</Badge>
          </div>
          {isUpdating ? (
            <p className="mt-1 text-xs text-secondary-text">Showing previous data while the watchlist updates.</p>
          ) : null}
          {items.length ? (
            <p className="mt-1 text-xs text-secondary-text">Showing {filteredItems.length} of {items.length} rows</p>
          ) : null}
        </div>
        <span className="text-xs text-secondary-text">
          Daily scan surface{realtimeLoading ? ' | loading SSI realtime' : ''}
        </span>
      </div>
      {items.length ? (
        <div className="mb-3 rounded-lg border border-border/60 bg-elevated/30 p-3" data-testid="indicator-filter-controls">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-7">
            <label className="flex flex-col gap-1 text-xs font-medium text-secondary-text">
              Search ticker
              <input
                value={filters.tickerSearch}
                onChange={(event) => setFilter('tickerSearch', event.target.value)}
                className="h-9 rounded-lg border border-border/70 bg-card px-3 text-sm font-normal uppercase text-foreground outline-none transition-colors placeholder:text-muted focus:border-cyan/50 focus:ring-2 focus:ring-cyan/15"
                placeholder="FPT"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-secondary-text">
              Data quality
              <select
                value={filters.dataQuality}
                onChange={(event) => setFilter('dataQuality', event.target.value as IndicatorDataQualityFilter)}
                className="h-9 rounded-lg border border-border/70 bg-card px-3 text-sm font-normal text-foreground outline-none transition-colors focus:border-cyan/50 focus:ring-2 focus:ring-cyan/15"
              >
                <option value="all">All</option>
                <option value="ready">Ready</option>
                <option value="partial">Partial</option>
                <option value="unavailable">Unavailable</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-secondary-text">
              Live status
              <select
                value={filters.liveStatus}
                onChange={(event) => setFilter('liveStatus', event.target.value as IndicatorLiveStatusFilter)}
                className="h-9 rounded-lg border border-border/70 bg-card px-3 text-sm font-normal text-foreground outline-none transition-colors focus:border-cyan/50 focus:ring-2 focus:ring-cyan/15"
              >
                <option value="all">All</option>
                <option value="ready">Ready</option>
                <option value="unavailable">Unavailable</option>
                <option value="disabled">Disabled</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-secondary-text">
              Foreign net
              <select
                value={filters.foreignNet}
                onChange={(event) => setFilter('foreignNet', event.target.value as IndicatorForeignNetFilter)}
                className="h-9 rounded-lg border border-border/70 bg-card px-3 text-sm font-normal text-foreground outline-none transition-colors focus:border-cyan/50 focus:ring-2 focus:ring-cyan/15"
              >
                <option value="all">All</option>
                <option value="positive">Foreign net positive</option>
                <option value="negative">Foreign net negative</option>
                <option value="zero-missing">Zero / missing</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-secondary-text">
              Volume / 20D
              <select
                value={filters.volumeRatio}
                onChange={(event) => setFilter('volumeRatio', event.target.value as IndicatorVolumeRatioFilter)}
                className="h-9 rounded-lg border border-border/70 bg-card px-3 text-sm font-normal text-foreground outline-none transition-colors focus:border-cyan/50 focus:ring-2 focus:ring-cyan/15"
              >
                <option value="all">All</option>
                <option value="elevated">Elevated</option>
                <option value="normal">Normal</option>
                <option value="missing">Missing</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-secondary-text">
              RSI14
              <select
                value={filters.rsiRange}
                onChange={(event) => setFilter('rsiRange', event.target.value as IndicatorRsiRangeFilter)}
                className="h-9 rounded-lg border border-border/70 bg-card px-3 text-sm font-normal text-foreground outline-none transition-colors focus:border-cyan/50 focus:ring-2 focus:ring-cyan/15"
              >
                <option value="all">All</option>
                <option value="lt30">&lt; 30</option>
                <option value="30-70">30 - 70</option>
                <option value="gt70">&gt; 70</option>
                <option value="missing">Missing</option>
              </select>
            </label>
            <div className="flex items-end">
              <Button type="button" variant="outline" size="sm" onClick={() => setFilters(INITIAL_INDICATOR_FILTERS)}>
                Reset filters
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      {realtimeError ? (
        <div className="mb-3 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
          SSI realtime unavailable. Daily SSI data is still available.
        </div>
      ) : null}
      {selectedTickerHiddenByFilters ? (
        <div className="mb-3 rounded-lg border border-cyan/20 bg-cyan/10 p-2 text-xs text-secondary-text">
          Selected ticker is hidden by filters.
        </div>
      ) : null}
      {!items.length ? (
        <div className="rounded-lg border border-danger/25 bg-danger/10 p-4 text-sm text-danger" data-testid="indicator-daily-unavailable-state">
          <p className="font-medium">Daily data unavailable</p>
          <p className="mt-1 text-xs text-secondary-text">No daily SSI rows are available for the active watchlist.</p>
        </div>
      ) : null}
      {items.length && !filteredItems.length ? (
        <div className="rounded-lg border border-border/60 bg-elevated/30 p-4 text-sm text-secondary-text" data-testid="indicator-empty-filter-state">
          <p className="font-medium text-foreground">No rows match current filters.</p>
          <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => setFilters(INITIAL_INDICATOR_FILTERS)}>
            Reset filters
          </Button>
        </div>
      ) : null}
      {filteredItems.length ? (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1040px] text-left text-sm">
          <thead className="border-b border-border/70 text-xs uppercase text-secondary-text">
            <tr>
              <th className="py-2 pr-3">{sortButton('ticker', 'Ticker')}</th>
              <th className="px-3 py-2 text-right">{sortButton('dailyClose', 'Daily close', 'ml-auto')}</th>
              <th className="px-3 py-2 text-right">{sortButton('changePct', '% change', 'ml-auto')}</th>
              <th className="px-3 py-2 text-right">{sortButton('rsi14', 'RSI14', 'ml-auto')}</th>
              <th className="px-3 py-2">MA state</th>
              <th className="px-3 py-2 text-right">{sortButton('volumeRatio', 'Volume / 20D avg', 'ml-auto')}</th>
              <th className="px-3 py-2 text-right">{sortButton('foreignNetVolume', 'Foreign net volume', 'ml-auto')}</th>
              <th className="px-3 py-2">{sortButton('dataQuality', 'Data quality')}</th>
              <th className="px-3 py-2">Realtime / live status</th>
            </tr>
          </thead>
          <tbody>
            {sortedItems.map((item) => {
              const quote = realtimeQuotes[item.ticker];
              const close = dailyCloseValue(item);
              const volumeRatio = volumeRatioValue(item);
              const foreignNetVolume = foreignNetVolumeValue(item);
              const dataQuality = dataQualityBadge(item);
              const maState = maStateBadge(item);
              const liveStatus = liveStatusBadge(item, quote, marketPhase);
              return (
                <tr
                  key={item.ticker}
                  data-testid={`indicator-row-${item.ticker}`}
                  className={cn(
                    'cursor-pointer border-b border-border/40 text-secondary-text hover:bg-elevated/40',
                    selectedTicker === item.ticker && 'bg-elevated/60 text-foreground',
                  )}
                  onClick={() => onSelect(item.ticker)}
                >
                  <td className="py-3 pr-3 font-semibold text-foreground">
                    <a
                      href={`/vietnam/company/${item.ticker}`}
                      className="text-foreground hover:text-cyan"
                      aria-label={`Open ${item.ticker} company research`}
                      onClick={(event) => event.stopPropagation()}
                    >
                      {item.ticker}
                    </a>
                    {companyDisplayName(item) ? (
                      <div className="mt-1 text-xs font-normal text-secondary-text">{companyDisplayName(item)}</div>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <div className="font-medium text-foreground">{formatPrice(close)}</div>
                    <div className="mt-1 text-xs text-secondary-text">SSI DailyOhlc</div>
                  </td>
                  <td className={cn('px-3 py-3 text-right font-medium', signalTone(item.changePct))}>
                    {hasDisplayValue(item.changePct) ? `${formatSignedNumber(item.changePct, 2)}%` : '-'}
                  </td>
                  <td className="px-3 py-3 text-right">{formatNumber(rsi14Value(item), 2)}</td>
                  <td className="px-3 py-3">
                    <Badge variant={maState.variant}>{maState.label}</Badge>
                  </td>
                  <td className="px-3 py-3 text-right">
                    {volumeRatio === null ? '-' : `${formatNumber(volumeRatio, 2)}x`}
                  </td>
                  <td className={cn('px-3 py-3 text-right font-medium', signalTone(foreignNetVolume))}>
                    <div>{hasDisplayValue(foreignNetVolume) ? formatSignedNumber(foreignNetVolume, 0) : '-'}</div>
                    <div className="mt-1 text-xs font-normal text-secondary-text">SSI DailyStockPrice</div>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={dataQuality.variant}>{dataQuality.label}</Badge>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={liveStatus.variant}>{liveStatus.label}</Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      ) : null}
    </section>
  );
};

const CHART_WIDTH = 960;
const PRICE_TOP = 24;
const PRICE_HEIGHT = 300;
const VOLUME_TOP = 352;
const VOLUME_HEIGHT = 110;
const RSI_TOP = 498;
const RSI_HEIGHT = 108;
const AXIS_TOP = RSI_TOP + RSI_HEIGHT + 16;
const AXIS_LABEL_Y = AXIS_TOP + 20;
const CHART_HEIGHT = 652;
const CHART_LEFT = 58;
const CHART_RIGHT = 20;
const PLOT_WIDTH = CHART_WIDTH - CHART_LEFT - CHART_RIGHT;
const MIN_VISIBLE_CANDLES = 20;

type ChartVisibleWindow = {
  start: number;
  end: number;
};

const chartX = (index: number, count: number) => (
  CHART_LEFT + (count <= 1 ? PLOT_WIDTH / 2 : (index / (count - 1)) * PLOT_WIDTH)
);

const minimumVisibleCandles = (total: number) => Math.min(MIN_VISIBLE_CANDLES, Math.max(total, 0));

const clampChartWindow = (window: ChartVisibleWindow, total: number): ChartVisibleWindow => {
  if (total <= 0) return { start: 0, end: 0 };
  const minimumSize = minimumVisibleCandles(total);
  const requestedSize = window.end - window.start;
  const size = Math.min(total, Math.max(minimumSize, requestedSize || total));
  const start = Math.max(0, Math.min(total - size, window.start));
  return { start, end: start + size };
};

const fullChartWindow = (total: number): ChartVisibleWindow => ({ start: 0, end: Math.max(0, total) });

const chartWindowAroundCenter = (window: ChartVisibleWindow, total: number, size: number): ChartVisibleWindow => {
  if (total <= 0) return fullChartWindow(total);
  const currentSize = Math.max(1, window.end - window.start);
  const center = window.start + (currentSize - 1) / 2;
  const start = Math.round(center - (size - 1) / 2);
  return clampChartWindow({ start, end: start + size }, total);
};

const zoomChartWindow = (window: ChartVisibleWindow, total: number, direction: 'in' | 'out'): ChartVisibleWindow => {
  const currentSize = window.end - window.start;
  if (total <= 0 || currentSize <= 0) return fullChartWindow(total);
  const minimumSize = minimumVisibleCandles(total);
  const targetSize = direction === 'in'
    ? Math.max(minimumSize, Math.round(currentSize * 0.68))
    : Math.min(total, Math.round(currentSize / 0.68));
  return chartWindowAroundCenter(window, total, targetSize);
};

const panChartWindow = (window: ChartVisibleWindow, total: number, direction: 'left' | 'right'): ChartVisibleWindow => {
  const size = window.end - window.start;
  if (total <= 0 || size <= 0) return fullChartWindow(total);
  const step = Math.max(1, Math.round(size * 0.2));
  const nextStart = direction === 'left' ? window.start - step : window.start + step;
  return clampChartWindow({ start: nextStart, end: nextStart + size }, total);
};

const numericChartValues = (points: VietnamChartPoint[], keys: Array<keyof VietnamChartPoint>) =>
  points.flatMap((point) => keys.map((key) => point[key])).filter((value): value is number => typeof value === 'number' && Number.isFinite(value));

const parseChartDate = (value?: string | null) => {
  if (!value) return null;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const formatChartAxisLabel = (value: string, spanDays: number) => {
  const parsed = parseChartDate(value);
  if (!parsed) return value;
  if (spanDays <= 45) {
    return new Intl.DateTimeFormat('en-US', { month: '2-digit', day: '2-digit' }).format(parsed);
  }
  if (spanDays <= 120) {
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(parsed);
  }
  return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}`;
};

const chartDateTicks = (points: VietnamChartPoint[]) => {
  const datedPoints = points
    .map((point, index) => ({ index, date: point.date, parsed: parseChartDate(point.date) }))
    .filter((point): point is { index: number; date: string; parsed: Date } => Boolean(point.date && point.parsed));
  if (datedPoints.length < 2) return [];

  const firstDate = datedPoints[0].parsed;
  const lastDate = datedPoints[datedPoints.length - 1].parsed;
  const spanDays = Math.max(1, Math.round((lastDate.getTime() - firstDate.getTime()) / 86_400_000));
  const desiredCount = datedPoints.length >= 80 ? 6 : datedPoints.length >= 40 ? 5 : Math.min(4, datedPoints.length);
  const seenIndexes = new Set<number>();
  const seenLabels = new Set<string>();

  return Array.from({ length: desiredCount }, (_, tickIndex) => {
    const sourceIndex = Math.round((tickIndex * (datedPoints.length - 1)) / Math.max(desiredCount - 1, 1));
    return datedPoints[sourceIndex];
  })
    .filter((point) => {
      if (seenIndexes.has(point.index)) return false;
      seenIndexes.add(point.index);
      return true;
    })
    .map((point) => ({ ...point, label: formatChartAxisLabel(point.date, spanDays) }))
    .filter((point) => {
      if (seenLabels.has(point.label)) return false;
      seenLabels.add(point.label);
      return true;
    });
};

const chartScale = (min: number, max: number, top: number, height: number) => {
  const padding = (max - min) * 0.08 || Math.max(Math.abs(max) * 0.08, 1);
  const low = min - padding;
  const high = max + padding;
  return (value?: number | null) => {
    if (value === null || value === undefined || !Number.isFinite(value)) return null;
    return top + ((high - value) / (high - low || 1)) * height;
  };
};

const chartPath = (
  points: VietnamChartPoint[],
  key: keyof VietnamChartPoint,
  yScale: (value?: number | null) => number | null,
) => {
  let started = false;
  return points.map((point, index) => {
    const y = yScale(point[key] as number | null | undefined);
    if (y === null) return null;
    const command = started ? 'L' : 'M';
    started = true;
    return `${command} ${chartX(index, points.length).toFixed(1)} ${y.toFixed(1)}`;
  })
    .filter(Boolean)
    .join(' ');
};

const BrokerInspectChartSvg: React.FC<{
  points: VietnamChartPoint[];
  showMA20: boolean;
  showMA50: boolean;
  showBollinger: boolean;
}> = ({ points, showMA20, showMA50, showBollinger }) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const priceKeys: Array<keyof VietnamChartPoint> = ['high', 'low', 'open', 'close'];
  if (showMA20) priceKeys.push('ma20');
  if (showMA50) priceKeys.push('ma50');
  if (showBollinger) priceKeys.push('bbUpper', 'bbMid', 'bbLower');
  const priceValues = numericChartValues(points, priceKeys);
  const volumeValues = numericChartValues(points, ['volume', 'volumeMa20', 'volumeMa50']);
  if (!priceValues.length) {
    return <p className="text-sm text-secondary-text">Chart data unavailable</p>;
  }
  const priceScale = chartScale(Math.min(...priceValues), Math.max(...priceValues), PRICE_TOP, PRICE_HEIGHT);
  const volumeScale = chartScale(0, Math.max(...volumeValues, 1), VOLUME_TOP, VOLUME_HEIGHT);
  const rsiScale = chartScale(0, 100, RSI_TOP, RSI_HEIGHT);
  const candleWidth = Math.max(3, Math.min(11, PLOT_WIDTH / Math.max(points.length, 1) * 0.62));
  const hoverPoint = hoverIndex === null ? null : points[hoverIndex] ?? null;
  const dateTicks = chartDateTicks(points);

  const handleMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width * CHART_WIDTH;
    const rawIndex = Math.round((x - CHART_LEFT) / (PLOT_WIDTH / Math.max(points.length - 1, 1)));
    setHoverIndex(Math.max(0, Math.min(points.length - 1, rawIndex)));
  };

  return (
    <div className="relative">
      <svg
        role="img"
        aria-label="Candlestick price chart with volume and RSI panels"
        data-testid="inspect-candlestick-chart"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        className="h-[540px] w-full rounded-lg border border-border/60 bg-[#07111d]"
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {[PRICE_TOP, PRICE_TOP + PRICE_HEIGHT, VOLUME_TOP, VOLUME_TOP + VOLUME_HEIGHT, RSI_TOP, RSI_TOP + RSI_HEIGHT].map((y) => (
          <line key={`grid-${y}`} x1={CHART_LEFT} x2={CHART_WIDTH - CHART_RIGHT} y1={y} y2={y} stroke="rgba(148,163,184,0.18)" />
        ))}
        <text x={14} y={PRICE_TOP + 18} fill="#94a3b8" fontSize="12">Price</text>
        <text x={14} y={VOLUME_TOP + 18} fill="#94a3b8" fontSize="12">Daily volume</text>
        <text x={14} y={RSI_TOP + 18} fill="#94a3b8" fontSize="12">RSI14</text>
        <line x1={CHART_LEFT} x2={CHART_WIDTH - CHART_RIGHT} y1={rsiScale(30) ?? 0} y2={rsiScale(30) ?? 0} stroke="#64748b" strokeDasharray="5 5" />
        <line x1={CHART_LEFT} x2={CHART_WIDTH - CHART_RIGHT} y1={rsiScale(70) ?? 0} y2={rsiScale(70) ?? 0} stroke="#64748b" strokeDasharray="5 5" />
        <text x={CHART_WIDTH - CHART_RIGHT - 24} y={(rsiScale(30) ?? 0) - 4} fill="#94a3b8" fontSize="11">30</text>
        <text x={CHART_WIDTH - CHART_RIGHT - 24} y={(rsiScale(70) ?? 0) - 4} fill="#94a3b8" fontSize="11">70</text>

        {points.map((point, index) => {
          const x = chartX(index, points.length);
          const openY = priceScale(point.open);
          const closeY = priceScale(point.close);
          const highY = priceScale(point.high);
          const lowY = priceScale(point.low);
          const volumeY = volumeScale(point.volume);
          const color = point.close != null && point.open != null && point.close >= point.open ? '#22c55e' : '#ef4444';
          const bodyTop = Math.min(openY ?? 0, closeY ?? 0);
          const bodyHeight = Math.max(1.5, Math.abs((openY ?? 0) - (closeY ?? 0)));
          return (
            <g key={`${point.date}-${index}`}>
              {highY !== null && lowY !== null ? <line x1={x} x2={x} y1={highY} y2={lowY} stroke={color} strokeWidth="1.3" /> : null}
              {openY !== null && closeY !== null ? (
                <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} fill={color} rx="1" />
              ) : null}
              {volumeY !== null ? (
                <rect x={x - candleWidth / 2} y={volumeY} width={candleWidth} height={VOLUME_TOP + VOLUME_HEIGHT - volumeY} fill={color} opacity="0.35" />
              ) : null}
            </g>
          );
        })}

        {showMA20 ? <path d={chartPath(points, 'ma20', priceScale)} fill="none" stroke="#a78bfa" strokeWidth="1.6" /> : null}
        {showMA50 ? <path d={chartPath(points, 'ma50', priceScale)} fill="none" stroke="#f59e0b" strokeWidth="1.6" /> : null}
        {showBollinger ? (
          <>
            <path d={chartPath(points, 'bbUpper', priceScale)} fill="none" stroke="#64748b" strokeWidth="1" />
            <path d={chartPath(points, 'bbMid', priceScale)} fill="none" stroke="#94a3b8" strokeWidth="1" strokeDasharray="5 5" />
            <path d={chartPath(points, 'bbLower', priceScale)} fill="none" stroke="#64748b" strokeWidth="1" />
          </>
        ) : null}
        <path d={chartPath(points, 'volumeMa20', volumeScale)} fill="none" stroke="#38bdf8" strokeWidth="1.4" />
        <path d={chartPath(points, 'volumeMa50', volumeScale)} fill="none" stroke="#f97316" strokeWidth="1.4" />
        <path d={chartPath(points, 'rsi14', rsiScale)} fill="none" stroke="#22c55e" strokeWidth="1.8" />

        {dateTicks.length ? (
          <g aria-label="Chart date axis">
            <line x1={CHART_LEFT} x2={CHART_WIDTH - CHART_RIGHT} y1={AXIS_TOP} y2={AXIS_TOP} stroke="rgba(148,163,184,0.22)" />
            {dateTicks.map((tick) => {
              const x = chartX(tick.index, points.length);
              return (
                <g key={`date-tick-${tick.index}`}>
                  <line x1={x} x2={x} y1={AXIS_TOP} y2={AXIS_TOP + 5} stroke="rgba(148,163,184,0.45)" />
                  <text
                    data-testid="inspect-chart-date-label"
                    x={x}
                    y={AXIS_LABEL_Y}
                    fill="#94a3b8"
                    fontSize="11"
                    textAnchor={tick.index === 0 ? 'start' : tick.index === points.length - 1 ? 'end' : 'middle'}
                  >
                    {tick.label}
                  </text>
                </g>
              );
            })}
          </g>
        ) : null}

        {hoverIndex !== null ? (
          <line x1={chartX(hoverIndex, points.length)} x2={chartX(hoverIndex, points.length)} y1={PRICE_TOP} y2={RSI_TOP + RSI_HEIGHT} stroke="rgba(226,232,240,0.45)" strokeDasharray="4 4" />
        ) : null}
      </svg>
      {hoverPoint ? (
        <div className="pointer-events-none absolute right-3 top-3 rounded-lg border border-border/70 bg-card/95 p-3 text-xs shadow-soft-card">
          <p className="font-semibold text-foreground">{hoverPoint.date ?? '-'}</p>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-secondary-text">
            <dt>Open</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.open)}</dd>
            <dt>High</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.high)}</dd>
            <dt>Low</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.low)}</dd>
            <dt>Close</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.close)}</dd>
            <dt>Daily volume</dt><dd className="text-right text-foreground">{formatNumber(hoverPoint.volume)}</dd>
            <dt>MA20</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.ma20)}</dd>
            <dt>MA50</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.ma50)}</dd>
            <dt>Daily volume MA20</dt><dd className="text-right text-foreground">{formatNumber(hoverPoint.volumeMa20)}</dd>
            <dt>Daily volume MA50</dt><dd className="text-right text-foreground">{formatNumber(hoverPoint.volumeMa50)}</dd>
            <dt>RSI14</dt><dd className="text-right text-foreground">{formatNumber(hoverPoint.rsi14, 2)}</dd>
            {showBollinger ? (
              <>
                <dt>Bollinger upper</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.bbUpper)}</dd>
                <dt>Bollinger mid</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.bbMid)}</dd>
                <dt>Bollinger lower</dt><dd className="text-right text-foreground">{formatPrice(hoverPoint.bbLower)}</dd>
              </>
            ) : null}
          </dl>
        </div>
      ) : null}
    </div>
  );
};

const ChartRangeControls: React.FC<{
  rangeLabel: InspectRangeLabel;
  onRangeChange: (range: InspectRangeLabel) => void;
}> = ({ rangeLabel, onRangeChange }) => (
  <div className="flex flex-wrap gap-1">
    {INSPECT_RANGES.map((range) => (
      <button
        key={range.label}
        type="button"
        onClick={() => onRangeChange(range.label)}
        className={cn(
          'h-8 rounded-md border px-3 text-xs font-medium transition-colors',
          rangeLabel === range.label
            ? 'border-cyan bg-cyan/10 text-cyan'
            : 'border-border/70 bg-card/60 text-secondary-text hover:bg-hover hover:text-foreground',
        )}
        aria-pressed={rangeLabel === range.label}
      >
        {range.label}
      </button>
    ))}
  </div>
);

const ChartOverlayControls: React.FC<{
  showMA20: boolean;
  showMA50: boolean;
  showBollinger: boolean;
  onShowMA20Change: (value: boolean) => void;
  onShowMA50Change: (value: boolean) => void;
  onShowBollingerChange: (value: boolean) => void;
}> = ({
  showMA20,
  showMA50,
  showBollinger,
  onShowMA20Change,
  onShowMA50Change,
  onShowBollingerChange,
}) => (
  <div className="flex flex-wrap gap-2">
    <label className="inline-flex h-8 items-center gap-2 rounded-md border border-border/70 bg-card/60 px-3 text-xs text-secondary-text">
      <input type="checkbox" checked={showMA20} onChange={(event) => onShowMA20Change(event.target.checked)} />
      MA20
    </label>
    <label className="inline-flex h-8 items-center gap-2 rounded-md border border-border/70 bg-card/60 px-3 text-xs text-secondary-text">
      <input type="checkbox" checked={showMA50} onChange={(event) => onShowMA50Change(event.target.checked)} />
      MA50
    </label>
    <label className="inline-flex h-8 items-center gap-2 rounded-md border border-border/70 bg-card/60 px-3 text-xs text-secondary-text">
      <input type="checkbox" checked={showBollinger} onChange={(event) => onShowBollingerChange(event.target.checked)} />
      Bollinger
    </label>
  </div>
);

const ChartWindowControls: React.FC<{
  pointsLength: number;
  visibleCount: number;
  canZoomIn: boolean;
  canZoomOut: boolean;
  canPanLeft: boolean;
  canPanRight: boolean;
  isZoomed: boolean;
  visibleCountTestId: string;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onPanLeft: () => void;
  onPanRight: () => void;
  onReset: () => void;
  onExpand?: () => void;
}> = ({
  pointsLength,
  visibleCount,
  canZoomIn,
  canZoomOut,
  canPanLeft,
  canPanRight,
  isZoomed,
  visibleCountTestId,
  onZoomIn,
  onZoomOut,
  onPanLeft,
  onPanRight,
  onReset,
  onExpand,
}) => (
  <div className="flex flex-wrap items-center gap-1">
    <button
      type="button"
      onClick={onZoomIn}
      disabled={!canZoomIn}
      aria-label="Zoom in chart"
      className={cn(
        'h-8 rounded-md border px-3 text-xs font-medium transition-colors',
        canZoomIn ? 'border-border/70 bg-card/60 text-secondary-text hover:bg-hover hover:text-foreground' : 'cursor-not-allowed border-border/40 bg-card/30 text-secondary-text/50',
      )}
    >
      +
    </button>
    <button
      type="button"
      onClick={onZoomOut}
      disabled={!canZoomOut}
      aria-label="Zoom out chart"
      className={cn(
        'h-8 rounded-md border px-3 text-xs font-medium transition-colors',
        canZoomOut ? 'border-border/70 bg-card/60 text-secondary-text hover:bg-hover hover:text-foreground' : 'cursor-not-allowed border-border/40 bg-card/30 text-secondary-text/50',
      )}
    >
      -
    </button>
    <button
      type="button"
      onClick={onPanLeft}
      disabled={!canPanLeft}
      aria-label="Pan left"
      className={cn(
        'h-8 rounded-md border px-3 text-xs font-medium transition-colors',
        canPanLeft ? 'border-border/70 bg-card/60 text-secondary-text hover:bg-hover hover:text-foreground' : 'cursor-not-allowed border-border/40 bg-card/30 text-secondary-text/50',
      )}
    >
      Left
    </button>
    <button
      type="button"
      onClick={onPanRight}
      disabled={!canPanRight}
      aria-label="Pan right"
      className={cn(
        'h-8 rounded-md border px-3 text-xs font-medium transition-colors',
        canPanRight ? 'border-border/70 bg-card/60 text-secondary-text hover:bg-hover hover:text-foreground' : 'cursor-not-allowed border-border/40 bg-card/30 text-secondary-text/50',
      )}
    >
      Right
    </button>
    <button
      type="button"
      onClick={onReset}
      disabled={!isZoomed}
      aria-label="Reset chart zoom"
      className={cn(
        'h-8 rounded-md border px-3 text-xs font-medium transition-colors',
        isZoomed ? 'border-border/70 bg-card/60 text-secondary-text hover:bg-hover hover:text-foreground' : 'cursor-not-allowed border-border/40 bg-card/30 text-secondary-text/50',
      )}
    >
      Reset
    </button>
    {onExpand ? (
      <button
        type="button"
        onClick={onExpand}
        aria-label="Expand chart"
        className="inline-flex h-8 items-center gap-2 rounded-md border border-border/70 bg-card/60 px-3 text-xs font-medium text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
      >
        <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
        Expand
      </button>
    ) : null}
    <span className="ml-2 text-xs text-secondary-text" data-testid={visibleCountTestId}>
      Showing {visibleCount} of {pointsLength}
    </span>
  </div>
);

const InspectChartCard: React.FC<{ item: VietnamWatchItem }> = ({ item }) => {
  const [rangeLabel, setRangeLabel] = useState<InspectRangeLabel>('6M');
  const [showMA20, setShowMA20] = useState(true);
  const [showMA50, setShowMA50] = useState(true);
  const [showBollinger, setShowBollinger] = useState(false);
  const [chart, setChart] = useState<VietnamChartResponse | null>(null);
  const [visibleWindow, setVisibleWindow] = useState<ChartVisibleWindow>(fullChartWindow(0));
  const [isExpanded, setIsExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const points = useMemo(() => (
    chart?.points?.length ? chart.points : chart?.candles ?? []
  ), [chart]);
  const clampedVisibleWindow = clampChartWindow(visibleWindow, points.length);
  const visiblePoints = useMemo(
    () => points.slice(clampedVisibleWindow.start, clampedVisibleWindow.end),
    [points, clampedVisibleWindow.start, clampedVisibleWindow.end],
  );
  const visibleCount = visiblePoints.length;
  const canZoomIn = points.length > minimumVisibleCandles(points.length) && visibleCount > minimumVisibleCandles(points.length);
  const canZoomOut = visibleCount < points.length;
  const canPanLeft = clampedVisibleWindow.start > 0;
  const canPanRight = clampedVisibleWindow.end < points.length;
  const isZoomed = visibleCount > 0 && visibleCount < points.length;
  const chartSourceLabel = chart?.status === 'unavailable'
    ? 'SSI unavailable'
    : chart?.source || 'SSI';
  const chartSectionState: SectionState = loading
    ? 'Loading'
    : points.length
      ? 'Ready'
      : error
        ? 'Failed'
        : 'Unavailable';

  const updateVisibleWindow = (updater: (window: ChartVisibleWindow) => ChartVisibleWindow) => {
    setVisibleWindow((current) => clampChartWindow(updater(clampChartWindow(current, points.length)), points.length));
  };

  useEffect(() => {
    if (!isExpanded) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsExpanded(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded]);

  useEffect(() => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const loadChart = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await stocksApi.getVietnamChart(item.ticker, rangeLabel);
        if (requestId !== requestIdRef.current) return;
        setChart(response);
        setVisibleWindow(fullChartWindow(response.points.length));
      } catch (err) {
        if (requestId !== requestIdRef.current) return;
        setChart(null);
        setVisibleWindow(fullChartWindow(0));
        setError(err instanceof Error ? err.message : 'Chart data unavailable');
      } finally {
        if (requestId === requestIdRef.current) setLoading(false);
      }
    };
    void loadChart();
  }, [item.ticker, rangeLabel]);

  return (
    <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4" data-testid="inspect-chart-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground">Inspect chart</h3>
            <Badge variant={sectionStateVariant(chartSectionState)}>{chartSectionState}</Badge>
          </div>
          <p className="mt-1 text-xs text-secondary-text">Daily OHLCV from {chartSourceLabel}. SSI realtime remains separate.</p>
        </div>
        <ChartRangeControls rangeLabel={rangeLabel} onRangeChange={setRangeLabel} />
      </div>

      <div className="mt-3">
        <ChartOverlayControls
          showMA20={showMA20}
          showMA50={showMA50}
          showBollinger={showBollinger}
          onShowMA20Change={setShowMA20}
          onShowMA50Change={setShowMA50}
          onShowBollingerChange={setShowBollinger}
        />
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-secondary-text">Loading chart data...</p>
      ) : points.length ? (
        <div className="mt-4 space-y-3">
          <ChartWindowControls
            pointsLength={points.length}
            visibleCount={visibleCount}
            canZoomIn={canZoomIn}
            canZoomOut={canZoomOut}
            canPanLeft={canPanLeft}
            canPanRight={canPanRight}
            isZoomed={isZoomed}
            visibleCountTestId="inspect-chart-visible-count"
            onZoomIn={() => updateVisibleWindow((window) => zoomChartWindow(window, points.length, 'in'))}
            onZoomOut={() => updateVisibleWindow((window) => zoomChartWindow(window, points.length, 'out'))}
            onPanLeft={() => updateVisibleWindow((window) => panChartWindow(window, points.length, 'left'))}
            onPanRight={() => updateVisibleWindow((window) => panChartWindow(window, points.length, 'right'))}
            onReset={() => setVisibleWindow(fullChartWindow(points.length))}
            onExpand={() => setIsExpanded(true)}
          />
          <div className="flex flex-wrap gap-2 text-xs text-secondary-text">
            <span data-testid="inspect-legend-candles">Candlesticks</span>
            {showMA20 ? <span data-testid="inspect-legend-ma20">MA20</span> : null}
            {showMA50 ? <span data-testid="inspect-legend-ma50">MA50</span> : null}
            {showBollinger ? <span data-testid="inspect-legend-bollinger">Bollinger upper/mid/lower</span> : null}
            <span>Daily volume MA20</span>
            <span>Daily volume MA50</span>
            <span>RSI14</span>
          </div>
          <BrokerInspectChartSvg points={visiblePoints} showMA20={showMA20} showMA50={showMA50} showBollinger={showBollinger} />
          <p className="text-xs text-secondary-text">RSI14 numeric guides: 30 and 70.</p>
        </div>
      ) : (
        <p className="mt-4 text-sm text-secondary-text">Chart data unavailable</p>
      )}
      {error ? <p className="mt-2 text-xs text-secondary-text">Chart endpoint unavailable: {error}</p> : null}

      <div className="mt-3 space-y-1 text-xs text-secondary-text">
        <p>Daily OHLCV source: {chartSourceLabel}</p>
        <p>SSI realtime is separate and not used as daily close.</p>
        {chart?.latestDate ? <p>Latest chart date: {chart.latestDate}</p> : null}
      </div>
      {isExpanded && points.length ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="inspect-chart-expanded-title"
          className="fixed inset-0 z-50 flex bg-background/95 p-3 backdrop-blur-sm md:p-6"
        >
          <div className="flex min-h-0 w-full flex-col rounded-lg border border-border/70 bg-elevated p-4 shadow-soft-card">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 id="inspect-chart-expanded-title" className="text-base font-semibold text-foreground">Expanded inspect chart</h3>
                <p className="mt-1 text-xs text-secondary-text">Daily OHLCV from {chartSourceLabel}. SSI realtime remains separate.</p>
              </div>
              <button
                type="button"
                onClick={() => setIsExpanded(false)}
                aria-label="Close expanded chart"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border/70 bg-card/60 text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <div className="mt-3">
              <ChartRangeControls rangeLabel={rangeLabel} onRangeChange={setRangeLabel} />
            </div>

            <div className="mt-3">
              <ChartOverlayControls
                showMA20={showMA20}
                showMA50={showMA50}
                showBollinger={showBollinger}
                onShowMA20Change={setShowMA20}
                onShowMA50Change={setShowMA50}
                onShowBollingerChange={setShowBollinger}
              />
            </div>

            <div className="mt-4">
              <ChartWindowControls
                pointsLength={points.length}
                visibleCount={visibleCount}
                canZoomIn={canZoomIn}
                canZoomOut={canZoomOut}
                canPanLeft={canPanLeft}
                canPanRight={canPanRight}
                isZoomed={isZoomed}
                visibleCountTestId="inspect-chart-expanded-visible-count"
                onZoomIn={() => updateVisibleWindow((window) => zoomChartWindow(window, points.length, 'in'))}
                onZoomOut={() => updateVisibleWindow((window) => zoomChartWindow(window, points.length, 'out'))}
                onPanLeft={() => updateVisibleWindow((window) => panChartWindow(window, points.length, 'left'))}
                onPanRight={() => updateVisibleWindow((window) => panChartWindow(window, points.length, 'right'))}
                onReset={() => setVisibleWindow(fullChartWindow(points.length))}
              />
            </div>

            <div className="mt-3 flex flex-wrap gap-2 text-xs text-secondary-text">
              <span>Candlesticks</span>
              {showMA20 ? <span>MA20</span> : null}
              {showMA50 ? <span>MA50</span> : null}
              {showBollinger ? <span>Bollinger upper/mid/lower</span> : null}
              <span>Daily volume MA20</span>
              <span>Daily volume MA50</span>
              <span>RSI14</span>
            </div>

            <div className="mt-3 min-h-0 flex-1 overflow-y-auto pr-1 [&_svg]:h-[min(68vh,760px)]">
              <BrokerInspectChartSvg points={visiblePoints} showMA20={showMA20} showMA50={showMA50} showBollinger={showBollinger} />
              <div className="mt-3 space-y-1 text-xs text-secondary-text">
                <p>RSI14 numeric guides: 30 and 70.</p>
                <p>Daily OHLCV source: {chartSourceLabel}</p>
                <p>SSI realtime is separate and not used as daily close.</p>
                {chart?.latestDate ? <p>Latest chart date: {chart.latestDate}</p> : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const CorporateActionEventRow: React.FC<{ event: VietnamCorporateActionEvent }> = ({ event }) => (
  <div className="rounded-lg border border-border/50 bg-card/50 p-3 text-sm">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={event.status === 'upcoming' ? 'info' : 'default'}>{event.status}</Badge>
        <span className="font-medium text-foreground">{event.eventType.replaceAll('_', ' ')}</span>
      </div>
      <span className="text-xs text-secondary-text">{event.exDate ?? event.recordDate ?? event.paymentDate ?? '-'}</span>
    </div>
    <dl className="mt-2 grid gap-2 text-xs text-secondary-text md:grid-cols-3">
      <div>
        <dt>Ex-date</dt>
        <dd className="font-medium text-foreground">{event.exDate ?? '-'}</dd>
      </div>
      <div>
        <dt>Record date</dt>
        <dd className="font-medium text-foreground">{event.recordDate ?? '-'}</dd>
      </div>
      <div>
        <dt>Payment date</dt>
        <dd className="font-medium text-foreground">{event.paymentDate ?? '-'}</dd>
      </div>
      {event.cashDividendPerShare != null ? (
        <div>
          <dt>Cash dividend</dt>
          <dd className="font-medium text-foreground">{formatNumber(event.cashDividendPerShare)} VND/share</dd>
        </div>
      ) : null}
      {event.stockDividendRatio ? (
        <div>
          <dt>Stock dividend ratio</dt>
          <dd className="font-medium text-foreground">{event.stockDividendRatio}</dd>
        </div>
      ) : null}
      {event.rightsRatio ? (
        <div>
          <dt>Rights ratio</dt>
          <dd className="font-medium text-foreground">{event.rightsRatio}</dd>
        </div>
      ) : null}
    </dl>
    {event.description ? <p className="mt-2 text-xs text-secondary-text">{event.description}</p> : null}
    {event.source || event.lastCheckedAt ? (
      <p className="mt-2 text-xs text-secondary-text">
        Source: {event.source ?? '-'} | last checked {formatVietnamTime(event.lastCheckedAt)}
      </p>
    ) : null}
    {event.sourceUrl ? (
      <a href={event.sourceUrl} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-cyan hover:underline">
        Source link
      </a>
    ) : null}
  </div>
);

const SelectedTickerDisclosure: React.FC<{
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}> = ({ title, defaultOpen = false, children }) => (
  <details
    open={defaultOpen}
    className="rounded-lg border border-border/60 bg-elevated/30 p-3 text-sm text-secondary-text"
    data-testid={`selected-disclosure-${title.toLowerCase().replaceAll(' ', '-')}`}
  >
    <summary className="cursor-pointer text-sm font-semibold text-foreground">{title}</summary>
    <div className="mt-3">{children}</div>
  </details>
);

const StockDetailView: React.FC<{
  item?: VietnamWatchItem | null;
  fixtureMode?: boolean;
  realtimeQuote?: VietnamRealtimeQuote | null;
  realtimeTrades?: VietnamRealtimeTrade[];
  corporateActions?: VietnamCorporateActionsResponse | null;
  corporateActionsLoading?: boolean;
  corporateActionsError?: string | null;
  tradesLoading?: boolean;
  tradesError?: string | null;
  marketPhase: VietnamMarketPhase;
}> = ({
  item,
  fixtureMode = false,
  realtimeQuote,
  realtimeTrades = [],
  corporateActions = null,
  corporateActionsLoading = false,
  corporateActionsError,
  tradesLoading = false,
  tradesError,
  marketPhase,
}) => {
  if (!item) {
    return (
      <section className="rounded-lg border border-border/70 bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="label-uppercase text-secondary-text">Stock detail</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Daily data unavailable</h2>
            <p className="mt-2 text-sm text-secondary-text">No selected ticker detail can be shown until daily watchlist rows load.</p>
          </div>
          <Badge variant={sectionStateVariant('Unavailable')}>Unavailable</Badge>
        </div>
      </section>
    );
  }
  const indicators = item.indicators;
  const latestIntradayCandle = item.intradayCandles?.at(-1);
  const conditionSummary = buildVietnamConditionSummary({ item, fixtureMode });
  const marketStatusDetails = (item.statusDetails ?? []).filter((detail) => !DATA_CAVEAT_LABELS.has(detail.label));
  const realtimeState = realtimeSnapshotState(realtimeQuote, marketPhase.code);
  const hasRealtimeSnapshot = hasRealtimeSnapshotData(realtimeQuote);
  const hasCurrentIntraday = hasCurrentIntradayData(item);
  const hasTradeTape = hasTradeTapeData(realtimeTrades);
  const intradayReasonCode = optionalLiveReasonCode(item.intradayStatus);
  const intradaySectionState: SectionState = hasCurrentIntraday
    ? intradayReasonCode === 'cadence_mismatch' || ['different_from_requested', 'irregular'].includes(intradayCadenceStatus(item) ?? '')
      ? 'Partial'
      : 'Ready'
    : item.intradayStatus?.status === 'disabled'
      ? 'Disabled'
      : 'Unavailable';
  const realtimeSectionState: SectionState = hasRealtimeSnapshot
    ? 'Ready'
    : realtimeQuote?.status === 'disabled' || item.realtimeStatus?.status === 'disabled'
      ? 'Disabled'
      : 'Unavailable';
  const tradeTapeSectionState: SectionState = tradesLoading
    ? 'Loading'
    : hasTradeTape
      ? 'Ready'
      : item.tradeTapeStatus?.status === 'disabled'
        ? 'Disabled'
        : 'Unavailable';
  const sessionCandlesCount = item.intradayPulse?.sessionCandlesCount ?? 0;
  const hasSessionCandles = sessionCandlesCount > 0;
  const hasSessionHighLowFromIntraday = intradaySessionHigh(item) != null && intradaySessionLow(item) != null;
  const hasSessionRangeFromIntraday = intradaySessionRange(item) != null;
  const hasSessionVolumeFromIntraday = intradaySessionVolume(item) != null;
  const missingSessionMetricText = hasSessionCandles ? 'Session value unavailable' : 'Not enough session candles';
  const missingSessionHighLowTitle = hasSessionCandles
    ? 'Session high/low is unavailable from current provider-returned intraday candles.'
    : 'Session high/low requires current-session intraday candles.';
  const missingSessionRangeTitle = hasSessionCandles
    ? 'Session range is unavailable from current provider-returned intraday candles.'
    : 'Session range requires current-session intraday candles.';
  const missingSessionVolumeTitle = hasSessionCandles
    ? 'Session volume is unavailable from current provider-returned intraday candles.'
    : 'Session volume requires current-session intraday candles.';
  const hasVolumeVsAverage = intradayVolumeVsAverage(item) != null;
  const avgVolume20D = indicators.avgVolume20D ?? item.liquidity?.avgVolume20D;
  const sessionVolumeRatioText = sessionVolumeToAvgDailyVolume(item, realtimeQuote, realtimeState);
  const finalCloseLabel = finalCloseDisplayLabel(item.finalCloseStatus);
  const foreignNet5dLatestAvailable = indicators.foreignNet5dLatestAvailable;
  const foreignNet20dLatestAvailable = indicators.foreignNet20dLatestAvailable;
  const foreignHistoryCount = indicators.foreignNetHistoryCount ?? 0;
  const detailNewsItems = item.news ?? [];
  const newsContextStatus = newsContextStatusLabel(item, detailNewsItems.length);
  const ssiDailyStockPrice = item.dailyStockPrice ?? {};
  const ssiReferencePrice = ssiDailyStockPrice.referencePrice ?? item.ssiReferencePrice ?? item.priceLimit?.referencePrice ?? null;
  const ssiCeilingPrice = ssiDailyStockPrice.ceilingPrice ?? item.ssiCeilingPrice ?? item.priceLimit?.ceilingPrice ?? null;
  const ssiFloorPrice = ssiDailyStockPrice.floorPrice ?? item.ssiFloorPrice ?? item.priceLimit?.floorPrice ?? null;
  const ssiDailyClose = item.latestPrice ?? item.close ?? null;
  const priceVsReference = ssiDailyClose != null && ssiReferencePrice != null ? ssiDailyClose - ssiReferencePrice : null;
  const priceVsReferencePct = priceVsReference != null && ssiReferencePrice ? priceVsReference / ssiReferencePrice * 100 : null;
  const ssiDailyHasCoreValues = [
    ssiReferencePrice,
    ssiCeilingPrice,
    ssiFloorPrice,
    ssiDailyStockPrice.adjustedClose,
    ssiDailyStockPrice.matchedVolume,
    ssiDailyStockPrice.matchedValue,
    ssiDailyStockPrice.putThroughVolume,
    ssiDailyStockPrice.putThroughValue,
    ssiDailyStockPrice.foreignBuyVolume,
    ssiDailyStockPrice.foreignSellVolume,
    ssiDailyStockPrice.foreignNetVolume,
    ssiDailyStockPrice.foreignBuyValue,
    ssiDailyStockPrice.foreignSellValue,
    ssiDailyStockPrice.foreignNetValue,
  ].some(hasDisplayValue);
  const ssiDailyStatus = ssiDailyStockPrice.status ?? item.priceLimit?.status ?? (
    ssiDailyHasCoreValues ? 'ok' : 'unavailable'
  );
  const hasSsiDailyStockPrice = ssiDailyStatus === 'ok' && ssiDailyHasCoreValues;
  const rawSsiDailySource = ssiDailyStockPrice.source ?? item.referenceSource ?? item.priceLimit?.source;
  const ssiDailySource = !rawSsiDailySource || rawSsiDailySource === 'SSI' ? 'SSI DailyStockPrice' : rawSsiDailySource;
  const ssiDailyQualityStatus = ssiDailyStockPrice.qualityStatus ?? ssiDailyStatus;
  const ssiDailyDateMatch = ssiDailyStockPrice.dateMatch ?? item.dailyStockPriceDateMatch ?? 'unknown';
  const hasForeignNetHistory = (
    hasDisplayValue(foreignNet5dLatestAvailable) ||
    hasDisplayValue(foreignNet20dLatestAvailable)
  );
  const ssiDailyRows = [
    { label: 'Reference price', value: `${formatPrice(ssiReferencePrice)} VND`, show: hasDisplayValue(ssiReferencePrice) },
    { label: 'Ceiling price / floor price', value: `${formatPrice(ssiCeilingPrice)} / ${formatPrice(ssiFloorPrice)} VND`, show: hasDisplayValue(ssiCeilingPrice) && hasDisplayValue(ssiFloorPrice) },
    { label: 'Ceiling price', value: `${formatPrice(ssiCeilingPrice)} VND`, show: hasDisplayValue(ssiCeilingPrice) && !hasDisplayValue(ssiFloorPrice) },
    { label: 'Floor price', value: `${formatPrice(ssiFloorPrice)} VND`, show: hasDisplayValue(ssiFloorPrice) && !hasDisplayValue(ssiCeilingPrice) },
    { label: 'Foreign buy', value: `${formatNumber(ssiDailyStockPrice.foreignBuyVolume)} shares`, show: hasDisplayValue(ssiDailyStockPrice.foreignBuyVolume) },
    { label: 'Foreign sell', value: `${formatNumber(ssiDailyStockPrice.foreignSellVolume)} shares`, show: hasDisplayValue(ssiDailyStockPrice.foreignSellVolume) },
    { label: 'Foreign net volume', value: `${formatNumber(ssiDailyStockPrice.foreignNetVolume ?? item.ssiForeignNetVolume ?? item.foreign?.net)} shares`, tone: signalTone(ssiDailyStockPrice.foreignNetVolume ?? item.ssiForeignNetVolume ?? item.foreign?.net), show: hasDisplayValue(ssiDailyStockPrice.foreignNetVolume ?? item.ssiForeignNetVolume ?? item.foreign?.net) },
    { label: 'Foreign net value', value: `${formatNumber(ssiDailyStockPrice.foreignNetValue ?? item.ssiForeignNetValue ?? item.foreign?.netValue)} VND`, tone: signalTone(ssiDailyStockPrice.foreignNetValue ?? item.ssiForeignNetValue ?? item.foreign?.netValue), show: hasDisplayValue(ssiDailyStockPrice.foreignNetValue ?? item.ssiForeignNetValue ?? item.foreign?.netValue) },
    { label: 'Matched volume', value: `${formatNumber(ssiDailyStockPrice.matchedVolume ?? item.ssiMatchedVolume)} shares`, show: hasDisplayValue(ssiDailyStockPrice.matchedVolume ?? item.ssiMatchedVolume) },
    { label: 'Matched value', value: `${formatNumber(ssiDailyStockPrice.matchedValue ?? item.ssiMatchedValue)} VND`, show: hasDisplayValue(ssiDailyStockPrice.matchedValue ?? item.ssiMatchedValue) },
    { label: 'Put-through volume', value: `${formatNumber(ssiDailyStockPrice.putThroughVolume ?? item.ssiPutThroughVolume)} shares`, show: hasDisplayValue(ssiDailyStockPrice.putThroughVolume ?? item.ssiPutThroughVolume) },
    { label: 'Put-through value', value: `${formatNumber(ssiDailyStockPrice.putThroughValue ?? item.ssiPutThroughValue)} VND`, show: hasDisplayValue(ssiDailyStockPrice.putThroughValue ?? item.ssiPutThroughValue) },
    { label: 'Adjusted close', value: `${formatPrice(ssiDailyStockPrice.adjustedClose ?? item.ssiAdjustedClose)} VND`, show: hasDisplayValue(ssiDailyStockPrice.adjustedClose ?? item.ssiAdjustedClose) },
  ].filter((row) => row.show);
  const symbolMetadata = item.symbolMetadata ?? {};
  const metadataExchangeMarket = [
    metadataValue(item, 'exchange'),
    metadataValue(item, 'market'),
  ].filter(hasDisplayValue).filter((value, index, values) => values.indexOf(value) === index).join(' / ');
  const metadataIndustry = metadataValue(item, 'industry');
  const metadataSector = metadataValue(item, 'sector');
  const metadataQualityStatus = symbolMetadata.qualityStatus ?? (
    symbolMetadata.status === 'ok' ? 'partial' : 'unavailable'
  );
  const symbolMetadataRows = [
    { label: 'Vietnamese name', value: symbolMetadata.name ?? item.companyName ?? item.name, show: hasDisplayValue(symbolMetadata.name ?? item.companyName ?? item.name) },
    { label: 'English name', value: symbolMetadata.nameEn, show: hasDisplayValue(symbolMetadata.nameEn) },
    { label: 'Exchange / market', value: metadataExchangeMarket, show: hasDisplayValue(metadataExchangeMarket) },
    { label: 'Industry', value: metadataIndustry, show: hasDisplayValue(metadataIndustry) },
    { label: 'Sector', value: metadataSector, show: hasDisplayValue(metadataSector) && metadataSector !== metadataIndustry },
    { label: 'Security type', value: metadataValue(item, 'securityType'), show: hasDisplayValue(metadataValue(item, 'securityType')) },
    { label: 'Issuer', value: metadataValue(item, 'issuer'), show: hasDisplayValue(metadataValue(item, 'issuer')) },
    { label: 'Lot size', value: formatNumber(metadataValue(item, 'lotSize') as number | null), show: hasDisplayValue(metadataValue(item, 'lotSize') as number | null) },
    { label: 'Listed shares', value: formatNumber(metadataValue(item, 'listedShares') as number | null), show: hasDisplayValue(metadataValue(item, 'listedShares') as number | null) },
    { label: 'Listed date', value: metadataValue(item, 'listedDate'), show: hasDisplayValue(metadataValue(item, 'listedDate')) },
  ].filter((row) => row.show);
  const corporateActionEvents = (corporateActions?.events ?? corporateActions?.items ?? []).filter((event) => event.ticker === item.ticker);
  const upcomingCorporateActions = corporateActionEvents.filter((event) => event.status === 'upcoming');
  const recentCorporateActions = corporateActionEvents.filter((event) => event.status === 'recent' || event.status === 'past');
  const displayCorporateActions = [...upcomingCorporateActions, ...recentCorporateActions];
  const corporateActionsUnavailable = (
    Boolean(corporateActionsError)
    || ['disabled', 'not_configured', 'not_implemented', 'unavailable', 'error'].includes(corporateActions?.status ?? '')
  );
  return (
    <section className="rounded-lg border border-border/70 bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="label-uppercase text-secondary-text">Stock detail</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">{item.ticker}</h2>
        </div>
        <div className="flex flex-wrap gap-1">
          <Badge variant={sectionStateVariant(hasOfficialDailyData(item) ? 'Ready' : 'Unavailable')}>
            {hasOfficialDailyData(item) ? 'Ready' : 'Unavailable'}
          </Badge>
          {marketStatusLabels(item, item.statusLabels?.length ?? 0).map((label) => (
            <Badge key={label} variant={statusVariant(label)}>{label}</Badge>
          ))}
        </div>
      </div>
      <div className="mt-3 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
        Labels are neutral condition tags only.
      </div>
      <div className="mt-4 grid gap-3">
      <SelectedTickerDisclosure title="Price context" defaultOpen>
        <p className="mb-3 text-xs text-secondary-text">
          Daily close: SSI DailyOhlc · Reference and limits: SSI DailyStockPrice · Prices: VND.
        </p>
        {ssiDailyDateMatch === 'mismatched' ? (
          <p className="mb-3 rounded-lg border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
            DailyStockPrice date differs from DailyOhlc.
          </p>
        ) : null}
        <dl className="grid gap-3 text-sm md:grid-cols-3 xl:grid-cols-4">
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Daily close</dt>
            <dd className="mt-1 font-medium text-foreground">{formatPrice(item.dailyClose ?? item.latestPrice ?? item.close)} / {formatPrice(item.ohlcvClose ?? item.close)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Price source</dt>
            <dd className="mt-1 flex flex-wrap gap-1">
              <Badge variant={priceSourceVariant(item.latestPriceSource)}>{item.latestPriceSource ?? 'unknown'}</Badge>
            </dd>
            <dd className="mt-2 text-xs text-secondary-text">
              {item.latestPriceSource === 'ohlcv'
                ? 'No reliable latest matched quote field is present, so daily OHLCV close is used.'
                : isSsiDailyPriceSource(item.latestPriceSource)
                  ? 'SSI DailyOhlc close is used because no reliable latest matched quote field is present.'
                : 'Daily price comes from quote data when a reliable field is present.'}
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Date / final close</dt>
            <dd className="mt-1 font-medium text-foreground">{item.latestPriceDate ?? item.priceDate ?? '-'} / {finalCloseLabel}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Vs reference</dt>
            <dd className={cn('mt-1 font-medium', signalTone(priceVsReference))}>
              {formatReferenceDelta(priceVsReference, priceVsReferencePct)}
            </dd>
          </div>
          {ssiDailyRows.filter((row) => ['Reference price', 'Ceiling price / floor price', 'Ceiling price', 'Floor price', 'Adjusted close'].includes(row.label)).map((row) => (
            <div key={`${item.ticker}-price-context-${row.label}`} className="rounded-lg bg-card/60 p-3">
              <dt className="text-xs text-secondary-text">{row.label === 'Reference price' ? 'Reference' : row.label === 'Ceiling price / floor price' ? 'Ceiling / floor' : row.label}</dt>
              <dd className={cn('mt-1 font-medium text-foreground', row.tone)}>{row.value}</dd>
            </div>
          ))}
          {ssiDailyStockPrice.date ? (
            <div className="rounded-lg bg-card/60 p-3">
              <dt className="text-xs text-secondary-text">SSI date</dt>
              <dd className="mt-1 font-medium text-foreground">{ssiDailyStockPrice.date}</dd>
            </div>
          ) : null}
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Last fetched</dt>
            <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(latestFetchedValue(item))}</dd>
            <dd className="mt-1 text-xs text-secondary-text">{formatRelativeAge(latestFetchedValue(item))}</dd>
          </div>
        </dl>
      </SelectedTickerDisclosure>

      <SelectedTickerDisclosure title="Flow context">
        <p className="mb-3 text-xs text-secondary-text">
          SSI DailyStockPrice · Volume fields: shares · Value fields: VND.
        </p>
        <dl className="grid gap-3 text-sm md:grid-cols-3 xl:grid-cols-4">
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">20D avg volume</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(avgVolume20D)}</dd>
          </div>
          {sessionVolumeRatioText ? (
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Session / 20D</dt>
            <dd className="mt-1 font-medium text-foreground">{sessionVolumeRatioText}</dd>
          </div>
          ) : null}
          {ssiDailyRows.filter((row) => ['Foreign buy', 'Foreign sell', 'Foreign net volume', 'Foreign net value', 'Matched volume', 'Matched value', 'Put-through volume', 'Put-through value'].includes(row.label)).map((row) => (
            <div key={`${item.ticker}-flow-context-${row.label}`} className="rounded-lg bg-card/60 p-3">
              <dt className="text-xs text-secondary-text">{row.label === 'Foreign net volume' ? 'Foreign net' : row.label}</dt>
              <dd className={cn('mt-1 font-medium text-foreground', row.tone)}>{row.value}</dd>
            </div>
          ))}
          {hasForeignNetHistory || !hasSsiDailyStockPrice ? (
            <>
              <div className="rounded-lg bg-card/60 p-3">
                <dt className="text-xs text-secondary-text">Foreign net 5D</dt>
                <dd className={cn('mt-1 font-medium', signalTone(foreignNet5dLatestAvailable))}>
                  {foreignNet5dLatestAvailable == null && foreignHistoryCount < 5 ? 'Need 5 foreign rows' : formatNumber(foreignNet5dLatestAvailable)}
                </dd>
              </div>
              <div className="rounded-lg bg-card/60 p-3">
                <dt className="text-xs text-secondary-text">Foreign net 20D</dt>
                <dd className={cn('mt-1 font-medium', signalTone(foreignNet20dLatestAvailable))}>
                  {foreignNet20dLatestAvailable == null && foreignHistoryCount < 20 ? 'Need 20 foreign rows' : formatNumber(foreignNet20dLatestAvailable)}
                </dd>
              </div>
              <div className="rounded-lg bg-card/60 p-3">
                <dt className="text-xs text-secondary-text">Daily / foreign dates</dt>
                <dd className="mt-1 font-medium text-foreground">{item.ohlcvDate ?? '-'} / {item.foreignNetDate ?? '-'}</dd>
              </div>
              <div className="rounded-lg bg-card/60 p-3">
                <dt className="text-xs text-secondary-text">Foreign date match</dt>
                <dd className="mt-1">
                  <Badge variant={dateMatchVariant(item.foreignDateMatch)}>{item.foreignDateMatch ?? 'unknown'}</Badge>
                </dd>
              </div>
            </>
          ) : null}
        </dl>
      </SelectedTickerDisclosure>

      <SelectedTickerDisclosure title="Technical context">
      <div className="rounded-lg border border-border/60 bg-elevated/30 p-4">
        <h3 className="text-sm font-semibold text-foreground">Condition summary</h3>
        <p className="mt-1 text-xs text-secondary-text">{VIETNAM_CONDITION_SUMMARY_SUBTITLE}</p>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-secondary-text">
          {conditionSummary.map((bullet) => (
            <li key={`${item.ticker}-condition-${bullet}`}>{bullet}</li>
          ))}
        </ul>
      </div>
      <DataCaveatDisclosure item={item} className="mt-3" testId="selected-data-caveats" />
      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-4">
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Bollinger 20,2</dt>
          <dd className="mt-1 font-medium text-foreground">
            {formatPrice(indicators.bollinger?.lower)} / {formatPrice(indicators.bollinger?.middle)} / {formatPrice(indicators.bollinger?.upper)}
          </dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">To 20D high</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(indicators.distanceTo20dHighPct, 2)}%</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">To 20D low</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(indicators.distanceTo20dLowPct, 2)}%</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">MA20 / MA50</dt>
          <dd className="mt-1 font-medium text-foreground">{formatPrice(indicators.ma20)} / {formatPrice(indicators.ma50)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">RSI14</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(indicators.rsi14Wilder ?? indicators.rsi14, 2)}</dd>
        </div>
      </dl>
      <InspectChartCard item={item} />
      {marketStatusDetails.length ? (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-foreground">Condition reasons</h3>
          <div className="mt-2 grid gap-2">
            {marketStatusDetails.map((detail) => (
              <div key={`${detail.label}-${detail.reason}`} className="rounded-lg border border-border/60 bg-elevated/40 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={severityVariant(detail.severity)}>{detail.label}</Badge>
                  <span className="text-xs text-secondary-text">{detail.severity}</span>
                </div>
                <p className="mt-2 text-sm text-secondary-text">{detail.reason}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      </SelectedTickerDisclosure>

      <SelectedTickerDisclosure title="Source coverage">
      <div className="rounded-lg border border-border/60 bg-elevated/30 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Symbol metadata</h3>
              <p className="mt-1 text-xs text-secondary-text">SSI Securities and SecuritiesDetails coverage.</p>
            </div>
            <div className="flex flex-wrap gap-1">
              <Badge variant={metadataQualityStatus === 'complete' ? 'success' : 'warning'}>{metadataQualityStatus}</Badge>
              <Badge variant="default">{symbolMetadata.source ?? item.metadataSource ?? 'SSI SecuritiesDetails'}</Badge>
            </div>
          </div>
          {symbolMetadataRows.length ? (
            <dl className="mt-3 grid gap-3 text-sm md:grid-cols-3 xl:grid-cols-4">
            {symbolMetadataRows.map((row) => (
              <div key={`${item.ticker}-metadata-${row.label}`}>
                <dt className="text-xs text-secondary-text">{row.label}</dt>
                <dd className="mt-1 font-medium text-foreground">{row.value}</dd>
              </div>
            ))}
            </dl>
          ) : null}
          {metadataQualityStatus === 'partial' ? (
            <p className="mt-3 text-xs text-secondary-text">Profile partial. Some metadata is unavailable.</p>
          ) : metadataQualityStatus === 'unavailable' ? (
            <p className="mt-3 text-xs text-secondary-text">Profile unavailable. Daily SSI data is still available.</p>
          ) : null}
        </div>
      <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-foreground">DailyStockPrice coverage</h3>
            <p className="mt-1 text-xs text-secondary-text">Reference, limits, matched, put-through, and foreign fields.</p>
          </div>
          <div className="flex flex-wrap gap-1">
            <Badge variant={ssiDailyQualityStatus === 'ok' ? 'info' : 'warning'}>{ssiDailyQualityStatus ?? 'unavailable'}</Badge>
            <Badge variant="default">{ssiDailySource}</Badge>
            <Badge variant={dateMatchVariant(ssiDailyDateMatch)}>{ssiDailyDateMatch}</Badge>
          </div>
        </div>
        <p className="mt-3 text-sm text-secondary-text">
          {ssiDailyRows.length
            ? 'DailyStockPrice values are organized under Price context and Flow context.'
            : 'SSI DailyStockPrice fields are unavailable for this ticker.'}
        </p>
        <p className="mt-3 text-xs text-secondary-text">
          Adjusted close is shown only when SSI provides it. Corporate actions are not inferred from reference or adjusted prices.
        </p>
      </div>
      <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Corporate actions</h3>
            <p className="mt-1 text-xs text-secondary-text">Recent and upcoming events</p>
          </div>
          <Badge variant={corporateActions?.status === 'ok' ? 'info' : 'default'}>
            {corporateActionsLoading ? 'loading' : corporateActions?.status ?? 'unavailable'}
          </Badge>
        </div>
        {corporateActionsLoading ? (
          <p className="mt-3 text-sm text-secondary-text">Checking corporate action calendar...</p>
        ) : corporateActionsUnavailable ? (
          <p className="mt-3 text-sm text-secondary-text">Corporate action history/calendar unavailable.</p>
        ) : displayCorporateActions.length ? (
          <div className="mt-3 grid gap-4">
            <div>
              <h4 className="text-xs font-semibold uppercase text-secondary-text">Upcoming</h4>
              <div className="mt-2 grid gap-2">
                {upcomingCorporateActions.length ? upcomingCorporateActions.map((event, index) => (
                  <CorporateActionEventRow key={`${event.ticker}-${event.eventType}-${event.exDate ?? event.recordDate ?? index}`} event={event} />
                )) : <p className="text-xs text-secondary-text">No upcoming events.</p>}
              </div>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase text-secondary-text">Recent, last {corporateActions?.monthsBack ?? 6} months</h4>
              <div className="mt-2 grid gap-2">
                {recentCorporateActions.length ? recentCorporateActions.map((event, index) => (
                  <CorporateActionEventRow key={`${event.ticker}-${event.eventType}-${event.exDate ?? event.recordDate ?? index}`} event={event} />
                )) : <p className="text-xs text-secondary-text">No recent events.</p>}
              </div>
            </div>
          </div>
        ) : (
          <p className="mt-3 text-sm text-secondary-text">No recent or upcoming corporate actions found.</p>
        )}
        {corporateActions?.source || corporateActions?.lastCheckedAt ? (
          <p className="mt-3 text-xs text-secondary-text">
            Source: {corporateActions.source ?? '-'} | last checked {formatVietnamTime(corporateActions.lastCheckedAt)}
          </p>
        ) : null}
        {corporateActions?.errorDetail ? (
          <p className="mt-2 text-xs text-secondary-text">{corporateActions.errorDetail}</p>
        ) : null}
      </div>
      {!hasSsiDailyStockPrice && item.foreignDateMatch === 'mismatched' && item.foreignNetDate && item.ohlcvDate ? (
        <p className="mt-3 text-xs text-secondary-text">
          Foreign data as of {item.foreignNetDate}; OHLCV date {item.ohlcvDate}.
        </p>
      ) : null}
      </SelectedTickerDisclosure>

      <SelectedTickerDisclosure title="Live context">
      <div className="rounded-lg border border-border/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Intraday</h3>
            <p className="mt-1 text-xs text-secondary-text">
              {item.intradaySource ?? item.intradayStatus?.source ?? 'SSI IntradayOhlc'} provider-returned candles. {intradayCadenceText(item)}. Status: {item.intradayStatus?.status ?? 'disabled'}.
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            <Badge variant={sectionStateVariant(intradaySectionState)}>{intradaySectionState}</Badge>
            <Badge variant="default">{item.intradaySource ?? item.intradayStatus?.source ?? 'SSI'}</Badge>
            <Badge variant={intradayCadenceStatus(item) === 'matched' ? 'info' : 'warning'}>{intradayCadenceText(item)}</Badge>
            <Badge variant={item.intradayIsRealtimeQuote ? 'success' : 'warning'}>
              {item.intradayIsRealtimeQuote ? 'Realtime quote' : 'Not realtime quote'}
            </Badge>
          </div>
        </div>
        {item.intradayWarning ? (
          <div className="mt-3 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
            {item.intradayWarning}
          </div>
        ) : null}
        {hasCurrentIntraday ? (
        <dl className="mt-3 grid gap-3 text-sm md:grid-cols-4">
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Intraday close</dt>
            <dd className="mt-1 font-medium text-foreground">{formatPrice(intradayLatestClose(item))}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Intraday change</dt>
            <dd className={cn('mt-1 font-medium', signalTone(intradayChange(item)))}>
              {formatPrice(intradayChange(item))} / {formatNumber(intradayChangePercent(item), 2)}%
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">High / low / range</dt>
            <dd className="mt-1 font-medium text-foreground">
              {formatPrice(intradayLatestHigh(item))} / {formatPrice(intradayLatestLow(item))} / {formatNumber(item.intradayPulse?.rangePercent, 2)}%
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Intraday volume</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(intradayLatestVolume(item))}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Session high / low from intraday</dt>
            <dd className="mt-1 font-medium text-foreground" title={hasSessionHighLowFromIntraday ? undefined : missingSessionHighLowTitle}>
              {hasSessionHighLowFromIntraday
                ? `${formatPrice(intradaySessionHigh(item))} / ${formatPrice(intradaySessionLow(item))}`
                : missingSessionMetricText}
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Session range from intraday</dt>
            <dd className="mt-1 font-medium text-foreground" title={hasSessionRangeFromIntraday ? undefined : missingSessionRangeTitle}>
              {hasSessionRangeFromIntraday ? `${formatNumber(intradaySessionRange(item), 2)}%` : missingSessionMetricText}
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Session intraday volume</dt>
            <dd className="mt-1 font-medium text-foreground" title={hasSessionVolumeFromIntraday ? undefined : missingSessionVolumeTitle}>
              {hasSessionVolumeFromIntraday ? formatNumber(intradaySessionVolume(item)) : missingSessionMetricText}
            </dd>
          </div>
          {hasVolumeVsAverage ? (
            <div className="rounded-lg bg-card/60 p-3">
              <dt className="text-xs text-secondary-text">Volume vs average</dt>
              <dd className="mt-1 font-medium text-foreground">
                {formatRatio(intradayVolumeVsAverage(item))}
              </dd>
            </div>
          ) : null}
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Candles loaded</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(item.intradayCandles?.length ?? 0)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Session candles</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(sessionCandlesCount)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Provider cadence</dt>
            <dd className="mt-1 font-medium text-foreground">{intradayCadenceText(item)}</dd>
            <dd className="mt-1 text-xs text-secondary-text">Requested {item.intradayRequestedTimeframe ?? item.intradayTimeframe ?? '-'}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Intraday / daily date</dt>
            <dd className="mt-1 font-medium text-foreground">{item.intradayLatestDate ?? '-'} / {item.dailyPriceDate ?? '-'}</dd>
            <dd className="mt-1 text-xs text-secondary-text">{item.dateMatch ?? 'unknown'}</dd>
          </div>
        </dl>
        ) : (
          <p className="mt-3 text-sm text-secondary-text">{optionalLiveStatusText('intraday', item.intradayStatus)}</p>
        )}
        {hasCurrentIntraday ? (
        <div className="mt-3 flex flex-wrap gap-1">
          {(item.intradayLabels ?? []).map((label) => (
            <Badge key={`${item.ticker}-detail-${label}`} variant={intradayVariant(label)}>{label}</Badge>
          ))}
        </div>
        ) : null}
        {hasCurrentIntraday && item.intradayDetails?.length ? (
          <div className="mt-3 grid gap-2">
            {item.intradayDetails.map((detail) => (
              <div key={`${item.ticker}-intraday-${detail.label}-${detail.reason}`} className="rounded-lg border border-border/50 bg-card/50 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={severityVariant(detail.severity)}>{detail.label}</Badge>
                  <span className="text-xs text-secondary-text">{detail.severity}</span>
                </div>
                <p className="mt-2 text-sm text-secondary-text">{detail.reason}</p>
              </div>
            ))}
          </div>
        ) : null}
        <p className="mt-3 text-xs text-secondary-text">
          {item.intradayStatus?.status === 'ok'
            ? 'SSI IntradayOhlc candles are separate from SSI realtime board and trade tape context.'
            : 'SSI intraday is unavailable or disabled; SSI realtime board and trade tape context remain separate.'}
        </p>
      </div>
      <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-foreground">SSI realtime</h3>
          <div className="flex flex-wrap gap-1">
            <Badge variant={sectionStateVariant(realtimeSectionState)}>{realtimeSectionState}</Badge>
            <Badge variant={realtimeSnapshotStateVariant(realtimeState)}>{realtimeState.label}</Badge>
          </div>
        </div>
        {hasRealtimeSnapshot ? (
        <dl className="mt-3 grid gap-3 text-sm md:grid-cols-4">
          <div>
            <dt className="text-xs text-secondary-text">Realtime price</dt>
            <dd className="mt-1 font-medium text-foreground">{formatPrice(realtimeQuote?.snapshotPrice ?? realtimeQuote?.realtimePrice)}</dd>
          </div>
          <div>
            <dt className="text-xs text-secondary-text">Realtime time</dt>
            <dd className="mt-1 font-medium text-foreground">{realtimeSnapshotTimeText(realtimeQuote)}</dd>
            <dd className="mt-1 text-xs text-secondary-text">{realtimeSnapshotFreshnessText(realtimeQuote)}</dd>
          </div>
          <div>
            <dt className="text-xs text-secondary-text">Realtime change</dt>
            <dd className={cn('mt-1 font-medium', signalTone(realtimeQuote?.priceChange))}>
              {formatPrice(realtimeQuote?.priceChange)} / {formatNumber(realtimeQuote?.percentChange, 2)}%
            </dd>
          </div>
          <div>
            <dt className="text-xs text-secondary-text">Realtime volume</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(realtimeQuote?.volumeAccumulated)}</dd>
          </div>
        </dl>
        ) : (
          <p className="mt-3 text-sm text-secondary-text">{realtimeUnavailableStatusText(item.realtimeStatus)}</p>
        )}
        {hasRealtimeSnapshot ? (
        <p className="mt-3 text-xs text-secondary-text">
          {realtimeState.reason}
        </p>
        ) : null}
        {hasRealtimeSnapshot && realtimeQuote?.error ? (
          <p className="mt-1 text-xs text-secondary-text">{realtimeErrorMessage(realtimeQuote.error)}</p>
        ) : null}
        {hasRealtimeSnapshot ? (
        <p className="mt-3 text-xs text-secondary-text">
          {realtimeQuote?.snapshotNote ?? 'SSI realtime snapshot; may differ from trade tape'}
        </p>
        ) : null}
      </div>
      <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-foreground">Trade tape</h3>
          <div className="flex flex-wrap gap-1">
            <Badge variant={sectionStateVariant(tradeTapeSectionState)}>{tradeTapeSectionState}</Badge>
            <Badge variant={tradesError ? 'warning' : 'info'}>SSI trade tape</Badge>
          </div>
        </div>
        <p className="mt-2 text-xs text-secondary-text">
          Historical trade tape is separate from X-TRADE latest-trade stream context.
        </p>
        {tradesError || (!tradesLoading && !hasTradeTape) ? (
          <div className="mt-3 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
            {optionalLiveStatusText('tradeTape', item.tradeTapeStatus)}
          </div>
        ) : null}
        {hasTradeTape ? (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-xs">
              <thead className="border-b border-border/70 uppercase text-secondary-text">
                <tr>
                  <th className="py-2 pr-3">Time</th>
                  <th className="px-3 py-2 text-right">Trade tape price</th>
                  <th className="px-3 py-2 text-right">Trade tape volume</th>
                  <th className="px-3 py-2">Trade type</th>
                  <th className="px-3 py-2">Source</th>
                </tr>
              </thead>
              <tbody>
                {realtimeTrades.slice(0, 8).map((trade, index) => (
                  <tr key={`${trade.id ?? index}-${trade.time ?? 'time'}`} className="border-b border-border/40 text-secondary-text">
                    <td className="py-2 pr-3">{trade.time ?? '-'}</td>
                    <td className="px-3 py-2 text-right text-foreground">{formatPrice(trade.price)}</td>
                    <td className="px-3 py-2 text-right">{formatNumber(trade.volume)}</td>
                    <td className="px-3 py-2">{neutralTradeType(trade.matchType)}</td>
                    <td className="px-3 py-2">{trade.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
      </SelectedTickerDisclosure>

      <SelectedTickerDisclosure title="News context">
      <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-foreground">News</h3>
          <Badge variant={detailNewsItems.length ? 'info' : 'default'}>{newsContextStatus}</Badge>
        </div>
        {detailNewsItems.length ? (
          <div className="mt-3 grid gap-3">
            {detailNewsItems.slice(0, DETAIL_NEWS_LIMIT).map((news, index) => {
              const summaryHasArtifacts = hasEncodingArtifacts(news.summary);
              const titleHasArtifacts = hasEncodingArtifacts(news.title);
              const timestamp = newsTimestamp(news);
              const absoluteTime = parseMozyTimestamp(timestamp) ? formatAbsoluteDateTime(timestamp) : undefined;
              return (
                <article key={`${item.ticker}-detail-news-${news.url ?? news.title ?? index}`} className="rounded-lg border border-border/50 bg-card/50 p-3">
                  <a
                    href={news.url || '#'}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-cyan hover:underline"
                  >
                    {neutralizeRecommendationText(news.title) || 'Untitled news'}
                  </a>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-secondary-text" title={absoluteTime}>
                    {news.source ? <span>{news.source}</span> : null}
                    {news.source ? <span aria-hidden="true">·</span> : null}
                    <span>{formatRelativeTime(timestamp)}</span>
                  </div>
                  {news.summary && !summaryHasArtifacts ? (
                    <p className="mt-2 line-clamp-2 text-sm text-secondary-text">{neutralizeRecommendationText(news.summary)}</p>
                  ) : summaryHasArtifacts ? (
                    <p className="mt-2 text-xs text-warning">Summary hidden because text encoding looks damaged.</p>
                  ) : null}
                  {titleHasArtifacts ? (
                    <p className="mt-2 text-xs text-warning">Title may contain source encoding artifacts.</p>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 text-sm text-secondary-text">
            {newsUnavailableText(item)}
          </p>
        )}
      </div>
      </SelectedTickerDisclosure>

      <SelectedTickerDisclosure title="Diagnostics">
        <p className="text-xs font-medium text-foreground">Advanced / Raw Data</p>
        <div className="mt-3 grid gap-3 text-xs md:grid-cols-2">
          <div>
            <p className="font-medium text-foreground">Raw fields</p>
            <p>latest_price_raw_field: {item.latestPriceRawField ?? '-'}</p>
            <p>quote_price_raw_field: {item.quotePriceRawField ?? '-'}</p>
            <p>foreign_buy_raw_field: {item.foreignBuyRawField ?? '-'}</p>
            <p>foreign_sell_raw_field: {item.foreignSellRawField ?? '-'}</p>
          </div>
          <div>
            <p className="font-medium text-foreground">Raw timestamps</p>
            <p>latest_price_date: {rawDateLabel(item.latestPriceDate)}</p>
            <p>quote_date: {rawDateLabel(item.quoteDate)}</p>
            <p>intraday date_time: {rawDateLabel(latestIntradayCandle?.dateTime)}</p>
            <p>intraday timestamp: {rawDateLabel(latestIntradayCandle?.timestamp)}</p>
          </div>
          <div>
            <p className="font-medium text-foreground">Cache internals</p>
            <pre className="mt-1 max-h-44 overflow-auto rounded bg-background/60 p-2">{JSON.stringify({
              status: item.cacheStatus,
              lastFetchedAt: item.cacheLastFetchedAt,
              nextRefreshAt: item.cacheNextRefreshAt,
              errors: item.cacheErrors,
            }, null, 2)}</pre>
          </div>
          <div>
            <p className="font-medium text-foreground">Rule inputs</p>
            <pre className="mt-1 max-h-44 overflow-auto rounded bg-background/60 p-2">{JSON.stringify({
              statusDetails: item.statusDetails,
              intradayDetails: item.intradayDetails,
            }, null, 2)}</pre>
          </div>
          {symbolMetadata.diagnostics && Object.keys(symbolMetadata.diagnostics).length ? (
            <div>
              <p className="font-medium text-foreground">Profile metadata diagnostics</p>
              <pre className="mt-1 max-h-44 overflow-auto rounded bg-background/60 p-2">{JSON.stringify(symbolMetadata.diagnostics, null, 2)}</pre>
            </div>
          ) : null}
        </div>
      </SelectedTickerDisclosure>
      </div>
    </section>
  );
};

const VietnamDashboardPage: React.FC = () => {
  const initialCustomWatchlist = useMemo(() => readCustomWatchlist(), []);
  const [watchlist, setWatchlist] = useState<string[]>(DEFAULT_WATCHLIST);
  const [activePresetId, setActivePresetId] = useState<VietnamDashboardActivePresetId>('my');
  const [customWatchlistInput, setCustomWatchlistInput] = useState(() => formatCustomWatchlistInput(initialCustomWatchlist));
  const [customWatchlist, setCustomWatchlist] = useState<string[]>(initialCustomWatchlist);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [customNotice, setCustomNotice] = useState<string | null>(initialCustomWatchlist.length ? 'Saved locally in this browser.' : null);
  const [data, setData] = useState<VietnamWatchlistResponse | null>(null);
  const [realtimeQuotes, setRealtimeQuotes] = useState<Record<string, VietnamRealtimeQuote | undefined>>({});
  const [realtimeLoading, setRealtimeLoading] = useState(false);
  const [realtimeError, setRealtimeError] = useState<string | null>(null);
  const [realtimeTrades, setRealtimeTrades] = useState<VietnamRealtimeTrade[]>([]);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [corporateActions, setCorporateActions] = useState<VietnamCorporateActionsResponse | null>(null);
  const [corporateActionsLoading, setCorporateActionsLoading] = useState(false);
  const [corporateActionsError, setCorporateActionsError] = useState<string | null>(null);
  const [dailyIndex, setDailyIndex] = useState<VietnamDailyIndexResponse | null>(null);
  const [indexList, setIndexList] = useState<VietnamIndexListResponse | null>(null);
  const [indexComponents, setIndexComponents] = useState<VietnamIndexComponentsResponse | null>(null);
  const [indexCoverageError, setIndexCoverageError] = useState<string | null>(null);
  const [lastRealtimeSnapshotRefreshAt, setLastRealtimeSnapshotRefreshAt] = useState<string | null>(null);
  const [lastTradeTapeRefreshAt, setLastTradeTapeRefreshAt] = useState<string | null>(null);
  const [lastRealtimeErrorAt, setLastRealtimeErrorAt] = useState<string | null>(null);
  const [observability, setObservability] = useState<VietnamObservabilityResponse | null>(null);
  const [marketPhase, setMarketPhase] = useState(() => getVietnamMarketPhase());
  const [loading, setLoading] = useState(true);
  const [forceLoading, setForceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(DEFAULT_WATCHLIST[0]);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(180);
  const [realtimeAutoRefreshEnabled, setRealtimeAutoRefreshEnabled] = useState(true);
  const [realtimeSnapshotRefreshInterval, setRealtimeSnapshotRefreshInterval] = useState(3);
  const [tradeTapeAutoRefreshEnabled, setTradeTapeAutoRefreshEnabled] = useState(false);
  const [tradeTapeRefreshInterval, setTradeTapeRefreshInterval] = useState(10);
  const [realtimeSnapshotNextRefreshAt, setRealtimeSnapshotNextRefreshAt] = useState<number | null>(null);
  const [tradeTapeNextRefreshAt, setTradeTapeNextRefreshAt] = useState<number | null>(null);
  const [realtimeSnapshotCountdownSeconds, setRealtimeSnapshotCountdownSeconds] = useState<number | null>(null);
  const [tradeTapeCountdownSeconds, setTradeTapeCountdownSeconds] = useState<number | null>(null);
  const [lastRefreshKind, setLastRefreshKind] = useState<'manual' | 'auto' | 'force live'>('manual');
  const [lastRefreshAt, setLastRefreshAt] = useState<string | null>(null);
  const [nextRefreshAt, setNextRefreshAt] = useState<number | null>(null);
  const [countdownSeconds, setCountdownSeconds] = useState<number | null>(null);
  const [isTabHidden, setIsTabHidden] = useState(() => typeof document !== 'undefined' && document.visibilityState === 'hidden');
  const logicalWatchlist = useMemo(() => {
    const seen = new Set<string>();
    return watchlist
      .map((ticker) => normalizeVietnamTicker(ticker))
      .filter((ticker) => {
        if (!ticker || seen.has(ticker)) return false;
        seen.add(ticker);
        return true;
      });
  }, [watchlist]);
  const logicalWatchlistKey = useMemo(() => logicalWatchlist.join(','), [logicalWatchlist]);
  const logicalWatchlistRef = useRef(logicalWatchlist);
  logicalWatchlistRef.current = logicalWatchlist;
  const selectedTickerRef = useRef(selectedTicker);
  selectedTickerRef.current = selectedTicker;
  const requestIdRef = useRef(0);
  const initialWatchlistLoadStartedRef = useRef(false);
  const realtimeRequestIdRef = useRef(0);
  const tradesRequestIdRef = useRef(0);
  const corporateActionsRequestIdRef = useRef(0);
  const nextRefreshAtRef = useRef(0);
  const realtimeSnapshotNextRefreshAtRef = useRef(0);
  const tradeTapeNextRefreshAtRef = useRef(0);
  const realtimeSnapshotRefreshInFlightRef = useRef(false);
  const tradeTapeRefreshInFlightRef = useRef(false);
  const pendingRealtimeSnapshotTickersRef = useRef<string[] | null>(null);
  const pendingTradeTapeSymbolRef = useRef<string | null>(null);
  const unmountedRef = useRef(false);

  useEffect(() => () => {
    unmountedRef.current = true;
    realtimeRequestIdRef.current += 1;
    tradesRequestIdRef.current += 1;
    corporateActionsRequestIdRef.current += 1;
  }, []);

  const loadObservability = useCallback(async () => {
    try {
      const response = await stocksApi.getVietnamObservability();
      setObservability(response);
    } catch {
      // Observability is diagnostic only; keep dashboard data flows independent.
    }
  }, []);

  const loadRealtimeQuotes = useCallback(async (tickers: string[]) => {
    const seen = new Set<string>();
    const requestedTickers = tickers
      .map((ticker) => normalizeVietnamTicker(ticker))
      .filter((ticker) => {
        if (!/^[A-Z0-9]{2,10}$/.test(ticker) || seen.has(ticker)) return false;
        seen.add(ticker);
        return true;
      })
      .slice(0, VIETNAM_WATCHLIST_MAX_SIZE);
    if (!requestedTickers.length) {
      setRealtimeQuotes({});
      return;
    }
    const requestId = realtimeRequestIdRef.current + 1;
    realtimeRequestIdRef.current = requestId;
    setRealtimeLoading(true);
    setRealtimeError(null);
    try {
      const response = await stocksApi.getVietnamRealtimeQuotes(requestedTickers);
      if (requestId !== realtimeRequestIdRef.current || unmountedRef.current) return;
      const nextQuotes = Object.fromEntries(
        response.quotes
          .map((quote) => [normalizeVietnamTicker(quote.symbol ?? quote.ticker ?? ''), quote] as const)
          .filter(([ticker]) => Boolean(ticker)),
      );
      if (Object.keys(nextQuotes).length || response.status === 'ok') {
        setRealtimeQuotes((previous) => (
          response.status === 'ok'
            ? nextQuotes
            : { ...previous, ...nextQuotes }
        ));
      }
      setLastRealtimeSnapshotRefreshAt(new Date().toISOString());
      setRealtimeError(response.status === 'ok' ? null : realtimeErrorMessage(response.statusMessage ?? response.error) ?? 'SSI realtime unavailable');
      if (response.status !== 'ok') {
        setLastRealtimeErrorAt(new Date().toISOString());
      }
      void loadObservability();
    } catch (err) {
      if (requestId !== realtimeRequestIdRef.current || unmountedRef.current) return;
      setLastRealtimeErrorAt(new Date().toISOString());
      setRealtimeError(realtimeErrorMessage(err instanceof Error ? err.message : null) ?? (err instanceof Error ? err.message : 'SSI realtime unavailable'));
      void loadObservability();
    } finally {
      if (requestId === realtimeRequestIdRef.current && !unmountedRef.current) {
        setRealtimeLoading(false);
      }
    }
  }, [loadObservability]);

  const loadRealtimeTrades = useCallback(async (symbol: string | null) => {
    if (!symbol) {
      setRealtimeTrades([]);
      return;
    }
    const requestId = tradesRequestIdRef.current + 1;
    tradesRequestIdRef.current = requestId;
    setTradesLoading(true);
    setTradesError(null);
    try {
      const response = await stocksApi.getVietnamRealtimeTrades(symbol, 100);
      if (requestId !== tradesRequestIdRef.current || unmountedRef.current) return;
      if (symbol !== selectedTickerRef.current) return;
      setRealtimeTrades(response.trades);
      setLastTradeTapeRefreshAt(new Date().toISOString());
      setTradesError(response.status === 'ok' ? null : realtimeErrorMessage(response.statusMessage ?? response.error) ?? 'Trade tape unavailable');
      if (response.status !== 'ok') {
        setLastRealtimeErrorAt(new Date().toISOString());
      }
      void loadObservability();
    } catch (err) {
      if (requestId !== tradesRequestIdRef.current || unmountedRef.current) return;
      setLastRealtimeErrorAt(new Date().toISOString());
      setTradesError(realtimeErrorMessage(err instanceof Error ? err.message : null) ?? (err instanceof Error ? err.message : 'Trade tape unavailable'));
      void loadObservability();
    } finally {
      if (requestId === tradesRequestIdRef.current && !unmountedRef.current) {
        setTradesLoading(false);
      }
    }
  }, [loadObservability]);

  const loadCorporateActions = useCallback(async (symbol: string | null) => {
    if (!symbol) {
      setCorporateActions(null);
      setCorporateActionsError(null);
      return;
    }
    const requestId = corporateActionsRequestIdRef.current + 1;
    corporateActionsRequestIdRef.current = requestId;
    setCorporateActionsLoading(true);
    setCorporateActionsError(null);
    try {
      const response = await stocksApi.getVietnamCorporateActions([symbol], 6);
      if (requestId !== corporateActionsRequestIdRef.current || unmountedRef.current) return;
      if (symbol !== selectedTickerRef.current) return;
      setCorporateActions(response);
      setCorporateActionsError(response.status === 'error' ? response.error ?? 'Corporate action history/calendar unavailable.' : null);
    } catch (err) {
      if (requestId !== corporateActionsRequestIdRef.current || unmountedRef.current) return;
      setCorporateActions(null);
      setCorporateActionsError(err instanceof Error ? err.message : 'Corporate action history/calendar unavailable.');
    } finally {
      if (requestId === corporateActionsRequestIdRef.current && !unmountedRef.current) {
        setCorporateActionsLoading(false);
      }
    }
  }, []);

  const loadIndexCoverage = useCallback(async () => {
    setIndexCoverageError(null);
    const [listResult, dailyResult, componentResult] = await Promise.allSettled([
      stocksApi.getVietnamIndexList('HOSE'),
      stocksApi.getVietnamDailyIndex(['VNINDEX', 'VN30']),
      stocksApi.getVietnamIndexComponents('VN30'),
    ]);

    if (listResult.status === 'fulfilled') {
      setIndexList(listResult.value);
    } else {
      setIndexList({
        status: 'unavailable',
        source: 'SSI IndexList',
        reason: 'IndexList unavailable',
        market: 'HOSE',
        rows: [],
        count: 0,
        fallbackUsed: false,
      });
    }

    if (dailyResult.status === 'fulfilled') {
      setDailyIndex(dailyResult.value);
    } else {
      setDailyIndex({
        status: 'unavailable',
        source: 'SSI DailyIndex',
        reason: 'SSI daily index unavailable.',
        requestedIndexCodes: ['VNINDEX', 'VN30'],
        latestDate: null,
        rows: [],
        count: 0,
        fallbackUsed: false,
      });
    }

    if (componentResult.status === 'fulfilled') {
      setIndexComponents(componentResult.value);
    } else {
      setIndexComponents({
        status: 'unavailable',
        source: 'SSI IndexComponents',
        reason: 'IndexComponents unavailable',
        indexCode: 'VN30',
        rows: [],
        count: 0,
        fallbackUsed: false,
      });
    }

    if (listResult.status === 'rejected' || dailyResult.status === 'rejected' || componentResult.status === 'rejected') {
      setIndexCoverageError('SSI index coverage request unavailable.');
    }
  }, []);

  const refreshRealtimeSnapshots = useCallback(async (tickersOverride?: string[]) => {
    const targetTickers = tickersOverride ?? logicalWatchlistRef.current;
    if (realtimeSnapshotRefreshInFlightRef.current) {
      if (tickersOverride) {
        pendingRealtimeSnapshotTickersRef.current = targetTickers;
      }
      return false;
    }
    realtimeSnapshotRefreshInFlightRef.current = true;
    try {
      await loadRealtimeQuotes(targetTickers);
      return true;
    } finally {
      realtimeSnapshotRefreshInFlightRef.current = false;
      const pendingTickers = pendingRealtimeSnapshotTickersRef.current;
      pendingRealtimeSnapshotTickersRef.current = null;
      if (pendingTickers && pendingTickers.join(',') !== targetTickers.join(',')) {
        void refreshRealtimeSnapshots(pendingTickers);
      }
    }
  }, [loadRealtimeQuotes]);

  const refreshTradeTape = useCallback(async (selectedTickerOverride?: string | null) => {
    const targetTicker = selectedTickerOverride ?? selectedTicker;
    if (tradeTapeRefreshInFlightRef.current) {
      if (targetTicker) {
        pendingTradeTapeSymbolRef.current = targetTicker;
      }
      return false;
    }
    tradeTapeRefreshInFlightRef.current = true;
    try {
      await loadRealtimeTrades(targetTicker);
      return true;
    } finally {
      tradeTapeRefreshInFlightRef.current = false;
      const pendingSymbol = pendingTradeTapeSymbolRef.current;
      pendingTradeTapeSymbolRef.current = null;
      if (pendingSymbol && pendingSymbol !== targetTicker) {
        void refreshTradeTape(pendingSymbol);
      }
    }
  }, [loadRealtimeTrades, selectedTicker]);

  const load = useCallback(async (
    forceRefresh = false,
    refreshKind: 'manual' | 'auto' | 'force live' = forceRefresh ? 'force live' : 'manual',
    tickersOverride?: string[],
    commitIntent?: WatchlistCommitIntent,
  ) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setForceLoading(forceRefresh);
    setError(null);
    try {
      const requestedTickers = tickersOverride ?? logicalWatchlistRef.current;
      const nextData = await stocksApi.getVietnamWatchlist(requestedTickers, forceRefresh);
      if (requestId !== requestIdRef.current) return;
      if (!isCompleteWatchlistResponse(nextData, requestedTickers)) {
        setError('Incomplete watchlist response; keeping previous successful snapshot.');
        return;
      }
      setData(nextData);
      if (commitIntent) {
        setWatchlist(commitIntent.tickers);
        setActivePresetId(commitIntent.presetId);
        setSelectedTicker(commitIntent.selectedTicker);
        if (commitIntent.customWatchlist) {
          setCustomWatchlist(commitIntent.customWatchlist);
        }
        if (commitIntent.customWatchlistInput !== undefined) {
          setCustomWatchlistInput(commitIntent.customWatchlistInput);
        }
        if (commitIntent.customNotice !== undefined) {
          setCustomNotice(commitIntent.customNotice);
        }
      }
      setLastRefreshKind(refreshKind);
      setLastRefreshAt(new Date().toISOString());
      void loadObservability();
      void refreshRealtimeSnapshots(requestedTickers);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load Vietnam dashboard');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setForceLoading(false);
      }
    }
  }, [loadObservability, refreshRealtimeSnapshots]);

  const handlePresetSelect = useCallback((presetId: VietnamDashboardPresetId) => {
    const presetTickers = getDashboardPresetTickers(presetId);
    if (!presetTickers) {
      setWatchlistError('Preset list is unavailable.');
      return;
    }
    const nextSelectedTicker = selectedTickerRef.current && presetTickers.includes(selectedTickerRef.current) ? selectedTickerRef.current : presetTickers[0] ?? null;
    setWatchlistError(null);
    void load(false, 'manual', presetTickers, {
      tickers: presetTickers,
      presetId,
      selectedTicker: nextSelectedTicker,
    });
  }, [load]);

  const applyCustomTickers = useCallback((tickers: string[], successNotice = 'Saved locally in this browser.') => {
    const formattedInput = formatCustomWatchlistInput(tickers);
    const nextSelectedTicker = selectedTickerRef.current && tickers.includes(selectedTickerRef.current) ? selectedTickerRef.current : tickers[0] ?? null;
    void load(false, 'manual', tickers, {
      tickers,
      presetId: 'custom',
      selectedTicker: nextSelectedTicker,
      customWatchlist: tickers,
      customWatchlistInput: formattedInput,
      customNotice: successNotice,
    });
  }, [load]);

  const handleCustomPresetSelect = useCallback(() => {
    if (!customWatchlist.length) {
      setWatchlistError('Custom watchlist is empty.');
      setCustomNotice(null);
      return;
    }
    setWatchlistError(null);
    applyCustomTickers(customWatchlist);
  }, [applyCustomTickers, customWatchlist]);

  const handleApplyCustom = useCallback(() => {
    const result = parseCustomWatchlistInput(customWatchlistInput);
    if (result.error) {
      setWatchlistError(result.error);
      setCustomNotice(null);
      return;
    }
    setCustomWatchlistInput(formatCustomWatchlistInput(result.tickers));
    setWatchlistError(null);
    setCustomNotice(result.messages.length ? result.messages.join(' ') : null);
    applyCustomTickers(result.tickers, result.messages.length ? result.messages.join(' ') : 'Saved locally in this browser.');
  }, [applyCustomTickers, customWatchlistInput]);

  const handleSaveCustom = useCallback(() => {
    const result = parseCustomWatchlistInput(customWatchlistInput);
    if (result.error) {
      setWatchlistError(result.error);
      setCustomNotice(null);
      return;
    }
    setCustomWatchlist(result.tickers);
    setCustomWatchlistInput(formatCustomWatchlistInput(result.tickers));
    setWatchlistError(null);
    const saved = writeCustomWatchlist(result.tickers);
    const status = saved ? 'Saved locally in this browser.' : 'Saved for this session only.';
    setCustomNotice([...result.messages, status].join(' '));
  }, [customWatchlistInput]);

  const handleClearCustom = useCallback(() => {
    clearCustomWatchlist();
    setCustomWatchlist([]);
    setCustomWatchlistInput('');
    setWatchlistError(null);
    setCustomNotice(null);
    if (activePresetId === 'custom') {
      setActivePresetId('my');
    }
  }, [activePresetId]);

  const handleResetWatchlist = useCallback(() => {
    const nextSelectedTicker = selectedTickerRef.current && DEFAULT_WATCHLIST.includes(selectedTickerRef.current) ? selectedTickerRef.current : DEFAULT_WATCHLIST[0] ?? null;
    void load(false, 'manual', DEFAULT_WATCHLIST, {
      tickers: DEFAULT_WATCHLIST,
      presetId: 'my',
      selectedTicker: nextSelectedTicker,
    });
    setWatchlistError(null);
  }, [load]);

  const handleRefreshRealtimeData = useCallback(() => {
    void Promise.allSettled([
      refreshRealtimeSnapshots(),
      refreshTradeTape(),
    ]);
  }, [refreshRealtimeSnapshots, refreshTradeTape]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setMarketPhase(getVietnamMarketPhase());
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void loadIndexCoverage();
  }, [loadIndexCoverage]);

  useEffect(() => {
    if (initialWatchlistLoadStartedRef.current) return;
    initialWatchlistLoadStartedRef.current = true;
    void load(false, 'manual', logicalWatchlistRef.current);
  }, [load]);

  useEffect(() => {
    void refreshTradeTape(selectedTicker);
  }, [refreshTradeTape, selectedTicker]);

  useEffect(() => {
    void loadCorporateActions(selectedTicker);
  }, [loadCorporateActions, selectedTicker]);

  useEffect(() => {
    const onVisibilityChange = () => {
      const hidden = document.visibilityState === 'hidden';
      setIsTabHidden(hidden);
      if (!hidden && autoRefreshEnabled) {
        const next = Date.now() + autoRefreshInterval * 1000;
        nextRefreshAtRef.current = next;
        setNextRefreshAt(next);
        setCountdownSeconds(autoRefreshInterval);
      }
      if (!hidden && realtimeAutoRefreshEnabled && Date.now() >= realtimeSnapshotNextRefreshAtRef.current) {
        const next = Date.now() + realtimeSnapshotRefreshInterval * 1000;
        realtimeSnapshotNextRefreshAtRef.current = next;
        setRealtimeSnapshotNextRefreshAt(next);
        setRealtimeSnapshotCountdownSeconds(realtimeSnapshotRefreshInterval);
        void refreshRealtimeSnapshots();
      }
      if (!hidden && tradeTapeAutoRefreshEnabled && Date.now() >= tradeTapeNextRefreshAtRef.current) {
        const next = Date.now() + tradeTapeRefreshInterval * 1000;
        tradeTapeNextRefreshAtRef.current = next;
        setTradeTapeNextRefreshAt(next);
        setTradeTapeCountdownSeconds(tradeTapeRefreshInterval);
        void refreshTradeTape();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [
    autoRefreshEnabled,
    autoRefreshInterval,
    realtimeAutoRefreshEnabled,
    tradeTapeAutoRefreshEnabled,
    realtimeSnapshotRefreshInterval,
    tradeTapeRefreshInterval,
    refreshRealtimeSnapshots,
    refreshTradeTape,
  ]);

  useEffect(() => {
    if (!autoRefreshEnabled) {
      setNextRefreshAt(null);
      setCountdownSeconds(null);
      return undefined;
    }
    const next = Date.now() + autoRefreshInterval * 1000;
    nextRefreshAtRef.current = next;
    setNextRefreshAt(next);
    setCountdownSeconds(autoRefreshInterval);
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'hidden') {
        setIsTabHidden(true);
        setCountdownSeconds(null);
        return;
      }
      setIsTabHidden(false);
      setCountdownSeconds(() => {
        const remaining = Math.max(0, Math.ceil((nextRefreshAtRef.current - Date.now()) / 1000));
        return remaining;
      });
      if (Date.now() >= nextRefreshAtRef.current) {
        const newNext = Date.now() + autoRefreshInterval * 1000;
        nextRefreshAtRef.current = newNext;
        setNextRefreshAt(newNext);
        setCountdownSeconds(autoRefreshInterval);
        void load(false, 'auto');
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [autoRefreshEnabled, autoRefreshInterval, load]);

  useEffect(() => {
    if (!realtimeAutoRefreshEnabled) {
      setRealtimeSnapshotNextRefreshAt(null);
      setRealtimeSnapshotCountdownSeconds(null);
      return undefined;
    }
    const scheduleNext = () => {
      const next = Date.now() + realtimeSnapshotRefreshInterval * 1000;
      realtimeSnapshotNextRefreshAtRef.current = next;
      setRealtimeSnapshotNextRefreshAt(next);
      setRealtimeSnapshotCountdownSeconds(realtimeSnapshotRefreshInterval);
    };
    scheduleNext();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'hidden') {
        setIsTabHidden(true);
        setRealtimeSnapshotCountdownSeconds(null);
        return;
      }
      setIsTabHidden(false);
      setRealtimeSnapshotCountdownSeconds(Math.max(0, Math.ceil((realtimeSnapshotNextRefreshAtRef.current - Date.now()) / 1000)));
      if (Date.now() < realtimeSnapshotNextRefreshAtRef.current) return;
      scheduleNext();
      if (!realtimeSnapshotRefreshInFlightRef.current) {
        void refreshRealtimeSnapshots();
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [realtimeAutoRefreshEnabled, realtimeSnapshotRefreshInterval, refreshRealtimeSnapshots]);

  useEffect(() => {
    if (!tradeTapeAutoRefreshEnabled) {
      setTradeTapeNextRefreshAt(null);
      setTradeTapeCountdownSeconds(null);
      return undefined;
    }
    const scheduleNext = () => {
      const next = Date.now() + tradeTapeRefreshInterval * 1000;
      tradeTapeNextRefreshAtRef.current = next;
      setTradeTapeNextRefreshAt(next);
      setTradeTapeCountdownSeconds(tradeTapeRefreshInterval);
    };
    scheduleNext();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'hidden') {
        setIsTabHidden(true);
        setTradeTapeCountdownSeconds(null);
        return;
      }
      setIsTabHidden(false);
      setTradeTapeCountdownSeconds(Math.max(0, Math.ceil((tradeTapeNextRefreshAtRef.current - Date.now()) / 1000)));
      if (Date.now() < tradeTapeNextRefreshAtRef.current) return;
      scheduleNext();
      if (!tradeTapeRefreshInFlightRef.current) {
        void refreshTradeTape();
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [tradeTapeAutoRefreshEnabled, tradeTapeRefreshInterval, refreshTradeTape]);

  useEffect(() => {
    const rows = data?.watchlist ?? [];
    const currentWatchlist = logicalWatchlistRef.current;
    if (selectedTicker && currentWatchlist.includes(selectedTicker)) {
      return;
    }
    if (rows.length && !rows.some((item) => item.ticker === selectedTicker)) {
      setSelectedTicker(rows[0].ticker);
    }
  }, [data, logicalWatchlistKey, selectedTicker]);

  const summary = useMemo(() => {
    const rows = data?.watchlist ?? [];
    const up = rows.filter((item) => (item.changePct ?? 0) > 0).length;
    const avgLiquidity = rows.length
      ? Math.round(rows.reduce((sum, item) => sum + (item.liquidity.score ?? 0), 0) / rows.length)
      : 0;
    const foreignNetVolume = sumSsiForeignNetVolume(rows);
    return { count: rows.length, up, avgLiquidity, foreignNetVolume };
  }, [data]);

  const selectedItem = useMemo(
    () => (data?.watchlist ?? []).find((item) => item.ticker === selectedTicker) ?? data?.watchlist?.[0] ?? null,
    [data, selectedTicker],
  );
  const hasCommittedData = Boolean(data);
  const isUpdatingWatchlist = loading && hasCommittedData;

  return (
    <AppPage className="space-y-5">
      <header className="flex flex-col gap-4 border-b border-border/70 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="label-uppercase text-secondary-text">Vietnam market</p>
          <h1 className="mt-2 text-2xl font-semibold text-foreground md:text-3xl">Watchlist Monitor</h1>
          <p className="mt-2 max-w-3xl text-sm text-secondary-text">
            SSI daily OHLCV, price-limit awareness, foreign flow, liquidity, and technical score tracking.
          </p>
          <p className="mt-2 max-w-3xl text-xs text-secondary-text">
            During trading hours, the latest daily candle close may represent the latest traded price. After market close, it represents the final close.
          </p>
          <p className="mt-1 max-w-3xl text-xs text-secondary-text">
            Labels are neutral condition tags only.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => void load(false)} isLoading={loading && !forceLoading} loadingText="Refreshing">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => void load(true)} isLoading={forceLoading} loadingText="Refreshing live">
            <DatabaseZap className="h-4 w-4" />
            Force live refresh
          </Button>
          <Button variant="secondary" onClick={handleRefreshRealtimeData} isLoading={realtimeLoading || tradesLoading} loadingText="Refreshing realtime">
            <Activity className="h-4 w-4" />
            Refresh realtime
          </Button>
        </div>
      </header>

      <DataReadinessStrip
        data={data}
        selectedItem={selectedItem}
        loading={loading}
        realtimeQuotes={realtimeQuotes}
        realtimeLoading={realtimeLoading}
        realtimeTrades={realtimeTrades}
        tradesLoading={tradesLoading}
        tradesError={tradesError}
        marketPhase={marketPhase}
      />

      <IndexContextPanel
        dailyIndex={dailyIndex}
        indexComponents={indexComponents}
      />

      {isUpdatingWatchlist || (hasCommittedData && error) ? (
        <div
          className={cn(
            'flex flex-wrap items-center gap-2 rounded-lg border p-3 text-xs',
            error ? 'border-warning/25 bg-warning/10 text-warning' : 'border-cyan/20 bg-cyan/10 text-cyan',
          )}
          data-testid="watchlist-request-status"
        >
          <Badge variant={error ? 'warning' : 'info'}>{error ? 'Last update failed' : 'Updating...'}</Badge>
          <span className={error ? 'text-warning' : 'text-secondary-text'}>Showing previous data</span>
        </div>
      ) : null}

      <section className="rounded-lg border border-border/70 bg-card p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-foreground">Refresh control</h2>
              <Badge variant={sectionStateVariant(isUpdatingWatchlist ? 'Updating...' : error && !hasCommittedData ? 'Failed' : 'Ready')}>
                {isUpdatingWatchlist ? 'Updating...' : error && !hasCommittedData ? 'Failed' : 'Ready'}
              </Badge>
              <Badge variant={autoRefreshEnabled ? 'success' : 'default'}>
                Auto-refresh {autoRefreshEnabled ? 'ON' : 'OFF'}
              </Badge>
              <Badge variant={realtimeAutoRefreshEnabled ? 'success' : 'default'}>
                Auto-refresh realtime {realtimeAutoRefreshEnabled ? 'ON' : 'OFF'}
              </Badge>
              <Badge variant={tradeTapeAutoRefreshEnabled ? 'success' : 'default'}>
                Auto-refresh trade tape {tradeTapeAutoRefreshEnabled ? 'ON' : 'OFF'}
              </Badge>
              {isTabHidden && (autoRefreshEnabled || realtimeAutoRefreshEnabled || tradeTapeAutoRefreshEnabled) ? <Badge variant="warning">Paused while tab hidden</Badge> : null}
              {(realtimeLoading || tradesLoading) ? <Badge variant="info">Refreshing realtime...</Badge> : null}
            </div>
            <p className="mt-1 text-xs text-secondary-text">
              Auto-refresh uses the normal cached watchlist request. Force live refresh remains manual.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 text-sm text-secondary-text">
              <input
                type="checkbox"
                checked={autoRefreshEnabled}
                onChange={(event) => setAutoRefreshEnabled(event.target.checked)}
                className="h-4 w-4 rounded border-border bg-elevated"
              />
              Auto-refresh
            </label>
            <label className="flex items-center gap-2 text-sm text-secondary-text">
              Interval
              <select
                value={autoRefreshInterval}
                onChange={(event) => setAutoRefreshInterval(Number(event.target.value))}
                className="h-9 rounded-lg border border-border/70 bg-elevated px-3 text-sm text-foreground"
              >
                {AUTO_REFRESH_INTERVALS.map((seconds) => (
                  <option key={seconds} value={seconds}>{seconds}s</option>
                ))}
              </select>
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-secondary-text">
              <input
                type="checkbox"
                checked={realtimeAutoRefreshEnabled}
                onChange={(event) => setRealtimeAutoRefreshEnabled(event.target.checked)}
                className="h-4 w-4 rounded border-border bg-elevated"
              />
              Auto-refresh realtime
            </label>
            <label className="flex items-center gap-2 text-sm text-secondary-text">
              SSI realtime
              <select
                value={realtimeSnapshotRefreshInterval}
                onChange={(event) => setRealtimeSnapshotRefreshInterval(Number(event.target.value))}
                className="h-9 rounded-lg border border-border/70 bg-elevated px-3 text-sm text-foreground"
              >
                {REALTIME_SNAPSHOT_REFRESH_INTERVALS.map((seconds) => (
                  <option key={seconds} value={seconds}>{seconds}s</option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-secondary-text">
              Trade tape
              <select
                value={tradeTapeRefreshInterval}
                onChange={(event) => setTradeTapeRefreshInterval(Number(event.target.value))}
                className="h-9 rounded-lg border border-border/70 bg-elevated px-3 text-sm text-foreground"
              >
                {TRADE_TAPE_REFRESH_INTERVALS.map((seconds) => (
                  <option key={seconds} value={seconds}>{seconds}s</option>
                ))}
              </select>
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-secondary-text">
              <input
                type="checkbox"
                checked={tradeTapeAutoRefreshEnabled}
                onChange={(event) => setTradeTapeAutoRefreshEnabled(event.target.checked)}
                className="h-4 w-4 rounded border-border bg-elevated"
              />
              Auto-refresh trade tape
            </label>
          </div>
        </div>
        <dl className="mt-4 grid gap-3 text-sm md:grid-cols-6">
          <div className="rounded-lg bg-elevated/50 p-3">
            <dt className="text-xs text-secondary-text">Selected interval</dt>
            <dd className="mt-1 font-medium text-foreground">{autoRefreshInterval}s</dd>
          </div>
          <div className="rounded-lg bg-elevated/50 p-3">
            <dt className="text-xs text-secondary-text">Last refreshed at</dt>
            <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(lastRefreshAt)}</dd>
            <dd className="mt-1 text-xs text-secondary-text">{formatRelativeAge(lastRefreshAt)}</dd>
          </div>
          <div className="rounded-lg bg-elevated/50 p-3">
            <dt className="text-xs text-secondary-text">Next refresh</dt>
            <dd className="mt-1 font-medium text-foreground">
              {autoRefreshEnabled && !isTabHidden ? formatCountdown(countdownSeconds) : 'Paused'}
            </dd>
            <dd className="mt-1 text-xs text-secondary-text">
              {autoRefreshEnabled && !isTabHidden && nextRefreshAt ? formatVietnamTime(nextRefreshAt) : '-'}
            </dd>
          </div>
          <div className="rounded-lg bg-elevated/50 p-3">
            <dt className="text-xs text-secondary-text">Last refresh type</dt>
            <dd className="mt-1 font-medium text-foreground">{lastRefreshKind}</dd>
          </div>
          <div className="rounded-lg bg-elevated/50 p-3">
            <dt className="text-xs text-secondary-text">Next SSI realtime</dt>
            <dd className="mt-1 font-medium text-foreground">
              {realtimeAutoRefreshEnabled && !isTabHidden ? formatCountdown(realtimeSnapshotCountdownSeconds) : 'Paused'}
            </dd>
            <dd className="mt-1 text-xs text-secondary-text">
              {realtimeAutoRefreshEnabled && !isTabHidden && realtimeSnapshotNextRefreshAt ? formatVietnamTime(realtimeSnapshotNextRefreshAt) : '-'}
            </dd>
          </div>
          <div className="rounded-lg bg-elevated/50 p-3">
            <dt className="text-xs text-secondary-text">Next trade tape</dt>
            <dd className="mt-1 font-medium text-foreground">
              {tradeTapeAutoRefreshEnabled && !isTabHidden ? formatCountdown(tradeTapeCountdownSeconds) : 'Paused'}
            </dd>
            <dd className="mt-1 text-xs text-secondary-text">
              {tradeTapeAutoRefreshEnabled && !isTabHidden && tradeTapeNextRefreshAt ? formatVietnamTime(tradeTapeNextRefreshAt) : '-'}
            </dd>
          </div>
        </dl>
        <div className="mt-3 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
          Daily close currently uses the configured daily OHLCV candle close when no reliable realtime matched quote field is present.
        </div>
      </section>

      <section className="rounded-lg border border-border/70 bg-card p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-foreground">Edit Watchlist</h2>
              <Badge variant={sectionStateVariant(isUpdatingWatchlist ? 'Updating...' : 'Ready')}>
                {isUpdatingWatchlist ? 'Updating...' : 'Ready'}
              </Badge>
              <Badge variant="default">{watchlist.length}/{VIETNAM_WATCHLIST_MAX_SIZE}</Badge>
            </div>
            <p className="mt-1 text-xs text-secondary-text">
              Saved locally in this browser. Changes refresh through the normal cached watchlist request.
            </p>
            <p className="mt-1 text-xs text-secondary-text">
              Preset groups are scan buckets only.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={handleResetWatchlist}>
            <RotateCcw className="h-4 w-4" />
            Reset to default
          </Button>
        </div>
        <div className="mt-4">
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Preset groups">
            <button
              type="button"
              aria-pressed={activePresetId === 'custom'}
              onClick={handleCustomPresetSelect}
              className={cn(
                'h-9 rounded-lg border px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/25',
                activePresetId === 'custom'
                  ? 'border-cyan/50 bg-cyan/15 text-cyan'
                  : 'border-border/70 bg-elevated text-secondary-text hover:bg-hover hover:text-foreground',
              )}
            >
              Custom
            </button>
            {VIETNAM_DASHBOARD_PRESETS.map((preset) => {
              const isActive = activePresetId === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => handlePresetSelect(preset.id)}
                  className={cn(
                    'h-9 rounded-lg border px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/25',
                    isActive
                      ? 'border-cyan/50 bg-cyan/15 text-cyan'
                      : 'border-border/70 bg-elevated text-secondary-text hover:bg-hover hover:text-foreground',
                  )}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-secondary-text">
            Selecting a preset replaces the active list and refreshes normally through the cached watchlist endpoint.
          </p>
        </div>
        <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-3">
          <label className="flex flex-col text-sm font-medium text-foreground">
            Custom watchlist
            <textarea
              value={customWatchlistInput}
              onChange={(event) => {
                setCustomWatchlistInput(event.target.value);
                if (watchlistError) setWatchlistError(null);
              }}
              placeholder="FPT, VPB, ACB"
              rows={3}
              className="mt-2 min-h-20 rounded-lg border border-border/70 bg-card px-3 py-2 text-sm font-normal uppercase text-foreground outline-none transition-colors placeholder:text-muted focus:border-cyan/50 focus:ring-2 focus:ring-cyan/15"
            />
          </label>
          <p className="mt-2 text-xs text-secondary-text">Saved locally in this browser.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={handleApplyCustom}>
              Apply custom
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={handleSaveCustom}>
              Save custom
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={handleClearCustom}>
              Clear custom
            </Button>
          </div>
          {watchlistError ? (
            <div className="mt-3 flex gap-2 rounded-lg border border-warning/20 bg-warning/10 p-3 text-xs text-warning">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{watchlistError}</span>
            </div>
          ) : null}
          {customNotice ? (
            <div className="mt-3 rounded-lg border border-border/60 bg-card/70 p-3 text-xs text-secondary-text">
              {customNotice}
            </div>
          ) : null}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {watchlist.map((ticker) => (
            <span
              key={ticker}
              className="inline-flex h-9 items-center rounded-lg border border-border/70 bg-elevated px-3 text-sm font-medium text-foreground"
            >
              {ticker}
            </span>
          ))}
        </div>
        <p className="mt-3 text-xs text-secondary-text">
          Custom symbols use uppercase letters and numbers, 2 to 10 characters. Separators: comma, whitespace, semicolon, or newline.
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-border/70 bg-card p-4">
          <Activity className="mb-3 h-5 w-5 text-cyan" />
          <p className="text-xs text-secondary-text">Tickers</p>
          <p className="text-2xl font-semibold text-foreground">{summary.count}</p>
        </div>
        <div className="rounded-lg border border-border/70 bg-card p-4">
          <ArrowUpRight className="mb-3 h-5 w-5 text-success" />
          <p className="text-xs text-secondary-text">Advancers</p>
          <p className="text-2xl font-semibold text-foreground">{summary.up}</p>
        </div>
        <div className="rounded-lg border border-border/70 bg-card p-4">
          <Banknote className="mb-3 h-5 w-5 text-warning" />
          <p className="text-xs text-secondary-text">Avg liquidity</p>
          <p className="text-2xl font-semibold text-foreground">{summary.avgLiquidity}/100</p>
        </div>
        <div className="rounded-lg border border-border/70 bg-card p-4" data-testid="foreign-net-volume-summary-card">
          <ShieldAlert className="mb-3 h-5 w-5 text-purple" />
          <p className="text-xs text-secondary-text">Foreign net volume</p>
          <p className={cn('text-2xl font-semibold', signalTone(summary.foreignNetVolume))}>{formatNumber(summary.foreignNetVolume)}</p>
          <p className="mt-1 text-xs text-secondary-text">SSI DailyStockPrice · shares</p>
        </div>
      </section>

      {error && !hasCommittedData ? (
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm text-danger">{error}</div>
      ) : null}

      {loading && !data ? (
        <Loading label="Loading Vietnam watchlist..." />
      ) : (
        <>
          <WatchlistScanSummary
            items={data?.watchlist ?? []}
            realtimeQuotes={realtimeQuotes}
            marketPhase={marketPhase}
          />
          <IndicatorTable
            items={data?.watchlist ?? []}
            realtimeQuotes={realtimeQuotes}
            realtimeLoading={realtimeLoading}
            realtimeError={realtimeError}
            isUpdating={isUpdatingWatchlist}
            hasRequestFailure={Boolean(error)}
            selectedTicker={selectedItem?.ticker}
            marketPhase={marketPhase}
            onSelect={setSelectedTicker}
          />
          <SelectedTickerHeader
            item={selectedItem}
            realtimeQuote={selectedItem ? realtimeQuotes[selectedItem.ticker] : null}
            marketPhase={marketPhase}
          />
          <StockDetailView
            item={selectedItem}
            fixtureMode={data?.fixtureMode}
            realtimeQuote={selectedItem ? realtimeQuotes[selectedItem.ticker] : null}
            realtimeTrades={realtimeTrades}
            corporateActions={corporateActions}
            corporateActionsLoading={corporateActionsLoading}
            corporateActionsError={corporateActionsError}
            tradesLoading={tradesLoading}
            tradesError={tradesError}
            marketPhase={marketPhase}
          />
          <section className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {(data?.watchlist ?? []).map((item) => (
              <WatchCard key={item.ticker} item={item} realtimeQuote={realtimeQuotes[item.ticker]} marketPhase={marketPhase} />
            ))}
          </section>
          <DataStatusPanel
            data={data}
            selectedItem={selectedItem}
            dailyIndex={dailyIndex}
            indexList={indexList}
            indexComponents={indexComponents}
            indexCoverageError={indexCoverageError}
            realtimeQuotes={realtimeQuotes}
            realtimeTrades={realtimeTrades}
            watchlist={watchlist}
            realtimeError={realtimeError}
            tradesError={tradesError}
            lastRealtimeSnapshotRefreshAt={lastRealtimeSnapshotRefreshAt}
            lastTradeTapeRefreshAt={lastTradeTapeRefreshAt}
            lastRealtimeErrorAt={lastRealtimeErrorAt}
            realtimeAutoRefreshEnabled={realtimeAutoRefreshEnabled}
            tradeTapeAutoRefreshEnabled={tradeTapeAutoRefreshEnabled}
            realtimeSnapshotRefreshInterval={realtimeSnapshotRefreshInterval}
            tradeTapeRefreshInterval={tradeTapeRefreshInterval}
            marketPhase={marketPhase}
            observability={observability}
          />
        </>
      )}

      {data ? (
        <section className="rounded-lg border border-border/70 bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-foreground">Dashboard formulas</h2>
            <div className="flex flex-wrap gap-2">
              <Badge variant="info">{data.ruleMetadata?.ruleSetName ?? 'Vietnam neutral technical labels'}</Badge>
              <Badge variant="default">{data.ruleMetadata?.ruleSetVersion ?? 'v1'}</Badge>
              <Badge variant={data.ruleMetadata?.noRecommendation ? 'success' : 'warning'}>Neutral tags only</Badge>
            </div>
          </div>
          <dl className="mt-3 grid gap-2 text-sm md:grid-cols-2">
            {Object.entries(data.formulas).map(([key, formula]) => (
              <div key={key} className="rounded-lg bg-elevated/50 p-3">
              <dt className="font-medium text-foreground">{formulaDisplayLabel(key)}</dt>
                <dd className="mt-1 text-secondary-text">{neutralFormulaText(formula)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </AppPage>
  );
};

export default VietnamDashboardPage;
