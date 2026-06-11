import { describe, expect, it } from 'vitest';
import { getVietnamMarketPhase } from '../vietnamMarketPhase';

const vnDate = (isoWithOffset: string) => new Date(isoWithOffset);

describe('getVietnamMarketPhase', () => {
  it.each([
    ['Monday 08:59 VN', '2026-06-08T08:59:00+07:00', 'Pre-open', 'pre_open', false, false, false],
    ['Monday 09:05 VN', '2026-06-08T09:05:00+07:00', 'ATO opening auction', 'ato', true, true, false],
    ['Monday 10:00 VN', '2026-06-08T10:00:00+07:00', 'Continuous morning', 'continuous_morning', true, false, true],
    ['Monday 12:00 VN', '2026-06-08T12:00:00+07:00', 'Lunch break', 'lunch_break', false, false, false],
    ['Monday 13:30 VN', '2026-06-08T13:30:00+07:00', 'Continuous afternoon', 'continuous_afternoon', true, false, true],
    ['Monday 14:35 VN', '2026-06-08T14:35:00+07:00', 'ATC closing auction', 'atc', true, true, false],
    ['Monday 14:50 VN', '2026-06-08T14:50:00+07:00', 'Post-close', 'post_close', false, false, false],
    ['Monday 15:05 VN', '2026-06-08T15:05:00+07:00', 'Closed', 'closed', false, false, false],
    ['Saturday 10:00 VN', '2026-06-13T10:00:00+07:00', 'Weekend / closed', 'weekend_closed', false, false, false],
  ])('%s -> %s', (_label, timestamp, phase, code, isTradingSession, isAuction, isContinuous) => {
    expect(getVietnamMarketPhase(vnDate(timestamp))).toMatchObject({
      phase,
      code,
      isTradingSession,
      isAuction,
      isContinuous,
      holidayAware: false,
    });
  });
});
