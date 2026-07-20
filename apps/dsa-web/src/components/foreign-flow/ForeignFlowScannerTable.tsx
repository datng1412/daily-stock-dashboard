import { Link } from 'react-router-dom';
import type { VietnamForeignFlowBatchSymbol } from '../../api/stocks';
import { cn } from '../../utils/cn';
import { formatCompactShareVolume, formatCompactVndValue, formatFullSharesTitle, formatFullVndTitle } from '../../utils/vietnamNumberFormat';
import { Badge } from '../common';
import {
  filterForeignFlowRows,
  foreignFlowTodaySideValue,
  foreignFlowWindowDisplay,
  foreignFlowWindowStateLabel,
  sortForeignFlowRows,
  type ForeignFlowDirection,
  type ForeignFlowFilter,
  type ForeignFlowMetric,
  type ForeignFlowSort,
  type ForeignFlowWindow,
  type ForeignFlowWindowDisplay,
} from './foreignFlowViewModel';

const stateBadge = (display: ForeignFlowWindowDisplay) => {
  const variant = display.state === 'ready'
    ? 'success'
    : display.state === 'unavailable'
      ? 'danger'
      : 'warning';
  return <Badge variant={variant}>{foreignFlowWindowStateLabel(display)}</Badge>;
};

type ScannerHeader = {
  key?: ForeignFlowSort;
  label: string;
  align?: string;
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
  const visibleRows = sortForeignFlowRows(
    filterForeignFlowRows(rows, filter, window, metric),
    sort,
    direction,
    metric,
    window,
  );
  const formatter = metric === 'value' ? formatCompactVndValue : formatCompactShareVolume;
  const title = metric === 'value' ? formatFullVndTitle : formatFullSharesTitle;
  const cell = (
    value: number | null,
    signed = false,
    display?: ForeignFlowWindowDisplay,
  ) => {
    if (value === null || !Number.isFinite(value)) {
      return <span aria-label="Không khả dụng">—</span>;
    }
    const coverage = display?.state === 'incomplete' && display.coveredSessions !== null
      ? `${display.coveredSessions}/${display.requestedSessions} phiên`
      : null;
    return (
      <span aria-label={`Giá trị đầy đủ: ${title(value)}`}>
        {formatter(value, '—', signed)}
        {coverage ? <span className="ml-1 block text-[10px] text-warning">{coverage}</span> : null}
      </span>
    );
  };
  const headers: ScannerHeader[] = [
    { key: 'ticker', label: 'Mã' },
    { key: 'date', label: 'Ngày dữ liệu' },
    { label: 'NN mua', align: 'text-right' },
    { label: 'NN bán', align: 'text-right' },
    { key: 'latest', label: 'NN ròng', align: 'text-right' },
    { key: '5', label: 'NN 5P', align: 'text-right' },
    { key: '20', label: 'NN 20P', align: 'text-right' },
    { key: 'state', label: 'Trạng thái', align: 'text-left' },
  ];

  return (
    <section className="rounded-lg border border-border/70 bg-card" aria-labelledby="foreign-flow-scanner-heading">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 p-4">
        <div>
          <h2 id="foreign-flow-scanner-heading" className="text-base font-semibold text-foreground">Bộ quét watchlist</h2>
          <p className="mt-1 text-xs text-secondary-text">
            {visibleRows.length}/{rows.length} mã · Đơn vị: {metric === 'value' ? 'VND' : 'cổ phiếu'}
          </p>
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
              {headers.map((header, index) => {
                const active = header.key !== undefined && sort === header.key;
                return (
                  <th
                    key={`${header.key ?? header.label}-${index}`}
                    scope="col"
                    aria-sort={header.key ? (active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none') : undefined}
                    className={cn('px-3 py-3 font-medium', header.align, active && 'bg-cyan/10 text-cyan')}
                  >
                    {header.key ? (
                      <button
                        type="button"
                        className={cn('inline-flex items-center gap-1 hover:text-foreground', header.align === 'text-right' && 'ml-auto')}
                        onClick={() => onSort(header.key as ForeignFlowSort)}
                        aria-label={`Sắp xếp theo ${header.label}`}
                      >
                        {header.label}{active ? <span aria-hidden="true">{direction === 'asc' ? '↑' : '↓'}</span> : null}
                      </button>
                    ) : header.label}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const selected = row.ticker === selectedTicker;
              const latest = foreignFlowWindowDisplay(row, 'today', metric);
              const five = foreignFlowWindowDisplay(row, '5', metric);
              const twenty = foreignFlowWindowDisplay(row, '20', metric);
              const selectedWindow = foreignFlowWindowDisplay(row, window, metric);
              return (
                <tr key={row.ticker} className={cn('border-t border-border/50 hover:bg-hover/50', selected && 'bg-cyan/10')} aria-selected={selected || undefined}>
                  <td className="px-3 py-3">
                    <button type="button" className="font-semibold text-foreground hover:text-cyan" onClick={() => onSelectTicker(row.ticker)}>{row.ticker}</button>
                  </td>
                  <td className="px-3 py-3 text-secondary-text">{row.latestTradingDate ?? '—'}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{cell(foreignFlowTodaySideValue(row, 'buy', metric))}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{cell(foreignFlowTodaySideValue(row, 'sell', metric))}</td>
                  <td className={cn('px-3 py-3 text-right font-medium tabular-nums', (latest.value ?? 0) > 0 ? 'text-success' : (latest.value ?? 0) < 0 ? 'text-danger' : 'text-foreground')}>{cell(latest.value, true)}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{cell(five.value, true, five)}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{cell(twenty.value, true, twenty)}</td>
                  <td className="px-3 py-3">{stateBadge(selectedWindow)}</td>
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
