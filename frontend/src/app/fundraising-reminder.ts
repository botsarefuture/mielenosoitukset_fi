/**
 * Fundraising opening reminder: copy and request helpers. The consent text
 * version must match `reminderConsentVersion` in go-api/fundraising_reminder.go;
 * change both together with the privacy notice (docs/fundraising-reminder.md).
 */
export const reminderConsentVersion = '2026-11-13';

export const reminderPath = '/api/fundraising/reminder';

export const reminderCopy = {
  title: 'Tilaa muistutus sähköpostiin',
  intro: 'Jos haluat, lähetämme sinulle yhden sähköpostiviestin, kun keräys alkaa. Vahvistat tilauksen ensin sähköpostiin tulevasta linkistä.',
  emailLabel: 'Sähköpostiosoite',
  consent: 'Hyväksyn, että Mielenosoitukset.fi käyttää sähköpostiosoitettani tämän yhden muistutuksen lähettämiseen.',
  results: 'Haluan myös kuulla keräyksen tuloksista',
  resultsHint: 'Valinta on vapaaehtoinen. Voimme lähettää tällöin yhden viestin tuloksista keräyksen päätyttyä.',
  submit: 'Tilaa muistutus',
  sent: 'Tarkista sähköpostisi. Jos osoite on kelvollinen, lähetämme siihen vahvistusviestin.',
  sending: 'Lähetetään',
  privacy: 'Lue, miten osoitettasi käsitellään',
  retention: 'Poistamme osoitteen viimeistään 30 päivää keräyksen päättymisen jälkeen. Voit poistaa sen milloin tahansa jokaisen viestin linkistä.',
  error: 'Tilausta ei voitu lähettää. Yritä uudelleen hetken kuluttua.',
  rateLimited: 'Yrityksiä on liian monta. Odota hetki ja yritä uudelleen.',
  confirmTitle: 'Vahvista muistutuksen tilaus',
  confirmIntro: 'Vahvista tilaus painamalla painiketta. Sen jälkeen saat yhden viestin, kun keräys alkaa.',
  confirmButton: 'Vahvista tilaus',
  confirmed: 'Tilaus on vahvistettu. Lähetämme sinulle yhden viestin, kun keräys alkaa.',
  removeTitle: 'Poista sähköpostiosoitteesi',
  removeIntro: 'Painamalla painiketta poistamme osoitteesi ja kaikki siihen liittyvät tiedot. Et saa enää viestejä tästä tilauksesta.',
  removeButton: 'Poista osoitteeni',
  removed: 'Osoitteesi on poistettu. Et saa enää viestejä tästä tilauksesta.',
  badLink: 'Linkki ei kelpaa. Avaa se uudelleen sähköpostiviestistä.',
} as const;

export type ReminderMode = 'vahvista' | 'peru';

/** The mode and one-time token from `?muistutus=…#t=…`. The token stays in the fragment, so it is never sent to a server or logged. */
export function readReminderLink(search: string, hash: string): { mode: ReminderMode; token: string } | null {
  const mode = new URLSearchParams(search).get('muistutus');
  if (mode !== 'vahvista' && mode !== 'peru') return null;
  const token = new URLSearchParams(hash.replace(/^#/, '')).get('t') ?? '';
  return { mode, token };
}

export type ReminderResult = { ok: boolean; status: number; message: string };

async function post(path: string, body: Record<string, unknown>): Promise<ReminderResult> {
  try {
    const response = await fetch(path, {
      method: 'POST', credentials: 'omit', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({})) as { message?: unknown };
    return { ok: response.ok, status: response.status, message: typeof data.message === 'string' ? data.message : '' };
  } catch {
    return { ok: false, status: 0, message: '' };
  }
}

export const signUpForReminder = (input: { email: string; resultsConsent: boolean; website: string; locale?: string }) =>
  post(reminderPath, { email: input.email, consent: true, results_consent: input.resultsConsent, website: input.website, locale: input.locale ?? 'fi' });

export const confirmReminder = (token: string) => post(`${reminderPath}/confirm`, { token });

export const removeReminder = (token: string) => post(`${reminderPath}/unsubscribe`, { token });
