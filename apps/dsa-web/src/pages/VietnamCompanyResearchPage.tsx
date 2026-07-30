import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import {
  stocksApi,
  type VietnamCompanyResearchResponse,
  type VietnamCurrentForeignFlowResponse,
  type VietnamRealtimeTrade,
} from '../api/stocks';
import { AppPage, Badge, Button, Loading } from '../components/common';
import { OrderBookLadder } from '../components/dashboard';
import LatestForeignFlowCard from '../components/foreign-flow/LatestForeignFlowCard';
import { selectLatestForeignFlowSession } from '../components/foreign-flow/latestForeignFlowSessionModel';
import { cn } from '../utils/cn';
import {
  CEILING_PRICE_CLASS,
  FLOOR_PRICE_CLASS,
  formatCompactShareVolume,
  formatCompactVndValue,
  formatCompactVnPrice,
  formatFullSharesTitle,
  formatFullVndTitle,
  ssiBoardPriceValueClass,
  REFERENCE_PRICE_CLASS,
} from '../utils/vietnamNumberFormat';

type StatusVariant = React.ComponentProps<typeof Badge>['variant'];

type MetricRow = {
  label: string;
  value?: number | string | null;
  formatter?: (value?: number | string | null) => string;
  titleFormatter?: (value?: number | string | null) => string | undefined;
  tone?: string;
  testId?: string;
};

type DiagnosticRow = {
  section: string;
  label: string;
  value: string;
};

const TRADE_TAPE_STARTUP_MAX_WAIT_MS = 20_000;
const SELECTED_LIVE_CONTEXT_REFRESH_INTERVAL_MS = 3_000;
const CURRENT_FOREIGN_FLOW_REFRESH_INTERVAL_MS = 15_000;

const statusVariant = (status?: string | null): StatusVariant => {
  if (status === 'ok' || status === 'complete' || status === 'ready' || status === 'completed') return 'success';
  if (status === 'loading' || status === 'reconnecting' || status === 'no_data') return 'info';
  if (status === 'partial' || status === 'incomplete' || status === 'provisional') return 'warning';
  if (status === 'not_implemented') return 'info';
  if (status === 'missing' || status === 'unavailable' || status === 'disabled') return 'warning';
  return 'default';
};

const statusLabel = (status?: string | null) => {
  if (status === 'not_implemented') return 'Not implemented yet';
  if (status === 'disabled') return 'Disabled';
  if (!status) return 'Unknown';
  return status.replaceAll('_', ' ');
};

const statusTextClass = (status?: string | null) => {
  if (status === 'ready' || status === 'ok' || status === 'complete') return 'text-success';
  if (status === 'partial' || status === 'incomplete') return 'text-warning';
  return 'text-secondary-text';
};

const formatNumber = (value?: number | string | null, digits = 0) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
  }
  if (typeof value === 'string' && value.trim()) return value;
  return '\u2014';
};

const formatPrice = (value?: number | string | null) => formatCompactVnPrice(value, '\u2014');
const formatVolume = (value?: number | string | null) => formatCompactShareVolume(value, '\u2014');
const formatVndValue = (value?: number | string | null) => formatCompactVndValue(value, '\u2014');

const formatSignedNumber = (value?: number | string | null) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const sign = value > 0 ? '+' : '';
    return `${sign}${formatNumber(value, 2)}`;
  }
  return formatNumber(value);
};

const formatSignedPriceChange = (value?: number | string | null) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const formatted = formatCompactVnPrice(Math.abs(value));
    if (value > 0) return `+${formatted}`;
    if (value < 0) return `-${formatted}`;
    return formatted;
  }
  return formatNumber(value);
};

const finiteNumber = (value?: number | string | null) => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

const formatPercent = (value?: number | string | null, signed = false) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const formatted = new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Math.abs(value));
    if (signed) {
      const sign = value > 0 ? '+' : value < 0 ? '-' : '';
      return `${sign}${formatted}%`;
    }
    return `${new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)}%`;
  }
  return formatNumber(value);
};

const formatSource = (source?: string | null) => source || 'Source pending';

const normalizeTicker = (ticker?: string) => (ticker ?? '').trim().toUpperCase().replace(/\.VN$/i, '');

const hasMetricValue = (value?: number | string | null) => (
  value !== null && value !== undefined && value !== '' && !(typeof value === 'number' && Number.isNaN(value))
);

const capabilityStatusFromValues = (
  values: Array<number | string | null | undefined>,
): 'ready' | 'partial' | 'unavailable' => {
  const present = values.map(hasMetricValue);
  if (present.every(Boolean)) return 'ready';
  if (present.some(Boolean)) return 'partial';
  return 'unavailable';
};

const tradeSideLabel = (trade: VietnamRealtimeTrade) => {
  const normalized = String(trade.side ?? '').trim().toLowerCase();
  if (normalized === 'buy') return 'Buy';
  if (normalized === 'sell') return 'Sell';
  return '—';
};

const tradeSideClass = (trade: VietnamRealtimeTrade) => {
  const normalized = String(trade.side ?? '').trim().toLowerCase();
  if (normalized === 'buy') return 'text-success';
  if (normalized === 'sell') return 'text-danger';
  return 'text-secondary-text';
};

const tradeChangeValue = (trade: VietnamRealtimeTrade, referencePrice?: number | null) => {
  const explicit = finiteNumber(trade.change ?? null);
  if (explicit !== null) return explicit;
  const price = finiteNumber(trade.price ?? null);
  const reference = finiteNumber(referencePrice ?? null);
  if (price === null || price <= 0 || reference === null || reference <= 0) return null;
  return price - reference;
};

const tradeChangePctValue = (trade: VietnamRealtimeTrade, referencePrice?: number | null) => {
  const explicit = finiteNumber(trade.changePct ?? null);
  if (explicit !== null) return explicit;
  const change = tradeChangeValue(trade, referencePrice);
  const reference = finiteNumber(referencePrice ?? null);
  if (change === null || reference === null || reference <= 0) return null;
  return (change / reference) * 100;
};

const tradeChangeClass = (value?: number | null) => {
  const numeric = finiteNumber(value ?? null);
  if (numeric === null) return 'text-secondary-text';
  if (numeric > 0) return 'text-success';
  if (numeric < 0) return 'text-danger';
  return REFERENCE_PRICE_CLASS;
};

const diagnosticLabel = (key: string) => {
  const knownLabels: Record<string, string> = {
    attemptedEndpoints: 'Attempted endpoints',
    attempted_endpoints: 'Attempted endpoints',
    lastEndpoint: 'Last endpoint',
    last_endpoint: 'Last endpoint',
    httpStatus: 'HTTP status',
    http_status: 'HTTP status',
    providerMessage: 'Provider message',
    provider_message: 'Provider message',
    rawProviderErrorSummary: 'Provider error summary',
    raw_provider_error_summary: 'Provider error summary',
    sanitizedErrorContext: 'Sanitized error context',
    sanitized_error_context: 'Sanitized error context',
    retryable: 'Retryable',
  };
  if (knownLabels[key]) return knownLabels[key];
  const words = key.replace(/([A-Z])/g, ' $1').replaceAll('_', ' ').trim();
  return words ? `${words.charAt(0).toUpperCase()}${words.slice(1)}` : key;
};

const diagnosticValueText = (value: unknown): string | null => {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    const values = value.map(diagnosticValueText).filter((entry): entry is string => Boolean(entry));
    return values.length ? values.join(', ') : null;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

const liveStatusDiagnosticRows = (
  section: string,
  diagnostics?: Record<string, unknown> | null,
): DiagnosticRow[] => (
  Object.entries(diagnostics ?? {})
    .map(([key, value]) => ({
      section,
      label: diagnosticLabel(key),
      value: diagnosticValueText(value),
    }))
    .filter((row): row is DiagnosticRow => Boolean(row.value))
);

const normalizedStatus = (value?: string | null) => String(value ?? '').trim().toLowerCase();

const safeStatusString = (value: unknown) => {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  return text || null;
};

const statusDiagnosticValue = (
  statusBlock: VietnamCompanyResearchResponse['tradeTapeStatus'] | VietnamCompanyResearchResponse['realtimeStatus'] | null | undefined,
  diagnostics: Record<string, unknown> | null | undefined,
  key: string,
) => (
  safeStatusString((statusBlock as Record<string, unknown> | null | undefined)?.[key])
  ?? safeStatusString(diagnostics?.[key])
);

const streamLifecycleState = (
  statusBlock: VietnamCompanyResearchResponse['tradeTapeStatus'] | VietnamCompanyResearchResponse['realtimeStatus'] | null | undefined,
  diagnostics: Record<string, unknown> | null | undefined,
) => normalizedStatus(
  statusDiagnosticValue(statusBlock, diagnostics, 'streamState')
  ?? statusDiagnosticValue(statusBlock, diagnostics, 'stream_state'),
);

const streamLifecycleCopy = (state: string, fallback: string) => {
  if (state === 'recovering' || state === 'awaiting_subscription') {
    return 'Reconnecting — showing last known data when available.';
  }
  if (state === 'stale') return 'Stale — showing last known data.';
  if (state === 'closed') return 'Market closed — showing last known data.';
  return fallback;
};

const tradeTapeReasonCode = (
  statusBlock: VietnamCompanyResearchResponse['tradeTapeStatus'] | null | undefined,
  diagnostics: Record<string, unknown> | null | undefined,
) => (
  safeStatusString(statusBlock?.reasonCode)
  ?? safeStatusString(statusBlock?.classification)
  ?? statusDiagnosticValue(statusBlock, diagnostics, 'reasonCode')
  ?? statusDiagnosticValue(statusBlock, diagnostics, 'reason_code')
);

const TRADE_TAPE_PENDING_REASON_CODES = new Set([
  'stream_not_started',
  'manager_not_started',
  'xtrade_not_subscribed',
  'stream_cache_empty',
  'xtrade_cache_empty',
  'cache_empty',
  'subscribed_empty',
  'streaming_trade_tape_supported',
  'unknown',
]);

const TRADE_TAPE_PENDING_STATUSES = new Set([
  'loading',
  'starting',
  'pending',
  'not_started',
  'cache_empty',
  'subscribed_empty',
  'xtrade_not_subscribed',
  'running_idle',
]);

const TRADE_TAPE_TERMINAL_REASON_CODES = new Set([
  'disabled',
  'config_disabled',
  'market_closed',
  'idle_market_closed',
  'after_hours_stale',
  'not_implemented',
  'latest_trade_stream_only',
  'unavailable_provider_error',
  'historical_trade_tape_unavailable',
  'auth_or_entitlement_failure',
]);

const isCompanyTradeTapeWarmupPending = (snapshot: VietnamCompanyResearchResponse) => {
  const statusBlock = snapshot.tradeTapeStatus;
  const diagnostics = snapshot.diagnostics?.tradeTape;
  const status = normalizedStatus(statusBlock?.status);
  const reasonCode = normalizedStatus(tradeTapeReasonCode(statusBlock, diagnostics));
  if (status === 'disabled' || status === 'not_implemented' || TRADE_TAPE_TERMINAL_REASON_CODES.has(reasonCode)) {
    return false;
  }
  const candidates = [
    status,
    reasonCode,
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'managerState')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'manager_state')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'runtimeStatus')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'runtime_status')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'streamingStatus')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'streaming_status')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'cacheStatus')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'cache_status')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'tradeTapeSubscriptionStatus')),
    normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'trade_tape_subscription_status')),
  ].filter(Boolean);
  const bufferCount = Number(
    (diagnostics?.tradeTapeBufferRowCount ?? diagnostics?.trade_tape_buffer_row_count) ?? Number.NaN,
  );
  const subscriptionStatus = normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'tradeTapeSubscriptionStatus'))
    || normalizedStatus(statusDiagnosticValue(statusBlock, diagnostics, 'trade_tape_subscription_status'));
  if (subscriptionStatus === 'subscribed' && (!Number.isFinite(bufferCount) || bufferCount === 0)) return true;
  return candidates.some((candidate) => (
    TRADE_TAPE_PENDING_STATUSES.has(candidate)
    || TRADE_TAPE_PENDING_REASON_CODES.has(candidate)
  ));
};

const hasCompanyIntradayData = (snapshot: VietnamCompanyResearchResponse) => (
  snapshot.intraday?.status === 'ok'
  && Boolean(snapshot.intraday.pulse)
  && (snapshot.intraday.candles?.length ?? 0) > 0
);

const hasCompanyRealtimeData = (snapshot: VietnamCompanyResearchResponse) => (
  snapshot.realtimeStatus?.status === 'ok'
  && Boolean(snapshot.realtimeSnapshot)
  && hasMetricValue(snapshot.realtimeSnapshot?.price ?? snapshot.realtimeSnapshot?.realtimePrice)
);

const companyIntradayCadenceText = (snapshot: VietnamCompanyResearchResponse) => {
  const intraday = snapshot.intraday;
  const cadence = intraday?.granularityLabel ?? intraday?.actualGranularity ?? intraday?.granularity ?? 'unknown';
  const requested = intraday?.requestedTimeframe ?? null;
  if (intraday?.cadenceStatus === 'matched' && requested) return `Provider cadence: ${cadence}`;
  if (intraday?.cadenceStatus === 'different_from_requested' && requested) return `Returned cadence differs from requested ${requested}: ${cadence}`;
  if (intraday?.cadenceStatus === 'irregular') return 'Provider cadence irregular';
  if (intraday?.cadenceStatus === 'unavailable') return 'Provider cadence unavailable';
  return cadence === 'unknown' || cadence === 'provider-returned' ? 'Provider cadence unknown' : `Provider cadence: ${cadence}`;
};

const hasCompanyTradeTapeData = (snapshot: VietnamCompanyResearchResponse) => (
  (snapshot.tradeTape?.length ?? 0) > 0
);

const TradeTapeRowsTable: React.FC<{
  rows: VietnamRealtimeTrade[];
  referencePrice?: number | null;
  ceilingPrice?: number | null;
  floorPrice?: number | null;
}> = ({ rows, referencePrice, ceilingPrice, floorPrice }) => (
  <div className="mt-3 overflow-x-auto">
    <table className="w-full min-w-[520px] text-left text-xs">
      <thead className="border-b border-border/70 uppercase text-secondary-text">
        <tr>
          <th className="py-2 pr-3">Time</th>
          <th className="px-3 py-2">B/S</th>
          <th className="px-3 py-2 text-right">Vol</th>
          <th className="px-3 py-2 text-right">Price</th>
          <th className="px-3 py-2 text-right">+/-</th>
          <th className="px-3 py-2 text-right">+/-(%)</th>
        </tr>
      </thead>
      <tbody>
        {rows.slice(0, 8).map((trade, index) => {
          const change = tradeChangeValue(trade, referencePrice);
          const changePct = tradeChangePctValue(trade, referencePrice);
          return (
            <tr key={`${trade.id ?? trade.sequence ?? index}-${trade.timestamp ?? trade.time ?? 'time'}`} className="border-b border-border/40 text-secondary-text">
              <td className="py-2 pr-3">{trade.timestampDisplay ?? trade.time ?? trade.timestamp ?? '-'}</td>
              <td className={cn('px-3 py-2 font-medium', tradeSideClass(trade))}>{tradeSideLabel(trade)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-secondary-text" title={formatFullSharesTitle(trade.volume)}>{formatNumber(trade.volume)}</td>
              <td className={cn('px-3 py-2 text-right font-medium tabular-nums', ssiBoardPriceValueClass(trade.price, referencePrice, ceilingPrice, floorPrice))}>
                {formatPrice(trade.price)}
              </td>
              <td className={cn('px-3 py-2 text-right font-medium tabular-nums', tradeChangeClass(change))}>{formatSignedPriceChange(change)}</td>
              <td className={cn('px-3 py-2 text-right font-medium tabular-nums', tradeChangeClass(changePct))}>{formatSignedNumber(changePct)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

const SectionShell: React.FC<{
  title: string;
  source?: string | null;
  status?: string | null;
  children: React.ReactNode;
  className?: string;
}> = ({ title, source, status, children, className }) => (
  <section className={cn('min-w-0 rounded-lg border border-border/70 bg-card p-4 shadow-soft-card', className)}>
    <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      <div className="flex flex-wrap gap-2">
        <Badge variant="default">{formatSource(source)}</Badge>
        <Badge variant={statusVariant(status)}>{statusLabel(status)}</Badge>
      </div>
    </div>
    {children}
  </section>
);

const MetricGrid: React.FC<{ rows: MetricRow[] }> = ({ rows }) => (
  <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
    {rows.map((row) => (
      <div key={row.label} className="rounded-lg border border-border/50 bg-elevated/35 p-3">
        <dt className="text-xs uppercase tracking-normal text-secondary-text">{row.label}</dt>
        <dd
          className={cn('mt-1 text-sm font-semibold text-foreground', row.tone)}
          data-testid={row.testId}
          title={row.titleFormatter?.(row.value)}
        >
          {row.formatter ? row.formatter(row.value) : formatNumber(row.value)}
        </dd>
      </div>
    ))}
  </dl>
);

const newsText = (item: Record<string, unknown>, key: string) => {
  const value = item[key];
  return typeof value === 'string' && value.trim() ? value.trim() : null;
};

const safeExternalNewsUrl = (value: string | null | undefined): string | null => {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? value : null;
  } catch {
    return null;
  }
};

const isPersonalResearchNewsItem = (item: Record<string, unknown>) => (
  newsText(item, 'providerMode') === 'local_personal_research_only'
  || newsText(item, 'rightsStatus') === 'personal_research_only'
);

const CompanyNewsSection: React.FC<{ block: VietnamCompanyResearchResponse['news'] }> = ({ block }) => {
  const items = block.items ?? [];
  return (
    <SectionShell title="News" source={block.source} status={block.status}>
      {items.length ? (
        <div className="grid gap-3">
          {items.slice(0, 3).map((item, index) => {
            const title = newsText(item, 'title') ?? 'Untitled news';
            const url = safeExternalNewsUrl(newsText(item, 'url'));
            const source = newsText(item, 'source') ?? block.source ?? null;
            const sourceName = newsText(item, 'sourceName');
            const category = newsText(item, 'category');
            const publishedAt = newsText(item, 'publishedAt') ?? newsText(item, 'published_at');
            const summary = newsText(item, 'summary');
            return (
              <article key={`${url ?? newsText(item, 'rawUrl') ?? title}-${index}`} className="rounded-lg border border-border/50 bg-elevated/35 p-3">
                {url ? (
                  <a href={url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-cyan hover:underline">
                    {title}
                  </a>
                ) : (
                  <p className="text-sm font-medium text-foreground">{title}</p>
                )}
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-secondary-text">
                  {source ? <span>{source}</span> : null}
                  {sourceName ? <span>{sourceName}</span> : null}
                  {category ? <span>{category}</span> : null}
                  {publishedAt ? <span>{publishedAt}</span> : null}
                  {source === 'Vnstock Community' ? <Badge variant="info">Vnstock Community</Badge> : null}
                  {isPersonalResearchNewsItem(item) ? <Badge variant="info">Personal research</Badge> : null}
                </div>
                {summary ? <p className="mt-2 line-clamp-2 text-sm text-secondary-text">{summary}</p> : null}
              </article>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-secondary-text">
          {block.status === 'disabled' ? 'News disabled.' : block.message || 'Not implemented yet.'}
        </p>
      )}
    </SectionShell>
  );
};

const SourceCoveragePanel: React.FC<{ snapshot: VietnamCompanyResearchResponse }> = ({ snapshot }) => (
  <SectionShell title="Source coverage" source="Backend contract" status={snapshot.status}>
    <div className="grid gap-3">
      {Array.from(new Set(snapshot.sourceCoverage.map((item) => item.group ?? 'Other'))).map((group) => (
        <div key={group}>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-secondary-text">{group}</h3>
          <div className="grid gap-1">
            {snapshot.sourceCoverage.filter((item) => (item.group ?? 'Other') === group).map((item) => (
              <div
                key={`${item.block}-${item.source ?? 'none'}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/40 bg-elevated/25 px-3 py-2 text-sm"
              >
                <span className="font-medium text-foreground">{item.block}</span>
                <span className="flex flex-wrap items-center gap-2">
                  <span className="hidden text-xs text-secondary-text sm:inline">{formatSource(item.source)}</span>
                  <Badge variant={statusVariant(item.status)}>{statusLabel(item.status)}</Badge>
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  </SectionShell>
);

const CompanyQualitySummary: React.FC<{ snapshot: VietnamCompanyResearchResponse }> = ({ snapshot }) => {
  const summary = snapshot.qualitySummary;
  if (!summary?.groups?.length) return null;
  return (
    <section className="rounded-lg border border-border/70 bg-card p-4 shadow-soft-card" aria-label="Company Research Data Summary">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-foreground">Data summary</h2>
        <Badge variant={statusVariant(summary.overallStatus)} size="md">
          {statusLabel(summary.overallStatus)}
        </Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {summary.groups.slice(0, 3).map((group) => (
          <div key={group.key} className="rounded-lg border border-border/50 bg-elevated/30 p-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-medium text-foreground">{group.label}</h3>
              <Badge variant={statusVariant(group.status)}>{statusLabel(group.status)}</Badge>
            </div>
            {group.detail ? <p className="mt-1 text-xs text-secondary-text">{group.detail}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
};

const CompanyDiagnosticsPanel: React.FC<{ snapshot: VietnamCompanyResearchResponse }> = ({ snapshot }) => {
  const rows = [
    ...liveStatusDiagnosticRows('Session context', snapshot.diagnostics?.session),
    ...liveStatusDiagnosticRows('Adjustment lineage', snapshot.diagnostics?.adjustment),
    ...liveStatusDiagnosticRows('Live channel states', snapshot.diagnostics?.liveChannels),
    ...liveStatusDiagnosticRows('DailyStockPrice capabilities', snapshot.diagnostics?.dailyStockPriceCapabilities),
    ...liveStatusDiagnosticRows('Foreign-flow lineage', snapshot.diagnostics?.foreignFlow),
    ...liveStatusDiagnosticRows('Intraday contract', snapshot.diagnostics?.intraday),
    ...liveStatusDiagnosticRows('Profile readiness', snapshot.diagnostics?.profile),
    ...liveStatusDiagnosticRows('Quality issues', {
      codes: snapshot.qualitySummary?.issueCodes ?? [],
    }),
    ...liveStatusDiagnosticRows('SSI profile metadata status', snapshot.profile.diagnostics),
    ...liveStatusDiagnosticRows('SSI DailyStockPrice status', snapshot.dailyStockPrice?.diagnostics),
    ...liveStatusDiagnosticRows('SSI intraday status', snapshot.intraday?.diagnostics),
    ...liveStatusDiagnosticRows('SSI realtime status', snapshot.diagnostics?.realtime),
    ...liveStatusDiagnosticRows('SSI trade tape status', snapshot.diagnostics?.tradeTape),
    ...liveStatusDiagnosticRows('SSI order book status', snapshot.diagnostics?.orderBook),
  ];

  if (!rows.length) return null;

  return (
    <details className="rounded-lg border border-border/60 bg-elevated/30 p-3 text-xs text-secondary-text">
      <summary className="cursor-pointer font-medium text-foreground">Show diagnostics</summary>
      <dl className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((row) => (
          <div key={`${row.section}-${row.label}`} className="rounded-lg border border-border/60 bg-card/50 p-3">
            <dt>{row.section} - {row.label}</dt>
            <dd className="mt-1 break-words font-medium text-foreground">{row.value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
};

const CompanyHeader: React.FC<{ snapshot: VietnamCompanyResearchResponse; onRefresh: () => void; refreshing: boolean }> = ({
  snapshot,
  onRefresh,
  refreshing,
}) => (
  <section className="rounded-lg border border-border/70 bg-card p-4 shadow-soft-card">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <Link to="/vietnam" className="inline-flex items-center gap-2 text-sm text-cyan hover:text-cyan-light">
          <ArrowLeft className="h-4 w-4" />
          Vietnam dashboard
        </Link>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold text-foreground">{snapshot.ticker}</h1>
          <Badge variant={statusVariant(snapshot.status)} size="md">{statusLabel(snapshot.status)}</Badge>
          <Badge variant="info" size="md">Company research</Badge>
        </div>
        {snapshot.profile.name || snapshot.profile.exchange || snapshot.profile.market ? (
          <p className="mt-2 text-sm text-secondary-text">
            {[snapshot.profile.name, snapshot.profile.exchange, snapshot.profile.market]
              .filter((value, index, values) => Boolean(value) && values.indexOf(value) === index)
              .join(' | ')}
          </p>
        ) : null}
      </div>
      <Button type="button" variant="secondary" onClick={onRefresh} isLoading={refreshing} loadingText="Refreshing">
        <RefreshCw className="h-4 w-4" />
        Refresh
      </Button>
    </div>
  </section>
);

const VietnamCompanyResearchPage: React.FC = () => {
  const params = useParams<{ ticker: string }>();
  const ticker = useMemo(() => normalizeTicker(params.ticker), [params.ticker]);
  const [snapshot, setSnapshot] = useState<VietnamCompanyResearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentFlow, setCurrentFlow] = useState<VietnamCurrentForeignFlowResponse | null>(null);
  const [currentFlowLoading, setCurrentFlowLoading] = useState(false);
  const [currentFlowError, setCurrentFlowError] = useState<string | null>(null);
  const [tradeTapeWarmupTimedOut, setTradeTapeWarmupTimedOut] = useState(false);
  const tradeTapeWarmupStartedAtRef = useRef<{ symbol: string; startedAt: number } | null>(null);
  const selectedLiveContextRefreshInFlightRef = useRef(false);
  const currentFlowRequestIdRef = useRef(0);

  const loadSnapshot = useCallback(async (forceRefresh = false, background = false) => {
    if (!ticker) {
      setError('Ticker is required.');
      setLoading(false);
      return;
    }
    if (forceRefresh) setRefreshing(true);
    else if (!background) setLoading(true);
    setError(null);
    try {
      const response = await stocksApi.getVietnamCompanyResearch(ticker, forceRefresh);
      setSnapshot(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load company research snapshot.';
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [ticker]);

  const refreshSelectedLiveContext = useCallback(() => {
    if (!ticker || selectedLiveContextRefreshInFlightRef.current) return false;
    selectedLiveContextRefreshInFlightRef.current = true;
    void loadSnapshot(false, true).finally(() => {
      selectedLiveContextRefreshInFlightRef.current = false;
    });
    return true;
  }, [loadSnapshot, ticker]);

  const loadCurrentFlow = useCallback(async (
    signal?: AbortSignal,
    forceRefresh = false,
  ) => {
    if (!ticker) return;
    currentFlowRequestIdRef.current += 1;
    const requestId = currentFlowRequestIdRef.current;
    setCurrentFlowLoading(true);
    setCurrentFlowError(null);
    try {
      const response = await stocksApi.getVietnamCurrentForeignFlow(ticker, {
        forceRefresh,
        signal,
      });
      if (!signal?.aborted && requestId === currentFlowRequestIdRef.current) {
        setCurrentFlow(response);
      }
    } catch (err) {
      if (!signal?.aborted && requestId === currentFlowRequestIdRef.current) {
        setCurrentFlowError(
          err instanceof Error
            ? 'Foreign flow could not be loaded.'
            : 'Foreign flow unavailable.',
        );
      }
    } finally {
      if (!signal?.aborted && requestId === currentFlowRequestIdRef.current) {
        setCurrentFlowLoading(false);
      }
    }
  }, [ticker]);

  useEffect(() => {
    void loadSnapshot(false);
  }, [loadSnapshot]);

  useEffect(() => {
    let inFlight = false;
    let controller: AbortController | null = null;
    let wasHidden = document.visibilityState === 'hidden';
    const request = (forceRefresh = false) => {
      if (inFlight || document.visibilityState === 'hidden') return;
      inFlight = true;
      controller = new AbortController();
      void loadCurrentFlow(controller.signal, forceRefresh).finally(() => {
        inFlight = false;
      });
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        wasHidden = true;
        return;
      }
      if (!wasHidden) return;
      wasHidden = false;
      request(true);
    };
    setCurrentFlow(null);
    const initialRequest = window.setTimeout(() => request(false), 0);
    const timer = window.setInterval(
      () => request(false),
      CURRENT_FOREIGN_FLOW_REFRESH_INTERVAL_MS,
    );
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      window.clearTimeout(initialRequest);
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      controller?.abort();
    };
  }, [loadCurrentFlow]);

  useEffect(() => {
    if (!ticker || loading || refreshing) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'hidden') return;
      refreshSelectedLiveContext();
    }, SELECTED_LIVE_CONTEXT_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [loading, refreshing, refreshSelectedLiveContext, ticker]);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') return;
      refreshSelectedLiveContext();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [refreshSelectedLiveContext]);

  useEffect(() => {
    if (!ticker || !snapshot || hasCompanyTradeTapeData(snapshot) || !isCompanyTradeTapeWarmupPending(snapshot)) {
      tradeTapeWarmupStartedAtRef.current = null;
      setTradeTapeWarmupTimedOut(false);
      return undefined;
    }
    if (tradeTapeWarmupStartedAtRef.current?.symbol !== ticker) {
      tradeTapeWarmupStartedAtRef.current = { symbol: ticker, startedAt: Date.now() };
      setTradeTapeWarmupTimedOut(false);
    }
    const elapsed = Date.now() - tradeTapeWarmupStartedAtRef.current.startedAt;
    const timer = window.setTimeout(
      () => setTradeTapeWarmupTimedOut(true),
      Math.max(0, TRADE_TAPE_STARTUP_MAX_WAIT_MS - elapsed),
    );
    return () => window.clearTimeout(timer);
  }, [snapshot, ticker]);

  if (loading && !snapshot) {
    return (
      <AppPage>
        <Loading label="Loading Vietnam company research..." />
      </AppPage>
    );
  }

  if (error && !snapshot) {
    return (
      <AppPage className="space-y-4">
        <Link to="/vietnam" className="inline-flex items-center gap-2 text-sm text-cyan hover:text-cyan-light">
          <ArrowLeft className="h-4 w-4" />
          Vietnam dashboard
        </Link>
        <section className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm text-danger">{error}</section>
      </AppPage>
    );
  }

  if (!snapshot) return null;

  const referencePrice = snapshot.price.referencePrice;
  const ceilingPrice = snapshot.price.ceilingPrice;
  const floorPrice = snapshot.price.floorPrice;
  const boardPriceClass = (price?: number | string | null) => (
    ssiBoardPriceValueClass(price, referencePrice, ceilingPrice, floorPrice)
  );
  const latestPriceTone = boardPriceClass(snapshot.price.latestPrice);
  const dailyCloseTone = boardPriceClass(snapshot.price.dailyClose);
  const priceVsReferenceTone = boardPriceClass(
    snapshot.price.dailyClose ?? snapshot.price.latestPrice,
  );

  const priceRows: MetricRow[] = [
    { label: 'Canonical latest price (VND)', value: snapshot.price.latestPrice, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: latestPriceTone, testId: 'company-latest-price' },
    { label: 'Daily close (VND)', value: snapshot.price.dailyClose, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: dailyCloseTone, testId: 'company-daily-close' },
    { label: 'Reference price (VND)', value: snapshot.price.referencePrice, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: REFERENCE_PRICE_CLASS, testId: 'company-reference-price' },
    { label: 'Ceiling price (VND)', value: snapshot.price.ceilingPrice, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: CEILING_PRICE_CLASS, testId: 'company-ceiling-price' },
    { label: 'Floor price (VND)', value: snapshot.price.floorPrice, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: FLOOR_PRICE_CLASS, testId: 'company-floor-price' },
    { label: 'Price date', value: snapshot.price.priceDate, formatter: (value?: number | string | null) => formatNumber(value) },
  ].filter((row) => (
    ['Canonical latest price (VND)', 'Daily close (VND)', 'Price date'].includes(row.label)
    || hasMetricValue(row.value)
  ));
  const profileRows: MetricRow[] = [
    { label: 'Ticker', value: snapshot.profile.ticker },
    { label: 'Company name', value: snapshot.profile.name },
    { label: 'English name', value: snapshot.profile.nameEn },
    { label: 'Exchange', value: snapshot.profile.exchange },
    { label: 'Market', value: snapshot.profile.market },
    {
      label: 'Sector',
      value: snapshot.profile.sector,
    },
    { label: 'Industry', value: snapshot.profile.industry },
    { label: 'Security type', value: snapshot.profile.securityType },
    { label: 'Issuer', value: snapshot.profile.issuer },
    { label: 'Lot size', value: snapshot.profile.lotSize },
    { label: 'Listed shares', value: snapshot.profile.listedShares },
    { label: 'Listed date', value: snapshot.profile.listedDate },
  ].filter((row: MetricRow) => (
    hasMetricValue(row.value)
    && !(row.label === 'Sector' && row.value === snapshot.profile.industry)
  ));
  const profileQualityStatus = snapshot.profile.coreProfileStatus ?? (
    snapshot.profile.status === 'ok' ? 'ready' : 'unavailable'
  );
  const tradingRows: MetricRow[] = [
    { label: 'Open (VND)', value: snapshot.tradingStats.open, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: boardPriceClass(snapshot.tradingStats.open), testId: 'company-open-price' },
    { label: 'High (VND)', value: snapshot.tradingStats.high, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: boardPriceClass(snapshot.tradingStats.high), testId: 'company-high-price' },
    { label: 'Low (VND)', value: snapshot.tradingStats.low, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: boardPriceClass(snapshot.tradingStats.low), testId: 'company-low-price' },
    { label: 'Close (VND)', value: snapshot.tradingStats.close, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: boardPriceClass(snapshot.tradingStats.close), testId: 'company-close-price' },
    { label: 'Daily OHLCV volume (shares)', value: snapshot.tradingStats.volume, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Daily OHLCV value (VND)', value: snapshot.tradingStats.value, formatter: formatVndValue, titleFormatter: formatFullVndTitle },
  ];
  const dailyStockPriceRows: MetricRow[] = [
    { label: 'Matched volume (shares)', value: snapshot.dailyStockPrice?.matchedVolume, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Matched value (VND)', value: snapshot.dailyStockPrice?.matchedValue, formatter: formatVndValue, titleFormatter: formatFullVndTitle },
    { label: 'Put-through volume (shares)', value: snapshot.dailyStockPrice?.putThroughVolume, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Put-through value (VND)', value: snapshot.dailyStockPrice?.putThroughValue, formatter: formatVndValue, titleFormatter: formatFullVndTitle },
    { label: 'Adjusted close (VND)', value: snapshot.dailyStockPrice?.adjustedClose, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'DailyStockPrice date', value: snapshot.dailyStockPrice?.date, formatter: (value?: number | string | null) => formatNumber(value) },
  ].filter((row: MetricRow) => hasMetricValue(row.value));
  const dailyStockPriceStatus = snapshot.dailyStockPrice?.qualityStatus ?? snapshot.dailyStockPrice?.status ?? 'unavailable';
  const dailyStockPriceCapabilities = snapshot.dailyStockPrice?.capabilities ?? {
    priceLimitsStatus: capabilityStatusFromValues([
      snapshot.dailyStockPrice?.referencePrice,
      snapshot.dailyStockPrice?.ceilingPrice,
      snapshot.dailyStockPrice?.floorPrice,
    ]),
    matchedStatsStatus: capabilityStatusFromValues([
      snapshot.dailyStockPrice?.matchedVolume,
      snapshot.dailyStockPrice?.matchedValue,
    ]),
    putThroughStatus: capabilityStatusFromValues([
      snapshot.dailyStockPrice?.putThroughVolume,
      snapshot.dailyStockPrice?.putThroughValue,
    ]),
    foreignFlowStatus: snapshot.foreignFlow.capabilityStatus ?? (
      snapshot.foreignFlow.status === 'ok' ? 'ready' : 'unavailable'
    ),
    sessionMetadataStatus: hasMetricValue(snapshot.dailyStockPrice?.date) ? 'ready' as const : 'unavailable' as const,
    overallStatus: dailyStockPriceStatus === 'ok'
      ? 'ready' as const
      : dailyStockPriceStatus === 'partial'
        ? 'partial' as const
        : 'unavailable' as const,
  };
  const dailyStockPriceCapabilityRows = [
    { label: 'Matched statistics', status: dailyStockPriceCapabilities.matchedStatsStatus },
    { label: 'Put-through statistics', status: dailyStockPriceCapabilities.putThroughStatus },
    { label: 'Price limits', status: dailyStockPriceCapabilities.priceLimitsStatus },
    { label: 'Foreign flow', status: dailyStockPriceCapabilities.foreignFlowStatus },
    { label: 'Session metadata', status: dailyStockPriceCapabilities.sessionMetadataStatus },
  ];
  const dailyStockPriceDateMatch = snapshot.dailyStockPrice?.dateMatch ?? snapshot.foreignFlow.dateMatch ?? 'unknown';
  const latestForeignFlowSession = selectLatestForeignFlowSession({
    completed: {
      sessionDate: snapshot.foreignFlow.date
        ?? snapshot.dailyStockPrice?.date
        ?? snapshot.sessionContext?.completedSessionDate,
      source: snapshot.foreignFlow.source ?? 'SSI DailyStockPrice',
      foreignBuyVolume: snapshot.foreignFlow.foreignBuyVolume,
      foreignSellVolume: snapshot.foreignFlow.foreignSellVolume,
      foreignNetVolume: snapshot.foreignFlow.foreignNetVolume,
      foreignBuyValue: snapshot.foreignFlow.foreignBuyValue,
      foreignSellValue: snapshot.foreignFlow.foreignSellValue,
      foreignNetValue: snapshot.foreignFlow.foreignNetValue,
    },
    current: currentFlow,
  });
  const technicalRows: MetricRow[] = [
    { label: 'MA20', value: snapshot.technical.ma20, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'MA50', value: snapshot.technical.ma50, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'RSI14', value: snapshot.technical.rsi14, formatter: (value) => formatNumber(value, 2) },
    { label: 'Bollinger upper', value: snapshot.technical.bollingerUpper, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'Bollinger middle', value: snapshot.technical.bollingerMiddle, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'Bollinger lower', value: snapshot.technical.bollingerLower, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: '52W high (VND)', value: snapshot.technical.high52w, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: '52W high date', value: snapshot.technical.high52wDate },
    { label: '52W low (VND)', value: snapshot.technical.low52w, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: '52W low date', value: snapshot.technical.low52wDate },
    { label: 'Avg volume 10D', value: snapshot.technical.avgVolume10d, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Avg volume 3M', value: snapshot.technical.avgVolume3m, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Daily range %', value: snapshot.technical.dailyRangePct, formatter: (value) => formatPercent(value) },
  ];
  const technicalDetailRows: MetricRow[] = [
    { label: '52W coverage', value: snapshot.technical.highLow52wCoverageStatus },
    { label: '52W history rows', value: snapshot.technical.highLow52wHistoryCount },
    { label: '10D volume coverage', value: snapshot.technical.avgVolume10dCoverageStatus },
    { label: '10D volume history rows', value: snapshot.technical.avgVolume10dHistoryCount },
    { label: '3M volume coverage', value: snapshot.technical.avgVolume3mCoverageStatus },
    { label: '3M volume history rows', value: snapshot.technical.avgVolume3mHistoryCount },
    { label: 'Price vs reference %', value: snapshot.technical.priceVsReferencePct, formatter: (value) => formatPercent(value, true), tone: priceVsReferenceTone, testId: 'company-price-vs-reference' },
    { label: 'Price vs reference state', value: snapshot.technical.priceVsReferenceStatus },
    { label: 'Calculation source', value: snapshot.technical.ssiDerivedMetricsSource },
  ];
  const hasIntradayData = hasCompanyIntradayData(snapshot);
  const hasRealtimeData = hasCompanyRealtimeData(snapshot);
  const hasTradeTapeRows = hasCompanyTradeTapeData(snapshot);
  const tradeTapeWarmupPending = (
    !hasTradeTapeRows
    && !tradeTapeWarmupTimedOut
    && isCompanyTradeTapeWarmupPending(snapshot)
  );
  const realtimeStreamState = streamLifecycleState(snapshot.realtimeStatus, snapshot.diagnostics?.realtime);
  const tradeTapeStreamState = streamLifecycleState(snapshot.tradeTapeStatus, snapshot.diagnostics?.tradeTape);
  const realtimePanelStatus = realtimeStreamState === 'stale'
    ? 'stale'
    : realtimeStreamState === 'recovering' || realtimeStreamState === 'awaiting_subscription'
      ? 'loading'
      : realtimeStreamState === 'closed'
        ? 'closed'
        : snapshot.realtimeStatus?.status ?? 'unavailable';
  const tradeTapePanelStatus = tradeTapeStreamState === 'stale'
    ? 'stale'
    : tradeTapeStreamState === 'recovering' || tradeTapeStreamState === 'awaiting_subscription'
      ? 'loading'
      : tradeTapeStreamState === 'closed'
        ? 'closed'
        : hasTradeTapeRows ? 'ok' : tradeTapeWarmupPending ? 'loading' : snapshot.tradeTapeStatus?.status ?? 'unavailable';
  const intradayPulse = snapshot.intraday?.pulse;
  const intradayChangeBaseline = intradayPulse?.intradayChangeBaseline;
  const hasSupportedIntradayChangeBaseline = intradayChangeBaseline === 'first_session_candle_open';
  const latestIntradayChange = hasSupportedIntradayChangeBaseline ? intradayPulse?.intradayChange : null;
  const latestIntradayChangePercent = hasSupportedIntradayChangeBaseline ? intradayPulse?.intradayChangePercent : null;
  const intradayChangeLabel = intradayChangeBaseline === 'first_session_candle_open'
    ? 'Change vs first session candle open'
    : 'Change (baseline unavailable)';
  const intradayChangePercentLabel = intradayChangeBaseline === 'first_session_candle_open'
    ? 'Change % vs first session candle open'
    : 'Change % (baseline unavailable)';
  const intradayPanelStatus = snapshot.intraday?.capabilityStatus
    ?? (snapshot.intraday?.cadenceStatus === 'irregular' || snapshot.intraday?.cadenceStatus === 'different_from_requested'
      ? 'partial'
      : snapshot.intraday?.status ?? 'unavailable');
  const intradayRows: MetricRow[] = [
    { label: 'Latest intraday close', value: intradayPulse?.latestIntradayClose ?? intradayPulse?.latest1hClose, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    {
      label: intradayChangeLabel,
      value: latestIntradayChange,
      formatter: formatSignedNumber,
      tone: typeof latestIntradayChange === 'number' && latestIntradayChange < 0 ? 'text-danger' : 'text-success',
    },
    { label: intradayChangePercentLabel, value: latestIntradayChangePercent, formatter: (value) => hasMetricValue(value) ? `${formatNumber(value, 2)}%` : formatNumber(value) },
    { label: 'Latest intraday volume', value: intradayPulse?.latestIntradayVolume ?? intradayPulse?.latest1hVolume, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Session volume from intraday', value: intradayPulse?.sessionVolumeFromIntraday ?? intradayPulse?.sessionVolumeFrom1H, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Provider cadence', value: companyIntradayCadenceText(snapshot), formatter: (value) => formatNumber(value) },
    { label: 'Candles loaded', value: snapshot.intraday?.candles?.length ?? 0 },
  ];
  const realtimeRows: MetricRow[] = [
    { label: 'Realtime snapshot price', value: snapshot.realtimeSnapshot?.price ?? snapshot.realtimeSnapshot?.realtimePrice, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'Realtime change', value: snapshot.realtimeSnapshot?.change ?? snapshot.realtimeSnapshot?.priceChange, formatter: formatSignedNumber },
    { label: 'Realtime change %', value: snapshot.realtimeSnapshot?.changePct ?? snapshot.realtimeSnapshot?.percentChange, formatter: (value) => `${formatNumber(value, 2)}%` },
    { label: 'Realtime reference price', value: snapshot.realtimeSnapshot?.referencePrice, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'SSI realtime/session volume', value: snapshot.realtimeSnapshot?.volume ?? snapshot.realtimeSnapshot?.volumeAccumulated, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Fetched at', value: snapshot.realtimeSnapshot?.fetchedAt, formatter: (value) => formatNumber(value) },
  ];
  const tradeTapeRows: MetricRow[] = [
    { label: 'Trades loaded', value: snapshot.tradeTape?.length ?? 0 },
    { label: 'Latest time', value: snapshot.tradeTape?.[0]?.time, formatter: (value) => formatNumber(value) },
    { label: 'Latest trade tape price', value: snapshot.tradeTape?.[0]?.price, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'Latest trade tape volume', value: snapshot.tradeTape?.[0]?.volume, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Latest trade tape value', value: snapshot.tradeTape?.[0]?.value, formatter: formatVndValue, titleFormatter: formatFullVndTitle },
    { label: 'Source', value: snapshot.tradeTapeStatus?.source, formatter: (value) => formatNumber(value) },
  ];

  return (
    <AppPage className="space-y-4">
      <CompanyHeader
        snapshot={snapshot}
        onRefresh={() => {
          void loadSnapshot(true);
          void loadCurrentFlow(undefined, true);
        }}
        refreshing={refreshing}
      />
      {error ? <section className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-warning">{error}</section> : null}
      <CompanyQualitySummary snapshot={snapshot} />
      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionShell title="Company profile" source={snapshot.profile.source} status={profileQualityStatus}>
          <MetricGrid rows={profileRows} />
          {snapshot.profile.optionalMetadataStatus === 'incomplete' && profileQualityStatus === 'ready' ? (
            <p className="mt-3 text-xs text-secondary-text">Optional metadata incomplete.</p>
          ) : profileQualityStatus === 'unavailable' ? (
            <p className="mt-3 text-xs text-secondary-text">Profile unavailable. Daily SSI data is still available.</p>
          ) : null}
        </SectionShell>
        <SourceCoveragePanel snapshot={snapshot} />
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <SectionShell title="Price summary" source={snapshot.price.source} status={snapshot.price.status}>
          <p className="mb-3 text-xs text-secondary-text">
            Canonical price: {formatSource(snapshot.price.canonicalSource ?? snapshot.price.source)}.
            {snapshot.price.sourceFreshness === 'latest_completed' && snapshot.price.completedSessionDate
              ? ` Latest completed session ${snapshot.price.completedSessionDate}.`
              : null}
            {snapshot.price.finalCloseStatus === 'provisional' ? ' Current session · provisional.' : null}
          </p>
          {dailyStockPriceDateMatch === 'mismatched' ? (
            <p className="mb-3 rounded-lg border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
              DailyStockPrice date differs from DailyOhlc.
            </p>
          ) : null}
          <MetricGrid rows={priceRows} />
        </SectionShell>
        <SectionShell title="Trading stats" source={snapshot.tradingStats.source} status={snapshot.tradingStats.status}>
          <MetricGrid rows={tradingRows} />
        </SectionShell>
        <SectionShell title="DailyStockPrice enrichment" source={snapshot.dailyStockPrice?.source ?? 'SSI DailyStockPrice'} status={dailyStockPriceCapabilities.overallStatus}>
          <p className="mb-3 text-xs text-secondary-text">
            Matched and put-through volume use shares; matched and put-through value use VND. Canonical daily close remains SSI DailyOhlc.
          </p>
          <div className="mb-3 grid gap-2 sm:grid-cols-2" aria-label="DailyStockPrice capability states">
            {dailyStockPriceCapabilityRows.map((capability) => (
              <div key={capability.label} className="flex items-center justify-between gap-2 rounded-lg border border-border/50 bg-elevated/25 px-3 py-2 text-xs">
                <span className="text-secondary-text">{capability.label}</span>
                <span className={cn('font-medium', statusTextClass(capability.status))}>
                  {statusLabel(capability.status)}
                </span>
              </div>
            ))}
          </div>
          {dailyStockPriceRows.length ? (
            <MetricGrid rows={dailyStockPriceRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI DailyStockPrice enrichment unavailable.</p>
          )}
        </SectionShell>
        <LatestForeignFlowCard
          view={latestForeignFlowSession}
          loading={currentFlowLoading}
          error={currentFlowError}
          compact
        />
        <SectionShell title="Technical snapshot" source={snapshot.technical.source} status={snapshot.technical.status}>
          <p className="mb-3 text-xs text-secondary-text">
            SSI-derived metrics are calculated from SSI DailyOhlc; price-vs-reference also uses SSI DailyStockPrice reference.
          </p>
          <MetricGrid rows={technicalRows} />
          <details className="mt-3 rounded-lg border border-border/60 bg-elevated/20 p-3">
            <summary className="cursor-pointer text-sm font-medium text-foreground">Technical details and coverage</summary>
            <div className="mt-3">
              <MetricGrid rows={technicalDetailRows} />
            </div>
          </details>
        </SectionShell>
        <SectionShell title="Intraday pulse" source={snapshot.intraday?.source ?? 'SSI IntradayOhlc'} status={intradayPanelStatus}>
          {hasIntradayData ? (
            <p className="mb-3 text-xs text-secondary-text">
              {companyIntradayCadenceText(snapshot)}. Requested {snapshot.intraday?.requestedTimeframe ?? '-'}; SSI IntradayOhlc is not a realtime matched quote.
            </p>
          ) : null}
          {hasIntradayData ? (
            <MetricGrid rows={intradayRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI intraday unavailable.</p>
          )}
        </SectionShell>
        <SectionShell title="SSI realtime" source={snapshot.realtimeStatus?.source ?? 'SSI realtime contract'} status={realtimePanelStatus}>
          {hasRealtimeData ? (
            <MetricGrid rows={realtimeRows} />
          ) : (
            <p className="text-sm text-secondary-text">
              {snapshot.liveMarket?.channels.lastPrice === 'no_data'
                ? 'Last-price snapshot has no data.'
                : streamLifecycleCopy(realtimeStreamState, 'Last-price snapshot unavailable. Other live channels may still be usable.')}
            </p>
          )}
        </SectionShell>
        <OrderBookLadder
          className="min-w-0"
          orderBook={snapshot.orderBook}
          status={snapshot.orderBookStatus}
          referencePrice={referencePrice}
          ceilingPrice={ceilingPrice}
          floorPrice={floorPrice}
        />
        <SectionShell title="SSI trade tape" source={snapshot.tradeTapeStatus?.source ?? 'SSI trade-tape contract'} status={tradeTapePanelStatus}>
          {hasTradeTapeRows ? (
            <>
              <MetricGrid rows={tradeTapeRows} />
              <TradeTapeRowsTable
                rows={snapshot.tradeTape ?? []}
                referencePrice={referencePrice}
                ceilingPrice={ceilingPrice}
                floorPrice={floorPrice}
              />
            </>
          ) : tradeTapeWarmupPending ? (
            <p className="text-sm text-secondary-text">Loading SSI trade tape...</p>
          ) : (
            <p className="text-sm text-secondary-text">
              {tradeTapeWarmupTimedOut
                ? 'No trade-tape rows arrived during the bounded startup wait.'
                : snapshot.liveMarket?.channels.tradeTape === 'reconnecting'
                  ? 'Trade tape reconnecting.'
                  : streamLifecycleCopy(tradeTapeStreamState, 'SSI trade tape unavailable.')}
            </p>
          )}
        </SectionShell>
      </section>
      {snapshot.news.status === 'ok' || snapshot.news.items.length ? (
        <section className="grid gap-4 lg:grid-cols-3">
          <CompanyNewsSection block={snapshot.news} />
        </section>
      ) : null}
      <CompanyDiagnosticsPanel snapshot={snapshot} />
    </AppPage>
  );
};

export default VietnamCompanyResearchPage;
