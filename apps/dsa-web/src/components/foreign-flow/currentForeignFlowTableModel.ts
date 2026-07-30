import type { VietnamCurrentForeignFlowResponse } from '../../api/stocks';
import { foreignFlowSign } from '../../utils/foreignFlowSign';
import type {
  SymbolForeignFlowMetric,
  SymbolForeignFlowMetricRow,
} from './foreignFlowSymbolAnalyticsModel';
import { selectLatestForeignFlowSession } from './latestForeignFlowSessionModel';

export const mapCurrentFlowToSessionDisplayRow = (
  data: VietnamCurrentForeignFlowResponse | null,
  metric: SymbolForeignFlowMetric,
  latestCompletedDate?: string | null,
): SymbolForeignFlowMetricRow | null => {
  const selected = selectLatestForeignFlowSession({
    completed: latestCompletedDate ? { sessionDate: latestCompletedDate } : null,
    current: data,
  });
  if (!selected || selected.sourceKind !== 'current') {
    return null;
  }

  const buy = metric === 'value' ? selected.foreignBuyValue : selected.foreignBuyVolume;
  const sell = metric === 'value' ? selected.foreignSellValue : selected.foreignSellVolume;
  const net = metric === 'value' ? selected.foreignNetValue : selected.foreignNetVolume;
  const present = [buy, sell, net].filter((value) => value !== null).length;

  return {
    tradingDate: selected.sessionDate,
    buy,
    sell,
    net,
    rolling5: null,
    rolling20: null,
    cumulative: null,
    usable: net !== null,
    sign: foreignFlowSign(net),
    state: present === 0 ? 'unavailable' : present === 3 ? 'ready' : 'partial',
    unit: metric === 'value' ? 'VND' : 'shares',
    displayOrigin: 'current_session_provisional',
    statusLabel: selected.status,
  };
};

export const mergeCurrentFlowSessionDisplayRow = (
  completedRows: SymbolForeignFlowMetricRow[],
  currentFlow: VietnamCurrentForeignFlowResponse | null,
  metric: SymbolForeignFlowMetric,
  latestAcceptedDate?: string | null,
): SymbolForeignFlowMetricRow[] => {
  const latestVisibleCompletedDate = completedRows.reduce<string | null>(
    (latest, row) => !latest || row.tradingDate > latest ? row.tradingDate : latest,
    null,
  );
  const currentRow = mapCurrentFlowToSessionDisplayRow(
    currentFlow,
    metric,
    latestAcceptedDate ?? latestVisibleCompletedDate,
  );
  if (
    !currentRow
    || completedRows.some((row) => row.tradingDate === currentRow.tradingDate)
  ) {
    return [...completedRows];
  }
  return [currentRow, ...completedRows];
};
