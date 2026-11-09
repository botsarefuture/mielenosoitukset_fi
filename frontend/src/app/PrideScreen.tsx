import { PrideMap } from '../components/pride/PrideMap';
import { PublicListingPage } from '../pages/PublicListingPage';
import type { AppConfig } from './config';
import { listingProps } from './listing';
import type { ListingBootstrap } from './listing';
import type { SessionSummary } from './session';

export const prideRoute = { name: 'listing', scope: 'tag', value: 'pride' } as const;

export const prideCopy = {
  title: 'Pride näkyväksi',
  lead: 'Löydä tulevat Pride-aiheiset mielenosoitukset eri puolilta Suomea ja ilmoita oma tapahtumasi mukaan.',
};

const mapMessages = {
  title: 'Pride-kartta',
  loading: 'Ladataan Pride-karttaa...',
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

export default function PrideScreen({ config, session, listing }: {
  config: AppConfig; session: SessionSummary; listing?: ListingBootstrap;
}) {
  const props = listingProps(prideRoute, config, session);
  return <div className="pride-page">
    <section className="pride-intro" aria-labelledby="pride-title">
      <h1 id="pride-title">{prideCopy.title}</h1>
      <p className="pride-intro__lead">{prideCopy.lead}</p>
      <div className="pride-actions">
        <a className="button button-primary" href="#demos">Katso mielenosoitukset</a>
        <a className="button button-secondary" href={config.urls.submit}>Ilmoita mielenosoitus</a>
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
        messages={{ ...props.messages, empty: 'Meille ei vielä ole ilmoitettu tulevia Pride-mielenosoituksia.' }}
        initialData={listing?.page ?? undefined} initialSearch={listing?.query} />
    </section>

    <section className="pride-information" aria-labelledby="pride-about-title">
      <h2 id="pride-about-title">Miksi Pride näkyväksi?</h2>
      <p>Pride näkyväksi kokoaa Pride-aiheiset mielenosoitukset yhteen paikkaan. Näkyvyys auttaa osallistujia löytämään tapahtumat ja tukee yhdenvertaisuutta.</p>
      <p>Jokaisella on oikeus olla oma itsensä ja osallistua ilman syrjintää.</p>
    </section>

    <section className="pride-guidelines" id="demo-guidelines" aria-labelledby="pride-guidelines-title">
      <h2 id="pride-guidelines-title">Ilmoita Pride-mielenosoitus</h2>
      <ol>
        <li><a href={config.urls.submit}>Avaa ilmoituslomake</a>. Kerro tapahtuman nimi, ajankohta, paikka ja kuvaus.</li>
        <li>Lisää tageihin pride, jotta tapahtuma löytyy tältä sivulta.</li>
        <li>Tarkista tiedot ja lähetä ilmoitus. Ilmoitukset tarkistetaan ennen julkaisua.</li>
      </ol>
      <p>Ilmoitus ei saa sisältää syrjintää tai vihapuhetta. <a href="/terms">Lue käyttöehdot</a>.</p>
    </section>
  </div>;
}
