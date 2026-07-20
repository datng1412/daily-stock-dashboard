import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { VietnamForeignFlowAnalyticsFamily, VietnamForeignFlowSymbolHistoryResponse } from '../../../api/stocks';
import { ForeignFlowSymbolAnalyticsPanel } from '../ForeignFlowSymbolAnalyticsPanel';

const family = (): VietnamForeignFlowAnalyticsFamily => ({
  latest: { value: 20, tradingDate: '2026-07-20' },
  windows: Object.fromEntries(([5, 20, 60] as const).map((requestedSessions) => [String(requestedSessions), {
    requestedSessions, observedSessions: 1, coveredSessions: 1, complete: false, startDate: '2026-07-20', endDate: '2026-07-20', netSum: 20,
    averageNet: 20, averageAbsoluteNet: 20, netBuySessionCount: 1, netSellSessionCount: 0, zeroSessionCount: 0, unavailableSessionCount: 0,
    maxNetBuy: { value: 20, tradingDate: '2026-07-20' }, maxNetSell: null,
  }])) as VietnamForeignFlowAnalyticsFamily['windows'],
  currentStreak: { direction: 'net_buy', sessions: 1, startDate: '2026-07-20', endDate: '2026-07-20', basis: 'accepted_provider_rows' },
  latestReversal: null,
  comparison: { latestValue: 20, sampleCount20d: 1, sampleCount60d: 1, unusualFlowState: 'unavailable', unusualFlowBasis: ['insufficient_finite_history'] },
});

const data = {
  ticker: 'FPT', source: 'ssi_fastconnect', sourceEndpoint: 'daily_stock_price', finality: 'daily_available', dataState: 'ready', freshness: 'fresh',
  rows: [{ tradingDate: '2026-07-20', foreignBuyValue: 100, foreignSellValue: 80, foreignNetValue: 20, foreignBuyVolume: 10, foreignSellVolume: 8, foreignNetVolume: 2 }],
  latestRow: { tradingDate: '2026-07-20', foreignBuyValue: 100, foreignSellValue: 80, foreignNetValue: 20 }, coverage: { coveredSessions: 1, startDate: '2026-07-20', endDate: '2026-07-20' },
  analytics: { observedSessions: 1, value: family(), volume: family(), rollingSeries: [{ tradingDate: '2026-07-20', rollingNet5dValue: null, rollingNet20dValue: null }] },
} as VietnamForeignFlowSymbolHistoryResponse;

describe('ForeignFlowSymbolAnalyticsPanel', () => {
  it('renders summary, analytics, chart, and history table while controls stay local', () => {
    const onMetricChange = vi.fn(); const onRangeChange = vi.fn(); const onModeChange = vi.fn(); const onWindowChange = vi.fn();
    render(<ForeignFlowSymbolAnalyticsPanel ticker="FPT" data={data} loading={false} updating={false} error={null} metric="value" range={60} mode="net" window="latest" onMetricChange={onMetricChange} onRangeChange={onRangeChange} onModeChange={onModeChange} onWindowChange={onWindowChange} onRetry={vi.fn()} onForceRefresh={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole('heading', { name: 'Phân tích dòng tiền ngoại · FPT' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Lịch sử theo phiên' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Chi tiết phiên' })).toBeInTheDocument();
    expect(screen.getByText('Mua ròng 1 phiên')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Khối lượng' }));
    fireEvent.click(screen.getByRole('button', { name: '40 phiên' }));
    fireEvent.click(screen.getByRole('button', { name: 'Rolling' }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Cửa sổ tóm tắt mã' })).getByRole('button', { name: '20 phiên' }));
    expect(onMetricChange).toHaveBeenCalledWith('volume'); expect(onRangeChange).toHaveBeenCalledWith(40); expect(onModeChange).toHaveBeenCalledWith('rolling'); expect(onWindowChange).toHaveBeenCalledWith('20');
  });

  it('renders unavailable without fake numeric cards', () => {
    render(<ForeignFlowSymbolAnalyticsPanel ticker="FPT" data={null} loading={false} updating={false} error="network" metric="value" range={60} mode="net" window="latest" onMetricChange={vi.fn()} onRangeChange={vi.fn()} onModeChange={vi.fn()} onWindowChange={vi.fn()} onRetry={vi.fn()} onForceRefresh={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Không thể tải lịch sử dòng tiền ngoại cho FPT.');
    expect(screen.queryByText('NN ròng')).not.toBeInTheDocument();
  });
});
