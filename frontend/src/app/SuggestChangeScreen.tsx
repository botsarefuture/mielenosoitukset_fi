import { useEffect, useRef, useState } from 'react';
import { suggestionLead, suggestionTitle, type SuggestionDemo } from './suggest-change';
import ListEditor from './suggest-change/ListEditor';
import MarkdownPreview from './suggest-change/MarkdownPreview';
import './information/information.css';
import './suggest-change/suggest-change.css';

export default function SuggestChangeScreen({ demo }: { demo: SuggestionDemo }) {
  const [description, setDescription] = useState(demo.fields.description_markdown);
  const [notices, setNotices] = useState<{ category: string; message: string }[]>([]);
  useEffect(() => {
    // Flask redirects back here with a flashed error when a submission is empty or fails.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    void fetch('/get_flash_messages', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      headers: { Accept: 'application/json' } }).then(async response => {
      if (!response.ok) return;
      const value = await response.json() as { messages?: unknown };
      if (!Array.isArray(value.messages)) return;
      setNotices(value.messages.filter((item): item is { category?: unknown; message: string } => !!item
        && typeof item === 'object' && typeof (item as { message?: unknown }).message === 'string')
        .slice(0, 5).map(item => ({
          category: typeof item.category === 'string' && ['success', 'error', 'warning', 'info'].includes(item.category) ? item.category : 'info',
          message: item.message,
        })));
    }).catch(() => {}).finally(() => clearTimeout(timer));
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const displayDate = /^\d{4}-\d{2}-\d{2}$/.test(demo.fields.date)
    ? demo.fields.date.split('-').reverse().map(Number).join('.') : demo.fields.date;
  const displayTime = [demo.fields.start_time, demo.fields.end_time].filter(Boolean)
    .map(time => time.replace(/^(\d{1,2}):(\d{2})(?::\d{2})?$/, '$1.$2')).join('–');
  const format = (prefix: string, suffix = '', template = '') => {
    const field = textarea.current;
    if (!field) return;
    const selected = field.value.slice(field.selectionStart, field.selectionEnd);
    field.setRangeText(template || (prefix === '- ' || prefix === '> ' ? (selected || field.value.slice(field.selectionStart)).split('\n').map(line => prefix + line).join('\n') : prefix + selected + suffix),
      field.selectionStart, (prefix === '- ' || prefix === '> ') && !selected ? field.value.length : field.selectionEnd, 'end');
    setDescription(field.value);
    field.focus();
  };
  const input = (name: keyof SuggestionDemo['fields'], label: string, help?: string, placeholder?: string) =>
    <div className="suggest-change-field"><label htmlFor={name}>{label}</label>
      <input id={name} name={name} type="text" defaultValue={demo.fields[name]} placeholder={placeholder} aria-describedby={help ? `${name}-help` : undefined} />
      {help && <p className="suggest-change-help" id={`${name}-help`}>{help}</p>}
    </div>;
  return <article className="public-page-shell information-page suggest-change-page" aria-labelledby="suggest-change-title">
    <header className="public-page-header"><div className="public-page-header__content">
      <h1 className="public-page-header__title" id="suggest-change-title">{suggestionTitle}</h1>
      <p className="public-page-header__description">{suggestionLead}</p>
    </div></header>
    {notices.map((notice, index) => <div key={index} className={`flash-message flash-message--inline flash-${notice.category}`}
      role={notice.category === 'error' ? 'alert' : 'status'}><span className="flash-text">{notice.message}</span></div>)}
    <section className="public-prose-card suggest-change-summary">
      <h2>Mielenosoitus, jota olet päivittämässä</h2><p>{demo.fields.title}</p>
      <p>{[displayDate, displayTime, demo.fields.city].filter(Boolean).join(' · ')}</p>
      <p>Ylläpito käy ehdotuksen läpi ennen kuin muutos näkyy kaikille.</p>
    </section>
    <form method="post" action={`/suggest_change/${demo.id}`} id="suggestForm" className="public-prose-card suggest-change-form">
      <fieldset><legend>Perustiedot</legend><p>Tarkista otsikko, päivä ja kellonajat.</p>
        <div className="suggest-change-grid">
          {input('title', 'Otsikko', 'Esimerkiksi tapahtuman virallinen nimi.')}
          {input('date', 'Päivämäärä', 'Muoto: vvvv-kk-pp', 'vvvv-kk-pp')}
          {input('start_time', 'Alkamisaika', 'Esimerkiksi 14:00', '14:00')}
          {input('end_time', 'Päättymisaika', 'Valinnainen, jos tapahtuman loppuaika tiedetään.', '15:30')}
        </div>
      </fieldset>
      <fieldset><legend>Paikka ja linkit</legend><p>Kerro, missä tapahtuma järjestetään ja mistä löytyy lisätietoa.</p>
        <div className="suggest-change-grid">
          {input('city', 'Kaupunki')}{input('address', 'Osoite', 'Voit kirjoittaa esimerkiksi torin, puiston tai kokoontumispaikan osoitteen.')}
          {input('facebook', 'Facebook-tapahtuman URL', 'Valinnainen linkki tapahtumasivulle tai lisätietoihin.', 'https://facebook.com/events/...')}
        </div>
      </fieldset>
      <fieldset><legend>Reitti ja aihetunnisteet</legend>
        <ListEditor name="route" label="Reitti (marsseille)" initial={demo.fields.route} placeholder="Kirjoita reittipiste ja paina Enter"
          help="Lisää marssin pysähdykset tai kadut oikeassa järjestyksessä. Sama katu voi esiintyä useamman kerran." />
        <ListEditor name="tags" label="Aihetunnisteet" initial={demo.fields.tags} placeholder="Kirjoita tagi ja paina Enter"
          help="Kirjoita tagit ilman #-merkkiä. Jos lisäät sen, poistamme sen automaattisesti." />
      </fieldset>
      <fieldset><legend>Järjestäjät</legend><p>Kerro, kuka tai ketkä mielenosoituksen järjestävät.</p>
        {demo.organizersCurrent !== undefined && <p className="suggest-change-current"><strong>Nykyiset järjestäjät:</strong> {demo.organizersCurrent}</p>}
        <ListEditor name="organizers" label="Järjestäjät" initial={demo.fields.organizers} placeholder="Kirjoita järjestäjä ja paina Enter"
          help="Kirjoita järjestäjän nimi. Halutessasi lisää sähköposti tai kotisivu sulkuihin: Yhdistys (yhdistys@example.fi, https://yhdistys.fi)." />
      </fieldset>
      <fieldset><legend>Kuvaus</legend><p>Kirjoita tavallisena tekstinä. HTML-koodia ei tarvitse eikä pidä käyttää.</p>
        <div className="suggest-change-field"><label htmlFor="description-markdown">Kuvausteksti</label>
          <div className="detail-actions suggest-change-toolbar" role="group" aria-label="Kuvausteksti">
            <button className="detail-button" type="button" onClick={() => format('**', '**')}>Lihavointi</button>
            <button className="detail-button" type="button" onClick={() => format('*', '*')}>Kursiivi</button>
            <button className="detail-button" type="button" onClick={() => format('- ')}>Lista</button>
            <button className="detail-button" type="button" onClick={() => format('> ')}>Nosto</button>
            <button className="detail-button" type="button" onClick={() => format('', '', '[linkin teksti](https://example.com)')}>Linkki</button>
          </div>
          <textarea ref={textarea} id="description-markdown" name="description_markdown" rows={10} value={description}
            placeholder="Kerro esimerkiksi, kenelle tapahtuma on tarkoitettu, mikä on teema, mistä kulkue lähtee ja mitä osallistujien kannattaa tietää."
            onChange={event => setDescription(event.target.value)} aria-describedby="description-help" />
          <p id="description-help" className="suggest-change-help">Voit kirjoittaa pelkkää tavallista tekstiä. Halutessasi voit käyttää myös yksinkertaista muotoilua, kuten **lihavointia**, listoja ja linkkejä.</p>
        </div>
        <MarkdownPreview value={description} />
      </fieldset>
      <fieldset><legend>Viesti ylläpidolle</legend><p>Tähän voit kertoa taustatietoa muutoksesta.</p>
        <div className="suggest-change-field"><label htmlFor="reporter_comment">Miksi tämä muutos olisi hyvä tehdä?</label>
          <textarea id="reporter_comment" name="reporter_comment" rows={4} placeholder="Esimerkiksi: aika on muuttunut, osoite tarkentui tai kuvaus kaipaa lisätietoja." aria-describedby="comment-help" />
          <p id="comment-help" className="suggest-change-help">Valinnainen, mutta usein hyödyllinen ylläpidolle.</p>
        </div>
      </fieldset>
      <fieldset><legend>Yhteystiedot</legend><p>Voit jättää sähköpostiosoitteesi, jos haluat, että voimme kysyä tarkennuksia.</p>
        <div className="suggest-change-field"><label htmlFor="reporter_email">Sähköpostiosoitteesi</label>
          <input type="email" id="reporter_email" name="reporter_email" placeholder="email@example.com" aria-describedby="email-help" />
          <p id="email-help" className="suggest-change-help">Valinnainen. Käytämme tätä vain ehdotukseen liittyvään viestintään.</p>
        </div>
      </fieldset>
      <div className="detail-actions suggest-change-actions">
        <button className="detail-button detail-button--primary" type="submit">Lähetä ehdotus</button>
        <button className="detail-button detail-button--danger" type="submit" form="suggest-change-cancel" formNoValidate>Peruuta</button>
      </div>
    </form>
    <form id="suggest-change-cancel" method="get" action={`/demonstration/${demo.id}`} />
  </article>;
}
