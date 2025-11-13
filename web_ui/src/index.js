import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import App from './App';
import { Admin } from './pages';
import { createAppTheme } from './styles/themes';
import reportWebVitals from './reportWebVitals';

/**
 * Root component with theme switching support
 */
function Root() {
  const [currentTheme, setCurrentTheme] = useState(() => {
    // Load theme from localStorage
    try {
      const saved = localStorage.getItem('sparky_settings');
      if (saved) {
        const settings = JSON.parse(saved);
        return createAppTheme(settings.theme || 'blue');
      }
    } catch (error) {
      console.error('Error loading theme:', error);
    }
    return createAppTheme('blue');
  });

  // Listen for theme changes
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === 'sparky_settings') {
        try {
          const settings = JSON.parse(e.newValue);
          if (settings.theme) {
            setCurrentTheme(createAppTheme(settings.theme));
          }
        } catch (error) {
          console.error('Error updating theme:', error);
        }
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const handleThemeChange = (themeName) => {
    setCurrentTheme(createAppTheme(themeName));
  };

  return (
    <ThemeProvider theme={currentTheme}>
      <CssBaseline />
      <Routes>
        <Route path="/" element={<App onThemeChange={handleThemeChange} />} />
        <Route path="/chat" element={<App onThemeChange={handleThemeChange} />} />
        <Route path="/chat/:chatId" element={<App onThemeChange={handleThemeChange} />} />
        <Route path="/admin" element={<Admin />} />
      </Routes>
    </ThemeProvider>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <Root />
    </BrowserRouter>
  </React.StrictMode>
);

reportWebVitals();
