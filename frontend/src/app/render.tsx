import { appConfig } from './config';
import { catalog } from './i18n';
import { routeForPath, routeMeta } from './routes';
import { fetchSession } from './session';
import type { SessionSummary } from './session';

/**
 * Metadata-only server rendering.
 *
 * The server writes the document head (title, description, robots, social
 * previews, favicons, theme bootstrap and stylesheets) and an empty app root.
 * Page components render in the browser, so a request does no React rendering
 * and no event query. Event metadata that must be indexed can be added to this
 * head per route without rendering the page body.
 */

export type RenderInput = {
  path: string;
  origin: string;
  apiBase: string;
  sessionUrl: string;
  cookie?: string;
};

export type RenderAssets = { head: string; scripts: string };

export type RenderResult = {
  status: number;
  html: string;
};

const escapeHtml = (value: string) => value
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

/** JSON in a script element must not be able to close the element. */
const serialize = (value: unknown) => JSON.stringify(value)
  .replaceAll('<', '\\u003c').replaceAll('>', '\\u003e')
  .replaceAll('&', '\\u0026').replaceAll('\u2028', '\\u2028').replaceAll('\u2029', '\\u2029');

function headMarkup(options: {
  title: string; description: string; robots: string; canonical: string | null;
  url: string; origin: string; locale: string; assets: string;
  siteAnalyticsEnabled: boolean;
}) {
  const ogImage = `${options.origin}/static/images/og-default.jpg`;
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
${options.siteAnalyticsEnabled ? `<script src="https://cdn2.mielenosoitukset.fi/vendor/web-vitals/6.2.2/web-vitals.iife.js" integrity="sha256-Hl6bmva41xz+9QjlqGnFO0zyu8ytjJtaxmTDTpP2FRo=" defer crossorigin="anonymous"></script>
<script src="/static/js/site_analytics.js" defer></script>` : ''}
${options.assets}`;
}

export async function renderPage(input: RenderInput, assets: RenderAssets): Promise<RenderResult> {
  const route = routeForPath(input.path);
  if (!route) {
    return {
      status: 404,
      html: `<!DOCTYPE html><html lang="fi"><head>
<meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="robots" content="noindex, follow" /><title>404 | Mielenosoitukset.fi</title>
<link rel="stylesheet" href="/static/css/style.css"></head>
<body><main id="main-content" class="container-main-content"><h1>404</h1>
<p><a href="/">Mielenosoitukset.fi</a></p></main></body></html>`,
    };
  }
  const session: SessionSummary = await fetchSession(input.sessionUrl, input.cookie);
  const config = appConfig({
    origin: input.origin, apiBase: input.apiBase, locale: session.locale,
    path: input.path, locales: session.locales,
  });
  const text = catalog(config.locale);
  const meta = routeMeta(route, config, text);
  const url = `${config.origin}${input.path === '/' ? '/' : input.path}`;
  const bootstrap = serialize({ config, session, path: input.path, route });
  const html = `<!DOCTYPE html>
<html lang="${escapeHtml(config.locale)}">
<head>
${headMarkup({
    title: meta.title, description: meta.description, robots: meta.robots,
    canonical: meta.canonical, url, origin: config.origin, locale: config.locale,
    assets: assets.head,
    siteAnalyticsEnabled: session.siteAnalyticsEnabled,
  })}
</head>
<body>
<div id="app"></div>
<noscript><p class="container-main-content">Mielenosoitukset.fi käyttää JavaScriptiä. <a href="/demonstrations">Kaikki mielenosoitukset</a> · <a href="/calendar/">Kalenteri</a></p></noscript>
<script type="application/json" id="app-bootstrap">${bootstrap}</script>
${assets.scripts}
</body>
</html>`;
  return { status: 200, html };
}
