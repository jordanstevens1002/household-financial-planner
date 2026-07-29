import { createTheme } from '@mui/material';

export const appTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#315b4c',
      dark: '#214438',
      light: '#dce9e3',
    },
    secondary: {
      main: '#a4582c',
    },
    background: {
      default: '#f4f7f5',
      paper: '#ffffff',
    },
  },
  shape: {
    borderRadius: 10,
  },
  typography: {
    fontFamily: '"Inter", "Segoe UI", sans-serif',
    h1: {
      fontSize: '2rem',
      fontWeight: 700,
    },
    h2: {
      fontSize: '1.5rem',
      fontWeight: 700,
    },
  },
  components: {
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          textTransform: 'none',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
  },
});
