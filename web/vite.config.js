import { defineConfig } from 'vite';

// base relativo: funciona em https://<usuario>.github.io/<repo>/ e em domínio próprio
export default defineConfig({
  base: './',
  build: { outDir: 'dist', assetsDir: 'assets', sourcemap: false },
});
