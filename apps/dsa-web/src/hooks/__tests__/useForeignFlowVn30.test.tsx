import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type VietnamVn30ForeignFlowResponse } from '../../api/stocks';
import { useForeignFlowVn30 } from '../useForeignFlowVn30';

vi.mock('../../api/stocks', () => ({
  stocksApi: { getVietnamVn30ForeignFlow: vi.fn() },
}));

const mockedVn30 = vi.mocked(stocksApi.getVietnamVn30ForeignFlow);

const response = (usable: number): VietnamVn30ForeignFlowResponse => ({
  componentCounts: { usable },
} as VietnamVn30ForeignFlowResponse);

beforeEach(() => {
  vi.clearAllMocks();
  mockedVn30.mockResolvedValue(response(2));
});

describe('useForeignFlowVn30', () => {
  it('owns no request while inactive and makes one normal request when activated', async () => {
    const { result, rerender } = renderHook(
      ({ active }) => useForeignFlowVn30(active, 7),
      { initialProps: { active: false } },
    );

    expect(result.current.data).toBeNull();
    expect(mockedVn30).not.toHaveBeenCalled();
    rerender({ active: true });

    await waitFor(() => expect(mockedVn30).toHaveBeenCalledTimes(1));
    expect(mockedVn30).toHaveBeenCalledWith(expect.objectContaining({ topN: 7, forceRefresh: false }));
    await waitFor(() => expect(result.current.data?.componentCounts.usable).toBe(2));
  });

  it('aborts an older request and ignores its late response', async () => {
    let resolveFirst: ((value: VietnamVn30ForeignFlowResponse) => void) | undefined;
    mockedVn30
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce(response(3));
    const { result, rerender } = renderHook(
      ({ topN }) => useForeignFlowVn30(true, topN),
      { initialProps: { topN: 5 } },
    );
    await waitFor(() => expect(mockedVn30).toHaveBeenCalledTimes(1));

    rerender({ topN: 6 });
    await waitFor(() => expect(mockedVn30).toHaveBeenCalledTimes(2));
    expect(mockedVn30.mock.calls[0][0]?.signal?.aborted).toBe(true);
    await waitFor(() => expect(result.current.data?.componentCounts.usable).toBe(3));

    await act(async () => { resolveFirst?.(response(1)); });
    expect(result.current.data?.componentCounts.usable).toBe(3);
  });

  it('retains usable same-scope data when a force refresh returns no usable components', async () => {
    mockedVn30.mockResolvedValueOnce(response(2)).mockResolvedValueOnce(response(0));
    const { result } = renderHook(() => useForeignFlowVn30(true));
    await waitFor(() => expect(result.current.data?.componentCounts.usable).toBe(2));

    await act(async () => { await result.current.forceRefresh(); });

    expect(mockedVn30.mock.calls[1][0]).toMatchObject({ forceRefresh: true });
    expect(result.current.data?.componentCounts.usable).toBe(2);
    expect(result.current.error).toBe('Latest VN30 refresh returned no usable component history.');
  });
});
