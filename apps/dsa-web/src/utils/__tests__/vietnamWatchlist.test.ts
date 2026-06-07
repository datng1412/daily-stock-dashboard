import { describe, expect, it } from 'vitest';
import {
  VIETNAM_WATCHLIST_MAX_SIZE,
  VIETNAM_WATCHLIST_STORAGE_KEY,
  normalizeVietnamTicker,
  readVietnamWatchlist,
  validateVietnamTicker,
} from '../vietnamWatchlist';

const makeStorage = (initialValue: string | null) => ({
  getItem: (key: string) => (key === VIETNAM_WATCHLIST_STORAGE_KEY ? initialValue : null),
});

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
});
