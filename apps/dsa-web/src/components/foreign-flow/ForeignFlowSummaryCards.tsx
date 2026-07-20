import type { VietnamForeignFlowBatchResponse } from '../../api/stocks';
import { formatCompactShareVolume, formatCompactVndValue } from '../../utils/vietnamNumberFormat';
import { Badge } from '../common';
import { summarizeForeignFlow, type ForeignFlowMetric, type ForeignFlowWindow } from './foreignFlowViewModel';

const SummaryCard = ({ label, value, detail }: { label: string; value: string; detail: string }) => (
  <div className="rounded-lg border border-border/70 bg-card p-4">
    <p className="text-xs font-medium uppercase tracking-wide text-secondary-text">{label}</p>
    <p className="mt-2 text-xl font-semibold tabular-nums text-foreground">{value}</p>
    <p className="mt-1 text-xs text-secondary-text">{detail}</p>
  </div>
);

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
  const windowLabel = window === 'today' ? 'Phiên gần nhất' : `${window} phiên`;
  const format = (value: number | null, signed = false) => formatter(value, 'Không khả dụng', signed);

  return (
    <section aria-labelledby="foreign-flow-summary-heading">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 id="foreign-flow-summary-heading" className="text-base font-semibold text-foreground">Tổng quan watchlist</h2>
        <Badge variant={data.dataState === 'ready' ? 'success' : data.dataState === 'unavailable' ? 'danger' : 'warning'}>
          {data.dataState}
        </Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <SummaryCard
          label={`NN ròng · ${windowLabel}`}
          value={format(summary.net.value, true)}
          detail={`${summary.net.contributors}/${data.normalizedCount} mã đóng góp · ${unit}`}
        />
        {window === 'today' ? (
          <>
            <SummaryCard label="NN mua · Phiên gần nhất" value={format(summary.buy.value)} detail={`${summary.buy.contributors} mã đóng góp · ${unit}`} />
            <SummaryCard label="NN bán · Phiên gần nhất" value={format(summary.sell.value)} detail={`${summary.sell.contributors} mã đóng góp · ${unit}`} />
          </>
        ) : (
          <SummaryCard
            label="Mua / bán theo cửa sổ"
            value="Không khả dụng"
            detail="Batch hiện chỉ cung cấp tổng ròng cho cửa sổ nhiều phiên."
          />
        )}
        <SummaryCard
          label="Độ phủ"
          value={`${data.usableCount}/${data.normalizedCount} mã`}
          detail={`Coverage ${Math.round(data.coverageRatio * 100)}%`}
        />
        <SummaryCard
          label="Ngày dữ liệu gần nhất"
          value={summary.latestTradingDate ?? 'Không khả dụng'}
          detail={summary.mixedTradingDates ? 'Nhiều ngày dữ liệu trong watchlist' : 'Ngày SSI DailyStockPrice gần nhất'}
        />
      </div>
    </section>
  );
};
