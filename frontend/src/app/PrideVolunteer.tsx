import { useState } from 'react';
import type { FormEvent } from 'react';
import { prideVolunteerCopy as c, signUpBannerCarrier, validateVolunteer } from './pride-volunteer';
import type { VolunteerField, VolunteerInput, VolunteerResult } from './pride-volunteer';

type Errors = Partial<Record<VolunteerField, string>>;

/** Call for banner carriers. Shown only behind the pride_banner.json switch. */
export function PrideVolunteer({ privacyUrl, submit = signUpBannerCarrier }: {
  privacyUrl: string; submit?: (input: VolunteerInput) => Promise<VolunteerResult>;
}) {
  const [errors, setErrors] = useState<Errors>({});
  const [failure, setFailure] = useState('');
  const [sending, setSending] = useState(false);
  const [sentTo, setSentTo] = useState('');
  const [unsure, setUnsure] = useState(false);
  const count = Object.keys(errors).length;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sending) return;
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? '').trim();
    const input: VolunteerInput = {
      name: text('name'), email: text('email'), city: text('city'), pride: unsure ? '' : text('pride'),
      unsure, note: text('note'), consent: form.get('consent') === 'on', website: text('hp_trap'),
    };
    const found = validateVolunteer(input);
    setErrors(found);
    setFailure('');
    const first = (['name', 'email', 'consent'] as const).find(field => found[field]);
    if (first) {
      (event.currentTarget.elements.namedItem(first) as HTMLElement | null)?.focus();
      return;
    }
    setSending(true);
    const result = await submit(input);
    setSending(false);
    if (result.ok) setSentTo(input.email);
    else setFailure(result.message || c.failed);
  }

  const invalid = (field: VolunteerField) => errors[field] ? { 'aria-invalid': true as const, 'aria-describedby': `pv-${field}-err` } : {};
  const fieldError = (field: VolunteerField) => errors[field] && <p className="pride-error" id={`pv-${field}-err`}>{errors[field]}</p>;

  return <section className="pride-volunteer" id="banderolli" aria-labelledby="pv-heading">
    <div className="pride-volunteer__intro">
      <h2 id="pv-heading">{c.title}</h2>
      <p>{c.intro}</p>
      <p>{c.call}</p>
      <dl className="pride-volunteer__terms">
        {c.terms.map(term => <div key={term.title}><dt>{term.title}</dt><dd>{term.text}</dd></div>)}
      </dl>
    </div>
    {sentTo ? <div className="pride-form pride-done" id="banderolli-lomake" role="status" tabIndex={-1} ref={node => node?.focus()}>
      <div className="pride-done__symbol" aria-hidden="true">✓</div>
      <h3>{c.doneTitle}</h3>
      <p>{c.doneSent} <strong>{sentTo}</strong>. {c.doneConfirm}</p>
      <p>{c.doneWait}</p>
      <p className="pride-muted">{c.donePromise}</p>
    </div> : <form className="pride-form" id="banderolli-lomake" method="post" noValidate aria-labelledby="pv-title"
      aria-busy={sending || undefined} onSubmit={onSubmit}>
      <h3 id="pv-title">{c.formTitle}</h3>
      {(count > 0 || failure) && <div className="pride-alert" role="alert">
        <div>{count > 0 ? <><strong>{c.errorTitle(count)}</strong>{c.errorHelp}</> : failure}</div>
      </div>}
      <fieldset disabled={sending}>
        <legend className="visually-hidden">{c.legend}</legend>
        <div hidden aria-hidden="true">
          <label htmlFor="pv-hp">Jätä tämä kenttä tyhjäksi</label>
          <input type="text" id="pv-hp" name="hp_trap" tabIndex={-1} autoComplete="off" />
        </div>
        <div className={`pride-field${errors.name ? ' is-invalid' : ''}`}>
          <label htmlFor="pv-name">{c.name} <span aria-hidden="true">*</span></label>
          <input type="text" id="pv-name" name="name" autoComplete="given-name" maxLength={60} required
            placeholder={c.namePlaceholder} {...invalid('name')} />
          {fieldError('name')}
        </div>
        <div className={`pride-field${errors.email ? ' is-invalid' : ''}`}>
          <label htmlFor="pv-email">{c.email} <span aria-hidden="true">*</span></label>
          <input type="email" id="pv-email" name="email" autoComplete="email" inputMode="email" maxLength={254} required
            placeholder={c.emailPlaceholder} aria-describedby={`pv-email-hint${errors.email ? ' pv-email-err' : ''}`}
            aria-invalid={errors.email ? true : undefined} />
          <p className="pride-hint" id="pv-email-hint">{c.emailHint}</p>
          {fieldError('email')}
        </div>
        <div className="pride-field">
          <label htmlFor="pv-city">{c.city} <span className="pride-optional">{c.optional}</span></label>
          <input type="text" id="pv-city" name="city" autoComplete="address-level2" maxLength={80} placeholder={c.cityPlaceholder} />
        </div>
        <div className="pride-field">
          <label htmlFor="pv-pride">{c.pride} <span className="pride-optional">{c.optional}</span></label>
          <input type="text" id="pv-pride" name="pride" maxLength={120} placeholder={c.pridePlaceholder}
            disabled={unsure} aria-describedby="pv-pride-hint" />
          <label className="pride-check pride-check--inline">
            <input type="checkbox" name="unsure" checked={unsure} onChange={event => setUnsure(event.target.checked)} />
            <span>{c.unsure}</span>
          </label>
          <p className="pride-hint" id="pv-pride-hint">{c.prideHint}</p>
        </div>
        <div className="pride-field">
          <label htmlFor="pv-note">{c.note} <span className="pride-optional">{c.optional}</span></label>
          <textarea id="pv-note" name="note" rows={4} maxLength={500} aria-describedby="pv-note-hint" />
          <p className="pride-hint" id="pv-note-hint">{c.noteHint}</p>
        </div>
        <div className={`pride-field${errors.consent ? ' is-invalid' : ''}`}>
          <label className="pride-check pride-check--consent">
            <input type="checkbox" id="pv-consent" name="consent" required {...invalid('consent')} />
            <span>{c.consent}</span>
          </label>
          {fieldError('consent')}
        </div>
        <p className="pride-privacy">{c.privacyBefore}<a href={privacyUrl}>{c.privacyLink}</a>{c.privacyAfter}</p>
        <button className="button" type="submit">{sending ? c.sending : c.submit}</button>
      </fieldset>
    </form>}
  </section>;
}
