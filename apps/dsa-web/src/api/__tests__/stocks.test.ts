import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi } from '../stocks';

const get = vi.hoisted(() => vi.fn());
const post = vi.hoisted(() => vi.fn());

vi.mock('../index', () => ({
  default: {
    get,
    post,
  },
}));

describe('stocksApi Vietnam SSI-derived metric mapping', () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
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

  it('parses typed 1m session metadata with explicit ticker and date identity', async () => {
    get.mockResolvedValueOnce({
      data: {
        ticker: 'FPT',
        interval: '1m',
        trading_date: '2026-06-24',
        timezone: 'Asia/Ho_Chi_Minh',
        status: 'ready',
        session_state: 'continuous_morning',
        freshness: 'updating',
        last_provider_refresh_at: '2026-06-24T02:16:07+00:00',
        newest_bar_age_seconds: 8,
        provider_snapshot_age_seconds: 3,
        current_bar_state: 'provisional',
        bars: [{ time: 1782266400, open: 1, high: 2, low: 1, close: 2, volume: 3 }],
        source: { provider: 'ssi_fastconnect', dataset: 'IntradayOhlc' },
        cache: { status: 'miss', is_stale: false },
        diagnostics: { requested_date: '2026-06-24', usable_bars: 1 },
      },
    });
    const controller = new AbortController();

    const result = await stocksApi.getVietnamIntradayChart('FPT', '2026-06-24', {
      forceRefresh: true,
      signal: controller.signal,
    });

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/vn/intraday-chart', {
      params: { ticker: 'FPT', interval: '1m', date: '2026-06-24', force_refresh: true },
      timeout: 120000,
      signal: controller.signal,
    });
    expect(result.tradingDate).toBe('2026-06-24');
    expect(result.bars[0].time).toBe(1782266400);
    expect(result.cache.isStale).toBe(false);
    expect(result.sessionState).toBe('continuous_morning');
    expect(result.freshness).toBe('updating');
    expect(result.lastProviderRefreshAt).toBe('2026-06-24T02:16:07+00:00');
    expect(result.newestBarAgeSeconds).toBe(8);
    expect(result.providerSnapshotAgeSeconds).toBe(3);
    expect(result.currentBarState).toBe('provisional');
  });

  it('sends one normalized bounded foreign-flow batch request with abort ownership', async () => {
    post.mockResolvedValueOnce({
      data: {
        source: 'ssi_fastconnect',
        source_endpoint: 'daily_stock_price',
        volume_unit: 'shares',
        value_unit: 'VND',
        finality: 'daily_available',
        requested_tickers: ['FPT', 'VCB'],
        normalized_tickers: ['FPT', 'VCB'],
        requested_count: 2,
        normalized_count: 2,
        returned_count: 2,
        usable_count: 1,
        fresh_count: 1,
        stale_count: 0,
        empty_count: 0,
        unavailable_count: 1,
        coverage_ratio: 0.5,
        complete: false,
        data_state: 'partial',
        rows: [{
          ticker: 'FPT',
          data_state: 'ready',
          freshness: 'fresh',
          latest_trading_date: '2026-07-17',
          foreign_net_value_5d: 5_000_000_000,
          foreign_net_volume_5d: 500_000,
          foreign_net_value_20d: 12_000_000_000,
          foreign_net_volume_20d: 1_200_000,
          covered_sessions_5d: 3,
          complete_5d: false,
          window_end_date_5d: '2026-07-17',
          covered_sessions_20d: 20,
          complete_20d: true,
          window_end_date_20d: '2026-07-17',
          source: 'ssi_fastconnect',
          source_endpoint: 'daily_stock_price',
          volume_unit: 'shares',
          value_unit: 'VND',
          finality: 'daily_available',
          fetched_at: '2026-07-17T10:00:00+00:00',
        }],
        rankings: {
          latest_net_value: { top_buy: [], top_sell: [] },
          net_value_5d: { top_buy: [], top_sell: [] },
          net_value_20d: { top_buy: [], top_sell: [] },
        },
        fetched_at: '2026-07-17T10:00:00+00:00',
      },
    });
    const controller = new AbortController();

    const result = await stocksApi.getVietnamForeignFlowBatch([' fpt ', 'FPT.VN', 'vcb'], {
      topN: 3,
      forceRefresh: true,
      signal: controller.signal,
    });

    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith('/api/v1/stocks/vn/foreign-flow/batch', {
      tickers: ['FPT', 'VCB'],
      top_n: 3,
      force_refresh: true,
    }, {
      timeout: 120000,
      signal: controller.signal,
    });
    expect(result.dataState).toBe('partial');
    expect(result.coverageRatio).toBe(0.5);
    expect(result.rows[0]).toMatchObject({
      foreignNetValue5d: 5_000_000_000,
      foreignNetVolume5d: 500_000,
      foreignNetValue20d: 12_000_000_000,
      foreignNetVolume20d: 1_200_000,
      coveredSessions5d: 3,
      complete5d: false,
      coveredSessions20d: 20,
      complete20d: true,
    });
    expect(result.rankings.netValue5d).toEqual({ topBuy: [], topSell: [] });
    expect(result.rankings.netValue20d).toEqual({ topBuy: [], topSell: [] });
  });

  it('caps foreign-flow requests at the stable first 30 unique symbols', async () => {
    post.mockResolvedValueOnce({ data: { normalized_tickers: [] } });
    const tickers = Array.from({ length: 35 }, (_, index) => `A${index.toString().padStart(2, '0')}`);

    await stocksApi.getVietnamForeignFlowBatch(tickers);

    const request = post.mock.calls[0][1] as { tickers: string[] };
    expect(request.tickers).toHaveLength(30);
    expect(request.tickers[0]).toBe('A00');
    expect(request.tickers[29]).toBe('A29');
  });
});
