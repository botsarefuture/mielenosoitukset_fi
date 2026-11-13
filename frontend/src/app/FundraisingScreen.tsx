import data from '../../../mielenosoitukset_fi/utils/data/fundraising.json';
import type { AppConfig } from './config';
import { useState } from 'react';
import { fundraisingDetails, fundraisingExtras, fundraisingIcs } from './fundraising';
import type { FundraisingDetails, FundraisingExtras } from './fundraising';

const finnishDate = (iso: string) => iso.split('-').reverse().join('.');

function Arrow() {
  return <i className="fas fa-arrow-right" aria-hidden="true" />;
}

/** Copies the IBAN; the button label confirms it for assistive technology too. */
function CopyIban({ iban }: { iban: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(iban);
      setState('copied');
    } catch {
      setState('failed');
    }
  };
  return <>
    <button type="button" className="fundraising-copy" onClick={copy}>Kopioi tilinumero</button>
    <span className="fundraising-copy__status" role="status">{state === 'copied' ? 'Tilinumero kopioitu' : state === 'failed' ? 'Kopiointi ei onnistunut, valitse numero ja kopioi se itse' : ''}</span>
  </>;
}

/** The fundraising page; payment details appear only while donations are open. */
export function FundraisingPage({ details, extras, config }: { details: FundraisingDetails; extras: FundraisingExtras; config: AppConfig }) {
  const f = details;
  const pre = extras.pre_launch;
  const opens = extras.opens_date;
  const opensShort = opens ? finnishDate(opens).replace(/\.\d{4}$/, '.') : '';
  const calendarHref = opens
    ? `data:text/calendar;charset=utf-8,${encodeURIComponent(fundraisingIcs(opens, `${config.origin}/ker%C3%A4ys`))}` : '';
  const status = pre ? `Aukeaa ${opens ? finnishDate(opens) : ''}` : f.is_preparation ? 'Valmistelussa' : f.can_donate ? 'Keräys avoinna' : 'Lahjoittaminen suljettu';
  return <article className="public-content campaign-page" lang="fi">
    <section className="campaign-fundraising-intro" aria-labelledby="fundraising-title">
      <div>
        <h1 id="fundraising-title">Jotta mielenosoitukset löytyvät</h1>
        <p>Haluamme tuoda Mielenosoitukset.fi-palvelun yhä useamman ihmisen tietoon. Pienkeräyksellä rahoitetaan yhteinen markkinointikampanja.</p>
      </div>
    </section>

    {pre && opens && <section className="public-content__card fundraising-prelaunch" aria-labelledby="prelaunch-title">
      <h2 id="prelaunch-title">Pienkeräys aukeaa {opensShort}</h2>
      <p>Keräys alkaa {finnishDate(opens)} kello 0.00. Lahjoitusohjeet ja tilinumero julkaistaan tälle sivulle silloin. Lahjoita vasta keräysajan alettua.</p>
      <a className="fundraising-calendar" href={calendarHref} download="pienkerays-aukeaa.ics">Lisää kalenteriin</a>
      <p className="fundraising-prelaunch__note">Kalenterimerkintä ladataan laitteellesi. Emme kerää siihen yhteystietojasi.</p>
    </section>}

    <div className="public-content__grid">
      <div className="public-content__sections">
        <section className="public-content__card" aria-labelledby="purpose-title">
          <h2 id="purpose-title">Mihin varat käytetään?</h2>
          <p>Kerätyt varat käytetään Mielenosoitukset.fi-palvelun tunnettuuden lisäämiseen tähtäävän markkinointikampanjan toteuttamiseen.</p>
          <ul>
            <li>Markkinointimateriaalien, kuten tarrojen, julisteiden ja banderollien, suunnittelu, valmistus ja hankinta.</li>
            <li>Kampanjan toteuttamisesta aiheutuvat muut kulut, kuten matkakulut.</li>
          </ul>
          <h3>Jos varoja jää yli</h3>
          <p>Mikäli varoja jää ensisijaisen käyttötarkoituksen toteuttamisen jälkeen, ne käytetään Mielenosoitukset.fi-palvelun ylläpitoon ja jatkuvuuden turvaamiseen.</p>
        </section>

        <section className="public-content__card" aria-labelledby="service-title">
          <h2 id="service-title">Mikä on Mielenosoitukset.fi?</h2>
          <p>Mielenosoitukset.fi kokoaa Suomessa järjestettäviä mielenosoituksia yhteen paikkaan. Palvelusta voit etsiä tulevia tapahtumia ja ilmoittaa mielenosoituksesta muiden löydettäväksi.</p>
          <p>Palvelua ylläpidetään riippumattomana, voittoa tavoittelemattomana vapaaehtoisprojektina. Tavoitteena on helpottaa tapahtumien löytämistä ja osallistumista.</p>
          <a className="public-content__link" href={config.urls.info}>Lue lisää palvelusta <Arrow /></a>
        </section>
      </div>

      <aside className="public-content__card public-content__summary" aria-labelledby="summary-title">
        <h2 id="summary-title">Keräyksen tiedot</h2>
        <dl className="public-content__facts">
          <div><dt>Pienkeräysnumero</dt><dd>{f.collection_number || 'Vahvistetaan myöhemmin'}</dd></div>
          <div><dt>Keräysaika</dt><dd>{f.display_start_date && f.display_end_date
            ? <><time dateTime={f.display_start_date}>{finnishDate(f.display_start_date)}</time>–<time dateTime={f.display_end_date}>{finnishDate(f.display_end_date)}</time></>
            : 'Vahvistetaan myöhemmin'}</dd></div>
          <div><dt>Keräysalue</dt><dd>{extras.area || 'Vahvistetaan myöhemmin'}</dd></div>
          <div><dt>Keräyksen järjestäjä</dt><dd>{f.organizer || 'Vahvistetaan myöhemmin'}</dd></div>
          <div><dt>Keräystavoite</dt><dd className="public-content__amount">2 500 €</dd></div>
          <div><dt>Tilanne</dt><dd>{status}</dd></div>
        </dl>
        {pre ? <div className="public-content__notice">
          <h3>Lahjoittaminen ei ole vielä avoinna</h3>
          <p>Tilinumero ja lahjoitusohjeet julkaistaan, kun keräys alkaa.</p>
        </div> : f.can_donate ? <section className="public-content__notice" aria-labelledby="donate-title">
          <h3 id="donate-title">Näin lahjoitat</h3>
          <p>Lahjoita vain keräysaikana {finnishDate(f.start_date!)}–{finnishDate(f.end_date!)}. Älä tee lahjoitusta keräysajan päätyttyä.</p>
          <div className="campaign-mobilepay-links">{f.mobilepay_links.filter(link => link.url).map(link =>
            <a key={link.url} className="public-content__link" href={link.url} rel="noopener noreferrer">{link.label} <Arrow /></a>)}</div>
          {f.iban && f.recipient && <>
            <dl className="public-content__facts">
              <div><dt>Saaja</dt><dd>{f.recipient}</dd></div>
              <div><dt>Tilinumero (IBAN)</dt><dd className="fundraising-iban">{f.iban}</dd></div>
              {extras.bic && <div><dt>BIC</dt><dd>{extras.bic}</dd></div>}
              {f.reference && <div><dt>Viite</dt><dd>{f.reference}</dd></div>}
            </dl>
            <CopyIban iban={f.iban} />
          </>}
          {f.payment_url && <a className="public-content__link" href={f.payment_url} rel="noopener noreferrer">Siirry lahjoittamaan <Arrow /></a>}
        </section> : <div className="public-content__notice">
          <h3>{f.is_preparation ? 'Lahjoittaminen ei ole vielä avoinna' : 'Lahjoittaminen on suljettu'}</h3>
          <p>{f.confirmed
            ? 'Lahjoituksia voi tehdä vain vahvistettuna keräysaikana ja keräyksen ollessa avoinna.'
            : 'Keräyksen järjestäjä ja lahjoitusohjeet julkaistaan, kun tiedot on vahvistettu.'}</p>
        </div>}
        {!pre && f.is_preparation && f.mobilepay_links.length > 0 && <section className="public-content__notice" aria-labelledby="mobilepay-title">
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

/** `data` is the API copy; the bundled file is the fallback when the API is unreachable. */
export default function FundraisingScreen({ config, today, data }: { config: AppConfig; today: string; data?: Record<string, unknown> | null }) {
  return <FundraisingPage details={fundraisingDetails(data ?? fundraisingData, today)} extras={fundraisingExtras(data ?? fundraisingData, today)} config={config} />;
}
