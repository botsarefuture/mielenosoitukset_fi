import { useEffect } from 'react';
import { PrideMap } from '../components/pride/PrideMap';
import { PrideVolunteer } from './PrideVolunteer';
import { prideVolunteerCopy, prideVolunteerEnabled } from './pride-volunteer';
import { PublicListingPage } from '../pages/PublicListingPage';
import type { AppConfig } from './config';
import { listingProps } from './listing';
import type { ListingBootstrap } from './listing';
import type { SessionSummary } from './session';

export const prideRoute = { name: 'listing', scope: 'tag', value: 'pride' } as const;

export const prideCopy = {
  title: 'Pride näkyväksi',
  lead: 'Löydä tulevat Pride-aiheiset mielenosoitukset eri puolilta Suomea ja ilmoita oma tapahtumasi mukaan.',
  empty: 'Meille ei vielä ole ilmoitettu tulevia Pride-mielenosoituksia.',
};

const mapMessages = {
  title: 'Pride-kartta',
  loading: 'Ladataan Pride-karttaa…',
  error: 'Pride-kartan lataaminen epäonnistui. Yritä uudelleen.',
  retry: 'Yritä uudelleen',
  empty: 'Kartalla ei vielä ole tulevia Pride-mielenosoituksia.',
  noCoordinates: 'Tapahtumille ei ole karttasijaintia. Löydät ne mielenosoituslistasta.',
  tileError: 'Karttapohjan lataaminen epäonnistui. Tapahtumat löytyvät myös listasta.',
  popupDetails: 'Avaa mielenosoitus',
  summary: 'Pride-mielenosoituksia: __EVENTS__. Paikkakuntia: __CITIES__. Kartalla: __MAPPED__.',
  zoomIn: 'Lähennä', zoomOut: 'Loitonna',
  mapLabel: 'Pride-mielenosoitukset kartalla',
};

/** Shared with the no-JavaScript document, so both keep the same background and instructions. */
export function PrideDetails({ submitUrl }: { submitUrl: string }) {
  return <>
    <section className="pride-information" aria-labelledby="pride-about-title">
      <h2 id="pride-about-title">Miksi Pride näkyväksi?</h2>
      <p>Pride näkyväksi kokoaa Pride-aiheiset mielenosoitukset yhteen paikkaan. Näkyvyys auttaa osallistujia löytämään tapahtumat ja tukee yhdenvertaisuutta.</p>
      <p>Jokaisella on oikeus olla oma itsensä ja osallistua ilman syrjintää.</p>
    </section>

    <section className="pride-guidelines" id="demo-guidelines" aria-labelledby="pride-guidelines-title">
      <h2 id="pride-guidelines-title">Ilmoita Pride-mielenosoitus</h2>
      <ol>
        <li><a href={submitUrl}>Avaa ilmoituslomake</a>. Kerro tapahtuman nimi, ajankohta, paikka ja kuvaus.</li>
        <li>Lisää tageihin pride, jotta tapahtuma löytyy tältä sivulta.</li>
        <li>Tarkista tiedot ja lähetä ilmoitus. Ilmoitukset tarkistetaan ennen julkaisua.</li>
      </ol>
      <p>Ilmoitus ei saa sisältää syrjintää tai vihapuhetta. <a href="/terms">Lue käyttöehdot</a>.</p>
    </section>
  </>;
}

export default function PrideScreen({ config, session, listing }: {
  config: AppConfig; session: SessionSummary; listing?: ListingBootstrap;
}) {
  const props = listingProps(prideRoute, config, session);
  // The page mounts after the browser resolves the address hash, so a direct link has to scroll here.
  // Scrolling loads more events above the lower sections, so stay aligned until the reader takes over.
  useEffect(() => {
    const { hash } = window.location;
    const target = ['#demos', '#demo-guidelines', '#pride-map-section', '#banderolli'].includes(hash) ? document.querySelector(hash) : null;
    const page = document.querySelector('.pride-page');
    if (!target || !page) return undefined;
    const align = () => target.scrollIntoView({ block: 'start' });
    const observer = new ResizeObserver(align);
    observer.observe(page);
    const inputs = ['wheel', 'touchstart', 'pointerdown', 'keydown'];
    const stop = () => {
      observer.disconnect();
      window.clearTimeout(timer);
      inputs.forEach(name => window.removeEventListener(name, stop));
    };
    const timer = window.setTimeout(stop, 8000);
    inputs.forEach(name => window.addEventListener(name, stop, { passive: true }));
    align();
    return stop;
  }, []);
  const volunteers = prideVolunteerEnabled();
  return <div className="pride-page">
    <section className="pride-intro" aria-labelledby="pride-title">
      <h1 id="pride-title">{prideCopy.title}</h1>
      <p className="pride-intro__lead">{prideCopy.lead}</p>
      <div className="pride-actions">
        <a className="button button-primary" href="#demos">Katso mielenosoitukset</a>
        <a className="button button-secondary" href={config.urls.submit}>Ilmoita mielenosoitus</a>
        {volunteers && <a className="button button-secondary" href="#banderolli">{prideVolunteerCopy.navButton}</a>}
      </div>
    </section>

    <section className="pride-map-section" id="pride-map-section" aria-labelledby="pride-map-title">
      <header className="pride-section-header">
        <h2 id="pride-map-title">Pride-kartta</h2>
        <p>Kartalla näkyvät kaikki tulevat Pride-mielenosoitukset. Listan haku ei rajaa karttaa.</p>
      </header>
      <PrideMap endpoint={props.endpoint} detailUrl={config.urls.detail} seriesUrl={config.urls.series}
        locale={config.locale} tag="pride" messages={mapMessages} />
    </section>

    <section id="demos" aria-labelledby="listing-title">
      <PublicListingPage {...props} title="Pride-mielenosoitukset" headingLevel={2}
        messages={{ ...props.messages, empty: prideCopy.empty }}
        initialData={listing?.page ?? undefined} initialSearch={listing?.query}
        onSearch={search => {
          if (!session.siteAnalyticsEnabled || navigator.doNotTrack === '1') return;
          try { navigator.sendBeacon('/api/analytics/event', new Blob([
            JSON.stringify({ event: 'demo_search', resource_id: search.slice(0, 120) }),
          ], { type: 'application/json' })); } catch { /* Optional analytics. */ }
        }} />
    </section>

    {volunteers && <PrideVolunteer privacyUrl={config.urls.privacy} />}

    <PrideDetails submitUrl={config.urls.submit} />
  </div>;
}
