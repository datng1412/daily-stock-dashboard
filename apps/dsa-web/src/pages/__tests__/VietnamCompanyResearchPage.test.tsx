import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
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
  },
  price: {
    latestPrice: 124.6,
    dailyClose: 124.6,
    referencePrice: 123,
    ceilingPrice: 131.6,
    floorPrice: 114.4,
    priceDate: '2026-06-17',
    source: 'SSI DailyOhlc',
    canonicalSource: 'SSI DailyOhlc',
    referenceSource: 'SSI DailyStockPrice',
    status: 'ok',
  },
  tradingStats: {
    open: 123.4,
    high: 125,
    low: 122.8,
    close: 124.6,
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
    referencePrice: 123,
    ceilingPrice: 131.6,
    floorPrice: 114.4,
    adjustedClose: 124.6,
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
  },
  technical: {
    ma20: 120,
    ma50: 118,
    rsi14: 55.5,
    bollingerUpper: 130,
    bollingerMiddle: 120,
    bollingerLower: 110,
    source: 'derived from SSI DailyOhlc',
    status: 'ok',
  },
  intraday: {
    source: 'SSI IntradayOhlc',
    status: 'ok',
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
      price: 124.8,
      volume: 1000,
      value: 124_800_000,
      source: 'SSI',
    },
  ],
  diagnostics: {
    realtime: {},
    tradeTape: {},
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
  sourceCoverage: [
    { block: 'Daily OHLCV', source: 'SSI DailyOhlc', status: 'ok' },
    { block: 'Daily stock price', source: 'SSI DailyStockPrice', status: 'ok' },
    { block: 'Intraday OHLCV', source: 'SSI IntradayOhlc', status: 'ok' },
    { block: 'Realtime snapshot', source: 'SSI realtime contract', status: 'ok' },
    { block: 'Trade tape', source: 'SSI trade-tape contract', status: 'ok' },
    { block: 'Profile', source: 'SSI SecuritiesDetails', status: 'ok' },
    { block: 'News', source: 'NewsProvider future', status: 'not_implemented' },
    { block: 'Financials', source: 'external provider future', status: 'not_implemented' },
    { block: 'Corporate actions', source: 'external provider future', status: 'not_implemented' },
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
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(makeCompanySnapshot());
  });

  it('renders ticker header, source coverage, and not implemented placeholders', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.getByText('FPT Corporation | HOSE')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Data Quality Summary' })).toBeInTheDocument();
    expect(screen.getByText('Data quality: ok')).toBeInTheDocument();
    expect(screen.getByText('Canonical price source: SSI DailyOhlc')).toBeInTheDocument();
    expect(screen.getByText('No data quality issues detected.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Source coverage' })).toBeInTheDocument();
    expect(screen.getByText('Daily OHLCV')).toBeInTheDocument();
    expect(screen.getByText('Canonical latest price (VND)')).toBeInTheDocument();
    expect(screen.getByText('Reference price (VND)')).toBeInTheDocument();
    expect(screen.getByText('Canonical price: SSI DailyOhlc. Reference and limit fields: SSI DailyStockPrice.')).toBeInTheDocument();
    expect(screen.getByText('Daily OHLCV volume (shares)')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'DailyStockPrice enrichment' })).toBeInTheDocument();
    expect(screen.getByText('Matched volume (shares)')).toBeInTheDocument();
    expect(screen.getByText('Matched value (VND)')).toBeInTheDocument();
    expect(screen.getByText('Put-through volume (shares)')).toBeInTheDocument();
    expect(screen.getByText('Foreign net volume (shares)')).toBeInTheDocument();
    expect(screen.getByText('Foreign net value (VND)')).toBeInTheDocument();
    expect(screen.getByText('SSI realtime/session volume')).toBeInTheDocument();
    expect(screen.getByText('Latest trade tape volume')).toBeInTheDocument();
    expect(screen.getByText('Latest trade tape price')).toBeInTheDocument();
    expect(screen.getAllByText('SSI DailyStockPrice').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Intraday pulse' })).toBeInTheDocument();
    expect(screen.getAllByText('SSI IntradayOhlc').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SSI realtime contract').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SSI trade-tape contract').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SSI DailyOhlc').length).toBeGreaterThan(0);
    expect(screen.queryByText('Volume')).not.toBeInTheDocument();
    expect(screen.queryByText('Value')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'SSI realtime' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'SSI trade tape' })).toBeInTheDocument();
    expect(screen.getByText('Trades loaded')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'News' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Financials' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Events' })).toBeInTheDocument();
    expect(screen.getAllByText('Not implemented yet').length).toBeGreaterThanOrEqual(3);

    await waitFor(() => {
      expect(stocksApi.getVietnamCompanyResearch).toHaveBeenCalledWith('FPT', false);
    });
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
    expect(screen.getByText('SSI realtime unavailable. Daily SSI data is still available.')).toBeInTheDocument();
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

  it('renders DailyOhlc versus DailyStockPrice mismatch in the data quality summary', async () => {
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

    const summary = await screen.findByLabelText('Data Quality Summary');
    expect(summary).toHaveTextContent('Data quality: partial');
    expect(summary).toHaveTextContent('DailyOhlc differs from DailyStockPrice for the same date.');
    expect(summary).toHaveTextContent('DailyOhlc 70,700');
    expect(summary).toHaveTextContent('DailyStockPrice 70,800');
    expect(summary).toHaveTextContent('Realtime: unavailable');
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

  it('hides null optional DailyStockPrice metrics instead of rendering zero', async () => {
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
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'DailyStockPrice enrichment' })).toBeInTheDocument();
    expect(screen.queryByText('Matched volume (shares)')).not.toBeInTheDocument();
    expect(screen.queryByText('Put-through value (VND)')).not.toBeInTheDocument();
    expect(screen.queryByText('Foreign net volume (shares)')).not.toBeInTheDocument();
    expect(screen.getByText('SSI DailyStockPrice foreign flow unavailable.')).toBeInTheDocument();
  });

  it('renders profile partial in the data quality summary', async () => {
    const snapshot = makeCompanySnapshot();
    snapshot.profile.name = null;
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

    const summary = await screen.findByLabelText('Data Quality Summary');
    expect(summary).toHaveTextContent('Profile partial. Some metadata is unavailable.');
    expect(summary).toHaveTextContent('Profile: partial');
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
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.queryByText('Company name unavailable')).not.toBeInTheDocument();
    expect(screen.getByText('Profile partial. Some metadata is unavailable.')).toBeInTheDocument();
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
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Data Quality Summary')).not.toBeInTheDocument();
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

    const summary = await screen.findByLabelText('Data Quality Summary');
    expect(summary).toHaveTextContent('Data quality issue detected.');
    expect(summary).not.toHaveTextContent(/RealtimeQuote|HTTP status|raw provider|attempted endpoints/i);
  });

  it('does not use recommendation wording in the data quality summary', async () => {
    renderPage();

    const summary = await screen.findByLabelText('Data Quality Summary');
    expect(summary.textContent).not.toMatch(/\b(buy|sell|hold)\b|target[- ]price|recommendation/i);
  });
});
