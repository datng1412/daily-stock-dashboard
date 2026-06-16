import { render, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPanelErrorBoundary } from '../SettingsPanelErrorBoundary';

function ThrowingPanel({ message = 'mock settings panel crash' }: { message?: string }): ReactElement {
  throw new Error(message);
}

describe('SettingsPanelErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a configurable desktop-log diagnostic fallback when a settings panel throws', () => {
    render(
      <SettingsPanelErrorBoundary
        title="NotificationSettings"
        resetKey="notification"
        diagnosticHint={(
          <>
            Review and provide the desktop logs
            <code>desktop.log</code>
            , plus the release version, Windows version, and entry point.
          </>
        )}
      >
        <ThrowingPanel />
      </SettingsPanelErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('NotificationSettings failed to load')).toBeInTheDocument();
    expect(screen.getByText('desktop.log')).toBeInTheDocument();
    expect(screen.getByText(/release version, Windows version, and entry point/)).toBeInTheDocument();
    expect(screen.getByText(/Error summary: mock settings panel crash/)).toBeInTheDocument();
  });

  it('redacts and truncates sensitive error summary text', () => {
    render(
      <SettingsPanelErrorBoundary title="NotificationSettings" resetKey="notification">
        <ThrowingPanel
          message={`Webhook failed: https://hooks.slack.com/services/T000/B000/path-secret?token=super-secret-token&foo=bar OPENAI_API_KEY=sk-supersecretvalue123456 ${'x'.repeat(220)}`}
        />
      </SettingsPanelErrorBoundary>
    );

    const summary = screen.getByText(/Error summary: /).textContent ?? '';

    expect(summary).toContain('https://hooks.slack.com/[redacted]?[redacted]');
    expect(summary).toContain('?[redacted]');
    expect(summary).toContain('OPENAI_API_KEY=[redacted]');
    expect(summary).not.toContain('/services/T000/B000/path-secret');
    expect(summary).not.toContain('path-secret');
    expect(summary).not.toContain('super-secret-token');
    expect(summary).not.toContain('sk-supersecretvalue123456');
    expect(summary.length).toBeLessThanOrEqual('Error summary: '.length + 183);
  });

  it('resets after resetKey changes so the panel can render again', async () => {
    const { rerender } = render(
      <SettingsPanelErrorBoundary title="Agent Settings" resetKey="agent:v1">
        <ThrowingPanel />
      </SettingsPanelErrorBoundary>
    );

    expect(screen.getByText('Agent Settings failed to load')).toBeInTheDocument();

    rerender(
      <SettingsPanelErrorBoundary title="Agent Settings" resetKey="agent:v2">
        <div>Agent settings recovered</div>
      </SettingsPanelErrorBoundary>
    );

    await waitFor(() => {
      expect(screen.getByText('Agent settings recovered')).toBeInTheDocument();
    });
    expect(screen.queryByText('Agent Settings failed to load')).not.toBeInTheDocument();
  });
});
