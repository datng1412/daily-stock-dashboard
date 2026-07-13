import { describe, expect, it } from 'vitest';
import { getRealtimeSnapshotDisplayState } from '../realtimeSnapshotState';

describe('persisted SSI realtime display state', () => {
  it('never labels a persisted snapshot as live during an active session', () => {
    const state = getRealtimeSnapshotDisplayState({
      quoteStatus: 'ok',
      ageSeconds: 5,
      isStale: true,
      snapshotSource: 'persisted',
      snapshotCapturedAt: '2026-07-10T08:00:00+00:00',
      marketPhaseCode: 'continuous_morning',
      snapshotTimeDisplay: '2026-07-10T08:00:00+00:00',
    });

    expect(state.label).toBe('Last known SSI realtime');
    expect(state.reason).toContain('Waiting for live SSI updates');
    expect(state.label).not.toContain('live');
  });

  it('uses market-closed last-known copy after close', () => {
    const state = getRealtimeSnapshotDisplayState({
      quoteStatus: 'ok',
      ageSeconds: 60,
      isStale: true,
      snapshotSource: 'persisted',
      marketPhaseCode: 'post_close',
      snapshotTimeDisplay: '2026-07-10T08:00:00+00:00',
    });

    expect(state.label).toBe('Last known SSI realtime');
    expect(state.reason).toContain('Market closed — showing last known data.');
  });
});
