import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { stocksApi } from '../api/stocks';
import { AppPage, Button } from '../components/common';
import {
  buildHoldingsSnapshot, HOLDINGS_CHART_RANGE, HOLDINGS_KEY, HOLDINGS_LIMIT,
  loadHoldingCharts, parseHolding, readHoldings, type Holding,
} from '../utils/vietnamHoldings';
import { vietnamTodayIso } from '../utils/vietnamIntradayPolling';

type Snapshot = ReturnType<typeof buildHoldingsSnapshot>;
const price = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const weight = new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 1 });
const inputClass = 'w-full rounded-lg border border-border bg-base px-3 py-2 text-foreground';

function SnapshotResults({ snapshot, confirmed }: { snapshot: Snapshot; confirmed: boolean }) {
  const aggregate = confirmed ? snapshot.aggregate : null;
  return (
    <>
      {aggregate ? (
        <dl className="grid gap-3 rounded-xl border border-border/70 bg-base p-4 text-sm sm:grid-cols-3">
          <div><dt className="text-secondary-text">Total value</dt><dd className="mt-1 font-semibold">{price.format(aggregate.total)} VND</dd></div>
          <div><dt className="text-secondary-text">Largest holding</dt><dd className="mt-1 font-semibold">{aggregate.largest.ticker} · {weight.format(aggregate.largest.value / aggregate.total)}</dd></div>
          <div><dt className="text-secondary-text">Top-three weight</dt><dd className="mt-1 font-semibold">{weight.format(aggregate.topThreeWeight)}</dd></div>
        </dl>
      ) : null}
      <div className="overflow-x-auto rounded-lg border border-border/70" role="region" aria-label="Holding values table" tabIndex={0}>
        <table className="w-full whitespace-nowrap text-left text-sm">
          <thead className="bg-base text-secondary-text">
            <tr>
              {['Ticker', 'Shares', 'Close (VND/share)', 'Value (VND)', 'Weight', 'Mark status'].map((label) => (
                <th key={label} scope="col" className="px-3 py-2 font-medium">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {snapshot.rows.map((row) => (
              <tr key={row.ticker} className="border-t border-border/70">
                <th scope="row" className="px-3 py-2">{row.ticker}</th>
                <td className="px-3 py-2 tabular-nums">{price.format(row.shares)}</td>
                <td className="px-3 py-2 tabular-nums">{row.close === undefined ? '—' : price.format(row.close)}</td>
                <td className="px-3 py-2 tabular-nums">{confirmed && row.value !== undefined ? price.format(row.value) : '—'}</td>
                <td className="px-3 py-2 tabular-nums">{aggregate && row.value !== undefined ? weight.format(row.value / aggregate.total) : '—'}</td>
                <td className="px-3 py-2">{row.cache ? row.status + ' · ' + row.cache : row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function VietnamHoldingsPage() {
  const [holdings, setHoldings] = useState(readHoldings);
  const [ticker, setTicker] = useState('');
  const [shares, setShares] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [inputError, setInputError] = useState('');
  const [storageError, setStorageError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [previous, setPrevious] = useState<Snapshot | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const active = useRef<AbortController | null>(null);

  useEffect(() => () => {
    active.current?.abort();
    active.current = null;
  }, []);

  function clearForm() {
    setTicker('');
    setShares('');
    setEditing(null);
    setInputError('');
  }

  function updateHoldings(next: Holding[]) {
    active.current?.abort();
    setHoldings(next);
    setSnapshot(null);
    setPrevious(null);
    setConfirmed(false);
    setStorageError(false);
    try {
      if (next.length) localStorage.setItem(HOLDINGS_KEY, JSON.stringify(next));
      else localStorage.removeItem(HOLDINGS_KEY);
    } catch {
      setStorageError(true);
    }
  }

  function saveHolding(event: FormEvent) {
    event.preventDefault();
    const holding = parseHolding(ticker, shares);
    if (!holding) {
      setInputError('Enter a three-character VN equity ticker and a positive whole-share quantity.');
      return;
    }
    if (!editing && holdings.some((row) => row.ticker === holding.ticker)) {
      setInputError(holding.ticker + ' is already in your holdings.');
      return;
    }
    if (!editing && holdings.length >= HOLDINGS_LIMIT) return;
    updateHoldings(editing
      ? holdings.map((row) => row.ticker === editing ? holding : row)
      : [...holdings, holding]);
    clearForm();
  }

  async function load() {
    if (active.current || !holdings.length) return;
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setSnapshot(null);
    setConfirmed(false);
    try {
      const results = await loadHoldingCharts(holdings, controller.signal, (symbol, signal) =>
        stocksApi.getVietnamChart(symbol, HOLDINGS_CHART_RANGE, { signal }));
      if (!controller.signal.aborted) {
        setSnapshot(buildHoldingsSnapshot(holdings, results, vietnamTodayIso()));
      }
    } finally {
      if (active.current === controller) {
        active.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <AppPage className="space-y-5">
      <header className="border-b border-border/70 pb-4">
        <Link to="/vietnam" className="text-sm text-secondary-text underline">Vietnam Market Overview</Link>
        <h1 className="mt-2 text-2xl font-semibold text-foreground md:text-3xl">VN Holdings Concentration Snapshot</h1>
        <p className="mt-1 max-w-3xl text-sm text-secondary-text">
          See how the value of up to eight VN equities is distributed on one observed prior trading date. Tickers and share quantities are stored in this browser.
        </p>
      </header>

      <section aria-labelledby="holdings-heading" className="space-y-4 rounded-2xl border border-border/70 bg-card p-4 md:p-5">
        <h2 id="holdings-heading" className="text-lg font-semibold">Holdings <span className="text-sm font-normal text-secondary-text">{holdings.length}/{HOLDINGS_LIMIT}</span></h2>
        <form onSubmit={saveHolding} className="flex flex-wrap items-end gap-3">
          <label className="w-36 max-w-full space-y-1 text-sm">
            <span>VN equity ticker</span>
            <input className={inputClass} value={ticker} onChange={(event) => setTicker(event.target.value)} placeholder="FPT" maxLength={12} disabled={Boolean(editing)} />
          </label>
          <label className="w-40 max-w-full space-y-1 text-sm">
            <span>Whole shares</span>
            <input className={inputClass} value={shares} onChange={(event) => setShares(event.target.value)} inputMode="numeric" placeholder="100" maxLength={24} />
          </label>
          <Button type="submit" variant="secondary" disabled={!editing && holdings.length >= HOLDINGS_LIMIT}>{editing ? 'Save shares' : 'Add holding'}</Button>
          {editing ? <Button variant="ghost" onClick={clearForm}>Cancel edit</Button> : null}
        </form>
        {inputError ? <p role="alert" className="text-sm text-danger">{inputError}</p> : null}
        {storageError ? <p role="alert" className="text-sm text-danger">Could not update browser storage. Changes apply to this page only.</p> : null}
        {holdings.length ? (
          <ul className="grid gap-2 sm:grid-cols-2">
            {holdings.map((row) => (
              <li key={row.ticker} className="flex flex-wrap items-center justify-between gap-x-2 rounded-lg border border-border/70 px-3 py-2">
                <span className="text-sm"><strong>{row.ticker}</strong> · {price.format(row.shares)} {row.shares === 1 ? 'share' : 'shares'}</span>
                <span className="flex gap-1">
                  <Button size="xsm" variant="ghost" aria-label={'Edit ' + row.ticker} onClick={() => {
                    setEditing(row.ticker);
                    setTicker(row.ticker);
                    setShares(String(row.shares));
                    setInputError('');
                  }}>Edit</Button>
                  <Button size="xsm" variant="ghost" aria-label={'Remove ' + row.ticker} onClick={() => {
                    updateHoldings(holdings.filter(({ ticker }) => ticker !== row.ticker));
                    if (editing === row.ticker) clearForm();
                  }}>Remove</Button>
                </span>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button disabled={!holdings.length || Boolean(editing)} isLoading={loading} loadingText="Loading daily charts…" onClick={() => void load()}>
            {snapshot || previous ? 'Refresh snapshot' : 'Load snapshot'}
          </Button>
          <Button variant="ghost" disabled={!holdings.length && !ticker && !shares} onClick={() => {
            updateHoldings([]);
            clearForm();
          }}>Clear holdings</Button>
        </div>
      </section>

      <section aria-labelledby="snapshot-heading" className="space-y-4 rounded-2xl border border-border/70 bg-card p-4 md:p-5">
        <div className="space-y-1">
          <h2 id="snapshot-heading" className="text-lg font-semibold">Snapshot</h2>
          <p className="text-sm text-secondary-text" role="status">
            {loading ? 'Loading SSI daily charts…' : snapshot
              ? (snapshot.date ?? 'No observed prior date') + ' · SSI V3 DailyOhlc · ' + snapshot.coverage + '/' + snapshot.rows.length + ' eligible'
              : 'Load saved holdings to check price coverage.'}
          </p>
        </div>
        {snapshot ? (
          <>
            {snapshot.coverage < snapshot.rows.length ? (
              <p className="text-sm text-secondary-text">Coverage is incomplete. Total value and weights are unavailable.</p>
            ) : !snapshot.aggregate ? (
              <p className="text-sm text-secondary-text">Total value exceeds the supported range. Weights are unavailable.</p>
            ) : null}
            {snapshot.date && snapshot.coverage > 0 && !confirmed ? (
              <div className="space-y-2 rounded-xl border border-border/70 bg-base p-3">
                <p className="text-sm text-secondary-text">Confirm these are VN equities and the entered shares apply to {snapshot.date} on the same share basis as the SSI closes. Adjust quantities manually for corporate actions if needed.</p>
                <Button variant="secondary" size="sm" onClick={() => {
                  setConfirmed(true);
                  if (snapshot.aggregate) setPrevious(snapshot);
                }}>Confirm shares for {snapshot.date}</Button>
              </div>
            ) : null}
            <SnapshotResults snapshot={snapshot} confirmed={confirmed} />
          </>
        ) : null}
        {previous && !(confirmed && snapshot?.aggregate) ? (
          <details className="space-y-3 rounded-xl border border-border/70 bg-base p-3">
            <summary className="cursor-pointer text-sm font-medium">Previous confirmed snapshot · {previous.date}</summary>
            <SnapshotResults snapshot={previous} confirmed />
          </details>
        ) : null}
      </section>
    </AppPage>
  );
}

