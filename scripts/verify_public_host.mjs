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
// The home batch is read by the server, so it needs its own address; the session
// fake below is only a session endpoint.
const homeApi = createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ events: [], recommended: false }));
});
await new Promise(resolve => homeApi.listen(0, '127.0.0.1', resolve));
const homeBase = `http://127.0.0.1:${homeApi.address().port}/api`;
const input = { path: '/', origin: 'https://example.test', apiBase: `${base}/api`,
  apiReadBase: homeBase, sessionUrl: `${base}/session` };
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
  const forms = await Promise.all(Array.from({ length: 8 }, () => page({ path: '/submit' })));
  const tokens = forms.map(result => bootstrap(result.html).submission.token);
  assert.equal(new Set(tokens).size, 8, 'Submission idempotency tokens are per document, never shared');
  for (const result of forms) {
    assert.equal(result.status, 200);
    assert.equal(result.headers['Cache-Control'], 'no-store');
    assert.match(result.html, /<title>Ilmoita mielenosoituksesta \| Mielenosoitukset.fi<\/title>/);
    assert.match(result.html, /<link rel="canonical" href="https:\/\/example.test\/submit">/);
    assert.match(result.html, /<noscript><article class="submit-page">/);
    assert.match(result.html, /name="submission_token"/);
    assert(!bootstrap(result.html).submission.canEditDemo);
  }
  assert.equal((await page({ path: '/submit/facebook_import' })).status, 404,
    'Nested import POST handling remains outside the page host');
  console.log('PASS: standalone submission head/no-JS form and per-document tokens without content reads');
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
  for (const [path, heading, canonical, anchor] of [
    ['/info', 'Tietoa Mielenosoitukset.fi', '/info'],
    ['/ohjeet', 'Selkeät ohjeet kaikille järjestäjille', '/ohjeet', 'submit-checklist'],
    ['/ohjeet/', 'Selkeät ohjeet kaikille järjestäjille', '/ohjeet', 'faq'],
    ['/privacy', 'Tietosuojaseloste', '/privacy'],
    ['/terms', 'Käyttöehdot', '/terms', 'terms-appeal'],
    ['/upcoming/translations/', 'Käännöshanke', '/upcoming/translations/'],
  ]) {
    const response = await page({ path });
    assert.equal(response.status, 200, path);
    const body = response.html.split('<body>')[1].split('<script type="application/json"')[0];
    assert(body.includes(heading) && body.includes('id="main-content"'), path);
    assert(response.html.includes(`rel="canonical" href="${input.origin}${canonical}"`), path);
    if (anchor) assert(body.includes(`id="${anchor}"`), path);
  }
  assert.equal((await page({ path: '/upcoming/translations/join' })).status, 404);
  const infoBody = result => result.html.split('<body>')[1].split('<script type="application/json"')[0];
  assert(!infoBody(await page({ path: '/info' })).includes('about-campaign'), 'Anonymous visitors do not see a campaign that sends them to login');
  assert(infoBody(await page({ path: '/info', cookie: 'session=alice' })).includes('about-campaign'), 'Signed-in visitors can preview the campaign');
  assert(infoBody(await page({ path: '/info' })).includes('about-facts'));
  console.log('PASS: information pages render readable HTML and retain canonical URLs and anchors');
  const contactReads = [];
  let contactMode = 'ok';
  let minted = 0;
  const contactSessions = createServer((req, res) => {
    const url = new URL(req.url, 'http://session.test');
    contactReads.push({ scoped: url.searchParams.get('contact_form') === '1', cookie: req.headers.cookie ?? null });
    if (contactMode === 'down') { res.writeHead(503); res.end(); return; }
    const body = { authenticated: false, locale: 'fi', locales: [{ code: 'fi', name: 'Suomi' }], role: 'guest' };
    const headers = { 'Content-Type': 'application/json' };
    if (url.searchParams.get('contact_form') === '1') {
      minted++;
      body.contact_form = { enabled: contactMode !== 'disabled', csrf_token: String(minted).padStart(43, 'T'),
        messages: contactMode === 'sent' ? [['success', 'Yhteydenottopyyntö välitetty onnistuneesti!']] : [],
        limits: { name_max: 120, email_max: 254, message_min: 10, message_max: 5000 } };
      headers['Set-Cookie'] = `session=visitor-${minted}; HttpOnly; Path=/; SameSite=Lax`;
    }
    res.writeHead(200, headers);
    res.end(JSON.stringify(body));
  });
  await new Promise(resolve => contactSessions.listen(0, '127.0.0.1', resolve));
  try {
    const contact = changes => page({ path: '/contact', sessionUrl: `http://127.0.0.1:${contactSessions.address().port}/session`, ...changes });
    const [first, second] = await Promise.all([contact(), contact()]);
    for (const [index, result] of [first, second].entries()) {
      assert.equal(result.status, 200);
      assert.equal(result.headers['Cache-Control'], 'private, no-store');
      assert.equal(result.headers['Set-Cookie'].length, 1);
      assert.match(result.headers['Set-Cookie'][0], /^session=visitor-\d; HttpOnly/);
      assert(result.html.includes(`value="${result.headers['Set-Cookie'][0].match(/visitor-(\d)/)[1].padStart(43, 'T')}"`),
        'Each visitor receives the cookie that belongs to their own token');
    }
    assert.notDeepEqual(first.headers['Set-Cookie'], second.headers['Set-Cookie']);
    const tokenOf = result => result.html.match(/name="csrf_token" value="([^"]+)"/)[1];
    assert.notEqual(tokenOf(first), tokenOf(second), 'Concurrent anonymous visitors never share a form token');
    assert.equal(contactReads.filter(read => read.scoped && read.cookie === null).length, 2,
      'Each cookieless visitor gets its own scoped session read');
    const body = first.html.split('<body>')[1].split('<script type="application/json"')[0];
    for (const text of ['Ota yhteyttä', 'action="/contact"', 'method="post"', 'name="website"', 'name="subject"',
      'value="Tuki"', 'maxLength="5000"', 'minLength="10"', 'tuki@mielenosoitukset.fi']) assert(body.includes(text), text);
    assert(first.html.includes('rel="canonical" href="https://example.test/contact"'));
    assert(!body.includes('site-hero__eyebrow'));
    const before = contactReads.length;
    const head = await contact({ headOnly: true });
    assert.equal(head.status, 200);
    assert(contactReads.slice(before).every(read => !read.scoped), 'HEAD must not mint a token');
    const returning = await contact({ cookie: 'session=visitor-1' });
    assert.equal(contactReads.at(-1).cookie, 'session=visitor-1');
    assert.notEqual(tokenOf(returning), tokenOf(first));
    contactMode = 'sent';
    const sent = await contact({ cookie: 'session=visitor-1' });
    assert.match(sent.html, /role="status"[^>]*><span class="flash-text">Yhteydenottopyyntö välitetty onnistuneesti!/);
    contactMode = 'disabled';
    const disabled = await contact();
    assert(disabled.html.includes('tilapäisesti poissa käytöstä') && !disabled.html.includes('id="contact-form"'));
    contactMode = 'down';
    const down = await contact();
    assert.equal(down.status, 200);
    assert(down.html.includes('Lomaketta ei voitu ladata') && !down.html.includes('id="contact-form"'));
    assert.equal(down.headers['Set-Cookie'], undefined);
  } finally { contactSessions.close(); }
  console.log('PASS: contact page mints a private per-visitor form token, forwards the session cookie, skips HEAD and degrades to email');
  let campaignState = { status: 200, body: { published: false } };
  const campaignApi = createServer((req, res) => {
    if (req.url !== '/api/campaign/publication') { res.writeHead(404); res.end(); return; }
    res.writeHead(campaignState.status, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(campaignState.body));
  });
  await new Promise(resolve => campaignApi.listen(0, '127.0.0.1', resolve));
  try {
    const campaign = changes => page({ path: '/kampanja/', apiReadBase: `http://127.0.0.1:${campaignApi.address().port}/api`, ...changes });
    for (const state of [{ status: 200, body: { published: false } }, { status: 200, body: { published: 'true' } },
      { status: 503, body: {} }, { status: 200, body: [] }]) {
      campaignState = state;
      const hidden = await campaign();
      assert.equal(hidden.status, 302, JSON.stringify(state));
      assert.equal(hidden.redirect, '/users/auth/login?next=%2Fkampanja%2F');
      assert.equal(hidden.headers['Cache-Control'], 'private, no-store');
    }
    campaignState = { status: 200, body: { published: false } };
    const preview = await campaign({ cookie: 'session=alice' });
    assert.equal(preview.status, 200);
    assert.equal(preview.headers['Cache-Control'], 'private, no-store');
    assert.equal(preview.headers['X-Robots-Tag'], 'noindex, nofollow');
    assert.match(preview.html, /<meta name="robots" content="noindex, nofollow" \/>/);
    campaignState = { status: 200, body: { published: true } };
    const live = await campaign();
    assert.equal(live.status, 200);
    assert.equal(live.headers['Cache-Control'], 'private, no-store');
    assert.equal(live.headers['X-Robots-Tag'], undefined);
    const body = live.html.split('<body>')[1].split('<script type="application/json"')[0];
    assert(body.includes('Yhdessä näkyväksi') && body.includes('id="vapaaehtoiseksi"') && body.includes('id="newsletter"'));
    assert(live.html.includes('rel="canonical" href="https://example.test/kampanja/"'));
    assert(live.html.includes('og:image" content="https://example.test/static/kampanja/og-banner.png"'));
    assert(live.html.includes('/static/css/campaign.css'));
    assert(body.includes('/kampanja/api/volunteers') || live.html.includes('/kampanja/api/volunteers'));
    assert.equal((await page({ path: '/kampanja' })).status, 404, 'Flask keeps the slash redirect');
    assert.equal((await page({ path: '/kampanja/confirm/token' })).status, 404, 'Confirmation stays in Flask');
    const fundraising = changes => campaign({ path: '/ker%C3%A4ys', ...changes });
    campaignState = { status: 200, body: { published: false } };
    for (const path of ['/ker%C3%A4ys', '/keräys']) {
      const hidden = await fundraising({ path });
      assert.equal(hidden.status, 302, path);
      assert.equal(hidden.redirect, '/users/auth/login?next=%2Fker%C3%A4ys');
      assert.equal(hidden.headers['Cache-Control'], 'private, no-store');
    }
    const fundPreview = await fundraising({ cookie: 'session=alice' });
    assert.equal(fundPreview.status, 200);
    assert.equal(fundPreview.headers['X-Robots-Tag'], 'noindex, nofollow');
    campaignState = { status: 200, body: { published: true } };
    const fundLive = await fundraising();
    assert.equal(fundLive.status, 200);
    assert.equal(fundLive.headers['Cache-Control'], 'private, no-store');
    const fundBody = fundLive.html.split('<body>')[1].split('<script type="application/json"')[0];
    for (const text of ['Jotta mielenosoitukset löytyvät', '2 500 €', 'Valmistelussa', 'Lahjoittaminen ei ole vielä avoinna',
      'jatkuvuuden turvaamiseen', 'href="/contact"', 'MobilePay 1', 'MobilePay 2',
      '<article class="public-content campaign-page" lang="fi">']) assert(fundBody.includes(text), text);
    assert.match(fundBody, /datetime="2026-11-15"[^]*datetime="2027-02-15"/i);
    for (const text of ['Näin lahjoitat', 'Tilinumero (IBAN)', 'name="iban"', 'type="submit"']) assert(!fundBody.includes(text), text);
    assert(fundLive.html.includes('rel="canonical" href="https://example.test/ker%C3%A4ys"'));
    assert(fundLive.html.includes('/static/css/public-content.css'));
    assert.match(bootstrap(fundLive.html).today, /^\d{4}-\d{2}-\d{2}$/);
  } finally { campaignApi.close(); }
  console.log('PASS: campaign and fundraising pages keep the publication gate: signed-in preview, fail-closed reads, private no-store and noindex until published');
  const { fundraisingDetails } = await import(pathToFileURL(`${root}/frontend/dist/server/render.js`));
  const parity = JSON.parse(readFileSync(`${root}/tests/fixtures/fundraising_parity.json`, "utf8"));
  for (const item of parity) {
    const got = fundraisingDetails(item.input, item.today);
    assert.deepEqual(Object.fromEntries(Object.entries(got).sort()), item.expected, item.name);
  }
  console.log(`PASS: fundraising rules match the Python implementation on ${parity.length} shared cases`);
} finally {
  await new Promise(resolve => sessionServer.close(resolve));
  await new Promise(resolve => homeApi.close(resolve));
}

// Detail route: one projected API read for the head, no body rendering.
const detailId = '66fa58601102367d5d52887f';
const longDescription = `<p>${'Pitkä kuvaus '.repeat(40)}</p>`;
const publicReads = [];
const localReads = [];
// Relative dates keep the selection and index assertions stable over time.
const day = offset => new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);
const seriesParent = '66fa58601102367d5d528000';
const organizationId = '66fa58601102367d5d528099';
const farParent = '66fa58601102367d5d528001';
const orphanParent = '66fa58601102367d5d528002';
const childUpcoming = '66fa58601102367d5d528010';
const childPast = '66fa58601102367d5d528011';
const childCancelled = '66fa58601102367d5d528012';
const orphanChild = '66fa58601102367d5d528013';
const farChild = '66fa58601102367d5d528014';
const archivedChild = '66fa58601102367d5d528015';
const seriesOccurrences = [
  { id: childUpcoming, slug: 'occurrence-a', date: day(30), start_time: '14:00', end_time: '15:00', cancelled: false },
  { id: childPast, slug: 'occurrence-b', date: day(-30), start_time: '10:00', end_time: '11:00', cancelled: false },
  { id: childCancelled, slug: 'occurrence-c', date: day(31), cancelled: true },
];
// Children resolve by id or slug, and know their parent series.
const children = {
  'occurrence-a': { id: childUpcoming, parent: seriesParent },
  'occurrence-b': { id: childPast, parent: seriesParent },
  'archived-child': { id: archivedChild, parent: seriesParent, date: day(-900) },
  'orphan-child': { id: orphanChild, parent: orphanParent },
  [childUpcoming]: { id: childUpcoming, parent: seriesParent, slug: 'occurrence-a' },
  [childPast]: { id: childPast, parent: seriesParent, slug: 'occurrence-b' },
  [childCancelled]: { id: childCancelled, parent: seriesParent, slug: 'occurrence-c', cancelled: true },
  [archivedChild]: { id: archivedChild, parent: seriesParent, slug: 'archived-child', date: day(-900) },
  [orphanChild]: { id: orphanChild, parent: orphanParent, slug: 'orphan-child' },
};
function createApi(log) {
  return createServer((req, res) => {
    const url = new URL(req.url, 'http://api.test');
    log.push(req.url);
    const identifier = decodeURIComponent(url.pathname.split('/').pop() ?? '');
    const send = (status, body) => {
      res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify(body));
    };
    if (identifier === 'home') {
      return send(200, { events: [{ _id: detailId, title: 'Test event', detail_url: '/demonstration/may-day-2026' }], recommended: false });
    }
    if (url.pathname === '/api/cities') {
      return send(200, { day: day(0), cities: [{ key: 'helsinki', name: 'Helsinki', phrase: 'Helsingissä',
        demo_count: 5, today_count: 2, upcoming_count: 3 }], private: 'DO-NOT-BOOTSTRAP' });
    }
    if (url.pathname === '/api/calendar/2028/2') {
      return send(200, { year: 2028, month: 2, ...(url.searchParams.get('city') ? {city:url.searchParams.get('city')} : {}), total: 2, days: [{ date: '2028-02-29', count: 2 }] });
    }
    if (url.pathname === '/api/calendar/2028') {
      const city = url.searchParams.get('city');
      return send(200, {year:2028,month:0,...(city ? {city} : {}),total:city ? 2 : 3,
        days:[{date:'2028-02-29',count:2},...(!city ? [{date:'2028-12-31',count:1}] : [])]});
    }
    if (url.pathname.startsWith('/api/organizations/')) {
      if (identifier !== organizationId) return send(404, { error: 'organization not found' });
      return send(200, { _id: organizationId, name: 'Test Organization', description: 'Public profile',
        email: 'public@example.test', website: 'https://example.test', logo: '', verified: false,
        social_media_links: {}, invitations: ['private@example.test'], members: ['private-user'] });
    }
    if (url.pathname === '/api/demonstrations') {
      if (url.searchParams.get('per_page') === '20') return send(200, { page: Number(url.searchParams.get('page')), per_page: 20,
        total: 21, total_pages: 2, result_start: 21, result_end: 21,
        results: [{ _id: detailId, title: 'Selected calendar event', date: url.searchParams.get('date_start'), detail_url: `/demonstration/${detailId}` }] });
      return send(200, { page: 1, per_page: 12, total: 1, total_pages: 1, result_start: 1, result_end: 1,
        results: [{ _id: detailId, title: 'Test listing event' }] });
    }
    if (url.pathname.includes('/series/')) {
      if (identifier === orphanParent) return send(404, { error: 'series not found' });
      if (identifier === farParent) {
        return send(200, { id: farParent, occurrences: [{ id: farChild, slug: 'far-child', date: day(900), cancelled: false }] });
      }
      if (identifier === seriesParent) return send(200, { id: seriesParent, occurrences: seriesOccurrences });
      return send(404, { error: 'series not found' });
    }
    if (identifier === 'slow') return; // never answers; the host must give up
    if (identifier === 'broken') { res.writeHead(503); res.end('{}'); return; }
    if (identifier === 'nonpublic') return send(404, { error: 'demonstration not found' });
    const child = children[identifier];
    if (child) {
      return send(200, { _id: child.id, title: 'Test occurrence', description: 'Kuvaus',
        slug: child.slug ?? identifier, parent: child.parent, date: child.date ?? day(30),
        start_time: '14:00', end_time: '15:00', cancelled: child.cancelled ?? false, city: 'Helsinki',
        address: 'Mannerheimintie 1', preview_image: null });
    }
    const doc = {
      _id: detailId, title: 'Test event', description: longDescription,
      slug: identifier === detailId ? 'may-day-2026' : identifier,
      running_number: 4242, date: identifier === 'far-future' ? day(900) : '2026-12-01',
      start_time: '14:00', end_time: '15:00', cancelled: false,
      city: 'Helsinki', address: 'Mannerheimintie 1', preview_image: null, parent: null,
    };
    send(200, doc);
  });
}
const publicApi = createApi(publicReads);
const localApi = createApi(localReads);
await new Promise(resolve => publicApi.listen(0, '127.0.0.1', resolve));
await new Promise(resolve => localApi.listen(0, '127.0.0.1', resolve));
const apiBase = `http://127.0.0.1:${publicApi.address().port}/api`;
// The server reads through the local address; the browser keeps the public one.
const apiReadBase = `http://127.0.0.1:${localApi.address().port}/api`;
let detailSessionReads = 0;
const detailSession = createServer((req, res) => {
  detailSessionReads++;
  const scopedId = new URL(req.url, 'http://session.test').searchParams.get('organization_id');
  res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ authenticated: Boolean(req.headers.cookie), name: null, locale: 'fi',
    locales: [{ code: 'fi', name: 'Suomi' }], site_analytics_enabled: true, matomo_enabled: false,
    ...(scopedId && req.headers.cookie ? { organization: { id: scopedId,
      following: req.headers.cookie === 'session=alice', invited: false, has_messages: false,
      permissions: { EDIT_ORGANIZATION: req.headers.cookie === 'session=alice' } } } : {}) }));
});
await new Promise(resolve => detailSession.listen(0, '127.0.0.1', resolve));
const detailSessionUrl = `http://127.0.0.1:${detailSession.address().port}/session`;
const detailPage = (changes = {}) => page({ apiBase, apiReadBase, sessionUrl: detailSessionUrl, ...changes });
try {
  const event = await detailPage({ path: '/demonstration/may-day-2026' });
  assert.equal(event.status, 200);
  assert.match(event.html, /<title>Test event \| Mielenosoitukset\.fi<\/title>/);
  assert.match(event.html, /<link rel="canonical" href="https:\/\/example\.test\/demonstration\/may-day-2026">/);
  assert.match(event.html, /<meta name="robots" content="index, follow" \/>/);
  assert.match(event.html, /<script type="application\/ld\+json">\{"@context":"https:\/\/schema\.org","@type":"Event"/);
  assert.match(event.html, /"startDate":"2026-12-01T14:00"/);
  assert.match(event.html, /public-detail\.css/);
  assert.equal(event.headers?.['X-Robots-Tag'], undefined, 'Indexable detail pages set no robots header');
  const detailBootstrap = bootstrap(event.html).detail;
  assert.deepEqual(detailBootstrap, { id: detailId, identifier: 'may-day-2026',
    canonicalUrl: 'https://example.test/demonstration/may-day-2026' });
  const description = event.html.match(/<meta name="description" content="([^"]*)"/)[1];
  assert(!description.includes('<p>'), 'Meta description must strip markup');
  assert(description.length <= 200 && description.endsWith('...'), 'Meta description is truncated like the shell');
  assert(detailSessionReads <= 1, 'Anonymous detail configuration is read at most once while cached');
  const readsAfterFirstPage = detailSessionReads;

  // A hex URL resolves and still advertises the canonical slug.
  const byId = await detailPage({ path: `/demonstration/${detailId}` });
  assert.equal(byId.status, 200);
  assert.equal(bootstrap(byId.html).detail.identifier, detailId);
  assert.equal(bootstrap(byId.html).detail.canonicalUrl, 'https://example.test/demonstration/may-day-2026');

  // Dates past the discovery horizon stay out of the index, in the head and header.
  const farFuture = await detailPage({ path: '/demonstration/far-future' });
  assert.equal(farFuture.status, 200);
  assert.match(farFuture.html, /<meta name="robots" content="noindex, follow" \/>/);
  assert.equal(farFuture.headers?.['X-Robots-Tag'], 'noindex, follow');

  // Anonymous visitors get 404; signed-in visitors keep the Flask preview path.
  assert.equal((await detailPage({ path: '/demonstration/nonpublic' })).status, 404);
  const preview = await detailPage({ path: '/demonstration/nonpublic', cookie: 'session=alice' });
  assert.equal(preview.status, 302);
  assert.equal(preview.redirect, '/demonstration/nonpublic?preview=1');
  const flagged = await detailPage({ path: '/demonstration/nonpublic', cookie: 'session=alice', search: '?preview=1' });
  assert.equal(flagged.status, 404, 'The flagged request must not redirect again');

  // A backend failure is a 503, never a shell that looks indexed.
  const broken = await detailPage({ path: '/demonstration/broken' });
  assert.equal(broken.status, 503);
  assert.equal(broken.headers?.['Retry-After'], '30');
  const started = performance.now();
  assert.equal((await detailPage({ path: '/demonstration/slow' })).status, 503);
  assert(performance.now() - started < 2500, 'The head read is bounded');

  // Sub-paths, a trailing slash and the bare route still belong to Flask.
  const unowned = ['/demonstration/may-day-2026/ics', '/demonstration/may-day-2026/children',
    '/demonstration/may-day-2026/', '/demonstration/'];
  const apiBefore = localReads.length;
  const readsBefore = detailSessionReads;
  for (const path of unowned) {
    assert.equal((await detailPage({ path })).status, 404, path);
  }
  assert.equal(localReads.length, apiBefore, 'Unowned paths must not query the API');
  assert.equal(detailSessionReads, readsBefore, 'Unowned paths must not read the session');
  assert(detailSessionReads >= readsAfterFirstPage, 'Detail pages do read the session summary');
  for (const read of localReads) {
    assert(read.includes('?lang=fi'), `The head read asks for the page language: ${read}`);
  }
  assert.equal(publicReads.length, 0, 'Server reads must use the local API address');

  // A repeated view reuses the cached head instead of another API request.
  const readsBeforeRepeat = localReads.length;
  const repeated = await detailPage({ path: '/demonstration/may-day-2026' });
  assert.equal(repeated.status, 200);
  assert.equal(localReads.length, readsBeforeRepeat, 'A repeat view must not re-read the head');

  // The home batch is read once by the server and inlined for the browser.
  const homeFirst = await detailPage({ path: '/' });
  assert.equal(homeFirst.status, 200);
  assert.equal(bootstrap(homeFirst.html).home.events.length, 1);
  assert.equal(bootstrap(homeFirst.html).config.apiBase, apiBase, 'The browser keeps the public API base');
  const homeReads = localReads.filter(read => read.includes('/home')).length;
  assert.equal(homeReads, 1, 'The home batch is read once');
  const homeAgain = await detailPage({ path: '/' });
  assert.equal(bootstrap(homeAgain.html).home.events.length, 1);
  assert.equal(localReads.filter(read => read.includes('/home')).length, homeReads, 'The home batch is cached');
  // The series page renders the selected occurrence with its own canonical.
  const seriesPage = await detailPage({ path: `/demonstration/${seriesParent}/children` });
  assert.equal(seriesPage.status, 200);
  const seriesBootstrap = bootstrap(seriesPage.html);
  assert.equal(seriesBootstrap.detail.id, childUpcoming, 'The next active occurrence is shown first');
  assert.equal(seriesBootstrap.detail.canonicalUrl,
    `https://example.test/demonstration/${seriesParent}/children`, 'Sharing uses the series URL');
  assert.deepEqual(seriesBootstrap.series.occurrences.map(item => item.id),
    [childUpcoming, childCancelled, childPast], 'Upcoming, then cancelled and past occurrences');
  assert.equal(seriesBootstrap.series.occurrences[0].selected, true);
  assert.equal(seriesBootstrap.series.occurrences[0].url,
    `/demonstration/${seriesParent}/children?occurrence=occurrence-a`);
  assert.match(seriesPage.html,
    new RegExp(`<link rel="canonical" href="https://example.test/demonstration/${seriesParent}/children">`));
  assert.match(seriesPage.html, /<meta name="robots" content="index, follow" \/>/);
  assert.match(seriesPage.html, /"@type":"Event"/, 'The selected occurrence still carries structured data');

  const chosen = await detailPage({ path: `/demonstration/${seriesParent}/children`, search: '?occurrence=occurrence-b' });
  assert.equal(bootstrap(chosen.html).detail.id, childPast, 'A requested occurrence wins');

  const archived = await detailPage({ path: `/demonstration/${seriesParent}/children`, search: '?occurrence=archived-child' });
  assert.equal(bootstrap(archived.html).detail.id, archivedChild, 'An explicit archive link bypasses the chooser window');
  const cancelledChoice = await detailPage({ path: `/demonstration/${seriesParent}/children`, search: '?occurrence=occurrence-c' });
  assert.equal(bootstrap(cancelledChoice.html).detail.id, childCancelled, 'An explicit cancelled occurrence remains selectable');
  const foreignChoice = await detailPage({ path: `/demonstration/${seriesParent}/children`, search: '?occurrence=orphan-child' });
  assert.equal(bootstrap(foreignChoice.html).detail.id, childUpcoming, 'A foreign occurrence cannot override series membership');
  assert.equal((await detailPage({ path: `/demonstration/${seriesParent}/children`, search: '?occurrence=broken' })).status,
    503, 'An unavailable explicit selection does not silently show another event');
  const unchangedSeries = await detailPage({ path: `/demonstration/${seriesParent}/children` });
  assert.equal(bootstrap(unchangedSeries.html).series.occurrences.length, seriesOccurrences.length,
    'An explicit selection does not expand the shared cached chooser');

  // A public series redirects its occurrence URLs to the series page.
  const moved = await detailPage({ path: '/demonstration/occurrence-a' });
  assert.equal(moved.status, 301);
  assert.equal(moved.redirect, `/demonstration/${seriesParent}/children?occurrence=occurrence-a`);

  // An occurrence whose parent series is not public stands on its own.
  const orphan = await detailPage({ path: '/demonstration/orphan-child' });
  assert.equal(orphan.status, 200);
  assert.equal(bootstrap(orphan.html).detail.identifier, 'orphan-child');

  // A series without any date in the discovery window stays noindex.
  const farSeries = await detailPage({ path: `/demonstration/${farParent}/children` });
  assert.equal(farSeries.status, 200);
  assert.equal(farSeries.headers?.['X-Robots-Tag'], 'noindex, follow');
  assert.equal((await detailPage({ path: '/demonstration/nothex/children' })).status, 404,
    'A series parent must be an ObjectId');
  assert.equal((await detailPage({ path: `/demonstration/${orphanParent}/children` })).status, 404,
    'A nonpublic series is 404');
  console.log('PASS: detail head metadata, canonical, JSON-LD, noindex header, preview redirect, bounded 503, local read base, head and home caching, series page and occurrence redirect, unowned sub-paths');
  const beforeListing = localReads.filter(read => read.startsWith('/api/demonstrations?')).length;
  const listings = await Promise.all(Array.from({ length: 8 }, () => detailPage({ path: '/demonstrations', search: '?utm_source=review' })));
  assert(listings.every(result => bootstrap(result.html).listing.page.results.length === 1));
  await detailPage({ path: '/demonstrations' });
  assert.equal(localReads.filter(read => read.startsWith('/api/demonstrations?')).length, beforeListing + 1,
    'Concurrent and warm listings coalesce and ignore campaign cache fragmentation');
  const cityPage = await detailPage({ path: '/city/helsinki', search: '?city=Tampere' });
  assert.match(cityPage.html, /Helsinki: Mielenosoitukset/);
  assert(localReads.some(read => read.startsWith('/api/demonstrations?') && read.includes('city=Helsinki')));
  const tagPage = await detailPage({ path: '/tag/rauha' });
  assert.match(tagPage.html, /#rauha: Mielenosoitukset/);
  assert.equal(bootstrap(tagPage.html).listing.page.total, 1);
  for (const path of ['/pride-nakyvaksi', '/pride', '/pride/']) {
    const pride = await detailPage({ path, search: '?tag=rauha&city=Tampere' });
    assert.equal(pride.status, 200);
    assert.match(pride.html, /<link rel="canonical" href="https:\/\/example.test\/pride-nakyvaksi">/);
    assert.match(pride.html, /<title>Pride näkyväksi \| Mielenosoitukset.fi<\/title>/);
    assert.match(pride.html, /leaflet\/leaflet.js/);
    assert.match(pride.html, /<noscript>[^]*Test listing event[^]*<\/noscript>/);
    assert.match(pride.html, /<noscript>[^]*Miksi Pride näkyväksi\?[^]*id="demo-guidelines"[^]*<\/noscript>/);
    assert.match(pride.html, /<noscript>[^]*Näytetään [^]*Kaikki mielenosoitukset[^]*<\/noscript>/);
    assert.match(pride.html, /<noscript>[^]*kun JavaScript on käytössä[^]*<\/noscript>/);
    assert.equal(bootstrap(pride.html).route.name, 'pride');
  }
  assert(localReads.some(read => read.startsWith('/api/demonstrations?') && read.includes('tag=pride') && read.includes('city=Tampere')
    && !read.includes('tag=rauha')), 'Pride keeps its fixed tag and accepts listing filters');
  console.log('PASS: listing bootstrap, query coalescing/cache, canonical city/tag titles and fixed scopes, Pride aliases');
  const beforeCities = localReads.filter(read => read === '/api/cities').length;
  const cityDocuments = await Promise.all(Array.from({ length: 8 }, () => detailPage({ path: '/cities' })));
  assert.equal(localReads.filter(read => read === '/api/cities').length, beforeCities + 1);
  const directory = cityDocuments[0];
  assert.equal(directory.status, 200);
  assert.equal(bootstrap(directory.html).cities.cities[0].upcoming_count, 3);
  assert(!directory.html.includes('DO-NOT-BOOTSTRAP'));
  assert.match(directory.html, /<link rel="canonical" href="https:\/\/example.test\/cities">/);
  assert.equal((directory.html.match(/<title>/g) ?? []).length, 1);
  assert.match(directory.html, /"@type":"CollectionPage"/);
  const todayDocument = await detailPage({ path: '/city/helsinki/tanaan', search: '?city=Tampere&date_start=2000-01-01&in_past=true&parent_id=foreign' });
  assert.equal(todayDocument.status, 200);
  assert.match(todayDocument.html, /Mielenosoitukset Helsingissä tänään/);
  const todayRead = localReads.filter(read => read.startsWith('/api/demonstrations?') && read.includes('today=true')).at(-1);
  assert(todayRead && todayRead.includes('city=Helsinki') && !/date_start|in_past|parent_id/.test(todayRead));
  assert.equal((todayDocument.html.match(/rel="canonical"/g) ?? []).length, 1);
  assert.equal((await detailPage({ path: '/city/not-a-city/tanaan' })).status, 404);
  assert.equal((await detailPage({ path: '/mielenosoitukset-tanaan' })).status, 200);
  const unavailableCities = await detailPage({ path: '/cities', apiReadBase: `${apiReadBase}/missing-api` });
  assert.equal(unavailableCities.status, 503);
  assert.equal(bootstrap(unavailableCities.html).cities, null);
  assert.equal(unavailableCities.headers['X-Robots-Tag'], 'noindex, follow');
  console.log('PASS: city directory coalescing/public projection, today locked filters, canonical/head/structured data and invalid-city404');
  const monthReads = localReads.filter(read => read === '/api/calendar/2028/2').length;
  const calendarPages = await Promise.all(Array.from({ length: 8 }, () => detailPage({ path: '/calendar/2028/2/' })));
  assert.equal(localReads.filter(read => read === '/api/calendar/2028/2').length, monthReads + 1);
  const month = calendarPages[0];
  assert.equal(month.status, 200);
  assert.equal(bootstrap(month.html).calendar.day, 29);
  assert.match(month.html, /<link rel="canonical" href="https:\/\/example.test\/calendar\/2028\/2\/">/);
  assert.match(month.html, /"@type":"CollectionPage"/);
  assert.match(month.html, /<noscript>.*helmikuu 2028/);
  const leapSelection = await detailPage({ path: '/calendar/2028/2/', search: '?day=29&page=2' });
  assert.equal(bootstrap(leapSelection.html).calendar.day, 29);
  assert.equal(bootstrap(leapSelection.html).calendar.page, 2);
  assert.equal(bootstrap(leapSelection.html).calendar.events.results[0].date, '2028-02-29');
  assert.match(leapSelection.html, /<noscript>[\s\S]*Selected calendar event<\/a>/);
  assert.match(leapSelection.html, /href="\?day=29&amp;page=1#calendar-agenda"|href="\?day=29&page=1#calendar-agenda"/);
  assert.match(leapSelection.html, /noindex, follow/);
  assert.equal((await detailPage({ path: '/calendar/2028/2', search: '?day=29' })).redirect, '/calendar/2028/2/?day=29');
  for (const path of ['/calendar/2028/13/', '/calendar/1999/12/', '/city/not-a-city/calendar/']) assert.equal((await detailPage({ path })).status, 404);
  const annual = await detailPage({ path:'/calendar/2028/' });
  assert.equal(annual.status,200);
  assert.equal(bootstrap(annual.html).calendar.data.total,3);
  assert.equal(bootstrap(annual.html).route.name,'calendar-year');
  assert.match(annual.html,/rel="canonical" href="https:\/\/example.test\/calendar\/2028\/"/);
  const cityAnnual = await detailPage({ path:'/city/helsinki/calendar/2028/' });
  assert.equal(bootstrap(cityAnnual.html).calendar.data.total,2);
  assert.equal(bootstrap(cityAnnual.html).calendar.city,'helsinki');
  assert.match(cityAnnual.html,/href="\/city\/helsinki\/calendar\/2028\/2\/"/);
  const cityMonth = await detailPage({ path:'/city/helsinki/calendar/2028/2/', search:'?day=29' });
  assert.equal(cityMonth.status,200);
  assert(bootstrap(cityMonth.html).calendar.events);
  assert(localReads.some(read=>read.startsWith('/api/demonstrations?') && read.includes('date_start=2028-02-29') && read.includes('city=Helsinki')));
  assert.equal((await detailPage({ path:'/calendar/2028/',search:'?city=Helsinki' })).redirect,'/city/helsinki/calendar/2028/');
  assert.equal((await detailPage({ path:'/city/helsinki/calendar/2028/',search:'?city=' })).redirect,'/calendar/2028/');
  assert.equal((await detailPage({ path:'/city/HELSINKI/calendar/2028/' })).redirect,'/city/helsinki/calendar/2028/');
  const unavailableCalendar = await detailPage({ path: '/calendar/2028/2/', apiReadBase: `${apiReadBase}/missing-api` });
  assert.equal(unavailableCalendar.status, 503);
  assert.equal(unavailableCalendar.headers['X-Robots-Tag'], 'noindex, follow');
  console.log('PASS: calendar year/month/city scopes, cache/coalescing, leap day, canonical/no-JS/metadata, query preservation, native area form redirects and failed-read503');
  const beforeOrganizations = localReads.filter(read => read.startsWith('/api/organizations/')).length;
  const organizationPages = await Promise.all(Array.from({ length: 8 }, () => detailPage({ path: `/organization/${organizationId}` })));
  await detailPage({ path: `/organization/${organizationId}` });
  assert.equal(localReads.filter(read => read.startsWith('/api/organizations/')).length, beforeOrganizations + 1);
  assert(organizationPages.every(result => result.status === 200 && bootstrap(result.html).organization.listing.page));
  assert(!organizationPages[0].html.includes('private@example.test'));
  assert(!organizationPages[0].html.includes('private-user'));
  assert.match(organizationPages[0].html, /"@type":"Organization"/);
  const [orgAlice, orgBob] = await Promise.all(['alice', 'bob'].map(name => detailPage({
    path: `/organization/${organizationId}`, cookie: `session=${name}`,
  })));
  assert.equal(bootstrap(orgAlice.html).session.organization.following, true);
  assert.equal(bootstrap(orgBob.html).session.organization.following, false);
  assert.equal(bootstrap(organizationPages[0].html).session.organization, undefined);
  const restricted = await detailPage({ path: `/organization/${organizationId}`,
    search: '?organization_id=foreign&parent_id=foreign&in_past=true&max_days_till=1' });
  assert(restricted.status === 200);
  const scopedRead = localReads.filter(read => read.startsWith('/api/demonstrations?') && read.includes(`organization_id=${organizationId}`)).at(-1);
  assert(scopedRead && !/parent_id|in_past|max_days_till/.test(scopedRead));
  const missingOrg = await detailPage({ path: '/organization/66fa58601102367d5d528098' });
  assert.equal(missingOrg.status, 302); assert.equal(missingOrg.redirect, '/');
  const fill = await detailPage({ path: `/organization/${organizationId}/fill` });
  assert.equal(fill.status, 200);
  const fillBody = fill.html.split('<body>')[1].split('<script type="application/json"')[0];
  for (const text of ['Test Organization', `action="/organization/${organizationId}/save_suggestion"`, 'method="post"',
    'name="logo"', 'Lisää alusta', 'Nykyiset tiedot', 'Tallenna ehdotus']) assert(fillBody.includes(text), text);
  assert(!fillBody.includes('value="None"') && !fillBody.includes('org-fill-label'));
  assert.match(fill.html, /<meta name="robots" content="noindex, follow" \/>/);
  const missingFill = await detailPage({ path: '/organization/66fa58601102367d5d528098/fill' });
  assert.equal(missingFill.status, 302); assert.equal(missingFill.redirect, '/');
  console.log('PASS: organization cache/coalescing, public projection, private scoped sessions, fixed event scope and missing organizations and the fill-in form');
} finally {
  publicApi.closeAllConnections?.();
  localApi.closeAllConnections?.();
  await new Promise(resolve => publicApi.close(resolve));
  await new Promise(resolve => localApi.close(resolve));
  await new Promise(resolve => detailSession.close(resolve));
}

const socketDirectory = mkdtempSync(join(tmpdir(), 'moso-session-'));
const socketPath = join(socketDirectory, 'flask.sock');
let socketReads = 0;
const socketServer = createServer((req, res) => {
  socketReads++;
  assert.equal(req.headers.host, 'mielenosoitukset.fi');
  assert.equal(req.headers['x-forwarded-proto'], 'https');
  if (req.headers.cookie === 'session=alice') assert.equal(req.headers['x-forwarded-for'], '192.0.2.1');
  if (req.headers.cookie === 'session=alice') assert.equal(req.headers['cf-connecting-ip'], '2001:db8::1');
  if (req.headers.cookie === 'session=bob') assert.equal(req.headers['x-forwarded-for'], undefined);
  if (req.url === '/slow') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.write('{'); setTimeout(() => res.end('}'), 2000); return;
  }
  if (req.url === '/aborted') { res.writeHead(200, { 'Content-Type': 'application/json' }); res.write('{'); res.destroy(); return; }
  if (req.url === '/redirect') { res.writeHead(302, { Location: '/api/session' }); res.end(); return; }
  if (req.url === '/invalid') { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end('<html>'); return; }
  if (req.url === '/api/session?translation_join=1' && req.headers.cookie === 'session=translator-candidate') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Set-Cookie': ['session=updated; Path=/; HttpOnly'] });
    res.end(JSON.stringify({ authenticated: true, translation_join: { joined: false, csrf_token: 't'.repeat(43) } }));
    return;
  }
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
  const [alice, bob] = await Promise.all([
    socketPage({ cookie: 'session=alice', clientIp: '192.0.2.1', cloudflareIp: '2001:db8::1' }),
    socketPage({ cookie: 'session=bob', clientIp: 'invalid, 192.0.2.2' }),
  ]);
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
  const joinPage = { path: '/upcoming/translations/', cookie: 'session=translator-candidate' };
  const joinResponse = await socketPage(joinPage);
  assert.deepEqual(joinResponse.headers['Set-Cookie'], ['session=updated; Path=/; HttpOnly']);
  assert(joinResponse.html.includes(`name="csrf_token" value="${'t'.repeat(43)}"`));
  const joinHead = await socketPage({ ...joinPage, headOnly: true });
  assert.equal(joinHead.headers['Set-Cookie'], undefined);
  assert(!joinHead.html.includes('name="csrf_token"'));
  const guestJoin = await socketPage({ path: joinPage.path });
  assert(!guestJoin.html.includes('name="csrf_token"') && !guestJoin.headers['Set-Cookie']);
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
// The spawned host serves a detail page through the real HTTP server: headers,
// the preview redirect and the query flag all have to survive that layer.
let publicAvailable = true;
const hostApi = createServer((req, res) => {
  if (req.url === '/api/public-status') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ available: publicAvailable }));
    return;
  }
  if (req.url === '/toggle-lockdown') {
    publicAvailable = false;
    res.end('ok');
    return;
  }
  const identifier = decodeURIComponent(new URL(req.url, 'http://api.test').pathname.split('/').pop() ?? '');
  if (identifier === 'nonpublic') { res.writeHead(404); res.end('{}'); return; }
  res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ _id: detailId, title: 'Test event', description: 'Kuvaus',
    slug: identifier, running_number: 4242, date: identifier === 'far-future' ? '2035-01-01' : '2026-12-01',
    start_time: '14:00', end_time: '15:00', cancelled: false, city: 'Helsinki', address: null, preview_image: null }));
});
await new Promise(resolve => hostApi.listen(0, '127.0.0.1', resolve));
const hostSession = createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ authenticated: true, name: 'Alice', locale: 'fi',
    locales: [{ code: 'fi', name: 'Suomi' }], site_analytics_enabled: false, matomo_enabled: false }));
});
await new Promise(resolve => hostSession.listen(0, '127.0.0.1', resolve));
const child = spawn(process.execPath, ['frontend/server.mjs'], { cwd: root,
  env: { ...process.env, APP_PORT: String(port),
    SESSION_URL: `http://127.0.0.1:${hostSession.address().port}/api/session`,
    PUBLIC_API_BASE: `http://127.0.0.1:${hostApi.address().port}/api`,
    APP_BUILD_SHA: 'verification-build', FLASK_SOCKET_PATH: '' }, stdio: ['ignore', 'pipe', 'pipe'] });
const get = (path, method = 'GET', headers = {}) => new Promise((resolve, reject) => {
  const req = request({ hostname: '127.0.0.1', port, path, method, headers }, res => {
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
  const detail = await get('/demonstration/may-day-2026');
  assert.equal(detail.status, 200);
  assert.match(detail.body, /<link rel="canonical" href="http:\/\/127\.0\.0\.1:\d+\/demonstration\/may-day-2026">/);
  assert.equal(detail.headers['x-robots-tag'], undefined);
  const farFuture = await get('/demonstration/far-future');
  assert.equal(farFuture.headers['x-robots-tag'], 'noindex, follow', 'The robots header reaches the browser');
  const signedIn = { Cookie: 'session=alice' };
  assert.equal((await get('/demonstration/nonpublic')).status, 404, 'Anonymous visitors keep the 404');
  const preview = await get('/demonstration/nonpublic', 'GET', signedIn);
  assert.equal(preview.status, 302);
  assert.equal(preview.headers.location, '/demonstration/nonpublic?preview=1');
  assert.match(preview.headers['cache-control'], /no-store/);
  assert.equal((await get('/demonstration/nonpublic?preview=1', 'GET', signedIn)).status, 404,
    'The flagged request must not redirect again');
  // A security lockdown must stop public pages, yet keep recovery entry points
  // reachable so the board can sign in and reopen the site.
  await new Promise((resolve, reject) => {
    request(`http://127.0.0.1:${hostApi.address().port}/toggle-lockdown`, res => { res.resume(); res.on('end', resolve); })
      .on('error', reject).end();
  });
  await new Promise(resolve => setTimeout(resolve, 1100));
  const locked = await get('/demonstration/may-day-2026');
  assert.equal(locked.status, 503, 'Locked public page must not be served');
  assert.equal(locked.headers['retry-after'], '60');
  assert.equal(locked.headers['x-robots-tag'], 'noindex');
  assert.match(locked.body, /Palvelu on tilapäisesti suljettu/);
  assert.equal(locked.headers['cache-control'], 'no-store');
  assert.equal((await get('/health')).status, 200, 'Health stays available during a lockdown');
  assert.notEqual((await get('/auth/god')).status, 503, 'God login stays reachable during a lockdown');
  console.log('PASS: public lockdown returns 503 with Retry-After and keeps health and god login reachable');
  {
    const { availabilityReader, AVAILABILITY_GRACE_MS } = await import(pathToFileURL(`${root}/frontend/public-availability.mjs`));
    let clock = 1_000_000;
    let reply = 'error';
    const fetcher = async () => {
      if (reply === 'error') throw new Error('connection refused');
      if (reply === 'http-503') return new Response('{}', { status: 503 });
      return new Response(JSON.stringify({ available: reply === 'open' }), { status: 200 });
    };
    const read = availabilityReader('http://api.test/api', fetcher, () => clock);
    const step = async (next, ms = 2000) => { reply = next; clock += ms; return read(); };
    assert.equal(await step('error'), false, 'A fresh host without an answer fails closed');
    assert.equal(await step('open'), true);
    assert.equal(await step('error'), true, 'A failed read within the grace period keeps the last open answer');
    assert.equal(await step('http-503'), true, 'An HTTP error is a failed read, not a lockdown');
    assert.equal(await step('error', AVAILABILITY_GRACE_MS), false, 'A failure outlasting the grace period fails closed');
    assert.equal(await step('open'), true);
    assert.equal(await step('locked'), false, 'An explicit lockdown applies at once');
    assert.equal(await step('error'), false, 'A failed read after a lockdown does not reopen the site');
    reply = 'open';
    assert.equal(await read(), false, 'Answers are reused for one second');
  }
  console.log('PASS: availability reads ride out brief failures for 30 s but apply a lockdown at once and fail closed without an answer');
  console.log('PASS: malformed URL, directory and traversal requests return 404 without crashing; real asset GET/HEAD and immutable caching');
  console.log('PASS: the HTTP server sends detail metadata, the robots header and the preview redirect');
} finally {
  child.kill('SIGTERM');
  hostApi.closeAllConnections?.();
  await new Promise(resolve => hostApi.close(resolve));
  await new Promise(resolve => hostSession.close(resolve));
}
