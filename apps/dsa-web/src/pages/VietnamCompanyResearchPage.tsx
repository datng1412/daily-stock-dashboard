import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { stocksApi, type VietnamCompanyResearchResponse } from '../api/stocks';
import { AppPage, Badge, Button, Loading } from '../components/common';
import { DataQualitySummary } from '../components/dashboard';
import { cn } from '../utils/cn';
import {
  CEILING_PRICE_CLASS,
  FLOOR_PRICE_CLASS,
  formatCompactShareVolume,
  formatCompactVndValue,
  formatCompactVnPrice,
  formatFullSharesTitle,
  formatFullVndTitle,
  priceReferenceValueClass,
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

const statusVariant = (status?: string | null): StatusVariant => {
  if (status === 'ok' || status === 'complete') return 'success';
  if (status === 'partial') return 'warning';
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

const formatNumber = (value?: number | string | null, digits = 0) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
  }
  if (typeof value === 'string' && value.trim()) return value;
  return 'Unavailable';
};

const formatPrice = (value?: number | string | null) => formatCompactVnPrice(value);
const formatVolume = (value?: number | string | null) => formatCompactShareVolume(value);
const formatSignedVolume = (value?: number | string | null) => formatCompactShareVolume(value, 'Unavailable', true);
const formatVndValue = (value?: number | string | null) => formatCompactVndValue(value);
const formatSignedVndValue = (value?: number | string | null) => formatCompactVndValue(value, 'Unavailable', true);

const formatSignedNumber = (value?: number | string | null) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const sign = value > 0 ? '+' : '';
    return `${sign}${formatNumber(value)}`;
  }
  return formatNumber(value);
};

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
  snapshot.tradeTapeStatus?.status === 'ok'
  && (snapshot.tradeTape?.length ?? 0) > 0
);

const SectionShell: React.FC<{
  title: string;
  source?: string | null;
  status?: string | null;
  children: React.ReactNode;
  className?: string;
}> = ({ title, source, status, children, className }) => (
  <section className={cn('rounded-lg border border-border/70 bg-card p-4 shadow-soft-card', className)}>
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

const PlaceholderSection: React.FC<{
  title: string;
  block: VietnamCompanyResearchResponse['news'];
}> = ({ title, block }) => (
  <SectionShell title={title} source={block.source} status={block.status}>
    <p className="text-sm text-secondary-text">
      {block.message || 'Not implemented yet.'}
    </p>
  </SectionShell>
);

const SourceCoveragePanel: React.FC<{ snapshot: VietnamCompanyResearchResponse }> = ({ snapshot }) => (
  <SectionShell title="Source coverage" source="Backend contract" status={snapshot.status}>
    <div className="grid gap-2">
      {snapshot.sourceCoverage.map((item) => (
        <div
          key={`${item.block}-${item.source ?? 'none'}`}
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/50 bg-elevated/35 px-3 py-2 text-sm"
        >
          <span className="font-medium text-foreground">{item.block}</span>
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-secondary-text">{formatSource(item.source)}</span>
            <Badge variant={statusVariant(item.status)}>{statusLabel(item.status)}</Badge>
          </span>
        </div>
      ))}
    </div>
  </SectionShell>
);

const CompanyDiagnosticsPanel: React.FC<{ snapshot: VietnamCompanyResearchResponse }> = ({ snapshot }) => {
  const rows = [
    ...liveStatusDiagnosticRows('SSI profile metadata status', snapshot.profile.diagnostics),
    ...liveStatusDiagnosticRows('SSI DailyStockPrice status', snapshot.dailyStockPrice?.diagnostics),
    ...liveStatusDiagnosticRows('SSI intraday status', snapshot.intraday?.diagnostics),
    ...liveStatusDiagnosticRows('SSI realtime status', snapshot.diagnostics?.realtime),
    ...liveStatusDiagnosticRows('SSI trade tape status', snapshot.diagnostics?.tradeTape),
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

  const loadSnapshot = async (forceRefresh = false) => {
    if (!ticker) {
      setError('Ticker is required.');
      setLoading(false);
      return;
    }
    if (forceRefresh) setRefreshing(true);
    else setLoading(true);
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
  };

  useEffect(() => {
    void loadSnapshot(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

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
  const latestPriceTone = priceReferenceValueClass(snapshot.price.latestPrice, referencePrice);
  const dailyCloseTone = priceReferenceValueClass(snapshot.price.dailyClose, referencePrice);
  const priceVsReferenceTone = priceReferenceValueClass(
    snapshot.price.dailyClose ?? snapshot.price.latestPrice,
    referencePrice,
  );

  const priceRows: MetricRow[] = [
    { label: 'Canonical latest price (VND)', value: snapshot.price.latestPrice, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: latestPriceTone, testId: 'company-latest-price' },
    { label: 'Daily close (VND)', value: snapshot.price.dailyClose, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: dailyCloseTone, testId: 'company-daily-close' },
    { label: 'Reference price (VND)', value: snapshot.price.referencePrice, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: REFERENCE_PRICE_CLASS, testId: 'company-reference-price' },
    { label: 'Ceiling price (VND)', value: snapshot.price.ceilingPrice, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: CEILING_PRICE_CLASS, testId: 'company-ceiling-price' },
    { label: 'Floor price (VND)', value: snapshot.price.floorPrice, formatter: formatPrice, titleFormatter: formatFullVndTitle, tone: FLOOR_PRICE_CLASS, testId: 'company-floor-price' },
    { label: 'Price date', value: snapshot.price.priceDate, formatter: (value) => formatNumber(value) },
  ];
  const profileRows: MetricRow[] = [
    { label: 'Ticker', value: snapshot.profile.ticker },
    { label: 'Company name', value: snapshot.profile.name },
    { label: 'English name', value: snapshot.profile.nameEn },
    { label: 'Exchange', value: snapshot.profile.exchange },
    { label: 'Market', value: snapshot.profile.market },
    { label: 'Industry', value: snapshot.profile.industry },
    {
      label: 'Sector',
      value: snapshot.profile.sector,
    },
    { label: 'Security type', value: snapshot.profile.securityType },
    { label: 'Issuer', value: snapshot.profile.issuer },
    { label: 'Lot size', value: snapshot.profile.lotSize },
    { label: 'Listed shares', value: snapshot.profile.listedShares },
    { label: 'Listed date', value: snapshot.profile.listedDate },
  ].filter((row: MetricRow) => (
    hasMetricValue(row.value)
    && !(row.label === 'Sector' && row.value === snapshot.profile.industry)
  ));
  const profileQualityStatus = snapshot.profile.qualityStatus ?? (
    snapshot.profile.status === 'ok' ? 'partial' : 'unavailable'
  );
  const tradingRows: MetricRow[] = [
    { label: 'Open (VND)', value: snapshot.tradingStats.open, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'High (VND)', value: snapshot.tradingStats.high, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'Low (VND)', value: snapshot.tradingStats.low, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    { label: 'Close (VND)', value: snapshot.tradingStats.close, formatter: formatPrice, titleFormatter: formatFullVndTitle },
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
  const dailyStockPriceDateMatch = snapshot.dailyStockPrice?.dateMatch ?? snapshot.foreignFlow.dateMatch ?? 'unknown';
  const foreignRows: MetricRow[] = [
    { label: 'Foreign buy volume (shares)', value: snapshot.foreignFlow.foreignBuyVolume, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Foreign sell volume (shares)', value: snapshot.foreignFlow.foreignSellVolume, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    {
      label: 'Foreign net volume (shares)',
      value: snapshot.foreignFlow.foreignNetVolume,
      formatter: formatSignedVolume,
      titleFormatter: formatFullSharesTitle,
      tone: typeof snapshot.foreignFlow.foreignNetVolume === 'number' && snapshot.foreignFlow.foreignNetVolume < 0 ? 'text-danger' : 'text-success',
    },
    { label: 'Foreign buy value (VND)', value: snapshot.foreignFlow.foreignBuyValue, formatter: formatVndValue, titleFormatter: formatFullVndTitle },
    { label: 'Foreign sell value (VND)', value: snapshot.foreignFlow.foreignSellValue, formatter: formatVndValue, titleFormatter: formatFullVndTitle },
    {
      label: 'Foreign net value (VND)',
      value: snapshot.foreignFlow.foreignNetValue,
      formatter: formatSignedVndValue,
      titleFormatter: formatFullVndTitle,
      tone: typeof snapshot.foreignFlow.foreignNetValue === 'number' && snapshot.foreignFlow.foreignNetValue < 0 ? 'text-danger' : 'text-success',
    },
  ].filter((row: MetricRow) => hasMetricValue(row.value));
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
    { label: '52W coverage', value: snapshot.technical.highLow52wCoverageStatus },
    { label: 'Avg volume 10D', value: snapshot.technical.avgVolume10d, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: 'Avg volume 3M', value: snapshot.technical.avgVolume3m, formatter: formatVolume, titleFormatter: formatFullSharesTitle },
    { label: '3M volume coverage', value: snapshot.technical.avgVolume3mCoverageStatus },
    { label: 'Price vs reference %', value: snapshot.technical.priceVsReferencePct, formatter: (value) => formatPercent(value, true), tone: priceVsReferenceTone, testId: 'company-price-vs-reference' },
    { label: 'Daily range %', value: snapshot.technical.dailyRangePct, formatter: (value) => formatPercent(value) },
  ];
  const hasIntradayData = hasCompanyIntradayData(snapshot);
  const hasRealtimeData = hasCompanyRealtimeData(snapshot);
  const hasTradeTapeRows = hasCompanyTradeTapeData(snapshot);
  const intradayPulse = snapshot.intraday?.pulse;
  const latestIntradayChange = intradayPulse?.intradayChange ?? intradayPulse?.latest1hChange;
  const intradayRows: MetricRow[] = [
    { label: 'Latest intraday close', value: intradayPulse?.latestIntradayClose ?? intradayPulse?.latest1hClose, formatter: formatPrice, titleFormatter: formatFullVndTitle },
    {
      label: 'Intraday change',
      value: latestIntradayChange,
      formatter: formatSignedNumber,
      tone: typeof latestIntradayChange === 'number' && latestIntradayChange < 0 ? 'text-danger' : 'text-success',
    },
    { label: 'Intraday change %', value: intradayPulse?.intradayChangePercent ?? intradayPulse?.latest1hChangePercent, formatter: (value) => `${formatNumber(value, 2)}%` },
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
      <CompanyHeader snapshot={snapshot} onRefresh={() => void loadSnapshot(true)} refreshing={refreshing} />
      {error ? <section className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-warning">{error}</section> : null}
      <DataQualitySummary summary={snapshot.dataQualitySummary} />
      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionShell title="Company profile" source={snapshot.profile.source} status={profileQualityStatus}>
          <MetricGrid rows={profileRows} />
          {profileQualityStatus === 'partial' ? (
            <p className="mt-3 text-xs text-secondary-text">Profile partial. Some metadata is unavailable.</p>
          ) : profileQualityStatus === 'unavailable' ? (
            <p className="mt-3 text-xs text-secondary-text">Profile unavailable. Daily SSI data is still available.</p>
          ) : null}
        </SectionShell>
        <SourceCoveragePanel snapshot={snapshot} />
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <SectionShell title="Price summary" source={snapshot.price.source} status={snapshot.price.status}>
          <p className="mb-3 text-xs text-secondary-text">
            Canonical price: {formatSource(snapshot.price.canonicalSource ?? snapshot.price.source)}. Reference and limit fields: {formatSource(snapshot.price.referenceSource)}.
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
        <SectionShell title="DailyStockPrice enrichment" source={snapshot.dailyStockPrice?.source ?? 'SSI DailyStockPrice'} status={dailyStockPriceStatus}>
          <p className="mb-3 text-xs text-secondary-text">
            Matched and put-through volume use shares; matched and put-through value use VND. Canonical daily close remains SSI DailyOhlc.
          </p>
          {dailyStockPriceRows.length ? (
            <MetricGrid rows={dailyStockPriceRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI DailyStockPrice enrichment unavailable.</p>
          )}
        </SectionShell>
        <SectionShell title="Foreign flow" source={snapshot.foreignFlow.source} status={snapshot.foreignFlow.status}>
          <p className="mb-3 text-xs text-secondary-text">
            SSI DailyStockPrice · Volume: shares · Value: VND.
          </p>
          {foreignRows.length ? (
            <MetricGrid rows={foreignRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI DailyStockPrice foreign flow unavailable.</p>
          )}
        </SectionShell>
        <SectionShell title="Technical snapshot" source={snapshot.technical.source} status={snapshot.technical.status}>
          <p className="mb-3 text-xs text-secondary-text">
            SSI-derived metrics are calculated from SSI DailyOhlc; price-vs-reference also uses SSI DailyStockPrice reference.
          </p>
          <MetricGrid rows={technicalRows} />
        </SectionShell>
        <SectionShell title="Intraday pulse" source={snapshot.intraday?.source ?? 'SSI IntradayOhlc'} status={snapshot.intraday?.status ?? 'unavailable'}>
          <p className="mb-3 text-xs text-secondary-text">
            {companyIntradayCadenceText(snapshot)}. Requested {snapshot.intraday?.requestedTimeframe ?? '-'}; SSI IntradayOhlc is not a realtime matched quote.
          </p>
          {hasIntradayData ? (
            <MetricGrid rows={intradayRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI intraday unavailable.</p>
          )}
        </SectionShell>
        <SectionShell title="SSI realtime" source={snapshot.realtimeStatus?.source ?? 'SSI realtime contract'} status={snapshot.realtimeStatus?.status ?? 'unavailable'}>
          {hasRealtimeData ? (
            <MetricGrid rows={realtimeRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI realtime unavailable. Daily SSI data is still available.</p>
          )}
        </SectionShell>
        <SectionShell title="SSI trade tape" source={snapshot.tradeTapeStatus?.source ?? 'SSI trade-tape contract'} status={snapshot.tradeTapeStatus?.status ?? 'unavailable'}>
          {hasTradeTapeRows ? (
            <MetricGrid rows={tradeTapeRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI trade tape unavailable.</p>
          )}
        </SectionShell>
      </section>
      <section className="grid gap-4 lg:grid-cols-3">
        <PlaceholderSection title="News" block={snapshot.news} />
        <PlaceholderSection title="Financials" block={snapshot.financials} />
        <PlaceholderSection title="Events" block={snapshot.events} />
      </section>
      <CompanyDiagnosticsPanel snapshot={snapshot} />
    </AppPage>
  );
};

export default VietnamCompanyResearchPage;
