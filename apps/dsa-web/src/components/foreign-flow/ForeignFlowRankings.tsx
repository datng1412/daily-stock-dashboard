import { Link } from 'react-router-dom';
import type { VietnamForeignFlowBatchSymbol, VietnamForeignFlowRankingEntry } from '../../api/stocks';
import { cn } from '../../utils/cn';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import { formatCompactShareVolume, formatCompactVndValue, formatFullSharesTitle, formatFullVndTitle } from '../../utils/vietnamNumberFormat';
import { Badge } from '../common';
import { buildForeignFlowRankings, foreignFlowWindowLabel, type ForeignFlowMetric, type ForeignFlowWindow } from './foreignFlowViewModel';

const RankingList = ({
  title,
  entries,
  metric,
  emptyCopy,
  requestedSessions,
}: {
  title: string;
  entries: VietnamForeignFlowRankingEntry[];
  metric: ForeignFlowMetric;
  emptyCopy: string;
  requestedSessions: 1 | 5 | 20;
}) => (
  <div className="self-start rounded-lg border border-border/70 bg-card p-4">
    <h3 className="text-sm font-semibold text-foreground">{title}</h3>
    {entries.length ? (
      <ol className="mt-3 space-y-2">
        {entries.map((entry, index) => (
          <li key={entry.ticker} className="flex items-center justify-between gap-3 rounded-md bg-elevated/40 px-3 py-2">
            <div className="min-w-0">
              <span className="mr-2 text-xs text-secondary-text">{index + 1}</span>
              <Link className="font-semibold text-foreground hover:text-cyan" to={`/vietnam/company/${entry.ticker}`}>{entry.ticker}</Link>
              <div className="mt-1 flex flex-wrap gap-1 text-[11px] text-secondary-text">
                <span>{entry.tradingDate ?? 'Chưa có ngày'}</span>
                {entry.dataState === 'stale' ? <Badge variant="warning">Cũ</Badge> : null}
                {!entry.complete && Number.isInteger(entry.coveredSessions) && entry.coveredSessions >= 0 && entry.coveredSessions <= requestedSessions
                  ? <Badge>{entry.coveredSessions}/{requestedSessions} phiên</Badge>
                  : null}
              </div>
            </div>
            <span
              className={cn('shrink-0 font-medium tabular-nums', foreignFlowSignTextClass(entry.value))}
              aria-label={`Giá trị đầy đủ: ${metric === 'value' ? formatFullVndTitle(entry.value) : formatFullSharesTitle(entry.value)}`}
            >
              {metric === 'value'
                ? formatCompactVndValue(entry.value, '—', true)
                : formatCompactShareVolume(entry.value, '—', true)}
            </span>
          </li>
        ))}
      </ol>
    ) : <p className="mt-3 rounded-md border border-dashed border-border/60 px-3 py-2 text-sm text-secondary-text">{emptyCopy}</p>}
  </div>
);

export const ForeignFlowRankings = ({
  rows,
  window,
  metric,
}: {
  rows: VietnamForeignFlowBatchSymbol[];
  window: ForeignFlowWindow;
  metric: ForeignFlowMetric;
}) => {
  const rankings = buildForeignFlowRankings(rows, window, metric, 10);
  const requestedSessions = window === 'today' ? 1 : Number(window) as 5 | 20;
  return (
    <section aria-labelledby="foreign-flow-rankings-heading">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 id="foreign-flow-rankings-heading" className="text-base font-semibold text-foreground">Xếp hạng</h2>
        <Badge variant="info">Trong watchlist</Badge>
        <Badge>{foreignFlowWindowLabel(window)}</Badge>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <RankingList title="Top mua ròng trong watchlist" entries={rankings.topBuy} metric={metric} emptyCopy="Chưa có mã mua ròng đủ dữ liệu trong phạm vi này." requestedSessions={requestedSessions} />
        <RankingList title="Top bán ròng trong watchlist" entries={rankings.topSell} metric={metric} emptyCopy="Chưa có mã bán ròng đủ dữ liệu trong phạm vi này." requestedSessions={requestedSessions} />
      </div>
    </section>
  );
};
