import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { VietnamRelativeStrengthComparison, VietnamRelativeStrengthResponse } from '../../../api/stocks';
import { VietnamRelativeStrength } from '../VietnamRelativeStrength';

const comparison = (overrides: Partial<VietnamRelativeStrengthComparison> = {}): VietnamRelativeStrengthComparison => ({
  status: 'ready', usable: true, benchmarkCode: 'VNINDEX', benchmarkName: 'VNINDEX', source: 'SSI indexSummary',
  sourceEndpoint: '/api/v3/data/indexSummary', actualField: 'indexValue', methodology: 'provider_index_value_exact_aligned_sessions',
  peerSymbols: [], windows: {
    '1d': { requestedSessions: 1, status: 'ready', complete: true, startSession: '2026-08-07', endSession: '2026-08-10', stockReturnPct: 2, benchmarkReturnPct: 1, relativePerformancePp: 1, alignedSessionCount: 2, missingPeers: [] },
    '5d': { requestedSessions: 5, status: 'ready', complete: true, startSession: '2026-08-03', endSession: '2026-08-10', stockReturnPct: -1, benchmarkReturnPct: 1, relativePerformancePp: -2, alignedSessionCount: 6, missingPeers: [] },
    '20d': { requestedSessions: 20, status: 'ready', complete: true, startSession: '2026-07-13', endSession: '2026-08-10', stockReturnPct: 0, benchmarkReturnPct: 0, relativePerformancePp: 0, alignedSessionCount: 21, missingPeers: [] },
  },
  ...overrides,
});

const response = (): VietnamRelativeStrengthResponse => ({
  status: 'ready', dataState: 'ready', usable: true, ticker: 'FPT', stockSource: 'SSI DailyOhlc', stockLatestSession: '2026-08-10', stockSessionCount: 55,
  historicalConstituentCorrect: false,
  comparisons: {
    vnindex: comparison(),
    vn30: comparison({ benchmarkCode: 'VN30', benchmarkName: 'VN30' }),
    industry: comparison({ benchmarkCode: '9537', benchmarkName: 'Technology', source: 'SSI DailyOhlc + SSI ICB', sourceEndpoint: 'securitiesSummary + securitiesByBoard?index=VN30', actualField: 'close', methodology: 'current_vn30_icb_equal_weight_peers_excluding_selected', peerMemberCount: 1, peerSymbols: ['HPG'], historicalConstituentCorrect: false, officialSectorIndexReturn: false }),
  },
  timing: { totalMs: 10 }, diagnostics: {}, fetchedAt: '2026-08-11T00:00:00Z',
});

describe('VietnamRelativeStrength', () => {
  it('renders all comparisons, signed pp, exact zero, and underlying returns', () => {
    render(<VietnamRelativeStrength ticker="FPT" data={response()} loading={false} updating={false} error={null} onRefresh={vi.fn()} />);
    expect(screen.getByText('vs VNINDEX')).toBeInTheDocument();
    expect(screen.getByText('vs VN30')).toBeInTheDocument();
    expect(screen.getByText('vs Technology')).toBeInTheDocument();
    const row = screen.getByTestId('relative-strength-row-vnindex');
    expect(within(row).getByText('+1.00pp')).toBeInTheDocument();
    expect(within(row).getByText('-2.00pp')).toBeInTheDocument();
    expect(within(row).getByText('0.00pp')).toBeInTheDocument();
    expect(within(row).getByText('+2.00% / +1.00%')).toBeInTheDocument();
  });

  it('keeps valid short windows while rendering an unavailable 20D as em dash', () => {
    const data = response();
    data.status = 'partial';
    data.dataState = 'partial';
    data.comparisons.vn30.status = 'partial';
    data.comparisons.vn30.windows['20d'] = { requestedSessions: 20, status: 'unavailable', complete: false, alignedSessionCount: 6, missingPeers: [], reason: 'insufficient_aligned_provider_sessions' };
    render(<VietnamRelativeStrength ticker="FPT" data={data} loading={false} updating={false} error={null} onRefresh={vi.fn()} />);
    const row = screen.getByTestId('relative-strength-row-vn30');
    expect(within(row).getByText('+1.00pp')).toBeInTheDocument();
    expect(within(row).getAllByText('—').length).toBeGreaterThan(0);
  });

  it('uses local overflow and contains no recommendation or alpha wording', () => {
    render(<VietnamRelativeStrength ticker="FPT" data={response()} loading={false} updating={false} error={null} onRefresh={vi.fn()} />);
    expect(screen.getByTestId('relative-strength-scroll')).toHaveClass('overflow-x-auto');
    const text = screen.getByTestId('relative-strength').textContent?.toLowerCase() ?? '';
    expect(text).not.toMatch(/\bbuy\b|\bsell\b|alpha|recommendation|target/);
  });
});
