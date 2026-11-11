import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import type { SessionSummary } from './session';
import { cityCatalog, findCity } from './cities';
import {
  applicationStatusLabels, cityAdminCopy, cityAdminMinePath, cityAdminPath, cityAdminSubmitPath,
  nationallyManagedCities,
} from './city-admin-route';
import './information/information.css';
import './contact/contact.css';
import './city-admin/city-admin.css';

type Application = { id: string; city_keys: string[]; status: string; created_at: string };
type Result = { kind: 'success' | 'error'; message: string } | null;

const cityName = (key: string) => findCity(key)?.name ?? key;
const applicableCities = cityCatalog.filter(city => !nationallyManagedCities.has(city.key));

/** Choose cities from the catalog; a datalist keeps 300+ names usable on mobile. */
function CityPicker({ id, label, hint, value, onChange, max, allowNational }: {
  id: string; label: string; hint: string; value: string[]; onChange: (keys: string[]) => void;
  max: number; allowNational: boolean;
}) {
  const [draft, setDraft] = useState('');
  const [problem, setProblem] = useState('');
  const options = allowNational ? cityCatalog : applicableCities;
  const add = () => {
    const city = findCity(draft);
    if (!city) { setProblem('Valitse paikkakunta listasta.'); return; }
    if (!allowNational && nationallyManagedCities.has(city.key)) {
      setProblem(`${city.name} on valtakunnallisen ylläpitotiimin hoitama, joten sille ei haeta kaupunkiadmineja.`);
      return;
    }
    if (value.length >= max && !value.includes(city.key)) { setProblem(`Voit valita enintään ${max} paikkakuntaa.`); return; }
    setProblem('');
    setDraft('');
    if (!value.includes(city.key)) onChange([...value, city.key]);
  };
  return <div className="city-admin-picker">
    <label htmlFor={id}>{label}</label>
    <p className="city-admin-hint" id={`${id}-hint`}>{hint}</p>
    <div className="city-admin-picker__row">
      <input id={id} list={`${id}-options`} value={draft} autoComplete="off" aria-describedby={`${id}-hint`}
        onChange={event => setDraft(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); add(); } }} />
      <button type="button" className="detail-button detail-button--quiet" onClick={add}>Lisää</button>
    </div>
    <datalist id={`${id}-options`}>{options.map(city => <option key={city.key} value={city.name} />)}</datalist>
    {problem ? <p className="city-admin-field-error" role="alert">{problem}</p> : null}
    {value.length ? <ul className="city-admin-chips" aria-label={label}>
      {value.map(key => <li key={key}>
        <span>{cityName(key)}</span>
        <button type="button" aria-label={`Poista ${cityName(key)}`} onClick={() => onChange(value.filter(item => item !== key))}>×</button>
      </li>)}
    </ul> : null}
  </div>;
}

function MyApplications({ applications }: { applications: Application[] }) {
  if (!applications.length) return null;
  return <section className="public-prose-card" aria-labelledby="city-admin-mine-title">
    <h2 id="city-admin-mine-title">Hakemuksesi</h2>
    <ul className="city-admin-applications">
      {applications.map(item => <li key={item.id}>
        <span>{item.city_keys.map(cityName).join(', ')}</span>
        <span className="city-admin-status">{applicationStatusLabels[item.status] ?? item.status}</span>
        <span className="city-admin-date">{new Date(item.created_at).toLocaleDateString('fi-FI')}</span>
      </li>)}
    </ul>
  </section>;
}

/** The application page. Go stores the application; the national team reviews it as a case. */
export default function CityAdminApplyScreen({ session }: { session: SessionSummary }) {
  const [cities, setCities] = useState<string[]>([]);
  const [activeIn, setActiveIn] = useState<string[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<Result>(null);
  const open = applications.some(item => item.status === 'received' || item.status === 'in_review');

  useEffect(() => {
    const preset = findCity(new URLSearchParams(window.location.search).get('city') ?? '');
    if (preset && !nationallyManagedCities.has(preset.key)) setCities([preset.key]);
    if (!session.authenticated) return;
    fetch(cityAdminMinePath, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      .then(response => response.ok ? response.json() : null)
      .then(data => { if (data && Array.isArray(data.applications)) setApplications(data.applications); })
      .catch(() => { /* The form works without the status list. */ });
  }, [session.authenticated]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (!cities.length) { setResult({ kind: 'error', message: 'Valitse vähintään yksi paikkakunta.' }); return; }
    setSending(true);
    setResult(null);
    try {
      const response = await fetch(cityAdminSubmitPath, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({
          city_keys: cities, about: form.get('about'), references: form.get('references'),
          consent: form.get('consent') === 'on',
          activism: {
            cities: activeIn, organizations: form.get('organizations'),
            experience: form.get('experience'), experience_details: form.get('experience_details'),
          },
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok && data.success) {
        setApplications([{ id: data.id, city_keys: cities, status: 'received', created_at: new Date().toISOString() }, ...applications]);
        setResult({ kind: 'success', message: 'Kiitos! Hakemuksesi on vastaanotettu. Ylläpito ottaa sinuun yhteyttä.' });
      } else {
        setResult({ kind: 'error', message: typeof data.message === 'string' ? data.message : 'Hakemusta ei voitu lähettää. Yritä uudelleen.' });
      }
    } catch {
      setResult({ kind: 'error', message: 'Hakemusta ei voitu lähettää. Tarkista yhteys ja yritä uudelleen.' });
    } finally {
      setSending(false);
    }
  };

  return <article className="public-page-shell information-page city-admin-page" aria-labelledby="city-admin-title">
    <header className="public-page-header">
      <div className="public-page-header__content">
        <h1 className="public-page-header__title" id="city-admin-title">{cityAdminCopy.title}</h1>
        <p className="public-page-header__description">{cityAdminCopy.description}</p>
      </div>
    </header>
    <div className="public-content-stack">
      <section className="public-prose-card" aria-labelledby="city-admin-role-title">
        <h2 id="city-admin-role-title">Mitä kaupunkiadmin tekee?</h2>
        <ul>
          <li>Tarkistaa oman paikkakuntansa uudet mielenosoitusilmoitukset ja hyväksyy tai palauttaa ne.</li>
          <li>Korjaa virheitä ja peruutuksia, ja vastaa ilmoittajien kysymyksiin.</li>
          <li>Toimii yhdessä paikkakunnan toisen kaupunkiadminin ja valtakunnallisen ylläpidon kanssa.</li>
        </ul>
        <p>Tavoitteena on vähintään kaksi kaupunkiadminia paikkakuntaa kohden. Helsingin ilmoitukset käsittelee valtakunnallinen ylläpitotiimi.</p>
      </section>

      {result?.kind === 'success' ? null : <MyApplications applications={applications} />}

      <section className="public-prose-card" aria-labelledby="city-admin-form-title">
        <h2 id="city-admin-form-title">Hae kaupunkiadminiksi</h2>
        {result ? <div className={`flash-message flash-message--inline flash-${result.kind === 'success' ? 'success' : 'error'}`}
          role={result.kind === 'success' ? 'status' : 'alert'}><span className="flash-text">{result.message}</span></div> : null}
        {result?.kind === 'success' ? <MyApplications applications={applications} /> : null}
        {!session.authenticated ? <p>Hakeminen vaatii käyttäjätilin, jonka sähköpostiosoite on vahvistettu.{' '}
          <a href={`/users/auth/login?next=${encodeURIComponent(cityAdminPath)}`}>Kirjaudu sisään</a> tai{' '}
          <a href="/users/auth/register">luo tili</a>.</p>
        : open ? <p>Sinulla on käsittelyssä oleva hakemus. Voit hakea uudelleen, kun se on käsitelty.</p>
        : <form className="contact-form city-admin-form" onSubmit={submit} noValidate={false}>
          <CityPicker id="city-admin-cities" label="Paikkakunnat, joilla haluat toimia" hint="1–5 paikkakuntaa."
            value={cities} onChange={setCities} max={5} allowNational={false} />
          <label htmlFor="city-admin-about">Kerro itsestäsi ja miksi haluat kaupunkiadminiksi</label>
          <textarea id="city-admin-about" name="about" rows={6} required minLength={50} maxLength={3000} />
          <fieldset className="city-admin-fieldset">
            <legend>Aktivismi</legend>
            <CityPicker id="city-admin-active" label="Paikkakunnat, joilla olet aktiivinen" hint="Vapaaehtoinen, enintään 10."
              value={activeIn} onChange={setActiveIn} max={10} allowNational />
            <label htmlFor="city-admin-organizations">Ryhmät tai järjestöt, joissa toimit</label>
            <textarea id="city-admin-organizations" name="organizations" rows={3} maxLength={1000}
              placeholder="Voit jättää tyhjäksi, jos et toimi missään ryhmässä." />
            <label htmlFor="city-admin-experience">Kokemus mielenosoitusten tai tapahtumien järjestämisestä</label>
            <select id="city-admin-experience" name="experience" required defaultValue="">
              <option value="" disabled>Valitse</option>
              <option value="none">Ei kokemusta</option>
              <option value="some">Jonkin verran</option>
              <option value="lot">Paljon</option>
            </select>
            <label htmlFor="city-admin-experience-details">Kuvaile kokemustasi lyhyesti</label>
            <textarea id="city-admin-experience-details" name="experience_details" rows={3} maxLength={2000} />
          </fieldset>
          <label htmlFor="city-admin-references">Suosittelijat (vapaaehtoinen)</label>
          <textarea id="city-admin-references" name="references" rows={2} maxLength={1000}
            placeholder="Esimerkiksi paikallinen aktiivi tai sivuston käyttäjä, joka voi suositella sinua." />
          <label className="city-admin-consent">
            <input type="checkbox" name="consent" required />
            <span>Hyväksyn, että ylläpito käsittelee hakemukseni ja säilyttää sen <a href="/privacy">tietosuojaselosteen</a> mukaisesti.</span>
          </label>
          <button type="submit" className="detail-button detail-button--primary" disabled={sending}>
            {sending ? 'Lähetetään…' : 'Lähetä hakemus'}
          </button>
        </form>}
      </section>
    </div>
  </article>;
}
