import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { VietnamForeignFlowBatchResponse, VietnamForeignFlowBatchSymbol } from '../../../api/stocks';
import { ForeignFlowBreadth } from '../ForeignFlowBreadth';
import { ForeignFlowConcentration } from '../ForeignFlowConcentration';
import { ForeignFlowDivergingBars } from '../ForeignFlowDivergingBars';
import { ForeignFlowSummaryCards } from '../ForeignFlowSummaryCards';
import { ForeignFlowTreemap } from '../ForeignFlowTreemap';
import { buildForeignFlowWorkspaceViewModel } from '../foreignFlowViewModel';

const row = (ticker: string, value: number | null, overrides: Partial<VietnamForeignFlowBatchSymbol> = {}): VietnamForeignFlowBatchSymbol => ({
  ticker,
  dataState: 'ready',
  freshness: 'fresh',
  latestTradingDate: '2026-07-17',
  foreignBuyVolume: 100,
  foreignSellVolume: 40,
  foreignNetVolume: value,
  foreignBuyValue: 1_000,
  foreignSellValue: 400,
  foreignNetValue: value,
  foreignNetVolume5d: value,
  foreignNetValue5d: value,
  foreignNetVolume20d: value,
  foreignNetValue20d: value,
  coveredSessions5d: 5,
  complete5d: true,
  coveredSessions20d: 20,
  complete20d: true,
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: 'shares',
  valueUnit: 'VND',
  finality: 'daily_available',
  fetchedAt: '2026-07-17T08:00:00Z',
  ...overrides,
});

const workspace = buildForeignFlowWorkspaceViewModel([
  row('AAA', 100),
  row('BBB', -50, { coveredSessions5d: 3, complete5d: false }),
  row('ZERO', 0),
  row('NONE', null),
], '5', 'value');

const response = (rows: VietnamForeignFlowBatchSymbol[]): VietnamForeignFlowBatchResponse => ({
  source: 'ssi_fastconnect',
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: 'shares',
  valueUnit: 'VND',
  finality: 'daily_available',
  requestedTickers: rows.map((item) => item.ticker),
  normalizedTickers: rows.map((item) => item.ticker),
  requestedCount: rows.length,
  normalizedCount: rows.length,
  returnedCount: rows.length,
  usableCount: rows.length,
  freshCount: rows.length,
  staleCount: 0,
  emptyCount: 0,
  unavailableCount: 0,
  coverageRatio: rows.length ? 1 : 0,
  complete: true,
  dataState: 'ready',
  rows,
  rankings: {
    latestNetValue: { topBuy: [], topSell: [] },
    netValue5d: { topBuy: [], topSell: [] },
    netValue20d: { topBuy: [], topSell: [] },
  },
  fetchedAt: '2026-07-17T08:00:00Z',
});

describe('foreign-flow visualization components', () => {
  it('shows all six latest value/volume metrics and only cumulative net fields for 5 sessions', () => {
    const data = response([row('AAA', 100), row('BBB', -50)]);
    const { rerender } = render(<ForeignFlowSummaryCards data={data} window="today" metric="value" />);

    expect(screen.getByText('Tổng mua')).toBeInTheDocument();
    expect(screen.getByText('Tổng bán')).toBeInTheDocument();
    expect(screen.getByText('Mua bán ròng')).toBeInTheDocument();
    expect(screen.getAllByText('Giá trị')).toHaveLength(3);
    expect(screen.getAllByText('Khối lượng')).toHaveLength(3);
    expect(screen.getByText('2K')).toBeInTheDocument();
    expect(screen.getByText('800')).toBeInTheDocument();

    rerender(<ForeignFlowSummaryCards data={data} window="5" metric="volume" />);
    expect(screen.getByText('Mua bán ròng 5 phiên · Giá trị')).toBeInTheDocument();
    expect(screen.getByText('Mua bán ròng 5 phiên · Khối lượng')).toBeInTheDocument();
    expect(screen.queryByText('Tổng mua')).not.toBeInTheDocument();
    expect(screen.queryByText('Tổng bán')).not.toBeInTheDocument();
  });

  it('renders breadth counts with a color-independent accessible summary', () => {
    render(<ForeignFlowBreadth breadth={workspace.breadth} window="5" metric="value" />);

    expect(screen.getByRole('img', { name: '1 mã mua ròng, 1 mã bán ròng, 1 mã trung tính, 1 mã không có dữ liệu' })).toBeInTheDocument();
    expect(screen.getByText('3/4 mã có dữ liệu')).toBeInTheDocument();
    expect(screen.getByText(/Chưa đủ phiên 1 mã/)).toBeInTheDocument();
  });

  it('renders absolute-flow concentration and an honest zero-data state', () => {
    const { rerender } = render(<ForeignFlowConcentration concentration={workspace.concentration} window="5" metric="value" />);

    expect(screen.getByText('66.7%')).toBeInTheDocument();
    expect(screen.getAllByText('100.0%')).toHaveLength(2);
    expect(screen.getByText(/Tổng độ lớn 150/)).toBeInTheDocument();

    const empty = buildForeignFlowWorkspaceViewModel([row('ZERO', 0)], 'today', 'value');
    rerender(<ForeignFlowConcentration concentration={empty.concentration} window="today" metric="value" />);
    expect(screen.getByText('Chưa đủ dữ liệu để tính mức độ tập trung.')).toBeInTheDocument();
  });

  it('renders focusable treemap cells with sign, completeness, and keyboard selection', () => {
    const onSelectTicker = vi.fn();
    render(
      <ForeignFlowTreemap
        items={workspace.treemapItems}
        window="5"
        metric="value"
        selectedTicker={null}
        onSelectTicker={onSelectTicker}
      />,
    );

    expect(screen.getByRole('group', { name: /Bản đồ 2 mã trong watchlist, 5 phiên, giá trị/ })).toBeInTheDocument();
    const buyCell = screen.getByRole('button', { name: /AAA, mua ròng.*5 phiên.*đầy đủ/ });
    const sellCell = screen.getByRole('button', { name: /BBB, bán ròng.*3\/5 phiên, chưa đầy đủ/ });
    expect(buyCell).toHaveAttribute('tabindex', '0');
    fireEvent.keyDown(sellCell, { key: 'Enter' });
    expect(onSelectTicker).toHaveBeenCalledWith('BBB');
  });

  it('renders an honest treemap empty state without an empty SVG', () => {
    render(<ForeignFlowTreemap items={[]} window="today" metric="volume" selectedTicker={null} onSelectTicker={vi.fn()} />);

    expect(screen.getByText(/Chưa có dữ liệu mua bán ròng để hiển thị bản đồ/)).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: /Bản đồ/ })).not.toBeInTheDocument();
  });

  it('uses one shared magnitude scale for buyers and sellers and keeps one-sided states compact', () => {
    const { rerender } = render(
      <MemoryRouter>
        <ForeignFlowDivergingBars buyers={workspace.buyers} sellers={workspace.sellers} window="5" metric="value" />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('foreign-flow-buy-bar-AAA')).toHaveStyle({ width: '100%' });
    expect(screen.getByTestId('foreign-flow-sell-bar-BBB')).toHaveStyle({ width: '50%' });
    expect(screen.getByLabelText(/BBB.*Chưa đủ phiên/)).toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <ForeignFlowDivergingBars buyers={workspace.buyers} sellers={[]} window="5" metric="value" />
      </MemoryRouter>,
    );
    expect(screen.getByText('Chưa có mã bán ròng đủ dữ liệu.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'AAA' })).toBeInTheDocument();
  });
});
