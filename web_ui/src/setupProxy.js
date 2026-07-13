/**
 * Dev-server middleware for CRA.
 *
 * API calls go directly to the backend (see src/config.js + CORS on FastAPI).
 * This file only sets COEP/COOP headers needed for SharedArrayBuffer / speech WASM.
 */
module.exports = function setupProxy(app) {
  app.use((req, res, next) => {
    // Enable cross-origin isolation for SharedArrayBuffer (multi-threaded WASM).
    // 'credentialless' allows CDN resources while enabling SharedArrayBuffer.
    res.setHeader('Cross-Origin-Embedder-Policy', 'credentialless');
    res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
    res.setHeader('Cross-Origin-Resource-Policy', 'cross-origin');
    next();
  });

  console.log('✓ Dev headers configured (no API proxy — browser calls REACT_APP_API_URL directly)');
};
