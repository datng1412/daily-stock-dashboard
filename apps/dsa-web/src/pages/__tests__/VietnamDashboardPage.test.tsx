import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  stocksApi,
  type VietnamRealtimeResponse,
  type VietnamRealtimeTradesResponse,
  type VietnamWatchItem,
  type VietnamWatchlistResponse,
} from '../../api/stocks';
import { VIETNAM_WATCHLIST_STORAGE_KEY } from '../../utils/vietnamWatchlist';
import VietnamDashboardPage from '../VietnamDashboardPage';

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getVietnamWatchlist: vi.fn(),
    getVietnamRealtimeQuotes: vi.fn(),
    getVietnamRealtimeTrades: vi.fn(),
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

const makeResponse = (tickers: string[], options: { fixtureMode?: boolean } = {}): VietnamWatchlistResponse => ({
  market: 'VN',
  source: options.fixtureMode ? 'Mozyfin fixture' : 'Mozyfin live',
  fixtureMode: options.fixtureMode ?? false,
  lastRefreshTime: '2026-06-10T08:00:00Z',
  units: { close: 'VND', volume: 'shares' },
  dataQuality: {
    source: options.fixtureMode ? 'Mozyfin fixture' : 'Mozyfin live',
    fixtureMode: options.fixtureMode ?? false,
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
const mockedGetVietnamRealtimeQuotes = vi.mocked(stocksApi.getVietnamRealtimeQuotes);
const mockedGetVietnamRealtimeTrades = vi.mocked(stocksApi.getVietnamRealtimeTrades);

const makeRealtimeResponse = (tickers: string[], options: { stale?: boolean; unavailable?: boolean } = {}): VietnamRealtimeResponse => ({
  market: 'VN',
  source: 'vnstock_kbs',
  status: options.unavailable ? 'unavailable' : 'ok',
  error: options.unavailable ? 'vnstock is not installed' : null,
  requestedTickers: tickers,
  quotes: tickers.map((ticker) => ({
    symbol: ticker,
    realtimePrice: ticker === 'FPT' ? 101.5 : 100.5,
    realtimeTime: '10:15:00',
    realtimeTimeDisplay: '2026-06-11T10:15:00+07:00',
    snapshotPrice: ticker === 'FPT' ? 101.5 : 100.5,
    snapshotTime: '10:15:00',
    snapshotTimeDisplay: '2026-06-11T10:15:00+07:00',
    snapshotNote: 'KBS board snapshot; may differ from trade tape',
    ageSeconds: options.stale ? 600 : 20,
    isStale: options.stale ?? false,
    staleReason: options.stale ? 'age_gt_60s' : null,
    referencePrice: 100,
    openPrice: 100,
    highPrice: 102,
    lowPrice: 99,
    averagePrice: 100.5,
    priceChange: 1.5,
    percentChange: 1.5,
    volumeAccumulated: 1000,
    totalValue: 100000,
    bidPrice1: 101.4,
    bidVol1: 100,
    askPrice1: 101.6,
    askVol1: 200,
    foreignBuyVolume: 10,
    foreignSellVolume: 5,
    foreignRoom: 100000,
    source: 'vnstock_kbs',
    status: options.unavailable ? 'unavailable' : 'ok',
    error: options.unavailable ? 'vnstock is not installed' : null,
  })),
  cache: { cacheStatus: 'miss' },
});

const makeTradesResponse = (symbol: string): VietnamRealtimeTradesResponse => ({
  market: 'VN',
  source: 'vnstock_kbs',
  symbol,
  status: 'ok',
  error: null,
  trades: [
    {
      time: '10:16:00',
      price: 101.7,
      volume: 300,
      matchType: 'buy',
      id: '1',
      source: 'vnstock_kbs',
    },
  ],
  note: 'Trade tape may exclude auction/ATC prints depending on provider output',
  cache: { cacheStatus: 'miss' },
});

const clickTickerRow = (ticker: string) => {
  const indicatorTable = screen.getByRole('heading', { name: 'Indicator table' }).closest('section');
  if (!indicatorTable) throw new Error('Indicator table section not found');
  const row = within(indicatorTable).getByText(ticker).closest('tr');
  if (!row) throw new Error(`No table row found for ${ticker}`);
  fireEvent.click(row);
};

const dataStatusPanel = () => {
  const panel = screen.getByRole('heading', { name: 'Data status' }).closest('section');
  if (!panel) throw new Error('Data status panel not found');
  return within(panel);
};

describe('VietnamDashboardPage watchlist loading', () => {
  beforeEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    localStorage.clear();
    mockedGetVietnamWatchlist.mockReset();
    mockedGetVietnamRealtimeQuotes.mockReset();
    mockedGetVietnamRealtimeTrades.mockReset();
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => makeResponse(tickers?.length ? tickers : defaultTickers));
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => makeTradesResponse(symbol));
  });

  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
  });

  it('force-refreshes a newly added non-default ticker using the updated watchlist', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'gmd.vn' } });
    fireEvent.click(screen.getByRole('button', { name: /add ticker/i }));

    const expectedTickers = [...defaultTickers, 'GMD'];
    await waitFor(() => {
      expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(expectedTickers, true);
      expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(expectedTickers);
    });

    expect(JSON.parse(localStorage.getItem(VIETNAM_WATCHLIST_STORAGE_KEY) ?? '[]')).toEqual(expectedTickers);
    expect(screen.getAllByText('GMD').length).toBeGreaterThan(0);
  });

  it('keeps preset switching on the selected preset list without forcing live refresh', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    fireEvent.change(screen.getByLabelText('Preset list'), { target: { value: 'tech' } });

    await waitFor(() => {
      expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(['FPT', 'CMG', 'ELC', 'VGI', 'VTP', 'CTR'], false);
      expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(['FPT', 'CMG', 'ELC', 'VGI', 'VTP', 'CTR']);
    });
  });

  it('keeps Mozyfin daily close, KBS snapshot, and trade tape separate', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getAllByText(/Daily close/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/KBS snapshot/i).length).toBeGreaterThan(0);
    expect(await screen.findByRole('heading', { name: 'Latest trade tape' })).toBeInTheDocument();
    expect(screen.getByText('Trade tape may not include auction/ATC prints.')).toBeInTheDocument();
    expect(screen.getByText('KBS board snapshot; may differ from trade tape')).toBeInTheDocument();
    expect(screen.getAllByText(/OHLCV close 100/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('101.5').length).toBeGreaterThan(0);
  });

  it('renders data status with Mozyfin source and fixture state', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const panel = dataStatusPanel();
    expect(panel.getByText('Data status')).toBeInTheDocument();
    expect(panel.getAllByText('Mozyfin live').length).toBeGreaterThan(0);
    expect(panel.getByText('fixture_mode false')).toBeInTheDocument();
    expect(panel.getByText('Overview refresh')).toBeInTheDocument();
    expect(panel.getByText('Selected detail')).toBeInTheDocument();
  });

  it('shows fixture warning in data status when Mozyfin fixture mode is active', async () => {
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => makeResponse(tickers?.length ? tickers : defaultTickers, { fixtureMode: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const panel = dataStatusPanel();
    expect(panel.getAllByText('Mozyfin fixture').length).toBeGreaterThan(0);
    expect(panel.getByText('fixture_mode true')).toBeInTheDocument();
    expect(panel.getByText('Fixture mode is active; Mozyfin rows are sample data.')).toBeInTheDocument();
  });

  it('shows KBS ok status when snapshot rows are fresh', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const panel = dataStatusPanel();
    expect(panel.getByText('KBS ok')).toBeInTheDocument();
    expect(panel.getByText('stale 0 | unavailable 0')).toBeInTheDocument();
  });

  it('realtime failure does not erase overview rows', async () => {
    mockedGetVietnamRealtimeQuotes.mockRejectedValueOnce(new Error('KBS down'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(await screen.findByText(/KBS snapshot unavailable: KBS down/)).toBeInTheDocument();
    expect(screen.getAllByText('FPT').length).toBeGreaterThan(0);
    expect(screen.getAllByText('ACB').length).toBeGreaterThan(0);
  });

  it('shows stale badge when KBS marks a snapshot stale', async () => {
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { stale: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getAllByText('Stale').length).toBeGreaterThan(0);
    expect(screen.getAllByText('2026-06-11T10:15:00+07:00').length).toBeGreaterThan(0);
    expect(dataStatusPanel().getByText('KBS stale')).toBeInTheDocument();
    expect(dataStatusPanel().getByText(`stale ${defaultTickers.length} | unavailable 0`)).toBeInTheDocument();
  });

  it('shows KBS unavailable count when snapshot rows are unavailable', async () => {
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { unavailable: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const panel = dataStatusPanel();
    expect(panel.getByText('KBS unavailable')).toBeInTheDocument();
    expect(panel.getByText(`stale 0 | unavailable ${defaultTickers.length}`)).toBeInTheDocument();
  });

  it('refresh KBS calls realtime endpoints only', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    fireEvent.click(screen.getByRole('button', { name: /refresh kbs/i }));

    await waitFor(() => {
      expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);
      expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100);
    });
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('shows KBS auto-refresh controls', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByRole('checkbox', { name: 'Auto-refresh KBS' })).toBeInTheDocument();
    expect(screen.getByLabelText('KBS quotes')).toHaveValue('15');
    expect([...screen.getByLabelText('KBS quotes').querySelectorAll('option')].map((option) => option.value)).toEqual(['10', '15', '30']);
    expect(screen.getByLabelText('Latest trade tape')).toHaveValue('10');
    expect([...screen.getByLabelText('Latest trade tape').querySelectorAll('option')].map((option) => option.value)).toEqual(['5', '10', '15']);
  });

  it('auto-refresh KBS calls trades and quotes on their own intervals only', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh KBS' }));

    await act(async () => {
      vi.advanceTimersByTime(10000);
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100);
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);

    mockedGetVietnamRealtimeTrades.mockClear();

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(dataStatusPanel().getByText('on')).toBeInTheDocument();
    expect(dataStatusPanel().getByText('quotes 15s | trades 10s')).toBeInTheDocument();
  });

  it('selected 5s trade tape interval calls only trades endpoint', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    fireEvent.change(screen.getByLabelText('Latest trade tape'), { target: { value: '5' } });
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh KBS' }));

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100);
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('auto-refresh KBS skips quote ticks while quote refresh is in flight without blocking trades', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    let resolveQuotes: ((response: VietnamRealtimeResponse) => void) | undefined;
    mockedGetVietnamRealtimeQuotes.mockImplementation(() => new Promise((resolve) => {
      resolveQuotes = resolve;
    }));

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh KBS' }));

    await act(async () => {
      vi.advanceTimersByTime(15000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100);

    mockedGetVietnamRealtimeTrades.mockClear();
    await act(async () => {
      vi.advanceTimersByTime(15000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveQuotes?.(makeRealtimeResponse(defaultTickers));
    });
  });

  it('auto-refresh KBS skips trade ticks while trade refresh is in flight without blocking quotes', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    let resolveTrades: ((response: VietnamRealtimeTradesResponse) => void) | undefined;
    mockedGetVietnamRealtimeTrades.mockImplementation(() => new Promise((resolve) => {
      resolveTrades = resolve;
    }));

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh KBS' }));

    await act(async () => {
      vi.advanceTimersByTime(10000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);

    await act(async () => {
      resolveTrades?.(makeTradesResponse('FPT'));
    });
  });

  it('auto-refresh KBS pauses while the document is hidden', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh KBS' }));

    await act(async () => {
      vi.advanceTimersByTime(15000);
    });

    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
  });

  it('selecting ticker fetches latest trades without reloading the watchlist', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await screen.findByRole('heading', { name: 'Indicator table' });
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;

    clickTickerRow('ACB');

    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('ACB', 100));
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(await screen.findByText('10:16:00')).toBeInTheDocument();
  });

  it('rejects invalid tickers without issuing another watchlist request', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'BAD SYMBOL' } });
    fireEvent.click(screen.getByRole('button', { name: /add ticker/i }));

    expect(await screen.findByText('Use letters and numbers only, up to 10 characters.')).toBeInTheDocument();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(1);
  });

  it('does not render recommendation wording', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.queryByText(/recommend/i)).not.toBeInTheDocument();
  });
});
