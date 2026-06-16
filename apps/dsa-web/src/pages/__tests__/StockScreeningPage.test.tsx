import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StockScreeningPage from '../StockScreeningPage';

const { enableAlphaSift, getAlphaSiftStatus, getStrategies, screenStocks } = vi.hoisted(() => ({
  enableAlphaSift: vi.fn(),
  getAlphaSiftStatus: vi.fn(),
  getStrategies: vi.fn(),
  screenStocks: vi.fn(),
}));

vi.mock('../../api/alphasift', () => ({
  alphasiftApi: {
    enable: (...args: unknown[]) => enableAlphaSift(...args),
    getStatus: (...args: unknown[]) => getAlphaSiftStatus(...args),
    getStrategies: (...args: unknown[]) => getStrategies(...args),
    screen: (...args: unknown[]) => screenStocks(...args),
  },
}));

const mockStrategiesResponse = {
  enabled: true,
  strategies: [
    {
      id: 'dual_low',
      name: 'Dual Low',
      title: 'Dual Low',
      description: 'Low valuation strategy',
      category: 'value',
      tag: 'value',
      tags: ['value'],
      marketScope: ['cn'],
    },
  ],
  strategyCount: 1,
};

describe('StockScreeningPage', () => {
  beforeEach(() => {
    enableAlphaSift.mockReset();
    getAlphaSiftStatus.mockReset();
    getStrategies.mockReset();
    screenStocks.mockReset();
    getStrategies.mockResolvedValue(mockStrategiesResponse);
  });

  it('re-syncs enabled state when AlphaSift install fails after config is enabled', async () => {
    getAlphaSiftStatus
      .mockResolvedValueOnce({
        enabled: false,
        available: false,
        installSpecIsDefault: true,
      })
      .mockResolvedValueOnce({
        enabled: true,
        available: false,
        installSpecIsDefault: true,
      });
    enableAlphaSift.mockRejectedValueOnce(new Error('Failed to install AlphaSift'));

    render(<StockScreeningPage />);

    expect(await screen.findByText('Screening disabled')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run screening/ })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Enable AlphaSift' }));

    await waitFor(() => expect(getAlphaSiftStatus).toHaveBeenCalledTimes(2));
    expect(screen.getByText('Screening enabled')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run screening/ })).not.toBeDisabled();
    expect(screen.getByText('Failed to install AlphaSift')).toBeInTheDocument();
  });

  it('shows input strategy when strategy is not in preset list', async () => {
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: false,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValue({
      enabled: true,
      candidates: [],
      candidateCount: 0,
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('Screening enabled')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Strategy parameter'), {
      target: { value: 'custom_strategy_alpha' },
    });

    expect(screen.getByDisplayValue('custom_strategy_alpha')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Run screening/ }));
    await waitFor(() => expect(screenStocks).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText(/CustomStrategy \(custom_strategy_alpha\)/)).toBeInTheDocument());
  });

  it('uses supported AlphaSift strategy ids and cn market', async () => {
    getStrategies.mockResolvedValueOnce({
      enabled: true,
      strategies: [
        { id: 'balanced_alpha', name: 'Balanced screening', description: 'desc', category: 'Framework' },
        { id: 'capital_heat', name: 'Capital heat', description: 'desc', category: 'Momentum' },
        { id: 'dual_low', name: 'Dual-low', description: 'desc', category: 'Value' },
        { id: 'oversold_reversal', name: 'Oversold', description: 'desc', category: 'Reversal' },
        { id: 'shrink_pullback', name: 'Low-volume pullback', description: 'desc', category: 'Trend' },
      ],
      strategyCount: 5,
    });
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: false,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValue({
      enabled: true,
      candidates: [],
      candidateCount: 0,
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('Screening enabled')).toBeInTheDocument();

    const marketSelect = screen.getByLabelText('Market') as HTMLSelectElement;
    expect(Array.from(marketSelect.options).map((option) => option.value)).toEqual(['cn']);

    [
      ['Balanced screening', 'balanced_alpha'],
      ['Capital heat', 'capital_heat'],
      ['Oversold', 'oversold_reversal'],
      ['Low-volume pullback', 'shrink_pullback'],
    ].forEach(([label, id]) => {
      fireEvent.click(screen.getByRole('button', { name: new RegExp(label) }));
      expect(screen.getByDisplayValue(id)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Run screening/ }));
    await waitFor(() => expect(screenStocks).toHaveBeenCalledTimes(1));
    expect(screenStocks).toHaveBeenCalledWith({
      market: 'cn',
      strategy: 'shrink_pullback',
      maxResults: 3,
    });
  });

  it('clears previous screening candidates when strategy changes', async () => {
    getStrategies.mockResolvedValueOnce({
      enabled: true,
      strategies: [
        { id: 'dual_low', name: 'Dual-low screening', description: 'desc', category: 'Value' },
        { id: 'capital_heat', name: 'Capital heat', description: 'desc', category: 'Momentum' },
      ],
      strategyCount: 2,
    });
    getAlphaSiftStatus.mockResolvedValueOnce({
      enabled: true,
      available: true,
      installSpecIsDefault: true,
    });
    screenStocks.mockResolvedValueOnce({
      enabled: true,
      candidates: [
        {
          rank: 1,
          code: '000001',
          name: 'Old strategy stock',
          score: 88.5,
          reason: 'old result',
          raw: {},
        },
      ],
      candidateCount: 1,
    });

    render(<StockScreeningPage />);

    expect(await screen.findByText('Screening enabled')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Run screening/ }));

    expect(await screen.findByText('Old strategy stock')).toBeInTheDocument();
    expect(screen.getByText('Screening completed')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Capital heat/ }));

    expect(screen.queryByText('Old strategy stock')).not.toBeInTheDocument();
    expect(screen.getByText('Waiting to run')).toBeInTheDocument();
    expect(screen.getByText('Current strategy: Capital heat · A-shares')).toBeInTheDocument();
  });
});
