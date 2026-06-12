import { describe, expect, it } from 'vitest';
import type { VietnamWatchItem } from '../../api/stocks';
import {
  buildVietnamConditionSummary,
  containsForbiddenConditionSummaryWording,
} from '../vietnamConditionSummary';

const makeItem = (overrides: Partial<VietnamWatchItem> = {}): VietnamWatchItem => ({
  ticker: 'FPT',
  entity: 'FPT Corp',
  exchange: 'HOSE',
  latestPrice: 118000,
  latestPriceSource: 'ohlcv',
  latestPriceDate: '2026-06-05',
  ohlcvClose: 118000,
  ohlcvDate: '2026-06-05',
  foreignNetDate: '2026-06-05',
  foreignDateMatch: 'matched',
  close: 118000,
  changePct: 1.2,
  volume: 1200000,
  liquidity: { avgVolume20D: 980000, score: 82 },
  priceLimit: { distanceToLimitPct: 4.5, nearLimit: false },
  foreign: { net: 125000, signal: 'foreign_net_positive' },
  foreignNetUnit: 'shares',
  indicators: {
    close: 118000,
    ma20: 115000,
    ma50: 110000,
    rsi14: 56.12,
    rsi14Wilder: 55.42,
    avgVolume20D: 980000,
    volumeRatio: 1.22,
    foreignNet5D: 500000,
    foreignNet20D: 1200000,
  },
  statusLabels: ['Stronger than short-term average', 'Volume expansion'],
  statusDetails: [
    {
      label: 'Volume expansion',
      severity: 'info',
      reason: 'Volume ratio is above the configured neutral threshold.',
    },
  ],
  validation: { valid: true, tradingDate: '2026-06-05', missingFields: [], errors: [] },
  trend: { signalScore: 2, trendStatus: 'neutral' },
  warnings: [],
  news: [
    { title: 'FPT announces cloud service expansion', source: 'Fixture News' },
    { title: 'FPT technology revenue update released', source: 'Fixture News' },
  ],
  intradayTimeframe: '1h',
  intradayIsRealtimeQuote: false,
  intradayPulse: {
    latest1hClose: 118000,
    latest1hChange: 500,
    latest1hChangePercent: 0.43,
    rangePercent: 1.1,
    latest1hVolume: 150000,
  },
  intradayLabels: ['1H positive'],
  intradayDetails: [],
  cacheStatus: {
    ohlcvCache: 'hit',
    quoteCache: 'hit',
    newsCache: 'hit',
    intradayCache: 'hit',
  },
  cacheLastFetchedAt: {},
  cacheNextRefreshAt: {},
  cacheErrors: {},
  ...overrides,
});

describe('Vietnam condition summary', () => {
  it('builds 3-5 concise bullets from existing watchlist data', () => {
    const bullets = buildVietnamConditionSummary({ item: makeItem() });

    expect(bullets.length).toBeGreaterThanOrEqual(3);
    expect(bullets.length).toBeLessThanOrEqual(5);
    expect(bullets.join(' ')).toContain('Current neutral condition labels');
    expect(bullets.join(' ')).toContain('Daily technical state');
    expect(bullets.join(' ')).toContain('Intraday 1H pulse');
    expect(bullets.join(' ')).toContain('FPT announces cloud service expansion');
  });

  it('includes fixture mode language for sample data', () => {
    const bullets = buildVietnamConditionSummary({ item: makeItem(), fixtureMode: true });

    expect(bullets).toContain('Fixture mode active. Summary is based on sample data.');
    expect(bullets.length).toBeLessThanOrEqual(5);
  });

  it('mentions foreign date mismatch, stale cache, and missing news', () => {
    const bullets = buildVietnamConditionSummary({
      item: makeItem({
        foreignDateMatch: 'mismatched',
        warnings: ['foreign data date differs from OHLCV date'],
        news: [],
        cacheStatus: {
          ohlcvCache: 'stale',
          quoteCache: 'hit',
          newsCache: 'miss',
          intradayCache: 'hit',
        },
      }),
    });
    const summary = bullets.join(' ');

    expect(summary).toContain('foreign data is latest available and not same-day');
    expect(summary).toContain('stale cache was used');
    expect(summary).toContain('no recent news returned by current data source');
  });

  it('guards generated bullets against forbidden recommendation wording', () => {
    expect(containsForbiddenConditionSummaryWording('Should buy FPT')).toBe(true);
    expect(containsForbiddenConditionSummaryWording('target price 120000')).toBe(true);

    const bullets = buildVietnamConditionSummary({
      item: makeItem({
        statusLabels: ['Should buy', 'Volume expansion'],
        statusDetails: [
          {
            label: 'Strong buy',
            severity: 'info',
            reason: 'Forbidden source text should not render.',
          },
        ],
        news: [
          { title: 'Should buy FPT after earnings' },
          { title: 'FPT technology revenue update released' },
        ],
      }),
    });

    for (const bullet of bullets) {
      expect(containsForbiddenConditionSummaryWording(bullet)).toBe(false);
    }
    expect(bullets.join(' ')).toContain('Volume expansion');
    expect(bullets.join(' ')).toContain('FPT technology revenue update released');
  });

  it('does not claim news is missing when returned headlines are filtered', () => {
    const bullets = buildVietnamConditionSummary({
      item: makeItem({
        news: [{ title: 'Should buy FPT after earnings' }],
      }),
    });

    expect(bullets.join(' ')).toContain('returned headlines were omitted by the wording guard');
    for (const bullet of bullets) {
      expect(containsForbiddenConditionSummaryWording(bullet)).toBe(false);
    }
  });
});
