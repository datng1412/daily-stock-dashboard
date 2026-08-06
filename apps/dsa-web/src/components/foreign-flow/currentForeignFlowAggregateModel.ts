import type {
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
const isAnomalousCompleted = (row: ForeignFlowDisplayRow) => Boolean(
  row.suspiciousZeroSession
  || row.anomaly
  || row.anomalyCode
  || row.anomalyStatus === 'unresolved_provider_anomaly'
  || row.dataQuality === 'anomalous',
);
const completedSuppressesCurrent = (row: ForeignFlowDisplayRow) => Boolean(
  dateOf(row)
  && row.complete !== false
  && row.dataQuality !== 'incomplete'
  && row.dataQuality !== 'anomalous'
  && row.isPartial !== true
  && !isAnomalousCompleted(row),
);
const currentDisplayEligible = (current: VietnamCurrentForeignFlowAggregateResponse) => (
  current.usable
  && ['ready', 'partial', 'stale', 'market_closed'].includes(current.dataState)
);

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
    isPartial: (
      row.isPartial === true
      || row.complete === false
      || row.dataQuality === 'incomplete'
    ),
    isAnomalous: isAnomalousCompleted(row),
  }),
  isCurrent: false,
  isCompleted: true,
  isPartial: (
    row.isPartial === true
    || row.complete === false
    || row.dataQuality === 'incomplete'
    || row.dataQuality === 'anomalous'
    || isAnomalousCompleted(row)
  ),
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
  if (!current || !currentDisplayEligible(current)) return normalizedCompleted;
  if (mode === 'vn30') {
    const currentRows = current.displaySeries
      .filter((row) => (
        row.sourceKind === 'current'
        || row.finality === 'current_session_provisional'
      ))
      .map((row) => normalizeCurrentRow(row, current));
    const completedDates = new Set(
      normalizedCompleted.filter(completedSuppressesCurrent).map(dateOf).filter(Boolean),
    );
    const currentDates = new Set(currentRows.map(dateOf).filter(Boolean));
    return [
      ...normalizedCompleted.filter((row) => (
        !currentDates.has(dateOf(row)) || completedSuppressesCurrent(row)
      )),
      ...currentRows.filter((row) => row.tradingDate && !completedDates.has(row.tradingDate)),
    ];
  }
  const currentDate = text(current.providerSessionDate);
  const completedDates = new Set(
    normalizedCompleted.filter(completedSuppressesCurrent).map(dateOf).filter(Boolean),
  );
  const aggregate = current.aggregate ?? null;
  if (!aggregate || !currentDate || !hasFlowValues(aggregate)) {
    return normalizedCompleted;
  }
  const currentRow = normalizeCurrentRow({
    ...aggregate,
    tradingDate: currentDate,
    currentState: current.dataState,
    source: current.source,
  }, current);
  return [
    ...normalizedCompleted.filter((row) => (
      dateOf(row) !== currentDate || completedSuppressesCurrent(row)
    )),
    ...(completedDates.has(currentDate) ? [] : [currentRow]),
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
