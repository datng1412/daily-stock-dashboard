import type { VietnamWatchItem } from '../api/stocks';

export const VIETNAM_CONDITION_SUMMARY_SUBTITLE = 'Neutral data summary, not a trading recommendation.';

export const VIETNAM_CONDITION_SUMMARY_FORBIDDEN_PATTERNS = [
  /\bbuy\b/i,
  /\bsell\b/i,
  /\bhold\b/i,
  /\baccumulate\b/i,
  /\bcut\s+loss\b/i,
  /\btake\s+profit\b/i,
  /\btarget\s+price\b/i,
  /\bentry\s+price\b/i,
  /\bstrong\s+buy\b/i,
  /\bstrong\s+sell\b/i,
  /\bshould\s+buy\b/i,
  /\bshould\s+sell\b/i,
  /\bwill\s+rise\b/i,
  /\bwill\s+fall\b/i,
] as const;

type VietnamConditionSummaryInput = {
  item: VietnamWatchItem;
  fixtureMode?: boolean;
};

const formatNumber = (value?: number | null, maximumFractionDigits = 2) => {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return new Intl.NumberFormat('en-US', { maximumFractionDigits }).format(value);
};

export const containsForbiddenConditionSummaryWording = (value?: string | null) => {
  if (!value) return false;
  return VIETNAM_CONDITION_SUMMARY_FORBIDDEN_PATTERNS.some((pattern) => pattern.test(value));
};

const safeText = (value?: string | null) => {
  const text = value?.trim();
  if (!text || containsForbiddenConditionSummaryWording(text)) return null;
  return text;
};

const safeList = (values: Array<string | null | undefined>) =>
  values.map(safeText).filter((value): value is string => Boolean(value));

const hasStaleCache = (item: VietnamWatchItem) =>
  Object.values(item.cacheStatus ?? {}).some((status) => status?.toLowerCase().includes('stale'));

const buildLabelsBullet = (item: VietnamWatchItem) => {
  const labels = safeList(item.statusLabels ?? []);
  const details = safeList((item.statusDetails ?? []).map((detail) => detail.label));
  const detailSuffix = details.length ? ` Detail states: ${details.slice(0, 2).join(', ')}.` : '';
  return `Current neutral condition labels: ${labels.length ? labels.slice(0, 4).join(', ') : 'none returned'}.${detailSuffix}`;
};

const buildTechnicalBullet = (item: VietnamWatchItem) => {
  const rsi = formatNumber(item.indicators.rsi14Wilder ?? item.indicators.rsi14, 2);
  const volumeRatio = formatNumber(item.indicators.volumeRatio, 2);
  const ma20 = formatNumber(item.indicators.ma20, 2);
  const ma50 = formatNumber(item.indicators.ma50, 2);
  const pulseChange = formatNumber(item.intradayPulse?.latest1hChangePercent, 2);
  const pulseRange = formatNumber(item.intradayPulse?.rangePercent, 2);
  const pulseVolume = formatNumber(item.intradayPulse?.latest1hVolume, 0);

  const dailyParts = [
    rsi ? `RSI14 ${rsi}` : null,
    volumeRatio ? `volume ratio ${volumeRatio}` : null,
    ma20 && ma50 ? `MA20/MA50 ${ma20}/${ma50}` : null,
  ].filter(Boolean);
  const intradayParts = [
    pulseChange ? `1H change ${pulseChange}%` : null,
    pulseRange ? `range ${pulseRange}%` : null,
    pulseVolume ? `volume ${pulseVolume}` : null,
  ].filter(Boolean);

  return `Daily technical state: ${dailyParts.length ? dailyParts.join('; ') : 'limited indicator data returned'}. Intraday 1H pulse: ${intradayParts.length ? intradayParts.join('; ') : 'no pulse returned'}.`;
};

const buildDataQualityBullet = (item: VietnamWatchItem) => {
  const parts: string[] = [];
  if (item.foreignDateMatch === 'matched') {
    parts.push('foreign date matches the price date');
  } else if (item.foreignDateMatch === 'mismatched') {
    parts.push('foreign data is latest available and not same-day');
  } else {
    parts.push('foreign date match is unavailable');
  }

  if ((item.warnings ?? []).length > 0) {
    parts.push(`${item.warnings.length} data-quality warning${item.warnings.length === 1 ? '' : 's'} returned`);
  } else {
    parts.push('no data-quality warnings returned');
  }

  if (hasStaleCache(item)) {
    parts.push('stale cache was used');
  } else {
    const cacheStates = safeList(Object.values(item.cacheStatus ?? {}));
    parts.push(cacheStates.length ? `cache states: ${Array.from(new Set(cacheStates)).join(', ')}` : 'cache state unavailable');
  }

  return `Foreign/date/data-quality state: ${parts.join('; ')}.`;
};

const buildNewsBullet = (item: VietnamWatchItem) => {
  if (!(item.news ?? []).length) return 'News: no recent news returned by current data source.';
  const headlines = safeList((item.news ?? []).map((news) => news.title));
  if (!headlines.length) return 'News: returned headlines were omitted by the wording guard.';
  return `Recent news headlines: ${headlines.slice(0, 3).join('; ')}.`;
};

export const buildVietnamConditionSummary = ({ item, fixtureMode = false }: VietnamConditionSummaryInput) => {
  const bullets = [
    fixtureMode ? 'Fixture mode active. Summary is based on sample data.' : null,
    buildLabelsBullet(item),
    buildTechnicalBullet(item),
    buildDataQualityBullet(item),
    buildNewsBullet(item),
  ].filter((bullet): bullet is string => Boolean(bullet));

  return bullets.filter((bullet) => !containsForbiddenConditionSummaryWording(bullet)).slice(0, 5);
};
