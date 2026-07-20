import { useCallback, useEffect, useRef, useState } from 'react';
import { stocksApi, type VietnamVn30ForeignFlowResponse } from '../api/stocks';

export const useForeignFlowVn30 = (active: boolean, topN = 10) => {
  const [data, setData] = useState<VietnamVn30ForeignFlowResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const dataRef = useRef(data);
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
    if (!active) {
      abortRef.current = null;
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const response = await stocksApi.getVietnamVn30ForeignFlow({
        topN,
        forceRefresh,
        signal: controller.signal,
      });
      if (!mountedRef.current || requestId !== requestIdRef.current) return;
      if (dataRef.current?.componentCounts.usable && response.componentCounts.usable === 0) {
        setError('Latest VN30 refresh returned no usable component history.');
      } else {
        setData(response);
      }
    } catch (caught) {
      if (controller.signal.aborted || !mountedRef.current || requestId !== requestIdRef.current) return;
      setError(caught instanceof Error ? caught.message : 'VN30 foreign-flow aggregate unavailable.');
    } finally {
      if (mountedRef.current && requestId === requestIdRef.current) {
        setLoading(false);
        if (abortRef.current === controller) abortRef.current = null;
      }
    }
  }, [active, topN]);

  useEffect(() => {
    void load(false);
  }, [load]);

  return {
    data: active ? data : null,
    loading: active && loading,
    updating: active && loading && Boolean(data),
    error: active ? error : null,
    refresh: useCallback(() => load(false), [load]),
    forceRefresh: useCallback(() => load(true), [load]),
  };
};
