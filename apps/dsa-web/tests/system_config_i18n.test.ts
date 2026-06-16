import { describe, expect, it } from 'vitest';
import { getFieldOptionLabelZh, getFieldTitleZh } from '../src/utils/systemConfigI18n';

const requiredLocalizedKeys = [
  'TICKFLOW_API_KEY',
  'STOCK_INDEX_REMOTE_UPDATE_ENABLED',
  'SEARXNG_BASE_URLS',
  'ENABLE_REALTIME_QUOTE',
  'ENABLE_CHIP_DISTRIBUTION',
  'PYTDX_HOST',
  'PYTDX_PORT',
  'PYTDX_SERVERS',
  'BIAS_THRESHOLD',
  'TELEGRAM_BOT_TOKEN',
  'TELEGRAM_CHAT_ID',
  'TELEGRAM_MESSAGE_THREAD_ID',
  'FEISHU_STREAM_ENABLED',
  'DINGTALK_STREAM_ENABLED',
  'EMAIL_SENDER',
  'EMAIL_PASSWORD',
  'EMAIL_RECEIVERS',
  'DISCORD_WEBHOOK_URL',
  'DISCORD_BOT_TOKEN',
  'DISCORD_MAIN_CHANNEL_ID',
  'DISCORD_INTERACTIONS_PUBLIC_KEY',
  'SLACK_BOT_TOKEN',
  'SLACK_CHANNEL_ID',
  'SLACK_WEBHOOK_URL',
  'PUSHPLUS_TOPIC',
  'PUSHOVER_USER_KEY',
  'PUSHOVER_API_TOKEN',
  'SERVERCHAN3_SENDKEY',
  'ASTRBOT_URL',
  'ASTRBOT_TOKEN',
  'CUSTOM_WEBHOOK_BEARER_TOKEN',
  'WEBHOOK_VERIFY_SSL',
  'SINGLE_STOCK_NOTIFY',
  'REPORT_TYPE',
  'REPORT_LANGUAGE',
  'REPORT_TEMPLATES_DIR',
  'REPORT_INTEGRITY_ENABLED',
  'REPORT_RENDERER_ENABLED',
  'REPORT_INTEGRITY_RETRY',
  'REPORT_HISTORY_COMPARE_N',
  'MERGE_EMAIL_NOTIFICATION',
  'NOTIFICATION_REPORT_CHANNELS',
  'NOTIFICATION_ALERT_CHANNELS',
  'NOTIFICATION_SYSTEM_ERROR_CHANNELS',
  'NOTIFICATION_DEDUP_TTL_SECONDS',
  'NOTIFICATION_COOLDOWN_SECONDS',
  'NOTIFICATION_QUIET_HOURS',
  'NOTIFICATION_TIMEZONE',
  'NOTIFICATION_MIN_SEVERITY',
  'NOTIFICATION_DAILY_DIGEST_ENABLED',
  'SCHEDULE_ENABLED',
  'SCHEDULE_RUN_IMMEDIATELY',
  'TRADING_DAY_CHECK_ENABLED',
  'WEBUI_HOST',
  'LOG_DIR',
  'WEBUI_ENABLED',
  'WEBUI_AUTO_BUILD',
  'ADMIN_AUTH_ENABLED',
  'TRUST_X_FORWARDED_FOR',
  'RUN_IMMEDIATELY',
  'MARKET_REVIEW_ENABLED',
  'MARKET_REVIEW_REGION',
  'ANALYSIS_DELAY',
  'DEBUG',
  'AGENT_NL_ROUTING',
  'AGENT_DEEP_RESEARCH_BUDGET',
  'AGENT_DEEP_RESEARCH_TIMEOUT',
  'AGENT_EVENT_MONITOR_ENABLED',
  'AGENT_EVENT_MONITOR_INTERVAL_MINUTES',
  'AGENT_EVENT_ALERT_RULES_JSON',
] as const;

describe('systemConfigI18n required key coverage', () => {
  it('provides English title mappings for known missing keys', () => {
    requiredLocalizedKeys.forEach((key) => {
      expect(getFieldTitleZh(key, key)).not.toBe(key);
    });
  });

  it('uses an English primary title for SearXNG base URLs', () => {
    const title = getFieldTitleZh('SEARXNG_BASE_URLS', 'SEARXNG_BASE_URLS');

    expect(title).toBe('SearXNG self-hosted instance URLs');
    expect(title).not.toBe('SearXNG Base URLs');
  });
});

describe('systemConfigI18n option label localization', () => {
  const realSelectOptionCases = [
    ['NEWS_STRATEGY_PROFILE', 'ultra_short', undefined, 'Ultra short (1 day)'],
    ['NEWS_STRATEGY_PROFILE', 'short', undefined, 'Short (3 days)'],
    ['NEWS_STRATEGY_PROFILE', 'medium', undefined, 'Medium (7 days)'],
    ['NEWS_STRATEGY_PROFILE', 'long', undefined, 'Long (30 days)'],
    ['REPORT_TYPE', 'simple', undefined, 'Simple'],
    ['REPORT_TYPE', 'full', undefined, 'Full'],
    ['REPORT_TYPE', 'brief', undefined, 'Brief'],
    ['REPORT_LANGUAGE', 'zh', 'Chinese', 'Chinese'],
    ['REPORT_LANGUAGE', 'en', 'English', 'English'],
    ['NOTIFICATION_MIN_SEVERITY', '', 'Not set', 'Not set'],
    ['NOTIFICATION_MIN_SEVERITY', 'info', 'info', 'Info'],
    ['NOTIFICATION_MIN_SEVERITY', 'warning', 'warning', 'Warning'],
    ['NOTIFICATION_MIN_SEVERITY', 'error', 'error', 'Error'],
    ['NOTIFICATION_MIN_SEVERITY', 'critical', 'critical', 'Critical'],
    ['LOG_LEVEL', 'DEBUG', undefined, 'Debug'],
    ['LOG_LEVEL', 'INFO', undefined, 'Info'],
    ['LOG_LEVEL', 'WARNING', undefined, 'Warning'],
    ['LOG_LEVEL', 'ERROR', undefined, 'Error'],
    ['LOG_LEVEL', 'CRITICAL', undefined, 'Critical'],
    ['MARKET_REVIEW_REGION', 'cn', undefined, 'A-shares'],
    ['MARKET_REVIEW_REGION', 'hk', undefined, 'Hong Kong stocks'],
    ['MARKET_REVIEW_REGION', 'us', undefined, 'US stocks'],
    ['MARKET_REVIEW_REGION', 'both', undefined, 'All markets'],
    ['MARKET_REVIEW_COLOR_SCHEME', 'green_up', 'Green Up / Red Down', 'Green up / red down'],
    ['MARKET_REVIEW_COLOR_SCHEME', 'red_up', 'Red Up / Green Down', 'Red up / green down'],
    ['AGENT_ARCH', 'single', 'Single Agent', 'Single Agent'],
    ['AGENT_ARCH', 'multi', 'Multi Agent (Orchestrator)', 'Multi-Agent (orchestrator)'],
    ['AGENT_ORCHESTRATOR_MODE', 'quick', 'Quick', 'Quick'],
    ['AGENT_ORCHESTRATOR_MODE', 'standard', 'Standard', 'Standard'],
    ['AGENT_ORCHESTRATOR_MODE', 'full', 'Full', 'Full'],
    ['AGENT_ORCHESTRATOR_MODE', 'specialist', 'Specialist', 'Specialist'],
    ['AGENT_SKILL_ROUTING', 'auto', 'Auto (Regime-based)', 'Auto (market-status based)'],
    ['AGENT_SKILL_ROUTING', 'manual', 'Manual (Use AGENT_SKILLS)', 'Manual (use AGENT_SKILLS)'],
  ] as const;

  it('localizes all select options currently exposed by system config schema', () => {
    realSelectOptionCases.forEach(([key, value, fallbackLabel, expectedLabel]) => {
      const label = getFieldOptionLabelZh(key, value, fallbackLabel);

      expect(label).toBe(expectedLabel);
      expect(label).not.toBe(value);
    });
  });
});
