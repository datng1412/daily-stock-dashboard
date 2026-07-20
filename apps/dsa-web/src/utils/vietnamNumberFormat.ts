const FULL_NUMBER_FORMATTER = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 2,
});

const compactNumber = (
  value: number,
  scale: number,
  suffix: string,
  options: { minimumFractionDigits?: number; maximumFractionDigits?: number },
) => {
  const scaled = value / scale;
  return `${new Intl.NumberFormat('en-US', {
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
    maximumFractionDigits: options.maximumFractionDigits ?? 2,
  }).format(scaled)}${suffix}`;
};

const finiteNumber = (value?: number | string | null): number | null => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

const FOREIGN_FLOW_INTEGER_FORMATTER = new Intl.NumberFormat('en-US', {
  useGrouping: true,
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const FOREIGN_FLOW_DECIMAL_FORMATTER = new Intl.NumberFormat('en-US', {
  useGrouping: true,
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Deterministic foreign-flow VND display; never relies on the browser locale. */
export const formatForeignFlowValue = (
  value?: number | string | null,
  fallback = '—',
) => {
  const numeric = finiteNumber(value);
  if (numeric === null) return fallback;
  if (numeric === 0) return '0';
  if (Math.abs(numeric) >= 1_000_000_000) {
    return `${FOREIGN_FLOW_DECIMAL_FORMATTER.format(numeric / 1_000_000_000)}Tỷ`;
  }
  return FOREIGN_FLOW_INTEGER_FORMATTER.format(numeric);
};

/** Foreign-flow volumes are always complete share counts, never K/M compact values. */
export const formatForeignFlowVolume = (
  value?: number | string | null,
  fallback = '—',
) => {
  const numeric = finiteNumber(value);
  if (numeric === null) return fallback;
  if (numeric === 0) return '0';
  return FOREIGN_FLOW_INTEGER_FORMATTER.format(numeric);
};

export const formatForeignFlowCount = formatForeignFlowVolume;

export const formatForeignFlowPercent = (
  value?: number | string | null,
  fallback = '—',
) => {
  const numeric = finiteNumber(value);
  if (numeric === null) return fallback;
  return `${FOREIGN_FLOW_DECIMAL_FORMATTER.format(numeric === 0 ? 0 : numeric)}%`;
};

export const formatForeignFlowRatio = (
  value?: number | string | null,
  fallback = '—',
) => {
  const numeric = finiteNumber(value);
  if (numeric === null) return fallback;
  return FOREIGN_FLOW_DECIMAL_FORMATTER.format(numeric === 0 ? 0 : numeric);
};

export type SsiBoardPriceState = 'ceiling' | 'floor' | 'reference' | 'above_reference' | 'below_reference' | 'neutral';
export type SsiBoardPriceRole = 'reference' | 'ceiling' | 'floor';

export const getSsiBoardPriceState = (
  price?: number | string | null,
  reference?: number | string | null,
  ceiling?: number | string | null,
  floor?: number | string | null,
): SsiBoardPriceState => {
  const numericPrice = finiteNumber(price);
  const numericReference = finiteNumber(reference);
  if (numericPrice === null || numericReference === null || numericPrice <= 0 || numericReference <= 0) {
    return 'neutral';
  }
  const numericCeiling = finiteNumber(ceiling);
  const numericFloor = finiteNumber(floor);
  if (numericCeiling !== null && numericCeiling > 0 && numericPrice === numericCeiling) return 'ceiling';
  if (numericFloor !== null && numericFloor > 0 && numericPrice === numericFloor) return 'floor';
  if (numericPrice === numericReference) return 'reference';
  if (numericPrice > numericReference) return 'above_reference';
  if (numericPrice < numericReference) return 'below_reference';
  return 'neutral';
};

export const ssiBoardPriceStateClass = (state: SsiBoardPriceState) => {
  if (state === 'ceiling') return 'text-ceiling-purple';
  if (state === 'floor') return 'text-cyan';
  if (state === 'reference') return 'text-reference-yellow';
  if (state === 'above_reference') return 'text-success';
  if (state === 'below_reference') return 'text-danger';
  return 'text-secondary-text';
};

export const ssiBoardPriceValueClass = (
  price?: number | string | null,
  reference?: number | string | null,
  ceiling?: number | string | null,
  floor?: number | string | null,
) => ssiBoardPriceStateClass(getSsiBoardPriceState(price, reference, ceiling, floor));

export const getSsiBoardRoleClass = (role: SsiBoardPriceRole) => {
  if (role === 'ceiling') return 'text-ceiling-purple';
  if (role === 'floor') return 'text-cyan';
  return 'text-reference-yellow';
};

export const REFERENCE_PRICE_CLASS = getSsiBoardRoleClass('reference');
export const CEILING_PRICE_CLASS = getSsiBoardRoleClass('ceiling');
export const FLOOR_PRICE_CLASS = getSsiBoardRoleClass('floor');

const signPrefix = (value: number) => {
  if (value > 0) return '+';
  if (value < 0) return '-';
  return '';
};

export const formatCompactVnPrice = (value?: number | string | null, fallback = 'Unavailable') => {
  const numeric = finiteNumber(value);
  if (numeric === null) {
    if (typeof value === 'string' && value.trim()) return value;
    return fallback;
  }
  const boardPrice = numeric / 1_000;
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(boardPrice);
};

export const formatCompactShareVolume = (
  value?: number | string | null,
  fallback = 'Unavailable',
  signed = false,
) => {
  const numeric = finiteNumber(value);
  if (numeric === null) {
    if (typeof value === 'string' && value.trim()) return value;
    return fallback;
  }
  const absolute = Math.abs(numeric);
  const sign = signed ? signPrefix(numeric) : '';
  if (absolute >= 1_000_000) {
    return `${sign}${compactNumber(absolute, 1_000_000, 'M', {
      minimumFractionDigits: absolute % 1_000_000 === 0 && absolute < 10_000_000 ? 1 : 0,
      maximumFractionDigits: 2,
    })}`;
  }
  if (absolute >= 1_000) {
    return `${sign}${compactNumber(absolute, 1_000, 'K', {
      maximumFractionDigits: 2,
    })}`;
  }
  return `${sign}${FULL_NUMBER_FORMATTER.format(absolute)}`;
};

export const formatCompactVndValue = (
  value?: number | string | null,
  fallback = 'Unavailable',
  signed = false,
) => {
  const numeric = finiteNumber(value);
  if (numeric === null) {
    if (typeof value === 'string' && value.trim()) return value;
    return fallback;
  }
  const absolute = Math.abs(numeric);
  const sign = signed ? signPrefix(numeric) : '';
  if (absolute >= 1_000_000_000_000) {
    return `${sign}${compactNumber(absolute, 1_000_000_000_000, 'T', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}`;
  }
  if (absolute >= 1_000_000_000) {
    return `${sign}${compactNumber(absolute, 1_000_000_000, 'B', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}`;
  }
  if (absolute >= 1_000_000) {
    return `${sign}${compactNumber(absolute, 1_000_000, 'M', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}`;
  }
  if (absolute >= 1_000) {
    return `${sign}${compactNumber(absolute, 1_000, 'K', {
      maximumFractionDigits: 1,
    })}`;
  }
  return `${sign}${FULL_NUMBER_FORMATTER.format(absolute)}`;
};

export const formatFullVndTitle = (value?: number | string | null) => {
  const numeric = finiteNumber(value);
  if (numeric === null) return undefined;
  return `${FULL_NUMBER_FORMATTER.format(numeric)} VND`;
};

export const formatFullSharesTitle = (value?: number | string | null) => {
  const numeric = finiteNumber(value);
  if (numeric === null) return undefined;
  return `${FULL_NUMBER_FORMATTER.format(numeric)} shares`;
};
