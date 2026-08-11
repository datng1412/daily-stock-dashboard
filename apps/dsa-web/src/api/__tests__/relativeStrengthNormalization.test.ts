import { describe, expect, it } from 'vitest';

import { toCamelCase } from '../utils';
import { normalizeVietnamRelativeStrengthResponse } from '../stocks';

describe('relative strength API normalization', () => {
  it('normalizes percentage-point and session fields while preserving window keys', () => {
    const camel = toCamelCase<Record<string, unknown>>({
      comparisons: {
        vnindex: {
          windows: {
            '1d': { relative_performance_pp: 1.25, start_session: '2026-08-07' },
          },
        },
        vn30: { windows: {} },
        industry: { windows: {} },
      },
    });
    const normalized = normalizeVietnamRelativeStrengthResponse(camel as never);
    expect(normalized.comparisons.vnindex.windows['1d'].relativePerformancePp).toBe(1.25);
    expect(normalized.comparisons.vnindex.windows['1d'].startSession).toBe('2026-08-07');
    expect((camel as { comparisons: { vnindex: { windows: Record<string, unknown> } } }).comparisons.vnindex.windows['1D']).toBeDefined();
  });
});
