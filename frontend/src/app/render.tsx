import { appConfig } from './config';
import { randomUUID } from 'node:crypto';
import { renderToStaticMarkup } from 'react-dom/server';
import { SubmitFallback } from './SubmitFallback';
import { submitProps } from './submit';
import type { SubmitBootstrap } from './submit';
import { detailMessages } from './detail';
import { loadDetailHead, loadSeries, selectOccurrence, seriesNavigation, seriesPath } from './detail-route';
import type { DetailBootstrap, DetailSeries } from './detail-route';
import { catalog } from './i18n';
import { ttlCache } from './server-cache';
import { listingProps, listingQuery, loadListingPage } from './listing';
import type { ListingBootstrap } from './listing';
import { loadOrganization } from './organization';
import type { OrganizationBootstrap } from './organization';
import { dayLabel, findCity, helsinkiDay, loadCities } from './cities';
import type { CitiesData } from './cities';
import { citiesMeta, todayMeta, cityItems, todayItems, discoveryStructuredData } from './discovery-meta';
import type { HomeData } from '../pages/HomePage';
import { routeForPath, routeMeta } from './routes';
import type { RouteMeta } from './routes';
import { fetchSession } from './session-server';
import type { SessionSummary } from './session';

/**
 * Metadata-only server rendering.
 *
 * The server writes the document head (title, description, robots, social
 * previews, favicons, theme bootstrap and stylesheets) and an empty app root.
 * Page components render in the browser, except a small React-owned no-JS form.
 * Routes whose metadata comes from an event do one projected API read for the
 * head; the page body is still fetched by the browser.
 */

export type RenderInput = {
  path: string;
  origin: string;
  /** Public API base the browser uses; also the fallback read base. */
  apiBase: string;
  /** Preferred server-side read base, e.g. the API on loopback. */
  apiReadBase?: string;
  sessionUrl: string;
  flaskSocketPath?: string;
  clientIp?: string;
  cloudflareIp?: string;
  cookie?: string;
  doNotTrack?: boolean;
  /** Raw query string; used only to detect the Flask preview fallback. */
  search?: string;
};

export type RenderAssets = { head: string; scripts: string; listing?: string; organization?: string; cities?: string; today?: string; submit?: string };

export type RenderResult = {
  status: number;
  html: string;
  headers?: Record<string, string>;
  /** Absolute or site-relative redirect target; the server sends Location. */
  redirect?: string;
};

const escapeHtml = (value: string) => value
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

/** JSON in a script element must not be able to close the element. */
const serialize = (value: unknown) => JSON.stringify(value)
  .replaceAll('<', '\\u003c').replaceAll('>', '\\u003e')
  .replaceAll('&', '\\u0026').replaceAll('\u2028', '\\u2028').replaceAll('\u2029', '\\u2029');

/** The existing detail stylesheet; the host page uses the same markup. */
const DETAIL_STYLESHEET = '/static/css/public-detail.css?v=20261101-react-detail-2';

/**
 * The home batch is the same for every anonymous visitor, so the server reads it
 * once and inlines it. The browser then paints cards without a second request.
 */
const HOME_CACHE_TTL_MS = 30_000;
const HOME_TIMEOUT_MS = 1200;
const homeBatches = ttlCache<HomeData>(HOME_CACHE_TTL_MS, 4);

function validHomeData(value: unknown): value is HomeData {
  if (!value || typeof value !== 'object') return false;
  const data = value as Record<string, unknown>;
  if (!Array.isArray(data.events) || data.events.length > 50 || typeof data.recommended !== 'boolean') return false;
  return data.events.every((event) => {
    if (!event || typeof event !== 'object') return false;
    const item = event as Record<string, unknown>;
    return typeof item._id === 'string' && typeof item.title === 'string';
  });
}

async function loadHomeBatch(readBase: string, locale: string): Promise<HomeData | null> {
  const key = `${readBase}\n${locale}`;
  const cached = homeBatches.get(key);
  if (cached) return cached;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HOME_TIMEOUT_MS);
  try {
    const response = await fetch(`${readBase}/home?lang=${encodeURIComponent(locale)}`, {
      signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' },
    });
    if (!response.ok) return null;
    const data = await response.json();
    if (!validHomeData(data)) return null;
    homeBatches.set(key, data);
    return data;
  } catch {
    // The page still works: the browser retries its own request after hydration.
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function headMarkup(options: {
  title: string; description: string; robots: string; canonical: string | null;
  url: string; origin: string; locale: string; assets: string;
  siteAnalyticsEnabled: boolean;
  image?: string | null;
  jsonLd?: unknown;
  extraHead?: string;
}) {
  const ogImage = options.image ?? `${options.origin}/static/images/og-default.jpg`;
  return `<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preconnect" href="https://cdn2.mielenosoitukset.fi" crossorigin>
<link rel="preload" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"></noscript>
<script>
  (function () {
    let theme = null;
    try { theme = localStorage.getItem('theme'); } catch (e) {}
    if (!theme) {
      try {
        const user = JSON.parse(localStorage.getItem('current_user') || 'null');
        if (user && typeof user.dark_mode === 'boolean') theme = user.dark_mode ? 'dark' : 'light';
      } catch (e) {}
    }
    if (!theme) theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    const root = document.documentElement;
    root.classList.add('js');
    root.classList.toggle('dark', theme === 'dark');
    root.classList.toggle('light', theme !== 'dark');
  })();
</script>
<link rel="alternate" type="application/rss+xml" title="Mielenosoitukset.fi: RSS" href="${escapeHtml(options.origin)}/demonstrations.rss">
<title>${escapeHtml(options.title)}</title>
<meta name="description" content="${escapeHtml(options.description)}" />
<meta name="keywords" content="mielenosoitukset, aktivismi, Suomi" />
<meta name="robots" content="${escapeHtml(options.robots)}" />
${options.canonical ? `<link rel="canonical" href="${escapeHtml(options.canonical)}">` : ''}
<meta name="author" content="Mielenosoitukset.fi" />
<meta name="theme-color" content="#007bff" />
<link rel="apple-touch-icon" sizes="180x180" href="/static/icons/icon_apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/static/icons/icon_favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/static/icons/icon_favicon-16x16.png">
<link rel="manifest" href="/manifest.json">
<link rel="shortcut icon" href="/static/icons/favicon.ico" type="image/x-icon">
<meta property="og:title" content="${escapeHtml(options.title)}" />
<meta property="og:description" content="${escapeHtml(options.description)}" />
<meta property="og:image" content="${escapeHtml(ogImage)}" />
<meta property="og:url" content="${escapeHtml(options.url)}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Mielenosoitukset.fi" />
<meta property="og:locale" content="${escapeHtml(options.locale)}_FI" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="${escapeHtml(options.title)}" />
<meta name="twitter:description" content="${escapeHtml(options.description)}" />
<meta name="twitter:image" content="${escapeHtml(ogImage)}" />
<meta name="twitter:site" content="@Mielenosoitukset" />
<meta name="twitter:creator" content="@Mielenosoitukset" />
<meta name="twitter:image:alt" content="Mielenosoituksen kuva" />
${options.jsonLd ? `<script type="application/ld+json">${serialize(options.jsonLd)}</script>` : ''}
<link rel="preload" href="/static/css/style.css?v=20261015-heading-1" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="/static/css/style.css?v=20261015-heading-1"></noscript>
<link rel="preload" href="/static/fa/css/all.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="/static/fa/css/all.css"></noscript>
<link rel="preload" href="https://cdn2.mielenosoitukset.fi/vendor/bootstrap/5.3.0/bootstrap.min.css" as="style" crossorigin onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn2.mielenosoitukset.fi/vendor/bootstrap/5.3.0/bootstrap.min.css" crossorigin></noscript>
<link rel="stylesheet" href="/static/css/home.css">
<link rel="stylesheet" href="/static/css/product-tokens.css?v=20261027-product-tokens-1">
<link rel="stylesheet" href="/static/css/user-workspace.css?v=20261028-user-workspace-2">
<link rel="stylesheet" href="/static/css/public-header.css?v=20261027-react-header-1">
<link rel="stylesheet" href="/static/css/flash.css?v=20260928-campaign-feedback-1">
<link rel="stylesheet" href="/static/css/public_hero.css?v=20261015-hero-width-1">
${options.extraHead ?? ''}
${options.siteAnalyticsEnabled ? `<script src="https://cdn2.mielenosoitukset.fi/vendor/web-vitals/6.2.2/web-vitals.iife.js" integrity="sha256-Hl6bmva41xz+9QjlqGnFO0zyu8ytjJtaxmTDTpP2FRo=" defer crossorigin="anonymous"></script>
<script src="/static/js/site_analytics.js" defer></script>` : ''}
${options.assets}`;
}

function notFoundDocument() {
  return `<!DOCTYPE html><html lang="fi"><head>
<meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="robots" content="noindex, follow" /><title>404 | Mielenosoitukset.fi</title>
<link rel="stylesheet" href="/static/css/style.css"></head>
<body><main id="main-content" class="container-main-content"><h1>404</h1>
<p><a href="/">Mielenosoitukset.fi</a></p></main></body></html>`;
}

function unavailableDocument() {
  return '<!DOCTYPE html><html lang="fi"><head><meta charset="UTF-8" />'
    + '<meta name="robots" content="noindex, follow" />'
    + '<title>Palvelu ei ole juuri nyt käytettävissä</title></head>'
    + '<body><h1>Palvelu ei ole juuri nyt käytettävissä</h1></body></html>';
}

export async function renderPage(input: RenderInput, assets: RenderAssets): Promise<RenderResult> {
  const route = routeForPath(input.path);
  if (!route) return { status: 404, html: notFoundDocument() };
  const readBase = input.apiReadBase ?? input.apiBase;
  if (route.name === 'today' && route.value && !findCity(route.value)) {
    return { status: 404, html: notFoundDocument(), headers: { 'X-Robots-Tag': 'noindex, follow' } };
  }
  const organizationRead = route.name === 'organization' ? loadOrganization(readBase, route.id) : null;
  const citiesRead = route.name === 'cities' ? loadCities(readBase) : null;
  let sessionUrl = input.sessionUrl;
  if (route.name === 'organization' && input.cookie) {
    const scoped = new URL(sessionUrl);
    scoped.searchParams.set('organization_id', route.id);
    sessionUrl = scoped.href;
  }
  const summary: SessionSummary = await fetchSession(sessionUrl, input.cookie,
    1200, input.flaskSocketPath, input.origin, input.clientIp, input.cloudflareIp);
  const session = input.doNotTrack
    ? { ...summary, siteAnalyticsEnabled: false, matomoEnabled: false }
    : summary;
  const config = appConfig({
    origin: input.origin, apiBase: input.apiBase, locale: session.locale,
    path: input.path, locales: session.locales,
  });
  const text = catalog(config.locale);

  let meta: RouteMeta = routeMeta(route, config, text);
  let detail: DetailBootstrap | undefined;
  let series: DetailSeries | undefined;
  let home: HomeData | null = null;
  let listing: ListingBootstrap | undefined;
  let organization: OrganizationBootstrap | undefined;
  let cities: CitiesData | null | undefined;
  let submission: SubmitBootstrap | undefined;
  let status = 200;
  let jsonLd: unknown;
  let extraHead = '';
  let noscript = '<noscript><p class="container-main-content">Mielenosoitukset.fi käyttää JavaScriptiä. '
    + '<a href="/demonstrations">Kaikki mielenosoitukset</a> · <a href="/calendar/">Kalenteri</a></p></noscript>';
  const headers: Record<string, string> = {};

  if (route.name === 'submit') {
    const settings = session.submission;
    submission = { token: randomUUID().replaceAll('-', ''), locales: settings?.locales ?? ['fi'],
      defaultLanguage: settings?.defaultLanguage ?? 'fi', canEditDemo: settings?.canEditDemo ?? false,
      sent: new URLSearchParams(input.search ?? '').get('sent') === '1',
      conflict: new URLSearchParams(input.search ?? '').get('conflict') === '1' };
    meta = { title: 'Ilmoita mielenosoituksesta | Mielenosoitukset.fi',
      description: 'Ilmoita mielenosoituksesta ja auta muita löytämään tapahtuma. Tarkistamme ilmoituksen ennen julkaisua.',
      canonical: `${config.origin}/submit`, robots: submission.sent || submission.conflict ? 'noindex, follow' : 'index, follow' };
    headers['Cache-Control'] = 'no-store';
    extraHead = '<link rel="stylesheet" href="/static/css/submit.css?v=20261102-submit-calendar-grid-1">'
      + (assets.submit ?? '');
    const props = submitProps(config, submission);
    noscript = `<noscript>${submission.sent
      ? `<article class="submit-page"><h1>${escapeHtml(props.messages.successTitle)}</h1><p>${escapeHtml(props.messages.successBody)}</p><a href="/">${escapeHtml(props.messages.backHome)}</a></article>`
      : (submission.conflict ? `<p role="alert">${escapeHtml(props.messages.conflictTitle)}. ${escapeHtml(props.messages.errorConflictCancelled)}</p>` : '') + renderToStaticMarkup(<SubmitFallback {...props} />)}</noscript>`;
  }

  if (route.name === 'detail') {
    const loaded = await loadDetailHead(route.identifier, config, readBase);
    if (loaded.status === 'unavailable') {
      // Never answer a down backend with a page that looks fine to a crawler.
      return { status: 503, html: unavailableDocument(), headers: { 'Cache-Control': 'no-store', 'Retry-After': '30' } };
    }
    if (loaded.status === 'not-found') {
      // A signed-in visitor may still be able to preview a nonpublic event; the
      // preview workflow stays on Flask behind an explicit query flag.
      const askedForPreview = new URLSearchParams(input.search ?? '').has('preview');
      if (session.authenticated && !askedForPreview) {
        return { status: 302, html: '', redirect: `${input.path}?preview=1` };
      }
      return { status: 404, html: notFoundDocument(), headers: { 'X-Robots-Tag': 'noindex, follow' } };
    }
    // An occurrence of a public series lives on the series page, exactly like the
    // Flask redirect. A nonpublic parent leaves the occurrence standing alone.
    if (loaded.parent) {
      const parentSeries = await loadSeries(loaded.parent, config, readBase);
      if (parentSeries.status === 'ready') {
        const target = seriesPath(config, loaded.parent, loaded.slug ?? loaded.bootstrap.id);
        return { status: 301, html: '', redirect: target };
      }
    }
    const messages = detailMessages(config.locale);
    meta = loaded.meta;
    detail = loaded.bootstrap;
    jsonLd = loaded.jsonLd;
    extraHead = `<link rel="stylesheet" href="${DETAIL_STYLESHEET}">`;
    if (loaded.noindex) headers['X-Robots-Tag'] = 'noindex, follow';
    noscript = `<noscript><article class="public-detail container-main-content">`
      + `<h1>${escapeHtml(loaded.heading)}</h1>`
      + `<p>${escapeHtml(meta.description)}</p>`
      + `<a href="${escapeHtml(config.urls.demonstrations)}">${escapeHtml(messages.allEvents)}</a>`
      + `</article></noscript>`;
  }

  if (route.name === 'series') {
    const loaded = await loadSeries(route.parent, config, readBase);
    if (loaded.status === 'unavailable') {
      return { status: 503, html: unavailableDocument(), headers: { 'Cache-Control': 'no-store', 'Retry-After': '30' } };
    }
    if (loaded.status === 'not-found') {
      return { status: 404, html: notFoundDocument(), headers: { 'X-Robots-Tag': 'noindex, follow' } };
    }
    const requested = new URLSearchParams(input.search ?? '').get('occurrence')?.trim() || null;
    let occurrences = loaded.occurrences;
    if (requested && !loaded.occurrences.some((occurrence) => occurrence.slug === requested
      || occurrence.id === requested
      || (occurrence.runningNumber !== null && String(occurrence.runningNumber) === requested))) {
      // Explicit archive/cancelled links are not limited by the chooser window.
      // The public event read must still prove membership in this exact series.
      const requestedEvent = await loadDetailHead(requested, config, readBase);
      if (requestedEvent.status === 'unavailable') {
        return { status: 503, html: unavailableDocument(), headers: { 'Cache-Control': 'no-store', 'Retry-After': '30' } };
      }
      if (requestedEvent.status === 'ready' && requestedEvent.parent === route.parent) {
        occurrences = [...occurrences, requestedEvent.occurrence];
      }
    }
    const selected = selectOccurrence(occurrences, requested);
    if (!selected) {
      // A series with no active occurrence has nothing to show, like the
      // chooser's empty state, and must stay out of the index.
      return { status: 404, html: notFoundDocument(), headers: { 'X-Robots-Tag': 'noindex, follow' } };
    }
    const event = await loadDetailHead(selected.id, config, readBase);
    if (event.status === 'unavailable') {
      return { status: 503, html: unavailableDocument(), headers: { 'Cache-Control': 'no-store', 'Retry-After': '30' } };
    }
    if (event.status === 'not-found') {
      return { status: 404, html: notFoundDocument(), headers: { 'X-Robots-Tag': 'noindex, follow' } };
    }
    const messages = detailMessages(config.locale);
    const canonical = `${config.origin}${seriesPath(config, route.parent)}`;
    meta = {
      ...event.meta,
      // The series page is canonical for every occurrence, as on Flask.
      canonical,
      robots: loaded.indexable ? 'index, follow' : 'noindex, follow',
    };
    detail = { ...event.bootstrap, canonicalUrl: canonical };
    series = seriesNavigation(config, { ...loaded, occurrences }, selected.id, messages.series);
    jsonLd = event.jsonLd;
    extraHead = `<link rel="stylesheet" href="${DETAIL_STYLESHEET}">`;
    if (!loaded.indexable) headers['X-Robots-Tag'] = 'noindex, follow';
    noscript = `<noscript><article class="public-detail container-main-content">`
      + `<h1>${escapeHtml(event.heading)}</h1>`
      + `<p>${escapeHtml(meta.description)}</p>`
      + `<a href="${escapeHtml(config.urls.demonstrations)}">${escapeHtml(messages.allEvents)}</a>`
      + `</article></noscript>`;
  }

  if (route.name === 'home') home = await loadHomeBatch(readBase, config.locale);
  if (route.name === 'cities') {
    cities = await citiesRead;
    const filters = new URLSearchParams(input.search ?? '');
    meta = citiesMeta(config, cities, Boolean(filters.get('q') || filters.get('today')));
    const items = cityItems(config, cities);
    jsonLd = discoveryStructuredData(meta, items);
    extraHead = assets.cities ?? '';
    noscript = `<noscript><article class="container-main-content"><h1>Kaupungit</h1><p>${escapeHtml(meta.description)}</p>`
      + `<a href="/mielenosoitukset-tanaan">Mielenosoitukset tänään</a><ul>`
      + items.map(item => `<li><a href="${escapeHtml(item.url)}">${escapeHtml(item.name)}</a></li>`).join('') + '</ul></article></noscript>';
    if (!cities) { status = 503; headers['Retry-After'] = '30'; headers['X-Robots-Tag'] = 'noindex, follow'; }
  }
  if (route.name === 'today') {
    const todayRoute = { name: 'listing', scope: route.value ? 'city-today' : 'today', value: route.value } as const;
    const query = listingQuery(todayRoute, input.search ?? '', config.locale);
    listing = { query: input.search ?? '', page: await loadListingPage(readBase, query) };
    meta = todayMeta(config, route.value);
    const items = todayItems(config, listing.page);
    jsonLd = discoveryStructuredData(meta, items);
    extraHead = assets.today ?? '';
    noscript = `<noscript><article class="container-main-content"><h1>${escapeHtml(meta.title.split(' | ')[0])}</h1>`
      + `<p>${escapeHtml(dayLabel(listing.page?.day ?? helsinkiDay()))}</p><p>${escapeHtml(meta.description)}</p><ul>`
      + items.map((item, index) => {
        const event = listing?.page?.results[index];
        const details = [event?.cancelled ? 'Peruttu' : '', event?.start_time, event?.city, event?.address].filter(Boolean).join(' · ');
        return `<li><a href="${escapeHtml(item.url)}">${escapeHtml(item.name)}</a> ${escapeHtml(details)}</li>`;
      }).join('')
      + '</ul><a href="/demonstrations">Kaikki mielenosoitukset</a></article></noscript>';
    if (!listing.page) { status = 503; meta.robots = 'noindex, follow'; headers['Retry-After'] = '30'; headers['X-Robots-Tag'] = 'noindex, follow'; }
  }
  if (route.name === 'listing') {
    const props = listingProps(route, config, session);
    const query = listingQuery(route, input.search ?? '', config.locale);
    listing = { query: input.search ?? '', page: await loadListingPage(readBase, query) };
    meta = { title: `${props.title} | Mielenosoitukset.fi`, description: props.title,
      canonical: `${config.origin}${input.path}`, robots: 'index, follow' };
    extraHead = '<link rel="stylesheet" href="/static/vendor/flatpickr/4.6.13/flatpickr.min.css">'
      + (assets.listing ?? '');
    noscript = `<noscript><p class="container-main-content">Lista avautuu JavaScriptillä. `
      + `<a href="${escapeHtml(props.rssUrl!)}">RSS</a> · <a href="/calendar/">Kalenteri</a></p></noscript>`;
  }
  if (route.name === 'organization') {
    const loaded = await organizationRead!;
    if (loaded.status === 'not-found') {
      return { status: 302, html: '', redirect: config.urls.home };
    }
    if (loaded.status === 'unavailable') {
      return { status: 503, html: unavailableDocument(), headers: { 'Retry-After': '30' } };
    }
    const profile = loaded.profile;
    const query = listingQuery({ name: 'listing', scope: 'organization', value: route.id }, input.search ?? '', config.locale);
    organization = { profile, listing: { query: input.search ?? '', page: await loadListingPage(readBase, query) } };
    meta = { title: `${profile.name} - Tiedot | Mielenosoitukset.fi`,
      description: profile.description.slice(0, 200) || `${profile.name}: organisaation tiedot ja mielenosoitukset.`,
      canonical: `${config.origin}/organization/${profile._id}`, robots: 'index, follow',
      image: profile.logo ? new URL(profile.logo, config.origin).href : null };
    jsonLd = { '@context': 'https://schema.org', '@type': 'Organization', name: profile.name,
      description: profile.description, url: meta.canonical,
      ...(meta.image ? { logo: meta.image } : {}),
      sameAs: Object.values(profile.social_media_links).filter(url => /^https?:\/\//i.test(url)) };
    extraHead = '<link rel="stylesheet" href="/static/vendor/flatpickr/4.6.13/flatpickr.min.css">'
      + (assets.organization ?? '');
    noscript = `<noscript><article class="container-main-content"><h1>${escapeHtml(profile.name)}</h1>`
      + `<p>${escapeHtml(profile.description)}</p>`
      + (profile.website ? `<p><a href="${escapeHtml(profile.website)}">Verkkosivut</a></p>` : '')
      + (profile.email ? `<p><a href="mailto:${escapeHtml(profile.email)}">${escapeHtml(profile.email)}</a></p>` : '')
      + `<a href="/demonstrations">Kaikki mielenosoitukset</a></article></noscript>`;
  }
  const url = `${config.origin}${input.path === '/' ? '/' : input.path}`;
  const bootstrap = serialize({ config, session, path: input.path, route,
    ...(detail ? { detail } : {}), ...(series ? { series } : {}), ...(home ? { home } : {}),
    ...(listing ? { listing } : {}), ...(organization ? { organization } : {}), ...(cities !== undefined ? { cities } : {}),
    ...(submission ? { submission } : {}) });
  const html = `<!DOCTYPE html>
<html lang="${escapeHtml(config.locale)}">
<head>
${headMarkup({
    title: meta.title, description: meta.description, robots: meta.robots,
    canonical: meta.canonical, url, origin: config.origin, locale: config.locale,
    assets: assets.head, image: meta.image ?? null, jsonLd, extraHead,
    siteAnalyticsEnabled: session.siteAnalyticsEnabled,
  })}
</head>
<body>
<div id="app"></div>
${noscript}
<script type="application/json" id="app-bootstrap">${bootstrap}</script>
${assets.scripts}
</body>
</html>`;
  return { status, html, headers };
}
