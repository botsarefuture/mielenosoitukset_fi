import assert from 'node:assert/strict';
import { createServer, request } from 'node:http';
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Run after npm run app:build. No MongoDB, credentials or external services required.
const root = fileURLToPath(new URL('..', import.meta.url)).replace(/\/$/, '');
const { renderPage } = await import(pathToFileURL(`${root}/frontend/dist/server/render.js`));
let reads = 0;
const sessionServer = createServer((req, res) => {
  reads++;
  if (req.url === '/down') { res.writeHead(503); res.end(); return; }
  const name = req.headers.cookie?.includes('alice') ? 'Alice' : 'Bob';
  const authenticated = Boolean(req.headers.cookie);
  setTimeout(() => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ authenticated, name, locale: 'fi', locales: [{ code: 'fi', name: 'Suomi' }],
      role: authenticated ? 'user' : 'guest', site_analytics_enabled: true, matomo_enabled: true }));
  }, 25);
});
await new Promise(resolve => sessionServer.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${sessionServer.address().port}`;
const input = { path: '/', origin: 'https://example.test', apiBase: `${base}/api`, sessionUrl: `${base}/session` };
const assets = { head: '', scripts: '' };
const page = (changes = {}) => renderPage({ ...input, ...changes }, assets);
const bootstrap = html => JSON.parse(html.match(/id="app-bootstrap">([\s\S]*?)<\/script>/)[1]);
try {
  assert.equal((await page({ path: '/not-migrated' })).status, 404);
  assert.equal(reads, 0, 'Unknown routes must not fetch a session');
  const anonymous = await Promise.all(Array.from({ length: 8 }, () => page()));
  assert.equal(reads, 1, 'Concurrent cookieless requests share one public configuration read');
  assert(anonymous.every(result => !bootstrap(result.html).session.authenticated));
  assert(anonymous.every(result => bootstrap(result.html).session.name === null));
  await page();
  assert.equal(reads, 1, 'Warm public configuration avoids another request');
  const dnt = await page({ doNotTrack: true });
  assert.equal(bootstrap(dnt.html).session.siteAnalyticsEnabled, false);
  assert.equal(bootstrap(dnt.html).session.matomoEnabled, false);
  assert(!dnt.html.includes('web-vitals.iife.js'));
  assert.equal(bootstrap((await page()).html).session.siteAnalyticsEnabled, true,
    'DNT must not mutate the shared public configuration');
  const [alice, bob] = await Promise.all([page({ cookie: 'session=alice' }), page({ cookie: 'session=bob' })]);
  assert.equal(reads, 3, 'Cookie-bearing requests must not share reads');
  assert.equal(bootstrap(alice.html).session.name, 'Alice');
  assert.equal(bootstrap(bob.html).session.name, 'Bob');
  assert.equal(bootstrap((await page()).html).session.name, null);
  const originalNow = Date.now;
  try {
    for (const elapsed of [31_000, 299_000]) {
      Date.now = () => originalNow() + elapsed;
      await page();
      assert.equal(reads, 3, 'Public configuration stays cached before five minutes');
    }
    Date.now = () => originalNow() + 301_000;
    await page();
  } finally { Date.now = originalNow; }
  assert.equal(reads, 4, 'Expired public configuration is refreshed');
  await page({ sessionUrl: `${base}/down` });
  await page({ sessionUrl: `${base}/down` });
  assert.equal(reads, 6, 'Failed configuration reads must not be cached');
  console.log('PASS: unknown-route zero reads; eight concurrent anonymous pages one read; warm zero reads; private sessions isolated; TTL and failure handling');
} finally { await new Promise(resolve => sessionServer.close(resolve)); }

const socketDirectory = mkdtempSync(join(tmpdir(), 'moso-session-'));
const socketPath = join(socketDirectory, 'flask.sock');
let socketReads = 0;
const socketServer = createServer((req, res) => {
  socketReads++;
  assert.equal(req.headers.host, 'mielenosoitukset.fi');
  assert.equal(req.headers['x-forwarded-proto'], 'https');
  if (req.url === '/slow') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.write('{'); setTimeout(() => res.end('}'), 2000); return;
  }
  if (req.url === '/aborted') { res.writeHead(200, { 'Content-Type': 'application/json' }); res.write('{'); res.destroy(); return; }
  if (req.url === '/redirect') { res.writeHead(302, { Location: '/api/session' }); res.end(); return; }
  if (req.url === '/invalid') { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end('<html>'); return; }
  res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
  if (req.url === '/oversized') { res.end(JSON.stringify({ authenticated: false, name: 'x'.repeat(70_000) })); return; }
  res.end(JSON.stringify({ authenticated: Boolean(req.headers.cookie), name: req.headers.cookie ?? null,
    locale: 'fi', locales: [{ code: 'fi', name: 'Suomi' }] }));
});
await new Promise(resolve => socketServer.listen(socketPath, resolve));
const socketPage = (changes = {}) => page({ sessionUrl: 'http://mielenosoitukset.fi/api/session',
  origin: 'https://mielenosoitukset.fi', flaskSocketPath: socketPath, ...changes });
try {
  await socketPage({ path: '/not-migrated' });
  assert.equal(socketReads, 0);
  await Promise.all(Array.from({ length: 8 }, () => socketPage()));
  assert.equal(socketReads, 1, 'Socket public configuration is coalesced');
  await socketPage();
  assert.equal(socketReads, 1, 'Socket public configuration is cached');
  const [alice, bob] = await Promise.all([socketPage({ cookie: 'session=alice' }), socketPage({ cookie: 'session=bob' })]);
  assert.equal(bootstrap(alice.html).session.name, 'session=alice');
  assert.equal(bootstrap(bob.html).session.name, 'session=bob');
  assert.equal(socketReads, 3, 'Socket private sessions are uncached and isolated');
  assert.equal(bootstrap((await socketPage()).html).session.name, null);
  for (const path of ['/redirect', '/invalid', '/oversized', '/aborted']) {
    const before = socketReads;
    for (let i = 0; i < 2; i++) {
      const result = await socketPage({ sessionUrl: `http://mielenosoitukset.fi${path}` });
      assert.equal(bootstrap(result.html).session.authenticated, false);
    }
    assert.equal(socketReads, before + 2, `${path} failures must not be cached or followed`);
  }
  const started = performance.now();
  await socketPage({ sessionUrl: 'http://mielenosoitukset.fi/slow' });
  assert(performance.now() - started < 1800, 'Socket timeout includes incomplete response bodies');
  const before = socketReads;
  const missing = await socketPage({ flaskSocketPath: join(socketDirectory, 'missing.sock') });
  assert.equal(bootstrap(missing.html).session.siteAnalyticsEnabled, false);
  assert.equal(socketReads, before, 'Cache cannot leak between socket paths');
  console.log('PASS: Unix socket host/proto, anonymous coalescing/cache, private cookie isolation, bounded body/timeout, aborted/invalid/redirect responses and transport isolation');
} finally {
  socketServer.closeAllConnections();
  await new Promise(resolve => socketServer.close(resolve));
  rmSync(socketDirectory, { recursive: true, force: true });
}

const listener = createServer();
await new Promise(resolve => listener.listen(0, '127.0.0.1', resolve));
const port = listener.address().port;
await new Promise(resolve => listener.close(resolve));
const child = spawn(process.execPath, ['frontend/server.mjs'], { cwd: root,
  env: { ...process.env, APP_PORT: String(port), SESSION_URL: `${base}/down`,
    APP_BUILD_SHA: 'verification-build', FLASK_SOCKET_PATH: '' }, stdio: ['ignore', 'pipe', 'pipe'] });
const get = (path, method = 'GET') => new Promise((resolve, reject) => {
  const req = request({ hostname: '127.0.0.1', port, path, method }, res => {
    let body = ''; res.on('data', value => { body += value; });
    res.on('end', () => resolve({ status: res.statusCode, body, headers: res.headers }));
  });
  req.on('error', reject); req.end();
});
try {
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Host startup timeout')), 10_000);
    child.stdout.on('data', data => { if (String(data).includes('Public app listening')) { clearTimeout(timer); resolve(); } });
    child.once('exit', code => reject(new Error(`Host exited ${code}`)));
  });
  for (const path of ['/app-assets/%', '/app-assets/assets', '/app-assets/%2e%2e/server/render.js']) {
    assert.equal((await get(path)).status, 404, path);
    assert.equal((await get('/health')).status, 200, 'Malformed asset requests must not crash the host');
  }
  assert.equal(JSON.parse((await get('/health')).body).build_sha, 'verification-build');
  const manifest = JSON.parse(readFileSync(`${root}/frontend/dist/client/.vite/manifest.json`));
  const asset = `/app-assets/${manifest['src/app/client.tsx'].file}`;
  assert.equal((await get(asset)).status, 200);
  const head = await get(asset, 'HEAD');
  assert.equal(head.status, 200); assert.equal(head.body, '');
  assert.match(head.headers['cache-control'], /immutable/);
  console.log('PASS: malformed URL, directory and traversal requests return 404 without crashing; real asset GET/HEAD and immutable caching');
} finally { child.kill('SIGTERM'); }
