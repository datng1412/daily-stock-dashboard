import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, ArrowDown, ArrowDownRight, ArrowUp, ArrowUpRight, Banknote, DatabaseZap, Plus, RefreshCw, RotateCcw, ShieldAlert, X } from 'lucide-react';
import { stocksApi, type VietnamWatchItem, type VietnamWatchlistResponse } from '../api/stocks';
import { AppPage, Badge, Button, Input, Loading } from '../components/common';
import { cn } from '../utils/cn';
import { buildVietnamConditionSummary, VIETNAM_CONDITION_SUMMARY_SUBTITLE } from '../utils/vietnamConditionSummary';
import { formatRelativeAge, formatVietnamDateTime, formatVietnamTime, parseMozyTimestamp } from '../utils/vietnamTime';
import {
  VIETNAM_WATCHLIST_MAX_SIZE,
  VIETNAM_WATCHLIST_PRESETS,
  getVietnamPresetTickers,
  moveVietnamTicker,
  normalizeVietnamWatchlist,
  readVietnamWatchlist,
  validateVietnamTicker,
  type VietnamWatchlistPresetId,
  writeVietnamWatchlist,
} from '../utils/vietnamWatchlist';

const DEFAULT_TICKERS = ['FPT', 'VPB', 'MSB', 'SCS', 'ACV', 'ACB'];
const AUTO_REFRESH_INTERVALS = [60, 180, 300];
const DEFAULT_WATCHLIST = normalizeVietnamWatchlist(DEFAULT_TICKERS) ?? DEFAULT_TICKERS;
const DETAIL_NEWS_LIMIT = 8;

const formatNumber = (value?: number | null, maximumFractionDigits = 0) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits }).format(value);
};

const formatPrice = (value?: number | null) => formatNumber(value, 2);

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
  if (source === 'ohlcv') return 'warning';
  return 'default';
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

const intradayVariant = (label?: string | null) => {
  if (['Intraday up', 'Intraday flat', 'Intraday volume expansion'].includes(label ?? '')) return 'info';
  if (['Intraday down', 'Intraday wide range', 'Intraday data limited', 'Not realtime quote'].includes(label ?? '')) return 'warning';
  return 'default';
};

const cacheVariant = (status?: string | null) => {
  if (status === 'hit') return 'success';
  if (status === 'miss' || status === 'refresh') return 'info';
  if (status === 'stale') return 'warning';
  if (status === 'error') return 'danger';
  return 'default';
};

const cacheLabel = (status?: string | null) => status ?? 'missing';

const rawDateLabel = (value?: string | number | null) => (value === null || value === undefined || value === '' ? '—' : String(value));

const compactLabels = (labels?: string[], max = 4) => (labels ?? ['Watch']).slice(0, max);

const hasEncodingArtifacts = (value?: string | null) => Boolean(value && /(?:Ã|Â|â€|�)/.test(value));

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

const cacheFreshness = (item: VietnamWatchItem) => {
  if (Object.values(item.cacheStatus ?? {}).includes('stale')) return { label: 'stale', variant: 'warning' as const };
  if (Object.values(item.cacheStatus ?? {}).includes('error')) return { label: 'error', variant: 'danger' as const };
  if (Object.values(item.cacheStatus ?? {}).includes('miss') || Object.values(item.cacheStatus ?? {}).includes('refresh')) {
    return { label: 'live refreshed', variant: 'info' as const };
  }
  return { label: 'cached', variant: 'success' as const };
};

const importantWarnings = (item: VietnamWatchItem) =>
  (item.warnings ?? []).filter((warning) =>
    [
      'Quote does not provide a reliable latest price field',
      'latest price uses OHLCV close',
      'Foreign net date does not match',
      'Final close status is unknown',
      'Adjusted/unadjusted price status is unknown',
      'Intraday 1H candle data is not a realtime matched quote',
      'stale cached data',
    ].some((needle) => warning.includes(needle)),
  );

const WatchCard: React.FC<{ item: VietnamWatchItem }> = ({ item }) => {
  const positive = (item.changePct ?? 0) >= 0;
  const TrendIcon = positive ? ArrowUpRight : ArrowDownRight;
  const displayWarnings = importantWarnings(item);
  const freshness = cacheFreshness(item);
  const lastFetched = latestFetchedValue(item);

  return (
    <article className="rounded-lg border border-border/70 bg-card p-4 shadow-soft-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-foreground">{item.ticker}</h2>
            <Badge variant="info">{item.exchange ?? 'VN'}</Badge>
            <Badge variant="default">{item.marketIndex ?? 'VNINDEX.VN'}</Badge>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {compactLabels(item.statusLabels, 3).map((label) => (
              <Badge key={label} variant={statusVariant(label)}>{label}</Badge>
            ))}
            {(item.statusLabels?.length ?? 0) > 3 ? <Badge variant="default">+{(item.statusLabels?.length ?? 0) - 3}</Badge> : null}
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
          <p className="text-xs text-secondary-text">Latest price (VND)</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <p className="text-lg font-semibold text-foreground">{formatPrice(item.latestPrice ?? item.close)}</p>
            <Badge variant={priceSourceVariant(item.latestPriceSource)}>{(item.latestPriceSource ?? 'unknown').toUpperCase()}</Badge>
          </div>
          <p className="text-xs text-secondary-text">OHLCV close {formatPrice(item.ohlcvClose ?? item.close)}</p>
        </div>
        <div>
          <p className="text-xs text-secondary-text">Volume (shares)</p>
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
        <div>
          <p className="text-xs text-secondary-text">Volume ratio</p>
          <p className="font-semibold text-foreground">{formatNumber(item.indicators.volumeRatio, 2)}</p>
        </div>
        <div>
          <p className="text-xs text-secondary-text">Cache</p>
          <Badge variant={freshness.variant}>{freshness.label}</Badge>
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
            {item.finalCloseStatus ?? 'unknown'}
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
          <span className="text-secondary-text">Cache</span>
          <span className="text-foreground">{formatVietnamTime(lastFetched)} ({formatRelativeAge(lastFetched)})</span>
        </div>
      </div>

      {item.intradayPulse ? (
        <div className="mt-3 rounded-lg border border-border/60 bg-elevated/40 p-3 text-xs">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-foreground">Intraday Pulse {item.intradayTimeframe?.toUpperCase() ?? '1H'}</span>
            <div className="flex flex-wrap gap-1">
              {(item.intradayLabels ?? []).slice(0, 2).map((label) => (
                <Badge key={`${item.ticker}-${label}`} variant={intradayVariant(label)}>{label}</Badge>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-secondary-text">
            <span>1H close {formatPrice(item.intradayPulse.latest1hClose)}</span>
            <span className={signalTone(item.intradayPulse.latest1hChange)}>Change {formatPrice(item.intradayPulse.latest1hChange)} ({formatNumber(item.intradayPulse.latest1hChangePercent, 2)}%)</span>
            <span>Time {formatVietnamTime(item.intradayCandles?.at(-1)?.dateTime ?? item.intradayCandles?.at(-1)?.timestamp)}</span>
            <span>Range {formatNumber(item.intradayPulse.rangePercent, 2)}%</span>
            <span>Volume {formatNumber(item.intradayPulse.latest1hVolume)}</span>
          </div>
        </div>
      ) : null}

      {displayWarnings.length > 0 ? (
        <div className="mt-3 space-y-2">
          {displayWarnings.map((warning) => (
            <div key={warning} className="flex gap-2 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      ) : null}
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

      {item.news.length > 0 ? (
        <div className="mt-3 border-t border-border/60 pt-3">
          <p className="mb-2 text-xs font-medium text-secondary-text">Latest news</p>
          {item.news.slice(0, 2).map((news) => (
            <a
              key={`${news.title}-${news.url}`}
              href={news.url || '#'}
              target="_blank"
              rel="noreferrer"
              className="block truncate text-sm text-cyan hover:underline"
            >
              {news.title}
            </a>
          ))}
        </div>
      ) : null}
    </article>
  );
};

const CacheMetadataPanel: React.FC<{
  data: VietnamWatchlistResponse;
  items: VietnamWatchItem[];
}> = ({ data, items }) => {
  const metadata = data.cacheMetadata;
  const fetchedTimes = items.flatMap((item) => [
    item.cacheLastFetchedAt?.ohlcv,
    item.cacheLastFetchedAt?.quote,
    item.cacheLastFetchedAt?.intradayOhlcv,
    item.cacheLastFetchedAt?.news,
  ]).filter((value): value is string => Boolean(value));
  const refreshTimes = items.flatMap((item) => [
    item.cacheNextRefreshAt?.ohlcv,
    item.cacheNextRefreshAt?.quote,
    item.cacheNextRefreshAt?.intradayOhlcv,
    item.cacheNextRefreshAt?.news,
  ]).filter((value): value is string => Boolean(value));
  const latestFetched = fetchedTimes.sort()[fetchedTimes.length - 1];
  const nextRefresh = refreshTimes.sort()[0];

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <DatabaseZap className="h-5 w-5 text-cyan" />
          <h2 className="text-base font-semibold text-foreground">Cache status</h2>
        </div>
        <Badge variant={data.fixtureMode ? 'warning' : 'success'}>
          {data.fixtureMode ? 'Mozyfin fixture' : 'Mozyfin live'}
        </Badge>
      </div>
      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-5">
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Cache hits</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(metadata.cacheHitCount)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Cache misses</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(metadata.cacheMissCount)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Stale used</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(metadata.staleCacheUsedCount)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Last fetched</dt>
          <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(latestFetched)}</dd>
          <dd className="mt-1 text-xs text-secondary-text">{formatRelativeAge(latestFetched)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Next refresh</dt>
          <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(nextRefresh)}</dd>
        </div>
      </dl>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <Badge variant="default">OHLCV TTL {formatNumber(metadata.cacheTtlSeconds.ohlcv)}s</Badge>
        <Badge variant="default">Quote TTL {formatNumber(metadata.cacheTtlSeconds.quote)}s</Badge>
        <Badge variant="default">Intraday 1H TTL {formatNumber(metadata.cacheTtlSeconds.intradayOhlcv)}s</Badge>
        <Badge variant="default">News TTL {formatNumber(metadata.cacheTtlSeconds.news)}s</Badge>
      </div>
      <details className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-3">
        <summary className="cursor-pointer text-sm font-medium text-foreground">Advanced cache internals</summary>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="border-b border-border/70 text-xs uppercase text-secondary-text">
              <tr>
                <th className="py-2 pr-3">Ticker</th>
                <th className="px-3 py-2">OHLCV</th>
                <th className="px-3 py-2">Quote</th>
                <th className="px-3 py-2">Intraday 1H</th>
                <th className="px-3 py-2">News</th>
                <th className="px-3 py-2">Last fetched</th>
                <th className="px-3 py-2">Next refresh</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={`cache-${item.ticker}`} className="border-b border-border/40 text-secondary-text">
                  <td className="py-3 pr-3 font-semibold text-foreground">{item.ticker}</td>
                  <td className="px-3 py-3">
                    <Badge variant={cacheVariant(item.cacheStatus.ohlcvCache)}>{cacheLabel(item.cacheStatus.ohlcvCache)}</Badge>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={cacheVariant(item.cacheStatus.quoteCache)}>{cacheLabel(item.cacheStatus.quoteCache)}</Badge>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={cacheVariant(item.cacheStatus.intradayCache)}>{cacheLabel(item.cacheStatus.intradayCache)}</Badge>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={cacheVariant(item.cacheStatus.newsCache)}>{cacheLabel(item.cacheStatus.newsCache)}</Badge>
                  </td>
                  <td className="px-3 py-3">
                    <span className="block">OHLCV {formatVietnamTime(item.cacheLastFetchedAt?.ohlcv)} ({formatRelativeAge(item.cacheLastFetchedAt?.ohlcv)})</span>
                    <span className="block">Quote {formatVietnamTime(item.cacheLastFetchedAt?.quote)} ({formatRelativeAge(item.cacheLastFetchedAt?.quote)})</span>
                    <span className="block">1H {formatVietnamTime(item.cacheLastFetchedAt?.intradayOhlcv)} ({formatRelativeAge(item.cacheLastFetchedAt?.intradayOhlcv)})</span>
                    <span className="block">News {formatVietnamTime(item.cacheLastFetchedAt?.news)} ({formatRelativeAge(item.cacheLastFetchedAt?.news)})</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className="block">OHLCV {formatVietnamTime(item.cacheNextRefreshAt?.ohlcv)}</span>
                    <span className="block">Quote {formatVietnamTime(item.cacheNextRefreshAt?.quote)}</span>
                    <span className="block">1H {formatVietnamTime(item.cacheNextRefreshAt?.intradayOhlcv)}</span>
                    <span className="block">News {formatVietnamTime(item.cacheNextRefreshAt?.news)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
};

const IndicatorTable: React.FC<{
  items: VietnamWatchItem[];
  selectedTicker?: string | null;
  onSelect: (ticker: string) => void;
}> = ({ items, selectedTicker, onSelect }) => (
  <section className="rounded-lg border border-border/70 bg-card p-4">
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-base font-semibold text-foreground">Indicator table</h2>
      <span className="text-xs text-secondary-text">Neutral status labels only</span>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1120px] text-left text-sm">
        <thead className="border-b border-border/70 text-xs uppercase text-secondary-text">
          <tr>
            <th className="py-2 pr-3">Ticker</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2 text-right">Latest price</th>
            <th className="px-3 py-2">Source</th>
            <th className="px-3 py-2">Price date</th>
            <th className="px-3 py-2 text-right">1H change</th>
            <th className="px-3 py-2">Final close</th>
            <th className="px-3 py-2 text-right">MA20</th>
            <th className="px-3 py-2 text-right">RSI14 Wilder/RMA</th>
            <th className="px-3 py-2 text-right">Vol ratio</th>
            <th className="px-3 py-2">Warnings</th>
            <th className="px-3 py-2">Cache</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.ticker}
              className={cn(
                'cursor-pointer border-b border-border/40 text-secondary-text hover:bg-elevated/40',
                selectedTicker === item.ticker && 'bg-elevated/60 text-foreground',
              )}
              onClick={() => onSelect(item.ticker)}
            >
              <td className="py-3 pr-3 font-semibold text-foreground">{item.ticker}</td>
              <td className="px-3 py-3">
                <div className="flex flex-wrap gap-1">
                  {compactLabels(item.statusLabels, 3).map((label) => (
                    <Badge key={label} variant={statusVariant(label)}>{label}</Badge>
                  ))}
                  {(item.statusLabels?.length ?? 0) > 3 ? <Badge variant="default">+{(item.statusLabels?.length ?? 0) - 3}</Badge> : null}
                </div>
              </td>
              <td className="px-3 py-3 text-right">{formatPrice(item.latestPrice ?? item.close)}</td>
              <td className="px-3 py-3">
                <Badge variant={priceSourceVariant(item.latestPriceSource)}>{(item.latestPriceSource ?? 'unknown').toUpperCase()}</Badge>
              </td>
              <td className="px-3 py-3">{item.latestPriceDate ?? item.priceDate ?? '-'}</td>
              <td className={cn('px-3 py-3 text-right', signalTone(item.intradayPulse?.latest1hChange))}>
                {formatNumber(item.intradayPulse?.latest1hChangePercent, 2)}%
              </td>
              <td className="px-3 py-3">
                <Badge variant={item.finalCloseStatus === 'final' ? 'success' : item.finalCloseStatus === 'not_final' ? 'warning' : 'default'}>
                  {item.finalCloseStatus ?? 'unknown'}
                </Badge>
              </td>
              <td className="px-3 py-3 text-right">{formatPrice(item.indicators.ma20)}</td>
              <td className="px-3 py-3 text-right">{formatNumber(item.indicators.rsi14Wilder ?? item.indicators.rsi14, 2)}</td>
              <td className="px-3 py-3 text-right">{formatNumber(item.indicators.volumeRatio, 2)}</td>
              <td className="px-3 py-3">
                <Badge variant={importantWarnings(item).length ? 'warning' : 'success'}>{importantWarnings(item).length}</Badge>
              </td>
              <td className="px-3 py-3">
                <Badge variant={cacheFreshness(item).variant}>{cacheFreshness(item).label}</Badge>
                <div className="mt-1 text-xs text-secondary-text">{formatRelativeAge(latestFetchedValue(item))}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </section>
);

const StockDetailView: React.FC<{ item?: VietnamWatchItem | null; fixtureMode?: boolean }> = ({ item, fixtureMode = false }) => {
  if (!item) return null;
  const indicators = item.indicators;
  const latestIntradayCandle = item.intradayCandles?.at(-1);
  const displayWarnings = importantWarnings(item);
  const conditionSummary = buildVietnamConditionSummary({ item, fixtureMode });
  return (
    <section className="rounded-lg border border-border/70 bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="label-uppercase text-secondary-text">Stock detail</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">{item.ticker}</h2>
        </div>
        <div className="flex flex-wrap gap-1">
          {(item.statusLabels ?? ['Watch']).map((label) => (
            <Badge key={label} variant={statusVariant(label)}>{label}</Badge>
          ))}
        </div>
      </div>
      <div className="mt-3 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
        Labels are neutral condition tags, not trading recommendations.
      </div>
      <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4">
        <h3 className="text-sm font-semibold text-foreground">Condition Summary</h3>
        <p className="mt-1 text-xs text-secondary-text">{VIETNAM_CONDITION_SUMMARY_SUBTITLE}</p>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-secondary-text">
          {conditionSummary.map((bullet) => (
            <li key={`${item.ticker}-condition-${bullet}`}>{bullet}</li>
          ))}
        </ul>
      </div>
      {displayWarnings.length > 0 ? (
        <div className="mt-3 grid gap-2">
          {displayWarnings.map((warning) => (
            <div key={`detail-warning-${warning}`} className="flex gap-2 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      ) : null}
      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-4">
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Bollinger 20,2 (VND)</dt>
          <dd className="mt-1 font-medium text-foreground">
            {formatPrice(indicators.bollinger?.lower)} / {formatPrice(indicators.bollinger?.middle)} / {formatPrice(indicators.bollinger?.upper)}
          </dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">20D average volume (shares)</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(indicators.avgVolume20d)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Distance to 20D high</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(indicators.distanceTo20dHighPct, 2)}%</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Distance to 20D low</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(indicators.distanceTo20dLowPct, 2)}%</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">MA20 / MA50 (VND)</dt>
          <dd className="mt-1 font-medium text-foreground">{formatPrice(indicators.ma20)} / {formatPrice(indicators.ma50)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">RSI14 Wilder/RMA</dt>
          <dd className="mt-1 font-medium text-foreground">{formatNumber(indicators.rsi14Wilder ?? indicators.rsi14, 2)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Latest price / OHLCV close (VND)</dt>
          <dd className="mt-1 font-medium text-foreground">{formatPrice(item.latestPrice ?? item.close)} / {formatPrice(item.ohlcvClose ?? item.close)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Latest price source</dt>
          <dd className="mt-1 flex flex-wrap gap-1">
            <Badge variant={priceSourceVariant(item.latestPriceSource)}>{item.latestPriceSource ?? 'unknown'}</Badge>
          </dd>
          <dd className="mt-2 text-xs text-secondary-text">
            {item.latestPriceSource === 'ohlcv'
              ? 'Mozyfin quote has no reliable latest matched price, so daily OHLCV close is used.'
              : 'Latest price comes from quote data when a reliable field is present.'}
          </dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Price date / final close</dt>
          <dd className="mt-1 font-medium text-foreground">{item.latestPriceDate ?? item.priceDate ?? '-'} / {item.finalCloseStatus ?? 'unknown'}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Last fetched</dt>
          <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(latestFetchedValue(item))}</dd>
          <dd className="mt-1 text-xs text-secondary-text">{formatRelativeAge(latestFetchedValue(item))}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Foreign net 5D ({item.foreignNetUnit ?? 'unknown'})</dt>
          <dd className={cn('mt-1 font-medium', signalTone(indicators.foreignNet5d))}>{formatNumber(indicators.foreignNet5d)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Foreign net 20D ({item.foreignNetUnit ?? 'unknown'})</dt>
          <dd className={cn('mt-1 font-medium', signalTone(indicators.foreignNet20d))}>{formatNumber(indicators.foreignNet20d)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">OHLCV / foreign dates</dt>
          <dd className="mt-1 font-medium text-foreground">{item.ohlcvDate ?? '-'} / {item.foreignNetDate ?? '-'}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Foreign date match</dt>
          <dd className="mt-1">
            <Badge variant={dateMatchVariant(item.foreignDateMatch)}>{item.foreignDateMatch ?? 'unknown'}</Badge>
          </dd>
        </div>
      </dl>
      <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Intraday Pulse</h3>
            <p className="mt-1 text-xs text-secondary-text">
              {item.intradaySource ?? 'Mozyfin OHLCV'} {item.intradayTimeframe?.toUpperCase() ?? '1H'} candles, separate from daily latest price. Latest candle {formatVietnamDateTime(latestIntradayCandle?.dateTime ?? latestIntradayCandle?.timestamp)}.
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            <Badge variant="default">{item.intradayTimeframe?.toUpperCase() ?? '1H'}</Badge>
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
        <dl className="mt-3 grid gap-3 text-sm md:grid-cols-4">
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Latest 1H close (VND)</dt>
            <dd className="mt-1 font-medium text-foreground">{formatPrice(item.intradayPulse?.latest1hClose)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">1H change</dt>
            <dd className={cn('mt-1 font-medium', signalTone(item.intradayPulse?.latest1hChange))}>
              {formatPrice(item.intradayPulse?.latest1hChange)} / {formatNumber(item.intradayPulse?.latest1hChangePercent, 2)}%
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">1H high / low / range</dt>
            <dd className="mt-1 font-medium text-foreground">
              {formatPrice(item.intradayPulse?.latest1hHigh)} / {formatPrice(item.intradayPulse?.latest1hLow)} / {formatNumber(item.intradayPulse?.rangePercent, 2)}%
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">1H volume (shares)</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(item.intradayPulse?.latest1hVolume)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Session high / low from 1H</dt>
            <dd className="mt-1 font-medium text-foreground">
              {formatPrice(item.intradayPulse?.sessionHighFrom1h)} / {formatPrice(item.intradayPulse?.sessionLowFrom1h)}
            </dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Cumulative 1H volume</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(item.intradayPulse?.cumulative1hVolume)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Volume vs avg 1H</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(item.intradayPulse?.volumeVsAvg1h, 2)}</dd>
          </div>
          <div className="rounded-lg bg-card/60 p-3">
            <dt className="text-xs text-secondary-text">Candles loaded</dt>
            <dd className="mt-1 font-medium text-foreground">{formatNumber(item.intradayCandles?.length ?? 0)}</dd>
          </div>
        </dl>
        <div className="mt-3 flex flex-wrap gap-1">
          {(item.intradayLabels ?? []).map((label) => (
            <Badge key={`${item.ticker}-detail-${label}`} variant={intradayVariant(label)}>{label}</Badge>
          ))}
        </div>
        {item.intradayDetails?.length ? (
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
      </div>
      {item.statusDetails?.length ? (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-foreground">Label reasons</h3>
          <div className="mt-2 grid gap-2">
            {item.statusDetails.map((detail) => (
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
      <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-foreground">Latest news</h3>
          <Badge variant="default">{Math.min(item.news.length, DETAIL_NEWS_LIMIT)} shown</Badge>
        </div>
        {item.news.length ? (
          <div className="mt-3 grid gap-3">
            {item.news.slice(0, DETAIL_NEWS_LIMIT).map((news, index) => {
              const summaryHasArtifacts = hasEncodingArtifacts(news.summary);
              const titleHasArtifacts = hasEncodingArtifacts(news.title);
              return (
                <article key={`${item.ticker}-detail-news-${news.url ?? news.title ?? index}`} className="rounded-lg border border-border/50 bg-card/50 p-3">
                  <a
                    href={news.url || '#'}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-cyan hover:underline"
                  >
                    {news.title || 'Untitled news'}
                  </a>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-secondary-text">
                    {news.source ? <span>{news.source}</span> : null}
                    {news.publishedAt ? <span>{formatVietnamDateTime(news.publishedAt)}</span> : null}
                  </div>
                  {news.summary && !summaryHasArtifacts ? (
                    <p className="mt-2 line-clamp-2 text-sm text-secondary-text">{news.summary}</p>
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
          <p className="mt-3 text-sm text-secondary-text">No recent news returned for this ticker.</p>
        )}
      </div>
      <details className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
        <summary className="cursor-pointer font-medium text-foreground">Advanced / Raw Data</summary>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
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
        </div>
      </details>
    </section>
  );
};

const VietnamDashboardPage: React.FC = () => {
  const initialWatchlist = useMemo(() => readVietnamWatchlist(DEFAULT_WATCHLIST), []);
  const [watchlist, setWatchlist] = useState<string[]>(initialWatchlist.tickers);
  const [activePresetId, setActivePresetId] = useState<VietnamWatchlistPresetId>('my');
  const [watchlistInput, setWatchlistInput] = useState('');
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [storageWarning, setStorageWarning] = useState<string | null>(
    initialWatchlist.usedFallback ? 'Saved watchlist was invalid and default tickers were restored.' : null,
  );
  const [data, setData] = useState<VietnamWatchlistResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [forceLoading, setForceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(initialWatchlist.tickers[0] ?? DEFAULT_WATCHLIST[0]);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(180);
  const [lastRefreshKind, setLastRefreshKind] = useState<'manual' | 'auto' | 'force live'>('manual');
  const [lastRefreshAt, setLastRefreshAt] = useState<string | null>(null);
  const [nextRefreshAt, setNextRefreshAt] = useState<number | null>(null);
  const [countdownSeconds, setCountdownSeconds] = useState<number | null>(null);
  const [isTabHidden, setIsTabHidden] = useState(() => typeof document !== 'undefined' && document.visibilityState === 'hidden');
  const requestIdRef = useRef(0);
  const nextRefreshAtRef = useRef(0);
  const nextWatchlistLoadRef = useRef<{ tickers: string[]; forceRefresh: boolean; refreshKind: 'manual' | 'auto' | 'force live' } | null>(null);

  const persistWatchlist = useCallback((nextTickers: string[]) => {
    try {
      writeVietnamWatchlist(nextTickers);
      setStorageWarning(null);
    } catch {
      setStorageWarning('Watchlist changed for this session, but localStorage could not be updated.');
    }
  }, []);

  const applyWatchlist = useCallback((nextTickers: string[], presetId: VietnamWatchlistPresetId = 'my', nextSelectedTicker?: string | null) => {
    setWatchlist(nextTickers);
    setActivePresetId(presetId);
    setSelectedTicker(nextSelectedTicker ?? nextTickers[0] ?? null);
    persistWatchlist(nextTickers);
  }, [persistWatchlist]);

  const load = useCallback(async (
    forceRefresh = false,
    refreshKind: 'manual' | 'auto' | 'force live' = forceRefresh ? 'force live' : 'manual',
    tickersOverride?: string[],
  ) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setForceLoading(forceRefresh);
    setError(null);
    try {
      const requestedTickers = tickersOverride ?? watchlist;
      const nextData = await stocksApi.getVietnamWatchlist(requestedTickers, forceRefresh);
      if (requestId !== requestIdRef.current) return;
      setData(nextData);
      setLastRefreshKind(refreshKind);
      setLastRefreshAt(new Date().toISOString());
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load Vietnam dashboard');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setForceLoading(false);
      }
    }
  }, [watchlist]);

  const handlePresetChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
    const presetId = event.target.value as VietnamWatchlistPresetId;
    if (presetId === 'my') {
      const storedWatchlist = readVietnamWatchlist(DEFAULT_WATCHLIST);
      setStorageWarning(storedWatchlist.usedFallback ? 'Saved watchlist was invalid and default tickers were restored.' : null);
      setWatchlist(storedWatchlist.tickers);
      setActivePresetId('my');
      setSelectedTicker(storedWatchlist.tickers[0] ?? null);
      return;
    }
    const presetTickers = getVietnamPresetTickers(presetId);
    if (!presetTickers) {
      setWatchlistError('Preset list is unavailable.');
      return;
    }
    setWatchlistError(null);
    applyWatchlist(presetTickers, presetId);
  }, [applyWatchlist]);

  const handleAddTicker = useCallback((event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const result = validateVietnamTicker(watchlistInput, watchlist);
    if (!result.valid) {
      setWatchlistError(result.error);
      return;
    }
    const nextTickers = [...watchlist, result.ticker];
    nextWatchlistLoadRef.current = { tickers: nextTickers, forceRefresh: true, refreshKind: 'force live' };
    applyWatchlist(nextTickers, 'my', result.ticker);
    setWatchlistInput('');
    setWatchlistError(null);
  }, [applyWatchlist, watchlist, watchlistInput]);

  const handleRemoveTicker = useCallback((ticker: string) => {
    if (watchlist.length <= 1) {
      setWatchlistError('Watchlist must contain at least one ticker.');
      return;
    }
    const nextTickers = watchlist.filter((item) => item !== ticker);
    const nextSelectedTicker = selectedTicker === ticker ? nextTickers[0] ?? null : selectedTicker;
    applyWatchlist(nextTickers, 'my', nextSelectedTicker);
    setWatchlistError(null);
  }, [applyWatchlist, selectedTicker, watchlist]);

  const handleMoveTicker = useCallback((ticker: string, direction: 'up' | 'down') => {
    const nextTickers = moveVietnamTicker(watchlist, ticker, direction);
    if (nextTickers === watchlist) return;
    applyWatchlist(nextTickers, 'my', ticker);
    setWatchlistError(null);
  }, [applyWatchlist, watchlist]);

  const handleResetWatchlist = useCallback(() => {
    applyWatchlist(DEFAULT_WATCHLIST, 'my');
    setWatchlistInput('');
    setWatchlistError(null);
  }, [applyWatchlist]);

  useEffect(() => {
    const queuedLoad = nextWatchlistLoadRef.current;
    if (queuedLoad) {
      nextWatchlistLoadRef.current = null;
      void load(queuedLoad.forceRefresh, queuedLoad.refreshKind, queuedLoad.tickers);
      return;
    }
    void load();
  }, [load]);

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
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [autoRefreshEnabled, autoRefreshInterval]);

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
    const rows = data?.watchlist ?? [];
    if (selectedTicker && watchlist.includes(selectedTicker)) {
      return;
    }
    if (rows.length && !rows.some((item) => item.ticker === selectedTicker)) {
      setSelectedTicker(rows[0].ticker);
    }
  }, [data, selectedTicker, watchlist]);

  const summary = useMemo(() => {
    const rows = data?.watchlist ?? [];
    const up = rows.filter((item) => (item.changePct ?? 0) > 0).length;
    const avgLiquidity = rows.length
      ? Math.round(rows.reduce((sum, item) => sum + (item.liquidity.score ?? 0), 0) / rows.length)
      : 0;
    const foreignNet = rows.reduce((sum, item) => sum + (item.foreign.net ?? 0), 0);
    return { count: rows.length, up, avgLiquidity, foreignNet };
  }, [data]);

  const rowsLoaded = useMemo(
    () => (data?.watchlist ?? []).reduce((sum, item) => sum + (item.rowsLoaded ?? 0), 0),
    [data],
  );

  const selectedItem = useMemo(
    () => (data?.watchlist ?? []).find((item) => item.ticker === selectedTicker) ?? data?.watchlist?.[0] ?? null,
    [data, selectedTicker],
  );

  return (
    <AppPage className="space-y-5">
      <header className="flex flex-col gap-4 border-b border-border/70 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="label-uppercase text-secondary-text">Vietnam market</p>
          <h1 className="mt-2 text-2xl font-semibold text-foreground md:text-3xl">Watchlist Monitor</h1>
          <p className="mt-2 max-w-3xl text-sm text-secondary-text">
            Mozyfin-backed OHLCV, price-limit awareness, foreign flow, liquidity, and technical score tracking.
          </p>
          <p className="mt-2 max-w-3xl text-xs text-secondary-text">
            During trading hours, the latest daily candle close may represent the latest traded price. After market close, it represents the final close.
          </p>
          <p className="mt-1 max-w-3xl text-xs text-secondary-text">
            Labels are neutral condition tags, not trading recommendations.
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
        </div>
      </header>

      <section className="rounded-lg border border-border/70 bg-card p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-foreground">Refresh control</h2>
              <Badge variant={autoRefreshEnabled ? 'success' : 'default'}>
                Auto-refresh {autoRefreshEnabled ? 'ON' : 'OFF'}
              </Badge>
              {isTabHidden && autoRefreshEnabled ? <Badge variant="warning">Paused while tab hidden</Badge> : null}
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
          </div>
        </div>
        <dl className="mt-4 grid gap-3 text-sm md:grid-cols-4">
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
        </dl>
        <div className="mt-3 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
          Latest price currently uses OHLCV candle close because Mozyfin quote does not expose a reliable realtime matched price.
        </div>
      </section>

      <section className="rounded-lg border border-border/70 bg-card p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-foreground">Edit Watchlist</h2>
              <Badge variant="default">{watchlist.length}/{VIETNAM_WATCHLIST_MAX_SIZE}</Badge>
            </div>
            <p className="mt-1 text-xs text-secondary-text">
              Saved locally in this browser. Changes refresh through the normal cached watchlist request.
            </p>
            <p className="mt-1 text-xs text-secondary-text">
              Preset lists are convenience lists, not investment suggestions.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={handleResetWatchlist}>
            <RotateCcw className="h-4 w-4" />
            Reset to default
          </Button>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,260px)_1fr] lg:items-end">
          <label className="flex flex-col text-sm text-secondary-text">
            Preset list
            <select
              value={activePresetId}
              onChange={handlePresetChange}
              className="mt-2 h-10 rounded-lg border border-border/70 bg-elevated px-3 text-sm text-foreground"
            >
              <option value="my">My Watchlist</option>
              {VIETNAM_WATCHLIST_PRESETS.map((preset) => (
                <option key={preset.id} value={preset.id}>{preset.label}</option>
              ))}
            </select>
          </label>
          <p className="text-xs text-secondary-text">
            Selecting a preset replaces the active list and refreshes normally through the cached watchlist endpoint.
          </p>
        </div>
        <form className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start" onSubmit={handleAddTicker}>
          <Input
            label="Ticker"
            value={watchlistInput}
            onChange={(event) => {
              setWatchlistInput(event.target.value);
              if (watchlistError) setWatchlistError(null);
            }}
            error={watchlistError ?? undefined}
            placeholder="FPT or FPT.VN"
            autoComplete="off"
            autoCapitalize="characters"
            className="uppercase"
          />
          <Button type="submit" variant="secondary" className="mt-0 sm:mt-7">
            <Plus className="h-4 w-4" />
            Add ticker
          </Button>
        </form>
        {storageWarning ? (
          <div className="mt-3 flex gap-2 rounded-lg border border-warning/20 bg-warning/10 p-3 text-xs text-warning">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{storageWarning}</span>
          </div>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {watchlist.map((ticker, index) => (
            <span
              key={ticker}
              className="inline-flex h-9 items-center gap-1 rounded-lg border border-border/70 bg-elevated px-2 text-sm font-medium text-foreground"
            >
              <span className="px-1">{ticker}</span>
              <button
                type="button"
                onClick={() => handleMoveTicker(ticker, 'up')}
                disabled={index === 0}
                className="inline-flex h-6 w-6 items-center justify-center rounded-md text-secondary-text transition-colors hover:bg-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/25 disabled:pointer-events-none disabled:opacity-35"
                aria-label={`Move ${ticker} up`}
              >
                <ArrowUp className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => handleMoveTicker(ticker, 'down')}
                disabled={index === watchlist.length - 1}
                className="inline-flex h-6 w-6 items-center justify-center rounded-md text-secondary-text transition-colors hover:bg-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/25 disabled:pointer-events-none disabled:opacity-35"
                aria-label={`Move ${ticker} down`}
              >
                <ArrowDown className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => handleRemoveTicker(ticker)}
                className="inline-flex h-5 w-5 items-center justify-center rounded-md text-secondary-text transition-colors hover:bg-danger/10 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/25"
                aria-label={`Remove ${ticker}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ))}
        </div>
        <p className="mt-3 text-xs text-secondary-text">
          Accepted symbols use letters and numbers only, up to 10 characters. A trailing .VN suffix is removed before saving.
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
        <div className="rounded-lg border border-border/70 bg-card p-4">
          <ShieldAlert className="mb-3 h-5 w-5 text-purple" />
          <p className="text-xs text-secondary-text">Foreign net</p>
          <p className={cn('text-2xl font-semibold', signalTone(summary.foreignNet))}>{formatNumber(summary.foreignNet)}</p>
        </div>
      </section>

      {error ? (
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm text-danger">{error}</div>
      ) : null}

      {data ? (
        <section className="rounded-lg border border-border/70 bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <DatabaseZap className="h-5 w-5 text-cyan" />
              <h2 className="text-base font-semibold text-foreground">Data quality</h2>
            </div>
            <Badge variant={data.fixtureMode ? 'warning' : 'success'}>
              {data.fixtureMode ? 'Fixture mode' : 'Live mode'}
            </Badge>
          </div>
          <dl className="mt-4 grid gap-3 text-sm md:grid-cols-5">
            <div className="rounded-lg bg-elevated/50 p-3">
              <dt className="text-xs text-secondary-text">Data source</dt>
              <dd className="mt-1 font-medium text-foreground">{data.dataQuality.source}</dd>
            </div>
            <div className="rounded-lg bg-elevated/50 p-3">
              <dt className="text-xs text-secondary-text">Trading date</dt>
              <dd className="mt-1 font-medium text-foreground">{data.dataQuality.lastTradingDate ?? '-'}</dd>
            </div>
            <div className="rounded-lg bg-elevated/50 p-3">
              <dt className="text-xs text-secondary-text">Rows loaded</dt>
              <dd className="mt-1 font-medium text-foreground">{formatNumber(rowsLoaded)}</dd>
            </div>
            <div className="rounded-lg bg-elevated/50 p-3">
              <dt className="text-xs text-secondary-text">Fixture active</dt>
              <dd className="mt-1 font-medium text-foreground">{data.dataQuality.fixtureMode ? 'Yes' : 'No'}</dd>
            </div>
            <div className="rounded-lg bg-elevated/50 p-3">
              <dt className="text-xs text-secondary-text">Last refresh</dt>
              <dd className="mt-1 font-medium text-foreground">{formatVietnamTime(data.dataQuality.lastRefreshTime)}</dd>
              <dd className="mt-1 text-xs text-secondary-text">{formatRelativeAge(data.dataQuality.lastRefreshTime)}</dd>
            </div>
          </dl>
          <div className="mt-3 rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
            Units: latest price and OHLCV fields are VND, volume is shares, and foreign net is labeled shares only when Mozyfin quote quantity fields are used.
          </div>
          {Object.keys(data.dataQuality.missingFields).length || Object.keys(data.dataQuality.errors).length ? (
            <div className="mt-3 space-y-2">
              {Object.entries(data.dataQuality.missingFields).map(([ticker, fields]) => (
                <div key={`missing-${ticker}`} className="rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
                  {ticker}: missing {fields.join(', ')}
                </div>
              ))}
              {Object.entries(data.dataQuality.errors).map(([ticker, errors]) => (
                <div key={`error-${ticker}`} className="rounded-lg border border-danger/20 bg-danger/10 p-2 text-xs text-danger">
                  {ticker}: {errors.join('; ')}
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {data ? (
        <CacheMetadataPanel data={data} items={data.watchlist ?? []} />
      ) : null}

      {loading && !data ? (
        <Loading label="Loading Vietnam watchlist..." />
      ) : (
        <>
          <IndicatorTable items={data?.watchlist ?? []} selectedTicker={selectedItem?.ticker} onSelect={setSelectedTicker} />
          <StockDetailView item={selectedItem} fixtureMode={data?.fixtureMode} />
          <section className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {(data?.watchlist ?? []).map((item) => (
              <WatchCard key={item.ticker} item={item} />
            ))}
          </section>
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
                <dt className="font-medium text-foreground">{key.replaceAll('_', ' ')}</dt>
                <dd className="mt-1 text-secondary-text">{formula}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </AppPage>
  );
};

export default VietnamDashboardPage;
