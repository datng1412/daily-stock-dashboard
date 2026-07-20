import type { ReactNode } from 'react';
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { VietnamVn30ForeignFlowDaily } from '../../../api/stocks';
import { Vn30ForeignFlowHistoryChart } from '../Vn30ForeignFlowHistoryChart';

vi.mock('recharts', () => {
  const Container = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return {
    ResponsiveContainer: Container,
    ComposedChart: Container,
    Bar: ({ children, dataKey }: { children?: ReactNode; dataKey: string }) => <div data-testid={`bar-${dataKey}`}>{children}</div>,
    Cell: ({ fill }: { fill: string }) => <span data-testid="chart-cell" data-fill={fill} />,
    CartesianGrid: () => null,
    Legend: () => null,
    Line: () => null,
    ReferenceLine: () => null,
    Tooltip: () => null,
    XAxis: () => null,
    YAxis: () => null,
  };
});

const daily = (tradingDate: string, net: number | null): VietnamVn30ForeignFlowDaily => ({
  tradingDate,
  foreignBuyVolume: 100,
  foreignSellVolume: 50,
  foreignNetVolume: net,
  foreignBuyValue: 1_000,
  foreignSellValue: 500,
  foreignNetValue: net,
  volumeCoverageCount: net === null ? 0 : 1,
  volumeCoverageRatio: net === null ? 0 : 1,
  valueCoverageCount: net === null ? 0 : 1,
  valueCoverageRatio: net === null ? 0 : 1,
  volumeCoverage: { coveredComponents: net === null ? 0 : 1, expectedComponents: 1, coverageRatio: net === null ? 0 : 1, complete: net !== null },
  valueCoverage: { coveredComponents: net === null ? 0 : 1, expectedComponents: 1, coverageRatio: net === null ? 0 : 1, complete: net !== null },
  volumeBreadth: { netBuyCount: net !== null && net > 0 ? 1 : 0, netSellCount: net !== null && net < 0 ? 1 : 0, zeroCount: net === 0 ? 1 : 0, unavailableCount: net === null ? 1 : 0 },
  valueBreadth: { netBuyCount: net !== null && net > 0 ? 1 : 0, netSellCount: net !== null && net < 0 ? 1 : 0, zeroCount: net === 0 ? 1 : 0, unavailableCount: net === null ? 1 : 0 },
  positiveComponents: net !== null && net > 0 ? 1 : 0,
  negativeComponents: net !== null && net < 0 ? 1 : 0,
  zeroComponents: net === 0 ? 1 : 0,
  missingComponents: net === null ? 1 : 0,
  dataState: net === null ? 'unavailable' : 'ready',
  state: net === null ? 'unavailable' : 'ready',
});

describe('Vn30ForeignFlowHistoryChart', () => {
  it('colors signed net bars green/red while keeping zero neutral and null unavailable', () => {
    render(
      <Vn30ForeignFlowHistoryChart
        series={[daily('2026-07-14', 10), daily('2026-07-15', -5), daily('2026-07-16', 0), daily('2026-07-17', null)]}
        metric="value"
        mode="net"
        range="5"
        onModeChange={vi.fn()}
        onRangeChange={vi.fn()}
      />,
    );

    const cells = within(screen.getByTestId('bar-net')).getAllByTestId('chart-cell');
    expect(cells.map((cell) => cell.getAttribute('data-fill'))).toEqual([
      'hsl(var(--success))',
      'hsl(var(--danger))',
      'hsl(var(--foreground))',
      'hsl(var(--secondary-text))',
    ]);
  });
});
