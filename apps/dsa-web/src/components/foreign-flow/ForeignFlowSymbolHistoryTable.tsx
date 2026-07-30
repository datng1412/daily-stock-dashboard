import { useMemo, useState } from 'react';
import { cn } from '../../utils/cn';
import { formatForeignFlowValue, formatForeignFlowVolume } from '../../utils/vietnamNumberFormat';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import type { SymbolForeignFlowMetric, SymbolForeignFlowMetricRow } from './foreignFlowSymbolAnalyticsModel';

type SortKey = 'tradingDate' | 'buy' | 'sell' | 'net' | 'rolling5' | 'rolling20';

export const ForeignFlowSymbolHistoryTable = ({ rows, metric }: { rows: SymbolForeignFlowMetricRow[]; metric: SymbolForeignFlowMetric }) => {
  const [sort, setSort] = useState<SortKey>('tradingDate');
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc');
  const format = metric === 'value' ? formatForeignFlowValue : formatForeignFlowVolume;
  const sorted = useMemo(() => [...rows].sort((left, right) => {
    const leftCurrent = left.displayOrigin === 'current_session_provisional';
    const rightCurrent = right.displayOrigin === 'current_session_provisional';
    if (leftCurrent !== rightCurrent) return leftCurrent ? -1 : 1;
    const a = left[sort]; const b = right[sort];
    if (a === null && b === null) return right.tradingDate.localeCompare(left.tradingDate);
    if (a === null) return 1; if (b === null) return -1;
    const compared = typeof a === 'string' ? a.localeCompare(String(b)) : Number(a) - Number(b);
    return (direction === 'asc' ? compared : -compared) || right.tradingDate.localeCompare(left.tradingDate);
  }), [direction, rows, sort]);
  const chooseSort = (key: SortKey) => { setDirection(sort === key && direction === 'desc' ? 'asc' : 'desc'); setSort(key); };
  const heading = (key: SortKey, label: string) => <button type="button" onClick={() => chooseSort(key)} className="whitespace-nowrap font-medium">{label}</button>;
  return <section aria-labelledby="symbol-flow-table-heading">
    <h3 id="symbol-flow-table-heading" className="text-sm font-semibold text-foreground">Chi tiết phiên</h3>
    <div className="mt-3 overflow-x-auto rounded-lg border border-border/70">
      <table className="min-w-full text-sm">
        <thead className="bg-elevated/60 text-secondary-text"><tr>
          <th className="px-3 py-2 text-left" aria-sort={sort === 'tradingDate' ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}>{heading('tradingDate', 'Ngày')}</th>
          {([['buy', 'NN mua'], ['sell', 'NN bán'], ['net', 'NN ròng'], ['rolling5', 'Ròng 5P'], ['rolling20', 'Ròng 20P']] as const).map(([key, label]) => <th key={key} className="px-3 py-2 text-right" aria-sort={sort === key ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}>{heading(key, label)}</th>)}
          <th className="px-3 py-2 text-left">Trạng thái</th>
        </tr></thead>
        <tbody>{sorted.map((row) => {
          const isCurrent = row.displayOrigin === 'current_session_provisional';
          const status = row.statusLabel
            ?? (isCurrent
              ? 'Không khả dụng'
              : row.sourceKind === 'completed' || row.finality === 'completed_accepted'
                ? 'Đủ'
                : row.state === 'ready'
                  ? 'Đủ'
                  : row.state === 'partial'
                    ? 'Thiếu trường'
                    : 'Không có');
          return <tr
            key={row.tradingDate}
            className={cn('border-t border-border/60', isCurrent && 'bg-primary/5')}
            data-current-session={isCurrent ? 'true' : undefined}
            data-testid={isCurrent ? 'current-session-flow-row' : undefined}
          >
          <td className={cn('px-3 py-2 tabular-nums', isCurrent && 'font-semibold')}>
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
              {isCurrent ? <span aria-hidden="true" className="size-1.5 rounded-full bg-primary" /> : null}
              {row.tradingDate}
            </span>
          </td>
          <td className="px-3 py-2 text-right tabular-nums">{format(row.buy, '—')}</td><td className="px-3 py-2 text-right tabular-nums">{format(row.sell, '—')}</td>
          {[row.net, row.rolling5, row.rolling20].map((value, index) => <td key={index} className={cn('px-3 py-2 text-right tabular-nums', foreignFlowSignTextClass(value))}>{format(value)}</td>)}
          <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{status}</td>
        </tr>;
        })}</tbody>
      </table>
    </div>
  </section>;
};
