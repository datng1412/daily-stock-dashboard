import { describe, expect, it } from 'vitest';
import { foreignFlowSign, foreignFlowSignChartColor, foreignFlowSignTextClass } from '../foreignFlowSign';

describe('foreign-flow sign styling', () => {
  it.each([
    [1, 'positive', 'text-success', 'hsl(var(--success))'],
    [-1, 'negative', 'text-danger', 'hsl(var(--danger))'],
    [0, 'zero', 'text-foreground', 'hsl(var(--foreground))'],
    [null, 'unavailable', 'text-secondary-text', 'hsl(var(--secondary-text))'],
    [Number.NaN, 'unavailable', 'text-secondary-text', 'hsl(var(--secondary-text))'],
  ] as const)('maps %s without conflating zero and unavailable', (value, sign, textClass, chartColor) => {
    expect(foreignFlowSign(value)).toBe(sign);
    expect(foreignFlowSignTextClass(value)).toBe(textClass);
    expect(foreignFlowSignChartColor(value)).toBe(chartColor);
  });
});
