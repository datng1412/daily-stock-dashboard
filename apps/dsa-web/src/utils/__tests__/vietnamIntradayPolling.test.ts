import { describe, expect, it } from 'vitest';

import {
  getNextVietnamIntradayAction,
  getVietnamScheduledSessionState,
  shouldPollCurrentIntraday,
  vietnamIntradayStatusLabel,
  vietnamTodayIso,
} from '../vietnamIntradayPolling';

describe('Vietnam intraday polling helpers', () => {
  it('derives the Vietnam date from an absolute timestamp', () => {
    expect(vietnamTodayIso(new Date('2026-07-15T18:30:00Z'))).toBe('2026-07-16');
  });

  it.each([
    ['2026-07-16T01:00:00Z', 'pre_open'],
    ['2026-07-16T02:16:00Z', 'continuous_morning'],
    ['2026-07-16T05:00:00Z', 'lunch'],
    ['2026-07-16T06:01:00Z', 'continuous_afternoon'],
    ['2026-07-16T07:31:00Z', 'atc'],
    ['2026-07-16T07:46:00Z', 'closed'],
    ['2026-07-18T02:16:00Z', 'closed'],
  ])('classifies %s as %s', (timestamp, expected) => {
    expect(getVietnamScheduledSessionState(new Date(timestamp))).toBe(expected);
  });

  it('aligns active polling to the current minute boundary plus seven seconds', () => {
    expect(getNextVietnamIntradayAction(new Date('2026-07-16T02:16:05Z'))).toEqual({ delayMs: 2_000, kind: 'poll' });
    expect(getNextVietnamIntradayAction(new Date('2026-07-16T02:16:08Z'))).toEqual({ delayMs: 59_000, kind: 'poll' });
  });

  it('schedules one afternoon wake-up across lunch and one post-close reconciliation', () => {
    expect(getNextVietnamIntradayAction(new Date('2026-07-16T04:29:50Z'))).toEqual({
      delayMs: 5_417_000,
      kind: 'afternoon_resume',
    });
    expect(getNextVietnamIntradayAction(new Date('2026-07-16T05:00:00Z'))).toEqual({
      delayMs: 3_607_000,
      kind: 'afternoon_resume',
    });
    expect(getNextVietnamIntradayAction(new Date('2026-07-16T07:44:50Z'))).toEqual({
      delayMs: 30_000,
      kind: 'post_close',
    });
  });

  it('uses one opening wake-up and no recurring requests after close', () => {
    expect(getNextVietnamIntradayAction(new Date('2026-07-16T01:00:00Z'))).toEqual({
      delayMs: 4_507_000,
      kind: 'morning_resume',
    });
    expect(getNextVietnamIntradayAction(new Date('2026-07-16T08:00:00Z'))).toBeNull();
    expect(shouldPollCurrentIntraday('lunch')).toBe(false);
  });

  it('maps honest user-facing states without a live label', () => {
    expect(vietnamIntradayStatusLabel('completed', 'completed', true)).toBe('Completed');
    expect(vietnamIntradayStatusLabel('pre_open', 'unavailable', false)).toBe('Pre-open');
    expect(vietnamIntradayStatusLabel('lunch', 'delayed', true)).toBe('Lunch break');
    expect(vietnamIntradayStatusLabel('closed', 'delayed', true)).toBe('Closed');
    expect(vietnamIntradayStatusLabel('continuous_morning', 'updating', true)).toBe('Updating');
    expect(vietnamIntradayStatusLabel('continuous_afternoon', 'delayed', true)).toBe('Delayed');
    expect(vietnamIntradayStatusLabel('atc', 'stale', true)).toBe('Stale');
    expect(vietnamIntradayStatusLabel('continuous_morning', 'unavailable', false)).toBe('No data yet');
  });
});
