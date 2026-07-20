import { formatForeignFlowPercent } from '../../utils/vietnamNumberFormat';
import { foreignFlowWindowLabel, type ForeignFlowBreadthModel, type ForeignFlowMetric, type ForeignFlowWindow } from './foreignFlowViewModel';

const percentage = (count: number, total: number): string => formatForeignFlowPercent(
  total > 0 ? (count / total) * 100 : 0,
);

export const ForeignFlowBreadth = ({
  breadth,
  window,
  metric,
  scopeLabel = 'watchlist',
}: {
  breadth: ForeignFlowBreadthModel;
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
  scopeLabel?: string;
}) => {
  const groups = [
    { key: 'buy', label: 'Mua ròng', count: breadth.buyCount, className: 'bg-success/75' },
    { key: 'sell', label: 'Bán ròng', count: breadth.sellCount, className: 'bg-danger/75' },
    { key: 'zero', label: 'Trung tính', count: breadth.zeroCount, className: 'bg-border' },
    { key: 'unavailable', label: 'Không có dữ liệu', count: breadth.unavailableCount, className: 'bg-secondary-text/25' },
  ];

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" aria-labelledby="foreign-flow-breadth-heading">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="foreign-flow-breadth-heading" className="text-base font-semibold text-foreground">Độ rộng {scopeLabel}</h2>
          <p className="mt-1 text-xs text-secondary-text">{foreignFlowWindowLabel(window)} · {metric === 'value' ? 'Giá trị' : 'Khối lượng'}</p>
        </div>
        <p className="text-sm font-medium tabular-nums text-foreground">
          {breadth.usableCount}/{breadth.normalizedCount} mã có dữ liệu
        </p>
      </div>
      {breadth.normalizedCount > 0 ? (
        <>
          <div
            className="mt-4 flex h-3 overflow-hidden rounded-full bg-elevated"
            role="img"
            aria-label={`${breadth.buyCount} mã mua ròng, ${breadth.sellCount} mã bán ròng, ${breadth.zeroCount} mã trung tính, ${breadth.unavailableCount} mã không có dữ liệu`}
          >
            {groups.filter((group) => group.count > 0).map((group) => (
              <span
                key={group.key}
                aria-hidden="true"
                className={group.className}
                style={{ width: percentage(group.count, breadth.normalizedCount) }}
              />
            ))}
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {groups.map((group) => (
              <div key={group.key}>
                <dt className="flex items-center gap-2 text-secondary-text">
                  <span className={`h-2.5 w-2.5 rounded-full ${group.className}`} aria-hidden="true" />
                  {group.label}
                </dt>
                <dd className="mt-1 font-semibold tabular-nums text-foreground">{group.count} mã</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-xs text-secondary-text">
            Hoàn chỉnh {breadth.completeCount} mã · Chưa đủ phiên {breadth.incompleteCount} mã{breadth.staleCount ? ` · Dữ liệu cũ ${breadth.staleCount} mã` : ''}
          </p>
        </>
      ) : <p className="mt-4 text-sm text-secondary-text">Chưa có mã trong phạm vi để tính độ rộng.</p>}
    </section>
  );
};
