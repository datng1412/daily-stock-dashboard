import type {
  VietnamForeignFlowWatchlistItem,
  VietnamForeignFlowWatchlistWindow,
} from '../../api/stocks';
import {
  buildForeignFlowCsv,
  type ForeignFlowExplorerMetric,
} from './foreignFlowExplorerModel';
import {
  normalizeVietnamTicker,
  VIETNAM_WATCHLIST_MAX_SIZE,
} from '../../utils/vietnamWatchlist';

export const FOREIGN_FLOW_WATCHLIST_STORAGE_KEY = 'stockclock.vn.foreignFlowWatchlist.v1';

export type ForeignFlowWatchlistFilter =
  | 'all'
  | 'net_buyers'
  | 'net_sellers'
  | 'active_buy_streak'
  | 'active_sell_streak'
  | 'stale'
  | 'partial'
  | 'unavailable'
  | 'anomaly';

export type ForeignFlowWatchlistSort =
  | 'input'
  | 'ticker'
  | 'latest_session'
  | 'net_1d'
  | 'net_5d'
  | 'net_20d'
  | 'net_60d'
  | 'streak'
  | 'freshness'
  | 'anomaly';

export type ForeignFlowWatchlistPreferences = {
  tickers: string[];
  metric: ForeignFlowExplorerMetric;
  window: VietnamForeignFlowWatchlistWindow;
  filter: ForeignFlowWatchlistFilter;
  sort: ForeignFlowWatchlistSort;
  direction: 'asc' | 'desc';
};

export const DEFAULT_FOREIGN_FLOW_WATCHLIST_PREFERENCES: ForeignFlowWatchlistPreferences = {
  tickers: [],
  metric: 'value',
  window: 20,
  filter: 'all',
  sort: 'input',
  direction: 'asc',
};

const TICKER_RE = /^[A-Z0-9]{1,10}$/;
const FILTERS: ForeignFlowWatchlistFilter[] = [
  'all', 'net_buyers', 'net_sellers', 'active_buy_streak', 'active_sell_streak',
  'stale', 'partial', 'unavailable', 'anomaly',
];
const SORTS: ForeignFlowWatchlistSort[] = [
  'input', 'ticker', 'latest_session', 'net_1d', 'net_5d', 'net_20d',
  'net_60d', 'streak', 'freshness', 'anomaly',
];
const WINDOWS: VietnamForeignFlowWatchlistWindow[] = [1, 5, 20, 60];

export const parseForeignFlowWatchlistInput = (
  input: string | string[],
  existing: string[] = [],
) => {
  const values = Array.isArray(input) ? input : input.split(/[\s,]+/);
  const tickers = [...existing];
  const seen = new Set(tickers);
  const invalid: string[] = [];
  let duplicateCount = 0;
  let limitedCount = 0;
  values.forEach((raw) => {
    if (!String(raw).trim()) return;
    const ticker = normalizeVietnamTicker(String(raw));
    if (!TICKER_RE.test(ticker) || ticker === 'ALL') {
      invalid.push(String(raw).trim());
      return;
    }
    if (seen.has(ticker)) {
      duplicateCount += 1;
      return;
    }
    if (tickers.length >= VIETNAM_WATCHLIST_MAX_SIZE) {
      limitedCount += 1;
      return;
    }
    seen.add(ticker);
    tickers.push(ticker);
  });
  return { tickers, invalid, duplicateCount, limitedCount };
};

export const readForeignFlowWatchlistPreferences = (
  storage: Pick<Storage, 'getItem'> | null,
): ForeignFlowWatchlistPreferences => {
  if (!storage) return DEFAULT_FOREIGN_FLOW_WATCHLIST_PREFERENCES;
  try {
    const raw = storage.getItem(FOREIGN_FLOW_WATCHLIST_STORAGE_KEY);
    if (!raw) return DEFAULT_FOREIGN_FLOW_WATCHLIST_PREFERENCES;
    const parsed = JSON.parse(raw) as Partial<ForeignFlowWatchlistPreferences>;
    const tickers = parseForeignFlowWatchlistInput(
      Array.isArray(parsed.tickers) ? parsed.tickers.filter((value): value is string => typeof value === 'string') : [],
    ).tickers;
    return {
      tickers,
      metric: parsed.metric === 'volume' ? 'volume' : 'value',
      window: WINDOWS.includes(parsed.window as VietnamForeignFlowWatchlistWindow)
        ? parsed.window as VietnamForeignFlowWatchlistWindow
        : 20,
      filter: FILTERS.includes(parsed.filter as ForeignFlowWatchlistFilter)
        ? parsed.filter as ForeignFlowWatchlistFilter
        : 'all',
      sort: SORTS.includes(parsed.sort as ForeignFlowWatchlistSort)
        ? parsed.sort as ForeignFlowWatchlistSort
        : 'input',
      direction: parsed.direction === 'desc' ? 'desc' : 'asc',
    };
  } catch {
    return DEFAULT_FOREIGN_FLOW_WATCHLIST_PREFERENCES;
  }
};

export const writeForeignFlowWatchlistPreferences = (
  preferences: ForeignFlowWatchlistPreferences,
  storage: Pick<Storage, 'setItem'> | null,
) => {
  if (!storage) return;
  storage.setItem(FOREIGN_FLOW_WATCHLIST_STORAGE_KEY, JSON.stringify({
    tickers: preferences.tickers,
    metric: preferences.metric,
    window: preferences.window,
    filter: preferences.filter,
    sort: preferences.sort,
    direction: preferences.direction,
  }));
};

export const foreignFlowWatchlistMetric = (
  item: VietnamForeignFlowWatchlistItem,
  metric: ForeignFlowExplorerMetric,
  window: VietnamForeignFlowWatchlistWindow,
  side: 'buy' | 'sell' | 'net' = 'net',
): number | null => {
  const key = `${side}${metric === 'value' ? 'Value' : 'Volume'}${window}d` as keyof VietnamForeignFlowWatchlistItem;
  const value = item[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
};

const compareNullable = (left: number | string | null, right: number | string | null) => {
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  return typeof left === 'number' && typeof right === 'number'
    ? left - right
    : String(left).localeCompare(String(right));
};

export const selectForeignFlowWatchlistRows = (
  items: VietnamForeignFlowWatchlistItem[],
  options: {
    metric: ForeignFlowExplorerMetric;
    window: VietnamForeignFlowWatchlistWindow;
    filter: ForeignFlowWatchlistFilter;
    search: string;
    sort: ForeignFlowWatchlistSort;
    direction: 'asc' | 'desc';
  },
) => {
  const inputOrder = new Map(items.map((item, index) => [item.ticker, index]));
  const filtered = items.filter((item) => {
    if (!item.ticker.includes(options.search.trim().toUpperCase())) return false;
    const net = foreignFlowWatchlistMetric(item, options.metric, options.window);
    switch (options.filter) {
      case 'net_buyers': return net !== null && net > 0;
      case 'net_sellers': return net !== null && net < 0;
      case 'active_buy_streak': return (item.buyStreak ?? 0) > 0;
      case 'active_sell_streak': return (item.sellStreak ?? 0) > 0;
      case 'stale': return item.sourceFreshness === 'stale';
      case 'partial': return item.availability === 'partial';
      case 'unavailable': return item.availability === 'unavailable';
      case 'anomaly': return item.containsProviderAnomaly;
      default: return true;
    }
  });
  const valueFor = (item: VietnamForeignFlowWatchlistItem): number | string | null => {
    if (options.sort === 'input') return inputOrder.get(item.ticker) ?? 0;
    if (options.sort === 'ticker') return item.ticker;
    if (options.sort === 'latest_session') return item.latestSession ?? null;
    if (options.sort.startsWith('net_')) {
      const window = Number(options.sort.slice(4, -1)) as VietnamForeignFlowWatchlistWindow;
      return foreignFlowWatchlistMetric(item, options.metric, window);
    }
    if (options.sort === 'streak') return Math.max(item.buyStreak ?? 0, item.sellStreak ?? 0);
    if (options.sort === 'freshness') return item.sourceSessionLag ?? null;
    return item.anomalyCount;
  };
  return [...filtered].sort((left, right) => {
    const compared = compareNullable(valueFor(left), valueFor(right));
    return (options.direction === 'asc' ? compared : -compared)
      || (inputOrder.get(left.ticker) ?? 0) - (inputOrder.get(right.ticker) ?? 0);
  });
};

export const summarizeForeignFlowWatchlist = (
  items: VietnamForeignFlowWatchlistItem[],
  metric: ForeignFlowExplorerMetric,
  window: VietnamForeignFlowWatchlistWindow,
) => {
  const sessions = [...new Set(items.map((item) => item.latestSession).filter(Boolean))];
  return {
    total: items.length,
    ready: items.filter((item) => item.availability === 'ready').length,
    partial: items.filter((item) => item.availability === 'partial').length,
    unavailable: items.filter((item) => item.availability === 'unavailable').length,
    netBuy: items.filter((item) => (foreignFlowWatchlistMetric(item, metric, window) ?? 0) > 0).length,
    netSell: items.filter((item) => (foreignFlowWatchlistMetric(item, metric, window) ?? 0) < 0).length,
    anomaly: items.filter((item) => item.containsProviderAnomaly).length,
    sourceSession: sessions.length === 1 ? sessions[0] : sessions.length > 1 ? 'mixed source sessions' : null,
  };
};

export const buildForeignFlowWatchlistCsv = (
  items: VietnamForeignFlowWatchlistItem[],
  metric: ForeignFlowExplorerMetric,
  window: VietnamForeignFlowWatchlistWindow,
) => buildForeignFlowCsv(items.map((item) => ({
  ticker: item.ticker,
  selected_metric: metric,
  selected_window: window,
  latest_session: item.latestSession,
  source_freshness: item.sourceFreshness,
  actual_session_count: item.actualSessionCount,
  availability: item.availability,
  failure_class: item.failureClass,
  buy_streak: item.buyStreak,
  sell_streak: item.sellStreak,
  streak_metric_basis: item.streakMetricBasis,
  contains_provider_anomaly: item.containsProviderAnomaly,
  anomaly_sessions: item.anomalySessions.join('|'),
  buy_value_1d: item.buyValue1d,
  sell_value_1d: item.sellValue1d,
  net_value_1d: item.netValue1d,
  buy_value_5d: item.buyValue5d,
  sell_value_5d: item.sellValue5d,
  net_value_5d: item.netValue5d,
  buy_value_20d: item.buyValue20d,
  sell_value_20d: item.sellValue20d,
  net_value_20d: item.netValue20d,
  buy_value_60d: item.buyValue60d,
  sell_value_60d: item.sellValue60d,
  net_value_60d: item.netValue60d,
  buy_volume_1d: item.buyVolume1d,
  sell_volume_1d: item.sellVolume1d,
  net_volume_1d: item.netVolume1d,
  buy_volume_5d: item.buyVolume5d,
  sell_volume_5d: item.sellVolume5d,
  net_volume_5d: item.netVolume5d,
  buy_volume_20d: item.buyVolume20d,
  sell_volume_20d: item.sellVolume20d,
  net_volume_20d: item.netVolume20d,
  buy_volume_60d: item.buyVolume60d,
  sell_volume_60d: item.sellVolume60d,
  net_volume_60d: item.netVolume60d,
})), { mode: 'watchlist', metric, window: String(window) as '1' | '5' | '20' | '60' });
