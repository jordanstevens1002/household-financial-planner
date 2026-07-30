import {
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
} from '@tanstack/react-router';

import { AuthenticatedApp } from '../features/auth/AuthenticatedApp';
import { RouteError } from './RouteError';

const rootRoute = createRootRoute({
  component: AuthenticatedApp,
  errorComponent: RouteError,
  notFoundComponent: lazyRouteComponent(
    () => import('../features/foundation/NotFoundPage'),
    'NotFoundPage',
  ),
});

const indexRoute = createRoute({
  component: lazyRouteComponent(
    () => import('../features/foundation/OverviewPage'),
    'OverviewPage',
  ),
  getParentRoute: () => rootRoute,
  path: '/',
});

function placeholderRoute(
  path:
    | '/cash-flow'
    | '/households'
    | '/people'
    | '/properties'
    | '/purchases'
    | '/retirement'
    | '/scenarios'
    | '/settings'
    | '/timeline',
) {
  return createRoute({
    component: lazyRouteComponent(
      () => import('../features/foundation/PlaceholderPage'),
      'PlaceholderPage',
    ),
    getParentRoute: () => rootRoute,
    path,
  });
}

const routeTree = rootRoute.addChildren([
  indexRoute,
  placeholderRoute('/households'),
  placeholderRoute('/people'),
  placeholderRoute('/cash-flow'),
  placeholderRoute('/properties'),
  placeholderRoute('/purchases'),
  placeholderRoute('/retirement'),
  placeholderRoute('/timeline'),
  placeholderRoute('/scenarios'),
  placeholderRoute('/settings'),
]);

export function createAppRouter() {
  return createRouter({
    defaultPreload: 'intent',
    routeTree,
  });
}

export const router = createAppRouter();

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
