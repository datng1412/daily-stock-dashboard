import { describe, expect, it, vi } from 'vitest';
import {
  buildForeignFlowCsv,
  explorerDateBounds,
  selectForeignFlowWindow,
  sumNullable,
} from '../foreignFlowExplorerModel';

describe('foreignFlowExplorerModel', () => {
  const rows = Array.from({ length: 65 }, (_, index) => ({
    tradingDate: `2026-05-${String(index + 1).padStart(2, '0')}`,
    net: index === 64 ? 0 : index,
    anomaly: index === 63,
  }));

  it('selects the latest 60 actual returned sessions rather than calendar days', () => {
    const selected = selectForeignFlowWindow(rows, '60', (row) => row.tradingDate, (row) => row.anomaly);
    expect(selected.actualSessionCount).toBe(60);
    expect(selected.rows).toHaveLength(60);
    expect(selected.complete).toBe(true);
    expect(selected.containsProviderAnomaly).toBe(true);
  });

  it('validates inclusive custom bounds and prevents unbounded calls', () => {
    expect(explorerDateBounds('custom', '2026-07-01', '2026-07-01')).toEqual({ fromDate: '2026-07-01', toDate: '2026-07-01' });
    expect(() => explorerDateBounds('custom', '2026-07-02', '2026-07-01')).toThrow(/Start date/);
    expect(() => explorerDateBounds('custom', '2026-01-01', '2026-07-01')).toThrow(/120/);
  });

  it('keeps null distinct from real zero', () => {
    expect(sumNullable([null, undefined])).toBeNull();
    expect(sumNullable([null, 0])).toBe(0);
  });

  it('exports UTF-8 CSV with raw numeric values and selection metadata', () => {
    const csv = buildForeignFlowCsv([{ trading_date: '2026-07-21', net_value: 123456789 }], {
      mode: 'ticker',
      metric: 'value',
      window: '20',
    });
    expect(csv.startsWith('\uFEFF')).toBe(true);
    expect(csv).toContain('selected_mode,selected_metric,selected_window');
    expect(csv).toContain('ticker,value,20,2026-07-21,123456789');
    expect(csv).not.toContain('123.46M');
    vi.restoreAllMocks();
  });
});
