import { useCallback, useEffect, useRef, useState } from 'react';
import { stocksApi, type VietnamForeignFlowSymbolHistoryResponse } from '../api/stocks';
import { normalizeVietnamTicker } from '../utils/vietnamWatchlist';

const RETENTION_MS = 300_000;
const RETENTION_LIMIT = 10;
const retained = new Map<string, { data: VietnamForeignFlowSymbolHistoryResponse; retainedAt: number }>();

const readRetained = (ticker: string) => {
  const entry = retained.get(ticker);
  if (!entry || Date.now() - entry.retainedAt > RETENTION_MS) {
    retained.delete(ticker);
    return null;
  }
  return entry.data;
};

const retain = (ticker: string, data: VietnamForeignFlowSymbolHistoryResponse) => {
  retained.delete(ticker);
  retained.set(ticker, { data, retainedAt: Date.now() });
  while (retained.size > RETENTION_LIMIT) retained.delete(retained.keys().next().value as string);
};

export const useForeignFlowSymbolAnalytics = (rawTicker: string | null, open: boolean) => {
  const ticker = normalizeVietnamTicker(rawTicker ?? '');
  const validTicker = /^[A-Z0-9]{1,10}$/.test(ticker) && ticker !== 'ALL';
  const [data, setData] = useState<VietnamForeignFlowSymbolHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

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
    if (!open || !validTicker) {
      setLoading(false);
      setError(null);
      return;
    }
    const previous = readRetained(ticker);
    setData(previous);
    setLoading(true);
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await stocksApi.getVietnamForeignFlowSymbolHistory(ticker, {
        limit: 60,
        forceRefresh,
        signal: controller.signal,
      });
      if (!mountedRef.current || requestId !== requestIdRef.current) return;
      retain(ticker, response);
      setData(response);
    } catch (caught) {
      if (controller.signal.aborted || !mountedRef.current || requestId !== requestIdRef.current) return;
      setError(caught instanceof Error ? caught.message : `Foreign-flow history unavailable for ${ticker}.`);
    } finally {
      if (mountedRef.current && requestId === requestIdRef.current) {
        setLoading(false);
        if (abortRef.current === controller) abortRef.current = null;
      }
    }
  }, [open, ticker, validTicker]);

  useEffect(() => {
    if (!open || !validTicker) {
      requestIdRef.current += 1;
      abortRef.current?.abort();
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }
    void load(false);
  }, [load, open, validTicker]);

  return {
    ticker,
    data: open && data?.ticker === ticker ? data : null,
    loading: open && loading,
    updating: open && loading && data?.ticker === ticker,
    error: open ? error : null,
    retry: useCallback(() => load(false), [load]),
    forceRefresh: useCallback(() => load(true), [load]),
  };
};
