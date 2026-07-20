import { describe, expect, it } from 'vitest';
import {
  formatCompactShareVolume,
  formatCompactVndValue,
  formatCompactVnPrice,
  formatFullSharesTitle,
  formatFullVndTitle,
  formatForeignFlowCount,
  formatForeignFlowPercent,
  formatForeignFlowRatio,
  formatForeignFlowValue,
  formatForeignFlowVolume,
  getSsiBoardPriceState,
  getSsiBoardRoleClass,
  ssiBoardPriceValueClass,
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

  it('formats foreign-flow VND with deterministic decimal and grouping separators', () => {
    expect(formatForeignFlowValue(14_500_000_000)).toBe('14.50Tỷ');
    expect(formatForeignFlowValue(150_050_000_000)).toBe('150.05Tỷ');
    expect(formatForeignFlowValue(150_000_000_000)).toBe('150.00Tỷ');
    expect(formatForeignFlowValue(-14_500_000_000)).toBe('-14.50Tỷ');
    expect(formatForeignFlowValue(150_500_505)).toBe('150,500,505');
    expect(formatForeignFlowValue(999_999_999)).toBe('999,999,999');
    expect(formatForeignFlowValue(1_000_000_000)).toBe('1.00Tỷ');
    expect(formatForeignFlowValue(1_250_000_000_000)).toBe('1,250.00Tỷ');
  });

  it('formats foreign-flow shares, counts, percentages, ratios, zero, and unavailable values', () => {
    expect(formatForeignFlowVolume(250_000)).toBe('250,000');
    expect(formatForeignFlowVolume(1_500_000)).toBe('1,500,000');
    expect(formatForeignFlowVolume(-250_000)).toBe('-250,000');
    expect(formatForeignFlowCount(250_000)).toBe('250,000');
    expect(formatForeignFlowPercent(87.5)).toBe('87.50%');
    expect(formatForeignFlowPercent(100)).toBe('100.00%');
    expect(formatForeignFlowRatio(-1.254)).toBe('-1.25');
    expect(formatForeignFlowValue(-0)).toBe('0');
    expect(formatForeignFlowVolume(0)).toBe('0');
    expect(formatForeignFlowValue(null)).toBe('—');
    expect(formatForeignFlowValue(Number.NaN)).toBe('—');
    expect(formatForeignFlowValue(Number.POSITIVE_INFINITY)).toBe('—');
  });

  it('classifies prices by SSI board priority', () => {
    expect(getSsiBoardPriceState(107000, 100000, 107000, 93000)).toBe('ceiling');
    expect(getSsiBoardPriceState(93000, 100000, 107000, 93000)).toBe('floor');
    expect(getSsiBoardPriceState(100000, 100000, 107000, 93000)).toBe('reference');
    expect(getSsiBoardPriceState(101000, 100000, 107000, 93000)).toBe('above_reference');
    expect(getSsiBoardPriceState(99000, 100000, 107000, 93000)).toBe('below_reference');
    expect(getSsiBoardPriceState(100000, null, 107000, 93000)).toBe('neutral');
    expect(getSsiBoardPriceState(100000, 0, 107000, 93000)).toBe('neutral');
    expect(getSsiBoardPriceState(107000, 100000, 107000, 93000)).toBe('ceiling');
    expect(getSsiBoardPriceState(93000, 100000, 107000, 93000)).toBe('floor');
  });

  it('maps SSI board states and static roles to board color classes', () => {
    expect(ssiBoardPriceValueClass(107000, 100000, 107000, 93000)).toBe('text-ceiling-purple');
    expect(ssiBoardPriceValueClass(93000, 100000, 107000, 93000)).toBe('text-cyan');
    expect(ssiBoardPriceValueClass(100000, 100000, 107000, 93000)).toBe('text-reference-yellow');
    expect(ssiBoardPriceValueClass(101000, 100000, 107000, 93000)).toBe('text-success');
    expect(ssiBoardPriceValueClass(99000, 100000, 107000, 93000)).toBe('text-danger');
    expect(ssiBoardPriceValueClass(null, 100000, 107000, 93000)).toBe('text-secondary-text');
    expect(getSsiBoardRoleClass('reference')).toBe('text-reference-yellow');
    expect(getSsiBoardRoleClass('ceiling')).toBe('text-ceiling-purple');
    expect(getSsiBoardRoleClass('floor')).toBe('text-cyan');
  });
});
