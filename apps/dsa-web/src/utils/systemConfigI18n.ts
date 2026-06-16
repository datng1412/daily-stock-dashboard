import type { SystemConfigCategory } from '../types/systemConfig';

const categoryTitleMap: Record<SystemConfigCategory, string> = {
  base: 'Base settings',
  data_source: 'Data sources',
  ai_model: 'AI model',
  notification: 'Notification channels',
  system: 'System settings',
  agent: 'Agent settings',
  backtest: 'Backtest settings',
  uncategorized: 'Other',
};

const categoryDescriptionMap: Partial<Record<SystemConfigCategory, string>> = {
  base: 'Manage watchlists and base runtime parameters.',
  data_source: 'Manage market data sources and priority rules.',
  ai_model: 'Manage model services, model names, and inference parameters.',
  notification: 'Manage bots, webhooks, and message delivery.',
  system: 'Manage scheduling, logs, ports, and other runtime parameters.',
  agent: 'Manage Agent mode, strategies, and multi-Agent orchestration.',
  backtest: 'Manage backtest switches, evaluation windows, and engine parameters.',
  uncategorized: 'Other uncategorized settings.',
};

const fieldTitleMap: Record<string, string> = {
  STOCK_LIST: 'Watchlist',
  TUSHARE_TOKEN: 'Tushare Token',
  BOCHA_API_KEYS: 'Bocha API Keys',
  TAVILY_API_KEYS: 'Tavily API Keys',
  ANSPIRE_API_KEYS: 'Anspire API Keys',
  SERPAPI_API_KEYS: 'SerpAPI API Keys',
  BRAVE_API_KEYS: 'Brave API Keys',
  STOCK_INDEX_REMOTE_UPDATE_ENABLED: 'Remote stock index updates',
  SEARXNG_BASE_URLS: 'SearXNG self-hosted instance URLs',
  SEARXNG_PUBLIC_INSTANCES_ENABLED: 'SearXNG public instance discovery',
  MINIMAX_API_KEYS: 'MiniMax API Keys',
  NEWS_STRATEGY_PROFILE: 'News strategy window',
  NEWS_MAX_AGE_DAYS: 'Maximum news age (days)',
  REALTIME_SOURCE_PRIORITY: 'Realtime data source priority',
  TICKFLOW_API_KEY: 'TickFlow API Key',
  ENABLE_REALTIME_QUOTE: 'Enable realtime quotes',
  ENABLE_REALTIME_TECHNICAL_INDICATORS: 'Intraday technical indicators',
  ENABLE_CHIP_DISTRIBUTION: 'Enable chip distribution analysis',
  PYTDX_HOST: 'Pytdx host',
  PYTDX_PORT: 'Pytdx port',
  PYTDX_SERVERS: 'Pytdx server list',
  BIAS_THRESHOLD: 'BIAS threshold',
  LITELLM_MODEL: 'Main model',
  AGENT_LITELLM_MODEL: 'Agent main model',
  LITELLM_FALLBACK_MODELS: 'Fallback models',
  LITELLM_CONFIG: 'Advanced model routing config',
  LLM_CHANNELS: 'LLM channels',
  LLM_TEMPERATURE: 'Sampling temperature',
  AIHUBMIX_KEY: 'AIHubmix Key',
  ANSPIRE_LLM_ENABLED: 'Enable Anspire LLM',
  ANSPIRE_LLM_BASE_URL: 'Anspire LLM gateway',
  ANSPIRE_LLM_MODEL: 'Anspire default model',
  DEEPSEEK_API_KEY: 'DeepSeek API Key',
  GEMINI_API_KEY: 'Gemini API Key',
  GEMINI_MODEL: 'Gemini model',
  GEMINI_TEMPERATURE: 'Gemini temperature',
  OPENAI_API_KEY: 'OpenAI API Key',
  OPENAI_BASE_URL: 'OpenAI Base URL',
  OPENAI_MODEL: 'OpenAI model',
  WECHAT_WEBHOOK_URL: 'WeCom Webhook',
  FEISHU_WEBHOOK_URL: 'Feishu group bot Webhook',
  FEISHU_WEBHOOK_SECRET: 'Feishu Webhook signing secret',
  FEISHU_WEBHOOK_KEYWORD: 'Feishu Webhook keyword',
  FEISHU_APP_ID: 'Feishu App ID',
  FEISHU_APP_SECRET: 'Feishu App Secret',
  FEISHU_STREAM_ENABLED: 'Feishu Stream mode',
  DINGTALK_APP_KEY: 'DingTalk App Key',
  DINGTALK_APP_SECRET: 'DingTalk App Secret',
  DINGTALK_STREAM_ENABLED: 'DingTalk Stream mode',
  TELEGRAM_BOT_TOKEN: 'Telegram Bot Token',
  TELEGRAM_CHAT_ID: 'Telegram Chat ID',
  TELEGRAM_MESSAGE_THREAD_ID: 'Telegram topic thread ID',
  EMAIL_SENDER: 'Sender email',
  EMAIL_PASSWORD: 'Email authorization code',
  EMAIL_RECEIVERS: 'Recipient email list',
  DISCORD_WEBHOOK_URL: 'Discord Webhook URL',
  DISCORD_BOT_TOKEN: 'Discord Bot Token',
  DISCORD_MAIN_CHANNEL_ID: 'Discord main channel ID',
  DISCORD_INTERACTIONS_PUBLIC_KEY: 'Discord interactions public key',
  SLACK_BOT_TOKEN: 'Slack Bot Token',
  SLACK_CHANNEL_ID: 'Slack channel ID',
  SLACK_WEBHOOK_URL: 'Slack Webhook URL',
  PUSHPLUS_TOPIC: 'PushPlus topic',
  PUSHOVER_USER_KEY: 'Pushover User Key',
  PUSHOVER_API_TOKEN: 'Pushover API Token',
  SERVERCHAN3_SENDKEY: 'ServerChan3 SendKey',
  ASTRBOT_URL: 'AstrBot URL',
  ASTRBOT_TOKEN: 'AstrBot Token',
  CUSTOM_WEBHOOK_URLS: 'Custom Webhook URLs',
  CUSTOM_WEBHOOK_BEARER_TOKEN: 'Custom Webhook Bearer Token',
  CUSTOM_WEBHOOK_BODY_TEMPLATE: 'Custom Webhook body template',
  WEBHOOK_VERIFY_SSL: 'Webhook SSL verification',
  SINGLE_STOCK_NOTIFY: 'Per-stock notifications',
  REPORT_TYPE: 'Report type',
  REPORT_LANGUAGE: 'Report language',
  REPORT_TEMPLATES_DIR: 'Report templates directory',
  REPORT_INTEGRITY_ENABLED: 'Report integrity check',
  REPORT_RENDERER_ENABLED: 'Report renderer',
  REPORT_INTEGRITY_RETRY: 'Report integrity retry count',
  REPORT_HISTORY_COMPARE_N: 'Historical comparison periods',
  MERGE_EMAIL_NOTIFICATION: 'Merge email notifications',
  NOTIFICATION_REPORT_CHANNELS: 'Report notification channels',
  NOTIFICATION_ALERT_CHANNELS: 'Alert notification channels',
  NOTIFICATION_SYSTEM_ERROR_CHANNELS: 'System error notification channels',
  NOTIFICATION_DEDUP_TTL_SECONDS: 'Notification dedup window (seconds)',
  NOTIFICATION_COOLDOWN_SECONDS: 'Notification cooldown (seconds)',
  NOTIFICATION_QUIET_HOURS: 'Notification quiet hours',
  NOTIFICATION_TIMEZONE: 'Notification timezone',
  NOTIFICATION_MIN_SEVERITY: 'Minimum notification severity',
  NOTIFICATION_DAILY_DIGEST_ENABLED: 'Enable daily digest notifications',
  NTFY_URL: 'ntfy URL',
  NTFY_TOKEN: 'ntfy Token',
  GOTIFY_URL: 'Gotify URL',
  GOTIFY_TOKEN: 'Gotify Token',
  PUSHPLUS_TOKEN: 'PushPlus Token',
  REPORT_SUMMARY_ONLY: 'Summary only',
  REPORT_SHOW_LLM_MODEL: 'Show analysis model',
  MAX_WORKERS: 'Max workers',
  SCHEDULE_ENABLED: 'Enable scheduled tasks',
  SCHEDULE_RUN_IMMEDIATELY: 'Run scheduled task after saving',
  TRADING_DAY_CHECK_ENABLED: 'Enable trading-day check',
  WEBUI_HOST: 'WebUI host',
  ADMIN_AUTH_ENABLED: 'Enable admin authentication',
  TRUST_X_FORWARDED_FOR: 'Trust X-Forwarded-For',
  RUN_IMMEDIATELY: 'Run immediately on startup',
  MARKET_REVIEW_ENABLED: 'Enable market review',
  MARKET_REVIEW_REGION: 'Market review region',
  MARKET_REVIEW_COLOR_SCHEME: 'Market review color scheme',
  ANALYSIS_DELAY: 'Analysis startup delay (seconds)',
  SCHEDULE_TIME: 'Scheduled task time',
  DEBUG: 'Debug mode',
  HTTP_PROXY: 'HTTP proxy',
  LOG_DIR: 'Log directory',
  LOG_LEVEL: 'Log level',
  WEBUI_ENABLED: 'Start WebUI by default',
  WEBUI_AUTO_BUILD: 'Auto-build frontend before startup',
  WEBUI_PORT: 'WebUI port',
  AGENT_MODE: 'Enable Agent Ask Stock',
  AGENT_MAX_STEPS: 'Agent max steps',
  AGENT_SKILLS: 'Active Agent strategies',
  AGENT_SKILL_DIR: 'Agent strategy directory',
  AGENT_ARCH: 'Agent architecture mode',
  AGENT_ORCHESTRATOR_MODE: 'Orchestration mode',
  AGENT_ORCHESTRATOR_TIMEOUT_S: 'Agent timeout (seconds)',
  AGENT_RISK_OVERRIDE: 'Risk Agent veto',
  AGENT_SKILL_AUTOWEIGHT: 'Strategy auto-weighting',
  AGENT_SKILL_ROUTING: 'Strategy routing mode',
  AGENT_MEMORY_ENABLED: 'Memory and calibration',
  AGENT_NL_ROUTING: 'Natural language routing',
  AGENT_DEEP_RESEARCH_BUDGET: 'Deep Research budget',
  AGENT_DEEP_RESEARCH_TIMEOUT: 'Deep Research timeout (seconds)',
  AGENT_EVENT_MONITOR_ENABLED: 'Enable event monitoring',
  AGENT_EVENT_MONITOR_INTERVAL_MINUTES: 'Event monitor interval (minutes)',
  AGENT_EVENT_ALERT_RULES_JSON: 'Event alert rules (JSON)',
  AGENT_CONTEXT_COMPRESSION_ENABLED: 'Context compression',
  AGENT_CONTEXT_COMPRESSION_PROFILE: 'Context compression profile',
  AGENT_CONTEXT_COMPRESSION_TRIGGER_TOKENS: 'Compression trigger threshold (tokens)',
  AGENT_CONTEXT_PROTECTED_TURNS: 'Protected raw turns',
  BACKTEST_ENABLED: 'Enable backtest',
  BACKTEST_EVAL_WINDOW_DAYS: 'Backtest evaluation window (trading days)',
  BACKTEST_MIN_AGE_DAYS: 'Backtest minimum record age',
  BACKTEST_ENGINE_VERSION: 'Backtest engine version',
  BACKTEST_NEUTRAL_BAND_PCT: 'Backtest neutral band threshold (%)',
};

const fieldDescriptionMap: Record<string, string> = {
  STOCK_LIST: 'Comma-separated stock codes, for example 600519,300750.',
  STOCK_INDEX_REMOTE_UPDATE_ENABLED: 'Controls whether the stock autocomplete index is refreshed from GitHub main. Failures fall back to cache or bundled data.',
  NEWS_STRATEGY_PROFILE: 'News window profile: ultra_short=1 day, short=3 days, medium=7 days, long=30 days.',
  NEWS_MAX_AGE_DAYS: 'Maximum news age. The actual window is the smaller value between the strategy profile and this setting.',
  REALTIME_SOURCE_PRIORITY: 'Comma-separated data source priority order.',
  ENABLE_REALTIME_QUOTE: 'Controls whether realtime quote retrieval is enabled.',
  ENABLE_REALTIME_TECHNICAL_INDICATORS: 'Uses realtime price for intraday MA5/MA10/MA20 calculations when enabled; otherwise uses the previous close.',
  ENABLE_CHIP_DISTRIBUTION: 'Controls chip distribution analysis. Disabling can reduce external requests and failure noise.',
  LITELLM_MODEL: 'Main model in provider/model format. It can be inferred after channels are configured.',
  AGENT_LITELLM_MODEL: 'Agent-specific main model. Blank inherits the main model.',
  LITELLM_FALLBACK_MODELS: 'Comma-separated fallback models tried in order when the main model fails.',
  LITELLM_CONFIG: 'Path to an advanced LiteLLM YAML routing file. It takes priority only when parsed successfully with a model_list.',
  LLM_CHANNELS: 'Comma-separated channel names. Prefer managing them with the channel editor above.',
  LLM_TEMPERATURE: 'Controls output randomness. 0 is deterministic, 2 is maximum randomness.',
  REPORT_LANGUAGE: 'Notification report language (zh/en).',
  REPORT_SHOW_LLM_MODEL: 'Shows the LLM model name in notification report footers. This affects display only.',
  MAX_WORKERS: 'Maximum async task queue concurrency. Applies when the queue is idle after saving.',
  SCHEDULE_ENABLED: 'Enables daily scheduled analysis tasks.',
  TRADING_DAY_CHECK_ENABLED: 'Skips scheduled analysis automatically on non-trading days.',
  MARKET_REVIEW_ENABLED: 'Controls whether the market review flow is enabled.',
  MARKET_REVIEW_REGION: 'Default market region for market review, such as cn/us/hk.',
  MARKET_REVIEW_COLOR_SCHEME: 'Controls market review index change colors.',
  AGENT_MODE: 'Controls whether ReAct Agent Ask Stock is enabled.',
  AGENT_SKILLS: 'Comma-separated strategy list. Blank uses the default strategy declared in metadata; all enables every strategy.',
  AGENT_CONTEXT_COMPRESSION_ENABLED: 'Compresses visible Ask Stock chat history in long sessions. Off by default.',
  BACKTEST_ENABLED: 'Controls whether backtest is enabled.',
  BACKTEST_EVAL_WINDOW_DAYS: 'Backtest evaluation window length in trading days.',
  BACKTEST_NEUTRAL_BAND_PCT: 'Neutral return band percentage, for example 2 means -2% to +2%.',
};

const fieldOptionLabelMap: Record<string, Record<string, string>> = {
  NEWS_STRATEGY_PROFILE: {
    ultra_short: 'Ultra short (1 day)',
    short: 'Short (3 days)',
    medium: 'Medium (7 days)',
    long: 'Long (30 days)',
  },
  REPORT_TYPE: {
    simple: 'Simple',
    full: 'Full',
    brief: 'Brief',
  },
  REPORT_LANGUAGE: {
    zh: 'Chinese',
    en: 'English',
    chinese: 'Chinese',
    english: 'English',
  },
  NOTIFICATION_MIN_SEVERITY: {
    '': 'Not set',
    'not set': 'Not set',
    info: 'Info',
    warning: 'Warning',
    error: 'Error',
    critical: 'Critical',
  },
  MARKET_REVIEW_COLOR_SCHEME: {
    green_up: 'Green up / red down',
    red_up: 'Red up / green down',
    'green up / red down': 'Green up / red down',
    'red up / green down': 'Red up / green down',
  },
  LOG_LEVEL: {
    debug: 'Debug',
    info: 'Info',
    warning: 'Warning',
    error: 'Error',
    critical: 'Critical',
  },
  MARKET_REVIEW_REGION: {
    cn: 'A-shares',
    hk: 'Hong Kong stocks',
    us: 'US stocks',
    both: 'All markets',
  },
  AGENT_ARCH: {
    single: 'Single Agent',
    multi: 'Multi-Agent (orchestrator)',
    'single agent': 'Single Agent',
    'multi agent (orchestrator)': 'Multi-Agent (orchestrator)',
  },
  AGENT_ORCHESTRATOR_MODE: {
    quick: 'Quick',
    standard: 'Standard',
    full: 'Full',
    specialist: 'Specialist',
  },
  AGENT_SKILL_ROUTING: {
    auto: 'Auto (market-status based)',
    manual: 'Manual (use AGENT_SKILLS)',
    'auto (regime-based)': 'Auto (market-status based)',
    'manual (use agent_skills)': 'Manual (use AGENT_SKILLS)',
  },
};

function normalizeOptionToken(raw: string): string {
  return raw.trim().toLowerCase();
}

export function getCategoryTitleZh(category: SystemConfigCategory, fallback?: string): string {
  return categoryTitleMap[category] || fallback || category;
}

export function getCategoryDescriptionZh(category: SystemConfigCategory, fallback?: string): string {
  return categoryDescriptionMap[category] || fallback || '';
}

export function getFieldTitleZh(key: string, fallback?: string): string {
  return fieldTitleMap[key] || fallback || key;
}

export function getFieldDescriptionZh(key: string, fallback?: string): string {
  return fieldDescriptionMap[key] || fallback || '';
}

export function getFieldOptionLabelZh(key: string, value: string, fallbackLabel?: string): string {
  const map = fieldOptionLabelMap[key];
  if (!map) {
    return fallbackLabel ?? value;
  }

  const byValue = map[normalizeOptionToken(value)];
  if (byValue) {
    return byValue;
  }

  if (fallbackLabel) {
    const byLabel = map[normalizeOptionToken(fallbackLabel)];
    if (byLabel) {
      return byLabel;
    }
  }

  return fallbackLabel ?? value;
}
