import { describe, expect, it } from 'vitest';
import type { VietnamForeignFlowSymbolAnalytics } from '../../../api/stocks';
import { buildSymbolForeignFlowRows, getSymbolForeignFlowMetric } from '../foreignFlowSymbolAnalyticsModel';

describe('foreignFlowSymbolAnalyticsModel', () => {
  it('selects one metric family without converting missing fields to zero', () => {
    expect(getSymbolForeignFlowMetric({ tradingDate: '2026-07-20', foreignBuyValue: 10, foreignSellValue: null, foreignNetValue: null }, 'value')).toMatchObject({ buy: 10, sell: null, net: null, usable: false, sign: 'unavailable', state: 'partial', unit: 'VND' });
  });

  it('uses canonical backend rolling fields, keeps gaps, and slices deterministically', () => {
    const analytics = { rollingSeries: [
      { tradingDate: '2026-07-18', rollingNet5dValue: null, rollingNet20dValue: null },
      { tradingDate: '2026-07-19', rollingNet5dValue: 3, rollingNet20dValue: null },
      { tradingDate: '2026-07-20', rollingNet5dValue: 4, rollingNet20dValue: 7 },
    ] } as VietnamForeignFlowSymbolAnalytics;
    const rows = buildSymbolForeignFlowRows([
      { tradingDate: '2026-07-18', foreignNetValue: 2 },
      { tradingDate: '2026-07-19', foreignNetValue: null },
      { tradingDate: '2026-07-20', foreignNetValue: 5 },
    ], analytics, 'value', 20);
    expect(rows.map((row) => row.cumulative)).toEqual([2, null, 7]);
    expect(rows.map((row) => row.rolling5)).toEqual([null, 3, 4]);
  });
});
