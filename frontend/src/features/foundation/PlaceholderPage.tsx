import { useRouterState } from '@tanstack/react-router';

import { EmptyState } from '../../shared/EmptyState';

const pageNames: Record<string, string> = {
  '/cash-flow': 'Cash flow',
  '/households': 'Households',
  '/people': 'People',
  '/properties': 'Properties',
  '/purchases': 'Purchase plans',
  '/retirement': 'Retirement',
  '/scenarios': 'Scenarios',
  '/settings': 'Settings',
  '/timeline': 'Timeline',
};

export function PlaceholderPage() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const title = pageNames[pathname] ?? 'Planned workflow';

  return (
    <EmptyState
      description="This area is reserved in the application shell. Keep using Appsmith until its tested React migration is complete."
      title={`${title} is coming soon`}
    />
  );
}
