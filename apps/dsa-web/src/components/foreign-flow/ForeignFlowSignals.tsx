import type {
  VietnamForeignFlowSignalDirection,
  VietnamForeignFlowSignals,
} from '../../api/stocks';
import { cn } from '../../utils/cn';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import { formatForeignFlowPercent, formatForeignFlowValue } from '../../utils/vietnamNumberFormat';
import { foreignFlowSignalLabel } from './foreignFlowSignalModel';

const DirectionCard = ({ label, signal }: {
  label: string;
  signal: VietnamForeignFlowSignalDirection;
}) => (
  <article className="rounded-lg border border-border/70 bg-elevated/30 p-3">
    <p className="text-xs text-secondary-text">{label}</p>
    <p className={cn('mt-1 font-semibold', foreignFlowSignTextClass(signal.netValue))}>
      {foreignFlowSignalLabel(signal.state)}
    </p>
    <p className="mt-1 tabular-nums text-sm">{signal.netValue == null ? '—' : formatForeignFlowValue(signal.netValue)}</p>
    <p className="mt-1 text-[11px] text-secondary-text">
      {signal.coveredSessions}/{signal.requestedSessions} phiên · {signal.complete ? 'đủ' : 'chưa đủ'}
    </p>
  </article>
);

export const ForeignFlowSignalsBlock = ({ signals, title = 'Tín hiệu dòng tiền ngoại', limitation }: {
  signals: VietnamForeignFlowSignals;
  title?: string;
  limitation?: string;
}) => {
  const intensityDetail = signals.intensity.absolutePercentile60d == null
    ? `${signals.intensity.sampleCount60d}/60 phiên quan sát`
    : `Percentile tuyệt đối ${formatForeignFlowPercent(signals.intensity.absolutePercentile60d)}`;
  const finiteZScore = typeof signals.intensity.zScore60d === 'number'
    && Number.isFinite(signals.intensity.zScore60d)
    ? signals.intensity.zScore60d
    : null;
  return (
    <section className="rounded-xl border border-cyan/25 bg-card p-4" aria-label={title}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="mt-1 text-xs text-secondary-text">
            Giá trị ròng VND · phiên hoàn tất · {signals.latestCompletedDate ?? 'chưa có ngày dữ liệu'}
          </p>
        </div>
        <span className="rounded-full border border-border/70 px-2 py-1 text-[11px] text-secondary-text">Mô tả, không dự báo</span>
      </div>
      {limitation ? <p className="mt-3 text-xs text-warning">{limitation}</p> : null}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <DirectionCard label="1 phiên" signal={signals.direction1d} />
        <DirectionCard label="5 phiên" signal={signals.direction5d} />
        <DirectionCard label="20 phiên" signal={signals.direction20d} />
      </div>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border/70 bg-elevated/30 p-3">
          <dt className="text-xs text-secondary-text">Động lượng 5 phiên gần nhất so với 5 phiên trước</dt>
          <dd className="mt-1 font-semibold">{foreignFlowSignalLabel(signals.momentum.state)}</dd>
          <p className="mt-1 text-xs tabular-nums text-secondary-text">
            Gần nhất {signals.momentum.recent5Average == null ? '—' : `${formatForeignFlowValue(signals.momentum.recent5Average)}/phiên`}
            {' · '}Trước đó {signals.momentum.previous5Average == null ? '—' : `${formatForeignFlowValue(signals.momentum.previous5Average)}/phiên`}
          </p>
          <p className="mt-1 text-[11px] text-secondary-text">{signals.momentum.coveredSessions}/10 phiên · không chồng lấn</p>
        </div>
        <div className="rounded-lg border border-border/70 bg-elevated/30 p-3">
          <dt className="text-xs text-secondary-text">Cường độ</dt>
          <dd className="mt-1 font-semibold">{foreignFlowSignalLabel(signals.intensity.state)}</dd>
          <p className="mt-1 text-xs text-secondary-text">{intensityDetail}</p>
          {finiteZScore == null ? null : <p className="mt-1 text-[11px] text-secondary-text">z-score {finiteZScore.toFixed(2)}</p>}
        </div>
      </dl>
    </section>
  );
};
