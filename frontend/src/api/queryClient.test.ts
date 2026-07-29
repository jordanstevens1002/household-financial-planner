import { ApiError } from './client';
import { shouldRetry } from './queryClient';

describe('shouldRetry', () => {
  it('does not retry errors which require user action', () => {
    for (const kind of ['unauthorised', 'forbidden', 'validation'] as const) {
      expect(shouldRetry(0, new ApiError('No retry', kind, 400))).toBe(false);
    }
  });

  it('limits transient failures to two retries', () => {
    expect(shouldRetry(0, new Error('Network'))).toBe(true);
    expect(shouldRetry(1, new Error('Network'))).toBe(true);
    expect(shouldRetry(2, new Error('Network'))).toBe(false);
  });
});
