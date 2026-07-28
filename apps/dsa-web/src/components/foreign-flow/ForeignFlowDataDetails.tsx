import type {
  VietnamFlowDataResponse,
  VietnamVn30ForeignFlowResponse,
} from '../../api/stocks';
import { Badge } from '../common';
import { mapIndustryFlowViewState, mapVn30FlowViewState } from './foreignFlowViewState';

const displayValue = (input: unknown): string => {
  if (input === null || input === undefined || input === '') return '—';
  if (typeof input === 'boolean') return input ? 'true' : 'false';
  if (Array.isArray(input)) return input.length ? input.join(', ') : '—';
  return String(input);
};

const DetailGrid = ({ rows }: { rows: Array<[string, unknown]> }) => (
  <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
    {rows.map(([label, content]) => (
      <div key={label} className="min-w-0 border-b border-border/50 pb-3">
        <dt className="text-xs text-secondary-text">{label}</dt>
        <dd className="mt-1 break-words text-sm font-medium">{displayValue(content)}</dd>
      </div>
    ))}
  </dl>
);

export const ForeignFlowDataDetails = ({
  vn30,
  industry,
}: {
  vn30: VietnamVn30ForeignFlowResponse | null;
  industry: VietnamFlowDataResponse | null;
}) => {
  const vn30State = vn30 ? mapVn30FlowViewState(vn30) : null;
  const industryState = industry ? mapIndustryFlowViewState(industry) : null;

  if (!vn30 && !industry) {
    return (
      <section className="rounded-xl border border-border/70 bg-card p-5">
        <h2 className="font-semibold">Data Details</h2>
        <p className="mt-2 text-sm text-secondary-text">Load Overview or a detailed mode to inspect provenance and diagnostics.</p>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/70 bg-card p-5" aria-labelledby="vn30-data-details-heading">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h2 id="vn30-data-details-heading" className="font-semibold">VN30 foreign flow provenance</h2>
          {vn30State ? (
            <Badge variant={vn30State.availability === 'ready' ? 'success' : vn30State.availability === 'partial' ? 'warning' : 'default'}>
              {vn30State.availability}
            </Badge>
          ) : null}
        </div>
        <DetailGrid rows={[
          ['Provider', vn30?.source],
          ['Provider version', vn30?.canonicalProviderVersion],
          ['Source endpoint', vn30?.sourceEndpoint],
          ['Source session', vn30?.decomposition.latestCompletedSession],
          ['Fetched at', vn30?.fetchedAt],
          ['Cache state', vn30?.cache.status],
          ['Cache age', vn30 ? `${vn30.cache.ageSeconds}s` : null],
          ['Source freshness', vn30State?.freshness],
          ['Coverage', vn30?.decomposition.latest?.valueCoverageRatio],
          ['Actual sessions', vn30?.decomposition.series.length],
          ['Failure class', vn30State?.failureClass],
          ['Anomaly sessions', vn30?.decomposition.anomalySessions],
          ['Direct VN30 capability', vn30?.canonical.capabilityStatus],
          ['Historical constituent correctness', vn30?.historicalConstituentCorrect],
          ['Membership source', vn30?.membershipSource],
          ['Aggregation mode', vn30?.decompositionAggregationMode],
        ]} />
      </section>

      <section className="rounded-xl border border-border/70 bg-card p-5" aria-labelledby="industry-data-details-heading">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h2 id="industry-data-details-heading" className="font-semibold">Industry provenance</h2>
          {industryState ? (
            <Badge variant={industryState.availability === 'ready' ? 'success' : industryState.availability === 'partial' ? 'warning' : 'default'}>
              {industryState.availability}
            </Badge>
          ) : null}
        </div>
        <DetailGrid rows={[
          ['Provider', industry?.source],
          ['Provider version', industry?.providerVersion],
          ['Source endpoint', industry?.endpoint],
          ['Fetched at', industry?.fetchedAt],
          ['Cache state', industry?.cache?.status],
          ['Cache age', industry?.cache?.ageSeconds === null || industry?.cache?.ageSeconds === undefined ? null : `${industry.cache.ageSeconds}s`],
          ['Source freshness', industryState?.freshness],
          ['Requested symbols', industry?.requestedSymbolCount],
          ['Classified symbols', industry?.classifiedSymbolCount],
          ['Failure class', industryState?.failureClass],
          ['Current-session status', industry?.currentSessionStatus],
          ['Universe', industry?.universe],
        ]} />
      </section>

      <p className="text-xs text-secondary-text">
        Direct VN30 foreign fields remain diagnostic and secondary. Current-membership decomposition is not historically constituent-correct, and completed-session data does not imply current-session flow.
      </p>
    </div>
  );
};
