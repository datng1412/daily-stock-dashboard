import { describe, expect, it } from 'vitest';
import type { VietnamChartPoint, VietnamWatchItem } from '../../../api/stocks';
import {
  formatShortTermZoneRange,
  formatVietnamChartPrice,
  normalizeLightweightChartData,
  normalizeShortTermChartZones,
  parseVietnamBusinessDay,
} from '../lightweightChartData';

const point = (date: string, overrides: Partial<VietnamChartPoint> = {}): VietnamChartPoint => ({
  date, open: 70_000, high: 72_000, low: 69_000, close: 71_000, volume: 1_000,
  ma20: 70_500, ma50: 69_500, volumeMa20: 900, volumeMa50: 800, rsi14: 55,
  bbUpper: 75_000, bbMid: 70_000, bbLower: 65_000,
  ...overrides,
});

describe('lightweight VN chart data', () => {
  it('maps a trading date directly to BusinessDay without a timezone conversion', () => {
    expect(parseVietnamBusinessDay('2026-07-13')).toEqual({ year: 2026, month: 7, day: 13 });
    expect(parseVietnamBusinessDay('2026-02-29')).toBeNull();
    expect(parseVietnamBusinessDay('not-a-date')).toBeNull();
  });

  it('sorts ascending and deterministically keeps the last valid duplicate date', () => {
    const data = normalizeLightweightChartData([
      point('2026-07-12'), point('2026-07-10'), point('2026-07-12', { close: 71_500 }),
    ]);
    expect(data.candles.map((bar) => bar.time)).toEqual([
      { year: 2026, month: 7, day: 10 }, { year: 2026, month: 7, day: 12 },
    ]);
    expect(data.candles[1]).toMatchObject({ close: 71_500 });
  });

  it.each([
    point('bad-date'),
    point('2026-07-10', { open: Number.NaN }),
    point('2026-07-10', { close: 0 }),
    point('2026-07-10', { high: 68_000 }),
    point('2026-07-10', { low: 73_000 }),
    point('2026-07-10', { volume: -1 }),
  ])('rejects invalid bars', (invalid) => {
    expect(normalizeLightweightChartData([invalid]).candles).toEqual([]);
  });

  it('aligns volume and indicators to candle BusinessDay values and omits missing leading values', () => {
    const data = normalizeLightweightChartData([
      point('2026-07-10', { ma20: null, rsi14: null }),
      point('2026-07-11', { open: 72_000, close: 70_000 }),
    ]);
    expect(data.volume).toHaveLength(2);
    expect(data.volume[0].color).toContain('34,197,94');
    expect(data.volume[1].color).toContain('239,68,68');
    expect(data.ma20).toHaveLength(1);
    expect(data.rsi14).toHaveLength(1);
    expect(data.bbUpper[0].time).toEqual(data.candles[0].time);
  });

  it.each([60, 250, 500])('maps %i daily sessions without dropping aligned series', (size) => {
    const start = Date.UTC(2024, 0, 1);
    const input = Array.from({ length: size }, (_, index) => (
      point(new Date(start + index * 86_400_000).toISOString().slice(0, 10), {
        open: 70_000 + index,
        high: 72_000 + index,
        low: 69_000 + index,
        close: 71_000 + index,
      })
    ));
    const data = normalizeLightweightChartData(input);
    expect(data.candles).toHaveLength(size);
    expect(data.volume).toHaveLength(size);
    expect(data.rsi14).toHaveLength(size);
    expect(data.candles[0].time).toEqual({ year: 2024, month: 1, day: 1 });
  });

  it('uses raw DailyOhlc values while formatting the existing board-style display unit', () => {
    const data = normalizeLightweightChartData([point('2026-07-10', { close: 72_100, high: 73_000 })]);
    expect(data.candles[0]).toMatchObject({ close: 72_100 });
    expect(formatVietnamChartPrice(72_100)).toBe('72.10');
    expect(formatShortTermZoneRange(72_100, 72_100)).toBe('72.10');
    expect(formatShortTermZoneRange(72_100, 72_600)).toBe('72.10–72.60');
  });

  it('normalizes at most S1/S2/R1/R2 from the backend contract without recalculation', () => {
    const zones = normalizeShortTermChartZones({
      status: 'ok',
      support: [{ lower: 69_000, upper: 69_800 }, { lower: 67_000, upper: 68_000 }, { lower: 1, upper: 2 }],
      resistance: [{ lower: 73_500, upper: 74_100 }, { lower: 75_400, upper: 76_000 }],
    } as VietnamWatchItem['indicators']['shortTermZones']);
    expect(zones.map((zone) => zone.label)).toEqual(['S1', 'S2', 'R1', 'R2']);
    expect(zones[0]).toMatchObject({ lower: 69_000, upper: 69_800, midpoint: 69_400, formattedRange: '69.00–69.80', primary: true });
    expect(normalizeShortTermChartZones({ status: 'unavailable', support: [], resistance: [] } as VietnamWatchItem['indicators']['shortTermZones'])).toEqual([]);
  });
});
