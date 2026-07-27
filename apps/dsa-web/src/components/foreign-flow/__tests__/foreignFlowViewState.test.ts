import { describe, expect, it } from 'vitest';
import type {
  VietnamFlowDataResponse,
  VietnamForeignFlowSymbolHistoryResponse,
  VietnamForeignFlowWatchlistResponse,
  VietnamVn30ForeignFlowResponse,
} from '../../../api/stocks';
import {
  mapIndustryFlowViewState,
  mapProprietaryFlowViewState,
  mapTickerFlowViewState,
  mapVn30FlowViewState,
  mapWatchlistFlowViewState,
} from '../foreignFlowViewState';

describe('foreignFlowViewState', () => {
  it('distinguishes provider-unavailable ticker data from successful empty data', () => {
    const base = {
      ticker: 'FPT',
      source: 'ssi_fastconnect',
      sourceEndpoint: 'daily_stock_price',
      volumeUnit: 'shares',
      valueUnit: 'VND',
      finality: 'daily_available',
      rows: [],
      windows: {},
      requested: { mode: 'recent_sessions', returnedSessionCount: 0 },
      coverage: { coveredSessions: 0 },
      fetchedAt: '2026-07-27T00:00:00Z',
    } as unknown as VietnamForeignFlowSymbolHistoryResponse;

    expect(mapTickerFlowViewState({
      ...base,
      dataState: 'unavailable',
      freshness: 'unavailable',
      failureClass: 'network_error',
    })).toMatchObject({
      availability: 'unavailable',
      usable: false,
      failureClass: 'network_error',
      hasData: false,
    });
    expect(mapTickerFlowViewState({
      ...base,
      dataState: 'empty',
      freshness: 'empty',
    })).toMatchObject({
      availability: 'ready',
      usable: false,
      failureClass: null,
      hasData: false,
    });
  });

  it('keeps partial VN30 decomposition usable while direct capability is secondary', () => {
    const state = mapVn30FlowViewState({
      status: 'partial',
      dataState: 'partial',
      usable: true,
      sourceCoverage: [{
        source: 'direct',
        capabilityStatus: 'unsupported',
        usable: false,
        failureClass: 'DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED',
      }],
      membership: { failureClass: null },
      decomposition: {
        usable: true,
        series: [{ tradingDate: '2026-07-25' }],
        anomalyCount: 0,
      },
    } as unknown as VietnamVn30ForeignFlowResponse);

    expect(state).toMatchObject({
      availability: 'partial',
      usable: true,
      hasData: true,
      failureClass: null,
    });
  });

  it('normalizes aggregate and watchlist contracts through shared adapters', () => {
    const unavailable: VietnamFlowDataResponse = {
      status: 'unavailable',
      dataState: 'unavailable',
      usable: false,
      failureClass: 'authorization',
      source: 'ssi_fastconnect',
      providerVersion: 'v3',
      rows: [],
    };
    expect(mapIndustryFlowViewState(unavailable).failureClass).toBe('authorization');
    expect(mapProprietaryFlowViewState({
      ...unavailable,
      status: 'partial',
      dataState: 'partial',
      usable: true,
      failureClass: null,
      rows: [{ tradingDate: '2026-07-25' }],
    })).toMatchObject({ availability: 'partial', usable: true, hasData: true });

    expect(mapWatchlistFlowViewState({
      status: 'unavailable',
      dataState: 'unavailable',
      usable: false,
      requestedTickers: ['FPT'],
      normalizedTickers: ['FPT'],
      duplicateTickersRemoved: 0,
      expectedSymbolCount: 1,
      readySymbolCount: 0,
      partialSymbolCount: 0,
      unavailableSymbolCount: 1,
      requestedSessionCount: 20,
      fetchedAt: '2026-07-27T00:00:00Z',
      provider: 'ssi_fastconnect',
      providerVersion: 'v3',
      cacheState: 'unavailable',
      failureClass: 'provider_unavailable',
      items: [{
        ticker: 'FPT',
        availability: 'unavailable',
        dataState: 'unavailable',
        sourceFreshness: 'unknown',
        fetchedAt: '2026-07-27T00:00:00Z',
        cacheState: 'unavailable',
        actualSessionCount: 0,
        requestedSessionCount: 20,
        complete: false,
        streakMetricBasis: 'foreign_net_value',
        containsProviderAnomaly: false,
        anomalySessions: [],
        anomalyCount: 0,
        source: 'ssi_fastconnect',
        sourceEndpoint: 'daily_stock_price',
      }],
    } as VietnamForeignFlowWatchlistResponse)).toMatchObject({
      availability: 'unavailable',
      usable: false,
      hasData: true,
    });
  });
});
