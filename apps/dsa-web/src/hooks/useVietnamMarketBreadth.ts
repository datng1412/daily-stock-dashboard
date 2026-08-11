import { useCallback, useEffect, useRef, useState } from 'react';

import { stocksApi, type VietnamMarketBreadthResponse } from '../api/stocks';

export const useVietnamMarketBreadth = () => {
  const [data, setData] = useState<VietnamMarketBreadthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async (forceRefresh = false) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    if (data) setUpdating(true);
    else setLoading(true);
    setError(null);
    try {
      const response = await stocksApi.getVietnamMarketBreadth({
        forceRefresh,
        signal: controller.signal,
      });
      if (requestId !== requestIdRef.current) return;
      if (response.usable || !data) setData(response);
      setError(response.usable ? null : response.membership.reason ?? 'VN30 breadth unavailable.');
    } catch (reason) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setError(reason instanceof Error ? reason.message : 'VN30 breadth unavailable.');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setUpdating(false);
      }
    }
  }, [data]);

  useEffect(() => {
    void load(false);
    return () => {
      requestIdRef.current += 1;
      abortRef.current?.abort();
    };
    // One page-owned initial request; later refreshes are explicit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    data,
    loading,
    updating,
    error,
    refresh: () => load(false),
  };
};
