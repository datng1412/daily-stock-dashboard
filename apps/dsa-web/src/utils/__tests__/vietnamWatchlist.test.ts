import { describe, expect, it } from 'vitest';
import {
  VIETNAM_WATCHLIST_MAX_SIZE,
  VIETNAM_WATCHLIST_PRESETS,
  VIETNAM_WATCHLIST_STORAGE_KEY,
  getVietnamPresetTickers,
  moveVietnamTicker,
  normalizeVietnamTicker,
  readVietnamWatchlist,
  validateVietnamTicker,
  writeVietnamWatchlist,
} from '../vietnamWatchlist';

const makeStorage = (initialValue: string | null) => ({
  getItem: (key: string) => (key === VIETNAM_WATCHLIST_STORAGE_KEY ? initialValue : null),
});

const makeWritableStorage = () => {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
  };
};

describe('Vietnam watchlist helpers', () => {
  it('normalizes ticker input', () => {
    expect(normalizeVietnamTicker(' fpt ')).toBe('FPT');
    expect(normalizeVietnamTicker('fpt.vn')).toBe('FPT');
    expect(normalizeVietnamTicker('vpB.Vn')).toBe('VPB');
  });

  it('accepts letters and numbers up to 10 characters', () => {
    expect(validateVietnamTicker('abc123')).toEqual({ valid: true, ticker: 'ABC123' });
    expect(validateVietnamTicker('ABC1234567')).toEqual({ valid: true, ticker: 'ABC1234567' });
  });

  it('rejects empty, duplicate, oversized, and invalid-character tickers', () => {
    expect(validateVietnamTicker('')).toMatchObject({ valid: false });
    expect(validateVietnamTicker('FPT', ['FPT'])).toMatchObject({ valid: false, ticker: 'FPT' });
    expect(validateVietnamTicker('ABC12345678')).toMatchObject({ valid: false, ticker: 'ABC12345678' });
    expect(validateVietnamTicker('FP T')).toMatchObject({ valid: false, ticker: 'FP T' });
    expect(validateVietnamTicker('FPT;rm')).toMatchObject({ valid: false, ticker: 'FPT;RM' });
  });

  it('rejects additions beyond max watchlist size', () => {
    const existing = Array.from({ length: VIETNAM_WATCHLIST_MAX_SIZE }, (_, index) => `VN${index}`);
    expect(validateVietnamTicker('FPT', existing)).toMatchObject({
      valid: false,
      ticker: 'FPT',
    });
  });

  it('loads a valid stored watchlist as normalized tickers', () => {
    const result = readVietnamWatchlist(['FPT', 'VPB'], makeStorage(JSON.stringify([' msb ', 'acb.vn'])));
    expect(result).toEqual({ tickers: ['MSB', 'ACB'], usedFallback: false });
  });

  it('falls back to defaults when localStorage is empty or invalid', () => {
    expect(readVietnamWatchlist(['FPT', 'VPB'], makeStorage(null))).toEqual({
      tickers: ['FPT', 'VPB'],
      usedFallback: false,
    });
    expect(readVietnamWatchlist(['FPT', 'VPB'], makeStorage('{bad json'))).toEqual({
      tickers: ['FPT', 'VPB'],
      usedFallback: true,
    });
    expect(readVietnamWatchlist(['FPT', 'VPB'], makeStorage(JSON.stringify(['FPT', 'FPT'])))).toEqual({
      tickers: ['FPT', 'VPB'],
      usedFallback: true,
    });
    expect(readVietnamWatchlist(['FPT', 'VPB'], makeStorage(JSON.stringify(['FPT', 'BAD SYMBOL'])))).toEqual({
      tickers: ['FPT', 'VPB'],
      usedFallback: true,
    });
  });

  it('defines normalized preset lists within the max watchlist size', () => {
    expect(VIETNAM_WATCHLIST_PRESETS.map((preset) => preset.id)).toEqual(['banks', 'tech']);
    for (const preset of VIETNAM_WATCHLIST_PRESETS) {
      const normalized = getVietnamPresetTickers(preset.id);
      expect(normalized).toEqual(preset.tickers);
      expect(normalized?.length).toBeLessThanOrEqual(VIETNAM_WATCHLIST_MAX_SIZE);
    }
  });

  it('returns preset tickers and handles invalid preset ids safely', () => {
    expect(getVietnamPresetTickers('banks')).toContain('VCB');
    expect(getVietnamPresetTickers('tech')).toEqual(['FPT', 'CMG', 'ELC', 'VGI', 'VTP', 'CTR']);
    expect(getVietnamPresetTickers('my', [' fpt.vn ', 'vpB'])).toEqual(['FPT', 'VPB']);
    expect(getVietnamPresetTickers('missing' as never)).toBeNull();
  });

  it('moves tickers up and down without changing invalid edge positions', () => {
    expect(moveVietnamTicker(['FPT', 'VPB', 'MSB'], 'MSB', 'up')).toEqual(['FPT', 'MSB', 'VPB']);
    expect(moveVietnamTicker(['FPT', 'VPB', 'MSB'], 'FPT', 'down')).toEqual(['VPB', 'FPT', 'MSB']);
    expect(moveVietnamTicker(['FPT', 'VPB'], 'FPT', 'up')).toEqual(['FPT', 'VPB']);
    expect(moveVietnamTicker(['FPT', 'VPB'], 'VPB', 'down')).toEqual(['FPT', 'VPB']);
    expect(moveVietnamTicker(['FPT', 'VPB'], 'MSB', 'up')).toEqual(['FPT', 'VPB']);
  });

  it('persists reordered watchlists as normalized arrays', () => {
    const storage = makeWritableStorage();
    writeVietnamWatchlist(['fpt.vn', 'MSB', 'VPB'], storage);
    expect(readVietnamWatchlist(['FPT'], storage)).toEqual({
      tickers: ['FPT', 'MSB', 'VPB'],
      usedFallback: false,
    });
  });

  it('does not persist invalid watchlists', () => {
    const storage = makeWritableStorage();
    expect(() => writeVietnamWatchlist(['FPT', 'FPT'], storage)).toThrow('Invalid Vietnam watchlist');
    expect(storage.getItem(VIETNAM_WATCHLIST_STORAGE_KEY)).toBeNull();
  });
});
