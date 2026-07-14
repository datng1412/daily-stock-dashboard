import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  const series: Array<ReturnType<typeof makeSeries>> = [];
  function makeSeries() {
    return {
      setData: vi.fn(), applyOptions: vi.fn(), createPriceLine: vi.fn(), attachPrimitive: vi.fn(), detachPrimitive: vi.fn(),
      priceToCoordinate: vi.fn((price: number) => price / 1_000),
    };
  }
  const timeScale = {
    subscribeVisibleLogicalRangeChange: vi.fn(), unsubscribeVisibleLogicalRangeChange: vi.fn(),
    setVisibleLogicalRange: vi.fn(), fitContent: vi.fn(),
  };
  const chart = {
    addSeries: vi.fn((...args: unknown[]) => { void args; const value = makeSeries(); series.push(value); return value; }),
    panes: vi.fn(() => [{ setStretchFactor: vi.fn() }, { setStretchFactor: vi.fn() }, { setStretchFactor: vi.fn() }]),
    subscribeCrosshairMove: vi.fn(), unsubscribeCrosshairMove: vi.fn(), timeScale: vi.fn(() => timeScale),
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })), remove: vi.fn(),
  };
  return { series, timeScale, chart, createChart: vi.fn(() => chart) };
});

vi.mock('lightweight-charts', () => ({
  createChart: mocks.createChart,
  CandlestickSeries: { type: 'Candlestick' }, HistogramSeries: { type: 'Histogram' }, LineSeries: { type: 'Line' },
  ColorType: { Solid: 'solid' }, CrosshairMode: { Normal: 0 }, LineStyle: { Dashed: 2 },
}));

import { VietnamLightweightChart } from '../VietnamLightweightChart';

const points = [{
  date: '2026-07-13', open: 70_000, high: 72_000, low: 69_000, close: 71_000, volume: 1_000,
  ma20: 70_500, ma50: 69_500, volumeMa20: 900, volumeMa50: 800, rsi14: 55,
  bbUpper: 75_000, bbMid: 70_000, bbLower: 65_000,
}];

describe('VietnamLightweightChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.series.length = 0;
  });

  it('creates one chart with native price, volume, and RSI panes and applies data', () => {
    const { unmount } = render(
      <VietnamLightweightChart ticker="FPT" points={points} shortTermZones={[]} showMA20 showMA50 showBollinger={false} showShortTermZones={false} />,
    );
    expect(mocks.createChart).toHaveBeenCalledTimes(1);
    expect(mocks.chart.addSeries).toHaveBeenCalledTimes(10);
    expect(mocks.chart.addSeries.mock.calls[0][2]).toBe(0);
    expect(mocks.chart.addSeries.mock.calls[1][2]).toBe(1);
    expect(mocks.chart.addSeries.mock.calls[4][2]).toBe(2);
    expect(mocks.series[0].setData).toHaveBeenCalledWith([expect.objectContaining({ close: 71_000 })]);
    expect(mocks.series[1].setData).toHaveBeenCalledWith([expect.objectContaining({ value: 1_000 })]);
    expect(mocks.chart.subscribeCrosshairMove).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('link', { name: 'TradingView' })).toHaveAttribute('href', 'https://www.tradingview.com/');
    unmount();
    expect(mocks.chart.unsubscribeCrosshairMove).toHaveBeenCalledTimes(1);
    expect(mocks.timeScale.unsubscribeVisibleLogicalRangeChange).toHaveBeenCalledTimes(1);
    expect(mocks.chart.remove).toHaveBeenCalledTimes(1);
  });

  it('updates ticker data and visibility without recreating the chart', () => {
    const { rerender } = render(
      <VietnamLightweightChart ticker="FPT" points={points} shortTermZones={[]} showMA20 showMA50 showBollinger={false} showShortTermZones={false} />,
    );
    rerender(
      <VietnamLightweightChart ticker="HPG" points={[{ ...points[0], close: 72_000 }]} shortTermZones={[]} showMA20={false} showMA50 showBollinger showShortTermZones={false} />,
    );
    expect(mocks.createChart).toHaveBeenCalledTimes(1);
    expect(mocks.series[0].setData).toHaveBeenLastCalledWith([expect.objectContaining({ close: 72_000 })]);
    expect(mocks.series[5].applyOptions).toHaveBeenLastCalledWith({ visible: false });
    expect(mocks.series[7].applyOptions).toHaveBeenLastCalledWith({ visible: true });
  });

  it('renders a safe unavailable overlay without fake bars', () => {
    render(
      <VietnamLightweightChart ticker="FPT" points={[]} shortTermZones={[]} showMA20 showMA50 showBollinger={false} showShortTermZones={false} unavailable />,
    );
    expect(screen.getByText('SSI daily chart data unavailable.')).toBeInTheDocument();
    expect(mocks.series[0].setData).toHaveBeenCalledWith([]);
  });
});
