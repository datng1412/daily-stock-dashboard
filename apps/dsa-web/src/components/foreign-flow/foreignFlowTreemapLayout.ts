import type { ForeignFlowWorkspaceRow } from './foreignFlowViewModel';

export type ForeignFlowTreemapRect = {
  item: ForeignFlowWorkspaceRow;
  x: number;
  y: number;
  width: number;
  height: number;
};

const totalWeight = (items: ForeignFlowWorkspaceRow[]): number => (
  items.reduce((total, item) => total + item.magnitude, 0)
);

const splitIndex = (items: ForeignFlowWorkspaceRow[]): number => {
  const target = totalWeight(items) / 2;
  let accumulated = 0;
  for (let index = 0; index < items.length - 1; index += 1) {
    accumulated += items[index].magnitude;
    if (accumulated >= target) return index + 1;
  }
  return Math.max(1, items.length - 1);
};

const layoutGroup = (
  items: ForeignFlowWorkspaceRow[],
  x: number,
  y: number,
  width: number,
  height: number,
): ForeignFlowTreemapRect[] => {
  if (!items.length || width <= 0 || height <= 0) return [];
  if (items.length === 1) return [{ item: items[0], x, y, width, height }];

  const splitAt = splitIndex(items);
  const first = items.slice(0, splitAt);
  const second = items.slice(splitAt);
  const weight = totalWeight(items);
  const firstRatio = weight > 0 ? totalWeight(first) / weight : 0.5;

  if (width >= height) {
    const firstWidth = width * firstRatio;
    return [
      ...layoutGroup(first, x, y, firstWidth, height),
      ...layoutGroup(second, x + firstWidth, y, width - firstWidth, height),
    ];
  }

  const firstHeight = height * firstRatio;
  return [
    ...layoutGroup(first, x, y, width, firstHeight),
    ...layoutGroup(second, x, y + firstHeight, width, height - firstHeight),
  ];
};

export const layoutForeignFlowTreemap = (
  items: ForeignFlowWorkspaceRow[],
  width = 1_000,
  height = 420,
): ForeignFlowTreemapRect[] => {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return [];
  const eligible = items
    .filter((item) => Number.isFinite(item.magnitude) && item.magnitude > 0)
    .sort((left, right) => right.magnitude - left.magnitude || left.ticker.localeCompare(right.ticker));
  return layoutGroup(eligible, 0, 0, width, height);
};
