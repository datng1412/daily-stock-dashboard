import { describe, expect, it } from 'vitest';
import type { ForeignFlowWorkspaceRow } from '../foreignFlowViewModel';
import { layoutForeignFlowTreemap } from '../foreignFlowTreemapLayout';

const item = (ticker: string, magnitude: number): ForeignFlowWorkspaceRow => ({
  ticker,
  sourceRow: {} as ForeignFlowWorkspaceRow['sourceRow'],
  display: {
    value: magnitude,
    coveredSessions: 1,
    requestedSessions: 1,
    complete: true,
    usable: true,
    stale: false,
    state: 'ready',
    endDate: '2026-07-17',
  },
  value: magnitude,
  magnitude,
  sign: 'buy',
  shareOfAbsoluteFlow: null,
});

const overlaps = (
  left: ReturnType<typeof layoutForeignFlowTreemap>[number],
  right: ReturnType<typeof layoutForeignFlowTreemap>[number],
) => left.x < right.x + right.width - 1e-9
  && left.x + left.width > right.x + 1e-9
  && left.y < right.y + right.height - 1e-9
  && left.y + left.height > right.y + 1e-9;

describe('foreign-flow treemap layout', () => {
  it('returns deterministic bounded non-overlapping rectangles', () => {
    const items = [item('BBB', 20), item('AAA', 20), item('CCC', 10), item('DDD', 5)];
    const first = layoutForeignFlowTreemap(items, 1_000, 420);
    const second = layoutForeignFlowTreemap([...items].reverse(), 1_000, 420);

    expect(first).toEqual(second);
    expect(first.map((rect) => rect.item.ticker)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    first.forEach((rect) => {
      expect(rect.x).toBeGreaterThanOrEqual(0);
      expect(rect.y).toBeGreaterThanOrEqual(0);
      expect(rect.width).toBeGreaterThan(0);
      expect(rect.height).toBeGreaterThan(0);
      expect(rect.x + rect.width).toBeLessThanOrEqual(1_000 + 1e-9);
      expect(rect.y + rect.height).toBeLessThanOrEqual(420 + 1e-9);
    });
    first.forEach((left, index) => first.slice(index + 1).forEach((right) => expect(overlaps(left, right)).toBe(false)));
  });

  it('allocates area exactly in proportion to weight', () => {
    const rectangles = layoutForeignFlowTreemap([item('BIG', 75), item('SMALL', 25)], 400, 200);
    const totalArea = 400 * 200;
    expect(rectangles[0].width * rectangles[0].height).toBeCloseTo(totalArea * 0.75);
    expect(rectangles[1].width * rectangles[1].height).toBeCloseTo(totalArea * 0.25);
  });

  it('handles empty, invalid, one-item, and thirty-item inputs', () => {
    expect(layoutForeignFlowTreemap([])).toEqual([]);
    expect(layoutForeignFlowTreemap([item('BAD', 0)])).toEqual([]);
    expect(layoutForeignFlowTreemap([item('ONE', 1)], 300, 120)[0]).toMatchObject({ x: 0, y: 0, width: 300, height: 120 });
    const thirty = layoutForeignFlowTreemap(Array.from({ length: 30 }, (_, index) => item(`T${index}`, 1)));
    expect(thirty).toHaveLength(30);
    expect(thirty.every((rect) => rect.width > 0 && rect.height > 0)).toBe(true);
  });
});
