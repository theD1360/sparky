const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Add CORS headers middleware for all responses
  app.use((req, res, next) => {
    // Enable cross-origin isolation for SharedArrayBuffer support (required for multi-threaded WASM)
    // Using 'credentialless' mode to allow external CDN access while enabling SharedArrayBuffer
    res.setHeader('Cross-Origin-Embedder-Policy', 'credentialless');
    res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
    
    // Allow cross-origin requests for our own resources
    res.setHeader('Cross-Origin-Resource-Policy', 'cross-origin');
    next();
  });

  // Proxy all /api/* requests to the backend server
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://server:8000',
      changeOrigin: true,
      logLevel: 'debug',
      onProxyReq: (proxyReq, req, res) => {
        console.log('Proxying:', req.method, req.path, '→', 'http://server:8000' + req.path);
      },
      onProxyRes: (proxyRes, req, res) => {
        // Ensure CORP header is set for proxied responses
        proxyRes.headers['cross-origin-resource-policy'] = 'cross-origin';
      },
      onError: (err, req, res) => {
        console.error('Proxy error:', err);
        res.writeHead(500, {
          'Content-Type': 'application/json',
        });
        res.end(JSON.stringify({ error: 'Proxy error', details: err.message }));
      },
    })
  );

  // Proxy WebSocket connections
  app.use(
    '/ws',
    createProxyMiddleware({
      target: 'http://server:8000',
      changeOrigin: true,
      ws: true,
      logLevel: 'debug',
    })
  );

  // Proxy file upload endpoint
  app.use(
    '/upload_file',
    createProxyMiddleware({
      target: 'http://server:8000',
      changeOrigin: true,
      logLevel: 'debug',
    })
  );

  // Proxy file thumbnail endpoint
  app.use(
    '/file_thumbnail',
    createProxyMiddleware({
      target: 'http://server:8000',
      changeOrigin: true,
      logLevel: 'debug',
    })
  );

  console.log('✓ Proxy configured for development server');
  console.log('  - /api/* → http://server:8000');
  console.log('  - /ws/* → http://server:8000 (WebSocket)');
  console.log('  - /upload_file → http://server:8000');
  console.log('  - /file_thumbnail → http://server:8000');
};

