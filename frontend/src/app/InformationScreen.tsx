import { informationPages } from './information';
import type { InformationPage } from './information';
import type { SessionSummary } from './session';
import { AboutContent } from './information/AboutContent';
import { GuidesContent } from './information/GuidesContent';
import { PrivacyContent } from './information/PrivacyContent';
import { TermsContent } from './information/TermsContent';
import { TranslationContent } from './information/TranslationContent';
import './information/information.css';

const documentDates = {
  privacy: { iso: '2026-06-09', label: '9.6.2026' },
  terms: { iso: '2025-10-12', label: '12.10.2025' },
};

export default function InformationScreen({ page, session }: { page: InformationPage; session: SessionSummary }) {
  if (page === 'guides') return <GuidesContent />;
  const { title, description } = informationPages[page];
  const date = page === 'privacy' || page === 'terms' ? documentDates[page] : null;
  const titleId = page === 'terms' ? 'terms-title' : 'information-title';
  return <article className="public-page-shell information-page" aria-labelledby={titleId}>
    <header className="public-page-header">
      <div className="public-page-header__content">
        <h1 className="public-page-header__title" id={titleId}>{title}</h1>
        <p className="public-page-header__description">{description}</p>
      </div>
      {date && <div className="public-page-header__meta">
        <span>Päivitetty <time dateTime={date.iso}>{date.label}</time></span>
      </div>}
    </header>
    <div className="public-content-stack">
      {page === 'translations' && session.translationJoin?.messages.map(({ category, message }, index) =>
        <div key={index} className={`flash-message flash-message--inline flash-${category}`}
          role={category === 'error' || category === 'danger' ? 'alert' : 'status'}>
          <span className="flash-text">{message}</span>
        </div>)}
      {page === 'info' && <AboutContent />}
      {page === 'privacy' && <PrivacyContent />}
      {page === 'terms' && <TermsContent />}
      {page === 'translations' && <TranslationContent session={session} />}
    </div>
  </article>;
}
