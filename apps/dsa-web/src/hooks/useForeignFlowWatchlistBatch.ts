import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { stocksApi, type VietnamForeignFlowBatchResponse } from '../api/stocks';
import { resolveVietnamForeignFlowScope } from '../utils/vietnamCustomWatchlist';

type UseForeignFlowWatchlistBatchOptions = {
  topN?: number;
};

export const useForeignFlowWatchlistBatch = (
  tickers: string[],
  options: UseForeignFlowWatchlistBatchOptions = {},
) => {
  const topN = options.topN ?? 5;
  const scope = resolveVietnamForeignFlowScope(tickers);
  const scopeKey = scope.tickers.join(',');
  const requestedTickers = useMemo(() => scopeKey ? scopeKey.split(',') : [], [scopeKey]);
  const [data, setData] = useState<VietnamForeignFlowBatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const dataRef = useRef(data);
  const mountedRef = useRef(true);
  dataRef.current = data;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestIdRef.current += 1;
      abortRef.current?.abort();
    };
  }, []);

  const load = useCallback(async (forceRefresh = false) => {
    requestIdRef.current += 1;
    const requestId = requestIdRef.current;
    abortRef.current?.abort();

    if (!requestedTickers.length) {
      abortRef.current = null;
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const response = await stocksApi.getVietnamForeignFlowBatch(requestedTickers, {
        topN,
        forceRefresh,
        signal: controller.signal,
      });
      if (!mountedRef.current || requestId !== requestIdRef.current) return;
      const previous = dataRef.current;
      const sameScope = previous?.normalizedTickers.join(',') === scopeKey;
      if (sameScope && previous.usableCount > 0 && response.usableCount === 0) {
        setError('Latest foreign-flow refresh returned no usable rows.');
      } else {
        setData(response);
      }
    } catch (caught) {
      if (controller.signal.aborted || !mountedRef.current || requestId !== requestIdRef.current) return;
      setError(caught instanceof Error ? caught.message : 'Foreign-flow batch unavailable.');
    } finally {
      if (mountedRef.current && requestId === requestIdRef.current) {
        setLoading(false);
        if (abortRef.current === controller) abortRef.current = null;
      }
    }
  }, [requestedTickers, scopeKey, topN]);

  useEffect(() => {
    void load(false);
  }, [load]);

  const currentData = data?.normalizedTickers.join(',') === scopeKey ? data : null;
  const refresh = useCallback(() => load(false), [load]);
  const forceRefresh = useCallback(() => load(true), [load]);

  return {
    data: currentData,
    loading,
    updating: loading && Boolean(currentData),
    error,
    scope,
    refresh,
    forceRefresh,
  };
};
