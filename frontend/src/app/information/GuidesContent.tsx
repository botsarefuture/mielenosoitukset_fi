export function GuidesContent() {
  return (
    <div className="guide-page">
      <header className="guide-hero">
        <div className="guide-hero-content">
          <p className="guide-eyebrow"><i className="fas fa-book-open" aria-hidden="true" /> Ohjekeskus</p>
          <h1>Selkeät ohjeet kaikille järjestäjille</h1>
          <p className="guide-lead">
            Ilmoita tapahtuma onnistuneesti, valitse toimiva kuva ja löydä apu nopeasti.
            Aloita alta tai siirry suoraan tarvitsemaasi ohjeeseen.
          </p>
          <div className="guide-hero-actions">
            <a className="guide-button guide-button-primary" href="/submit">
              <i className="fas fa-bullhorn" aria-hidden="true" />
              Ilmoita mielenosoitus
            </a>
            <a className="guide-button guide-button-secondary" href="#submit-checklist">
              Katso tarkistuslista
              <i className="fas fa-arrow-down" aria-hidden="true" />
            </a>
          </div>
        </div>
        <div className="guide-hero-summary" aria-label="Ohjeen tärkeimmät vaiheet">
          <p className="guide-summary-title">Onnistunut ilmoitus kolmessa vaiheessa</p>
          <ol>
            <li><span>1</span><div><strong>Tarkista perustiedot</strong><small>Nimi, aika, paikka ja yhteystiedot</small></div></li>
            <li><span>2</span><div><strong>Lisää selkeä kuva</strong><small>Suositus vähintään 1200 × 675 px</small></div></li>
            <li><span>3</span><div><strong>Lähetä ja seuraa sähköpostia</strong><small>Otamme yhteyttä, jos tarvitsemme lisätietoja</small></div></li>
          </ol>
        </div>
      </header>

      <div className="guide-layout">
        <aside className="guide-sidebar">
          <nav className="guide-nav" aria-label="Ohjesivun sisällysluettelo">
            <p>Sisällys</p>
            <a href="#getting-started"><i className="fas fa-play-circle" aria-hidden="true" /> Aloita tästä</a>
            <a href="#submit-checklist"><i className="fas fa-check-circle" aria-hidden="true" /> Tarkistuslista</a>
            <a href="#submit-help"><i className="fas fa-life-ring" aria-hidden="true" /> Lähetys ei onnistu</a>
            <a href="#image-guide"><i className="fas fa-image" aria-hidden="true" /> Tapahtumakuva</a>
            <a href="#org-help"><i className="fas fa-users" aria-hidden="true" /> Organisaatiotilit</a>
            <a href="#faq"><i className="fas fa-question-circle" aria-hidden="true" /> Usein kysyttyä</a>
          </nav>
          <div className="guide-support-card">
            <i className="fas fa-headset" aria-hidden="true" />
            <strong>Tarvitsetko apua?</strong>
            <p>Kerro tapahtuman nimi, päivä ja paikkakunta, niin pääsemme nopeasti alkuun.</p>
            <a href="mailto:tuki@mielenosoitukset.fi">tuki@mielenosoitukset.fi</a>
          </div>
        </aside>

        <div className="guide-content">
          <section className="guide-section" id="getting-started">
            <div className="guide-section-heading">
              <span className="guide-section-number">01</span>
              <div>
                <p className="guide-kicker">Aloita tästä</p>
                <h2>Näin ilmoitat mielenosoituksen</h2>
                <p>Ilmoittaminen onnistuu ilman käyttäjätiliä. Varaa muutama minuutti ja pidä tapahtuman perustiedot valmiina.</p>
              </div>
            </div>

            <ol className="guide-steps">
              <li>
                <span className="guide-step-number">1</span>
                <div>
                  <h3>Avaa ilmoituslomake</h3>
                  <p>Siirry <a href="/submit">ilmoituslomakkeelle</a> ja täytä tapahtuman nimi, ajankohta sekä kokoontumispaikka.</p>
                </div>
              </li>
              <li>
                <span className="guide-step-number">2</span>
                <div>
                  <h3>Kerro olennaiset tiedot</h3>
                  <p>Kirjoita lyhyt kuvaus tavoitteesta ja käytännön järjestelyistä. Lisää toimiva sähköpostiosoite yhteydenottoja varten.</p>
                </div>
              </li>
              <li>
                <span className="guide-step-number">3</span>
                <div>
                  <h3>Lähetä ilmoitus</h3>
                  <p>Tarkista tiedot vielä kerran ja lähetä. Ylläpito käsittelee ilmoituksen, ja saat tarvittaessa lisäkysymykset sähköpostitse.</p>
                </div>
              </li>
            </ol>

            <div className="guide-note guide-note-blue">
              <i className="fas fa-info-circle" aria-hidden="true" />
              <div>
                <strong>Ilmoituksen ei tarvitse olla täydellinen.</strong>
                <p>Voit lähettää meille myöhemmin korjauksia tai lisätietoja. Tärkeintä on, että tapahtuman aika, paikka ja yhteystiedot ovat oikein.</p>
                <p>Jos tarvitset käännösapua, ota yhteyttä meihin: <a href="mailto:tuki@mielenosoitukset.fi">tuki@mielenosoitukset.fi</a>.</p>
              </div>
            </div>
          </section>

          <section className="guide-section" id="submit-checklist">
            <div className="guide-section-heading">
              <span className="guide-section-number">02</span>
              <div>
                <p className="guide-kicker">Ennen lähetystä</p>
                <h2>Nopea tarkistuslista</h2>
                <p>Käy nämä läpi ennen kuin painat lähetä. Näin ilmoitus voidaan käsitellä nopeammin.</p>
              </div>
            </div>

            <ul className="guide-checklist">
              <li><i className="fas fa-check" aria-hidden="true" /><div><strong>Selkeä nimi</strong><span>Nimestä ymmärtää heti, mistä tapahtumassa on kyse.</span></div></li>
              <li><i className="fas fa-check" aria-hidden="true" /><div><strong>Oikea päivä ja aika</strong><span>Päivämäärä, alkamisaika ja paikkakunta on tarkistettu.</span></div></li>
              <li><i className="fas fa-check" aria-hidden="true" /><div><strong>Tarkka kokoontumispaikka</strong><span>Osoite tai helposti tunnistettava kohta on ilmoitettu.</span></div></li>
              <li><i className="fas fa-check" aria-hidden="true" /><div><strong>Ytimekäs kuvaus</strong><span>Tavoite, kohderyhmä ja tärkeät käytännön tiedot löytyvät kuvauksesta.</span></div></li>
              <li><i className="fas fa-check" aria-hidden="true" /><div><strong>Toimiva sähköposti</strong><span>Ylläpito voi tavoittaa sinut, jos jokin tieto vaatii tarkennusta.</span></div></li>
              <li><i className="fas fa-check" aria-hidden="true" /><div><strong>Käyttökelpoinen kuva</strong><span>Kuva on riittävän suuri ja tärkeä sisältö on keskialueella.</span></div></li>
            </ul>
          </section>

          <section className="guide-section" id="submit-help">
            <div className="guide-section-heading">
              <span className="guide-section-number">03</span>
              <div>
                <p className="guide-kicker">Ongelmatilanteet</p>
                <h2>Jos ilmoituksen lähetys ei mene heti läpi</h2>
                <p>Useimmat lähetysongelmat ratkeavat tarkistamalla lomakkeen viestin ja yrittämällä rauhassa uudelleen.</p>
              </div>
            </div>

            <div className="guide-note guide-note-orange">
              <i className="fas fa-exclamation-triangle" aria-hidden="true" />
              <div>
                <strong>Samankaltaista tapahtumaa koskeva ilmoitus ei välttämättä tarkoita virhettä.</strong>
                <p>Tarkista viesti rauhassa ja yritä tarvittaessa uudelleen, jos olet varma, että kyseessä on eri tapahtuma.</p>
              </div>
            </div>

            <div className="guide-troubleshooting">
              <article>
                <span>1</span>
                <div><h3>Lue virheilmoitus loppuun</h3><p>Viesti kertoo yleensä, puuttuuko jokin tieto vai löytyikö mahdollinen päällekkäinen ilmoitus.</p></div>
              </article>
              <article>
                <span>2</span>
                <div><h3>Tarkista mahdollinen kaksoiskappale</h3><p>Vertaa nimeä, päivämäärää, kaupunkia ja osoitetta. Jos kyse on eri tapahtumasta, vahvista ja lähetä uudelleen.</p></div>
              </article>
              <article>
                <span>3</span>
                <div><h3>Yritä samalla selaimella uudelleen</h3><p>Odota hetki äläkä avaa samaa lomaketta moneen välilehteen yhtä aikaa.</p></div>
              </article>
              <article>
                <span>4</span>
                <div><h3>Tarkista sähköpostisi</h3><p>Katso saapuiko vahvistus ja varmista, ettei sähköpostiosoitteessa ole kirjoitusvirhettä.</p></div>
              </article>
            </div>

            <div className="guide-support-wide">
              <div>
                <p className="guide-kicker">Jos ongelma jatkuu</p>
                <h3>Lähetä meille nämä tiedot</h3>
                <p>Tapahtuman nimi, paikkakunta, päivämäärä ja mahdollinen virheilmoitus. Kuvakaappaus auttaa paljon.</p>
              </div>
              <a className="guide-button guide-button-primary" href="mailto:tuki@mielenosoitukset.fi">
                <i className="fas fa-envelope" aria-hidden="true" />
                Ota yhteyttä tukeen
              </a>
            </div>
          </section>

          <section className="guide-section" id="image-guide">
            <div className="guide-section-heading">
              <span className="guide-section-number">04</span>
              <div>
                <p className="guide-kicker">Kuvat</p>
                <h2>Toimiva tapahtumakuva</h2>
                <p>Hyvä vaakakuva näyttää terävältä tapahtumasivulla ja kestää rajauksen myös pienemmissä korteissa.</p>
              </div>
            </div>

            <div className="guide-image-spec" id="image-spec">
              <div className="guide-ratio-preview" aria-hidden="true">
                <div className="guide-safe-area">
                  <i className="fas fa-image" />
                  <strong>Pidä tärkeä sisältö tässä</strong>
                  <span>16:9</span>
                </div>
              </div>
              <div>
                <p className="guide-kicker">Suositus</p>
                <h3>Suositeltu koko: vähintään 1200 × 675 pikseliä</h3>
                <p>1600 × 900 tai suurempi toimii erinomaisesti. Alle 800 × 450 pikselin kuva ei yleensä riitä terävään koko sivun levyiseen esitykseen.</p>
                <ul className="guide-compact-list">
                  <li><i className="fas fa-check" aria-hidden="true" /> PNG, JPG ja WebP käyvät</li>
                  <li><i className="fas fa-check" aria-hidden="true" /> Jätä reunoille hieman tyhjää</li>
                  <li><i className="fas fa-check" aria-hidden="true" /> Käytä vähän tekstiä ja vahvaa kontrastia</li>
                </ul>
              </div>
            </div>

            <h3 className="guide-subheading" id="image-usage">Missä kuva näkyy?</h3>
            <div className="guide-feature-grid">
              <article><i className="fas fa-th-large" aria-hidden="true" /><h3>Etusivun kortit</h3><p>Oma tapahtumakuva näkyy ensisijaisesti korteissa. Kuvaa voidaan rajata kortin muotoon.</p></article>
              <article><i className="fas fa-mobile-alt" aria-hidden="true" /><h3>Mobiililista</h3><p>Pidä ihmiset, sanat ja logot keskialueella, jotta ne eivät jää rajauksen ulkopuolelle.</p></article>
              <article><i className="fas fa-window-maximize" aria-hidden="true" /><h3>Tapahtumasivu</h3><p>Kuva näkyy leveässä galleriassa. Hyvin pieniä kuvia ei venytetä sumeiksi.</p></article>
              <article><i className="fas fa-share-alt" aria-hidden="true" /><h3>Linkkien jaot</h3><p>Somepalvelut käyttävät yleensä erillistä automaattista esikatselukuvaa.</p></article>
            </div>

            <div className="guide-note guide-note-blue" id="auto-preview">
              <i className="fas fa-magic" aria-hidden="true" />
              <div>
                <strong>Jos et lisää omaa kuvaa, luomme automaattisen kuvan.</strong>
                <p>Siinä näkyvät tapahtuman nimi, sijainti, ajankohta ja tärkeimmät tunnisteet. Voit korvata sen myöhemmin omalla kansikuvalla.</p>
              </div>
            </div>
          </section>

          <section className="guide-section" id="org-help">
            <div className="guide-section-heading">
              <span className="guide-section-number">05</span>
              <div>
                <p className="guide-kicker">Järjestöt ja ryhmät</p>
                <h2>Organisaatiotilit</h2>
                <p>Järjestö, verkosto tai muu toimija voi saada oman profiilin ja hallita tapahtumia organisaation nimissä.</p>
              </div>
            </div>

            <div className="guide-org-grid">
              <div>
                <h3>Lähetä tukeen</h3>
                <ul className="guide-compact-list">
                  <li><i className="fas fa-check" aria-hidden="true" /> organisaation nimi</li>
                  <li><i className="fas fa-check" aria-hidden="true" /> virallinen sähköpostiosoite</li>
                  <li><i className="fas fa-check" aria-hidden="true" /> verkkosivu ja some-kanavat</li>
                  <li><i className="fas fa-check" aria-hidden="true" /> lyhyt kuvaus toiminnasta</li>
                  <li><i className="fas fa-check" aria-hidden="true" /> kutsuttavien henkilöiden nimet ja sähköpostit</li>
                </ul>
              </div>
              <div className="guide-org-process">
                <h3>Mitä tapahtuu seuraavaksi?</h3>
                <ol>
                  <li><span>1</span><p>Lähetät tiedot sähköpostitse.</p></li>
                  <li><span>2</span><p>Luomme profiilin ja lisäämme kutsut.</p></li>
                  <li><span>3</span><p>Saat sähköpostin, kun profiili on valmis.</p></li>
                </ol>
              </div>
            </div>
            <a className="guide-button guide-button-primary" href="mailto:tuki@mielenosoitukset.fi?subject=Organisaatiotili">
              <i className="fas fa-envelope" aria-hidden="true" />
              Pyydä organisaatiotiliä
            </a>
          </section>

          <section className="guide-section" id="faq">
            <div className="guide-section-heading">
              <span className="guide-section-number">06</span>
              <div>
                <p className="guide-kicker">Usein kysyttyä</p>
                <h2>Nopeat vastaukset</h2>
              </div>
            </div>

            <div className="guide-faq">
              <details>
                <summary>Kuva ei näy heti. Mitä teen?<i className="fas fa-plus" aria-hidden="true" /></summary>
                <p>Automaattinen kuva ilmestyy, kun tapahtuma hyväksytään. Jos kuva puuttuu vielä sen jälkeen, ota yhteyttä tukeen.</p>
              </details>
              <details>
                <summary>Voinko käyttää pystysuuntaista kuvaa?<i className="fas fa-plus" aria-hidden="true" /></summary>
                <p>Voit, mutta suosittelemme 16:9-vaakakuvaa. Pystykuvan reunoille voi jäädä tapahtumasivulla pehmennetty tausta, ja korteissa kuvaa voidaan rajata keskeltä.</p>
              </details>
              <details>
                <summary>Mikä on automaattinen esikatselukuva?<i className="fas fa-plus" aria-hidden="true" /></summary>
                <p>Se on tapahtuman tiedoista luotu erillinen automaattinen esikatselukuva, jota käytetään yleensä linkkien jaoissa ja Mastodonissa.</p>
              </details>
              <details>
                <summary>Mistä tiedän, menikö ilmoitus perille?<i className="fas fa-plus" aria-hidden="true" /></summary>
                <p>Tarkista sähköpostisi. Jos et saanut viestiä tai olet epävarma, lähetä tukeen tapahtuman nimi, päivämäärä ja paikkakunta.</p>
              </details>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
