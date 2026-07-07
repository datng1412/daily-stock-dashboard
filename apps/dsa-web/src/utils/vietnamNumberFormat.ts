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
