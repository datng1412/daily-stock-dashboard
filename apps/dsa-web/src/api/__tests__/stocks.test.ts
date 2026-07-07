import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi } from '../stocks';

const get = vi.hoisted(() => vi.fn());

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('stocksApi Vietnam SSI-derived metric mapping', () => {
  beforeEach(() => {
    get.mockReset();
  });

  it('normalizes watchlist SSI-derived value keys that include numeric suffixes', async () => {
    get.mockResolvedValueOnce({
      data: {
        market: 'VN',
        source: 'SSI',
        actual_source: 'SSI',
        status: 'ok',
        watchlist: [
          {
            ticker: 'FPT',
            status: 'ok',
            latest_price: 124.6,
            latest_price_source: 'SSI DailyOhlc',
            indicators: {
              high_52w: 140,
              high_52w_date: '2026-06-01',
              low_52w: 90,
              low_52w_date: '2025-12-01',
              high_low_52w_history_count: 252,
              high_low_52w_coverage_status: 'complete',
              avg_volume_10d: 1_100_000,
              avg_volume_10d_history_count: 10,
              avg_volume_10d_coverage_status: 'complete',
              avg_volume_3m: 1_050_000,
              avg_volume_3m_history_count: 63,
              avg_volume_3m_coverage_status: 'complete',
              price_vs_reference_pct: 1.3,
              daily_range_pct: 1.77,
            },
          },
        ],
      },
    });

    const result = await stocksApi.getVietnamWatchlist(['FPT']);
    const indicators = result.watchlist[0].indicators;

    expect(indicators.high52w).toBe(140);
    expect(indicators.high52wDate).toBe('2026-06-01');
    expect(indicators.low52w).toBe(90);
    expect(indicators.low52wDate).toBe('2025-12-01');
    expect(indicators.avgVolume10d).toBe(1_100_000);
    expect(indicators.avgVolume10dCoverageStatus).toBe('complete');
    expect(indicators.avgVolume3m).toBe(1_050_000);
    expect(indicators.avgVolume3mCoverageStatus).toBe('complete');
    expect(indicators.priceVsReferencePct).toBe(1.3);
    expect(indicators.dailyRangePct).toBe(1.77);
  });

  it('normalizes company technical SSI-derived value keys that include numeric suffixes', async () => {
    get.mockResolvedValueOnce({
      data: {
        ticker: 'FPT',
        status: 'ok',
        technical: {
          high_52w: 140,
          high_52w_date: '2026-06-01',
          low_52w: 90,
          low_52w_date: '2025-12-01',
          avg_volume_10d: 1_100_000,
          avg_volume_10d_coverage_status: 'complete',
          avg_volume_3m: 1_050_000,
          avg_volume_3m_coverage_status: 'complete',
          price_vs_reference_pct: 1.3,
          daily_range_pct: 1.77,
          source: 'SSI-derived',
          status: 'ok',
        },
      },
    });

    const result = await stocksApi.getVietnamCompanyResearch('FPT');

    expect(result.technical.high52w).toBe(140);
    expect(result.technical.high52wDate).toBe('2026-06-01');
    expect(result.technical.low52w).toBe(90);
    expect(result.technical.low52wDate).toBe('2025-12-01');
    expect(result.technical.avgVolume10d).toBe(1_100_000);
    expect(result.technical.avgVolume10dCoverageStatus).toBe('complete');
    expect(result.technical.avgVolume3m).toBe(1_050_000);
    expect(result.technical.avgVolume3mCoverageStatus).toBe('complete');
    expect(result.technical.priceVsReferencePct).toBe(1.3);
    expect(result.technical.dailyRangePct).toBe(1.77);
  });
});
