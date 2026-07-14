import { describe, expect, it, vi } from 'vitest';
import type { SeriesAttachedParameter, SeriesType, Time } from 'lightweight-charts';
import { ShortTermZonesPrimitive } from '../ShortTermZonesPrimitive';
import type { ShortTermChartZone } from '../lightweightChartData';

const zones: ShortTermChartZone[] = [
  { label: 'S1', lower: 69_000, upper: 69_800, midpoint: 69_400, kind: 'support', primary: true, formattedRange: '69.00–69.80' },
  { label: 'S2', lower: 67_000, upper: 68_000, midpoint: 67_500, kind: 'support', primary: false, formattedRange: '67.00–68.00' },
  { label: 'R1', lower: 73_500, upper: 74_100, midpoint: 73_800, kind: 'resistance', primary: true, formattedRange: '73.50–74.10' },
  { label: 'R2', lower: 75_400, upper: 76_000, midpoint: 75_700, kind: 'resistance', primary: false, formattedRange: '75.40–76.00' },
];

const attach = (primitive: ShortTermZonesPrimitive) => {
  const requestUpdate = vi.fn();
  const priceToCoordinate = vi.fn((price: number) => price / 1_000);
  primitive.attached({ series: { priceToCoordinate }, requestUpdate } as unknown as SeriesAttachedParameter<Time, SeriesType>);
  return { requestUpdate, priceToCoordinate };
};

describe('ShortTermZonesPrimitive', () => {
  it('has no visuals while off and exposes no autoscale expansion', () => {
    const primitive = new ShortTermZonesPrimitive();
    attach(primitive);
    expect(primitive.paneViews()).toEqual([]);
    expect(primitive.priceAxisViews()).toEqual([]);
    expect('autoscaleInfo' in primitive).toBe(false);
  });

  it('creates at most four readable midpoint axis views and requests a redraw', () => {
    const primitive = new ShortTermZonesPrimitive();
    const { requestUpdate, priceToCoordinate } = attach(primitive);
    primitive.setZones([...zones, zones[0]]);
    const views = primitive.priceAxisViews();
    expect(views).toHaveLength(4);
    expect(views.map((view) => view.text())).toEqual([
      'S1 69.00–69.80', 'S2 67.00–68.00', 'R1 73.50–74.10', 'R2 75.40–76.00',
    ]);
    expect(views[0].coordinate()).toBe(69.4);
    expect(priceToCoordinate).toHaveBeenCalledWith(69_400);
    expect(primitive.paneViews()).toHaveLength(1);
    expect(requestUpdate).toHaveBeenCalled();
  });

  it('clears and detaches all primitive references', () => {
    const primitive = new ShortTermZonesPrimitive();
    attach(primitive);
    primitive.setZones(zones);
    primitive.clear();
    expect(primitive.paneViews()).toEqual([]);
    expect(primitive.priceAxisViews()).toEqual([]);
    primitive.detached();
    expect(primitive.priceAxisViews()).toEqual([]);
  });
});
