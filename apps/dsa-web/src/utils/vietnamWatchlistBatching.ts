export const VN30_WATCHLIST_BATCH_SIZE_DEFAULT = 5;
export const VN30_WATCHLIST_BATCH_SIZE_MIN = 3;
export const VN30_WATCHLIST_BATCH_SIZE_MAX = 10;

export const resolveVietnamWatchlistBatchSize = (
  totalTickers: number,
  preferredBatchSize = VN30_WATCHLIST_BATCH_SIZE_DEFAULT,
) => {
  const safeTotal = Math.max(0, Math.trunc(totalTickers));
  if (!safeTotal) return 0;
  const numericPreferred = Number.isFinite(preferredBatchSize)
    ? Math.trunc(preferredBatchSize)
    : VN30_WATCHLIST_BATCH_SIZE_DEFAULT;
  const boundedPreferred = Math.min(
    VN30_WATCHLIST_BATCH_SIZE_MAX,
    Math.max(VN30_WATCHLIST_BATCH_SIZE_MIN, numericPreferred),
  );
  return Math.min(safeTotal, boundedPreferred);
};

export const chunkVietnamWatchlistTickers = (
  tickers: string[],
  preferredBatchSize = VN30_WATCHLIST_BATCH_SIZE_DEFAULT,
) => {
  const batchSize = resolveVietnamWatchlistBatchSize(tickers.length, preferredBatchSize);
  if (!batchSize) return [];
  const chunks: string[][] = [];
  for (let index = 0; index < tickers.length; index += batchSize) {
    chunks.push(tickers.slice(index, index + batchSize));
  }
  return chunks;
};
