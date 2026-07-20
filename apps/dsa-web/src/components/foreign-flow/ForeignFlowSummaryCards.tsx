import type { VietnamForeignFlowBatchResponse } from '../../api/stocks';
import { cn } from '../../utils/cn';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import { formatCompactShareVolume, formatCompactVndValue } from '../../utils/vietnamNumberFormat';
import { Badge } from '../common';
import {
  buildForeignFlowWorkspaceViewModel,
  foreignFlowWindowLabel,
  summarizeForeignFlow,
  type ForeignFlowMetric,
  type ForeignFlowWindow,
  type ForeignFlowWindowState,
} from './foreignFlowViewModel';

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

const PairedMetricCard = ({
  label,
  value,
  volume,
  metric,
}: {
  label: string;
  value: number | null;
  volume: number | null;
  metric: ForeignFlowMetric;
}) => (
  <div className="rounded-lg border border-border/70 bg-card p-4">
    <p className="text-xs font-medium uppercase tracking-wide text-secondary-text">{label}</p>
    <dl className="mt-3 grid grid-cols-2 gap-3">
      <div className={cn('rounded-md px-3 py-2', metric === 'value' ? 'bg-cyan/10' : 'bg-elevated/45')}>
        <dt className="text-[11px] text-secondary-text">Giá trị</dt>
        <dd className={cn('mt-1 font-semibold tabular-nums', label === 'Mua bán ròng' ? foreignFlowSignTextClass(value) : 'text-foreground')}>{formatCompactVndValue(value, '—', label === 'Mua bán ròng')}</dd>
      </div>
      <div className={cn('rounded-md px-3 py-2', metric === 'volume' ? 'bg-cyan/10' : 'bg-elevated/45')}>
        <dt className="text-[11px] text-secondary-text">Khối lượng</dt>
        <dd className={cn('mt-1 font-semibold tabular-nums', label === 'Mua bán ròng' ? foreignFlowSignTextClass(volume) : 'text-foreground')}>{formatCompactShareVolume(volume, '—', label === 'Mua bán ròng')}</dd>
      </div>
    </dl>
  </div>
);

const MetricCard = ({ label, value, detail, valueClassName }: { label: string; value: string; detail: string; valueClassName?: string }) => (
  <div className="rounded-lg border border-border/70 bg-card p-4">
    <p className="text-xs font-medium uppercase tracking-wide text-secondary-text">{label}</p>
    <p className={cn('mt-2 text-xl font-semibold tabular-nums', valueClassName ?? 'text-foreground')}>{value}</p>
    <p className="mt-1 text-xs text-secondary-text">{detail}</p>
  </div>
);

export const ForeignFlowSummaryCards = ({
  data,
  window,
  metric,
  scopeLabel = 'watchlist',
}: {
  data: VietnamForeignFlowBatchResponse;
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
  scopeLabel?: string;
}) => {
  const valueSummary = summarizeForeignFlow(data.rows, window, 'value');
  const volumeSummary = summarizeForeignFlow(data.rows, window, 'volume');
  const selectedWorkspace = buildForeignFlowWorkspaceViewModel(data.rows, window, metric);
  const selectedSummary = metric === 'value' ? valueSummary : volumeSummary;
  const windowLabel = foreignFlowWindowLabel(window);
  const badgeVariant = selectedSummary.selectedWindowState === 'ready'
    ? 'success'
    : selectedSummary.selectedWindowState === 'unavailable'
      ? 'danger'
      : 'warning';
  const dateDetail = selectedSummary.mixedTradingDates
    ? `Nhiều ngày kết thúc dữ liệu trong ${scopeLabel}`
    : `Dữ liệu phiên ${formatTradingDate(selectedSummary.latestTradingDate)}`;

  return (
    <section aria-labelledby="foreign-flow-summary-heading">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 id="foreign-flow-summary-heading" className="text-base font-semibold text-foreground">Tổng quan {scopeLabel}</h2>
        <Badge variant="info">{windowLabel}</Badge>
        <Badge variant={badgeVariant}>{stateCopy(selectedSummary.selectedWindowState)}</Badge>
      </div>
      {window === 'today' ? (
        <div className="grid gap-3 lg:grid-cols-3">
          <PairedMetricCard label="Tổng mua" value={valueSummary.buy.value} volume={volumeSummary.buy.value} metric={metric} />
          <PairedMetricCard label="Tổng bán" value={valueSummary.sell.value} volume={volumeSummary.sell.value} metric={metric} />
          <PairedMetricCard label="Mua bán ròng" value={valueSummary.net.value} volume={volumeSummary.net.value} metric={metric} />
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label={`Mua bán ròng ${windowLabel} · Giá trị`}
            value={formatCompactVndValue(valueSummary.net.value, '—', true)}
            valueClassName={foreignFlowSignTextClass(valueSummary.net.value)}
            detail={`${valueSummary.net.contributors}/${data.normalizedCount} mã có dữ liệu`}
          />
          <MetricCard
            label={`Mua bán ròng ${windowLabel} · Khối lượng`}
            value={formatCompactShareVolume(volumeSummary.net.value, '—', true)}
            valueClassName={foreignFlowSignTextClass(volumeSummary.net.value)}
            detail={`${volumeSummary.net.contributors}/${data.normalizedCount} mã có dữ liệu`}
          />
          <MetricCard
            label="Độ phủ cửa sổ"
            value={`${selectedWorkspace.breadth.usableCount}/${data.normalizedCount} mã`}
            detail={`${selectedWorkspace.breadth.completeCount} mã đầy đủ · ${selectedWorkspace.breadth.incompleteCount} mã chưa đủ phiên`}
          />
          <MetricCard
            label="Ngày kết thúc gần nhất"
            value={formatTradingDate(selectedSummary.latestTradingDate)}
            detail={dateDetail}
          />
        </div>
      )}
      {window === 'today' ? (
        <p className="mt-3 text-xs text-secondary-text">
          {selectedSummary.net.contributors}/{data.normalizedCount} mã có dữ liệu · {dateDetail}
        </p>
      ) : null}
    </section>
  );
};
