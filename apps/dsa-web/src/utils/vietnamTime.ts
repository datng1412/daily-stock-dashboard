const VIETNAM_TIME_ZONE = 'Asia/Ho_Chi_Minh';
const EMPTY_TIME = '—';

export type MozyTimestampInput = string | number | Date | null | undefined;

export const parseMozyTimestamp = (input: MozyTimestampInput): Date | null => {
  if (input === null || input === undefined || input === '') return null;
  if (input instanceof Date) {
    const value = input.getTime();
    return Number.isNaN(value) ? null : new Date(value);
  }

  if (typeof input === 'number' || /^\d+$/.test(String(input).trim())) {
    const numeric = Number(input);
    if (!Number.isFinite(numeric)) return null;
    const milliseconds = numeric >= 1_000_000_000_000 ? numeric : numeric * 1000;
    const date = new Date(milliseconds);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const date = new Date(input);
  return Number.isNaN(date.getTime()) ? null : date;
};

const partsToMap = (parts: Intl.DateTimeFormatPart[]) =>
  Object.fromEntries(parts.map((part) => [part.type, part.value]));

export const formatVietnamDateTime = (input: MozyTimestampInput): string => {
  const date = parseMozyTimestamp(input);
  if (!date) return EMPTY_TIME;
  const parts = partsToMap(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: VIETNAM_TIME_ZONE,
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(date),
  );
  return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute} VN`;
};

export const formatVietnamTime = (input: MozyTimestampInput): string => {
  const date = parseMozyTimestamp(input);
  if (!date) return EMPTY_TIME;
  const parts = partsToMap(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: VIETNAM_TIME_ZONE,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(date),
  );
  return `${parts.hour}:${parts.minute}:${parts.second} VN`;
};

export const formatRelativeAge = (input: MozyTimestampInput, now: MozyTimestampInput = new Date()): string => {
  const date = parseMozyTimestamp(input);
  const reference = parseMozyTimestamp(now);
  if (!date || !reference) return EMPTY_TIME;
  const diffSeconds = Math.max(0, Math.floor((reference.getTime() - date.getTime()) / 1000));
  if (diffSeconds < 60) return `${diffSeconds}s ago`;
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};
