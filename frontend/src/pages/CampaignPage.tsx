import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { VolunteerForm } from '../components/VolunteerForm';
import type { VolunteerFormProps } from '../components/VolunteerForm';

export interface CampaignPageProps {
  urls: { home: string; fundraising: string; privacy: string };
  volunteer: VolunteerFormProps;
  newsletter: { endpoint: string; listId: string };
  serverFallback?: boolean;
}

function NewsletterForm({ endpoint, listId, disabled }: CampaignPageProps['newsletter'] & { disabled: boolean }) {
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<{ error: boolean; text: string } | null>(null);
  const requestPending = useRef(false);

  async function subscribe(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (requestPending.current || disabled) return;
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    const email = String(new FormData(form).get('email') || '').trim();
    requestPending.current = true;
    setPending(true);
    setFeedback(null);
    try {
      const response = await fetch(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, list_id: listId }),
      });
      const result = await response.json().catch(() => null);
      if (response.ok && result && !result.error && typeof result.message === 'string' && result.message.trim()) {
        setFeedback({ error: false, text: 'Uutiskirjeen tilaus onnistui.' });
        form.reset();
      } else {
        setFeedback({ error: true, text: 'Tilaus ei onnistunut. Tarkista sähköpostiosoitteesi ja yritä uudelleen.' });
      }
    } catch {
      setFeedback({ error: true, text: 'Yhteys palveluun epäonnistui. Yritä myöhemmin uudelleen.' });
    } finally {
      requestPending.current = false;
      setPending(false);
    }
  }

  return <form id="newsletter-form" method="post" action={endpoint} onSubmit={subscribe} aria-busy={pending || undefined}>
    <fieldset id="newsletter-fields" disabled={disabled || pending}>
      <legend className="visually-hidden">Uutiskirjeen tilaus</legend>
      <label htmlFor="email" className="form-label">Sähköpostiosoite</label>
      <div className="campaign-newsletter__controls">
        <input type="email" id="email" name="email" className="form-control" autoComplete="email" placeholder="nimi@esimerkki.fi" required />
        <button className="campaign-button campaign-button--primary" type="submit" disabled={disabled || pending}>
          {pending ? 'Lähetetään…' : 'Tilaa uutiskirje'}
        </button>
      </div>
    </fieldset>
    <p id="newsletter-msg" className={`campaign-feedback${feedback ? ' show' : ''}${feedback?.error ? ' campaign-feedback--error' : ''}`}
      role={feedback?.error ? 'alert' : 'status'} aria-live="polite" hidden={!feedback}>{feedback?.text}</p>
    {disabled && <p className="campaign-loading-note">Uutiskirjeen tilaaminen tarvitsee JavaScriptin. Tilausta ei ole lähetetty.</p>}
  </form>;
}

export function CampaignPage({ urls, volunteer, newsletter, serverFallback = false }: CampaignPageProps) {
  return <div className="campaign-page" lang="fi">
    <section className="campaign-intro campaign-shell" aria-labelledby="campaign-title">
      <div className="campaign-intro__copy">
        <h1 id="campaign-title">Yhdessä näkyväksi</h1>
        <p className="campaign-intro__lead">Auta yhä useampaa löytämään mielenosoitukset.fi ja tulevat mielenosoitukset.</p>
        <div className="campaign-actions">
          <a className="campaign-button campaign-button--primary" href="#vapaaehtoiseksi">Tule vapaaehtoiseksi <span aria-hidden="true">→</span></a>
          <a className="campaign-text-link" href="#materiaalitavoitteet">Tutustu kampanjaan</a>
        </div>
      </div>
    </section>

    <div className="campaign-shell campaign-content">
      <section id="materiaalitavoitteet" className="campaign-overview" aria-labelledby="campaign-overview-title">
        <div><h2 id="campaign-overview-title">Näkyvyyttä eri puolilla Suomea</h2></div>
        <div><p>Teemme palvelua tunnetuksi materiaaleilla, viestinnällä ja paikallisella yhteistyöllä. Voit tulla mukaan omalla paikkakunnallasi tai verkossa.</p><p>Kampanjaa valmistellaan. Yhteinen tekeminen ja aikataulut tarkentuvat myöhemmin.</p></div>
      </section>
      <section id="kerays" className="campaign-fundraising" aria-labelledby="campaign-fundraising-title">
        <div><h2 id="campaign-fundraising-title">Kampanjan pienkeräys</h2><p>Keräyksen suunnitelma, ajantasainen tilanne ja vahvistetut tiedot löytyvät keräyssivulta.</p></div>
        <a className="campaign-text-link" href={urls.fundraising}>Tutustu pienkeräykseen <span aria-hidden="true">→</span></a>
      </section>

      <section id="vapaaehtoiseksi" className="campaign-volunteer" aria-labelledby="volunteer-title">
        <div className="campaign-volunteer__intro">
          <h2 id="volunteer-title">Tule vapaaehtoiseksi</h2>
          <p>Pienikin panos auttaa. Aiempi kokemus ei ole edellytys, ja voit kertoa itse, millainen tekeminen sopii sinulle.</p>
          <dl className="campaign-help">
            <div><dt>Materiaalien jakaminen</dt><dd>Auta levittämään tietoa palvelusta omalla paikkakunnallasi.</dd></div>
            <div><dt>Some ja viestintä</dt><dd>Jaa tietoa tai tuo omaa osaamistasi kampanjan sisältöihin.</dd></div>
            <div><dt>Tapahtumat ja yhteistyö</dt><dd>Auta tavoittamaan paikallisia järjestöjä ja yhteisöjä.</dd></div>
          </dl>
          <a className="campaign-text-link" href="mailto:tuki@mielenosoitukset.fi">Kysy lisää sähköpostitse</a>
        </div>
        <div className="volunteer-signup campaign-signup">
          <h2>Ilmoittaudu mukaan</h2>
          <p id="vol-help">Nimi ja sähköposti ovat pakollisia. Muut tiedot voit täyttää halutessasi.</p>
          <p className="campaign-signup__confirmation">Vahvista ilmoittautumisesi sähköpostiisi saapuvasta linkistä.</p>
          <p className="volunteer-privacy">Tietoja käytetään vapaaehtoistoiminnan yhteydenpitoon. <a href={urls.privacy}>Tietosuojaseloste</a>.</p>
          {serverFallback ? <>
            <p className="campaign-loading-note">Lomaketta ladataan. Jos se ei avaudu, voit ottaa yhteyttä: <a href="mailto:tuki@mielenosoitukset.fi">tuki@mielenosoitukset.fi</a>.</p>
            <noscript><p>Ilmoittautumislomake tarvitsee JavaScriptin. Tietojasi ei ole lähetetty.</p></noscript>
            <fieldset className="campaign-fallback" disabled><VolunteerForm {...volunteer} /></fieldset>
          </> : <VolunteerForm {...volunteer} />}
        </div>
      </section>

      <section id="newsletter" className="campaign-newsletter" aria-labelledby="newsletter-title">
        <div><h2 id="newsletter-title">Tilaa kampanjan uutiskirje</h2><p>Tilaa uutiskirje, jos haluat seurata kampanjan etenemistä.</p></div>
        <NewsletterForm {...newsletter} disabled={serverFallback} />
      </section>
    </div>
  </div>;
}
