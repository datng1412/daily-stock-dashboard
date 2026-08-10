import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  stocksApi,
  type VietnamProprietaryFlowEodHistoryResponse,
  type VietnamProprietaryFlowEodLatestResponse,
  type VietnamProprietaryFlowEodRow,
} from '../../api/stocks';
import { Button, EmptyState } from '../common';
import { foreignFlowSignChartColor, foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import {
  formatForeignFlowValue,
  formatForeignFlowVolume,
  formatFullSharesTitle,
  formatFullVndTitle,
} from '../../utils/vietnamNumberFormat';

type EodData = {
  latest: VietnamProprietaryFlowEodLatestResponse;
  history: VietnamProprietaryFlowEodHistoryResponse;
};

const safeSourceUrl = (value: string) => {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.toString() : null;
  } catch {
    return null;
  }
};

const statusLabel = (row: VietnamProprietaryFlowEodRow) => (
  row.dataQuality === 'suspicious'
    ? 'Bất thường dữ liệu'
    : row.completeValue
      ? 'Đủ'
      : 'Thiếu dữ liệu'
);

const ValueCell = ({ value, kind = 'value' }: { value: number | null; kind?: 'value' | 'volume' }) => (
  <span
    className="tabular-nums"
    aria-label={kind === 'value' ? formatFullVndTitle(value) : formatFullSharesTitle(value)}
  >
    {kind === 'value' ? formatForeignFlowValue(value) : formatForeignFlowVolume(value)}
  </span>
);

export const ProprietaryFlowEodView = () => {
  const [data, setData] = useState<EodData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);
  const inFlight = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    const currentRequest = ++requestId.current;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const [latest, history] = await Promise.all([
        stocksApi.getVietnamProprietaryFlowEodLatest({ exchange: 'HOSE', signal: controller.signal }),
        stocksApi.getVietnamProprietaryFlowEodHistory({ exchange: 'HOSE', limit: 60, signal: controller.signal }),
      ]);
      if (requestId.current === currentRequest && !controller.signal.aborted) {
        setData({ latest, history });
      }
    } catch {
      if (requestId.current === currentRequest && !controller.signal.aborted) {
        setError(data
          ? 'Không thể làm mới dữ liệu. Đang giữ kết quả cuối cùng đã tải.'
          : 'Không thể tải dữ liệu tự doanh cuối ngày.');
      }
    } finally {
      if (requestId.current === currentRequest) {
        inFlight.current = false;
        setLoading(false);
      }
    }
  }, [data]);

  useEffect(() => {
    const initialRequest = globalThis.setTimeout(() => void load(), 0);
    return () => {
      globalThis.clearTimeout(initialRequest);
      requestId.current += 1;
      inFlight.current = false;
      controllerRef.current?.abort();
    };
  // One mount-owned request. Manual refresh is the only repeat trigger.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows = useMemo(
    () => [...(data?.history.series ?? [])].sort((left, right) => left.tradingDate.localeCompare(right.tradingDate)),
    [data],
  );
  const latest = data?.latest.latest ?? rows.at(-1) ?? null;

  return (
    <section className="space-y-4" aria-labelledby="proprietary-eod-title">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-border/70 bg-card p-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-secondary-text">HOSE · Phiên đã hoàn tất</p>
          <h2 id="proprietary-eod-title" className="mt-1 text-xl font-semibold">Dữ liệu tự doanh HOSE cuối ngày</h2>
          <p className="mt-1 text-sm text-secondary-text">Nhập thủ công có xác minh từ công bố chính thức; không phải dữ liệu trong phiên.</p>
        </div>
        <Button aria-label="Làm mới dữ liệu tự doanh cuối ngày" variant="outline" size="sm" onClick={() => void load()} disabled={loading} isLoading={loading}>
          <RefreshCw className="h-4 w-4" /> Làm mới
        </Button>
      </div>

      {error ? <div role="alert" className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">{error}</div> : null}
      {loading && !data ? <div className="h-32 animate-pulse rounded-xl bg-elevated/50" aria-label="Đang tải dữ liệu tự doanh cuối ngày" /> : null}

      {!loading && !latest && data?.latest.dataState === 'storage_error' ? (
        <EmptyState title="Không khả dụng" description="Kho dữ liệu tự doanh cuối ngày hiện không thể đọc." />
      ) : null}
      {!loading && !latest && data && data.latest.dataState !== 'storage_error' ? (
        <EmptyState title="Chưa có dữ liệu" description="Chưa có phiên HOSE nào được nhập và xác minh qua quy trình thủ công." />
      ) : null}

      {latest ? (
        <>
          <section className="rounded-xl border border-border/70 bg-card p-4" aria-label="Phiên tự doanh HOSE mới nhất">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div><p className="text-xs text-secondary-text">Ngày giao dịch</p><p className="font-semibold">{latest.tradingDate}</p></div>
              <span className="rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">{statusLabel(latest)}</span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div><p className="text-xs text-secondary-text">Giá trị mua</p><p className="text-lg font-semibold"><ValueCell value={latest.buyValue} /></p></div>
              <div><p className="text-xs text-secondary-text">Giá trị bán</p><p className="text-lg font-semibold"><ValueCell value={latest.sellValue} /></p></div>
              <div><p className="text-xs text-secondary-text">Giá trị ròng</p><p className={`text-lg font-semibold ${foreignFlowSignTextClass(latest.netValue)}`}><ValueCell value={latest.netValue} /></p></div>
            </div>
            <div className="mt-3 grid gap-3 border-t border-border/60 pt-3 text-sm sm:grid-cols-3">
              <div><p className="text-xs text-secondary-text">Khối lượng mua</p><ValueCell value={latest.buyVolume} kind="volume" /></div>
              <div><p className="text-xs text-secondary-text">Khối lượng bán</p><ValueCell value={latest.sellVolume} kind="volume" /></div>
              <div><p className="text-xs text-secondary-text">Khối lượng ròng</p><ValueCell value={latest.netVolume} kind="volume" /></div>
            </div>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-secondary-text">
              <span>Nguồn: {safeSourceUrl(latest.sourceUrl) ? <a className="text-cyan underline" href={safeSourceUrl(latest.sourceUrl) ?? undefined} target="_blank" rel="noopener noreferrer">{latest.sourceTitle || latest.sourceFileName || 'Công bố chính thức HOSE'}</a> : latest.sourceTitle || 'Công bố chính thức HOSE'}</span>
              <span>Xác minh: {latest.sourceEvidenceStrength === 'OFFICIAL_PDF_HASHED' ? 'PDF chính thức đã băm SHA-256' : 'URL chính thức, người dùng đã xác minh'}</span>
              {latest.sourceFileHash ? <span aria-label={`SHA-256 ${latest.sourceFileHash}`}>SHA-256: {latest.sourceFileHash.slice(0, 12)}…</span> : null}
            </div>
          </section>

          <section className="rounded-xl border border-border/70 bg-card p-4" aria-labelledby="proprietary-eod-chart-title">
            <h3 id="proprietary-eod-chart-title" className="text-sm font-semibold">Lịch sử giá trị tự doanh cuối ngày</h3>
            <p className="mt-1 text-xs text-secondary-text">Đơn vị VND. Khoảng trống là dữ liệu thiếu, không được đổi thành 0.</p>
            <div className="mt-3 h-72 min-w-0" role="img" aria-label={`Biểu đồ tự doanh cuối ngày, ${rows.length} phiên`}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
                  <XAxis dataKey="tradingDate" tickFormatter={(value: string) => value.slice(5)} tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(value: number) => formatForeignFlowValue(value)} tick={{ fontSize: 11 }} width={78} />
                  <Tooltip formatter={(value) => formatForeignFlowValue(typeof value === 'number' ? value : null)} labelFormatter={(label) => `Ngày ${label}`} />
                  <Legend /><ReferenceLine y={0} stroke="hsl(var(--border))" />
                  <Bar dataKey="buyValue" name="Mua" fill="hsl(var(--success))" />
                  <Bar dataKey="sellValue" name="Bán" fill="hsl(var(--danger))" />
                  <Bar dataKey="netValue" name="Ròng">{rows.map((row) => <Cell key={row.tradingDate} fill={foreignFlowSignChartColor(row.netValue)} />)}</Bar>
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="rounded-xl border border-border/70 bg-card p-4" aria-labelledby="proprietary-eod-history-title">
            <h3 id="proprietary-eod-history-title" className="text-sm font-semibold">Chi tiết phiên đã hoàn tất</h3>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-[860px] text-sm">
                <thead><tr className="text-secondary-text"><th className="p-2 text-left">Ngày</th><th className="p-2 text-right">Mua</th><th className="p-2 text-right">Bán</th><th className="p-2 text-right">Ròng</th><th className="p-2 text-right">KL mua</th><th className="p-2 text-right">KL bán</th><th className="p-2 text-right">KL ròng</th><th className="p-2 text-left">Nguồn</th><th className="p-2 text-left">Trạng thái</th></tr></thead>
                <tbody>{rows.map((row) => (
                  <tr key={`${row.exchange}:${row.tradingDate}`} className="border-t border-border/60">
                    <td className="p-2">{row.tradingDate}</td>
                    <td className="p-2 text-right"><ValueCell value={row.buyValue} /></td>
                    <td className="p-2 text-right"><ValueCell value={row.sellValue} /></td>
                    <td className={`p-2 text-right ${foreignFlowSignTextClass(row.netValue)}`}><ValueCell value={row.netValue} /></td>
                    <td className="p-2 text-right"><ValueCell value={row.buyVolume} kind="volume" /></td>
                    <td className="p-2 text-right"><ValueCell value={row.sellVolume} kind="volume" /></td>
                    <td className="p-2 text-right"><ValueCell value={row.netVolume} kind="volume" /></td>
                    <td className="p-2">{safeSourceUrl(row.sourceUrl) ? <a className="text-cyan underline" href={safeSourceUrl(row.sourceUrl) ?? undefined} target="_blank" rel="noopener noreferrer">{row.sourceTitle || row.sourceFileName || 'HOSE'}</a> : row.sourceTitle || 'HOSE'}</td>
                    <td className="p-2">{statusLabel(row)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
};
