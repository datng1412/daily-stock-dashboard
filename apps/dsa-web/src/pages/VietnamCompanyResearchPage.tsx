import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { stocksApi, type VietnamCompanyResearchResponse } from '../api/stocks';
import { AppPage, Badge, Button, Loading } from '../components/common';
import { DataQualitySummary } from '../components/dashboard';
import { cn } from '../utils/cn';

type StatusVariant = React.ComponentProps<typeof Badge>['variant'];

type MetricRow = {
  label: string;
  value?: number | string | null;
  formatter?: (value?: number | string | null) => string;
  tone?: string;
};

const statusVariant = (status?: string | null): StatusVariant => {
  if (status === 'ok') return 'success';
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

const formatPrice = (value?: number | string | null) => formatNumber(value, 2);

const formatSignedNumber = (value?: number | string | null) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const sign = value > 0 ? '+' : '';
    return `${sign}${formatNumber(value)}`;
  }
  return formatNumber(value);
};

const formatSource = (source?: string | null) => source || 'Source pending';

const normalizeTicker = (ticker?: string) => (ticker ?? '').trim().toUpperCase().replace(/\.VN$/i, '');

const hasMetricValue = (value?: number | string | null) => (
  value !== null && value !== undefined && value !== '' && !(typeof value === 'number' && Number.isNaN(value))
);

const hasCompanyIntradayData = (snapshot: VietnamCompanyResearchResponse) => (
  snapshot.intraday?.status === 'ok'
  && Boolean(snapshot.intraday.pulse)
  && (snapshot.intraday.candles?.length ?? 0) > 0
);

const hasCompanyRealtimeData = (snapshot: VietnamCompanyResearchResponse) => (
  snapshot.realtime?.status === 'ok'
  && Boolean(snapshot.realtime.snapshot)
  && hasMetricValue(snapshot.realtime.snapshot?.price ?? snapshot.realtime.snapshot?.realtimePrice)
);

const hasCompanyTradeTapeData = (snapshot: VietnamCompanyResearchResponse) => (
  snapshot.tradeTape?.status === 'ok'
  && (snapshot.tradeTape.trades?.length ?? 0) > 0
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
        <dd className={cn('mt-1 text-sm font-semibold text-foreground', row.tone)}>
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
        <p className="mt-2 text-sm text-secondary-text">
          {snapshot.profile.name || 'Company name unavailable'}{snapshot.profile.exchange ? ` | ${snapshot.profile.exchange}` : ''}
        </p>
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

  const priceRows: MetricRow[] = [
    { label: 'Canonical latest price', value: snapshot.price.latestPrice, formatter: formatPrice },
    { label: 'Daily close', value: snapshot.price.dailyClose, formatter: formatPrice },
    { label: 'Reference price', value: snapshot.price.referencePrice, formatter: formatPrice },
    { label: 'Ceiling price', value: snapshot.price.ceilingPrice, formatter: formatPrice },
    { label: 'Floor price', value: snapshot.price.floorPrice, formatter: formatPrice },
    { label: 'Price date', value: snapshot.price.priceDate, formatter: (value) => formatNumber(value) },
  ];
  const tradingRows: MetricRow[] = [
    { label: 'Open', value: snapshot.tradingStats.open, formatter: formatPrice },
    { label: 'High', value: snapshot.tradingStats.high, formatter: formatPrice },
    { label: 'Low', value: snapshot.tradingStats.low, formatter: formatPrice },
    { label: 'Close', value: snapshot.tradingStats.close, formatter: formatPrice },
    { label: 'Daily OHLCV volume', value: snapshot.tradingStats.volume },
    { label: 'Daily OHLCV value', value: snapshot.tradingStats.value },
  ];
  const foreignRows: MetricRow[] = [
    { label: 'Foreign buy volume', value: snapshot.foreignFlow.foreignBuyVolume },
    { label: 'Foreign sell volume', value: snapshot.foreignFlow.foreignSellVolume },
    {
      label: 'Foreign net volume',
      value: snapshot.foreignFlow.foreignNetVolume,
      formatter: formatSignedNumber,
      tone: typeof snapshot.foreignFlow.foreignNetVolume === 'number' && snapshot.foreignFlow.foreignNetVolume < 0 ? 'text-danger' : 'text-success',
    },
    { label: 'Foreign buy value', value: snapshot.foreignFlow.foreignBuyValue },
    { label: 'Foreign sell value', value: snapshot.foreignFlow.foreignSellValue },
    {
      label: 'Foreign net value',
      value: snapshot.foreignFlow.foreignNetValue,
      formatter: formatSignedNumber,
      tone: typeof snapshot.foreignFlow.foreignNetValue === 'number' && snapshot.foreignFlow.foreignNetValue < 0 ? 'text-danger' : 'text-success',
    },
  ];
  const technicalRows: MetricRow[] = [
    { label: 'MA20', value: snapshot.technical.ma20, formatter: formatPrice },
    { label: 'MA50', value: snapshot.technical.ma50, formatter: formatPrice },
    { label: 'RSI14', value: snapshot.technical.rsi14, formatter: (value) => formatNumber(value, 2) },
    { label: 'Bollinger upper', value: snapshot.technical.bollingerUpper, formatter: formatPrice },
    { label: 'Bollinger middle', value: snapshot.technical.bollingerMiddle, formatter: formatPrice },
    { label: 'Bollinger lower', value: snapshot.technical.bollingerLower, formatter: formatPrice },
  ];
  const hasIntradayData = hasCompanyIntradayData(snapshot);
  const hasRealtimeData = hasCompanyRealtimeData(snapshot);
  const hasTradeTapeRows = hasCompanyTradeTapeData(snapshot);
  const intradayPulse = snapshot.intraday?.pulse;
  const latestIntradayChange = intradayPulse?.intradayChange ?? intradayPulse?.latest1hChange;
  const intradayRows: MetricRow[] = [
    { label: 'Latest intraday close', value: intradayPulse?.latestIntradayClose ?? intradayPulse?.latest1hClose, formatter: formatPrice },
    {
      label: 'Intraday change',
      value: latestIntradayChange,
      formatter: formatSignedNumber,
      tone: typeof latestIntradayChange === 'number' && latestIntradayChange < 0 ? 'text-danger' : 'text-success',
    },
    { label: 'Intraday change %', value: intradayPulse?.intradayChangePercent ?? intradayPulse?.latest1hChangePercent, formatter: (value) => `${formatNumber(value, 2)}%` },
    { label: 'Latest intraday volume', value: intradayPulse?.latestIntradayVolume ?? intradayPulse?.latest1hVolume },
    { label: 'Session volume from intraday', value: intradayPulse?.sessionVolumeFromIntraday ?? intradayPulse?.sessionVolumeFrom1H },
    { label: 'Candles loaded', value: snapshot.intraday?.candles?.length ?? 0 },
  ];
  const realtimeRows: MetricRow[] = [
    { label: 'Realtime snapshot price', value: snapshot.realtime?.snapshot?.price ?? snapshot.realtime?.snapshot?.realtimePrice, formatter: formatPrice },
    { label: 'Realtime change', value: snapshot.realtime?.snapshot?.change ?? snapshot.realtime?.snapshot?.priceChange, formatter: formatSignedNumber },
    { label: 'Realtime change %', value: snapshot.realtime?.snapshot?.changePct ?? snapshot.realtime?.snapshot?.percentChange, formatter: (value) => `${formatNumber(value, 2)}%` },
    { label: 'Realtime reference price', value: snapshot.realtime?.snapshot?.referencePrice, formatter: formatPrice },
    { label: 'SSI realtime/session volume', value: snapshot.realtime?.snapshot?.volume ?? snapshot.realtime?.snapshot?.volumeAccumulated },
    { label: 'Fetched at', value: snapshot.realtime?.snapshot?.fetchedAt, formatter: (value) => formatNumber(value) },
  ];
  const tradeTapeRows: MetricRow[] = [
    { label: 'Trades loaded', value: snapshot.tradeTape?.trades?.length ?? 0 },
    { label: 'Latest time', value: snapshot.tradeTape?.trades?.[0]?.time, formatter: (value) => formatNumber(value) },
    { label: 'Latest trade tape price', value: snapshot.tradeTape?.trades?.[0]?.price, formatter: formatPrice },
    { label: 'Latest trade tape volume', value: snapshot.tradeTape?.trades?.[0]?.volume },
    { label: 'Latest trade tape value', value: snapshot.tradeTape?.trades?.[0]?.value },
    { label: 'Source', value: snapshot.tradeTape?.source, formatter: (value) => formatNumber(value) },
  ];

  return (
    <AppPage className="space-y-4">
      <CompanyHeader snapshot={snapshot} onRefresh={() => void loadSnapshot(true)} refreshing={refreshing} />
      {error ? <section className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-warning">{error}</section> : null}
      <DataQualitySummary summary={snapshot.dataQualitySummary} />
      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionShell title="Company profile" source={snapshot.profile.source} status={snapshot.profile.status}>
          <MetricGrid rows={[
            { label: 'Ticker', value: snapshot.profile.ticker, formatter: (value) => formatNumber(value) },
            { label: 'Company name', value: snapshot.profile.name, formatter: (value) => formatNumber(value) },
            { label: 'Exchange', value: snapshot.profile.exchange, formatter: (value) => formatNumber(value) },
            { label: 'Industry', value: snapshot.profile.industry, formatter: (value) => formatNumber(value) },
          ]} />
        </SectionShell>
        <SourceCoveragePanel snapshot={snapshot} />
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <SectionShell title="Price summary" source={snapshot.price.source} status={snapshot.price.status}>
          <p className="mb-3 text-xs text-secondary-text">
            Canonical price: {formatSource(snapshot.price.canonicalSource ?? snapshot.price.source)}. Reference and limit fields: {formatSource(snapshot.price.referenceSource)}.
          </p>
          <MetricGrid rows={priceRows} />
        </SectionShell>
        <SectionShell title="Trading stats" source={snapshot.tradingStats.source} status={snapshot.tradingStats.status}>
          <MetricGrid rows={tradingRows} />
        </SectionShell>
        <SectionShell title="Foreign flow" source={snapshot.foreignFlow.source} status={snapshot.foreignFlow.status}>
          <MetricGrid rows={foreignRows} />
        </SectionShell>
        <SectionShell title="Technical snapshot" source={snapshot.technical.source} status={snapshot.technical.status}>
          <MetricGrid rows={technicalRows} />
        </SectionShell>
        <SectionShell title="Intraday pulse" source={snapshot.intraday?.source ?? 'SSI IntradayOhlc'} status={snapshot.intraday?.status ?? 'unavailable'}>
          {hasIntradayData ? (
            <MetricGrid rows={intradayRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI intraday unavailable.</p>
          )}
        </SectionShell>
        <SectionShell title="SSI realtime" source={snapshot.realtime?.source ?? 'SSI realtime contract'} status={snapshot.realtime?.status ?? 'unavailable'}>
          {hasRealtimeData ? (
            <MetricGrid rows={realtimeRows} />
          ) : (
            <p className="text-sm text-secondary-text">SSI realtime unavailable. Daily SSI data is still available.</p>
          )}
        </SectionShell>
        <SectionShell title="SSI trade tape" source={snapshot.tradeTape?.source ?? 'SSI trade-tape contract'} status={snapshot.tradeTape?.status ?? 'unavailable'}>
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
    </AppPage>
  );
};

export default VietnamCompanyResearchPage;
