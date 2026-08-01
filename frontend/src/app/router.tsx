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

const administrationRoute = createRoute({
  component: lazyRouteComponent(
    () => import('../features/admin/AdminUsersPage'),
    'AdminUsersPage',
  ),
  getParentRoute: () => rootRoute,
  path: '/administration',
});

const legacyIdentityMigrationRoute = createRoute({
  component: lazyRouteComponent(
    () => import('../features/admin/LegacyIdentityMigrationPage'),
    'LegacyIdentityMigrationPage',
  ),
  getParentRoute: () => rootRoute,
  path: '/administration/legacy-identities',
});

const resetPasswordRoute = createRoute({
  component: () => null,
  getParentRoute: () => rootRoute,
  path: '/reset-password',
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
  administrationRoute,
  legacyIdentityMigrationRoute,
  resetPasswordRoute,
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
