export const VIETNAM_WATCHLIST_STORAGE_KEY = 'vietnamDashboard.watchlist.v1';
export const VIETNAM_WATCHLIST_MAX_SIZE = 30;

export type VietnamWatchlistLoadResult = {
  tickers: string[];
  usedFallback: boolean;
};

export type VietnamTickerValidationResult =
  | { valid: true; ticker: string }
  | { valid: false; ticker?: string; error: string };

export const normalizeVietnamTicker = (value: string) => {
  const trimmed = value.trim().toUpperCase();
  return trimmed.endsWith('.VN') ? trimmed.slice(0, -3) : trimmed;
};

export const validateVietnamTicker = (
  value: string,
  existingTickers: string[] = [],
  maxSize = VIETNAM_WATCHLIST_MAX_SIZE,
): VietnamTickerValidationResult => {
  const ticker = normalizeVietnamTicker(value);
  if (!ticker) {
    return { valid: false, error: 'Enter a ticker symbol.' };
  }
  if (!/^[A-Z0-9]{1,10}$/.test(ticker)) {
    return { valid: false, ticker, error: 'Use letters and numbers only, up to 10 characters.' };
  }
  if (existingTickers.includes(ticker)) {
    return { valid: false, ticker, error: `${ticker} is already in the watchlist.` };
  }
  if (existingTickers.length >= maxSize) {
    return { valid: false, ticker, error: `Watchlist is limited to ${maxSize} tickers.` };
  }
  return { valid: true, ticker };
};

export const normalizeVietnamWatchlist = (values: string[], maxSize = VIETNAM_WATCHLIST_MAX_SIZE) => {
  const tickers: string[] = [];
  for (const value of values) {
    const result = validateVietnamTicker(value, tickers, maxSize);
    if (!result.valid) {
      return null;
    }
    tickers.push(result.ticker);
  }
  return tickers.length ? tickers : null;
};

export const readVietnamWatchlist = (
  defaultTickers: string[],
  storage: Pick<Storage, 'getItem'> | null | undefined = typeof window === 'undefined' ? null : window.localStorage,
): VietnamWatchlistLoadResult => {
  const fallback = normalizeVietnamWatchlist(defaultTickers) ?? [];
  if (!storage) {
    return { tickers: fallback, usedFallback: false };
  }

  try {
    const raw = storage.getItem(VIETNAM_WATCHLIST_STORAGE_KEY);
    if (!raw) {
      return { tickers: fallback, usedFallback: false };
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.some((value) => typeof value !== 'string')) {
      return { tickers: fallback, usedFallback: true };
    }
    const tickers = normalizeVietnamWatchlist(parsed);
    return tickers ? { tickers, usedFallback: false } : { tickers: fallback, usedFallback: true };
  } catch {
    return { tickers: fallback, usedFallback: true };
  }
};

export const writeVietnamWatchlist = (
  tickers: string[],
  storage: Pick<Storage, 'setItem'> | null | undefined = typeof window === 'undefined' ? null : window.localStorage,
) => {
  if (!storage) return;
  storage.setItem(VIETNAM_WATCHLIST_STORAGE_KEY, JSON.stringify(tickers));
};
