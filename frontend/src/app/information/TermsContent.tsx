/** Published Finnish terms. Preserve section IDs for existing links. */
export function TermsContent() {
  return <>
    <section className="public-prose-card" aria-labelledby="terms-general">
      <h2 id="terms-general">Yleiset ehdot</h2>
      <p>
        Kaikkien sivustolla julkaistavien mielenosoitusten on oltava Suomen lakien ja asetusten mukaisia. Sivustollemme ilmoitetut mielenosoitukset eivät saa sisältää syrjintää, vihapuhetta, väkivaltaan yllyttämistä tai muuta epäasiallista sisältöä.
      </p>
      <p>
        Pidätämme oikeuden olla julkaisematta sivustollemme ilmoitettua mielenosoitusta ilman erillistä perustelua, mikäli katsomme, että se ei täytä edellä mainittuja ehtoja tai muita sivuston periaatteita.
      </p>
      <p>
        Sivustomme tietoja ja sisältöjä ei saa käyttää kaupallisiin tarkoituksiin ilman erillistä kirjallista lupaa.
      </p>
    </section>

    <section className="public-prose-card" aria-labelledby="terms-appeal">
      <h2 id="terms-appeal">Valitusprosessi</h2>
      <p>
        Jos mielenosoitustasi ei julkaista ja koet päätöksen olevan virheellinen, voit tehdä asiasta valituksen seuraavan prosessin mukaisesti:
      </p>
      <ol>
        <li>
          Lähetä valituksesi sähköpostilla osoitteeseen{' '}
          <a href="mailto:hallinto@mielenosoitukset.fi">hallinto@mielenosoitukset.fi</a>.
        </li>
        <li>Käsittelemme valituksesi 30 vuorokauden kuluessa sen vastaanottamisesta.</li>
        <li>Saat valituksestasi kirjallisen lopullisen päätöksen sähköpostilla. Tähän päätökseen ei voi hakea muutosta.</li>
      </ol>
    </section>

    <section className="public-prose-card" aria-labelledby="terms-liability">
      <h2 id="terms-liability">Vastuunrajoitus</h2>
      <p>
        Emme vastaa sivustolla olevien tietojen mahdollisista virheistä tai puutteista emmekä mahdollisista vahingoista, joita virheellisistä tiedoista saattaa aiheutua. Emme myöskään vastaa mahdollisista teknisistä häiriöistä, käyttökatkoista tai muista palvelun toimintahäiriöistä johtuvista ongelmista.
      </p>
    </section>

    <section className="public-prose-card" aria-labelledby="terms-changes">
      <h2 id="terms-changes">Muutokset käyttöehtoihin</h2>
      <p>
        Pidätämme oikeuden päivittää näitä käyttöehtoja tarvittaessa. Käyttäjien vastuulla on tutustua käyttöehtoihin säännöllisesti. Olennaisista muutoksista ilmoitamme selkeästi sivustollamme.
      </p>
      <p><strong>Käyttämällä sivustoamme hyväksyt nämä ehdot.</strong></p>
    </section>
  </>;
}
