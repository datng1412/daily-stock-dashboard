import type React from 'react';
import { Badge } from '../common';
import { cn } from '../../utils/cn';
import {
  formatCompactVnPrice,
  formatFullVndTitle,
  ssiBoardPriceValueClass,
} from '../../utils/vietnamNumberFormat';
import type { VietnamOptionalLiveStatus, VietnamOrderBook, VietnamOrderBookLevel } from '../../api/stocks';

const FULL_SHARES_FORMATTER = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 0,
});

const finiteNumber = (value?: number | string | null): number | null => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

const formatOrderBookVolume = (value?: number | string | null) => {
  const numeric = finiteNumber(value);
  if (numeric === null) {
    if (typeof value === 'string' && value.trim()) return value;
    return '—';
  }
  return FULL_SHARES_FORMATTER.format(numeric);
};

const statusVariant = (status?: string | null): React.ComponentProps<typeof Badge>['variant'] => {
  if (status === 'ok') return 'success';
  if (status === 'stale') return 'warning';
  if (status === 'disabled') return 'default';
  if (status === 'unavailable' || status === 'error') return 'warning';
  return 'default';
};

const statusLabel = (status?: string | null) => {
  if (!status) return 'unavailable';
  return status.replaceAll('_', ' ');
};

const reasonText = (status?: VietnamOptionalLiveStatus | null, orderBook?: VietnamOrderBook | null) => {
  const explicit = status?.message || orderBook?.staleReason;
  if (explicit) return explicit;
  const reason = status?.reasonCode || status?.classification;
  if (reason) return reason.replaceAll('_', ' ');
  if (status?.status === 'disabled') return 'Order book disabled.';
  return 'Order book unavailable.';
};

const isStaleOrderBook = (status?: VietnamOptionalLiveStatus | null, orderBook?: VietnamOrderBook | null) => (
  status?.status === 'stale'
  || status?.classification === 'stale'
  || status?.reasonCode === 'stale'
  || orderBook?.isStale === true
);

const validLevel = (level?: VietnamOrderBookLevel | null): level is VietnamOrderBookLevel => (
  Boolean(level)
  && finiteNumber(level?.level) !== null
  && finiteNumber(level?.price) !== null
  && finiteNumber(level?.volume) !== null
);

const levelsByNumber = (levels?: VietnamOrderBookLevel[]) => {
  const output = new Map<number, VietnamOrderBookLevel>();
  (levels ?? []).forEach((level) => {
    if (!validLevel(level)) return;
    const levelNumber = finiteNumber(level.level);
    if (levelNumber === null || levelNumber < 1) return;
    output.set(levelNumber, level);
  });
  return output;
};

export const OrderBookLadder: React.FC<{
  orderBook?: VietnamOrderBook | null;
  status?: VietnamOptionalLiveStatus | null;
  referencePrice?: number | null;
  ceilingPrice?: number | null;
  floorPrice?: number | null;
  className?: string;
}> = ({ orderBook, status, referencePrice, ceilingPrice, floorPrice, className }) => {
  const bidsByLevel = levelsByNumber(orderBook?.bids);
  const asksByLevel = levelsByNumber(orderBook?.asks);
  const levelNumbers = Array.from(new Set([...bidsByLevel.keys(), ...asksByLevel.keys()])).sort((left, right) => left - right);
  const hasRows = levelNumbers.length > 0;
  const stale = isStaleOrderBook(status, orderBook);
  const publicStatus = stale ? 'stale' : (status?.status ?? (hasRows ? 'ok' : 'unavailable'));

  return (
    <section className={cn('rounded-lg border border-border/60 bg-elevated/30 p-4', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Order Book — SSI X-QUOTE</h3>
          <p className="mt-1 text-xs text-secondary-text">
            Optional bid/ask ladder from the SSI X-QUOTE streaming cache. It does not change the DailyOhlc latest price.
          </p>
        </div>
        <div className="flex flex-wrap gap-1">
          <Badge variant={statusVariant(publicStatus)}>{statusLabel(publicStatus)}</Badge>
          <Badge variant="default">SSI X-QUOTE</Badge>
        </div>
      </div>

      {hasRows ? (
        <>
          {stale ? (
            <p className="mt-3 rounded-lg border border-warning/20 bg-warning/10 p-2 text-xs text-warning">
              Last available order book is stale: {reasonText(status, orderBook)}
            </p>
          ) : null}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-xs">
              <thead className="border-b border-border/70 uppercase text-secondary-text">
                <tr>
                  <th className="py-2 pr-3 text-center">Level</th>
                  <th className="px-3 py-2 text-right">Bid Vol</th>
                  <th className="px-3 py-2 text-right">Bid Price</th>
                  <th className="px-3 py-2 text-right">Ask Price</th>
                  <th className="px-3 py-2 text-right">Ask Vol</th>
                </tr>
              </thead>
              <tbody>
                {levelNumbers.map((levelNumber) => {
                  const bid = bidsByLevel.get(levelNumber);
                  const ask = asksByLevel.get(levelNumber);
                  return (
                    <tr key={`order-book-level-${levelNumber}`} className="border-b border-border/40 text-secondary-text">
                      <td className="py-2 pr-3 text-center tabular-nums">{levelNumber}</td>
                      <td className="px-3 py-2 text-right tabular-nums" title={bid ? `${formatOrderBookVolume(bid.volume)} shares` : undefined}>
                        {bid ? formatOrderBookVolume(bid.volume) : <span aria-label={`Bid level ${levelNumber} unavailable`}>—</span>}
                      </td>
                      <td
                        className={cn('px-3 py-2 text-right font-medium tabular-nums', ssiBoardPriceValueClass(bid?.price, referencePrice, ceilingPrice, floorPrice))}
                        title={formatFullVndTitle(bid?.price)}
                      >
                        {bid ? formatCompactVnPrice(bid.price) : <span aria-label={`Bid price level ${levelNumber} unavailable`}>—</span>}
                      </td>
                      <td
                        className={cn('px-3 py-2 text-right font-medium tabular-nums', ssiBoardPriceValueClass(ask?.price, referencePrice, ceilingPrice, floorPrice))}
                        title={formatFullVndTitle(ask?.price)}
                      >
                        {ask ? formatCompactVnPrice(ask.price) : <span aria-label={`Ask price level ${levelNumber} unavailable`}>—</span>}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums" title={ask ? `${formatOrderBookVolume(ask.volume)} shares` : undefined}>
                        {ask ? formatOrderBookVolume(ask.volume) : <span aria-label={`Ask level ${levelNumber} unavailable`}>—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-secondary-text">
            Source: SSI X-QUOTE{orderBook?.time ? ` · time ${orderBook.time}` : ''}{orderBook?.ageSeconds != null ? ` · age ${orderBook.ageSeconds}s` : ''}.
          </p>
        </>
      ) : (
        <p className="mt-3 text-sm text-secondary-text">
          {reasonText(status, orderBook)}
        </p>
      )}
    </section>
  );
};
