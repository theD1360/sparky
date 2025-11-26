import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import App from './App';
import { Admin } from './pages';
import { AuthProvider } from './components/auth/AuthProvider';
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import ProtectedRoute from './components/auth/ProtectedRoute';
import { createAppTheme } from './styles/themes';
import reportWebVitals from './reportWebVitals';
import { configureTransformers } from './utils/transformersConfig';
import './utils/clearModelCache'; // Import to expose cache utilities globally

// Note: Transformers configuration is now handled in the worker (speechWorker.js)
// This main-thread configuration is kept as a fallback for any other potential uses
// The worker loads and configures transformers independently from CDN
configureTransformers();

// Log cache utilities availability
console.log('🧹 Cache utilities loaded. Use window.clearModelCaches() if models fail to load.');

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
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          {/* Home page is public - no authentication required */}
          <Route
            path="/"
            element={<App onThemeChange={handleThemeChange} />}
          />
          {/* Chat routes require authentication */}
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <App onThemeChange={handleThemeChange} />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat/:chatId"
            element={
              <ProtectedRoute>
                <App onThemeChange={handleThemeChange} />
              </ProtectedRoute>
            }
          />
          {/* Admin routes require authentication and admin role */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireAdmin>
                <Admin />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/*"
            element={
              <ProtectedRoute requireAdmin>
                <Admin />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
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
