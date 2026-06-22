import type React from 'react';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import type { VietnamDataQualityIssue, VietnamDataQualitySummary } from '../../api/stocks';
import { Badge } from '../common';
import { cn } from '../../utils/cn';

type BadgeVariant = NonNullable<React.ComponentProps<typeof Badge>['variant']>;

const CHECKS: Array<{ key: keyof NonNullable<VietnamDataQualitySummary['checks']>; label: string }> = [
  { key: 'dailyOhlc', label: 'Daily OHLCV' },
  { key: 'dailyStockPrice', label: 'DailyStockPrice' },
  { key: 'finalCloseStatus', label: 'Final close' },
  { key: 'adjustedPriceStatus', label: 'Adjusted price' },
  { key: 'intraday', label: 'Intraday' },
  { key: 'realtime', label: 'Realtime' },
  { key: 'tradeTape', label: 'Trade tape' },
  { key: 'profile', label: 'Profile' },
  { key: 'news', label: 'News' },
];

const DIAGNOSTIC_PATTERN = /(attempted endpoint|endpoint|http(?:\s*status)?\s*\d|http status|raw provider|raw error|token|authorization|access token|account)/i;

const statusVariant = (status?: string | null): BadgeVariant => {
  if (status === 'ok' || status === 'final' || status === 'unadjusted') return 'success';
  if (status === 'error') return 'danger';
  if (status === 'partial' || status === 'stale' || status === 'unknown' || status === 'provisional') return 'warning';
  if (status === 'unavailable' || status === 'disabled' || status === 'not_implemented') return 'warning';
  return 'default';
};

const issueVariant = (severity?: string | null): BadgeVariant => {
  if (severity === 'error') return 'danger';
  if (severity === 'warning') return 'warning';
  return 'info';
};

const safeStatusLabel = (status?: string | null) => {
  if (!status) return 'Unknown';
  if (DIAGNOSTIC_PATTERN.test(status)) return 'Unavailable';
  if (status === 'ok') return 'OK';
  if (status === 'not_implemented') return 'Not implemented';
  return status.replaceAll('_', ' ');
};

const safeString = (value: unknown) => {
  if (typeof value !== 'string') return null;
  if (!value.trim() || DIAGNOSTIC_PATTERN.test(value)) return null;
  return value;
};

const formatNumber = (value: unknown) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value);
  }
  return null;
};

const formatIssueCopy = (issue: VietnamDataQualityIssue) => {
  const fields = issue.fields ?? {};
  switch (issue.code) {
    case 'daily_ohlc_vs_daily_stock_price_mismatch':
      return {
        title: 'DailyOhlc differs from DailyStockPrice for the same date.',
        detail: [
          safeString(fields.date),
          formatNumber(fields.dailyOhlcClose) ? `DailyOhlc ${formatNumber(fields.dailyOhlcClose)}` : null,
          formatNumber(fields.dailyStockPriceClose) ? `DailyStockPrice ${formatNumber(fields.dailyStockPriceClose)}` : null,
        ].filter(Boolean).join(' | '),
      };
    case 'profile_partial':
      return { title: 'Profile metadata partial.', detail: null };
    case 'final_close_status_unknown':
      return { title: 'Final close status unknown.', detail: null };
    case 'adjusted_price_status_unknown':
      return { title: 'Adjusted price status unknown.', detail: null };
    case 'intraday_stale_or_mismatched':
      return { title: 'SSI intraday unavailable for the latest daily date.', detail: null };
    case 'intraday_unavailable':
      return { title: 'SSI intraday unavailable.', detail: null };
    case 'intraday_disabled':
      return { title: 'SSI intraday disabled.', detail: null };
    case 'realtime_unavailable':
      return { title: 'SSI realtime unavailable.', detail: null };
    case 'realtime_disabled':
      return { title: 'SSI realtime disabled.', detail: null };
    case 'trade_tape_unavailable':
      return { title: 'SSI trade tape unavailable.', detail: null };
    case 'trade_tape_disabled':
      return { title: 'SSI trade tape disabled.', detail: null };
    case 'daily_ohlc_unavailable':
      return { title: 'Daily OHLCV unavailable.', detail: null };
    default:
      return { title: 'Data quality issue detected.', detail: null };
  }
};

export const DataQualitySummary: React.FC<{ summary?: VietnamDataQualitySummary | null; className?: string }> = ({
  summary,
  className,
}) => {
  if (!summary) return null;

  const issues = summary.issues ?? [];
  const checks = summary.checks ?? {};
  const visibleChecks = CHECKS
    .map((check) => ({ ...check, status: checks[check.key] }))
    .filter((check) => check.status !== undefined && check.status !== null && check.status !== '');
  const noIssues = issues.length === 0;

  return (
    <section className={cn('rounded-lg border border-border/70 bg-card p-4 shadow-soft-card', className)} aria-label="Data Quality Summary">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground">Data Quality Summary</h2>
          <div className="mt-2 flex flex-wrap gap-2 text-sm">
            <Badge variant={statusVariant(summary.overallStatus)} size="md">
              Data quality: {safeStatusLabel(summary.overallStatus).toLowerCase()}
            </Badge>
            {summary.canonicalPriceSource ? (
              <Badge variant="info" size="md">Canonical price source: {summary.canonicalPriceSource}</Badge>
            ) : null}
          </div>
        </div>
        {noIssues ? (
          <div className="inline-flex items-center gap-2 rounded-lg border border-success/20 bg-success/10 px-3 py-2 text-sm text-success">
            <CheckCircle2 className="h-4 w-4" />
            No data quality issues detected.
          </div>
        ) : null}
      </div>

      {!noIssues ? (
        <ul className="mt-4 grid gap-2">
          {issues.map((issue, index) => {
            const copy = formatIssueCopy(issue);
            return (
              <li key={`${issue.code ?? 'issue'}-${index}`} className="flex gap-3 rounded-lg border border-border/50 bg-elevated/35 p-3">
                {issue.severity === 'warning' ? (
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-warning" />
                ) : (
                  <Info className="mt-0.5 h-4 w-4 flex-none text-cyan" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-foreground">{copy.title}</p>
                    <Badge variant={issueVariant(issue.severity)}>{safeStatusLabel(issue.severity)}</Badge>
                  </div>
                  {copy.detail ? <p className="mt-1 text-xs text-secondary-text">{copy.detail}</p> : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}

      {visibleChecks.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {visibleChecks.map((check) => (
            <Badge key={check.key} variant={statusVariant(check.status)} className="capitalize">
              {check.label}: {safeStatusLabel(check.status)}
            </Badge>
          ))}
        </div>
      ) : null}
    </section>
  );
};
