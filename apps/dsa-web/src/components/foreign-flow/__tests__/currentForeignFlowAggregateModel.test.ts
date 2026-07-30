import { describe, expect, it } from 'vitest';
import type {
  VietnamCurrentForeignFlowAggregateResponse,
  VietnamForeignFlowWatchlistItem,
} from '../../../api/stocks';
import {
  applyCurrentWatchlistFlow,
  mergeCurrentAggregateRows,
  type ForeignFlowDisplayRow,
} from '../currentForeignFlowAggregateModel';

const currentAggregate = (
  overrides: Partial<VietnamCurrentForeignFlowAggregateResponse> = {},
): VietnamCurrentForeignFlowAggregateResponse => ({
  status: 'partial',
  dataState: 'ready',
  usable: true,
  scope: 'current_foreign_flow_aggregate',
  universe: 'VN30',
  providerSessionDate: '2026-07-29',
  isProvisional: true,
  finality: 'current_session_provisional',
  source: 'SSI FastConnect V3 ForeignRoomMessage',
  providerVersion: 'v3',
  endpoint: 'room.{symbol}',
  updateSemantics: 'cumulative_replacement_snapshot',
  aggregate: { foreignNetValue: 60 },
  displaySeries: [{
    tradingDate: '2026-07-29',
    foreignBuyValue: 100,
    foreignSellValue: 40,
    foreignNetValue: 60,
    sourceKind: 'current',
    finality: 'current_session_provisional',
  }],
  displayWindows: {},
  rankings: {},
  items: [],
  groups: [],
  coverage: {
    requestedSymbolCount: 2,
    classifiedSymbolCount: 2,
    subscribedSymbolCount: 2,
    observedSymbolCount: 1,
    completeVolumeCount: 1,
    completeValueCount: 1,
    missingSymbols: ['SSI'],
    staleSymbolCount: 0,
  },
  ...overrides,
});

describe('currentForeignFlowAggregateModel', () => {
  it('preserves stale current finality and values at full 30/30 coverage', () => {
    const completed: ForeignFlowDisplayRow[] = [
      { tradingDate: '2026-07-28', foreignNetValue: -10 },
      { tradingDate: '2026-07-29', foreignNetValue: 20 },
    ];
    const before = structuredClone(completed);
    const current = currentAggregate({
      status: 'ok',
      dataState: 'stale',
      providerSessionDate: '2026-07-30',
      displaySeries: [{
        tradingDate: '2026-07-30',
        foreignBuyValue: 539_680_000_000,
        foreignSellValue: 445_570_000_000,
        foreignNetValue: 94_120_000_000,
        foreignBuyVolume: 30,
        foreignSellVolume: 20,
        foreignNetVolume: 10,
        sourceKind: 'current',
        finality: 'current_session_provisional',
        isStale: true,
      }],
      coverage: {
        requestedSymbolCount: 30,
        classifiedSymbolCount: 30,
        subscribedSymbolCount: 30,
        observedSymbolCount: 30,
        completeVolumeCount: 30,
        completeValueCount: 30,
        missingSymbols: [],
        staleSymbolCount: 30,
      },
    });

    const merged = mergeCurrentAggregateRows(completed, current, 'vn30');

    expect(completed).toEqual(before);
    expect(merged.map((row) => row.tradingDate)).toEqual([
      '2026-07-28',
      '2026-07-29',
      '2026-07-30',
    ]);
    expect(merged[2]).toMatchObject({
      sourceKind: 'current',
      finality: 'current_session_provisional',
      currentState: 'stale',
      displayStatus: 'Mất kết nối',
      isCurrent: true,
      isCompleted: false,
      isStale: true,
      requestedCount: 30,
      observedCount: 30,
      completeValueCount: 30,
      completeVolumeCount: 30,
      foreignBuyValue: 539_680_000_000,
      foreignSellValue: 445_570_000_000,
      foreignNetValue: 94_120_000_000,
    });
    expect(merged[1]).toMatchObject({
      sourceKind: 'completed',
      finality: 'completed_accepted',
      displayStatus: 'Đủ',
    });
  });

  it.each([
    ['ready', 'Đang diễn ra'],
    ['market_closed', 'Tạm tính'],
  ] as const)('uses the shared status for %s current aggregates', (dataState, expected) => {
    const merged = mergeCurrentAggregateRows([], currentAggregate({
      dataState,
      displaySeries: [{
        tradingDate: '2026-07-30',
        foreignBuyValue: 1,
        foreignSellValue: 1,
        foreignNetValue: 0,
        sourceKind: 'current',
      }],
    }), 'vn30');

    expect(merged[0].displayStatus).toBe(expected);
    expect(merged[0].finality).toBe('current_session_provisional');
  });

  it('adds a newer provisional session without replacing completed history', () => {
    const completed: ForeignFlowDisplayRow[] = [
      { tradingDate: '2026-07-27', foreignNetValue: 10, sourceKind: 'completed' },
      { tradingDate: '2026-07-28', foreignNetValue: 20, sourceKind: 'completed' },
    ];

    const merged = mergeCurrentAggregateRows(completed, currentAggregate(), 'vn30');

    expect(merged.map((row) => row.tradingDate)).toEqual([
      '2026-07-27',
      '2026-07-28',
      '2026-07-29',
    ]);
    expect(merged[2]).toMatchObject({
      foreignNetValue: 60,
      finality: 'current_session_provisional',
    });
  });

  it('keeps accepted completed data authoritative for the same date', () => {
    const completed: ForeignFlowDisplayRow[] = [{
      tradingDate: '2026-07-29',
      foreignNetValue: 75,
      sourceKind: 'completed',
    }];

    const merged = mergeCurrentAggregateRows(completed, currentAggregate(), 'vn30');

    expect(merged).toHaveLength(1);
    expect(merged[0].foreignNetValue).toBe(75);
    expect(merged[0].sourceKind).toBe('completed');
    expect(merged[0].finality).toBe('completed_accepted');
    expect(merged[0].displayStatus).toBe('Đủ');
  });

  it('preserves explicit zero and missing values when current windows hydrate a watchlist', () => {
    const item = {
      ticker: 'FPT',
      availability: 'ready',
      dataState: 'ready',
      latestSession: '2026-07-28',
      sourceFreshness: 'latest_completed',
      cacheState: 'hit',
      actualSessionCount: 20,
      requestedSessionCount: 20,
      complete: true,
    } as VietnamForeignFlowWatchlistItem;
    const aggregate = currentAggregate({
      dataState: 'market_closed',
      items: [{
        symbol: 'FPT',
        providerSessionDate: '2026-07-29',
        dataState: 'market_closed',
        usable: true,
        isStale: false,
        streamStatus: 'market_closed',
        displayLatest: { tradingDate: '2026-07-29' },
        displayWindows: {
          '1': {
            foreignBuyValue: 0,
            foreignSellValue: null,
            foreignNetValue: null,
            foreignBuyVolume: 0,
            foreignSellVolume: null,
            foreignNetVolume: null,
          },
        },
      }],
    });

    const [hydrated] = applyCurrentWatchlistFlow([item], aggregate);

    expect(hydrated.buyValue1d).toBe(0);
    expect(hydrated.sellValue1d).toBeNull();
    expect(hydrated.netValue1d).toBeNull();
    expect(hydrated.latestSession).toBe('2026-07-29');
    expect(hydrated.displayFinality).toBe('current_session_provisional');
    expect(hydrated.displayStatus).toBe('Tạm tính');
    expect(hydrated.displayCoverage).toBe('1/2');
  });
});
