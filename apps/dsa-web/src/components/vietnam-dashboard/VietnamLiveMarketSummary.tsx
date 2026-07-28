import type React from 'react';

import { Badge, Button } from '../common';

export type VietnamLiveChannelState =
  | 'ready'
  | 'partial'
  | 'unavailable'
  | 'disabled'
  | 'loading'
  | 'reconnecting'
  | 'no_data'
  | 'stale'
  | 'error';

export interface VietnamLiveChannelSummary {
  key: string;
  label: string;
  state: VietnamLiveChannelState;
  detail: string;
}

const stateVariant = (state: VietnamLiveChannelState) => {
  if (state === 'ready') return 'success' as const;
  if (state === 'partial' || state === 'reconnecting' || state === 'stale') return 'warning' as const;
  if (state === 'unavailable' || state === 'error') return 'danger' as const;
  return 'default' as const;
};

export interface VietnamLiveMarketSummaryProps {
  overallState: VietnamLiveChannelState;
  overallLabel: string;
  channels: VietnamLiveChannelSummary[];
  onShowDetails?: () => void;
}

export const VietnamLiveMarketSummary: React.FC<VietnamLiveMarketSummaryProps> = ({
  overallState,
  overallLabel,
  channels,
  onShowDetails,
}) => (
  <section
    className="rounded-lg border border-border/70 bg-card p-4"
    aria-labelledby="vietnam-live-market-summary-title"
    data-testid="vietnam-live-market-summary"
  >
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="vietnam-live-market-summary-title" className="text-base font-semibold text-foreground">
            Live market
          </h2>
          <Badge variant={stateVariant(overallState)}>{overallLabel}</Badge>
        </div>
        <p className="mt-1 text-xs text-secondary-text">
          Optional live channels remain independent from completed daily data.
        </p>
      </div>
      {onShowDetails ? (
        <Button type="button" variant="outline" size="sm" onClick={onShowDetails}>
          Show live details
        </Button>
      ) : null}
    </div>
    <dl className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {channels.map((channel) => (
        <div key={channel.key} className="rounded-lg border border-border/50 bg-elevated/35 px-3 py-2">
          <dt className="flex flex-wrap items-center justify-between gap-2 text-xs text-secondary-text">
            <span>{channel.label}</span>
            <Badge variant={stateVariant(channel.state)}>{channel.state}</Badge>
          </dt>
          <dd className="mt-1 text-sm font-medium text-foreground">{channel.detail}</dd>
        </div>
      ))}
    </dl>
  </section>
);
