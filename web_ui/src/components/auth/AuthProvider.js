import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

/**
 * Decode JWT token to get expiration time
 * @param {string} token - JWT token
 * @returns {number|null} Expiration timestamp in milliseconds, or null if invalid
 */
const getTokenExpiration = (token) => {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    
    const payload = JSON.parse(atob(parts[1]));
    if (payload.exp) {
      // exp is in seconds, convert to milliseconds
      return payload.exp * 1000;
    }
    return null;
  } catch (error) {
    console.error('Error decoding token:', error);
    return null;
  }
};

/**
 * Check if token is expired or will expire soon
 * @param {string} token - JWT token
 * @param {number} bufferMinutes - Minutes before expiration to consider "soon" (default: 5)
 * @returns {boolean} True if token is expired or will expire soon
 */
const isTokenExpiringSoon = (token, bufferMinutes = 5) => {
  if (!token) return true;
  
  const expiration = getTokenExpiration(token);
  if (!expiration) return true;
  
  const now = Date.now();
  const bufferMs = bufferMinutes * 60 * 1000;
  
  return expiration <= (now + bufferMs);
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [refreshToken, setRefreshToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const refreshIntervalRef = useRef(null);

  const logout = useCallback(async () => {
    // Clear refresh interval
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }

    try {
      // Try to revoke token on server (optional - don't fail if it doesn't work)
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          await fetch('/api/auth/logout', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });
        } catch (error) {
          // Ignore logout API errors - still clear local state
          console.debug('Logout API call failed (non-critical):', error);
        }
      }
    } finally {
      // Always clear local state
      setUser(null);
      setToken(null);
      setRefreshToken(null);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_id'); // Remove old user_id
    }
  }, []);

  // Use refs to break circular dependency
  const refreshAccessTokenRef = useRef(null);
  const fetchUserInfoRef = useRef(null);

  const fetchUserInfo = useCallback(async (accessToken) => {
    try {
      const response = await fetch('/api/auth/me', {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        // Token might be expired, try to refresh
        const storedRefreshToken = localStorage.getItem('refresh_token');
        if (storedRefreshToken && refreshAccessTokenRef.current) {
          await refreshAccessTokenRef.current();
        } else {
          // No refresh token, clear auth
          logout();
        }
      }
    } catch (error) {
      console.error('Error fetching user info:', error);
      logout();
    } finally {
      setLoading(false);
    }
  }, [logout]);

  const refreshAccessToken = useCallback(async () => {
    try {
      const storedRefreshToken = localStorage.getItem('refresh_token');
      if (!storedRefreshToken) {
        logout();
        return;
      }

      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: storedRefreshToken }),
      });

      if (response.ok) {
        const data = await response.json();
        setToken(data.access_token);
        setRefreshToken(data.refresh_token);
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        // Fetch user info with new token
        if (fetchUserInfoRef.current) {
          await fetchUserInfoRef.current(data.access_token);
        }
        return true;
      } else {
        logout();
        return false;
      }
    } catch (error) {
      console.error('Error refreshing token:', error);
      logout();
      return false;
    }
  }, [logout]);

  // Update refs when functions change
  useEffect(() => {
    refreshAccessTokenRef.current = refreshAccessToken;
    fetchUserInfoRef.current = fetchUserInfo;
  }, [refreshAccessToken, fetchUserInfo]);

  // Load tokens from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('access_token');
    const storedRefreshToken = localStorage.getItem('refresh_token');
    
    if (storedToken) {
      setToken(storedToken);
      if (storedRefreshToken) {
        setRefreshToken(storedRefreshToken);
      }
      // Fetch user info
      fetchUserInfo(storedToken);
    } else {
      setLoading(false);
    }
  }, [fetchUserInfo]);

  const login = async (username, password) => {
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        const data = await response.json();
        setToken(data.access_token);
        setRefreshToken(data.refresh_token);
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        
        // Fetch user info
        await fetchUserInfo(data.access_token);
        return { success: true };
      } else {
        const error = await response.json();
        return { success: false, error: error.detail || 'Login failed' };
      }
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: 'Network error' };
    }
  };

  const register = async (username, email, password) => {
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, email, password }),
      });

      if (response.ok) {
        const userData = await response.json();
        // After registration, user needs to login
        return { success: true, user: userData };
      } else {
        const error = await response.json();
        return { success: false, error: error.detail || 'Registration failed' };
      }
    } catch (error) {
      console.error('Registration error:', error);
      return { success: false, error: 'Network error' };
    }
  };

  const getAuthHeaders = () => {
    if (token) {
      return {
        'Authorization': `Bearer ${token}`,
      };
    }
    return {};
  };

  // Set up automatic token refresh before expiration
  useEffect(() => {
    if (!token) {
      // Clear interval if no token
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
      return;
    }

    // Check token expiration and set up refresh interval
    const checkAndRefreshToken = async () => {
      const currentToken = localStorage.getItem('access_token');
      if (!currentToken) {
        return;
      }

      // Refresh if token is expiring soon (within 5 minutes)
      if (isTokenExpiringSoon(currentToken, 5)) {
        console.log('Token expiring soon, refreshing...');
        await refreshAccessToken();
      }
    };

    // Check immediately
    checkAndRefreshToken();

    // Set up interval to check every 5 minutes
    refreshIntervalRef.current = setInterval(checkAndRefreshToken, 5 * 60 * 1000);

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
    };
  }, [token, refreshAccessToken]);

  // Handle page visibility changes (e.g., machine waking from sleep)
  useEffect(() => {
    const handleVisibilityChange = async () => {
      if (document.visibilityState === 'visible' && token) {
        // Page became visible, check if token needs refresh
        const currentToken = localStorage.getItem('access_token');
        if (currentToken && isTokenExpiringSoon(currentToken, 0)) {
          console.log('Page visible and token expired/expiring, refreshing...');
          await refreshAccessToken();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [token, refreshAccessToken]);

  // Handle window focus (another indicator of user returning)
  useEffect(() => {
    const handleFocus = async () => {
      if (token) {
        const currentToken = localStorage.getItem('access_token');
        if (currentToken && isTokenExpiringSoon(currentToken, 0)) {
          console.log('Window focused and token expired/expiring, refreshing...');
          await refreshAccessToken();
        }
      }
    };

    window.addEventListener('focus', handleFocus);

    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [token, refreshAccessToken]);

  const value = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    loading,
    login,
    register,
    logout,
    getAuthHeaders,
    refreshAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

