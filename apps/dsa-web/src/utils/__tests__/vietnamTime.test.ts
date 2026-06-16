import { describe, expect, it } from 'vitest';
import {
  formatRelativeAge,
  formatRelativeTime,
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
  it('formats news relative time labels', () => {
    const now = '2026-06-16T12:00:00+07:00';

    expect(formatRelativeTime('2026-06-16T11:59:30+07:00', now)).toBe('Just now');
    expect(formatRelativeTime('2026-06-16T11:45:00+07:00', now)).toBe('15 minutes ago');
    expect(formatRelativeTime('2026-06-16T10:00:00+07:00', now)).toBe('2 hours ago');
    expect(formatRelativeTime('2026-06-15T12:00:00+07:00', now)).toBe('1 day ago');
    expect(formatRelativeTime('2026-06-13T12:00:00+07:00', now)).toBe('3 days ago');
    expect(formatRelativeTime('2026-06-08T12:00:00+07:00', now)).toBe('Jun 8, 2026');
    expect(formatRelativeTime('not-a-date', now)).toBe('Time unavailable');
    expect(formatRelativeTime(null, now)).toBe('Time unavailable');
  });

  it('parses supported news timestamp formats for relative labels', () => {
    const now = '2026-06-16T12:00:00+07:00';

    expect(formatRelativeTime('2026-06-16T11:45:00+07:00', now)).toBe('15 minutes ago');
    expect(formatRelativeTime(1781585100, now)).toBe('15 minutes ago');
    expect(formatRelativeTime(1781585100000, now)).toBe('15 minutes ago');
    expect(formatRelativeTime('2026-06-16 11:45:00', now)).toBe('15 minutes ago');
    expect(formatRelativeTime('16/06/2026 11:45', now)).toBe('15 minutes ago');
    expect(formatRelativeTime('16/06/2026', now)).toBe('12 hours ago');
    expect(formatRelativeTime('32/06/2026 11:45', now)).toBe('Time unavailable');
  });
});
