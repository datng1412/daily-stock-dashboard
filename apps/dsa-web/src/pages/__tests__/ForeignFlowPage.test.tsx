import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  stocksApi,
  type VietnamForeignFlowSymbolHistoryResponse,
  type VietnamVn30ForeignFlowResponse,
} from '../../api/stocks';
import ForeignFlowPage from '../ForeignFlowPage';

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getVietnamForeignFlowSymbolHistory: vi.fn(),
    getVietnamCurrentForeignFlow: vi.fn(),
    getVietnamCurrentForeignFlowAggregate: vi.fn(),
    getVietnamVn30ForeignFlow: vi.fn(),
    getVietnamIndustryFlow: vi.fn(),
    getVietnamProprietaryFlow: vi.fn(),
    getVietnamProprietaryFlowEodLatest: vi.fn(),
    getVietnamProprietaryFlowEodHistory: vi.fn(),
    getVietnamForeignFlowWatchlist: vi.fn(),
    getVietnamIndexComponents: vi.fn(),
  },
}));

const symbolHistory = vi.mocked(stocksApi.getVietnamForeignFlowSymbolHistory);
const currentFlow = vi.mocked(stocksApi.getVietnamCurrentForeignFlow);
const currentAggregate = vi.mocked(stocksApi.getVietnamCurrentForeignFlowAggregate);
const vn30 = vi.mocked(stocksApi.getVietnamVn30ForeignFlow);
const industry = vi.mocked(stocksApi.getVietnamIndustryFlow);
const proprietary = vi.mocked(stocksApi.getVietnamProprietaryFlow);
const proprietaryEodLatest = vi.mocked(stocksApi.getVietnamProprietaryFlowEodLatest);
const proprietaryEodHistory = vi.mocked(stocksApi.getVietnamProprietaryFlowEodHistory);
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
    { tradingDate: '2026-07-20', foreignBuyValue: 0, foreignSellValue: null, foreignNetValue: null, foreignBuyVolume: 0, foreignSellVolume: null, foreignNetVolume: null, dataQuality: 'incomplete', complete: false },
    { tradingDate: '2026-07-21', foreignBuyValue: 200, foreignSellValue: 50, foreignNetValue: 150, foreignBuyVolume: 20, foreignSellVolume: 5, foreignNetVolume: 15, dataQuality: 'complete', complete: true },
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
  currentFlow.mockResolvedValue({
    status: 'ok',
    dataState: 'ready',
    usable: true,
    source: 'SSI FastConnect V3 ForeignRoomMessage',
    providerVersion: 'v3',
    symbol: 'FPT',
    tradingDate: '2026-07-29',
    freshnessStatus: 'ready',
    isCurrentSession: true,
    isProvisional: true,
    current: {
      foreignBuyValue: 1_000,
      foreignSellValue: 400,
      foreignNetValue: 600,
      foreignBuyVolume: 10,
      foreignSellVolume: 4,
      foreignNetVolume: 6,
    },
    latestCompletedComparison: { date: '2026-07-28' },
    streamStatus: 'cache_hit',
    streamReason: '',
    endpoint: 'room.FPT',
    finality: 'current_session_provisional',
    updateSemantics: 'cumulative_replacement_snapshot',
    cache: { status: 'hit', ageSeconds: 1 },
  });
  currentAggregate.mockResolvedValue({
    status: 'unavailable',
    dataState: 'waiting',
    usable: false,
    scope: 'current_foreign_flow_aggregate',
    universe: 'VN30',
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
    status: 'unavailable',
    dataState: 'unavailable',
    usable: false,
    failureClass: 'proprietary_fields_unsupported',
    capabilityStatus: 'unsupported',
    source: 'ssi_fastconnect',
    providerVersion: 'v3',
    scope: 'index',
    identifier: 'VNINDEX',
    endpoint: 'none',
    fetchedAt: '2026-07-21T09:00:00Z',
    cache: { status: 'not_applicable', ageSeconds: null },
    rows: [],
    diagnostics: {
      attemptedOperation: 'none',
      reason: 'no_proven_proprietary_flow_fields',
    },
  });
  proprietaryEodLatest.mockResolvedValue({
    status: 'empty',
    dataState: 'no_data',
    exchange: 'HOSE',
    latest: null,
    source: 'official_exchange_pdf_manual_entry',
    warnings: [],
  });
  proprietaryEodHistory.mockResolvedValue({
    status: 'empty',
    dataState: 'no_data',
    exchange: 'HOSE',
    count: 0,
    series: [],
    sourceSummary: { sourceType: 'official_exchange_pdf_manual_entry', finality: 'completed_daily', valueUnit: 'VND', volumeUnit: 'shares' },
    warnings: [],
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

afterEach(() => {
  vi.useRealTimers();
});

describe('ForeignFlowPage', () => {
  it('starts in Overview with four primary KPIs, one primary chart, and no fixed watchlist', async () => {
    renderPage();
    await waitFor(() => expect(vn30).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(industry).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getAllByTestId('foreign-flow-primary-kpi')).toHaveLength(4);
    expect(screen.getByText('Net foreign flow through latest session')).toBeInTheDocument();
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
    await waitFor(() => expect(currentFlow).toHaveBeenCalledTimes(1));
    expect(symbolHistory).toHaveBeenCalledWith('FPT', expect.objectContaining({ limit: 20, forceRefresh: false }));
    expect(screen.getAllByRole('heading', { name: 'Foreign flow' })).toHaveLength(1);
    expect(screen.queryByRole('heading', { name: 'Current-session foreign flow' })).not.toBeInTheDocument();
    const latestCard = screen.getByTestId('latest-foreign-flow-card');
    expect(within(latestCard).getByText('Đang diễn ra')).toBeInTheDocument();
    expect(within(latestCard).getByText(/Session: 2026-07-29/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Selected window summary' })).not.toBeInTheDocument();
    fireEvent.click(within(screen.getByRole('group', { name: 'Metric' })).getByRole('button', { name: 'Volume' }));
    expect(symbolHistory).toHaveBeenCalledTimes(1);
    expect(currentFlow).toHaveBeenCalledTimes(1);
    expect(screen.getByText('2026-07-21T09:00:00Z')).toBeInTheDocument();
  });

  it('inserts the provider-backed current session first without changing completed rows', async () => {
    renderPage('/foreign-flow?mode=ticker&ticker=FPT');

    const currentRow = await screen.findByTestId('current-session-flow-row');
    expect(currentRow).toHaveAttribute('data-current-session', 'true');
    expect(within(currentRow).getByText('2026-07-29')).toBeInTheDocument();
    expect(within(currentRow).getByText('1,000')).toBeInTheDocument();
    expect(within(currentRow).getByText('400')).toBeInTheDocument();
    expect(within(currentRow).getByText('600')).toBeInTheDocument();
    expect(within(currentRow).getAllByText('—')).toHaveLength(2);
    expect(within(currentRow).getByText('Đang diễn ra')).toBeInTheDocument();

    const table = screen.getByRole('heading', { name: 'Chi tiết phiên' }).closest('section');
    expect(table).not.toBeNull();
    const rows = within(table as HTMLElement).getAllByRole('row').slice(1);
    expect(rows[0]).toBe(currentRow);
    expect(within(rows[1]).getByText('2026-07-21')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Đủ')).toBeInTheDocument();

    fireEvent.click(within(table as HTMLElement).getByRole('button', { name: 'NN mua' }));
    expect(within(table as HTMLElement).getAllByRole('row')[1]).toBe(currentRow);
    expect(currentFlow).toHaveBeenCalledTimes(1);
    expect(symbolHistory).toHaveBeenCalledTimes(1);
  });

  it('shows a dated waiting row without fabricated values', async () => {
    currentFlow.mockResolvedValue({
      status: 'unavailable',
      dataState: 'waiting',
      usable: false,
      source: 'ssi_fastconnect',
      providerVersion: 'v3',
      symbol: 'FPT',
      tradingDate: '2026-07-29',
      freshnessStatus: 'waiting',
      isCurrentSession: false,
      isProvisional: false,
      current: null,
      streamStatus: 'subscribed_no_event',
      streamReason: 'Waiting for room data.',
    });

    renderPage('/foreign-flow?mode=ticker&ticker=FPT');

    const currentRow = await screen.findByTestId('current-session-flow-row');
    expect(within(currentRow).getAllByText('—')).toHaveLength(5);
    expect(within(currentRow).getByText('Chờ dữ liệu')).toBeInTheDocument();
    expect(within(currentRow).queryByText('0')).not.toBeInTheDocument();
  });

  it('lets an accepted same-date row suppress the provisional display row', async () => {
    const payload = tickerPayload();
    payload.rows = [{
      tradingDate: '2026-07-29',
      foreignBuyValue: 200,
      foreignSellValue: 50,
      foreignNetValue: 150,
      foreignBuyVolume: 20,
      foreignSellVolume: 5,
      foreignNetVolume: 15,
    }];
    symbolHistory.mockResolvedValue(payload);

    renderPage('/foreign-flow?mode=ticker&ticker=FPT');

    await screen.findByText('Chi tiết phiên');
    await waitFor(() => expect(currentFlow).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId('current-session-flow-row')).not.toBeInTheDocument();
    const summary = screen.getByTestId('latest-foreign-flow-card');
    expect(within(summary).getByText('Đủ')).toBeInTheDocument();
    expect(within(summary).getByText(/Session: 2026-07-29/)).toBeInTheDocument();
    const table = screen.getByRole('heading', { name: 'Chi tiết phiên' }).closest('section');
    expect(table).not.toBeNull();
    expect(within(table as HTMLElement).getAllByText('2026-07-29')).toHaveLength(1);
    expect(within(table as HTMLElement).getByText('Đủ')).toBeInTheDocument();
  });

  it('polls current flow once per interval and force refresh issues one explicit read', async () => {
    vi.useFakeTimers();
    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await act(async () => {
      vi.advanceTimersByTime(0);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(currentFlow).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(15_000);
      await Promise.resolve();
    });
    expect(currentFlow).toHaveBeenCalledTimes(2);
    expect(currentFlow).toHaveBeenLastCalledWith(
      'FPT',
      expect.objectContaining({ forceRefresh: false }),
    );

    const forceRefresh = screen.getByRole('button', { name: /Force Refresh/ });
    fireEvent.click(forceRefresh);
    fireEvent.click(forceRefresh);
    await act(async () => {
      vi.advanceTimersByTime(0);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(currentFlow).toHaveBeenCalledTimes(3);
    expect(currentFlow).toHaveBeenLastCalledWith(
      'FPT',
      expect.objectContaining({
        forceRefresh: true,
        recoveryTrigger: 'manual_refresh',
      }),
    );
  });

  it('uses one effective current-flow polling lifecycle under React Strict Mode', async () => {
    vi.useFakeTimers();
    window.history.pushState({}, '', '/foreign-flow?mode=ticker&ticker=FPT');
    render(
      <StrictMode>
        <BrowserRouter>
          <ForeignFlowPage />
        </BrowserRouter>
      </StrictMode>,
    );

    await act(async () => {
      vi.advanceTimersByTime(0);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(currentFlow).toHaveBeenCalledTimes(1);
    expect(currentFlow).toHaveBeenCalledWith(
      'FPT',
      expect.objectContaining({ forceRefresh: false }),
    );
  });

  it('issues one bounded current-flow refresh on hidden-to-visible resume without clearing values', async () => {
    vi.useFakeTimers();
    let visibility: DocumentVisibilityState = 'visible';
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => visibility,
    });
    let resolveResume!: (
      value: Awaited<ReturnType<typeof stocksApi.getVietnamCurrentForeignFlow>>,
    ) => void;

    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await act(async () => {
      vi.advanceTimersByTime(0);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(currentFlow).toHaveBeenCalledTimes(1);
    expect(within(screen.getByTestId('latest-foreign-flow-card')).getByText(/Session: 2026-07-29/)).toBeInTheDocument();

    currentFlow.mockImplementationOnce(() => new Promise((resolve) => {
      resolveResume = resolve;
    }));
    visibility = 'hidden';
    fireEvent(document, new Event('visibilitychange'));
    await act(async () => {
      vi.advanceTimersByTime(15_000);
      await Promise.resolve();
    });
    expect(currentFlow).toHaveBeenCalledTimes(1);

    visibility = 'visible';
    fireEvent(document, new Event('visibilitychange'));
    fireEvent(document, new Event('visibilitychange'));
    expect(currentFlow).toHaveBeenCalledTimes(2);
    expect(currentFlow).toHaveBeenLastCalledWith(
      'FPT',
      expect.objectContaining({
        forceRefresh: true,
        recoveryTrigger: 'visibility_resume',
      }),
    );
    expect(within(screen.getByTestId('latest-foreign-flow-card')).getByText(/Session: 2026-07-29/)).toBeInTheDocument();

    resolveResume({
      status: 'partial',
      dataState: 'stale',
      usable: true,
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      providerVersion: 'v3',
      symbol: 'FPT',
      tradingDate: '2026-07-29',
      freshnessStatus: 'stale',
      isCurrentSession: true,
      isProvisional: true,
      current: {
        foreignBuyValue: 1_000,
        foreignSellValue: 400,
        foreignNetValue: 600,
        foreignBuyVolume: 10,
        foreignSellVolume: 4,
        foreignNetVolume: 6,
      },
      streamStatus: 'reconnecting',
      streamReason: 'Connection lost.',
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(within(screen.getByTestId('latest-foreign-flow-card')).getByText('Mất kết nối')).toBeInTheDocument();
  });

  it('retains the current VN30 row as stale when visibility recovery is unavailable', async () => {
    vi.useFakeTimers();
    let visibility: DocumentVisibilityState = 'visible';
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => visibility,
    });
    currentAggregate.mockResolvedValueOnce({
      status: 'ok',
      dataState: 'ready',
      usable: true,
      scope: 'current_foreign_flow_aggregate',
      universe: 'index:VN30',
      providerSessionDate: '2026-07-30',
      isProvisional: true,
      finality: 'current_session_provisional',
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      providerVersion: 'v3',
      endpoint: 'room.{symbol}',
      updateSemantics: 'cumulative_replacement_snapshot',
      aggregate: { foreignNetValue: 600 },
      displaySeries: [{
        tradingDate: '2026-07-30',
        sourceKind: 'current',
        finality: 'current_session_provisional',
        foreignBuyValue: 1_000,
        foreignSellValue: 400,
        foreignNetValue: 600,
        requestedCount: 30,
        observedCount: 30,
        completeValueCount: 30,
        completeVolumeCount: 30,
      }],
      displayWindows: {},
      rankings: {},
      items: [],
      groups: [],
      coverage: {
        requestedSymbolCount: 30,
        classifiedSymbolCount: 30,
        subscribedSymbolCount: 30,
        observedSymbolCount: 30,
        completeVolumeCount: 30,
        completeValueCount: 30,
        missingSymbols: [],
        staleSymbolCount: 0,
      },
      diagnostics: {},
    }).mockResolvedValueOnce({
      status: 'unavailable',
      dataState: 'unavailable',
      usable: false,
      failureClass: 'authentication_failed_retryable',
      scope: 'current_foreign_flow_aggregate',
      universe: 'index:VN30',
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
        requestedSymbolCount: 30,
        classifiedSymbolCount: 30,
        subscribedSymbolCount: 30,
        observedSymbolCount: 0,
        completeVolumeCount: 0,
        completeValueCount: 0,
        missingSymbols: [],
        staleSymbolCount: 0,
      },
      diagnostics: {},
    });

    renderPage('/foreign-flow?mode=vn30');
    await act(async () => {
      vi.advanceTimersByTime(0);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByTestId('current-session-flow-row')).toBeInTheDocument();

    visibility = 'hidden';
    fireEvent(document, new Event('visibilitychange'));
    visibility = 'visible';
    fireEvent(document, new Event('visibilitychange'));
    fireEvent(document, new Event('visibilitychange'));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(currentAggregate).toHaveBeenCalledTimes(2);
    expect(currentAggregate).toHaveBeenLastCalledWith(expect.objectContaining({
      forceRefresh: true,
      recoveryTrigger: 'visibility_resume',
    }));
    const retained = screen.getByTestId('current-session-flow-row');
    expect(within(retained).getByText('2026-07-30')).toBeInTheDocument();
    expect(within(retained).getByText('Mất kết nối')).toBeInTheDocument();
    expect(screen.queryByText('Overview unavailable')).not.toBeInTheDocument();
  });

  it('ignores a stale current-flow response after the selected symbol changes', async () => {
    let resolveFpt!: (
      value: Awaited<ReturnType<typeof stocksApi.getVietnamCurrentForeignFlow>>,
    ) => void;
    currentFlow
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveFpt = resolve;
      }))
      .mockResolvedValueOnce({
        status: 'ok',
        dataState: 'ready',
        usable: true,
        source: 'SSI FastConnect V3 ForeignRoomMessage',
        providerVersion: 'v3',
        symbol: 'HPG',
        tradingDate: '2026-07-30',
        freshnessStatus: 'ready',
        isCurrentSession: true,
        isProvisional: true,
        current: {
          foreignBuyValue: 2_000,
          foreignSellValue: 500,
          foreignNetValue: 1_500,
        },
        streamStatus: 'cache_hit',
        streamReason: '',
      });

    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await waitFor(() => expect(currentFlow).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'HPG' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load ticker' }));
    await waitFor(() => expect(currentFlow).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(within(screen.getByTestId('latest-foreign-flow-card')).getByText(/Session: 2026-07-30/)).toBeInTheDocument());

    resolveFpt({
      status: 'ok',
      dataState: 'ready',
      usable: true,
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      providerVersion: 'v3',
      symbol: 'FPT',
      tradingDate: '2026-07-31',
      freshnessStatus: 'ready',
      isCurrentSession: true,
      isProvisional: true,
      current: { foreignNetValue: 9_999 },
      streamStatus: 'cache_hit',
      streamReason: '',
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(within(screen.getByTestId('latest-foreign-flow-card')).getByText(/Session: 2026-07-30/)).toBeInTheDocument();
    expect(screen.queryByText(/Session: 2026-07-31/)).not.toBeInTheDocument();
  });

  it('keeps an explicit-zero after-hours snapshot visible as provisional', async () => {
    currentFlow.mockResolvedValue({
      status: 'partial',
      dataState: 'market_closed',
      usable: true,
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      providerVersion: 'v3',
      symbol: 'FPT',
      tradingDate: '2026-07-29',
      freshnessStatus: 'market_closed',
      isCurrentSession: true,
      isProvisional: true,
      current: {
        foreignBuyValue: 0,
        foreignSellValue: 0,
        foreignNetValue: 0,
        foreignBuyVolume: 0,
        foreignSellVolume: 0,
        foreignNetVolume: 0,
      },
      latestCompletedComparison: { date: '2026-07-28' },
      streamStatus: 'cache_hit',
      streamReason: 'Market closed.',
      endpoint: 'room.FPT',
      finality: 'current_session_provisional',
      updateSemantics: 'cumulative_replacement_snapshot',
      cache: { status: 'stale', ageSeconds: 120 },
    });

    renderPage('/foreign-flow?mode=ticker&ticker=FPT');

    const card = await screen.findByRole('region', { name: 'Foreign flow' });
    expect(within(card).getByText('Tạm tính')).toBeInTheDocument();
    expect(within(card).getByText(/Session: 2026-07-29/)).toBeInTheDocument();
    expect(within(card).getAllByText('0')).toHaveLength(6);
    const currentRow = await screen.findByTestId('current-session-flow-row');
    expect(within(currentRow).getByText('2026-07-29')).toBeInTheDocument();
    expect(within(currentRow).getByText('Tạm tính')).toBeInTheDocument();
  });

  it('uses returned sessions for 1D and preserves numeric zero separately from missing', async () => {
    renderPage('/foreign-flow?mode=ticker&ticker=FPT');
    await waitFor(() => expect(symbolHistory).toHaveBeenCalled());
    fireEvent.click(within(screen.getByRole('group', { name: 'Time window' })).getByRole('button', { name: '1D' }));
    const table = screen.getByRole('heading', { name: 'Chi tiết phiên' }).closest('section');
    expect(table).not.toBeNull();
    await waitFor(() => {
      expect(within(table as HTMLElement).getByText('2026-07-21')).toBeInTheDocument();
      expect(within(table as HTMLElement).queryByText('2026-07-20')).not.toBeInTheDocument();
    });
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

  it('keeps a stale full-coverage VN30 session provisional in the detail table', async () => {
    const payload = vn30Payload();
    payload.decomposition.latestCompletedSession = '2026-07-29';
    payload.decomposition.series = [
      {
        tradingDate: '2026-07-28',
        foreignBuyValue: 100,
        foreignSellValue: 80,
        foreignNetValue: 20,
        dataState: 'ready',
        state: 'ready',
      },
      {
        tradingDate: '2026-07-29',
        foreignBuyValue: 120,
        foreignSellValue: 90,
        foreignNetValue: 30,
        dataState: 'ready',
        state: 'ready',
      },
    ];
    vn30.mockResolvedValue(payload);
    currentAggregate.mockResolvedValue({
      status: 'ok',
      dataState: 'stale',
      usable: true,
      scope: 'current_foreign_flow_aggregate',
      universe: 'index:VN30',
      providerSessionDate: '2026-07-30',
      isProvisional: true,
      finality: 'current_session_provisional',
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      providerVersion: 'v3',
      endpoint: 'room.{symbol}',
      updateSemantics: 'cumulative_replacement_snapshot',
      aggregate: { foreignNetValue: 94_120_000_000 },
      displaySeries: [{
        tradingDate: '2026-07-30',
        sourceKind: 'current',
        finality: 'current_session_provisional',
        foreignBuyValue: 539_680_000_000,
        foreignSellValue: 445_570_000_000,
        foreignNetValue: 94_120_000_000,
        requestedCount: 30,
        observedCount: 30,
        completeValueCount: 30,
        completeVolumeCount: 30,
        isStale: true,
      }],
      displayWindows: {},
      rankings: {},
      items: [],
      groups: [],
      coverage: {
        requestedSymbolCount: 30,
        classifiedSymbolCount: 30,
        subscribedSymbolCount: 30,
        observedSymbolCount: 30,
        completeVolumeCount: 30,
        completeValueCount: 30,
        missingSymbols: [],
        staleSymbolCount: 30,
      },
    });

    renderPage('/foreign-flow?mode=vn30');

    const currentRow = await screen.findByTestId('current-session-flow-row');
    expect(within(currentRow).getByText('2026-07-30')).toBeInTheDocument();
    expect(within(currentRow).getByText('Mất kết nối')).toBeInTheDocument();
    expect(within(currentRow).queryByText('Đủ')).not.toBeInTheDocument();
    const table = screen.getByRole('heading', { name: 'Chi tiết phiên' }).closest('section');
    expect(table).not.toBeNull();
    const rows = within(table as HTMLElement).getAllByRole('row').slice(1);
    expect(within(rows[1]).getByText('2026-07-29')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Đủ')).toBeInTheDocument();
    expect(within(rows[2]).getByText('2026-07-28')).toBeInTheDocument();
    expect(within(rows[2]).getByText('Đủ')).toBeInTheDocument();
    expect(currentAggregate).toHaveBeenCalledTimes(1);
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

  it('uses current industry groups for rankings while the detail row stays canonical', async () => {
    currentAggregate.mockResolvedValue({
      status: 'ok',
      dataState: 'ready',
      usable: true,
      scope: 'current_foreign_flow_aggregate',
      universe: 'index:VN30',
      providerSessionDate: '2026-07-22',
      isProvisional: true,
      finality: 'current_session_provisional',
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      providerVersion: 'v3',
      endpoint: 'room.{symbol}',
      updateSemantics: 'cumulative_replacement_snapshot',
      aggregate: {
        foreignBuyValue: 600,
        foreignSellValue: 300,
        foreignNetValue: 300,
      },
      displaySeries: [],
      displayWindows: {},
      rankings: {},
      items: [],
      groups: [
        {
          icbCode: '10',
          icbName: 'Technology',
          foreignBuyValue: 400,
          foreignSellValue: 200,
          foreignNetValue: 200,
          coverageRatio: 1,
        },
        {
          icbCode: '20',
          icbName: 'Banks',
          foreignBuyValue: 200,
          foreignSellValue: 100,
          foreignNetValue: 100,
          coverageRatio: 1,
        },
        {
          icbCode: '30',
          icbName: 'Missing Industry',
          foreignBuyValue: null,
          foreignSellValue: null,
          foreignNetValue: null,
          coverageRatio: 0,
        },
      ],
      coverage: {
        requestedSymbolCount: 2,
        classifiedSymbolCount: 2,
        subscribedSymbolCount: 2,
        observedSymbolCount: 2,
        completeVolumeCount: 2,
        completeValueCount: 2,
        missingSymbols: [],
        staleSymbolCount: 0,
      },
    });

    renderPage('/foreign-flow?mode=industry');

    const rankings = await screen.findByRole('region', { name: 'industry rankings' });
    await waitFor(() => expect(currentAggregate).toHaveBeenCalledTimes(1));
    expect(within(rankings).getByText('Technology (10)')).toBeInTheDocument();
    expect(within(rankings).getByText('Banks (20)')).toBeInTheDocument();
    expect(within(rankings).queryByText(/Missing Industry/)).not.toBeInTheDocument();
    expect(within(rankings).queryByText(/unclassified/i)).not.toBeInTheDocument();
    await waitFor(() => expect(within(rankings).getByText('350')).toBeInTheDocument());
    const currentDetailRow = await screen.findByTestId('current-session-flow-row');
    expect(within(currentDetailRow).getAllByText('300')).toHaveLength(2);
  });

  it('renders the dedicated EOD proprietary empty state without calling the unsupported SSI capability', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Proprietary' }));
    await waitFor(() => expect(proprietaryEodLatest).toHaveBeenCalledTimes(1));
    expect(proprietaryEodHistory).toHaveBeenCalledTimes(1);
    expect(proprietary).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Dữ liệu tự doanh HOSE cuối ngày' })).toBeInTheDocument();
    expect(screen.getByText('Chưa có dữ liệu')).toBeInTheDocument();
    expect(screen.queryByText(/Realtime|Đang diễn ra|Tạm tính|15 giây/i)).not.toBeInTheDocument();
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

  it('renders missing completed fields as dashes and keeps explicit provider zero', async () => {
    symbolHistory.mockResolvedValue({
      ...tickerPayload(),
      rows: [{
        tradingDate: '2026-06-29',
        foreignBuyValue: null,
        foreignSellValue: null,
        foreignNetValue: null,
        foreignBuyVolume: null,
        foreignSellVolume: null,
        foreignNetVolume: null,
        dataQuality: 'incomplete',
        complete: false,
        missingForeignFields: [
          'foreign_buy_volume',
          'foreign_sell_volume',
          'foreign_buy_value',
          'foreign_sell_value',
        ],
      }, {
        tradingDate: '2026-06-30',
        foreignBuyValue: 0,
        foreignSellValue: 0,
        foreignNetValue: 0,
        foreignBuyVolume: 0,
        foreignSellVolume: 0,
        foreignNetVolume: 0,
        dataQuality: 'complete',
        complete: true,
      }],
      coverage: { requestedSessions: 20, coveredSessions: 2, complete: false },
    });
    currentFlow.mockResolvedValue({
      status: 'unavailable',
      dataState: 'unavailable',
      usable: false,
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      providerVersion: 'v3',
      symbol: 'FPT',
      tradingDate: null,
      freshnessStatus: 'unavailable',
      isCurrentSession: false,
      isProvisional: false,
      current: null,
      streamStatus: 'unavailable',
      streamReason: '',
      endpoint: 'room.FPT',
      cache: {},
    });

    renderPage('/foreign-flow?mode=ticker&ticker=FPT');

    const table = await screen.findByRole('heading', { name: 'Chi tiết phiên' });
    const section = table.closest('section');
    expect(section).not.toBeNull();
    const rows = within(section as HTMLElement).getAllByRole('row').slice(1);
    const missing = rows.find((row) => within(row).queryByText('2026-06-29'));
    const explicitZero = rows.find((row) => within(row).queryByText('2026-06-30'));
    expect(missing).toBeDefined();
    expect(within(missing as HTMLElement).getAllByText('—').length).toBeGreaterThanOrEqual(3);
    expect(within(missing as HTMLElement).getByText('Thiếu dữ liệu')).toBeInTheDocument();
    expect(within(missing as HTMLElement).queryByText('0')).not.toBeInTheDocument();
    expect(explicitZero).toBeDefined();
    expect(within(explicitZero as HTMLElement).getAllByText('0').length).toBeGreaterThanOrEqual(3);
    expect(within(explicitZero as HTMLElement).getByText('Đủ')).toBeInTheDocument();
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

  it('renders VN30 and Industry typed unavailable states while Proprietary uses its EOD state', async () => {
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
    expect(await screen.findByText('Chưa có dữ liệu')).toBeInTheDocument();
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

    expect(screen.queryByText('Provider publication lag')).not.toBeInTheDocument();
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
    await waitFor(() => expect(proprietaryEodLatest).toHaveBeenCalledTimes(1));
    expect(proprietaryEodHistory).toHaveBeenCalledTimes(1);
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
    expect(screen.getByTestId('latest-foreign-flow-card')).toBeInTheDocument();
    expect(screen.queryByText('Dữ liệu hiện không khả dụng')).not.toBeInTheDocument();
  });
});
