import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { stocksApi, type VietnamSectorStrengthResponse } from '../../api/stocks';
import { useVietnamSectorStrength } from '../useVietnamSectorStrength';

vi.mock('../../api/stocks', () => ({
  stocksApi: { getVietnamSectorStrength: vi.fn() },
}));

const response = (usable = true): VietnamSectorStrengthResponse => ({
  status: usable ? 'ready' : 'unavailable', dataState: usable ? 'ready' : 'unavailable', usable,
  indexCode: 'VN30', universe: 'current_vn30_membership', source: 'SSI',
  membershipSource: 'SSI IndexComponents', classificationSource: 'SSI ICB', priceSource: 'SSI DailyOhlc',
  foreignFlowSource: 'SSI DailyStockPrice', aggregationBasis: 'current_vn30_icb_equal_weight',
  historicalConstituentCorrect: false, officialSectorIndexReturn: false, priceFinality: 'completed_daily',
  membership: { requestedCount: 30, memberCount: 30, classifiedCount: 30, unclassifiedCount: 0, unclassifiedSymbols: [], groupCount: 1, duplicateSymbols: [], symbols: [] },
  groups: usable ? [{} as VietnamSectorStrengthResponse['groups'][number]] : [], timing: {}, diagnostics: {}, fetchedAt: '2026-08-11T00:00:00Z',
});

describe('useVietnamSectorStrength', () => {
  it('owns one initial request and retains usable data after a failed refresh', async () => {
    vi.mocked(stocksApi.getVietnamSectorStrength).mockResolvedValueOnce(response());
    const { result } = renderHook(() => useVietnamSectorStrength());
    await waitFor(() => expect(result.current.data?.usable).toBe(true));
    expect(stocksApi.getVietnamSectorStrength).toHaveBeenCalledTimes(1);
    expect(vi.mocked(stocksApi.getVietnamSectorStrength).mock.calls[0]?.[0]?.forceRefresh).toBe(false);

    vi.mocked(stocksApi.getVietnamSectorStrength).mockRejectedValueOnce(new Error('refresh unavailable'));
    await act(async () => { await result.current.refresh(); });

    expect(result.current.data?.usable).toBe(true);
    expect(result.current.error).toBe('refresh unavailable');
    expect(stocksApi.getVietnamSectorStrength).toHaveBeenCalledTimes(2);
  });
});
