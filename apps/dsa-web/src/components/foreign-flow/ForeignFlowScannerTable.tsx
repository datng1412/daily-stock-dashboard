import { Link } from 'react-router-dom';
import type { VietnamForeignFlowBatchSymbol } from '../../api/stocks';
import { cn } from '../../utils/cn';
import { formatCompactShareVolume, formatCompactVndValue, formatFullSharesTitle, formatFullVndTitle } from '../../utils/vietnamNumberFormat';
import { Badge } from '../common';
import {
  filterForeignFlowRows,
  foreignFlowNetValue,
  foreignFlowTodaySideValue,
  sortForeignFlowRows,
  type ForeignFlowDirection,
  type ForeignFlowFilter,
  type ForeignFlowMetric,
  type ForeignFlowSort,
  type ForeignFlowWindow,
} from './foreignFlowViewModel';

const stateBadge = (row: VietnamForeignFlowBatchSymbol) => {
  if (row.dataState === 'ready') return <Badge variant="success">Sẵn sàng</Badge>;
  if (row.dataState === 'stale') return <Badge variant="warning">Dữ liệu cũ</Badge>;
  if (row.dataState === 'empty') return <Badge>Không có dữ liệu</Badge>;
  return <Badge variant="danger">Không khả dụng</Badge>;
};

export const ForeignFlowScannerTable = ({
  rows,
  window,
  metric,
  sort,
  direction,
  filter,
  selectedTicker,
  onSort,
  onFilter,
  onSelectTicker,
}: {
  rows: VietnamForeignFlowBatchSymbol[];
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
  sort: ForeignFlowSort;
  direction: ForeignFlowDirection;
  filter: ForeignFlowFilter;
  selectedTicker: string | null;
  onSort: (sort: ForeignFlowSort) => void;
  onFilter: (filter: ForeignFlowFilter) => void;
  onSelectTicker: (ticker: string) => void;
}) => {
  const visibleRows = sortForeignFlowRows(filterForeignFlowRows(rows, filter, window, metric), sort, direction, metric);
  const formatter = metric === 'value' ? formatCompactVndValue : formatCompactShareVolume;
  const title = metric === 'value' ? formatFullVndTitle : formatFullSharesTitle;
  const cell = (value: number | null, signed = false, incomplete?: string) => value === null ? (
    <span aria-label="Không khả dụng" title="Không có giá trị từ SSI DailyStockPrice">
      —{incomplete ? <span className="ml-1 text-[10px] text-warning">{incomplete}</span> : null}
    </span>
  ) : (
    <span title={title(value)}>
      {formatter(value, '—', signed)}
      {incomplete ? <span className="ml-1 text-[10px] text-warning">{incomplete}</span> : null}
    </span>
  );
  const headers: Array<{ key: ForeignFlowSort; label: string; align?: string }> = [
    { key: 'ticker', label: 'Mã' },
    { key: 'date', label: 'Ngày dữ liệu' },
    { key: 'latest', label: 'NN mua', align: 'text-right' },
    { key: 'latest', label: 'NN bán', align: 'text-right' },
    { key: 'latest', label: 'NN ròng', align: 'text-right' },
    { key: '5', label: 'NN 5P', align: 'text-right' },
    { key: '20', label: 'NN 20P', align: 'text-right' },
    { key: 'state', label: 'Trạng thái' },
  ];

  return (
    <section className="rounded-lg border border-border/70 bg-card" aria-labelledby="foreign-flow-scanner-heading">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 p-4">
        <div>
          <h2 id="foreign-flow-scanner-heading" className="text-base font-semibold text-foreground">Bộ quét watchlist</h2>
          <p className="mt-1 text-xs text-secondary-text">{visibleRows.length}/{rows.length} mã · {metric === 'value' ? 'VND' : 'cổ phiếu'}</p>
        </div>
        <label className="text-xs text-secondary-text">
          Lọc trạng thái dòng tiền
          <select className="ml-2 rounded-md border border-border/70 bg-elevated px-2 py-1.5 text-foreground" value={filter} onChange={(event) => onFilter(event.target.value as ForeignFlowFilter)}>
            <option value="all">Tất cả</option>
            <option value="buy">Mua ròng</option>
            <option value="sell">Bán ròng</option>
            <option value="no-data">Chưa có dữ liệu</option>
          </select>
        </label>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[900px] w-full border-collapse text-sm">
          <thead className="bg-elevated/60 text-left text-xs text-secondary-text">
            <tr>
              {headers.map((header, index) => (
                <th key={`${header.key}-${index}`} scope="col" className={cn('px-3 py-3 font-medium', header.align)}>
                  <button type="button" className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => onSort(header.key)} aria-label={`Sắp xếp theo ${header.label}`}>
                    {header.label}{sort === header.key ? <span aria-hidden="true">{direction === 'asc' ? '↑' : '↓'}</span> : null}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const selected = row.ticker === selectedTicker;
              return (
                <tr key={row.ticker} className={cn('border-t border-border/50 hover:bg-hover/50', selected && 'bg-cyan/10')} aria-selected={selected || undefined}>
                  <td className="px-3 py-3">
                    <button type="button" className="font-semibold text-foreground hover:text-cyan" onClick={() => onSelectTicker(row.ticker)}>{row.ticker}</button>
                  </td>
                  <td className="px-3 py-3 text-secondary-text">{row.latestTradingDate ?? '—'}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{cell(foreignFlowTodaySideValue(row, 'buy', metric))}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{cell(foreignFlowTodaySideValue(row, 'sell', metric))}</td>
                  <td className={cn('px-3 py-3 text-right font-medium tabular-nums', (foreignFlowNetValue(row, 'today', metric) ?? 0) > 0 ? 'text-success' : (foreignFlowNetValue(row, 'today', metric) ?? 0) < 0 ? 'text-danger' : 'text-foreground')}>{cell(foreignFlowNetValue(row, 'today', metric), true)}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{cell(foreignFlowNetValue(row, '5', metric), true, row.complete5d ? undefined : `${row.coveredSessions5d}/5`)}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{cell(foreignFlowNetValue(row, '20', metric), true, row.complete20d ? undefined : `${row.coveredSessions20d}/20`)}</td>
                  <td className="px-3 py-3">{stateBadge(row)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {selectedTicker ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 p-4 text-sm">
          <span className="text-secondary-text">Đã chọn <strong className="text-foreground">{selectedTicker}</strong></span>
          <Link className="font-medium text-cyan hover:underline" to={`/vietnam/company/${selectedTicker}`}>Mở chi tiết mã</Link>
        </div>
      ) : null}
    </section>
  );
};
