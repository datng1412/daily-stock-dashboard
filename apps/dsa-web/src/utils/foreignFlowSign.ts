export type ForeignFlowSign = 'positive' | 'negative' | 'zero' | 'unavailable';

export const foreignFlowSign = (value: number | null | undefined): ForeignFlowSign => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'unavailable';
  if (value > 0) return 'positive';
  if (value < 0) return 'negative';
  return 'zero';
};

export const foreignFlowSignTextClass = (value: number | null | undefined): string => {
  const sign = foreignFlowSign(value);
  if (sign === 'positive') return 'text-success';
  if (sign === 'negative') return 'text-danger';
  if (sign === 'unavailable') return 'text-secondary-text';
  return 'text-foreground';
};

export const foreignFlowSignChartColor = (value: number | null | undefined): string => {
  const sign = foreignFlowSign(value);
  if (sign === 'positive') return 'hsl(var(--success))';
  if (sign === 'negative') return 'hsl(var(--danger))';
  if (sign === 'unavailable') return 'hsl(var(--secondary-text))';
  return 'hsl(var(--foreground))';
};
