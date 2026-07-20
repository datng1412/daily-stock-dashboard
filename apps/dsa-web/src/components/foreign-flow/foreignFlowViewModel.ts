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
export type ForeignFlowWindowState = 'ready' | 'incomplete' | 'unavailable' | 'empty' | 'stale';

export type ForeignFlowWindowDisplay = {
  value: number | null;
  coveredSessions: number | null;
  requestedSessions: 1 | 5 | 20;
  complete: boolean | null;
  usable: boolean;
  stale: boolean;
  state: ForeignFlowWindowState;
  endDate: string | null;
};

const finite = (value?: number | null): value is number => typeof value === 'number' && Number.isFinite(value);

const requestedSessionsFor = (window: ForeignFlowWindow): 1 | 5 | 20 => (
  window === 'today' ? 1 : Number(window) as 5 | 20
);

const validCoverage = (value: number | null | undefined, requestedSessions: number): number | null => (
  finite(value) && Number.isInteger(value) && value >= 0 && value <= requestedSessions ? value : null
);

export const foreignFlowWindowLabel = (window: ForeignFlowWindow): string => (
  window === 'today' ? 'Phiên gần nhất' : `${window} phiên`
);

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

export const foreignFlowWindowDisplay = (
  row: VietnamForeignFlowBatchSymbol,
  window: ForeignFlowWindow,
  metric: ForeignFlowMetric,
): ForeignFlowWindowDisplay => {
  const requestedSessions = requestedSessionsFor(window);
  const value = foreignFlowNetValue(row, window, metric);
  const coveredSessions = window === 'today'
    ? (row.latestTradingDate ? 1 : null)
    : validCoverage(
      window === '5' ? row.coveredSessions5d : row.coveredSessions20d,
      requestedSessions,
    );
  const complete = window === 'today'
    ? (value === null ? null : true)
    : (coveredSessions === null ? null : (window === '5' ? row.complete5d : row.complete20d));
  const endDate = window === 'today'
    ? row.latestTradingDate ?? null
    : (window === '5' ? row.windowEndDate5d : row.windowEndDate20d) ?? row.latestTradingDate ?? null;
  const sourceUsable = row.dataState === 'ready' || row.dataState === 'stale';
  const usable = sourceUsable && value !== null;
  const stale = usable && (row.dataState === 'stale' || row.freshness === 'stale');

  let state: ForeignFlowWindowState;
  if (row.dataState === 'empty') state = 'empty';
  else if (!usable) state = 'unavailable';
  else if (window !== 'today' && (coveredSessions !== requestedSessions || complete !== true)) state = 'incomplete';
  else if (stale) state = 'stale';
  else state = 'ready';

  return {
    value,
    coveredSessions,
    requestedSessions,
    complete,
    usable,
    stale,
    state,
    endDate,
  };
};

export const foreignFlowWindowStateLabel = (
  display: ForeignFlowWindowDisplay,
): string => {
  if (display.state === 'ready') return 'Sẵn sàng';
  if (display.state === 'stale') return 'Dữ liệu cũ';
  if (display.state === 'empty') return 'Không có dữ liệu';
  if (display.state === 'incomplete') return `Chưa đủ ${display.requestedSessions} phiên`;
  return display.requestedSessions === 1
    ? 'Không khả dụng'
    : `Thiếu dữ liệu ${display.requestedSessions} phiên`;
};

export const buildForeignFlowRankings = (
  rows: VietnamForeignFlowBatchSymbol[],
  window: ForeignFlowWindow,
  metric: ForeignFlowMetric,
  topN = 10,
): VietnamForeignFlowRankingPair => {
  const entries: VietnamForeignFlowRankingEntry[] = rows.flatMap((row) => {
    const display = foreignFlowWindowDisplay(row, window, metric);
    if (!display.usable || display.value === null || display.value === 0) return [];
    return [{
      ticker: row.ticker,
      value: display.value,
      tradingDate: display.endDate,
      coveredSessions: display.coveredSessions ?? 0,
      complete: display.complete === true,
      dataState: display.stale ? 'stale' : 'ready',
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
  const displays = rows.map((row) => foreignFlowWindowDisplay(row, window, metric));
  const usableDisplays = displays.filter((display) => display.usable);
  const net = sumFinite(displays.map((display) => display.usable ? display.value : null));
  const usableLatestRows = rows.filter((row) => row.dataState === 'ready' || row.dataState === 'stale');
  const buy = window === 'today'
    ? sumFinite(usableLatestRows.map((row) => foreignFlowTodaySideValue(row, 'buy', metric)))
    : { value: null, contributors: 0 };
  const sell = window === 'today'
    ? sumFinite(usableLatestRows.map((row) => foreignFlowTodaySideValue(row, 'sell', metric)))
    : { value: null, contributors: 0 };
  const dates = Array.from(new Set(displays.map((display) => display.endDate).filter((date): date is string => Boolean(date)))).sort();
  const selectedWindowState: ForeignFlowWindowState = usableDisplays.length === 0
    ? (displays.length > 0 && displays.every((display) => display.state === 'empty') ? 'empty' : 'unavailable')
    : usableDisplays.length < rows.length || displays.some((display) => display.state === 'incomplete')
      ? 'incomplete'
      : displays.some((display) => display.stale)
        ? 'stale'
        : 'ready';
  return {
    net,
    buy,
    sell,
    selectedWindowState,
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
  const display = foreignFlowWindowDisplay(row, window, metric);
  if (filter === 'no-data') return !display.usable;
  if (filter === 'buy') return display.value !== null && display.value > 0;
  return display.value !== null && display.value < 0;
});

const sortValue = (
  row: VietnamForeignFlowBatchSymbol,
  sort: ForeignFlowSort,
  metric: ForeignFlowMetric,
  selectedWindow: ForeignFlowWindow,
) => {
  if (sort === 'latest') return foreignFlowWindowDisplay(row, 'today', metric).value;
  if (sort === '5') return foreignFlowWindowDisplay(row, '5', metric).value;
  if (sort === '20') return foreignFlowWindowDisplay(row, '20', metric).value;
  if (sort === 'date') return row.latestTradingDate ?? null;
  if (sort === 'state') return foreignFlowWindowDisplay(row, selectedWindow, metric).state;
  return row.ticker;
};

export const sortForeignFlowRows = (
  rows: VietnamForeignFlowBatchSymbol[],
  sort: ForeignFlowSort,
  direction: ForeignFlowDirection,
  metric: ForeignFlowMetric,
  selectedWindow: ForeignFlowWindow = 'today',
) => [...rows].sort((left, right) => {
  const leftValue = sortValue(left, sort, metric, selectedWindow);
  const rightValue = sortValue(right, sort, metric, selectedWindow);
  if (leftValue === null && rightValue !== null) return 1;
  if (leftValue !== null && rightValue === null) return -1;
  if (leftValue === null && rightValue === null) return left.ticker.localeCompare(right.ticker);
  const comparison = typeof leftValue === 'number' && typeof rightValue === 'number'
    ? leftValue - rightValue
    : String(leftValue).localeCompare(String(rightValue));
  return (direction === 'asc' ? comparison : -comparison) || left.ticker.localeCompare(right.ticker);
});
