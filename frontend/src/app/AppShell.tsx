import {
  AppBar,
  Box,
  Button,
  Divider,
  Drawer,
  Stack,
  Toolbar,
  Typography,
} from '@mui/material';
import { Link, Outlet, useRouterState } from '@tanstack/react-router';

const drawerWidth = 224;

const navigation = [
  { label: 'Overview', to: '/' },
  { label: 'Households', to: '/households' },
  { label: 'People', to: '/people' },
  { label: 'Cash flow', to: '/cash-flow' },
  { label: 'Properties', to: '/properties' },
  { label: 'Purchase plans', to: '/purchases' },
  { label: 'Retirement', to: '/retirement' },
  { label: 'Timeline', to: '/timeline' },
  { label: 'Scenarios', to: '/scenarios' },
  { label: 'Settings', to: '/settings' },
] as const;

export function AppShell() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', minWidth: 1024 }}>
      <AppBar
        color="inherit"
        elevation={0}
        position="fixed"
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          ml: `${drawerWidth}px`,
          width: `calc(100% - ${drawerWidth}px)`,
        }}
      >
        <Toolbar>
          <Typography component="span" sx={{ fontWeight: 700 }}>
            Household Financial Planner
          </Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Typography color="text.secondary" variant="body2">
            React preview
          </Typography>
        </Toolbar>
      </AppBar>
      <Drawer
        slotProps={{ paper: { component: 'nav' } }}
        sx={{
          flexShrink: 0,
          width: drawerWidth,
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            width: drawerWidth,
          },
        }}
        variant="permanent"
      >
        <Toolbar>
          <Typography color="primary" sx={{ fontWeight: 800 }} variant="h6">
            HFP
          </Typography>
        </Toolbar>
        <Divider />
        <Stack spacing={0.5} sx={{ p: 1.5 }}>
          {navigation.map((item) => (
            <Button
              component={Link}
              key={item.to}
              sx={{ justifyContent: 'flex-start' }}
              to={item.to}
              variant={pathname === item.to ? 'contained' : 'text'}
            >
              {item.label}
            </Button>
          ))}
        </Stack>
      </Drawer>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          mt: 8,
          p: 4,
          width: `calc(100% - ${drawerWidth}px)`,
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}
