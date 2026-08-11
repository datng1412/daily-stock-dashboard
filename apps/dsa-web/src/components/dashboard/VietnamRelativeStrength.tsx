import { Activity, RefreshCw } from 'lucide-react';

import type { VietnamRelativeStrengthComparison, VietnamRelativeStrengthResponse } from '../../api/stocks';
import { Badge, Button } from '../common';

const windows = ['1d', '5d', '20d'] as const;

const signed = (value: number | null | undefined, suffix: '%' | 'pp') => {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}${suffix}`;
};

const label = (key: string, comparison: VietnamRelativeStrengthComparison) => {
  if (key === 'vnindex') return 'vs VNINDEX';
  if (key === 'vn30') return 'vs VN30';
  return comparison.benchmarkName ? `vs ${comparison.benchmarkName}` : 'vs Industry peers';
};

type Props = {
  ticker?: string | null;
  data: VietnamRelativeStrengthResponse | null;
  loading: boolean;
  updating: boolean;
  error: string | null;
  onRefresh: () => void;
};

export const VietnamRelativeStrength = ({ ticker, data, loading, updating, error, onRefresh }: Props) => {
  if (!ticker) return null;
  const comparisons = Object.entries(data?.comparisons ?? {}) as Array<[string, VietnamRelativeStrengthComparison]>;
  const usable = Boolean(data?.usable && comparisons.length);
  const status = loading && !data ? 'Loading' : data?.status === 'ready' ? 'Ready' : data?.status === 'partial' ? 'Partial' : 'Unavailable';

  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" aria-labelledby="relative-strength-title" data-testid="relative-strength">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-cyan" aria-hidden="true" />
            <h2 id="relative-strength-title" className="text-base font-semibold text-foreground">Relative Strength · {ticker}</h2>
            <Badge variant={data?.status === 'ready' ? 'success' : data?.status === 'partial' ? 'warning' : 'default'}>{status}</Badge>
          </div>
          <p className="mt-1 text-xs text-secondary-text">Completed-session return difference in percentage points; descriptive only.</p>
        </div>
        <Button aria-label="Refresh relative strength" variant="ghost" size="sm" onClick={onRefresh} disabled={loading || updating} isLoading={updating} loadingText="Refreshing relative strength">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {loading && !data ? (
        <p className="mt-4 text-sm text-secondary-text" role="status">Loading relative performance for {ticker}…</p>
      ) : usable ? (
        <>
          <div className="mt-4 max-w-full overflow-x-auto" data-testid="relative-strength-scroll">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="border-b border-border/70 text-left text-xs text-secondary-text">
                <tr>
                  <th className="px-2 py-2 font-medium">Comparison</th>
                  {windows.map((window) => <th key={window} className="px-2 py-2 text-right font-medium">{window.toUpperCase()}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {comparisons.map(([key, comparison]) => (
                  <tr key={key} data-testid={`relative-strength-row-${key}`}>
                    <td className="px-2 py-2.5">
                      <div className="font-medium text-foreground">{label(key, comparison)}</div>
                      <div className="text-xs text-secondary-text">{comparison.status === 'unavailable' ? 'No exact aligned window' : comparison.source}</div>
                    </td>
                    {windows.map((window) => {
                      const value = comparison.windows[window];
                      const title = value?.relativePerformancePp == null
                        ? value?.reason ?? 'Unavailable'
                        : `${ticker} ${signed(value.stockReturnPct, '%')} · benchmark ${signed(value.benchmarkReturnPct, '%')} · ${value.startSession} to ${value.endSession}`;
                      return (
                        <td key={window} className="px-2 py-2.5 text-right" title={title}>
                          <div className="font-medium text-foreground">{signed(value?.relativePerformancePp, 'pp')}</div>
                          <div className="text-xs text-secondary-text">{value?.stockReturnPct == null ? '—' : `${signed(value.stockReturnPct, '%')} / ${signed(value.benchmarkReturnPct, '%')}`}</div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="mt-3 text-xs text-secondary-text">
            <summary className="cursor-pointer">Method and provenance</summary>
            <p className="mt-2">Stock: SSI DailyOhlc. VNINDEX/VN30: SSI indexSummary indexValue on exact aligned provider sessions.</p>
            <p className="mt-1">Industry: equal-weight current VN30 same-ICB peers excluding {ticker}; not an official sector index and not historically constituent-correct.</p>
          </details>
        </>
      ) : (
        <div className="mt-4 rounded-md border border-border/60 bg-elevated/30 p-3 text-sm text-secondary-text" role="status">
          <p>Relative performance is unavailable for {ticker}.</p>
          <p className="mt-1 text-xs">{error ?? 'Exact stock, benchmark, or current peer sessions are insufficient.'}</p>
        </div>
      )}
      {updating && data ? <p className="mt-2 text-xs text-cyan" role="status">Refreshing; showing the latest usable result for {ticker}.</p> : null}
      {error && data?.usable ? <p className="mt-2 text-xs text-warning">The latest refresh failed; retained data remains visible.</p> : null}
    </section>
  );
};
