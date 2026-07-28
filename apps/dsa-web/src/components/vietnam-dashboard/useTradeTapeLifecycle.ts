import { useEffect, useRef, useState } from 'react';

export const TRADE_TAPE_STARTUP_DEADLINE_MS = 20_000;
export const TRADE_TAPE_STARTUP_POLL_INTERVAL_MS = 4_000;

export type TradeTapeLifecycleState =
  | 'loading'
  | 'ready'
  | 'reconnecting'
  | 'no_data'
  | 'stale'
  | 'unavailable'
  | 'disabled'
  | 'error';

export interface TradeTapeLifecycleEvidence {
  hasRows: boolean;
  status?: string | null;
  streamState?: string | null;
  pendingEvidence?: boolean;
  requestLoading?: boolean;
  requestError?: string | null;
  deadlineExpired?: boolean;
}

const normalizeState = (value?: string | null) => (
  String(value ?? '').trim().toLowerCase().replaceAll('-', '_')
);

const DISABLED_STATES = new Set(['disabled', 'not_implemented']);
const UNAVAILABLE_STATES = new Set(['unavailable', 'missing', 'unknown', 'not_found']);
const ERROR_STATES = new Set(['error', 'failed', 'failure']);
const RECONNECTING_STATES = new Set(['reconnecting', 'recovering', 'awaiting_subscription', 'starting']);
const STALE_STATES = new Set(['stale', 'closed']);
const READY_STATES = new Set(['ok', 'ready', 'available', 'success']);
const EMPTY_STATES = new Set(['empty', 'no_data', 'no_rows']);

export const resolveTradeTapeLifecycleState = ({
  hasRows,
  status,
  streamState,
  pendingEvidence = false,
  requestLoading = false,
  requestError,
  deadlineExpired = false,
}: TradeTapeLifecycleEvidence): TradeTapeLifecycleState => {
  const normalizedStatus = normalizeState(status);
  const normalizedStreamState = normalizeState(streamState);

  if (hasRows) {
    if (requestLoading || RECONNECTING_STATES.has(normalizedStreamState)) return 'reconnecting';
    if (requestError || ERROR_STATES.has(normalizedStatus) || UNAVAILABLE_STATES.has(normalizedStatus)) return 'stale';
    if (STALE_STATES.has(normalizedStatus) || STALE_STATES.has(normalizedStreamState)) return 'stale';
    return 'ready';
  }

  // Typed terminal provider states are authoritative even while another poll is in flight.
  if (DISABLED_STATES.has(normalizedStatus) || normalizedStreamState === 'disabled') return 'disabled';
  if (RECONNECTING_STATES.has(normalizedStreamState)) return 'reconnecting';
  if (UNAVAILABLE_STATES.has(normalizedStatus) || normalizedStreamState === 'unavailable') return 'unavailable';
  if (requestError || ERROR_STATES.has(normalizedStatus) || ERROR_STATES.has(normalizedStreamState)) return 'error';
  if (RECONNECTING_STATES.has(normalizedStatus) || RECONNECTING_STATES.has(normalizedStreamState)) return 'reconnecting';
  if (STALE_STATES.has(normalizedStatus) || STALE_STATES.has(normalizedStreamState)) return 'stale';

  if (!pendingEvidence && !requestLoading && (READY_STATES.has(normalizedStatus) || EMPTY_STATES.has(normalizedStatus))) {
    return 'no_data';
  }
  if (deadlineExpired) return requestLoading ? 'unavailable' : 'no_data';
  return 'loading';
};

export interface UseTradeTapeLifecycleOptions extends Omit<TradeTapeLifecycleEvidence, 'deadlineExpired'> {
  symbol?: string | null;
  generation?: string | number | null;
  onStartupPoll?: () => void;
  startupDeadlineMs?: number;
  startupPollIntervalMs?: number;
}

export interface TradeTapeLifecycleResult {
  state: TradeTapeLifecycleState;
  deadlineExpired: boolean;
  identity: string | null;
}

export const useTradeTapeLifecycle = ({
  symbol,
  generation,
  hasRows,
  status,
  streamState,
  pendingEvidence = false,
  requestLoading = false,
  requestError,
  onStartupPoll,
  startupDeadlineMs = TRADE_TAPE_STARTUP_DEADLINE_MS,
  startupPollIntervalMs = TRADE_TAPE_STARTUP_POLL_INTERVAL_MS,
}: UseTradeTapeLifecycleOptions): TradeTapeLifecycleResult => {
  const identity = symbol ? `${symbol}:${generation ?? 'initial'}` : null;
  const lifecycleRef = useRef<{ identity: string | null; startedAt: number | null }>({
    identity: null,
    startedAt: null,
  });
  const [expiredIdentity, setExpiredIdentity] = useState<string | null>(null);
  const deadlineExpired = identity !== null && expiredIdentity === identity;
  const state = resolveTradeTapeLifecycleState({
    hasRows,
    status,
    streamState,
    pendingEvidence,
    requestLoading,
    requestError,
    deadlineExpired,
  });

  useEffect(() => {
    if (lifecycleRef.current.identity !== identity) {
      lifecycleRef.current = { identity, startedAt: identity ? Date.now() : null };
    }
    const startedAt = lifecycleRef.current.startedAt;
    if (!identity || startedAt === null || state !== 'loading') return undefined;

    const remainingMs = Math.max(0, startupDeadlineMs - (Date.now() - startedAt));
    if (remainingMs === 0) {
      const expiredTimer = window.setTimeout(() => setExpiredIdentity(identity), 0);
      return () => window.clearTimeout(expiredTimer);
    }

    const deadlineTimer = window.setTimeout(() => {
      setExpiredIdentity(identity);
    }, remainingMs);
    const pollTimer = onStartupPoll
      ? window.setInterval(() => {
          if (Date.now() - startedAt < startupDeadlineMs) onStartupPoll();
        }, startupPollIntervalMs)
      : null;

    return () => {
      window.clearTimeout(deadlineTimer);
      if (pollTimer !== null) window.clearInterval(pollTimer);
    };
  }, [
    identity,
    onStartupPoll,
    startupDeadlineMs,
    startupPollIntervalMs,
    state,
  ]);

  return { state, deadlineExpired, identity };
};

export const tradeTapeLifecycleDetail = (
  state: TradeTapeLifecycleState,
  rowCount: number,
) => {
  if (state === 'ready') return `${rowCount} recent rows`;
  if (state === 'reconnecting') return rowCount > 0 ? 'Refreshing; showing last known trades' : 'Reconnecting — showing last known data when available.';
  if (state === 'stale') return rowCount > 0 ? 'Showing last known trades' : 'Trade tape stale';
  if (state === 'disabled') return 'Trade tape disabled';
  if (state === 'unavailable' || state === 'error') return 'SSI trade tape unavailable.';
  if (state === 'no_data') return 'No trades received';
  return 'Waiting for recent trades';
};
