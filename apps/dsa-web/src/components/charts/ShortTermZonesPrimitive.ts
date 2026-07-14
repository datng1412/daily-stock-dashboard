import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  ISeriesPrimitiveAxisView,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from 'lightweight-charts';
import type { ShortTermChartZone } from './lightweightChartData';

const SUPPORT_PRIMARY = '#0f766e';
const SUPPORT_SECONDARY = '#115e59';
const RESISTANCE_PRIMARY = '#b45309';
const RESISTANCE_SECONDARY = '#92400e';

const zoneColor = (zone: ShortTermChartZone) => {
  if (zone.kind === 'support') return zone.primary ? SUPPORT_PRIMARY : SUPPORT_SECONDARY;
  return zone.primary ? RESISTANCE_PRIMARY : RESISTANCE_SECONDARY;
};

class ZoneAxisView implements ISeriesPrimitiveAxisView {
  private readonly zone: ShortTermChartZone;
  private readonly coordinateFor: (price: number) => number | null;

  constructor(
    zone: ShortTermChartZone,
    coordinateFor: (price: number) => number | null,
  ) {
    this.zone = zone;
    this.coordinateFor = coordinateFor;
  }

  coordinate() { return this.coordinateFor(this.zone.midpoint) ?? -1_000; }
  text() { return `${this.zone.label} ${this.zone.formattedRange}`; }
  textColor() { return '#f8fafc'; }
  backColor() { return zoneColor(this.zone); }
  visible() { return this.coordinateFor(this.zone.midpoint) !== null; }
  tickVisible() { return true; }
}

class ZonesPaneRenderer implements IPrimitivePaneRenderer {
  private readonly zones: readonly ShortTermChartZone[];
  private readonly coordinateFor: (price: number) => number | null;

  constructor(
    zones: readonly ShortTermChartZone[],
    coordinateFor: (price: number) => number | null,
  ) {
    this.zones = zones;
    this.coordinateFor = coordinateFor;
  }

  draw(target: Parameters<IPrimitivePaneRenderer['draw']>[0]) {
    target.useMediaCoordinateSpace(({ context, mediaSize }) => {
      this.zones.forEach((zone) => {
        const upper = this.coordinateFor(zone.upper);
        const lower = this.coordinateFor(zone.lower);
        const midpoint = this.coordinateFor(zone.midpoint);
        if (upper === null || lower === null || midpoint === null) return;
        const top = Math.min(upper, lower);
        const bottom = Math.max(upper, lower);
        const color = zone.kind === 'support' ? '45,212,191' : '251,191,36';
        context.save();
        context.fillStyle = `rgba(${color},${zone.primary ? 0.10 : 0.04})`;
        context.fillRect(0, top, mediaSize.width, Math.max(1, bottom - top));
        context.strokeStyle = zone.kind === 'support'
          ? zone.primary ? 'rgba(94,234,212,0.72)' : 'rgba(94,234,212,0.38)'
          : zone.primary ? 'rgba(251,191,36,0.72)' : 'rgba(251,191,36,0.38)';
        context.lineWidth = zone.primary ? 1.25 : 1;
        context.setLineDash(zone.primary ? [] : [4, 4]);
        context.beginPath();
        context.moveTo(0, midpoint);
        context.lineTo(mediaSize.width, midpoint);
        context.stroke();
        context.restore();
      });
    });
  }
}

class ZonesPaneView implements IPrimitivePaneView {
  private readonly rendererInstance: ZonesPaneRenderer;
  constructor(rendererInstance: ZonesPaneRenderer) { this.rendererInstance = rendererInstance; }
  zOrder() { return 'bottom' as const; }
  renderer() { return this.rendererInstance; }
}

export class ShortTermZonesPrimitive implements ISeriesPrimitive<Time> {
  private attachedParameters: SeriesAttachedParameter<Time, SeriesType> | null = null;
  private zones: ShortTermChartZone[] = [];
  private paneViewsCache: readonly IPrimitivePaneView[] = [];
  private axisViewsCache: readonly ISeriesPrimitiveAxisView[] = [];

  attached(parameters: SeriesAttachedParameter<Time, SeriesType>) {
    this.attachedParameters = parameters;
    this.rebuildViews();
  }

  detached() {
    this.attachedParameters = null;
    this.paneViewsCache = [];
    this.axisViewsCache = [];
  }

  setZones(zones: readonly ShortTermChartZone[]) {
    this.zones = zones.slice(0, 4);
    this.rebuildViews();
    this.attachedParameters?.requestUpdate();
  }

  clear() { this.setZones([]); }
  updateAllViews() { this.rebuildViews(); }
  paneViews() { return this.paneViewsCache; }
  priceAxisViews() { return this.axisViewsCache; }

  private coordinateFor = (price: number) => this.attachedParameters?.series.priceToCoordinate(price) ?? null;

  private rebuildViews() {
    if (!this.attachedParameters || !this.zones.length) {
      this.paneViewsCache = [];
      this.axisViewsCache = [];
      return;
    }
    this.paneViewsCache = [new ZonesPaneView(new ZonesPaneRenderer(this.zones, this.coordinateFor))];
    this.axisViewsCache = this.zones.map((zone) => new ZoneAxisView(zone, this.coordinateFor));
  }
}
