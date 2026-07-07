import { describe, expect, it } from 'vitest';
import {
  formatCompactShareVolume,
  formatCompactVndValue,
  formatCompactVnPrice,
  formatFullSharesTitle,
  formatFullVndTitle,
} from '../vietnamNumberFormat';

describe('Vietnam compact number formatters', () => {
  it('formats VND/share prices as board-style thousand VND without a suffix', () => {
    expect(formatCompactVnPrice(72100)).toBe('72.10');
    expect(formatCompactVnPrice(72662.78)).toBe('72.66');
    expect(formatCompactVnPrice(110120)).toBe('110.12');
    expect(formatCompactVnPrice(null)).toBe('Unavailable');
  });

  it('formats share volume in K/M units', () => {
    expect(formatCompactShareVolume(50000)).toBe('50K');
    expect(formatCompactShareVolume(3000000)).toBe('3.0M');
    expect(formatCompactShareVolume(9715884)).toBe('9.72M');
  });

  it('formats VND trading values in B/T units', () => {
    expect(formatCompactVndValue(7300000000)).toBe('7.3B');
    expect(formatCompactVndValue(1200000000000)).toBe('1.2T');
  });

  it('formats full-value tooltip titles with semantic units', () => {
    expect(formatFullVndTitle(72100)).toBe('72,100 VND');
    expect(formatFullSharesTitle(9715884)).toBe('9,715,884 shares');
  });
});
