import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { stocksApi, type VietnamRelativeStrengthResponse } from '../../api/stocks';
import { useVietnamRelativeStrength } from '../useVietnamRelativeStrength';

vi.mock('../../api/stocks', () => ({
  stocksApi: { getVietnamRelativeStrength: vi.fn() },
}));

const response = (ticker: string, usable = true): VietnamRelativeStrengthResponse => ({
  status: usable ? 'ready' : 'unavailable', dataState: usable ? 'ready' : 'unavailable', usable,
  ticker, stockSource: 'SSI DailyOhlc', stockSessionCount: 21, historicalConstituentCorrect: false,
  comparisons: {} as VietnamRelativeStrengthResponse['comparisons'], timing: { totalMs: 1 }, diagnostics: {}, fetchedAt: '2026-08-11T00:00:00Z',
});

describe('useVietnamRelativeStrength', () => {
  it('owns one request per ticker and ignores an older ticker response', async () => {
    let resolveFpt!: (value: VietnamRelativeStrengthResponse) => void;
    let resolveHpg!: (value: VietnamRelativeStrengthResponse) => void;
    vi.mocked(stocksApi.getVietnamRelativeStrength)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFpt = resolve; }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveHpg = resolve; }));

    const { result, rerender } = renderHook(({ ticker }) => useVietnamRelativeStrength(ticker), { initialProps: { ticker: 'FPT' } });
    rerender({ ticker: 'HPG' });
    await act(async () => { resolveHpg(response('HPG')); });
    await waitFor(() => expect(result.current.data?.ticker).toBe('HPG'));
    await act(async () => { resolveFpt(response('FPT')); });

    expect(result.current.data?.ticker).toBe('HPG');
    expect(stocksApi.getVietnamRelativeStrength).toHaveBeenCalledTimes(2);
    expect(vi.mocked(stocksApi.getVietnamRelativeStrength).mock.calls.map((call) => call[0])).toEqual(['FPT', 'HPG']);
  });

  it('retains the same ticker after a failed refresh', async () => {
    vi.mocked(stocksApi.getVietnamRelativeStrength).mockResolvedValueOnce(response('FPT'));
    const { result } = renderHook(() => useVietnamRelativeStrength('FPT'));
    await waitFor(() => expect(result.current.data?.ticker).toBe('FPT'));
    vi.mocked(stocksApi.getVietnamRelativeStrength).mockRejectedValueOnce(new Error('refresh unavailable'));
    await act(async () => { await result.current.refresh(); });
    expect(result.current.data?.ticker).toBe('FPT');
    expect(result.current.error).toBe('refresh unavailable');
  });
});
