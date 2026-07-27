import type {
  VietnamFlowDataResponse,
  VietnamForeignFlowSymbolHistoryResponse,
  VietnamForeignFlowWatchlistResponse,
  VietnamVn30ForeignFlowResponse,
} from '../../api/stocks';

export type FlowAvailability = 'ready' | 'partial' | 'unavailable';
export type FlowFreshness = 'current' | 'latest_completed' | 'stale' | 'unknown';
export type FlowQuality = 'clean' | 'anomaly_present' | 'incomplete';

export type FlowViewState = {
  availability: FlowAvailability;
  usable: boolean;
  freshness: FlowFreshness;
  quality: FlowQuality;
  failureClass: string | null;
  hasData: boolean;
};

const failureFromDiagnostics = (payload: VietnamFlowDataResponse) => {
  const failure = payload.failureClass ?? payload.diagnostics?.failureClass;
  return typeof failure === 'string' && failure ? failure : null;
};

export const mapTickerFlowViewState = (
  payload: VietnamForeignFlowSymbolHistoryResponse,
): FlowViewState => {
  const hasData = payload.rows.length > 0;
  const unavailable = payload.dataState === 'unavailable';
  const stale = payload.dataState === 'stale' || payload.freshness === 'stale';
  return {
    availability: unavailable ? 'unavailable' : stale ? 'partial' : 'ready',
    usable: hasData && !unavailable,
    freshness: stale
      ? 'stale'
      : payload.freshness === 'fresh' && hasData
        ? 'latest_completed'
        : 'unknown',
    quality: payload.coverage.complete === false ? 'incomplete' : 'clean',
    failureClass: unavailable ? payload.failureClass ?? 'provider_unavailable' : null,
    hasData,
  };
};

export const mapVn30FlowViewState = (
  payload: VietnamVn30ForeignFlowResponse,
): FlowViewState => {
  const hasData = payload.decomposition.series.length > 0;
  const anomalyPresent = (payload.decomposition.anomalyCount ?? 0) > 0;
  const status = payload.status ?? payload.dataState;
  const usable = payload.usable ?? payload.decomposition.usable ?? hasData;
  return {
    availability: status === 'ready'
      ? 'ready'
      : status === 'unavailable'
        ? 'unavailable'
        : 'partial',
    usable: usable && hasData,
    freshness: status === 'stale'
      ? 'stale'
      : hasData
        ? 'latest_completed'
        : 'unknown',
    quality: anomalyPresent
      ? 'anomaly_present'
      : status === 'ready'
        ? 'clean'
        : 'incomplete',
    failureClass: status === 'unavailable'
      ? (payload.sourceCoverage ?? []).find((entry) => entry.failureClass)?.failureClass
        ?? payload.membership.failureClass
        ?? 'provider_unavailable'
      : null,
    hasData,
  };
};

const mapAggregateFlowViewState = (
  payload: VietnamFlowDataResponse,
): FlowViewState => {
  const hasData = (payload.rows?.length ?? 0) > 0;
  const availability = payload.dataState
    ?? (payload.status === 'ok' ? 'ready' : payload.status);
  return {
    availability,
    usable: payload.usable ?? (availability !== 'unavailable' && hasData),
    freshness: hasData ? 'latest_completed' : 'unknown',
    quality: availability === 'partial' ? 'incomplete' : 'clean',
    failureClass: availability === 'unavailable'
      ? failureFromDiagnostics(payload) ?? 'provider_unavailable'
      : null,
    hasData,
  };
};

export const mapIndustryFlowViewState = mapAggregateFlowViewState;
export const mapProprietaryFlowViewState = mapAggregateFlowViewState;

export const mapWatchlistFlowViewState = (
  payload: VietnamForeignFlowWatchlistResponse,
): FlowViewState => ({
  availability: payload.dataState,
  usable: payload.usable,
  freshness: payload.items.some((item) => item.sourceFreshness === 'stale')
    ? 'stale'
    : payload.items.some((item) => item.sourceFreshness === 'current')
      ? 'current'
      : payload.items.some((item) => item.sourceFreshness === 'latest_completed')
        ? 'latest_completed'
        : 'unknown',
  quality: payload.items.some((item) => item.containsProviderAnomaly)
    ? 'anomaly_present'
    : payload.dataState === 'ready'
      ? 'clean'
      : 'incomplete',
  failureClass: payload.failureClass ?? null,
  hasData: payload.items.length > 0,
});
