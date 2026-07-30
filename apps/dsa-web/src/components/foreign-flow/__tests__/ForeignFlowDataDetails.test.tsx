import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type {
  VietnamCurrentForeignFlowAggregateResponse,
  VietnamFlowDataResponse,
  VietnamVn30ForeignFlowResponse,
} from '../../../api/stocks';
import { ForeignFlowDataDetails } from '../ForeignFlowDataDetails';
import { currentIndustryCapability } from '../currentForeignFlowAggregateModel';

const currentAggregate = (
  overrides: Partial<VietnamCurrentForeignFlowAggregateResponse> = {},
): VietnamCurrentForeignFlowAggregateResponse => ({
  status: 'ok',
  dataState: 'ready',
  usable: true,
  scope: 'current_foreign_flow_aggregate',
  universe: 'index:VN30',
  providerSessionDate: '2026-07-30',
  isProvisional: true,
  finality: 'current_session_provisional',
  source: 'SSI FastConnect V3 ForeignRoomMessage',
  providerVersion: 'v3',
  endpoint: 'room.{symbol}',
  updateSemantics: 'cumulative_replacement_snapshot',
  aggregate: { foreignNetValue: 94_120_000_000 },
  displaySeries: [{
    tradingDate: '2026-07-30',
    sourceKind: 'current',
    finality: 'current_session_provisional',
  }],
  displayWindows: {},
  rankings: {},
  items: [],
  groups: [{ icbCode: '10', icbName: 'Technology' }],
  coverage: {
    requestedSymbolCount: 30,
    classifiedSymbolCount: 30,
    subscribedSymbolCount: 30,
    observedSymbolCount: 30,
    completeVolumeCount: 30,
    completeValueCount: 30,
    missingSymbols: [],
    staleSymbolCount: 0,
  },
  diagnostics: { provisionalPersisted: false },
  ...overrides,
});

const vn30 = {
  source: 'ssi_fastconnect',
  canonicalProviderVersion: 'v3',
  sourceEndpoint: 'daily_stock_price',
  fetchedAt: '2026-07-30T03:30:00Z',
  cache: { status: 'hit', ageSeconds: 5 },
  historicalConstituentCorrect: false,
  membershipSource: 'SSI IndexComponents',
  decompositionAggregationMode: 'CURRENT_MEMBERSHIP_DECOMPOSITION',
  decomposition: {
    latestCompletedSession: '2026-07-29',
    series: [{ tradingDate: '2026-07-29' }],
    anomalySessions: [],
    latest: { valueCoverageRatio: 1 },
  },
  canonical: { capabilityStatus: 'unsupported' },
} as unknown as VietnamVn30ForeignFlowResponse;

const industry = {
  status: 'partial',
  dataState: 'partial',
  usable: true,
  source: 'ssi_fastconnect',
  providerVersion: 'v3',
  endpoint: 'securitiesSummary',
  universe: 'index:VN30',
  currentSessionStatus: 'CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS',
  requestedSymbolCount: 30,
  classifiedSymbolCount: 30,
  rows: [{ tradingDate: '2026-07-29', icbCode: '10' }],
} as VietnamFlowDataResponse;

describe('ForeignFlowDataDetails', () => {
  it('separates completed, display, and provider sessions and replaces the obsolete diagnostic', () => {
    render(
      <ForeignFlowDataDetails
        vn30={vn30}
        industry={industry}
        currentAggregate={currentAggregate()}
      />,
    );

    const vn30Details = screen.getByRole('heading', { name: 'VN30 foreign flow provenance' }).closest('section');
    const industryDetails = screen.getByRole('heading', { name: 'Industry provenance' }).closest('section');
    expect(vn30Details).not.toBeNull();
    expect(industryDetails).not.toBeNull();
    expect(within(vn30Details as HTMLElement).getByText('Latest completed session')).toBeInTheDocument();
    expect(within(vn30Details as HTMLElement).getByText('2026-07-29')).toBeInTheDocument();
    expect(within(vn30Details as HTMLElement).getByText('Latest display session')).toBeInTheDocument();
    expect(within(vn30Details as HTMLElement).getAllByText('2026-07-30')).toHaveLength(2);
    expect(within(vn30Details as HTMLElement).getByText('Current provider session')).toBeInTheDocument();
    expect(within(vn30Details as HTMLElement).queryByText('Source session')).not.toBeInTheDocument();

    const capabilityLabel = within(industryDetails as HTMLElement).getByText('Current capability state');
    expect(capabilityLabel).toBeInTheDocument();
    expect(capabilityLabel.parentElement).toHaveTextContent('ready');
    expect(within(industryDetails as HTMLElement).getAllByText('index:VN30')).toHaveLength(2);
    expect(within(industryDetails as HTMLElement).queryByText('CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS')).not.toBeInTheDocument();
    expect(within(industryDetails as HTMLElement).getByText('Current observed symbols')).toBeInTheDocument();
    expect(within(industryDetails as HTMLElement).getByText('Current complete value coverage')).toBeInTheDocument();
    expect(within(industryDetails as HTMLElement).getByText('Current complete volume coverage')).toBeInTheDocument();
  });

  it.each([
    [currentAggregate(), 'ready'],
    [currentAggregate({
      status: 'partial',
      coverage: {
        ...currentAggregate().coverage,
        observedSymbolCount: 29,
        completeValueCount: 29,
        missingSymbols: ['VCB'],
      },
    }), 'partial'],
    [currentAggregate({ dataState: 'stale' }), 'stale'],
    [currentAggregate({ status: 'unavailable', dataState: 'waiting', usable: false, aggregate: null }), 'waiting'],
    [null, 'unavailable'],
  ] as const)('classifies current Industry capability as %s', (response, expected) => {
    expect(currentIndustryCapability(response)).toBe(expected);
  });

  it('keeps completed Industry provenance visible without a current aggregate', () => {
    render(<ForeignFlowDataDetails vn30={vn30} industry={industry} currentAggregate={null} />);

    expect(screen.getByRole('heading', { name: 'Industry provenance' })).toBeInTheDocument();
    expect(screen.getByText('securitiesSummary')).toBeInTheDocument();
    expect(screen.getByText('unavailable')).toBeInTheDocument();
  });
});
