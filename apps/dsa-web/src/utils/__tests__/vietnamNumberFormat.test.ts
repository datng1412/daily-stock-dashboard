import { describe, expect, it } from 'vitest';
import {
  formatCompactShareVolume,
  formatCompactVndValue,
  formatCompactVnPrice,
  formatFullSharesTitle,
  formatFullVndTitle,
  getPriceReferenceDirection,
  priceReferenceValueClass,
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

  it('classifies daily price direction against reference price', () => {
    expect(getPriceReferenceDirection(101000, 100000)).toBe('above');
    expect(getPriceReferenceDirection(99000, 100000)).toBe('below');
    expect(getPriceReferenceDirection(100000, 100000)).toBe('equal');
    expect(getPriceReferenceDirection(null, 100000)).toBe('neutral');
    expect(getPriceReferenceDirection(100000, null)).toBe('neutral');
    expect(getPriceReferenceDirection(100000, 0)).toBe('neutral');
  });

  it('maps reference-price direction to semantic UI classes', () => {
    expect(priceReferenceValueClass(101000, 100000)).toBe('text-success');
    expect(priceReferenceValueClass(99000, 100000)).toBe('text-danger');
    expect(priceReferenceValueClass(100000, 100000)).toBe('text-warning');
    expect(priceReferenceValueClass(null, 100000)).toBe('text-secondary-text');
  });
});
