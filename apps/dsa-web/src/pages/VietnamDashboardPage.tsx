import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Banknote, DatabaseZap, RefreshCw, ShieldAlert } from 'lucide-react';
import { stocksApi, type VietnamWatchItem, type VietnamWatchlistResponse } from '../api/stocks';
import { AppPage, Badge, Button, Loading } from '../components/common';
import { cn } from '../utils/cn';

const DEFAULT_TICKERS = ['FPT', 'VPB', 'MSB', 'SCS', 'ACV', 'ACB'];

const formatNumber = (value?: number | null, maximumFractionDigits = 0) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits }).format(value);
};

const formatPrice = (value?: number | null) => formatNumber(value, 2);

const formatDateTime = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
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

const cacheVariant = (status?: string | null) => {
  if (status === 'hit') return 'success';
  if (status === 'miss' || status === 'refresh') return 'info';
  if (status === 'stale') return 'warning';
  if (status === 'error') return 'danger';
  return 'default';
};

const cacheLabel = (status?: string | null) => status ?? 'missing';

const WatchCard: React.FC<{ item: VietnamWatchItem }> = ({ item }) => {
  const positive = (item.changePct ?? 0) >= 0;
  const TrendIcon = positive ? ArrowUpRight : ArrowDownRight;

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
            {(item.statusLabels ?? ['Watch']).map((label) => (
              <Badge key={label} variant={statusVariant(label)}>{label}</Badge>
            ))}
          </div>
          <p className="mt-1 text-xs text-secondary-text">{item.date ?? '-'} | {item.source ?? 'mozyfin-cli'}</p>
        </div>
        <div className={cn('flex items-center gap-1 text-sm font-semibold', signalTone(item.changePct))}>
          <TrendIcon className="h-4 w-4" />
          {formatNumber(item.changePct, 2)}%
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-secondary-text">Latest price (VND)</p>
          <p className="text-lg font-semibold text-foreground">{formatPrice(item.latestPrice ?? item.close)}</p>
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
            <Badge variant="default">{item.priceDate ?? '-'}</Badge>
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
          <span className="flex flex-wrap justify-end gap-1">
            <Badge variant={cacheVariant(item.cacheStatus.ohlcvCache)}>OHLCV {cacheLabel(item.cacheStatus.ohlcvCache)}</Badge>
            <Badge variant={cacheVariant(item.cacheStatus.quoteCache)}>Quote {cacheLabel(item.cacheStatus.quoteCache)}</Badge>
            <Badge variant={cacheVariant(item.cacheStatus.newsCache)}>News {cacheLabel(item.cacheStatus.newsCache)}</Badge>
          </span>
        </div>
      </div>

      {item.warnings.length > 0 ? (
        <div className="mt-3 space-y-2">
          {item.warnings.map((warning) => (
            <div key={warning} className="flex gap-2 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      ) : null}

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
    item.cacheLastFetchedAt?.news,
  ]).filter((value): value is string => Boolean(value));
  const refreshTimes = items.flatMap((item) => [
    item.cacheNextRefreshAt?.ohlcv,
    item.cacheNextRefreshAt?.quote,
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
          <dd className="mt-1 font-medium text-foreground">{formatDateTime(latestFetched)}</dd>
        </div>
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Next refresh</dt>
          <dd className="mt-1 font-medium text-foreground">{formatDateTime(nextRefresh)}</dd>
        </div>
      </dl>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <Badge variant="default">OHLCV TTL {formatNumber(metadata.cacheTtlSeconds.ohlcv)}s</Badge>
        <Badge variant="default">Quote TTL {formatNumber(metadata.cacheTtlSeconds.quote)}s</Badge>
        <Badge variant="default">News TTL {formatNumber(metadata.cacheTtlSeconds.news)}s</Badge>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-border/70 text-xs uppercase text-secondary-text">
            <tr>
              <th className="py-2 pr-3">Ticker</th>
              <th className="px-3 py-2">OHLCV</th>
              <th className="px-3 py-2">Quote</th>
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
                  <Badge variant={cacheVariant(item.cacheStatus.newsCache)}>{cacheLabel(item.cacheStatus.newsCache)}</Badge>
                </td>
                <td className="px-3 py-3">
                  <span className="block">OHLCV {formatDateTime(item.cacheLastFetchedAt?.ohlcv)}</span>
                  <span className="block">Quote {formatDateTime(item.cacheLastFetchedAt?.quote)}</span>
                  <span className="block">News {formatDateTime(item.cacheLastFetchedAt?.news)}</span>
                </td>
                <td className="px-3 py-3">
                  <span className="block">OHLCV {formatDateTime(item.cacheNextRefreshAt?.ohlcv)}</span>
                  <span className="block">Quote {formatDateTime(item.cacheNextRefreshAt?.quote)}</span>
                  <span className="block">News {formatDateTime(item.cacheNextRefreshAt?.news)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
      <table className="w-full min-w-[1040px] text-left text-sm">
        <thead className="border-b border-border/70 text-xs uppercase text-secondary-text">
          <tr>
            <th className="py-2 pr-3">Ticker</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2 text-right">Latest price</th>
            <th className="px-3 py-2 text-right">OHLCV close</th>
            <th className="px-3 py-2">Final close</th>
            <th className="px-3 py-2 text-right">MA20</th>
            <th className="px-3 py-2 text-right">MA50</th>
            <th className="px-3 py-2 text-right">RSI14 Wilder/RMA</th>
            <th className="px-3 py-2 text-right">Vol ratio</th>
            <th className="px-3 py-2 text-right">20D high</th>
            <th className="px-3 py-2 text-right">20D low</th>
            <th className="px-3 py-2 text-right">Foreign 5D</th>
            <th className="px-3 py-2 text-right">Foreign 20D</th>
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
                  {(item.statusLabels ?? ['Watch']).map((label) => (
                    <Badge key={label} variant={statusVariant(label)}>{label}</Badge>
                  ))}
                </div>
              </td>
              <td className="px-3 py-3 text-right">{formatPrice(item.latestPrice ?? item.close)}</td>
              <td className="px-3 py-3 text-right">{formatPrice(item.ohlcvClose ?? item.close)}</td>
              <td className="px-3 py-3">
                <Badge variant={item.finalCloseStatus === 'final' ? 'success' : item.finalCloseStatus === 'not_final' ? 'warning' : 'default'}>
                  {item.finalCloseStatus ?? 'unknown'}
                </Badge>
              </td>
              <td className="px-3 py-3 text-right">{formatPrice(item.indicators.ma20)}</td>
              <td className="px-3 py-3 text-right">{formatPrice(item.indicators.ma50)}</td>
              <td className="px-3 py-3 text-right">{formatNumber(item.indicators.rsi14Wilder ?? item.indicators.rsi14, 2)}</td>
              <td className="px-3 py-3 text-right">{formatNumber(item.indicators.volumeRatio, 2)}</td>
              <td className="px-3 py-3 text-right">{formatPrice(item.indicators.high20d)}</td>
              <td className="px-3 py-3 text-right">{formatPrice(item.indicators.low20d)}</td>
              <td className={cn('px-3 py-3 text-right', signalTone(item.indicators.foreignNet5d))}>
                {formatNumber(item.indicators.foreignNet5d)}
              </td>
              <td className={cn('px-3 py-3 text-right', signalTone(item.indicators.foreignNet20d))}>
                {formatNumber(item.indicators.foreignNet20d)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </section>
);

const StockDetailView: React.FC<{ item?: VietnamWatchItem | null }> = ({ item }) => {
  if (!item) return null;
  const indicators = item.indicators;
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
          <dt className="text-xs text-secondary-text">Price date / final close</dt>
          <dd className="mt-1 font-medium text-foreground">{item.priceDate ?? '-'} / {item.finalCloseStatus ?? 'unknown'}</dd>
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
        <div className="rounded-lg bg-elevated/50 p-3">
          <dt className="text-xs text-secondary-text">Foreign raw fields</dt>
          <dd className="mt-1 font-medium text-foreground">
            {item.foreignBuyRawField ?? '-'} / {item.foreignSellRawField ?? '-'}
          </dd>
        </div>
      </dl>
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
                {detail.inputs && Object.keys(detail.inputs).length ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {Object.entries(detail.inputs).map(([key, value]) => (
                      <Badge key={`${detail.label}-${key}`} variant="default">
                        {key.replaceAll('_', ' ')}: {String(value)}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
};

const VietnamDashboardPage: React.FC = () => {
  const [data, setData] = useState<VietnamWatchlistResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [forceLoading, setForceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(DEFAULT_TICKERS[0]);

  const load = async (forceRefresh = false) => {
    setLoading(true);
    setForceLoading(forceRefresh);
    setError(null);
    try {
      setData(await stocksApi.getVietnamWatchlist(DEFAULT_TICKERS, forceRefresh));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Vietnam dashboard');
    } finally {
      setLoading(false);
      setForceLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const rows = data?.watchlist ?? [];
    if (rows.length && !rows.some((item) => item.ticker === selectedTicker)) {
      setSelectedTicker(rows[0].ticker);
    }
  }, [data, selectedTicker]);

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
              <dd className="mt-1 font-medium text-foreground">{formatDateTime(data.dataQuality.lastRefreshTime)}</dd>
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
          <StockDetailView item={selectedItem} />
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
