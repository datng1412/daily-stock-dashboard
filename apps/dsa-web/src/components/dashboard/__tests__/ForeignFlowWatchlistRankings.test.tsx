import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { VietnamForeignFlowBatchResponse } from '../../../api/stocks';
import { ForeignFlowWatchlistRankings } from '../ForeignFlowWatchlistRankings';


const response = (overrides: Partial<VietnamForeignFlowBatchResponse> = {}): VietnamForeignFlowBatchResponse => ({
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: 'shares',
  valueUnit: 'VND',
  finality: 'daily_available',
  requestedTickers: ['FPT', 'VCB'],
  normalizedTickers: ['FPT', 'VCB'],
  requestedCount: 2,
  normalizedCount: 2,
  returnedCount: 2,
  usableCount: 1,
  freshCount: 1,
  staleCount: 0,
  emptyCount: 0,
  unavailableCount: 1,
  coverageRatio: 0.5,
  complete: false,
  dataState: 'partial',
  rows: [],
  rankings: {
    latestNetValue: {
      topBuy: [{ ticker: 'FPT', value: 2_500_000_000, tradingDate: '2026-07-17', coveredSessions: 1, complete: true, dataState: 'ready' }],
      topSell: [{ ticker: 'VCB', value: -1_200_000_000, tradingDate: '2026-07-17', coveredSessions: 1, complete: true, dataState: 'stale' }],
    },
    netValue5d: {
      topBuy: [{ ticker: 'FPT', value: 5_000_000_000, tradingDate: '2026-07-17', coveredSessions: 3, complete: false, dataState: 'ready' }],
      topSell: [],
    },
    netValue20d: { topBuy: [], topSell: [] },
  },
  fetchedAt: '2026-07-17T10:00:00+00:00',
  ...overrides,
});


describe('ForeignFlowWatchlistRankings', () => {
  it('renders watchlist-scoped buyers, sellers, coverage, stale and navigation states', () => {
    render(<ForeignFlowWatchlistRankings data={response()} totalTickerCount={2} onRetry={vi.fn()} />);

    expect(screen.getByText('Trong watchlist')).toBeInTheDocument();
    expect(screen.getByTestId('foreign-flow-rankings')).toHaveTextContent('1/2 mã có dữ liệu');
    expect(screen.getByText('Top mua ròng trong watchlist')).toBeInTheDocument();
    expect(screen.getByText('Top bán ròng trong watchlist')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'FPT' })).toHaveAttribute('href', '/vietnam/company/FPT');
    expect(screen.getByText('Cũ')).toBeInTheDocument();
  });

  it('switches deterministic ranking windows and marks incomplete coverage', () => {
    render(<ForeignFlowWatchlistRankings data={response()} totalTickerCount={2} onRetry={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: '5 phiên' }));

    expect(screen.getByRole('button', { name: '5 phiên' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('3 phiên')).toBeInTheDocument();
    expect(screen.getByText('Chưa có mã bán ròng trong phạm vi này.')).toBeInTheDocument();
  });

  it('renders honest unavailable state and invokes one retry', () => {
    const onRetry = vi.fn();
    render(<ForeignFlowWatchlistRankings
      data={response({
        dataState: 'unavailable',
        usableCount: 0,
        freshCount: 0,
        unavailableCount: 2,
        coverageRatio: 0,
        rankings: {
          latestNetValue: { topBuy: [], topSell: [] },
          netValue5d: { topBuy: [], topSell: [] },
          netValue20d: { topBuy: [], topSell: [] },
        },
      })}
      totalTickerCount={2}
      onRetry={onRetry}
    />);

    expect(screen.getByText(/Không có giá trị 0 thay thế/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('retains prior data while updating and exposes the 30-symbol bound', () => {
    render(<ForeignFlowWatchlistRankings
      data={response()}
      updating
      error="network"
      totalTickerCount={35}
      onRetry={vi.fn()}
    />);

    expect(screen.getByText('Đang cập nhật; tiếp tục hiển thị dữ liệu gần nhất.')).toBeInTheDocument();
    expect(screen.getByText('Cập nhật chưa khả dụng; đang giữ dữ liệu trước đó.')).toBeInTheDocument();
    expect(screen.getByText('Đang hiển thị dữ liệu dòng tiền ngoại cho 30/35 mã.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'FPT' })).toBeInTheDocument();
  });
});
