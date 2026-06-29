import type React from 'react';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import type { VietnamDataQualityIssue, VietnamDataQualitySummary } from '../../api/stocks';
import { Badge } from '../common';
import { cn } from '../../utils/cn';

type BadgeVariant = NonNullable<React.ComponentProps<typeof Badge>['variant']>;

type CheckKey = keyof NonNullable<VietnamDataQualitySummary['checks']>;

const CHECKS: Array<{ key: CheckKey; label: string }> = [
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

const COMPACT_CHECK_KEYS = new Set<CheckKey>(['dailyOhlc', 'intraday', 'realtime', 'tradeTape', 'profile', 'news']);
const DIAGNOSTIC_PATTERN = /(attempted endpoint|endpoint|http(?:\s*status)?\s*\d|http status|raw provider|raw error|token|authorization|access token|account)/i;

const statusVariant = (status?: string | null): BadgeVariant => {
  if (status === 'ok' || status === 'complete' || status === 'final' || status === 'unadjusted') return 'success';
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
    case 'daily_stock_price_date_mismatch':
      return {
        title: 'DailyStockPrice date differs from DailyOhlc.',
        detail: [
          safeString(fields.dailyOhlcDate) ? `DailyOhlc ${safeString(fields.dailyOhlcDate)}` : null,
          safeString(fields.dailyStockPriceDate) ? `DailyStockPrice ${safeString(fields.dailyStockPriceDate)}` : null,
        ].filter(Boolean).join(' | '),
      };
    case 'daily_stock_price_partial':
      return { title: 'DailyStockPrice enrichment partial.', detail: null };
    case 'profile_partial':
      return { title: 'Profile partial. Some metadata is unavailable.', detail: null };
    case 'profile_unavailable':
      return { title: 'Profile unavailable. Daily SSI data is still available.', detail: null };
    case 'final_close_status_unknown':
      return { title: 'Final close status unknown.', detail: null };
    case 'adjusted_price_status_unknown':
      return { title: 'Adjusted price status unknown.', detail: null };
    case 'intraday_stale_or_mismatched':
      return { title: 'SSI intraday unavailable for the latest daily date.', detail: null };
    case 'intraday_cadence_mismatch':
      return {
        title: 'SSI intraday cadence differs from the requested timeframe.',
        detail: [
          safeString(fields.requestedTimeframe) ? `requested ${safeString(fields.requestedTimeframe)}` : null,
          safeString(fields.actualGranularity) ? `actual ${safeString(fields.actualGranularity)}` : null,
          safeString(fields.cadenceStatus),
        ].filter(Boolean).join(' | '),
      };
    case 'intraday_unavailable_rate_limited':
      return { title: 'SSI intraday rate-limited by provider.', detail: null };
    case 'intraday_unavailable_date_mismatch':
      return { title: 'SSI intraday latest candle date differs from daily date.', detail: null };
    case 'intraday_unavailable_no_rows':
      return { title: 'SSI intraday returned no usable candles.', detail: null };
    case 'intraday_unavailable_provider_error':
      return { title: 'SSI intraday provider unavailable.', detail: null };
    case 'intraday_unavailable_unknown':
      return { title: 'SSI intraday unavailable; reason unknown.', detail: null };
    case 'intraday_unavailable':
      return { title: 'SSI intraday unavailable.', detail: null };
    case 'intraday_disabled':
      return { title: 'SSI intraday disabled.', detail: null };
    case 'realtime_config_disabled':
      return { title: 'SSI realtime streaming disabled.', detail: null };
    case 'realtime_not_started':
      return { title: 'SSI realtime manager not started.', detail: null };
    case 'realtime_bootstrap_symbols_empty':
      return { title: 'SSI realtime bootstrap symbols empty.', detail: null };
    case 'realtime_ticker_not_bootstrapped':
      return { title: 'Ticker not in SSI realtime bootstrap list.', detail: null };
    case 'realtime_running_idle':
      return { title: 'SSI realtime stream running idle.', detail: null };
    case 'realtime_cache_empty':
      return { title: 'SSI realtime cache empty for this ticker.', detail: null };
    case 'realtime_cache_stale':
      return { title: 'SSI realtime cache stale.', detail: null };
    case 'realtime_connection_error':
      return { title: 'SSI realtime connection unavailable.', detail: null };
    case 'realtime_auth_or_entitlement_failure':
      return { title: 'SSI realtime auth or entitlement failed.', detail: null };
    case 'realtime_network_or_tls_failure':
      return { title: 'SSI realtime network or TLS issue.', detail: null };
    case 'realtime_rate_limited':
      return { title: 'SSI realtime rate-limited by provider.', detail: null };
    case 'realtime_unknown':
      return { title: 'SSI realtime unavailable; reason unknown.', detail: null };
    case 'realtime_unavailable':
      return { title: 'SSI realtime unavailable.', detail: null };
    case 'realtime_disabled':
      return { title: 'SSI realtime disabled.', detail: null };
    case 'trade_tape_latest_trade_stream_only':
      return { title: 'Historical trade tape unavailable; X-TRADE is latest-trade stream only.', detail: null };
    case 'trade_tape_unavailable_no_rows':
      return { title: 'SSI trade tape returned no trade rows.', detail: null };
    case 'trade_tape_unavailable_provider_error':
      return { title: 'SSI trade tape provider unavailable.', detail: null };
    case 'trade_tape_unavailable_unknown':
      return { title: 'SSI trade tape unavailable; reason unknown.', detail: null };
    case 'trade_tape_not_implemented':
      return { title: 'Historical trade tape not proven by current SSI evidence.', detail: null };
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

export const DataQualitySummary: React.FC<{
  summary?: VietnamDataQualitySummary | null;
  className?: string;
  compact?: boolean;
}> = ({
  summary,
  className,
  compact = false,
}) => {
  if (!summary) return null;

  const issues = summary.issues ?? [];
  const checks = summary.checks ?? {};
  const visibleChecks = CHECKS
    .filter((check) => !compact || COMPACT_CHECK_KEYS.has(check.key))
    .map((check) => ({ ...check, status: checks[check.key] }))
    .filter((check) => check.status !== undefined && check.status !== null && check.status !== '');
  const visibleIssues = compact ? issues.slice(0, 2) : issues;
  const noIssues = issues.length === 0;

  return (
    <section
      className={cn(
        'rounded-lg border border-border/70 bg-card shadow-soft-card',
        compact ? 'p-3 shadow-none' : 'p-4',
        className,
      )}
      aria-label="Data Quality Summary"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {compact ? (
            <h3 className="text-sm font-semibold text-foreground">Data quality</h3>
          ) : (
            <h2 className="text-base font-semibold text-foreground">Data Quality Summary</h2>
          )}
          <div className={cn('mt-2 flex flex-wrap gap-2', compact ? 'text-xs' : 'text-sm')}>
            <Badge variant={statusVariant(summary.overallStatus)} size={compact ? 'sm' : 'md'}>
              Data quality: {safeStatusLabel(summary.overallStatus).toLowerCase()}
            </Badge>
            {summary.canonicalPriceSource ? (
              <Badge variant="info" size={compact ? 'sm' : 'md'}>Canonical price source: {summary.canonicalPriceSource}</Badge>
            ) : null}
          </div>
        </div>
        {noIssues ? (
          <div className={cn('inline-flex items-center gap-2 rounded-lg border border-success/20 bg-success/10 px-3 py-2 text-success', compact ? 'text-xs' : 'text-sm')}>
            <CheckCircle2 className="h-4 w-4" />
            {compact ? 'No issues detected.' : 'No data quality issues detected.'}
          </div>
        ) : null}
      </div>

      {!noIssues ? (
        <ul className={cn('grid gap-2', compact ? 'mt-3' : 'mt-4')}>
          {visibleIssues.map((issue, index) => {
            const copy = formatIssueCopy(issue);
            return (
              <li key={`${issue.code ?? 'issue'}-${index}`} className={cn('flex gap-3 rounded-lg border border-border/50 bg-elevated/35', compact ? 'p-2' : 'p-3')}>
                {issue.severity === 'warning' ? (
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-warning" />
                ) : (
                  <Info className="mt-0.5 h-4 w-4 flex-none text-cyan" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className={cn('font-medium text-foreground', compact ? 'text-xs' : 'text-sm')}>{copy.title}</p>
                    <Badge variant={issueVariant(issue.severity)}>{safeStatusLabel(issue.severity)}</Badge>
                  </div>
                  {copy.detail ? <p className="mt-1 text-xs text-secondary-text">{copy.detail}</p> : null}
                </div>
              </li>
            );
          })}
          {compact && issues.length > visibleIssues.length ? (
            <li className="text-xs text-secondary-text">{issues.length - visibleIssues.length} more data-quality issue(s) hidden.</li>
          ) : null}
        </ul>
      ) : null}

      {visibleChecks.length > 0 && compact ? (
        <details className="mt-3 text-xs text-secondary-text">
          <summary className="cursor-pointer font-medium text-foreground">Section checks</summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {visibleChecks.map((check) => (
              <Badge key={check.key} variant={statusVariant(check.status)} className="capitalize">
                {check.label}: {safeStatusLabel(check.status)}
              </Badge>
            ))}
          </div>
        </details>
      ) : null}

      {visibleChecks.length > 0 && !compact ? (
        <div className={cn('flex flex-wrap gap-2', compact ? 'mt-3' : 'mt-4')}>
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
