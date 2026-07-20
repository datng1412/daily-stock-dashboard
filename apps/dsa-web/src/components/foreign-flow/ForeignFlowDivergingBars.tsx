import { Link } from 'react-router-dom';
import { formatForeignFlowValue, formatForeignFlowVolume, formatFullSharesTitle, formatFullVndTitle } from '../../utils/vietnamNumberFormat';
import { Tooltip } from '../common';
import { foreignFlowWindowLabel, type ForeignFlowMetric, type ForeignFlowWindow, type ForeignFlowWorkspaceRow } from './foreignFlowViewModel';

const Marker = ({ item }: { item: ForeignFlowWorkspaceRow }) => {
  if (item.display.stale) return <span className="text-[10px] text-warning">Cũ</span>;
  if (item.display.state === 'incomplete') return <span className="text-[10px] text-warning">{item.display.coveredSessions ?? 0}/{item.display.requestedSessions} phiên</span>;
  return null;
};

const BarList = ({
  title,
  items,
  side,
  maxMagnitude,
  window,
  metric,
}: {
  title: string;
  items: ForeignFlowWorkspaceRow[];
  side: 'buy' | 'sell';
  maxMagnitude: number;
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
}) => {
  const formatter = metric === 'value' ? formatForeignFlowValue : formatForeignFlowVolume;
  const fullFormatter = metric === 'value' ? formatFullVndTitle : formatFullSharesTitle;
  return (
    <div>
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {items.length ? (
        <ol className="mt-3 space-y-3">
          {items.map((item) => {
            const width = maxMagnitude > 0 ? `${Math.max(2, (item.magnitude / maxMagnitude) * 100)}%` : '0%';
            const details = `${item.ticker} · ${fullFormatter(item.value)} · ${foreignFlowWindowLabel(window)} · ${metric === 'value' ? 'Giá trị' : 'Khối lượng'} · ${item.display.endDate ?? 'Chưa có ngày'} · ${item.display.complete === false ? 'Chưa đủ phiên' : 'Đầy đủ'} · ${item.display.stale ? 'Dữ liệu cũ' : 'Dữ liệu sẵn sàng'}`;
            return (
              <li key={item.ticker}>
                <Tooltip content={details} className="w-full">
                  <span className="block w-full" aria-label={details}>
                    <span className="mb-1 flex items-center justify-between gap-2 text-xs">
                      <Link className="font-semibold text-foreground hover:text-cyan" to={`/vietnam/company/${item.ticker}`}>{item.ticker}</Link>
                      <span className="flex items-center gap-2 tabular-nums text-foreground"><Marker item={item} />{formatter(item.value)}</span>
                    </span>
                    <span className="block h-2.5 overflow-hidden rounded-full bg-elevated" aria-hidden="true">
                      <span
                        data-testid={`foreign-flow-${side}-bar-${item.ticker}`}
                        className={`block h-full rounded-full ${side === 'buy' ? 'bg-success/75' : 'ml-auto bg-danger/75'}`}
                        style={{ width }}
                      />
                    </span>
                  </span>
                </Tooltip>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="mt-3 rounded-md border border-dashed border-border/60 px-3 py-2 text-sm text-secondary-text">
          Chưa có mã {side === 'buy' ? 'mua' : 'bán'} ròng đủ dữ liệu.
        </p>
      )}
    </div>
  );
};

export const ForeignFlowDivergingBars = ({
  buyers,
  sellers,
  window,
  metric,
  scopeLabel = 'watchlist',
}: {
  buyers: ForeignFlowWorkspaceRow[];
  sellers: ForeignFlowWorkspaceRow[];
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
  scopeLabel?: string;
}) => {
  const maxMagnitude = Math.max(0, ...buyers.map((item) => item.magnitude), ...sellers.map((item) => item.magnitude));
  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" aria-labelledby="foreign-flow-bars-heading">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="foreign-flow-bars-heading" className="text-base font-semibold text-foreground">Dòng tiền nổi bật</h2>
          <p className="mt-1 text-xs text-secondary-text">Trong {scopeLabel} · Cùng một thang độ lớn</p>
        </div>
        <p className="text-xs text-secondary-text">{foreignFlowWindowLabel(window)}</p>
      </div>
      <div className="mt-4 grid items-start gap-5">
        <BarList title="Top bán ròng" items={sellers} side="sell" maxMagnitude={maxMagnitude} window={window} metric={metric} />
        <BarList title="Top mua ròng" items={buyers} side="buy" maxMagnitude={maxMagnitude} window={window} metric={metric} />
      </div>
    </section>
  );
};
