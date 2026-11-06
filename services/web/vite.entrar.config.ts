// Build da tela de login, à parte do app: é o único conteúdo público do site.
// Sai em dist-entrar/ e é servido em /entrar/ sem sessão; o resto (dist/) exige login.
import { resolve } from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  root: resolve(__dirname, 'entrar'),
  base: '/entrar/',
  publicDir: false,
  build: {
    outDir: resolve(__dirname, 'dist-entrar'),
    emptyOutDir: true,
  },
  css: {
    preprocessorOptions: {
      scss: { quietDeps: true },
    },
  },
});
