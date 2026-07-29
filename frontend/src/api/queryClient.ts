import { QueryClient } from '@tanstack/react-query';

import { ApiError } from './client';

export function shouldRetry(failureCount: number, error: Error): boolean {
  if (
    error instanceof ApiError &&
    ['forbidden', 'unauthorised', 'validation'].includes(error.kind)
  ) {
    return false;
  }
  return failureCount < 2;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    mutations: {
      retry: false,
    },
    queries: {
      refetchOnWindowFocus: false,
      retry: shouldRetry,
      staleTime: 30_000,
    },
  },
});
