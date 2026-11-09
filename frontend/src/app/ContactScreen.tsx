import { contactCopy, contactPath } from './contact-route';
import type { SessionSummary } from './session';
import './information/information.css';
import './contact/contact.css';

const supportEmail = 'tuki@mielenosoitukset.fi';
const subjects = [['Tuki', 'Tukipyyntö'], ['Yleinen kysymys', 'Yleinen kysymys'], ['Palautetta', 'Palautetta'], ['Muu', 'Muu']];

/** The contact page. The form posts to Flask, which validates the one-time token and sends the message. */
export default function ContactScreen({ session }: { session: SessionSummary }) {
  const form = session.contactForm;
  const limits = form?.limits ?? { nameMax: 120, emailMax: 254, messageMin: 10, messageMax: 5000 };
  return <article className="public-page-shell information-page contact-page" aria-labelledby="contact-title">
    <header className="public-page-header">
      <div className="public-page-header__content">
        <h1 className="public-page-header__title" id="contact-title">{contactCopy.title}</h1>
        <p className="public-page-header__description">{contactCopy.description}</p>
      </div>
    </header>
    <div className="public-content-stack">
      {form?.messages.map(({ category, message }, index) =>
        <div key={index} className={`flash-message flash-message--inline flash-${category}`}
          role={category === 'error' || category === 'danger' ? 'alert' : 'status'}>
          <span className="flash-text">{message}</span>
        </div>)}

      <section className="public-prose-card" aria-labelledby="contact-options-title">
        <h2 id="contact-options-title">Yhteystiedot</h2>
        <p>Jos sinulla on kysyttävää, ehdotuksia tai haluat ottaa yhteyttä ylläpitäjiin, voit käyttää alla olevia yhteystapoja:</p>
        <div className="contact-options">
          <a className="contact-option" href={`mailto:${supportEmail}`}>
            <i className="fa-solid fa-envelope" aria-hidden="true" />
            <span><strong>Sähköposti</strong>{supportEmail}</span>
          </a>
          <a className="contact-option" href="#contact-form-section">
            <i className="fa-solid fa-comment" aria-hidden="true" />
            <span><strong>Yhteydenottolomake</strong>Lähetä viesti suoraan</span>
          </a>
        </div>
      </section>

      <section id="contact-form-section" className="public-prose-card" aria-labelledby="contact-form-title">
        <h2 id="contact-form-title">Ota yhteyttä lomakkeen kautta</h2>
        {form?.enabled && form.csrfToken ? <>
          <p>Täytä alla oleva lomake ja lähetä, niin olemme sinuun yhteydessä!</p>
          <form id="contact-form" className="contact-form" action={contactPath} method="post">
            <input type="hidden" name="csrf_token" value={form.csrfToken} />
            <div hidden aria-hidden="true">
              <label htmlFor="website">Verkkosivusto</label>
              <input type="text" id="website" name="website" tabIndex={-1} autoComplete="off" />
            </div>
            <label htmlFor="name">Nimi</label>
            <input type="text" id="name" name="name" required maxLength={limits.nameMax} autoComplete="name" placeholder="Kirjoita nimesi" />
            <label htmlFor="email">Sähköposti</label>
            <input type="email" id="email" name="email" required maxLength={limits.emailMax} autoComplete="email" placeholder="Kirjoita sähköpostisi" />
            <label htmlFor="subject">Aihe</label>
            <select id="subject" name="subject" required defaultValue="">
              <option value="" disabled>Valitse aihe</option>
              {subjects.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <label htmlFor="message">Viesti</label>
            <textarea id="message" name="message" rows={6} required minLength={limits.messageMin} maxLength={limits.messageMax}
              placeholder="Kirjoita viestisi tähän" />
            <button type="submit" className="button button-primary">Lähetä</button>
          </form>
        </> : <p className="contact-unavailable">{form && !form.enabled
          ? 'Yhteydenottolomake on tilapäisesti poissa käytöstä. Voit lähettää sähköpostia tukeen: '
          : 'Lomaketta ei voitu ladata. Voit lähettää sähköpostia tukeen: '}
          <a href={`mailto:${supportEmail}`}>{supportEmail}</a></p>}
      </section>
    </div>
  </article>;
}
