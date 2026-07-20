import { useMemo, useState } from 'react';
import { cn } from '../../utils/cn';
import { formatCompactShareVolume, formatCompactVndValue } from '../../utils/vietnamNumberFormat';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import type { SymbolForeignFlowMetric, SymbolForeignFlowMetricRow } from './foreignFlowSymbolAnalyticsModel';

type SortKey = 'tradingDate' | 'buy' | 'sell' | 'net' | 'rolling5' | 'rolling20';

export const ForeignFlowSymbolHistoryTable = ({ rows, metric }: { rows: SymbolForeignFlowMetricRow[]; metric: SymbolForeignFlowMetric }) => {
  const [sort, setSort] = useState<SortKey>('tradingDate');
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc');
  const format = metric === 'value' ? formatCompactVndValue : formatCompactShareVolume;
  const sorted = useMemo(() => [...rows].sort((left, right) => {
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
        <tbody>{sorted.map((row) => <tr key={row.tradingDate} className="border-t border-border/60">
          <td className="px-3 py-2 tabular-nums">{row.tradingDate}</td>
          <td className="px-3 py-2 text-right tabular-nums">{format(row.buy, '—')}</td><td className="px-3 py-2 text-right tabular-nums">{format(row.sell, '—')}</td>
          {[row.net, row.rolling5, row.rolling20].map((value, index) => <td key={index} className={cn('px-3 py-2 text-right tabular-nums', foreignFlowSignTextClass(value))}>{format(value, '—', true)}</td>)}
          <td className="px-3 py-2 text-secondary-text">{row.state === 'ready' ? 'Đủ' : row.state === 'partial' ? 'Thiếu trường' : 'Không có'}</td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>;
};
