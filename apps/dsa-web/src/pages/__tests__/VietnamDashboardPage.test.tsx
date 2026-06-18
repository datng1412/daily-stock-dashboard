import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  stocksApi,
  type VietnamChartResponse,
  type VietnamCorporateActionsResponse,
  type VietnamObservabilityResponse,
  type VietnamRealtimeResponse,
  type VietnamRealtimeTradesResponse,
  type VietnamWatchItem,
  type VietnamWatchlistResponse,
} from '../../api/stocks';
import { VIETNAM_WATCHLIST_STORAGE_KEY } from '../../utils/vietnamWatchlist';
import VietnamDashboardPage from '../VietnamDashboardPage';

const mockedGetVietnamMarketPhase = vi.fn();

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getVietnamWatchlist: vi.fn(),
    getVietnamRealtimeQuotes: vi.fn(),
    getVietnamRealtimeTrades: vi.fn(),
    getVietnamCorporateActions: vi.fn(),
    getVietnamObservability: vi.fn(),
    getVietnamChart: vi.fn(),
  },
}));

vi.mock('../../utils/vietnamMarketPhase', () => ({
  getVietnamMarketPhase: () => mockedGetVietnamMarketPhase(),
}));

const defaultTickers = ['FPT', 'VPB', 'MSB', 'SCS', 'ACV', 'ACB'];

const makeMarketPhase = (phase = 'Continuous afternoon', code = 'continuous_afternoon', isAuction = false) => ({
  phase,
  code,
  isTradingSession: code.includes('continuous') || isAuction,
  isAuction,
  isContinuous: code.includes('continuous'),
  holidayAware: false,
  nextLabel: isAuction ? 'Post-close' : 'ATC closing auction',
});

const makeChartData = () => Array.from({ length: 70 }, (_, index) => {
  const date = new Date(Date.UTC(2026, 3, 1 + index)).toISOString().slice(0, 10);
  const close = 100 + index;
  return {
    date,
    open: close - 1,
    high: close + 2,
    low: close - 2,
    close,
    volume: 1000 + index * 10,
    volumeMa20: index >= 19 ? 1100 + index * 5 : null,
    volumeMa50: index >= 49 ? 1250 + index * 5 : null,
    ma20: index >= 19 ? close - 2 : null,
    ma50: index >= 49 ? close - 5 : null,
    rsi14: index >= 14 ? 50 + (index % 10) : null,
    bbUpper: index >= 19 ? close + 10 : null,
    bbMid: index >= 19 ? close - 2 : null,
    bbLower: index >= 19 ? close - 14 : null,
  };
});

const makeChartResponse = (
  symbol = 'FPT',
  range = '6M',
  points = makeChartData(),
  overrides: Partial<VietnamChartResponse> = {},
): VietnamChartResponse => ({
  symbol,
  status: 'ok',
  source: 'SSI',
  timeframe: '1d',
  range,
  latestDate: points[points.length - 1]?.date ?? null,
  points,
  ...overrides,
});

const makeItem = (ticker: string): VietnamWatchItem => ({
  ticker,
  name: `${ticker} Listed Company`,
  entity: `${ticker}.VN`,
  exchange: 'HOSE',
  marketIndex: 'VNINDEX.VN',
  source: 'SSI',
  primarySource: 'SSI',
  actualSource: 'SSI',
  rowsLoaded: 3,
  date: '2026-06-10',
  latestPrice: 100,
  latestPriceSource: 'SSI',
  latestPriceRawField: 'close',
  latestPriceDate: '2026-06-10',
  quotePriceDate: null,
  quotePriceRawField: null,
  priceSourceWarning: null,
  ohlcvClose: 100,
  dailyClose: 100,
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
  liquidity: { avgVolume20D: 1000, score: 80 },
  priceLimit: {
    limitPct: 7,
    referencePrice: 99,
    ceilingPrice: 106,
    floorPrice: 92,
    distanceToLimitPct: 5,
    nearLimit: false,
    source: 'SSI DailyStockPrice',
    status: 'ok',
  },
  dailyStockPrice: {
    status: 'ok',
    date: '2026-06-10',
    referencePrice: 99,
    ceilingPrice: 106,
    floorPrice: 92,
    open: 99,
    high: 101,
    low: 98,
    close: 100,
    adjustedClose: 100,
    matchedVolume: 1234567,
    matchedValue: 123456789000,
    putThroughVolume: 1000,
    putThroughValue: 25000000,
    totalVolume: 1235567,
    totalValue: 123481789000,
    foreignBuyVolume: 10,
    foreignSellVolume: 5,
    foreignNetVolume: 5,
    foreignBuyValue: 1000000,
    foreignSellValue: 800000,
    foreignNetValue: 200000,
    source: 'SSI',
  },
  corporateAction: {
    status: 'unavailable',
    type: 'unknown',
    exDate: null,
    cashDividendPerShare: null,
    previousClose: 99,
    adjustedReferencePrice: null,
    adjustmentSource: 'manual_unavailable',
    priceVsAdjustedReference: null,
    priceVsAdjustedReferencePct: null,
    note: 'Corporate action data is unavailable; raw OHLCV close is unchanged.',
  },
  foreign: { buy: 10, sell: 5, net: 5, netValue: 200000, signal: 'foreign_net_positive' },
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
    avgVolume20D: 1000,
    volumeRatio: 1,
    high20d: 110,
    low20d: 90,
    distanceTo20dHighPct: -9,
    distanceTo20dLowPct: 11,
    foreignNet5D: 5,
    foreignNet20D: 10,
    foreignNetLatest: 5,
    foreignNet5dLatestAvailable: 15,
    foreignNet20dLatestAvailable: 30,
    foreignNetLatestAvailableDate: '2026-06-10',
    foreignNetHistoryCount: 20,
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
  source: options.fixtureMode ? 'Mozyfin fixture' : 'SSI live',
  fixtureMode: options.fixtureMode ?? false,
  lastRefreshTime: '2026-06-10T08:00:00Z',
  units: { close: 'VND', volume: 'shares' },
  dataQuality: {
    source: options.fixtureMode ? 'Mozyfin fixture' : 'SSI live',
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
const mockedGetVietnamCorporateActions = vi.mocked(stocksApi.getVietnamCorporateActions);
const mockedGetVietnamObservability = vi.mocked(stocksApi.getVietnamObservability);
const mockedGetVietnamChart = vi.mocked(stocksApi.getVietnamChart);

const makeObservabilityResponse = (overrides: Partial<VietnamObservabilityResponse> = {}): VietnamObservabilityResponse => ({
  market: 'VN',
  status: 'ok',
  mozyfin: {
    watchlistRequestsTotal: 3,
    watchlistCacheHitsTotal: 40,
    watchlistCacheMissesTotal: 8,
    singleflightWaitsTotal: 1,
    lastWatchlistRequestAt: '2026-06-11T08:00:00Z',
    lastFetchAt: '2026-06-11T08:00:00Z',
    lastCacheKey: "('VN', 'ohlcv', 'FPT')",
    lastTickersCount: 6,
    lastFetchDurationMs: 120,
  },
  kbs: {
    quoteRequestsTotal: 12,
    quoteSuccessTotal: 10,
    quoteUnavailableTotal: 2,
    tradeRequestsTotal: 20,
    tradeSuccessTotal: 16,
    tradeUnavailableTotal: 4,
    lastQuoteRequestAt: '2026-06-11T08:00:00Z',
    lastTradeRequestAt: '2026-06-11T08:00:00Z',
    lastQuoteTickersCount: 6,
    lastTradeSymbol: 'FPT',
    lastError: 'KBS provider timeout',
    lastRawErrorPresent: true,
  },
  ...overrides,
});

const makeRealtimeResponse = (
  tickers: string[],
  options: {
    stale?: boolean;
    unavailable?: boolean;
    ageSeconds?: number;
    isStale?: boolean;
    error?: string | null;
    errorDetail?: string | null;
    rawError?: string | null;
  } = {},
): VietnamRealtimeResponse => ({
  market: 'VN',
  source: 'vnstock_kbs',
  status: options.unavailable || options.error ? 'unavailable' : 'ok',
  error: options.error ?? (options.unavailable ? 'KBS unavailable' : null),
  errorDetail: options.errorDetail ?? (options.unavailable ? 'Provider returned an unavailable state.' : null),
  rawError: options.rawError ?? (options.unavailable ? 'vnstock is not installed' : null),
  requestedTickers: tickers,
  quotes: tickers.map((ticker) => {
    const rawStale = options.isStale ?? options.stale ?? false;
    const ageSeconds = options.ageSeconds ?? (rawStale ? 600 : 20);
    return ({
    symbol: ticker,
    realtimePrice: ticker === 'FPT' ? 101.5 : 100.5,
    realtimeTime: '10:15:00',
    realtimeTimeDisplay: '2026-06-11T10:15:00+07:00',
    snapshotPrice: ticker === 'FPT' ? 101.5 : 100.5,
    snapshotTime: '10:15:00',
    snapshotTimeDisplay: '2026-06-11T10:15:00+07:00',
    snapshotNote: 'KBS board snapshot; may differ from trade tape',
    ageSeconds,
    isStale: rawStale,
    staleReason: rawStale ? 'age_gt_60s' : null,
    referencePrice: 100,
    referencePriceSource: 'kbs_board',
    priceVsReference: ticker === 'FPT' ? 1.5 : 0.5,
    priceVsReferencePct: ticker === 'FPT' ? 1.5 : 0.5,
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
    status: options.unavailable || options.error ? 'unavailable' : 'ok',
    error: options.error ?? (options.unavailable ? 'KBS unavailable' : null),
    errorDetail: options.errorDetail ?? (options.unavailable ? 'Provider returned an unavailable state.' : null),
    rawError: options.rawError ?? (options.unavailable ? 'vnstock is not installed' : null),
  });
  }),
  cache: { cacheStatus: 'miss' },
});

const makeTradesResponse = (symbol: string): VietnamRealtimeTradesResponse => ({
  market: 'VN',
  source: 'vnstock_kbs',
  symbol,
  status: 'ok',
  error: null,
  errorDetail: null,
  rawError: null,
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

const makeCorporateActionsResponse = (
  tickers: string[],
  overrides: Partial<VietnamCorporateActionsResponse> = {},
): VietnamCorporateActionsResponse => ({
  market: 'VN',
  status: 'unavailable',
  source: null,
  lastCheckedAt: '2026-06-11T10:00:00+07:00',
  requestedTickers: tickers,
  monthsBack: 6,
  items: [],
  error: 'Corporate action history/calendar unavailable.',
  errorDetail: 'No verified Vietnam corporate-action event provider is configured.',
  ...overrides,
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

const dataStatusDiagnostics = () => {
  const details = screen.getByText('Show diagnostics').closest('details');
  if (!details) throw new Error('Data status diagnostics not found');
  return details;
};

const selectedTickerHeader = () => {
  const header = screen.getByText('Selected ticker').closest('section');
  if (!header) throw new Error('Selected ticker header not found');
  return within(header);
};

const inspectChartCard = () => {
  const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
  const chartHeading = detail.getByRole('heading', { name: 'Inspect chart' });
  const chartCard = chartHeading.closest('div')?.parentElement?.parentElement;
  if (!chartCard) throw new Error('Inspect chart card not found');
  return within(chartCard as HTMLElement);
};

const inspectDateLabels = (chartCard: ReturnType<typeof within>) =>
  chartCard.queryAllByTestId('inspect-chart-date-label').map((label: HTMLElement) => label.textContent ?? '');

describe('VietnamDashboardPage watchlist loading', () => {
  beforeEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    localStorage.clear();
    mockedGetVietnamWatchlist.mockReset();
    mockedGetVietnamRealtimeQuotes.mockReset();
    mockedGetVietnamRealtimeTrades.mockReset();
    mockedGetVietnamCorporateActions.mockReset();
    mockedGetVietnamObservability.mockReset();
    mockedGetVietnamChart.mockReset();
    mockedGetVietnamMarketPhase.mockReset();
    mockedGetVietnamMarketPhase.mockReturnValue(makeMarketPhase());
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => makeResponse(tickers?.length ? tickers : defaultTickers));
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => makeTradesResponse(symbol));
    mockedGetVietnamCorporateActions.mockImplementation(async (tickers) => makeCorporateActionsResponse(tickers));
    mockedGetVietnamObservability.mockImplementation(async () => makeObservabilityResponse());
    mockedGetVietnamChart.mockImplementation(async (symbol, range = '6M') => makeChartResponse(symbol, range));
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

  it('keeps SSI daily close, KBS snapshot, and trade tape separate', async () => {
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

  it('renders a compact selected ticker header with distinct source labels', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const header = selectedTickerHeader();
    expect(header.getByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(header.getByText('FPT Listed Company')).toBeInTheDocument();
    expect(header.getByText('Daily close')).toBeInTheDocument();
    expect(header.getByText('KBS snapshot')).toBeInTheDocument();
    expect(header.getByText('Vs SSI reference')).toBeInTheDocument();
    expect(header.getByText('Session volume')).toBeInTheDocument();
    expect(header.getByText('20D avg volume')).toBeInTheDocument();
    expect(header.getByText('Latest news')).toBeInTheDocument();
    expect(header.getByText('SSI daily')).toBeInTheDocument();
    expect(header.getByText('KBS realtime')).toBeInTheDocument();
  });

  it('shows neutral watchlist scan states for faster table comparison', async () => {
    const response = makeResponse(['FPT', 'VPB', 'MSB', 'SCS', 'ACV']);
    response.watchlist = response.watchlist.map((item) => {
      if (item.ticker === 'FPT') {
        return {
          ...item,
          statusLabels: ['Stronger than short-term average', 'Volume expansion', 'Foreign net positive'],
          liquidity: { ...item.liquidity, score: 82 },
        };
      }
      if (item.ticker === 'VPB') {
        return {
          ...item,
          changePct: -0.7,
          statusLabels: ['Weak short-term'],
        };
      }
      if (item.ticker === 'MSB') {
        return {
          ...item,
          statusLabels: ['Foreign data stale', 'Indicator caution', 'Price finality unknown', 'Adjusted price unknown'],
          statusDetails: [
            { label: 'Foreign data stale', severity: 'caution', reason: 'Foreign net date is missing or does not match the OHLCV date.' },
            { label: 'Indicator caution', severity: 'caution', reason: 'Indicator inputs include non-final, unknown-adjustment, or limited-history data.' },
            { label: 'Price finality unknown', severity: 'caution', reason: 'The dashboard cannot confirm whether the latest daily candle is final.' },
            { label: 'Adjusted price unknown', severity: 'caution', reason: 'The dashboard cannot confirm whether the OHLCV prices are adjusted or unadjusted.' },
          ],
          warnings: ['latest price uses OHLCV close because Mozyfin quote field is unreliable'],
        };
      }
      if (item.ticker === 'SCS') {
        return {
          ...item,
          validation: { ...item.validation, valid: false, errors: ['Missing daily close'] },
        };
      }
      return {
        ...item,
        cacheStatus: { ...item.cacheStatus, ohlcvCache: 'error' },
      };
    });
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const scanSummary = within(screen.getByTestId('watchlist-scan-summary'));
    expect(scanSummary.getByRole('heading', { name: 'Watchlist scan' })).toBeInTheDocument();
    expect(scanSummary.getByText('Sector grouping unavailable')).toBeInTheDocument();
    expect(scanSummary.getByText('Strong').closest('div')).toHaveTextContent('1');
    expect(scanSummary.getByText('Neutral').closest('div')).toHaveTextContent('1');
    expect(scanSummary.getByText('Weakening').closest('div')).toHaveTextContent('1');
    expect(scanSummary.getByText('Risk elevated').closest('div')).toHaveTextContent('0');
    expect(scanSummary.getByText('Data unavailable').closest('div')).toHaveTextContent('2');
    expect(scanSummary.queryByText(/buy|sell|hold/i)).not.toBeInTheDocument();

    const indicatorTable = within(screen.getByRole('heading', { name: 'Indicator table' }).closest('section') as HTMLElement);
    expect(indicatorTable.getByText('Scan state')).toBeInTheDocument();
    expect(indicatorTable.getByTestId('scan-state-FPT')).toHaveTextContent('Strong');
    expect(indicatorTable.getByTestId('scan-state-VPB')).toHaveTextContent('Weakening');
    expect(indicatorTable.getByTestId('scan-state-MSB')).toHaveTextContent('Neutral');
    expect(indicatorTable.getByTestId('scan-state-SCS')).toHaveTextContent('Data unavailable');
    expect(indicatorTable.getByTestId('scan-state-ACV')).toHaveTextContent('Data unavailable');
    expect(indicatorTable.getByTestId('table-caveats-FPT')).toHaveTextContent('None');
    expect(indicatorTable.getByTestId('table-caveats-MSB')).toHaveTextContent('4 caveats');
  });

  it('renders news source with relative time', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      news: [
        {
          title: 'FPT reports cloud revenue growth',
          url: 'https://example.com/fpt-cloud',
          source: 'CafeF',
          publishedAt: '',
          publishedDate: new Date(Date.now() - 125 * 60 * 1000).toISOString(),
          summary: 'Cloud revenue increased in the latest update.',
        },
      ],
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    expect((await screen.findAllByText('FPT reports cloud revenue growth')).length).toBeGreaterThan(0);
    expect(screen.getByText('CafeF · 2 hours ago')).toBeInTheDocument();
    expect(screen.queryByText('Time unavailable')).not.toBeInTheDocument();
  });

  it('shows SSI DailyStockPrice fields and corporate-action calendar unavailable state', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));
    await waitFor(() => expect(mockedGetVietnamCorporateActions).toHaveBeenCalledWith(['FPT'], 6));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByRole('heading', { name: 'SSI DailyStockPrice' })).toBeInTheDocument();
    expect(detail.getByText('Reference')).toBeInTheDocument();
    expect(within(detail.getByText('Reference').closest('div') as HTMLElement).getByText('99')).toBeInTheDocument();
    expect(detail.getByText('Ceiling / floor')).toBeInTheDocument();
    expect(detail.getByText('106 / 92')).toBeInTheDocument();
    expect(detail.getByText('Foreign net')).toBeInTheDocument();
    expect(detail.getByText('5 shares')).toBeInTheDocument();
    expect(detail.getByText('Foreign net value')).toBeInTheDocument();
    expect(detail.getByText('200,000')).toBeInTheDocument();
    expect(detail.getByText('Matched value')).toBeInTheDocument();
    expect(detail.getByText('123,456,789,000')).toBeInTheDocument();
    expect(detail.getByText('Put-through value')).toBeInTheDocument();
    expect(detail.getByText('25,000,000')).toBeInTheDocument();
    expect(detail.getByText('Adjusted close')).toBeInTheDocument();
    expect(detail.getAllByText('100').length).toBeGreaterThan(0);
    expect(detail.getByText('Daily close vs reference')).toBeInTheDocument();
    expect(within(detail.getByText('Daily close vs reference').closest('div') as HTMLElement).getByText('+1 / +1.01%')).toBeInTheDocument();
    expect(detail.getByText('Adjusted close is shown only when SSI provides it. Corporate actions are not inferred from reference or adjusted prices.')).toBeInTheDocument();
    expect(detail.queryByText('Foreign net 5D latest available')).not.toBeInTheDocument();
    expect(detail.queryByText('Foreign net 20D latest available')).not.toBeInTheDocument();
    expect(detail.queryByText('Need 5 foreign rows')).not.toBeInTheDocument();
    expect(detail.queryByText('Need 20 foreign rows')).not.toBeInTheDocument();
    expect(detail.getByRole('heading', { name: 'Corporate actions' })).toBeInTheDocument();
    expect(detail.getByText('Recent and upcoming events')).toBeInTheDocument();
    expect(detail.getByText('Corporate action history/calendar unavailable.')).toBeInTheDocument();
    expect(detail.getByText('No verified Vietnam corporate-action event provider is configured.')).toBeInTheDocument();
    expect(detail.getByText('Latest price / OHLCV close (VND)')).toBeInTheDocument();
    expect(detail.getByText('100 / 100')).toBeInTheDocument();
  });

  it('hides absent optional SSI DailyStockPrice rows without blank detail fields', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      dailyStockPrice: {
        status: 'ok',
        date: '2026-06-10',
        referencePrice: 99,
        ceilingPrice: 106,
        floorPrice: 92,
        source: 'SSI',
      },
      foreign: {
        ...response.watchlist[0].foreign,
        netValue: null,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByRole('heading', { name: 'SSI DailyStockPrice' })).toBeInTheDocument();
    expect(detail.getByText('Reference')).toBeInTheDocument();
    expect(detail.getByText('Ceiling / floor')).toBeInTheDocument();
    expect(detail.queryByText('Foreign net value')).not.toBeInTheDocument();
    expect(detail.queryByText('Matched value')).not.toBeInTheDocument();
    expect(detail.queryByText('Put-through value')).not.toBeInTheDocument();
    expect(detail.queryByText('Adjusted close')).not.toBeInTheDocument();
    expect(detail.queryByText('SSI DailyStockPrice fields are unavailable for this ticker.')).not.toBeInTheDocument();
  });

  it('shows explicit upcoming and recent corporate-action events without replacing raw close', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      latestPrice: 26500,
      dailyClose: 26500,
      ohlcvClose: 26500,
      close: 26500,
      previousClose: 27000,
      priceLimit: {
        ...response.watchlist[0].priceLimit,
        referencePrice: 26000,
        ceilingPrice: 27800,
        floorPrice: 24200,
      },
      dailyStockPrice: {
        ...response.watchlist[0].dailyStockPrice,
        referencePrice: 26000,
        ceilingPrice: 27800,
        floorPrice: 24200,
        close: 26500,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamCorporateActions.mockImplementation(async (tickers) => makeCorporateActionsResponse(tickers, {
      status: 'ok',
      source: 'provider_name',
      error: null,
      errorDetail: null,
      items: [
        {
          ticker: 'FPT',
          eventType: 'cash_dividend',
          status: 'upcoming',
          exDate: '2026-06-12',
          recordDate: '2026-06-13',
          paymentDate: '2026-06-30',
          cashDividendPerShare: 1000,
          description: 'Cash dividend 1,000 VND/share',
          source: 'provider_name',
          sourceUrl: null,
          lastCheckedAt: '2026-06-11T10:00:00+07:00',
        },
        {
          ticker: 'FPT',
          eventType: 'meeting',
          status: 'recent',
          exDate: null,
          recordDate: '2026-05-20',
          paymentDate: null,
          description: 'Annual general meeting',
          source: 'provider_name',
          sourceUrl: null,
          lastCheckedAt: '2026-06-11T10:00:00+07:00',
        },
      ],
    }));
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers),
      quotes: makeRealtimeResponse(tickers).quotes.map((quote) => ({
        ...quote,
        realtimePrice: quote.symbol === 'FPT' ? 26500 : quote.realtimePrice,
        snapshotPrice: quote.symbol === 'FPT' ? 26500 : quote.snapshotPrice,
        referencePrice: quote.symbol === 'FPT' ? 26000 : quote.referencePrice,
        priceVsReference: quote.symbol === 'FPT' ? 500 : quote.priceVsReference,
        priceVsReferencePct: quote.symbol === 'FPT' ? 1.92 : quote.priceVsReferencePct,
      })),
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamCorporateActions).toHaveBeenCalledWith(['FPT'], 6));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByText('Latest price / OHLCV close (VND)')).toBeInTheDocument();
    expect(detail.getByText('26,500 / 26,500')).toBeInTheDocument();
    expect(within(detail.getByText('Reference').closest('div') as HTMLElement).getByText('26,000')).toBeInTheDocument();
    expect(within(detail.getByText('Daily close vs reference').closest('div') as HTMLElement).getByText('+500 / +1.92%')).toBeInTheDocument();
    expect(detail.getByRole('heading', { name: 'Corporate actions' })).toBeInTheDocument();
    expect(detail.getByText('Recent and upcoming events')).toBeInTheDocument();
    expect(detail.getByText('Upcoming')).toBeInTheDocument();
    expect(detail.getByText('Recent, last 6 months')).toBeInTheDocument();
    expect(detail.getByText('cash dividend')).toBeInTheDocument();
    expect(detail.getAllByText('2026-06-12').length).toBeGreaterThan(0);
    expect(detail.getByText('Cash dividend')).toBeInTheDocument();
    expect(detail.getByText('1,000 VND/share')).toBeInTheDocument();
    expect(detail.getByText('meeting')).toBeInTheDocument();
    expect(detail.getByText('Annual general meeting')).toBeInTheDocument();
    expect(detail.getAllByText(/Source: provider_name/).length).toBeGreaterThan(0);
  });

  it('shows the OK-empty corporate-action state without inferring events', async () => {
    mockedGetVietnamCorporateActions.mockImplementation(async (tickers) => makeCorporateActionsResponse(tickers, {
      status: 'ok',
      source: 'provider_name',
      error: null,
      errorDetail: null,
      items: [],
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamCorporateActions).toHaveBeenCalledWith(['FPT'], 6));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByRole('heading', { name: 'Corporate actions' })).toBeInTheDocument();
    expect(detail.getByText('Recent and upcoming events')).toBeInTheDocument();
    expect(detail.getByText('No recent or upcoming corporate actions found.')).toBeInTheDocument();
  });

  it('renders the inspect chart with range controls, overlays, volume, and RSI', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    const chartHeading = detail.getByRole('heading', { name: 'Inspect chart' });
    const chartCard = within(chartHeading.closest('div')?.parentElement?.parentElement as HTMLElement);

    expect(chartCard.getByText('Daily OHLCV from SSI. KBS snapshot remains separate.')).toBeInTheDocument();
    expect(chartCard.getByRole('button', { name: '1M' })).toBeInTheDocument();
    expect(chartCard.getByRole('button', { name: '3M' })).toBeInTheDocument();
    expect(chartCard.getByRole('button', { name: '6M' })).toHaveAttribute('aria-pressed', 'true');
    expect(chartCard.getByRole('button', { name: '1Y' })).toBeInTheDocument();
    expect(chartCard.getByLabelText('MA20')).toBeChecked();
    expect(chartCard.getByLabelText('MA50')).toBeChecked();
    expect(chartCard.getByLabelText('Bollinger')).not.toBeChecked();
    expect(chartCard.getByRole('button', { name: 'Zoom in chart' })).toBeInTheDocument();
    expect(chartCard.getByRole('button', { name: 'Zoom out chart' })).toBeDisabled();
    expect(chartCard.getByRole('button', { name: 'Pan left' })).toBeDisabled();
    expect(chartCard.getByRole('button', { name: 'Pan right' })).toBeDisabled();
    expect(chartCard.getByRole('button', { name: 'Reset chart zoom' })).toBeDisabled();
    expect(chartCard.getByRole('button', { name: 'Expand chart' })).toBeInTheDocument();
    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 70 of 70');
    expect(chartCard.getByTestId('inspect-candlestick-chart')).toBeInTheDocument();
    expect(chartCard.getAllByTestId('inspect-chart-date-label').length).toBeGreaterThanOrEqual(4);
    expect(chartCard.getByText('Apr 1')).toBeInTheDocument();
    expect(chartCard.getByText('Jun 9')).toBeInTheDocument();
    expect(chartCard.getByTestId('inspect-legend-candles')).toHaveTextContent('Candlesticks');
    expect(chartCard.getByTestId('inspect-legend-ma20')).toBeInTheDocument();
    expect(chartCard.getByTestId('inspect-legend-ma50')).toBeInTheDocument();
    expect(chartCard.queryByTestId('inspect-legend-bollinger')).not.toBeInTheDocument();
    expect(chartCard.getByText('Volume MA20')).toBeInTheDocument();
    expect(chartCard.getByText('Volume MA50')).toBeInTheDocument();
    expect(chartCard.getAllByText('RSI14').length).toBeGreaterThan(0);
    expect(chartCard.getByText('RSI14 numeric guides: 30 and 70.')).toBeInTheDocument();
    expect(chartCard.getByText('Daily OHLCV source: SSI')).toBeInTheDocument();
    expect(chartCard.getByText('KBS snapshot is separate and not used as daily close.')).toBeInTheDocument();
    expect(chartCard.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();
  });

  it('renders SSI as the inspect chart source when the chart payload uses SSI', async () => {
    mockedGetVietnamChart.mockResolvedValue(makeChartResponse('FPT', '6M', makeChartData(), { source: 'SSI' }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    expect(chartCard.getByText('Daily OHLCV from SSI. KBS snapshot remains separate.')).toBeInTheDocument();
    expect(chartCard.getByText('Daily OHLCV source: SSI')).toBeInTheDocument();
    expect(chartCard.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();
  });

  it('renders an SSI unavailable source label for inspect chart payloads', async () => {
    mockedGetVietnamChart.mockResolvedValue(
      makeChartResponse('FPT', '6M', [], { status: 'unavailable', source: 'SSI', reason: 'SSI FastConnect unavailable' }),
    );

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    expect(chartCard.getByText('Daily OHLCV from SSI unavailable. KBS snapshot remains separate.')).toBeInTheDocument();
    expect(chartCard.getByText('Daily OHLCV source: SSI unavailable')).toBeInTheDocument();
    expect(chartCard.getByText('Chart data unavailable')).toBeInTheDocument();
    expect(chartCard.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();
  });

  it('zooms the inspect chart visible candle window in and out', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    const initialLabels = inspectDateLabels(chartCard);
    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 70 of 70');

    fireEvent.click(chartCard.getByRole('button', { name: 'Zoom in chart' }));

    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 48 of 70');
    expect(inspectDateLabels(chartCard)).not.toEqual(initialLabels);
    expect(chartCard.queryByText('Apr 1')).not.toBeInTheDocument();
    expect(chartCard.queryByText('Jun 9')).not.toBeInTheDocument();
    expect(chartCard.getByRole('button', { name: 'Zoom out chart' })).toBeEnabled();

    fireEvent.click(chartCard.getByRole('button', { name: 'Zoom out chart' }));

    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 70 of 70');
    expect(inspectDateLabels(chartCard)).toEqual(initialLabels);
  });

  it('pans the inspect chart visible window left and right', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    fireEvent.click(chartCard.getByRole('button', { name: 'Zoom in chart' }));
    const zoomedLabels = inspectDateLabels(chartCard);

    expect(chartCard.getByRole('button', { name: 'Pan left' })).toBeEnabled();
    expect(chartCard.getByRole('button', { name: 'Pan right' })).toBeEnabled();

    fireEvent.click(chartCard.getByRole('button', { name: 'Pan left' }));

    const leftLabels = inspectDateLabels(chartCard);
    expect(leftLabels).not.toEqual(zoomedLabels);
    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 48 of 70');

    fireEvent.click(chartCard.getByRole('button', { name: 'Pan right' }));

    expect(inspectDateLabels(chartCard)).not.toEqual(leftLabels);
    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 48 of 70');
  });

  it('resets the inspect chart visible window to the selected range', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    fireEvent.click(chartCard.getByRole('button', { name: 'Zoom in chart' }));
    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 48 of 70');

    fireEvent.click(chartCard.getByRole('button', { name: 'Reset chart zoom' }));

    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 70 of 70');
    expect(chartCard.getByText('Apr 1')).toBeInTheDocument();
    expect(chartCard.getByText('Jun 9')).toBeInTheDocument();
    expect(chartCard.getByRole('button', { name: 'Reset chart zoom' })).toBeDisabled();
  });

  it('opens an expanded inspect chart with the same controls and closes it', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    fireEvent.click(chartCard.getByRole('button', { name: 'Expand chart' }));

    const dialogElement = screen.getByRole('dialog', { name: 'Expanded inspect chart' });
    const dialog = within(dialogElement);
    expect(dialog.getByText('Daily OHLCV from SSI. KBS snapshot remains separate.')).toBeInTheDocument();
    expect(dialog.getByRole('button', { name: '6M' })).toHaveAttribute('aria-pressed', 'true');
    expect(dialog.getByLabelText('MA20')).toBeChecked();
    expect(dialog.getByLabelText('MA50')).toBeChecked();
    expect(dialog.getByLabelText('Bollinger')).not.toBeChecked();
    expect(dialog.getByRole('button', { name: 'Zoom in chart' })).toBeInTheDocument();
    expect(dialog.getByRole('button', { name: 'Pan left' })).toBeDisabled();
    expect(dialog.getByRole('button', { name: 'Reset chart zoom' })).toBeDisabled();
    expect(dialog.getByTestId('inspect-chart-expanded-visible-count')).toHaveTextContent('Showing 70 of 70');
    expect(dialog.getByTestId('inspect-candlestick-chart')).toBeInTheDocument();

    fireEvent.click(dialog.getByRole('button', { name: 'Zoom in chart' }));

    expect(dialog.getByTestId('inspect-chart-expanded-visible-count')).toHaveTextContent('Showing 48 of 70');
    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 48 of 70');

    fireEvent.click(dialog.getByLabelText('Bollinger'));
    expect(dialog.getByText('Bollinger upper/mid/lower')).toBeInTheDocument();
    expect(dialog.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();

    fireEvent.click(dialog.getByRole('button', { name: 'Close expanded chart' }));
    expect(screen.queryByRole('dialog', { name: 'Expanded inspect chart' })).not.toBeInTheDocument();

    fireEvent.click(chartCard.getByRole('button', { name: 'Expand chart' }));
    expect(screen.getByRole('dialog', { name: 'Expanded inspect chart' })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Expanded inspect chart' })).not.toBeInTheDocument();
  });

  it('shows Bollinger overlay only after enabling the chart toggle', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    const chartHeading = detail.getByRole('heading', { name: 'Inspect chart' });
    const chartCard = within(chartHeading.closest('div')?.parentElement?.parentElement as HTMLElement);

    expect(chartCard.queryByTestId('inspect-legend-bollinger')).not.toBeInTheDocument();
    fireEvent.click(chartCard.getByLabelText('Bollinger'));
    expect(chartCard.getByTestId('inspect-legend-bollinger')).toHaveTextContent('Bollinger upper/mid/lower');
  });

  it('requests the selected chart range when a range control changes', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    const chartHeading = detail.getByRole('heading', { name: 'Inspect chart' });
    const chartCard = within(chartHeading.closest('div')?.parentElement?.parentElement as HTMLElement);

    fireEvent.click(chartCard.getByRole('button', { name: '1Y' }));

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '1Y'));
    expect(chartCard.getByRole('button', { name: '1Y' })).toHaveAttribute('aria-pressed', 'true');
    expect(chartCard.getAllByTestId('inspect-chart-date-label').length).toBeGreaterThanOrEqual(4);
    expect(chartCard.getByText('Apr 1')).toBeInTheDocument();
    expect(chartCard.getByText('Jun 9')).toBeInTheDocument();
    expect(chartCard.queryByText(/buy|sell|hold|recommendation/i)).not.toBeInTheDocument();
  });

  it('resets chart zoom when switching the selected range', async () => {
    mockedGetVietnamChart.mockImplementation(async (symbol, range = '6M') => {
      const points = range === '1M' ? makeChartData().slice(40) : makeChartData();
      return makeChartResponse(symbol, range, points);
    });

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const chartCard = inspectChartCard();
    fireEvent.click(chartCard.getByRole('button', { name: 'Zoom in chart' }));
    expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 48 of 70');

    fireEvent.click(chartCard.getByRole('button', { name: '1M' }));

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '1M'));
    await waitFor(() => expect(chartCard.getByTestId('inspect-chart-visible-count')).toHaveTextContent('Showing 30 of 30'));
    expect(chartCard.getByRole('button', { name: 'Reset chart zoom' })).toBeDisabled();
    expect(chartCard.getByRole('button', { name: '1M' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('renders chart data unavailable when selected ticker has no chart points', async () => {
    mockedGetVietnamChart.mockResolvedValue(makeChartResponse('FPT', '6M', []));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    const chartHeading = detail.getByRole('heading', { name: 'Inspect chart' });
    const chartCard = within(chartHeading.closest('div')?.parentElement?.parentElement as HTMLElement);
    expect(chartCard.getByText('Chart data unavailable')).toBeInTheDocument();
    expect(chartCard.queryByRole('button', { name: 'Zoom in chart' })).not.toBeInTheDocument();
    expect(chartCard.queryByRole('button', { name: 'Zoom out chart' })).not.toBeInTheDocument();
    expect(chartCard.queryByRole('button', { name: 'Pan left' })).not.toBeInTheDocument();
    expect(chartCard.queryByRole('button', { name: 'Pan right' })).not.toBeInTheDocument();
    expect(chartCard.queryByRole('button', { name: 'Reset chart zoom' })).not.toBeInTheDocument();
    expect(chartCard.queryAllByTestId('inspect-chart-date-label')).toHaveLength(0);
  });

  it('keeps the watchlist rendered when the chart endpoint fails', async () => {
    mockedGetVietnamChart.mockRejectedValue(new Error('chart failed'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamChart).toHaveBeenCalledWith('FPT', '6M'));

    expect(screen.getByRole('heading', { name: 'Indicator table' })).toBeInTheDocument();
    const detail = within(screen.getByText('Stock detail').closest('section') as HTMLElement);
    expect(detail.getByText('Chart data unavailable')).toBeInTheDocument();
    expect(detail.getByText('Chart endpoint unavailable: chart failed')).toBeInTheDocument();
  });

  it('clarifies Mozyfin 1H and KBS volume labels while preserving numeric values', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: 4800000,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 4800000 },
      intradayCandles: [
        {
          dateTime: '2026-06-11T10:00:00+07:00',
          timestamp: 1781161200,
          open: 100,
          high: 103,
          low: 99,
          close: 102,
          volume: 1234567,
        },
      ],
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: 103,
        sessionLowFrom1H: 99,
        sessionRangePctFrom1H: 4,
        sessionVolumeFrom1H: 1234567,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2345678,
        loadedCandlesTotalVolume: 2345678,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: 1.75,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers),
      quotes: makeRealtimeResponse(tickers).quotes.map((quote) => ({
        ...quote,
        volumeAccumulated: quote.symbol === 'FPT' ? 3456000 : quote.volumeAccumulated,
      })),
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Latest 1H candle volume')).toBeInTheDocument();
    expect(screen.getByText('Mozyfin session 1H volume')).toBeInTheDocument();
    expect(screen.getAllByText('Session volume / 20D avg daily volume').length).toBeGreaterThan(0);
    expect(screen.queryByText('Loaded 1H candles total volume (all loaded)')).not.toBeInTheDocument();
    expect(screen.queryByText('Volume ratio')).not.toBeInTheDocument();
    expect(screen.queryByText('Vol ratio')).not.toBeInTheDocument();
    expect(screen.getByText('KBS session accumulated volume')).toBeInTheDocument();
    expect(screen.getByText('Mozyfin session 1H volume is calculated from filtered 1H candles; KBS session volume comes from the realtime board and may differ.')).toBeInTheDocument();
    expect(screen.getAllByText('1,234,567').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('3,456,000').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0.72x').length).toBeGreaterThan(0);
    expect(screen.getByText('103 / 99')).toBeInTheDocument();
    expect(screen.getByText('4%')).toBeInTheDocument();
    const sessionCandlesLabel = screen.getByText('Session 1H candles');
    expect(within(sessionCandlesLabel.closest('div') as HTMLElement).getByText('5')).toBeInTheDocument();
    expect(screen.queryByText('Not enough session candles')).not.toBeInTheDocument();
    expect(screen.getByText('Latest 1H volume vs avg 1H')).toBeInTheDocument();
    expect(screen.getByText('1.75x')).toBeInTheDocument();
  });

  it('falls back to Mozyfin session 1H volume when KBS accumulated volume is stale', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: 4800000,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 4800000 },
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: 103,
        sessionLowFrom1H: 99,
        sessionRangePctFrom1H: 4,
        sessionVolumeFrom1H: 2400000,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2400000,
        loadedCandlesTotalVolume: 2400000,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: null,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers, { stale: true }),
      quotes: makeRealtimeResponse(tickers, { stale: true }).quotes.map((quote) => ({
        ...quote,
        volumeAccumulated: quote.symbol === 'FPT' ? 3456000 : quote.volumeAccumulated,
      })),
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getAllByText('Session volume / 20D avg daily volume').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0.5x').length).toBeGreaterThan(0);
    expect(screen.queryByText('0.72x')).not.toBeInTheDocument();
  });

  it('shows volume ratio missing states when daily average or session volume is unavailable', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: null,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: null },
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: 103,
        sessionLowFrom1H: 99,
        sessionRangePctFrom1H: 4,
        sessionVolumeFrom1H: 2400000,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2400000,
        loadedCandlesTotalVolume: 2400000,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: null,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getAllByText('20D avg unavailable').length).toBeGreaterThan(0);
  });

  it('shows a session volume missing state when neither KBS nor Mozyfin session volume is available', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: 4800000,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 4800000 },
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: 103,
        sessionLowFrom1H: 99,
        sessionRangePctFrom1H: 4,
        sessionVolumeFrom1H: null,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2400000,
        loadedCandlesTotalVolume: 2400000,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: null,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => ({
      ...makeRealtimeResponse(tickers, { unavailable: true }),
      quotes: makeRealtimeResponse(tickers, { unavailable: true }).quotes.map((quote) => ({
        ...quote,
        volumeAccumulated: null,
      })),
    }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getAllByText('Session volume unavailable').length).toBeGreaterThan(0);
  });

  it('shows explanatory intraday empty states instead of bare placeholders', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: null,
        sessionLowFrom1H: null,
        sessionRangePctFrom1H: null,
        sessionVolumeFrom1H: null,
        sessionCandlesCount: 0,
        cumulative1hVolume: 2345678,
        loadedCandlesTotalVolume: 2345678,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: null,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const sessionHighLowLabel = screen.getByText('Session high / low from 1H');
    const sessionHighLowCard = sessionHighLowLabel.closest('div');
    expect(within(sessionHighLowCard as HTMLElement).getByText('Not enough session candles')).toHaveAttribute(
      'title',
      'Session high/low requires current-session intraday candles.',
    );
    expect(within(sessionHighLowCard as HTMLElement).queryByText('- / -')).not.toBeInTheDocument();

    const sessionVolumeLabel = screen.getByText('Mozyfin session 1H volume');
    const sessionVolumeCard = sessionVolumeLabel.closest('div');
    expect(within(sessionVolumeCard as HTMLElement).getByText('Not enough session candles')).toHaveAttribute(
      'title',
      'Session volume requires current-session intraday candles.',
    );

    expect(screen.queryByText('Latest 1H volume vs avg 1H')).not.toBeInTheDocument();
    expect(screen.queryByText('Avg unavailable')).not.toBeInTheDocument();
  });

  it('shows unavailable session values when session candles exist but metrics are missing', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      intradayPulse: {
        latest1hClose: 102,
        latest1hOpen: 100,
        latest1hHigh: 103,
        latest1hLow: 99,
        latest1hVolume: 1234567,
        latest1hChange: 2,
        latest1hChangePercent: 2,
        sessionHighFrom1H: null,
        sessionLowFrom1H: null,
        sessionRangePctFrom1H: null,
        sessionVolumeFrom1H: null,
        sessionCandlesCount: 5,
        cumulative1hVolume: 2345678,
        loadedCandlesTotalVolume: 2345678,
        direction: 'up',
        rangePercent: 4,
        volumeVsAvg1h: 1.75,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Session 1H candles')).toBeInTheDocument();
    expect(screen.getAllByText('5').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Session value unavailable').length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText('Not enough session candles')).not.toBeInTheDocument();
  });

  it('displays 20D average volume from indicators', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: 1234567,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 7654321 },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getAllByText('20D average volume (shares)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1,234,567').length).toBeGreaterThan(0);
  });

  it('falls back to liquidity 20D average volume when indicator value is missing', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      indicators: {
        ...response.watchlist[0].indicators,
        avgVolume20D: null,
      },
      liquidity: { ...response.watchlist[0].liquidity, avgVolume20D: 7654321 },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getAllByText('7,654,321').length).toBeGreaterThan(0);
  });

  it('displays final close as not confirmed instead of unknown', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      finalCloseStatus: 'unknown',
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const finalCloseLabel = screen.getByText('Price date / final close');
    const finalCloseCard = finalCloseLabel.closest('div');
    expect(within(finalCloseCard as HTMLElement).getByText('2026-06-10 / not confirmed')).toBeInTheDocument();
    expect(within(finalCloseCard as HTMLElement).queryByText(/unknown/)).not.toBeInTheDocument();
  });

  it('shows latest-available foreign net labels and mismatch note', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      dailyStockPrice: { status: 'unavailable', source: 'SSI DailyStockPrice' },
      ohlcvDate: '2026-06-12',
      foreignNetDate: '2026-06-11',
      foreignDateMatch: 'mismatched',
      indicators: {
        ...response.watchlist[0].indicators,
        foreignNet5dLatestAvailable: 12345,
        foreignNet20dLatestAvailable: -67890,
        foreignNetHistoryCount: 20,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Foreign net 5D latest available')).toBeInTheDocument();
    expect(screen.getByText('Foreign net 20D latest available')).toBeInTheDocument();
    expect(screen.getByText('12,345')).toBeInTheDocument();
    expect(screen.getByText('-67,890')).toBeInTheDocument();
    expect(screen.getByText('Foreign data as of 2026-06-11; OHLCV date 2026-06-12.')).toBeInTheDocument();
  });

  it('shows latest-available foreign empty states when quote history is short', async () => {
    const response = makeResponse(defaultTickers);
    response.watchlist[0] = {
      ...response.watchlist[0],
      dailyStockPrice: { status: 'unavailable', source: 'SSI DailyStockPrice' },
      indicators: {
        ...response.watchlist[0].indicators,
        foreignNet5dLatestAvailable: null,
        foreignNet20dLatestAvailable: null,
        foreignNetHistoryCount: 4,
      },
    };
    mockedGetVietnamWatchlist.mockResolvedValue(response);

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(screen.getByText('Need 5 foreign rows')).toBeInTheDocument();
    expect(screen.getByText('Need 20 foreign rows')).toBeInTheDocument();
  });

  it('renders data status with Mozyfin source and fixture state', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const panel = dataStatusPanel();
    expect(panel.getByText('Data status')).toBeInTheDocument();
    expect(panel.getByText('Data status: OK')).toBeInTheDocument();
    expect(panel.getByText('Continuous afternoon')).toBeInTheDocument();
    expect(panel.getAllByText('holidayAware=false').length).toBeGreaterThan(0);
    expect(panel.getAllByText('SSI live').length).toBeGreaterThan(0);
    expect(dataStatusDiagnostics()).not.toHaveAttribute('open');
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(dataStatusDiagnostics()).toHaveAttribute('open');
    expect(panel.getByText('VN market phase')).toBeInTheDocument();
    expect(panel.getByText('fixture_mode false')).toBeInTheDocument();
    expect(panel.getByText('Overview refresh')).toBeInTheDocument();
    expect(panel.getByText('Selected detail')).toBeInTheDocument();
  });

  it('fetches observability on initial load', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
  });

  it('observability failure does not break dashboard rendering', async () => {
    mockedGetVietnamObservability.mockRejectedValue(new Error('observability down'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    expect(await screen.findByRole('heading', { name: 'Data status' })).toBeInTheDocument();
    expect(screen.getAllByText('FPT').length).toBeGreaterThan(0);
  });

  it('displays compact observability counters in data status', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());

    const panel = dataStatusPanel();
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText('Mozyfin req')).toBeInTheDocument();
    expect(panel.getAllByText('3').length).toBeGreaterThan(0);
    expect(panel.getByText('Cache hit/miss')).toBeInTheDocument();
    expect(panel.getByText('40/8')).toBeInTheDocument();
    expect(panel.getByText('Single-flight waits')).toBeInTheDocument();
    expect(panel.getAllByText('1').length).toBeGreaterThan(0);
    expect(panel.getByText('KBS quote unavailable')).toBeInTheDocument();
    expect(panel.getByText('2/12')).toBeInTheDocument();
    expect(panel.getByText('KBS trade unavailable')).toBeInTheDocument();
    expect(panel.getByText('4/20')).toBeInTheDocument();
    expect(panel.getByText('KBS provider timeout')).toBeInTheDocument();
  });

  it('fetching observability does not call watchlist, realtime, or trades by itself', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    mockedGetVietnamWatchlist.mockClear();
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    await stocksApi.getVietnamObservability();

    expect(mockedGetVietnamWatchlist).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
  });

  it('shows auction helper copy during ATC phase', async () => {
    mockedGetVietnamMarketPhase.mockReturnValue(makeMarketPhase('ATC closing auction', 'atc', true));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const panel = dataStatusPanel();
    expect(panel.getByText('ATC closing auction')).toBeInTheDocument();
    expect(panel.getByText('Trade tape may differ during auction phases.')).toBeInTheDocument();
  });

  it('shows fixture warning in data status when Mozyfin fixture mode is active', async () => {
    mockedGetVietnamWatchlist.mockImplementation(async (tickers) => makeResponse(tickers?.length ? tickers : defaultTickers, { fixtureMode: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    const panel = dataStatusPanel();
    expect(panel.getAllByText('Mozyfin fixture').length).toBeGreaterThan(0);
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText('fixture_mode true')).toBeInTheDocument();
    expect(panel.getByText('Fixture mode is active; Mozyfin rows are sample data.')).toBeInTheDocument();
  });

  it('shows KBS ok status when snapshot rows are fresh', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const panel = dataStatusPanel();
    expect(panel.getAllByText('KBS snapshot live').length).toBeGreaterThan(0);
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText('raw stale 0 | unavailable 0')).toBeInTheDocument();
  });

  it('realtime failure does not erase overview rows', async () => {
    mockedGetVietnamRealtimeQuotes.mockRejectedValueOnce(new Error('KBS down'));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));

    expect(await screen.findByText(/KBS snapshot unavailable: KBS down/)).toBeInTheDocument();
    expect(screen.getAllByText('FPT').length).toBeGreaterThan(0);
    expect(screen.getAllByText('ACB').length).toBeGreaterThan(0);
  });

  it('shows normalized KBS timeout without raw provider text in warning banners', async () => {
    const rawTimeout = 'è¿žæŽ¥ä¸Šæ¸¸æœåŠ¡è¶…æ—¶: upstream timeout';
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, {
      error: 'KBS provider timeout',
      errorDetail: 'The upstream KBS provider did not respond in time.',
      rawError: rawTimeout,
    }));
    mockedGetVietnamRealtimeTrades.mockImplementation(async (symbol) => ({
      ...makeTradesResponse(symbol),
      status: 'unavailable',
      error: 'KBS provider timeout',
      errorDetail: 'The upstream KBS provider did not respond in time.',
      rawError: rawTimeout,
      trades: [],
    }));

    render(<VietnamDashboardPage />);

    expect(await screen.findByText('KBS snapshot unavailable: KBS provider timeout')).toBeInTheDocument();
    expect(screen.getByText('KBS issue: KBS provider timeout')).toBeInTheDocument();
    expect(screen.getByText('Latest trade tape unavailable: KBS provider timeout')).toBeInTheDocument();
    expect(screen.queryByText(/è¿žæŽ¥ä¸Šæ¸¸æœåŠ¡è¶…æ—¶/)).not.toBeInTheDocument();
  });

  it('shows active-trading stale warning when KBS marks a snapshot stale during trading', async () => {
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { stale: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getAllByText('KBS snapshot stale during trading').length).toBeGreaterThan(0);
    expect(screen.getAllByText('2026-06-11T10:15:00+07:00').length).toBeGreaterThan(0);
    const panel = dataStatusPanel();
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText(`raw stale ${defaultTickers.length} | unavailable 0`)).toBeInTheDocument();
    expect(panel.getByText('raw age 600s | raw stale true | reason age_gt_60s')).toBeInTheDocument();
    expect(screen.getAllByText('raw age 600s | raw stale true | reason age_gt_60s')).toHaveLength(1);
  });

  it('shows last available state after close without active-trading stale wording', async () => {
    mockedGetVietnamMarketPhase.mockReturnValue(makeMarketPhase('Closed', 'closed'));
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { stale: true, ageSeconds: 1200 }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    expect(screen.getAllByText('Last available KBS snapshot').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Market closed; snapshot may stop updating/).length).toBeGreaterThan(0);
    expect(screen.queryByText('KBS snapshot stale during trading')).not.toBeInTheDocument();
    const panel = dataStatusPanel();
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText(`raw stale ${defaultTickers.length} | unavailable 0`)).toBeInTheDocument();
    expect(panel.getByText('raw age 1200s | raw stale true | reason age_gt_60s')).toBeInTheDocument();
    expect(screen.getAllByText('raw age 1200s | raw stale true | reason age_gt_60s')).toHaveLength(1);
  });

  it('shows KBS unavailable count when snapshot rows are unavailable', async () => {
    mockedGetVietnamRealtimeQuotes.mockImplementation(async (tickers) => makeRealtimeResponse(tickers, { unavailable: true }));

    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers));

    const panel = dataStatusPanel();
    expect(panel.getAllByText('KBS snapshot unavailable').length).toBeGreaterThan(0);
    fireEvent.click(panel.getByText('Show diagnostics'));
    expect(panel.getByText(`raw stale 0 | unavailable ${defaultTickers.length}`)).toBeInTheDocument();
  });

  it('refresh KBS calls realtime endpoints only', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();
    mockedGetVietnamObservability.mockClear();

    fireEvent.click(screen.getByRole('button', { name: /refresh kbs/i }));

    await waitFor(() => {
      expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);
      expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100);
    });
    await waitFor(() => expect(mockedGetVietnamObservability).toHaveBeenCalled());
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
  });

  it('manual Refresh KBS does not create overlapping duplicate requests', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    let resolveQuotes: ((response: VietnamRealtimeResponse) => void) | undefined;
    let resolveTrades: ((response: VietnamRealtimeTradesResponse) => void) | undefined;
    mockedGetVietnamRealtimeQuotes.mockImplementation(() => new Promise((resolve) => {
      resolveQuotes = resolve;
    }));
    mockedGetVietnamRealtimeTrades.mockImplementation(() => new Promise((resolve) => {
      resolveTrades = resolve;
    }));

    fireEvent.click(screen.getByRole('button', { name: /refresh kbs/i }));

    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: /refreshing kbs/i })).toBeDisabled();

    await act(async () => {
      resolveQuotes?.(makeRealtimeResponse(defaultTickers));
      resolveTrades?.(makeTradesResponse('FPT'));
    });
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
    mockedGetVietnamObservability.mockClear();

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh KBS' }));

    await act(async () => {
      vi.advanceTimersByTime(10000);
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100);
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamObservability).toHaveBeenCalled();

    mockedGetVietnamRealtimeTrades.mockClear();
    mockedGetVietnamObservability.mockClear();

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledWith(defaultTickers);
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamObservability).toHaveBeenCalled();
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

  it('changing KBS intervals does not call Mozyfin endpoints', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    fireEvent.change(screen.getByLabelText('KBS quotes'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('Latest trade tape'), { target: { value: '5' } });

    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();
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

  it('visibility restore fires at most one quote and one trade request', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeQuotes.mockClear();
    mockedGetVietnamRealtimeTrades.mockClear();

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-refresh KBS' }));

    await act(async () => {
      vi.advanceTimersByTime(30000);
      await Promise.resolve();
    });
    expect(mockedGetVietnamRealtimeQuotes).not.toHaveBeenCalled();
    expect(mockedGetVietnamRealtimeTrades).not.toHaveBeenCalled();

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    fireEvent(document, new Event('visibilitychange'));

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockedGetVietnamRealtimeQuotes).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
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

  it('selected ticker change does not overlap trade fetches and refreshes pending ticker', async () => {
    render(<VietnamDashboardPage />);

    await waitFor(() => expect(mockedGetVietnamWatchlist).toHaveBeenCalledWith(defaultTickers, false));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));
    const watchlistCalls = mockedGetVietnamWatchlist.mock.calls.length;
    mockedGetVietnamRealtimeTrades.mockClear();

    let resolveFptTrades: ((response: VietnamRealtimeTradesResponse) => void) | undefined;
    mockedGetVietnamRealtimeTrades.mockImplementationOnce(() => new Promise((resolve) => {
      resolveFptTrades = resolve;
    }));

    fireEvent.click(screen.getByRole('button', { name: /refresh kbs/i }));
    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('FPT', 100));

    clickTickerRow('ACB');

    expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveFptTrades?.(makeTradesResponse('FPT'));
    });

    await waitFor(() => expect(mockedGetVietnamRealtimeTrades).toHaveBeenCalledWith('ACB', 100));
    expect(mockedGetVietnamWatchlist).toHaveBeenCalledTimes(watchlistCalls);
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
