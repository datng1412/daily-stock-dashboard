import { useState } from 'react';
import type {
  VietnamForeignFlowBatchResponse,
  VietnamForeignFlowRankingPair,
} from '../../api/stocks';
import { buildForeignFlowRankings, type ForeignFlowWindow } from '../foreign-flow/foreignFlowViewModel';
import { cn } from '../../utils/cn';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import { formatCompactVndValue, formatFullVndTitle } from '../../utils/vietnamNumberFormat';
import { Badge, Button } from '../common';

type RankingMetric = 'latest' | '5d' | '20d';

const metricOptions: Array<{ id: RankingMetric; label: string }> = [
  { id: 'latest', label: 'Phiên gần nhất' },
  { id: '5d', label: '5 phiên' },
  { id: '20d', label: '20 phiên' },
];

const rankingFor = (data: VietnamForeignFlowBatchResponse, metric: RankingMetric): VietnamForeignFlowRankingPair => {
  const window: ForeignFlowWindow = metric === '5d' ? '5' : metric === '20d' ? '20' : 'today';
  return buildForeignFlowRankings(data.rows, window, 'value', 5);
};

const RankingList = ({
  title,
  entries,
  emptyCopy,
  requestedSessions,
}: {
  title: string;
  entries: VietnamForeignFlowRankingPair['topBuy'];
  emptyCopy: string;
  requestedSessions: 1 | 5 | 20;
}) => (
  <div>
    <h3 className="text-sm font-semibold text-foreground">{title}</h3>
    {entries.length ? (
      <ol className="mt-2 space-y-2">
        {entries.map((entry) => (
          <li key={entry.ticker} className="flex items-center justify-between gap-3 rounded-md border border-border/50 bg-elevated/30 px-3 py-2">
            <div className="min-w-0">
              <a className="font-semibold text-foreground hover:text-cyan" href={`/vietnam/company/${entry.ticker}`}>
                {entry.ticker}
              </a>
              <div className="mt-0.5 flex flex-wrap gap-1 text-[11px] text-secondary-text">
                <span>{entry.tradingDate ?? 'Ngày chưa có'}</span>
                {entry.dataState === 'stale' ? <Badge variant="warning">Cũ</Badge> : null}
                {!entry.complete && Number.isInteger(entry.coveredSessions) && entry.coveredSessions >= 0 && entry.coveredSessions <= requestedSessions
                  ? <Badge variant="default">{entry.coveredSessions}/{requestedSessions} phiên</Badge>
                  : null}
              </div>
            </div>
            <span
              className={cn('shrink-0 font-medium tabular-nums', foreignFlowSignTextClass(entry.value))}
              aria-label={`Giá trị đầy đủ: ${formatFullVndTitle(entry.value)}`}
            >
              {formatCompactVndValue(entry.value, '—', true)}
            </span>
          </li>
        ))}
      </ol>
    ) : <p className="mt-2 text-sm text-secondary-text">{emptyCopy}</p>}
  </div>
);

export const ForeignFlowWatchlistRankings = ({
  data,
  loading = false,
  updating = false,
  error,
  totalTickerCount,
  onRetry,
}: {
  data?: VietnamForeignFlowBatchResponse | null;
  loading?: boolean;
  updating?: boolean;
  error?: string | null;
  totalTickerCount: number;
  onRetry: () => void;
}) => {
  const [metric, setMetric] = useState<RankingMetric>('latest');
  const rankings = data ? rankingFor(data, metric) : null;
  const requestedSessions = metric === 'latest' ? 1 : metric === '5d' ? 5 : 20;
  const stateLabel = loading && !data
    ? 'Loading'
    : updating
      ? 'Updating'
      : data?.dataState ?? (error ? 'unavailable' : 'empty');
  const coverage = data ? `${data.usableCount}/${data.normalizedCount} mã có dữ liệu` : null;

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" data-testid="foreign-flow-rankings">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-foreground">Dòng tiền ngoại</h2>
            <Badge variant="info">Trong watchlist</Badge>
            <Badge variant={data?.dataState === 'ready' ? 'success' : data?.dataState === 'unavailable' || error ? 'danger' : 'warning'}>
              {stateLabel}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-secondary-text">
            SSI DailyStockPrice · Dữ liệu theo phiên · VND{coverage ? ` · ${coverage}` : ''}
          </p>
          {totalTickerCount > 30 ? (
            <p className="mt-1 text-xs text-warning">Đang hiển thị dữ liệu dòng tiền ngoại cho 30/{totalTickerCount} mã.</p>
          ) : null}
          {updating && data ? <p className="mt-1 text-xs text-secondary-text">Đang cập nhật; tiếp tục hiển thị dữ liệu gần nhất.</p> : null}
          {error && data ? <p className="mt-1 text-xs text-warning">Cập nhật chưa khả dụng; đang giữ dữ liệu trước đó.</p> : null}
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onRetry} disabled={loading || updating}>
          {loading || updating ? 'Đang tải...' : 'Thử lại'}
        </Button>
      </div>

      {loading && !data ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2" aria-busy="true">
          <div className="h-24 animate-pulse rounded-lg bg-elevated/60" />
          <div className="h-24 animate-pulse rounded-lg bg-elevated/60" />
        </div>
      ) : data?.dataState === 'unavailable' && !data.usableCount ? (
        <div className="mt-4 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
          Dữ liệu dòng tiền ngoại trong watchlist hiện chưa khả dụng. Không có giá trị 0 thay thế.
        </div>
      ) : data?.dataState === 'empty' ? (
        <div className="mt-4 rounded-lg border border-border/60 bg-elevated/30 p-3 text-sm text-secondary-text">
          SSI DailyStockPrice chưa trả về lịch sử dòng tiền ngoại cho các mã trong phạm vi này.
        </div>
      ) : data && rankings ? (
        <>
          <div className="mt-4 flex flex-wrap gap-1" aria-label="Khoảng xếp hạng dòng tiền ngoại">
            {metricOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                className={cn(
                  'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                  metric === option.id
                    ? 'border-cyan bg-cyan/10 text-cyan'
                    : 'border-border/70 text-secondary-text hover:text-foreground',
                )}
                onClick={() => setMetric(option.id)}
                aria-pressed={metric === option.id}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            <RankingList
              title="Top mua ròng trong watchlist"
              entries={rankings.topBuy}
              emptyCopy="Chưa có mã mua ròng trong phạm vi này."
              requestedSessions={requestedSessions}
            />
            <RankingList
              title="Top bán ròng trong watchlist"
              entries={rankings.topSell}
              emptyCopy="Chưa có mã bán ròng trong phạm vi này."
              requestedSessions={requestedSessions}
            />
          </div>
        </>
      ) : totalTickerCount ? (
        <p className="mt-4 text-sm text-secondary-text">Dữ liệu dòng tiền ngoại chưa tải.</p>
      ) : (
        <p className="mt-4 text-sm text-secondary-text">Chọn watchlist để xem so sánh dòng tiền ngoại.</p>
      )}
    </section>
  );
};
