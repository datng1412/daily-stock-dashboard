const VIETNAM_TIME_ZONE = 'Asia/Ho_Chi_Minh';

export type VietnamMarketPhase = {
  phase: string;
  code: string;
  isTradingSession: boolean;
  isAuction: boolean;
  isContinuous: boolean;
  holidayAware: boolean;
  nextLabel?: string;
};

const vnDateParts = (date: Date) => {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: VIETNAM_TIME_ZONE,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const map = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    weekday: map.weekday,
    minutes: Number(map.hour) * 60 + Number(map.minute),
  };
};

const phase = (
  code: string,
  label: string,
  options: Pick<VietnamMarketPhase, 'isTradingSession' | 'isAuction' | 'isContinuous'>,
  nextLabel?: string,
): VietnamMarketPhase => ({
  phase: label,
  code,
  holidayAware: false,
  nextLabel,
  ...options,
});

export const getVietnamMarketPhase = (now: Date = new Date()): VietnamMarketPhase => {
  const { weekday, minutes } = vnDateParts(now);
  if (weekday === 'Sat' || weekday === 'Sun') {
    return phase('weekend_closed', 'Weekend / closed', {
      isTradingSession: false,
      isAuction: false,
      isContinuous: false,
    }, 'Pre-open');
  }

  if (minutes < 9 * 60) {
    return phase('pre_open', 'Pre-open', {
      isTradingSession: false,
      isAuction: false,
      isContinuous: false,
    }, 'ATO opening auction');
  }
  if (minutes < 9 * 60 + 15) {
    return phase('ato', 'ATO opening auction', {
      isTradingSession: true,
      isAuction: true,
      isContinuous: false,
    }, 'Continuous morning');
  }
  if (minutes < 11 * 60 + 30) {
    return phase('continuous_morning', 'Continuous morning', {
      isTradingSession: true,
      isAuction: false,
      isContinuous: true,
    }, 'Lunch break');
  }
  if (minutes < 13 * 60) {
    return phase('lunch_break', 'Lunch break', {
      isTradingSession: false,
      isAuction: false,
      isContinuous: false,
    }, 'Continuous afternoon');
  }
  if (minutes < 14 * 60 + 30) {
    return phase('continuous_afternoon', 'Continuous afternoon', {
      isTradingSession: true,
      isAuction: false,
      isContinuous: true,
    }, 'ATC closing auction');
  }
  if (minutes < 14 * 60 + 45) {
    return phase('atc', 'ATC closing auction', {
      isTradingSession: true,
      isAuction: true,
      isContinuous: false,
    }, 'Post-close');
  }
  if (minutes < 15 * 60) {
    return phase('post_close', 'Post-close', {
      isTradingSession: false,
      isAuction: false,
      isContinuous: false,
    }, 'Closed');
  }
  return phase('closed', 'Closed', {
    isTradingSession: false,
    isAuction: false,
    isContinuous: false,
  }, 'Pre-open');
};
