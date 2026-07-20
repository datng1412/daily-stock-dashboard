import { RefreshCw, X } from 'lucide-react';
import type { VietnamForeignFlowSymbolHistoryResponse } from '../../api/stocks';
import { Button } from '../common';
import { cn } from '../../utils/cn';
import { formatCompactShareVolume, formatCompactVndValue } from '../../utils/vietnamNumberFormat';
import { foreignFlowSignTextClass } from '../../utils/foreignFlowSign';
import { buildSymbolForeignFlowRows, type SymbolForeignFlowMetric, type SymbolForeignFlowRange } from './foreignFlowSymbolAnalyticsModel';
import { ForeignFlowSymbolHistoryChart, type SymbolForeignFlowChartMode } from './ForeignFlowSymbolHistoryChart';
import { ForeignFlowSymbolHistoryTable } from './ForeignFlowSymbolHistoryTable';

export type SymbolForeignFlowWindow = 'latest' | '5' | '20' | '60';

const formatMetric = (value: number | null | undefined, metric: SymbolForeignFlowMetric, signed = false) => metric === 'value'
  ? formatCompactVndValue(value, '—', signed)
  : formatCompactShareVolume(value, '—', signed);

export const ForeignFlowSymbolAnalyticsPanel = ({ ticker, data, loading, updating, error, metric, range, mode, window, onMetricChange, onRangeChange, onModeChange, onWindowChange, onRetry, onForceRefresh, onClose }: {
  ticker: string;
  data: VietnamForeignFlowSymbolHistoryResponse | null;
  loading: boolean;
  updating: boolean;
  error: string | null;
  metric: SymbolForeignFlowMetric;
  range: SymbolForeignFlowRange;
  mode: SymbolForeignFlowChartMode;
  window: SymbolForeignFlowWindow;
  onMetricChange: (value: SymbolForeignFlowMetric) => void;
  onRangeChange: (value: SymbolForeignFlowRange) => void;
  onModeChange: (value: SymbolForeignFlowChartMode) => void;
  onWindowChange: (value: SymbolForeignFlowWindow) => void;
  onRetry: () => void;
  onForceRefresh: () => void;
  onClose: () => void;
}) => {
  const analytics = data?.analytics ?? null;
  const family = analytics?.[metric] ?? null;
  const rows = buildSymbolForeignFlowRows(data?.rows ?? [], analytics, metric, range);
  const latest = data?.latestRow ?? null;
  const selectedWindow = window === 'latest' ? null : family?.windows[window] ?? null;
  const contextWindow = selectedWindow ?? family?.windows['60'] ?? null;
  const format = (value: number | null | undefined, signed = false) => formatMetric(value, metric, signed);
  const card = (label: string, value: string, detail?: string, signedValue?: number | null) => <div className="rounded-lg border border-border/70 bg-elevated/30 p-3"><dt className="text-xs text-secondary-text">{label}</dt><dd className={cn('mt-1 font-semibold tabular-nums', signedValue === undefined ? 'text-foreground' : foreignFlowSignTextClass(signedValue))}>{value}</dd>{detail ? <p className="mt-1 text-xs text-secondary-text">{detail}</p> : null}</div>;
  return <section className="rounded-lg border border-cyan/30 bg-card p-4" aria-labelledby="symbol-analytics-heading">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 id="symbol-analytics-heading" className="text-base font-semibold text-foreground">Phân tích dòng tiền ngoại · {ticker}</h2><p className="mt-1 text-xs text-secondary-text">SSI DailyStockPrice · dữ liệu theo phiên · {data?.coverage.coveredSessions ?? 0}/60 phiên quan sát{data?.freshness === 'stale' ? ' · dữ liệu cũ' : ''}</p></div>
      <div className="flex gap-2"><Button size="sm" variant="outline" onClick={onForceRefresh} disabled={loading}><RefreshCw className="h-4 w-4" /> {updating ? 'Đang cập nhật' : 'Làm mới'}</Button><Button size="sm" variant="ghost" onClick={onClose} aria-label="Đóng phân tích chi tiết"><X className="h-4 w-4" /></Button></div>
    </div>
    <div className="mt-4 flex flex-wrap gap-2">
      <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Đơn vị phân tích mã">{(['value', 'volume'] as const).map((value) => <button key={value} type="button" aria-pressed={metric === value} onClick={() => onMetricChange(value)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${metric === value ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}>{value === 'value' ? 'Giá trị' : 'Khối lượng'}</button>)}</div>
      <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Cửa sổ tóm tắt mã">{(['latest', '5', '20', '60'] as const).map((value) => <button key={value} type="button" aria-pressed={window === value} onClick={() => onWindowChange(value)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${window === value ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}>{value === 'latest' ? 'Phiên gần nhất' : `${value} phiên`}</button>)}</div>
      <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Chế độ biểu đồ mã">{(['net', 'buy-sell', 'cumulative', 'rolling'] as const).map((value) => <button key={value} type="button" aria-pressed={mode === value} onClick={() => onModeChange(value)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${mode === value ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}>{value === 'net' ? 'Ròng' : value === 'buy-sell' ? 'Mua / bán' : value === 'cumulative' ? 'Lũy kế' : 'Rolling'}</button>)}</div>
      <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Khoảng lịch sử mã">{([20, 40, 60] as const).map((value) => <button key={value} type="button" aria-pressed={range === value} onClick={() => onRangeChange(value)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${range === value ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}>{value} phiên</button>)}</div>
    </div>
    {loading && !data ? <p className="mt-5 text-sm text-secondary-text" role="status">Đang tải lịch sử dòng tiền ngoại · {ticker}</p> : null}
    {error && !data ? <div className="mt-5 rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">Không thể tải lịch sử dòng tiền ngoại cho {ticker}.<div className="mt-3"><Button variant="outline" size="sm" onClick={onRetry}>Thử lại</Button></div></div> : null}
    {error && data ? <p className="mt-4 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-warning" role="status">Cập nhật chưa khả dụng; đang giữ dữ liệu gần nhất của {ticker}.</p> : null}
    {data?.dataState === 'empty' ? <p className="mt-5 rounded-lg border border-border/70 p-4 text-sm text-secondary-text">Không có dữ liệu dòng tiền ngoại trong phạm vi quan sát.</p> : null}
    {data?.dataState === 'unavailable' ? <div className="mt-5 rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">Không thể tải lịch sử dòng tiền ngoại cho {ticker}.<div className="mt-3"><Button variant="outline" size="sm" onClick={onRetry}>Thử lại</Button></div></div> : null}
    {data && data.dataState !== 'empty' && data.dataState !== 'unavailable' && family ? <div className="mt-5 space-y-5">
      {window === 'latest' ? <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {card('Giá trị mua', formatMetric(latest?.foreignBuyValue, 'value'), latest?.tradingDate)}
        {card('Giá trị bán', formatMetric(latest?.foreignSellValue, 'value'), latest?.tradingDate)}
        {card('Giá trị ròng', formatMetric(latest?.foreignNetValue, 'value', true), latest?.tradingDate, latest?.foreignNetValue)}
        {card('Khối lượng mua', formatMetric(latest?.foreignBuyVolume, 'volume'), latest?.tradingDate)}
        {card('Khối lượng bán', formatMetric(latest?.foreignSellVolume, 'volume'), latest?.tradingDate)}
        {card('Khối lượng ròng', formatMetric(latest?.foreignNetVolume, 'volume', true), latest?.tradingDate, latest?.foreignNetVolume)}
      </dl> : selectedWindow ? <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {card(`Ròng ${window} phiên`, format(selectedWindow.netSum, true), `${selectedWindow.coveredSessions}/${selectedWindow.requestedSessions} phiên · ${selectedWindow.complete ? 'đủ' : 'chưa đủ'}`, selectedWindow.netSum)}
        {card('Bình quân ròng', format(selectedWindow.averageNet, true), `${selectedWindow.startDate ?? '—'} → ${selectedWindow.endDate ?? '—'}`, selectedWindow.averageNet)}
        {card('Bình quân độ lớn', format(selectedWindow.averageAbsoluteNet), 'Giá trị tuyệt đối')}
        {card('Phân bố phiên', `${selectedWindow.netBuySessionCount} mua · ${selectedWindow.netSellSessionCount} bán`, `${selectedWindow.zeroSessionCount} trung tính · ${selectedWindow.unavailableSessionCount} thiếu`) }
      </dl> : null}
      <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {card('Chuỗi hiện tại', family.currentStreak.direction === 'net_buy' ? `Mua ròng ${family.currentStreak.sessions} phiên` : family.currentStreak.direction === 'net_sell' ? `Bán ròng ${family.currentStreak.sessions} phiên` : family.currentStreak.direction === 'none' ? 'Phiên gần nhất trung tính' : 'Không đủ dữ liệu chuỗi', `${family.currentStreak.startDate ?? '—'} → ${family.currentStreak.endDate ?? '—'}`)}
        {card('Đảo chiều gần nhất', family.latestReversal ? `${family.latestReversal.fromDirection === 'net_buy' ? 'Mua' : 'Bán'} → ${family.latestReversal.toDirection === 'net_buy' ? 'Mua' : 'Bán'}` : 'Chưa ghi nhận', family.latestReversal?.tradingDate ?? 'Trong phạm vi dữ liệu')}
        {card('Độ lớn gần nhất', family.comparison.unusualFlowState === 'elevated' ? 'Cao so với phạm vi quan sát' : family.comparison.unusualFlowState === 'normal' ? 'Trong phạm vi bình thường' : 'Chưa đủ dữ liệu so sánh', family.comparison.absolutePercentile60d == null ? undefined : `Percentile ${family.comparison.absolutePercentile60d.toFixed(0)} / 60 phiên`)}
        {card('Bao phủ', `${analytics?.observedSessions ?? 0}/60 phiên`, `${data.coverage.startDate ?? '—'} → ${data.coverage.endDate ?? '—'}`)}
        {card('Phân bố phiên', contextWindow ? `${contextWindow.netBuySessionCount} mua · ${contextWindow.netSellSessionCount} bán` : '—', contextWindow ? `${contextWindow.zeroSessionCount} trung tính · ${contextWindow.unavailableSessionCount} thiếu` : undefined)}
        {card('Phiên mua ròng lớn nhất', contextWindow?.maxNetBuy ? format(contextWindow.maxNetBuy.value, true) : '—', contextWindow?.maxNetBuy?.tradingDate, contextWindow?.maxNetBuy?.value)}
        {card('Phiên bán ròng lớn nhất', contextWindow?.maxNetSell ? format(contextWindow.maxNetSell.value, true) : '—', contextWindow?.maxNetSell?.tradingDate, contextWindow?.maxNetSell?.value)}
      </dl>
      <ForeignFlowSymbolHistoryChart rows={rows} metric={metric} mode={mode} />
      <ForeignFlowSymbolHistoryTable rows={rows} metric={metric} />
    </div> : null}
  </section>;
};
