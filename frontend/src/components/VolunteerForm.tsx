import { useRef, useState } from 'react';
import type { FormEvent } from 'react';

type FieldName = 'name' | 'email' | 'phone' | 'city' | 'notes';
type Feedback = { kind: 'success' | 'error'; message: string };

export interface VolunteerFormProps {
  endpoint: string;
  messages: {
    required: string;
    invalid: string;
    success: string;
    failed: string;
    network: string;
    sending: string;
  };
}

export function VolunteerForm({ endpoint, messages }: VolunteerFormProps) {
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [invalid, setInvalid] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  // State updates are batched: the ref also guards two submits in the same tick.
  const requestPending = useRef(false);

  function clearInvalid(event: FormEvent<HTMLFormElement>) {
    const field = event.target;
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
      setInvalid((previous) => previous.filter((id) => id !== field.id));
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (requestPending.current) return;

    const form = event.currentTarget;
    const fields = Array.from(form.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea'));
    const missing = fields.filter((field) => field.required && !field.value.trim());
    const invalidFields = fields.filter((field) => missing.includes(field) || !field.validity.valid);
    setInvalid(invalidFields.map((field) => field.id));
    if (invalidFields.length) {
      setFeedback({ kind: 'error', message: missing.length ? messages.required : messages.invalid });
      invalidFields[0].focus();
      return;
    }

    const payload = Object.fromEntries(fields.map((field) => [field.name, field.value.trim()]));
    requestPending.current = true;
    setPending(true);
    setFeedback(null);
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      });
      // Login redirects and non-JSON server errors are failures, never successful signups.
      const result = await response.json().catch(() => null);
      if (response.ok && result?.success === true) {
        setFeedback({ kind: 'success', message: messages.success });
        form.reset();
      } else {
        setFeedback({
          kind: 'error',
          message: typeof result?.error === 'string' && result.error ? result.error : messages.failed,
        });
      }
    } catch {
      setFeedback({ kind: 'error', message: messages.network });
    } finally {
      requestPending.current = false;
      setPending(false);
    }
  }

  const fieldProps = (name: FieldName) => ({
    id: `vol-${name}`,
    name,
    className: 'form-control',
    'aria-invalid': invalid.includes(`vol-${name}`) ? true : undefined,
  });

  return (
    <form id="volunteer-form" method="post" action={endpoint} noValidate
      aria-describedby="vol-help vol-msg" aria-busy={pending || undefined}
      onSubmit={submit} onInput={clearInvalid}>
      <fieldset id="vol-fields" disabled={pending}>
        <legend className="visually-hidden">Ilmoittautumistiedot</legend>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="vol-name" className="form-label">Nimi <span style={{ color: 'var(--secondary-orange)' }}>*</span></label>
            <input {...fieldProps('name')} autoComplete="name" placeholder="Etunimi Sukunimi" required aria-required="true" />
          </div>
          <div className="form-group">
            <label htmlFor="vol-email" className="form-label">Sähköposti <span style={{ color: 'var(--secondary-orange)' }}>*</span></label>
            <input {...fieldProps('email')} type="email" autoComplete="email" placeholder="nimi@esimerkki.fi" required aria-required="true" />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="vol-phone" className="form-label">Puhelin</label>
            <input {...fieldProps('phone')} type="tel" autoComplete="tel" placeholder="040 123 4567" />
          </div>
          <div className="form-group">
            <label htmlFor="vol-city" className="form-label">Kaupunki</label>
            <input {...fieldProps('city')} autoComplete="address-level2" placeholder="Helsinki" />
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="vol-notes" className="form-label">Mikä sinua kiinnostaa?</label>
          <textarea {...fieldProps('notes')} rows={4}
            placeholder="Esim. tarrojen jakaminen Turussa, somesisällöt tai muutama tunti silloin tällöin." />
        </div>
        <button className="btn btn-primary" id="vol-submit" type="submit" disabled={pending} aria-busy={pending || undefined}>
          <i className="fa-solid fa-paper-plane" aria-hidden="true" />
          <span id="vol-submit-label">{pending ? messages.sending : 'Lähetä ilmoittautuminen'}</span>
        </button>
      </fieldset>
      <div id="vol-msg" className={`flash-message flash-message--inline${feedback ? ` flash-${feedback.kind}` : ''}`}
        role={feedback?.kind === 'error' ? 'alert' : 'status'} aria-live="polite" aria-atomic="true" tabIndex={-1} hidden={!feedback}>
        <span className="flash-icon" aria-hidden="true">
          <i className={`fa-solid ${feedback?.kind === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'}`} />
        </span>
        <span className="flash-content"><span id="vol-msg-text" className="flash-text">{feedback?.message}</span></span>
      </div>
    </form>
  );
}
