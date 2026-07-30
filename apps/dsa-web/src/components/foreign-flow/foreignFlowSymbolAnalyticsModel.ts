import type {
  VietnamForeignFlowHistoryRow,
  VietnamForeignFlowSymbolAnalytics,
} from '../../api/stocks';
import { foreignFlowSign, type ForeignFlowSign } from '../../utils/foreignFlowSign';
import type {
  ForeignFlowCurrentState,
  ForeignFlowFinality,
  ForeignFlowSourceKind,
  LatestForeignFlowStatus,
} from './latestForeignFlowSessionModel';

export type SymbolForeignFlowMetric = 'value' | 'volume';
export type SymbolForeignFlowRange = 20 | 40 | 60;

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

export type SymbolForeignFlowMetricRow = {
  tradingDate: string;
  buy: number | null;
  sell: number | null;
  net: number | null;
  rolling5: number | null;
  rolling20: number | null;
  cumulative: number | null;
  usable: boolean;
  sign: ForeignFlowSign;
  state: 'ready' | 'partial' | 'unavailable';
  unit: 'VND' | 'shares';
  displayOrigin?: 'completed_session' | 'current_session_provisional';
  sourceKind?: ForeignFlowSourceKind;
  source?: string | null;
  finality?: ForeignFlowFinality;
  currentState?: ForeignFlowCurrentState | null;
  providerStatus?: string | null;
  displayStatus?: LatestForeignFlowStatus;
  statusLabel?: LatestForeignFlowStatus;
  isCurrent?: boolean;
  isCompleted?: boolean;
  isPartial?: boolean;
  isStale?: boolean;
  requestedCount?: number | null;
  observedCount?: number | null;
  completeValueCount?: number | null;
  completeVolumeCount?: number | null;
  providerTime?: string | null;
  receivedAt?: string | null;
};

export const getSymbolForeignFlowMetric = (
  row: VietnamForeignFlowHistoryRow,
  metric: SymbolForeignFlowMetric,
  rolling?: { rolling5?: number | null; rolling20?: number | null },
): Omit<SymbolForeignFlowMetricRow, 'cumulative'> => {
  const buyRaw = metric === 'value' ? row.foreignBuyValue : row.foreignBuyVolume;
  const sellRaw = metric === 'value' ? row.foreignSellValue : row.foreignSellVolume;
  const netRaw = metric === 'value' ? row.foreignNetValue : row.foreignNetVolume;
  const buy = finite(buyRaw) ? buyRaw : null;
  const sell = finite(sellRaw) ? sellRaw : null;
  const net = finite(netRaw) ? netRaw : null;
  const rolling5 = finite(rolling?.rolling5) ? rolling.rolling5 : null;
  const rolling20 = finite(rolling?.rolling20) ? rolling.rolling20 : null;
  const present = [buy, sell, net].filter((value) => value !== null).length;
  return {
    tradingDate: row.tradingDate,
    buy,
    sell,
    net,
    rolling5,
    rolling20,
    usable: net !== null,
    sign: foreignFlowSign(net),
    state: present === 0 ? 'unavailable' : present === 3 ? 'ready' : 'partial',
    unit: metric === 'value' ? 'VND' : 'shares',
  };
};

export const buildSymbolForeignFlowRows = (
  rows: VietnamForeignFlowHistoryRow[],
  analytics: VietnamForeignFlowSymbolAnalytics | null | undefined,
  metric: SymbolForeignFlowMetric,
  range: SymbolForeignFlowRange,
): SymbolForeignFlowMetricRow[] => {
  const rollingByDate = new Map((analytics?.rollingSeries ?? []).map((row) => [row.tradingDate, {
    rolling5: metric === 'value' ? row.rollingNet5dValue : row.rollingNet5dVolume,
    rolling20: metric === 'value' ? row.rollingNet20dValue : row.rollingNet20dVolume,
  }]));
  let cumulative = 0;
  return rows.slice(-range).map((row) => {
    const selected = getSymbolForeignFlowMetric(row, metric, rollingByDate.get(row.tradingDate));
    if (selected.net !== null) cumulative += selected.net;
    return { ...selected, cumulative: selected.net === null ? null : cumulative };
  });
};
