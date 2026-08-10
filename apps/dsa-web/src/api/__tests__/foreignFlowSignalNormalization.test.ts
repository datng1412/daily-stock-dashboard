import { describe, expect, it } from 'vitest';
import { normalizeVietnamForeignFlowSignals } from '../stocks';
import { toCamelCase } from '../utils';

const providerSignals = () => ({
  basis: 'foreign_net_value',
  source: 'ssi_fastconnect',
  source_endpoint: 'daily_stock_price',
  finality: 'daily_available',
  latest_completed_date: '2026-08-07',
  direction_1d: { state: 'distributing', net_value: -3, requested_sessions: 1, observed_sessions: 1, covered_sessions: 1, complete: true },
  direction_5d: { state: 'accumulating', net_value: 8, requested_sessions: 5, observed_sessions: 5, covered_sessions: 5, complete: true },
  direction_20d: { state: 'unavailable', net_value: null, requested_sessions: 20, observed_sessions: 18, covered_sessions: 18, complete: false },
  momentum: { state: 'decelerating', requested_sessions: 10, observed_sessions: 10, covered_sessions: 10, complete: true },
  reversal: { detected: true, from_direction: 'accumulating', to_direction: 'distributing' },
  intensity: { state: 'elevated', absolute_percentile_60d: 94.2, z_score_60d: -2.1, sample_count_60d: 60, threshold_basis: [] },
});

describe('normalizeVietnamForeignFlowSignals', () => {
  it('normalizes camelcase-keys numeric suffix casing at the API boundary', () => {
    const camel = toCamelCase<Record<string, unknown>>(providerSignals());

    expect(camel).toHaveProperty('direction1D');
    expect(camel).not.toHaveProperty('direction1d');

    const normalized = normalizeVietnamForeignFlowSignals(camel);
    expect(normalized?.direction1d.netValue).toBe(-3);
    expect(normalized?.direction5d.netValue).toBe(8);
    expect(normalized?.direction20d.complete).toBe(false);
    expect(normalized?.intensity).toMatchObject({
      absolutePercentile60d: 94.2,
      zScore60d: -2.1,
      sampleCount60d: 60,
    });
  });

  it('returns null for an incomplete signal object instead of exposing an unsafe shape', () => {
    const malformed = toCamelCase<Record<string, unknown>>(providerSignals());
    delete malformed.direction5D;

    expect(normalizeVietnamForeignFlowSignals(malformed)).toBeNull();
  });
});
