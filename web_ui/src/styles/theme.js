import { createTheme } from '@mui/material/styles';

// Create a dark, sleek theme for Sparky Studio
export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#3b82f6',
      light: '#60a5fa',
      dark: '#2563eb',
    },
    secondary: {
      main: '#8b5cf6',
    },
    background: {
      default: '#0a0e1a',
      paper: '#111827',
    },
    text: {
      primary: '#f1f5f9',
      secondary: '#94a3b8',
    },
    divider: '#1f2937',
    action: {
      hover: 'rgba(255, 255, 255, 0.05)',
      selected: 'rgba(59, 130, 246, 0.15)',
    },
  },
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif',
    h6: {
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: '#374151 #0a0e1a',
          '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
            width: 8,
            height: 8,
          },
          '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
            borderRadius: 8,
            backgroundColor: '#374151',
          },
          '&::-webkit-scrollbar-thumb:hover, & *::-webkit-scrollbar-thumb:hover': {
            backgroundColor: '#4b5563',
          },
          '&::-webkit-scrollbar-track, & *::-webkit-scrollbar-track': {
            backgroundColor: '#0a0e1a',
          },
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
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundImage: 'none',
          borderColor: '#1f2937',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
        },
      },
    },
  },
});

