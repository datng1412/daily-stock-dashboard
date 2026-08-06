import { describe, expect, it } from 'vitest';
import type { VietnamCurrentForeignFlowResponse } from '../../../api/stocks';
import {
  selectForeignFlowDisplayStatus,
  selectLatestForeignFlowSession,
  type CompletedForeignFlowSessionInput,
} from '../latestForeignFlowSessionModel';

const completed = (
  changes: Partial<CompletedForeignFlowSessionInput> = {},
): CompletedForeignFlowSessionInput => ({
  sessionDate: '2026-07-28',
  source: 'SSI DailyStockPrice',
  foreignBuyVolume: 1_000,
  foreignSellVolume: 400,
  foreignNetVolume: 600,
  foreignBuyValue: 100_000_000,
  foreignSellValue: 40_000_000,
  foreignNetValue: 60_000_000,
  ...changes,
});

const current = (
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
    foreignBuyVolume: 1_250,
    foreignSellVolume: 400,
    foreignNetVolume: 850,
    foreignBuyValue: 125_000_000,
    foreignSellValue: 40_000_000,
    foreignNetValue: 85_000_000,
    totalRoom: 9_000,
    currentRoom: 8_000,
    streamTimestamp: '2026/07/29 10:08:00',
    receivedAt: '2026-07-29T03:08:01Z',
  },
  streamStatus: 'cache_hit',
  streamReason: '',
  finality: 'current_session_provisional',
  ...changes,
});

describe('selectForeignFlowDisplayStatus', () => {
  it.each([
    [{ sourceKind: 'completed', finality: 'completed_accepted' }, 'Đủ'],
    [{ sourceKind: 'current', finality: 'current_session_provisional', currentState: 'ready', usable: true }, 'Đang diễn ra'],
    [{ sourceKind: 'current', finality: 'current_session_provisional', currentState: 'stale', usable: true }, 'Mất kết nối'],
    [{ sourceKind: 'current', finality: 'current_session_provisional', currentState: 'ready', providerStatus: 'disconnected', usable: true }, 'Mất kết nối'],
    [{ sourceKind: 'current', finality: 'current_session_provisional', currentState: 'market_closed', usable: true }, 'Tạm tính'],
    [{ sourceKind: 'current', finality: 'current_session_provisional', currentState: 'waiting', usable: false }, 'Chờ dữ liệu'],
    [{ sourceKind: 'current', finality: 'current_session_provisional', currentState: 'unavailable', usable: false }, 'Không khả dụng'],
    [{ sourceKind: 'current', finality: 'current_session_provisional', usable: true, hasUsableValues: true }, 'Không khả dụng'],
  ] as const)('maps %o to %s without using numeric coverage', (input, expected) => {
    expect(selectForeignFlowDisplayStatus(input)).toBe(expected);
  });

  it('does not let complete numeric coverage turn a current row into completed data', () => {
    expect(selectForeignFlowDisplayStatus({
      sourceKind: 'current',
      finality: 'current_session_provisional',
      currentState: 'stale',
      usable: true,
      hasUsableValues: true,
    })).toBe('Mất kết nối');
  });

  it('distinguishes anomalous completed rows and accepts partial current rows', () => {
    expect(selectForeignFlowDisplayStatus({
      sourceKind: 'completed',
      finality: 'completed_accepted',
      isAnomalous: true,
    })).toBe('B\u1ea5t th\u01b0\u1eddng d\u1eef li\u1ec7u');
    expect(selectForeignFlowDisplayStatus({
      sourceKind: 'current',
      finality: 'current_session_provisional',
      currentState: 'partial',
      usable: true,
    })).toBe('\u0110ang di\u1ec5n ra');
  });
});

describe('selectLatestForeignFlowSession', () => {
  it('selects the newer current session and maps only trading-flow fields', () => {
    const selected = selectLatestForeignFlowSession({
      completed: completed(),
      current: current(),
    });

    expect(selected).toMatchObject({
      sessionDate: '2026-07-29',
      sourceKind: 'current',
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
    });
    expect(selected).not.toHaveProperty('totalRoom');
    expect(selected).not.toHaveProperty('currentRoom');
  });

  it('selects a newer completed session and gives completed data same-date precedence', () => {
    expect(selectLatestForeignFlowSession({
      completed: completed({ sessionDate: '2026-07-30' }),
      current: current(),
    })?.sourceKind).toBe('completed');

    const sameDate = selectLatestForeignFlowSession({
      completed: completed({ sessionDate: '2026-07-29' }),
      current: current(),
    });
    expect(sameDate).toMatchObject({
      sourceKind: 'completed',
      finality: 'completed_accepted',
      status: 'Đủ',
      foreignNetValue: 60_000_000,
    });
  });

  it('uses completed data when the current response has no safe provider date', () => {
    expect(selectLatestForeignFlowSession({
      completed: completed(),
      current: current({ tradingDate: null }),
    })).toMatchObject({ sourceKind: 'completed', sessionDate: '2026-07-28' });

    expect(selectLatestForeignFlowSession({
      completed: completed(),
      current: current({ tradingDate: '07/29/2026' }),
    })).toMatchObject({ sourceKind: 'completed', sessionDate: '2026-07-28' });
  });

  it('keeps waiting and unavailable current values null instead of fabricating zero', () => {
    const waiting = selectLatestForeignFlowSession({
      completed: completed(),
      current: current({
        status: 'unavailable',
        dataState: 'waiting',
        usable: false,
        current: null,
      }),
    });
    const unavailable = selectLatestForeignFlowSession({
      completed: completed(),
      current: current({
        status: 'unavailable',
        dataState: 'unavailable',
        usable: false,
        current: null,
      }),
    });

    expect(waiting).toMatchObject({
      status: 'Chờ dữ liệu',
      foreignBuyValue: null,
      foreignSellValue: null,
      foreignNetValue: null,
    });
    expect(unavailable).toMatchObject({
      status: 'Không khả dụng',
      foreignBuyValue: null,
      foreignSellValue: null,
      foreignNetValue: null,
    });
  });

  it('retains stale and usable-error snapshots with the connectivity label', () => {
    expect(selectLatestForeignFlowSession({
      completed: completed(),
      current: current({ status: 'partial', dataState: 'stale' }),
    })).toMatchObject({ status: 'Mất kết nối', foreignNetValue: 85_000_000 });

    expect(selectLatestForeignFlowSession({
      completed: completed(),
      current: current({ status: 'partial', dataState: 'error' }),
    })).toMatchObject({ status: 'Mất kết nối', foreignNetValue: 85_000_000 });

    expect(selectLatestForeignFlowSession({
      completed: completed(),
      current: current({
        status: 'unavailable',
        dataState: 'error',
        usable: false,
        current: null,
      }),
    })).toMatchObject({ status: 'Không khả dụng', foreignNetValue: null });

    expect(selectLatestForeignFlowSession({
      completed: completed(),
      current: current({ streamStatus: 'reconnecting' }),
    })).toMatchObject({ status: 'Mất kết nối', foreignNetValue: 85_000_000 });
  });

  it('retains a newer provider snapshot as provisional after market close', () => {
    const selected = selectLatestForeignFlowSession({
      completed: completed({ sessionDate: '2026-07-28' }),
      current: current({
        status: 'partial',
        dataState: 'market_closed',
        freshnessStatus: 'market_closed',
        streamStatus: 'reconnecting',
      }),
    });

    expect(selected).toMatchObject({
      sessionDate: '2026-07-29',
      sourceKind: 'current',
      finality: 'current_session_provisional',
      status: 'Tạm tính',
      foreignBuyVolume: 1_250,
      foreignSellVolume: 400,
      foreignNetVolume: 850,
      foreignBuyValue: 125_000_000,
      foreignSellValue: 40_000_000,
      foreignNetValue: 85_000_000,
      providerTime: '2026/07/29 10:08:00',
      receiptTime: '2026-07-29T03:08:01Z',
    });
  });

  it('does not label a market-closed capability provisional without a usable snapshot', () => {
    expect(selectLatestForeignFlowSession({
      completed: completed(),
      current: current({
        status: 'unavailable',
        dataState: 'market_closed',
        usable: false,
        current: null,
      }),
    })).toMatchObject({
      sessionDate: '2026-07-29',
      status: 'Không khả dụng',
      foreignNetValue: null,
    });
  });

  it('preserves explicit zero and rejects non-finite or missing values', () => {
    const selected = selectLatestForeignFlowSession({
      completed: completed(),
      current: current({
        current: {
          foreignBuyVolume: 0,
          foreignSellVolume: null,
          foreignNetVolume: Number.NaN,
          foreignBuyValue: 0,
          foreignSellValue: undefined,
          foreignNetValue: Number.POSITIVE_INFINITY,
        },
      }),
    });

    expect(selected).toMatchObject({
      foreignBuyVolume: 0,
      foreignSellVolume: null,
      foreignNetVolume: null,
      foreignBuyValue: 0,
      foreignSellValue: null,
      foreignNetValue: null,
    });
  });

  it('maps the completed session without deriving missing net values', () => {
    const selected = selectLatestForeignFlowSession({
      completed: completed({
        foreignBuyValue: 50,
        foreignSellValue: 20,
        foreignNetValue: null,
      }),
      current: null,
    });

    expect(selected).toMatchObject({
      sourceKind: 'completed',
      status: 'Đủ',
      foreignBuyValue: 50,
      foreignSellValue: 20,
      foreignNetValue: null,
    });
  });

  it('keeps accepted finality but labels a missing-field completed row incomplete', () => {
    const selected = selectLatestForeignFlowSession({
      completed: completed({
        sessionDate: '2026-06-30',
        foreignBuyValue: null,
        foreignSellValue: null,
        foreignNetValue: null,
        dataQuality: 'incomplete',
        complete: false,
      }),
    });

    expect(selected).toMatchObject({
      sessionDate: '2026-06-30',
      sourceKind: 'completed',
      finality: 'completed_accepted',
      status: 'Thiếu dữ liệu',
      foreignBuyValue: null,
      foreignSellValue: null,
      foreignNetValue: null,
    });
  });
});
