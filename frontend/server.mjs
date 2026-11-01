// Public app host: metadata-only rendering plus the client bundle.
//
// It renders the document head, an empty app root and the bootstrap JSON. Page
// components and event data are fetched and rendered by the browser, so a page
// request does no React rendering and no event query.
import { createServer } from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { readFile, realpath, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('.', import.meta.url)));
const clientDir = join(root, 'dist', 'client');
const manifestPath = join(clientDir, '.vite', 'manifest.json');

const port = Number(process.env.APP_PORT || 8090);
const origin = (process.env.APP_ORIGIN || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
const apiBase = (process.env.PUBLIC_API_BASE || 'https://api.mielenosoitukset.fi/api').replace(/\/+$/, '');
const flaskOrigin = (process.env.FLASK_API_ORIGIN || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const sessionUrl = process.env.SESSION_URL || `${flaskOrigin}/api/session`;
const flaskSocketPath = process.env.FLASK_SOCKET_PATH || undefined;
// Local verification only: production serves /static directly from the web server.
const staticDir = process.env.STATIC_DIR ? resolve(process.env.STATIC_DIR) : null;

if (!existsSync(manifestPath)) {
  console.error(`Missing client build manifest at ${manifestPath}. Run the app build first.`);
  process.exit(1);
}

function assetTags(manifest) {
  const entry = manifest['src/app/client.tsx'];
  if (!entry) throw new Error('Client entry is missing from the manifest');
  const css = new Set(entry.css ?? []);
  const modules = new Set([entry.file]);
  for (const name of entry.imports ?? []) {
    const imported = manifest[name];
    if (!imported) continue;
    modules.add(imported.file);
    for (const file of imported.css ?? []) css.add(file);
  }
  return {
    head: [...css].map((file) => `<link rel="stylesheet" href="/app-assets/${file}">`)
      .concat([...modules].filter((file) => file.endsWith('.js'))
        .map((file) => `<link rel="modulepreload" href="/app-assets/${file}">`)).join('\n'),
    scripts: `<script type="module" src="/app-assets/${entry.file}"></script>`,
  };
}

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const assets = assetTags(manifest);
const { renderPage } = await import(new URL('./dist/server/render.js', import.meta.url));

const types = {
  '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.woff2': 'font/woff2', '.map': 'application/json',
};

function sendHTML(response, status, html, headOnly, extraHeaders = {}) {
  response.writeHead(status, {
    'Content-Type': 'text/html; charset=utf-8',
    // The header depends on the session cookie; never share it through a cache.
    'Cache-Control': 'no-store',
    Vary: 'Cookie',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    ...extraHeaders,
  });
  response.end(headOnly ? undefined : html);
}

async function serveAsset(pathname, response, headOnly, prefix = '/app-assets/', directory = clientDir) {
  try {
    const relative = normalize(decodeURIComponent(pathname.slice(prefix.length)));
    const base = await realpath(directory);
    const file = await realpath(resolve(directory, relative));
    if (!file.startsWith(`${base}/`) || !(await stat(file)).isFile()) throw new Error('Not an asset');
    const body = headOnly ? undefined : await readFile(file);
    response.writeHead(200, {
      'Content-Type': types[extname(file)] || 'application/octet-stream',
      // Only the app bundle has hashed file names; existing site assets keep a short cache.
      'Cache-Control': prefix === '/app-assets/'
        ? 'public, max-age=31536000, immutable' : 'public, max-age=3600',
      'X-Content-Type-Options': 'nosniff',
    });
    response.end(body);
  } catch {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end(headOnly ? undefined : 'not found');
  }
}

const server = createServer(async (request, response) => {
  const headOnly = request.method === 'HEAD';
  let url;
  try { url = new URL(request.url ?? '/', 'http://localhost'); }
  catch {
    response.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end(headOnly ? undefined : 'invalid request URL');
    return;
  }
  if (request.method !== 'GET' && !headOnly) {
    response.writeHead(405, { Allow: 'GET, HEAD', 'Content-Type': 'text/plain; charset=utf-8' });
    response.end('method not allowed');
    return;
  }
  if (url.pathname === '/health') {
    response.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    response.end(headOnly ? undefined : JSON.stringify({ status: 'ok', build_sha: process.env.APP_BUILD_SHA || 'development' }));
    return;
  }
  if (url.pathname.startsWith('/app-assets/')) {
    await serveAsset(url.pathname, response, headOnly);
    return;
  }
  if (staticDir && url.pathname.startsWith('/static/')) {
    await serveAsset(url.pathname, response, headOnly, '/static/', staticDir);
    return;
  }
  try {
    const result = await renderPage({
      path: url.pathname, search: url.search, origin, apiBase, sessionUrl, flaskSocketPath,
      cookie: request.headers.cookie,
      doNotTrack: request.headers.dnt === '1',
    }, assets);
    if (result.redirect) {
      // A site-relative preview target stays on the same public origin; the web
      // server decides which handler owns the flagged request.
      response.writeHead(result.status, {
        Location: result.redirect, 'Content-Length': '0', 'Cache-Control': 'no-store', Vary: 'Cookie',
      });
      response.end();
      return;
    }
    sendHTML(response, result.status, result.html, headOnly, result.headers);
  } catch (error) {
    console.error('Page rendering failed', error);
    sendHTML(response, 503, '<!DOCTYPE html><title>Palvelu ei ole juuri nyt käytettävissä</title>'
      + '<h1>Palvelu ei ole juuri nyt käytettävissä</h1>', headOnly);
  }
});

server.listen(port, process.env.APP_ADDR || '127.0.0.1', () => {
  console.log(`Public app listening on ${process.env.APP_ADDR || '127.0.0.1'}:${port} for ${origin}`);
});

function stop() {
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}
process.on('SIGTERM', stop);
process.on('SIGINT', stop);
