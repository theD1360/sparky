import { createTheme } from '@mui/material/styles';

/**
 * Base theme configuration shared across all themes
 */
const baseTheme = {
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
};

/**
 * Theme color palettes
 */
const themePalettes = {
  blue: {
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
  purple: {
    mode: 'dark',
    primary: {
      main: '#a855f7',
      light: '#c084fc',
      dark: '#9333ea',
    },
    secondary: {
      main: '#ec4899',
    },
    background: {
      default: '#0a0a1a',
      paper: '#1a1025',
    },
    text: {
      primary: '#f1f5f9',
      secondary: '#94a3b8',
    },
    divider: '#2d1b3d',
    action: {
      hover: 'rgba(255, 255, 255, 0.05)',
      selected: 'rgba(168, 85, 247, 0.15)',
    },
  },
  green: {
    mode: 'dark',
    primary: {
      main: '#10b981',
      light: '#34d399',
      dark: '#059669',
    },
    secondary: {
      main: '#14b8a6',
    },
    background: {
      default: '#0a1a14',
      paper: '#0f1e18',
    },
    text: {
      primary: '#f1f5f9',
      secondary: '#94a3b8',
    },
    divider: '#1f3a2d',
    action: {
      hover: 'rgba(255, 255, 255, 0.05)',
      selected: 'rgba(16, 185, 129, 0.15)',
    },
  },
  orange: {
    mode: 'dark',
    primary: {
      main: '#f59e0b',
      light: '#fbbf24',
      dark: '#d97706',
    },
    secondary: {
      main: '#f97316',
    },
    background: {
      default: '#1a0f0a',
      paper: '#1f1510',
    },
    text: {
      primary: '#f1f5f9',
      secondary: '#94a3b8',
    },
    divider: '#3a2d1f',
    action: {
      hover: 'rgba(255, 255, 255, 0.05)',
      selected: 'rgba(245, 158, 11, 0.15)',
    },
  },
};

/**
 * Create a theme based on color selection
 * @param {string} colorTheme - Theme color name (blue, purple, green, orange)
 * @returns {Object} MUI theme object
 */
export const createAppTheme = (colorTheme = 'blue') => {
  const palette = themePalettes[colorTheme] || themePalettes.blue;
  
  return createTheme({
    ...baseTheme,
    palette,
  });
};

/**
 * Default theme (blue)
 */
export const theme = createAppTheme('blue');

/**
 * Get all available themes
 * @returns {Array<Object>} Array of theme options
 */
export const getAvailableThemes = () => [
  { name: 'blue', label: 'Ocean Blue', color: '#3b82f6' },
  { name: 'purple', label: 'Purple Haze', color: '#a855f7' },
  { name: 'green', label: 'Forest Green', color: '#10b981' },
  { name: 'orange', label: 'Sunset Orange', color: '#f59e0b' },
];

