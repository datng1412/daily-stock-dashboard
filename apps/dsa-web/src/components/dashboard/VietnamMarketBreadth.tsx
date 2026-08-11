import { Activity, RefreshCw } from 'lucide-react';

import type { VietnamMarketBreadthResponse } from '../../api/stocks';
import { Badge, Button } from '../common';

const percent = (value?: number | null) => value == null || !Number.isFinite(value) ? '—' : `${value.toFixed(2)}%`;

type Props = {
  data: VietnamMarketBreadthResponse | null;
  loading: boolean;
  updating: boolean;
  error: string | null;
  onRefresh: () => void;
};

export const VietnamMarketBreadth = ({ data, loading, updating, error, onRefresh }: Props) => {
  const usable = Boolean(data?.usable && data.direction && data.ma20 && data.ma50 && data.participation);
  const statusLabel = loading && !data ? 'Đang tải' : data?.status === 'ready' ? 'Đầy đủ' : data?.status === 'partial' ? 'Một phần' : 'Không khả dụng';
  const statusVariant = data?.status === 'ready' ? 'success' : data?.status === 'partial' ? 'warning' : 'default';
  const finalityLabel = data?.finality === 'completed_daily'
    ? 'phiên đã hoàn tất'
    : data?.finality === 'provisional_daily'
      ? 'phiên đang diễn ra'
      : 'chưa xác nhận trạng thái phiên';

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" aria-labelledby="vn30-breadth-title" data-testid="vn30-market-breadth">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-cyan" aria-hidden="true" />
            <h2 id="vn30-breadth-title" className="text-base font-semibold text-foreground">Độ rộng VN30</h2>
            <Badge variant={statusVariant}>{statusLabel}</Badge>
          </div>
          <p className="mt-1 text-xs text-secondary-text">SSI IndexComponents hiện tại · SSI DailyOhlc</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onRefresh} disabled={loading || updating} isLoading={updating} loadingText="Đang cập nhật">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Làm mới
        </Button>
      </div>

      {loading && !data ? (
        <p className="mt-4 text-sm text-secondary-text" role="status">Đang tải độ rộng VN30…</p>
      ) : usable ? (
        <div className="mt-4 grid gap-4 md:grid-cols-[1.2fr_1fr]">
          <div>
            <p className="text-lg font-semibold text-foreground">
              <span className="text-success">{data!.direction!.advances} tăng</span>
              <span className="text-secondary-text"> · </span>
              <span className="text-danger">{data!.direction!.declines} giảm</span>
              <span className="text-secondary-text"> · {data!.direction!.unchanged} đứng giá</span>
            </p>
            <p className="mt-2 text-xs text-secondary-text">
              Phiên {data!.providerSessionDate ?? '—'} · {finalityLabel} · Coverage {data!.coverage.alignedCount}/{data!.coverage.membershipCount}
            </p>
            {data!.status === 'partial' ? (
              <p className="mt-2 text-xs text-warning">
                Thiếu {data!.coverage.missingCount}; lệch phiên {data!.coverage.sessionMismatchCount}. Không ngoại suy dữ liệu thiếu.
              </p>
            ) : null}
          </div>
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3 md:grid-cols-1 lg:grid-cols-3">
            <div className="rounded-md bg-elevated/50 p-3">
              <dt className="text-xs text-secondary-text">Trên MA20</dt>
              <dd className="mt-1 font-semibold text-foreground">{data!.ma20!.aboveCount} / {data!.ma20!.usableCount}</dd>
              <dd className="text-xs text-secondary-text">{percent(data!.ma20!.percentAbove)}</dd>
            </div>
            <div className="rounded-md bg-elevated/50 p-3">
              <dt className="text-xs text-secondary-text">Trên MA50</dt>
              <dd className="mt-1 font-semibold text-foreground">{data!.ma50!.aboveCount} / {data!.ma50!.usableCount}</dd>
              <dd className="text-xs text-secondary-text">{percent(data!.ma50!.percentAbove)}</dd>
            </div>
            <div className="rounded-md bg-elevated/50 p-3">
              <dt className="text-xs text-secondary-text">Mức tham gia</dt>
              <dd className="mt-1 font-semibold text-foreground">{percent((data!.participation!.ratio ?? null) == null ? null : data!.participation!.ratio! * 100)}</dd>
              <dd className="text-xs text-secondary-text">{data!.direction!.usableCount}/{data!.coverage.membershipCount} mã dùng được</dd>
            </div>
          </dl>
        </div>
      ) : (
        <div className="mt-4 rounded-md border border-border/60 bg-elevated/30 p-3 text-sm text-secondary-text" role="status">
          <p>Độ rộng VN30 không khả dụng.</p>
          <p className="mt-1 text-xs">{error ?? data?.membership.reason ?? 'Không có dữ liệu thành viên hoặc DailyOhlc đủ điều kiện.'}</p>
        </div>
      )}
      {updating && data ? <p className="mt-2 text-xs text-cyan" role="status">Đang cập nhật; giữ kết quả gần nhất.</p> : null}
      {error && data?.usable ? <p className="mt-2 text-xs text-warning">Lần làm mới gần nhất thất bại; đang giữ kết quả dùng được.</p> : null}
    </section>
  );
};
