export const VIETNAM_WATCHLIST_STORAGE_KEY = 'vietnamDashboard.watchlist.v1';
export const VIETNAM_WATCHLIST_MAX_SIZE = 30;

export type VietnamWatchlistPresetId = 'my' | 'banks' | 'tech';

export type VietnamWatchlistPreset = {
  id: Exclude<VietnamWatchlistPresetId, 'my'>;
  label: string;
  description: string;
  tickers: string[];
};

export type VietnamWatchlistLoadResult = {
  tickers: string[];
  usedFallback: boolean;
};

export type VietnamTickerValidationResult =
  | { valid: true; ticker: string }
  | { valid: false; ticker?: string; error: string };

export const VIETNAM_WATCHLIST_PRESETS: VietnamWatchlistPreset[] = [
  {
    id: 'banks',
    label: 'Banks',
    description: 'Common VN bank tickers; preset list only.',
    tickers: ['VCB', 'BID', 'CTG', 'TCB', 'VPB', 'MBB', 'ACB', 'STB', 'HDB', 'VIB', 'SHB', 'MSB', 'TPB', 'LPB', 'SSB', 'EIB'],
  },
  {
    id: 'tech',
    label: 'Tech',
    description: 'Common VN technology and telecom infrastructure tickers; preset list only.',
    tickers: ['FPT', 'CMG', 'ELC', 'VGI', 'VTP', 'CTR'],
  },
];

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

export const getVietnamPresetTickers = (presetId: VietnamWatchlistPresetId, myWatchlist: string[] = []) => {
  if (presetId === 'my') {
    return normalizeVietnamWatchlist(myWatchlist);
  }
  const preset = VIETNAM_WATCHLIST_PRESETS.find((item) => item.id === presetId);
  return preset ? normalizeVietnamWatchlist(preset.tickers) : null;
};

export const moveVietnamTicker = (tickers: string[], ticker: string, direction: 'up' | 'down') => {
  const index = tickers.indexOf(ticker);
  if (index < 0) return tickers;
  const nextIndex = direction === 'up' ? index - 1 : index + 1;
  if (nextIndex < 0 || nextIndex >= tickers.length) return tickers;
  const nextTickers = [...tickers];
  [nextTickers[index], nextTickers[nextIndex]] = [nextTickers[nextIndex], nextTickers[index]];
  return nextTickers;
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
  const normalized = normalizeVietnamWatchlist(tickers);
  if (!normalized) {
    throw new Error('Invalid Vietnam watchlist');
  }
  storage.setItem(VIETNAM_WATCHLIST_STORAGE_KEY, JSON.stringify(normalized));
};
