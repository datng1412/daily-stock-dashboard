import type {
  VietnamForeignFlowBatchSymbol,
  VietnamForeignFlowRankingEntry,
  VietnamForeignFlowRankingPair,
} from '../../api/stocks';

export type ForeignFlowWindow = 'today' | '5' | '20';
export type ForeignFlowMetric = 'value' | 'volume';
export type ForeignFlowSort = 'ticker' | 'latest' | '5' | '20' | 'date' | 'state';
export type ForeignFlowDirection = 'asc' | 'desc';
export type ForeignFlowFilter = 'all' | 'buy' | 'sell' | 'no-data';

const finite = (value?: number | null): value is number => typeof value === 'number' && Number.isFinite(value);

export const foreignFlowNetValue = (
  row: VietnamForeignFlowBatchSymbol,
  window: ForeignFlowWindow,
  metric: ForeignFlowMetric,
): number | null => {
  const value = window === 'today'
    ? (metric === 'value' ? row.foreignNetValue : row.foreignNetVolume)
    : window === '5'
      ? (metric === 'value' ? row.foreignNetValue5d : row.foreignNetVolume5d)
      : (metric === 'value' ? row.foreignNetValue20d : row.foreignNetVolume20d);
  return finite(value) ? value : null;
};

export const foreignFlowTodaySideValue = (
  row: VietnamForeignFlowBatchSymbol,
  side: 'buy' | 'sell',
  metric: ForeignFlowMetric,
): number | null => {
  const value = metric === 'value'
    ? (side === 'buy' ? row.foreignBuyValue : row.foreignSellValue)
    : (side === 'buy' ? row.foreignBuyVolume : row.foreignSellVolume);
  return finite(value) ? value : null;
};

const windowCoverage = (row: VietnamForeignFlowBatchSymbol, window: ForeignFlowWindow) => {
  if (window === '5') return { covered: row.coveredSessions5d, complete: row.complete5d };
  if (window === '20') return { covered: row.coveredSessions20d, complete: row.complete20d };
  return { covered: row.latestTradingDate ? 1 : 0, complete: Boolean(row.latestTradingDate) };
};

export const buildForeignFlowRankings = (
  rows: VietnamForeignFlowBatchSymbol[],
  window: ForeignFlowWindow,
  metric: ForeignFlowMetric,
  topN = 10,
): VietnamForeignFlowRankingPair => {
  const entries: VietnamForeignFlowRankingEntry[] = rows.flatMap((row) => {
    const value = foreignFlowNetValue(row, window, metric);
    if (value === null || value === 0 || (row.dataState !== 'ready' && row.dataState !== 'stale')) return [];
    const coverage = windowCoverage(row, window);
    return [{
      ticker: row.ticker,
      value,
      tradingDate: row.latestTradingDate,
      coveredSessions: coverage.covered,
      complete: coverage.complete,
      dataState: row.dataState,
    }];
  });
  const byMagnitudeThenTicker = (left: VietnamForeignFlowRankingEntry, right: VietnamForeignFlowRankingEntry) => (
    Math.abs(right.value) - Math.abs(left.value) || left.ticker.localeCompare(right.ticker)
  );
  return {
    topBuy: entries.filter((entry) => entry.value > 0).sort(byMagnitudeThenTicker).slice(0, topN),
    topSell: entries.filter((entry) => entry.value < 0).sort(byMagnitudeThenTicker).slice(0, topN),
  };
};

const sumFinite = (values: Array<number | null>) => {
  const contributors = values.filter(finite);
  return {
    value: contributors.length ? contributors.reduce((sum, value) => sum + value, 0) : null,
    contributors: contributors.length,
  };
};

export const summarizeForeignFlow = (
  rows: VietnamForeignFlowBatchSymbol[],
  window: ForeignFlowWindow,
  metric: ForeignFlowMetric,
) => {
  const net = sumFinite(rows.map((row) => foreignFlowNetValue(row, window, metric)));
  const buy = window === 'today'
    ? sumFinite(rows.map((row) => foreignFlowTodaySideValue(row, 'buy', metric)))
    : { value: null, contributors: 0 };
  const sell = window === 'today'
    ? sumFinite(rows.map((row) => foreignFlowTodaySideValue(row, 'sell', metric)))
    : { value: null, contributors: 0 };
  const dates = Array.from(new Set(rows.map((row) => row.latestTradingDate).filter((date): date is string => Boolean(date)))).sort();
  return {
    net,
    buy,
    sell,
    latestTradingDate: dates.at(-1) ?? null,
    mixedTradingDates: dates.length > 1,
  };
};

export const filterForeignFlowRows = (
  rows: VietnamForeignFlowBatchSymbol[],
  filter: ForeignFlowFilter,
  window: ForeignFlowWindow,
  metric: ForeignFlowMetric,
) => rows.filter((row) => {
  if (filter === 'all') return true;
  const value = foreignFlowNetValue(row, window, metric);
  if (filter === 'no-data') return value === null;
  if (filter === 'buy') return value !== null && value > 0;
  return value !== null && value < 0;
});

const sortValue = (row: VietnamForeignFlowBatchSymbol, sort: ForeignFlowSort, metric: ForeignFlowMetric) => {
  if (sort === 'latest') return foreignFlowNetValue(row, 'today', metric);
  if (sort === '5') return foreignFlowNetValue(row, '5', metric);
  if (sort === '20') return foreignFlowNetValue(row, '20', metric);
  if (sort === 'date') return row.latestTradingDate ?? null;
  if (sort === 'state') return row.dataState;
  return row.ticker;
};

export const sortForeignFlowRows = (
  rows: VietnamForeignFlowBatchSymbol[],
  sort: ForeignFlowSort,
  direction: ForeignFlowDirection,
  metric: ForeignFlowMetric,
) => [...rows].sort((left, right) => {
  const leftValue = sortValue(left, sort, metric);
  const rightValue = sortValue(right, sort, metric);
  if (leftValue === null && rightValue !== null) return 1;
  if (leftValue !== null && rightValue === null) return -1;
  if (leftValue === null && rightValue === null) return left.ticker.localeCompare(right.ticker);
  const comparison = typeof leftValue === 'number' && typeof rightValue === 'number'
    ? leftValue - rightValue
    : String(leftValue).localeCompare(String(rightValue));
  return (direction === 'asc' ? comparison : -comparison) || left.ticker.localeCompare(right.ticker);
});
