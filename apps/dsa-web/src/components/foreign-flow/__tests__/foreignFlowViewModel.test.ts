import { describe, expect, it } from 'vitest';
import type { VietnamForeignFlowBatchSymbol } from '../../../api/stocks';
import {
  buildForeignFlowRankings,
  filterForeignFlowRows,
  foreignFlowWindowDisplay,
  sortForeignFlowRows,
  summarizeForeignFlow,
} from '../foreignFlowViewModel';

const row = (ticker: string, overrides: Partial<VietnamForeignFlowBatchSymbol> = {}): VietnamForeignFlowBatchSymbol => ({
  ticker,
  dataState: 'ready',
  freshness: 'fresh',
  latestTradingDate: '2026-07-17',
  foreignBuyVolume: 100,
  foreignSellVolume: 40,
  foreignNetVolume: 60,
  foreignBuyValue: 1_000,
  foreignSellValue: 400,
  foreignNetValue: 600,
  foreignNetVolume5d: 300,
  foreignNetValue5d: 3_000,
  foreignNetVolume20d: 1_200,
  foreignNetValue20d: 12_000,
  coveredSessions5d: 5,
  complete5d: true,
  coveredSessions20d: 20,
  complete20d: true,
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: 'shares',
  valueUnit: 'VND',
  finality: 'daily_available',
  fetchedAt: '2026-07-17T08:00:00Z',
  ...overrides,
});

describe('foreign-flow view model', () => {
  it('builds null-aware daily totals while counting explicit zero', () => {
    const summary = summarizeForeignFlow([
      row('AAA'),
      row('BBB', { foreignBuyValue: 0, foreignSellValue: 0, foreignNetValue: 0 }),
      row('CCC', { foreignBuyValue: null, foreignSellValue: null, foreignNetValue: null }),
    ], 'today', 'value');

    expect(summary.buy).toEqual({ value: 1_000, contributors: 2 });
    expect(summary.sell).toEqual({ value: 400, contributors: 2 });
    expect(summary.net).toEqual({ value: 600, contributors: 2 });
  });

  it('returns unavailable totals when all values are null and does not invent multi-session sides', () => {
    const summary = summarizeForeignFlow([
      row('AAA', { foreignNetValue5d: null }),
    ], '5', 'value');

    expect(summary.net).toEqual({ value: null, contributors: 0 });
    expect(summary.buy).toEqual({ value: null, contributors: 0 });
    expect(summary.sell).toEqual({ value: null, contributors: 0 });
    expect(summary.selectedWindowState).toBe('unavailable');
  });

  it('derives selected-window state and validates coverage without clamping invalid values', () => {
    expect(foreignFlowWindowDisplay(row('AAA', {
      foreignNetValue5d: 500,
      coveredSessions5d: 3,
      complete5d: false,
    }), '5', 'value')).toMatchObject({
      value: 500,
      coveredSessions: 3,
      requestedSessions: 5,
      complete: false,
      usable: true,
      state: 'incomplete',
    });

    expect(foreignFlowWindowDisplay(row('BBB', {
      foreignNetValue5d: 500,
      coveredSessions5d: 99,
      complete5d: false,
    }), '5', 'value')).toMatchObject({
      coveredSessions: null,
      complete: null,
      state: 'incomplete',
    });

    expect(foreignFlowWindowDisplay(row('CCC', {
      foreignNetValue5d: Number.NaN,
    }), '5', 'value')).toMatchObject({ value: null, usable: false, state: 'unavailable' });
  });

  it('does not inherit latest-ready state when the selected multi-session value is absent', () => {
    const summary = summarizeForeignFlow([
      row('AAA', { foreignNetValue5d: null }),
      row('BBB', { foreignNetValue5d: 200, coveredSessions5d: 3, complete5d: false }),
    ], '5', 'value');

    expect(summary.net).toEqual({ value: 200, contributors: 1 });
    expect(summary.selectedWindowState).toBe('incomplete');
    expect(foreignFlowWindowDisplay(row('AAA', { foreignNetValue5d: null }), '5', 'value').state).toBe('unavailable');
  });

  it('preserves stale usable selected-window values', () => {
    const display = foreignFlowWindowDisplay(row('AAA', {
      dataState: 'stale',
      freshness: 'stale',
    }), '20', 'value');

    expect(display).toMatchObject({ value: 12_000, usable: true, stale: true, state: 'stale' });
  });

  it('reports the latest observed date and mixed-date state', () => {
    const summary = summarizeForeignFlow([
      row('AAA', { latestTradingDate: '2026-07-16' }),
      row('BBB', { latestTradingDate: '2026-07-17' }),
    ], 'today', 'volume');

    expect(summary.latestTradingDate).toBe('2026-07-17');
    expect(summary.mixedTradingDates).toBe(true);
  });

  it('ranks positive and negative rows by magnitude with ticker ties and excludes zero/null', () => {
    const rankings = buildForeignFlowRankings([
      row('BBB', { foreignNetVolume5d: 500 }),
      row('AAA', { foreignNetVolume5d: 500 }),
      row('CCC', { foreignNetVolume5d: -700, complete5d: false, coveredSessions5d: 3 }),
      row('DDD', { foreignNetVolume5d: 0 }),
      row('EEE', { foreignNetVolume5d: null }),
    ], '5', 'volume', 10);

    expect(rankings.topBuy.map((entry) => entry.ticker)).toEqual(['AAA', 'BBB']);
    expect(rankings.topSell.map((entry) => entry.ticker)).toEqual(['CCC']);
    expect(rankings.topSell[0]).toMatchObject({ complete: false, coveredSessions: 3 });
  });

  it('filters by selected window and keeps null numeric rows last in either direction', () => {
    const rows = [
      row('BBB', { foreignNetValue20d: null }),
      row('CCC', { foreignNetValue20d: -20 }),
      row('AAA', { foreignNetValue20d: 10 }),
    ];

    expect(filterForeignFlowRows(rows, 'sell', '20', 'value').map((item) => item.ticker)).toEqual(['CCC']);
    expect(sortForeignFlowRows(rows, '20', 'desc', 'value').map((item) => item.ticker)).toEqual(['AAA', 'CCC', 'BBB']);
    expect(sortForeignFlowRows(rows, '20', 'asc', 'value').map((item) => item.ticker)).toEqual(['CCC', 'AAA', 'BBB']);
  });
});
