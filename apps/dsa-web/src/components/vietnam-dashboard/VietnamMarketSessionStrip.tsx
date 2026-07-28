import type React from 'react';
import { Activity, RefreshCw } from 'lucide-react';

import { Badge, Button } from '../common';
import { cn } from '../../utils/cn';
import type { VietnamLiveChannelState } from './VietnamLiveMarketSummary';

type SessionStripState = VietnamLiveChannelState;

const stateVariant = (state: SessionStripState) => {
  if (state === 'ready') return 'success' as const;
  if (state === 'partial' || state === 'reconnecting' || state === 'stale') return 'warning' as const;
  if (state === 'unavailable' || state === 'error') return 'danger' as const;
  return 'default' as const;
};

export interface VietnamMarketSessionStripProps {
  universeLabel: string;
  marketPhase: string;
  completedSession?: string | null;
  liveState: SessionStripState;
  liveLabel: string;
  sourceLabel: string;
  freshnessLabel: string;
  refreshing?: boolean;
  refreshDisabled?: boolean;
  onRefresh: () => void;
  detailsHref?: string;
  className?: string;
}

export const VietnamMarketSessionStrip: React.FC<VietnamMarketSessionStripProps> = ({
  universeLabel,
  marketPhase,
  completedSession,
  liveState,
  liveLabel,
  sourceLabel,
  freshnessLabel,
  refreshing = false,
  refreshDisabled = false,
  onRefresh,
  detailsHref = '#vn-dashboard-data-details',
  className,
}) => (
  <section
    className={cn(
      'rounded-lg border border-border/70 bg-card px-4 py-3 shadow-soft-card',
      className,
    )}
    aria-label="Vietnam market session"
    data-testid="vietnam-market-session-strip"
  >
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
        <span className="inline-flex items-center gap-2 font-semibold text-foreground">
          <Activity className="h-4 w-4 text-cyan" aria-hidden="true" />
          {universeLabel}
        </span>
        <span className="text-xs text-secondary-text">{marketPhase}</span>
        <span className="text-xs text-secondary-text">
          Latest completed {completedSession || '—'}
        </span>
        <Badge variant={stateVariant(liveState)}>{liveLabel}</Badge>
        <span className="text-xs text-secondary-text">{sourceLabel}</span>
        <span className="text-xs text-secondary-text">{freshnessLabel}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <a
          href={detailsHref}
          className="inline-flex h-9 items-center rounded-lg px-3 text-sm font-medium text-secondary-text transition-colors hover:bg-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/25"
        >
          Data details
        </a>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={onRefresh}
          isLoading={refreshing}
          loadingText="Refreshing"
          disabled={refreshDisabled}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </div>
    </div>
  </section>
);
