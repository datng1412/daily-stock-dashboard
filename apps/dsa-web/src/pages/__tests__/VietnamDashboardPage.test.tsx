import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type VietnamWatchItem, type VietnamWatchlistResponse } from '../../api/stocks';
import { VIETNAM_WATCHLIST_STORAGE_KEY } from '../../utils/vietnamWatchlist';
import VietnamDashboardPage from '../VietnamDashboardPage';

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getVietnamWatchlist: vi.fn(),
  },
}));

const defaultTickers = ['FPT', 'VPB', 'MSB', 'SCS', 'ACV', 'ACB'];

const makeItem = (ticker: string): VietnamWatchItem => ({
  ticker,
  entity: `${ticker}.VN`,
  exchange: 'HOSE',
  marketIndex: 'VNINDEX.VN',
  source: 'mozyfin-cli',
  rowsLoaded: 3,
  date: '2026-06-10',
  latestPrice: 100,
  latestPriceSource: 'ohlcv',
  latestPriceRawField: 'close',
  latestPriceDate: '2026-06-10',
  quotePriceDate: null,
  quotePriceRawField: null,
  priceSourceWarning: null,
  ohlcvClose: 100,
  priceDate: '2026-06-10',
  ohlcvDate: '2026-06-10',
  quoteDate: '2026-06-10',
  foreignNetDate: '2026-06-10',
  foreignDateMatch: 'matched',
  candleStatus: 'unknown',
  finalCloseStatus: 'unknown',
  priceAdjustmentStatus: 'unknown',
  adjustedPriceStatus: 'unknown',
  open: 99,
  high: 101,
  low: 98,
  close: 100,
  previousClose: 99,
  changePct: 1,
  volume: 1000,
  amount: 100000,
  liquidity: { avgVolume20d: 1000, score: 80 },
  priceLimit: {
    limitPct: 7,
    ceilingPrice: 106,
    floorPrice: 92,
    distanceToLimitPct: 5,
    nearLimit: false,
  },
  foreign: { buy: 10, sell: 5, net: 5, signal: 'foreign_net_positive' },
  foreignNetUnit: 'shares',
  foreignBuyRawField: 'foreign_buy',
  foreignSellRawField: 'foreign_sell',
  indicators: {
    close: 100,
    ma20: 99,
    ma50: 98,
    rsi14: 55,
    rsi14Wilder: 55,
    bollinger: { middle: 99, upper: 110, lower: 90 },
    avgVolume20d: 1000,
    volumeRatio: 1,
    high20d: 110,
    low20d: 90,
    distanceTo20dHighPct: -9,
    distanceTo20dLowPct: 11,
    foreignNet5d: 5,
    foreignNet20d: 10,
    foreignNetLatest: 5,
  },
  statusLabels: ['Watch'],
  statusDetails: [],
  validation: { valid: true, tradingDate: '2026-06-10', missingFields: [], errors: [] },
  trend: {},
  warnings: [],
  news: [],
  intradayTimeframe: '1h',
  intradaySource: 'Mozyfin OHLCV',
  intradayIsRealtimeQuote: false,
  intradayWarning: 'Intraday 1H candle data is not a realtime matched quote.',
  intradayCandles: [],
  intradayPulse: undefined,
  intradayLabels: [],
  intradayDetails: [],
  cacheStatus: {
    ohlcvCache: 'miss',
    quoteCache: 'miss',
    intradayCache: 'miss',
    newsCache: 'miss',
  },
  cacheLastFetchedAt: {
    ohlcv: '2026-06-10T08:00:00Z',
    quote: '2026-06-10T08:00:00Z',
    intradayOhlcv: '2026-06-10T08:00:00Z',
    news: '2026-06-10T08:00:00Z',
  },
  cacheNextRefreshAt: {},
  cacheErrors: {},
  error: null,
});

const makeResponse = (tickers: string[]): VietnamWatchlistResponse => ({
  market: 'VN',
  source: 'Mozyfin live',
  fixtureMode: false,
  lastRefreshTime: '2026-06-10T08:00:00Z',
  units: { close: 'VND', volume: 'shares' },
  dataQuality: {
    source: 'Mozyfin live',
    fixtureMode: false,
    symbolsLoaded: tickers.length,
    lastTradingDate: '2026-06-10',
    missingFields: {},
    errors: {},
    lastRefreshTime: '2026-06-10T08:00:00Z',
    units: { close: 'VND', volume: 'shares' },
  },
  cacheMetadata: {
    cacheHitCount: 0,
    cacheMissCount: tickers.length,
    staleCacheUsedCount: 0,
    cacheTtlSeconds: { ohlcv: 300, quote: 60, intradayOhlcv: 60, news: 1800 },
    lastFetchedAt: {},
    nextRefreshAt: {},
    symbols: {},
  },
  watchlist: tickers.map(makeItem),
  ruleMetadata: { ruleSetName: 'Vietnam neutral technical labels', ruleSetVersion: 'v1', noRecommendation: true },
  formulas: { neutralStatusLabels: 'Rule-based neutral condition labels only; no trading recommendations are generated' },
});

const mockedGetVietnamWatchlist = vi.mocked(stocksApi.getVietnamWatchlist);

describe('VietnamDashboardPage watchlist loading', () => {
  beforeEach(() => {
    localStorage.clear();
    mockedGetVietnamWatchlist.mockReset();
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => makeResponse(tickers?.length ? tickers : defaultTickers));
  });

  it('force-refreshes a newly added non-default ticker using the updated watchlist', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'gmd.vn' } });
    fireEvent.click(screen.getByRole('button', { name: /add ticker/i }));

    const expectedTickers = [...defaultTickers, 'GMD'];
    await waitFor(() => {
      expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(expectedTickers, true);
    });

    expect(JSON.parse(localStorage.getItem(VIETNAM_WATCHLIST_STORAGE_KEY) ?? '[]')).toEqual(expectedTickers);
    expect(screen.getAllByText('GMD').length).toBeGreaterThan(0);
  });

  it('keeps preset switching on the selected preset list without forcing live refresh', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    fireEvent.change(screen.getByLabelText('Preset list'), { target: { value: 'tech' } });

    await waitFor(() => {
      expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['FPT', 'CMG', 'ELC', 'VGI', 'VTP', 'CTR'], false);
    });
  });

  it('rejects invalid tickers without issuing another watchlist request', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'BAD SYMBOL' } });
    fireEvent.click(screen.getByRole('button', { name: /add ticker/i }));

    expect(await screen.findByText('Use letters and numbers only, up to 10 characters.')).toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(1);
  });
});
