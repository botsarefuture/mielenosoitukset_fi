// Developer panel, GET /developer and GET /developer/apps/<id>. The data comes
// from the Go read routes behind the auth bridge (go-api/developer.go); the
// copy is the Flask templates' Finnish msgids. Every write (creating, rotating
// and revoking tokens, scope requests) stays in Flask.
export const developerPath = '/developer';
export const developerOverviewApi = '/api/developer/overview';
export const developerAppApi = '/api/developer/apps/';
export const developerAccessRequestPath = '/developer/request_access';
export const developerAppsPath = '/developer/apps';

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
  writeNote: 'Uusien sovellusten ja tokenien luonti ja peruminen tehdään sovellusnäkymässä.',
} as const;

export type DeveloperApp = {
  id: string; name: string; description: string; clientId: string; allowedScopes: string[]; createdAt?: string;
};
export type DeveloperToken = { id: string; type: string; scopes: string[]; expiresAt?: string };

export type DeveloperRead =
  | { status: 'locked' }
  | { status: 'overview'; apps: DeveloperApp[]; tokens: DeveloperToken[] }
  | { status: 'app'; app: DeveloperApp; tokens: DeveloperToken[] };

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
  if (appRequested) {
    const app = readApp(raw.app);
    return app ? { status: 'app', app, tokens: readTokens(raw.tokens) } : null;
  }
  if (!Array.isArray(raw.apps)) return null;
  return { status: 'overview', apps: raw.apps.flatMap(item => readApp(item) ?? []), tokens: readTokens(raw.tokens) };
}

export function formatDeveloperDate(iso?: string): string {
  if (!iso) return '–';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '–';
  return new Intl.DateTimeFormat('fi-FI', { timeZone: 'Europe/Helsinki', day: 'numeric', month: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit' }).format(date);
}
