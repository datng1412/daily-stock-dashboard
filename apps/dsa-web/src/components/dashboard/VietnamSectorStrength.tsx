import { ArrowUpDown, Layers3, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';

import type { VietnamSectorStrengthGroup, VietnamSectorStrengthResponse } from '../../api/stocks';
import { formatCompactVndValue, formatFullVndTitle } from '../../utils/vietnamNumberFormat';
import { Badge, Button } from '../common';

type SortKey = 'return1d' | 'ma20' | 'ma50' | 'foreign1d' | 'foreign5d' | 'foreign20d';

const sortOptions: Array<{ key: SortKey; label: string }> = [
  { key: 'return1d', label: '1D' },
  { key: 'ma20', label: '>MA20' },
  { key: 'ma50', label: '>MA50' },
  { key: 'foreign1d', label: 'NN 1D' },
  { key: 'foreign5d', label: 'NN 5D' },
  { key: 'foreign20d', label: 'NN 20D' },
];

const metric = (group: VietnamSectorStrengthGroup, key: SortKey): number | null | undefined => {
  if (key === 'return1d') return group.return1D.value;
  if (key === 'ma20') return group.ma20.percentAbove;
  if (key === 'ma50') return group.ma50.percentAbove;
  if (key === 'foreign1d') return group.foreignFlow.windows['1'].netValue;
  if (key === 'foreign5d') return group.foreignFlow.windows['5'].netValue;
  return group.foreignFlow.windows['20'].netValue;
};

const signedPercent = (value?: number | null) => {
  if (value == null || !Number.isFinite(value)) return '—';
  const percent = value * 100;
  return `${percent > 0 ? '+' : ''}${percent.toFixed(2)}%`;
};

const signedValue = (value?: number | null) => (
  value == null || !Number.isFinite(value) ? '—' : formatCompactVndValue(value, '—', true)
);

type Props = {
  data: VietnamSectorStrengthResponse | null;
  loading: boolean;
  updating: boolean;
  error: string | null;
  onRefresh: () => void;
};

export const VietnamSectorStrength = ({ data, loading, updating, error, onRefresh }: Props) => {
  const [sortKey, setSortKey] = useState<SortKey>('return1d');
  const groups = useMemo(() => [...(data?.groups ?? [])].sort((left, right) => {
    const leftValue = metric(left, sortKey);
    const rightValue = metric(right, sortKey);
    if (leftValue == null && rightValue == null) return left.icbName.localeCompare(right.icbName);
    if (leftValue == null) return 1;
    if (rightValue == null) return -1;
    return rightValue - leftValue || left.icbName.localeCompare(right.icbName);
  }), [data?.groups, sortKey]);
  const usable = Boolean(data?.usable && groups.length);
  const statusLabel = loading && !data
    ? 'Đang tải'
    : data?.status === 'ready'
      ? 'Đầy đủ'
      : data?.status === 'partial'
        ? 'Một phần'
        : 'Không khả dụng';
  const statusVariant = data?.status === 'ready' ? 'success' : data?.status === 'partial' ? 'warning' : 'default';

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" aria-labelledby="vn30-sector-strength-title" data-testid="vn30-sector-strength">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Layers3 className="h-4 w-4 text-cyan" aria-hidden="true" />
            <h2 id="vn30-sector-strength-title" className="text-base font-semibold text-foreground">Sức mạnh ngành VN30</h2>
            <Badge variant={statusVariant}>{statusLabel}</Badge>
          </div>
          <p className="mt-1 text-xs text-secondary-text">Nhóm ICB của thành viên VN30 hiện tại · không phải chỉ số ngành chính thức</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onRefresh} disabled={loading || updating} isLoading={updating} loadingText="Đang cập nhật">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Làm mới
        </Button>
      </div>

      {loading && !data ? (
        <p className="mt-4 text-sm text-secondary-text" role="status">Đang tải dữ liệu ngành VN30…</p>
      ) : usable ? (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2" aria-label="Sắp xếp ngành">
            <span className="inline-flex items-center gap-1 text-xs text-secondary-text"><ArrowUpDown className="h-3.5 w-3.5" aria-hidden="true" /> Sắp xếp:</span>
            {sortOptions.map((option) => (
              <button
                key={option.key}
                type="button"
                className={`rounded-md border px-2 py-1 text-xs transition-colors ${sortKey === option.key ? 'border-cyan/50 bg-cyan/10 text-cyan' : 'border-border/70 text-secondary-text hover:text-foreground'}`}
                aria-pressed={sortKey === option.key}
                onClick={() => setSortKey(option.key)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="mt-3 max-w-full overflow-x-auto" data-testid="sector-table-scroll">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="border-b border-border/70 text-left text-xs text-secondary-text">
                <tr>
                  <th className="px-2 py-2 font-medium">Ngành</th>
                  <th className="px-2 py-2 text-right font-medium">1D</th>
                  <th className="px-2 py-2 text-right font-medium">&gt;MA20</th>
                  <th className="px-2 py-2 text-right font-medium">&gt;MA50</th>
                  <th className="px-2 py-2 text-right font-medium">NN 1D</th>
                  <th className="px-2 py-2 text-right font-medium">NN 5D</th>
                  <th className="px-2 py-2 text-right font-medium">NN 20D</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {groups.map((group) => (
                  <tr key={`${group.icbCode}-${group.icbName}`} data-testid="sector-row">
                    <td className="px-2 py-2.5">
                      <div className="font-medium text-foreground">{group.icbName}</div>
                      <div className="text-xs text-secondary-text">{group.memberCount} mã · {group.memberSymbols.join(', ')}</div>
                    </td>
                    <td className="px-2 py-2.5 text-right font-medium text-foreground">{signedPercent(group.return1D.value)}</td>
                    <td className="px-2 py-2.5 text-right text-foreground">{group.ma20.usableCount ? `${group.ma20.aboveCount}/${group.ma20.usableCount}` : '—'}</td>
                    <td className="px-2 py-2.5 text-right text-foreground">{group.ma50.usableCount ? `${group.ma50.aboveCount}/${group.ma50.usableCount}` : '—'}</td>
                    {(['1', '5', '20'] as const).map((window) => {
                      const flow = group.foreignFlow.windows[window];
                      const title = flow.netValue == null
                        ? `Thiếu ${flow.missingMemberCount}/${flow.requestedMemberCount} mã`
                        : `${formatFullVndTitle(flow.netValue)} · coverage ${flow.usableMemberCount}/${flow.requestedMemberCount}`;
                      return <td key={window} className="px-2 py-2.5 text-right text-foreground" title={title}>{signedValue(flow.netValue)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="mt-3 text-xs text-secondary-text">
            <summary className="cursor-pointer">Nguồn và phạm vi dữ liệu</summary>
            <p className="mt-2">Giá: SSI DailyOhlc {data?.priceSessionDate ?? '—'} ({data?.priceFinality ?? 'unknown'}). Dòng tiền NN hoàn tất: SSI DailyStockPrice {data?.foreignFlowLatestCompletedDate ?? '—'}.</p>
            <p className="mt-1">Phân loại {data?.membership.classifiedCount}/{data?.membership.memberCount}; chưa phân loại: {data?.membership.unclassifiedSymbols.join(', ') || 'không có'}. Cơ cấu là thành viên VN30 hiện tại, không đúng lịch sử thành phần.</p>
          </details>
        </>
      ) : (
        <div className="mt-4 rounded-md border border-border/60 bg-elevated/30 p-3 text-sm text-secondary-text" role="status">
          <p>Dữ liệu ngành VN30 không khả dụng.</p>
          <p className="mt-1 text-xs">{error ?? 'Chưa có đủ thành viên VN30, phân loại ICB hoặc dữ liệu nguồn hợp lệ.'}</p>
        </div>
      )}
      {updating && data ? <p className="mt-2 text-xs text-cyan" role="status">Đang cập nhật; giữ kết quả dùng được gần nhất.</p> : null}
      {error && data?.usable ? <p className="mt-2 text-xs text-warning">Lần làm mới gần nhất thất bại; đang giữ kết quả dùng được.</p> : null}
    </section>
  );
};
