import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AlertTriggerHistory } from '../AlertTriggerHistory';

describe('AlertTriggerHistory', () => {
  it('shows sanitized VN provenance and its existing deep link', () => {
    render(<AlertTriggerHistory triggers={[{
      id: 1,
      ruleId: 7,
      target: 'FPT',
      observedValue: 3.2,
      threshold: 2,
      reason: 'FPT relative performance matched gt 2',
      dataSource: 'SSI completed-session analytics',
      dataTimestamp: '2026-08-10T00:00:00',
      status: 'triggered',
      diagnostics: JSON.stringify({
        family: 'vn_relative_strength', session: '2026-08-10',
        finality: 'completed_daily', deep_link: '/vietnam?ticker=FPT',
      }),
    }]} />);

    expect(screen.getByText(/Session 2026-08-10/)).toHaveTextContent('completed_daily');
    expect(screen.getByRole('link', { name: 'Open context' })).toHaveAttribute('href', '/vietnam?ticker=FPT');
    expect(screen.queryByText(/buy|sell now|opportunity/i)).not.toBeInTheDocument();
  });

  it('keeps explicit zero distinct from missing', () => {
    render(<AlertTriggerHistory triggers={[{
      id: 2, target: 'VN30', observedValue: 0, threshold: 0,
      status: 'triggered', reason: 'Explicit zero matched equality',
    }]} />);
    expect(screen.getAllByText('0')).toHaveLength(2);
  });
});
