import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { CitySelect } from '../components/submit/CitySelect';
import { DateField } from '../components/submit/DateField';
import { DescriptionEditor } from '../components/submit/DescriptionEditor';
import type { DescriptionEditorHandle } from '../components/submit/DescriptionEditor';
import { OrganizerList } from '../components/submit/OrganizerList';
import {
  applyDraftFields,
  clearDraft,
  draftHasContent,
  draftOrganizers,
  fieldsToDraftFields,
  readDraft,
  readLegacyDraft,
  writeDraft,
} from '../components/submit/draft';
import type { DraftDelta } from '../components/submit/draft';
import type {
  ConflictData,
  InvalidField,
  Organizer,
  SubmitFields,
  SubmitPageProps,
} from '../components/submit/types';
import { STEP_COUNT } from '../components/submit/types';

/** Element ids kept from the legacy form: labels, tests and the server expect them. */
const FIELD_IDS: Record<string, string> = {
  title: 'name',
  tags: 'tags',
  defaultLanguage: 'default_language',
  date: 'date',
  startTime: 'start_time',
  endTime: 'end_time',
  eventType: 'type',
  route: 'route',
  city: 'city-value',
  address: 'address',
  submitterRole: 'submitter_role',
  submitterName: 'submitter_name',
  submitterEmail: 'submitter_email',
  acceptTerms: 'accept_terms',
};

const ADDRESS_PATTERN = /^.+(?:,\s*\d{3,5})?$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

type ImportEvent = {
  title?: string;
  description_html?: string;
  start_date?: string;
  start_time?: string;
  end_time?: string;
  city?: string;
  address?: string;
  organizers?: string[];
  organizer?: string;
  image_url?: string;
  facebook_url?: string;
};

type ImportResponse = {
  success?: boolean;
  error?: string;
  message?: string;
  warnings?: string[];
  fields_summary?: Array<{ key: string; label: string; imported: boolean }>;
  event?: ImportEvent;
};

type Feedback = { message: string; category: 'error' | 'warning' | 'info' } | null;

export function SubmitPage(props: SubmitPageProps) {
  const { messages, cities, locales, localeNames, defaultLanguage, token, action, importUrl } = props;

  const initialFields: SubmitFields = useMemo(() => ({
    title: '',
    tags: '',
    defaultLanguage,
    descriptionHtml: '',
    date: '',
    startTime: '',
    endTime: '',
    eventType: '',
    route: '',
    city: '',
    address: '',
    submitterRole: '',
    submitterName: '',
    submitterEmail: '',
    acceptTerms: false,
    facebook: '',
    facebookImported: false,
    facebookImageUrl: '',
  }), [defaultLanguage]);

  const [fields, setFields] = useState<SubmitFields>(initialFields);
  const [organizers, setOrganizers] = useState<Organizer[]>([]);
  const [step, setStep] = useState(1);
  const [invalid, setInvalid] = useState<Set<string>>(new Set());
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [submitting, setSubmitting] = useState(false);
  const [importState, setImportState] = useState<{ status: 'idle' | 'loading' | 'error' | 'success'; text?: string; warnings?: string[]; imported?: string[]; missing?: string[] }>({ status: 'idle' });
  const [draftRestored, setDraftRestored] = useState(false);
  // Autosave stays off until the restore commit has been applied, otherwise the
  // first effect run persists a stale empty state and deletes the draft.
  const [draftArmed, setDraftArmed] = useState(false);
  const [restoredDelta, setRestoredDelta] = useState<DraftDelta | null>(null);
  const [delta, setDelta] = useState<DraftDelta | null>(null);
  const [conflict, setConflict] = useState<ConflictData | null>(null);
  const [showTestBanner, setShowTestBanner] = useState(false);
  const [hasFile, setHasFile] = useState(false);

  const formRef = useRef<HTMLFormElement>(null);
  const editorRef = useRef<DescriptionEditorHandle>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const conflictRef = useRef<HTMLDialogElement>(null);
  const conflictResolve = useRef<((confirmed: boolean) => void) | null>(null);
  const draftReady = useRef(false);
  // Set by "delete draft": the pagehide flush must not recreate what we just removed.
  const draftSuppressed = useRef(false);
  const saveTimer = useRef<number | null>(null);
  const mounted = useRef(false);

  const set = useCallback(<K extends keyof SubmitFields>(key: K, value: SubmitFields[K]) => {
    setFields((current) => ({ ...current, [key]: value }));
    setInvalid((current) => {
      if (!current.has(key as string)) return current;
      const next = new Set(current);
      next.delete(key as string);
      return next;
    });
  }, []);

  /* ---------------------------------------------------------------- drafts */

  const buildDraft = useCallback(() => ({
    version: 2,
    savedAt: Date.now(),
    step,
    fields: fieldsToDraftFields(fields),
    organizers: organizers.map(({ name, email, website, isPrivate, showName, showEmail }) => ({
      name, email, website, isPrivate, showName, showEmail,
    })),
    descriptionDelta: delta,
  }), [delta, fields, organizers, step]);

  const persistDraft = useCallback(() => {
    if (!draftReady.current || draftSuppressed.current) return;
    const draft = buildDraft();
    if (!draftHasContent(draft)) {
      clearDraft();
      return;
    }
    writeDraft(draft);
  }, [buildDraft]);

  const scheduleSave = useCallback(() => {
    if (!draftReady.current || draftSuppressed.current) return;
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(persistDraft, 200);
  }, [persistDraft]);

  // Restore a saved draft once, before autosave starts.
  useEffect(() => {
    if (mounted.current) return;
    mounted.current = true;
    const restored = readDraft() ?? readLegacyDraft();
    if (restored) {
      setFields((current) => applyDraftFields(current, restored.fields));
      setOrganizers(draftOrganizers(restored.organizers));
      setRestoredDelta(restored.descriptionDelta);
      setDelta(restored.descriptionDelta);
      setStep(restored.step);
      setDraftRestored(true);
      // The editor mounts with the page; push the stored document through its API.
      if (restored.descriptionDelta) {
        window.setTimeout(() => editorRef.current?.setDelta(restored.descriptionDelta), 0);
      }
    }
    setOrganizers((current) => (current.length ? current : [newOrganizer()]));
    draftReady.current = true;
    setDraftArmed(true);
  }, []);

  // Debounced autosave on every edit, plus a flush when the page is hidden.
  useEffect(() => {
    if (!draftArmed) return;
    scheduleSave();
  }, [draftArmed, fields, organizers, delta, step, scheduleSave]);

  useEffect(() => {
    if (!draftArmed) return;
    const flush = () => persistDraft();
    window.addEventListener('pagehide', flush);
    return () => window.removeEventListener('pagehide', flush);
  }, [draftArmed, persistDraft]);

  /* ------------------------------------------------------------ navigation */

  const focusHeading = (nextStep: number) => {
    const heading = document.getElementById(`page-${nextStep}`)?.querySelector('h2');
    if (!heading) return;
    heading.setAttribute('tabindex', '-1');
    heading.focus({ preventScroll: true });
    heading.scrollIntoView({ block: 'start', behavior: 'instant' });
  };

  const goTo = useCallback((next: number, { focus = false } = {}) => {
    setStep((current) => {
      if (next < 1 || next > STEP_COUNT) return current;
      return next;
    });
    if (focus) window.setTimeout(() => focusHeading(next), 0);
  }, []);

  /* ------------------------------------------------------------ validation */

  const validate = useCallback((target: number): InvalidField[] => {
    const problems: InvalidField[] = [];
    const require = (key: keyof SubmitFields, message: string) => {
      const value = fields[key];
      if (typeof value === 'string' && value.trim()) return;
      if (typeof value === 'boolean' && value) return;
      problems.push({ name: key, message });
    };

    if (target === 2) {
      require('title', messages.errorRequired);
      require('tags', messages.errorRequired);
      require('defaultLanguage', messages.errorRequired);
    }
    if (target === 3) {
      require('date', messages.errorRequired);
      require('startTime', messages.errorRequired);
      require('eventType', messages.errorRequired);
      require('city', messages.errorRequired);
      require('address', messages.errorRequired);
      if (fields.address.trim() && !ADDRESS_PATTERN.test(fields.address.trim())) {
        problems.push({ name: 'address', message: messages.addressHelper });
      }
    }
    if (target === 4) {
      const named = organizers.filter((organizer) => organizer.name.trim());
      if (named.length === 0) problems.push({ name: 'organizers', message: messages.errorRequired });
    }
    if (target === 5) {
      require('submitterRole', messages.errorRequired);
      require('submitterName', messages.errorRequired);
      if (!fields.submitterEmail.trim()) {
        problems.push({ name: 'submitterEmail', message: messages.errorRequired });
      } else if (!EMAIL_PATTERN.test(fields.submitterEmail.trim())) {
        problems.push({ name: 'submitterEmail', message: messages.errorRequired });
      }
      if (!fields.acceptTerms) problems.push({ name: 'acceptTerms', message: messages.errorTerms });
    }
    return problems;
  }, [fields, messages, organizers]);

  const showProblems = useCallback((problems: InvalidField[]) => {
    setInvalid(new Set(problems.map((problem) => problem.name as string)));
    setFeedback({ message: problems[0]?.message ?? messages.errorRequired, category: 'error' });
    const first = problems[0];
    if (!first) return;
    const id = first.name === 'organizers'
      ? `organizer_name_${organizers.findIndex((organizer) => !organizer.name.trim()) + 1}`
      : FIELD_IDS[first.name];
    const element = id ? document.getElementById(id) : null;
    element?.focus({ preventScroll: true });
    element?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [messages, organizers]);

  const next = useCallback(() => {
    const problems = validate(step);
    if (problems.length) {
      showProblems(problems);
      return;
    }
    setFeedback(null);
    if (step < STEP_COUNT) goTo(step + 1, { focus: true });
  }, [goTo, showProblems, step, validate]);

  const previous = useCallback(() => {
    if (step > 1) goTo(step - 1, { focus: true });
  }, [goTo, step]);

  const chooseImport = useCallback(() => {
    goTo(2, { focus: true });
    window.setTimeout(() => document.getElementById('facebook')?.focus(), 0);
  }, [goTo]);

  const chooseManual = useCallback(() => goTo(2, { focus: true }), [goTo]);

  /* ------------------------------------------------------- facebook import */

  const applyImport = useCallback((event: ImportEvent) => {
    setFields((current) => ({
      ...current,
      title: event.title ?? current.title,
      date: event.start_date ?? current.date,
      startTime: event.start_time ?? current.startTime,
      endTime: event.end_time ?? current.endTime,
      city: event.city ?? current.city,
      address: event.address ?? current.address,
      facebook: event.facebook_url ?? current.facebook,
      facebookImageUrl: event.image_url ?? current.facebookImageUrl,
      facebookImported: true,
    }));
    if (event.description_html) editorRef.current?.setHtml(event.description_html);
    const names = event.organizers?.length ? event.organizers : event.organizer ? [event.organizer] : [];
    if (names.length) {
      const rows = names.map((name, index) => ({
        key: `import-${Date.now()}-${index}`,
        name,
        email: '',
        website: '',
        isPrivate: false,
        showName: true,
        showEmail: true,
      }));
      setOrganizers((current) => {
        const kept = current.filter((organizer) => organizer.name.trim() || organizer.email.trim());
        return [...kept.filter((organizer) => !names.includes(organizer.name)), ...rows];
      });
    }
  }, []);

  const runImport = useCallback(async () => {
    const url = fields.facebook.trim();
    if (!url) {
      setImportState({ status: 'error', text: messages.importEmptyUrl });
      return;
    }
    setImportState({ status: 'loading' });
    try {
      const response = await fetch(importUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: `url=${encodeURIComponent(url)}`,
      });
      let data: ImportResponse | null = null;
      try {
        data = (await response.json()) as ImportResponse;
      } catch {
        data = null;
      }
      if (!response.ok || !data?.success) {
        setImportState({ status: 'error', text: data?.error || messages.importFailed });
        return;
      }
      applyImport(data.event ?? {});
      const summary = data.fields_summary ?? [];
      setImportState({
        status: 'success',
        text: data.message,
        warnings: data.warnings,
        imported: summary.filter((row) => row.imported).map((row) => row.label),
        missing: summary
          .filter((row) => !row.imported && !['end_date', 'end_time', 'image_url'].includes(row.key))
          .map((row) => row.label),
      });
    } catch (error) {
      console.error('Facebook import failed:', error);
      setImportState({ status: 'error', text: messages.importFailed });
    }
  }, [applyImport, fields.facebook, importUrl, messages]);

  /* -------------------------------------------------------------- delivery */

  const buildFormData = useCallback((force: boolean) => {
    const data = new FormData();
    data.set('title', fields.title);
    data.set('tags', fields.tags);
    data.set('default_language', fields.defaultLanguage);
    data.set('description', editorRef.current?.getHtml() ?? fields.descriptionHtml);
    data.set('date', fields.date);
    data.set('start_time', fields.startTime);
    data.set('end_time', fields.endTime);
    data.set('type', fields.eventType);
    data.set('route', fields.eventType === 'marssi' ? fields.route : '');
    data.set('city', fields.city);
    data.set('address', fields.address);
    data.set('submitter_role', fields.submitterRole);
    data.set('submitter_name', fields.submitterName);
    data.set('submitter_email', fields.submitterEmail);
    data.set('accept_terms', fields.acceptTerms ? '1' : '');
    data.set('submission_token', token);
    data.set('facebook', fields.facebook);
    data.set('facebook_imported', fields.facebookImported ? '1' : '');
    data.set('facebook_image_url', fields.facebookImageUrl);
    if (force) data.set('force_submit', '1');
    organizers.forEach((organizer, position) => {
      const index = position + 1;
      data.set(`organizer_name_${index}`, organizer.name);
      data.set(`organizer_email_${index}`, organizer.email);
      data.set(`organizer_website_${index}`, organizer.website);
      if (organizer.isPrivate) data.set(`organizer_is_private_${index}`, 'on');
      if (organizer.showName) data.set(`organizer_show_name_${index}`, 'on');
      if (organizer.showEmail) data.set(`organizer_show_email_${index}`, 'on');
    });
    const file = fileRef.current?.files?.[0];
    if (file) data.set('image', file);
    return data;
  }, [fields, organizers, token]);

  const post = useCallback((force: boolean) => fetch(action, {
    method: 'POST',
    body: buildFormData(force),
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  }), [action, buildFormData]);

  /** Only an explicit non-redirected JSON success confirms delivery. */
  const delivered = useCallback(async (response: Response) => {
    if (!response.ok || response.redirected) return false;
    if (!(response.headers.get('content-type') || '').includes('application/json')) return false;
    try {
      const result = (await response.clone().json()) as { success?: boolean };
      return result?.success === true;
    } catch {
      return false;
    }
  }, []);

  const reportError = useCallback(async (response: Response, fallback?: string) => {
    let message = response.status === 429 ? messages.errorRateLimited : (fallback || messages.errorGeneric);
    try {
      if ((response.headers.get('content-type') || '').includes('application/json')) {
        const data = (await response.json()) as { message?: string; error_code?: string };
        if (response.status !== 429 && data?.message) message = data.message;
        if (data?.error_code) message += ` (${messages.errorCodeLabel}: ${data.error_code})`;
      }
    } catch (error) {
      console.error('Error parsing server response', error);
    }
    setFeedback({ message, category: 'error' });
  }, [messages]);

  const askConflict = useCallback((data: ConflictData) => new Promise<boolean>((resolve) => {
    conflictResolve.current = resolve;
    setConflict(data);
    window.setTimeout(() => {
      conflictRef.current?.showModal();
      document.getElementById('submit-conflict-cancel')?.focus();
    }, 0);
  }), []);

  const closeConflict = (confirmed: boolean) => {
    conflictRef.current?.close();
    setConflict(null);
    const resolve = conflictResolve.current;
    conflictResolve.current = null;
    resolve?.(confirmed);
  };

  const submit = useCallback(async (event?: FormEvent) => {
    event?.preventDefault();
    const problems = validate(5);
    if (problems.length) {
      showProblems(problems);
      return;
    }
    if (submitting) return;
    setSubmitting(true);
    setFeedback(null);
    try {
      const response = await post(false);
      if (await delivered(response)) {
        clearDraft();
        setStep(STEP_COUNT);
        window.setTimeout(() => focusHeading(STEP_COUNT), 0);
        return;
      }
      if (response.status === 409) {
        let data: ConflictData | null = null;
        if ((response.headers.get('content-type') || '').includes('application/json')) {
          try {
            data = (await response.json()) as ConflictData;
          } catch (error) {
            console.error('Error parsing conflict response JSON', error);
          }
        }
        const isConflict = (data as { conflict?: boolean } | null)?.conflict;
        if (data && isConflict) {
          const confirmed = await askConflict(data);
          if (!confirmed) {
            setFeedback({ message: messages.errorConflictCancelled, category: 'info' });
            return;
          }
          const retry = await post(true);
          if (await delivered(retry)) {
            clearDraft();
            setStep(STEP_COUNT);
            window.setTimeout(() => focusHeading(STEP_COUNT), 0);
            return;
          }
          await reportError(retry, messages.errorConflictForceFailed);
          return;
        }
        setFeedback({ message: `${messages.errorGeneric} (${messages.errorCodeLabel}: SUBMIT_CONFLICT)`, category: 'error' });
        return;
      }
      await reportError(response);
    } catch (error) {
      console.error('Network error:', error);
      setFeedback({ message: messages.errorGeneric, category: 'error' });
    } finally {
      setSubmitting(false);
    }
  }, [askConflict, delivered, messages, post, reportError, showProblems, submitting, validate]);

  /* ------------------------------------------------------- test mode (§dev) */

  useEffect(() => {
    if (!props.canEditDemo) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get('mode') !== 'test') return;
    setShowTestBanner(true);
    const future = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
    const iso = `${future.getFullYear()}-${String(future.getMonth() + 1).padStart(2, '0')}-${String(future.getDate()).padStart(2, '0')}`;
    setFields((current) => ({
      ...current,
      title: 'Testi-ilmoitus — automatisoitu',
      tags: 'testi, automaattinen',
      date: iso,
      startTime: '18:00',
      endTime: '20:00',
      city: 'Helsinki',
      address: 'Testikatu 1, 00100 Helsinki',
      facebook: 'https://facebook.com/events/0000000000',
      submitterRole: 'järjestäjä',
      submitterName: 'Testikäyttäjä',
      submitterEmail: 'test@example.com',
      acceptTerms: true,
    }));
    setOrganizers([{ ...newOrganizer(), name: 'Testijärjestäjä', email: 'organizer@example.com', website: 'https://example.org' }]);
  }, [props.canEditDemo]);

  /* ------------------------------------------------------------- rendering */

  const routeItems = useMemo(
    () => fields.route.split(/[,]+/).map((item) => item.trim()).filter(Boolean),
    [fields.route],
  );
  const previewSrc = fields.facebookImageUrl || undefined;
  const steps = messages.steps;
  const progressLabel = steps[step - 1] ?? steps[0];

  return (
    <div className="submit-page">
      {showTestBanner && (
        <div className="cache-notice" role="status">
          <strong>Test Mode</strong> — automaattinen testidata täytetty.
          <button type="button" onClick={() => setShowTestBanner(false)}>Sulje</button>
        </div>
      )}

      <section className="submit-intro">
        <div className="submit-intro-content">
          <h1>{messages.introTitle}</h1>
          <p className="lead">{messages.introLead}</p>
          <a className="hero-help-link" href={props.guidesUrl}>
            <i className="fa-solid fa-circle-question" aria-hidden="true" /> {messages.helpLink}
          </a>
        </div>
      </section>

      {draftRestored && (
        <div id="cacheNotice" className="cache-notice" role="status">
          {messages.draftNotice}
          <button
            type="button"
            id="resetCacheBtn"
            onClick={() => {
              // Stop autosave and the unload flush before reloading, otherwise the
              // restored values are written straight back to storage.
              draftSuppressed.current = true;
              clearDraft();
              window.location.reload();
            }}
          >
            {messages.draftReset}
          </button>
        </div>
      )}

      <aside className="progress-container" aria-label={steps[0]}>
        <p className="submit-step-status" aria-live="polite" aria-atomic="true">
          <strong>{progressLabel}</strong><span>{step} / {STEP_COUNT}</span>
        </p>
        <ol className="progress-steps">
          {steps.map((label, index) => (
            <li
              key={label}
              data-page={index + 1}
              className={`progress-step${index + 1 === step ? ' active' : index + 1 < step ? ' completed' : ''}`}
              aria-current={index + 1 === step ? 'step' : undefined}
              aria-label={label}
            >
              <span className="step-circle" aria-hidden="true">
                {index + 1 < step ? <i className="fa-solid fa-check" /> : index + 1}
              </span>
              <span className="step-label">{label}</span>
            </li>
          ))}
        </ol>
      </aside>

      <form
        ref={formRef}
        method="POST"
        action={action}
        encType="multipart/form-data"
        id="myForm"
        className="user-form"
        noValidate
        onSubmit={submit}
      >
        <input type="hidden" name="submission_token" value={token} />

        <div className="form-container">
          <details className="submit-help-card">
            <summary>{messages.beforeSubmitTitle}</summary>
            {messages.beforeSubmitBody.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            <p><a href={props.guidesUrl}>{messages.beforeSubmitGuides}</a></p>
          </details>

          {feedback && (
            <div
              id="submit-feedback"
              className={`user-form-feedback user-form-feedback--${feedback.category}`}
              role={feedback.category === 'error' ? 'alert' : 'status'}
              aria-live={feedback.category === 'error' ? 'assertive' : 'polite'}
              tabIndex={-1}
            >
              <i className="fa-solid fa-circle-info" aria-hidden="true" />
              <p>{feedback.message}</p>
            </div>
          )}

          {/* 1 — how to add the event */}
          <div className={`form-page${step === 1 ? ' active' : ''}`} id="page-1" hidden={step !== 1}>
            <div className="page-header">
              <h2><i className="fa-solid fa-wand-magic-sparkles" aria-hidden="true" /> {messages.choiceTitle}</h2>
              <p>{messages.choiceLead}</p>
            </div>
            <div className="import-choice-cards">
              <button type="button" className="import-choice-card" onClick={chooseImport}>
                <span className="import-choice-icon"><i className="fa-brands fa-facebook" aria-hidden="true" /></span>
                <span className="import-choice-title">{messages.importTitle}</span>
                <span className="import-choice-desc">{messages.importDescription}</span>
              </button>
              <button type="button" className="import-choice-card" onClick={chooseManual}>
                <span className="import-choice-icon"><i className="fa-solid fa-pen" aria-hidden="true" /></span>
                <span className="import-choice-title">{messages.manualTitle}</span>
                <span className="import-choice-desc">{messages.manualDescription}</span>
              </button>
            </div>
          </div>

          {/* 2 — basics */}
          <div className={`form-page${step === 2 ? ' active' : ''}`} id="page-2" hidden={step !== 2}>
            <div className="page-header">
              <h2><i className="fa-solid fa-info-circle" aria-hidden="true" /> {messages.basicsTitle}</h2>
              <p>{messages.basicsLead}</p>
            </div>

            <div className="form-group">
              <label htmlFor="facebook">{messages.facebookLabel}</label>
              <input
                type="url"
                id="facebook"
                name="facebook"
                value={fields.facebook}
                placeholder={messages.facebookPlaceholder}
                onChange={(event) => {
                  set('facebook', event.target.value);
                  set('facebookImported', false);
                }}
              />
              <div className="helper-text"><i className="fa-brands fa-facebook" aria-hidden="true" /> {messages.facebookHelper}</div>
            </div>

            <div className="form-group facebook-import-group">
              <div className="facebook-import-row">
                <button type="button" className="btn btn-secondary" id="facebook-import-btn" onClick={() => void runImport()} disabled={importState.status === 'loading'}>
                  <i className="fa-brands fa-facebook" aria-hidden="true" /> {messages.importButton}
                </button>
                <div className="helper-text"><i className="fa-solid fa-wand-magic-sparkles" aria-hidden="true" /> {messages.importHelper}</div>
              </div>
              {importState.status !== 'idle' && (
                <div
                  id="facebook-import-status"
                  className={`facebook-import-status ${importState.status}`}
                  role="status"
                  aria-live="polite"
                >
                  <div className="fb-import-message">
                    {importState.status === 'loading' ? messages.importLoading
                      : importState.status === 'error' ? importState.text
                        : importState.status === 'success' ? (importState.text ?? messages.importButton) : null}
                  </div>
                  {!!importState.warnings?.length && (
                    <div className="fb-import-warnings">
                      {importState.warnings.map((warning) => <div key={warning}>{warning}</div>)}
                    </div>
                  )}
                  {(!!importState.imported?.length || !!importState.missing?.length) && (
                    <div className="fb-import-fields">
                      {!!importState.imported?.length && (
                        <div>{messages.importImported}{' '}
                          {importState.imported.map((label) => <span className="fb-field-label" key={label}>{label}</span>)}
                        </div>
                      )}
                      {!!importState.missing?.length && (
                        <div>{messages.importMissing}{' '}
                          {importState.missing.map((label) => <span className="fb-field-label" key={label}>{label}</span>)}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="name">{messages.titleLabel}<span className="required-asterisk">*</span></label>
              <input
                type="text"
                id="name"
                name="title"
                value={fields.title}
                placeholder={messages.titlePlaceholder}
                required
                aria-invalid={invalid.has('title') || undefined}
                onChange={(event) => set('title', event.target.value)}
              />
              <div className="helper-text"><i className="fa-solid fa-lightbulb" aria-hidden="true" /> {messages.titleHelper}</div>
            </div>

            <div className="form-group">
              <label htmlFor="tags">{messages.tagsLabel}<span className="required-asterisk">*</span></label>
              <input
                type="text"
                id="tags"
                name="tags"
                value={fields.tags}
                placeholder={messages.tagsPlaceholder}
                required
                aria-invalid={invalid.has('tags') || undefined}
                onChange={(event) => set('tags', event.target.value)}
              />
              <div className="helper-text"><i className="fa-solid fa-tags" aria-hidden="true" /> {messages.tagsHelper}</div>
            </div>

            <div className="form-group">
              <label htmlFor="default_language">{messages.languageLabel}<span className="required-asterisk">*</span></label>
              <select
                id="default_language"
                name="default_language"
                value={fields.defaultLanguage}
                required
                onChange={(event) => set('defaultLanguage', event.target.value)}
              >
                {locales.map((locale) => (
                  <option key={locale} value={locale}>{localeNames[locale] ?? locale.toUpperCase()}</option>
                ))}
              </select>
              <div className="helper-text"><i className="fa-solid fa-language" aria-hidden="true" /> {messages.languageHelper}</div>
            </div>

            <div className="form-group">
              <label htmlFor="editor-container">{messages.descriptionLabel}</label>
              <DescriptionEditor
                ref={editorRef}
                initialHtml={fields.descriptionHtml}
                initialDelta={restoredDelta}
                ariaLabel={messages.descriptionLabel}
                onChange={(html, nextDelta) => {
                  setDelta(nextDelta);
                  setFields((current) => (current.descriptionHtml === html ? current : { ...current, descriptionHtml: html }));
                }}
              />
              <div className="helper-text"><i className="fa-solid fa-info-circle" aria-hidden="true" /> {messages.descriptionHelper}</div>
            </div>

            <div className="form-group">
              <label htmlFor="image">{messages.imageLabel}</label>
              <input
                ref={fileRef}
                type="file"
                id="image"
                name="image"
                accept="image/*"
                onChange={() => setHasFile(Boolean(fileRef.current?.files?.length))}
              />
              <div className="helper-text"><i className="fa-solid fa-image" aria-hidden="true" /> {messages.imageHelper}</div>
              <div className="image-preview-container">
                {previewSrc && <img id="image-preview" alt="" src={previewSrc} style={{ maxWidth: '100%' }} />}
              </div>
              {(previewSrc || hasFile) && (
                <button
                  type="button"
                  className="btn btn-danger"
                  id="removeImage"
                  onClick={() => {
                    if (fileRef.current) fileRef.current.value = '';
                    setHasFile(false);
                    set('facebookImageUrl', '');
                  }}
                >
                  <i className="fa-solid fa-trash" aria-hidden="true" /> {messages.removeImage}
                </button>
              )}
            </div>

            <StepNavigation messages={messages} onPrevious={previous} onNext={next} />
          </div>

          {/* 3 — time and place */}
          <div className={`form-page${step === 3 ? ' active' : ''}`} id="page-3" hidden={step !== 3}>
            <div className="page-header">
              <h2>                  <i className="fa-solid fa-calendar" aria-hidden="true" /> {messages.timePlaceTitle}</h2>
              <p>{messages.timePlaceLead}</p>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label id="date-label" htmlFor="date">{messages.dateLabel}<span className="required-asterisk">*</span></label>
                <DateField
                  id="date"
                  name="date"
                  value={fields.date}
                  onChange={(value) => set('date', value)}
                  required
                  describedBy="date-helper"
                  labelledBy="date-label"
                />
                <div className="helper-text" id="date-helper">
                  <i className="fa-solid fa-calendar-days" aria-hidden="true" /> {messages.dateFormatHelper}
                </div>
              </div>
              <div className="form-group">
                <label htmlFor="start_time">{messages.startTimeLabel}<span className="required-asterisk">*</span></label>
                <DateField
                  id="start_time"
                  name="start_time"
                  mode="time"
                  value={fields.startTime}
                  onChange={(value) => set('startTime', value)}
                  required
                  label={messages.startTimeLabel}
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="end_time">{messages.endTimeLabel}</label>
              <DateField
                id="end_time"
                name="end_time"
                mode="time"
                value={fields.endTime}
                onChange={(value) => set('endTime', value)}
                label={messages.endTimeLabel}
              />
              <div className="helper-text"><i className="fa-solid fa-clock" aria-hidden="true" /> {messages.endTimeHelper}</div>
            </div>

            <div className="form-group">
              <label htmlFor="type">{messages.typeLabel}<span className="required-asterisk">*</span></label>
              <select
                id="type"
                name="type"
                value={fields.eventType}
                required
                onChange={(event) => set('eventType', event.target.value)}
              >
                <option value="" disabled>{messages.typePlaceholder}</option>
                <option value="paikallaan">{messages.typeOption.paikallaan}</option>
                <option value="marssi">{messages.typeOption.marssi}</option>
                <option value="muut">{messages.typeOption.muut}</option>
              </select>
            </div>

            {fields.eventType === 'marssi' && (
              // `.optional-section` is display:none in submit.css; the modifier
              // is what makes the chosen route section visible.
              <div className="optional-section optional-section--open" id="march-route-container">
                <div className="form-group">
                  <label htmlFor="route">{messages.routeLabel}</label>
                  <textarea
                    id="route"
                    name="route"
                    value={fields.route}
                    placeholder={messages.routePlaceholder}
                    onChange={(event) => set('route', event.target.value)}
                  />
                  <div className="helper-text"><i className="fa-solid fa-route" aria-hidden="true" /> {messages.routeHelper}</div>
                </div>
                <div className="form-group">
                  <label htmlFor="route-preview">{messages.routePreviewLabel}</label>
                  <div id="route-preview" className="editor-container" style={{ minHeight: 60, padding: '0.75rem' }}>
                    {routeItems.length === 0
                      ? <em style={{ color: 'var(--color-text-secondary)' }}>{messages.routePreviewEmpty}</em>
                      : <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>{routeItems.map((item) => <li key={item}>{item}</li>)}</ul>}
                  </div>
                  <div className="helper-text"><i className="fa-solid fa-eye" aria-hidden="true" /> {messages.routePreviewHelper}</div>
                </div>
              </div>
            )}

            <CitySelect
              id="city"
              cities={cities}
              value={fields.city}
              onChange={(city) => set('city', city)}
              required
              messages={messages}
              label={messages.cityLabel}
            />

            <div className="form-group">
              <label htmlFor="address">{messages.addressLabel}<span className="required-asterisk">*</span></label>
              <input
                type="text"
                id="address"
                name="address"
                value={fields.address}
                placeholder={messages.addressPlaceholder}
                required
                aria-invalid={invalid.has('address') || undefined}
                onChange={(event) => set('address', event.target.value)}
              />
              <div className="helper-text"><i className="fa-solid fa-map-marker-alt" aria-hidden="true" /> {messages.addressHelper}</div>
            </div>

            <StepNavigation messages={messages} onPrevious={previous} onNext={next} />
          </div>

          {/* 4 — organizers */}
          <div className={`form-page${step === 4 ? ' active' : ''}`} id="page-4" hidden={step !== 4}>
            <div className="page-header">
              <h2><i className="fa-solid fa-users-gear" aria-hidden="true" /> {messages.organizersTitle}</h2>
              <p>{messages.organizersLead}</p>
            </div>
            <OrganizerList
              organizers={organizers}
              onChange={setOrganizers}
              orgSearchUrl={props.orgSearchUrl}
              messages={messages}
            />
            <div className="helper-text" style={{ marginTop: '1.5rem' }}>
              <i className="fa-solid fa-heart" aria-hidden="true" /> {messages.organizerHelper}
            </div>

            <StepNavigation messages={messages} onPrevious={previous} onNext={next} />
          </div>

          {/* 5 — contact and terms */}
          <div className={`form-page${step === 5 ? ' active' : ''}`} id="page-5" hidden={step !== 5}>
            <div className="page-header">
              <h2><i className="fa-solid fa-user-check" aria-hidden="true" /> {messages.contactTitle}</h2>
              <p>{messages.contactLead}</p>
            </div>

            <div className="form-group">
              <label htmlFor="submitter_role">{messages.roleLabel}<span className="required-asterisk">*</span></label>
              <input
                type="text"
                id="submitter_role"
                name="submitter_role"
                value={fields.submitterRole}
                placeholder={messages.rolePlaceholder}
                required
                onChange={(event) => set('submitterRole', event.target.value)}
              />
              <div className="helper-text"><i className="fa-solid fa-id-badge" aria-hidden="true" /> {messages.roleHelper}</div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="submitter_name">{messages.nameLabel}<span className="required-asterisk">*</span></label>
                <input
                  type="text"
                  id="submitter_name"
                  name="submitter_name"
                  value={fields.submitterName}
                  placeholder={messages.namePlaceholder}
                  required
                  onChange={(event) => set('submitterName', event.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="submitter_email">{messages.emailLabel}<span className="required-asterisk">*</span></label>
                <input
                  type="email"
                  id="submitter_email"
                  name="submitter_email"
                  value={fields.submitterEmail}
                  placeholder={messages.emailPlaceholder}
                  required
                  aria-invalid={invalid.has('submitterEmail') || undefined}
                  onChange={(event) => set('submitterEmail', event.target.value)}
                />
              </div>
            </div>

            <div className="helper-text" style={{ marginBottom: '2rem' }}>
              <i className="fa-solid fa-shield-halved" aria-hidden="true" /> {messages.contactHelper}
            </div>

            <div className="checkbox-group">
              <input
                type="checkbox"
                id="accept_terms"
                name="accept_terms"
                checked={fields.acceptTerms}
                required
                aria-invalid={invalid.has('acceptTerms') || undefined}
                onChange={(event) => set('acceptTerms', event.target.checked)}
              />
              <label htmlFor="accept_terms">
                {messages.acceptTermsPrefix}{' '}
                <a href={props.termsUrl} target="_blank" rel="noreferrer">{messages.termsLink}</a>{' '}
                {messages.acceptTermsAnd}{' '}
                <a href={props.privacyUrl} target="_blank" rel="noreferrer">{messages.privacyLink}</a>.
                <span className="required-asterisk">*</span>
              </label>
            </div>

            <div className="form-navigation">
              <button type="button" className="btn btn-secondary" onClick={previous}>
                <i className="fa-solid fa-arrow-left" aria-hidden="true" /> {messages.previous}
              </button>
              <div className="btn-nav-spacer" />
              <button type="submit" id="submit-form" className={`btn btn-success${submitting ? ' loading' : ''}`} disabled={submitting}>
                <i className="fa-solid fa-paper-plane" aria-hidden="true" />
                {submitting ? messages.sending : messages.submit}
              </button>
            </div>
          </div>

          {/* 6 — delivered */}
          <div className={`form-page${step === 6 ? ' active' : ''}`} id="page-6" hidden={step !== 6}>
            <div className="success-page">
              <div className="success-icon"><i className="fa-solid fa-check" aria-hidden="true" /></div>
              <h2>{messages.successTitle}</h2>
              <p>{messages.successBody}</p>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap', marginTop: '2rem' }}>
                <a href={props.homeUrl} className="btn btn-primary">
                  <i className="fa-solid fa-home" aria-hidden="true" /> {messages.backHome}
                </a>
                <a href={action} className="btn btn-secondary">
                  <i className="fa-solid fa-plus" aria-hidden="true" /> {messages.newEvent}
                </a>
              </div>
            </div>
          </div>

        </div>
      </form>

      <dialog className="modal user-modal" id="submitConflictModal" ref={conflictRef} aria-labelledby="submitConflictModalLabel">
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h2 className="modal-title fs-5" id="submitConflictModalLabel">{messages.conflictTitle}</h2>
              <button type="button" className="btn-close" aria-label={messages.conflictCancel} onClick={() => closeConflict(false)} />
            </div>
            <div className="modal-body">
              <p id="submit-conflict-message">{conflict?.message || messages.conflictLead}</p>
              <p>{messages.conflictLead}</p>
              <h3 className="h6">{messages.conflictMatches}</h3>
              <ol id="submit-conflict-matches" className="user-conflict-list">
                {(conflict?.demos ?? []).slice(0, 5).map((demo, index) => (
                  <li key={`${demo.title ?? ''}-${index}`}>
                    {[demo.title, demo.date, demo.address].filter(Boolean).join(' | ')}
                  </li>
                ))}
              </ol>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" id="submit-conflict-cancel" onClick={() => closeConflict(false)}>
                {messages.conflictCancel}
              </button>
              <button type="button" className="btn btn-primary" id="submit-conflict-confirm" onClick={() => closeConflict(true)}>
                {messages.conflictConfirm}
              </button>
            </div>
          </div>
        </div>
      </dialog>

      <div className="submit-support">
        <div className="page-header">
          <h2><i className="fa-solid fa-life-ring" aria-hidden="true" /> {messages.supportTitle}</h2>
          <p>{messages.supportLead}</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <a href={props.contactUrl} className="btn btn-secondary">
            <i className="fa-solid fa-envelope" aria-hidden="true" /> {messages.supportContact}
          </a>
          <a href={props.infoUrl} className="btn btn-secondary">
            <i className="fa-solid fa-circle-info" aria-hidden="true" /> {messages.supportInfo}
          </a>
        </div>
      </div>
    </div>
  );
}

/** Prev/next controls rendered inside each input step. */
function StepNavigation({ messages, onPrevious, onNext }: {
  messages: SubmitPageProps['messages'];
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <div className="form-navigation">
      <button type="button" className="btn btn-secondary" onClick={onPrevious}>
        <i className="fa-solid fa-arrow-left" aria-hidden="true" /> {messages.previous}
      </button>
      <div className="btn-nav-spacer" />
      <button type="button" className="btn btn-primary" onClick={onNext}>
        {messages.next} <i className="fa-solid fa-arrow-right" aria-hidden="true" />
      </button>
    </div>
  );
}

function newOrganizer(): Organizer {
  return {
    key: `org-${Math.random().toString(36).slice(2)}`,
    name: '',
    email: '',
    website: '',
    isPrivate: false,
    showName: true,
    showEmail: true,
  };
}
