import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

/**
 * Client bundle for the standalone public app.
 *
 * It is built separately from the Flask islands so the two can be deployed
 * independently. Output stays outside the committed island assets.
 */
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  base: '/app-assets/',
  build: {
    outDir: 'dist/client',
    emptyOutDir: true,
    manifest: true,
    target: 'es2022',
    rollupOptions: {
      input: { app: fileURLToPath(new URL('./src/app/client.tsx', import.meta.url)) },
    },
  },
});
