import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [{
    name: 'science-spa-fallback',
    configureServer(server) {
      server.middlewares.use((request, _response, next) => {
        const path = (request.url || '').split('?')[0];
        if (path === '/science' || /^\/science\/(?!index\.html|src\/|assets\/)/.test(path)) request.url = '/science/index.html';
        next();
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((request, _response, next) => {
        const path = (request.url || '').split('?')[0];
        if (path === '/science' || /^\/science\/(?!index\.html|assets\/)/.test(path)) request.url = '/science/index.html';
        next();
      });
    },
  }],
  root: 'site',
  publicDir: 'public',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    target: 'es2022',
    rollupOptions: {
      input: {
        universe: resolve(import.meta.dirname, 'site/index.html'),
        science: resolve(import.meta.dirname, 'site/science/index.html'),
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 4173,
  },
});
