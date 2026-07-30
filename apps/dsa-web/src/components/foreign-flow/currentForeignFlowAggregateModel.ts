import type {
  VietnamCurrentForeignFlowDataState,
  VietnamCurrentForeignFlowDisplayRow,
  VietnamCurrentForeignFlowAggregateResponse,
  VietnamForeignFlowWatchlistItem,
} from '../../api/stocks';
import { selectForeignFlowDisplayStatus } from './latestForeignFlowSessionModel';

export type ForeignFlowDisplayRow = VietnamCurrentForeignFlowDisplayRow & {
  tradingDate?: string | null;
  icbCode?: string | null;
};

const text = (value: unknown) => typeof value === 'string' ? value : '';
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const dateOf = (row: ForeignFlowDisplayRow) => text(row.tradingDate || row.date);
const hasFlowValues = (row: ForeignFlowDisplayRow) => [
  row.foreignBuyVolume,
  row.foreignSellVolume,
  row.foreignNetVolume,
  row.foreignBuyValue,
  row.foreignSellValue,
  row.foreignNetValue,
].some(finite);

export type IndustryCurrentCapability = 'ready' | 'partial' | 'stale' | 'waiting' | 'unavailable';

export const currentIndustryCapability = (
  current: VietnamCurrentForeignFlowAggregateResponse | null,
): IndustryCurrentCapability => {
  if (!current) return 'unavailable';
  if (!current.usable) {
    return current.dataState === 'waiting' ? 'waiting' : 'unavailable';
  }
  if (
    current.dataState === 'stale'
    || current.dataState === 'error'
    || current.dataState === 'market_closed'
  ) {
    return 'stale';
  }
  const coverage = current.coverage;
  const complete = coverage.requestedSymbolCount > 0
    && current.groups.length > 0
    && coverage.classifiedSymbolCount === coverage.requestedSymbolCount
    && coverage.observedSymbolCount === coverage.requestedSymbolCount
    && coverage.completeValueCount === coverage.requestedSymbolCount
    && coverage.completeVolumeCount === coverage.requestedSymbolCount;
  return complete ? 'ready' : 'partial';
};

const normalizeCompletedRow = (row: ForeignFlowDisplayRow): ForeignFlowDisplayRow => ({
  ...row,
  tradingDate: dateOf(row),
  sourceKind: 'completed',
  finality: 'completed_accepted',
  displayStatus: selectForeignFlowDisplayStatus({
    sourceKind: 'completed',
    finality: 'completed_accepted',
  }),
  isCurrent: false,
  isCompleted: true,
  isStale: false,
});

const normalizeCurrentRow = (
  row: ForeignFlowDisplayRow,
  current: VietnamCurrentForeignFlowAggregateResponse,
): ForeignFlowDisplayRow => {
  const currentState = row.currentState ?? row.dataState ?? current.dataState;
  const providerStatus = text(row.providerStatus) || currentState;
  const displayStatus = selectForeignFlowDisplayStatus({
    sourceKind: 'current',
    finality: 'current_session_provisional',
    currentState,
    providerStatus,
    usable: current.usable,
    hasUsableValues: hasFlowValues(row),
  });
  return {
    ...row,
    tradingDate: dateOf(row) || text(row.providerSessionDate) || text(current.providerSessionDate),
    sourceKind: 'current',
    source: text(row.source) || current.source,
    finality: 'current_session_provisional',
    currentState,
    providerStatus,
    displayStatus,
    isCurrent: true,
    isCompleted: false,
    isPartial: Boolean(row.isPartial) || current.status === 'partial',
    isStale: Boolean(row.isStale) || currentState === 'stale',
    requestedCount: finite(row.requestedCount)
      ? row.requestedCount
      : current.coverage.requestedSymbolCount,
    observedCount: finite(row.observedCount)
      ? row.observedCount
      : current.coverage.observedSymbolCount,
    completeValueCount: finite(row.completeValueCount)
      ? row.completeValueCount
      : current.coverage.completeValueCount,
    completeVolumeCount: finite(row.completeVolumeCount)
      ? row.completeVolumeCount
      : current.coverage.completeVolumeCount,
  };
};

export const mergeCurrentAggregateRows = (
  completedRows: ForeignFlowDisplayRow[],
  current: VietnamCurrentForeignFlowAggregateResponse | null,
  mode: 'vn30' | 'industry',
): ForeignFlowDisplayRow[] => {
  const normalizedCompleted = completedRows.map(normalizeCompletedRow);
  if (!current?.usable) return normalizedCompleted;
  if (mode === 'vn30') {
    const currentRows = current.displaySeries
      .filter((row) => (
        row.sourceKind === 'current'
        || row.finality === 'current_session_provisional'
      ))
      .map((row) => normalizeCurrentRow(row, current));
    const completedDates = new Set(normalizedCompleted.map(dateOf).filter(Boolean));
    return [
      ...normalizedCompleted,
      ...currentRows.filter((row) => row.tradingDate && !completedDates.has(row.tradingDate)),
    ];
  }
  const completedKeys = new Set(
    normalizedCompleted.map((row) => `${dateOf(row)}:${text(row.icbCode)}`),
  );
  const currentRows = current.groups.map((group) => normalizeCurrentRow({
    ...group,
    icbCode: text(group.icbCode),
    icbName: text(group.icbName),
    tradingDate: text(group.providerSessionDate || current.providerSessionDate),
    currentState: (group.dataState ?? current.dataState) as VietnamCurrentForeignFlowDataState,
  }, current));
  return [
    ...normalizedCompleted,
    ...currentRows.filter((row) => (
      row.tradingDate
      && !completedKeys.has(`${row.tradingDate}:${text(row.icbCode)}`)
    )),
  ];
};

export const applyCurrentWatchlistFlow = (
  items: VietnamForeignFlowWatchlistItem[],
  current: VietnamCurrentForeignFlowAggregateResponse | null,
): VietnamForeignFlowWatchlistItem[] => {
  if (!current?.usable) return items;
  const currentByTicker = new Map(current.items.map((item) => [item.symbol, item]));
  return items.map((item) => {
    const currentItem = currentByTicker.get(item.ticker);
    if (!currentItem?.displayWindows) return item;
    const result: VietnamForeignFlowWatchlistItem = { ...item };
    ([1, 5, 20, 60] as const).forEach((window) => {
      const values = currentItem.displayWindows?.[String(window)];
      if (!values) return;
      const suffix = `${window}d`;
      const assign = (target: string, source: string) => {
        (result as unknown as Record<string, unknown>)[target] = (
          typeof values[source] === 'number' ? values[source] : null
        );
      };
      assign(`buyValue${suffix}`, 'foreignBuyValue');
      assign(`sellValue${suffix}`, 'foreignSellValue');
      assign(`netValue${suffix}`, 'foreignNetValue');
      assign(`buyVolume${suffix}`, 'foreignBuyVolume');
      assign(`sellVolume${suffix}`, 'foreignSellVolume');
      assign(`netVolume${suffix}`, 'foreignNetVolume');
    });
    const latest = currentItem.displayLatest;
    return {
      ...result,
      latestSession: typeof latest?.tradingDate === 'string'
        ? latest.tradingDate
        : result.latestSession,
      sourceFreshness: currentItem.usable
        ? currentItem.isStale ? 'stale' : 'current'
        : result.sourceFreshness,
      availability: currentItem.usable && current.status === 'partial'
        ? 'partial'
        : result.availability,
      dataState: currentItem.usable && current.status === 'partial'
        ? 'partial'
        : result.dataState,
      displayFinality: currentItem.usable
        ? 'current_session_provisional'
        : 'completed_accepted',
      displayStatus: selectForeignFlowDisplayStatus({
        sourceKind: currentItem.usable ? 'current' : 'completed',
        finality: currentItem.usable
          ? 'current_session_provisional'
          : 'completed_accepted',
        currentState: currentItem.dataState,
        providerStatus: currentItem.streamStatus,
        usable: currentItem.usable,
        hasUsableValues: Boolean(currentItem.displayLatest),
      }),
      displayCoverage: `${current.coverage.observedSymbolCount}/${current.coverage.requestedSymbolCount}`,
    };
  });
};
