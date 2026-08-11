import { describe, expect, it } from 'vitest';

import { toCamelCase } from '../utils';

describe('sector strength API normalization', () => {
  it('preserves camelcase-keys digit capitalization in the typed contract', () => {
    const normalized = toCamelCase<{ return1D: { value: number } }>({
      return_1d: { value: 0.0125 },
    });

    expect(normalized.return1D.value).toBe(0.0125);
  });
});
