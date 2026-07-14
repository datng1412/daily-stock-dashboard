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
  formatVietnamChartTick,
  formatVietnamRsiValue,
  formatVietnamChartTime,
  normalizeLightweightChartData,
  type ShortTermChartZone,
  type VietnamChartTimeframe,
  VN_CHART_PRICE_MIN_MOVE,
} from './lightweightChartData';
import { ShortTermZonesPrimitive } from './ShortTermZonesPrimitive';

type TooltipState = {
  ticker: string;
  contextKey: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  left: number;
  top: number;
};

const TOOLTIP_WIDTH_PX = 180;
const TOOLTIP_HEIGHT_PX = 150;
const TOOLTIP_MARGIN_PX = 8;
const TOOLTIP_OFFSET_PX = 14;

export const VN_CHART_PRICE_SCALE_MIN_WIDTH = 148;
// The visible axis is pane-scoped in Lightweight Charts. Pane 2 owns this right
// scale exclusively, independently of the price and volume panes.
export const VN_CHART_RSI_PRICE_SCALE_ID = 'right';
export const VN_CHART_COMPACT_PANE_STRETCH = [68, 14, 18] as const;
export const VN_CHART_EXPANDED_PANE_STRETCH = [70, 12, 18] as const;

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
  timeframe?: VietnamChartTimeframe;
  requestKey?: string;
  expanded?: boolean;
  initialLogicalRange?: IRange<number> | null;
  onLogicalRangeChange?: (range: IRange<number> | null) => void;
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
  timeframe = '1D',
  requestKey = '',
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
  const latestContextRef = useRef(`${ticker}:${timeframe}:${requestKey}`);
  const previousContextRef = useRef<string | null>(null);
  const initialFallbackHeightRef = useRef(expanded ? 680 : 520);
  const tooltipElementRef = useRef<HTMLDivElement | null>(null);
  const tooltipContentKeyRef = useRef<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const chartData = useMemo(() => normalizeLightweightChartData(points, timeframe), [points, timeframe]);

  useEffect(() => { latestRangeHandlerRef.current = onLogicalRangeChange; }, [onLogicalRangeChange]);
  useEffect(() => { latestTickerRef.current = ticker; }, [ticker]);
  useEffect(() => { latestContextRef.current = `${ticker}:${timeframe}:${requestKey}`; }, [requestKey, ticker, timeframe]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    let disposed = false;
    const chart = createChart(container, {
      autoSize: true,
      height: initialFallbackHeightRef.current,
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
      rightPriceScale: {
        borderColor: 'rgba(148,163,184,0.28)',
        minimumWidth: VN_CHART_PRICE_SCALE_MIN_WIDTH,
      },
      timeScale: {
        borderColor: 'rgba(148,163,184,0.28)',
        timeVisible: false,
        secondsVisible: false,
        lockVisibleTimeRangeOnResize: true,
      },
      localization: { locale: 'en-US' },
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
    const volumeMa20 = chart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 1, priceFormat: { type: 'volume' }, priceScaleId: 'right', priceLineVisible: false, lastValueVisible: false }, 1);
    const volumeMa50 = chart.addSeries(LineSeries, { color: '#f97316', lineWidth: 1, priceFormat: { type: 'volume' }, priceScaleId: 'right', priceLineVisible: false, lastValueVisible: false }, 1);
    const rsi14 = chart.addSeries(LineSeries, {
      color: '#22c55e', lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
      priceFormat: { type: 'custom', minMove: 0.01, formatter: formatVietnamRsiValue },
      priceScaleId: VN_CHART_RSI_PRICE_SCALE_ID,
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

    const handleCrosshairMove = (param: Parameters<IChartApi['subscribeCrosshairMove']>[0] extends (value: infer P) => void ? P : never) => {
      if (disposed) return;
      const candle = param.seriesData.get(candles);
      if (!param.point || !param.time || !candle || !('open' in candle)) {
        tooltipContentKeyRef.current = null;
        setTooltip(null);
        return;
      }
      const volumePoint = param.seriesData.get(volume);
      const nextTooltip: TooltipState = {
        ticker: latestTickerRef.current,
        contextKey: latestContextRef.current,
        date: formatVietnamChartTime(param.time), open: candle.open, high: candle.high, low: candle.low, close: candle.close,
        volume: volumePoint && 'value' in volumePoint ? volumePoint.value : undefined,
        left: Math.max(
          TOOLTIP_MARGIN_PX,
          Math.min(
            param.point.x + TOOLTIP_OFFSET_PX,
            container.clientWidth - TOOLTIP_WIDTH_PX - TOOLTIP_MARGIN_PX,
          ),
        ),
        top: Math.max(
          TOOLTIP_MARGIN_PX,
          Math.min(
            param.point.y + TOOLTIP_OFFSET_PX,
            container.clientHeight - TOOLTIP_HEIGHT_PX - TOOLTIP_MARGIN_PX,
          ),
        ),
      };
      const contentKey = [
        nextTooltip.ticker,
        nextTooltip.date,
        nextTooltip.open,
        nextTooltip.high,
        nextTooltip.low,
        nextTooltip.close,
        nextTooltip.volume ?? '',
      ].join('|');
      if (tooltipContentKeyRef.current === contentKey && tooltipElementRef.current) {
        tooltipElementRef.current.style.left = `${nextTooltip.left}px`;
        tooltipElementRef.current.style.top = `${nextTooltip.top}px`;
        return;
      }
      tooltipContentKeyRef.current = contentKey;
      setTooltip(nextTooltip);
    };
    const handleRange = (range: IRange<number> | null) => {
      if (!disposed) latestRangeHandlerRef.current?.(range);
    };
    chart.subscribeCrosshairMove(handleCrosshairMove);
    chart.timeScale().subscribeVisibleLogicalRangeChange(handleRange);
    chartRef.current = chart;
    seriesRef.current = { candles, volume, volumeMa20, volumeMa50, rsi14, ma20, ma50, bbUpper, bbMid, bbLower };
    zonesPrimitiveRef.current = primitive;

    return () => {
      disposed = true;
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleRange);
      candles.detachPrimitive(primitive);
      primitive.clear();
      tooltipContentKeyRef.current = null;
      tooltipElementRef.current = null;
      zonesPrimitiveRef.current = null;
      seriesRef.current = null;
      chartRef.current = null;
      chart.remove();
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.applyOptions({
      localization: {
        timeFormatter: (time: Time) => formatVietnamChartTime(time),
      },
      timeScale: {
        timeVisible: timeframe === '1m',
        secondsVisible: false,
        tickMarkFormatter: (time: Time) => formatVietnamChartTick(time, timeframe),
      },
    });
  }, [timeframe]);

  useEffect(() => {
    const panes = chartRef.current?.panes();
    if (!panes) return;
    const stretch = expanded ? VN_CHART_EXPANDED_PANE_STRETCH : VN_CHART_COMPACT_PANE_STRETCH;
    panes[0]?.setStretchFactor(stretch[0]);
    panes[1]?.setStretchFactor(stretch[1]);
    panes[2]?.setStretchFactor(stretch[2]);
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
    const context = `${ticker}:${timeframe}:${requestKey}`;
    const contextChanged = previousContextRef.current !== null && context !== previousContextRef.current;
    if (contextChanged || (!initialLogicalRange && previousContextRef.current === null)) chart.timeScale().fitContent();
    else if (initialLogicalRange) chart.timeScale().setVisibleLogicalRange(initialLogicalRange);
    previousContextRef.current = context;
  }, [chartData, initialLogicalRange, requestKey, ticker, timeframe]);

  useEffect(() => { seriesRef.current?.ma20.applyOptions({ visible: showMA20 }); }, [showMA20]);
  useEffect(() => { seriesRef.current?.ma50.applyOptions({ visible: showMA50 }); }, [showMA50]);
  useEffect(() => {
    seriesRef.current?.bbUpper.applyOptions({ visible: showBollinger });
    seriesRef.current?.bbMid.applyOptions({ visible: showBollinger });
    seriesRef.current?.bbLower.applyOptions({ visible: showBollinger });
  }, [showBollinger]);
  useEffect(() => {
    zonesPrimitiveRef.current?.setZones(
      showShortTermZones && !loading && !unavailable ? shortTermZones : [],
    );
  }, [loading, shortTermZones, showShortTermZones, ticker, unavailable]);

  return (
    <div className="relative min-w-0 overflow-hidden" data-testid="vietnam-lightweight-chart" data-ticker={ticker} data-timeframe={timeframe}>
      <div
        ref={containerRef}
        className={expanded
          ? 'h-[clamp(480px,68vh,760px)] min-w-0 w-full overflow-hidden rounded-lg border border-border/60'
          : 'h-[clamp(420px,58vh,540px)] min-w-0 w-full overflow-hidden rounded-lg border border-border/60'}
        aria-label={`${ticker} ${timeframe === '1m' ? 'one-minute history' : 'daily'} candlestick chart`}
      />
      {loading ? <div className="absolute inset-0 grid place-items-center bg-[#07111d]/85 text-sm text-secondary-text">Loading chart data...</div> : null}
      {unavailable ? <div className="absolute inset-0 grid place-items-center bg-[#07111d]/90 text-sm text-secondary-text">{timeframe === '1m' ? 'SSI one-minute history unavailable.' : 'SSI daily chart data unavailable.'}</div> : null}
      {tooltip && tooltip.ticker === ticker && tooltip.contextKey === `${ticker}:${timeframe}:${requestKey}` && !loading && !unavailable ? (
        <div
          ref={tooltipElementRef}
          data-testid="lightweight-chart-tooltip"
          className="pointer-events-none absolute z-10 w-[180px] max-w-[calc(100%-1rem)] rounded-lg border border-border/70 bg-card/95 p-3 text-xs shadow-soft-card"
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
