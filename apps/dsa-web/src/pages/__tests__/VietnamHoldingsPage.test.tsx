import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type VietnamChartResponse } from '../../api/stocks';
import { HOLDINGS_KEY, buildHoldingsSnapshot, parseHolding, readHoldings, type Holding } from '../../utils/vietnamHoldings';
import { vietnamTodayIso } from '../../utils/vietnamIntradayPolling';
import VietnamHoldingsPage from '../VietnamHoldingsPage';

vi.mock('../../api/stocks', () => ({ stocksApi: { getVietnamChart: vi.fn() } }));

const chartApi = vi.mocked(stocksApi.getVietnamChart);
const date = '2026-11-02';
const today = '2026-11-03';
const holdings = [{ ticker: 'FPT', shares: 2 }, { ticker: 'SSI', shares: 1 }];
const point = { date, open: 9, high: 12, low: 8, close: 10, volume: 1 };

function chart(symbol: string, overrides: Partial<VietnamChartResponse> = {}): VietnamChartResponse {
  return {
    symbol, timeframe: '1d', range: '6M', status: 'ok', source: 'SSI', actualSource: 'SSI',
    providerVersion: 'v3', endpoint: 'securitiesSummary', fallbackUsed: false,
    diagnostics: { complete: true, freshnessStatus: 'fresh', cacheSource: 'provider' },
    points: [point], ...overrides,
  };
}

const snapshot = (...charts: VietnamChartResponse[]) =>
  buildHoldingsSnapshot(holdings, charts.map((chart) => ({ chart })), today);

function openPage(rows: Holding[] = holdings) {
  localStorage.setItem(HOLDINGS_KEY, JSON.stringify(rows));
  return render(<VietnamHoldingsPage />, { wrapper: MemoryRouter });
}

beforeEach(() => {
  vi.setSystemTime(new Date('2026-11-03T12:00:00Z'));
  localStorage.clear();
  chartApi.mockReset();
});

afterEach(() => vi.useRealTimers());

describe('holdings input and eligibility', () => {
  it('normalizes, validates, deduplicates and caps persisted holdings', () => {
    expect(parseHolding(' fpt.vn ', '0010')).toEqual({ ticker: 'FPT', shares: 10 });
    for (const invalid of [0, -1, 1.5, '1e3', '0x10', Number.MAX_SAFE_INTEGER + 1]) {
      expect(parseHolding('FPT', invalid)).toBeNull();
    }
    expect(parseHolding('VNINDEX', '1')).toBeNull();
    const rows = [null, { ticker: 'FPT', shares: -1 }, ...Array.from({ length: 9 }, (_, i) => ({ ticker: 'AA' + i, shares: i + 1 }))];
    localStorage.setItem(HOLDINGS_KEY, JSON.stringify([rows[2], ...rows]));
    expect(readHoldings()).toEqual(rows.slice(2, 10));
    localStorage.setItem(HOLDINGS_KEY, '{');
    expect(readHoldings()).toEqual([]);
  });

  it('uses Vietnam time and ignores today, future and invalid calendar dates', () => {
    const vnToday = vietnamTodayIso(new Date('2026-11-02T17:00:00Z'));
    const result = snapshot(chart('FPT', {
      latestDate: today,
      points: [{ ...point, date: today }, { ...point, date: '2026-12-02' }, { ...point, date: '2026-10-32' }, point],
    }), chart('SSI'));
    expect(vnToday).toBe(today);
    expect(result.date).toBe(date);
    expect(result.aggregate).toMatchObject({ total: 30, largest: { ticker: 'FPT', value: 20 }, topThreeWeight: 1 });
  });

  it('uses one newest observed prior date across charts even when an older date would give full coverage', () => {
    const older = { ...point, date: '2026-10-30' };
    const result = snapshot(chart('FPT', { points: [older, point] }), chart('SSI', { points: [older] }));
    expect(result.date).toBe(date);
    expect(result.coverage).toBe(1);
    expect(result.rows[1].status).toBe('Exact-date mark missing');
    expect(result.aggregate).toBeNull();
  });

  it.each([
    ['stale cache', { diagnostics: { complete: true, freshnessStatus: 'fresh', cacheSource: 'provider_backed_stale' } }],
    ['stale history', { diagnostics: { complete: true, freshnessStatus: 'stale', cacheSource: 'provider' } }],
    ['missing diagnostics', { diagnostics: undefined }],
    ['incomplete history', { diagnostics: { complete: false, freshnessStatus: 'fresh', cacheSource: 'provider' } }],
    ['fallback', { fallbackUsed: true }],
    ['wrong symbol', { symbol: 'VCB' }],
    ['wrong range', { range: '1M' }],
    ['wrong version', { providerVersion: 'v2' }],
    ['conflicting source', { source: 'Mozyfin' }],
    ['null close', { points: [{ ...point, close: null }] }],
    ['zero volume', { points: [{ ...point, volume: 0 }] }],
    ['invalid high', { points: [{ ...point, high: 8 }] }],
    ['duplicate marks', { points: [point, point] }],
  ])('suppresses aggregates for %s', (scenario, fields) => {
    expect(snapshot(chart('FPT'), chart('SSI', fields)).aggregate, scenario).toBeNull();
  });

  it('ranks four holdings by value and uses the whole eligible denominator', () => {
    const rows = [...holdings, { ticker: 'VCB', shares: 3 }, { ticker: 'HPG', shares: 4 }];
    const results = rows.map(({ ticker }) => ({ chart: chart(ticker) }));
    const result = buildHoldingsSnapshot(rows, results, today);
    expect(result.aggregate).toMatchObject({ total: 100, largest: { ticker: 'HPG' }, topThreeWeight: 0.9 });
  });
});

describe('holdings snapshot page', () => {
  it('saves edits locally and rejects duplicate normalized tickers without requesting charts', () => {
    const page = openPage();
    fireEvent.change(screen.getByLabelText('VN equity ticker'), { target: { value: 'fpt.vn' } });
    fireEvent.change(screen.getByLabelText('Whole shares'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add holding' }));
    expect(screen.getByRole('alert')).toHaveTextContent('already in your holdings');
    fireEvent.click(screen.getByRole('button', { name: 'Edit FPT' }));
    fireEvent.change(screen.getByLabelText('Whole shares'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save shares' }));
    page.unmount();
    render(<VietnamHoldingsPage />, { wrapper: MemoryRouter });
    expect(screen.getByText(/3 shares/)).toBeVisible();
    expect(chartApi).not.toHaveBeenCalled();
  });

  it('loads on demand, binds confirmation to the observed date, and separates the previous result after failure', async () => {
    chartApi.mockImplementation(async (symbol) => chart(symbol));
    openPage();
    expect(chartApi).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Load snapshot' }));
    const confirm = await screen.findByRole('button', { name: 'Confirm shares for ' + date });
    expect(screen.queryByText('Total value')).not.toBeInTheDocument();
    fireEvent.click(confirm);
    expect(screen.getByText('30 VND')).toBeVisible();
    expect(screen.getByText('FPT · 66.7%')).toBeVisible();
    expect(chartApi.mock.calls.map(([symbol, range]) => [symbol, range])).toEqual([['FPT', '6M'], ['SSI', '6M']]);

    chartApi.mockImplementation(async (symbol) => {
      if (symbol === 'SSI') throw new Error('network');
      return chart(symbol);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh snapshot' }));
    expect(screen.getByText('Previous confirmed snapshot · ' + date)).toBeVisible();
    expect(await screen.findByText('Request failed')).toBeVisible();
    const current = screen.getAllByRole('region', { name: 'Holding values table' })[0];
    expect(within(current).queryByText('66.7%')).not.toBeInTheDocument();
    expect(screen.getByText('Coverage is incomplete. Total value and weights are unavailable.')).toBeVisible();
  });

  it('limits eight-position loads to two workers and discards an aborted batch before replacement', async () => {
    const pending: Array<() => void> = [];
    chartApi.mockImplementation((symbol) => new Promise((resolve) => {
      pending.push(() => resolve(chart(symbol)));
    }));
    openPage(['FPT', 'SSI', 'VCB', 'HPG', 'VNM', 'MWG', 'SHS', 'ACV'].map((ticker) => ({ ticker, shares: 1 })));
    expect(screen.getByRole('button', { name: 'Add holding' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Load snapshot' }));
    expect(chartApi).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole('button', { name: 'Remove VCB' }));
    expect(chartApi.mock.calls[0][2]?.signal?.aborted).toBe(true);
    expect(screen.getByRole('button', { name: 'Loading daily charts…' })).toBeDisabled();
    await act(async () => pending.splice(0).forEach((finish) => finish()));
    expect(chartApi).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('button', { name: /Confirm shares/ })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('VN equity ticker'), { target: { value: 'VCB' } });
    fireEvent.change(screen.getByLabelText('Whole shares'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add holding' }));
    fireEvent.click(screen.getByRole('button', { name: 'Load snapshot' }));
    expect(pending).toHaveLength(2);
    while (pending.length) {
      await act(async () => pending.splice(0).forEach((finish) => finish()));
      expect(pending.length).toBeLessThanOrEqual(2);
    }
    await waitFor(() => expect(chartApi).toHaveBeenCalledTimes(10));
    expect(screen.getByRole('status')).toHaveTextContent('8/8 eligible');
    fireEvent.click(screen.getByRole('button', { name: 'Clear holdings' }));
    expect(localStorage.getItem(HOLDINGS_KEY)).toBeNull();
    expect(chartApi).toHaveBeenCalledTimes(10);
  });
});

