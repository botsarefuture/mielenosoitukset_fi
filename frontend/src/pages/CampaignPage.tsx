import { useState } from 'react';
import { VolunteerForm } from '../components/VolunteerForm';
import type { VolunteerFormProps } from '../components/VolunteerForm';
import { campaignPhase, defaultSchedule, fiDate, fiDayMonth, fiRange, fiWeekdayEssive, fiWeekdayShort, fiWeekday } from '../app/campaign-schedule';
import type { CampaignSchedule, Milestone } from '../app/campaign-schedule';

export interface CampaignPageProps {
  urls: { home: string; fundraising: string; privacy: string; pride?: string };
  volunteer: VolunteerFormProps;
  /** Dates from the shared fundraising configuration. */
  schedule?: CampaignSchedule;
  /** Helsinki date (`YYYY-MM-DD`) the server computed the phase from. */
  today: string;
  /** Address shown in the ready-made share text, without the scheme. */
  shareAddress?: string;
  /** The opening interest form is off until its backend ships. */
  openingForm?: boolean;
  serverFallback?: boolean;
}

const Icon = ({ name }: { name: string }) => <i className={`fa-solid fa-${name}`} aria-hidden="true" />;
const Arrow = () => <span aria-hidden="true">→</span>;

function CopyShare({ text }: { text: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setState('copied');
    } catch {
      setState('failed');
    }
  };
  return <>
    <button className="kv-btn" type="button" onClick={copy}><Icon name="copy" /> Kopioi teksti</button>
    <span className="kv-copy-status" role="status">{state === 'copied' ? 'Teksti kopioitu' : state === 'failed' ? 'Kopiointi ei onnistunut, valitse teksti ja kopioi se itse' : ''}</span>
  </>;
}

function Timeline({ schedule, milestones, urls, openingForm }: { schedule: CampaignSchedule; milestones: Milestone[]; urls: CampaignPageProps['urls']; openingForm: boolean }) {
  const items: Record<Milestone['key'], { time: string; title: string; text: string; link?: { href: string; label: string } }> = {
    collectionOpens: { time: fiDate(schedule.collectionStart), title: 'Pienkeräys aukeaa', text: 'Keräys rahoittaa kampanjan markkinointia ja palvelun ylläpitoa.',
      link: { href: urls.fundraising, label: 'Tutustu pienkeräykseen' } },
    collectionEnds: { time: fiDate(schedule.collectionEnd), title: 'Pienkeräys päättyy', text: 'Keräysaika päättyy.' },
    campaignStarts: { time: fiDate(schedule.campaignStart), title: 'Kampanja alkaa', text: 'Kampanja käynnistyy eri puolilla Suomea.' },
    opening: { time: `${fiWeekdayShort(schedule.openingDate)} ${fiDate(schedule.openingDate)}, klo ${schedule.openingTime} alkaen`, title: 'Kampanjan avajaiset',
      text: `${schedule.openingCityIn[0].toUpperCase()}${schedule.openingCityIn.slice(1)}. Paikka tarkentuu.`,
      link: openingForm ? { href: '#avajaiset', label: 'Ilmoittaudu kiinnostuneeksi' } : undefined },
    marketingWeek: { time: fiRange(schedule.marketingStart, schedule.marketingEnd), title: 'Markkinointiviikko', text: 'Kampanjan näkyvin viikko. Ohjelma tarkentuu.' },
  };
  return <ol className="kx-tl">
    {milestones.map(milestone => {
      const item = items[milestone.key];
      const className = milestone.state === 'current' ? 'kx-tl__cur' : milestone.state === 'done' ? 'kx-tl__done' : 'kx-tl__next';
      const label = milestone.state === 'current' ? 'Tässä ollaan nyt' : milestone.upNext ? 'Seuraavaksi' : '';
      return <li key={milestone.key} className={className} aria-current={milestone.state === 'current' ? 'step' : undefined}>
        <span className="kx-tl__dot">{milestone.state === 'done' && <Icon name="check" />}</span>
        {label
          ? <span className="kx-here"><Icon name="location-dot" />{label}</span>
          : <span className="kx-here kx-here--empty" aria-hidden="true">&nbsp;</span>}
        <time dateTime={milestone.key === 'collectionEnds' ? schedule.collectionEnd : milestone.from}>{item.time}</time>
        <h3>{item.title}</h3>
        <p>{item.text}</p>
        {item.link && <a className="campaign-text-link" href={item.link.href}>{item.link.label} <Arrow /></a>}
      </li>;
    })}
  </ol>;
}

export function CampaignPage({ urls, volunteer, schedule = defaultSchedule, today, shareAddress = 'mielenosoitukset.fi/kampanja', openingForm = false, serverFallback = false }: CampaignPageProps) {
  const phase = campaignPhase(schedule, today);
  const s = schedule;
  const collectionRange = `${fiDate(s.collectionStart)}–${fiDate(s.collectionEnd)}`;
  const marketing = fiRange(s.marketingStart, s.marketingEnd);
  const openingLine = `${fiWeekdayEssive(s.openingDate)} ${fiDate(s.openingDate)}`;
  const opensShort = fiDayMonth(s.collectionStart);
  const shareText = `Mielenosoitukset.fi kokoaa tulevat mielenosoitukset eri puolilta Suomea yhteen kalenteriin. Kampanja alkaa ${fiDate(s.campaignStart)}. Lue lisää: ${shareAddress}`;
  const fundraisingInfo = <section id="kerays" className="kv-sec" aria-labelledby="ker"><div className="kv-trust kv-trust--compact">
    <h2 id="ker" className="kv-h2" style={{ marginBottom: '.9rem', fontSize: '1.4rem' }}>Tietoa keräyksestä</h2>
    <dl>
      <div><dt>Pienkeräysnumero</dt><dd>{s.collectionNumber}</dd></div>
      <div><dt>Aika</dt><dd>{collectionRange}</dd></div>
      <div><dt>Alue</dt><dd>{s.area}</dd></div>
      <div><dt>Käyttötarkoitus</dt><dd>Kampanjan markkinointi (tarrat, julisteet ja banderollit) sekä palvelun ylläpito</dd></div>
    </dl>
    <a className="campaign-text-link kv-link" href={urls.fundraising} style={{ marginTop: '.5rem' }}>Lue lisää keräyksestä <Arrow /></a>
  </div></section>;
  const helpCards = phase.collectionClosed ? 3 : 4;

  return <div className="campaign-page kv" lang="fi">
    <section className="kv-hero" aria-labelledby="t">
      <div>
        <h1 id="t">Mielenosoitukset.fi näkyviin kymmeniin kaupunkeihin</h1>
        <p className="kv-lead">Mielenosoitukset.fi kokoaa Suomen mielenosoitukset yhteen paikkaan. Kampanja tekee palvelun tunnetuksi, jotta yhä useampi löytää tiedon tulevista mielenosoituksista.</p>
        <div className="kv-actions">
          <a className="kv-btn kv-btn--primary" href="#vapaaehtoiseksi">Tule mukaan</a>
          <a className="kv-btn" href="#avajaiset">Tule avajaisiin</a>
          {phase.preLaunch && <a className="kv-btn kv-btn--soft" href={urls.fundraising}><Icon name="clock" /> Pienkeräys aukeaa {opensShort}</a>}
          {phase.collectionOpen && <a className="kv-btn kv-btn--primary" href={urls.fundraising}>Lahjoita keräykseen</a>}
        </div>
        <p className="kv-meta"><i className="fa-regular fa-calendar" aria-hidden="true" /> Kampanja alkaa {fiDate(s.campaignStart)}. Avajaiset {openingLine} {s.openingCityIn}.</p>
      </div>
      <aside className="kv-card--facts" aria-label="Kampanja lyhyesti">
        <h2>Kampanja lyhyesti</h2>
        <div className="kv-fact"><b>noin 25 000</b><span>tarraa kampanjan tavoitteena</span></div>
        <div className="kv-fact"><b>12</b><span>banderollia, joista 8 Pride-banderollia</span></div>
        <div className="kv-fact"><b>{fiRange(s.marketingStart, s.marketingEnd, false)}</b><span>markkinointiviikko {s.marketingStart.slice(0, 4)}</span></div>
      </aside>
    </section>

    <section className="kv-sec" aria-labelledby="auta">
      <h2 id="auta">Näin voit auttaa</h2>
      <div className={`kv-help${helpCards === 3 ? ' kv-help--3' : ''}`}>
        {phase.preLaunch && <div><span className="kv-ico"><Icon name="bell" /></span><h3>Pienkeräys aukeaa {opensShort}</h3>
          <p>Keräys rahoittaa kampanjan markkinointia ja palvelun ylläpitoa. Lahjoittaminen on mahdollista vasta, kun keräys avautuu.</p>
          <a className="kv-btn" href={`${urls.fundraising}#prelaunch-title`}>Tilaa muistutus</a></div>}
        {phase.collectionOpen && <div><span className="kv-ico"><Icon name="hand-holding-heart" /></span><h3>Lahjoita keräykseen</h3>
          <p>Keräys rahoittaa kampanjan markkinointia ja palvelun ylläpitoa.</p>
          <a className="kv-btn kv-btn--primary" href={urls.fundraising}>Lahjoita keräykseen</a></div>}
        <div><span className="kv-ico"><Icon name="people-group" /></span><h3>Tule vapaaehtoiseksi</h3>
          <p>Jaa tarroja, kanna banderollia Pridessa tai auta viestinnässä.</p>
          <a className="kv-btn kv-btn--primary" href="#vapaaehtoiseksi">Ilmoittaudu mukaan</a></div>
        <div><span className="kv-ico"><Icon name="champagne-glasses" /></span><h3>Tule avajaisiin</h3>
          <p>{openingLine[0].toUpperCase()}{openingLine.slice(1)} {s.openingCityIn}. Paikka tarkentuu.</p>
          <a className="kv-btn" href="#avajaiset">{openingForm ? 'Ilmoittaudu kiinnostuneeksi' : 'Katso tiedot'}</a></div>
        <div><span className="kv-ico"><Icon name="share-nodes" /></span><h3>Jaa tieto eteenpäin</h3>
          <p>Kopioi valmis teksti ja lähetä se ryhmään tai kaverille.</p>
          <details><summary>Näytä teksti</summary><p>{shareText}</p></details>
          {serverFallback ? null : <CopyShare text={shareText} />}</div>
      </div>
    </section>

    {phase.collectionInfoFirst && fundraisingInfo}

    <section className="kv-sec" aria-labelledby="mita">
      <h2 id="mita">Mistä on kyse</h2>
      <div className="kv-what">
        <figure className="kx-stickerfig">
          <img src="/static/kampanja/sticker-2026-fi.png" width={1145} height={1600} loading="lazy" style={{ maxWidth: 260 }}
            alt="Vuoden 2026 tarra: QR-koodi ja teksti Kaikki mielenosoitukset kädenulottuvilla" />
          <figcaption>Esimerkki: vuoden 2026 tarra</figcaption>
        </figure>
        <div>
          <ul>
            <li><span className="kv-ico"><Icon name="sticky-note" /></span><div><h3>Tarrat</h3><p>Tavoitteena on noin 25 000 tarraa kymmeniin kaupunkeihin. Tarroissa on palvelun osoite ja QR-koodi.</p></div></li>
            <li><span className="kv-ico"><Icon name="flag" /></span><div><h3>Banderollit ja Pride näkyväksi</h3><p>Kampanjaan kuuluu 12 banderollia: 8 Pride-banderollia ja 4 tavallista. Tavoitteena on, että jokaisessa Pridessa on Mielenosoitukset.fi-banderolli. <a className="kv-link" href="#pride">Lue lisää</a></p></div></li>
            <li><span className="kv-ico"><Icon name="server" /></span><div><h3>Palvelun ylläpito</h3><p>Kalenteri pysyy ajan tasalla ja kaikkien käytössä.</p></div></li>
          </ul>
          <div className="kv-actions"><a className="kv-btn kv-btn--primary kv-btn--wide" href="#vapaaehtoiseksi">Tule levittämään</a></div>
        </div>
      </div>
    </section>

    {!phase.collectionInfoFirst && fundraisingInfo}

    <section className="kv-sec" aria-labelledby="aikataulu">
      <h2 id="aikataulu">Aikataulu</h2>
      <Timeline schedule={s} milestones={phase.milestones} urls={urls} openingForm={openingForm} />
    </section>

    <section className="kv-sec" aria-labelledby="lahde"><div className="kv-vol">
      <div>
        <h2 id="lahde" className="kv-h2" style={{ marginBottom: '1rem' }}>Tule mukaan</h2>
        <p className="kv-lead">Yksi ihminen riittää aloittamaan. Kerro, missä haluaisit auttaa, niin otamme yhteyttä. Jos haluat auttaa markkinointiviikolla {marketing}, kerro siitä ilmoittautuessasi.</p>
      </div>
      <div className="volunteer-signup campaign-signup kv-form" id="vapaaehtoiseksi">
        <h3>Ilmoittaudu vapaaehtoiseksi</h3>
        <p className="kv-small">Nimi ja sähköposti ovat pakollisia.</p>
        <p className="kv-small">Vahvistat ilmoittautumisen sähköpostilla. Käytämme tietoja vain yhteydenpitoon vapaaehtoistoiminnassa. <a className="kv-link" href={urls.privacy}>Tietosuojaseloste</a></p>
        {serverFallback ? <>
          <p className="campaign-loading-note">Lomaketta ladataan. Jos se ei avaudu, voit ottaa yhteyttä: <a href="mailto:tuki@mielenosoitukset.fi">tuki@mielenosoitukset.fi</a>.</p>
          <noscript><p>Ilmoittautumislomake tarvitsee JavaScriptin. Tietojasi ei ole lähetetty.</p></noscript>
          <fieldset className="campaign-fallback" disabled><VolunteerForm {...volunteer} /></fieldset>
        </> : <VolunteerForm {...volunteer} />}
      </div>
    </div></section>

    <section id="avajaiset" className="kv-sec" aria-labelledby="av"><div className="kv-party kv-party--solo">
      <div>
        <h2 id="av" className="kv-h2" style={{ marginBottom: '1.25rem' }}>Kampanjan avajaiset {s.openingCityIn}</h2>
        <dl className="kv-facts2">
          <div><dt>Päivä</dt><dd>{fiWeekday(s.openingDate)} {fiDate(s.openingDate)}</dd></div>
          <div><dt>Aika</dt><dd>{s.openingTime} alkaen</dd></div>
          <div><dt>Paikka</dt><dd>{s.openingCity}, paikka tarkentuu</dd></div>
        </dl>
        <p className="kv-lead" style={{ fontSize: '1.05rem' }}>Tervetuloa kampanjan avajaisiin. Tapaa vapaaehtoisia ja kuule, mitä kampanja tekee. Ilmoittautuminen ei sido mihinkään.</p>
      </div>
    </div></section>

    <section id="pride" className="kv-sec" aria-labelledby="pr"><div className="kv-pride">
      <div>
        <h2 id="pr" className="kv-h2" style={{ marginBottom: '1rem' }}>Pride näkyväksi</h2>
        <p className="kv-lead" style={{ fontSize: '1.05rem' }}>Tavoitteena on, että jokaisessa Pridessa on Mielenosoitukset.fi-banderolli. Tarvitsemme kantajia. Banderolleja on 12: 8 Pride-banderollia ja 4 tavallista.</p>
        <div className="kv-actions"><a className="kv-btn kv-btn--primary" href={`${urls.pride ?? '/pride-nakyvaksi'}#banderolli`}>Ilmoittaudu kantajaksi</a></div>
      </div>
      <div className="kv-pairs"><div><b>8</b><span>Pride-banderollia</span></div><div><b>4</b><span>tavallista banderollia</span></div></div>
    </div></section>

    <section className="kv-sec" aria-labelledby="ukk">
      <h2 id="ukk">Usein kysyttyä</h2>
      <div className="kv-faq">
        <details><summary>Milloin kampanja alkaa?</summary><p>Kampanja alkaa {fiDate(s.campaignStart)}. Sitä ennen, {collectionRange}, pienkeräys kerää varat tarroihin, banderolleihin ja palvelun ylläpitoon.</p></details>
        <details><summary>Mihin keräysvarat käytetään?</summary><p>Kampanjan markkinointiin eli tarroihin, julisteisiin ja banderolleihin sekä palvelun ylläpitoon. Tarkemmat tiedot ovat keräyssivulla.</p></details>
        <details><summary>Onko keräys luvallinen?</summary><p>Keräys on pienkeräys, jonka numero on {s.collectionNumber}. Keräysaika on {collectionRange}, ja keräys on voimassa koko Suomessa Ahvenanmaata lukuun ottamatta.</p></details>
        <details><summary>Miten voin auttaa ilman rahaa?</summary><p>Voit ilmoittautua vapaaehtoiseksi, jakaa tietoa palvelusta tai tulla avajaisiin. Jakamiseen ei tarvita ilmoittautumista.</p></details>
        <details><summary>Missä ja milloin avajaiset ovat?</summary><p>Kampanjan avajaiset ovat {openingLine} {s.openingCityIn} kello {s.openingTime} alkaen. Paikka tarkentuu. Kerromme sen kaikille, jotka ovat ilmoittautuneet kiinnostuneiksi.</p></details>
        <details><summary>Mitä tietoja avajaisiin ilmoittautuminen tallentaa?</summary><p>Tallennamme sähköpostiosoitteesi ja halutessasi paikkakunnan sekä vastauksesi pääsylippukysymykseen. Käytämme tietoja avajaisten viesteihin ja kampanjan päivityksiin. Voit perua milloin tahansa. Poistamme tiedot avajaisten jälkeen, ellet anna uutta suostumusta.</p></details>
        <details><summary>Mikä on markkinointiviikko?</summary><p>Markkinointiviikko on {marketing}, maanantaista sunnuntaihin. Tavoitteena on tehdä siitä kampanjan näkyvin viikko. Ohjelma ei ole vielä selvillä ja tarkentuu myöhemmin.</p></details>
        <details><summary>Miten tarrat jaetaan?</summary><p>Voit ilmoittautua vapaaehtoiseksi ja kertoa, että voisit ottaa vastaan oman alueesi tarroja ja auttaa jakamaan niitä. Otamme sinuun yhteyttä myöhemmin. Toimituksesta tai aikataulusta emme lupaa vielä mitään.</p></details>
      </div>
    </section>

    <section className="kv-sec kv-close"><p>Mielenosoitukset.fi löytyy sieltä, minne tieto ehtii. Auta viemään se perille.</p><a className="kv-btn kv-btn--primary" href="#vapaaehtoiseksi">Tule levittämään</a></section>
  </div>;
}
