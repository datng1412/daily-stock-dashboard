import { render, screen, waitFor } from '@testing-library/react';
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
    exchange: 'HOSE',
    industry: null,
    source: 'SSI',
    status: 'ok',
  },
  price: {
    latestPrice: 124.6,
    dailyClose: 124.6,
    referencePrice: 123,
    ceilingPrice: 131.6,
    floorPrice: 114.4,
    priceDate: '2026-06-17',
    source: 'SSI DailyStockPrice',
    status: 'ok',
  },
  tradingStats: {
    open: 123.4,
    high: 125,
    low: 122.8,
    close: 124.6,
    volume: 1_234_567,
    value: 123_456_789_000,
    source: 'SSI DailyStockPrice',
    status: 'ok',
  },
  foreignFlow: {
    foreignBuyVolume: 100_000,
    foreignSellVolume: 80_000,
    foreignNetVolume: 20_000,
    foreignBuyValue: 1_000_000_000,
    foreignSellValue: 800_000_000,
    foreignNetValue: 200_000_000,
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
    source: 'derived_from_ssi_ohlcv',
    status: 'ok',
  },
  intraday: {
    source: 'SSI',
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
  realtime: {
    source: 'SSI',
    status: 'ok',
    message: null,
    snapshot: {
      ticker: 'FPT',
      price: 124.8,
      change: 0.2,
      changePct: 0.16,
      referencePrice: 123,
      volume: 10_000,
      source: 'SSI',
      status: 'ok',
    },
  },
  tradeTape: {
    source: 'SSI',
    status: 'ok',
    message: null,
    trades: [
      {
        time: '10:16:00',
        price: 124.8,
        volume: 1000,
        value: 124_800_000,
        source: 'SSI',
      },
    ],
  },
  sourceCoverage: [
    { block: 'Daily OHLCV', source: 'SSI DailyOhlc', status: 'ok' },
    { block: 'Daily stock price', source: 'SSI DailyStockPrice', status: 'ok' },
    { block: 'Intraday OHLCV', source: 'SSI IntradayOhlc', status: 'ok' },
    { block: 'Realtime snapshot', source: 'SSI', status: 'ok' },
    { block: 'Trade tape', source: 'SSI', status: 'ok' },
    { block: 'Profile', source: 'SSI SecuritiesDetails', status: 'ok' },
    { block: 'News', source: 'NewsProvider', status: 'not_implemented' },
    { block: 'Financials', source: 'TBD', status: 'not_implemented' },
    { block: 'Corporate actions', source: 'TBD', status: 'not_implemented' },
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
    expect(screen.getByRole('heading', { name: 'Source coverage' })).toBeInTheDocument();
    expect(screen.getByText('Daily OHLCV')).toBeInTheDocument();
    expect(screen.getAllByText('SSI DailyStockPrice').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Intraday pulse' })).toBeInTheDocument();
    expect(screen.getByText('SSI IntradayOhlc')).toBeInTheDocument();
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
      source: 'SSI',
      status: 'unavailable',
      message: 'SSI IntradayOhlc latest candle date does not match latest daily trading date.',
      candles: [],
      pulse: undefined,
    };
    snapshot.realtime = {
      source: 'SSI',
      status: 'unavailable',
      message: 'SSI FastConnect realtime snapshot unavailable (attempted endpoints: RealtimeQuote).',
      snapshot: null,
    };
    snapshot.tradeTape = {
      source: 'SSI',
      status: 'unavailable',
      message: 'SSI FastConnect trade tape unavailable (attempted endpoints: TradeTape).',
      trades: [],
    };
    vi.mocked(stocksApi.getVietnamCompanyResearch).mockResolvedValue(snapshot);

    renderPage();

    expect(await screen.findByRole('heading', { name: 'FPT' })).toBeInTheDocument();
    expect(screen.getByText('SSI intraday unavailable.')).toBeInTheDocument();
    expect(screen.getByText('SSI realtime unavailable. Daily SSI data is still available.')).toBeInTheDocument();
    expect(screen.getByText('SSI trade tape unavailable.')).toBeInTheDocument();
    expect(screen.queryByText('Latest intraday close')).not.toBeInTheDocument();
    expect(screen.queryByText('Session volume from intraday')).not.toBeInTheDocument();
    expect(screen.queryByText('Snapshot price')).not.toBeInTheDocument();
    expect(screen.queryByText('Trades loaded')).not.toBeInTheDocument();
    expect(screen.queryByText(/attempted endpoints/i)).not.toBeInTheDocument();
  });
});
