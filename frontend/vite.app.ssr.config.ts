import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

/**
 * Server bundle for the standalone public app.
 *
 * Includes document metadata and server-rendered pages. Dependencies and compiled
 * API documentation are bundled so the runtime needs neither node_modules nor Python.
 */
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [{
    name: 'api-docs',
    resolveId(id) {
      if (id === 'virtual:api-docs') return '\0api-docs';
    },
    load(id) {
      if (id !== '\0api-docs') return;
      const compiler = fileURLToPath(new URL('./render-api-docs.py', import.meta.url));
      this.addWatchFile(compiler);
      this.addWatchFile(fileURLToPath(new URL('../docs/api.md', import.meta.url)));
      const document = execFileSync('python3', [compiler], { encoding: 'utf8' });
      return `export default ${document};`;
    },
  }],
  ssr: { noExternal: true },
  build: {
    outDir: 'dist/server',
    emptyOutDir: true,
    ssr: 'src/app/render.tsx',
    target: 'node22',
    rollupOptions: { output: { format: 'es' } },
  },
});
