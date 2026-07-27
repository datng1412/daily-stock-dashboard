import { describe, expect, it } from 'vitest';
import type { VietnamForeignFlowWatchlistItem } from '../../../api/stocks';
import {
  buildForeignFlowWatchlistCsv,
  FOREIGN_FLOW_WATCHLIST_STORAGE_KEY,
  foreignFlowWatchlistMetric,
  parseForeignFlowWatchlistInput,
  readForeignFlowWatchlistPreferences,
  selectForeignFlowWatchlistRows,
  summarizeForeignFlowWatchlist,
  writeForeignFlowWatchlistPreferences,
} from '../foreignFlowWatchlistModel';

const item = (
  ticker: string,
  net20: number | null,
  overrides: Partial<VietnamForeignFlowWatchlistItem> = {},
): VietnamForeignFlowWatchlistItem => ({
  ticker,
  availability: 'ready',
  dataState: 'ready',
  latestSession: '2026-07-21',
  sourceFreshness: 'latest_completed',
  sourceSessionLag: 0,
  fetchedAt: '2026-07-21T09:00:00Z',
  cacheState: 'hit',
  cacheAgeSeconds: 5,
  actualSessionCount: 60,
  requestedSessionCount: 60,
  complete: true,
  buyValue1d: 30,
  sellValue1d: 20,
  netValue1d: 10,
  buyValue5d: 150,
  sellValue5d: 100,
  netValue5d: 50,
  buyValue20d: net20 === null ? null : 600,
  sellValue20d: net20 === null ? null : 400,
  netValue20d: net20,
  buyValue60d: 1_800,
  sellValue60d: 1_200,
  netValue60d: 600,
  buyVolume1d: 3,
  sellVolume1d: 2,
  netVolume1d: 1,
  buyVolume5d: 15,
  sellVolume5d: 10,
  netVolume5d: 5,
  buyVolume20d: 60,
  sellVolume20d: 40,
  netVolume20d: net20 === null ? null : net20 / 10,
  buyVolume60d: 180,
  sellVolume60d: 120,
  netVolume60d: 60,
  buyStreak: net20 !== null && net20 > 0 ? 2 : 0,
  sellStreak: net20 !== null && net20 < 0 ? 3 : 0,
  streakMetricBasis: 'foreign_net_value',
  containsProviderAnomaly: false,
  anomalySessions: [],
  anomalyCount: 0,
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  ...overrides,
});

describe('foreignFlowWatchlistModel', () => {
  it('normalizes pasted separators, removes duplicates, rejects invalids, and enforces 30', () => {
    const parsed = parseForeignFlowWatchlistInput(' fpt,SSI\nhpg FPT bad* ');
    expect(parsed.tickers).toEqual(['FPT', 'SSI', 'HPG']);
    expect(parsed.duplicateCount).toBe(1);
    expect(parsed.invalid).toEqual(['bad*']);

    const limited = parseForeignFlowWatchlistInput(
      Array.from({ length: 31 }, (_, index) => `A${String(index).padStart(2, '0')}`),
    );
    expect(limited.tickers).toHaveLength(30);
    expect(limited.limitedCount).toBe(1);
  });

  it('persists only tickers and safe UI preferences', () => {
    let stored = '';
    const storage = {
      getItem: (key: string) => key === FOREIGN_FLOW_WATCHLIST_STORAGE_KEY ? stored : null,
      setItem: (_key: string, value: string) => { stored = value; },
    };
    writeForeignFlowWatchlistPreferences({
      tickers: ['FPT', 'SSI'],
      metric: 'volume',
      window: 60,
      filter: 'anomaly',
      sort: 'net_20d',
      direction: 'desc',
    }, storage);
    expect(stored).not.toContain('items');
    expect(stored).not.toContain('provider');
    expect(readForeignFlowWatchlistPreferences(storage).tickers).toEqual(['FPT', 'SSI']);
  });

  it('filters and numerically sorts while preserving null and zero', () => {
    const rows = [item('ZERO', 0), item('NULL', null), item('BUY', 300), item('SELL', -200)];
    const buyers = selectForeignFlowWatchlistRows(rows, {
      metric: 'value',
      window: 20,
      filter: 'net_buyers',
      search: '',
      sort: 'net_20d',
      direction: 'desc',
    });
    expect(buyers.map((row) => row.ticker)).toEqual(['BUY']);
    expect(foreignFlowWatchlistMetric(rows[0], 'value', 20)).toBe(0);
    expect(foreignFlowWatchlistMetric(rows[1], 'value', 20)).toBeNull();
  });

  it('summarizes mixed sessions without a false common date', () => {
    const summary = summarizeForeignFlowWatchlist([
      item('FPT', 100),
      item('SSI', -100, { latestSession: '2026-07-18', availability: 'partial' }),
      item('HPG', null, { availability: 'unavailable', containsProviderAnomaly: true }),
    ], 'value', 20);
    expect(summary).toMatchObject({
      total: 3,
      ready: 1,
      partial: 1,
      unavailable: 1,
      netBuy: 1,
      netSell: 1,
      anomaly: 1,
      sourceSession: 'mixed source sessions',
    });
  });

  it('exports current rows with BOM and raw values', () => {
    const csv = buildForeignFlowWatchlistCsv([item('FPT', 123456789)], 'value', 20);
    expect(csv.startsWith('\uFEFF')).toBe(true);
    expect(csv).toContain('123456789');
    expect(csv).not.toContain('123.46');
    expect(csv).toContain('FPT');
  });
});
