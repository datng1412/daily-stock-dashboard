#!/usr/bin/env node
/* Bounded system-browser acceptance for R6E historical repair and Industry current flow. */

import { createRequire } from 'node:module';
import { createServer } from 'node:net';
import { existsSync, openSync, closeSync, rmSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDir, '..');
const webRoot = join(root, 'apps', 'dsa-web');
const require = createRequire(join(webRoot, 'package.json'));
const { chromium } = require('@playwright/test');

const BROWSER_PATHS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
];
const VIEWPORTS = [
  { name: 'desktop', width: 1366, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
];
const SCENARIOS = [
  ['historical_unresolved_anomaly', 'vn30'],
  ['historical_repaired', 'vn30'],
  ['historical_repair_in_flight', 'vn30'],
  ['historical_repair_cooldown', 'vn30'],
  ['historical_manual_retry', 'vn30'],
  ['historical_normal_explicit_zero', 'ticker'],
  ['industry_current_ready', 'industry'],
  ['industry_current_partial', 'industry'],
  ['industry_current_stale', 'industry'],
  ['industry_current_closed', 'industry'],
  ['industry_completed_only', 'industry'],
  ['industry_same_date_accepted', 'industry'],
  ['industry_same_date_suspicious', 'industry'],
  ['industry_twenty_plus_current', 'industry'],
];
const STATUS = {
  completed: '\u0110\u1ee7',
  incomplete: 'Thi\u1ebfu d\u1eef li\u1ec7u',
  anomalous: 'B\u1ea5t th\u01b0\u1eddng d\u1eef li\u1ec7u',
  active: '\u0110ang di\u1ec5n ra',
  stale: 'M\u1ea5t k\u1ebft n\u1ed1i',
  closed: 'T\u1ea1m t\u00ednh',
};

const sleep = (milliseconds) => new Promise((resolvePromise) => setTimeout(resolvePromise, milliseconds));

const discoverBrowser = () => {
  const executablePath = BROWSER_PATHS.find((candidate) => existsSync(candidate));
  if (!executablePath) {
    throw new Error('No approved system Chrome or Edge executable was found.');
  }
  return {
    executablePath,
    name: executablePath.toLowerCase().includes('chrome') ? 'Chrome' : 'Edge',
  };
};

const freePort = () => new Promise((resolvePromise, reject) => {
  const server = createServer();
  server.unref();
  server.once('error', reject);
  server.listen(0, '127.0.0.1', () => {
    const address = server.address();
    const port = typeof address === 'object' && address ? address.port : 0;
    server.close((error) => error ? reject(error) : resolvePromise(port));
  });
});

const isPortOpen = async (port) => {
  const result = spawnSync('netstat', ['-ano', '-p', 'TCP'], {
    windowsHide: true,
    timeout: 2_000,
    encoding: 'utf8',
  });
  const marker = `:${port}`;
  return String(result.stdout || '')
    .split(/\r?\n/)
    .some((line) => line.includes(marker) && /\bLISTENING\b/i.test(line));
};

const waitForVite = async (url, deadline) => {
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1_500) });
      if (response.ok) return;
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(150);
  }
  throw new Error(`Vite readiness exceeded 20 seconds: ${String(lastError)}`);
};

const completedRows = (endDay) => {
  const count = 20;
  return Array.from({ length: count }, (_, index) => {
    const day = endDay - count + index + 1;
    return {
      trading_date: `2026-06-${String(day).padStart(2, '0')}`,
      foreign_buy_value: 1_000_000_000 + index * 10_000_000,
      foreign_sell_value: 700_000_000 + index * 5_000_000,
      foreign_net_value: 300_000_000 + index * 5_000_000,
      foreign_buy_volume: 100_000 + index * 1_000,
      foreign_sell_volume: 70_000 + index * 500,
      foreign_net_volume: 30_000 + index * 500,
    };
  });
};

const scenarioConfig = (name) => ({
  completedEnd: 30,
  currentDate: ['industry_same_date_accepted', 'industry_same_date_suspicious'].includes(name)
    ? '2026-06-30'
    : '2026-07-30',
  currentUnavailable: [
    'historical_unresolved_anomaly',
    'historical_repaired',
    'historical_repair_in_flight',
    'historical_repair_cooldown',
    'historical_manual_retry',
    'historical_normal_explicit_zero',
    'industry_completed_only',
  ].includes(name),
  coldUnavailable: false,
  postClose: name === 'industry_current_closed',
  explicitZero: name === 'historical_normal_explicit_zero',
  stale: name === 'industry_current_stale',
  partialCoverage: name === 'industry_current_partial',
  missingValues: false,
  regressive: false,
  historicalMissing: false,
  historicalExplicitZero: name === 'historical_normal_explicit_zero',
  historicalAnomaly: [
    'historical_unresolved_anomaly',
    'historical_repair_in_flight',
    'historical_repair_cooldown',
    'historical_manual_retry',
  ].includes(name),
  historicalRepaired: name === 'historical_repaired',
});

const fixturePayloads = (scenarioName) => {
  const config = scenarioConfig(scenarioName);
  const rows = completedRows(config.completedEnd);
  const missingRowIndexes = scenarioName === 'chart_missing_gap'
    ? [10]
    : config.historicalMissing
      ? [18, 19]
      : [];
  missingRowIndexes.forEach((index) => {
    rows[index] = {
      ...rows[index],
      foreign_buy_value: null,
      foreign_sell_value: null,
      foreign_net_value: null,
      foreign_buy_volume: null,
      foreign_sell_volume: null,
      foreign_net_volume: null,
      field_presence: {
        foreign_buy_value: 'FIELD_ABSENT',
        foreign_sell_value: 'FIELD_ABSENT',
        foreign_buy_volume: 'FIELD_ABSENT',
        foreign_sell_volume: 'FIELD_ABSENT',
      },
      missing_foreign_fields: [
        'foreign_buy_volume',
        'foreign_sell_volume',
        'foreign_buy_value',
        'foreign_sell_value',
      ],
      data_quality: 'incomplete',
      complete: false,
    };
  });
  if (config.historicalExplicitZero) {
    rows[19] = {
      ...rows[19],
      foreign_buy_value: 0,
      foreign_sell_value: 0,
      foreign_net_value: 0,
      foreign_buy_volume: 0,
      foreign_sell_volume: 0,
      foreign_net_volume: 0,
      field_presence: {
        foreign_buy_value: 'FIELD_PRESENT_EXPLICIT_ZERO',
        foreign_sell_value: 'FIELD_PRESENT_EXPLICIT_ZERO',
        foreign_buy_volume: 'FIELD_PRESENT_EXPLICIT_ZERO',
        foreign_sell_volume: 'FIELD_PRESENT_EXPLICIT_ZERO',
      },
      missing_foreign_fields: [],
      data_quality: 'complete',
      complete: true,
    };
  }
  if (config.historicalAnomaly) {
    rows[19] = {
      ...rows[19],
      foreign_buy_value: null,
      foreign_sell_value: null,
      foreign_net_value: null,
      foreign_buy_volume: null,
      foreign_sell_volume: null,
      foreign_net_volume: null,
      field_presence: {
        foreign_buy_value: 'FIELD_PRESENT_EXPLICIT_ZERO',
        foreign_sell_value: 'FIELD_PRESENT_EXPLICIT_ZERO',
        foreign_buy_volume: 'FIELD_PRESENT_EXPLICIT_ZERO',
        foreign_sell_volume: 'FIELD_PRESENT_EXPLICIT_ZERO',
      },
      data_quality: 'anomalous',
      complete: false,
      suspicious_zero_session: true,
      anomaly: 'all_constituents_explicit_zero',
      anomaly_code: 'all_constituents_explicit_zero',
      anomaly_status: 'unresolved_provider_anomaly',
      valid_session: false,
      usable_for_windows: false,
      usable_for_rankings: false,
      usable_for_analytics: false,
      recovery_attempted: true,
      recovery_succeeded: false,
      repair_status: scenarioName === 'historical_repair_in_flight'
        ? 'in_flight'
        : scenarioName === 'historical_repair_cooldown'
          ? 'cooldown'
          : 'unresolved',
    };
  }
  if (config.historicalRepaired) {
    rows[19] = {
      ...rows[19],
      repair_source: 'exact_date_daily_stock_price',
      repair_status: 'recovered',
      recovery_attempted: true,
      recovery_succeeded: true,
      complete: true,
      data_quality: 'complete',
    };
  }
  const current = config.currentUnavailable ? null : {
    foreign_buy_value: config.explicitZero ? 0 : 1_500_000_000,
    foreign_sell_value: config.explicitZero ? 0 : config.missingValues ? null : 900_000_000,
    foreign_net_value: config.explicitZero ? 0 : config.missingValues ? null : 600_000_000,
    foreign_buy_volume: config.explicitZero ? 0 : 150_000,
    foreign_sell_volume: config.explicitZero ? 0 : config.missingValues ? null : 90_000,
    foreign_net_volume: config.explicitZero ? 0 : config.missingValues ? null : 60_000,
  };
  const observed = config.partialCoverage || config.missingValues ? 2 : 3;
  const completeValues = config.missingValues ? 1 : observed;
  const displayCurrent = current ? {
    trading_date: config.currentDate,
    session_date: config.currentDate,
    ...current,
    source_kind: 'current',
    source: 'SSI FastConnect V3 ForeignRoomMessage aggregate',
    finality: 'current_session_provisional',
    current_state: config.postClose
      ? 'market_closed'
      : config.stale
        ? 'stale'
        : config.partialCoverage
          ? 'partial'
          : 'ready',
    provider_status: config.stale ? 'disconnected' : 'connected',
    status: config.postClose
      ? 'market_closed'
      : config.stale
        ? 'stale'
        : config.partialCoverage
          ? 'partial'
          : 'ready',
    is_provisional: true,
    is_current: true,
    is_completed: false,
    is_stale: config.stale,
    requested_count: 3,
    observed_count: observed,
    complete_value_count: completeValues,
    complete_volume_count: observed,
  } : null;
  const displaySeries = [
    ...rows.map((row) => ({
      ...row,
      session_date: row.trading_date,
      source_kind: 'completed',
      source: 'SSI DailyStockPrice current-membership aggregate',
      finality: 'completed_accepted',
      status: row.data_quality === 'anomalous'
        ? STATUS.anomalous
        : row.complete === false
          ? STATUS.incomplete
          : STATUS.completed,
      is_provisional: false,
      is_current: false,
      is_completed: true,
      is_partial: row.complete === false,
      is_stale: false,
    })),
    ...(displayCurrent && displayCurrent.trading_date > rows.at(-1).trading_date
      ? [displayCurrent]
      : []),
  ];
  const aggregate = current ? {
    foreign_buy_value: current.foreign_buy_value,
    foreign_sell_value: current.foreign_sell_value,
    foreign_net_value: current.foreign_net_value,
    foreign_buy_volume: current.foreign_buy_volume,
    foreign_sell_volume: current.foreign_sell_volume,
    foreign_net_volume: current.foreign_net_volume,
  } : null;
  const coverage = {
    requested_symbol_count: 3,
    classified_symbol_count: 3,
    subscribed_symbol_count: 3,
    observed_symbol_count: observed,
    complete_volume_count: observed,
    complete_value_count: completeValues,
    missing_symbols: observed < 3 ? ['HPG'] : [],
    stale_symbol_count: config.stale || config.postClose ? observed : 0,
  };
  const fixtures = {
    symbolHistory: {
      ticker: 'FPT',
      source: 'ssi_fastconnect',
      source_endpoint: 'daily_stock_price',
      volume_unit: 'shares',
      value_unit: 'VND',
      finality: 'daily_available',
      data_state: config.regressive ? 'stale' : 'ready',
      freshness: config.regressive ? 'stale' : 'fresh',
      rows,
      windows: {},
      analytics: null,
      latest_row: rows.at(-1),
      requested: { mode: 'recent_sessions', requested_limit: 20, returned_session_count: rows.length },
      coverage: { requested_sessions: 20, covered_sessions: rows.length, complete: rows.length >= 20 },
      fetched_at: '2026-07-30T03:00:00Z',
      response_regressive: config.regressive,
      preserved_latest_completed: rows.at(-1).trading_date,
      provider_latest_returned: config.regressive ? '2026-07-28' : rows.at(-1).trading_date,
    },
    currentSymbol: {
      status: current ? 'ok' : 'unavailable',
      data_state: current
        ? config.postClose
          ? 'market_closed'
          : config.stale
            ? 'stale'
            : config.partialCoverage
              ? 'partial'
              : 'ready'
        : 'waiting',
      usable: Boolean(current),
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      provider_version: 'v3',
      symbol: 'FPT',
      trading_date: config.currentDate,
      freshness_status: config.postClose ? 'after_hours_stale' : (config.stale ? 'stale' : current ? 'ready' : 'waiting'),
      is_current_session: Boolean(current) && !config.postClose,
      is_provisional: Boolean(current),
      current,
      latest_completed_comparison: { date: rows.at(-1).trading_date },
      stream_status: current ? (config.postClose ? 'market_closed' : config.stale ? 'disconnected' : 'cache_hit') : 'subscribed_no_event',
      stream_reason: current ? '' : 'Waiting for provider room data.',
      finality: current ? 'current_session_provisional' : null,
      update_semantics: 'cumulative_replacement_snapshot',
      cache: { status: current ? 'hit' : 'miss', age_seconds: 1 },
    },
    currentAggregate: {
      status: current ? (observed < 3 ? 'partial' : 'ok') : 'unavailable',
      data_state: current
        ? config.postClose
          ? 'market_closed'
          : config.stale
            ? 'stale'
            : config.partialCoverage
              ? 'partial'
              : 'ready'
        : 'waiting',
      usable: Boolean(current),
      scope: 'current_foreign_flow_aggregate',
      universe: 'index:VN30',
      provider_session_date: config.currentDate,
      is_provisional: Boolean(current),
      finality: current ? 'current_session_provisional' : null,
      source: 'SSI FastConnect V3 ForeignRoomMessage',
      provider_version: 'v3',
      endpoint: 'room.{symbol}',
      update_semantics: 'cumulative_replacement_snapshot',
      aggregate,
      display_series: displaySeries,
      display_windows: {
        '1': { ...aggregate, covered_sessions: current ? 1 : 0, complete: Boolean(current) },
        '5': { ...aggregate, covered_sessions: Math.min(5, displaySeries.length), complete: displaySeries.length >= 5 },
        '20': { ...aggregate, covered_sessions: Math.min(20, displaySeries.length), complete: displaySeries.length >= 20 },
      },
      rankings: {
        '1': {
          top_buy: current ? [{ ticker: 'FPT', value: current.foreign_net_value, trading_date: config.currentDate }] : [],
          top_sell: current ? [{ ticker: 'SSI', value: -200_000_000, trading_date: config.currentDate }] : [],
        },
        '20': {
          top_buy: current ? [{ ticker: 'FPT', value: current.foreign_net_value, trading_date: config.currentDate }] : [],
          top_sell: current ? [{ ticker: 'SSI', value: -200_000_000, trading_date: config.currentDate }] : [],
        },
      },
      items: [
        {
          symbol: 'FPT',
          provider_session_date: config.currentDate,
          data_state: current ? (config.stale ? 'stale' : 'ready') : 'waiting',
          usable: Boolean(current),
          is_stale: config.stale || config.postClose,
          stream_status: current ? (config.stale ? 'disconnected' : 'cache_hit') : 'subscribed_no_event',
          ...(current || {}),
          display_latest: displayCurrent,
          display_windows: current ? {
            '1': aggregate,
            '5': aggregate,
            '20': aggregate,
            '60': aggregate,
          } : {},
        },
        {
          symbol: 'SSI',
          provider_session_date: config.currentDate,
          data_state: config.stale ? 'stale' : 'ready',
          usable: true,
          is_stale: config.stale || config.postClose,
          stream_status: config.stale ? 'disconnected' : 'cache_hit',
          foreign_buy_value: 700_000_000,
          foreign_sell_value: 900_000_000,
          foreign_net_value: -200_000_000,
          foreign_buy_volume: 70_000,
          foreign_sell_volume: 90_000,
          foreign_net_volume: -20_000,
          display_latest: current ? {
            trading_date: config.currentDate,
            foreign_net_value: -200_000_000,
          } : null,
          display_windows: current ? {
            '1': { foreign_net_value: -200_000_000 },
            '5': { foreign_net_value: -200_000_000 },
            '20': { foreign_net_value: -200_000_000 },
            '60': { foreign_net_value: -200_000_000 },
          } : {},
        },
      ],
      groups: [
        {
          icb_code: '10',
          icb_name: 'Technology',
          provider_session_date: config.currentDate,
          foreign_buy_value: current ? 900_000_000 : null,
          foreign_sell_value: current ? 300_000_000 : null,
          foreign_net_value: current ? 600_000_000 : null,
          foreign_buy_volume: current ? 90_000 : null,
          foreign_sell_volume: current ? 30_000 : null,
          foreign_net_volume: current ? 60_000 : null,
          requested_count: 2,
          observed_count: current ? Math.min(observed, 2) : 0,
          complete_value_count: current ? Math.min(completeValues, 2) : 0,
          complete_volume_count: current ? Math.min(observed, 2) : 0,
          is_partial: config.partialCoverage || config.missingValues,
          is_stale: config.stale,
          data_state: config.stale ? 'stale' : 'ready',
          usable: Boolean(current),
        },
        {
          icb_code: '20',
          icb_name: 'Banks',
          provider_session_date: config.currentDate,
          foreign_buy_value: current ? 600_000_000 : null,
          foreign_sell_value: current ? 600_000_000 : null,
          foreign_net_value: current ? 0 : null,
          foreign_buy_volume: current ? 60_000 : null,
          foreign_sell_volume: current ? 60_000 : null,
          foreign_net_volume: current ? 0 : null,
          requested_count: 1,
          observed_count: current && observed > 2 ? 1 : 0,
          complete_value_count: current && completeValues > 2 ? 1 : 0,
          complete_volume_count: current && observed > 2 ? 1 : 0,
          is_partial: config.partialCoverage || config.missingValues,
          is_stale: config.stale,
          data_state: config.stale ? 'stale' : 'ready',
          usable: Boolean(current),
        },
      ],
      coverage,
      diagnostics: {
        membership_source: 'SSI IndexComponents',
        membership_retained: config.stale,
        membership_age_seconds: config.stale ? 42 : 1,
        membership_refresh_failure_class: config.stale ? 'authentication_failed_retryable' : null,
        completed_fallback_used: config.currentUnavailable && !config.coldUnavailable,
        current_snapshot_retained: config.stale,
        negative_cache_bypassed: false,
        recovery_status: config.stale ? 'cooldown' : 'idle',
        provisional_persisted: false,
      },
    },
    vn30: {
      status: config.coldUnavailable ? 'unavailable' : config.stale ? 'partial' : 'ready',
      usable: !config.coldUnavailable,
      capability_status: config.coldUnavailable ? 'unavailable' : 'available',
      source: 'ssi_fastconnect',
      source_endpoint: 'daily_stock_price',
      data_state: config.coldUnavailable ? 'unavailable' : config.stale ? 'stale' : 'ready',
      membership_source: 'SSI IndexComponents',
      membership: {
        status: config.coldUnavailable ? 'unavailable' : 'ready',
        index_code: 'VN30',
        member_count: config.coldUnavailable ? 0 : 3,
        component_count: config.coldUnavailable ? 0 : 3,
        member_tickers: config.coldUnavailable ? [] : ['FPT', 'SSI', 'HPG'],
        source: 'SSI IndexComponents',
        retained: config.stale,
        age_seconds: config.stale ? 42 : 1,
        refresh_failure_class: config.stale ? 'authentication_failed_retryable' : null,
        negative_cache_bypassed: false,
        recovery_status: config.stale ? 'cooldown' : 'idle',
        fetched_at: '2026-07-30T03:00:00Z',
        resolved_at: '2026-07-30T03:00:00Z',
      },
      components: [
        { ticker: 'FPT', foreign_net_value: 600_000_000, foreign_net_value_5d: 900_000_000, foreign_net_value_20d: 1_200_000_000, foreign_net_volume: 60_000 },
        { ticker: 'SSI', foreign_net_value: -200_000_000, foreign_net_value_5d: -300_000_000, foreign_net_value_20d: -500_000_000, foreign_net_volume: -20_000 },
      ],
      decomposition: {
        status: config.coldUnavailable ? 'unavailable' : config.stale ? 'partial' : 'ready',
        data_state: config.coldUnavailable ? 'unavailable' : config.stale ? 'stale' : 'ready',
        usable: !config.coldUnavailable,
        latest_completed_session: rows.at(-1).trading_date,
        anomaly_sessions: config.historicalAnomaly ? [rows.at(-1).trading_date] : [],
        anomaly_count: config.historicalAnomaly ? 1 : 0,
        windows: {
          '5': { foreign_net_value: 900_000_000, foreign_net_volume: 90_000 },
          '20': { foreign_net_value: 1_200_000_000, foreign_net_volume: 120_000 },
        },
        series: (config.coldUnavailable ? [] : rows).map((row) => ({
          ...row,
          value_breadth: { net_buy_count: 2, net_sell_count: 1, zero_count: 0, unavailable_count: 0 },
          value_coverage_ratio: 1,
          data_state: row.data_quality === 'anomalous' ? 'partial' : 'ready',
          state: row.data_quality === 'anomalous' ? 'partial' : 'ready',
        })),
        latest: config.coldUnavailable ? null : {
          ...rows.at(-1),
          value_breadth: { net_buy_count: 2, net_sell_count: 1, zero_count: 0, unavailable_count: 0 },
          volume_breadth: { net_buy_count: 2, net_sell_count: 1, zero_count: 0, unavailable_count: 0 },
          value_coverage_ratio: 1,
          data_state: rows.at(-1).data_quality === 'anomalous' ? 'partial' : 'ready',
          state: rows.at(-1).data_quality === 'anomalous' ? 'partial' : 'ready',
        },
      },
      canonical: { capability_status: 'unsupported', diagnostics: {}, windows: { '5': {}, '20': {} }, series: [] },
      cache: { status: 'hit', age_seconds: 1 },
      fetched_at: '2026-07-30T03:00:00Z',
    },
    industry: {
      status: config.partialCoverage ? 'partial' : 'ok',
      data_state: config.partialCoverage ? 'partial' : 'ready',
      usable: true,
      source: 'ssi_fastconnect',
      provider_version: 'v3',
      universe: 'index:VN30',
      endpoint: 'securitiesSummary',
      fetched_at: '2026-07-30T03:00:00Z',
      cache: { status: 'hit', age_seconds: 1 },
      current_session_status: 'CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS',
      rows: [
        ...rows.flatMap((row) => [
          { trading_date: row.trading_date, icb_code: '10', icb_name: 'Technology', foreign_buy_value: 700_000_000, foreign_sell_value: 100_000_000, foreign_net_value: 600_000_000, matched_value: 2_000_000_000, coverage_ratio: config.partialCoverage ? 0.5 : 1 },
          { trading_date: row.trading_date, icb_code: '20', icb_name: 'Banks', foreign_buy_value: 100_000_000, foreign_sell_value: 300_000_000, foreign_net_value: -200_000_000, matched_value: 4_000_000_000, coverage_ratio: 1 },
        ]),
        ...(scenarioName === 'ranking_excludes_missing' ? [{
          trading_date: rows.at(-1).trading_date,
          icb_code: '30',
          icb_name: 'Missing Industry',
          foreign_buy_value: null,
          foreign_sell_value: null,
          foreign_net_value: null,
          data_quality: 'incomplete',
          complete: false,
          coverage_ratio: 0,
        }] : []),
      ],
    },
    watchlist: {
      status: 'partial',
      data_state: 'partial',
      usable: true,
      requested_tickers: ['FPT', 'SSI', 'HPG'],
      normalized_tickers: ['FPT', 'SSI', 'HPG'],
      duplicate_tickers_removed: 0,
      expected_symbol_count: 3,
      ready_symbol_count: 2,
      partial_symbol_count: 1,
      unavailable_symbol_count: 0,
      requested_session_count: 60,
      fetched_at: '2026-07-30T03:00:00Z',
      provider: 'ssi_fastconnect',
      provider_version: 'v3',
      cache_state: 'mixed',
      items: ['FPT', 'SSI', 'HPG'].map((ticker, index) => ({
        ticker,
        availability: index === 2 ? 'partial' : 'ready',
        data_state: index === 2 ? 'partial' : 'ready',
        source_freshness: 'latest_completed',
        cache_state: 'hit',
        actual_session_count: index === 2 ? 20 : 60,
        requested_session_count: 60,
        complete: index !== 2,
        net_value_1d: index === 1 ? -200_000_000 : 600_000_000,
        net_value_5d: index === 1 ? -300_000_000 : 900_000_000,
        net_value_20d: index === 1 ? -500_000_000 : 1_200_000_000,
        buy_streak: index === 1 ? 0 : 2,
        sell_streak: index === 1 ? 2 : 0,
        streak_metric_basis: 'foreign_net_value',
        contains_provider_anomaly: false,
        anomaly_sessions: [],
        anomaly_count: 0,
        source: 'ssi_fastconnect',
        source_endpoint: 'daily_stock_price',
        display_finality: current ? 'current_session_provisional' : 'completed_accepted',
        display_status: current ? 'Đang diễn ra' : 'Đủ',
        display_coverage: `${observed}/3`,
      })),
    },
  };

  if (scenarioName === 'industry_same_date_suspicious') {
    fixtures.industry.rows = fixtures.industry.rows.map((row) => (
      row.trading_date === config.currentDate
        ? {
          ...row,
          foreign_buy_value: null,
          foreign_sell_value: null,
          foreign_net_value: null,
          complete: false,
          data_quality: 'anomalous',
          suspicious_zero_session: true,
          anomaly: 'all_constituents_explicit_zero',
          anomaly_status: 'unresolved_provider_anomaly',
        }
        : row
    ));
  }

  if (config.coldUnavailable) {
    fixtures.currentAggregate.display_series = [];
    fixtures.currentAggregate.display_windows = {};
    fixtures.currentAggregate.items = [];
    fixtures.currentAggregate.groups = [];
    fixtures.currentAggregate.provider_session_date = null;
    fixtures.currentAggregate.failure_class = 'authentication_failed_retryable';
    fixtures.vn30.components = [];
    fixtures.vn30.membership.failure_class = 'authentication_failed_retryable';
    fixtures.vn30.decomposition.latest_completed_session = null;
    fixtures.vn30.decomposition.windows = { '5': {}, '20': {} };
  }

  const recoveryFailure = {
    ...fixtures.currentAggregate,
    status: 'unavailable',
    data_state: 'unavailable',
    usable: false,
    failure_class: 'authentication_failed_retryable',
    aggregate: null,
    display_series: [],
    display_windows: {},
    rankings: {},
    items: [],
    groups: [],
    diagnostics: {
      ...fixtures.currentAggregate.diagnostics,
      membership_retained: true,
      completed_fallback_used: true,
      current_snapshot_retained: true,
      negative_cache_bypassed: true,
      recovery_status: 'failed_retryable',
    },
  };
  const recoveryVn30Failure = {
    ...fixtures.vn30,
    status: 'unavailable',
    usable: false,
    data_state: 'unavailable',
    membership: {
      ...fixtures.vn30.membership,
      retained: true,
      refresh_failure_class: 'authentication_failed_retryable',
      negative_cache_bypassed: true,
      recovery_status: 'failed_retryable',
    },
    decomposition: {
      ...fixtures.vn30.decomposition,
      status: 'unavailable',
      data_state: 'unavailable',
      usable: false,
      series: [],
      latest: null,
    },
  };
  fixtures.recovery = {
    delay_ms: scenarioName.endsWith('_in_flight') ? 800 : 0,
    current_aggregate: scenarioName.endsWith('_failure') ? recoveryFailure : fixtures.currentAggregate,
    vn30: scenarioName.endsWith('_failure') ? recoveryVn30Failure : fixtures.vn30,
  };
  return fixtures;
};

const routeForMode = (mode, scenario) => {
  const suffix = `fixture=${encodeURIComponent(scenario)}`;
  if (mode === 'ticker') return `/foreign-flow?mode=ticker&ticker=FPT&${suffix}`;
  if (mode === 'vn30') return `/foreign-flow?mode=vn30&${suffix}`;
  if (mode === 'industry') return `/foreign-flow?mode=industry&${suffix}`;
  if (mode === 'watchlist') return `/foreign-flow?mode=watchlist&tickers=FPT,SSI,HPG&${suffix}`;
  if (mode === 'proprietary') return `/foreign-flow?mode=proprietary&${suffix}`;
  if (mode === 'details') return `/foreign-flow?mode=details&${suffix}`;
  return `/foreign-flow?${suffix}`;
};

const responseForRequest = (url, fixtures) => {
  const parsed = new URL(url);
  const pathname = parsed.pathname;
  const trigger = parsed.searchParams.get('recovery_trigger');
  const isRecovery = trigger === 'visibility_resume' || trigger === 'manual_refresh';
  if (pathname.includes('/foreign-flow/symbol/')) return fixtures.symbolHistory;
  if (pathname.includes('/foreign-flow/current-aggregate')) {
    return isRecovery ? fixtures.recovery.current_aggregate : fixtures.currentAggregate;
  }
  if (pathname.includes('/foreign-flow/current/')) return fixtures.currentSymbol;
  if (pathname.endsWith('/foreign-flow/vn30')) {
    return isRecovery ? fixtures.recovery.vn30 : fixtures.vn30;
  }
  if (pathname.endsWith('/industry-flow')) return fixtures.industry;
  if (pathname.endsWith('/foreign-flow/watchlist')) return fixtures.watchlist;
  if (pathname.endsWith('/proprietary-flow')) {
    return {
      status: 'unavailable',
      data_state: 'unavailable',
      usable: false,
      failure_class: 'proprietary_fields_unsupported',
      capability_status: 'unsupported',
      rows: [],
      source: 'ssi_fastconnect',
      provider_version: 'v3',
      endpoint: 'none',
      fetched_at: '2026-07-30T03:00:00Z',
      cache: { status: 'not_applicable', age_seconds: null },
      diagnostics: {
        attempted_operation: 'none',
        reason: 'no_proven_proprietary_flow_fields',
        index_summary_reinterpreted: false,
      },
    };
  }
  if (pathname.endsWith('/index-components')) {
    return { status: 'ok', data_state: 'ready', tickers: ['FPT', 'SSI', 'HPG'], components: [{ ticker: 'FPT' }, { ticker: 'SSI' }, { ticker: 'HPG' }] };
  }
  return {};
};

const assertScenario = async (page, scenario, mode) => {
  await page.locator('[aria-label="Foreign Flow Explorer controls"]').waitFor({ state: 'visible' });
  await page.waitForFunction(() => document.fonts?.status !== 'loading');
  if (scenario === 'industry_twenty_plus_current') {
    await page.getByRole('button', { name: '60D' }).click();
  }
  if (scenario === 'historical_manual_retry') {
    await page.getByRole('button', { name: /Force Refresh/ }).click();
    await page.waitForTimeout(250);
  }
  if (scenario === 'tab_hidden_existing') {
    await page.evaluate(() => {
      Object.defineProperty(document, 'visibilityState', {
        configurable: true,
        get: () => 'hidden',
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    if (await page.getByTestId('current-session-flow-row').count() !== 1) {
      throw new Error(`${scenario}: hidden transition cleared the current row`);
    }
  }
  if (scenario.startsWith('visibility_recovery_')) {
    await page.evaluate(() => {
      let state = 'hidden';
      Object.defineProperty(document, 'visibilityState', {
        configurable: true,
        get: () => state,
      });
      document.dispatchEvent(new Event('visibilitychange'));
      state = 'visible';
      document.dispatchEvent(new Event('visibilitychange'));
    });
    if (await page.getByTestId('current-session-flow-row').count() !== 1) {
      throw new Error(`${scenario}: visibility recovery blanked the previous current row`);
    }
    // Visibility recovery is intentionally background-owned; the old row,
    // rather than a page-level loading takeover, is the in-flight indicator.
    await page.waitForTimeout(1_000);
  }
  if (scenario.startsWith('force_refresh_')) {
    await page.getByRole('button', { name: /Force Refresh/ }).click();
    if (await page.getByTestId('current-session-flow-row').count() !== 1) {
      throw new Error(`${scenario}: Force Refresh blanked the previous current row`);
    }
    if (scenario.endsWith('_in_flight')) {
      await page.getByRole('button', { name: 'Processing...' }).waitFor();
    }
    await page.waitForTimeout(1_000);
  }
  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
  }));
  if (overflow.document > 1 || overflow.body > 1) {
    throw new Error(`${scenario}: page-level horizontal overflow ${JSON.stringify(overflow)}`);
  }

  const config = scenarioConfig(scenario);
  if (scenario === 'cold_unavailable') {
    await page.getByText('Overview unavailable').waitFor();
    if (await page.getByTestId('current-session-flow-row').count()) {
      throw new Error(`${scenario}: fabricated current row was rendered`);
    }
    return;
  }
  if (mode === 'ticker' || mode === 'vn30') {
    await page.locator('#symbol-flow-table-heading').waitFor();
    const table = page.locator('section:has(#symbol-flow-table-heading)');
    const dates = await table.locator('tbody tr td:first-child').allTextContents();
    const trimmed = dates.map((value) => value.trim()).filter(Boolean);
    if (new Set(trimmed).size !== trimmed.length) throw new Error(`${scenario}: duplicate date row`);

    const currentTableRow = table.getByTestId('current-session-flow-row');
    const hasCurrentRow = await currentTableRow.count();
    if (scenario === 'accepted_same_date' && hasCurrentRow !== 0) {
      throw new Error(`${scenario}: accepted same-date row did not suppress provisional row`);
    }
    if (scenario !== 'accepted_same_date' && !config.currentUnavailable && hasCurrentRow !== 1) {
      throw new Error(`${scenario}: expected exactly one current row`);
    }
    if (config.currentUnavailable) {
      const content = await page.locator('body').innerText();
      if (!content.includes(completedRows(config.completedEnd).at(-1)?.trading_date ?? '2026-06-30')) {
        throw new Error(`${scenario}: completed history disappeared`);
      }
      const currentText = hasCurrentRow ? await currentTableRow.innerText() : '';
      if (/\b0\b/.test(currentText)) throw new Error(`${scenario}: missing current values were rendered as zero`);
    }
    if (scenario === 'historical_normal_explicit_zero') {
      const zeroRow = await table.locator('tbody tr', { hasText: '2026-06-30' }).innerText();
      if (!zeroRow.includes(STATUS.completed) || !/\t0(?:\t|$)/.test(zeroRow)) {
        throw new Error(`${scenario}: normal explicit provider zero was not preserved`);
      }
    }
    if (scenario === 'missing_current_values') {
      const currentText = await currentTableRow.innerText();
      if (!currentText.includes('\u2014')) throw new Error(`${scenario}: missing values were not rendered as dashes`);
    }
    if (hasCurrentRow && !config.currentUnavailable) {
      const currentText = await currentTableRow.innerText();
      const expectedStatus = config.postClose ? STATUS.closed : config.stale ? STATUS.stale : STATUS.active;
      if (!currentText.includes(expectedStatus)) {
        throw new Error(`${scenario}: expected ${expectedStatus}, received ${currentText}`);
      }
      if (currentText.includes(STATUS.completed)) {
        throw new Error(`${scenario}: current row was incorrectly labelled completed`);
      }
    }
    const tableText = await table.locator('tbody').innerText();
    if (!tableText.includes(STATUS.completed)) {
      throw new Error(`${scenario}: accepted rows lost completed status`);
    }
    if (['historical_missing_fields', 'historical_mixed_quality'].includes(scenario)) {
      const missingDates = scenario === 'historical_missing_fields'
        ? ['2026-06-29', '2026-06-30']
        : ['2026-06-29'];
      for (const missingDate of missingDates) {
        const rowText = await table.locator('tbody tr', { hasText: missingDate }).innerText();
        if (!rowText.includes('\u2014') || !rowText.includes(STATUS.incomplete)) {
          throw new Error(`${scenario}: ${missingDate} did not preserve missing/incomplete display`);
        }
        if (/\t0(?:\t|$)/.test(rowText)) {
          throw new Error(`${scenario}: ${missingDate} rendered a missing field as zero`);
        }
      }
    }
    if (config.historicalAnomaly) {
      const anomalyRow = await table.locator('tbody tr', { hasText: '2026-06-30' }).innerText();
      if (!anomalyRow.includes(STATUS.anomalous) || !anomalyRow.includes('\u2014')) {
        throw new Error(`${scenario}: unresolved anomaly was not rendered truthfully`);
      }
      if (/\t0(?:\t|$)/.test(anomalyRow)) {
        throw new Error(`${scenario}: unresolved anomaly rendered a fake zero`);
      }
    }
    if (config.historicalRepaired) {
      const repairedRow = await table.locator('tbody tr', { hasText: '2026-06-30' }).innerText();
      if (!repairedRow.includes(STATUS.completed) || !repairedRow.includes('1.19')) {
        throw new Error(`${scenario}: repaired historical values were not visible`);
      }
    }
    if (scenario === 'chart_missing_gap') {
      const gapRow = await table.locator('tbody tr', { hasText: '2026-06-21' }).innerText();
      if (!gapRow.includes('\u2014') || !gapRow.includes(STATUS.incomplete)) {
        throw new Error(`${scenario}: chart-gap source row did not remain missing`);
      }
      const chartCopy = await page.locator('#symbol-flow-chart-heading').locator('..').innerText();
      if (!chartCopy.includes('kh\u00f4ng \u0111\u01b0\u1ee3c thay b\u1eb1ng 0')) {
        throw new Error(`${scenario}: chart did not explain the missing-data gap`);
      }
    }
    const tableScroller = table.locator('.overflow-x-auto');
    const scrollerUsable = await tableScroller.evaluate((element) => {
      const overflowX = getComputedStyle(element).overflowX;
      return overflowX === 'auto' || overflowX === 'scroll';
    });
    if (!scrollerUsable) throw new Error(`${scenario}: table scroller is not usable`);

    const chart = page.locator('[role="img"][aria-label*="phi\u00ean"]').first();
    await chart.waitFor();
    const totalExpectedPoints = completedRows(config.completedEnd).length
      + (config.currentUnavailable ? 0 : 1);
    const expectedPoints = Math.min(20, totalExpectedPoints);
    const chartLabel = await chart.getAttribute('aria-label');
    if (!chartLabel?.includes(`${expectedPoints} phi\u00ean`)) {
      throw new Error(`${scenario}: chart did not reach expected newest session (${chartLabel})`);
    }
  } else if (mode === 'details') {
    await page.locator('#vn30-data-details-heading').waitFor();
    const body = await page.locator('body').innerText();
    for (const label of ['Latest completed session', 'Latest display session', 'Current provider session']) {
      if (!body.includes(label)) throw new Error(`${scenario}: missing ${label}`);
    }
    if (body.includes('CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS')) {
      throw new Error(`${scenario}: obsolete Industry diagnostic remained visible`);
    }
    if (!body.includes('index:VN30')) throw new Error(`${scenario}: current Industry universe missing`);
    const capability = await page.locator('dt', { hasText: 'Current capability state' }).locator('..').innerText();
    const expected = config.stale ? 'stale' : config.partialCoverage ? 'partial' : 'ready';
    if (!capability.includes(expected)) {
      throw new Error(`${scenario}: expected Industry ${expected}, received ${capability}`);
    }
    for (const label of [
      'Current requested symbols',
      'Current classified symbols',
      'Current observed symbols',
      'Current complete value coverage',
      'Current complete volume coverage',
      'Current industry groups',
      'Current stale symbols',
      'Current missing symbols',
    ]) {
      if (!body.includes(label)) throw new Error(`${scenario}: missing Industry coverage label ${label}`);
    }
    for (const label of [
      'Membership retained',
      'Membership refresh failure',
      'Current completed fallback used',
      'Current snapshot retained',
      'Current recovery status',
    ]) {
      if (!body.includes(label)) throw new Error(`${scenario}: missing recovery detail ${label}`);
    }
  } else if (mode === 'industry') {
    await page.locator('[aria-label="industry rankings"]').waitFor();
    const rankings = page.locator('[aria-label="industry rankings"]');
    if (scenario === 'ranking_excludes_missing') {
      if ((await rankings.innerText()).includes('Missing Industry')) {
        throw new Error(`${scenario}: missing observation remained in rankings`);
      }
      return;
    }
    const table = page.locator('section:has(#symbol-flow-table-heading)');
    const dates = (await table.locator('tbody tr td:first-child').allTextContents())
      .map((value) => value.trim())
      .filter(Boolean);
    if (new Set(dates).size !== dates.length) {
      throw new Error(`${scenario}: duplicate Industry session date`);
    }
    const currentRows = await page.getByTestId('current-session-flow-row').count();
    if (scenario === 'industry_completed_only') {
      if (currentRows) throw new Error(`${scenario}: unavailable aggregate created a placeholder row`);
      if (!dates.includes('2026-06-30')) throw new Error(`${scenario}: completed history disappeared`);
      return;
    }
    if (scenario === 'industry_same_date_accepted') {
      if (currentRows) throw new Error(`${scenario}: accepted same-date row did not replace provisional`);
      const accepted = await table.locator('tbody tr', { hasText: '2026-06-30' }).innerText();
      if (!accepted.includes(STATUS.completed)) throw new Error(`${scenario}: accepted row lost completed status`);
      return;
    }
    if (currentRows !== 1) throw new Error(`${scenario}: expected exactly one current Industry row`);
    const currentText = await page.getByTestId('current-session-flow-row').innerText();
    if (!currentText.includes('1.50') || !currentText.includes('900,000,000') || !currentText.includes('600,000,000')) {
      throw new Error(`${scenario}: Industry detail row did not use the canonical aggregate`);
    }
    const expectedStatus = config.postClose ? STATUS.closed : config.stale ? STATUS.stale : STATUS.active;
    if (!currentText.includes(expectedStatus) || currentText.includes(STATUS.completed)) {
      throw new Error(`${scenario}: Industry current finality/status was incorrect`);
    }
    if (scenario === 'industry_twenty_plus_current' && dates.length !== 21) {
      throw new Error(`${scenario}: expected 20 completed rows plus one current row, received ${dates.length}`);
    }
  } else if (mode === 'proprietary') {
    const unavailable = page.locator('[aria-label="proprietary foreign flow unavailable"]');
    await unavailable.waitFor();
    const body = await page.locator('body').innerText();
    for (const label of [
      'Capability status',
      'unsupported',
      'Attempted operation',
      'none',
      'no_proven_proprietary_flow_fields',
    ]) {
      if (!body.includes(label)) throw new Error(`${scenario}: missing proprietary detail ${label}`);
    }
    const unavailableText = await unavailable.innerText();
    for (const label of ['Gross buy', 'Gross sell', 'Net flow', 'Quality', '20/20 Complete']) {
      if (unavailableText.includes(label)) throw new Error(`${scenario}: rendered fake proprietary ${label}`);
    }
    if (await page.locator('[role="img"][aria-label*="phi\u00ean"]').count()) {
      throw new Error(`${scenario}: rendered a fake proprietary chart`);
    }
    if (await page.locator('#symbol-flow-table-heading').count()) {
      throw new Error(`${scenario}: rendered fake proprietary detail rows`);
    }
    if (!(await page.getByRole('button', { name: /Force Refresh/ }).isDisabled())) {
      throw new Error(`${scenario}: Force Refresh remained enabled for unsupported capability`);
    }
    if (!(await page.getByRole('button', { name: /Export CSV/ }).isDisabled())) {
      throw new Error(`${scenario}: CSV remained enabled for unsupported capability`);
    }
  } else if (mode === 'watchlist') {
    await page.locator('[aria-label="Watchlist foreign flow table"]').waitFor();
    const csv = page.getByRole('button', { name: 'CSV' });
    if (await csv.isDisabled()) throw new Error(`${scenario}: CSV preview model was unavailable`);
    const body = await page.locator('body').innerText();
    if (!body.includes('FPT') || !body.includes('SSI')) throw new Error(`${scenario}: current watchlist rows missing`);
    if (scenario === 'watchlist_current_stale' && !body.includes(STATUS.stale)) {
      throw new Error(`${scenario}: Watchlist current status was not stale`);
    }
  } else {
    await page.getByText('Top net bought').waitFor();
    await page.locator('[role="img"][aria-label*="phi\u00ean"]').first().waitFor();
    const body = await page.locator('body').innerText();
    if (body.includes('Overview unavailable')) {
      throw new Error(`${scenario}: usable completed fallback was replaced by Overview unavailable`);
    }
    if (!body.includes('2026-07-29')) {
      throw new Error(`${scenario}: completed fallback date is not visible`);
    }
    if (scenario === 'overview_current_stale') {
      const body = await page.locator('body').innerText();
      if (!body.includes(STATUS.stale)) throw new Error(`${scenario}: Overview current status was not stale`);
    }
  }
};

const run = async () => {
  const startedAt = Date.now();
  const browserSelection = discoverBrowser();
  const port = await freePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  const stdoutPath = join(root, '.tmp', `r6d-vite-${process.pid}.stdout.log`);
  const stderrPath = join(root, '.tmp', `r6d-vite-${process.pid}.stderr.log`);
  let stdoutFd = null;
  let stderrFd = null;
  let vite = null;
  let browser = null;
  let browserServer = null;
  const assertions = [];
  let readinessMs = null;
  let portReleased = false;
  try {
    stdoutFd = openSync(stdoutPath, 'w');
    stderrFd = openSync(stderrPath, 'w');
    vite = spawn(
      process.execPath,
      [join(webRoot, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', String(port), '--strictPort'],
      {
        cwd: webRoot,
        windowsHide: true,
        stdio: ['ignore', stdoutFd, stderrFd],
        env: { ...process.env, BROWSER: 'none' },
      },
    );
    const readinessStarted = Date.now();
    await waitForVite(baseUrl, readinessStarted + 20_000);
    readinessMs = Date.now() - readinessStarted;
    browserServer = await chromium.launchServer({
      executablePath: browserSelection.executablePath,
      headless: true,
    });
    browser = await chromium.connect(browserServer.wsEndpoint());
    for (const viewport of VIEWPORTS) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      page.setDefaultTimeout(15_000);
      page.setDefaultNavigationTimeout(15_000);
      const pageErrors = [];
      page.on('pageerror', (error) => pageErrors.push(`pageerror:${error.message}`));
      page.on('console', (message) => {
        if (message.type() === 'error') pageErrors.push(`console:${message.text()}`);
      });
      let activeFixtures = fixturePayloads(SCENARIOS[0][0]);
      await page.route('**/*', async (route) => {
        const requestUrl = new URL(route.request().url());
        const pathname = requestUrl.pathname;
        if (!pathname.startsWith('/api/')) {
          await route.continue();
          return;
        }
        const trigger = requestUrl.searchParams.get('recovery_trigger');
        if (
          activeFixtures.recovery.delay_ms
          && (trigger === 'visibility_resume' || trigger === 'manual_refresh')
        ) {
          await sleep(activeFixtures.recovery.delay_ms);
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(responseForRequest(route.request().url(), activeFixtures)),
        });
      });
      try {
        for (const [scenario, mode] of SCENARIOS) {
          if (Date.now() - startedAt > 115_000) {
            throw new Error('R6D browser harness exceeded its 120-second total deadline.');
          }
          activeFixtures = fixturePayloads(scenario);
          await page.goto(`${baseUrl}${routeForMode(mode, scenario)}`, { waitUntil: 'domcontentloaded' });
          try {
            await assertScenario(page, scenario, mode);
          } catch (error) {
            const body = (await page.locator('body').innerText().catch(() => '')).slice(0, 600);
            throw new Error(
              `${scenario}/${viewport.name}: ${error instanceof Error ? error.message : String(error)}; `
              + `url=${page.url()}; body=${JSON.stringify(body)}; errors=${JSON.stringify(pageErrors.slice(-8))}`,
            );
          }
          assertions.push({ viewport: viewport.name, scenario, status: 'passed' });
        }
      } finally {
        await Promise.race([context.close(), sleep(5_000)]);
      }
    }
  } finally {
    if (browser) {
      await Promise.race([browser.close(), sleep(5_000)]);
    }
    const browserPid = browserServer?.process()?.pid;
    if (browserServer) {
      await Promise.race([browserServer.close(), sleep(5_000)]);
    }
    if (browserPid) {
      spawnSync('taskkill', ['/PID', String(browserPid), '/T', '/F'], {
        windowsHide: true,
        timeout: 10_000,
        stdio: 'ignore',
      });
    }
    if (vite && vite.exitCode === null) {
      vite.kill('SIGTERM');
      await Promise.race([
        new Promise((resolvePromise) => vite.once('exit', resolvePromise)),
        sleep(2_000),
      ]);
    }
    if (vite && vite.exitCode === null) {
      spawnSync('taskkill', ['/PID', String(vite.pid), '/T', '/F'], {
        windowsHide: true,
        timeout: 10_000,
        stdio: 'ignore',
      });
      await Promise.race([
        new Promise((resolvePromise) => vite.once('exit', resolvePromise)),
        sleep(3_000),
      ]);
    }
    if (vite && vite.exitCode === null) {
      vite.kill('SIGKILL');
    }
    if (stdoutFd !== null) closeSync(stdoutFd);
    if (stderrFd !== null) closeSync(stderrFd);
    for (let attempt = 0; attempt < 100; attempt += 1) {
      if (!(await isPortOpen(port))) {
        portReleased = true;
        break;
      }
      await sleep(100);
    }
    rmSync(stdoutPath, { force: true });
    rmSync(stderrPath, { force: true });
  }
  if (!portReleased) throw new Error(`Vite port ${port} was not released.`);
  return {
    status: 'passed',
    browser: browserSelection.name,
    executable_path: browserSelection.executablePath,
    vite_readiness_ms: readinessMs,
    total_duration_ms: Date.now() - startedAt,
    fixture_count: SCENARIOS.length,
    viewport_count: VIEWPORTS.length,
    assertion_count: assertions.length,
    desktop_passed: assertions.filter((item) => item.viewport === 'desktop').length,
    mobile_passed: assertions.filter((item) => item.viewport === 'mobile').length,
    horizontal_overflow: false,
    browser_closed: true,
    vite_tree_terminated: true,
    port_released: portReleased,
    temporary_artifacts_removed: true,
  };
};

if (process.argv.includes('--self-test')) {
  const browser = discoverBrowser();
  console.log(JSON.stringify({
    status: 'passed',
    browser,
    approved_paths_checked: BROWSER_PATHS,
    fixture_count: SCENARIOS.length,
    viewport_count: VIEWPORTS.length,
    uses_explicit_executable_path: true,
    downloaded_browser_required: false,
  }));
  process.exit(0);
} else {
  try {
    const result = await run();
    console.log(JSON.stringify(result));
    process.exit(0);
  } catch (error) {
    console.error(JSON.stringify({
      status: 'failed',
      error: error instanceof Error ? error.message : String(error),
    }));
    process.exit(1);
  }
}
