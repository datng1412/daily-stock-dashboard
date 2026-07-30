import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  stocksApi,
  type VietnamForeignFlowWatchlistItem,
  type VietnamForeignFlowWatchlistResponse,
} from '../../../api/stocks';
import { FOREIGN_FLOW_WATCHLIST_STORAGE_KEY } from '../foreignFlowWatchlistModel';
import { ForeignFlowWatchlistScreener } from '../ForeignFlowWatchlistScreener';

vi.mock('../../../api/stocks', () => ({
  stocksApi: {
    getVietnamForeignFlowWatchlist: vi.fn(),
    getVietnamCurrentForeignFlowAggregate: vi.fn(),
    getVietnamIndexComponents: vi.fn(),
  },
}));

const watchlist = vi.mocked(stocksApi.getVietnamForeignFlowWatchlist);
const currentAggregate = vi.mocked(stocksApi.getVietnamCurrentForeignFlowAggregate);
const indexComponents = vi.mocked(stocksApi.getVietnamIndexComponents);

const makeItem = (
  ticker: string,
  net20: number | null,
  overrides: Partial<VietnamForeignFlowWatchlistItem> = {},
): VietnamForeignFlowWatchlistItem => ({
  ticker,
  availability: 'ready',
  dataState: 'ready',
  latestSession: '2026-07-21',
  sourceFreshness: 'latest_completed',
  sourceSessionLag: 0,
  fetchedAt: '2026-07-21T09:00:00Z',
  cacheState: 'hit',
  cacheAgeSeconds: 5,
  actualSessionCount: 60,
  requestedSessionCount: 60,
  complete: true,
  buyValue1d: 30,
  sellValue1d: 20,
  netValue1d: net20 === null ? null : net20 / 20,
  buyValue5d: 150,
  sellValue5d: 100,
  netValue5d: net20 === null ? null : net20 / 4,
  buyValue20d: net20 === null ? null : 600,
  sellValue20d: net20 === null ? null : 400,
  netValue20d: net20,
  buyValue60d: 1_800,
  sellValue60d: 1_200,
  netValue60d: net20 === null ? null : net20 * 3,
  buyVolume1d: 3,
  sellVolume1d: 2,
  netVolume1d: net20 === null ? null : net20 / 200,
  buyVolume5d: 15,
  sellVolume5d: 10,
  netVolume5d: net20 === null ? null : net20 / 40,
  buyVolume20d: 60,
  sellVolume20d: 40,
  netVolume20d: net20 === null ? null : net20 / 10,
  buyVolume60d: 180,
  sellVolume60d: 120,
  netVolume60d: net20 === null ? null : net20 * 0.3,
  buyStreak: net20 !== null && net20 > 0 ? 2 : 0,
  sellStreak: net20 !== null && net20 < 0 ? 3 : 0,
  streakMetricBasis: 'foreign_net_value',
  containsProviderAnomaly: false,
  anomalySessions: [],
  anomalyCount: 0,
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  ...overrides,
});

const itemFor = (ticker: string) => {
  if (ticker === 'SSI') return makeItem('SSI', -200, {
    availability: 'partial',
    dataState: 'partial',
    latestSession: '2026-07-18',
    sourceFreshness: 'stale',
    sourceSessionLag: 1,
    complete: false,
    actualSessionCount: 20,
    containsProviderAnomaly: true,
    anomalySessions: ['2026-07-17'],
    anomalyCount: 1,
  });
  if (ticker === 'HPG') return makeItem('HPG', null, {
    availability: 'unavailable',
    dataState: 'unavailable',
    latestSession: null,
    sourceFreshness: 'unknown',
    sourceSessionLag: null,
    complete: false,
    actualSessionCount: 0,
    failureClass: 'provider_unavailable',
  });
  return makeItem(ticker, ticker === 'ZERO' ? 0 : 300);
};

const responseFor = (tickers: string[]): VietnamForeignFlowWatchlistResponse => {
  const items = tickers.map(itemFor);
  const ready = items.filter((item) => item.availability === 'ready').length;
  const partial = items.filter((item) => item.availability === 'partial').length;
  const unavailable = items.filter((item) => item.availability === 'unavailable').length;
  return {
    status: unavailable === items.length ? 'unavailable' : ready === items.length ? 'ready' : 'partial',
    dataState: unavailable === items.length ? 'unavailable' : ready === items.length ? 'ready' : 'partial',
    usable: ready + partial > 0,
    requestedTickers: tickers,
    normalizedTickers: tickers,
    duplicateTickersRemoved: 0,
    expectedSymbolCount: tickers.length,
    readySymbolCount: ready,
    partialSymbolCount: partial,
    unavailableSymbolCount: unavailable,
    requestedSessionCount: 60,
    fetchedAt: '2026-07-21T09:00:00Z',
    provider: 'ssi_fastconnect',
    providerVersion: 'v3',
    cacheState: 'hit',
    cacheAgeSeconds: 5,
    items,
  };
};

const renderScreener = (url = '/vietnam/foreign-flow?mode=watchlist') => {
  window.history.pushState({}, '', url);
  return render(<BrowserRouter><ForeignFlowWatchlistScreener /></BrowserRouter>);
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  watchlist.mockImplementation(async (tickers) => responseFor(tickers));
  currentAggregate.mockResolvedValue({
    status: 'unavailable',
    dataState: 'waiting',
    usable: false,
    scope: 'current_foreign_flow_aggregate',
    universe: 'watchlist',
    isProvisional: false,
    source: 'SSI FastConnect V3 ForeignRoomMessage',
    providerVersion: 'v3',
    endpoint: 'room.{symbol}',
    updateSemantics: 'cumulative_replacement_snapshot',
    aggregate: null,
    displaySeries: [],
    displayWindows: {},
    rankings: {},
    items: [],
    groups: [],
    coverage: {
      requestedSymbolCount: 0,
      classifiedSymbolCount: 0,
      subscribedSymbolCount: 0,
      observedSymbolCount: 0,
      completeVolumeCount: 0,
      completeValueCount: 0,
      missingSymbols: [],
      staleSymbolCount: 0,
    },
  });
  indexComponents.mockResolvedValue({
    status: 'ok',
    source: 'ssi_fastconnect',
    indexCode: 'VN30',
    market: 'HOSE',
    rows: [{ symbol: 'FPT' }, { symbol: 'SSI' }],
    count: 2,
  });
});

describe('ForeignFlowWatchlistScreener', () => {
  it('starts empty and never loads a fixed symbol set', () => {
    renderScreener();
    expect(screen.getByRole('heading', { name: 'Create a foreign-flow watchlist' })).toBeInTheDocument();
    expect(watchlist).not.toHaveBeenCalled();
    expect(indexComponents).not.toHaveBeenCalled();
  });

  it('uses explicit URL tickers before a saved local watchlist', async () => {
    localStorage.setItem(FOREIGN_FLOW_WATCHLIST_STORAGE_KEY, JSON.stringify({
      tickers: ['FPT'],
      metric: 'value',
      window: 20,
    }));
    renderScreener('/vietnam/foreign-flow?mode=watchlist&tickers=SSI');
    await waitFor(() => expect(watchlist).toHaveBeenCalledWith(
      ['SSI'],
      expect.objectContaining({ sessions: 60, forceRefresh: false }),
    ));
    expect(screen.getByRole('link', { name: 'SSI' })).toBeInTheDocument();
  });

  it('adds pasted separators, deduplicates, removes, and clears explicitly', async () => {
    renderScreener();
    fireEvent.change(screen.getByLabelText('Add tickers'), { target: { value: 'fpt, SSI\nHPG FPT' } });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/ }));
    await waitFor(() => expect(watchlist).toHaveBeenCalledWith(
      ['FPT', 'SSI', 'HPG'],
      expect.objectContaining({ sessions: 60 }),
    ));
    expect(screen.getByText(/duplicate ticker ignored/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Remove SSI' }));
    await waitFor(() => expect(watchlist).toHaveBeenLastCalledWith(
      ['FPT', 'HPG'],
      expect.any(Object),
    ));
    fireEvent.click(screen.getByRole('button', { name: 'Clear watchlist' }));
    expect(screen.getByRole('heading', { name: 'Create a foreign-flow watchlist' })).toBeInTheDocument();
  });

  it('reports malformed input without issuing a request', () => {
    renderScreener();
    fireEvent.change(screen.getByLabelText('Add tickers'), { target: { value: 'bad*' } });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/ }));
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid ticker');
    expect(watchlist).not.toHaveBeenCalled();
  });

  it('switches metric/window and filters locally without refetching', async () => {
    renderScreener('/vietnam/foreign-flow?mode=watchlist&tickers=FPT,SSI,HPG');
    await waitFor(() => expect(watchlist).toHaveBeenCalledTimes(1));
    fireEvent.click(within(screen.getByRole('group', { name: 'Watchlist metric' })).getByRole('button', { name: 'Volume' }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Watchlist window' })).getByRole('button', { name: '5D' }));
    fireEvent.change(screen.getByLabelText('Filter'), { target: { value: 'net_sellers' } });
    fireEvent.change(screen.getByLabelText('Sort'), { target: { value: 'net_5d' } });
    expect(watchlist).toHaveBeenCalledTimes(1);
    const table = screen.getByRole('region', { name: 'Watchlist foreign flow table' });
    expect(within(table).getByText('SSI')).toBeInTheDocument();
    expect(within(table).queryByText('FPT')).not.toBeInTheDocument();
  });

  it('keeps partial/unavailable rows, distinguishes zero/null, and labels mixed sessions', async () => {
    renderScreener('/vietnam/foreign-flow?mode=watchlist&tickers=ZERO,SSI,HPG');
    await waitFor(() => expect(screen.getByRole('region', { name: 'Watchlist foreign flow table' })).toBeInTheDocument());
    expect(screen.getByText('mixed source sessions')).toBeInTheDocument();
    const table = screen.getByRole('region', { name: 'Watchlist foreign flow table' });
    expect(within(table).getAllByText('0').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('—').length).toBeGreaterThan(0);
    expect(within(table).getByText('partial')).toBeInTheDocument();
    expect(within(table).getByText('unavailable')).toBeInTheDocument();
  });

  it('deep-links a ticker with metric and window state', async () => {
    renderScreener('/vietnam/foreign-flow?mode=watchlist&tickers=FPT&metric=volume&window=60');
    const link = await screen.findByRole('link', { name: 'FPT' });
    expect(link).toHaveAttribute('href', '/vietnam/foreign-flow?mode=ticker&ticker=FPT&metric=volume&window=60');
  });

  it('preserves usable rows when an explicit refresh fails', async () => {
    renderScreener('/vietnam/foreign-flow?mode=watchlist&tickers=FPT');
    await screen.findByRole('link', { name: 'FPT' });
    watchlist.mockRejectedValueOnce(new Error('temporary failure'));
    fireEvent.click(screen.getByRole('button', { name: /Force Refresh/ }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('temporary failure'));
    expect(screen.getByRole('link', { name: 'FPT' })).toBeInTheDocument();
    expect(watchlist).toHaveBeenCalledTimes(2);
  });

  it('loads SSI-derived VN30 membership only after the explicit preset action', async () => {
    renderScreener();
    expect(indexComponents).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Use SSI VN30' }));
    await waitFor(() => expect(indexComponents).toHaveBeenCalledWith('VN30', 'HOSE'));
    await waitFor(() => expect(watchlist).toHaveBeenCalledWith(['FPT', 'SSI'], expect.any(Object)));
  });

  it('stores no provider response in localStorage', async () => {
    renderScreener('/vietnam/foreign-flow?mode=watchlist&tickers=FPT');
    await screen.findByRole('link', { name: 'FPT' });
    const stored = localStorage.getItem(FOREIGN_FLOW_WATCHLIST_STORAGE_KEY) ?? '';
    expect(stored).toContain('FPT');
    expect(stored).not.toContain('items');
    expect(stored).not.toContain('providerVersion');
  });
});
