import { Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatCompactShareVolume, formatCompactVndValue } from '../../utils/vietnamNumberFormat';
import { foreignFlowSignChartColor } from '../../utils/foreignFlowSign';
import type { SymbolForeignFlowMetricRow, SymbolForeignFlowMetric } from './foreignFlowSymbolAnalyticsModel';

export type SymbolForeignFlowChartMode = 'net' | 'buy-sell' | 'cumulative' | 'rolling';

export const ForeignFlowSymbolHistoryChart = ({ rows, metric, mode }: {
  rows: SymbolForeignFlowMetricRow[];
  metric: SymbolForeignFlowMetric;
  mode: SymbolForeignFlowChartMode;
}) => {
  const format = metric === 'value' ? formatCompactVndValue : formatCompactShareVolume;
  return (
    <section aria-labelledby="symbol-flow-chart-heading">
      <h3 id="symbol-flow-chart-heading" className="text-sm font-semibold text-foreground">Lịch sử theo phiên</h3>
      <p className="mt-1 text-xs text-secondary-text">Khoảng trống thể hiện trường dữ liệu không có; không được thay bằng 0.</p>
      {rows.length ? <div className="mt-3 h-72 min-w-0" role="img" aria-label={`Biểu đồ dòng tiền ngoại ${mode}, ${rows.length} phiên`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
            <XAxis dataKey="tradingDate" tickFormatter={(value: string) => value.slice(5)} tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(value: number) => format(value, '—', true)} tick={{ fontSize: 11 }} width={76} />
            <Tooltip formatter={(value) => format(typeof value === 'number' ? value : null, 'Không có', true)} labelFormatter={(label) => `Ngày ${label}`} />
            <Legend /><ReferenceLine y={0} stroke="hsl(var(--border))" />
            {mode === 'net' ? <Bar dataKey="net" name="Ròng">{rows.map((row) => <Cell key={row.tradingDate} fill={foreignFlowSignChartColor(row.net)} />)}</Bar> : null}
            {mode === 'buy-sell' ? <><Bar dataKey="buy" name="Mua" fill="hsl(var(--success))" /><Bar dataKey="sell" name="Bán" fill="hsl(var(--danger))" /></> : null}
            {mode === 'cumulative' ? <Line dataKey="cumulative" name="Lũy kế ròng" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} connectNulls={false} /> : null}
            {mode === 'rolling' ? <><Line dataKey="rolling5" name="Ròng 5P" stroke="hsl(var(--cyan))" strokeWidth={2} dot={false} connectNulls={false} /><Line dataKey="rolling20" name="Ròng 20P" stroke="hsl(var(--warning))" strokeWidth={2} dot={false} connectNulls={false} /></> : null}
          </ComposedChart>
        </ResponsiveContainer>
      </div> : <p className="mt-3 text-sm text-secondary-text">Không có dữ liệu để vẽ biểu đồ.</p>}
    </section>
  );
};
