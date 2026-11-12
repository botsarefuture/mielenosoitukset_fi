import { confirmationCopy } from '../data/campaign';

export interface ConfirmationPageProps {
  status: keyof typeof confirmationCopy;
  urls: { home: string; campaign: string };
}

export function ConfirmationPage({ status, urls }: ConfirmationPageProps) {
  const copy = confirmationCopy[status];
  const success = status === 'success';
  return <div className="campaign-page confirmation-page" lang="fi">
    <section className="campaign-confirmation" aria-labelledby="confirmation-title">
      <div className={`campaign-confirmation__symbol${success ? '' : ' campaign-confirmation__symbol--error'}`} aria-hidden="true">{success ? '✓' : '!'}</div>
      <h1 id="confirmation-title">{copy.title}</h1>
      <p className="campaign-confirmation__lead">{copy.description}</p>
      <p>{copy.detail}</p>
      <div className="campaign-actions">
        <a className="campaign-button campaign-button--primary" href={urls.campaign}>Palaa kampanjasivulle</a>
        <a className="campaign-text-link" href={urls.home}>Etusivulle</a>
      </div>
      {!success && <a className="campaign-confirmation__contact" href="mailto:tuki@mielenosoitukset.fi">tuki@mielenosoitukset.fi</a>}
    </section>
  </div>;
}
