const facts = [
  { icon: 'fa-calendar-check', value: '2024', label: 'Perustettu' },
  { icon: 'fa-scale-balanced', value: 'Riippumaton', label: 'Ei sidoksissa puolueisiin tai järjestöihin' },
  { icon: 'fa-hand-holding-heart', value: 'Vapaaehtoisvoimin', label: 'Voittoa tavoittelematon' },
];

/** `campaign` is true when the campaign page is public or the visitor can preview it. */
export function AboutContent({ campaign = false }: { campaign?: boolean }) {
  return <>
    <dl className="about-facts">
      {facts.map(fact => <div key={fact.value} className="about-fact">
        <i className={`fa-solid ${fact.icon}`} aria-hidden="true" />
        <dt>{fact.label}</dt>
        <dd>{fact.value}</dd>
      </div>)}
    </dl>

    {campaign && <section className="about-campaign" aria-labelledby="about-campaign-title">
      <i className="fa-solid fa-bullhorn about-campaign__icon" aria-hidden="true" />
      <div>
        <h2 id="about-campaign-title">Tule mukaan valtakunnalliseen kampanjaan</h2>
        <p>Tule mukaan levittämään tietoa mielenosoitukset.fi:stä kaikkialle Suomeen. Rahoita kampanjaa, levitä markkinointimateriaaleja, tule vapaaehtoiseksi tai jaa tietoa sosiaalisessa mediassa.</p>
        <div className="detail-actions">
          <a className="detail-button detail-button--primary" href="/kampanja/">Tutustu kampanjaan</a>
          <a className="detail-button" href="/kampanja/#vapaaehtoiseksi">Tule vapaaehtoiseksi</a>
        </div>
      </div>
    </section>}

    <div className="about-grid">
      <div className="about-main">
        <section className="public-prose-card" aria-labelledby="about-what-title">
          <h2 id="about-what-title">Mikä on Mielenosoitukset.fi?</h2>
          <p>Mielenosoitukset.fi on sivusto, joka kokoaa yhteen kaikki Suomessa järjestettävät mielenosoitukset ja yhteiskunnalliset tapahtumat. Tavoitteenamme on tarjota kattava ja ajankohtainen tietolähde, jossa voit seurata tulevia tapahtumia ja ilmoittaa omasta mielenosoituksestasi helposti ja nopeasti.</p>
          <p>Sivustomme toimii riippumattomana alustana, joka tarjoaa avoimen ja neutraalin paikan kaikille mielenosoituksille ja protesteille. Meidän tavoitteemme on auttaa löytämään tietoa, osallistumaan aktiivisesti yhteiskunnallisiin tapahtumiin ja edistämään vapaata mielipiteenilmaisua.</p>
          <div className="detail-actions"><a className="detail-button detail-button--primary" href="/demonstrations">Selaa mielenosoituksia</a></div>
        </section>
        <section className="public-prose-card" aria-labelledby="about-submit-title">
          <h2 id="about-submit-title">Kuinka ilmoitan mielenosoituksesta?</h2>
          <p>Huomasitko, ettei jokin mielenosoitus vielä ole sivustolla? Voit ilmoittaa siitä itse. Täytä <a href="/submit">ilmoituslomake</a> ja varmista, että kaikki tiedot ovat oikein ja ajankohtaisia. Mielenosoitus näkyy sivustolla heti hyväksynnän jälkeen.</p>
          <div className="about-questions">
            <div>
              <h3>Voinko ilmoittaa jonkun muun kuin itseni järjestämän mielenosoituksen?</h3>
              <p>Totta kai! Kannustamme kaikkia ilmoittamaan mielenosoituksista, jotta sivusto pysyy mahdollisimman kattavana ja ajantasaisena.</p>
            </div>
            <div>
              <h3>Kauanko hyväksyntä kestää?</h3>
              <p>Hyväksyntä kestää yleensä noin yhdestä tunnista 48 tuntiin. Ethän huolestu, jos hyväksynnässä menee kauemmin. Mikäli ilmoitus tarvitsee käsitellä nopeasti, voit ottaa yhteyttä!</p>
            </div>
          </div>
          <div className="detail-actions">
            <a className="detail-button detail-button--primary" href="/submit">Ilmoita tapahtuma</a>
            <a className="detail-button" href="/ohjeet">Ohjeet järjestäjille</a>
          </div>
        </section>
      </div>

      <aside className="about-side" aria-label="Ylläpito ja yhteystiedot">
        <section className="public-prose-card" aria-labelledby="about-who-title">
          <h2 id="about-who-title">Kuka ylläpitää sivustoa?</h2>
          <p>Mielenosoitukset.fi ylläpidetään riippumattomana projektina vapaaehtoisten toimesta. Emme ole sidoksissa mihinkään poliittiseen puolueeseen tai organisaatioon. Pyrimme tarjoamaan neutraalin alustan, joka tukee monimuotoista ja vapaata mielipiteenilmaisua kaikille.</p>
          <h3>Miten alusta rahoitetaan?</h3>
          <p>Mielenosoitukset.fi pyörii voittoa tavoittelemattomana ja riippumattomana projektina. Alustan infrakulut, kuten palvelinvuokrat ja verkkotunnus, rahoitetaan yksityishenkilöiden tuella.</p>
          <h3>Yksityisyys ja evästeet</h3>
          <p>Lisätietoa evästeiden käytöstä ja henkilötietojen käsittelystä löydät <a href="/privacy">tietosuojaselosteesta</a>.</p>
        </section>
        <section className="public-prose-card" aria-labelledby="about-contact-title">
          <h2 id="about-contact-title">Yhteystiedot</h2>
          <p>Jos sinulla on kysyttävää tai ehdotuksia, voit ottaa yhteyttä ylläpitäjiin.</p>
          <div className="contact-options contact-options--stacked">
            <a className="contact-option" href="mailto:tuki@mielenosoitukset.fi">
              <i className="fa-solid fa-envelope" aria-hidden="true" />
              <span><strong>Sähköposti</strong>tuki@mielenosoitukset.fi</span>
            </a>
            <a className="contact-option" href="/contact">
              <i className="fa-solid fa-comment" aria-hidden="true" />
              <span><strong>Yhteydenottolomake</strong>Lähetä viesti suoraan</span>
            </a>
          </div>
        </section>
      </aside>
    </div>
  </>;
}
