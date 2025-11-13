const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
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

