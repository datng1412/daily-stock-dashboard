import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Download, RefreshCw, Search } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import {
  stocksApi,
  type VietnamFlowDataResponse,
  type VietnamForeignFlowSymbolHistoryResponse,
  type VietnamVn30ForeignFlowResponse,
} from '../api/stocks';
import { AppPage, Badge, Button, EmptyState, Input, PageHeader, Select } from '../components/common';
import { ForeignFlowSymbolHistoryChart, type SymbolForeignFlowChartMode } from '../components/foreign-flow/ForeignFlowSymbolHistoryChart';
import { ForeignFlowSymbolHistoryTable } from '../components/foreign-flow/ForeignFlowSymbolHistoryTable';
import { ForeignFlowWatchlistScreener } from '../components/foreign-flow/ForeignFlowWatchlistScreener';
import {
  buildForeignFlowCsv,
  downloadForeignFlowCsv,
  explorerDateBounds,
  selectForeignFlowWindow,
  sumNullable,
  type ForeignFlowExplorerMetric,
  type ForeignFlowExplorerMode,
  type ForeignFlowExplorerWindow,
} from '../components/foreign-flow/foreignFlowExplorerModel';
import type { SymbolForeignFlowMetricRow } from '../components/foreign-flow/foreignFlowSymbolAnalyticsModel';
import { formatForeignFlowPercent, formatForeignFlowValue, formatForeignFlowVolume } from '../utils/vietnamNumberFormat';
import { normalizeVietnamTicker } from '../utils/vietnamWatchlist';

type ExplorerData =
  | { mode: 'ticker'; payload: VietnamForeignFlowSymbolHistoryResponse }
  | { mode: 'vn30'; payload: VietnamVn30ForeignFlowResponse }
  | { mode: 'industry' | 'proprietary'; payload: VietnamFlowDataResponse };

type FlowRow = Record<string, unknown> & {
  tradingDate?: string;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
  proprietaryBuyVolume?: number | null;
  proprietarySellVolume?: number | null;
  proprietaryNetVolume?: number | null;
  proprietaryBuyValue?: number | null;
  proprietarySellValue?: number | null;
  proprietaryNetValue?: number | null;
};
type RankedRow = { label: string; net: number | null; turnover?: number | null; coverage?: number | null };

const MODES: Array<{ value: ForeignFlowExplorerMode; label: string }> = [
  { value: 'watchlist', label: 'Watchlist · Danh sách theo dõi' },
  { value: 'ticker', label: 'Ticker' },
  { value: 'vn30', label: 'Current VN30 basket' },
  { value: 'industry', label: 'Industry' },
  { value: 'proprietary', label: 'Proprietary' },
];
const WINDOWS: ForeignFlowExplorerWindow[] = ['1', '5', '20', '60', 'custom'];
const STORAGE_KEY = 'stockclock.vn.foreignFlowExplorer.preferences.v1';
const TICKER_RE = /^[A-Z0-9]{1,10}$/;

const readPreference = <T extends string>(key: string, allowed: readonly T[], fallback: T): T => {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Record<string, unknown>;
    return allowed.includes(parsed[key] as T) ? parsed[key] as T : fallback;
  } catch {
    return fallback;
  }
};
const readTickerPreference = () => {
  try {
    const value = (JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Record<string, unknown>).ticker;
    return typeof value === 'string' ? normalizeVietnamTicker(value) : '';
  } catch {
    return '';
  }
};

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const text = (value: unknown) => typeof value === 'string' ? value : '';
const dateOf = (row: FlowRow) => text(row.tradingDate || row.date);
const anomalyOf = (row: FlowRow) => Boolean(
  row.suspiciousZeroSession || row.containsProviderAnomaly || row.anomaly || row.anomalyCode,
);
const numberOf = (row: FlowRow, key: string) => finite(row[key]) ? row[key] as number : null;
const fieldsFor = (metric: ForeignFlowExplorerMetric) => metric === 'value'
  ? ['foreignBuyValue', 'foreignSellValue', 'foreignNetValue'] as const
  : ['foreignBuyVolume', 'foreignSellVolume', 'foreignNetVolume'] as const;

const toFlowRows = (data: ExplorerData | null): FlowRow[] => {
  if (!data) return [];
  if (data.mode === 'ticker') return data.payload.rows as FlowRow[];
  if (data.mode === 'vn30') return data.payload.decomposition.series as FlowRow[];
  if (data.mode === 'proprietary') {
    return (data.payload.rows ?? []).map((rawRow) => {
      const row = rawRow as FlowRow;
      return {
        ...row,
        foreignBuyVolume: row.proprietaryBuyVolume,
        foreignSellVolume: row.proprietarySellVolume,
        foreignNetVolume: row.proprietaryNetVolume,
        foreignBuyValue: row.proprietaryBuyValue,
        foreignSellValue: row.proprietarySellValue,
        foreignNetValue: row.proprietaryNetValue,
      };
    });
  }
  return (data.payload.rows ?? []) as FlowRow[];
};

const aggregateBySession = (rows: FlowRow[], metric: ForeignFlowExplorerMetric): SymbolForeignFlowMetricRow[] => {
  const [buyKey, sellKey, netKey] = fieldsFor(metric);
  const grouped = new Map<string, FlowRow[]>();
  rows.forEach((row) => {
    const date = dateOf(row);
    if (date) grouped.set(date, [...(grouped.get(date) ?? []), row]);
  });
  let cumulative = 0;
  return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([tradingDate, entries]) => {
    const buy = sumNullable(entries.map((row) => numberOf(row, buyKey)));
    const sell = sumNullable(entries.map((row) => numberOf(row, sellKey)));
    const net = sumNullable(entries.map((row) => numberOf(row, netKey)));
    if (net !== null) cumulative += net;
    const present = [buy, sell, net].filter((value) => value !== null).length;
    return {
      tradingDate,
      buy,
      sell,
      net,
      rolling5: null,
      rolling20: null,
      cumulative: net === null ? null : cumulative,
      usable: net !== null,
      sign: net === null ? 'unavailable' : net > 0 ? 'positive' : net < 0 ? 'negative' : 'zero',
      state: present === 0 ? 'unavailable' : present === 3 ? 'ready' : 'partial',
      unit: metric === 'value' ? 'VND' : 'shares',
    };
  });
};

const sumMetric = (rows: FlowRow[], metric: ForeignFlowExplorerMetric, side: 'buy' | 'sell' | 'net') => {
  const key = fieldsFor(metric)[side === 'buy' ? 0 : side === 'sell' ? 1 : 2];
  return sumNullable(rows.map((row) => numberOf(row, key)));
};

const formatMetric = (value: number | null, metric: ForeignFlowExplorerMetric) => (
  metric === 'value' ? formatForeignFlowValue(value) : formatForeignFlowVolume(value)
);

const ForeignFlowPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedMode = searchParams.get('mode');
  const initialMode = MODES.some((item) => item.value === requestedMode)
    ? requestedMode as ForeignFlowExplorerMode
    : searchParams.get('scope') === 'vn30'
      ? 'vn30'
      : readPreference('mode', MODES.map((item) => item.value), 'watchlist');
  const [mode, setMode] = useState<ForeignFlowExplorerMode>(initialMode);
  const [window, setWindow] = useState<ForeignFlowExplorerWindow>(() => {
    const requested = searchParams.get('window') as ForeignFlowExplorerWindow | null;
    return requested && WINDOWS.includes(requested) ? requested : readPreference('window', WINDOWS, '20');
  });
  const [metric, setMetric] = useState<ForeignFlowExplorerMetric>(() => {
    const requested = searchParams.get('metric');
    return requested === 'volume' || requested === 'value'
      ? requested
      : readPreference('metric', ['value', 'volume'], 'value');
  });
  const initialTicker = normalizeVietnamTicker(searchParams.get('ticker') ?? readTickerPreference());
  const [tickerDraft, setTickerDraft] = useState(initialTicker);
  const [ticker, setTicker] = useState(TICKER_RE.test(initialTicker) ? initialTicker : '');
  const [proprietaryTarget, setProprietaryTarget] = useState('index:VNINDEX');
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [customFrom, setCustomFrom] = useState(() => {
    const date = new Date();
    date.setUTCDate(date.getUTCDate() - 30);
    return date.toISOString().slice(0, 10);
  });
  const [customTo, setCustomTo] = useState(today);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [chartMode, setChartMode] = useState<SymbolForeignFlowChartMode>('net');
  const [data, setData] = useState<ExplorerData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    document.title = 'Foreign Flow Explorer';
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ mode, window, metric, ticker }));
  }, [metric, mode, ticker, window]);

  const validationError = useMemo(() => {
    if (mode === 'watchlist') return null;
    if (mode === 'ticker' && tickerDraft && !TICKER_RE.test(normalizeVietnamTicker(tickerDraft))) {
      return 'Ticker must contain 1–10 letters or digits.';
    }
    try {
      explorerDateBounds(window, customFrom, customTo);
      return null;
    } catch (caught) {
      return caught instanceof Error ? caught.message : 'Invalid date range.';
    }
  }, [customFrom, customTo, mode, tickerDraft, window]);

  const load = useCallback(async (forceRefresh = false) => {
    if (mode === 'watchlist') {
      setData(null);
      setError(null);
      return;
    }
    if (mode === 'ticker' && !ticker) {
      setData(null);
      setError(null);
      return;
    }
    let bounds: { fromDate: string; toDate: string };
    try {
      bounds = explorerDateBounds(window, customFrom, customTo);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Invalid date range.');
      return;
    }
    requestId.current += 1;
    const currentRequest = requestId.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      let next: ExplorerData;
      if (mode === 'ticker') {
        const payload = await stocksApi.getVietnamForeignFlowSymbolHistory(ticker, {
          ...(window === 'custom'
            ? { fromDate: bounds.fromDate, toDate: bounds.toDate }
            : { limit: Number(window) }),
          forceRefresh,
          signal: controller.signal,
        });
        next = { mode, payload };
      } else if (mode === 'vn30') {
        next = {
          mode,
          payload: await stocksApi.getVietnamVn30ForeignFlow({
            topN: 10,
            forceRefresh,
            signal: controller.signal,
          }),
        };
      } else if (mode === 'industry') {
        next = {
          mode,
          payload: await stocksApi.getVietnamIndustryFlow({
            indexCode: 'VN30',
            fromDate: bounds.fromDate,
            toDate: bounds.toDate,
          }, { signal: controller.signal }),
        };
      } else {
        const [scope, identifier] = proprietaryTarget.split(':') as ['board' | 'index', string];
        next = {
          mode,
          payload: await stocksApi.getVietnamProprietaryFlow(scope, identifier, {
            fromDate: bounds.fromDate,
            toDate: bounds.toDate,
            forceRefresh,
            signal: controller.signal,
          }),
        };
      }
      if (currentRequest === requestId.current && !controller.signal.aborted) setData(next);
    } catch (caught) {
      if (controller.signal.aborted || currentRequest !== requestId.current) return;
      setError(caught instanceof Error ? caught.message : 'Foreign-flow data is unavailable.');
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  }, [customFrom, customTo, mode, proprietaryTarget, ticker, window]);

  useEffect(() => {
    void load(false);
    return () => abortRef.current?.abort();
  }, [load]);

  const rawRows = useMemo(() => toFlowRows(data), [data]);
  const selection = useMemo(
    () => selectForeignFlowWindow(rawRows, window, dateOf, anomalyOf, customFrom, customTo),
    [customFrom, customTo, rawRows, window],
  );
  const chartRows = useMemo(() => aggregateBySession(selection.rows, metric), [metric, selection.rows]);
  const totalBuy = sumMetric(selection.rows, metric, 'buy');
  const totalSell = sumMetric(selection.rows, metric, 'sell');
  const totalNet = sumMetric(selection.rows, metric, 'net');
  const validNetSessions = chartRows.filter((row) => row.net !== null).length;
  const averageNet = totalNet === null || validNetSessions === 0 ? null : totalNet / validNetSessions;

  const provenance = useMemo(() => {
    if (!data) return null;
    if (data.mode === 'ticker') return {
      source: data.payload.source,
      endpoint: data.payload.sourceEndpoint,
      fetchedAt: data.payload.fetchedAt,
      cache: 'not exposed',
      freshness: data.payload.freshness,
      state: data.payload.dataState,
    };
    if (data.mode === 'vn30') return {
      source: data.payload.source,
      endpoint: data.payload.sourceEndpoint,
      fetchedAt: data.payload.fetchedAt,
      cache: `${data.payload.cache.status} · ${data.payload.cache.ageSeconds}s`,
      freshness: data.payload.decomposition.latest?.freshness
        ?? (data.payload.decomposition.latestCompletedSession ? 'latest_completed' : 'unknown'),
      state: data.payload.dataState,
    };
    const latestFlowRow = (data.payload.rows ?? []).at(-1) as Record<string, unknown> | undefined;
    return {
      source: data.payload.source,
      endpoint: data.payload.endpoint ?? '—',
      fetchedAt: data.payload.fetchedAt ?? '—',
      cache: `${data.payload.cache?.status ?? 'unknown'} · ${data.payload.cache?.ageSeconds ?? '—'}s`,
      freshness: text(latestFlowRow?.freshnessStatus)
        || (selection.sessionDates.length ? 'latest_completed' : 'unknown'),
      state: data.payload.status,
    };
  }, [data, selection.sessionDates]);

  const rankedRows = useMemo<RankedRow[]>(() => {
    if (!data || (data.mode !== 'vn30' && data.mode !== 'industry')) return [];
    if (data.mode === 'vn30') {
      const key = metric === 'value'
        ? window === '60' ? 'foreignNetValue60d' : window === '20' ? 'foreignNetValue20d' : window === '5' ? 'foreignNetValue5d' : 'foreignNetValue'
        : window === '60' ? 'foreignNetVolume60d' : window === '20' ? 'foreignNetVolume20d' : window === '5' ? 'foreignNetVolume5d' : 'foreignNetVolume';
      return data.payload.components
        .map((row) => ({ label: row.ticker, net: finite(row[key]) ? row[key] as number : null }))
        .filter((row) => row.net !== null)
        .sort((left, right) => (right.net ?? 0) - (left.net ?? 0));
    }
    const grouped = new Map<string, { label: string; net: number[]; turnover: number[]; coverage: number[] }>();
    selection.rows.forEach((row) => {
      const code = text(row.icbCode) || 'unclassified';
      const current = grouped.get(code) ?? { label: text(row.icbName) || code, net: [], turnover: [], coverage: [] };
      const net = numberOf(row, fieldsFor(metric)[2]);
      const turnover = numberOf(row, metric === 'value' ? 'matchedValue' : 'matchedVolume');
      const coverage = numberOf(row, 'coverageRatio');
      if (net !== null) current.net.push(net);
      if (turnover !== null) current.turnover.push(turnover);
      if (coverage !== null) current.coverage.push(coverage);
      grouped.set(code, current);
    });
    return [...grouped.entries()].map(([code, item]): RankedRow => ({
      label: `${item.label} (${code})`,
      net: item.net.length ? item.net.reduce((sum, value) => sum + value, 0) : null,
      turnover: item.turnover.length ? item.turnover.reduce((sum, value) => sum + value, 0) : null,
      coverage: item.coverage.length ? item.coverage.reduce((sum, value) => sum + value, 0) / item.coverage.length : null,
    })).sort((left, right) => (right.net ?? Number.NEGATIVE_INFINITY) - (left.net ?? Number.NEGATIVE_INFINITY));
  }, [data, metric, selection.rows, window]);
  const vn30Latest = data?.mode === 'vn30'
    ? data.payload.decomposition.latest ?? data.payload.decomposition.series.at(-1) ?? null
    : null;

  const applyTicker = () => {
    const normalized = normalizeVietnamTicker(tickerDraft);
    if (!TICKER_RE.test(normalized)) {
      setError('Ticker must contain 1–10 letters or digits.');
      return;
    }
    setTicker(normalized);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set('ticker', normalized);
      next.set('mode', 'ticker');
      return next;
    });
  };

  const exportCsv = () => {
    const csv = buildForeignFlowCsv(selection.rows, { mode, metric, window });
    const subject = mode === 'ticker' ? ticker.toLowerCase() : mode === 'proprietary' ? proprietaryTarget.replace(':', '-').toLowerCase() : mode;
    downloadForeignFlowCsv(csv, `stockclock-${mode === 'proprietary' ? 'proprietary' : 'foreign'}-${subject}-${window}d.csv`);
  };

  return (
    <AppPage className="space-y-5">
      <PageHeader
        eyebrow="Vietnam · SSI FastConnect V3"
        title="Foreign Flow Explorer"
        description="Inspect provider-backed completed-session foreign and proprietary flow without converting missing values to zero."
        actions={mode === 'watchlist' ? undefined : (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => void load(true)} isLoading={loading} disabled={Boolean(validationError) || (mode === 'ticker' && !ticker)}>
              <RefreshCw className="h-4 w-4" /> Force Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={exportCsv} disabled={!selection.rows.length}>
              <Download className="h-4 w-4" /> Export CSV
            </Button>
          </div>
        )}
      />

      <section className="space-y-4 rounded-xl border border-border/70 bg-card p-4" aria-label="Foreign Flow Explorer controls">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Explorer mode">
          {MODES.map((item) => (
            <button key={item.value} type="button" aria-pressed={mode === item.value}
              className={`rounded-lg px-3 py-2 text-sm font-medium ${mode === item.value ? 'bg-cyan/15 text-cyan' : 'bg-elevated/40 text-secondary-text hover:text-foreground'}`}
              onClick={() => {
                setMode(item.value);
                setData(null);
                setSearchParams((current) => {
                  const next = new URLSearchParams(current);
                  next.set('mode', item.value);
                  return next;
                });
              }}>
              {item.label}
            </button>
          ))}
        </div>
        {mode !== 'watchlist' ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {mode === 'ticker' ? (
            <Input label="Ticker" value={tickerDraft} placeholder="Enter ticker"
              onChange={(event) => setTickerDraft(normalizeVietnamTicker(event.target.value))}
              onKeyDown={(event) => { if (event.key === 'Enter') applyTicker(); }}
              error={validationError ?? undefined}
              trailingAction={<button type="button" aria-label="Load ticker" onClick={applyTicker}><Search className="h-4 w-4" /></button>} />
          ) : null}
          {mode === 'proprietary' ? (
            <Select label="Supported scope" value={proprietaryTarget} onChange={setProprietaryTarget}
              options={[
                { value: 'index:VNINDEX', label: 'VNINDEX' },
                { value: 'index:VN30', label: 'VN30' },
                { value: 'board:HOSE', label: 'HOSE' },
              ]} />
          ) : null}
          <Select label="Sort direction" value={sortDirection} onChange={(value) => setSortDirection(value as 'asc' | 'desc')}
            options={[{ value: 'desc', label: 'Highest first' }, { value: 'asc', label: 'Lowest first' }]} />
          <Select label="Chart" value={chartMode} onChange={(value) => setChartMode(value as SymbolForeignFlowChartMode)}
            options={[
              { value: 'net', label: 'Net flow' },
              { value: 'buy-sell', label: 'Gross buy / sell' },
              { value: 'cumulative', label: 'Cumulative net' },
            ]} />
        </div> : null}
        {mode !== 'watchlist' ? <div className="flex flex-wrap gap-3">
          <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Time window">
            {WINDOWS.map((item) => <button key={item} type="button" aria-pressed={window === item}
              className={`rounded-md px-3 py-1.5 text-sm ${window === item ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}
              onClick={() => setWindow(item)}>{item === 'custom' ? 'Custom' : `${item}D`}</button>)}
          </div>
          <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Metric">
            {(['value', 'volume'] as const).map((item) => <button key={item} type="button" aria-pressed={metric === item}
              className={`rounded-md px-3 py-1.5 text-sm ${metric === item ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}
              onClick={() => setMetric(item)}>{item === 'value' ? 'Value' : 'Volume'}</button>)}
          </div>
          {window === 'custom' ? (
            <>
              <Input aria-label="Custom start date" type="date" value={customFrom} max={customTo} onChange={(event) => setCustomFrom(event.target.value)} />
              <Input aria-label="Custom end date" type="date" value={customTo} min={customFrom} max={today} onChange={(event) => setCustomTo(event.target.value)} />
            </>
          ) : null}
        </div> : null}
      </section>

      {mode === 'watchlist' ? <ForeignFlowWatchlistScreener /> : null}

      {mode === 'ticker' && !ticker ? (
        <EmptyState icon={<Search className="h-8 w-8" />} title="Enter a ticker"
          description="No fixed ticker or watchlist is loaded automatically." />
      ) : null}
      {loading && !data ? <div className="h-32 animate-pulse rounded-xl bg-elevated/50" aria-label="Loading foreign flow" /> : null}
      {error ? <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</div> : null}

      {data ? (
        <>
          <section className="grid gap-2 rounded-xl border border-border/70 bg-card p-4 text-sm md:grid-cols-3 xl:grid-cols-6" aria-label="Provenance and freshness">
            <div><span className="text-secondary-text">Source</span><p>{provenance?.source}</p></div>
            <div><span className="text-secondary-text">Endpoint</span><p>{provenance?.endpoint}</p></div>
            <div><span className="text-secondary-text">Source session</span><p>{selection.sessionDates.at(-1) ?? '—'}</p></div>
            <div><span className="text-secondary-text">Fetched at</span><p>{provenance?.fetchedAt}</p></div>
            <div><span className="text-secondary-text">Cache</span><p>{provenance?.cache}</p></div>
            <div><span className="text-secondary-text">Source freshness</span><p>{provenance?.freshness}</p></div>
          </section>

          {mode === 'vn30' ? (
            <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
              <strong>Dòng tiền ngoại rổ VN30 hiện tại / Current VN30 basket foreign flow</strong> · membership source: SSI IndexComponents ·
              aggregation mode: CURRENT_MEMBERSHIP_DECOMPOSITION · historical_constituent_correct = false.
              Direct VN30 capability is secondary: {(data as Extract<ExplorerData, { mode: 'vn30' }>).payload.canonical.capabilityStatus}.
            </div>
          ) : null}
          {mode === 'industry' ? (
            <div className="rounded-lg border border-border/70 bg-card p-3 text-sm text-secondary-text">
              Industry flow is bounded to current VN30 membership. Turnover is trading activity, not foreign net cash flow.
              Current-session industry flow remains unavailable.
            </div>
          ) : null}

          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6" aria-label="Selected window summary">
            {[
              ['Gross buy', totalBuy],
              ['Gross sell', totalSell],
              ['Net flow', totalNet],
              ['Average / valid session', averageNet],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-xl border border-border/70 bg-card p-4">
                <p className="text-xs text-secondary-text">{label}</p>
                <p className="mt-1 font-semibold tabular-nums">{formatMetric(value as number | null, metric)}</p>
              </div>
            ))}
            <div className="rounded-xl border border-border/70 bg-card p-4">
              <p className="text-xs text-secondary-text">Session coverage</p>
              <p className="mt-1 font-semibold">{selection.actualSessionCount}/{selection.requestedSessionCount ?? selection.actualSessionCount}</p>
              <p className="text-xs text-secondary-text">{selection.complete ? 'Complete' : 'Incomplete'}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-card p-4">
              <p className="text-xs text-secondary-text">Quality</p>
              <p className="mt-1 font-semibold">{selection.containsProviderAnomaly ? 'Anomaly present' : 'Clean'}</p>
              <p className="text-xs text-secondary-text">{selection.anomalySessions.join(', ') || 'No labelled anomaly'}</p>
            </div>
          </section>

          {mode === 'vn30' && data.mode === 'vn30' && vn30Latest ? (
            <section className="rounded-xl border border-border/70 bg-card p-4" aria-label="VN30 breadth">
              <h2 className="font-semibold">Breadth and coverage</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge>Members {data.payload.membership.memberCount}</Badge>
                <Badge>Expected 30</Badge>
                <Badge>Net buy {vn30Latest.valueBreadth?.netBuyCount ?? '—'}</Badge>
                <Badge>Net sell {vn30Latest.valueBreadth?.netSellCount ?? '—'}</Badge>
                <Badge>Neutral {vn30Latest.valueBreadth?.zeroCount ?? '—'}</Badge>
                <Badge>Unavailable {vn30Latest.valueBreadth?.unavailableCount ?? '—'}</Badge>
                <Badge>Coverage {vn30Latest.valueCoverageRatio === null || vn30Latest.valueCoverageRatio === undefined ? '—' : formatForeignFlowPercent(vn30Latest.valueCoverageRatio * 100)}</Badge>
              </div>
            </section>
          ) : null}

          <section className="rounded-xl border border-border/70 bg-card p-4">
            <ForeignFlowSymbolHistoryChart rows={chartRows} metric={metric} mode={chartMode} />
          </section>

          {rankedRows.length ? (
            <section className="rounded-xl border border-border/70 bg-card p-4" aria-label={`${mode} rankings`}>
              <h2 className="font-semibold">{mode === 'industry' ? 'Industry rankings' : 'Component rankings'}</h2>
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead><tr className="text-secondary-text"><th className="p-2 text-left">Name</th><th className="p-2 text-right">Net</th>{mode === 'industry' ? <><th className="p-2 text-right">Turnover</th><th className="p-2 text-right">Coverage</th></> : null}</tr></thead>
                  <tbody>{[...rankedRows].sort((left, right) => sortDirection === 'desc' ? (right.net ?? 0) - (left.net ?? 0) : (left.net ?? 0) - (right.net ?? 0)).map((row) => (
                    <tr key={row.label} className="border-t border-border/60">
                      <td className="p-2">{row.label}</td><td className="p-2 text-right tabular-nums">{formatMetric(row.net, metric)}</td>
                      {mode === 'industry' ? <><td className="p-2 text-right tabular-nums">{formatMetric(row.turnover ?? null, metric)}</td><td className="p-2 text-right">{row.coverage === null || row.coverage === undefined ? '—' : formatForeignFlowPercent(row.coverage * 100)}</td></> : null}
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </section>
          ) : null}

          <section className="rounded-xl border border-border/70 bg-card p-4">
            <ForeignFlowSymbolHistoryTable rows={chartRows} metric={metric} />
          </section>
          <p className="text-xs text-secondary-text">
            Availability: {provenance?.state} · requested sessions: {selection.requestedSessionCount ?? 'custom'} ·
            actual sessions: {selection.actualSessionCount} · missing: {selection.missingSessions ?? 'not derivable'}.
            Provider numeric zero remains zero; missing values remain —.
          </p>
        </>
      ) : null}
    </AppPage>
  );
};

export default ForeignFlowPage;
