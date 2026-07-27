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
    { ticker: 'FPT', foreignNetValue20d: 500 },
    { ticker: 'HPG', foreignNetValue20d: -100 },
  ],
  decomposition: {
    latestCompletedSession: '2026-07-21',
    series: [
      {
        tradingDate: '2026-07-21',
        foreignBuyValue: 1_000,
        foreignSellValue: 600,
        foreignNetValue: 400,
        valueBreadth: { netBuyCount: 1, netSellCount: 1, zeroCount: 0, unavailableCount: 0 },
        valueCoverageRatio: 1,
      },
    ],
  },
  canonical: { capabilityStatus: 'unsupported' },
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
});

describe('ForeignFlowPage', () => {
  it('starts with a user-controlled empty watchlist and no provider request', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: 'Create a foreign-flow watchlist' })).toBeInTheDocument();
    expect(screen.getByText(/No symbols are loaded by default/)).toBeInTheDocument();
    expect(symbolHistory).not.toHaveBeenCalled();
  });

  it('loads a validated ticker and keeps value/volume selection request-free', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Ticker' }));
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'fpt' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load ticker' }));
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
    fireEvent.click(screen.getByRole('button', { name: 'Industry' }));
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

    fireEvent.click(screen.getByRole('button', { name: 'Industry' }));
    expect(await screen.findByRole('region', { name: 'industry foreign flow unavailable' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Proprietary' }));
    expect(await screen.findByRole('region', { name: 'proprietary foreign flow unavailable' })).toBeInTheDocument();
    view.unmount();
  });

  it('preserves usable mode data and avoids refetch when revisiting a mode', async () => {
    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await waitFor(() => expect(symbolHistory).toHaveBeenCalledTimes(1));
    expect(screen.getByText('2026-07-21T09:00:00Z')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Current VN30 basket' }));
    await waitFor(() => expect(vn30).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: 'Ticker' }));

    await waitFor(() => expect(screen.getByText('2026-07-21T09:00:00Z')).toBeInTheDocument());
    expect(symbolHistory).toHaveBeenCalledTimes(1);
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
