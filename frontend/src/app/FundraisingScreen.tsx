import data from '../../../mielenosoitukset_fi/utils/data/fundraising.json';
import type { AppConfig } from './config';
import { fundraisingDetails } from './fundraising';
import type { FundraisingDetails } from './fundraising';

const finnishDate = (iso: string) => iso.split('-').reverse().join('.');

function Arrow() {
  return <i className="fas fa-arrow-right" aria-hidden="true" />;
}

/** The fundraising page; payment details appear only while donations are open. */
export function FundraisingPage({ details, config }: { details: FundraisingDetails; config: AppConfig }) {
  const f = details;
  const status = f.is_preparation ? 'Valmistelussa' : f.can_donate ? 'Keräys avoinna' : 'Lahjoittaminen suljettu';
  return <article className="public-content campaign-page" lang="fi">
    <section className="campaign-fundraising-intro" aria-labelledby="fundraising-title">
      <div>
        <h1 id="fundraising-title">Jotta mielenosoitukset löytyvät</h1>
        <p>Haluamme tuoda mielenosoitukset.fi-palvelun yhä useamman ihmisen tietoon. {f.is_preparation
          ? 'Suunnittelemme pienkeräystä yhteisen markkinointikampanjan toteuttamiseen.'
          : 'Pienkeräyksellä rahoitetaan yhteinen markkinointikampanja.'}</p>
      </div>
    </section>

    <div className="public-content__grid">
      <div className="public-content__sections">
        <section className="public-content__card" aria-labelledby="purpose-title">
          <h2 id="purpose-title">Mihin varat käytetään?</h2>
          <p>Kerätyt varat käytetään mielenosoitukset.fi-palvelun tunnettuuden lisäämiseen tähtäävän markkinointikampanjan toteuttamiseen.</p>
          <ul>
            <li>Markkinointimateriaalien, kuten tarrojen, julisteiden ja banderollien, suunnittelu, valmistus ja hankinta.</li>
            <li>Kampanjan toteuttamisesta aiheutuvat muut kulut, kuten matkakulut.</li>
          </ul>
          <h3>Jos varoja jää yli</h3>
          <p>Mikäli varoja jää ensisijaisen käyttötarkoituksen toteuttamisen jälkeen, ne käytetään mielenosoitukset.fi-palvelun ylläpitoon ja jatkuvuuden turvaamiseen.</p>
        </section>

        <section className="public-content__card" aria-labelledby="service-title">
          <h2 id="service-title">Mikä on Mielenosoitukset.fi?</h2>
          <p>Mielenosoitukset.fi kokoaa Suomessa järjestettäviä mielenosoituksia yhteen paikkaan. Palvelusta voit etsiä tulevia tapahtumia ja ilmoittaa mielenosoituksesta muiden löydettäväksi.</p>
          <p>Palvelua ylläpidetään riippumattomana, voittoa tavoittelemattomana vapaaehtoisprojektina. Tavoitteena on helpottaa tapahtumien löytämistä ja osallistumista.</p>
          <a className="public-content__link" href={config.urls.info}>Lue lisää palvelusta <Arrow /></a>
        </section>
      </div>

      <aside className="public-content__card public-content__summary" aria-labelledby="summary-title">
        <h2 id="summary-title">{f.is_preparation ? 'Keräyksen suunnitelma' : 'Keräyksen tiedot'}</h2>
        {f.is_preparation && <p>Ilmoitus on tarkoitus jättää 10.11.2026. Ilmoituksen jättämistä tai keräyksen aloitusta ei ole vahvistettu.</p>}
        <dl className="public-content__facts">
          <div><dt>Keräystavoite</dt><dd className="public-content__amount">2 500 €</dd></div>
          <div><dt>{f.confirmed ? 'Keräysaika' : 'Suunniteltu keräysaika'}</dt><dd>{f.display_start_date && f.display_end_date
            ? <><time dateTime={f.display_start_date}>{finnishDate(f.display_start_date)}</time>–<time dateTime={f.display_end_date}>{finnishDate(f.display_end_date)}</time></>
            : 'Vahvistetaan myöhemmin'}</dd></div>
          <div><dt>Tilanne</dt><dd>{status}</dd></div>
          <div><dt>Keräyksen järjestäjä</dt><dd>{f.confirmed ? f.organizer : 'Vahvistetaan myöhemmin'}</dd></div>
          <div><dt>Keräysnumero</dt><dd>{f.confirmed ? f.collection_number : 'Lisätään ilmoituksen vahvistamisen jälkeen'}</dd></div>
        </dl>
        {f.can_donate ? <section className="public-content__notice" aria-labelledby="donate-title">
          <h3 id="donate-title">Näin lahjoitat</h3>
          <p>Lahjoita vain keräysaikana {finnishDate(f.start_date!)}–{finnishDate(f.end_date!)}. Älä tee lahjoitusta keräysajan päätyttyä.</p>
          <div className="campaign-mobilepay-links">{f.mobilepay_links.filter(link => link.url).map(link =>
            <a key={link.url} className="public-content__link" href={link.url} rel="noopener noreferrer">{link.label} <Arrow /></a>)}</div>
          {f.iban && f.recipient && <dl className="public-content__facts">
            <div><dt>Saaja</dt><dd>{f.recipient}</dd></div>
            <div><dt>Tilinumero (IBAN)</dt><dd>{f.iban}</dd></div>
            {f.reference && <div><dt>Viite</dt><dd>{f.reference}</dd></div>}
          </dl>}
          {f.payment_url && <a className="public-content__link" href={f.payment_url} rel="noopener noreferrer">Siirry lahjoittamaan <Arrow /></a>}
        </section> : <div className="public-content__notice">
          <h3>{f.is_preparation ? 'Lahjoittaminen ei ole vielä avoinna' : 'Lahjoittaminen on suljettu'}</h3>
          <p>{f.confirmed
            ? 'Lahjoituksia voi tehdä vain vahvistettuna keräysaikana ja keräyksen ollessa avoinna.'
            : 'Keräyksen järjestäjä, keräysnumero ja lahjoitusohjeet julkaistaan, kun tiedot ja aloitus on vahvistettu. Myös keräysaika on vielä suunniteltu.'}</p>
        </div>}
        {f.is_preparation && f.mobilepay_links.length > 0 && <section className="public-content__notice" aria-labelledby="mobilepay-title">
          <h3 id="mobilepay-title">MobilePay</h3>
          {f.mobilepay_links.map((link, index) => <p key={index}><strong>{link.label}</strong><br />Linkki lisätään ennen keräyksen avaamista.</p>)}
        </section>}
        <p>Onko sinulla kysyttävää keräyksestä?</p>
        <a className="public-content__link" href={config.urls.contact}>Ota yhteyttä <Arrow /></a>
        <p><a className="public-content__link" href="mailto:tuki@mielenosoitukset.fi">tuki@mielenosoitukset.fi</a></p>
      </aside>
    </div>
  </article>;
}

export const fundraisingData: unknown = data;

export default function FundraisingScreen({ config, today }: { config: AppConfig; today: string }) {
  return <FundraisingPage details={fundraisingDetails(fundraisingData, today)} config={config} />;
}
