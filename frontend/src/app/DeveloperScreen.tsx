import { useEffect, useState } from 'react';
import type { AppConfig } from './config';
import type { SessionSummary } from './session';
import { useSession } from './useSession';
import {
  developerAccessRequestPath, developerAppApi, developerAppsPath, developerCopy as copy, developerOverviewApi,
  developerPath, formatDeveloperDate, readDeveloper,
} from './developer-route';
import type { DeveloperRead, DeveloperToken } from './developer-route';
import './information/information.css';
import './suggest-change/suggest-change.css';
import './developer/developer.css';

type Load = { state: 'loading' } | { state: 'anonymous' } | { state: 'unavailable' } | { state: 'not-found' }
  | { state: 'ready'; data: DeveloperRead };

const notice = (kind: 'error' | 'info', children: React.ReactNode) =>
  <div className={`flash-message flash-message--inline flash-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
    <span className="flash-text">{children}</span>
  </div>;

function Tokens({ tokens, empty }: { tokens: DeveloperToken[]; empty: string }) {
  if (!tokens.length) return <p className="developer-muted">{empty}</p>;
  return <ul className="developer-list">
    {tokens.map(token => <li key={token.id || `${token.type}-${token.expiresAt}`}>
      <strong>{token.type}</strong> — {token.scopes.join(', ') || 'read'}
      <div className="developer-muted">{copy.validUntil} {formatDeveloperDate(token.expiresAt)}</div>
    </li>)}
  </ul>;
}

function Locked() {
  return <section className="public-prose-card developer-card">
    <h2>{copy.lockedTitle}</h2>
    <p>{copy.lockedLead}</p>
    <form method="post" action={developerAccessRequestPath} className="suggest-change-form">
      <div className="suggest-change-field">
        <label htmlFor="developer-reason">{copy.reason}</label>
        <textarea id="developer-reason" name="reason" rows={3} required placeholder={copy.reasonPlaceholder} />
      </div>
      <div className="detail-actions">
        <button type="submit" className="detail-button detail-button--primary">{copy.send}</button>
        <a className="detail-button" href={copy.settingsUrl}>{copy.settings}</a>
      </div>
    </form>
  </section>;
}

function Overview({ data }: { data: Extract<DeveloperRead, { status: 'overview' }> }) {
  return <div className="developer-grid">
    <section className="public-prose-card developer-card" aria-labelledby="developer-apps">
      <h2 id="developer-apps">{copy.appsHeading}</h2>
      {data.apps.length ? <ul className="developer-list">
        {data.apps.map(app => <li key={app.id}>
          <a href={`${developerPath}/apps/${app.id}`}><strong>{app.name}</strong></a>
          <div className="developer-muted">Client ID: <code>{app.clientId}</code></div>
        </li>)}
      </ul> : <p className="developer-muted">{copy.noApps}</p>}
      <div className="detail-actions"><a className="detail-button" href={developerAppsPath}>{copy.openApps}</a></div>
    </section>
    <section className="public-prose-card developer-card" aria-labelledby="developer-personal">
      <h2 id="developer-personal">{copy.personalHeading}</h2>
      <Tokens tokens={data.tokens} empty={copy.noPersonal} />
    </section>
  </div>;
}

function AppDetail({ data }: { data: Extract<DeveloperRead, { status: 'app' }> }) {
  const { app } = data;
  return <>
    <div className="detail-actions"><a className="detail-button" href={developerPath}>← {copy.back}</a></div>
    <section className="public-prose-card developer-card" aria-labelledby="developer-app-name">
      <h2 id="developer-app-name">{app.name}</h2>
      {app.description && <p>{app.description}</p>}
      <p className="developer-muted">Client ID: <code>{app.clientId}</code></p>
    </section>
    <div className="developer-grid">
      <section className="public-prose-card developer-card" aria-labelledby="developer-scopes">
        <h2 id="developer-scopes">{copy.scopesHeading}</h2>
        <p className="developer-pills">{(app.allowedScopes.length ? app.allowedScopes : ['read'])
          .map(scope => <span className="developer-pill" key={scope}>{scope}</span>)}</p>
      </section>
      <section className="public-prose-card developer-card" aria-labelledby="developer-tokens">
        <h2 id="developer-tokens">{copy.tokenHistory}</h2>
        <Tokens tokens={data.tokens} empty={copy.noTokens} />
      </section>
    </div>
  </>;
}

export default function DeveloperScreen({ config, session: initial, appId }: { config: AppConfig; session: SessionSummary; appId?: string }) {
  const { session, status } = useSession(initial, { endpoint: config.urls.authMe });
  const [load, setLoad] = useState<Load>(initial.authenticated ? { state: 'loading' } : { state: 'anonymous' });
  const next = appId ? `${developerPath}/apps/${appId}` : developerPath;
  // The bridge answer may say the visitor signed out (or in) since the page was rendered.
  const signedIn = status === 'ready' ? session.authenticated : initial.authenticated;

  useEffect(() => {
    if (!signedIn) { setLoad({ state: 'anonymous' }); return; }
    const controller = new AbortController();
    setLoad({ state: 'loading' });
    (async () => {
      try {
        const response = await fetch(appId ? developerAppApi + appId : developerOverviewApi,
          { credentials: 'same-origin', cache: 'no-store', signal: controller.signal, headers: { Accept: 'application/json' } });
        if (response.status === 401) { setLoad({ state: 'anonymous' }); return; }
        if (response.status === 404 && appId) { setLoad({ state: 'not-found' }); return; }
        if (!response.ok) throw new Error('unavailable');
        const data = readDeveloper(await response.json(), Boolean(appId));
        setLoad(data ? { state: 'ready', data } : { state: 'unavailable' });
      } catch {
        if (!controller.signal.aborted) setLoad({ state: 'unavailable' });
      }
    })();
    return () => controller.abort();
  }, [signedIn, appId]);

  return <article className="public-page-shell information-page suggest-change-page developer-page" aria-labelledby="developer-title">
    <header className="public-page-header"><div className="public-page-header__content">
      <h1 className="public-page-header__title" id="developer-title">{copy.title}</h1>
      {!appId && <p className="public-page-header__description">{copy.lead}</p>}
    </div></header>
    {load.state === 'loading' && <p role="status">{copy.loading}</p>}
    {load.state === 'anonymous' && <>
      {notice('info', copy.loginLead)}
      <div className="detail-actions"><a className="detail-button detail-button--primary"
        href={`${config.urls.login}?next=${encodeURIComponent(next)}`}>{copy.login}</a></div>
    </>}
    {load.state === 'unavailable' && notice('error', copy.unavailable)}
    {load.state === 'not-found' && <>
      {notice('error', copy.notFound)}
      <div className="detail-actions"><a className="detail-button" href={developerPath}>← {copy.back}</a></div>
    </>}
    {load.state === 'ready' && (load.data.status === 'locked' ? <Locked />
      : load.data.status === 'overview' ? <Overview data={load.data} /> : <AppDetail data={load.data} />)}
  </article>;
}
