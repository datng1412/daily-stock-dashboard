import { describe, expect, it } from 'vitest';
import {
  formatRelativeAge,
  formatVietnamDateTime,
  formatVietnamTime,
  parseMozyTimestamp,
} from '../vietnamTime';

describe('Vietnam time helpers', () => {
  it('formats UTC ISO timestamps into Vietnam time', () => {
    expect(formatVietnamDateTime('2026-06-03T07:00:00+00:00')).toBe('03/06/2026 14:00 VN');
    expect(formatVietnamDateTime('2026-06-03T07:00:00Z')).toBe('03/06/2026 14:00 VN');
  });

  it('treats Mozyfin numeric timestamps as Unix seconds unless clearly milliseconds', () => {
    expect(formatVietnamDateTime(1780470000)).toBe('03/06/2026 14:00 VN');
    expect(formatVietnamDateTime('1780470000')).toBe('03/06/2026 14:00 VN');
    expect(formatVietnamDateTime(1780470000000)).toBe('03/06/2026 14:00 VN');
  });

  it('formats Vietnam-only time and relative age', () => {
    expect(formatVietnamTime('2026-06-03T07:00:23Z')).toBe('14:00:23 VN');
    expect(formatRelativeAge('2026-06-03T07:00:00Z', '2026-06-03T07:00:42Z')).toBe('42s ago');
    expect(formatRelativeAge('2026-06-03T07:00:00Z', '2026-06-03T07:03:00Z')).toBe('3m ago');
    expect(formatRelativeAge('2026-06-03T07:00:00Z', '2026-06-03T08:00:00Z')).toBe('1h ago');
  });

  it('handles invalid or empty inputs safely', () => {
    expect(parseMozyTimestamp(null)).toBeNull();
    expect(parseMozyTimestamp(undefined)).toBeNull();
    expect(parseMozyTimestamp('not-a-date')).toBeNull();
    expect(formatVietnamDateTime(null)).toBe('—');
    expect(formatVietnamDateTime('not-a-date')).toBe('—');
  });
});
