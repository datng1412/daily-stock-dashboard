import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { VietnamMarketBreadthResponse } from '../../../api/stocks';
import { VietnamMarketBreadth } from '../VietnamMarketBreadth';


const response = (overrides: Partial<VietnamMarketBreadthResponse> = {}): VietnamMarketBreadthResponse => ({
  status: 'ready',
  dataState: 'ready',
  usable: true,
  indexCode: 'VN30',
  source: 'SSI',
  sourceEndpoint: 'securitiesSummary',
  aggregationBasis: 'current_vn30_membership_daily_ohlc',
  historicalConstituentCorrect: false,
  providerSessionDate: '2026-08-07',
  finality: 'completed_daily',
  freshness: 'fresh',
  membership: {
    status: 'ready', source: 'SSI IndexComponents', basis: 'current_vn30_membership',
    memberCount: 30, symbols: [], duplicateCount: 0, duplicateSymbols: [], invalidCount: 0,
  },
  direction: { advances: 18, declines: 10, unchanged: 2, usableCount: 30 },
  participation: { ratio: 28 / 30, formula: '(advances + declines) / direction_usable_count' },
  ma20: { aboveCount: 20, notAboveCount: 9, usableCount: 29, percentAbove: 68.9655, formula: 'close > SMA(close, 20)' },
  ma50: { aboveCount: 17, notAboveCount: 10, usableCount: 27, percentAbove: 62.963, formula: 'close > SMA(close, 50)' },
  coverage: {
    requestedCount: 30, membershipCount: 30, observedCount: 30, alignedCount: 30,
    directionUsableCount: 30, ma20UsableCount: 29, ma50UsableCount: 27,
    missingCount: 0, missingSymbols: [], sessionMismatchCount: 0, sessionMismatchSymbols: [],
  },
  timing: {}, diagnostics: {}, fetchedAt: '2026-08-07T09:00:00Z',
  ...overrides,
});

const renderBreadth = (data: VietnamMarketBreadthResponse | null, props = {}) => {
  const onRefresh = vi.fn();
  render(
    <VietnamMarketBreadth
      data={data}
      loading={false}
      updating={false}
      error={null}
      onRefresh={onRefresh}
      {...props}
    />,
  );
  return onRefresh;
};

describe('VietnamMarketBreadth', () => {
  it('shows counts, independent denominators, percentages, session and neutral copy', () => {
    renderBreadth(response());
    const card = screen.getByTestId('vn30-market-breadth');
    expect(within(card).getByText('18 tăng')).toBeInTheDocument();
    expect(within(card).getByText('20 / 29')).toBeInTheDocument();
    expect(within(card).getByText('68.97%')).toBeInTheDocument();
    expect(within(card).getByText('17 / 27')).toBeInTheDocument();
    expect(within(card).getByText('62.96%')).toBeInTheDocument();
    expect(within(card).getByText('93.33%')).toBeInTheDocument();
    expect(within(card).getByText(/Phiên 2026-08-07 · phiên đã hoàn tất/)).toBeInTheDocument();
    expect(card.textContent).not.toMatch(/Bullish|Bearish|Strong Buy|Risk On|Risk Off/);
  });

  it('keeps real zeros distinct from missing percentages', () => {
    renderBreadth(response({
      direction: { advances: 0, declines: 0, unchanged: 30, usableCount: 30 },
      participation: { ratio: 0, formula: '(advances + declines) / direction_usable_count' },
      ma20: { aboveCount: 0, notAboveCount: 0, usableCount: 0, percentAbove: null, formula: 'close > SMA(close, 20)' },
      ma50: { aboveCount: 0, notAboveCount: 0, usableCount: 0, percentAbove: null, formula: 'close > SMA(close, 50)' },
    }));
    expect(screen.getByText('0 tăng')).toBeInTheDocument();
    expect(screen.getByText('0.00%')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(2);
  });

  it('discloses partial coverage and refresh state without blanking data', () => {
    const onRefresh = renderBreadth(response({
      status: 'partial',
      dataState: 'partial',
      coverage: {
        requestedCount: 30, membershipCount: 30, observedCount: 29, alignedCount: 28,
        directionUsableCount: 28, ma20UsableCount: 27, ma50UsableCount: 25,
        missingCount: 2, missingSymbols: ['AAA', 'BBB'], sessionMismatchCount: 1, sessionMismatchSymbols: ['BBB'],
      },
    }), { updating: true, error: 'refresh failed' });
    expect(screen.getByText(/Thiếu 2; lệch phiên 1/)).toBeInTheDocument();
    expect(screen.getByText('Đang cập nhật; giữ kết quả gần nhất.')).toBeInTheDocument();
    expect(screen.getByText('Lần làm mới gần nhất thất bại; đang giữ kết quả dùng được.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Đang cập nhật/ }));
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it('renders typed unavailable membership without fake metrics', () => {
    renderBreadth(response({
      status: 'unavailable', dataState: 'unavailable', usable: false,
      membership: {
        status: 'unavailable', source: 'SSI IndexComponents', basis: 'current_vn30_membership',
        memberCount: 0, symbols: [], duplicateCount: 0, duplicateSymbols: [], invalidCount: 0,
        reason: 'Exact membership unavailable.',
      },
      direction: null, participation: null, ma20: null, ma50: null,
    }));
    expect(screen.getByText('Độ rộng VN30 không khả dụng.')).toBeInTheDocument();
    expect(screen.getByText('Exact membership unavailable.')).toBeInTheDocument();
    expect(screen.queryByText(/tăng/)).not.toBeInTheDocument();
  });
});

