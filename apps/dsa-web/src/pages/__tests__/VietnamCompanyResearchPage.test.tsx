import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type VietnamCompanyResearchResponse } from '../../api/stocks';
import VietnamCompanyResearchPage from '../VietnamCompanyResearchPage';

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getVietnamCompanyResearch: vi.fn(),
  },
}));

const makeCompanySnapshot = (): VietnamCompanyResearchResponse => ({
  ticker: 'FPT',
  status: 'ok',
  sessionContext: {
    completedSessionDate: '2026-06-17',
    liveSessionDate: '2026-06-18',
    providerEventTime: '2026-06-18T09:41:23+07:00',
    sessionPhase: 'continuous_morning',
    marketSessionActive: true,
    sourceFreshness: 'latest_completed',
  },
  liveMarket: {
    status: 'ready',
    channels: {
      lastPrice: 'ready',
      orderBook: 'ready',
      tradeTape: 'ready',
      intraday: 'ready',
    },
    usableChannelCount: 4,
    sessionDate: '2026-06-18',
  },
  profile: {
    ticker: 'FPT',
    name: 'FPT Corporation',
    nameEn: 'FPT Corporation',
    exchange: 'HOSE',
    market: 'HOSE',
    industry: 'Information Technology',
    sector: 'Technology',
    securityType: 'stock',
    issuer: 'FPT',
    lotSize: 100,
    listedShares: 1_471_000_000,
    listedDate: '2006-12-13',
    source: 'SSI SecuritiesDetails',
    status: 'ok',
    qualityStatus: 'complete',
    completeness: 1,
    missingFields: [],
    fieldCoverage: { symbol: true, name: true, industry: true },
    diagnostics: {
      endpoint: 'SecuritiesDetails',
      requestedSymbol: 'FPT',
      normalizedRowCount: 1,
    },
    coreProfileStatus: 'ready',
    optionalMetadataStatus: 'complete',
    classificationSource: 'SSI SecuritiesDetails',
  },
  price: {
    latestPrice: 124600,
    dailyClose: 124600,
    referencePrice: 123000,
    ceilingPrice: 131600,
    floorPrice: 114400,
    priceDate: '2026-06-17',
    source: 'SSI DailyOhlc',
    canonicalSource: 'SSI DailyOhlc',
    referenceSource: 'SSI DailyStockPrice',
    referencePriceSource: 'SSI DailyStockPrice',
    ceilingPriceSource: 'SSI DailyStockPrice',
    floorPriceSource: 'SSI DailyStockPrice',
    completedSessionDate: '2026-06-17',
    finalCloseStatus: 'completed',
    adjustmentStatus: 'not_provided',
    sourceFreshness: 'latest_completed',
    status: 'ok',
  },
  tradingStats: {
    open: 123400,
    high: 125000,
    low: 122800,
    close: 124600,
    volume: 1_234_567,
    value: 123_456_789_000,
    source: 'SSI DailyOhlc',
    status: 'ok',
  },
  dailyStockPrice: {
    status: 'ok',
    qualityStatus: 'ok',
    source: 'SSI DailyStockPrice',
    date: '2026-06-17',
    dateMatch: 'matched',
    referencePrice: 123000,
    ceilingPrice: 131600,
    floorPrice: 114400,
    adjustedClose: 124600,
    matchedVolume: 1_234_567,
    matchedValue: 123_456_789_000,
    putThroughVolume: 1_000,
    putThroughValue: 25_000_000,
    foreignBuyVolume: 100_000,
    foreignSellVolume: 80_000,
    foreignNetVolume: 20_000,
    foreignBuyValue: 1_000_000_000,
    foreignSellValue: 800_000_000,
    foreignNetValue: 200_000_000,
    foreignFlowValueState: 'nonzero',
    foreignFieldPresence: {
      foreign_buy_volume: 'FIELD_PRESENT_NONZERO',
      foreign_sell_volume: 'FIELD_PRESENT_NONZERO',
      foreign_net_volume: 'DERIVED_FROM_PRESENT_INPUTS',
      foreign_buy_value: 'FIELD_PRESENT_NONZERO',
      foreign_sell_value: 'FIELD_PRESENT_NONZERO',
      foreign_net_value: 'DERIVED_FROM_PRESENT_INPUTS',
    },
    capabilities: {
      priceLimitsStatus: 'ready',
      matchedStatsStatus: 'ready',
      putThroughStatus: 'ready',
      foreignFlowStatus: 'ready',
      sessionMetadataStatus: 'ready',
      overallStatus: 'ready',
    },
    missingFields: [],
    units: {
      matchedVolume: 'shares',
      matchedValue: 'VND',
    },
  },
  foreignFlow: {
    foreignBuyVolume: 100_000,
    foreignSellVolume: 80_000,
    foreignNetVolume: 20_000,
    foreignBuyValue: 1_000_000_000,
    foreignSellValue: 800_000_000,
    foreignNetValue: 200_000_000,
    date: '2026-06-17',
    dateMatch: 'matched',
    volumeUnit: 'shares',
    valueUnit: 'VND',
    source: 'SSI DailyStockPrice',
    status: 'ok',
    capabilityStatus: 'ready',
    valueState: 'nonzero',
    fieldPresence: {
      foreign_buy_volume: 'FIELD_PRESENT_NONZERO',
      foreign_sell_volume: 'FIELD_PRESENT_NONZERO',
      foreign_net_volume: 'DERIVED_FROM_PRESENT_INPUTS',
      foreign_buy_value: 'FIELD_PRESENT_NONZERO',
      foreign_sell_value: 'FIELD_PRESENT_NONZERO',
      foreign_net_value: 'DERIVED_FROM_PRESENT_INPUTS',
    },
  },
  technical: {
    ma20: 120000,
    ma50: 118000,
    rsi14: 55.5,
    bollingerUpper: 130000,
    bollingerMiddle: 120000,
    bollingerLower: 110000,
    high52w: 140000,
    high52wDate: '2026-06-01',
    low52w: 90000,
    low52wDate: '2025-12-01',
    highLow52wHistoryCount: 252,
    highLow52wCoverageStatus: 'complete',
    avgVolume10d: 1_100_000,
    avgVolume10dHistoryCount: 10,
    avgVolume10dCoverageStatus: 'complete',
    avgVolume3m: 1_050_000,
    avgVolume3mHistoryCount: 63,
    avgVolume3mCoverageStatus: 'complete',
    priceVsReferencePct: 1.3,
    priceVsReferenceStatus: 'ok',
    dailyRangePct: 1.77,
    dailyRangeStatus: 'ok',
    ssiDerivedMetricsStatus: 'ok',
    ssiDerivedMetricsSource: 'SSI DailyOhlc + SSI DailyStockPrice',
    source: 'SSI-derived',
    status: 'ok',
  },
  intraday: {
    source: 'SSI IntradayOhlc',
    status: 'ok',
    capabilityStatus: 'ready',
    requestedTimeframe: '1h',
    actualGranularity: '1m',
    cadenceStatus: 'matched',
    message: null,
    candles: [
      { dateTime: '2026-06-17T10:00:00+07:00', open: 123, high: 125, low: 122, close: 124, volume: 1000 },
    ],
    pulse: {
      latest1hClose: 124,
      latest1hChange: 1,
      latest1hChangePercent: 0.81,
      latest1hVolume: 1000,
      sessionVolumeFrom1H: 1000,
      latestIntradayClose: 124,
      intradayChange: 1,
      intradayChangePercent: 0.81,
      intradayChangeBaseline: 'first_session_candle_open',
      intradayChangeBaselineValue: 123,
      latestIntradayVolume: 1000,
      sessionVolumeFromIntraday: 1000,
      direction: 'up',
    },
  },
  realtimeStatus: {
    source: 'SSI realtime contract',
    status: 'ok',
    message: null,
  },
  realtimeSnapshot: {
    ticker: 'FPT',
    price: 124.8,
    change: 0.2,
    changePct: 0.16,
    referencePrice: 123,
    volume: 10_000,
    source: 'SSI',
    status: 'ok',
  },
  tradeTapeStatus: {
    source: 'SSI trade-tape contract',
    status: 'ok',
    message: null,
  },
  tradeTape: [
    {
      time: '10:16:00',
      timestamp: '2026-06-11T10:16:00+07:00',
      timestampDisplay: '10:16:00',
      price: 124800,
      volume: 1000,
      value: 124_800_000,
      side: 'sell',
      sideLabel: 'Sell',
      sideIfAvailable: 'SD',
      change: 1800,
      changePct: 1.46,
      rawType: 'X-TRADE',
      source: 'SSI',
    },
  ],
  orderBookSource: 'SSI X-QUOTE',
  orderBookStatus: {
    source: 'SSI X-QUOTE',
    status: 'ok',
    message: null,
  },
  orderBook: {
    ticker: 'FPT',
    symbol: 'FPT',
    source: 'SSI X-QUOTE',
    streamDataType: 'X-QUOTE',
    time: '09:41:23',
    ageSeconds: 2,
    bids: [
      { level: 1, price: 123000, volume: 19_400 },
      { level: 2, price: 122000, volume: 25_100 },
      { level: 4, price: 114400, volume: 84_800 },
    ],
    asks: [
      { level: 1, price: 124600, volume: 7_400 },
      { level: 2, price: 131600, volume: 50_500 },
      { level: 3, price: 132000, volume: 6_000 },
      { level: 4, price: 133000, volume: 1_000 },
    ],
  },
  diagnostics: {
    realtime: {},
    tradeTape: {},
    orderBook: {},
    foreignFlow: {
      capabilityStatus: 'ready',
      valueState: 'nonzero',
    },
    intraday: {
      capabilityStatus: 'ready',
      requestedTimeframe: '1h',
      actualGranularity: '1m',
      cadenceStatus: 'matched',
      changeBaseline: 'first_session_candle_open',
      changeBaselineValue: 123,
    },
  },
  dataQualitySummary: {
    overallStatus: 'ok',
    canonicalPriceSource: 'SSI DailyOhlc',
    issues: [],
    checks: {
      dailyOhlc: 'ok',
      dailyStockPrice: 'ok',
      finalCloseStatus: 'final',
      adjustedPriceStatus: 'unadjusted',
      intraday: 'ok',
      realtime: 'ok',
      tradeTape: 'ok',
      profile: 'ok',
      news: 'not_implemented',
    },
  },
  qualitySummary: {
    overallStatus: 'ready',
    groups: [
      { key: 'daily_data', label: 'Daily data', status: 'ready', detail: 'Latest completed 2026-06-17' },
      { key: 'live_market', label: 'Live market', status: 'ready', detail: 'Order book ready, Last price ready' },
      { key: 'company_metadata', label: 'Company metadata', status: 'ready', detail: 'Core profile ready' },
    ],
    issueCodes: [],
    primaryIssues: [],
  },
  sourceCoverage: [
    { group: 'Prices', block: 'Daily OHLCV', source: 'SSI DailyOhlc', status: 'ok' },
    { group: 'Prices', block: 'Daily stock price', source: 'SSI DailyStockPrice', status: 'ok' },
    { group: 'Live market', block: 'Intraday OHLCV', source: 'SSI IntradayOhlc', status: 'ok' },
    { group: 'Live market', block: 'Realtime snapshot', source: 'SSI realtime contract', status: 'ok' },
    { group: 'Live market', block: 'Order book', source: 'SSI X-QUOTE', status: 'ok' },
    { group: 'Live market', block: 'Trade tape', source: 'SSI trade-tape contract', status: 'ok' },
    { group: 'Company', block: 'Profile', source: 'SSI SecuritiesDetails', status: 'ok' },
    { group: 'Company', block: 'Optional metadata', source: 'SSI SecuritiesDetails', status: 'complete' },
    { group: 'News', block: 'News', source: 'NewsProvider future', status: 'not_implemented' },
  ],
  news: {
    items: [],
    status: 'not_implemented',
    source: null,
    message: 'News provider is not implemented yet.',
  },
  financials: {
    items: [],
    status: 'not_implemented',
    source: null,
  },
  events: {
    items: [],
    status: 'not_implemented',
    source: null,
  },
  warnings: [],
  errors: {},
});

const renderPage = () => render(
  <MemoryRouter initialEntries={['/vietnam/company/FPT']}>
    <Routes>
      <Route path="/vietnam/company/:ticker" element={<VietnamCompanyResearchPage />} />
    </Routes>
  </MemoryRouter>,
);

describe('VietnamCompanyResearchPage', () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(makeCompanySnapshot());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders ticker header, source coverage, and not implemented placeholders', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.getByText('FPT Corporation | HOSE')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Data summary' })).toBeInTheDocument();
    expect(screen.getByText('Daily data')).toBeInTheDocument();
    expect(screen.getAllByText('Live market').length).toBeGreaterThan(0);
    expect(screen.getByText('Company metadata')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Source coverage' })).toBeInTheDocument();
    expect(screen.getByText('Daily OHLCV')).toBeInTheDocument();
    expect(screen.getByText('Canonical latest price (VND)')).toBeInTheDocument();
    expect(screen.getByText('Reference price (VND)')).toBeInTheDocument();
    expect(screen.getByText(/Canonical price: SSI DailyOhlc\./)).toBeInTheDocument();
    expect(screen.getAllByText(/Latest completed 2026-06-17/).length).toBeGreaterThan(0);
    expect(screen.getByText('Daily OHLCV volume (shares)')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'DailyStockPrice enrichment' })).toBeInTheDocument();
    expect(screen.getByText('Matched volume (shares)')).toBeInTheDocument();
    expect(screen.getByText('Matched value (VND)')).toBeInTheDocument();
    expect(screen.getByText('Put-through volume (shares)')).toBeInTheDocument();
    expect(screen.getByText('Foreign net volume (shares)')).toBeInTheDocument();
    expect(screen.getByText('Foreign net value (VND)')).toBeInTheDocument();
    expect(screen.getByText('52W high (VND)')).toBeInTheDocument();
    expect(screen.getByText('140.00')).toBeInTheDocument();
    expect(screen.getByText('52W low (VND)')).toBeInTheDocument();
    expect(screen.getByText('90.00')).toBeInTheDocument();
    expect(screen.getByText('Avg volume 10D')).toBeInTheDocument();
    expect(screen.getByText('1.1M')).toBeInTheDocument();
    expect(screen.getByText('Avg volume 3M')).toBeInTheDocument();
    expect(screen.getByText('1.05M')).toBeInTheDocument();
    expect(screen.getAllByText('1.23M').length).toBeGreaterThan(0);
    expect(screen.getAllByText('123.5B').length).toBeGreaterThan(0);
    expect(screen.getByText('Price vs reference %')).toBeInTheDocument();
    expect(screen.getByText('+1.30%')).toBeInTheDocument();
    expect(screen.getByText('Daily range %')).toBeInTheDocument();
    expect(screen.getByText('1.77%')).toBeInTheDocument();
    expect(screen.getAllByText('SSI-derived').length).toBeGreaterThan(0);
    expect(screen.getByText('SSI realtime/session volume')).toBeInTheDocument();
    expect(screen.getByText('Latest trade tape volume')).toBeInTheDocument();
    expect(screen.getByText('Latest trade tape price')).toBeInTheDocument();
    expect(screen.getAllByText('SSI DailyStockPrice').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Intraday pulse' })).toBeInTheDocument();
    expect(screen.getAllByText('SSI IntradayOhlc').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SSI realtime contract').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SSI trade-tape contract').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SSI DailyOhlc').length).toBeGreaterThan(0);
    expect(screen.getByRole('columnheader', { name: 'Vol' })).toBeInTheDocument();
    expect(screen.queryByText('Value')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'SSI realtime' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'SSI trade tape' })).toBeInTheDocument();
    expect(screen.getByText('Trades loaded')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Time' })).toBeInTheDocument();
    expect(screen.getAllByText('10:16:00').length).toBeGreaterThan(0);
    expect(screen.queryByRole('heading', { name: 'News', level: 2 })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Financials' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Events' })).not.toBeInTheDocument();

    await waitFor(() => {
      expect(stocksApi.getVietnamCompanyResearch).toHaveBeenCalledWith('FPT', false);
    });
  });

  it('renders company SSI X-QUOTE order book with dynamic levels and board colors', async () => {
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(makeCompanySnapshot());

    renderPage();

    const section = (await screen.findByRole('heading', { name: 'Order Book — SSI X-QUOTE' })).closest('section');
    if (!section) throw new Error('SSI X-QUOTE order book section not found');
    const book = within(section);

    expect(book.getAllByText('SSI X-QUOTE').length).toBeGreaterThan(0);
    expect(book.getByRole('columnheader', { name: 'Bid Vol' })).toBeInTheDocument();
    expect(book.getByRole('columnheader', { name: 'Bid Price' })).toBeInTheDocument();
    expect(book.getByRole('columnheader', { name: 'Ask Price' })).toBeInTheDocument();
    expect(book.getByRole('columnheader', { name: 'Ask Vol' })).toBeInTheDocument();
    expect(book.getAllByRole('row')).toHaveLength(5);
    expect(book.getByText('19,400')).toBeInTheDocument();
    expect(book.getByText('7,400')).toBeInTheDocument();
    expect(book.getAllByText('123.00').some((node) => node.className.includes('text-reference-yellow'))).toBe(true);
    expect(book.getAllByText('114.40').some((node) => node.className.includes('text-cyan'))).toBe(true);
    expect(book.getAllByText('131.60').some((node) => node.className.includes('text-ceiling-purple'))).toBe(true);
    expect(book.getByText('124.60')).toHaveClass('text-success');
    expect(book.getByLabelText('Bid level 3 unavailable')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /foreign room/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /market index pulse/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /session status/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('company-latest-price')).toHaveTextContent('124.60');
  });

  it('renders company SSI X-QUOTE unavailable without fake rows', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.orderBook = null;
    snapshot.orderBookStatus = {
      source: 'SSI X-QUOTE',
      status: 'unavailable',
      message: 'Order book unavailable.',
      reasonCode: 'stream_cache_empty',
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const section = (await screen.findByRole('heading', { name: 'Order Book — SSI X-QUOTE' })).closest('section');
    if (!section) throw new Error('SSI X-QUOTE order book section not found');
    const book = within(section);

    expect(book.getByText('Order book unavailable.')).toBeInTheDocument();
    expect(book.queryByRole('columnheader', { name: 'Bid Vol' })).not.toBeInTheDocument();
    expect(book.queryByText('Bid Price')).not.toBeInTheDocument();
    expect(book.queryByText('Ask Price')).not.toBeInTheDocument();
  });

  it('keeps a ready order book usable when other live channels are unavailable', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.liveMarket = {
      status: 'partial',
      channels: {
        lastPrice: 'no_data',
        orderBook: 'ready',
        tradeTape: 'reconnecting',
        intraday: 'unavailable',
      },
      usableChannelCount: 1,
      sessionDate: '2026-06-18',
    };
    snapshot.qualitySummary = {
      overallStatus: 'partial',
      groups: [
        { key: 'daily_data', label: 'Daily data', status: 'ready', detail: 'Latest completed 2026-06-17' },
        { key: 'live_market', label: 'Live market', status: 'partial', detail: 'Order book ready, Trade tape reconnecting' },
        { key: 'company_metadata', label: 'Company metadata', status: 'ready', detail: 'Core profile ready' },
      ],
    };
    snapshot.realtimeSnapshot = null;
    snapshot.realtimeStatus = { status: 'unavailable', reasonCode: 'stream_cache_empty' };
    snapshot.tradeTape = [];
    snapshot.tradeTapeStatus = { status: 'unavailable', reasonCode: 'recovering' };
    snapshot.intraday = { status: 'unavailable', candles: [], pulse: null };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const summary = await screen.findByLabelText('Company Research Data Summary');
    expect(summary).toHaveTextContent('Order book ready, Trade tape reconnecting');
    expect(screen.getByRole('heading', { name: 'Order Book — SSI X-QUOTE' })).toBeInTheDocument();
    expect(screen.queryByText('SSI realtime unavailable. Daily SSI data is still available.')).not.toBeInTheDocument();
  });

  it('hides all unavailable reference and limit tiles without substituting daily close', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.price.referencePrice = null;
    snapshot.price.ceilingPrice = null;
    snapshot.price.floorPrice = null;
    snapshot.price.referencePriceSource = null;
    snapshot.price.ceilingPriceSource = null;
    snapshot.price.floorPriceSource = null;
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByTestId('company-latest-price')).toHaveTextContent('124.60');
    expect(screen.queryByText('Reference price (VND)')).not.toBeInTheDocument();
    expect(screen.queryByText('Ceiling price (VND)')).not.toBeInTheDocument();
    expect(screen.queryByText('Floor price (VND)')).not.toBeInTheDocument();
  });

  it('moves trade tape from loading to a bounded no-data state', async () => {
    vi.useFakeTimers();
    const snapshot = makeCompanySnapshot();
    snapshot.tradeTape = [];
    snapshot.tradeTapeStatus = {
      status: 'unavailable',
      reasonCode: 'stream_cache_empty',
      classification: 'stream_cache_empty',
    };
    snapshot.diagnostics = {
      ...snapshot.diagnostics,
      tradeTape: {
        streamingStatus: 'running',
        tradeTapeSubscriptionStatus: 'subscribed',
        tradeTapeBufferRowCount: 0,
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText('Loading SSI trade tape...')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_001);
    });
    expect(screen.getByText('No trade-tape rows arrived during the bounded startup wait.')).toBeInTheDocument();
    expect(screen.queryByText('Loading SSI trade tape...')).not.toBeInTheDocument();
  });

  it('refreshes the company live snapshot immediately when tab focus returns', async () => {
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(makeCompanySnapshot());

    renderPage();

    await waitFor(() => {
      expect(stocksApi.getVietnamCompanyResearch).toHaveBeenCalledWith('FPT', false);
    });
    const baselineCalls = vi.mocked(stocksApi.getVietnamCompanyResearch).mock.calls.length;

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    fireEvent(document, new Event('visibilitychange'));
    expect(stocksApi.getVietnamCompanyResearch).toHaveBeenCalledTimes(baselineCalls);

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    fireEvent(document, new Event('visibilitychange'));

    await waitFor(() => {
      expect(stocksApi.getVietnamCompanyResearch).toHaveBeenCalledTimes(baselineCalls + 1);
    });
    expect(stocksApi.getVietnamCompanyResearch).toHaveBeenLastCalledWith('FPT', false);
  });

  it('shows company trade rows when stale diagnostics accompany buffered X-TRADE data', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.tradeTapeStatus = {
      status: 'unavailable',
      source: 'SSI trade-tape contract',
      message: 'SSI trade tape unavailable.',
      reasonCode: 'stream_cache_stale',
      classification: 'stream_cache_stale',
    };
    snapshot.diagnostics = {
      ...snapshot.diagnostics,
      tradeTape: {
        streamingStatus: 'cache_stale',
        cacheStatus: 'stale',
        tradeTapeBufferRowCount: 50,
        tradeTapeReturnedRowCount: 1,
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const section = (await screen.findByRole('heading', { name: 'SSI trade tape' })).closest('section');
    if (!section) throw new Error('SSI trade tape section not found');
    const tradeTape = within(section);

    expect(tradeTape.getAllByText('10:16:00').length).toBeGreaterThan(0);
    expect(tradeTape.getByRole('columnheader', { name: 'Time' })).toBeInTheDocument();
    expect(tradeTape.getByRole('columnheader', { name: 'B/S' })).toBeInTheDocument();
    expect(tradeTape.getByRole('columnheader', { name: 'Vol' })).toBeInTheDocument();
    expect(tradeTape.getByRole('columnheader', { name: 'Price' })).toBeInTheDocument();
    expect(tradeTape.getByRole('columnheader', { name: '+/-' })).toBeInTheDocument();
    expect(tradeTape.getByRole('columnheader', { name: '+/-(%)' })).toBeInTheDocument();
    const side = tradeTape.getByText('Sell');
    expect(side).toHaveClass('text-danger');
    const price = tradeTape.getAllByText('124.80').find((node) => node.className.includes('text-success'));
    if (!price) throw new Error('Colored trade price cell not found');
    expect(price.className).toContain('text-success');
    expect(tradeTape.getAllByText('1,000').length).toBeGreaterThan(0);
    expect(tradeTape.getByText('+1.80')).toHaveClass('text-success');
    expect(tradeTape.getByText('+1.46')).toHaveClass('text-success');
    expect(tradeTape.getByText('ok')).toBeInTheDocument();
    expect(tradeTape.queryByText('SSI trade tape unavailable.')).not.toBeInTheDocument();
  });

  it('refetches pending company trade tape until rows arrive', async () => {
    const pending = makeCompanySnapshot();
    pending.tradeTape = [];
    pending.tradeTapeStatus = {
      status: 'unavailable',
      source: 'SSI trade-tape contract',
      message: 'No SSI trade rows available yet.',
      reasonCode: 'stream_cache_empty',
      classification: 'stream_cache_empty',
    };
    pending.diagnostics = {
      ...pending.diagnostics,
      tradeTape: {
        streamingStatus: 'running',
        managerState: 'running',
        tradeTapeSubscriptionStatus: 'subscribed',
        tradeTapeBufferRowCount: 0,
      },
    };
    const ready = makeCompanySnapshot();
    ready.tradeTapeStatus = {
      status: 'unavailable',
      source: 'SSI trade-tape contract',
      message: 'SSI trade tape ready.',
      reasonCode: 'buffered_rows_available',
      classification: 'buffered_rows_available',
    };
    ready.diagnostics = {
      ...ready.diagnostics,
      tradeTape: {
        streamingStatus: 'cache_stale',
        cacheStatus: 'stale',
        tradeTapeReturnedRowCount: 1,
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch)
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce(ready);
    renderPage();

    expect(await screen.findByText('Loading SSI trade tape...')).toBeInTheDocument();

    const section = screen.getByRole('heading', { name: 'SSI trade tape' }).closest('section');
    if (!section) throw new Error('SSI trade tape section not found');
    const tradeTape = within(section);
    await waitFor(() => expect(tradeTape.getByRole('columnheader', { name: 'Time' })).toBeInTheDocument(), { timeout: 6500 });
    expect(vi.mocked(stocksApi.getVietnamCompanyResearch).mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(tradeTape.getAllByText('10:16:00').length).toBeGreaterThan(0);
    expect(tradeTape.queryByText('Loading SSI trade tape...')).not.toBeInTheDocument();
    expect(tradeTape.queryByText('SSI trade tape unavailable.')).not.toBeInTheDocument();
  }, 10_000);

  it.each([
    { latestPrice: 124600, dailyClose: 124600, referencePrice: 123000, ceilingPrice: 131600, floorPrice: 114400, priceVsReferencePct: 1.3, expectedClass: 'text-success' },
    { latestPrice: 121000, dailyClose: 121000, referencePrice: 123000, ceilingPrice: 131600, floorPrice: 114400, priceVsReferencePct: -1.63, expectedClass: 'text-danger' },
    { latestPrice: 123000, dailyClose: 123000, referencePrice: 123000, ceilingPrice: 131600, floorPrice: 114400, priceVsReferencePct: 0, expectedClass: 'text-reference-yellow' },
    { latestPrice: 131600, dailyClose: 131600, referencePrice: 123000, ceilingPrice: 131600, floorPrice: 114400, priceVsReferencePct: 6.99, expectedClass: 'text-ceiling-purple' },
    { latestPrice: 114400, dailyClose: 114400, referencePrice: 123000, ceilingPrice: 131600, floorPrice: 114400, priceVsReferencePct: -6.99, expectedClass: 'text-cyan' },
    { latestPrice: null, dailyClose: null, referencePrice: 123000, ceilingPrice: 131600, floorPrice: 114400, priceVsReferencePct: null, expectedClass: 'text-secondary-text' },
    { latestPrice: 124600, dailyClose: 124600, referencePrice: null, ceilingPrice: 131600, floorPrice: 114400, priceVsReferencePct: null, expectedClass: 'text-secondary-text' },
  ])('colors company price metrics by SSI board convention %#', async ({
    latestPrice,
    dailyClose,
    referencePrice,
    ceilingPrice,
    floorPrice,
    priceVsReferencePct,
    expectedClass,
  }) => {
    const snapshot = makeCompanySnapshot();
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue({
      ...snapshot,
      price: {
        ...snapshot.price,
        latestPrice,
        dailyClose,
        referencePrice,
        ceilingPrice,
        floorPrice,
      },
      technical: {
        ...snapshot.technical,
        priceVsReferencePct,
      },
    });

    renderPage();

    expect(await screen.findByTestId('company-latest-price')).toHaveClass(expectedClass);
    expect(screen.getByTestId('company-daily-close')).toHaveClass(expectedClass);
    expect(screen.getByTestId('company-price-vs-reference')).toHaveClass(expectedClass);
    if (referencePrice === null) {
      expect(screen.queryByTestId('company-reference-price')).not.toBeInTheDocument();
    } else {
      expect(screen.getByTestId('company-reference-price')).toHaveClass('text-reference-yellow');
    }
    expect(screen.getByTestId('company-ceiling-price')).toHaveClass('text-ceiling-purple');
    expect(screen.getByTestId('company-floor-price')).toHaveClass('text-cyan');
  });

  it('colors company open high low close prices with the same SSI board convention', async () => {
    const snapshot = makeCompanySnapshot();
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue({
      ...snapshot,
      tradingStats: {
        ...snapshot.tradingStats,
        open: snapshot.price.referencePrice,
        high: snapshot.price.ceilingPrice,
        low: snapshot.price.floorPrice,
        close: 124600,
      },
    });

    renderPage();

    expect(await screen.findByTestId('company-open-price')).toHaveClass('text-reference-yellow');
    expect(screen.getByTestId('company-high-price')).toHaveClass('text-ceiling-purple');
    expect(screen.getByTestId('company-low-price')).toHaveClass('text-cyan');
    expect(screen.getByTestId('company-close-price')).toHaveClass('text-success');
  });

  it('renders unavailable SSI-derived company metrics without fake values', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.technical = {
      ...snapshot.technical,
      high52w: null,
      high52wDate: null,
      low52w: null,
      low52wDate: null,
      highLow52wHistoryCount: 9,
      highLow52wCoverageStatus: 'insufficient',
      avgVolume10d: null,
      avgVolume10dHistoryCount: 9,
      avgVolume10dCoverageStatus: 'insufficient',
      avgVolume3m: null,
      avgVolume3mHistoryCount: 9,
      avgVolume3mCoverageStatus: 'insufficient',
      priceVsReferencePct: null,
      priceVsReferenceStatus: 'reference_unavailable',
      dailyRangePct: null,
      dailyRangeStatus: 'insufficient',
      ssiDerivedMetricsStatus: 'insufficient',
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Technical snapshot' })).toBeInTheDocument();
    expect(screen.getByText('52W high (VND)')).toBeInTheDocument();
    expect(screen.getByText('Avg volume 10D')).toBeInTheDocument();
    expect(screen.getAllByText('\u2014').length).toBeGreaterThan(0);
    expect(screen.getAllByText('insufficient').length).toBeGreaterThan(0);
  });

  it('renders concise unavailable live sections without fake metric rows', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.intraday = {
      source: 'SSI IntradayOhlc',
      status: 'unavailable',
      message: 'SSI intraday unavailable for the latest daily date.',
      candles: [],
      pulse: null,
      diagnostics: {
        intradayLatestDate: '2026-06-12',
        dailyPriceDate: '2026-06-17',
        dateMatch: 'mismatched',
      },
    };
    snapshot.realtimeStatus = {
      source: 'SSI realtime contract',
      status: 'unavailable',
      message: 'SSI realtime unavailable.',
    };
    snapshot.realtimeSnapshot = null;
    snapshot.tradeTapeStatus = {
      source: 'SSI trade-tape contract',
      status: 'unavailable',
      message: 'SSI trade tape unavailable.',
    };
    snapshot.tradeTape = [];
    snapshot.diagnostics = {
      realtime: {
        attemptedEndpoints: ['RealtimeQuote'],
        httpStatus: 404,
        retryable: false,
      },
      tradeTape: {
        attemptedEndpoints: ['TradeTape'],
        httpStatus: 404,
        retryable: false,
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.getByText('SSI intraday unavailable.')).toBeInTheDocument();
    expect(screen.getByText('Last-price snapshot unavailable. Other live channels may still be usable.')).toBeInTheDocument();
    expect(screen.getByText('SSI trade tape unavailable.')).toBeInTheDocument();
    expect(screen.queryByText('Latest intraday close')).not.toBeInTheDocument();
    expect(screen.queryByText('Session volume from intraday')).not.toBeInTheDocument();
    expect(screen.queryByText('Realtime snapshot price')).not.toBeInTheDocument();
    expect(screen.queryByText('Trades loaded')).not.toBeInTheDocument();
    const liveSections = within(screen.getByRole('heading', { name: 'Intraday pulse' }).closest('section')?.parentElement as HTMLElement);
    expect(liveSections.queryByText(/RealtimeQuote|TradeTape|HTTP status|attempted endpoints/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Show diagnostics'));
    expect(screen.getByText('SSI realtime status - Attempted endpoints')).toBeInTheDocument();
    expect(screen.getByText('RealtimeQuote')).toBeInTheDocument();
    expect(screen.getByText('SSI trade tape status - Attempted endpoints')).toBeInTheDocument();
    expect(screen.getByText('TradeTape')).toBeInTheDocument();
  });

  it('renders reconnecting and closed stream lifecycle copy without raw errors', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.realtimeSnapshot = null;
    snapshot.tradeTape = [];
    snapshot.realtimeStatus = { source: 'SSI realtime contract', status: 'unavailable' };
    snapshot.tradeTapeStatus = { source: 'SSI trade-tape contract', status: 'unavailable' };
    snapshot.diagnostics = {
      ...snapshot.diagnostics,
      realtime: { stream_state: 'recovering', last_error_class: 'network_closed' },
      tradeTape: { stream_state: 'closed' },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByText('Reconnecting — showing last known data when available.')).toBeInTheDocument();
    expect(screen.getByText('Market closed — showing last known data.')).toBeInTheDocument();
    expect(screen.queryByText(/Connection to remote host was lost/i)).not.toBeInTheDocument();
  });

  it('keeps DailyOhlc versus DailyStockPrice detail out of the compact summary', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.dataQualitySummary = {
      overallStatus: 'partial',
      canonicalPriceSource: 'SSI DailyOhlc',
      issues: [
        {
          code: 'daily_ohlc_vs_daily_stock_price_mismatch',
          severity: 'warning',
          message: 'SSI DailyOhlc close differs from SSI DailyStockPrice close for the same trading date.',
          fields: {
            dailyOhlcClose: 70_700,
            dailyStockPriceClose: 70_800,
            date: '2026-06-22',
          },
        },
      ],
      checks: {
        dailyOhlc: 'ok',
        dailyStockPrice: 'ok',
        finalCloseStatus: 'unknown',
        adjustedPriceStatus: 'unknown',
        intraday: 'unavailable',
        realtime: 'unavailable',
        tradeTape: 'unavailable',
        profile: 'ok',
        news: 'not_implemented',
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const summary = await screen.findByLabelText('Company Research Data Summary');
    expect(within(summary).getByText('Daily data')).toBeInTheDocument();
    expect(summary).not.toHaveTextContent('DailyOhlc differs from DailyStockPrice for the same date.');
    expect(summary).not.toHaveTextContent('DailyOhlc 70,700');
    expect(screen.getByRole('heading', { name: 'Price summary' })).toBeInTheDocument();
  });

  it('renders DailyStockPrice date mismatch without replacing canonical daily fields', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.dailyStockPrice = {
      ...snapshot.dailyStockPrice,
      qualityStatus: 'partial',
      date: '2026-06-16',
      dateMatch: 'mismatched',
      stalenessReason: 'DailyStockPrice date differs from DailyOhlc.',
    };
    snapshot.foreignFlow.date = '2026-06-16';
    snapshot.foreignFlow.dateMatch = 'mismatched';
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByText('DailyStockPrice date differs from DailyOhlc.')).toBeInTheDocument();
    expect(screen.getByText('Canonical latest price (VND)')).toBeInTheDocument();
    expect(screen.getAllByText('SSI DailyOhlc').length).toBeGreaterThan(0);
  });

  it('keeps DailyStockPrice capability states independent when price limits are unavailable', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.dailyStockPrice = {
      ...snapshot.dailyStockPrice,
      qualityStatus: 'partial',
      referencePrice: null,
      ceilingPrice: null,
      floorPrice: null,
      capabilities: {
        priceLimitsStatus: 'unavailable',
        matchedStatsStatus: 'ready',
        putThroughStatus: 'ready',
        foreignFlowStatus: 'ready',
        sessionMetadataStatus: 'ready',
        overallStatus: 'partial',
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const section = (await screen.findByRole('heading', { name: 'DailyStockPrice enrichment' })).closest('section');
    if (!section) throw new Error('DailyStockPrice section not found');
    const capabilities = within(section).getByLabelText('DailyStockPrice capability states');
    expect(within(within(capabilities).getByText('Matched statistics').closest('div') as HTMLElement).getByText('ready')).toBeInTheDocument();
    expect(within(within(capabilities).getByText('Put-through statistics').closest('div') as HTMLElement).getByText('ready')).toBeInTheDocument();
    expect(within(within(capabilities).getByText('Price limits').closest('div') as HTMLElement).getByText('unavailable')).toBeInTheDocument();
    expect(within(within(capabilities).getByText('Foreign flow').closest('div') as HTMLElement).getByText('ready')).toBeInTheDocument();
    expect(within(within(capabilities).getByText('Session metadata').closest('div') as HTMLElement).getByText('ready')).toBeInTheDocument();
    expect(within(section).getByText('partial')).toBeInTheDocument();
    expect(within(section).getByText('2026-06-17')).toBeInTheDocument();
    expect(within(section).queryByText('Reference price (VND)')).not.toBeInTheDocument();
  });

  it('renders explicit provider foreign zero as zero with compact lineage', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.dailyStockPrice = {
      ...snapshot.dailyStockPrice,
      foreignBuyVolume: 0,
      foreignSellVolume: 0,
      foreignNetVolume: 0,
      foreignBuyValue: 0,
      foreignSellValue: 0,
      foreignNetValue: 0,
      foreignFlowValueState: 'explicit_zero',
    };
    snapshot.foreignFlow = {
      ...snapshot.foreignFlow,
      foreignBuyVolume: 0,
      foreignSellVolume: 0,
      foreignNetVolume: 0,
      foreignBuyValue: 0,
      foreignSellValue: 0,
      foreignNetValue: 0,
      capabilityStatus: 'ready',
      valueState: 'explicit_zero',
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const section = (await screen.findByRole('heading', { name: 'Foreign flow' })).closest('section');
    if (!section) throw new Error('Foreign flow section not found');
    const foreignFlow = within(section);
    expect(foreignFlow.getByText('Provider explicitly reported zero foreign totals; net values are derived only from complete gross pairs.')).toBeInTheDocument();
    expect(foreignFlow.getAllByText('0')).toHaveLength(6);
    expect(foreignFlow.getByText('ready')).toBeInTheDocument();
    expect(foreignFlow.queryByText('unavailable')).not.toBeInTheDocument();
  });

  it('renders missing foreign values as dashes and never as zero', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.dailyStockPrice = {
      status: 'ok',
      qualityStatus: 'partial',
      source: 'SSI DailyStockPrice',
      date: '2026-06-17',
      dateMatch: 'matched',
      referencePrice: 123,
      matchedVolume: null,
      matchedValue: null,
      putThroughVolume: null,
      putThroughValue: null,
      foreignNetVolume: null,
      foreignNetValue: null,
      foreignFlowValueState: 'unavailable',
      capabilities: {
        priceLimitsStatus: 'partial',
        matchedStatsStatus: 'unavailable',
        putThroughStatus: 'unavailable',
        foreignFlowStatus: 'unavailable',
        sessionMetadataStatus: 'ready',
        overallStatus: 'partial',
      },
    };
    snapshot.foreignFlow = {
      source: 'SSI DailyStockPrice',
      status: 'missing',
      date: '2026-06-17',
      dateMatch: 'matched',
      volumeUnit: 'shares',
      valueUnit: 'VND',
      foreignBuyVolume: null,
      foreignSellVolume: null,
      foreignNetVolume: null,
      foreignBuyValue: null,
      foreignSellValue: null,
      foreignNetValue: null,
      capabilityStatus: 'unavailable',
      valueState: 'unavailable',
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'DailyStockPrice enrichment' })).toBeInTheDocument();
    expect(screen.queryByText('Matched volume (shares)')).not.toBeInTheDocument();
    expect(screen.queryByText('Put-through value (VND)')).not.toBeInTheDocument();
    const section = screen.getByRole('heading', { name: 'Foreign flow' }).closest('section');
    if (!section) throw new Error('Foreign flow section not found');
    const foreignFlow = within(section);
    expect(foreignFlow.getByText('Provider foreign-flow fields were not supplied.')).toBeInTheDocument();
    expect(foreignFlow.getByText('Foreign net volume (shares)')).toBeInTheDocument();
    expect(foreignFlow.getAllByText('\u2014')).toHaveLength(6);
    expect(foreignFlow.queryByText('0')).not.toBeInTheDocument();
    expect(foreignFlow.getByText('unavailable')).toBeInTheDocument();
  });

  it('renders mixed foreign field coverage as partial', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.foreignFlow = {
      ...snapshot.foreignFlow,
      foreignBuyVolume: 100_000,
      foreignSellVolume: null,
      foreignNetVolume: null,
      foreignBuyValue: 1_000_000_000,
      foreignSellValue: null,
      foreignNetValue: null,
      capabilityStatus: 'partial',
      valueState: 'partial',
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const section = (await screen.findByRole('heading', { name: 'Foreign flow' })).closest('section');
    if (!section) throw new Error('Foreign flow section not found');
    const foreignFlow = within(section);
    expect(foreignFlow.getByText('Some provider foreign-flow fields are unavailable.')).toBeInTheDocument();
    expect(foreignFlow.getByText('partial')).toBeInTheDocument();
    expect(foreignFlow.getAllByText('\u2014')).toHaveLength(4);
    expect(foreignFlow.queryByText('0')).not.toBeInTheDocument();
  });

  it('renders irregular intraday cadence as partial with an explicit change baseline', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.intraday = {
      ...snapshot.intraday,
      status: 'ok',
      capabilityStatus: 'partial',
      cadenceStatus: 'irregular',
      requestedTimeframe: '1h',
      actualGranularity: 'irregular',
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const section = (await screen.findByRole('heading', { name: 'Intraday pulse' })).closest('section');
    if (!section) throw new Error('Intraday section not found');
    const intraday = within(section);
    expect(intraday.getByText('partial')).toBeInTheDocument();
    expect(intraday.queryByText('ok')).not.toBeInTheDocument();
    expect(intraday.getByText('Change vs first session candle open')).toBeInTheDocument();
    expect(intraday.getByText('Candles loaded')).toBeInTheDocument();
    expect(intraday.getByText('1')).toBeInTheDocument();
  });

  it('distinguishes a missing intraday baseline from a valid zero change', async () => {
    const missing = makeCompanySnapshot();
    missing.intraday = {
      ...missing.intraday,
      status: 'ok',
      pulse: {
        ...missing.intraday?.pulse,
        intradayChange: null,
        intradayChangePercent: null,
        intradayChangeBaseline: null,
        intradayChangeBaselineValue: null,
        latest1hChange: 1,
        latest1hChangePercent: 0.81,
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValueOnce(missing);
    const firstRender = renderPage();

    let section = (await screen.findByRole('heading', { name: 'Intraday pulse' })).closest('section');
    if (!section) throw new Error('Intraday section not found');
    let intraday = within(section);
    expect(within(intraday.getByText('Change (baseline unavailable)').closest('div') as HTMLElement).getByText('\u2014')).toBeInTheDocument();
    expect(within(intraday.getByText('Change % (baseline unavailable)').closest('div') as HTMLElement).getByText('\u2014')).toBeInTheDocument();

    firstRender.unmount();
    const zero = makeCompanySnapshot();
    zero.intraday = {
      ...zero.intraday,
      status: 'ok',
      pulse: {
        ...zero.intraday?.pulse,
        intradayChange: 0,
        intradayChangePercent: 0,
        intradayChangeBaseline: 'first_session_candle_open',
        intradayChangeBaselineValue: 123,
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValueOnce(zero);
    renderPage();

    section = (await screen.findByRole('heading', { name: 'Intraday pulse' })).closest('section');
    if (!section) throw new Error('Intraday section not found');
    intraday = within(section);
    expect(within(intraday.getByText('Change vs first session candle open').closest('div') as HTMLElement).getByText('0')).toBeInTheDocument();
    expect(within(intraday.getByText('Change % vs first session candle open').closest('div') as HTMLElement).getByText('0%')).toBeInTheDocument();
  });

  it('keeps technical coverage in the collapsed details disclosure', async () => {
    renderPage();

    const section = (await screen.findByRole('heading', { name: 'Technical snapshot' })).closest('section');
    if (!section) throw new Error('Technical snapshot section not found');
    const details = within(section).getByText('Technical details and coverage').closest('details');
    if (!details) throw new Error('Technical details disclosure not found');
    expect(within(details).getByText('52W coverage')).toBeInTheDocument();
    expect(within(details).getByText('3M volume coverage')).toBeInTheDocument();
    expect(within(details).getByText('Price vs reference %')).toBeInTheDocument();
    expect(within(section).getByText('MA20')).toBeInTheDocument();
    expect(within(section).getByText('MA50')).toBeInTheDocument();
    expect(within(section).getByText('RSI14')).toBeInTheDocument();
  });

  it('separates core profile readiness from optional metadata completeness', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.profile.name = null;
    snapshot.profile.coreProfileStatus = 'ready';
    snapshot.profile.optionalMetadataStatus = 'incomplete';
    snapshot.qualitySummary = {
      overallStatus: 'partial',
      groups: [
        { key: 'daily_data', label: 'Daily data', status: 'ready' },
        { key: 'live_market', label: 'Live market', status: 'ready' },
        { key: 'company_metadata', label: 'Company metadata', status: 'ready', detail: 'Core profile ready · Optional metadata incomplete' },
      ],
    };
    snapshot.dataQualitySummary = {
      overallStatus: 'partial',
      canonicalPriceSource: 'SSI DailyOhlc',
      issues: [
        {
          code: 'profile_partial',
          severity: 'info',
          message: 'Profile partial. Some metadata is unavailable.',
          fields: { missingFields: ['name', 'industry'] },
        },
      ],
      checks: {
        dailyOhlc: 'ok',
        dailyStockPrice: 'ok',
        finalCloseStatus: 'unknown',
        adjustedPriceStatus: 'unknown',
        intraday: 'ok',
        realtime: 'ok',
        tradeTape: 'ok',
        profile: 'partial',
        news: 'not_implemented',
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const summary = await screen.findByLabelText('Company Research Data Summary');
    expect(summary).toHaveTextContent('Core profile ready · Optional metadata incomplete');
    expect(screen.getByText('Optional metadata incomplete.')).toBeInTheDocument();
    expect(summary).not.toHaveTextContent('Profile partial');
  });

  it('keeps the company page useful with symbol, exchange, and market only', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.profile = {
      ticker: 'FPT',
      name: null,
      nameEn: null,
      exchange: 'HOSE',
      market: 'HOSE',
      industry: null,
      sector: null,
      securityType: null,
      issuer: null,
      lotSize: null,
      listedShares: null,
      listedDate: null,
      source: 'SSI SecuritiesDetails',
      status: 'ok',
      qualityStatus: 'partial',
      completeness: 0.25,
      missingFields: ['name', 'name_en', 'industry', 'sector', 'issuer'],
      fieldCoverage: { symbol: true, exchange: true, market: true, name: false },
      coreProfileStatus: 'ready',
      optionalMetadataStatus: 'incomplete',
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.queryByText('Company name unavailable')).not.toBeInTheDocument();
    expect(screen.getByText('Optional metadata incomplete.')).toBeInTheDocument();
    const profile = within(screen.getByRole('heading', { name: 'Company profile' }).closest('section') as HTMLElement);
    expect(profile.getByText('Ticker')).toBeInTheDocument();
    expect(profile.getByText('Exchange')).toBeInTheDocument();
    expect(profile.getAllByText('HOSE')).toHaveLength(2);
    expect(profile.queryByText('Company name')).not.toBeInTheDocument();
    expect(profile.queryByText('Industry')).not.toBeInTheDocument();
    expect(profile.queryByText('Sector')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Price summary' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'DailyStockPrice enrichment' })).toBeInTheDocument();
  });

  it('keeps daily sections visible when profile metadata is unavailable', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.profile = {
      ticker: 'FPT',
      name: null,
      source: 'SSI SecuritiesDetails',
      status: 'unavailable',
      qualityStatus: 'unavailable',
      completeness: 0,
      missingFields: ['name', 'industry', 'sector'],
      fieldCoverage: { name: false, industry: false, sector: false },
      diagnostics: { endpoint: 'SecuritiesDetails', failureClass: 'provider_unavailable' },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByText('Profile unavailable. Daily SSI data is still available.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Price summary' })).toBeInTheDocument();
    expect(screen.getByText('Canonical latest price (VND)')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Foreign flow' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'SSI realtime' })).toBeInTheDocument();
    expect(screen.queryByText('Company name unavailable')).not.toBeInTheDocument();
  });

  it('handles a missing data quality summary without blocking existing cards', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.dataQualitySummary = undefined;
    snapshot.qualitySummary = undefined;
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Company Research Data Summary')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Price summary' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Trading stats' })).toBeInTheDocument();
  });

  it('does not render endpoint diagnostics in the data quality summary', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.dataQualitySummary = {
      overallStatus: 'partial',
      canonicalPriceSource: 'SSI DailyOhlc',
      issues: [
        {
          code: 'provider_diagnostic_detail',
          severity: 'warning',
          message: 'SSI realtime unavailable; attempted endpoints: RealtimeQuote; HTTP status 404; raw provider error.',
          fields: {
            endpoint: 'RealtimeQuote',
            httpStatus: 404,
            rawProviderError: 'Not found',
          },
        },
      ],
      checks: {
        dailyOhlc: 'ok',
        dailyStockPrice: 'ok',
        realtime: 'HTTP status 404 from RealtimeQuote',
        tradeTape: 'unavailable',
      },
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const summary = await screen.findByLabelText('Company Research Data Summary');
    expect(summary).not.toHaveTextContent(/RealtimeQuote|HTTP status|raw provider|attempted endpoints/i);
  });

  it('renders at most three safe Community company-news headlines', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.news = {
      status: 'ok',
      source: 'Vnstock Community',
      message: 'Vnstock Community company news loaded for FPT.',
      items: [
        { title: 'Safe absolute', url: 'https://example.test/news', providerMode: 'community_free_ticker_news', rightsStatus: 'personal_research_only' },
        { title: 'Relative only', rawUrl: '/relative', url: null, providerMode: 'community_free_ticker_news', rightsStatus: 'personal_research_only' },
        { title: 'Unsafe URL', rawUrl: 'javascript:alert(1)', url: 'javascript:alert(1)', providerMode: 'community_free_ticker_news', rightsStatus: 'personal_research_only' },
        { title: 'Hidden fourth headline', url: null, providerMode: 'community_free_ticker_news', rightsStatus: 'personal_research_only' },
      ],
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    const safeLink = await screen.findByRole('link', { name: 'Safe absolute' });
    expect(safeLink).toHaveAttribute('href', 'https://example.test/news');
    expect(safeLink).toHaveAttribute('target', '_blank');
    expect(safeLink).toHaveAttribute('rel', expect.stringContaining('noopener'));
    expect(safeLink).toHaveAttribute('rel', expect.stringContaining('noreferrer'));
    expect(screen.queryByRole('link', { name: 'Relative only' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Unsafe URL' })).not.toBeInTheDocument();
    expect(screen.getAllByText('Personal research').length).toBeGreaterThan(0);
    expect(screen.queryByText('Hidden fourth headline')).not.toBeInTheDocument();
  });

  it('does not use recommendation wording in the data quality summary', async () => {
    renderPage();

    const summary = await screen.findByLabelText('Company Research Data Summary');
    expect(summary.textContent).not.toMatch(/\b(buy|sell|hold)\b|target[- ]price|recommendation/i);
  });
});
