import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { VietnamVn30ForeignFlowDaily } from '../../api/stocks';
import { formatForeignFlowValue, formatForeignFlowVolume } from '../../utils/vietnamNumberFormat';
import { foreignFlowSignChartColor } from '../../utils/foreignFlowSign';
import type { ForeignFlowMetric } from './foreignFlowViewModel';

export type Vn30ForeignFlowChartMode = 'net' | 'buy-sell' | 'cumulative' | 'breadth';
export type Vn30ForeignFlowChartRange = '5' | '10' | '20';

export const Vn30ForeignFlowHistoryChart = ({
  series,
  metric,
  mode,
  range,
  onModeChange,
  onRangeChange,
}: {
  series: VietnamVn30ForeignFlowDaily[];
  metric: ForeignFlowMetric;
  mode: Vn30ForeignFlowChartMode;
  range: Vn30ForeignFlowChartRange;
  onModeChange: (mode: Vn30ForeignFlowChartMode) => void;
  onRangeChange: (range: Vn30ForeignFlowChartRange) => void;
}) => {
  const selected = series.slice(-Number(range));
  const suffix = metric === 'value' ? 'Value' : 'Volume';
  const formatter = metric === 'value' ? formatForeignFlowValue : formatForeignFlowVolume;
  const chartRows = selected.map((row, index) => {
    const net = row[`foreignNet${suffix}` as keyof VietnamVn30ForeignFlowDaily] as number | null;
    const cumulativeValues = selected.slice(0, index + 1)
      .map((item) => item[`foreignNet${suffix}` as keyof VietnamVn30ForeignFlowDaily])
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    const breadth = metric === 'value' ? row.valueBreadth : row.volumeBreadth;
    return {
      date: row.tradingDate,
      buy: row[`foreignBuy${suffix}` as keyof VietnamVn30ForeignFlowDaily] as number | null,
      sell: row[`foreignSell${suffix}` as keyof VietnamVn30ForeignFlowDaily] as number | null,
      net,
      cumulative: cumulativeValues.length ? cumulativeValues.reduce((sum, value) => sum + value, 0) : null,
      breadthBuy: breadth.netBuyCount,
      breadthSell: -breadth.netSellCount,
      coverage: metric === 'value' ? row.valueCoverageRatio : row.volumeCoverageRatio,
    };
  });
  const valueFormatter = mode === 'breadth'
    ? (value: number | null) => value === null ? '—' : `${Math.abs(value)} mã`
    : (value: number | null) => formatter(value);
  return (
    <section className="rounded-lg border border-border/70 bg-card p-4" aria-labelledby="vn30-flow-history-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="vn30-flow-history-heading" className="text-base font-semibold text-foreground">Lịch sử dòng tiền VN30</h2>
          <p className="mt-1 text-xs text-secondary-text">Tổng hợp theo thành phần VN30 hiện tại; không phải lịch sử thành phần tại từng ngày.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Chế độ biểu đồ VN30">
            {(['net', 'buy-sell', 'cumulative', 'breadth'] as const).map((option) => <button key={option} type="button" aria-pressed={mode === option} onClick={() => onModeChange(option)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${mode === option ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}>{option === 'net' ? 'Ròng' : option === 'buy-sell' ? 'Mua / bán' : option === 'cumulative' ? 'Lũy kế ròng' : 'Độ rộng'}</button>)}
          </div>
          <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Khoảng biểu đồ VN30">
            {(['5', '10', '20'] as const).map((option) => <button key={option} type="button" aria-pressed={range === option} onClick={() => onRangeChange(option)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${range === option ? 'bg-cyan/15 text-cyan' : 'text-secondary-text'}`}>{option} phiên</button>)}
          </div>
        </div>
      </div>
      {chartRows.length ? (
        <div className="mt-4 h-72 min-w-0" role="img" aria-label={`Biểu đồ ${mode === 'net' ? 'mua bán ròng' : mode === 'buy-sell' ? 'mua và bán' : mode === 'cumulative' ? 'lũy kế ròng' : 'độ rộng'} VN30 ${range} phiên`}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartRows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
              <XAxis dataKey="date" tickFormatter={(value: string) => value.slice(5)} tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(value: number) => valueFormatter(value)} tick={{ fontSize: 11 }} width={76} />
              <Tooltip formatter={(value) => valueFormatter(typeof value === 'number' ? value : null)} labelFormatter={(label) => `Ngày ${label}`} />
              <Legend />
              <ReferenceLine y={0} stroke="hsl(var(--border))" />
              {mode === 'net' ? (
                <Bar dataKey="net" name="Mua bán ròng">
                  {chartRows.map((row) => <Cell key={row.date} fill={foreignFlowSignChartColor(row.net)} />)}
                </Bar>
              ) : mode === 'buy-sell' ? <>
                <Line dataKey="buy" name="Mua" stroke="hsl(var(--success))" strokeWidth={2} dot={false} connectNulls={false} />
                <Line dataKey="sell" name="Bán" stroke="hsl(var(--danger))" strokeWidth={2} dot={false} connectNulls={false} />
              </> : mode === 'cumulative'
                ? <Line dataKey="cumulative" name="Lũy kế ròng" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} connectNulls={false} />
                : <><Bar dataKey="breadthBuy" name="Số mã mua ròng" fill="hsl(var(--success))" /><Bar dataKey="breadthSell" name="Số mã bán ròng" fill="hsl(var(--danger))" /></>}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : <p className="mt-4 rounded-md border border-dashed border-border/60 px-3 py-4 text-sm text-secondary-text">Chưa có chuỗi lịch sử VN30 để vẽ biểu đồ.</p>}
    </section>
  );
};
