import { useCallback, useEffect, useRef, useState } from 'react';

import { stocksApi, type VietnamSectorStrengthResponse } from '../api/stocks';

export const useVietnamSectorStrength = () => {
  const [data, setData] = useState<VietnamSectorStrengthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dataRef = useRef<VietnamSectorStrengthResponse | null>(null);
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async (forceRefresh = false) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    if (dataRef.current) setUpdating(true);
    else setLoading(true);
    setError(null);
    try {
      const response = await stocksApi.getVietnamSectorStrength({
        forceRefresh,
        signal: controller.signal,
      });
      if (requestId !== requestIdRef.current) return;
      if (response.usable || !dataRef.current) {
        dataRef.current = response;
        setData(response);
      }
      setError(response.usable ? null : 'Dữ liệu ngành VN30 chưa khả dụng.');
    } catch (reason) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setError(reason instanceof Error ? reason.message : 'Dữ liệu ngành VN30 chưa khả dụng.');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setUpdating(false);
      }
    }
  }, []);

  useEffect(() => {
    void load(false);
    return () => {
      requestIdRef.current += 1;
      abortRef.current?.abort();
    };
  }, [load]);

  return {
    data,
    loading,
    updating,
    error,
    refresh: () => load(false),
    forceRefresh: () => load(true),
  };
};
