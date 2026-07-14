import type {
  BusinessDay,
  CandlestickData,
  HistogramData,
  LineData,
  Time,
  UTCTimestamp,
} from 'lightweight-charts';
import type { VietnamChartPoint, VietnamWatchItem } from '../../api/stocks';
import { formatCompactVnPrice } from '../../utils/vietnamNumberFormat';

export const VN_CHART_PRICE_MIN_MOVE = 10;
export const VN_CHART_PRICE_UNIT = 'raw VND/share with board-style thousand-VND display';

export type LightweightChartData = {
  candles: CandlestickData<Time>[];
  volume: HistogramData<Time>[];
  ma20: LineData<Time>[];
  ma50: LineData<Time>[];
  volumeMa20: LineData<Time>[];
  volumeMa50: LineData<Time>[];
  rsi14: LineData<Time>[];
  bbUpper: LineData<Time>[];
  bbMid: LineData<Time>[];
  bbLower: LineData<Time>[];
};

export type VietnamChartTimeframe = '1D' | '1m';

const VIETNAM_CHART_TIME_ZONE = 'Asia/Ho_Chi_Minh';
const VIETNAM_INTRADAY_TICK_FORMATTER = new Intl.DateTimeFormat('en-GB', {
  timeZone: VIETNAM_CHART_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});
const VIETNAM_INTRADAY_CROSSHAIR_FORMATTER = new Intl.DateTimeFormat('en-GB', {
  timeZone: VIETNAM_CHART_TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

export const formatVietnamChartTime = (time: Time) => {
  if (typeof time === 'object' && 'year' in time) {
    return `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}`;
  }
  if (typeof time === 'number') {
    const parts = Object.fromEntries(
      VIETNAM_INTRADAY_CROSSHAIR_FORMATTER
        .formatToParts(new Date(time * 1000))
        .map((part) => [part.type, part.value]),
    );
    return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute} VN`;
  }
  return String(time);
};

export const formatVietnamIntradayTick = (time: Time): string | null => (
  typeof time === 'number'
    ? VIETNAM_INTRADAY_TICK_FORMATTER.format(new Date(time * 1000))
    : null
);

export const formatVietnamChartTick = (time: Time, timeframe: VietnamChartTimeframe): string | null => (
  timeframe === '1m' ? formatVietnamIntradayTick(time) : null
);

export type ShortTermChartZone = {
  label: 'S1' | 'S2' | 'R1' | 'R2';
  lower: number;
  upper: number;
  midpoint: number;
  kind: 'support' | 'resistance';
  primary: boolean;
  formattedRange: string;
};

const daysInMonth = (year: number, month: number) => {
  if (month === 2) return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
};

export const parseVietnamBusinessDay = (value?: string | null): BusinessDay | null => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value?.trim() ?? '');
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1900 || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) return null;
  return { year, month, day };
};

export const businessDayKey = (day: BusinessDay) => (
  `${day.year}-${String(day.month).padStart(2, '0')}-${String(day.day).padStart(2, '0')}`
);

const finitePositive = (value?: number | null): value is number => (
  typeof value === 'number' && Number.isFinite(value) && value > 0
);

const finiteNonNegative = (value?: number | null): value is number => (
  typeof value === 'number' && Number.isFinite(value) && value >= 0
);

const validPoint = (point: VietnamChartPoint) => {
  if (!finitePositive(point.open) || !finitePositive(point.high) || !finitePositive(point.low) || !finitePositive(point.close)) return false;
  if (!finiteNonNegative(point.volume)) return false;
  return point.high >= Math.max(point.open, point.close, point.low)
    && point.low <= Math.min(point.open, point.close, point.high);
};

const linePoint = (time: Time, value?: number | null): LineData<Time> | null => (
  typeof value === 'number' && Number.isFinite(value) ? { time, value } : null
);

export const normalizeLightweightChartData = (
  points: VietnamChartPoint[],
  timeframe: VietnamChartTimeframe = '1D',
): LightweightChartData => {
  const byTime = new Map<string, { time: Time; point: VietnamChartPoint }>();
  points.forEach((point) => {
    const time = timeframe === '1m'
      ? (typeof point.time === 'number' && Number.isInteger(point.time) && point.time > 0
        ? point.time as UTCTimestamp
        : null)
      : parseVietnamBusinessDay(point.date);
    if (!time || !validPoint(point)) return;
    const key = typeof time === 'number' ? String(time).padStart(12, '0') : businessDayKey(time);
    byTime.set(key, { time, point });
  });
  const rows = [...byTime.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([, row]) => row);
  const result: LightweightChartData = {
    candles: [], volume: [], ma20: [], ma50: [], volumeMa20: [], volumeMa50: [], rsi14: [], bbUpper: [], bbMid: [], bbLower: [],
  };
  rows.forEach(({ time, point }) => {
    result.candles.push({ time, open: point.open!, high: point.high!, low: point.low!, close: point.close! });
    result.volume.push({
      time,
      value: point.volume!,
      color: point.close! >= point.open! ? 'rgba(34,197,94,0.45)' : 'rgba(239,68,68,0.45)',
    });
    (['ma20', 'ma50', 'volumeMa20', 'volumeMa50', 'rsi14', 'bbUpper', 'bbMid', 'bbLower'] as const).forEach((key) => {
      const mapped = linePoint(time, point[key]);
      if (mapped) result[key].push(mapped);
    });
  });
  return result;
};

export const formatVietnamChartPrice = (value: number) => formatCompactVnPrice(value, '—');

export const formatVietnamRsiValue = (value: number) => (
  Number.isFinite(value)
    ? value.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1')
    : '—'
);

export const formatShortTermZoneRange = (lower: number, upper: number) => {
  const lowerText = formatVietnamChartPrice(lower);
  const upperText = formatVietnamChartPrice(upper);
  return lowerText === upperText ? lowerText : `${lowerText}–${upperText}`;
};

const validZone = (zone: { lower?: number | null; upper?: number | null }) => (
  finitePositive(zone.lower) && finitePositive(zone.upper) && zone.lower <= zone.upper
);

export const normalizeShortTermChartZones = (
  zones?: VietnamWatchItem['indicators']['shortTermZones'],
): ShortTermChartZone[] => {
  if (!zones || zones.status === 'unavailable') return [];
  const mapZones = (
    values: Array<{ lower?: number | null; upper?: number | null }> | undefined,
    kind: 'support' | 'resistance',
  ) => (values ?? []).slice(0, 2).flatMap((zone, index) => {
    if (!validZone(zone)) return [];
    const lower = zone.lower!;
    const upper = zone.upper!;
    const label = `${kind === 'support' ? 'S' : 'R'}${index + 1}` as ShortTermChartZone['label'];
    return [{
      label,
      lower,
      upper,
      midpoint: (lower + upper) / 2,
      kind,
      primary: index === 0,
      formattedRange: formatShortTermZoneRange(lower, upper),
    }];
  });
  return [...mapZones(zones.support, 'support'), ...mapZones(zones.resistance, 'resistance')];
};
