import { useEffect, useRef, useState } from 'react';
import type { Organizer, SubmitMessages } from './types';
import { MAX_ORGANIZERS } from './draft';

type SearchResult = { name?: string; email?: string; description?: string; website?: string };

type OrganizerListProps = {
  organizers: Organizer[];
  onChange: (organizers: Organizer[]) => void;
  orgSearchUrl: string;
  messages: SubmitMessages;
};

/**
 * Organizer rows plus the organization lookup.
 *
 * The submitted field names (`organizer_name_1`, ...) and the "private hides the
 * email" rule are unchanged; `_collect_submission_organizers` on the server
 * relies on the index-suffixed keys.
 */
export function OrganizerList({ organizers, onChange, orgSearchUrl, messages }: OrganizerListProps) {
  const update = (index: number, patch: Partial<Organizer>) => {
    onChange(organizers.map((row, position) => (position === index ? { ...row, ...patch } : row)));
  };

  const remove = (index: number) => {
    onChange(organizers.filter((_row, position) => position !== index));
  };

  const add = () => {
    if (organizers.length >= MAX_ORGANIZERS) return;
    onChange([
      ...organizers,
      { key: `org-${Date.now()}-${organizers.length}`, name: '', email: '', website: '', isPrivate: false, showName: true, showEmail: true },
    ]);
  };

  return (
    <>
      <div className="organizer-list">
        {organizers.map((organizer, index) => (
          <OrganizerCard
            key={organizer.key}
            organizer={organizer}
            index={index + 1}
            messages={messages}
            orgSearchUrl={orgSearchUrl}
            onChange={(patch) => update(index, patch)}
            onRemove={organizers.length > 1 ? () => remove(index) : undefined}
          />
        ))}
      </div>
      <button type="button" className="add-organizer-button" onClick={add} disabled={organizers.length >= MAX_ORGANIZERS}>
        <i className="fa-solid fa-plus-circle" aria-hidden="true" /> {messages.addOrganizer}
      </button>
    </>
  );
}

type OrganizerCardProps = {
  organizer: Organizer;
  index: number;
  messages: SubmitMessages;
  orgSearchUrl: string;
  onChange: (patch: Partial<Organizer>) => void;
  onRemove?: () => void;
};

function OrganizerCard({ organizer, index, messages, orgSearchUrl, onChange, onRemove }: OrganizerCardProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'empty' | 'error'>('idle');
  const [expanded, setExpanded] = useState(false);
  const requestRef = useRef<AbortController | null>(null);

  // Cancel an in-flight lookup when the card unmounts.
  useEffect(() => () => requestRef.current?.abort(), []);

  const runSearch = async (value: string) => {
    const needle = value.trim();
    requestRef.current?.abort();
    if (needle.length < 2) {
      setResults(null);
      setStatus('idle');
      setExpanded(false);
      return;
    }
    const controller = new AbortController();
    requestRef.current = controller;
    setStatus('loading');
    try {
      const response = await fetch(`${orgSearchUrl}?q=${encodeURIComponent(needle)}`, { signal: controller.signal });
      if (!response.ok) throw new Error(`Organization search failed (${response.status})`);
      const data: unknown = await response.json();
      if (!Array.isArray(data)) throw new Error('Organization search returned invalid data');
      if (controller.signal.aborted) return;
      setResults(data as SearchResult[]);
      setStatus(data.length ? 'idle' : 'empty');
      setExpanded(true);
    } catch (error) {
      if ((error as Error).name === 'AbortError') return;
      console.error('Error searching organizations:', error);
      setResults(null);
      setStatus('error');
      setExpanded(true);
    }
  };

  const select = (result: SearchResult) => {
    onChange({
      name: result.name ?? '',
      email: result.email ?? '',
      website: result.website ?? '',
      isPrivate: false,
      showName: true,
      showEmail: true,
    });
    setQuery('');
    setResults(null);
    setStatus('idle');
    setExpanded(false);
  };

  const togglePrivate = (isPrivate: boolean) => {
    // A private submitter never exposes an email address.
    onChange(isPrivate
      ? { isPrivate, showEmail: false }
      : { isPrivate, showName: true, showEmail: true });
  };

  const field = (name: string) => `organizer_${name}_${index}`;
  const helpId = `org_search_help_${index}`;
  const listId = `org_search_results_${index}`;
  const message = status === 'empty'
    ? messages.organizerSearchEmpty
    : status === 'error'
      ? messages.organizerSearchError
      : '';

  return (
    <div className="organizer-card" id={`organizer-${index}`}>
      <div className="organizer-header">
        <h3><i className="fa-solid fa-building" aria-hidden="true" /> {messages.organizerLabel} {index}</h3>
        {onRemove && (
          <button type="button" className="btn-remove" onClick={onRemove} aria-label={`${messages.removeOrganizer} ${index}`}>
            <i className="fa-solid fa-times" aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="form-group">
        <label htmlFor={field('search')}>{messages.organizerSearchLabel}</label>
        <div className="user-autocomplete">
          <input
            type="search"
            className="user-autocomplete__control"
            id={field('search')}
            value={query}
            placeholder={messages.organizerSearchPlaceholder}
            autoComplete="off"
            maxLength={100}
            aria-expanded={expanded}
            aria-controls={listId}
            aria-describedby={helpId}
            onChange={(event) => {
              setQuery(event.target.value);
              void runSearch(event.target.value);
            }}
          />
          <ul
            id={listId}
            className="user-autocomplete__results"
            aria-label={messages.organizerSearchLabel}
            aria-live="polite"
            aria-busy={status === 'loading'}
            hidden={!expanded}
          >
            {message && <li className={`user-autocomplete__message${status === 'error' ? ' user-autocomplete__message--error' : ''}`}>{message}</li>}
            {(results ?? []).map((result, position) => (
              <li key={`${result.name ?? ''}-${position}`} className="user-autocomplete__item">
                <button type="button" className="user-autocomplete__option" onClick={() => select(result)}>
                  <span className="user-autocomplete__copy">
                    <strong className="user-autocomplete__name">{result.name ?? ''}</strong>
                    {result.email && <small className="user-autocomplete__detail">{result.email}</small>}
                    {result.description && <small className="user-autocomplete__detail">{result.description}</small>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <p className="user-autocomplete__help" id={helpId}>{messages.organizerSearchHelp}</p>
      </div>

      <div className="form-group">
        <label htmlFor={field('name')}>{messages.organizerName}<span className="required-asterisk">*</span></label>
        <input
          type="text"
          id={field('name')}
          name={field('name')}
          value={organizer.name}
          placeholder={messages.organizerName}
          maxLength={200}
          required
          onChange={(event) => onChange({ name: event.target.value })}
        />
      </div>
      <div className="form-group">
        <label htmlFor={field('website')}>{messages.organizerWebsite}</label>
        <input
          type="url"
          id={field('website')}
          name={field('website')}
          value={organizer.website}
          placeholder="https://example.com"
          maxLength={2048}
          onChange={(event) => onChange({ website: event.target.value })}
        />
      </div>
      <div className="form-group">
        <label htmlFor={field('email')}>{messages.organizerEmail}</label>
        <input
          type="email"
          id={field('email')}
          name={field('email')}
          value={organizer.email}
          placeholder="email@example.com"
          maxLength={254}
          onChange={(event) => onChange({ email: event.target.value })}
        />
      </div>
      <div className="privacy-options">
        <label className="privacy-checkbox">
          <input
            type="checkbox"
            id={field('is_private')}
            name={field('is_private')}
            checked={organizer.isPrivate}
            onChange={(event) => togglePrivate(event.target.checked)}
          />
          {messages.organizerPrivate}
        </label>
        <label className="privacy-checkbox">
          <input
            type="checkbox"
            id={field('show_name')}
            name={field('show_name')}
            checked={organizer.showName}
            onChange={(event) => onChange({ showName: event.target.checked })}
          />
          {messages.organizerShowName}
        </label>
        <label className="privacy-checkbox">
          <input
            type="checkbox"
            id={field('show_email')}
            name={field('show_email')}
            checked={organizer.showEmail}
            onChange={(event) => onChange({ showEmail: event.target.checked })}
          />
          {messages.organizerShowEmail}
        </label>
        <p className="privacy-hint">{messages.organizerPrivacyHint}</p>
      </div>
    </div>
  );
}
