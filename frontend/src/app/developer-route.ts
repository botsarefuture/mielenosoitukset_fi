// Developer panel, GET /developer and GET /developer/apps/<id>. The data comes
// from the Go read routes behind the auth bridge (go-api/developer.go); the
// copy is the Flask templates' Finnish msgids. The write controls (create app,
// rotate, create and revoke tokens) call the Go write routes and only appear when
// Go says writes are on (DEVELOPER_WRITES_ENABLED). Access and scope requests
// keep posting to the unchanged Flask endpoints, which send the admin email.
export const developerPath = '/developer';
export const developerOverviewApi = '/api/developer/overview';
export const developerAppApi = '/api/developer/apps/';
export const developerAccessRequestPath = '/developer/request_access';
export const developerAppsPath = '/developer/apps';
export const developerAppsApi = '/api/developer/apps';
export const developerTokensApi = '/api/developer/tokens';
export const developerScopeRequestPath = (appId: string) => `/developer/apps/${appId}/request_scopes`;
/** Scopes Go will issue; admin and mcp.admin need Flask's step-up and are never offered here. */
export const developerIssuableScopes = ['read', 'write', 'submit_demonstrations'] as const;
export const developerRequestableScopes = ['read', 'write', 'submit_demonstrations', 'admin', 'mcp.admin'] as const;

export const developerCopy = {
  title: 'Kehittäjäpaneeli',
  description: 'Kehittäjäpaneeli',
  lead: 'Hallinnoi sovelluksia ja henkilökohtaisia avaimia.',
  appsHeading: 'Sovellukset',
  noApps: 'Ei sovelluksia vielä.',
  openApps: 'Avaa sovellusnäkymä',
  personalHeading: 'Henkilökohtaiset tokenit',
  noPersonal: 'Ei henkilökohtaisia tokeneita.',
  validUntil: 'Voimassa:',
  back: 'Takaisin paneeliin',
  tokensHeading: 'Tokenit',
  tokenHistory: 'Olemassa olevat tokenit',
  noTokens: 'Ei token-historiaa',
  scopesHeading: 'Nykyiset oikeudet',
  loading: 'Ladataan kehittäjäpaneelia…',
  loginLead: 'Kirjaudu sisään nähdäksesi kehittäjäpaneelin.',
  login: 'Kirjaudu sisään',
  unavailable: 'Kehittäjäpaneelia ei saatu ladattua. Yritä hetken kuluttua uudelleen.',
  notFound: 'Sovellusta ei löytynyt.',
  lockedTitle: 'Kehittäjäpaneeli on lukittu',
  lockedLead: 'Pyydä käyttöoikeus perustelemalla, mihin tarvitset API-avaimet ja kehittäjäpaneelin.',
  reason: 'Perustelu',
  reasonPlaceholder: 'Kuvaile käyttötapaus ja miksi tarvitset pääsyn',
  send: 'Lähetä pyyntö',
  settings: 'Takaisin',
  settingsUrl: '/users/auth/settings',
  createApp: 'Luo sovellus',
  appName: 'Nimi',
  appDescription: 'Kuvaus',
  create: 'Luo',
  creating: 'Luodaan…',
  createPersonal: 'Luo henkilökohtainen token',
  createToken: 'Luo token',
  tokenType: 'Tyyppi',
  tokenShort: 'Lyhyt (48 h)',
  tokenLong: 'Pitkä (90 pv)',
  scopes: 'Oikeudet',
  revoke: 'Mitätöi token',
  revokeConfirm: 'Vahvista mitätöinti',
  cancel: 'Peruuta',
  close: 'Sulje',
  copy: 'Kopioi',
  copied: 'Kopioitu',
  reloadPage: 'Lataa sivu uudelleen',
  revoked: 'Token mitätöity.',
  rotate: 'Vaihda salaisuus',
  rotateConfirm: 'Vahvista: vanha salaisuus lakkaa toimimasta',
  rotateNote: 'Vanha client secret lakkaa toimimasta heti.',
  secretOnce: 'Talleta tämä heti. Sitä ei näytetä uudelleen.',
  tokenValue: 'Token',
  clientSecret: 'Client secret',
  requestScopes: 'Pyydä lisää oikeuksia',
  requestScopesLead: 'Ylläpitäjä käsittelee pyynnön.',
  noScopesToRequest: 'Sovelluksella on jo kaikki oikeudet.',
  pickScope: 'Valitse vähintään yksi scope.',
  reasonRequired: 'Perustelu vaaditaan.',
  failed: 'Toiminto epäonnistui. Yritä uudelleen.',
  rateLimited: 'Liian monta pyyntöä. Yritä hetken kuluttua uudelleen.',
  sessionExpired: 'Istunto vanhentui. Lataa sivu uudelleen.',
  privilegedElsewhere: 'Etuoikeutetut avaimet luodaan vanhalla kehittäjäsivulla.',
} as const;

export type DeveloperApp = {
  id: string; name: string; description: string; clientId: string; allowedScopes: string[]; createdAt?: string;
};
export type DeveloperToken = { id: string; type: string; scopes: string[]; expiresAt?: string };

/** `csrf` is set only when Go has the write routes on; without it the page shows no controls. */
export type DeveloperRead =
  | { status: 'locked' }
  | { status: 'overview'; apps: DeveloperApp[]; tokens: DeveloperToken[]; csrf?: string }
  | { status: 'app'; app: DeveloperApp; tokens: DeveloperToken[]; csrf?: string };

const text = (value: unknown, max = 500) => typeof value === 'string' ? value.slice(0, max) : '';
const list = (value: unknown) => Array.isArray(value)
  ? value.filter((item): item is string => typeof item === 'string').slice(0, 50).map(item => item.slice(0, 80)) : [];

export function readApp(value: unknown): DeveloperApp | null {
  const raw = value as Record<string, unknown> | null;
  if (!raw || typeof raw !== 'object' || typeof raw.id !== 'string' || !/^[a-f\d]{24}$/i.test(raw.id)) return null;
  return { id: raw.id, name: text(raw.name, 200), description: text(raw.description, 2000),
    clientId: text(raw.client_id, 200), allowedScopes: list(raw.allowed_scopes), createdAt: text(raw.created_at, 40) || undefined };
}

export function readTokens(value: unknown): DeveloperToken[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 200).flatMap(item => {
    const raw = item as Record<string, unknown> | null;
    if (!raw || typeof raw !== 'object') return [];
    return [{ id: text(raw.id, 40), type: text(raw.type, 20), scopes: list(raw.scopes), expiresAt: text(raw.expires_at, 40) || undefined }];
  });
}

/** Turn a Go answer into a page state; anything unexpected is `null` (unavailable), never an empty panel. */
export function readDeveloper(body: unknown, appRequested: boolean): DeveloperRead | null {
  const raw = body as Record<string, unknown> | null;
  if (!raw || typeof raw !== 'object' || typeof raw.access !== 'boolean') return null;
  if (!raw.access) return { status: 'locked' };
  const csrf = raw.writes === true && typeof raw.csrf === 'string' && /^[\w.-]{20,300}$/.test(raw.csrf) ? raw.csrf : undefined;
  if (appRequested) {
    const app = readApp(raw.app);
    return app ? { status: 'app', app, tokens: readTokens(raw.tokens), csrf } : null;
  }
  if (!Array.isArray(raw.apps)) return null;
  return { status: 'overview', apps: raw.apps.flatMap(item => readApp(item) ?? []), tokens: readTokens(raw.tokens), csrf };
}

export type WriteResult = { ok: true; body: Record<string, unknown> } | { ok: false; message: string };

/** Map a failed write to a Finnish message; the server's own text is shown only for 4xx input errors. */
export function writeFailure(status: number, body: unknown): string {
  const raw = body as Record<string, unknown> | null;
  const serverText = raw && typeof raw.error === 'string' ? raw.error.slice(0, 200) : '';
  if (status === 429) return developerCopy.rateLimited;
  if (status === 403 && serverText === 'invalid csrf token') return developerCopy.sessionExpired;
  if (status === 401) return developerCopy.sessionExpired;
  if (status >= 400 && status < 500 && serverText && serverText !== 'forbidden') return serverText;
  return developerCopy.failed;
}

/** One JSON write to the Go routes: same-origin cookie, CSRF header, secrets only in the returned body. */
export async function developerWrite(method: 'POST' | 'DELETE', url: string, csrf: string, payload?: unknown,
  fetcher: typeof fetch = fetch): Promise<WriteResult> {
  try {
    const response = await fetcher(url, { method, credentials: 'same-origin', cache: 'no-store',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: method === 'POST' ? JSON.stringify(payload ?? {}) : undefined });
    let body: unknown = null;
    try { body = await response.json(); } catch { /* an empty or non-JSON body is a failure below */ }
    if (!response.ok || !body || typeof body !== 'object') return { ok: false, message: writeFailure(response.status, body) };
    return { ok: true, body: body as Record<string, unknown> };
  } catch {
    return { ok: false, message: developerCopy.failed };
  }
}

export function formatDeveloperDate(iso?: string): string {
  if (!iso) return '–';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '–';
  return new Intl.DateTimeFormat('fi-FI', { timeZone: 'Europe/Helsinki', day: 'numeric', month: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit' }).format(date);
}
