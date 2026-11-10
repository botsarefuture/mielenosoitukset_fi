import { useEffect, useMemo, useRef, useState } from 'react';
import flatpickr from 'flatpickr';
import type { Instance } from 'flatpickr/dist/types/instance';
import type { Locale } from 'flatpickr/dist/types/locale';
import type { ListingProps } from './types';

export type ListingFilters = {
  search: string; city: string; location: string; date_start: string; date_end: string;
};

export function displayDate(iso: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso.split('-').reverse().join('.') : iso;
}

function calendarDate(value: string): Date | undefined {
  const match = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(value.trim());
  if (!match) return undefined;
  const [day, month, year] = match.slice(1).map(Number);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : undefined;
}

export function isoDate(value: string): string | null {
  if (!value.trim()) return '';
  const date = calendarDate(value);
  return date ? `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` : null;
}

function DateField({ edge, value, change, props, invalid }: {
  edge: 'start' | 'end'; value: string; change(value: string): void; props: ListingProps; invalid: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const calendar = useRef<Instance | null>(null);
  const latest = useRef(change);
  latest.current = change;
  useEffect(() => {
    const node = input.current!;
    const format = (date: Date, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat(props.locale,
      { ...options, timeZone: 'UTC' }).format(date);
    const weekdays = Array.from({ length: 7 }, (_, index) => new Date(Date.UTC(2024, 0, 7 + index, 12)));
    const months = Array.from({ length: 12 }, (_, index) => new Date(Date.UTC(2024, index, 1, 12)));
    // Preserve invalid manual input until the React form can explain the error.
    const guard = (event: Event) => {
      if (node.value && !calendarDate(node.value)) event.stopImmediatePropagation();
    };
    node.addEventListener('blur', guard, true);
    const picker = flatpickr(node, {
      dateFormat: 'd.m.Y', allowInput: true, disableMobile: true,
      parseDate: value => calendarDate(value) ?? new Date(Number.NaN),
      locale: {
        firstDayOfWeek: 1, yearAriaLabel: props.messages.year, monthAriaLabel: props.messages.month,
        weekdays: { shorthand: weekdays.map(date => format(date, { weekday: 'short' })) as Locale['weekdays']['shorthand'],
          longhand: weekdays.map(date => format(date, { weekday: 'long' })) as Locale['weekdays']['longhand'] },
        months: { shorthand: months.map(date => format(date, { month: 'short' })) as Locale['months']['shorthand'],
          longhand: months.map(date => format(date, { month: 'long' })) as Locale['months']['longhand'] },
      },
      onChange: (_, selected) => latest.current(selected),
      onReady: (_, __, instance) => {
        instance.calendarContainer.classList.add('public-date-calendar');
        instance.calendarContainer.id = `${node.id}-calendar`;
        instance.calendarContainer.setAttribute('role', 'dialog');
        instance.calendarContainer.setAttribute('aria-label', node.labels?.[0]?.textContent ?? '');
      },
      onOpen: () => node.setAttribute('aria-expanded', 'true'),
      onClose: () => node.setAttribute('aria-expanded', 'false'),
    });
    calendar.current = picker;
    return () => { node.removeEventListener('blur', guard, true); picker.destroy(); calendar.current = null; };
  }, [props.locale, props.messages.year, props.messages.month]);
  useEffect(() => {
    const picker = calendar.current;
    if (picker && (!value || calendarDate(value))) picker.setDate(value || [], false, 'd.m.Y');
  }, [value]);
  const label = edge === 'start' ? props.messages.startDate : props.messages.endDate;
  return <div className="public-search-field"><label htmlFor={`date_${edge}`}>{label}</label>
    <input ref={input} type="text" name={`display_date_${edge}`} id={`date_${edge}`}
      value={value} onChange={event => change(event.target.value)} placeholder={label} inputMode="numeric"
      role="combobox" aria-haspopup="dialog" aria-controls={`date_${edge}-calendar`} aria-expanded="false"
      aria-invalid={invalid} aria-describedby="date-error" onKeyDown={event => {
        const picker = calendar.current;
        if (event.key === 'ArrowDown' && picker) {
          event.preventDefault(); picker.open();
          picker.calendarContainer.querySelector<HTMLElement>('.flatpickr-day.selected, .flatpickr-day.today, .flatpickr-day:not(.flatpickr-disabled)')?.focus();
        }
        if (event.key === 'Escape') picker?.close();
      }} />
  </div>;
}

export function ReactSearchFilters({ props, values, change, submit, removeCity }: {
  props: ListingProps; values: ListingFilters; change(values: ListingFilters): void;
  submit(values: ListingFilters): void; removeCity(city: string): void;
}) {
  const text = props.messages;
  const [cityInput, setCityInput] = useState('');
  const [active, setActive] = useState(-1);
  const [focused, setFocused] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const hasSecondaryValues = Boolean((!props.fixed.city && values.city) || values.location
    || (!props.fixed.today && (values.date_start || values.date_end)) || cityInput);
  useEffect(() => { setHydrated(true); }, []);
  useEffect(() => {
    if (hasSecondaryValues) setFiltersOpen(true);
  }, [hasSecondaryValues, values.city, values.location, values.date_start, values.date_end, cityInput]);
  useEffect(() => {
    const start = isoDate(values.date_start), end = isoDate(values.date_end);
    if (start !== null && end !== null && !(start && end && start > end)) setInvalid(false);
  }, [values.date_start, values.date_end]);
  const cities = values.city.split(',').map(city => city.trim()).filter(Boolean);
  const matches = useMemo(() => cityInput.trim() ? props.cities.filter(city =>
    !cities.some(selected => selected.toLocaleLowerCase() === city.toLocaleLowerCase())
    && city.toLocaleLowerCase().includes(cityInput.trim().toLocaleLowerCase()))
    .sort((left, right) => left.localeCompare(right, props.locale)).slice(0, 20) : [], [props.cities, props.locale, cityInput, values.city]);
  const showSuggestions = focused && matches.length > 0;
  function validSubmit(next: ListingFilters) {
    const start = isoDate(next.date_start), end = isoDate(next.date_end);
    const valid = start !== null && end !== null && !(start && end && start > end);
    setInvalid(!valid);
    if (valid) submit(next);
  }
  function choose(city: string) {
    const next = { ...values, city: [...cities, city].join(',') };
    change(next); setCityInput(''); setActive(-1);
    if (props.fixed.tag) validSubmit(next);
  }
  return <form method="GET" className="search-form public-search-form" id="search-form"
    onSubmit={event => { event.preventDefault(); validSubmit(values); }}>
    <div className="public-search-field"><label htmlFor="demo-search">{text.search}</label>
      <input type="text" id="demo-search" name="search" value={values.search}
        onChange={event => change({ ...values, search: event.target.value })} placeholder={text.searchPlaceholder} />
    </div>
    {hydrated && <button type="button" className="detail-button public-search-toggle"
      aria-expanded={filtersOpen} aria-controls="secondary-filters" onClick={() => setFiltersOpen(open => !open)}>
      {text.filters}
    </button>}
    <div id="secondary-filters" className="public-search-secondary" data-collapsed={hydrated && !filtersOpen}>
    {props.fixed.city ? <input type="hidden" name="city" value={props.fixed.city} /> :
      <div className="public-search-field"><label htmlFor="city_input">{text.city}</label>
        <input type="text" id="city_input" value={cityInput} placeholder={text.city} autoComplete="off"
          role="combobox" aria-autocomplete="list" aria-expanded={showSuggestions} aria-controls="city_suggestions"
          aria-activedescendant={showSuggestions && active >= 0 ? `city-suggestion-${active}` : undefined}
          onChange={event => { setCityInput(event.target.value); setActive(-1); }}
          onFocus={() => setFocused(true)} onBlur={() => { setFocused(false); setActive(-1); }}
          onKeyDown={event => {
            if (event.key === 'Escape') { setFocused(false); setActive(-1); }
            if (event.key === 'ArrowDown' && matches.length) {
              event.preventDefault(); setFocused(true); setActive(index => Math.min(index + 1, matches.length - 1));
            }
            if (event.key === 'ArrowUp' && matches.length) { event.preventDefault(); setActive(index => Math.max(index - 1, 0)); }
            if (event.key === 'Enter' && showSuggestions && active >= 0) { event.preventDefault(); choose(matches[active]); }
          }} />
        <input type="hidden" name="city" id="city" value={values.city} />
        <div className={`suggestions${showSuggestions ? ' show' : ''}`} id="city_suggestions" role="listbox" aria-label={text.city}>
          {showSuggestions && matches.map((city, index) => <div key={city} className="suggestion-item"
            id={`city-suggestion-${index}`} role="option" aria-selected={active === index}
            onPointerDown={event => event.preventDefault()} onClick={() => choose(city)}>{city}</div>)}
        </div>
      </div>}
    <div className="public-search-field"><label htmlFor="demo-location">{text.location}</label>
      <input type="text" id="demo-location" name="location" value={values.location}
        onChange={event => change({ ...values, location: event.target.value })} placeholder={text.location} />
    </div>
    {!props.fixed.today && <div className="date-range public-search-dates">
      <DateField edge="start" value={values.date_start} change={value => change({ ...values, date_start: value })} props={props} invalid={invalid} />
      <DateField edge="end" value={values.date_end} change={value => change({ ...values, date_end: value })} props={props} invalid={invalid} />
    </div>}
    </div>
    <div className="date-error" id="date-error" role="alert" hidden={!invalid}>{text.dateError}</div>
    <input type="hidden" name="date_start" id="iso_date_start" value={isoDate(values.date_start) ?? ''} />
    <input type="hidden" name="date_end" id="iso_date_end" value={isoDate(values.date_end) ?? ''} />
    <button type="submit" className="detail-button detail-button--primary public-search-submit">{text.submitSearch}</button>
    <div className="filters" id="filters" aria-live="polite">{!props.fixed.city && cities.map(city =>
      <div key={city} className="public-filter-chip"><span>{text.city}: {city}</span>
        <button type="button" className="public-filter-chip__remove" aria-label={`${text.removeFilter}: ${city}`}
          onClick={() => removeCity(city)}>×</button></div>)}</div>
  </form>;
}
