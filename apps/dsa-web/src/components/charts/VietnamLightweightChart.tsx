import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type IRange,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts';
import type { VietnamChartPoint } from '../../api/stocks';
import { formatCompactShareVolume } from '../../utils/vietnamNumberFormat';
import {
  formatVietnamChartPrice,
  normalizeLightweightChartData,
  type ShortTermChartZone,
  VN_CHART_PRICE_MIN_MOVE,
} from './lightweightChartData';
import { ShortTermZonesPrimitive } from './ShortTermZonesPrimitive';

type TooltipState = {
  ticker: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  left: number;
  top: number;
};

type SeriesRefs = {
  candles: ISeriesApi<'Candlestick'>;
  volume: ISeriesApi<'Histogram'>;
  volumeMa20: ISeriesApi<'Line'>;
  volumeMa50: ISeriesApi<'Line'>;
  rsi14: ISeriesApi<'Line'>;
  ma20: ISeriesApi<'Line'>;
  ma50: ISeriesApi<'Line'>;
  bbUpper: ISeriesApi<'Line'>;
  bbMid: ISeriesApi<'Line'>;
  bbLower: ISeriesApi<'Line'>;
};

export type VietnamLightweightChartProps = {
  ticker: string;
  points: VietnamChartPoint[];
  shortTermZones: ShortTermChartZone[];
  showMA20: boolean;
  showMA50: boolean;
  showBollinger: boolean;
  showShortTermZones: boolean;
  loading?: boolean;
  unavailable?: boolean;
  expanded?: boolean;
  initialLogicalRange?: IRange<number> | null;
  onLogicalRangeChange?: (range: IRange<number> | null) => void;
};

const businessDayLabel = (time: Time) => {
  if (typeof time === 'object' && 'year' in time) {
    return `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}`;
  }
  return String(time);
};

export const VietnamLightweightChart: React.FC<VietnamLightweightChartProps> = ({
  ticker,
  points,
  shortTermZones,
  showMA20,
  showMA50,
  showBollinger,
  showShortTermZones,
  loading = false,
  unavailable = false,
  expanded = false,
  initialLogicalRange = null,
  onLogicalRangeChange,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<SeriesRefs | null>(null);
  const zonesPrimitiveRef = useRef<ShortTermZonesPrimitive | null>(null);
  const latestRangeHandlerRef = useRef(onLogicalRangeChange);
  const latestTickerRef = useRef(ticker);
  const previousTickerRef = useRef<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const chartData = useMemo(() => normalizeLightweightChartData(points), [points]);

  useEffect(() => { latestRangeHandlerRef.current = onLogicalRangeChange; }, [onLogicalRangeChange]);
  useEffect(() => { latestTickerRef.current = ticker; }, [ticker]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    const chart = createChart(container, {
      autoSize: true,
      height: expanded ? 680 : 520,
      layout: {
        background: { type: ColorType.Solid, color: '#07111d' },
        textColor: '#94a3b8',
        attributionLogo: true,
      },
      grid: {
        vertLines: { color: 'rgba(148,163,184,0.08)' },
        horzLines: { color: 'rgba(148,163,184,0.10)' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: 'rgba(148,163,184,0.28)', minimumWidth: 80 },
      timeScale: {
        borderColor: 'rgba(148,163,184,0.28)',
        timeVisible: false,
        secondsVisible: false,
        lockVisibleTimeRangeOnResize: true,
      },
      localization: { locale: 'en-US', priceFormatter: formatVietnamChartPrice },
      handleScroll: true,
      handleScale: true,
    });
    const priceFormat = { type: 'custom' as const, minMove: VN_CHART_PRICE_MIN_MOVE, formatter: formatVietnamChartPrice };
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e', downColor: '#ef4444', wickUpColor: '#22c55e', wickDownColor: '#ef4444',
      borderUpColor: '#22c55e', borderDownColor: '#ef4444', priceFormat,
    }, 0);
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' }, priceScaleId: 'right', priceLineVisible: false, lastValueVisible: false,
    }, 1);
    const volumeMa20 = chart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 1);
    const volumeMa50 = chart.addSeries(LineSeries, { color: '#f97316', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 1);
    const rsi14 = chart.addSeries(LineSeries, {
      color: '#22c55e', lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
      autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
    }, 2);
    rsi14.createPriceLine({ price: 30, color: '#64748b', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: '30' });
    rsi14.createPriceLine({ price: 70, color: '#64748b', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: '70' });
    const ma20 = chart.addSeries(LineSeries, { color: '#a78bfa', lineWidth: 2, priceFormat, priceLineVisible: false, lastValueVisible: false }, 0);
    const ma50 = chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 2, priceFormat, priceLineVisible: false, lastValueVisible: false }, 0);
    const bbUpper = chart.addSeries(LineSeries, { color: '#64748b', lineWidth: 1, priceFormat, priceLineVisible: false, lastValueVisible: false }, 0);
    const bbMid = chart.addSeries(LineSeries, { color: '#94a3b8', lineWidth: 1, lineStyle: LineStyle.Dashed, priceFormat, priceLineVisible: false, lastValueVisible: false }, 0);
    const bbLower = chart.addSeries(LineSeries, { color: '#64748b', lineWidth: 1, priceFormat, priceLineVisible: false, lastValueVisible: false }, 0);
    const primitive = new ShortTermZonesPrimitive();
    candles.attachPrimitive(primitive);
    const panes = chart.panes();
    panes[0]?.setStretchFactor(3);
    panes[1]?.setStretchFactor(1);
    panes[2]?.setStretchFactor(1);

    const handleCrosshairMove = (param: Parameters<IChartApi['subscribeCrosshairMove']>[0] extends (value: infer P) => void ? P : never) => {
      const candle = param.seriesData.get(candles);
      if (!param.point || !param.time || !candle || !('open' in candle)) {
        setTooltip(null);
        return;
      }
      const volumePoint = param.seriesData.get(volume);
      setTooltip({
        ticker: latestTickerRef.current,
        date: businessDayLabel(param.time), open: candle.open, high: candle.high, low: candle.low, close: candle.close,
        volume: volumePoint && 'value' in volumePoint ? volumePoint.value : undefined,
        left: Math.max(8, Math.min(param.point.x + 14, container.clientWidth - 190)),
        top: Math.max(8, Math.min(param.point.y + 14, container.clientHeight - 150)),
      });
    };
    const handleRange = (range: IRange<number> | null) => latestRangeHandlerRef.current?.(range);
    chart.subscribeCrosshairMove(handleCrosshairMove);
    chart.timeScale().subscribeVisibleLogicalRangeChange(handleRange);
    chartRef.current = chart;
    seriesRef.current = { candles, volume, volumeMa20, volumeMa50, rsi14, ma20, ma50, bbUpper, bbMid, bbLower };
    zonesPrimitiveRef.current = primitive;

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleRange);
      candles.detachPrimitive(primitive);
      primitive.clear();
      zonesPrimitiveRef.current = null;
      seriesRef.current = null;
      chartRef.current = null;
      chart.remove();
    };
  }, [expanded]);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;
    series.candles.setData(chartData.candles);
    series.volume.setData(chartData.volume);
    series.volumeMa20.setData(chartData.volumeMa20);
    series.volumeMa50.setData(chartData.volumeMa50);
    series.rsi14.setData(chartData.rsi14);
    series.ma20.setData(chartData.ma20);
    series.ma50.setData(chartData.ma50);
    series.bbUpper.setData(chartData.bbUpper);
    series.bbMid.setData(chartData.bbMid);
    series.bbLower.setData(chartData.bbLower);
    if (initialLogicalRange) chart.timeScale().setVisibleLogicalRange(initialLogicalRange);
    else if (ticker !== previousTickerRef.current || previousTickerRef.current === null) chart.timeScale().fitContent();
    previousTickerRef.current = ticker;
  }, [chartData, initialLogicalRange, ticker]);

  useEffect(() => { seriesRef.current?.ma20.applyOptions({ visible: showMA20 }); }, [showMA20]);
  useEffect(() => { seriesRef.current?.ma50.applyOptions({ visible: showMA50 }); }, [showMA50]);
  useEffect(() => {
    seriesRef.current?.bbUpper.applyOptions({ visible: showBollinger });
    seriesRef.current?.bbMid.applyOptions({ visible: showBollinger });
    seriesRef.current?.bbLower.applyOptions({ visible: showBollinger });
  }, [showBollinger]);
  useEffect(() => {
    zonesPrimitiveRef.current?.setZones(showShortTermZones ? shortTermZones : []);
    chartRef.current?.priceScale('right', 0).applyOptions({ minimumWidth: showShortTermZones ? 148 : 80 });
  }, [shortTermZones, showShortTermZones]);

  return (
    <div className="relative" data-testid="vietnam-lightweight-chart" data-ticker={ticker}>
      <div
        ref={containerRef}
        className={expanded ? 'h-[min(68vh,760px)] w-full overflow-hidden rounded-lg border border-border/60' : 'h-[540px] w-full overflow-hidden rounded-lg border border-border/60'}
        aria-label={`${ticker} daily candlestick chart`}
      />
      {loading ? <div className="absolute inset-0 grid place-items-center bg-[#07111d]/85 text-sm text-secondary-text">Loading chart data...</div> : null}
      {unavailable ? <div className="absolute inset-0 grid place-items-center bg-[#07111d]/90 text-sm text-secondary-text">SSI daily chart data unavailable.</div> : null}
      {tooltip && tooltip.ticker === ticker && !loading && !unavailable ? (
        <div
          data-testid="lightweight-chart-tooltip"
          className="pointer-events-none absolute z-10 w-[180px] rounded-lg border border-border/70 bg-card/95 p-3 text-xs shadow-soft-card"
          style={{ left: tooltip.left, top: tooltip.top }}
        >
          <p className="font-semibold text-foreground">{tooltip.date}</p>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-secondary-text">
            <dt>Open</dt><dd className="text-right text-foreground">{formatVietnamChartPrice(tooltip.open)}</dd>
            <dt>High</dt><dd className="text-right text-foreground">{formatVietnamChartPrice(tooltip.high)}</dd>
            <dt>Low</dt><dd className="text-right text-foreground">{formatVietnamChartPrice(tooltip.low)}</dd>
            <dt>Close</dt><dd className="text-right text-foreground">{formatVietnamChartPrice(tooltip.close)}</dd>
            <dt>Volume</dt><dd className="text-right text-foreground">{formatCompactShareVolume(tooltip.volume, '—')}</dd>
          </dl>
        </div>
      ) : null}
      <p className="mt-2 text-right text-[10px] text-muted">
        Charts by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="underline hover:text-secondary-text">TradingView</a>. Market data by StockClock/SSI.
      </p>
    </div>
  );
};
