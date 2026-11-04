import type { VietnamChartResponse } from '../api/stocks';
import { normalizeVietnamTicker } from './vietnamWatchlist';

export const HOLDINGS_KEY = 'vietnamHoldings.v1';
export const HOLDINGS_LIMIT = 8;
export const HOLDINGS_CHART_RANGE = '6M';

export type Holding = { ticker: string; shares: number };
export type ChartResult = { chart: VietnamChartResponse } | { error: true };
type HoldingMark = Holding & (
  | { status: 'Eligible'; close: number; value: number; cache: 'Provider' | 'Process cache' }
  | { status: string; close?: never; value?: never; cache?: never }
);

export function parseHolding(symbol: unknown, quantity: unknown): Holding | null {
  if (typeof symbol !== 'string') return null;
  const ticker = normalizeVietnamTicker(symbol);
  const shares = typeof quantity === 'string' && /^\d+$/.test(quantity.trim()) ? Number(quantity) : quantity;
  return /^[A-Z][A-Z0-9]{2}$/.test(ticker)
    && typeof shares === 'number' && Number.isSafeInteger(shares) && shares > 0
    ? { ticker, shares }
    : null;
}

export function readHoldings(): Holding[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(HOLDINGS_KEY) ?? '[]');
    if (!Array.isArray(saved)) return [];
    const holdings: Holding[] = [];
    for (const row of saved) {
      const holding = parseHolding(row?.ticker, row?.shares);
      if (holding && !holdings.some(({ ticker }) => ticker === holding.ticker)) holdings.push(holding);
      if (holdings.length === HOLDINGS_LIMIT) break;
    }
    return holdings;
  } catch {
    return [];
  }
}

export async function loadHoldingCharts(
  holdings: Holding[],
  signal: AbortSignal,
  fetchChart: (ticker: string, signal: AbortSignal) => Promise<VietnamChartResponse>,
): Promise<ChartResult[]> {
  const results: ChartResult[] = [];
  let next = 0;
  const worker = async () => {
    while (!signal.aborted && next < holdings.length) {
      const index = next++;
      try {
        results[index] = { chart: await fetchChart(holdings[index].ticker, signal) };
      } catch {
        results[index] = { error: true };
      }
    }
  };
  await Promise.all([worker(), worker()]);
  return results;
}

const positive = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value > 0;
const validPriorDate = (date: unknown, today: string): date is string => {
  if (typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(date) || date >= today) return false;
  const parsed = new Date(date);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date;
};

export function buildHoldingsSnapshot(holdings: Holding[], results: ChartResult[], today: string) {
  const charts = holdings.map(({ ticker }, index) => {
    const result = results[index];
    if (!result || 'error' in result) return null;
    const { chart } = result;
    return chart && chart.symbol === ticker && chart.timeframe === '1d'
      && chart.range === HOLDINGS_CHART_RANGE && chart.source === 'SSI' && chart.actualSource === 'SSI'
      && chart.providerVersion === 'v3' && chart.endpoint === 'securitiesSummary'
      && chart.fallbackUsed === false && Array.isArray(chart.points) ? chart : null;
  });
  let date: string | null = null;
  for (const chart of charts) {
    for (const point of chart?.points ?? []) {
      if (validPriorDate(point?.date, today) && (!date || point.date > date)) date = point.date;
    }
  }

  const rows: HoldingMark[] = holdings.map((holding, index) => {
    const chart = charts[index];
    const result = results[index];
    if (!result || 'error' in result) return { ...holding, status: 'Request failed' };
    if (!chart) return { ...holding, status: 'Unverified chart source or identity' };
    const { diagnostics } = chart;
    if (diagnostics?.cacheSource === 'provider_backed_stale' || diagnostics?.freshnessStatus === 'stale') {
      return { ...holding, status: 'Stale history' };
    }
    if (chart.status !== 'ok') return { ...holding, status: 'Daily history unavailable' };
    if (diagnostics?.freshnessStatus !== 'fresh' || diagnostics.complete !== true
      || (diagnostics.cacheSource !== 'provider' && diagnostics.cacheSource !== 'process_memory')) {
      return { ...holding, status: 'Freshness or completeness unverified' };
    }
    const marks = date ? chart.points.filter((point) => point?.date === date) : [];
    if (!marks.length) return { ...holding, status: 'Exact-date mark missing' };
    if (marks.length !== 1) return { ...holding, status: 'Ambiguous exact-date mark' };
    const { open, high, low, close, volume } = marks[0];
    if (!positive(open) || !positive(high) || !positive(low) || !positive(close)
      || high < Math.max(open, close) || low > Math.min(open, close) || !positive(volume)) {
      return { ...holding, status: 'Invalid price or matched volume' };
    }
    const value = holding.shares * close;
    if (!positive(value) || value > Number.MAX_SAFE_INTEGER) return { ...holding, status: 'Value exceeds supported range' };
    return { ...holding, status: 'Eligible', close, value, cache: diagnostics.cacheSource === 'provider' ? 'Provider' : 'Process cache' };
  });

  const eligible = rows.filter((row) => row.value !== undefined);
  const total = eligible.reduce((sum, row) => sum + row.value, 0);
  const ranked = [...eligible].sort((left, right) => right.value - left.value);
  const aggregate = eligible.length === holdings.length && positive(total) && total <= Number.MAX_SAFE_INTEGER
    ? { total, largest: ranked[0], topThreeWeight: ranked.slice(0, 3).reduce((sum, row) => sum + row.value, 0) / total }
    : null;
  return { date, rows, coverage: eligible.length, aggregate };
}

