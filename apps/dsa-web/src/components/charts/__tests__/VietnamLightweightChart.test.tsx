import { StrictMode } from 'react';
import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  const series: Array<ReturnType<typeof makeSeries>> = [];
  function makeSeries() {
    return {
      setData: vi.fn(), applyOptions: vi.fn(), createPriceLine: vi.fn(), attachPrimitive: vi.fn(), detachPrimitive: vi.fn(),
      priceToCoordinate: vi.fn((price: number) => price / 1_000),
    };
  }
  const panes = [
    { setStretchFactor: vi.fn() },
    { setStretchFactor: vi.fn() },
    { setStretchFactor: vi.fn() },
  ];
  const timeScale = {
    subscribeVisibleLogicalRangeChange: vi.fn(), unsubscribeVisibleLogicalRangeChange: vi.fn(),
    setVisibleLogicalRange: vi.fn(), fitContent: vi.fn(),
  };
  const chart = {
    addSeries: vi.fn((...args: unknown[]) => { void args; const value = makeSeries(); series.push(value); return value; }),
    panes: vi.fn(() => panes),
    subscribeCrosshairMove: vi.fn(), unsubscribeCrosshairMove: vi.fn(), timeScale: vi.fn(() => timeScale),
    remove: vi.fn(),
  };
  return { series, panes, timeScale, chart, createChart: vi.fn(() => chart) };
});

vi.mock('lightweight-charts', () => ({
  createChart: mocks.createChart,
  CandlestickSeries: { type: 'Candlestick' }, HistogramSeries: { type: 'Histogram' }, LineSeries: { type: 'Line' },
  ColorType: { Solid: 'solid' }, CrosshairMode: { Normal: 0 }, LineStyle: { Dashed: 2 },
}));

import {
  VietnamLightweightChart,
  VN_CHART_COMPACT_PANE_STRETCH,
  VN_CHART_EXPANDED_PANE_STRETCH,
  VN_CHART_PRICE_SCALE_MIN_WIDTH,
} from '../VietnamLightweightChart';
import type { ShortTermChartZone } from '../lightweightChartData';

const points = [{
  date: '2026-07-13', open: 70_000, high: 72_000, low: 69_000, close: 71_000, volume: 1_000,
  ma20: 70_500, ma50: 69_500, volumeMa20: 900, volumeMa50: 800, rsi14: 55,
  bbUpper: 75_000, bbMid: 70_000, bbLower: 65_000,
}];

const zones: ShortTermChartZone[] = [{
  label: 'S1', lower: 69_000, upper: 69_800, midpoint: 69_400,
  kind: 'support', primary: true, formattedRange: '69.00–69.80',
}];

const baseProps = {
  ticker: 'FPT',
  points,
  shortTermZones: zones,
  showMA20: true,
  showMA50: true,
  showBollinger: false,
  showShortTermZones: false,
};

describe('VietnamLightweightChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.series.length = 0;
  });

  it('creates one auto-sized chart with stable price, volume, and RSI panes and cleans it up', () => {
    const { unmount } = render(<VietnamLightweightChart {...baseProps} />);

    expect(mocks.createChart).toHaveBeenCalledTimes(1);
    expect(mocks.createChart).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        autoSize: true,
        rightPriceScale: expect.objectContaining({ minimumWidth: VN_CHART_PRICE_SCALE_MIN_WIDTH }),
        layout: expect.objectContaining({ attributionLogo: true }),
      }),
    );
    expect(mocks.chart.addSeries).toHaveBeenCalledTimes(10);
    expect(mocks.chart.addSeries.mock.calls[0][2]).toBe(0);
    expect(mocks.chart.addSeries.mock.calls[1][2]).toBe(1);
    expect(mocks.chart.addSeries.mock.calls[4][2]).toBe(2);
    expect(mocks.panes.map((pane) => pane.setStretchFactor.mock.calls.at(-1)?.[0])).toEqual(
      [...VN_CHART_COMPACT_PANE_STRETCH],
    );
    expect(mocks.series[4].createPriceLine).toHaveBeenCalledWith(expect.objectContaining({ price: 30, title: '30' }));
    expect(mocks.series[4].createPriceLine).toHaveBeenCalledWith(expect.objectContaining({ price: 70, title: '70' }));
    expect(mocks.series[0].setData).toHaveBeenCalledWith([expect.objectContaining({ close: 71_000 })]);
    expect(mocks.series[1].setData).toHaveBeenCalledWith([expect.objectContaining({ value: 1_000 })]);
    expect(mocks.chart.subscribeCrosshairMove).toHaveBeenCalledTimes(1);
    expect(mocks.timeScale.subscribeVisibleLogicalRangeChange).toHaveBeenCalledTimes(1);
    expect(mocks.timeScale.fitContent).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('link', { name: 'TradingView' })).toHaveAttribute('href', 'https://www.tradingview.com/');

    const primitive = mocks.series[0].attachPrimitive.mock.calls[0][0];
    unmount();
    expect(mocks.chart.unsubscribeCrosshairMove).toHaveBeenCalledWith(
      mocks.chart.subscribeCrosshairMove.mock.calls[0][0],
    );
    expect(mocks.timeScale.unsubscribeVisibleLogicalRangeChange).toHaveBeenCalledWith(
      mocks.timeScale.subscribeVisibleLogicalRangeChange.mock.calls[0][0],
    );
    expect(mocks.series[0].detachPrimitive).toHaveBeenCalledWith(primitive);
    expect(primitive.priceAxisViews()).toEqual([]);
    expect(mocks.chart.remove).toHaveBeenCalledTimes(1);
  });

  it('leaves one active chart container under StrictMode and removes each real chart instance once', () => {
    const { unmount } = render(
      <StrictMode><VietnamLightweightChart {...baseProps} /></StrictMode>,
    );

    expect(screen.getAllByLabelText('FPT daily candlestick chart')).toHaveLength(1);
    expect(mocks.createChart).toHaveBeenCalledTimes(2);
    expect(mocks.chart.remove).toHaveBeenCalledTimes(1);
    unmount();
    expect(mocks.chart.remove).toHaveBeenCalledTimes(2);
  });

  it('updates data, visibility, S/R, and pane proportions without recreating or resetting the chart', () => {
    const { rerender } = render(<VietnamLightweightChart {...baseProps} />);
    const initialFitCalls = mocks.timeScale.fitContent.mock.calls.length;
    const initialSetRangeCalls = mocks.timeScale.setVisibleLogicalRange.mock.calls.length;
    const primitive = mocks.series[0].attachPrimitive.mock.calls[0][0];
    const setZonesSpy = vi.spyOn(primitive, 'setZones');

    rerender(
      <VietnamLightweightChart
        {...baseProps}
        showMA20={false}
        showBollinger
        showShortTermZones
        expanded
      />,
    );

    expect(mocks.createChart).toHaveBeenCalledTimes(1);
    expect(mocks.series[5].applyOptions).toHaveBeenLastCalledWith({ visible: false });
    expect(mocks.series[7].applyOptions).toHaveBeenLastCalledWith({ visible: true });
    expect(setZonesSpy).toHaveBeenCalledWith(zones);
    expect(mocks.panes.map((pane) => pane.setStretchFactor.mock.calls.at(-1)?.[0])).toEqual(
      [...VN_CHART_EXPANDED_PANE_STRETCH],
    );
    expect(mocks.timeScale.fitContent).toHaveBeenCalledTimes(initialFitCalls);
    expect(mocks.timeScale.setVisibleLogicalRange).toHaveBeenCalledTimes(initialSetRangeCalls);

    rerender(<VietnamLightweightChart {...baseProps} unavailable />);
    expect(setZonesSpy).toHaveBeenLastCalledWith([]);
  });

  it('restores an owned logical range on mount but deliberately fits after a ticker change', () => {
    const initialLogicalRange = { from: 10, to: 40 };
    const { rerender } = render(
      <VietnamLightweightChart {...baseProps} initialLogicalRange={initialLogicalRange} />,
    );
    expect(mocks.timeScale.setVisibleLogicalRange).toHaveBeenCalledWith(initialLogicalRange);
    expect(mocks.timeScale.fitContent).not.toHaveBeenCalled();

    rerender(
      <VietnamLightweightChart
        {...baseProps}
        ticker="HPG"
        points={[{ ...points[0], close: 72_000 }]}
        initialLogicalRange={initialLogicalRange}
      />,
    );
    expect(mocks.createChart).toHaveBeenCalledTimes(1);
    expect(mocks.series[0].setData).toHaveBeenLastCalledWith([expect.objectContaining({ close: 72_000 })]);
    expect(mocks.timeScale.fitContent).toHaveBeenCalledTimes(1);
  });

  it('renders one contained tooltip, updates its position by ref, and clears stale content', () => {
    const { rerender } = render(<VietnamLightweightChart {...baseProps} />);
    const container = screen.getByLabelText('FPT daily candlestick chart');
    Object.defineProperty(container, 'clientWidth', { configurable: true, value: 500 });
    Object.defineProperty(container, 'clientHeight', { configurable: true, value: 400 });
    const crosshairHandler = mocks.chart.subscribeCrosshairMove.mock.calls[0][0];
    const seriesData = new Map([
      [mocks.series[0], { open: 70_000, high: 72_000, low: 69_000, close: 71_000 }],
      [mocks.series[1], { value: 1_000 }],
    ]);

    act(() => crosshairHandler({ point: { x: 20, y: 30 }, time: { year: 2026, month: 7, day: 13 }, seriesData }));
    const tooltip = screen.getByTestId('lightweight-chart-tooltip');
    expect(tooltip).toHaveTextContent('2026-07-13');
    expect(tooltip).toHaveTextContent('71.00');
    expect(tooltip).toHaveStyle({ left: '34px', top: '44px' });

    act(() => crosshairHandler({ point: { x: 100, y: 80 }, time: { year: 2026, month: 7, day: 13 }, seriesData }));
    expect(screen.getAllByTestId('lightweight-chart-tooltip')).toHaveLength(1);
    expect(tooltip).toHaveStyle({ left: '114px', top: '94px' });

    act(() => crosshairHandler({ point: null, time: null, seriesData: new Map() }));
    expect(screen.queryByTestId('lightweight-chart-tooltip')).not.toBeInTheDocument();

    act(() => crosshairHandler({ point: { x: 20, y: 30 }, time: { year: 2026, month: 7, day: 13 }, seriesData }));
    rerender(<VietnamLightweightChart {...baseProps} ticker="HPG" loading />);
    expect(screen.queryByTestId('lightweight-chart-tooltip')).not.toBeInTheDocument();
  });

  it('ignores late callbacks after unmount and unsubscribes the range handler', () => {
    const onLogicalRangeChange = vi.fn();
    const { unmount } = render(
      <VietnamLightweightChart {...baseProps} onLogicalRangeChange={onLogicalRangeChange} />,
    );
    const rangeHandler = mocks.timeScale.subscribeVisibleLogicalRangeChange.mock.calls[0][0];
    const crosshairHandler = mocks.chart.subscribeCrosshairMove.mock.calls[0][0];
    act(() => rangeHandler({ from: 1, to: 20 }));
    expect(onLogicalRangeChange).toHaveBeenCalledWith({ from: 1, to: 20 });

    unmount();
    act(() => {
      rangeHandler({ from: 2, to: 21 });
      crosshairHandler({ point: null, time: null, seriesData: new Map() });
    });
    expect(onLogicalRangeChange).toHaveBeenCalledTimes(1);
  });

  it('renders a safe unavailable overlay without fake bars', () => {
    render(<VietnamLightweightChart {...baseProps} points={[]} unavailable />);
    expect(screen.getByText('SSI daily chart data unavailable.')).toBeInTheDocument();
    expect(mocks.series[0].setData).toHaveBeenCalledWith([]);
  });
});
