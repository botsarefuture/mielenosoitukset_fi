import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  // Relative imports keep the build compatible with Flask's static URL prefix.
  base: './',
  build: {
    outDir: '../mielenosoitukset_fi/static/frontend',
    emptyOutDir: true,
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        volunteer: fileURLToPath(new URL('./src/entries/volunteer.tsx', import.meta.url)),
      },
    },
  },
});
