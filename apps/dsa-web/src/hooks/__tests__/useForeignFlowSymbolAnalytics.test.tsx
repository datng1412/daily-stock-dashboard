import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type VietnamForeignFlowSymbolHistoryResponse } from '../../api/stocks';
import { useForeignFlowSymbolAnalytics } from '../useForeignFlowSymbolAnalytics';

vi.mock('../../api/stocks', () => ({ stocksApi: { getVietnamForeignFlowSymbolHistory: vi.fn() } }));
const mockedHistory = vi.mocked(stocksApi.getVietnamForeignFlowSymbolHistory);
const response = (ticker: string) => ({ ticker, rows: [], dataState: 'empty' } as unknown as VietnamForeignFlowSymbolHistoryResponse);

beforeEach(() => { vi.clearAllMocks(); mockedHistory.mockImplementation(async (ticker) => response(ticker)); });

describe('useForeignFlowSymbolAnalytics', () => {
  it('owns no request while closed and exactly one request when opened', async () => {
    const { result, rerender } = renderHook(({ open }) => useForeignFlowSymbolAnalytics('FPT', open), { initialProps: { open: false } });
    expect(mockedHistory).not.toHaveBeenCalled();
    rerender({ open: true });
    await waitFor(() => expect(mockedHistory).toHaveBeenCalledTimes(1));
    expect(mockedHistory).toHaveBeenCalledWith('FPT', expect.objectContaining({ limit: 60, forceRefresh: false, signal: expect.any(AbortSignal) }));
    await waitFor(() => expect(result.current.data?.ticker).toBe('FPT'));
  });

  it('aborts and ignores an older ticker response', async () => {
    let resolveFpt: ((value: VietnamForeignFlowSymbolHistoryResponse) => void) | undefined;
    mockedHistory.mockImplementationOnce(() => new Promise((resolve) => { resolveFpt = resolve; })).mockResolvedValueOnce(response('HPG'));
    const { result, rerender } = renderHook(({ ticker }) => useForeignFlowSymbolAnalytics(ticker, true), { initialProps: { ticker: 'FPT' } });
    await waitFor(() => expect(mockedHistory).toHaveBeenCalledTimes(1));
    rerender({ ticker: 'HPG' });
    await waitFor(() => expect(mockedHistory).toHaveBeenCalledTimes(2));
    expect(mockedHistory.mock.calls[0][1]?.signal?.aborted).toBe(true);
    await waitFor(() => expect(result.current.data?.ticker).toBe('HPG'));
    await act(async () => { resolveFpt?.(response('FPT')); });
    expect(result.current.data?.ticker).toBe('HPG');
  });

  it('keeps same-ticker data visible during an explicit force refresh', async () => {
    let resolveRefresh: ((value: VietnamForeignFlowSymbolHistoryResponse) => void) | undefined;
    mockedHistory.mockResolvedValueOnce(response('VCB')).mockImplementationOnce(() => new Promise((resolve) => { resolveRefresh = resolve; }));
    const { result } = renderHook(() => useForeignFlowSymbolAnalytics('VCB', true));
    await waitFor(() => expect(result.current.data?.ticker).toBe('VCB'));
    act(() => { void result.current.forceRefresh(); });
    await waitFor(() => expect(result.current.updating).toBe(true));
    expect(result.current.data?.ticker).toBe('VCB');
    await act(async () => { resolveRefresh?.(response('VCB')); });
  });
});
