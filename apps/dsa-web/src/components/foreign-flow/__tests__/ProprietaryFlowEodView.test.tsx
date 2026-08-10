import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type VietnamProprietaryFlowEodRow } from '../../../api/stocks';
import { ProprietaryFlowEodView } from '../ProprietaryFlowEodView';

vi.mock('../../../api/stocks', () => ({
  stocksApi: {
    getVietnamProprietaryFlowEodLatest: vi.fn(),
    getVietnamProprietaryFlowEodHistory: vi.fn(),
    getVietnamCurrentForeignFlow: vi.fn(),
    getVietnamCurrentForeignFlowAggregate: vi.fn(),
  },
}));

const latest = vi.mocked(stocksApi.getVietnamProprietaryFlowEodLatest);
const history = vi.mocked(stocksApi.getVietnamProprietaryFlowEodHistory);
const current = vi.mocked(stocksApi.getVietnamCurrentForeignFlow);
const currentAggregate = vi.mocked(stocksApi.getVietnamCurrentForeignFlowAggregate);

const row = (overrides: Partial<VietnamProprietaryFlowEodRow> = {}): VietnamProprietaryFlowEodRow => ({
  tradingDate: '2026-08-06',
  exchange: 'HOSE',
  buyVolume: null,
  sellVolume: null,
  netVolume: null,
  buyValue: 2_000_000_000,
  sellValue: 1_500_000_000,
  netValue: 500_000_000,
  sourceType: 'official_exchange_pdf_manual_entry',
  sourceUrl: 'https://example.test/official.pdf',
  sourceTitle: 'Công bố chính thức HOSE',
  sourceFileName: 'official.pdf',
  sourceFileHash: 'a'.repeat(64),
  sourceFileSize: 12,
  sourceEvidenceStrength: 'OFFICIAL_PDF_HASHED',
  verifiedByUser: true,
  importedAt: '2026-08-06T12:00:00Z',
  finality: 'completed_daily',
  completeValue: true,
  completeVolume: false,
  complete: true,
  dataQuality: 'accepted_value_only',
  warnings: [],
  ...overrides,
});

const setData = (rows: VietnamProprietaryFlowEodRow[] = [row()]) => {
  latest.mockResolvedValue({
    status: rows.length ? 'ok' : 'empty',
    dataState: rows.length ? 'ready' : 'no_data',
    exchange: 'HOSE',
    latest: rows.at(-1) ?? null,
    source: 'official_exchange_pdf_manual_entry',
    warnings: [],
  });
  history.mockResolvedValue({
    status: rows.length ? 'ok' : 'empty',
    dataState: rows.length ? 'ready' : 'no_data',
    exchange: 'HOSE',
    count: rows.length,
    series: rows,
    sourceSummary: { sourceType: 'official_exchange_pdf_manual_entry', finality: 'completed_daily', valueUnit: 'VND', volumeUnit: 'shares' },
    warnings: [],
  });
};

beforeEach(() => {
  vi.clearAllMocks();
  setData();
});

describe('ProprietaryFlowEodView', () => {
  it('uses one EOD request owner and renders completed source-backed values', async () => {
    render(<ProprietaryFlowEodView />);
    expect(await screen.findByRole('heading', { name: 'Dữ liệu tự doanh HOSE cuối ngày' })).toBeInTheDocument();
    await waitFor(() => expect(latest).toHaveBeenCalledTimes(1));
    expect(history).toHaveBeenCalledTimes(1);
    expect(current).not.toHaveBeenCalled();
    expect(currentAggregate).not.toHaveBeenCalled();
    const card = screen.getByRole('region', { name: 'Phiên tự doanh HOSE mới nhất' });
    expect(card).toHaveTextContent('2.00Tỷ');
    expect(card).toHaveTextContent('1.50Tỷ');
    expect(card).toHaveTextContent('500,000,000');
    expect(card).toHaveTextContent('2026-08-06');
    expect(card).toHaveTextContent('Đủ');
    expect(card).toHaveTextContent('PDF chính thức đã băm SHA-256');
    expect(within(card).getByRole('link', { name: 'Công bố chính thức HOSE' })).toHaveAttribute('href', 'https://example.test/official.pdf');
    expect(screen.queryByText(/Realtime|Đang diễn ra|Tạm tính|15 giây/i)).not.toBeInTheDocument();
  });

  it('keeps missing volumes as dash and explicit zero as zero', async () => {
    setData([
      row({ tradingDate: '2026-08-05' }),
      row({ tradingDate: '2026-08-06', buyVolume: 0, sellVolume: 0, netVolume: 0, completeVolume: true, dataQuality: 'accepted' }),
    ]);
    render(<ProprietaryFlowEodView />);
    const table = await screen.findByRole('table');
    const tableRows = within(table).getAllByRole('row');
    expect(tableRows[1]).toHaveTextContent('2026-08-05');
    expect(within(tableRows[1]).getAllByText('—')).toHaveLength(3);
    expect(tableRows[2]).toHaveTextContent('2026-08-06');
    expect(within(tableRows[2]).getAllByText('0')).toHaveLength(3);
  });

  it('orders history ascending and exposes positive negative and zero semantics', async () => {
    setData([
      row({ tradingDate: '2026-08-06', netValue: 0, buyValue: 100, sellValue: 100 }),
      row({ tradingDate: '2026-08-04', netValue: 10, buyValue: 110, sellValue: 100 }),
      row({ tradingDate: '2026-08-05', netValue: -10, buyValue: 90, sellValue: 100 }),
    ]);
    render(<ProprietaryFlowEodView />);
    const table = await screen.findByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((item) => item.textContent?.slice(0, 10))).toEqual(['2026-08-04', '2026-08-05', '2026-08-06']);
    expect(rows[0].querySelector('.text-success')).not.toBeNull();
    expect(rows[1].querySelector('.text-danger')).not.toBeNull();
    expect(rows[2].querySelector('.text-success, .text-danger')).toBeNull();
  });

  it('renders no-data and storage-error terminal states', async () => {
    setData([]);
    const view = render(<ProprietaryFlowEodView />);
    expect(await screen.findByText('Chưa có dữ liệu')).toBeInTheDocument();
    view.unmount();

    latest.mockResolvedValue({ status: 'error', dataState: 'storage_error', exchange: 'HOSE', latest: null, source: 'official_exchange_pdf_manual_entry', warnings: ['durable_store_unavailable'] });
    history.mockResolvedValue({ status: 'error', dataState: 'storage_error', exchange: 'HOSE', count: 0, series: [], sourceSummary: {}, warnings: ['durable_store_unavailable'] });
    render(<ProprietaryFlowEodView />);
    expect(await screen.findByText('Không khả dụng')).toBeInTheDocument();
  });

  it('keeps last-known-good data during refresh failure and suppresses refresh spam', async () => {
    render(<ProprietaryFlowEodView />);
    await screen.findAllByText('2026-08-06');
    let rejectLatest!: (reason?: unknown) => void;
    let rejectHistory!: (reason?: unknown) => void;
    latest.mockReturnValueOnce(new Promise((_, reject) => { rejectLatest = reject; }));
    history.mockReturnValueOnce(new Promise((_, reject) => { rejectHistory = reject; }));
    const refresh = screen.getByRole('button', { name: /Làm mới/ });
    fireEvent.click(refresh);
    fireEvent.click(refresh);
    expect(latest).toHaveBeenCalledTimes(2);
    expect(history).toHaveBeenCalledTimes(2);
    await act(async () => {
      rejectLatest(new Error('offline'));
      rejectHistory(new Error('offline'));
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('Đang giữ kết quả cuối cùng');
    expect(screen.getAllByText('2026-08-06')).toHaveLength(2);
  });

  it('does not poll after the initial request', async () => {
    vi.useFakeTimers();
    render(<ProprietaryFlowEodView />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { vi.advanceTimersByTime(60_000); });
    expect(latest).toHaveBeenCalledTimes(1);
    expect(history).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
