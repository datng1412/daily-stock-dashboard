import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, RefreshCw, Users } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { AppPage, Badge, Button, EmptyState, PageHeader } from '../components/common';
import { ForeignFlowBreadth } from '../components/foreign-flow/ForeignFlowBreadth';
import { ForeignFlowConcentration } from '../components/foreign-flow/ForeignFlowConcentration';
import { ForeignFlowDivergingBars } from '../components/foreign-flow/ForeignFlowDivergingBars';
import { ForeignFlowScannerTable } from '../components/foreign-flow/ForeignFlowScannerTable';
import { ForeignFlowSummaryCards } from '../components/foreign-flow/ForeignFlowSummaryCards';
import { ForeignFlowTreemap } from '../components/foreign-flow/ForeignFlowTreemap';
import { ForeignFlowSymbolAnalyticsPanel, type SymbolForeignFlowWindow } from '../components/foreign-flow/ForeignFlowSymbolAnalyticsPanel';
import type { SymbolForeignFlowChartMode } from '../components/foreign-flow/ForeignFlowSymbolHistoryChart';
import type { SymbolForeignFlowMetric, SymbolForeignFlowRange } from '../components/foreign-flow/foreignFlowSymbolAnalyticsModel';
import { Vn30ForeignFlowHistoryChart, type Vn30ForeignFlowChartMode, type Vn30ForeignFlowChartRange } from '../components/foreign-flow/Vn30ForeignFlowHistoryChart';
import { Vn30ForeignFlowSummary } from '../components/foreign-flow/Vn30ForeignFlowSummary';
import {
  buildForeignFlowWorkspaceViewModel,
  summarizeForeignFlow,
  type ForeignFlowDirection,
  type ForeignFlowFilter,
  type ForeignFlowMetric,
  type ForeignFlowSort,
  type ForeignFlowWindow,
  type ForeignFlowView,
} from '../components/foreign-flow/foreignFlowViewModel';
import { useForeignFlowWatchlistBatch } from '../hooks/useForeignFlowWatchlistBatch';
import { useForeignFlowVn30 } from '../hooks/useForeignFlowVn30';
import { useForeignFlowSymbolAnalytics } from '../hooks/useForeignFlowSymbolAnalytics';
import type { VietnamForeignFlowBatchResponse, VietnamVn30ForeignFlowResponse } from '../api/stocks';
import { readVietnamCustomWatchlistValues } from '../utils/vietnamCustomWatchlist';
import { getVietnamMarketPhase } from '../utils/vietnamMarketPhase';
import { normalizeVietnamTicker } from '../utils/vietnamWatchlist';

const windows: Array<{ value: ForeignFlowWindow; label: string }> = [
  { value: 'today', label: 'Phiên gần nhất' },
  { value: '5', label: '5 phiên' },
  { value: '20', label: '20 phiên' },
];

const validWindow = (value: string | null): ForeignFlowWindow => (
  value === '5' || value === '20' ? value : 'today'
);
const validMetric = (value: string | null): ForeignFlowMetric => value === 'volume' ? 'volume' : 'value';
const validSort = (value: string | null): ForeignFlowSort => (
  value === 'ticker' || value === 'selected' || value === 'absolute' || value === 'share' || value === '5' || value === '20' || value === 'date' || value === 'state' ? value : 'selected'
);
const validDirection = (value: string | null): ForeignFlowDirection => value === 'asc' ? 'asc' : 'desc';
const validView = (value: string | null): ForeignFlowView => value === 'detailed' ? 'detailed' : 'overview';
const validScope = (value: string | null): 'watchlist' | 'vn30' => value === 'vn30' ? 'vn30' : 'watchlist';
const validChartMode = (value: string | null): Vn30ForeignFlowChartMode => (
  value === 'buy-sell' || value === 'cumulative' || value === 'breadth' ? value : 'net'
);
const validChartRange = (value: string | null): Vn30ForeignFlowChartRange => value === '5' || value === '10' ? value : '20';
const validSymbolMetric = (value: string | null): SymbolForeignFlowMetric => value === 'volume' ? 'volume' : 'value';
const validSymbolRange = (value: string | null): SymbolForeignFlowRange => value === '20' || value === '40' ? Number(value) as 20 | 40 : 60;
const validSymbolChart = (value: string | null): SymbolForeignFlowChartMode => value === 'buy-sell' || value === 'cumulative' || value === 'rolling' ? value : 'net';
const validSymbolWindow = (value: string | null): SymbolForeignFlowWindow => value === '5' || value === '20' || value === '60' ? value : 'latest';

const vn30AsBatchResponse = (
  data: VietnamVn30ForeignFlowResponse,
  metric: ForeignFlowMetric,
): VietnamForeignFlowBatchResponse => ({
  source: data.source,
  sourceEndpoint: 'daily_stock_price',
  volumeUnit: data.volumeUnit,
  valueUnit: data.valueUnit,
  finality: data.finality,
  requestedTickers: data.membership.memberTickers,
  normalizedTickers: data.membership.memberTickers,
  requestedCount: data.membership.memberCount,
  normalizedCount: data.membership.memberCount,
  returnedCount: data.components.length,
  usableCount: data.componentCounts.usable,
  freshCount: Math.max(0, data.componentCounts.usable - data.componentCounts.stale),
  staleCount: data.componentCounts.stale,
  emptyCount: data.componentCounts.empty,
  unavailableCount: data.componentCounts.unavailable,
  coverageRatio: data.membership.memberCount ? data.componentCounts.usable / data.membership.memberCount : 0,
  complete: data.dataState === 'ready',
  dataState: data.dataState,
  rows: data.components.map((row) => ({
    ...row,
    latestTradingDate: row.aggregateLatestDate ?? null,
    coveredSessions5d: metric === 'value' ? row.valueCoveredSessions5d : row.volumeCoveredSessions5d,
    complete5d: metric === 'value' ? row.valueComplete5d : row.volumeComplete5d,
    coveredSessions20d: metric === 'value' ? row.valueCoveredSessions20d : row.volumeCoveredSessions20d,
    complete20d: metric === 'value' ? row.valueComplete20d : row.volumeComplete20d,
    source: 'ssi_fastconnect',
    sourceEndpoint: 'daily_stock_price',
    volumeUnit: 'shares',
    valueUnit: 'VND',
    finality: 'daily_available',
    fetchedAt: data.fetchedAt,
  })),
  rankings: {
    latestNetValue: data.rankings.latestNetValue ?? { topBuy: [], topSell: [] },
    netValue5d: data.rankings.netValue5D ?? data.rankings.netValue5d ?? { topBuy: [], topSell: [] },
    netValue20d: data.rankings.netValue20D ?? data.rankings.netValue20d ?? { topBuy: [], topSell: [] },
  },
  fetchedAt: data.fetchedAt,
});

const ForeignFlowPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [watchlistValues] = useState(() => readVietnamCustomWatchlistValues());
  const [filter, setFilter] = useState<ForeignFlowFilter>('all');
  const [marketPhase] = useState(() => getVietnamMarketPhase());
  const scope = validScope(searchParams.get('scope'));
  const watchlistBatch = useForeignFlowWatchlistBatch(watchlistValues, { topN: 10, active: scope === 'watchlist' });
  const vn30 = useForeignFlowVn30(scope === 'vn30', 10);
  const window = validWindow(searchParams.get('window'));
  const metric = validMetric(searchParams.get('metric'));
  const sort = validSort(searchParams.get('sort'));
  const direction = validDirection(searchParams.get('direction'));
  const view = validView(searchParams.get('view'));
  const chartMode = validChartMode(searchParams.get('chart'));
  const chartRange = validChartRange(searchParams.get('range'));
  const symbolMetric = validSymbolMetric(searchParams.get('symbolMetric'));
  const symbolRange = validSymbolRange(searchParams.get('symbolRange'));
  const symbolChart = validSymbolChart(searchParams.get('symbolChart'));
  const symbolWindow = validSymbolWindow(searchParams.get('symbolWindow'));
  const vn30BatchData = useMemo(() => vn30.data ? vn30AsBatchResponse(vn30.data, metric) : null, [metric, vn30.data]);
  const batch = scope === 'vn30'
    ? { ...vn30, data: vn30BatchData, scope: { tickers: vn30.data?.membership.memberTickers ?? [], limited: false, totalNormalizedCount: vn30.data?.membership.memberCount ?? 0, invalidCount: 0 } }
    : watchlistBatch;
  const scopeLabel = scope === 'vn30' ? 'VN30' : 'watchlist';
  const requestedTicker = normalizeVietnamTicker(searchParams.get('ticker') ?? '');
  const selectedTicker = batch.scope.tickers.includes(requestedTicker) ? requestedTicker : null;
  const inspectOpen = searchParams.get('inspect') === '1' && Boolean(selectedTicker);
  const symbolAnalytics = useForeignFlowSymbolAnalytics(selectedTicker, inspectOpen);
  const selectedSummary = useMemo(
    () => batch.data ? summarizeForeignFlow(batch.data.rows, window, metric) : null,
    [batch.data, metric, window],
  );
  const workspace = useMemo(
    () => batch.data ? buildForeignFlowWorkspaceViewModel(batch.data.rows, window, metric) : null,
    [batch.data, metric, window],
  );

  useEffect(() => {
    const previousTitle = document.title;
    document.title = 'Dòng tiền ngoại';
    return () => { document.title = previousTitle; };
  }, []);

  const updateQuery = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null) next.delete(key);
      else next.set(key, value);
    });
    setSearchParams(next);
  };

  const handleSort = (nextSort: ForeignFlowSort) => {
    updateQuery({
      sort: nextSort,
      direction: sort === nextSort && direction === 'desc' ? 'asc' : 'desc',
    });
  };

  const stateCopy = useMemo(() => {
    if (batch.loading && !batch.data) return `Đang tải dữ liệu DailyStockPrice cho ${scopeLabel}.`;
    if (batch.updating) return 'Đang cập nhật; tiếp tục hiển thị dữ liệu gần nhất.';
    if (batch.error && batch.data) return 'Cập nhật chưa khả dụng; đang giữ dữ liệu trước đó.';
    if (scope === 'vn30' && vn30.data?.membership.status === 'unavailable') return 'Thành phần VN30 từ SSI IndexComponents hiện chưa khả dụng; không dùng danh sách thay thế.';
    if (selectedSummary?.selectedWindowState === 'incomplete') return `Một số mã chưa có đủ dữ liệu cho cửa sổ ${window === 'today' ? 'phiên gần nhất' : `${window} phiên`}; không thay bằng giá trị 0.`;
    if (selectedSummary?.selectedWindowState === 'stale') return 'Dữ liệu gần nhất đã cũ; vẫn giữ nguyên ngày và trạng thái nguồn.';
    if (selectedSummary?.selectedWindowState === 'empty') return 'SSI DailyStockPrice chưa trả về dòng dữ liệu được chấp nhận cho phạm vi này.';
    if (selectedSummary?.selectedWindowState === 'unavailable') return `Dữ liệu ${window === 'today' ? 'phiên gần nhất' : `${window} phiên`} hiện chưa khả dụng; không tạo tổng hoặc xếp hạng thay thế.`;
    return null;
  }, [batch.data, batch.error, batch.loading, batch.updating, scope, scopeLabel, selectedSummary, vn30.data, window]);

  return (
    <AppPage className="space-y-6">
      <PageHeader
        eyebrow="Vietnam · SSI DailyStockPrice"
        title="Dòng tiền ngoại"
        description={`Theo dõi mua, bán và mua bán ròng của khối ngoại trong ${scopeLabel}`}
        actions={scope === 'vn30' || batch.scope.tickers.length ? (
          <Button variant="outline" size="sm" onClick={batch.forceRefresh} isLoading={batch.loading} loadingText="Đang làm mới...">
            <RefreshCw className="h-4 w-4" /> Làm mới
          </Button>
        ) : null}
      />

      <section className="rounded-lg border border-border/70 bg-card p-4" aria-label="Phạm vi và điều khiển dữ liệu">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="mb-3 inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Phạm vi dòng tiền ngoại">
              {(['watchlist', 'vn30'] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${scope === option ? 'bg-cyan/15 text-cyan' : 'text-secondary-text hover:text-foreground'}`}
                  aria-pressed={scope === option}
                  onClick={() => updateQuery({ scope: option, ticker: null, inspect: null })}
                >{option === 'watchlist' ? 'Watchlist' : 'VN30'}</button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="info">{scope === 'vn30' ? 'VN30 · SSI IndexComponents' : 'Watchlist'}</Badge>
              <Badge>{batch.scope.tickers.length} mã</Badge>
              <Badge variant="default" aria-label="Nguồn: SSI DailyStockPrice · Trạng thái dữ liệu: daily_available">Dữ liệu theo phiên</Badge>
            </div>
            <p className="mt-2 text-sm text-secondary-text">Dữ liệu theo phiên giao dịch gần nhất có sẵn.</p>
            {scope === 'vn30' ? <p className="mt-1 text-xs text-secondary-text">Chuỗi lịch sử được tổng hợp theo thành phần VN30 hiện tại, không tái tạo thành phần lịch sử theo từng ngày.</p> : null}
            <p className="mt-1 text-xs text-secondary-text">Phiên thị trường: {marketPhase.phase}. Trạng thái phiên không thay đổi tính hợp lệ của dữ liệu ngày.</p>
            {scope === 'watchlist' && batch.scope.limited ? (
              <p className="mt-1 text-sm text-warning" role="status">Đang hiển thị 30/{batch.scope.totalNormalizedCount} mã đầu tiên. Các mã còn lại không được phân loại là lỗi nhà cung cấp.</p>
            ) : null}
            {scope === 'watchlist' && batch.scope.invalidCount ? <p className="mt-1 text-xs text-warning">Đã bỏ qua {batch.scope.invalidCount} mã không hợp lệ trong dữ liệu lưu cục bộ.</p> : null}
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Cửa sổ dòng tiền ngoại">
              {windows.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${window === option.value ? 'bg-cyan/15 text-cyan' : 'text-secondary-text hover:text-foreground'}`}
                  aria-pressed={window === option.value}
                  onClick={() => updateQuery({ window: option.value })}
                >{option.label}</button>
              ))}
            </div>
            <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Đơn vị dòng tiền ngoại">
              {(['value', 'volume'] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${metric === option ? 'bg-cyan/15 text-cyan' : 'text-secondary-text hover:text-foreground'}`}
                  aria-pressed={metric === option}
                  onClick={() => updateQuery({ metric: option })}
                >{option === 'value' ? 'Giá trị' : 'Khối lượng'}</button>
              ))}
            </div>
            <div className="inline-flex rounded-lg border border-border/70 p-1" role="group" aria-label="Mức độ chi tiết">
              {(['overview', 'detailed'] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${view === option ? 'bg-cyan/15 text-cyan' : 'text-secondary-text hover:text-foreground'}`}
                  aria-pressed={view === option}
                  onClick={() => updateQuery({ view: option })}
                >{option === 'overview' ? 'Tổng quan' : 'Chi tiết'}</button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {scope === 'watchlist' && !batch.scope.tickers.length ? (
        <EmptyState
          icon={<Users className="h-8 w-8" />}
          title="Watchlist đang trống"
          description="Chọn preset hoặc lưu danh sách mã trên trang Vietnam trước khi mở không gian dòng tiền ngoại."
          action={<Link className="btn-primary inline-flex items-center gap-2" to="/vietnam"><ArrowLeft className="h-4 w-4" /> Mở trang Vietnam</Link>}
        />
      ) : batch.loading && !batch.data ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Đang tải dòng tiền ngoại">
          {Array.from({ length: 6 }, (_, index) => <div key={index} className="h-28 animate-pulse rounded-lg bg-elevated/60" />)}
        </div>
      ) : batch.data && workspace ? (
        <>
          {stateCopy ? <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning" role="status">{stateCopy}</div> : null}
          {scope === 'vn30' && vn30.data
            ? <Vn30ForeignFlowSummary data={vn30.data} window={window} metric={metric} />
            : <ForeignFlowSummaryCards data={batch.data} window={window} metric={metric} scopeLabel={scopeLabel} />}
          {scope === 'vn30' && vn30.data ? (
            <Vn30ForeignFlowHistoryChart
              series={vn30.data.series}
              metric={metric}
              mode={chartMode}
              range={chartRange}
              onModeChange={(chart) => updateQuery({ chart })}
              onRangeChange={(range) => updateQuery({ range })}
            />
          ) : null}
          <div className="grid items-start gap-4 lg:grid-cols-2">
            <ForeignFlowBreadth breadth={workspace.breadth} window={window} metric={metric} scopeLabel={scopeLabel} />
            <ForeignFlowConcentration concentration={workspace.concentration} window={window} metric={metric} />
          </div>
          <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <ForeignFlowTreemap
              items={workspace.treemapItems}
              window={window}
              metric={metric}
              selectedTicker={selectedTicker}
              onSelectTicker={(ticker) => updateQuery({ ticker })}
              scopeLabel={scopeLabel}
            />
            <ForeignFlowDivergingBars buyers={workspace.buyers} sellers={workspace.sellers} window={window} metric={metric} scopeLabel={scopeLabel} />
          </div>
          <ForeignFlowScannerTable
            rows={batch.data.rows}
            window={window}
            metric={metric}
            sort={sort}
            direction={direction}
            filter={filter}
            view={view}
            selectedTicker={selectedTicker}
            onSort={handleSort}
            onFilter={setFilter}
            onSelectTicker={(ticker) => updateQuery({ ticker })}
            scopeLabel={scopeLabel}
          />
          {selectedTicker && !inspectOpen ? <div className="flex justify-end"><Button variant="outline" onClick={() => updateQuery({ inspect: '1' })}>Mở phân tích chi tiết · {selectedTicker}</Button></div> : null}
          {selectedTicker && inspectOpen ? <ForeignFlowSymbolAnalyticsPanel
            ticker={selectedTicker}
            data={symbolAnalytics.data}
            loading={symbolAnalytics.loading}
            updating={symbolAnalytics.updating}
            error={symbolAnalytics.error}
            metric={symbolMetric}
            range={symbolRange}
            mode={symbolChart}
            window={symbolWindow}
            onMetricChange={(value) => updateQuery({ symbolMetric: value })}
            onRangeChange={(value) => updateQuery({ symbolRange: String(value) })}
            onModeChange={(value) => updateQuery({ symbolChart: value })}
            onWindowChange={(value) => updateQuery({ symbolWindow: value })}
            onRetry={symbolAnalytics.retry}
            onForceRefresh={symbolAnalytics.forceRefresh}
            onClose={() => updateQuery({ inspect: null })}
          /> : null}
        </>
      ) : (
        <EmptyState
          title="Dữ liệu dòng tiền ngoại chưa khả dụng"
          description={`Không tạo số 0 thay thế. Bạn có thể thử lại mà không thay đổi ${scopeLabel}.`}
          action={<Button variant="outline" onClick={batch.refresh}>Thử lại</Button>}
        />
      )}
    </AppPage>
  );
};

export default ForeignFlowPage;
