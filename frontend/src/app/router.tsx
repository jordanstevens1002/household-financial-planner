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

const householdsRoute = createRoute({
  component: lazyRouteComponent(
    () => import('../features/households/HouseholdsPage'),
    'HouseholdsPage',
  ),
  getParentRoute: () => rootRoute,
  path: '/households',
});

const settingsRoute = createRoute({
  component: lazyRouteComponent(
    () => import('../features/settings/SettingsPage'),
    'SettingsPage',
  ),
  getParentRoute: () => rootRoute,
  path: '/settings',
});

const peopleRoute = createRoute({
  component: lazyRouteComponent(
    () => import('../features/people/PeoplePage'),
    'PeoplePage',
  ),
  getParentRoute: () => rootRoute,
  path: '/people',
});

const incomeRoute = createRoute({
  component: lazyRouteComponent(
    () => import('../features/income/IncomePage'),
    'IncomePage',
  ),
  getParentRoute: () => rootRoute,
  path: '/income',
});

const cashFlowRoute = createRoute({
  component: lazyRouteComponent(
    () => import('../features/cashflow/CashFlowPage'),
    'CashFlowPage',
  ),
  getParentRoute: () => rootRoute,
  path: '/cash-flow',
});

function placeholderRoute(
  path:
    | '/households'
    | '/properties'
    | '/purchases'
    | '/retirement'
    | '/scenarios'
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
  householdsRoute,
  peopleRoute,
  incomeRoute,
  cashFlowRoute,
  placeholderRoute('/properties'),
  placeholderRoute('/purchases'),
  placeholderRoute('/retirement'),
  placeholderRoute('/timeline'),
  placeholderRoute('/scenarios'),
  settingsRoute,
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
