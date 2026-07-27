export type ForeignFlowExplorerMode = 'ticker' | 'vn30' | 'industry' | 'proprietary';
export type ForeignFlowExplorerWindow = '1' | '5' | '20' | '60' | 'custom';
export type ForeignFlowExplorerMetric = 'value' | 'volume';

export type ForeignFlowWindowSelection<T> = {
  rows: T[];
  sessionDates: string[];
  requestedSessionCount: number | null;
  actualSessionCount: number;
  complete: boolean;
  missingSessions: number | null;
  containsProviderAnomaly: boolean;
  anomalySessions: string[];
};

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

export const explorerWindowCount = (window: ForeignFlowExplorerWindow): number | null => (
  window === 'custom' ? null : Number(window)
);

export const explorerDateBounds = (
  window: ForeignFlowExplorerWindow,
  customFrom: string,
  customTo: string,
  today = new Date(),
) => {
  if (window === 'custom') {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(customFrom) || !/^\d{4}-\d{2}-\d{2}$/.test(customTo)) {
      throw new Error('Choose both custom dates.');
    }
    if (customFrom > customTo) throw new Error('Start date must not be after end date.');
    const span = (Date.parse(`${customTo}T00:00:00Z`) - Date.parse(`${customFrom}T00:00:00Z`)) / 86_400_000 + 1;
    if (!Number.isFinite(span) || span > 120) throw new Error('Custom range cannot exceed 120 calendar days.');
    return { fromDate: customFrom, toDate: customTo };
  }
  const lookbackDays: Record<Exclude<ForeignFlowExplorerWindow, 'custom'>, number> = {
    '1': 14,
    '5': 20,
    '20': 45,
    '60': 120,
  };
  const to = new Date(today);
  const from = new Date(today);
  from.setUTCDate(from.getUTCDate() - lookbackDays[window]);
  return {
    fromDate: from.toISOString().slice(0, 10),
    toDate: to.toISOString().slice(0, 10),
  };
};

export const selectForeignFlowWindow = <T,>(
  rows: T[],
  window: ForeignFlowExplorerWindow,
  dateOf: (row: T) => string | null | undefined,
  anomalyOf: (row: T) => boolean = () => false,
  customFrom = '',
  customTo = '',
): ForeignFlowWindowSelection<T> => {
  const datedRows = rows
    .map((row, occurrence) => ({ row, date: String(dateOf(row) ?? ''), occurrence }))
    .filter((item) => /^\d{4}-\d{2}-\d{2}$/.test(item.date))
    .filter((item) => window !== 'custom' || (item.date >= customFrom && item.date <= customTo))
    .sort((left, right) => left.date.localeCompare(right.date) || left.occurrence - right.occurrence);
  const allDates = [...new Set(datedRows.map((item) => item.date))];
  const requested = explorerWindowCount(window);
  const sessionDates = requested === null ? allDates : allDates.slice(-requested);
  const selectedDates = new Set(sessionDates);
  const selected = datedRows.filter((item) => selectedDates.has(item.date));
  const anomalySessions = [...new Set(
    selected.filter((item) => anomalyOf(item.row)).map((item) => item.date),
  )];
  return {
    rows: selected.map((item) => item.row),
    sessionDates,
    requestedSessionCount: requested,
    actualSessionCount: sessionDates.length,
    complete: requested === null ? Boolean(sessionDates.length) : sessionDates.length === requested,
    missingSessions: requested === null ? null : Math.max(0, requested - sessionDates.length),
    containsProviderAnomaly: anomalySessions.length > 0,
    anomalySessions,
  };
};

export const sumNullable = (values: unknown[]): number | null => {
  const accepted = values.filter(finite);
  return accepted.length ? accepted.reduce((total, value) => total + value, 0) : null;
};

const csvCell = (value: unknown) => {
  if (value === null || value === undefined) return '';
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};

export const buildForeignFlowCsv = (
  rows: Array<Record<string, unknown>>,
  metadata: {
    mode: ForeignFlowExplorerMode;
    metric: ForeignFlowExplorerMetric;
    window: ForeignFlowExplorerWindow;
  },
) => {
  if (!rows.length) return '';
  const keys = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const columns = ['selected_mode', 'selected_metric', 'selected_window', ...keys];
  const body = rows.map((row) => [
    metadata.mode,
    metadata.metric,
    metadata.window,
    ...keys.map((key) => row[key]),
  ].map(csvCell).join(','));
  return `\uFEFF${columns.join(',')}\r\n${body.join('\r\n')}\r\n`;
};

export const downloadForeignFlowCsv = (csv: string, filename: string) => {
  if (!csv) return false;
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  return true;
};
