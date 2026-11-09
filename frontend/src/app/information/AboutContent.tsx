export function AboutContent() {
  return <>
    <section className="public-prose-card">
      <h2>Mikä on Mielenosoitukset.fi?</h2>
      <p>Mielenosoitukset.fi on sivusto, joka kokoaa yhteen kaikki Suomessa järjestettävät mielenosoitukset ja yhteiskunnalliset tapahtumat. Tavoitteenamme on tarjota kattava ja ajankohtainen tietolähde, jossa voit seurata tulevia tapahtumia ja ilmoittaa omasta mielenosoituksestasi helposti ja nopeasti.</p>
      <p>Sivustomme toimii riippumattomana alustana, joka tarjoaa avoimen ja neutraalin paikan kaikille mielenosoituksille ja protesteille. Meidän tavoitteemme on auttaa löytämään tietoa, osallistumaan aktiivisesti yhteiskunnallisiin tapahtumiin ja edistämään vapaata mielipiteenilmaisua.</p>
      <p>Palvelu perustettiin vuonna 2024.</p>
      <div className="information-actions"><a className="button button-primary" href="/demonstrations">Selaa mielenosoituksia</a></div>
    </section>
    <section className="public-prose-card">
      <h2>Kuinka ilmoitan mielenosoituksesta?</h2>
      <p>Huomasitko, ettei jokin mielenosoitus vielä ole sivustolla? Voit ilmoittaa siitä itse! Täytä <a href="/submit">ilmoituslomake</a> ja varmista, että kaikki tiedot ovat oikein ja ajankohtaisia. Mielenosoitus näkyy sivustolla heti hyväksynnän jälkeen.</p>
      <h3>Voinko ilmoittaa jonkun muun kuin itseni järjestämän mielenosoituksen?</h3>
      <p>Totta kai! Kannustamme kaikkia ilmoittamaan mielenosoituksista, jotta sivusto pysyy mahdollisimman kattavana ja ajantasaisena.</p>
      <h3>Kauanko hyväksyntä kestää?</h3>
      <p>Hyväksyntä kestää yleensä noin yhdestä tunnista 48 tuntiin. Ethän huolestu, jos hyväksynnässä menee kauemmin. Mikäli ilmoitus tarvitsee käsitellä nopeasti, voit ottaa yhteyttä!</p>
      <div className="information-actions">
        <a className="button button-primary" href="/submit">Ilmoita tapahtuma</a>
        <a href="/ohjeet">Ohjeet järjestäjille</a>
      </div>
    </section>
    <section className="public-prose-card">
      <h2>Kuka ylläpitää sivustoa?</h2>
      <p>Mielenosoitukset.fi ylläpidetään riippumattomana projektina vapaaehtoisten toimesta. Emme ole sidoksissa mihinkään poliittiseen puolueeseen tai organisaatioon. Pyrimme tarjoamaan neutraalin alustan, joka tukee monimuotoista ja vapaata mielipiteenilmaisua kaikille.</p>
      <h3>Miten alusta rahoitetaan?</h3>
      <p>Mielenosoitukset.fi pyörii voittoa tavoittelemattomana ja riippumattomana projektina. Alustan infrakulut, kuten palvelinvuokrat ja verkkotunnus, rahoitetaan yksityishenkilöiden tuella.</p>
      <h3>Yksityisyys ja evästeet</h3>
      <p>Lisätietoa evästeiden käytöstä ja henkilötietojen käsittelystä löydät <a href="/privacy">tietosuojaselosteesta</a>.</p>
    </section>
    <section className="public-prose-card">
      <h2>Tule mukaan valtakunnalliseen kampanjaan!</h2>
      <p>Tule mukaan levittämään tietoa mielenosoitukset.fi:stä kaikkialle Suomeen. Rahoita kampanjaa, levitä markkinointimateriaaleja, tule vapaaehtoiseksi tai jaa tietoa sosiaalisessa mediassa.</p>
      <div className="information-actions">
        <a href="/kampanja/">Tutustu kampanjaan</a>
        <a href="/kampanja/#vapaaehtoiseksi">Tule vapaaehtoiseksi</a>
      </div>
    </section>
    <section className="public-prose-card">
      <h2>Yhteystiedot</h2>
      <p>Jos sinulla on kysyttävää tai ehdotuksia, voit ottaa yhteyttä ylläpitäjiin.</p>
      <div className="information-actions">
        <a href="mailto:tuki@mielenosoitukset.fi">tuki@mielenosoitukset.fi</a>
        <a href="/contact">Yhteydenottolomake</a>
      </div>
    </section>
  </>;
}
