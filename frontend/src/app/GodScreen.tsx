import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import './god-auth.css';

type Reply = { stage: string; csrf?: string; message?: string; redirect?: string; activated?: boolean;
  authenticators?: string[]; options?: Record<string, unknown> };
const labels: Record<string, string> = {
  start: 'Aloita kirjautuminen', totp_first: 'Ensimmäinen authenticator', email_code: 'Sähköpostin vahvistuskoodi',
  passkey: 'Vahvista passkeyllä', totp_second: 'Toinen authenticator', email_link: 'Sähköpostin vahvistuslinkki',
  final_secret: 'Erillinen vahvistussalasana', enroll_email: 'Vahvista käyttöönotto sähköpostista',
  enroll_passkey: 'Ota turvatekijät käyttöön', enroll_secrets: 'Vahvista salasanat ja authenticatorit', enrolled: 'Käyttöönotto tallennettu',
};
const loginStages = ['start', 'totp_first', 'email_code', 'passkey', 'totp_second', 'email_link', 'final_secret'];

function fromBase64(value: string): ArrayBuffer {
  const normal = value.replaceAll('-', '+').replaceAll('_', '/');
  return Uint8Array.from(atob(normal + '='.repeat((4 - normal.length % 4) % 4)), c => c.charCodeAt(0)).buffer;
}
function toBase64(value: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(value))).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
}
async function passkey(options: Record<string, unknown>, register: boolean): Promise<unknown> {
  const decoded = { ...options, challenge: fromBase64(options.challenge as string) };
  for (const key of ['allowCredentials', 'excludeCredentials']) {
    if (Array.isArray(options[key])) Object.assign(decoded, { [key]: options[key].map((item: { id: string }) => ({ ...item, id: fromBase64(item.id) })) });
  }
  if (register) {
    const user = options.user as { id: string };
    Object.assign(decoded, { user: { ...user, id: fromBase64(user.id) } });
  }
  const credential = (register
    ? await navigator.credentials.create({ publicKey: decoded as unknown as PublicKeyCredentialCreationOptions })
    : await navigator.credentials.get({ publicKey: decoded as unknown as PublicKeyCredentialRequestOptions })) as PublicKeyCredential | null;
  if (!credential) throw new Error('Passkey-vahvistus keskeytettiin.');
  const response = credential.response;
  const fields: Record<string, unknown> = { clientDataJSON: toBase64(response.clientDataJSON) };
  if (register) {
    const attestation = response as AuthenticatorAttestationResponse;
    fields.attestationObject = toBase64(attestation.attestationObject);
    fields.transports = attestation.getTransports?.() ?? [];
  } else {
    const assertion = response as AuthenticatorAssertionResponse;
    fields.authenticatorData = toBase64(assertion.authenticatorData);
    fields.signature = toBase64(assertion.signature);
    fields.userHandle = assertion.userHandle ? toBase64(assertion.userHandle) : null;
  }
  return { id: credential.id, rawId: toBase64(credential.rawId), type: credential.type, response: fields };
}

export default function GodScreen() {
  const [reply, setReply] = useState<Reply>({ stage: 'loading' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [setup, setSetup] = useState(false);
  const csrf = useRef('');
  const [linkToken, setLinkToken] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);

  async function call(action: string, fields: Record<string, unknown> = {}) {
    const response = await fetch('/users/auth/login', { method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf.current },
      body: JSON.stringify({ god_action: action, ...fields }) });
    const result = await response.json() as Reply;
    if (!response.ok) throw new Error(result.message || 'Vahvistus ei onnistunut.');
    if (result.csrf) csrf.current = result.csrf;
    if (result.redirect) window.location.assign(result.redirect);
    return result;
  }
  useEffect(() => {
    // Bearer links use the fragment, so they never enter server access logs or
    // referrers. Remove it before third-party assets or later navigation.
    function readLink() {
      const params = new URLSearchParams(window.location.hash.slice(1));
      setLinkToken(params.get('verify') || params.get('enroll') || '');
      if (window.location.hash) window.history.replaceState(null, '', window.location.pathname);
    }
    readLink();
    window.addEventListener('hashchange', readLink);
    void call('status').then(setReply).catch(() => setError('Yhteys epäonnistui. Päivitä sivu ja yritä uudelleen.'));
    return () => window.removeEventListener('hashchange', readLink);
  }, []);
  useEffect(() => { if (reply.stage !== 'loading') heading.current?.focus(); }, [reply.stage]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true); setError('');
    try {
      const action = setup && reply.stage === 'start' ? 'enroll_start' : reply.stage;
      if (action === 'passkey' || action === 'enroll_passkey') {
        const register = action === 'enroll_passkey';
        const options = await call(register ? 'enroll_passkey_options' : 'passkey_options');
        const credential = await passkey(options.options!, register);
        setReply(await call(register ? 'enroll_passkey_verify' : 'passkey', { credential }));
      } else {
        setReply(await call(action, { username: values.get('username'), password: values.get('password'),
          secret: values.get('secret'), code: values.get('code'), codes: [values.get('first'), values.get('second')], token: linkToken }));
        if (action === 'enroll_email' || action === 'email_link') setLinkToken('');
      }
      form.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Vahvistus ei onnistunut.');
    } finally { setBusy(false); }
  }
  const stage = reply.stage;
  return <section className="god-auth" aria-busy={busy}>
    <h1>God-tilin turvallinen kirjautuminen</h1>
    <p>Kaikki vahvistukset tarvitaan jokaisella kirjautumisella. Kirjautuminen vanhenee 30 minuutissa.</p>
    {stage === 'loading' ? <p role="status">Ladataan kirjautumista...</p> : <>
      <h2 ref={heading} tabIndex={-1}>{setup && stage === 'start' ? 'Ensimmäinen käyttöönotto' : labels[stage]}</h2>
      {loginStages.includes(stage) && <p>Vaihe {loginStages.indexOf(stage) + 1} / 7</p>}
      {error && <p role="alert" className="god-auth-error">{error}</p>}
      {stage === 'enrolled' ? <p>{reply.activated
        ? 'Turvatekijät ja hallituksen hyväksynnät ovat valmiit. Voit nyt kirjautua god-tilille.'
        : 'Turvatekijät on tallennettu. Tili pysyy poissa käytöstä, kunnes kaksi hallituksen jäsentä on hyväksynyt sen.'}</p>
        : <form onSubmit={submit}>
          {stage === 'start' && <>
            {setup ? <p>Kirjaudu ensin Olivian tavalliselle tilille. Vahvista sen salasana ja authenticator-koodi. Käyttöönoton linkki lähetetään uuden tilin sähköpostiin.</p>
              : <label>Käyttäjänimi<input name="username" autoComplete="username" required /></label>}
            <label>{setup ? 'Tavallisen tilin salasana' : 'Salasana (vähintään 32 merkkiä)'}<input name="password" type="password" autoComplete="current-password" minLength={setup ? undefined : 32} maxLength={4096} required /></label>
            {setup && <label>Tavallisen tilin authenticator-koodi<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required /></label>}
          </>}
          {['totp_first', 'totp_second', 'email_code'].includes(stage) && <label>{labels[stage]}<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required /></label>}
          {['email_link', 'enroll_email'].includes(stage) && <p>Avaa lähetetty linkki tässä selaimessa. Vahvista sen jälkeen alla olevalla painikkeella. Linkki ja koko vahvistus ovat voimassa 15 minuuttia aloittamisesta.</p>}
          {stage === 'enroll_passkey' && <>
            <p>Lisää nämä kaksi erillistä authenticatoria eri laitteisiin. Tallenna molemmat ennen passkeyn lisäämistä. Älä jaa käyttöönottoavaimia.</p>
            {reply.authenticators?.map((uri, index) => <label key={index}>Authenticator {index + 1}: käyttöönottoavain
              <input readOnly value={new URL(uri).searchParams.get('secret') ?? ''} autoComplete="off" />
            </label>)}
          </>}
          {stage === 'enroll_secrets' && <>
            <label>Uuden god-tilin salasana, vähintään 32 merkkiä<input name="password" type="password" autoComplete="new-password" minLength={32} maxLength={4096} required /></label>
            <label>Ensimmäisen authenticatorin koodi<input name="first" inputMode="numeric" pattern="[0-9]{6}" required /></label>
            <label>Toisen authenticatorin koodi<input name="second" inputMode="numeric" pattern="[0-9]{6}" required /></label>
          </>}
          {['final_secret', 'enroll_secrets'].includes(stage) && <label>Erillinen vahvistussalasana, vähintään 64 merkkiä<input name="secret" type="password" autoComplete={stage === 'enroll_secrets' ? 'new-password' : 'off'} minLength={64} maxLength={4096} required /></label>}
          <button type="submit" disabled={busy || (['email_link', 'enroll_email'].includes(stage) && !linkToken)}>{busy ? 'Vahvistetaan...' : stage === 'enroll_passkey' ? 'Lisää passkey' : 'Vahvista ja jatka'}</button>
        </form>}
      {stage === 'start' && <button className="god-auth-secondary" type="button" disabled={busy} onClick={() => { setSetup(!setup); setError(''); }}>{setup ? 'Takaisin kirjautumiseen' : 'Ota uusi god-tili käyttöön'}</button>}
      {stage !== 'start' && <a href="/auth/god">Päivitä vahvistuksen tila</a>}
      <a href="/users/auth/login">Tavallinen kirjautuminen</a>
    </>}
    {stage === 'loading' && error && <p role="alert">{error}</p>}
  </section>;
}
