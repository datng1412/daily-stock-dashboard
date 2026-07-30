import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, RefreshCw } from 'lucide-react';
import type {
  VietnamFlowDataResponse,
  VietnamCurrentForeignFlowAggregateResponse,
  VietnamForeignFlowWatchlistResponse,
  VietnamVn30ForeignFlowComponent,
  VietnamVn30ForeignFlowDaily,
  VietnamVn30ForeignFlowResponse,
} from '../../api/stocks';
import { stocksApi } from '../../api/stocks';
import { cn } from '../../utils/cn';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import {
  formatForeignFlowPercent,
  formatForeignFlowValue,
  formatForeignFlowVolume,
} from '../../utils/vietnamNumberFormat';
import { Badge, Button } from '../common';
import type { SymbolForeignFlowMetricRow } from './foreignFlowSymbolAnalyticsModel';
import { ForeignFlowSymbolHistoryChart, type SymbolForeignFlowChartMode } from './ForeignFlowSymbolHistoryChart';
import {
  readForeignFlowWatchlistPreferences,
  foreignFlowWatchlistMetric,
} from './foreignFlowWatchlistModel';
import type {
  ForeignFlowExplorerMetric,
  ForeignFlowExplorerWindow,
} from './foreignFlowExplorerModel';
import {
  mapIndustryFlowViewState,
  mapVn30FlowViewState,
  mapWatchlistFlowViewState,
} from './foreignFlowViewState';
import { selectForeignFlowDisplayStatus } from './latestForeignFlowSessionModel';

type OverviewTarget = 'ticker' | 'industry' | 'watchlist' | 'details';

type ForeignFlowOverviewProps = {
  vn30: VietnamVn30ForeignFlowResponse | null;
  industry: VietnamFlowDataResponse | null;
  currentAggregate: VietnamCurrentForeignFlowAggregateResponse | null;
  loading: boolean;
  error: string | null;
  metric: ForeignFlowExplorerMetric;
  window: ForeignFlowExplorerWindow;
  chartMode: SymbolForeignFlowChartMode;
  onChartModeChange: (mode: SymbolForeignFlowChartMode) => void;
  onRefresh: () => void;
  onNavigate: (target: OverviewTarget, ticker?: string) => void;
};

type RankedItem = {
  label: string;
  value: number;
  contribution: number | null;
};

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const asText = (value: unknown): string => typeof value === 'string' ? value : '';

const metricFormatter = (metric: ForeignFlowExplorerMetric) => (
  metric === 'value' ? formatForeignFlowValue : formatForeignFlowVolume
);

const metricKeys = (metric: ForeignFlowExplorerMetric) => metric === 'value'
  ? { buy: 'foreignBuyValue', sell: 'foreignSellValue', net: 'foreignNetValue' }
  : { buy: 'foreignBuyVolume', sell: 'foreignSellVolume', net: 'foreignNetVolume' };

const dailyMetric = (
  row: VietnamVn30ForeignFlowDaily | null | undefined,
  metric: ForeignFlowExplorerMetric,
  side: 'buy' | 'sell' | 'net',
) => {
  const metricValue = row?.[metricKeys(metric)[side] as keyof VietnamVn30ForeignFlowDaily];
  return finite(metricValue) ? metricValue : null;
};

const windowMetric = (
  data: VietnamVn30ForeignFlowResponse,
  metric: ForeignFlowExplorerMetric,
  window: '1' | '5' | '20',
) => {
  if (window === '1') return dailyMetric(data.decomposition.latest ?? data.decomposition.series.at(-1), metric, 'net');
  const metricValue = data.decomposition.windows?.[window]?.[metricKeys(metric).net as keyof typeof data.decomposition.windows['5']];
  return finite(metricValue) ? metricValue : null;
};

const componentMetric = (
  row: VietnamVn30ForeignFlowComponent,
  metric: ForeignFlowExplorerMetric,
  window: ForeignFlowExplorerWindow,
) => {
  const suffix = metric === 'value' ? 'Value' : 'Volume';
  const key = window === '60'
    ? `foreignNet${suffix}60d`
    : window === '20'
      ? `foreignNet${suffix}20d`
      : window === '5'
        ? `foreignNet${suffix}5d`
        : `foreignNet${suffix}`;
  const metricValue = row[key as keyof VietnamVn30ForeignFlowComponent];
  return finite(metricValue) ? metricValue : null;
};

const buildRankings = (
  components: VietnamVn30ForeignFlowComponent[],
  metric: ForeignFlowExplorerMetric,
  window: ForeignFlowExplorerWindow,
) => {
  const values = components
    .map((row) => ({ label: row.ticker, value: componentMetric(row, metric, window) }))
    .filter((row): row is { label: string; value: number } => row.value !== null);
  const absoluteTotal = values.reduce((sum, row) => sum + Math.abs(row.value), 0);
  const mapItem = (row: { label: string; value: number }): RankedItem => ({
    ...row,
    contribution: absoluteTotal > 0 ? Math.abs(row.value) / absoluteTotal : null,
  });
  return {
    buyers: values.filter((row) => row.value > 0).sort((a, b) => b.value - a.value).slice(0, 5).map(mapItem),
    sellers: values.filter((row) => row.value < 0).sort((a, b) => a.value - b.value).slice(0, 5).map(mapItem),
  };
};

const buildChartRows = (
  series: VietnamVn30ForeignFlowDaily[],
  metric: ForeignFlowExplorerMetric,
  window: ForeignFlowExplorerWindow,
): SymbolForeignFlowMetricRow[] => {
  const requested = window === 'custom' ? series.length : Number(window);
  let cumulative = 0;
  return series.slice(-requested).map((row) => {
    const buy = dailyMetric(row, metric, 'buy');
    const sell = dailyMetric(row, metric, 'sell');
    const net = dailyMetric(row, metric, 'net');
    if (net !== null) cumulative += net;
    return {
      tradingDate: row.tradingDate,
      buy,
      sell,
      net,
      rolling5: null,
      rolling20: null,
      cumulative: net === null ? null : cumulative,
      usable: net !== null,
      sign: net === null ? 'unavailable' : net > 0 ? 'positive' : net < 0 ? 'negative' : 'zero',
      state: net === null ? 'unavailable' : row.dataState === 'stale' ? 'partial' : row.dataState,
      unit: metric === 'value' ? 'VND' : 'shares',
    };
  });
};

const industryRankings = (
  response: VietnamFlowDataResponse | null,
  metric: ForeignFlowExplorerMetric,
  window: ForeignFlowExplorerWindow,
) => {
  const rows = response?.rows ?? [];
  const dates = [...new Set(rows.map((row) => asText(row.tradingDate)).filter(Boolean))].sort();
  const selectedDates = new Set(window === 'custom' ? dates : dates.slice(-Number(window)));
  const grouped = new Map<string, { label: string; values: number[]; coverage: number[] }>();
  rows.forEach((row) => {
    if (!selectedDates.has(asText(row.tradingDate))) return;
    const code = asText(row.icbCode) || 'unclassified';
    const current = grouped.get(code) ?? {
      label: asText(row.icbName) || code,
      values: [],
      coverage: [],
    };
    const metricValue = row[metricKeys(metric).net];
    const coverage = row.coverageRatio;
    if (finite(metricValue)) current.values.push(metricValue);
    if (finite(coverage)) current.coverage.push(coverage);
    grouped.set(code, current);
  });
  const values = [...grouped.values()]
    .map((item) => ({
      label: item.label,
      value: item.values.length ? item.values.reduce((sum, current) => sum + current, 0) : null,
      coverage: item.coverage.length
        ? item.coverage.reduce((sum, current) => sum + current, 0) / item.coverage.length
        : null,
    }))
    .filter((item): item is { label: string; value: number; coverage: number | null } => item.value !== null);
  const absoluteTotal = values.reduce((sum, row) => sum + Math.abs(row.value), 0);
  return [...values]
    .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))
    .slice(0, 6)
    .map((item) => ({
      ...item,
      contribution: absoluteTotal > 0 ? Math.abs(item.value) / absoluteTotal : null,
    }));
};

const KpiCard = ({
  label,
  value,
  formatted,
  state,
}: {
  label: string;
  value: number | null;
  formatted: string;
  state?: string | null;
}) => (
  <article className="min-w-0 rounded-xl border border-border/70 bg-card p-4" data-testid="foreign-flow-primary-kpi">
    <div className="flex items-start justify-between gap-2">
      <p className="text-sm font-medium text-secondary-text">{label}</p>
      {state && state !== 'clean' ? <Badge variant="warning" size="sm">{state}</Badge> : null}
    </div>
    <p className={cn('mt-3 truncate text-2xl font-semibold tabular-nums', foreignFlowSignTextClass(value))}>
      {formatted}
    </p>
  </article>
);

const RankingPanel = ({
  title,
  rows,
  metric,
  onTicker,
}: {
  title: string;
  rows: RankedItem[];
  metric: ForeignFlowExplorerMetric;
  onTicker: (ticker: string) => void;
}) => {
  const format = metricFormatter(metric);
  return (
    <section>
      <h3 className="text-sm font-semibold">{title}</h3>
      {rows.length ? (
        <ol className="mt-2 divide-y divide-border/50">
          {rows.map((row) => (
            <li key={row.label} className="flex items-center justify-between gap-3 py-2">
              <button type="button" className="font-semibold hover:text-cyan" onClick={() => onTicker(row.label)}>
                {row.label}
              </button>
              <div className="text-right">
                <p className={cn('font-medium tabular-nums', foreignFlowSignTextClass(row.value))}>{format(row.value)}</p>
                <p className="text-[11px] text-secondary-text">
                  {row.contribution === null ? 'Contribution —' : `${formatForeignFlowPercent(row.contribution * 100)} contribution`}
                </p>
              </div>
            </li>
          ))}
        </ol>
      ) : <p className="mt-2 text-sm text-secondary-text">No usable ranked values.</p>}
    </section>
  );
};

const WatchlistOverview = ({
  metric,
  onOpen,
}: {
  metric: ForeignFlowExplorerMetric;
  onOpen: () => void;
}) => {
  const [tickers] = useState(() => readForeignFlowWatchlistPreferences(
    typeof globalThis.localStorage === 'undefined' ? null : globalThis.localStorage,
  ).tickers);
  const [data, setData] = useState<VietnamForeignFlowWatchlistResponse | null>(null);
  const [loading, setLoading] = useState(tickers.length > 0);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);

  useEffect(() => {
    if (!tickers.length) return undefined;
    requestRef.current += 1;
    const requestId = requestRef.current;
    const controller = new AbortController();
    stocksApi.getVietnamForeignFlowWatchlist(tickers, {
      sessions: 60,
      forceRefresh: false,
      signal: controller.signal,
    }).then((response) => {
      if (requestRef.current === requestId && !controller.signal.aborted) setData(response);
    }).catch((caught: unknown) => {
      if (requestRef.current === requestId && !controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : 'Watchlist summary unavailable.');
      }
    }).finally(() => {
      if (requestRef.current === requestId && !controller.signal.aborted) setLoading(false);
    });
    return () => {
      requestRef.current += 1;
      controller.abort();
    };
  }, [tickers]);

  const state = data ? mapWatchlistFlowViewState(data) : null;
  return (
    <section className="rounded-xl border border-border/70 bg-card p-4" aria-labelledby="overview-watchlist-heading">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 id="overview-watchlist-heading" className="font-semibold">Watchlist snapshot</h2>
          <p className="mt-1 text-xs text-secondary-text">Saved locally · no default symbols</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onOpen}>View full watchlist <ArrowRight className="h-4 w-4" /></Button>
      </div>
      {!tickers.length ? (
        <div className="mt-3 rounded-lg bg-elevated/35 p-4 text-sm text-secondary-text">
          Your watchlist is empty. Add symbols in Watchlist to see a compact comparison here.
        </div>
      ) : null}
      {loading && !data ? <div className="mt-3 h-20 animate-pulse rounded-lg bg-elevated/50" aria-label="Loading watchlist summary" /> : null}
      {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
      {data ? (
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-secondary-text">
              <tr>
                <th className="py-2 text-left">Ticker</th>
                <th className="px-2 py-2 text-right">Net 1D</th>
                <th className="px-2 py-2 text-right">Net 5D</th>
                <th className="px-2 py-2 text-right">Net 20D</th>
                <th className="py-2 text-left">Streak</th>
              </tr>
            </thead>
            <tbody>
              {data.items.slice(0, 6).map((item) => {
                const values = ([1, 5, 20] as const).map((itemWindow) => foreignFlowWatchlistMetric(item, metric, itemWindow));
                return (
                  <tr key={item.ticker} className="border-t border-border/50">
                    <td className="py-2 font-semibold">{item.ticker}</td>
                    {values.map((metricValue, index) => (
                      <td key={index} className={cn('px-2 py-2 text-right tabular-nums', foreignFlowSignTextClass(metricValue))}>
                        {metricValue === null ? '—' : metricFormatter(metric)(metricValue)}
                      </td>
                    ))}
                    <td className="py-2 text-secondary-text">
                      {item.buyStreak ? `Buy ${item.buyStreak}` : item.sellStreak ? `Sell ${item.sellStreak}` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {state?.availability !== 'ready' ? (
            <p className="mt-2 text-xs text-warning">Some saved symbols are {state?.availability}; usable rows remain visible.</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
};

export const ForeignFlowOverview = ({
  vn30,
  industry,
  currentAggregate,
  loading,
  error,
  metric,
  window,
  chartMode,
  onChartModeChange,
  onRefresh,
  onNavigate,
}: ForeignFlowOverviewProps) => {
  const format = metricFormatter(metric);
  const vn30State = vn30 ? mapVn30FlowViewState(vn30) : null;
  const industryState = industry ? mapIndustryFlowViewState(industry) : null;
  const latestCurrent = [...(currentAggregate?.displaySeries ?? [])].reverse().find(
    (row) => row.sourceKind === 'current',
  ) as VietnamVn30ForeignFlowDaily | undefined;
  const latest = latestCurrent
    ?? vn30?.decomposition.latest
    ?? vn30?.decomposition.series.at(-1)
    ?? null;
  const breadth = metric === 'value' ? latest?.valueBreadth : latest?.volumeBreadth;
  const kpis = vn30 ? (['1', '5', '20'] as const).map((item) => ({
    label: `Net foreign flow ${item}D${currentAggregate?.displayWindows?.[item]?.isProvisional ? ' · provisional' : ''}`,
    value: finite(currentAggregate?.displayWindows?.[item]?.[metricKeys(metric).net])
      ? currentAggregate?.displayWindows[item][metricKeys(metric).net] as number
      : windowMetric(vn30, metric, item),
  })) : [];
  const rankings = useMemo(
    () => {
      const current = currentAggregate?.rankings?.[window === 'custom' ? '60' : window];
      if (current) {
        const map = (rows: Array<Record<string, unknown>>): RankedItem[] => {
          const values = rows
            .map((row) => ({
              label: asText(row.ticker),
              value: finite(row.value) ? row.value : null,
            }))
            .filter((row): row is { label: string; value: number } => Boolean(row.label) && row.value !== null);
          const absoluteTotal = values.reduce((sum, row) => sum + Math.abs(row.value), 0);
          return values.map((row) => ({
            ...row,
            contribution: absoluteTotal > 0 ? Math.abs(row.value) / absoluteTotal : null,
          }));
        };
        return { buyers: map(current.topBuy), sellers: map(current.topSell) };
      }
      return buildRankings(vn30?.components ?? [], metric, window);
    },
    [currentAggregate?.rankings, metric, vn30?.components, window],
  );
  const history = useMemo(
    () => buildChartRows(
      (currentAggregate?.displaySeries?.length
        ? currentAggregate.displaySeries
        : vn30?.decomposition.series ?? []) as VietnamVn30ForeignFlowDaily[],
      metric,
      window,
    ),
    [currentAggregate, metric, vn30?.decomposition.series, window],
  );
  const industries = useMemo(
    () => industryRankings(industry, metric, window),
    [industry, metric, window],
  );
  const latestSession = latest?.tradingDate
    ?? vn30?.decomposition.latestCompletedSession
    ?? null;
  const publicationLag = Boolean(
    currentAggregate?.providerSessionDate
    && latestSession
    && latestSession < currentAggregate.providerSessionDate,
  );
  const currentDisplayStatus = currentAggregate ? selectForeignFlowDisplayStatus({
    sourceKind: 'current',
    finality: currentAggregate.finality ?? 'current_session_provisional',
    currentState: currentAggregate.dataState,
    providerStatus: currentAggregate.dataState,
    usable: currentAggregate.usable,
    hasUsableValues: Boolean(currentAggregate.aggregate),
  }) : null;

  if (loading && !vn30) {
    return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Loading Foreign Flow overview">
      {[0, 1, 2, 3].map((item) => <div key={item} className="h-28 animate-pulse rounded-xl bg-elevated/50" />)}
    </div>;
  }

  if (!vn30 || !vn30State?.usable) {
    return (
      <section className="rounded-xl border border-border/70 bg-card p-5" aria-label="Foreign Flow overview unavailable">
        <h2 className="font-semibold">Overview unavailable</h2>
        <p className="mt-2 text-sm text-secondary-text">{error ?? 'Completed-session VN30 foreign flow is unavailable.'}</p>
        <Button className="mt-4" variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="h-4 w-4" /> Retry
        </Button>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      {error ? <p role="alert" className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">{error}</p> : null}
      {vn30State.availability === 'partial' ? (
        <p className="text-sm text-warning" role="status">Partial data is usable. Missing coverage remains visible in Data Details.</p>
      ) : null}
      {currentAggregate?.usable ? (
        <p className="text-sm text-secondary-text" role="status">
          Current session: {currentDisplayStatus}
          {' · '}{currentAggregate.coverage.observedSymbolCount}/{currentAggregate.coverage.requestedSymbolCount} symbols
          {' · '}completed history remains authoritative below.
        </p>
      ) : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Foreign Flow primary KPIs">
        {kpis.map((item) => (
          <KpiCard
            key={item.label}
            label={item.label}
            value={item.value}
            formatted={item.value === null ? '—' : format(item.value)}
            state={vn30State.quality}
          />
        ))}
        <article className="rounded-xl border border-border/70 bg-card p-4" data-testid="foreign-flow-primary-kpi">
          <p className="text-sm font-medium text-secondary-text">Market breadth</p>
          <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-elevated" role="img"
            aria-label={`${breadth?.netBuyCount ?? 0} net-buy, ${breadth?.netSellCount ?? 0} net-sell, ${breadth?.zeroCount ?? 0} neutral, ${breadth?.unavailableCount ?? 0} unavailable`}>
            <span className="bg-success" style={{ flexGrow: breadth?.netBuyCount ?? 0 }} />
            <span className="bg-danger" style={{ flexGrow: breadth?.netSellCount ?? 0 }} />
            <span className="bg-border" style={{ flexGrow: breadth?.zeroCount ?? 0 }} />
            <span className="bg-secondary-text/30" style={{ flexGrow: breadth?.unavailableCount ?? 0 }} />
          </div>
          <p className="mt-3 text-sm">
            <span className="font-semibold text-success">+{breadth?.netBuyCount ?? 0} buy</span>
            <span className="mx-2 text-secondary-text">/</span>
            <span className="font-semibold text-danger">−{breadth?.netSellCount ?? 0} sell</span>
          </p>
          <p className="mt-1 text-xs text-secondary-text">
            {breadth?.zeroCount ?? 0} neutral · {breadth?.unavailableCount ?? 0} unavailable
          </p>
        </article>
      </section>

      <section className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(18rem,0.8fr)]">
        <div className="rounded-xl border border-border/70 bg-card p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold">Net foreign flow through latest session</h2>
              <p className="mt-1 text-xs text-secondary-text">Current provisional data is labelled; missing values remain gaps with no forward fill.</p>
            </div>
            <button type="button" className="text-xs text-secondary-text hover:text-foreground"
              aria-pressed={chartMode === 'buy-sell'}
              onClick={() => onChartModeChange(chartMode === 'buy-sell' ? 'net' : 'buy-sell')}>
              {chartMode === 'buy-sell' ? 'Show net only' : 'Show gross buy/sell'}
            </button>
          </div>
          <ForeignFlowSymbolHistoryChart rows={history} metric={metric} mode={chartMode} />
          {vn30.decomposition.anomalySessions.length ? (
            <p className="mt-2 text-xs text-warning">
              Anomaly markers: {vn30.decomposition.anomalySessions.filter((date) => history.some((row) => row.tradingDate === date)).join(', ') || 'outside selected window'}
            </p>
          ) : null}
        </div>
        <div className="grid gap-4 rounded-xl border border-border/70 bg-card p-4 sm:grid-cols-2 xl:grid-cols-1">
          <RankingPanel title="Top net bought" rows={rankings.buyers} metric={metric} onTicker={(ticker) => onNavigate('ticker', ticker)} />
          <RankingPanel title="Top net sold" rows={rankings.sellers} metric={metric} onTicker={(ticker) => onNavigate('ticker', ticker)} />
        </div>
      </section>

      <section className="rounded-xl border border-border/70 bg-card p-4" aria-labelledby="industry-leaders-heading">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 id="industry-leaders-heading" className="font-semibold">Industry leaders</h2>
            <p className="mt-1 text-xs text-secondary-text">Foreign net flow is primary; turnover is not used as a substitute.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => onNavigate('industry')}>View industries <ArrowRight className="h-4 w-4" /></Button>
        </div>
        {!industry || industryState?.availability === 'unavailable' ? (
          <p className="mt-3 rounded-lg bg-elevated/35 p-3 text-sm text-secondary-text">
            Industry summary unavailable. VN30 Overview remains usable.
          </p>
        ) : (
          <div className="mt-3 grid gap-x-6 sm:grid-cols-2 xl:grid-cols-3">
            {industries.map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-3 border-t border-border/50 py-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{item.label}</p>
                  <p className="text-[11px] text-secondary-text">
                    {item.contribution === null ? 'Contribution —' : `${formatForeignFlowPercent(item.contribution * 100)} contribution`}
                  </p>
                </div>
                <p className={cn('shrink-0 text-sm font-semibold tabular-nums', foreignFlowSignTextClass(item.value))}>{format(item.value)}</p>
              </div>
            ))}
          </div>
        )}
        {industryState?.availability === 'partial' ? <p className="mt-2 text-xs text-warning">Partial industry coverage remains visible.</p> : null}
      </section>

      <WatchlistOverview metric={metric} onOpen={() => onNavigate('watchlist')} />

      <button type="button" onClick={() => onNavigate('details')}
        className="flex w-full flex-wrap items-center justify-between gap-2 rounded-xl border border-border/70 bg-card px-4 py-3 text-left text-sm hover:bg-elevated/30">
        <span>
          <strong>SSI V3</strong> · Latest completed {latestSession ?? '—'} · Updated {vn30.fetchedAt}
        </span>
        <span className="flex flex-wrap items-center gap-2">
          {vn30State.availability === 'partial' ? <Badge variant="warning">Partial</Badge> : null}
          {vn30State.quality === 'anomaly_present' ? <Badge variant="warning">Anomaly</Badge> : null}
          {publicationLag ? <Badge variant="warning">Provider publication lag</Badge> : null}
          <span className="text-secondary-text">Data Details →</span>
        </span>
      </button>
    </div>
  );
};
