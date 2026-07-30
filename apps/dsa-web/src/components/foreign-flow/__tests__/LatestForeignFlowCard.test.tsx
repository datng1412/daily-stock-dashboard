import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import LatestForeignFlowCard from '../LatestForeignFlowCard';
import type { LatestForeignFlowSessionView } from '../latestForeignFlowSessionModel';

const view = (
  changes: Partial<LatestForeignFlowSessionView> = {},
): LatestForeignFlowSessionView => ({
  sessionDate: '2026-07-29',
  sourceKind: 'current',
  source: 'SSI FastConnect V3 ForeignRoomMessage',
  finality: 'current_session_provisional',
  status: 'Đang diễn ra',
  foreignBuyVolume: 1_250,
  foreignSellVolume: 400,
  foreignNetVolume: 850,
  foreignBuyValue: 125_000_000,
  foreignSellValue: 40_000_000,
  foreignNetValue: 85_000_000,
  providerTime: '2026/07/29 10:08:00',
  receiptTime: '2026-07-29T03:08:01Z',
  isCurrentSession: true,
  isCompleted: false,
  ...changes,
});

describe('LatestForeignFlowCard', () => {
  it('renders one latest-session current view with short status and six metrics', () => {
    render(<LatestForeignFlowCard view={view()} />);

    const card = screen.getByTestId('latest-foreign-flow-card');
    expect(within(card).getByRole('heading', { name: 'Foreign flow' })).toBeInTheDocument();
    expect(within(card).queryByText('Current-session foreign flow')).not.toBeInTheDocument();
    expect(within(card).getByText('Đang diễn ra')).toBeInTheDocument();
    expect(within(card).getByText(/Session: 2026-07-29/)).toBeInTheDocument();
    expect(within(card).getByText('Foreign buy volume (shares)')).toBeInTheDocument();
    expect(within(card).getByText('Foreign net value (VND)')).toBeInTheDocument();
    expect(within(card).getByText('Provider time: 2026/07/29 10:08:00')).toBeInTheDocument();
  });

  it('renders a completed session with completed status and no current metadata', () => {
    render(<LatestForeignFlowCard view={view({
      sessionDate: '2026-07-28',
      sourceKind: 'completed',
      source: 'SSI DailyStockPrice',
      finality: 'completed_accepted',
      status: 'Đủ',
      providerTime: null,
      receiptTime: null,
      isCurrentSession: false,
      isCompleted: true,
    })} />);

    expect(screen.getByText('Đủ')).toBeInTheDocument();
    expect(screen.getByText(/Dữ liệu phiên đã hoàn tất/)).toBeInTheDocument();
    expect(screen.queryByText(/Provider time:/)).not.toBeInTheDocument();
  });

  it('renders a retained post-close snapshot as provisional', () => {
    render(<LatestForeignFlowCard view={view({ status: 'Tạm tính' })} />);

    const card = screen.getByTestId('latest-foreign-flow-card');
    expect(within(card).getByText('Tạm tính')).toBeInTheDocument();
    expect(within(card).getByText(/Session: 2026-07-29/)).toBeInTheDocument();
    expect(within(card).getByText('+85.0M')).toBeInTheDocument();
    expect(within(card).getByText('Provider time: 2026/07/29 10:08:00')).toBeInTheDocument();
  });

  it('keeps explicit zero distinct from missing values', () => {
    render(<LatestForeignFlowCard view={view({
      status: 'Chờ dữ liệu',
      foreignBuyVolume: 0,
      foreignSellVolume: null,
      foreignNetVolume: null,
      foreignBuyValue: 0,
      foreignSellValue: null,
      foreignNetValue: null,
    })} />);

    const card = screen.getByTestId('latest-foreign-flow-card');
    expect(within(card).getAllByText('0')).toHaveLength(2);
    expect(within(card).getAllByText('—')).toHaveLength(4);
    expect(within(card).getByText('Chờ dữ liệu')).toBeInTheDocument();
  });

  it('renders one unavailable card when neither source has a safe session', () => {
    render(<LatestForeignFlowCard view={null} />);

    expect(screen.getByRole('heading', { name: 'Foreign flow' })).toBeInTheDocument();
    expect(screen.getByText('Không khả dụng')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(6);
  });
});
