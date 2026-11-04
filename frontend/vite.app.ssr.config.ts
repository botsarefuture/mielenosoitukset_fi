import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

/**
 * Server bundle for the standalone public app.
 *
 * Only the document head is rendered on the server; page components are not
 * rendered there. Dependencies are bundled so the runtime needs no node_modules.
 */
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  ssr: { noExternal: true },
  build: {
    outDir: 'dist/server',
    emptyOutDir: true,
    ssr: 'src/app/render.tsx',
    target: 'node22',
    rollupOptions: { output: { format: 'es' } },
  },
});
