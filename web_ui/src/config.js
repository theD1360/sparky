/**
 * Backend connection config.
 *
 * Browser calls the API directly (no CRA proxy). In Docker the UI container
 * sets REACT_APP_API_URL to the host-published API address (localhost:8000).
 * When unset (e.g. same-origin production static mount), paths stay relative.
 */

function resolveApiOrigin() {
  const explicit = (process.env.REACT_APP_API_URL || '').trim();
  if (explicit) {
    return explicit.replace(/\/$/, '');
  }
  const host = (process.env.REACT_APP_API_HOST || '').trim();
  if (host) {
    const port = process.env.REACT_APP_API_PORT || '8000';
    return `http://${host}:${port}`;
  }
  return '';
}

/** Absolute API origin, or '' for same-origin relative paths. */
export const API_ORIGIN = resolveApiOrigin();

/**
 * Build a full URL for a backend path.
 * @param {string} path - Absolute path on the API (e.g. '/api/auth/me')
 * @returns {string}
 */
export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return API_ORIGIN ? `${API_ORIGIN}${normalized}` : normalized;
}

/**
 * WebSocket URL for the chat channel.
 * Prefers REACT_APP_WS_* when set; otherwise derives from API_ORIGIN.
 * @param {string|null|undefined} token
 * @returns {string}
 */
export function getChatWsUrl(token) {
  let wsOrigin;
  const wsHost = (process.env.REACT_APP_WS_HOST || '').trim();
  if (wsHost) {
    const useTls =
      API_ORIGIN.startsWith('https') || window.location.protocol === 'https:';
    const proto = useTls ? 'wss:' : 'ws:';
    const port = process.env.REACT_APP_WS_PORT || '8000';
    wsOrigin = `${proto}//${wsHost}:${port}`;
  } else if (API_ORIGIN) {
    wsOrigin = API_ORIGIN.replace(/^https/i, 'wss').replace(/^http/i, 'ws');
  } else {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const port = process.env.REACT_APP_WS_PORT || '8000';
    wsOrigin = `${proto}//${window.location.hostname}:${port}`;
  }

  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${wsOrigin}/ws/chat${tokenParam}`;
}
