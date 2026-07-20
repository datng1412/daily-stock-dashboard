import { normalizeVietnamTicker, VIETNAM_WATCHLIST_MAX_SIZE } from './vietnamWatchlist';

export const VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY = 'vnDashboard.customWatchlist.v1';

export type VietnamForeignFlowScope = {
  tickers: string[];
  totalNormalizedCount: number;
  invalidCount: number;
  limited: boolean;
};

const storageOrNull = (): Pick<Storage, 'getItem'> | null => {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

export const readVietnamCustomWatchlistValues = (
  storage: Pick<Storage, 'getItem'> | null | undefined = storageOrNull(),
): string[] => {
  if (!storage) return [];
  try {
    const raw = storage.getItem(VIETNAM_CUSTOM_WATCHLIST_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.every((value) => typeof value === 'string') ? parsed : [];
  } catch {
    return [];
  }
};

export const resolveVietnamForeignFlowScope = (
  values: string[],
  maxSize = VIETNAM_WATCHLIST_MAX_SIZE,
): VietnamForeignFlowScope => {
  const seen = new Set<string>();
  const normalized: string[] = [];
  let invalidCount = 0;

  for (const value of values) {
    const ticker = normalizeVietnamTicker(value);
    if (!/^[A-Z0-9]{1,10}$/.test(ticker) || ticker === 'ALL') {
      invalidCount += 1;
      continue;
    }
    if (seen.has(ticker)) continue;
    seen.add(ticker);
    normalized.push(ticker);
  }

  return {
    tickers: normalized.slice(0, maxSize),
    totalNormalizedCount: normalized.length,
    invalidCount,
    limited: normalized.length > maxSize,
  };
};
