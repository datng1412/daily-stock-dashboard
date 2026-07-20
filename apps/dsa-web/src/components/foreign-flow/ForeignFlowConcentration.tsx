import { formatCompactShareVolume, formatCompactVndValue } from '../../utils/vietnamNumberFormat';
import { foreignFlowWindowLabel, type ForeignFlowConcentrationModel, type ForeignFlowMetric, type ForeignFlowWindow } from './foreignFlowViewModel';

const formatShare = (value: number | null): string => value === null ? '—' : `${(value * 100).toFixed(1)}%`;

export const ForeignFlowConcentration = ({
  concentration,
  window,
  metric,
}: {
  concentration: ForeignFlowConcentrationModel;
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
}) => {
  const formatter = metric === 'value' ? formatCompactVndValue : formatCompactShareVolume;
  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" aria-labelledby="foreign-flow-concentration-heading">
      <h2 id="foreign-flow-concentration-heading" className="text-base font-semibold text-foreground">Mức độ tập trung</h2>
      <p className="mt-1 text-xs text-secondary-text">Tỷ trọng trên tổng độ lớn tuyệt đối · {foreignFlowWindowLabel(window)}</p>
      {concentration.totalAbsoluteFlow === null ? (
        <p className="mt-4 rounded-md border border-dashed border-border/60 px-3 py-3 text-sm text-secondary-text">
          Chưa đủ dữ liệu để tính mức độ tập trung.
        </p>
      ) : (
        <>
          <dl className="mt-4 grid grid-cols-3 gap-3">
            {[
              ['Top 1', concentration.top1AbsoluteShare],
              ['Top 3', concentration.top3AbsoluteShare],
              ['Top 5', concentration.top5AbsoluteShare],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-md bg-elevated/50 px-3 py-3">
                <dt className="text-xs text-secondary-text">{label}</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums text-foreground">{formatShare(value as number | null)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-xs text-secondary-text">
            {concentration.eligibleCount} mã khác 0 · Tổng độ lớn {formatter(concentration.totalAbsoluteFlow, '—')}
          </p>
        </>
      )}
    </section>
  );
};
