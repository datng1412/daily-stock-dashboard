import type { VietnamForeignFlowBatchResponse } from '../../api/stocks';
import { formatCompactShareVolume, formatCompactVndValue } from '../../utils/vietnamNumberFormat';
import { Badge } from '../common';
import {
  foreignFlowWindowLabel,
  summarizeForeignFlow,
  type ForeignFlowMetric,
  type ForeignFlowWindow,
  type ForeignFlowWindowState,
} from './foreignFlowViewModel';

const SummaryCard = ({ label, value, detail }: { label: string; value: string; detail: string }) => (
  <div className="rounded-lg border border-border/70 bg-card p-4">
    <p className="text-xs font-medium uppercase tracking-wide text-secondary-text">{label}</p>
    <p className="mt-2 text-xl font-semibold tabular-nums text-foreground">{value}</p>
    <p className="mt-1 text-xs text-secondary-text">{detail}</p>
  </div>
);

const stateCopy = (state: ForeignFlowWindowState): string => {
  if (state === 'ready') return 'Sẵn sàng';
  if (state === 'incomplete') return 'Dữ liệu chưa đầy đủ';
  if (state === 'stale') return 'Dữ liệu cũ';
  if (state === 'empty') return 'Không có dữ liệu';
  return 'Không khả dụng';
};

const formatTradingDate = (value: string | null): string => {
  if (!value) return '—';
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
};

export const ForeignFlowSummaryCards = ({
  data,
  window,
  metric,
}: {
  data: VietnamForeignFlowBatchResponse;
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
}) => {
  const summary = summarizeForeignFlow(data.rows, window, metric);
  const formatter = metric === 'value' ? formatCompactVndValue : formatCompactShareVolume;
  const unit = metric === 'value' ? 'VND' : 'cổ phiếu';
  const windowLabel = foreignFlowWindowLabel(window);
  const format = (value: number | null, signed = false) => formatter(value, '—', signed);
  const badgeVariant = summary.selectedWindowState === 'ready'
    ? 'success'
    : summary.selectedWindowState === 'unavailable'
      ? 'danger'
      : 'warning';
  const contributorDetail = window === 'today'
    ? `${summary.net.contributors}/${data.normalizedCount} mã có dữ liệu · Đơn vị: ${unit}`
    : `${summary.net.contributors}/${data.normalizedCount} mã có dữ liệu ${windowLabel.toLowerCase()} · Đơn vị: ${unit}`;

  return (
    <section aria-labelledby="foreign-flow-summary-heading">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 id="foreign-flow-summary-heading" className="text-base font-semibold text-foreground">Tổng quan watchlist</h2>
        <Badge variant="info">{windowLabel}</Badge>
        <Badge variant={badgeVariant}>{stateCopy(summary.selectedWindowState)}</Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <SummaryCard
          label="Mua bán ròng"
          value={format(summary.net.value, true)}
          detail={contributorDetail}
        />
        {window === 'today' ? (
          <>
            <SummaryCard label="Tổng mua" value={format(summary.buy.value)} detail={`${summary.buy.contributors}/${data.normalizedCount} mã có dữ liệu · Đơn vị: ${unit}`} />
            <SummaryCard label="Tổng bán" value={format(summary.sell.value)} detail={`${summary.sell.contributors}/${data.normalizedCount} mã có dữ liệu · Đơn vị: ${unit}`} />
          </>
        ) : null}
        <SummaryCard
          label="Độ phủ"
          value={`${summary.net.contributors}/${data.normalizedCount} mã`}
          detail={summary.selectedWindowState === 'incomplete' ? `Chưa đủ dữ liệu ${windowLabel.toLowerCase()} cho toàn bộ watchlist` : `Số mã có giá trị ${windowLabel.toLowerCase()}`}
        />
        <SummaryCard
          label="Ngày dữ liệu gần nhất"
          value={formatTradingDate(summary.latestTradingDate)}
          detail={summary.mixedTradingDates ? 'Nhiều ngày dữ liệu trong watchlist' : `Dữ liệu phiên ${formatTradingDate(summary.latestTradingDate)}`}
        />
      </div>
    </section>
  );
};
