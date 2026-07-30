import { describe, expect, it } from 'vitest';
import type { VietnamCurrentForeignFlowResponse } from '../../../api/stocks';
import {
  mapCurrentFlowToSessionDisplayRow,
  mergeCurrentFlowSessionDisplayRow,
} from '../currentForeignFlowTableModel';
import type { SymbolForeignFlowMetricRow } from '../foreignFlowSymbolAnalyticsModel';

const currentResponse = (
  changes: Partial<VietnamCurrentForeignFlowResponse> = {},
): VietnamCurrentForeignFlowResponse => ({
  status: 'ok',
  dataState: 'ready',
  usable: true,
  source: 'SSI FastConnect V3 ForeignRoomMessage',
  providerVersion: 'v3',
  symbol: 'FPT',
  tradingDate: '2026-07-29',
  freshnessStatus: 'ready',
  isCurrentSession: true,
  isProvisional: true,
  current: {
    foreignBuyValue: 125_000_000_000,
    foreignSellValue: 40_000_000_000,
    foreignNetValue: 85_000_000_000,
    foreignBuyVolume: 1_250,
    foreignSellVolume: 400,
    foreignNetVolume: 850,
  },
  streamStatus: 'cache_hit',
  streamReason: '',
  finality: 'current_session_provisional',
  ...changes,
});

const completedRow = (
  tradingDate = '2026-07-28',
): SymbolForeignFlowMetricRow => ({
  tradingDate,
  buy: 10,
  sell: 4,
  net: 6,
  rolling5: 25,
  rolling20: 80,
  cumulative: 80,
  usable: true,
  sign: 'positive',
  state: 'ready',
  unit: 'VND',
});

describe('currentForeignFlowTableModel', () => {
  it('maps provider-backed value and volume fields without rolling calculations', () => {
    const valueRow = mapCurrentFlowToSessionDisplayRow(currentResponse(), 'value');
    const volumeRow = mapCurrentFlowToSessionDisplayRow(currentResponse(), 'volume');

    expect(valueRow).toMatchObject({
      tradingDate: '2026-07-29',
      buy: 125_000_000_000,
      sell: 40_000_000_000,
      net: 85_000_000_000,
      rolling5: null,
      rolling20: null,
      cumulative: null,
      displayOrigin: 'current_session_provisional',
      statusLabel: 'Đang diễn ra',
    });
    expect(volumeRow).toMatchObject({ buy: 1_250, sell: 400, net: 850 });
  });

  it('maps waiting and unavailable to dashes without fabricating zero', () => {
    const waiting = mapCurrentFlowToSessionDisplayRow(currentResponse({
      status: 'unavailable',
      dataState: 'waiting',
      usable: false,
      current: null,
    }), 'value');
    const unavailable = mapCurrentFlowToSessionDisplayRow(currentResponse({
      status: 'unavailable',
      dataState: 'unavailable',
      usable: false,
      current: null,
    }), 'value');

    expect(waiting).toMatchObject({
      buy: null,
      sell: null,
      net: null,
      statusLabel: 'Chờ dữ liệu',
    });
    expect(unavailable).toMatchObject({
      buy: null,
      sell: null,
      net: null,
      statusLabel: 'Không khả dụng',
    });
  });

  it('preserves stale/error values and maps connectivity labels truthfully', () => {
    const stale = mapCurrentFlowToSessionDisplayRow(currentResponse({
      status: 'partial',
      dataState: 'stale',
    }), 'value');
    const errorWithValues = mapCurrentFlowToSessionDisplayRow(currentResponse({
      status: 'partial',
      dataState: 'error',
    }), 'value');
    const errorWithoutValues = mapCurrentFlowToSessionDisplayRow(currentResponse({
      status: 'unavailable',
      dataState: 'error',
      usable: false,
      current: null,
    }), 'value');

    expect(stale?.statusLabel).toBe('Mất kết nối');
    expect(stale?.net).toBe(85_000_000_000);
    expect(errorWithValues?.statusLabel).toBe('Mất kết nối');
    expect(errorWithValues?.net).toBe(85_000_000_000);
    expect(errorWithoutValues).toMatchObject({
      buy: null,
      sell: null,
      net: null,
      statusLabel: 'Không khả dụng',
    });
  });

  it('preserves explicit provider zero separately from missing values', () => {
    const row = mapCurrentFlowToSessionDisplayRow(currentResponse({
      current: {
        foreignBuyValue: 0,
        foreignSellValue: null,
        foreignNetValue: null,
      },
    }), 'value');

    expect(row).toMatchObject({ buy: 0, sell: null, net: null });
  });

  it('requires a contract date and keeps a dated market-closed snapshot truthful', () => {
    expect(mapCurrentFlowToSessionDisplayRow(currentResponse({
      tradingDate: null,
    }), 'value')).toBeNull();
    expect(mapCurrentFlowToSessionDisplayRow(currentResponse({
      tradingDate: '07/29/2026',
    }), 'value')).toBeNull();
    expect(mapCurrentFlowToSessionDisplayRow(currentResponse({
      dataState: 'market_closed',
    }), 'value')).toMatchObject({
      tradingDate: '2026-07-29',
      statusLabel: 'Tạm tính',
    });
  });

  it('keeps a newer post-close row first without adding rolling values', () => {
    const completed = [
      completedRow('2026-07-28'),
      completedRow('2026-07-27'),
    ];
    const before = structuredClone(completed);
    const merged = mergeCurrentFlowSessionDisplayRow(
      completed,
      currentResponse({
        status: 'partial',
        dataState: 'market_closed',
        freshnessStatus: 'market_closed',
      }),
      'value',
    );

    expect(merged.map((row) => row.tradingDate)).toEqual([
      '2026-07-29',
      '2026-07-28',
      '2026-07-27',
    ]);
    expect(merged[0]).toMatchObject({
      displayOrigin: 'current_session_provisional',
      statusLabel: 'Tạm tính',
      buy: 125_000_000_000,
      sell: 40_000_000_000,
      net: 85_000_000_000,
      rolling5: null,
      rolling20: null,
    });
    expect(completed).toEqual(before);
  });

  it('prepends one display row without mutating completed history', () => {
    const completed = [completedRow()];
    const before = structuredClone(completed);
    const merged = mergeCurrentFlowSessionDisplayRow(
      completed,
      currentResponse(),
      'value',
    );

    expect(merged.map((row) => row.tradingDate)).toEqual([
      '2026-07-29',
      '2026-07-28',
    ]);
    expect(completed).toEqual(before);
    expect(merged).not.toBe(completed);
  });

  it('gives an accepted same-date row precedence over the provisional row', () => {
    const accepted = completedRow('2026-07-29');
    const merged = mergeCurrentFlowSessionDisplayRow(
      [accepted],
      currentResponse(),
      'value',
    );

    expect(merged).toHaveLength(1);
    expect(merged[0]).toEqual(accepted);
    expect(merged[0].displayOrigin).toBeUndefined();
    expect(merged[0].statusLabel).toBeUndefined();
  });

  it('gives a newer accepted row precedence over an older provisional row', () => {
    const accepted = completedRow('2026-07-30');
    const merged = mergeCurrentFlowSessionDisplayRow(
      [accepted],
      currentResponse(),
      'value',
    );

    expect(merged).toEqual([accepted]);
  });

  it('uses the latest accepted date even when that row is outside the visible window', () => {
    const visible = completedRow('2026-07-28');
    const merged = mergeCurrentFlowSessionDisplayRow(
      [visible],
      currentResponse(),
      'value',
      '2026-07-29',
    );

    expect(merged).toEqual([visible]);
    expect(merged[0].displayOrigin).toBeUndefined();
  });
});
