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

const ForeignFlowPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [watchlistValues] = useState(() => readVietnamCustomWatchlistValues());
  const [filter, setFilter] = useState<ForeignFlowFilter>('all');
  const [marketPhase] = useState(() => getVietnamMarketPhase());
  const batch = useForeignFlowWatchlistBatch(watchlistValues, { topN: 10 });
  const window = validWindow(searchParams.get('window'));
  const metric = validMetric(searchParams.get('metric'));
  const sort = validSort(searchParams.get('sort'));
  const direction = validDirection(searchParams.get('direction'));
  const view = validView(searchParams.get('view'));
  const requestedTicker = normalizeVietnamTicker(searchParams.get('ticker') ?? '');
  const selectedTicker = batch.scope.tickers.includes(requestedTicker) ? requestedTicker : null;
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
    if (batch.loading && !batch.data) return 'Đang tải dữ liệu DailyStockPrice cho watchlist.';
    if (batch.updating) return 'Đang cập nhật; tiếp tục hiển thị dữ liệu gần nhất.';
    if (batch.error && batch.data) return 'Cập nhật chưa khả dụng; đang giữ dữ liệu trước đó.';
    if (selectedSummary?.selectedWindowState === 'incomplete') return `Một số mã chưa có đủ dữ liệu cho cửa sổ ${window === 'today' ? 'phiên gần nhất' : `${window} phiên`}; không thay bằng giá trị 0.`;
    if (selectedSummary?.selectedWindowState === 'stale') return 'Dữ liệu gần nhất đã cũ; vẫn giữ nguyên ngày và trạng thái nguồn.';
    if (selectedSummary?.selectedWindowState === 'empty') return 'SSI DailyStockPrice chưa trả về dòng dữ liệu được chấp nhận cho phạm vi này.';
    if (selectedSummary?.selectedWindowState === 'unavailable') return `Dữ liệu ${window === 'today' ? 'phiên gần nhất' : `${window} phiên`} hiện chưa khả dụng; không tạo tổng hoặc xếp hạng thay thế.`;
    return null;
  }, [batch.data, batch.error, batch.loading, batch.updating, selectedSummary, window]);

  return (
    <AppPage className="space-y-6">
      <PageHeader
        eyebrow="Vietnam · SSI DailyStockPrice"
        title="Dòng tiền ngoại"
        description="Theo dõi mua, bán và mua bán ròng của khối ngoại trong watchlist"
        actions={batch.scope.tickers.length ? (
          <Button variant="outline" size="sm" onClick={batch.forceRefresh} isLoading={batch.loading} loadingText="Đang làm mới...">
            <RefreshCw className="h-4 w-4" /> Làm mới
          </Button>
        ) : null}
      />

      <section className="rounded-lg border border-border/70 bg-card p-4" aria-label="Phạm vi và điều khiển dữ liệu">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="info">Watchlist</Badge>
              <Badge>{batch.scope.tickers.length} mã</Badge>
              <Badge variant="default" aria-label="Nguồn: SSI DailyStockPrice · Trạng thái dữ liệu: daily_available">Dữ liệu theo phiên</Badge>
            </div>
            <p className="mt-2 text-sm text-secondary-text">Dữ liệu theo phiên giao dịch gần nhất có sẵn.</p>
            <p className="mt-1 text-xs text-secondary-text">Phiên thị trường: {marketPhase.phase}. Trạng thái phiên không thay đổi tính hợp lệ của dữ liệu ngày.</p>
            {batch.scope.limited ? (
              <p className="mt-1 text-sm text-warning" role="status">Đang hiển thị 30/{batch.scope.totalNormalizedCount} mã đầu tiên. Các mã còn lại không được phân loại là lỗi nhà cung cấp.</p>
            ) : null}
            {batch.scope.invalidCount ? <p className="mt-1 text-xs text-warning">Đã bỏ qua {batch.scope.invalidCount} mã không hợp lệ trong dữ liệu lưu cục bộ.</p> : null}
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

      {!batch.scope.tickers.length ? (
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
          <ForeignFlowSummaryCards data={batch.data} window={window} metric={metric} />
          <div className="grid items-start gap-4 lg:grid-cols-2">
            <ForeignFlowBreadth breadth={workspace.breadth} window={window} metric={metric} />
            <ForeignFlowConcentration concentration={workspace.concentration} window={window} metric={metric} />
          </div>
          <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <ForeignFlowTreemap
              items={workspace.treemapItems}
              window={window}
              metric={metric}
              selectedTicker={selectedTicker}
              onSelectTicker={(ticker) => updateQuery({ ticker })}
            />
            <ForeignFlowDivergingBars buyers={workspace.buyers} sellers={workspace.sellers} window={window} metric={metric} />
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
          />
        </>
      ) : (
        <EmptyState
          title="Dữ liệu dòng tiền ngoại chưa khả dụng"
          description="Không tạo số 0 thay thế. Bạn có thể thử lại mà không thay đổi watchlist."
          action={<Button variant="outline" onClick={batch.refresh}>Thử lại</Button>}
        />
      )}
    </AppPage>
  );
};

export default ForeignFlowPage;
