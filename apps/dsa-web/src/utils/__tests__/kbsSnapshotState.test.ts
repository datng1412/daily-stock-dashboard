import { describe, expect, it } from 'vitest';
import { getKbsSnapshotDisplayState } from '../kbsSnapshotState';

const okQuote = {
  quoteStatus: 'ok',
  snapshotTimeDisplay: '2026-06-11T10:15:00+07:00',
};

describe('getKbsSnapshotDisplayState', () => {
  it('marks active phase age 30s as live', () => {
    expect(getKbsSnapshotDisplayState({
      ...okQuote,
      ageSeconds: 30,
      isStale: false,
      marketPhaseCode: 'continuous_morning',
    }).state).toBe('live');
  });

  it('marks active phase age 120s as delayed', () => {
    expect(getKbsSnapshotDisplayState({
      ...okQuote,
      ageSeconds: 120,
      isStale: false,
      marketPhaseCode: 'continuous_morning',
    }).state).toBe('delayed');
  });

  it('marks active phase age 300s as stale during trading', () => {
    expect(getKbsSnapshotDisplayState({
      ...okQuote,
      ageSeconds: 300,
      isStale: false,
      marketPhaseCode: 'continuous_morning',
    }).state).toBe('stale_during_trading');
  });

  it('marks active phase raw stale as stale during trading', () => {
    expect(getKbsSnapshotDisplayState({
      ...okQuote,
      ageSeconds: 120,
      isStale: true,
      staleReason: 'age_gt_60s',
      marketPhaseCode: 'continuous_morning',
    }).state).toBe('stale_during_trading');
  });

  it('marks post-close old snapshots as last available post-close', () => {
    expect(getKbsSnapshotDisplayState({
      ...okQuote,
      ageSeconds: 1200,
      isStale: true,
      staleReason: 'age_gt_60s',
      marketPhaseCode: 'post_close',
    }).state).toBe('last_available_post_close');
  });

  it('marks closed old snapshots as last available closed', () => {
    expect(getKbsSnapshotDisplayState({
      ...okQuote,
      ageSeconds: 1200,
      isStale: true,
      staleReason: 'age_gt_60s',
      marketPhaseCode: 'closed',
    }).state).toBe('last_available_closed');
  });

  it('marks weekend old snapshots as last available weekend', () => {
    expect(getKbsSnapshotDisplayState({
      ...okQuote,
      ageSeconds: 1200,
      isStale: true,
      staleReason: 'age_gt_60s',
      marketPhaseCode: 'weekend_closed',
    }).state).toBe('last_available_weekend');
  });

  it('marks unavailable quote as unavailable', () => {
    expect(getKbsSnapshotDisplayState({
      quoteStatus: 'unavailable',
      ageSeconds: null,
      isStale: null,
      marketPhaseCode: 'continuous_morning',
      snapshotTimeDisplay: null,
    }).state).toBe('unavailable');
  });

  it('marks quote with missing age as unknown', () => {
    expect(getKbsSnapshotDisplayState({
      ...okQuote,
      ageSeconds: null,
      isStale: null,
      marketPhaseCode: 'continuous_morning',
    }).state).toBe('unknown');
  });
});
