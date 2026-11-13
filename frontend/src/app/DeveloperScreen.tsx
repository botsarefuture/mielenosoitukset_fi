import { useEffect, useState } from 'react';
import type { AppConfig } from './config';
import type { SessionSummary } from './session';
import { useSession } from './useSession';
import {
  developerAccessRequestPath, developerAppApi, developerAppsApi, developerCopy as copy, developerIssuableScopes,
  developerOverviewApi, developerPath, developerRequestableScopes, developerScopeRequestPath, developerTokensApi,
  developerWrite, formatDeveloperDate, readDeveloper,
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

/** What a write controls component needs: the CSRF token, and a way to reread the page after a change. */
type Writes = { csrf: string; reload: () => void };

function Tokens({ tokens, empty, writes }: { tokens: DeveloperToken[]; empty: string; writes?: Writes }) {
  const [message, setMessage] = useState<string>('');
  if (!tokens.length) return <p className="developer-muted">{empty}</p>;
  const revoke = async (id: string) => {
    if (!writes) return;
    const result = await developerWrite('DELETE', `${developerTokensApi}/${id}`, writes.csrf);
    if (result.ok) writes.reload(); else setMessage(result.message);
  };
  return <>
    {message && notice('error', message)}
    <ul className="developer-list">
      {tokens.map(token => <li key={token.id || `${token.type}-${token.expiresAt}`}>
        <strong>{token.type}</strong> — {token.scopes.join(', ') || 'read'}
        <div className="developer-muted">{copy.validUntil} {formatDeveloperDate(token.expiresAt)}</div>
        {writes && token.id && <div className="detail-actions">
          <button type="button" className="detail-button detail-button--danger" onClick={() => revoke(token.id)}>{copy.revoke}</button>
        </div>}
      </li>)}
    </ul>
  </>;
}

/** A secret the server will not show again. It lives only in this component's state. */
function SecretBox({ label, value, onClose }: { label: string; value: string; onClose: () => void }) {
  return <div className="flash-message flash-message--inline flash-info developer-secret" role="status">
    <span className="flash-text">
      <strong>{label}</strong> {copy.secretOnce}
      <code className="developer-secret__value">{value}</code>
    </span>
    <button type="button" className="detail-button" onClick={onClose}>OK</button>
  </div>;
}

function ScopeChecks({ options, picked, onChange, name }: { options: readonly string[]; picked: string[]; onChange: (next: string[]) => void; name: string }) {
  return <fieldset className="developer-scope-fieldset">
    <legend>{copy.scopes}</legend>
    {options.map(scope => <label className="developer-check" key={scope}>
      <input type="checkbox" name={name} value={scope} checked={picked.includes(scope)}
        onChange={event => onChange(event.target.checked ? [...picked, scope] : picked.filter(item => item !== scope))} />
      <span>{scope}</span>
    </label>)}
  </fieldset>;
}

type Secret = { label: string; value: string } | null;

function CreateAppForm({ writes }: { writes: Writes }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [secret, setSecret] = useState<Secret>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError('');
    const result = await developerWrite('POST', developerAppsApi, writes.csrf, { name, description });
    setBusy(false);
    if (!result.ok) { setError(result.message); return; }
    const app = result.body.app as Record<string, unknown> | undefined;
    setSecret(typeof app?.client_secret === 'string' ? { label: copy.clientSecret, value: app.client_secret } : null);
    setName(''); setDescription('');
    writes.reload();
  };
  return <section className="public-prose-card developer-card" aria-labelledby="developer-create-app">
    <h2 id="developer-create-app">{copy.createApp}</h2>
    <form className="suggest-change-form" onSubmit={submit}>
      <div className="suggest-change-field">
        <label htmlFor="developer-app-name-input">{copy.appName}</label>
        <input id="developer-app-name-input" value={name} maxLength={100} required onChange={event => setName(event.target.value)} />
      </div>
      <div className="suggest-change-field">
        <label htmlFor="developer-app-description">{copy.appDescription}</label>
        <textarea id="developer-app-description" rows={2} value={description} maxLength={1000} onChange={event => setDescription(event.target.value)} />
      </div>
      {error && notice('error', error)}
      <div className="detail-actions"><button type="submit" className="detail-button detail-button--primary" disabled={busy}>{busy ? copy.creating : copy.create}</button></div>
    </form>
    {secret && <SecretBox {...secret} onClose={() => setSecret(null)} />}
  </section>;
}

/** Personal tokens (no app) and app tokens share one form; appId decides which route it calls. */
function CreateTokenForm({ writes, appId, scopes }: { writes: Writes; appId?: string; scopes: readonly string[] }) {
  const [type, setType] = useState('short');
  const [picked, setPicked] = useState<string[]>(['read']);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [secret, setSecret] = useState<Secret>(null);
  const idPrefix = appId ? 'developer-app-token' : 'developer-personal-token';
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!picked.length) { setError(copy.pickScope); return; }
    setBusy(true); setError('');
    const url = appId ? `${developerAppsApi}/${appId}/token` : developerTokensApi;
    const result = await developerWrite('POST', url, writes.csrf, { type, scopes: picked });
    setBusy(false);
    if (!result.ok) { setError(result.message); return; }
    setSecret(typeof result.body.token === 'string' ? { label: copy.tokenValue, value: result.body.token } : null);
    writes.reload();
  };
  return <form className="suggest-change-form" onSubmit={submit}>
    <div className="suggest-change-field">
      <label htmlFor={`${idPrefix}-type`}>{copy.tokenType}</label>
      <select id={`${idPrefix}-type`} value={type} onChange={event => setType(event.target.value)}>
        <option value="short">{copy.tokenShort}</option>
        <option value="long">{copy.tokenLong}</option>
      </select>
    </div>
    <ScopeChecks options={scopes} picked={picked} onChange={setPicked} name={`${idPrefix}-scope`} />
    {error && notice('error', error)}
    <div className="detail-actions"><button type="submit" className="detail-button detail-button--primary" disabled={busy}>{busy ? copy.creating : copy.createToken}</button></div>
    {secret && <SecretBox {...secret} onClose={() => setSecret(null)} />}
  </form>;
}

function RotateSecret({ writes, appId, onRotated }: { writes: Writes; appId: string; onRotated: (secret: Secret) => void }) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');
  const rotate = async () => {
    setError('');
    const result = await developerWrite('POST', `${developerAppsApi}/${appId}/rotate`, writes.csrf, {});
    setConfirming(false);
    if (!result.ok) { setError(result.message); return; }
    onRotated(typeof result.body.client_secret === 'string' ? { label: copy.clientSecret, value: result.body.client_secret } : null);
    writes.reload();
  };
  return <>
    <p className="developer-muted">{copy.rotateNote}</p>
    {error && notice('error', error)}
    <div className="detail-actions">
      {confirming
        ? <button type="button" className="detail-button detail-button--danger" onClick={rotate}>{copy.rotateConfirm}</button>
        : <button type="button" className="detail-button" onClick={() => setConfirming(true)}>{copy.rotate}</button>}
    </div>
  </>;
}

/** Posts to the unchanged Flask endpoint, which stores the request and emails the admin. */
function ScopeRequest({ appId, current }: { appId: string; current: string[] }) {
  const options = developerRequestableScopes.filter(scope => !current.includes(scope));
  const [picked, setPicked] = useState<string[]>([]);
  const [reason, setReason] = useState('');
  const [result, setResult] = useState<{ kind: 'error' | 'info'; text: string } | null>(null);
  if (!options.length) return <p className="developer-muted">{copy.noScopesToRequest}</p>;
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!picked.length) { setResult({ kind: 'error', text: copy.pickScope }); return; }
    if (!reason.trim()) { setResult({ kind: 'error', text: copy.reasonRequired }); return; }
    try {
      const response = await fetch(developerScopeRequestPath(appId), { method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ scopes: picked, reason: reason.trim() }) });
      const body = await response.json().catch(() => null) as { status?: string; message?: string } | null;
      const text = typeof body?.message === 'string' ? body.message.slice(0, 200) : copy.failed;
      setResult({ kind: response.ok && body?.status === 'success' ? 'info' : 'error', text });
      if (response.ok && body?.status === 'success') { setPicked([]); setReason(''); }
    } catch { setResult({ kind: 'error', text: copy.failed }); }
  };
  return <form className="suggest-change-form" onSubmit={submit}>
    <p className="developer-muted">{copy.requestScopesLead}</p>
    <ScopeChecks options={options} picked={picked} onChange={setPicked} name="developer-request-scope" />
    <div className="suggest-change-field">
      <label htmlFor="developer-scope-reason">{copy.reason}</label>
      <textarea id="developer-scope-reason" rows={3} value={reason} maxLength={2000} onChange={event => setReason(event.target.value)} />
    </div>
    {result && notice(result.kind, result.text)}
    <div className="detail-actions"><button type="submit" className="detail-button detail-button--primary">{copy.send}</button></div>
  </form>;
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

function Overview({ data, writes }: { data: Extract<DeveloperRead, { status: 'overview' }>; writes?: Writes }) {
  return <div className="developer-grid">
    <section className="public-prose-card developer-card" aria-labelledby="developer-apps">
      <h2 id="developer-apps">{copy.appsHeading}</h2>
      {data.apps.length ? <ul className="developer-list">
        {data.apps.map(app => <li key={app.id}>
          <a href={`${developerPath}/apps/${app.id}`}><strong>{app.name}</strong></a>
          <div className="developer-muted">Client ID: <code>{app.clientId}</code></div>
        </li>)}
      </ul> : <p className="developer-muted">{copy.noApps}</p>}
    </section>
    {writes && <CreateAppForm writes={writes} />}
    <section className="public-prose-card developer-card" aria-labelledby="developer-personal">
      <h2 id="developer-personal">{copy.personalHeading}</h2>
      <Tokens tokens={data.tokens} empty={copy.noPersonal} writes={writes} />
    </section>
    {writes && <section className="public-prose-card developer-card" aria-labelledby="developer-create-personal">
      <h2 id="developer-create-personal">{copy.createPersonal}</h2>
      <CreateTokenForm writes={writes} scopes={developerIssuableScopes} />
    </section>}
  </div>;
}

function AppDetail({ data, writes }: { data: Extract<DeveloperRead, { status: 'app' }>; writes?: Writes }) {
  const { app } = data;
  const [rotated, setRotated] = useState<Secret>(null);
  const allowed = app.allowedScopes.length ? app.allowedScopes : ['read'];
  return <>
    <div className="detail-actions"><a className="detail-button" href={developerPath}>← {copy.back}</a></div>
    <section className="public-prose-card developer-card" aria-labelledby="developer-app-name">
      <h2 id="developer-app-name">{app.name}</h2>
      {app.description && <p>{app.description}</p>}
      <p className="developer-muted">Client ID: <code>{app.clientId}</code></p>
      {writes && <RotateSecret writes={writes} appId={app.id} onRotated={setRotated} />}
      {rotated && <SecretBox {...rotated} onClose={() => setRotated(null)} />}
    </section>
    <div className="developer-grid">
      <section className="public-prose-card developer-card" aria-labelledby="developer-scopes">
        <h2 id="developer-scopes">{copy.scopesHeading}</h2>
        <p className="developer-pills">{allowed.map(scope => <span className="developer-pill" key={scope}>{scope}</span>)}</p>
      </section>
      <section className="public-prose-card developer-card" aria-labelledby="developer-tokens">
        <h2 id="developer-tokens">{copy.tokenHistory}</h2>
        <Tokens tokens={data.tokens} empty={copy.noTokens} writes={writes} />
      </section>
      {writes && <section className="public-prose-card developer-card" aria-labelledby="developer-create-token">
        <h2 id="developer-create-token">{copy.createToken}</h2>
        <CreateTokenForm writes={writes} appId={app.id} scopes={developerIssuableScopes.filter(scope => allowed.includes(scope))} />
      </section>}
      {writes && <section className="public-prose-card developer-card" aria-labelledby="developer-request-scopes">
        <h2 id="developer-request-scopes">{copy.requestScopes}</h2>
        <ScopeRequest appId={app.id} current={allowed} />
      </section>}
    </div>
  </>;
}

export default function DeveloperScreen({ config, session: initial, appId }: { config: AppConfig; session: SessionSummary; appId?: string }) {
  const { session, status } = useSession(initial, { endpoint: config.urls.authMe });
  const [load, setLoad] = useState<Load>(initial.authenticated ? { state: 'loading' } : { state: 'anonymous' });
  // Bumped after a write so the lists and the CSRF token are read again; the old data stays visible meanwhile.
  const [reloads, setReloads] = useState(0);
  const reload = () => setReloads(count => count + 1);
  const next = appId ? `${developerPath}/apps/${appId}` : developerPath;
  // The bridge answer may say the visitor signed out (or in) since the page was rendered.
  const signedIn = status === 'ready' ? session.authenticated : initial.authenticated;

  useEffect(() => {
    if (!signedIn) { setLoad({ state: 'anonymous' }); return; }
    const controller = new AbortController();
    if (!reloads) setLoad({ state: 'loading' });
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
  }, [signedIn, appId, reloads]);

  return <article className="public-page-shell information-page suggest-change-page developer-page" aria-labelledby="developer-title">
    <header className="public-page-header"><div className="public-page-header__content">
      <h1 className="public-page-header__title" id="developer-title">{copy.title}</h1>
      <p className="public-page-header__description">{copy.lead}</p>
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
      : load.data.status === 'overview' ? <Overview data={load.data} writes={load.data.csrf ? { csrf: load.data.csrf, reload } : undefined} />
        : <AppDetail data={load.data} writes={load.data.csrf ? { csrf: load.data.csrf, reload } : undefined} />)}
  </article>;
}
