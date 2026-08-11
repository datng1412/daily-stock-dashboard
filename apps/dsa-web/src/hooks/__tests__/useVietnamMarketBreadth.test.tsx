import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { stocksApi, type VietnamMarketBreadthResponse } from '../../api/stocks';
import { useVietnamMarketBreadth } from '../useVietnamMarketBreadth';

vi.mock('../../api/stocks', () => ({
  stocksApi: { getVietnamMarketBreadth: vi.fn() },
}));

const ready: VietnamMarketBreadthResponse = {
  status: 'ready', dataState: 'ready', usable: true, indexCode: 'VN30', source: 'SSI',
  sourceEndpoint: 'securitiesSummary', aggregationBasis: 'current_vn30_membership_daily_ohlc',
  historicalConstituentCorrect: false, providerSessionDate: '2026-08-07', finality: 'completed_daily', freshness: 'fresh',
  membership: { status: 'ready', source: 'SSI IndexComponents', basis: 'current_vn30_membership', memberCount: 30, symbols: [], duplicateCount: 0, duplicateSymbols: [], invalidCount: 0 },
  direction: { advances: 10, declines: 10, unchanged: 10, usableCount: 30 },
  participation: { ratio: 2 / 3, formula: '(advances + declines) / direction_usable_count' },
  ma20: { aboveCount: 15, notAboveCount: 15, usableCount: 30, percentAbove: 50, formula: 'close > SMA(close, 20)' },
  ma50: { aboveCount: 12, notAboveCount: 18, usableCount: 30, percentAbove: 40, formula: 'close > SMA(close, 50)' },
  coverage: { requestedCount: 30, membershipCount: 30, observedCount: 30, alignedCount: 30, directionUsableCount: 30, ma20UsableCount: 30, ma50UsableCount: 30, missingCount: 0, missingSymbols: [], sessionMismatchCount: 0, sessionMismatchSymbols: [] },
  timing: {}, diagnostics: {}, fetchedAt: '2026-08-07T09:00:00Z',
};

describe('useVietnamMarketBreadth', () => {
  beforeEach(() => vi.mocked(stocksApi.getVietnamMarketBreadth).mockReset());

  it('owns one initial request and retains the last usable result after refresh failure', async () => {
    vi.mocked(stocksApi.getVietnamMarketBreadth).mockResolvedValueOnce(ready);
    const { result } = renderHook(() => useVietnamMarketBreadth());
    await waitFor(() => expect(result.current.data).toBe(ready));
    expect(stocksApi.getVietnamMarketBreadth).toHaveBeenCalledTimes(1);

    vi.mocked(stocksApi.getVietnamMarketBreadth).mockRejectedValueOnce(new Error('refresh unavailable'));
    await act(async () => { await result.current.refresh(); });

    expect(result.current.data).toBe(ready);
    expect(result.current.error).toBe('refresh unavailable');
    expect(stocksApi.getVietnamMarketBreadth).toHaveBeenCalledTimes(2);
  });
});
