import { useCallback, useEffect, useRef, useState } from 'react';

import { stocksApi, type VietnamRelativeStrengthResponse } from '../api/stocks';

const normalizeTicker = (value?: string | null) => value?.trim().toUpperCase() ?? '';

export const useVietnamRelativeStrength = (ticker?: string | null) => {
  const [data, setData] = useState<VietnamRelativeStrengthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dataRef = useRef<VietnamRelativeStrengthResponse | null>(null);
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const symbol = normalizeTicker(ticker);

  const load = useCallback(async (forceRefresh = false) => {
    if (!/^[A-Z0-9]{2,10}$/.test(symbol)) return;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const retainedForSymbol = dataRef.current?.ticker === symbol ? dataRef.current : null;
    if (retainedForSymbol) setUpdating(true);
    else {
      dataRef.current = null;
      setData(null);
      setLoading(true);
    }
    setError(null);
    try {
      const response = await stocksApi.getVietnamRelativeStrength(symbol, {
        forceRefresh,
        signal: controller.signal,
      });
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      if (response.ticker !== symbol) return;
      if (response.usable || !retainedForSymbol) {
        dataRef.current = response;
        setData(response);
      }
      setError(response.usable ? null : 'Relative performance is unavailable for this ticker.');
    } catch (reason) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setError(reason instanceof Error ? reason.message : 'Relative performance is unavailable.');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setUpdating(false);
      }
    }
  }, [symbol]);

  useEffect(() => {
    requestIdRef.current += 1;
    abortRef.current?.abort();
    if (!/^[A-Z0-9]{2,10}$/.test(symbol)) {
      dataRef.current = null;
      setData(null);
      setLoading(false);
      setUpdating(false);
      setError(null);
      return;
    }
    void load(false);
    return () => {
      requestIdRef.current += 1;
      abortRef.current?.abort();
    };
  }, [load, symbol]);

  return {
    data,
    loading,
    updating,
    error,
    refresh: () => load(false),
    forceRefresh: () => load(true),
  };
};
