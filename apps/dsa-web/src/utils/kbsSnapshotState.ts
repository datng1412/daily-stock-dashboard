export type KbsSnapshotDisplayState =
  | 'live'
  | 'delayed'
  | 'stale_during_trading'
  | 'last_available_post_close'
  | 'last_available_closed'
  | 'last_available_weekend'
  | 'unavailable'
  | 'unknown';

export type KbsSnapshotDisplaySeverity = 'ok' | 'info' | 'warning' | 'error' | 'unknown';

export type KbsSnapshotDisplayResult = {
  state: KbsSnapshotDisplayState;
  label: string;
  reason: string;
  severity: KbsSnapshotDisplaySeverity;
};

const ACTIVE_PHASES = new Set(['ato', 'continuous_morning', 'continuous_afternoon', 'atc']);

const unavailableStatuses = new Set(['unavailable', 'error']);

const ageLabel = (ageSeconds?: number | null) => {
  if (ageSeconds === null || ageSeconds === undefined || Number.isNaN(ageSeconds)) return 'age unavailable';
  if (ageSeconds < 60) return `${ageSeconds}s old`;
  const minutes = Math.floor(ageSeconds / 60);
  const seconds = ageSeconds % 60;
  return seconds === 0 ? `${minutes}m old` : `${minutes}m ${seconds}s old`;
};

const result = (
  state: KbsSnapshotDisplayState,
  label: string,
  reason: string,
  severity: KbsSnapshotDisplaySeverity,
): KbsSnapshotDisplayResult => ({ state, label, reason, severity });

export function getKbsSnapshotDisplayState(args: {
  quoteStatus?: string | null;
  ageSeconds?: number | null;
  isStale?: boolean | null;
  staleReason?: string | null;
  marketPhaseCode?: string | null;
  snapshotTimeDisplay?: string | null;
}): KbsSnapshotDisplayResult {
  const quoteStatus = args.quoteStatus?.toLowerCase() ?? null;
  if (quoteStatus && unavailableStatuses.has(quoteStatus)) {
    return result(
      'unavailable',
      'SSI realtime unavailable',
      'SSI realtime provider returned unavailable or error status.',
      'error',
    );
  }

  if (!quoteStatus && !args.snapshotTimeDisplay) {
    return result(
      'unavailable',
      'SSI realtime unavailable',
      'No SSI realtime quote is available for this ticker.',
      'error',
    );
  }

  if (args.ageSeconds === null || args.ageSeconds === undefined || Number.isNaN(args.ageSeconds)) {
    return result(
      'unknown',
      'SSI realtime time unknown',
      'SSI realtime snapshot exists, but its timestamp could not be parsed.',
      'unknown',
    );
  }

  const phaseCode = args.marketPhaseCode ?? 'unknown';
  const age = Math.max(0, Math.trunc(args.ageSeconds));
  const ageText = ageLabel(age);
  const rawStaleReason = args.staleReason ? ` Raw stale reason: ${args.staleReason}.` : '';

  if (ACTIVE_PHASES.has(phaseCode)) {
    if (args.isStale === true || age > 180) {
      return result(
        'stale_during_trading',
        'SSI realtime stale during trading',
        `Market is in an active trading phase and the snapshot is ${ageText}.${rawStaleReason}`,
        'warning',
      );
    }
    if (age > 60) {
      return result(
        'delayed',
        'SSI realtime delayed',
        `Market is in an active trading phase and the snapshot is ${ageText}.`,
        'info',
      );
    }
    return result(
      'live',
      'SSI realtime live',
      `Market is in an active trading phase and the snapshot is ${ageText}.`,
      'ok',
    );
  }

  if (phaseCode === 'lunch_break') {
    if (age <= 60) {
      return result(
        'live',
        'SSI realtime live',
        `Market is at lunch break and the snapshot is ${ageText}.`,
        'ok',
      );
    }
    if (age <= 180) {
      return result(
        'delayed',
        'SSI realtime delayed',
        `Market is at lunch break and the snapshot is ${ageText}.`,
        'info',
      );
    }
    return result(
      'last_available_closed',
      'Last available during break',
      `Market is at lunch break; snapshot may stop updating. Raw age is ${ageText}.${rawStaleReason}`,
      'info',
    );
  }

  if (phaseCode === 'post_close') {
    return result(
      'last_available_post_close',
      'Last available SSI realtime',
      `Market is post-close; snapshot may stop updating. Raw age is ${ageText}.${rawStaleReason}`,
      'info',
    );
  }

  if (phaseCode === 'weekend_closed') {
    return result(
      'last_available_weekend',
      'Last available SSI realtime',
      `Weekend / closed; snapshot may stop updating. Raw age is ${ageText}.${rawStaleReason}`,
      'info',
    );
  }

  if (phaseCode === 'closed' || phaseCode === 'pre_open') {
    return result(
      'last_available_closed',
      'Last available SSI realtime',
      `Market closed; snapshot may stop updating. Raw age is ${ageText}.${rawStaleReason}`,
      'info',
    );
  }

  return result(
    'unknown',
    'SSI realtime state unknown',
    `Market phase is unknown. Raw age is ${ageText}.${rawStaleReason}`,
    'unknown',
  );
}
