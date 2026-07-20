import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type VietnamForeignFlowBatchResponse, type VietnamForeignFlowBatchSymbol } from '../../api/stocks';
import { VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY } from '../../utils/vietnamCustomWatchlist';
import ForeignFlowPage from '../ForeignFlowPage';

vi.mock('../../api/stocks', () => ({
  stocksApi: { getVietnamForeignFlowBatch: vi.fn() },
}));

const mockedBatch = vi.mocked(stocksApi.getVietnamForeignFlowBatch);

const makeRow = (ticker: string, index: number, overrides: Partial<VietnamForeignFlowBatchSymbol> = {}): VietnamForeignFlowBatchSymbol => ({
  ticker,
  dataState: 'ready',
  freshness: 'fresh',
  latestTradingDate: '2026-07-17',
  foreignBuyVolume: 1_000 + index,
  foreignSellVolume: 400,
  foreignNetVolume: index % 2 ? -600 : 600,
  foreignBuyValue: 3_000_000_000,
  foreignSellValue: 1_000_000_000,
  foreignNetValue: index % 2 ? -1_000_000_000 : 2_000_000_000,
  foreignNetVolume5d: index % 2 ? -3_000 : 3_000,
  foreignNetValue5d: index % 2 ? -3_000_000_000 : 5_000_000_000,
  foreignNetVolume20d: index % 2 ? -8_000 : 8_000,
  foreignNetValue20d: index % 2 ? -8_000_000_000 : 12_000_000_000,
  coveredSessions5d: 5,
  complete5d: true,
  coveredSessions20d: 20,
  complete20d: true,
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: 'shares',
  valueUnit: 'VND',
  finality: 'daily_available',
  fetchedAt: '2026-07-17T08:00:00Z',
  ...overrides,
});

const makeResponse = (
  tickers: string[],
  overrides: Partial<VietnamForeignFlowBatchResponse> = {},
): VietnamForeignFlowBatchResponse => ({
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: 'shares',
  valueUnit: 'VND',
  finality: 'daily_available',
  requestedTickers: tickers,
  normalizedTickers: tickers,
  requestedCount: tickers.length,
  normalizedCount: tickers.length,
  returnedCount: tickers.length,
  usableCount: tickers.length,
  freshCount: tickers.length,
  staleCount: 0,
  emptyCount: 0,
  unavailableCount: 0,
  coverageRatio: 1,
  complete: true,
  dataState: 'ready',
  rows: tickers.map((ticker, index) => makeRow(ticker, index)),
  rankings: {
    latestNetValue: { topBuy: [], topSell: [] },
    netValue5d: { topBuy: [], topSell: [] },
    netValue20d: { topBuy: [], topSell: [] },
  },
  fetchedAt: '2026-07-17T08:00:00Z',
  ...overrides,
});

const renderPage = (url = '/foreign-flow') => {
  window.history.pushState({}, '', url);
  return render(<BrowserRouter><ForeignFlowPage /></BrowserRouter>);
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.history.pushState({}, '', '/foreign-flow');
  mockedBatch.mockImplementation(async (tickers) => makeResponse(tickers));
});

describe('ForeignFlowPage', () => {
  it('renders an empty-watchlist CTA without issuing a request', () => {
    renderPage();

    expect(screen.getByRole('heading', { name: 'Watchlist đang trống' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Mở trang Vietnam/ })).toHaveAttribute('href', '/vietnam');
    expect(mockedBatch).not.toHaveBeenCalled();
  });

  it('loads the current watchlist once and renders summary, rankings, scanner, and no history requests', async () => {
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(['FPT', 'HPG', 'SSI']));
    renderPage();

    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(1));
    expect(mockedBatch).toHaveBeenCalledWith(['FPT', 'HPG', 'SSI'], expect.objectContaining({ topN: 10, forceRefresh: false, signal: expect.any(AbortSignal) }));
    expect(screen.getByText('Tổng quan watchlist')).toBeInTheDocument();
    expect(screen.getByText(/Phiên thị trường:/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Độ rộng watchlist' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Mức độ tập trung' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Bản đồ dòng tiền · Watchlist' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Dòng tiền nổi bật' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Bộ quét watchlist' })).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(4);
    expect(mockedBatch).toHaveBeenCalledTimes(1);
  });

  it('updates URL presentation state without refetching and supports symbol navigation', async () => {
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(['FPT', 'HPG']));
    renderPage('/foreign-flow?window=90&metric=price&direction=sideways');
    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(1));

    expect(screen.getByRole('button', { name: 'Phiên gần nhất' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Giá trị' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: '5 phiên' }));
    fireEvent.click(screen.getByRole('button', { name: 'Khối lượng' }));
    fireEvent.click(screen.getByRole('button', { name: 'Chi tiết' }));
    fireEvent.click(screen.getByRole('button', { name: 'HPG' }));

    expect(window.location.search).toContain('window=5');
    expect(window.location.search).toContain('metric=volume');
    expect(window.location.search).toContain('view=detailed');
    expect(window.location.search).toContain('ticker=HPG');
    expect(screen.getByRole('link', { name: 'Mở chi tiết mã' })).toHaveAttribute('href', '/vietnam/company/HPG');
    expect(mockedBatch).toHaveBeenCalledTimes(1);
  });

  it('restores window state through browser history navigation', async () => {
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(['FPT']));
    renderPage();
    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '5 phiên' }));
    fireEvent.click(screen.getByRole('button', { name: '20 phiên' }));
    expect(screen.getByRole('button', { name: '20 phiên' })).toHaveAttribute('aria-pressed', 'true');

    await act(async () => {
      window.history.back();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    await waitFor(() => expect(screen.getByRole('button', { name: '5 phiên' })).toHaveAttribute('aria-pressed', 'true'));
    expect(mockedBatch).toHaveBeenCalledTimes(1);
  });

  it('shows a visible 30/N notice and sends one capped request', async () => {
    const tickers = Array.from({ length: 32 }, (_, index) => `T${String(index).padStart(2, '0')}`);
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(tickers));
    renderPage('/foreign-flow?view=detailed');

    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(1));
    expect(mockedBatch.mock.calls[0][0]).toHaveLength(30);
    expect(screen.getByText(/Đang hiển thị 30\/32 mã đầu tiên/)).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(31);
  });

  it('renders mixed dates, explicit zero, null cells, and incomplete window coverage honestly', async () => {
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(['FPT', 'HPG']));
    mockedBatch.mockResolvedValue(makeResponse(['FPT', 'HPG'], {
      rows: [
        makeRow('FPT', 0, { foreignNetValue: 0, latestTradingDate: '2026-07-16', foreignNetValue5d: 5_000_000_000, complete5d: false, coveredSessions5d: 3 }),
        makeRow('HPG', 1, { foreignNetValue: null, foreignNetValue5d: null, complete5d: false, coveredSessions5d: 2 }),
      ],
      usableCount: 1,
      coverageRatio: 0.5,
      complete: false,
      dataState: 'partial',
    }));
    renderPage('/foreign-flow?view=detailed');
    await screen.findByText(/Nhiều ngày kết thúc dữ liệu trong watchlist/);

    expect(screen.getAllByText(/1\/2 mã có dữ liệu/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('0').length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText('Không khả dụng').length).toBeGreaterThan(0);
    expect(screen.getByText('3/5 phiên')).toBeInTheDocument();
    expect(screen.queryByText('2/5 phiên')).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/undefined|NaN|Infinity|null\/5|null\/20/);
    expect(screen.getByText(/Một số mã chưa có đủ dữ liệu/)).toBeInTheDocument();
  });

  it('uses selected-window readiness, user-facing finality, clear units, and one active sort column', async () => {
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(['FPT', 'HPG']));
    mockedBatch.mockResolvedValue(makeResponse(['FPT', 'HPG'], {
      rows: [
        makeRow('FPT', 0, { foreignNetValue5d: 5_000_000_000, coveredSessions5d: 3, complete5d: false }),
        makeRow('HPG', 1, { foreignNetValue5d: null, coveredSessions5d: 2, complete5d: false }),
      ],
    }));
    renderPage('/foreign-flow?window=5&view=detailed');

    await screen.findByRole('heading', { name: 'Bộ quét watchlist' });
    expect(screen.getByLabelText(/Nguồn: SSI DailyStockPrice.*daily_available/)).toHaveTextContent('Dữ liệu theo phiên');
    expect(screen.queryByText('daily_available')).not.toBeInTheDocument();
    expect(screen.getByText('2/2 mã · Đơn vị: VND')).toBeInTheDocument();
    expect(screen.getAllByText('Dữ liệu chưa đầy đủ').length).toBeGreaterThan(0);
    expect(screen.getByText('Chưa đủ 5 phiên')).toBeInTheDocument();
    expect(screen.getByText('Thiếu dữ liệu 5 phiên')).toBeInTheDocument();
    const scanner = screen.getByRole('heading', { name: 'Bộ quét watchlist' }).closest('section') as HTMLElement;
    expect(within(scanner).getByRole('columnheader', { name: /NN 5P/ })).toHaveAttribute('aria-sort', 'descending');
    expect(within(scanner).getByRole('columnheader', { name: /^NN ròng/ })).toHaveAttribute('aria-sort', 'none');
    expect(within(scanner).getByRole('columnheader', { name: 'NN mua' })).not.toHaveAttribute('aria-sort');
    expect(within(scanner).getByRole('columnheader', { name: 'NN bán' })).not.toHaveAttribute('aria-sort');
    expect(document.body).not.toHaveTextContent(/undefined|NaN|Infinity|null\/5|null\/20/);
  });

  it('sorts and filters locally without additional requests', async () => {
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(['FPT', 'HPG', 'SSI']));
    renderPage('/foreign-flow?view=detailed');
    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText('Lọc trạng thái dòng tiền'), { target: { value: 'sell' } });
    const scanner = screen.getByRole('heading', { name: 'Bộ quét watchlist' }).closest('section') as HTMLElement;
    expect(within(scanner).getAllByRole('row')).toHaveLength(2);
    fireEvent.click(within(scanner).getByRole('button', { name: 'Sắp xếp theo NN 20P' }));
    expect(window.location.search).toContain('sort=20');
    expect(mockedBatch).toHaveBeenCalledTimes(1);
  });

  it('renders unavailable state with retry and does not fabricate totals', async () => {
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(['FPT']));
    mockedBatch.mockRejectedValue(new Error('provider unavailable'));
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Dữ liệu dòng tiền ngoại chưa khả dụng' })).toBeInTheDocument();
    expect(screen.queryByText('0 VND')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(2));
  });

  it.each([
    ['partial', 'Dữ liệu phiên gần nhất hiện chưa khả dụng'],
    ['stale', 'Dữ liệu gần nhất đã cũ'],
    ['empty', 'SSI DailyStockPrice chưa trả về dòng dữ liệu'],
    ['unavailable', 'Dữ liệu phiên gần nhất hiện chưa khả dụng'],
  ] as const)('shows an honest %s batch state', async (dataState, copy) => {
    window.localStorage.setItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY, JSON.stringify(['FPT']));
    mockedBatch.mockResolvedValue(makeResponse(['FPT'], {
      dataState,
      usableCount: dataState === 'stale' ? 1 : 0,
      freshCount: 0,
      staleCount: dataState === 'stale' ? 1 : 0,
      emptyCount: dataState === 'empty' ? 1 : 0,
      unavailableCount: dataState === 'unavailable' ? 1 : 0,
      coverageRatio: dataState === 'stale' ? 1 : 0,
      complete: false,
      rows: [makeRow('FPT', 0, {
        dataState: dataState === 'partial' ? 'unavailable' : dataState,
        freshness: dataState === 'partial' ? 'unavailable' : dataState,
        foreignNetValue: dataState === 'stale' ? 2_000_000_000 : null,
      })],
    }));

    renderPage();

    expect(await screen.findByText(new RegExp(copy))).toBeInTheDocument();
  });
});
