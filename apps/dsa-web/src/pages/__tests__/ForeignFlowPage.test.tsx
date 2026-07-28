import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  stocksApi,
  type VietnamForeignFlowSymbolHistoryResponse,
  type VietnamVn30ForeignFlowResponse,
} from '../../api/stocks';
import ForeignFlowPage from '../ForeignFlowPage';

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getVietnamForeignFlowSymbolHistory: vi.fn(),
    getVietnamVn30ForeignFlow: vi.fn(),
    getVietnamIndustryFlow: vi.fn(),
    getVietnamProprietaryFlow: vi.fn(),
    getVietnamForeignFlowWatchlist: vi.fn(),
    getVietnamIndexComponents: vi.fn(),
  },
}));

const symbolHistory = vi.mocked(stocksApi.getVietnamForeignFlowSymbolHistory);
const vn30 = vi.mocked(stocksApi.getVietnamVn30ForeignFlow);
const industry = vi.mocked(stocksApi.getVietnamIndustryFlow);
const proprietary = vi.mocked(stocksApi.getVietnamProprietaryFlow);
const watchlist = vi.mocked(stocksApi.getVietnamForeignFlowWatchlist);

const tickerPayload = (): VietnamForeignFlowSymbolHistoryResponse => ({
  ticker: 'FPT',
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: 'shares',
  valueUnit: 'VND',
  finality: 'daily_available',
  dataState: 'ready',
  freshness: 'fresh',
  rows: [
    { tradingDate: '2026-07-20', foreignBuyValue: 0, foreignSellValue: null, foreignNetValue: null, foreignBuyVolume: 0, foreignSellVolume: null, foreignNetVolume: null },
    { tradingDate: '2026-07-21', foreignBuyValue: 200, foreignSellValue: 50, foreignNetValue: 150, foreignBuyVolume: 20, foreignSellVolume: 5, foreignNetVolume: 15 },
  ],
  windows: {} as VietnamForeignFlowSymbolHistoryResponse['windows'],
  analytics: null,
  latestRow: null,
  requested: { mode: 'recent_sessions', requestedLimit: 20, returnedSessionCount: 2 },
  coverage: { requestedSessions: 20, coveredSessions: 2, complete: false },
  fetchedAt: '2026-07-21T09:00:00Z',
});

const vn30Payload = (): VietnamVn30ForeignFlowResponse => ({
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  dataState: 'partial',
  membership: { memberCount: 2, source: 'SSI IndexComponents' },
  components: [
    {
      ticker: 'FPT',
      foreignNetValue: 150,
      foreignNetValue5d: 300,
      foreignNetValue20d: 500,
      foreignNetVolume: 15,
      foreignNetVolume5d: 30,
      foreignNetVolume20d: 50,
    },
    {
      ticker: 'HPG',
      foreignNetValue: -50,
      foreignNetValue5d: -80,
      foreignNetValue20d: -100,
      foreignNetVolume: -5,
      foreignNetVolume5d: -8,
      foreignNetVolume20d: -10,
    },
  ],
  decomposition: {
    status: 'partial',
    dataState: 'partial',
    usable: true,
    latestCompletedSession: '2026-07-21',
    anomalySessions: [],
    anomalyCount: 0,
    windows: {
      '5': { foreignNetValue: 220, foreignNetVolume: 22 },
      '20': { foreignNetValue: 400, foreignNetVolume: 40 },
    },
    series: [
      {
        tradingDate: '2026-07-21',
        foreignBuyValue: 1_000,
        foreignSellValue: 600,
        foreignNetValue: 400,
        valueBreadth: { netBuyCount: 1, netSellCount: 1, zeroCount: 0, unavailableCount: 0 },
        valueCoverageRatio: 1,
        dataState: 'ready',
        state: 'ready',
      },
    ],
    latest: {
      tradingDate: '2026-07-21',
      foreignBuyValue: 1_000,
      foreignSellValue: 600,
      foreignNetValue: 400,
      foreignBuyVolume: 100,
      foreignSellVolume: 60,
      foreignNetVolume: 40,
      valueBreadth: { netBuyCount: 1, netSellCount: 1, zeroCount: 0, unavailableCount: 0 },
      volumeBreadth: { netBuyCount: 1, netSellCount: 1, zeroCount: 0, unavailableCount: 0 },
      valueCoverageRatio: 1,
      dataState: 'ready',
      state: 'ready',
    },
  },
  canonical: { capabilityStatus: 'unsupported', diagnostics: {}, windows: { '5': {}, '20': {} }, series: [] },
  cache: { status: 'hit', ageSeconds: 12 },
  fetchedAt: '2026-07-21T09:00:00Z',
} as unknown as VietnamVn30ForeignFlowResponse);

const renderPage = (url = '/foreign-flow') => {
  window.history.pushState({}, '', url);
  return render(<BrowserRouter><ForeignFlowPage /></BrowserRouter>);
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  symbolHistory.mockResolvedValue(tickerPayload());
  vn30.mockResolvedValue(vn30Payload());
  industry.mockResolvedValue({
    status: 'partial',
    source: 'ssi_fastconnect',
    providerVersion: 'v3',
    universe: 'index:VN30',
    endpoint: 'securitiesSummary',
    fetchedAt: '2026-07-21T09:00:00Z',
    cache: { status: 'miss', ageSeconds: null },
    currentSessionStatus: 'CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS',
    rows: [
      { tradingDate: '2026-07-21', icbCode: '10', icbName: 'Technology', foreignBuyValue: 200, foreignSellValue: 50, foreignNetValue: 150, matchedValue: 2_000, coverageRatio: 1 },
      { tradingDate: '2026-07-21', icbCode: '20', icbName: 'Banks', foreignBuyValue: 100, foreignSellValue: 200, foreignNetValue: -100, matchedValue: 4_000, coverageRatio: 0.8 },
    ],
  });
  proprietary.mockResolvedValue({
    status: 'ok',
    source: 'ssi_fastconnect',
    providerVersion: 'v3',
    scope: 'index',
    identifier: 'VNINDEX',
    endpoint: 'indexSummary',
    fetchedAt: '2026-07-21T09:00:00Z',
    cache: { status: 'miss', ageSeconds: null },
    rows: [{
      tradingDate: '2026-07-21',
      proprietaryBuyValue: 300,
      proprietarySellValue: 100,
      proprietaryNetValue: 200,
    }],
  });
  watchlist.mockResolvedValue({
    status: 'partial',
    dataState: 'partial',
    usable: true,
    requestedTickers: ['FPT', 'SSI'],
    normalizedTickers: ['FPT', 'SSI'],
    duplicateTickersRemoved: 0,
    expectedSymbolCount: 2,
    readySymbolCount: 1,
    partialSymbolCount: 1,
    unavailableSymbolCount: 0,
    requestedSessionCount: 60,
    fetchedAt: '2026-07-21T09:00:00Z',
    provider: 'ssi_fastconnect',
    providerVersion: 'v3',
    cacheState: 'mixed',
    items: [
      {
        ticker: 'FPT',
        availability: 'ready',
        sourceFreshness: 'latest_completed',
        cacheState: 'hit',
        actualSessionCount: 60,
        requestedSessionCount: 60,
        complete: true,
        netValue1d: 100,
        netValue5d: 300,
        netValue20d: 500,
        buyStreak: 2,
        sellStreak: 0,
        streakMetricBasis: 'foreign_net_value',
        containsProviderAnomaly: false,
        anomalySessions: [],
        anomalyCount: 0,
        source: 'ssi_fastconnect',
        sourceEndpoint: 'daily_stock_price',
      },
      {
        ticker: 'SSI',
        availability: 'partial',
        sourceFreshness: 'latest_completed',
        cacheState: 'miss',
        actualSessionCount: 20,
        requestedSessionCount: 60,
        complete: false,
        netValue1d: null,
        netValue5d: 0,
        netValue20d: -200,
        buyStreak: null,
        sellStreak: 1,
        streakMetricBasis: 'foreign_net_value',
        containsProviderAnomaly: false,
        anomalySessions: [],
        anomalyCount: 0,
        source: 'ssi_fastconnect',
        sourceEndpoint: 'daily_stock_price',
      },
    ],
  } as unknown as Awaited<ReturnType<typeof stocksApi.getVietnamForeignFlowWatchlist>>);
});

describe('ForeignFlowPage', () => {
  it('starts in Overview with four primary KPIs, one primary chart, and no fixed watchlist', async () => {
    renderPage();
    await waitFor(() => expect(vn30).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(industry).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getAllByTestId('foreign-flow-primary-kpi')).toHaveLength(4);
    expect(screen.getByText('Net foreign flow by completed session')).toBeInTheDocument();
    expect(screen.getByText(/Your watchlist is empty/)).toBeInTheDocument();
    expect(symbolHistory).not.toHaveBeenCalled();
    expect(stocksApi.getVietnamForeignFlowWatchlist).not.toHaveBeenCalled();
  });

  it('keeps Overview zero distinct from a missing KPI', async () => {
    const payload = vn30Payload();
    payload.decomposition.latest!.foreignNetValue = 0;
    payload.decomposition.windows['5'].foreignNetValue = null;
    vn30.mockResolvedValue(payload);

    renderPage();

    const oneDayCard = (await screen.findByText('Net foreign flow 1D')).closest('article');
    const fiveDayCard = screen.getByText('Net foreign flow 5D').closest('article');
    expect(oneDayCard).not.toBeNull();
    expect(fiveDayCard).not.toBeNull();
    expect(within(oneDayCard as HTMLElement).getByText('0')).toBeInTheDocument();
    expect(within(fiveDayCard as HTMLElement).getByText('—')).toBeInTheDocument();
  });

  it('keeps the usable VN30 Overview visible when Industry is unavailable', async () => {
    industry.mockResolvedValue({
      status: 'unavailable',
      dataState: 'unavailable',
      usable: false,
      failureClass: 'provider_unavailable',
      source: 'ssi_fastconnect',
      providerVersion: 'v3',
      endpoint: 'securitiesSummary',
      fetchedAt: '2026-07-21T09:00:00Z',
      cache: { status: 'unavailable', ageSeconds: null },
      rows: [],
    });

    renderPage();

    expect(await screen.findByText('Top net bought')).toBeInTheDocument();
    expect(screen.getByText('Industry summary unavailable. VN30 Overview remains usable.')).toBeInTheDocument();
    expect(screen.getAllByTestId('foreign-flow-primary-kpi')).toHaveLength(4);
  });

  it('loads a validated ticker and keeps value/volume selection request-free', async () => {
    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await waitFor(() => expect(symbolHistory).toHaveBeenCalledTimes(1));
    expect(symbolHistory).toHaveBeenCalledWith('FPT', expect.objectContaining({ limit: 20, forceRefresh: false }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Metric' })).getByRole('button', { name: 'Volume' }));
    expect(symbolHistory).toHaveBeenCalledTimes(1);
    expect(screen.getByText('2026-07-21T09:00:00Z')).toBeInTheDocument();
  });

  it('uses returned sessions for 1D and preserves numeric zero separately from missing', async () => {
    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await waitFor(() => expect(symbolHistory).toHaveBeenCalled());
    fireEvent.click(within(screen.getByRole('group', { name: 'Time window' })).getByRole('button', { name: '1D' }));
    await waitFor(() => expect(screen.getByText('1/1')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '20D' }));
    await waitFor(() => expect(screen.getAllByText('0').length).toBeGreaterThan(0));
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('renders usable current-membership VN30 decomposition with direct unsupported secondary', async () => {
    renderPage('/foreign-flow?mode=vn30');
    await waitFor(() => expect(vn30).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/Current VN30 basket foreign flow/)).toBeInTheDocument();
    expect(screen.getByText(/historical_constituent_correct = false/)).toBeInTheDocument();
    expect(screen.getByText(/Direct VN30 capability is secondary: unsupported/)).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'VN30 breadth' })).toHaveTextContent('Net buy 1');
  });

  it('exposes bounded industry data and labels turnover separately from net flow', async () => {
    renderPage();
    await waitFor(() => expect(industry).toHaveBeenCalledTimes(1));
    await screen.findByText('Industry leaders');
    fireEvent.click(screen.getByRole('button', { name: 'Industries' }));
    await waitFor(() => expect(industry).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/Turnover is trading activity, not foreign net cash flow/)).toBeInTheDocument();
    const rankings = screen.getByRole('region', { name: 'industry rankings' });
    expect(within(rankings).getByRole('columnheader', { name: 'Turnover' })).toBeInTheDocument();
    expect(within(rankings).getByText(/Technology/)).toBeInTheDocument();
  });

  it('offers only proven proprietary scopes and force refresh stays scoped', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Proprietary' }));
    await waitFor(() => expect(proprietary).toHaveBeenCalledTimes(1));
    const select = screen.getByLabelText('Supported scope');
    expect(within(select).getByRole('option', { name: 'VNINDEX' })).toBeInTheDocument();
    expect(within(select).getByRole('option', { name: 'VN30' })).toBeInTheDocument();
    expect(within(select).getByRole('option', { name: 'HOSE' })).toBeInTheDocument();
    expect(within(select).queryByRole('option', { name: /ticker|industry/i })).not.toBeInTheDocument();
    expect(screen.getAllByText('200').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /Force Refresh/ }));
    await waitFor(() => expect(proprietary).toHaveBeenLastCalledWith(
      'index',
      'VNINDEX',
      expect.objectContaining({ forceRefresh: true }),
    ));
  });

  it('renders ticker network failure as unavailable instead of empty chart content', async () => {
    symbolHistory.mockResolvedValue({
      ...tickerPayload(),
      dataState: 'unavailable',
      freshness: 'unavailable',
      failureClass: 'network_error',
      rows: [],
    });

    renderPage('/foreign-flow?mode=ticker&ticker=FPT');

    expect(await screen.findByRole('heading', { name: 'Dữ liệu hiện không khả dụng' })).toBeInTheDocument();
    expect(screen.getByText(/Không thể kết nối tới nguồn dữ liệu/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Selected window summary' })).not.toBeInTheDocument();
  });

  it('keeps successful empty ticker response distinct from provider failure', async () => {
    symbolHistory.mockResolvedValue({
      ...tickerPayload(),
      dataState: 'empty',
      freshness: 'empty',
      rows: [],
      failureClass: null,
    });

    renderPage('/foreign-flow?mode=ticker&ticker=FPT');

    expect(await screen.findByText('No completed-session records')).toBeInTheDocument();
    expect(screen.queryByText('Dữ liệu hiện không khả dụng')).not.toBeInTheDocument();
  });

  it('renders VN30, Industry, and Proprietary typed unavailable states explicitly', async () => {
    vn30.mockResolvedValue({
      ...vn30Payload(),
      status: 'unavailable',
      dataState: 'unavailable',
      usable: false,
      sourceCoverage: [{
        source: 'ssi_fastconnect',
        capabilityStatus: 'unavailable',
        usable: false,
        failureClass: 'network_error',
      }],
      decomposition: {
        ...vn30Payload().decomposition,
        status: 'unavailable',
        dataState: 'unavailable',
        usable: false,
        series: [],
      },
    } as unknown as VietnamVn30ForeignFlowResponse);
    const unavailableAggregate = {
      status: 'unavailable' as const,
      dataState: 'unavailable' as const,
      usable: false,
      failureClass: 'network_error',
      source: 'ssi_fastconnect',
      providerVersion: 'v3',
      endpoint: 'securitiesSummary',
      fetchedAt: '2026-07-21T09:00:00Z',
      cache: { status: 'unavailable', ageSeconds: null },
      rows: [],
    };
    industry.mockResolvedValue(unavailableAggregate);
    proprietary.mockResolvedValue(unavailableAggregate);

    const view = renderPage('/foreign-flow?mode=vn30');
    expect(await screen.findByRole('region', { name: 'vn30 foreign flow unavailable' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Industries' }));
    expect(await screen.findByRole('region', { name: 'industry foreign flow unavailable' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Proprietary' }));
    expect(await screen.findByRole('region', { name: 'proprietary foreign flow unavailable' })).toBeInTheDocument();
    view.unmount();
  });

  it('preserves usable mode data and avoids refetch when revisiting a mode', async () => {
    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await waitFor(() => expect(symbolHistory).toHaveBeenCalledTimes(1));
    expect(screen.getByText('2026-07-21T09:00:00Z')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Stocks' }));
    await waitFor(() => expect(vn30).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: 'Overview' }));
    await screen.findByText('Top net bought');
    fireEvent.click(screen.getByRole('button', { name: 'FPT' }));

    await waitFor(() => expect(screen.getByText('2026-07-21T09:00:00Z')).toBeInTheDocument());
    expect(symbolHistory).toHaveBeenCalledTimes(1);
  });

  it('keeps Overview metric and window changes local and hides gross series by default', async () => {
    renderPage();
    await screen.findByText('Top net bought');
    const vn30Calls = vn30.mock.calls.length;
    const industryCalls = industry.mock.calls.length;
    expect(screen.getByRole('button', { name: 'Show gross buy/sell' })).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(within(screen.getByRole('group', { name: 'Metric' })).getByRole('button', { name: 'Volume' }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Time window' })).getByRole('button', { name: '5D' }));

    await waitFor(() => {
      expect(vn30).toHaveBeenCalledTimes(vn30Calls);
      expect(industry).toHaveBeenCalledTimes(industryCalls);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Show gross buy/sell' }));
    expect(screen.getByRole('button', { name: 'Show net only' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('renders saved watchlist rows compactly without blanking partial items', async () => {
    localStorage.setItem('stockclock.vn.foreignFlowWatchlist.v1', JSON.stringify({
      tickers: ['FPT', 'SSI'],
      metric: 'value',
      window: 20,
      filter: 'all',
      sort: 'input',
      direction: 'asc',
    }));
    renderPage();

    await waitFor(() => expect(watchlist).toHaveBeenCalledTimes(1));
    const summary = screen.getByRole('heading', { name: 'Watchlist snapshot' }).closest('section');
    expect(summary).not.toBeNull();
    expect(within(summary as HTMLElement).getByText('FPT')).toBeInTheDocument();
    expect(within(summary as HTMLElement).getByText('SSI')).toBeInTheDocument();
    expect(within(summary as HTMLElement).getAllByText('—').length).toBeGreaterThan(0);
    expect(within(summary as HTMLElement).getByText(/usable rows remain visible/)).toBeInTheDocument();
  });

  it('keeps provider publication lag compact and secondary', async () => {
    renderPage();
    await screen.findByText('Top net bought');

    expect(screen.getByText('Provider publication lag')).toBeInTheDocument();
    expect(screen.queryByRole('alert', { name: /publication lag/i })).not.toBeInTheDocument();
  });

  it('moves technical provenance and direct capability into Data Details', async () => {
    renderPage();
    await screen.findByText('Top net bought');
    expect(screen.queryByText('securitiesSummary?index=')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Data Details' }));

    expect(await screen.findByRole('heading', { name: 'VN30 foreign flow provenance' })).toBeInTheDocument();
    expect(screen.getByText('Direct VN30 capability')).toBeInTheDocument();
    expect(screen.getByText('Historical constituent correctness')).toBeInTheDocument();
    expect(screen.getByText('unsupported')).toBeInTheDocument();
  });

  it('keeps explicit Watchlist and Proprietary deep links', async () => {
    const watchlistView = renderPage('/foreign-flow?mode=watchlist');
    expect(screen.getByRole('button', { name: 'Watchlist' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('heading', { name: 'Create a foreign-flow watchlist' })).toBeInTheDocument();
    watchlistView.unmount();

    renderPage('/foreign-flow?mode=proprietary');
    await waitFor(() => expect(proprietary).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button', { name: 'Proprietary' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('preserves same-mode usable data when a force refresh becomes unavailable', async () => {
    symbolHistory
      .mockResolvedValueOnce(tickerPayload())
      .mockResolvedValueOnce({
        ...tickerPayload(),
        dataState: 'unavailable',
        freshness: 'unavailable',
        failureClass: 'network_error',
        rows: [],
      });
    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await waitFor(() => expect(symbolHistory).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /Force Refresh/ }));

    await waitFor(() => expect(symbolHistory).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể kết nối');
    expect(screen.getByRole('region', { name: 'Selected window summary' })).toBeInTheDocument();
    expect(screen.queryByText('Dữ liệu hiện không khả dụng')).not.toBeInTheDocument();
  });
});
