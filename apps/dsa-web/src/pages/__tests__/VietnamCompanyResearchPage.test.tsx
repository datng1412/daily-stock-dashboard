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
  sourceCoverage: [
    { block: 'Daily OHLCV', source: 'SSI DailyOhlc', status: 'ok' },
    { block: 'Daily stock price', source: 'SSI DailyStockPrice', status: 'ok' },
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
    expect(screen.getByRole('heading', { name: 'News' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Financials' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Events' })).toBeInTheDocument();
    expect(screen.getAllByText('Not implemented yet').length).toBeGreaterThanOrEqual(3);

    await waitFor(() => {
      expect(stocksApi.getVietnamCompanyResearch).toHaveBeenCalledWith('FPT', false);
    });
  });
});
