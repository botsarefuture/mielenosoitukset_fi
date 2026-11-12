import { cancelLinkErrors, cancelLinkLead, cancelLinkTitle, type CancelLinkState } from './cancel-link';
import './information/information.css';
import './suggest-change/suggest-change.css';

const notice = (kind: 'error' | 'warning' | 'info', children: React.ReactNode) =>
  <div className={`flash-message flash-message--inline flash-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
    <span className="flash-text">{children}</span>
  </div>;

export default function CancelLinkScreen({ link, token }: { link: CancelLinkState; token: string }) {
  return <article className="public-page-shell information-page suggest-change-page" aria-labelledby="cancel-link-title">
    <header className="public-page-header"><div className="public-page-header__content">
      <h1 className="public-page-header__title" id="cancel-link-title">{cancelLinkTitle}</h1>
    </div></header>
    {link.state !== 'ready' ? <>
      {notice('error', cancelLinkErrors[link.state])}
      <div className="detail-actions"><a className="detail-button" href="/demonstrations">Kaikki mielenosoitukset</a></div>
    </> : <>
      <section className="public-prose-card suggest-change-summary">
        <h2>{link.demo.title}</h2>
        <p><strong>Päivämäärä:</strong> {link.demo.date}</p>
        <p><strong>Kaupunki:</strong> {link.demo.city}</p>
        <p>{cancelLinkLead}</p>
      </section>
      {link.demo.cancelled ? notice('warning', 'Mielenosoitus on jo merkitty perutuksi.')
        : link.cancellationPending ? notice('info', <>Peruutuspyyntö on jo lähetetty ylläpidolle. Peruminen tulee voimaan vasta hyväksynnän jälkeen.</>)
        : <>
          {link.canCancelDirectly
            ? notice('warning', <><strong>Tämä on virallinen järjestäjälinkki.</strong> Koska yhteystieto kuuluu Mielenosoitukset.fi:ssä vahvistetulle organisaatiolle, tällä linkillä tehty peruminen tulee voimaan heti. Vahvista, että haluat perua mielenosoituksen heti.</>)
            : notice('info', <><strong>Tämä linkki lähettää pyynnön ylläpidolle.</strong> Mielenosoitus ei peruunnu vielä tämän lomakkeen lähettämisellä, vaan vasta jos Mielenosoitukset.fi:n ylläpito hyväksyy pyynnön. Demo näkyy normaalisti siihen asti.</>)}
          <form method="post" action={`/cancel_demonstration/${token}`} className="public-prose-card suggest-change-form">
            <div className="suggest-change-field">
              <label htmlFor="reason">Perumisen syy (valinnainen)</label>
              <textarea id="reason" name="reason" rows={3} placeholder="Kerro lyhyesti miksi mielenosoitus perutaan..." />
            </div>
            <div className="detail-actions">
              <button type="submit" className={`detail-button ${link.canCancelDirectly ? 'detail-button--danger' : 'detail-button--primary'}`}>
                {link.canCancelDirectly ? 'Peruuta mielenosoitus' : 'Lähetä peruutuspyyntö'}
              </button>
            </div>
          </form>
        </>}
    </>}
  </article>;
}
