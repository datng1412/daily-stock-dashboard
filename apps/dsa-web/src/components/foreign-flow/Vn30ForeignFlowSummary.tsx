import type { VietnamVn30ForeignFlowResponse } from '../../api/stocks';
import { formatCompactShareVolume, formatCompactVndValue } from '../../utils/vietnamNumberFormat';
import { cn } from '../../utils/cn';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import { Badge } from '../common';
import type { ForeignFlowMetric, ForeignFlowWindow } from './foreignFlowViewModel';

const stateLabel = (state: VietnamVn30ForeignFlowResponse['dataState']) => {
  if (state === 'ready') return 'Sẵn sàng';
  if (state === 'stale') return 'Dữ liệu cũ';
  if (state === 'partial') return 'Dữ liệu một phần';
  return 'Không khả dụng';
};

export const Vn30ForeignFlowSummary = ({
  data,
  window,
  metric,
}: {
  data: VietnamVn30ForeignFlowResponse;
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
}) => {
  const selected = window === 'today' ? data.latest : data.windows[window];
  const family = metric === 'value' ? 'Value' : 'Volume';
  const buy = selected?.[`foreignBuy${family}` as keyof typeof selected] as number | null | undefined;
  const sell = selected?.[`foreignSell${family}` as keyof typeof selected] as number | null | undefined;
  const net = selected?.[`foreignNet${family}` as keyof typeof selected] as number | null | undefined;
  const coverage = window === 'today'
    ? (metric === 'value' ? data.latest?.valueCoverageRatio : data.latest?.volumeCoverageRatio)
    : (metric === 'value' ? data.windows[window].valueCoverageRatio : data.windows[window].volumeCoverageRatio);
  const formatter = metric === 'value' ? formatCompactVndValue : formatCompactShareVolume;
  const cards = [
    { label: 'Tổng mua', value: buy, signed: false },
    { label: 'Tổng bán', value: sell, signed: false },
    { label: 'Mua bán ròng', value: net, signed: true },
  ];
  return (
    <section aria-labelledby="vn30-foreign-flow-summary-heading">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 id="vn30-foreign-flow-summary-heading" className="text-base font-semibold text-foreground">Tổng quan VN30</h2>
        <Badge variant="info">{window === 'today' ? 'Phiên gần nhất' : `${window} phiên`}</Badge>
        <Badge variant={data.dataState === 'ready' ? 'success' : data.dataState === 'unavailable' ? 'danger' : 'warning'}>{stateLabel(data.dataState)}</Badge>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {cards.map((card) => (
          <div key={card.label} className="rounded-lg border border-border/70 bg-card p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-secondary-text">{card.label}</p>
            <p className={cn('mt-2 text-xl font-semibold tabular-nums', card.signed ? foreignFlowSignTextClass(card.value) : 'text-foreground')}>{formatter(card.value, '—', card.signed)}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-secondary-text">
        Độ phủ {coverage === undefined ? '—' : `${(coverage * 100).toFixed(1)}%`} · {data.componentCounts.usable}/{data.membership.memberCount} mã có lịch sử dùng được · Thành phần hiện tại từ SSI IndexComponents
      </p>
    </section>
  );
};
