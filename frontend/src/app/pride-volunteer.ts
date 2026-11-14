import data from '../../../mielenosoitukset_fi/utils/data/pride_banner.json';

/** The call for banner carriers is shown only while this switch in pride_banner.json is on. */
/** Keep in step with bannerConsentVersion in go-api/banner_volunteer.go. */
export const carrierConsentVersion = '2026-11-13';

export const prideVolunteerEnabled = (value: unknown = data): boolean =>
  typeof value === 'object' && value !== null && (value as { volunteer_form?: unknown }).volunteer_form === true;

export const prideVolunteerCopy = {
  navButton: 'Kanna banderollia',
  title: 'Tarvitsemme kantajia jokaiseen Prideen',
  intro: 'Tavoitteemme on, että jokaisessa Pridessa Suomessa on Mielenosoitukset.fi-banderolli. Banderolli tarvitsee kantajan.',
  call: 'Jos haluat kantaa sitä omalla paikkakunnallasi tai muualla, jätä yhteystietosi.',
  terms: [
    { title: 'Ilmoittautuminen ei sido', text: 'Ilmoittautuminen ei lupaa mitään kummallekaan puolelle. Voit perua sen milloin tahansa.' },
    { title: 'Sovimme tiedot yhdessä', text: 'Otamme yhteyttä myöhemmin ja sovimme kanssasi, miten banderolli kulkee ja mihin tapahtumaan.' },
  ],
  formTitle: 'Ilmoittaudu banderollin kantajaksi',
  legend: 'Banderollin kantajan ilmoittautuminen',
  name: 'Etunimi tai nimimerkki', namePlaceholder: 'Esimerkiksi Aino',
  email: 'Sähköposti', emailPlaceholder: 'nimi@esimerkki.fi',
  emailHint: 'Lähetämme siihen vahvistusviestin. Ilmoittautuminen tulee voimaan vasta, kun vahvistat sen.',
  city: 'Paikkakunta tai alue', cityPlaceholder: 'Esimerkiksi Oulu',
  pride: 'Mihin Prideen haluaisit lähteä?', pridePlaceholder: 'Tapahtuma tai paikkakunta',
  prideHint: 'Voit kirjoittaa tapahtuman tai paikkakunnan.', unsure: 'En tiedä vielä',
  note: 'Kerro halutessasi lisää',
  noteHint: 'Esimerkiksi milloin sinulle sopii tai miten pääset paikalle. Älä kirjoita tähän arkaluonteisia tietoja.',
  optional: '(valinnainen)',
  consent: 'Annan luvan tallentaa nimeni, sähköpostiosoitteeni ja antamani tiedot, jotta Mielenosoitukset.fi voi ottaa minuun yhteyttä banderollin kantamisesta. Voin perua luvan milloin tahansa. Tiedot poistetaan Pride-kauden jälkeen, ellen anna uutta lupaa.',
  privacyBefore: 'Käytämme tietoja vain tähän. Emme kysy puhelinnumeroa emmekä kotiosoitetta. Lisää tietoa on ',
  privacyLink: 'tietosuojaselosteessa', privacyAfter: '.',
  submit: 'Ilmoittaudu', sending: 'Lähetetään…',
  errorTitle: (count: number) => count === 1 ? 'Lomakkeessa on yksi korjattava' : `Lomakkeessa on ${count} korjattavaa`,
  errorHelp: 'Korjaa merkityt kentät ja lähetä lomake uudelleen.',
  nameMissing: 'Kirjoita etunimi tai nimimerkki.',
  emailInvalid: 'Tarkista sähköpostiosoite. Kirjoita se muodossa nimi@esimerkki.fi.',
  consentMissing: 'Anna lupa tietojen tallentamiseen, jotta voimme ottaa yhteyttä.',
  failed: 'Lähettäminen ei onnistunut. Yritä hetken kuluttua uudelleen.',
  rateLimited: 'Yrityksiä on liian monta. Odota hetki ja yritä uudelleen.',
  unavailable: 'Ilmoittautuminen ei ole vielä käytössä.',
  doneTitle: 'Tarkista sähköpostisi',
  doneSent: 'Viesti on matkalla osoitteeseen',
  doneConfirm: 'Avaa viestin linkki vahvistaaksesi ilmoittautumisen.',
  doneWait: 'Ilmoittautuminen tulee voimaan vasta vahvistuksen jälkeen. Jos viestiä ei kuulu muutamassa minuutissa, katso roskapostikansio.',
  donePromise: 'Ilmoittautuminen ei sido sinua mihinkään, ja voit perua sen milloin tahansa. Otamme yhteyttä myöhemmin ja sovimme tiedot yhdessä kanssasi.',
} as const;

export interface VolunteerInput { name: string; email: string; city: string; pride: string; unsure: boolean; note: string; consent: boolean; website: string }
export type VolunteerField = 'name' | 'email' | 'consent';
export type VolunteerResult = { ok: true } | { ok: false; message?: string };

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Required fields only; everything else is optional free text. */
export function validateVolunteer(input: Pick<VolunteerInput, 'name' | 'email' | 'consent'>): Partial<Record<VolunteerField, string>> {
  const c = prideVolunteerCopy;
  const errors: Partial<Record<VolunteerField, string>> = {};
  if (!input.name.trim()) errors.name = c.nameMissing;
  const email = input.email.trim();
  if (!email || email.length > 254 || !EMAIL.test(email)) errors.email = c.emailInvalid;
  if (!input.consent) errors.consent = c.consentMissing;
  return errors;
}

export const carrierPath = '/api/pride-banner/volunteer';

async function post(path: string, body: Record<string, unknown>): Promise<{ ok: boolean; status: number; message: string }> {
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

/**
 * Posts the signup to the Go API (docs/pride-banner-volunteers.md). The answer is the same for a new,
 * a pending and an already registered address, so the page never says which one it was.
 */
export async function signUpBannerCarrier(input: VolunteerInput): Promise<VolunteerResult> {
  const c = prideVolunteerCopy;
  const result = await post(carrierPath, {
    name: input.name, email: input.email, city: input.city, pride: input.pride, unsure: input.unsure,
    note: input.note, consent: true, locale: 'fi', website: input.website,
  });
  if (result.ok) return { ok: true };
  if (result.status === 404) return { ok: false, message: c.unavailable };
  if (result.status === 429) return { ok: false, message: c.rateLimited };
  if (result.status === 400 && result.message) return { ok: false, message: result.message };
  return { ok: false, message: c.failed };
}

export type CarrierLinkMode = 'vahvista' | 'peru';

/** The mode and one-time token from `?kantaja=…#t=…`. The token stays in the fragment, so it is never sent to a server or logged. */
export function readCarrierLink(search: string, hash: string): { mode: CarrierLinkMode; token: string } | null {
  const mode = new URLSearchParams(search).get('kantaja');
  if (mode !== 'vahvista' && mode !== 'peru') return null;
  return { mode, token: new URLSearchParams(hash.replace(/^#/, '')).get('t') ?? '' };
}

export const confirmCarrier = (token: string) => post(`${carrierPath}/confirm`, { token });
export const removeCarrier = (token: string) => post(`${carrierPath}/unsubscribe`, { token });

export const carrierLinkCopy = {
  confirmTitle: 'Vahvista ilmoittautumisesi',
  confirmIntro: 'Vahvista ilmoittautuminen banderollin kantajaksi painamalla painiketta. Sen jälkeen otamme sinuun yhteyttä myöhemmin ja sovimme tiedot yhdessä kanssasi.',
  confirmButton: 'Vahvista ilmoittautuminen',
  confirmed: 'Ilmoittautuminen on vahvistettu. Kiitos. Otamme yhteyttä myöhemmin. Voit perua ilmoittautumisen milloin tahansa viestin linkistä.',
  removeTitle: 'Poista tietosi',
  removeIntro: 'Kun painat painiketta, poistamme ilmoittautumisesi ja kaikki siihen liittyvät tiedot. Et saa enää viestejä banderollin kantamisesta.',
  removeButton: 'Poista tietoni',
  removed: 'Tietosi on poistettu. Et saa enää viestejä banderollin kantamisesta.',
  badLink: 'Linkki ei kelpaa. Avaa se uudelleen sähköpostiviestistä.',
  expired: 'Linkki on vanhentunut tai jo käytetty. Jos olet jo vahvistanut ilmoittautumisen, sinun ei tarvitse tehdä mitään. Muuten voit ilmoittautua uudelleen lomakkeella.',
  error: 'Toiminto ei onnistunut. Yritä uudelleen hetken kuluttua.',
} as const;
