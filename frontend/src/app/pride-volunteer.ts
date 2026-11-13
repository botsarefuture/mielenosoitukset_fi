import data from '../../../mielenosoitukset_fi/utils/data/pride_banner.json';

/** The call for banner carriers is shown only while this switch in pride_banner.json is on. */
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
  emailInvalid: 'Tarkista sähköpostiosoite. Siinä pitää olla esimerkiksi nimi@esimerkki.fi.',
  consentMissing: 'Anna lupa tietojen tallentamiseen, jotta voimme ottaa yhteyttä.',
  failed: 'Lähettäminen ei onnistunut. Yritä hetken kuluttua uudelleen.',
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

/**
 * Part 1 has no server behind the form: every attempt reports that signup is not open.
 * Part 2 replaces this with the Go API call that reuses the reminder signup system.
 */
export async function signUpBannerCarrier(_input: VolunteerInput): Promise<VolunteerResult> {
  return { ok: false, message: prideVolunteerCopy.unavailable };
}
