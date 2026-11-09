// Public app host: server-owned document metadata and the React client bundle.
//
// Information pages include server-rendered React markup. Event routes keep
// their client-rendered bodies and load data through the public API.
import { createServer } from 'node:http';
import { isIP } from 'node:net';
import { readFileSync, existsSync } from 'node:fs';
import { readFile, realpath, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { availabilityReader } from './public-availability.mjs';

const root = resolve(fileURLToPath(new URL('.', import.meta.url)));
const clientDir = join(root, 'dist', 'client');
const manifestPath = join(clientDir, '.vite', 'manifest.json');

const port = Number(process.env.APP_PORT || 8090);
const origin = (process.env.APP_ORIGIN || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
const apiBase = (process.env.PUBLIC_API_BASE || 'https://api.mielenosoitukset.fi/api').replace(/\/+$/, '');
// Server-side reads prefer a local API address, so the host does not pay a
// public round trip to itself. Browsers keep using PUBLIC_API_BASE.
const apiReadBase = (process.env.PUBLIC_API_LOCAL || apiBase).replace(/\/+$/, '');
const publicAvailable = availabilityReader(apiReadBase);
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
  function routeAssets(name) {
    const files = new Set();
    const styles = new Set();
    const visited = new Set();
    function collect(key) {
      if (visited.has(key) || !manifest[key]) return;
      visited.add(key);
      const chunk = manifest[key];
      files.add(chunk.file);
      for (const file of chunk.css ?? []) styles.add(file);
      for (const dependency of chunk.imports ?? []) collect(dependency);
    }
    collect(name);
    return [...files].filter(file => file.endsWith('.js'))
      .map(file => `<link rel="modulepreload" href="/app-assets/${file}">`).join('')
      + [...styles].map(file => `<link rel="stylesheet" href="/app-assets/${file}">`).join('');
  }
  return {
    listing: routeAssets('src/app/ListingScreen.tsx'),
    organization: routeAssets('src/app/OrganizationScreen.tsx'),
    cities: routeAssets('src/pages/CitiesPage.tsx'),
    today: routeAssets('src/app/TodayScreen.tsx'),
    submit: routeAssets('src/app/SubmitScreen.tsx'),
    calendar: routeAssets('src/app/CalendarScreen.tsx'),
    calendarYear: routeAssets('src/app/YearCalendarScreen.tsx'),
    godAuth: routeAssets('src/app/GodScreen.tsx'),
    pride: routeAssets('src/app/PrideScreen.tsx'),
    information: routeAssets('src/app/InformationScreen.tsx'),
    campaign: routeAssets('src/app/CampaignScreen.tsx'),
    fundraising: routeAssets('src/app/FundraisingScreen.tsx'),
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
    // Only our loopback reverse proxy may supply a forwarded client address.
    // Apache appends its peer on the right, matching Flask's one-hop ProxyFix.
    const peer = request.socket.remoteAddress;
    const localProxy = peer === '127.0.0.1' || peer === '::1' || peer === '::ffff:127.0.0.1';
    const forwarded = request.headers['x-forwarded-for'];
    const candidate = localProxy && typeof forwarded === 'string'
      ? forwarded.split(',').at(-1)?.trim() : peer;
    const clientIp = candidate && isIP(candidate) ? candidate : undefined;
    const cfCandidate = request.headers['cf-connecting-ipv6'] ?? request.headers['cf-connecting-ip'];
    const cloudflareIp = localProxy && typeof cfCandidate === 'string' && isIP(cfCandidate)
      ? cfCandidate : undefined;
    const result = await renderPage({
      path: url.pathname, search: url.search, origin, apiBase, apiReadBase, sessionUrl, flaskSocketPath,
      cookie: request.headers.cookie,
      headOnly,
      clientIp,
      cloudflareIp,
      doNotTrack: request.headers.dnt === '1',
      publicUnavailable: url.pathname === '/auth/god' ? false : !await publicAvailable(),
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
