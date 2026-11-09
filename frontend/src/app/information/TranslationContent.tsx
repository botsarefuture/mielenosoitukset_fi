import { informationPages } from '../information';
import type { SessionSummary } from '../session';

const email = 'kaannoshanke@mielenosoitukset.fi';

export function TranslationContent({ session }: { session: SessionSummary }) {
  const join = session.translationJoin;
  const loginUrl = '/users/auth/login?next=' + encodeURIComponent(informationPages.translations.path);
  return <>
    <section className="public-prose-card">
      <h2>Auta meitä tekemään sivustosta monikielinen!</h2>
      <p>Ensimmäisessä vaiheessa käännämme sivuston käyttöliittymän, ohjetekstit ja muut staattiset sisällöt. Tämän jälkeen toteutetaan järjestelmä, jonka avulla myös käyttäjien ilmoittamat mielenosoitukset ja tapahtumat voidaan kääntää useille kielille.</p>
      <p>Tämä työ tehdään yhdessä vapaaehtoisten kanssa. Tule mukaan!</p>
      <div className="information-actions">
        {join?.joined ? <strong>Olet mukana käännöstyössä</strong>
          : session.authenticated && join?.csrfToken ? <form method="post" action="/upcoming/translations/join">
              <input type="hidden" name="csrf_token" value={join.csrfToken} />
              <button type="submit" className="button button-primary">Liity kääntäjäksi</button>
            </form>
          : session.authenticated ? <a href={informationPages.translations.path}>Lataa sivu uudelleen liittyäksesi</a>
          : <a href={loginUrl} className="button button-primary">Kirjaudu sisään liittyäksesi</a>}
      </div>
    </section>
    <section className="public-prose-card">
      <h2>Mistä käännöshankkeessa on kyse?</h2>
      <p>Käännöshankkeen tavoitteena on tuoda Mielenosoitukset.fi täysin monikieliseksi sivustoksi. Tällä hetkellä keskitymme kääntämään käyttöliittymän, napit, ohjeet ja muun yleisen sisällön.</p>
      <p>Kun tämä vaihe on valmis, seuraava askel on rakentaa käännösjärjestelmä mielenosoitusten ja tapahtumien tiedoille. Näin myös ulkomaalaiset ja monikieliset yhteisöt voivat ilmoittaa ja löytää mielenosoituksia omalla kielellään.</p>
    </section>
    <section className="public-prose-card">
      <h2>Käännöshanketyöryhmä</h2>
      <p>Käännöstyötä koordinoi vapaaehtoisista koostuva käännöshanketyöryhmä, joka kokoontuu säännöllisesti suunnittelemaan ja edistämään hanketta. Työryhmään voi liittyä kuka tahansa, joka haluaa osallistua monikielisen yhteiskunnan rakentamiseen.</p>
      <h3>Tekninen toteutus</h3>
      <p>Sivuston käännösjärjestelmä on jo rakennettu. Kaikki tekstit voidaan näyttää automaattisesti eri kielillä, kun käännökset on lisätty. Seuraavaksi kehitämme tavan, jolla myös käyttäjien ilmoittamat mielenosoitusten tiedot voidaan kääntää turvallisesti ja luotettavasti.</p>
      <h3>Miten voin auttaa?</h3>
      <p>Voit auttaa osallistumalla käännöstyöhön, tarjoamalla oikolukua, tai auttamalla testauksessa. Myös kehittäjät, kieliaktivistit ja opiskelijat ovat lämpimästi tervetulleita mukaan!</p>
      <p>Ota yhteyttä osoitteessa <a href={`mailto:${email}`}>{email}</a>.</p>
    </section>
  </>;
}
