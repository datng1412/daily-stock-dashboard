import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { VietnamForeignFlowSignals } from '../../../api/stocks';
import { ForeignFlowSignalsBlock } from '../ForeignFlowSignals';
import { foreignFlowSignalLabel } from '../foreignFlowSignalModel';

const signals = (): VietnamForeignFlowSignals => ({
  basis: 'foreign_net_value',
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  finality: 'daily_available',
  latestCompletedDate: '2026-08-07',
  direction1d: { state: 'distributing', netValue: -23_090_000_000, requestedSessions: 1, observedSessions: 1, coveredSessions: 1, complete: true },
  direction5d: { state: 'accumulating', netValue: 41_700_000_000, requestedSessions: 5, observedSessions: 5, coveredSessions: 5, complete: true },
  direction20d: { state: 'unavailable', netValue: null, requestedSessions: 20, observedSessions: 18, coveredSessions: 18, complete: false },
  momentum: { state: 'decelerating', requestedSessions: 10, observedSessions: 10, coveredSessions: 10, complete: true, recent5Average: 8_340_000_000, previous5Average: 12_550_000_000 },
  reversal: { detected: true, fromDirection: 'accumulating', toDirection: 'distributing', previousDate: '2026-08-06', currentDate: '2026-08-07', previousValue: 2, currentValue: -3 },
  intensity: { state: 'elevated', absolutePercentile60d: 94.2, zScore60d: -2.1, sampleCount60d: 60, thresholdBasis: ['absolute_percentile_60d_gte_90'] },
});

describe('ForeignFlowSignalsBlock', () => {
  it('renders completed value signals with coverage and numeric formula inputs', () => {
    render(<ForeignFlowSignalsBlock signals={signals()} />);
    const block = screen.getByLabelText('Tín hiệu dòng tiền ngoại');

    expect(within(block).getByText('Phân phối')).toBeInTheDocument();
    expect(within(block).getByText('Tích lũy')).toBeInTheDocument();
    expect(within(block).getByText('Không đủ dữ liệu')).toBeInTheDocument();
    expect(within(block).getByText('Chậm lại')).toBeInTheDocument();
    expect(within(block).getByText('Bất thường cao')).toBeInTheDocument();
    expect(within(block).getByText('18/20 phiên · chưa đủ')).toBeInTheDocument();
    expect(within(block).getByText(/Gần nhất.*8\.34/)).toBeInTheDocument();
    expect(within(block).getByText(/Trước đó.*12\.55/)).toBeInTheDocument();
    expect(within(block).getByText('Percentile tuyệt đối 94.20%')).toBeInTheDocument();
    expect(block).toHaveTextContent('Mô tả, không dự báo');
    expect(block).not.toHaveTextContent(/Nên mua|Nên bán|Bullish|Bearish/i);
  });

  it('maps every canonical machine state to neutral Vietnamese copy', () => {
    expect([
      'accumulating', 'distributing', 'neutral', 'unavailable',
      'accelerating', 'decelerating', 'stable', 'reversal', 'elevated', 'normal',
    ].map((state) => foreignFlowSignalLabel(state as Parameters<typeof foreignFlowSignalLabel>[0]))).toEqual([
      'Tích lũy', 'Phân phối', 'Trung tính', 'Không đủ dữ liệu',
      'Gia tốc', 'Chậm lại', 'Ổn định', 'Đảo chiều', 'Bất thường cao', 'Bình thường',
    ]);
  });

  it('does not format a non-finite z-score', () => {
    const payload = signals();
    payload.intensity.zScore60d = Number.NaN;

    render(<ForeignFlowSignalsBlock signals={payload} />);

    expect(screen.getByRole('region')).not.toHaveTextContent('z-score');
  });
});
