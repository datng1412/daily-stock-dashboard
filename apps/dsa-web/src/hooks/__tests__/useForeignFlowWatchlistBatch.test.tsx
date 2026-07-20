import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type VietnamForeignFlowBatchResponse } from '../../api/stocks';
import { useForeignFlowWatchlistBatch } from '../useForeignFlowWatchlistBatch';

vi.mock('../../api/stocks', () => ({
  stocksApi: { getVietnamForeignFlowBatch: vi.fn() },
}));

const mockedBatch = vi.mocked(stocksApi.getVietnamForeignFlowBatch);

const response = (tickers: string[], usableCount = tickers.length): VietnamForeignFlowBatchResponse => ({
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
  usableCount,
  freshCount: usableCount,
  staleCount: 0,
  emptyCount: 0,
  unavailableCount: tickers.length - usableCount,
  coverageRatio: tickers.length ? usableCount / tickers.length : 0,
  complete: usableCount === tickers.length,
  dataState: usableCount ? 'ready' : 'unavailable',
  rows: [],
  rankings: {
    latestNetValue: { topBuy: [], topSell: [] },
    netValue5d: { topBuy: [], topSell: [] },
    netValue20d: { topBuy: [], topSell: [] },
  },
  fetchedAt: '2026-07-17T08:00:00Z',
});

beforeEach(() => {
  vi.clearAllMocks();
  mockedBatch.mockImplementation(async (tickers) => response(tickers));
});

describe('useForeignFlowWatchlistBatch', () => {
  it('makes no request for an empty scope and normalizes, deduplicates, and caps a populated scope', async () => {
    const { result, rerender } = renderHook(
      ({ tickers }) => useForeignFlowWatchlistBatch(tickers, { topN: 10 }),
      { initialProps: { tickers: [] as string[] } },
    );

    expect(mockedBatch).not.toHaveBeenCalled();
    const tickers = Array.from({ length: 32 }, (_, index) => `T${String(index).padStart(2, '0')}`);
    rerender({ tickers: [' fpt.vn ', 'FPT', ...tickers] });

    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(1));
    expect(mockedBatch.mock.calls[0][0]).toHaveLength(30);
    expect(mockedBatch.mock.calls[0][0].slice(0, 2)).toEqual(['FPT', 'T00']);
    expect(mockedBatch.mock.calls[0][1]).toMatchObject({ topN: 10, forceRefresh: false });
    expect(result.current.scope).toMatchObject({ totalNormalizedCount: 33, limited: true });
  });

  it('aborts an older scope and ignores its late response', async () => {
    let resolveFirst: ((value: VietnamForeignFlowBatchResponse) => void) | undefined;
    mockedBatch
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockImplementationOnce(async (tickers) => response(tickers));
    const { result, rerender } = renderHook(
      ({ tickers }) => useForeignFlowWatchlistBatch(tickers),
      { initialProps: { tickers: ['FPT'] } },
    );
    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(1));

    rerender({ tickers: ['HPG'] });
    await waitFor(() => expect(mockedBatch).toHaveBeenCalledTimes(2));
    expect(mockedBatch.mock.calls[0][1]?.signal?.aborted).toBe(true);
    await waitFor(() => expect(result.current.data?.normalizedTickers).toEqual(['HPG']));

    await act(async () => { resolveFirst?.(response(['FPT'])); });
    expect(result.current.data?.normalizedTickers).toEqual(['HPG']);
  });

  it('retains successful same-scope data when refresh returns no usable rows', async () => {
    mockedBatch
      .mockImplementationOnce(async (tickers) => response(tickers))
      .mockImplementationOnce(async (tickers) => response(tickers, 0));
    const { result } = renderHook(() => useForeignFlowWatchlistBatch(['FPT']));
    await waitFor(() => expect(result.current.data?.usableCount).toBe(1));

    await act(async () => { await result.current.refresh(); });

    expect(result.current.data?.usableCount).toBe(1);
    expect(result.current.error).toBe('Latest foreign-flow refresh returned no usable rows.');
  });
});
