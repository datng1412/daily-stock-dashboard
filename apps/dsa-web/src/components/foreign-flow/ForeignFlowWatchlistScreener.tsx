import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Download, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import {
  stocksApi,
  type VietnamCurrentForeignFlowAggregateResponse,
  type VietnamForeignFlowWatchlistResponse,
  type VietnamForeignFlowWatchlistWindow,
} from '../../api/stocks';
import { Badge, Button, EmptyState, Input, Select } from '../common';
import {
  buildForeignFlowWatchlistCsv,
  foreignFlowWatchlistMetric,
  parseForeignFlowWatchlistInput,
  readForeignFlowWatchlistPreferences,
  selectForeignFlowWatchlistRows,
  summarizeForeignFlowWatchlist,
  writeForeignFlowWatchlistPreferences,
  type ForeignFlowWatchlistFilter,
  type ForeignFlowWatchlistSort,
} from './foreignFlowWatchlistModel';
import {
  downloadForeignFlowCsv,
  type ForeignFlowExplorerMetric,
} from './foreignFlowExplorerModel';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import { formatForeignFlowValue, formatForeignFlowVolume } from '../../utils/vietnamNumberFormat';
import { mapWatchlistFlowViewState } from './foreignFlowViewState';
import { applyCurrentWatchlistFlow } from './currentForeignFlowAggregateModel';

const windowOptions: VietnamForeignFlowWatchlistWindow[] = [1, 5, 20, 60];

const formatMetric = (value: number | null, metric: ForeignFlowExplorerMetric) => (
  metric === 'value' ? formatForeignFlowValue(value) : formatForeignFlowVolume(value)
);

const activeStreak = (buy?: number | null, sell?: number | null) => (
  buy === null || buy === undefined || sell === null || sell === undefined
    ? 'Insufficient data'
    : buy > 0 ? `Net buy ${buy}` : sell > 0 ? `Net sell ${sell}` : 'None'
);

export const ForeignFlowWatchlistScreener = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [initial] = useState(() => {
    const stored = readForeignFlowWatchlistPreferences(
      typeof globalThis.localStorage === 'undefined' ? null : globalThis.localStorage,
    );
    const query = searchParams.get('tickers');
    const queryTickers = query === null ? null : parseForeignFlowWatchlistInput(query).tickers;
    const metric = searchParams.get('metric');
    const window = Number(searchParams.get('window'));
    return {
      ...stored,
      tickers: queryTickers ?? stored.tickers,
      metric: metric === 'volume' || metric === 'value' ? metric : stored.metric,
      window: windowOptions.includes(window as VietnamForeignFlowWatchlistWindow)
        ? window as VietnamForeignFlowWatchlistWindow
        : stored.window,
    };
  }); // Query/local state precedence is intentionally evaluated once on entry.
  const [tickers, setTickers] = useState(initial.tickers);
  const [metric, setMetric] = useState<ForeignFlowExplorerMetric>(initial.metric);
  const [selectedWindow, setSelectedWindow] = useState<VietnamForeignFlowWatchlistWindow>(initial.window);
  const [filter, setFilter] = useState<ForeignFlowWatchlistFilter>(initial.filter);
  const [sort, setSort] = useState<ForeignFlowWatchlistSort>(initial.sort);
  const [direction, setDirection] = useState<'asc' | 'desc'>(initial.direction);
  const [search, setSearch] = useState('');
  const [draft, setDraft] = useState('');
  const [editorError, setEditorError] = useState<string | null>(null);
  const [data, setData] = useState<VietnamForeignFlowWatchlistResponse | null>(null);
  const [currentAggregate, setCurrentAggregate] = useState<VietnamCurrentForeignFlowAggregateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [presetLoading, setPresetLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const dataRef = useRef(data);
  dataRef.current = data;
  const scopeKey = tickers.join(',');

  useEffect(() => () => {
    requestIdRef.current += 1;
    abortRef.current?.abort();
  }, []);

  useEffect(() => {
    writeForeignFlowWatchlistPreferences(
      { tickers, metric, window: selectedWindow, filter, sort, direction },
      typeof globalThis.localStorage === 'undefined' ? null : globalThis.localStorage,
    );
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set('mode', 'watchlist');
      if (tickers.length) next.set('tickers', tickers.join(','));
      else next.delete('tickers');
      next.set('metric', metric);
      next.set('window', String(selectedWindow));
      return next;
    }, { replace: true });
  }, [direction, filter, metric, selectedWindow, setSearchParams, sort, tickers]);

  const load = useCallback(async (forceRefresh = false) => {
    requestIdRef.current += 1;
    const requestId = requestIdRef.current;
    abortRef.current?.abort();
    if (!tickers.length) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const response = await stocksApi.getVietnamForeignFlowWatchlist(tickers, {
        sessions: 60,
        forceRefresh,
        signal: controller.signal,
      });
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      const previous = dataRef.current;
      const sameScope = previous?.normalizedTickers.join(',') === scopeKey;
      const previousState = previous ? mapWatchlistFlowViewState(previous) : null;
      const responseState = mapWatchlistFlowViewState(response);
      if (forceRefresh && sameScope && previousState?.usable && !responseState.usable) {
        setError('Refresh returned no usable rows. Previous usable data is preserved.');
      } else {
        setData(response);
      }
    } catch (caught) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setError(caught instanceof Error ? caught.message : 'Watchlist foreign flow is unavailable.');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        if (abortRef.current === controller) abortRef.current = null;
      }
    }
  }, [scopeKey, tickers]);

  useEffect(() => {
    void load(false);
  }, [load]);

  useEffect(() => {
    if (!tickers.length) {
      setCurrentAggregate(null);
      return undefined;
    }
    let inFlight = false;
    let wasHidden = document.visibilityState === 'hidden';
    let controller: AbortController | null = null;
    const request = () => {
      if (inFlight || document.visibilityState === 'hidden') return;
      inFlight = true;
      controller = new AbortController();
      void stocksApi.getVietnamCurrentForeignFlowAggregate({
        scope: 'watchlist',
        tickers,
        includeIndustries: false,
        signal: controller.signal,
      }).then((response) => {
        if (!controller?.signal.aborted && response.usable) {
          setCurrentAggregate(response);
        }
      }).catch(() => {
        // Preserve the last usable current-session snapshot on transient failures.
      }).finally(() => {
        inFlight = false;
      });
    };
    const handleVisibility = () => {
      if (document.visibilityState === 'hidden') {
        wasHidden = true;
        return;
      }
      if (wasHidden) {
        wasHidden = false;
        request();
      }
    };
    const initial = globalThis.setTimeout(request, 0);
    const timer = globalThis.setInterval(request, 15_000);
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      globalThis.clearTimeout(initial);
      globalThis.clearInterval(timer);
      document.removeEventListener('visibilitychange', handleVisibility);
      controller?.abort();
    };
  }, [data?.fetchedAt, scopeKey, tickers]);

  const currentData = data?.normalizedTickers.join(',') === scopeKey ? data : null;
  const effectiveItems = useMemo(
    () => applyCurrentWatchlistFlow(currentData?.items ?? [], currentAggregate),
    [currentAggregate, currentData?.items],
  );
  const selectedRows = useMemo(
    () => selectForeignFlowWatchlistRows(effectiveItems, {
      metric, window: selectedWindow, filter, search, sort, direction,
    }),
    [direction, effectiveItems, filter, metric, search, selectedWindow, sort],
  );
  const summary = useMemo(
    () => summarizeForeignFlowWatchlist(effectiveItems, metric, selectedWindow),
    [effectiveItems, metric, selectedWindow],
  );

  const addDraft = () => {
    const parsed = parseForeignFlowWatchlistInput(draft, tickers);
    if (parsed.invalid.length) {
      setEditorError(`Invalid ticker${parsed.invalid.length > 1 ? 's' : ''}: ${parsed.invalid.join(', ')}`);
      return;
    }
    if (parsed.limitedCount) {
      setEditorError('Watchlist is limited to 30 tickers.');
      return;
    }
    setTickers(parsed.tickers);
    setDraft('');
    setEditorError(parsed.duplicateCount ? `${parsed.duplicateCount} duplicate ticker ignored.` : null);
  };

  const loadVn30Preset = async () => {
    setPresetLoading(true);
    setEditorError(null);
    try {
      const response = await stocksApi.getVietnamIndexComponents('VN30', 'HOSE');
      const parsed = parseForeignFlowWatchlistInput(
        response.rows.map((row) => row.symbol ?? ''),
      );
      if (response.status !== 'ok' || !parsed.tickers.length) {
        setEditorError('SSI VN30 membership is unavailable.');
        return;
      }
      setTickers(parsed.tickers);
    } catch (caught) {
      setEditorError(caught instanceof Error ? caught.message : 'SSI VN30 membership is unavailable.');
    } finally {
      setPresetLoading(false);
    }
  };

  const exportCsv = () => {
    const csv = buildForeignFlowWatchlistCsv(selectedRows, metric, selectedWindow);
    downloadForeignFlowCsv(csv, `stockclock-foreign-watchlist-${metric}-${selectedWindow}d.csv`);
  };

  return (
    <div className="space-y-4">
      <section className="space-y-3 rounded-xl border border-border/70 bg-card p-4" aria-label="Watchlist editor">
        <div className="flex flex-wrap items-start gap-3">
          <label className="min-w-64 flex-1 text-sm">
            <span className="mb-1 block font-medium">Add tickers</span>
            <textarea
              aria-label="Add tickers"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  addDraft();
                }
              }}
              placeholder="FPT, SSI, HPG"
              className="min-h-20 w-full rounded-lg border border-border bg-background px-3 py-2 text-foreground"
            />
          </label>
          <div className="flex flex-wrap gap-2 pt-6">
            <Button onClick={addDraft} disabled={!draft.trim() || loading}>
              <Plus className="h-4 w-4" /> Add
            </Button>
            <Button variant="outline" onClick={() => void loadVn30Preset()} isLoading={presetLoading}>
              Use SSI VN30
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setTickers([]);
                setEditorError(null);
              }}
              disabled={!tickers.length || loading}
            >
              <Trash2 className="h-4 w-4" /> Clear watchlist
            </Button>
          </div>
        </div>
        {editorError ? <p role="alert" className="text-sm text-danger">{editorError}</p> : null}
        <div className="flex flex-wrap gap-2" aria-label="Current watchlist">
          {tickers.map((ticker) => (
            <span key={ticker} className="inline-flex items-center gap-1 rounded-full bg-elevated px-3 py-1 text-sm">
              {ticker}
              <button
                type="button"
                aria-label={`Remove ${ticker}`}
                onClick={() => setTickers((current) => current.filter((item) => item !== ticker))}
                disabled={loading}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ))}
          <span className="text-sm text-secondary-text">{tickers.length}/30 symbols</span>
        </div>
      </section>

      {tickers.length ? (
        <section className="space-y-3 rounded-xl border border-border/70 bg-card p-4" aria-label="Watchlist screener controls">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Input label="Search ticker" value={search} onChange={(event) => setSearch(event.target.value.toUpperCase())} />
            <Select label="Filter" value={filter} onChange={(value) => setFilter(value as ForeignFlowWatchlistFilter)}
              options={[
                { value: 'all', label: 'All' },
                { value: 'net_buyers', label: 'Net buyers' },
                { value: 'net_sellers', label: 'Net sellers' },
                { value: 'active_buy_streak', label: 'Active net-buy streak' },
                { value: 'active_sell_streak', label: 'Active net-sell streak' },
                { value: 'stale', label: 'Stale' },
                { value: 'partial', label: 'Partial' },
                { value: 'unavailable', label: 'Unavailable' },
                { value: 'anomaly', label: 'Anomaly present' },
              ]} />
            <Select label="Sort" value={sort} onChange={(value) => setSort(value as ForeignFlowWatchlistSort)}
              options={[
                { value: 'input', label: 'Watchlist order' },
                { value: 'ticker', label: 'Ticker' },
                { value: 'latest_session', label: 'Latest session' },
                { value: 'net_1d', label: 'Net 1D' },
                { value: 'net_5d', label: 'Net 5D' },
                { value: 'net_20d', label: 'Net 20D' },
                { value: 'net_60d', label: 'Net 60D' },
                { value: 'streak', label: 'Streak length' },
                { value: 'freshness', label: 'Freshness' },
                { value: 'anomaly', label: 'Anomaly' },
              ]} />
            <Select label="Direction" value={direction} onChange={(value) => setDirection(value as 'asc' | 'desc')}
              options={[{ value: 'asc', label: 'Ascending' }, { value: 'desc', label: 'Descending' }]} />
            <div className="flex items-end gap-2">
              <Button variant="outline" onClick={() => void load(true)} isLoading={loading} disabled={loading}>
                <RefreshCw className="h-4 w-4" /> Force Refresh
              </Button>
              <Button variant="outline" onClick={exportCsv} disabled={!selectedRows.length}>
                <Download className="h-4 w-4" /> CSV
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Watchlist metric">
              {(['value', 'volume'] as const).map((item) => (
                <button key={item} type="button" aria-pressed={metric === item}
                  className={`rounded-md px-3 py-1.5 text-sm ${metric === item ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}
                  onClick={() => setMetric(item)}>{item === 'value' ? 'Value' : 'Volume'}</button>
              ))}
            </div>
            <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Watchlist window">
              {windowOptions.map((item) => (
                <button key={item} type="button" aria-pressed={selectedWindow === item}
                  className={`rounded-md px-3 py-1.5 text-sm ${selectedWindow === item ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}
                  onClick={() => setSelectedWindow(item)}>{item}D</button>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {!tickers.length ? (
        <EmptyState
          title="Create a foreign-flow watchlist"
          description="Add up to 30 tickers or explicitly load the current SSI-derived VN30 membership. No symbols are loaded by default."
        />
      ) : null}
      {loading && !currentData ? <div className="h-32 animate-pulse rounded-xl bg-elevated/50" aria-label="Loading watchlist foreign flow" /> : null}
      {error ? <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</div> : null}

      {currentData ? (
        <>
          <section className="grid gap-2 sm:grid-cols-4 xl:grid-cols-8" aria-label="Watchlist summary">
            {[
              ['Total', summary.total],
              ['Ready', summary.ready],
              ['Partial', summary.partial],
              ['Unavailable', summary.unavailable],
              ['Net-buy', summary.netBuy],
              ['Net-sell', summary.netSell],
              ['Anomaly', summary.anomaly],
              ['Source session', summary.sourceSession ?? '—'],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-xl border border-border/70 bg-card p-3">
                <p className="text-xs text-secondary-text">{label}</p>
                <p className="mt-1 font-semibold">{value}</p>
              </div>
            ))}
          </section>
          <p className="text-xs text-secondary-text">
            Provider {currentData.provider} {currentData.providerVersion} · cache {currentData.cacheState} ·
            accepted completed history plus newer provisional current flow.
            {currentAggregate?.usable
              ? ` Current coverage ${currentAggregate.coverage.observedSymbolCount}/${currentAggregate.coverage.requestedSymbolCount}.`
              : ''}
            {' '}Metric, window, filter, sort, and CSV changes are local.
          </p>
          <section className="overflow-x-auto rounded-xl border border-border/70 bg-card" aria-label="Watchlist foreign flow table">
            <table className="min-w-full text-sm">
              <thead className="bg-elevated/50 text-secondary-text">
                <tr>
                  {['Ticker', 'Latest session', 'Net 1D', 'Net 5D', 'Net 20D', 'Net 60D', 'Active streak', 'Freshness', 'Data quality'].map((label) => (
                    <th key={label} className={`px-3 py-2 ${label.startsWith('Net') ? 'text-right' : 'text-left'}`}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {selectedRows.map((item) => (
                  <tr key={item.ticker} className="border-t border-border/60">
                    <td className="px-3 py-2 font-semibold">
                      <a
                        className="text-cyan hover:underline"
                        href={`/vietnam/foreign-flow?mode=ticker&ticker=${encodeURIComponent(item.ticker)}&metric=${metric}&window=${selectedWindow}`}
                      >
                        {item.ticker}
                      </a>
                    </td>
                    <td className="px-3 py-2">{item.latestSession ?? '—'}</td>
                    {windowOptions.map((itemWindow) => {
                      const value = foreignFlowWatchlistMetric(item, metric, itemWindow);
                      return <td key={itemWindow} className={`px-3 py-2 text-right tabular-nums ${foreignFlowSignTextClass(value)}`}>{formatMetric(value, metric)}</td>;
                    })}
                    <td className="px-3 py-2">{activeStreak(item.buyStreak, item.sellStreak)}</td>
                    <td className="px-3 py-2">
                      <span>{item.sourceFreshness}</span>
                      {item.sourceSessionLag ? <span className="block text-xs text-secondary-text">Observed lag {item.sourceSessionLag}</span> : null}
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant={item.availability === 'ready' ? 'success' : item.availability === 'partial' ? 'warning' : 'danger'}>
                        {item.availability}
                      </Badge>
                      {item.displayStatus ? (
                        <span className="block text-xs text-secondary-text">
                          {item.displayStatus} · {item.displayCoverage}
                        </span>
                      ) : null}
                      {item.containsProviderAnomaly ? <span className="ml-1 text-xs text-warning">Anomaly</span> : null}
                      {item.failureClass ? <span className="block text-xs text-secondary-text">{item.failureClass}</span> : null}
                      <span className="block text-xs text-secondary-text">{item.actualSessionCount}/60 sessions</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!selectedRows.length ? <p className="p-5 text-sm text-secondary-text">No rows match the current search and filter.</p> : null}
          </section>
        </>
      ) : null}
    </div>
  );
};

export default ForeignFlowWatchlistScreener;
