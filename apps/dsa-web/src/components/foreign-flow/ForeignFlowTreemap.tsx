import { cn } from '../../utils/cn';
import { formatCompactShareVolume, formatCompactVndValue, formatFullSharesTitle, formatFullVndTitle } from '../../utils/vietnamNumberFormat';
import { foreignFlowWindowLabel, type ForeignFlowMetric, type ForeignFlowWindow, type ForeignFlowWorkspaceRow } from './foreignFlowViewModel';
import { layoutForeignFlowTreemap } from './foreignFlowTreemapLayout';

const WIDTH = 1_000;
const HEIGHT = 420;

export const ForeignFlowTreemap = ({
  items,
  window,
  metric,
  selectedTicker,
  onSelectTicker,
}: {
  items: ForeignFlowWorkspaceRow[];
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
  selectedTicker: string | null;
  onSelectTicker: (ticker: string) => void;
}) => {
  const rectangles = layoutForeignFlowTreemap(items, WIDTH, HEIGHT);
  const formatter = metric === 'value' ? formatCompactVndValue : formatCompactShareVolume;
  const fullFormatter = metric === 'value' ? formatFullVndTitle : formatFullSharesTitle;
  const windowLabel = foreignFlowWindowLabel(window);

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" aria-labelledby="foreign-flow-treemap-heading">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="foreign-flow-treemap-heading" className="text-base font-semibold text-foreground">Bản đồ dòng tiền · Watchlist</h2>
          <p className="mt-1 text-xs text-secondary-text">Diện tích theo độ lớn tuyệt đối · {windowLabel} · {metric === 'value' ? 'Giá trị' : 'Khối lượng'}</p>
        </div>
        <p className="text-xs text-secondary-text">{items.length} mã khác 0</p>
      </div>
      {!rectangles.length ? (
        <p className="mt-4 rounded-md border border-dashed border-border/60 px-3 py-4 text-sm text-secondary-text">
          Chưa có dữ liệu mua bán ròng để hiển thị bản đồ trong phạm vi này.
        </p>
      ) : (
        <div className="mt-4 min-h-[260px] overflow-hidden rounded-md border border-border/60 bg-elevated/30 sm:min-h-[340px]">
          <svg
            className="block h-auto min-h-[260px] w-full sm:min-h-[340px]"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            preserveAspectRatio="none"
            role="group"
            aria-label={`Bản đồ ${items.length} mã trong watchlist, ${windowLabel}, ${metric === 'value' ? 'giá trị' : 'khối lượng'}`}
          >
            {rectangles.map(({ item, x, y, width, height }) => {
              const padding = 2;
              const cellWidth = Math.max(0, width - padding * 2);
              const cellHeight = Math.max(0, height - padding * 2);
              const showTicker = cellWidth >= 42 && cellHeight >= 24;
              const showValue = cellWidth >= 105 && cellHeight >= 52;
              const showMarker = cellWidth >= 90 && cellHeight >= 76 && (item.display.stale || item.display.state === 'incomplete');
              const signCopy = item.sign === 'buy' ? 'mua ròng' : 'bán ròng';
              const completeness = item.display.state === 'incomplete'
                ? `${item.display.coveredSessions ?? 0}/${item.display.requestedSessions} phiên, chưa đầy đủ`
                : 'đầy đủ';
              const details = `${item.ticker}, ${signCopy}, ${fullFormatter(item.value)}, ${windowLabel}, ${completeness}, ${item.display.stale ? 'dữ liệu cũ' : 'dữ liệu sẵn sàng'}, ngày ${item.display.endDate ?? 'chưa có'}`;
              return (
                <g
                  key={item.ticker}
                  role="button"
                  tabIndex={0}
                  aria-label={details}
                  onClick={() => onSelectTicker(item.ticker)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onSelectTicker(item.ticker);
                    }
                  }}
                  className="cursor-pointer outline-none focus-visible:opacity-80"
                >
                  <title>{details}</title>
                  <rect
                    x={x + padding}
                    y={y + padding}
                    width={cellWidth}
                    height={cellHeight}
                    rx={6}
                    className={cn(
                      item.sign === 'buy' ? 'fill-success/25 stroke-success/80' : 'fill-danger/25 stroke-danger/80',
                      item.ticker === selectedTicker && 'stroke-cyan',
                    )}
                    strokeWidth={item.ticker === selectedTicker ? 4 : 2}
                    strokeDasharray={item.display.stale || item.display.state === 'incomplete' ? '8 5' : undefined}
                  />
                  {showTicker ? (
                    <text x={x + 12} y={y + 23} className="fill-foreground text-[15px] font-semibold pointer-events-none">{item.ticker}</text>
                  ) : null}
                  {showValue ? (
                    <text x={x + 12} y={y + 44} className="fill-foreground text-[12px] pointer-events-none">{formatter(item.value, '—', true)}</text>
                  ) : null}
                  {showMarker ? (
                    <text x={x + 12} y={y + 64} className="fill-secondary-text text-[10px] pointer-events-none">
                      {item.display.stale ? 'Cũ' : `${item.display.coveredSessions ?? 0}/${item.display.requestedSessions} phiên`}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </svg>
        </div>
      )}
    </section>
  );
};
