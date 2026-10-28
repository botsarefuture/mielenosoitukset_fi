import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  // Relative imports keep the build compatible with Flask's static URL prefix.
  base: './',
  plugins: [{
    name: 'runtime-license-notices',
    generateBundle() {
      const notices = ['react', 'react-dom', 'scheduler', 'vite'].map((name) => {
        const filename = name === 'vite' ? 'LICENSE.md' : 'LICENSE';
        const license = readFileSync(new URL(`../node_modules/${name}/${filename}`, import.meta.url), 'utf8');
        return `${name}\n${license.replace(/[ \t]+$/gm, '')}`;
      });
      this.emitFile({ type: 'asset', fileName: 'THIRD_PARTY_LICENSES.txt', source: notices.join('\n\n') });
    },
  }],
  build: {
    outDir: '../mielenosoitukset_fi/static/frontend',
    emptyOutDir: true,
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        pride: fileURLToPath(new URL('./src/entries/pride.tsx', import.meta.url)),
        submit: fileURLToPath(new URL('./src/entries/submit.tsx', import.meta.url)),
        listing: fileURLToPath(new URL('./src/entries/listing.tsx', import.meta.url)),
        header: fileURLToPath(new URL('./src/entries/header.tsx', import.meta.url)),
        campaign: fileURLToPath(new URL('./src/entries/campaign.tsx', import.meta.url)),
        confirmation: fileURLToPath(new URL('./src/entries/confirmation.tsx', import.meta.url)),
        volunteer: fileURLToPath(new URL('./src/entries/volunteer.tsx', import.meta.url)),
      },
    },
  },
});
