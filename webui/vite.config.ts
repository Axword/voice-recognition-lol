import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

// Defaults to the app running on this machine. In Docker the panel lives in a
// sibling container, so compose sets LOLVOICE_API to http://panel:21337.
const apiTarget = process.env.LOLVOICE_API ?? 'http://127.0.0.1:21337';
const wsTarget = apiTarget.replace(/^http/, 'ws');

export default defineConfig({
  plugins: [preact()],
  base: '/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsDir: 'assets',
    target: 'es2020',
    cssCodeSplit: false,
    reportCompressedSize: true,
  },
  server: {
    port: 5173,
    strictPort: false,
    host: process.env.LOLVOICE_API ? '0.0.0.0' : 'localhost',
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: false,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
        changeOrigin: false,
      },
    },
  },
});
