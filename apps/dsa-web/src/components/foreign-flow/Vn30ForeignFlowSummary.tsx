import type { VietnamVn30ForeignFlowResponse } from '../../api/stocks';
import { formatForeignFlowValue, formatForeignFlowVolume } from '../../utils/vietnamNumberFormat';
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
  const dataDate = window === 'today' ? data.latest?.tradingDate : data.windows[window].endDate;
  const anomalySessions = window === 'today'
    ? data.latest?.suspiciousZeroSession && data.latest.tradingDate ? [data.latest.tradingDate] : []
    : data.windows[window].anomalySessions ?? [];
  const formatter = metric === 'value' ? formatForeignFlowValue : formatForeignFlowVolume;
  const cards = [
    { label: 'Tổng mua', value: buy, signed: false },
    { label: 'Tổng bán', value: sell, signed: false },
    { label: 'Mua bán ròng', value: net, signed: true },
  ];
  return (
    <section aria-labelledby="vn30-foreign-flow-summary-heading">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 id="vn30-foreign-flow-summary-heading" className="text-base font-semibold text-foreground">Dòng tiền ngoại rổ VN30 hiện tại</h2>
        <Badge variant="info">{window === 'today' ? 'Phiên gần nhất' : `${window} phiên`}</Badge>
        <Badge variant={data.dataState === 'ready' ? 'success' : data.dataState === 'unavailable' ? 'danger' : 'warning'}>{stateLabel(data.dataState)}</Badge>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {cards.map((card) => (
          <div key={card.label} className="rounded-lg border border-border/70 bg-card p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-secondary-text">{card.label}</p>
            <p className={cn('mt-2 text-xl font-semibold tabular-nums', card.signed ? foreignFlowSignTextClass(card.value) : 'text-foreground')}>{formatter(card.value)}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-secondary-text">
        Thành phần: VN30 hiện tại · Nguồn: tổng hợp dữ liệu SSI V3 theo từng mã · Ngày dữ liệu mới nhất: {dataDate ?? '—'}.
      </p>
      <p className="mt-1 text-xs text-secondary-text">
        Coverage: {data.componentCounts.usable}/{data.membership.memberCount} mã tại {data.decompositionDate ?? '—'} · Lịch sử thành phần theo từng kỳ: chưa áp dụng.
      </p>
      {data.canonical.capabilityStatus === 'unsupported' ? (
        <p className="mt-1 text-xs text-secondary-text">
          SSI V3 hiện không cung cấp các trường dòng tiền ngoại trực tiếp cho VN30; dữ liệu hiển thị là phân rã theo rổ hiện tại.
        </p>
      ) : null}
      {anomalySessions.length ? (
        <p className="mt-2 rounded-md border border-warning/25 bg-warning/5 px-3 py-2 text-xs text-secondary-text" role="note">
          Một số phiên có dữ liệu ngoại bằng 0 cho toàn bộ rổ theo nguồn SSI ({anomalySessions.join(', ')}).
        </p>
      ) : null}
    </section>
  );
};
