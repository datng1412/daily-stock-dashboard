import { Badge } from '../common';
import {
  formatCompactShareVolume,
  formatCompactVndValue,
  formatFullSharesTitle,
  formatFullVndTitle,
} from '../../utils/vietnamNumberFormat';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import { cn } from '../../utils/cn';
import type { LatestForeignFlowSessionView } from './latestForeignFlowSessionModel';

type Props = {
  view: LatestForeignFlowSessionView | null;
  loading?: boolean;
  error?: string | null;
  compact?: boolean;
};

const LatestForeignFlowCard = ({
  view,
  loading = false,
  error = null,
  compact = false,
}: Props) => {
  const metrics = [
    {
      label: 'Foreign buy volume (shares)',
      value: view?.foreignBuyVolume ?? null,
      format: formatCompactShareVolume,
      title: formatFullSharesTitle,
      signed: false,
    },
    {
      label: 'Foreign sell volume (shares)',
      value: view?.foreignSellVolume ?? null,
      format: formatCompactShareVolume,
      title: formatFullSharesTitle,
      signed: false,
    },
    {
      label: 'Foreign net volume (shares)',
      value: view?.foreignNetVolume ?? null,
      format: (value: number) => formatCompactShareVolume(value, '—', true),
      title: formatFullSharesTitle,
      signed: true,
    },
    {
      label: 'Foreign buy value (VND)',
      value: view?.foreignBuyValue ?? null,
      format: formatCompactVndValue,
      title: formatFullVndTitle,
      signed: false,
    },
    {
      label: 'Foreign sell value (VND)',
      value: view?.foreignSellValue ?? null,
      format: formatCompactVndValue,
      title: formatFullVndTitle,
      signed: false,
    },
    {
      label: 'Foreign net value (VND)',
      value: view?.foreignNetValue ?? null,
      format: (value: number) => formatCompactVndValue(value, '—', true),
      title: formatFullVndTitle,
      signed: true,
    },
  ];
  const status = view?.status ?? 'Không khả dụng';
  const statusVariant = status === 'Đủ' || status === 'Đang diễn ra'
    ? 'success'
    : status === 'Mất kết nối'
      ? 'danger'
      : 'warning';

  return (
    <section
      className="min-w-0 rounded-xl border border-border/70 bg-card p-4"
      aria-label="Foreign flow"
      data-testid="latest-foreign-flow-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="font-semibold">Foreign flow</h2>
          <p className="mt-1 text-xs text-secondary-text">
            Session: {view?.sessionDate ?? '—'} · {view?.isCurrentSession
              ? 'Dữ liệu trong phiên, chưa chốt.'
              : view?.isCompleted
                ? 'Dữ liệu phiên đã hoàn tất.'
                : 'Chưa có phiên hợp lệ.'}
          </p>
        </div>
        <Badge variant={statusVariant}>{status}</Badge>
      </div>

      {loading && !view ? (
        <p className="mt-3 text-sm text-secondary-text" role="status">Đang tải dữ liệu phiên gần nhất…</p>
      ) : error && !view ? (
        <p className="mt-3 text-sm text-secondary-text" role="status">{error}</p>
      ) : null}

      <div className={`mt-3 grid gap-2 ${compact ? 'grid-cols-2' : 'sm:grid-cols-2 xl:grid-cols-3'}`}>
        {metrics.map((item) => (
          <div key={item.label} className="min-w-0 rounded-lg border border-border/50 bg-elevated/25 p-3">
            <p className="text-xs text-secondary-text">{item.label}</p>
            <p
              className={cn(
                'mt-1 break-words font-semibold tabular-nums',
                item.signed && foreignFlowSignTextClass(item.value),
              )}
              title={item.value === null ? 'Provider field unavailable' : item.title(item.value)}
            >
              {item.value === null ? '—' : item.format(item.value)}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-3 flex min-w-0 flex-wrap gap-x-4 gap-y-1 text-xs text-secondary-text">
        <span>Source: {view?.source ?? '—'}</span>
        {view?.providerTime ? <span className="break-all">Provider time: {view.providerTime}</span> : null}
        {view?.receiptTime ? <span className="break-all">Received: {view.receiptTime}</span> : null}
      </div>
    </section>
  );
};

export default LatestForeignFlowCard;
