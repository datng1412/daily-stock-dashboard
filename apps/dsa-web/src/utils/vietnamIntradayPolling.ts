export type VietnamIntradaySessionState =
  | 'pre_open'
  | 'continuous_morning'
  | 'lunch'
  | 'continuous_afternoon'
  | 'atc'
  | 'closed';

export type VietnamIntradayScheduledAction = {
  delayMs: number;
  kind: 'poll' | 'morning_resume' | 'afternoon_resume' | 'post_close';
};

export const VIETNAM_INTRADAY_POLL_OFFSET_MS = 7_000;
export const VIETNAM_INTRADAY_POST_CLOSE_OFFSET_MS = 20_000;

const vietnamParts = (now: Date) => {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Ho_Chi_Minh',
      weekday: 'short',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(now).map((part) => [part.type, part.value]),
  );
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    weekday: parts.weekday,
    hour: Number(parts.hour),
    minute: Number(parts.minute),
  };
};

export const vietnamTodayIso = (now = new Date()) => vietnamParts(now).date;

export const getVietnamDateRolloverDelayMs = (now: Date) => {
  const nextVietnamMidnight = new Date(`${vietnamTodayIso(now)}T17:00:00Z`).getTime();
  return Math.max(1_000, nextVietnamMidnight - now.getTime());
};

export const getVietnamScheduledSessionState = (now: Date): VietnamIntradaySessionState => {
  const { weekday, hour, minute } = vietnamParts(now);
  if (weekday === 'Sat' || weekday === 'Sun') return 'closed';
  const minuteOfDay = (hour * 60) + minute;
  if (minuteOfDay < (9 * 60 + 15)) return 'pre_open';
  if (minuteOfDay < (11 * 60 + 30)) return 'continuous_morning';
  if (minuteOfDay < (13 * 60)) return 'lunch';
  if (minuteOfDay < (14 * 60 + 30)) return 'continuous_afternoon';
  if (minuteOfDay < (14 * 60 + 45)) return 'atc';
  return 'closed';
};

export const shouldPollCurrentIntraday = (state: VietnamIntradaySessionState) => (
  state === 'continuous_morning' || state === 'continuous_afternoon' || state === 'atc'
);

const vietnamTimestamp = (date: string, time: string) => new Date(`${date}T${time}+07:00`).getTime();

export const getNextVietnamIntradayAction = (now: Date): VietnamIntradayScheduledAction | null => {
  const state = getVietnamScheduledSessionState(now);
  const { date } = vietnamParts(now);
  if (state === 'pre_open') {
    return { delayMs: Math.max(0, vietnamTimestamp(date, '09:15:07') - now.getTime()), kind: 'morning_resume' };
  }
  if (state === 'lunch') {
    return { delayMs: Math.max(0, vietnamTimestamp(date, '13:00:07') - now.getTime()), kind: 'afternoon_resume' };
  }
  if (!shouldPollCurrentIntraday(state)) return null;

  const currentMinuteStart = Math.floor(now.getTime() / 60_000) * 60_000;
  let target = currentMinuteStart + VIETNAM_INTRADAY_POLL_OFFSET_MS;
  if (target <= now.getTime()) target += 60_000;
  const targetState = getVietnamScheduledSessionState(new Date(target));
  if (shouldPollCurrentIntraday(targetState)) {
    return { delayMs: target - now.getTime(), kind: 'poll' };
  }
  if (state === 'continuous_morning') {
    return { delayMs: Math.max(0, vietnamTimestamp(date, '13:00:07') - now.getTime()), kind: 'afternoon_resume' };
  }
  return {
    delayMs: Math.max(0, vietnamTimestamp(date, '14:45:20') - now.getTime()),
    kind: 'post_close',
  };
};

export const getVietnamIntradayCountdownSeconds = (targetAtMs: number | null, nowMs: number) => (
  targetAtMs == null ? null : Math.max(0, Math.ceil((targetAtMs - nowMs) / 1_000))
);

export const vietnamIntradayFinalRefreshKey = (ticker: string, tradingDate: string) => (
  `${ticker.trim().toUpperCase()}:${tradingDate}`
);

export const vietnamIntradayStatusLabel = (
  sessionState: string | null | undefined,
  freshness: string | null | undefined,
  hasBars: boolean,
  options?: { loading?: boolean; providerUnavailable?: boolean },
) => {
  if (sessionState === 'completed') return 'Completed';
  if (options?.loading && !hasBars) return 'Loading';
  if (sessionState === 'pre_open') return 'Pre-open';
  if (sessionState === 'lunch') return 'Lunch break';
  if (sessionState === 'closed') return 'Closed';
  if (freshness === 'stale') return 'Stale';
  if (options?.providerUnavailable && !hasBars) return 'SSI data unavailable';
  if (!hasBars || freshness === 'unavailable') return 'No data yet';
  if (freshness === 'updating') return 'Updating';
  return 'Delayed';
};
