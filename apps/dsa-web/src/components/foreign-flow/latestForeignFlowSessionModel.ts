import type { VietnamCurrentForeignFlowResponse } from '../../api/stocks';

export type LatestForeignFlowStatus =
  | 'Đủ'
  | 'Đang diễn ra'
  | 'Tạm tính'
  | 'Chờ dữ liệu'
  | 'Mất kết nối'
  | 'Không khả dụng';

export type ForeignFlowSourceKind = 'current' | 'completed';
export type ForeignFlowFinality = 'current_session_provisional' | 'completed_accepted';
export type ForeignFlowCurrentState =
  | 'waiting'
  | 'ready'
  | 'stale'
  | 'market_closed'
  | 'unavailable'
  | 'error';

export const selectForeignFlowDisplayStatus = ({
  sourceKind,
  finality,
  currentState,
  providerStatus,
  usable,
  hasUsableValues,
}: {
  sourceKind?: ForeignFlowSourceKind | null;
  finality?: ForeignFlowFinality | null;
  currentState?: ForeignFlowCurrentState | null;
  providerStatus?: string | null;
  usable?: boolean;
  hasUsableValues?: boolean;
}): LatestForeignFlowStatus => {
  if (sourceKind === 'completed' || finality === 'completed_accepted') return 'Đủ';

  const current = sourceKind === 'current' || finality === 'current_session_provisional';
  if (!current) return 'Không khả dụng';

  if (currentState === 'market_closed') {
    return usable || hasUsableValues ? 'Tạm tính' : 'Không khả dụng';
  }
  if (currentState === 'waiting') return 'Chờ dữ liệu';

  const disconnected = /disconnect|reconnect|resubscrib/i.test(providerStatus ?? '');
  if (currentState === 'stale' || disconnected) return 'Mất kết nối';
  if (currentState === 'error') {
    return usable || hasUsableValues ? 'Mất kết nối' : 'Không khả dụng';
  }
  if (currentState === 'unavailable') return 'Không khả dụng';
  if (currentState === 'ready' || (
    currentState === null
    && /connected|cache_hit/i.test(providerStatus ?? '')
  )) {
    return 'Đang diễn ra';
  }
  return 'Không khả dụng';
};

export type CompletedForeignFlowSessionInput = {
  sessionDate?: string | null;
  source?: string | null;
  foreignBuyVolume?: number | null;
  foreignSellVolume?: number | null;
  foreignNetVolume?: number | null;
  foreignBuyValue?: number | null;
  foreignSellValue?: number | null;
  foreignNetValue?: number | null;
};

export type LatestForeignFlowSessionView = {
  sessionDate: string;
  sourceKind: 'current' | 'completed';
  source: string;
  finality: 'current_session_provisional' | 'completed_accepted';
  status: LatestForeignFlowStatus;
  foreignBuyVolume: number | null;
  foreignSellVolume: number | null;
  foreignNetVolume: number | null;
  foreignBuyValue: number | null;
  foreignSellValue: number | null;
  foreignNetValue: number | null;
  providerTime: string | null;
  receiptTime: string | null;
  isCurrentSession: boolean;
  isCompleted: boolean;
};

const SESSION_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

const safeSessionDate = (value: unknown): string | null => (
  typeof value === 'string' && SESSION_DATE_RE.test(value) ? value : null
);

const finiteOrNull = (value: unknown): number | null => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

const textOrNull = (value: unknown): string | null => (
  typeof value === 'string' && value.trim() ? value : null
);

export const currentForeignFlowStatus = (
  current: VietnamCurrentForeignFlowResponse,
): LatestForeignFlowStatus => selectForeignFlowDisplayStatus({
  sourceKind: 'current',
  finality: 'current_session_provisional',
  currentState: current.dataState,
  providerStatus: current.streamStatus,
  usable: current.usable,
  hasUsableValues: Boolean(current.current),
});

const currentView = (
  current: VietnamCurrentForeignFlowResponse,
  sessionDate: string,
): LatestForeignFlowSessionView => {
  const values = current.current ?? {};
  return {
    sessionDate,
    sourceKind: 'current',
    source: current.source || 'SSI V3 ForeignRoomMessage',
    finality: 'current_session_provisional',
    status: currentForeignFlowStatus(current),
    foreignBuyVolume: finiteOrNull(values.foreignBuyVolume),
    foreignSellVolume: finiteOrNull(values.foreignSellVolume),
    foreignNetVolume: finiteOrNull(values.foreignNetVolume),
    foreignBuyValue: finiteOrNull(values.foreignBuyValue),
    foreignSellValue: finiteOrNull(values.foreignSellValue),
    foreignNetValue: finiteOrNull(values.foreignNetValue),
    providerTime: textOrNull(values.streamTimestamp) ?? textOrNull(values.time),
    receiptTime: textOrNull(values.receivedAt),
    isCurrentSession: true,
    isCompleted: false,
  };
};

const completedView = (
  completed: CompletedForeignFlowSessionInput,
  sessionDate: string,
): LatestForeignFlowSessionView => ({
  sessionDate,
  sourceKind: 'completed',
  source: completed.source || 'SSI DailyStockPrice',
  finality: 'completed_accepted',
  status: 'Đủ',
  foreignBuyVolume: finiteOrNull(completed.foreignBuyVolume),
  foreignSellVolume: finiteOrNull(completed.foreignSellVolume),
  foreignNetVolume: finiteOrNull(completed.foreignNetVolume),
  foreignBuyValue: finiteOrNull(completed.foreignBuyValue),
  foreignSellValue: finiteOrNull(completed.foreignSellValue),
  foreignNetValue: finiteOrNull(completed.foreignNetValue),
  providerTime: null,
  receiptTime: null,
  isCurrentSession: false,
  isCompleted: true,
});

export const selectLatestForeignFlowSession = ({
  completed,
  current,
}: {
  completed?: CompletedForeignFlowSessionInput | null;
  current?: VietnamCurrentForeignFlowResponse | null;
}): LatestForeignFlowSessionView | null => {
  const completedDate = safeSessionDate(completed?.sessionDate);
  const currentDate = safeSessionDate(current?.tradingDate);

  if (completed && completedDate && (!current || !currentDate || completedDate >= currentDate)) {
    return completedView(completed, completedDate);
  }
  if (current && currentDate) {
    return currentView(current, currentDate);
  }
  return null;
};
