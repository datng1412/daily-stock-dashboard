import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Download, RefreshCw, Search } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import {
  stocksApi,
  type VietnamCurrentForeignFlowAggregateResponse,
  type VietnamCurrentForeignFlowResponse,
  type VietnamFlowDataResponse,
  type VietnamForeignFlowSymbolHistoryResponse,
  type VietnamVn30ForeignFlowResponse,
} from '../api/stocks';
import { AppPage, Badge, Button, EmptyState, Input, PageHeader, Select } from '../components/common';
import { ForeignFlowSymbolHistoryChart, type SymbolForeignFlowChartMode } from '../components/foreign-flow/ForeignFlowSymbolHistoryChart';
import { ForeignFlowSymbolHistoryTable } from '../components/foreign-flow/ForeignFlowSymbolHistoryTable';
import { ForeignFlowWatchlistScreener } from '../components/foreign-flow/ForeignFlowWatchlistScreener';
import { ForeignFlowOverview } from '../components/foreign-flow/ForeignFlowOverview';
import { ForeignFlowDataDetails } from '../components/foreign-flow/ForeignFlowDataDetails';
import LatestForeignFlowCard from '../components/foreign-flow/LatestForeignFlowCard';
import { mergeCurrentFlowSessionDisplayRow } from '../components/foreign-flow/currentForeignFlowTableModel';
import {
  mergeCurrentAggregateRows,
  type ForeignFlowDisplayRow,
} from '../components/foreign-flow/currentForeignFlowAggregateModel';
import {
  selectForeignFlowDisplayStatus,
  selectLatestForeignFlowSession,
  type ForeignFlowCurrentState,
} from '../components/foreign-flow/latestForeignFlowSessionModel';
import {
  mapIndustryFlowViewState,
  mapProprietaryFlowViewState,
  mapTickerFlowViewState,
  mapVn30FlowViewState,
  type FlowViewState,
} from '../components/foreign-flow/foreignFlowViewState';
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
type DataMode = Exclude<ForeignFlowExplorerMode, 'watchlist'>;
type PageMode = ForeignFlowExplorerMode | 'overview' | 'details';
type ModeRequestState = {
  data: ExplorerData | null;
  loading: boolean;
  error: string | null;
  scopeKey: string | null;
};
type ModeStateMap = Record<DataMode, ModeRequestState>;

type FlowRow = ForeignFlowDisplayRow & {
  tradingDate?: string | null;
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

const CURRENT_FLOW_POLL_INTERVAL_MS = 15_000;

const MODES: Array<{ value: PageMode; label: string }> = [
  { value: 'overview', label: 'Overview' },
  { value: 'vn30', label: 'Stocks' },
  { value: 'industry', label: 'Industries' },
  { value: 'watchlist', label: 'Watchlist' },
  { value: 'proprietary', label: 'Proprietary' },
  { value: 'details', label: 'Data Details' },
];
const PAGE_MODES: PageMode[] = ['overview', 'ticker', 'vn30', 'industry', 'watchlist', 'proprietary', 'details'];
const WINDOWS: ForeignFlowExplorerWindow[] = ['1', '5', '20', '60', 'custom'];
const STORAGE_KEY = 'stockclock.vn.foreignFlowExplorer.preferences.v1';
const TICKER_RE = /^[A-Z0-9]{1,10}$/;
const DATA_MODES: DataMode[] = ['ticker', 'vn30', 'industry', 'proprietary'];
const initialModeStates = (): ModeStateMap => Object.fromEntries(
  DATA_MODES.map((item) => [item, {
    data: null,
    loading: false,
    error: null,
    scopeKey: null,
  }]),
) as ModeStateMap;

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
const CURRENT_FLOW_STATES: ForeignFlowCurrentState[] = [
  'waiting',
  'ready',
  'stale',
  'market_closed',
  'unavailable',
  'error',
];
const currentStateOf = (value: unknown): ForeignFlowCurrentState | null => (
  typeof value === 'string' && CURRENT_FLOW_STATES.includes(value as ForeignFlowCurrentState)
    ? value as ForeignFlowCurrentState
    : null
);
const sumCount = (rows: FlowRow[], key: keyof FlowRow): number | null => {
  const values = rows.map((row) => row[key]).filter(finite);
  return values.length ? values.reduce((sum, value) => sum + value, 0) : null;
};

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
    const semantic = entries.find((row) => (
      row.sourceKind === 'current'
      || row.finality === 'current_session_provisional'
      || row.isCurrent === true
    )) ?? entries.find((row) => (
      row.sourceKind === 'completed'
      || row.finality === 'completed_accepted'
      || row.isCompleted === true
    ));
    const isCurrent = Boolean(
      semantic?.sourceKind === 'current'
      || semantic?.finality === 'current_session_provisional'
      || semantic?.isCurrent === true,
    );
    const hasSemantics = Boolean(semantic);
    const sourceKind = hasSemantics ? isCurrent ? 'current' : 'completed' : undefined;
    const finality = hasSemantics
      ? isCurrent ? 'current_session_provisional' : 'completed_accepted'
      : undefined;
    const currentState = isCurrent
      ? currentStateOf(semantic?.currentState ?? semantic?.dataState)
      : null;
    const providerStatus = isCurrent ? text(semantic?.providerStatus) || currentState : null;
    const displayStatus = hasSemantics
      ? selectForeignFlowDisplayStatus({
        sourceKind,
        finality,
        currentState,
        providerStatus,
        usable: present > 0,
        hasUsableValues: present > 0,
      })
      : undefined;
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
      ...(hasSemantics ? {
        displayOrigin: isCurrent ? 'current_session_provisional' as const : 'completed_session' as const,
        sourceKind,
        source: text(semantic?.source) || null,
        finality,
        currentState,
        providerStatus,
        displayStatus,
        statusLabel: displayStatus,
        isCurrent,
        isCompleted: !isCurrent,
        isPartial: entries.some((row) => row.isPartial === true) || present < 3,
        isStale: isCurrent && (
          entries.some((row) => row.isStale === true)
          || currentState === 'stale'
        ),
        requestedCount: sumCount(entries, 'requestedCount'),
        observedCount: sumCount(entries, 'observedCount'),
        completeValueCount: sumCount(entries, 'completeValueCount'),
        completeVolumeCount: sumCount(entries, 'completeVolumeCount'),
        providerTime: text(semantic?.providerTime) || null,
        receivedAt: text(semantic?.receivedAt) || null,
      } : {}),
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

const viewStateFor = (data: ExplorerData | null): FlowViewState | null => {
  if (!data) return null;
  if (data.mode === 'ticker') return mapTickerFlowViewState(data.payload);
  if (data.mode === 'vn30') return mapVn30FlowViewState(data.payload);
  if (data.mode === 'industry') return mapIndustryFlowViewState(data.payload);
  return mapProprietaryFlowViewState(data.payload);
};

const safeFailureMessage = (failureClass: string | null) => {
  if (failureClass === 'network_error' || failureClass === 'dns_error'
    || failureClass === 'connection_refused' || failureClass === 'proxy_error'
    || failureClass === 'tls_error') {
    return 'Không thể kết nối tới nguồn dữ liệu. Vui lòng thử lại sau.';
  }
  if (failureClass === 'request_timeout' || failureClass === 'connect_timeout'
    || failureClass === 'read_timeout') {
    return 'Nguồn dữ liệu phản hồi quá chậm. Vui lòng thử lại sau.';
  }
  if (failureClass === 'authentication_failed' || failureClass === 'authentication'
    || failureClass === 'entitlement_unavailable' || failureClass === 'authorization') {
    return 'Quyền truy cập nguồn dữ liệu hiện không khả dụng.';
  }
  return 'Nguồn dữ liệu hiện chưa thể cung cấp kết quả cho yêu cầu này.';
};

const ForeignFlowPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedMode = searchParams.get('mode');
  const initialMode = PAGE_MODES.includes(requestedMode as PageMode)
    ? requestedMode as PageMode
    : searchParams.get('scope') === 'vn30'
      ? 'vn30'
      : 'overview';
  const [mode, setMode] = useState<PageMode>(initialMode);
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
  const [currentFlow, setCurrentFlow] = useState<{
    symbol: string;
    data: VietnamCurrentForeignFlowResponse | null;
    loading: boolean;
    error: string | null;
  }>({ symbol: '', data: null, loading: false, error: null });
  const [currentFlowRefreshGeneration, setCurrentFlowRefreshGeneration] = useState(0);
  const [currentAggregateRefreshGeneration, setCurrentAggregateRefreshGeneration] = useState(0);
  const [currentAggregate, setCurrentAggregate] = useState<{
    data: VietnamCurrentForeignFlowAggregateResponse | null;
    loading: boolean;
    error: string | null;
  }>({ data: null, loading: false, error: null });
  const [modeStates, setModeStates] = useState<ModeStateMap>(initialModeStates);
  const modeStatesRef = useRef(modeStates);
  const requestIds = useRef<Record<DataMode, number>>({
    ticker: 0,
    vn30: 0,
    industry: 0,
    proprietary: 0,
  });
  const abortRefs = useRef<Record<DataMode, AbortController | null>>({
    ticker: null,
    vn30: null,
    industry: null,
    proprietary: null,
  });
  const activeState = DATA_MODES.includes(mode as DataMode) ? modeStates[mode as DataMode] : null;
  const data = activeState?.data ?? null;
  const loading = activeState?.loading ?? false;
  const error = activeState?.error ?? null;
  const viewState = useMemo(() => viewStateFor(data), [data]);

  const updateModeState = useCallback((
    targetMode: DataMode,
    update: (current: ModeRequestState) => ModeRequestState,
  ) => {
    setModeStates((current) => ({
      ...current,
      [targetMode]: update(current[targetMode]),
    }));
  }, []);

  useEffect(() => {
    document.title = 'Foreign Flow Explorer';
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ mode, window, metric, ticker }));
  }, [metric, mode, ticker, window]);

  useEffect(() => {
    modeStatesRef.current = modeStates;
  }, [modeStates]);

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

  const loadMode = useCallback(async (
    requestMode: DataMode,
    forceRefresh = false,
  ) => {
    if (requestMode === 'ticker' && !ticker) {
      updateModeState('ticker', (current) => ({ ...current, error: null }));
      return;
    }
    let bounds: { fromDate: string; toDate: string };
    try {
      bounds = explorerDateBounds(
        requestMode === 'industry' && window !== 'custom' ? '60' : window,
        customFrom,
        customTo,
      );
    } catch (caught) {
      updateModeState(requestMode, (current) => ({
        ...current,
        error: caught instanceof Error ? caught.message : 'Invalid date range.',
      }));
      return;
    }
    const scopeKey = requestMode === 'ticker'
      ? `${ticker}:${window}:${bounds.fromDate}:${bounds.toDate}`
      : requestMode === 'vn30'
        ? 'VN30'
        : requestMode === 'industry'
          ? `VN30:${bounds.fromDate}:${bounds.toDate}`
          : `${proprietaryTarget}:${bounds.fromDate}:${bounds.toDate}`;
    const previous = modeStatesRef.current[requestMode];
    if (!forceRefresh && previous.scopeKey === scopeKey && viewStateFor(previous.data)?.usable) {
      return;
    }
    requestIds.current[requestMode] += 1;
    const currentRequest = requestIds.current[requestMode];
    abortRefs.current[requestMode]?.abort();
    const controller = new AbortController();
    abortRefs.current[requestMode] = controller;
    updateModeState(requestMode, (current) => ({
      ...current,
      loading: true,
      error: null,
    }));
    try {
      let next: ExplorerData;
      if (requestMode === 'ticker') {
        const payload = await stocksApi.getVietnamForeignFlowSymbolHistory(ticker, {
          ...(window === 'custom'
            ? { fromDate: bounds.fromDate, toDate: bounds.toDate }
            : { limit: Number(window) }),
          forceRefresh,
          signal: controller.signal,
        });
        next = { mode: requestMode, payload };
      } else if (requestMode === 'vn30') {
        next = {
          mode: requestMode,
          payload: await stocksApi.getVietnamVn30ForeignFlow({
            topN: 10,
            forceRefresh,
            signal: controller.signal,
          }),
        };
      } else if (requestMode === 'industry') {
        next = {
          mode: requestMode,
          payload: await stocksApi.getVietnamIndustryFlow({
            indexCode: 'VN30',
            fromDate: bounds.fromDate,
            toDate: bounds.toDate,
          }, { signal: controller.signal }),
        };
      } else {
        const [scope, identifier] = proprietaryTarget.split(':') as ['board' | 'index', string];
        next = {
          mode: requestMode,
          payload: await stocksApi.getVietnamProprietaryFlow(scope, identifier, {
            fromDate: bounds.fromDate,
            toDate: bounds.toDate,
            forceRefresh,
            signal: controller.signal,
          }),
        };
      }
      if (
        currentRequest === requestIds.current[requestMode]
        && !controller.signal.aborted
      ) {
        const nextViewState = viewStateFor(next);
        updateModeState(requestMode, (current) => {
          const preserveUsable = forceRefresh
            && current.scopeKey === scopeKey
            && Boolean(viewStateFor(current.data)?.usable)
            && nextViewState?.availability === 'unavailable';
          return preserveUsable
            ? {
              ...current,
              loading: false,
              error: safeFailureMessage(nextViewState.failureClass),
            }
            : {
              data: next,
              loading: false,
              error: null,
              scopeKey,
            };
        });
      }
    } catch (caught) {
      if (
        controller.signal.aborted
        || currentRequest !== requestIds.current[requestMode]
      ) return;
      updateModeState(requestMode, (current) => ({
        ...current,
        error: caught instanceof Error ? caught.message : 'Foreign-flow data is unavailable.',
      }));
    } finally {
      if (currentRequest === requestIds.current[requestMode]) {
        updateModeState(requestMode, (current) => ({ ...current, loading: false }));
      }
    }
  }, [customFrom, customTo, proprietaryTarget, ticker, updateModeState, window]);

  const load = useCallback(async (forceRefresh = false) => {
    if (mode === 'overview' || mode === 'details') {
      await Promise.all([
        loadMode('vn30', forceRefresh),
        loadMode('industry', forceRefresh),
      ]);
      return;
    }
    if (DATA_MODES.includes(mode as DataMode)) {
      await loadMode(mode as DataMode, forceRefresh);
    }
  }, [loadMode, mode]);

  useEffect(() => {
    void load(false);
    const requestModes: DataMode[] = mode === 'overview' || mode === 'details'
      ? ['vn30', 'industry']
      : DATA_MODES.includes(mode as DataMode)
        ? [mode as DataMode]
        : [];
    if (!requestModes.length) return undefined;
    const modeAbortRefs = abortRefs.current;
    const modeRequestIds = requestIds.current;
    return () => {
      requestModes.forEach((requestMode) => {
        modeAbortRefs[requestMode]?.abort();
        modeRequestIds[requestMode] += 1;
      });
    };
  }, [load, mode]);

  useEffect(() => {
    if (mode !== 'ticker' || !ticker) return undefined;
    let inFlight = false;
    let controller: AbortController | null = null;
    let wasHidden = document.visibilityState === 'hidden';
    const request = (forceRefresh = false) => {
      if (inFlight || document.visibilityState === 'hidden') return;
      inFlight = true;
      controller = new AbortController();
      setCurrentFlow((current) => ({
        symbol: ticker,
        data: current.symbol === ticker ? current.data : null,
        loading: true,
        error: null,
      }));
      void stocksApi.getVietnamCurrentForeignFlow(ticker, {
        forceRefresh,
        signal: controller.signal,
      })
        .then((payload) => {
          if (!controller?.signal.aborted) {
            setCurrentFlow({ symbol: ticker, data: payload, loading: false, error: null });
          }
        })
        .catch((caught: unknown) => {
          if (!controller?.signal.aborted) {
            setCurrentFlow((current) => ({
              ...current,
              symbol: ticker,
              loading: false,
              error: caught instanceof Error
                ? 'Foreign flow could not be loaded.'
                : 'Foreign flow unavailable.',
            }));
          }
        })
        .finally(() => {
          inFlight = false;
        });
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        wasHidden = true;
        return;
      }
      if (!wasHidden) return;
      wasHidden = false;
      request(true);
    };
    const initialRequest = globalThis.setTimeout(
      () => request(currentFlowRefreshGeneration > 0),
      0,
    );
    const timer = globalThis.setInterval(() => request(false), CURRENT_FLOW_POLL_INTERVAL_MS);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      globalThis.clearTimeout(initialRequest);
      globalThis.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      controller?.abort();
    };
  }, [currentFlowRefreshGeneration, mode, ticker]);

  useEffect(() => {
    if (!['overview', 'details', 'vn30', 'industry'].includes(mode)) return undefined;
    let inFlight = false;
    let controller: AbortController | null = null;
    let wasHidden = document.visibilityState === 'hidden';
    const request = (forceRefresh = false) => {
      if (inFlight || document.visibilityState === 'hidden') return;
      inFlight = true;
      controller = new AbortController();
      setCurrentAggregate((current) => ({ ...current, loading: true, error: null }));
      void stocksApi.getVietnamCurrentForeignFlowAggregate({
        scope: 'vn30',
        includeIndustries: true,
        forceRefresh,
        signal: controller.signal,
      }).then((payload) => {
        if (!controller?.signal.aborted) {
          setCurrentAggregate((previous) => ({
            data: payload.usable ? payload : previous.data,
            loading: false,
            error: null,
          }));
        }
      }).catch(() => {
        if (!controller?.signal.aborted) {
          setCurrentAggregate((previous) => ({
            ...previous,
            loading: false,
            error: 'Current-session aggregate is unavailable; completed sessions remain visible.',
          }));
        }
      }).finally(() => {
        inFlight = false;
      });
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        wasHidden = true;
        return;
      }
      if (!wasHidden) return;
      wasHidden = false;
      request(true);
    };
    const initialRequest = globalThis.setTimeout(
      () => request(currentAggregateRefreshGeneration > 0),
      0,
    );
    const timer = globalThis.setInterval(() => request(false), CURRENT_FLOW_POLL_INTERVAL_MS);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      globalThis.clearTimeout(initialRequest);
      globalThis.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      controller?.abort();
    };
  }, [currentAggregateRefreshGeneration, mode]);

  const rawRows = useMemo(() => {
    const completedRows = toFlowRows(data);
    if (!data) return completedRows;
    if (data.mode !== 'vn30' && data.mode !== 'industry') return completedRows;
    return mergeCurrentAggregateRows(
      completedRows,
      currentAggregate.data,
      data.mode,
    );
  }, [currentAggregate.data, data]);
  const selection = useMemo(
    () => selectForeignFlowWindow(rawRows, window, dateOf, anomalyOf, customFrom, customTo),
    [customFrom, customTo, rawRows, window],
  );
  const chartRows = useMemo(() => aggregateBySession(selection.rows, metric), [metric, selection.rows]);
  const currentFlowData = currentFlow.symbol === ticker ? currentFlow.data : null;
  const latestCompletedTickerSession = useMemo(() => {
    if (!data || data.mode !== 'ticker') return null;
    const candidates = [
      ...data.payload.rows,
      ...(data.payload.latestRow ? [data.payload.latestRow] : []),
    ].filter((row) => /^\d{4}-\d{2}-\d{2}$/.test(row.tradingDate));
    const latest = candidates.reduce<(typeof candidates)[number] | null>(
      (selected, row) => !selected || row.tradingDate > selected.tradingDate ? row : selected,
      null,
    );
    return latest ? {
      sessionDate: latest.tradingDate,
      source: 'SSI DailyStockPrice',
      foreignBuyVolume: latest.foreignBuyVolume,
      foreignSellVolume: latest.foreignSellVolume,
      foreignNetVolume: latest.foreignNetVolume,
      foreignBuyValue: latest.foreignBuyValue,
      foreignSellValue: latest.foreignSellValue,
      foreignNetValue: latest.foreignNetValue,
    } : null;
  }, [data]);
  const latestTickerSession = useMemo(
    () => selectLatestForeignFlowSession({
      completed: latestCompletedTickerSession,
      current: currentFlowData,
    }),
    [currentFlowData, latestCompletedTickerSession],
  );
  const detailRows = useMemo(
    () => mode === 'ticker'
      ? mergeCurrentFlowSessionDisplayRow(
        chartRows,
        currentFlowData,
        metric,
        latestCompletedTickerSession?.sessionDate,
      )
      : chartRows,
    [chartRows, currentFlowData, latestCompletedTickerSession?.sessionDate, metric, mode],
  );
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
      cache: `${data.payload.cacheState ?? 'unknown'} · ${data.payload.cacheAgeSeconds ?? '—'}s`,
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
      const currentByTicker = new Map(
        (currentAggregate.data?.items ?? []).map((row) => [row.symbol, row]),
      );
      return data.payload.components
        .map((row) => {
          const currentWindow = currentByTicker.get(row.ticker)?.displayWindows?.[
            window === 'custom' ? '60' : window
          ];
          const currentValue = currentWindow?.[
            metric === 'value' ? 'foreignNetValue' : 'foreignNetVolume'
          ];
          return {
            label: row.ticker,
            net: finite(currentValue)
              ? currentValue
              : finite(row[key]) ? row[key] as number : null,
          };
        })
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
  }, [currentAggregate.data?.items, data, metric, selection.rows, window]);
  const vn30Latest = data?.mode === 'vn30'
    ? data.payload.decomposition.latest ?? data.payload.decomposition.series.at(-1) ?? null
    : null;

  const applyTicker = () => {
    const normalized = normalizeVietnamTicker(tickerDraft);
    if (!TICKER_RE.test(normalized)) {
      updateModeState('ticker', (current) => ({
        ...current,
        error: 'Ticker must contain 1–10 letters or digits.',
      }));
      return;
    }
    setTicker(normalized);
    setMode('ticker');
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set('ticker', normalized);
      next.set('mode', 'ticker');
      return next;
    });
  };

  const navigateTo = (target: PageMode, selectedTicker?: string) => {
    if (selectedTicker) {
      const normalized = normalizeVietnamTicker(selectedTicker);
      setTickerDraft(normalized);
      setTicker(normalized);
    }
    setMode(target);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set('mode', target);
      if (selectedTicker) next.set('ticker', normalizeVietnamTicker(selectedTicker));
      return next;
    });
  };

  const exportCsv = () => {
    if (!DATA_MODES.includes(mode as DataMode)) return;
    const csv = buildForeignFlowCsv(selection.rows, { mode: mode as ForeignFlowExplorerMode, metric, window });
    const subject = mode === 'ticker' ? ticker.toLowerCase() : mode === 'proprietary' ? proprietaryTarget.replace(':', '-').toLowerCase() : mode;
    downloadForeignFlowCsv(csv, `stockclock-${mode === 'proprietary' ? 'proprietary' : 'foreign'}-${subject}-${window}d.csv`);
  };

  return (
    <AppPage className="space-y-5">
      <PageHeader
        eyebrow="Vietnam · SSI FastConnect V3"
        title="Foreign Flow Explorer"
        description="Inspect provider-backed foreign and proprietary flow while keeping current and completed session finality explicit."
        actions={DATA_MODES.includes(mode as DataMode) ? (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => {
              void load(true);
              if (mode === 'ticker' && ticker) {
                setCurrentFlowRefreshGeneration((current) => current + 1);
              } else if (['vn30', 'industry'].includes(mode)) {
                setCurrentAggregateRefreshGeneration((current) => current + 1);
              }
            }} isLoading={loading} disabled={Boolean(validationError) || (mode === 'ticker' && !ticker)}>
              <RefreshCw className="h-4 w-4" /> Force Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={exportCsv} disabled={!selection.rows.length}>
              <Download className="h-4 w-4" /> Export CSV
            </Button>
          </div>
        ) : undefined}
      />

      <section className="space-y-4 rounded-xl border border-border/70 bg-card p-4" aria-label="Foreign Flow Explorer controls">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Explorer mode">
          {MODES.map((item) => (
            <button key={item.value} type="button" aria-pressed={mode === item.value}
              className={`rounded-lg px-3 py-2 text-sm font-medium ${mode === item.value ? 'bg-cyan/15 text-cyan' : 'bg-elevated/40 text-secondary-text hover:text-foreground'}`}
              onClick={() => {
                if (mode === item.value) return;
                navigateTo(item.value);
              }}>
              {item.label}
            </button>
          ))}
        </div>
        {mode === 'overview' ? (
          <div className="grid items-end gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(12rem,1fr)_auto_auto_minmax(10rem,auto)_auto]">
            <Select label="Universe" value="vn30" onChange={() => undefined}
              options={[{ value: 'vn30', label: 'Current VN30 basket' }]} />
            <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Time window">
              {WINDOWS.filter((item) => item !== 'custom').map((item) => <button key={item} type="button" aria-pressed={window === item}
                className={`rounded-md px-3 py-1.5 text-sm ${window === item ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}
                onClick={() => setWindow(item)}>{item}D</button>)}
            </div>
            <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Metric">
              {(['value', 'volume'] as const).map((item) => <button key={item} type="button" aria-pressed={metric === item}
                className={`rounded-md px-3 py-1.5 text-sm ${metric === item ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}
                onClick={() => setMetric(item)}>{item === 'value' ? 'Value' : 'Volume'}</button>)}
            </div>
            <div className="text-sm">
              <span className="block text-xs text-secondary-text">Latest completed</span>
              <span className="font-medium">{(modeStates.vn30.data?.mode === 'vn30'
                ? modeStates.vn30.data.payload.decomposition.latestCompletedSession
                : null) ?? '—'}</span>
            </div>
            <Button variant="outline" size="sm" onClick={() => {
              void load(true);
              setCurrentAggregateRefreshGeneration((current) => current + 1);
            }}
              isLoading={modeStates.vn30.loading || modeStates.industry.loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
          </div>
        ) : null}
        {DATA_MODES.includes(mode as DataMode) ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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
        {DATA_MODES.includes(mode as DataMode) ? <div className="flex flex-wrap gap-3">
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

      {mode === 'overview' ? (
        <ForeignFlowOverview
          vn30={modeStates.vn30.data?.mode === 'vn30' ? modeStates.vn30.data.payload : null}
          industry={modeStates.industry.data?.mode === 'industry' ? modeStates.industry.data.payload : null}
          currentAggregate={currentAggregate.data}
          loading={modeStates.vn30.loading || modeStates.industry.loading}
          error={modeStates.vn30.error ?? modeStates.industry.error}
          metric={metric}
          window={window}
          chartMode={chartMode === 'buy-sell' ? 'buy-sell' : 'net'}
          onChartModeChange={setChartMode}
          onRefresh={() => {
            void load(true);
            setCurrentAggregateRefreshGeneration((current) => current + 1);
          }}
          onNavigate={navigateTo}
        />
      ) : null}

      {mode === 'details' ? (
        <ForeignFlowDataDetails
          vn30={modeStates.vn30.data?.mode === 'vn30' ? modeStates.vn30.data.payload : null}
          industry={modeStates.industry.data?.mode === 'industry' ? modeStates.industry.data.payload : null}
          currentAggregate={currentAggregate.data}
        />
      ) : null}

      {mode === 'watchlist' ? <ForeignFlowWatchlistScreener /> : null}

      {mode === 'ticker' && !ticker ? (
        <EmptyState icon={<Search className="h-8 w-8" />} title="Enter a ticker"
          description="No fixed ticker or watchlist is loaded automatically." />
      ) : null}
      {loading && !data ? <div className="h-32 animate-pulse rounded-xl bg-elevated/50" aria-label="Loading foreign flow" /> : null}
      {error ? <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</div> : null}
      {mode === 'ticker' && ticker ? (
        <LatestForeignFlowCard
          view={latestTickerSession}
          loading={(loading && !data) || (currentFlow.symbol === ticker && currentFlow.loading)}
          error={currentFlow.symbol === ticker ? currentFlow.error : null}
        />
      ) : null}

      {data && viewState?.availability === 'unavailable' && !viewState.usable ? (
        <section
          className="rounded-xl border border-warning/30 bg-warning/10 p-5"
          aria-label={`${mode} foreign flow unavailable`}
        >
          <p className="text-xs font-medium uppercase tracking-wide text-secondary-text">
            {MODES.find((item) => item.value === mode)?.label ?? mode}
          </p>
          <h2 className="mt-1 text-lg font-semibold">Dữ liệu hiện không khả dụng</h2>
          <p className="mt-2 text-sm text-secondary-text">
            {safeFailureMessage(viewState.failureClass)}
          </p>
          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
            <div><dt className="text-secondary-text">Source</dt><dd>{provenance?.source ?? '—'}</dd></div>
            <div><dt className="text-secondary-text">Fetched at</dt><dd>{provenance?.fetchedAt ?? '—'}</dd></div>
            <div><dt className="text-secondary-text">Cache</dt><dd>{provenance?.cache ?? '—'}</dd></div>
          </dl>
        </section>
      ) : null}

      {data && viewState?.availability !== 'unavailable' && !viewState?.usable ? (
        <EmptyState
          title="No completed-session records"
          description="The provider request succeeded, but no records were returned for this selection."
        />
      ) : null}

      {data && viewState?.usable && viewState.availability === 'partial' ? (
        <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm" role="status">
          Partial data is available. Missing coverage remains visible and is not converted to zero.
        </div>
      ) : null}

      {data && viewState?.usable ? (
        <>
          <section className="grid gap-2 rounded-xl border border-border/70 bg-card p-4 text-sm md:grid-cols-3 xl:grid-cols-6" aria-label="Provenance and freshness">
            <div><span className="text-secondary-text">Source</span><p>{provenance?.source}</p></div>
            <div><span className="text-secondary-text">Endpoint</span><p>{provenance?.endpoint}</p></div>
            <div><span className="text-secondary-text">{mode === 'ticker' ? 'Latest session' : 'Latest display session'}</span><p>{mode === 'ticker' ? latestTickerSession?.sessionDate ?? '—' : selection.sessionDates.at(-1) ?? '—'}</p></div>
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
              Current-session totals use observed SSI ForeignRoomMessage rows only; missing members are excluded and coverage stays visible.
            </div>
          ) : null}

          {mode !== 'ticker' ? <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6" aria-label="Selected window summary">
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
          </section> : null}

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
            <ForeignFlowSymbolHistoryTable rows={detailRows} metric={metric} />
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
