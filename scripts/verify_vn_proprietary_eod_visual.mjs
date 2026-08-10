#!/usr/bin/env node
/* Bounded system-browser acceptance for verified manual HOSE Proprietary EOD. */

import { createRequire } from 'node:module';
import { createConnection, createServer } from 'node:net';
import { existsSync, mkdirSync, openSync, closeSync, rmSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const webRoot = join(root, 'apps', 'dsa-web');
const require = createRequire(join(webRoot, 'package.json'));
const { chromium } = require('@playwright/test');
const browsers = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
];
const viewports = [
  { name: 'desktop', width: 1366, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
];
const scenarioMatrix = [
  'no_data', 'value_only', 'with_volume', 'positive_net', 'negative_net',
  'zero_net', 'missing_volume', 'source_url', 'source_hash', 'history_20',
  'refresh_loading', 'refresh_lkg', 'storage_error', 'foreign_regression',
];
const scenarios = process.env.VN_PROPRIETARY_EOD_VISUAL_SCENARIO
  ? [process.env.VN_PROPRIETARY_EOD_VISUAL_SCENARIO]
  : scenarioMatrix;
const sleep = (ms) => new Promise((resolvePromise) => setTimeout(resolvePromise, ms));

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

const portOpen = (port) => String(spawnSync('netstat', ['-ano', '-p', 'TCP'], {
  windowsHide: true, timeout: 2_000, encoding: 'utf8',
}).stdout || '').split(/\r?\n/).some((line) => line.includes(`:${port}`) && /LISTENING/i.test(line));

const acceptsConnection = (port) => new Promise((resolvePromise) => {
  const socket = createConnection({ host: '127.0.0.1', port });
  const finish = (value) => {
    socket.destroy();
    resolvePromise(value);
  };
  socket.setTimeout(300, () => finish(false));
  socket.once('connect', () => finish(true));
  socket.once('error', () => finish(false));
});

const waitReady = async (url) => {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1_500) });
      if (response.ok) return;
    } catch { /* bounded retry */ }
    await sleep(150);
  }
  throw new Error('Vite readiness exceeded 20 seconds');
};

const row = (date, index, scenario) => {
  const buy = 2_000_000_000 + index * 10_000_000;
  const sell = scenario === 'negative_net'
    ? buy + 500_000_000
    : scenario === 'zero_net'
      ? buy
      : buy - 500_000_000;
  const volume = !['value_only', 'missing_volume'].includes(scenario);
  return {
    trading_date: date,
    exchange: 'HOSE',
    buy_volume: volume ? 100_000 + index : null,
    sell_volume: volume ? 80_000 + index : null,
    net_volume: volume ? 20_000 : null,
    buy_value: buy,
    sell_value: sell,
    net_value: buy - sell,
    source_type: 'official_exchange_pdf_manual_entry',
    source_url: 'https://example.test/hose-official.pdf',
    source_title: 'Công bố chính thức HOSE',
    source_file_name: scenario === 'source_url' ? null : 'hose-official.pdf',
    source_file_hash: ['source_hash', 'with_volume', 'history_20'].includes(scenario) ? 'a'.repeat(64) : null,
    source_file_size: ['source_hash', 'with_volume', 'history_20'].includes(scenario) ? 128 : null,
    source_evidence_strength: ['source_hash', 'with_volume', 'history_20'].includes(scenario)
      ? 'OFFICIAL_PDF_HASHED' : 'OFFICIAL_URL_USER_VERIFIED',
    verified_by_user: true,
    imported_at: '2026-08-06T12:00:00Z',
    finality: 'completed_daily',
    complete_value: true,
    complete_volume: volume,
    complete: true,
    data_quality: volume ? 'accepted' : 'accepted_value_only',
    warnings: volume ? [] : ['source_pdf_unavailable_hash_not_recorded'],
  };
};

const fixture = (scenario) => {
  if (scenario === 'storage_error') return { state: 'storage_error', rows: [] };
  if (scenario === 'no_data') return { state: 'no_data', rows: [] };
  const count = scenario === 'history_20' ? 20 : 1;
  const rows = Array.from({ length: count }, (_, index) => row(
    `2026-07-${String(index + 10).padStart(2, '0')}`,
    index,
    scenario,
  ));
  return { state: 'ready', rows };
};

const foreignHistory = {
  ticker: 'FPT', source: 'ssi_fastconnect', source_endpoint: 'daily_stock_price',
  volume_unit: 'shares', value_unit: 'VND', finality: 'daily_available',
  data_state: 'empty', freshness: 'empty', rows: [], windows: {}, latest_row: null,
  requested: { mode: 'recent_sessions', requested_limit: 20, returned_session_count: 0 },
  coverage: { requested_sessions: 20, covered_sessions: 0, complete: false },
  fetched_at: '2026-08-06T12:00:00Z',
};

const fulfillJson = (route, value, status = 200) => route.fulfill({
  status,
  contentType: 'application/json',
  body: JSON.stringify(value),
});

const run = async () => {
  const executablePath = browsers.find(existsSync);
  if (!executablePath) throw new Error('No approved system Chrome/Edge executable found');
  const port = await freePort();
  if (portOpen(port)) throw new Error(`dynamic port collision: ${port}`);
  const tmp = join(root, '.tmp');
  mkdirSync(tmp, { recursive: true });
  const stdoutPath = join(tmp, `proprietary-eod-vite-${process.pid}.stdout.log`);
  const stderrPath = join(tmp, `proprietary-eod-vite-${process.pid}.stderr.log`);
  const stdout = openSync(stdoutPath, 'w');
  const stderr = openSync(stderrPath, 'w');
  let vite = null;
  let browserServer = null;
  let browser = null;
  const results = [];
  try {
    vite = spawn(process.execPath, [
      join(webRoot, 'node_modules', 'vite', 'bin', 'vite.js'),
      '--host', '127.0.0.1', '--port', String(port), '--strictPort',
    ], { cwd: webRoot, stdio: ['ignore', stdout, stderr], windowsHide: true });
    await waitReady(`http://127.0.0.1:${port}`);
    browserServer = await chromium.launchServer({ executablePath, headless: true });
    browser = await chromium.connect(browserServer.wsEndpoint());
    for (const scenario of scenarios) {
      for (const viewport of viewports) {
        const context = await browser.newContext({ viewport });
        const page = await context.newPage();
        page.setDefaultTimeout(8_000);
        const counts = { latest: 0, history: 0 };
        const data = fixture(scenario);
        await page.route('**/api/v1/stocks/**', async (route) => {
          const pathname = new URL(route.request().url()).pathname;
          if (pathname.endsWith('/vn/proprietary-flow/eod/latest')) {
            counts.latest += 1;
            if (scenario === 'refresh_lkg' && counts.latest > 1) return fulfillJson(route, { detail: 'offline' }, 503);
            if (scenario === 'refresh_loading' && counts.latest > 1) await sleep(450);
            return fulfillJson(route, {
              status: data.rows.length ? 'ok' : data.state === 'storage_error' ? 'error' : 'empty',
              data_state: data.state,
              exchange: 'HOSE', latest: data.rows.at(-1) ?? null,
              source: 'official_exchange_pdf_manual_entry', warnings: [],
            });
          }
          if (pathname.endsWith('/vn/proprietary-flow/eod/history')) {
            counts.history += 1;
            if (scenario === 'refresh_lkg' && counts.history > 1) return fulfillJson(route, { detail: 'offline' }, 503);
            if (scenario === 'refresh_loading' && counts.history > 1) await sleep(450);
            return fulfillJson(route, {
              status: data.rows.length ? 'ok' : data.state === 'storage_error' ? 'error' : 'empty',
              data_state: data.state, exchange: 'HOSE', count: data.rows.length,
              series: data.rows, source_summary: { value_unit: 'VND', volume_unit: 'shares' }, warnings: [],
            });
          }
          if (pathname.endsWith('/vn/foreign-flow/current/FPT')) return fulfillJson(route, {
            status: 'unavailable', data_state: 'waiting', usable: false, source: 'ssi_fastconnect',
            provider_version: 'v3', symbol: 'FPT', freshness_status: 'empty', current: null,
            stream_status: 'waiting', stream_reason: '', finality: 'current_session_provisional', cache: {},
          });
          if (pathname.endsWith('/vn/foreign-flow/FPT')) return fulfillJson(route, foreignHistory);
          return fulfillJson(route, { status: 'unavailable', data_state: 'unavailable', usable: false, rows: [] });
        });
        const mode = scenario === 'foreign_regression' ? 'ticker&ticker=FPT' : 'proprietary';
        await page.goto(`http://127.0.0.1:${port}/foreign-flow?mode=${mode}`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
        if (scenario === 'foreign_regression') {
          await page.getByRole('heading', { name: 'Foreign Flow Explorer' }).waitFor();
          if (await page.getByRole('heading', { name: 'Dữ liệu tự doanh HOSE cuối ngày' }).count()) throw new Error('foreign tab rendered EOD component');
        } else {
          await page.getByRole('heading', { name: 'Dữ liệu tự doanh HOSE cuối ngày' }).waitFor();
          if (scenario === 'no_data') await page.getByText('Chưa có dữ liệu').waitFor();
          else if (scenario === 'storage_error') await page.getByText('Không khả dụng').waitFor();
          else await page.getByRole('region', { name: 'Phiên tự doanh HOSE mới nhất' }).waitFor();
          if (scenario === 'refresh_loading') {
            const refresh = page.getByRole('button', { name: 'Làm mới dữ liệu tự doanh cuối ngày' });
            await refresh.click();
            await page.waitForTimeout(25);
            if (!(await refresh.isDisabled())) throw new Error(`refresh was not single-flight disabled: ${scenario}/${viewport.name}; counts=${JSON.stringify(counts)}`);
            await page.waitForTimeout(500);
          }
          if (scenario === 'refresh_lkg') {
            await page.getByRole('button', { name: 'Làm mới dữ liệu tự doanh cuối ngày' }).click();
            await page.getByRole('alert').waitFor();
            await page.getByRole('region', { name: 'Phiên tự doanh HOSE mới nhất' }).waitFor();
          }
          const body = await page.locator('body').innerText();
          if (/Realtime|Đang diễn ra|Tạm tính|15 giây/i.test(body)) throw new Error(`forbidden current-session copy in ${scenario}`);
          if (counts.latest !== (['refresh_loading', 'refresh_lkg'].includes(scenario) ? 2 : 1)) throw new Error(`unexpected latest request count ${counts.latest}`);
          if (counts.history !== (['refresh_loading', 'refresh_lkg'].includes(scenario) ? 2 : 1)) throw new Error(`unexpected history request count ${counts.history}`);
        }
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
        if (overflow) throw new Error(`page horizontal overflow: ${scenario}/${viewport.name}`);
        if (viewport.name === 'mobile' && data.rows.length) {
          const tableScroller = page.locator('table').locator('..');
          if (await tableScroller.count()) {
            const dimensions = await tableScroller.evaluate((node) => ({ client: node.clientWidth, scroll: node.scrollWidth }));
            if (dimensions.scroll <= dimensions.client) throw new Error(`mobile table is not scrollable: ${scenario}`);
          }
        }
        results.push({ scenario, viewport: viewport.name, page_overflow: false, latest_requests: counts.latest, history_requests: counts.history });
        await context.close();
      }
    }
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    if (browserServer) await browserServer.close().catch(() => undefined);
    if (vite && vite.exitCode === null) {
      vite.kill('SIGTERM');
      await Promise.race([
        new Promise((resolvePromise) => vite.once('exit', resolvePromise)),
        sleep(2_000),
      ]);
    }
    if (vite && vite.exitCode === null) {
      spawnSync('taskkill', ['/PID', String(vite.pid), '/T', '/F'], { windowsHide: true, timeout: 8_000 });
    }
    closeSync(stdout); closeSync(stderr);
    const releaseDeadline = Date.now() + 10_000;
    while (await acceptsConnection(port) && Date.now() < releaseDeadline) await sleep(150);
    if (await acceptsConnection(port)) throw new Error(`Vite port ${port} remains open after cleanup`);
    rmSync(stdoutPath, { force: true });
    rmSync(stderrPath, { force: true });
  }
  console.log(JSON.stringify({ outcome: 'pass', browser: executablePath, port_released: true, checks: results.length, results }));
};

const timeout = new Promise((_, reject) => {
  const guard = setTimeout(() => reject(new Error('visual acceptance exceeded 120 seconds')), 120_000);
  guard.unref();
});
await Promise.race([run(), timeout]);
