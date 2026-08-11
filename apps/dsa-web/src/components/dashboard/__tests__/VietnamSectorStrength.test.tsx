import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { VietnamSectorStrengthGroup, VietnamSectorStrengthResponse } from '../../../api/stocks';
import { VietnamSectorStrength } from '../VietnamSectorStrength';

const group = (overrides: Partial<VietnamSectorStrengthGroup> = {}): VietnamSectorStrengthGroup => ({
  icbCode: '8300', icbName: 'Banks', memberSymbols: ['ACB', 'VCB'], memberCount: 2, dataState: 'partial',
  return1D: { value: 0.01, usableCount: 2, missingCount: 0, method: 'equal_weight_mean_member_close_return' },
  direction: { advances: 1, declines: 1, unchanged: 0, usableCount: 2 },
  ma20: { aboveCount: 1, notAboveCount: 1, usableCount: 2, percentAbove: 50 },
  ma50: { aboveCount: 2, notAboveCount: 0, usableCount: 2, percentAbove: 100 },
  foreignFlow: {
    source: 'SSI DailyStockPrice', finality: 'completed_accepted', latestCompletedDate: '2026-08-10',
    windows: {
      '1': { requestedSessions: 1, requestedMemberCount: 2, usableMemberCount: 2, missingMemberCount: 0, usableSymbols: ['ACB', 'VCB'], coverageRatio: 1, complete: true, netValue: 0, startDate: '2026-08-10', endDate: '2026-08-10', observedStartDates: ['2026-08-10'], observedEndDates: ['2026-08-10'] },
      '5': { requestedSessions: 5, requestedMemberCount: 2, usableMemberCount: 2, missingMemberCount: 0, usableSymbols: ['ACB', 'VCB'], coverageRatio: 1, complete: true, netValue: -2_000_000_000, startDate: '2026-08-04', endDate: '2026-08-10', observedStartDates: ['2026-08-04'], observedEndDates: ['2026-08-10'] },
      '20': { requestedSessions: 20, requestedMemberCount: 2, usableMemberCount: 0, missingMemberCount: 2, usableSymbols: [], coverageRatio: 0, complete: false, netValue: null, observedStartDates: [], observedEndDates: [] },
    },
  },
  ...overrides,
});

const response = (groups = [group()]): VietnamSectorStrengthResponse => ({
  status: 'partial', dataState: 'partial', usable: true, indexCode: 'VN30', universe: 'current_vn30_membership', source: 'SSI',
  membershipSource: 'SSI IndexComponents', classificationSource: 'SSI ICB', priceSource: 'SSI DailyOhlc', foreignFlowSource: 'SSI DailyStockPrice',
  aggregationBasis: 'current_vn30_icb_equal_weight', historicalConstituentCorrect: false, officialSectorIndexReturn: false,
  priceSessionDate: '2026-08-11', priceFinality: 'completed_daily', foreignFlowLatestCompletedDate: '2026-08-10',
  membership: { requestedCount: 30, memberCount: 30, classifiedCount: 29, unclassifiedCount: 1, unclassifiedSymbols: ['UNK'], groupCount: groups.length, duplicateSymbols: [], symbols: [] },
  groups, timing: {}, diagnostics: {}, fetchedAt: '2026-08-11T00:00:00Z',
});

describe('VietnamSectorStrength', () => {
  it('renders signed, zero, missing and independent coverage truthfully', () => {
    render(<VietnamSectorStrength data={response()} loading={false} updating={false} error={null} onRefresh={vi.fn()} />);
    const row = screen.getByTestId('sector-row');
    expect(within(row).getByText('+1.00%')).toBeInTheDocument();
    expect(within(row).getByText('1/2')).toBeInTheDocument();
    expect(within(row).getByText('2/2')).toBeInTheDocument();
    expect(within(row).getByText('0')).toBeInTheDocument();
    expect(within(row).getByText('-2.0B')).toBeInTheDocument();
    expect(within(row).getByText('—')).toBeInTheDocument();
    expect(screen.getByText(/chưa phân loại: UNK/i)).toBeInTheDocument();
  });

  it('sorts locally without requesting data', () => {
    const onRefresh = vi.fn();
    render(<VietnamSectorStrength data={response([
      group({ icbCode: '1', icbName: 'Banks', ma20: { aboveCount: 1, notAboveCount: 1, usableCount: 2, percentAbove: 50 } }),
      group({ icbCode: '2', icbName: 'Technology', ma20: { aboveCount: 2, notAboveCount: 0, usableCount: 2, percentAbove: 100 } }),
    ])} loading={false} updating={false} error={null} onRefresh={onRefresh} />);
    fireEvent.click(screen.getByRole('button', { name: '>MA20' }));
    const rows = screen.getAllByTestId('sector-row');
    expect(within(rows[0]).getByText('Technology')).toBeInTheDocument();
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it('keeps table scrolling local and shows unavailable state', () => {
    const { rerender } = render(<VietnamSectorStrength data={response()} loading={false} updating={false} error={null} onRefresh={vi.fn()} />);
    expect(screen.getByTestId('sector-table-scroll')).toHaveClass('overflow-x-auto');
    rerender(<VietnamSectorStrength data={null} loading={false} updating={false} error="provider unavailable" onRefresh={vi.fn()} />);
    expect(screen.getByText('Dữ liệu ngành VN30 không khả dụng.')).toBeInTheDocument();
    expect(screen.getByText('provider unavailable')).toBeInTheDocument();
  });
});
