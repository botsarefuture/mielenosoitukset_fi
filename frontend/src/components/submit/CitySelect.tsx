import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import type { SubmitMessages } from './types';

/**
 * City picker.
 *
 * Replaces the `paikkakunta-dropdown.html` partial (our own inline script), so it
 * is native React. The trigger is styled as a normal form control rather than a
 * button, and the option list is an anchored panel with its own stacking context;
 * previously only `.dropdown-content` was absolutely positioned, so the panel
 * escaped to an unrelated ancestor and looked like it never opened.
 *
 * The submitted control keeps the legacy id/name because the server reads
 * `request.form["city"]`.
 */
type CitySelectProps = {
  id: string;
  cities: string[];
  value: string;
  onChange: (city: string) => void;
  required?: boolean;
  messages: SubmitMessages;
  label: string;
  describedBy?: string;
};

export function CitySelect({
  id, cities, value, onChange, required, messages, label, describedBy,
}: CitySelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listId = useId();

  const visible = useMemo(() => {
    const needle = query.trim().toLocaleUpperCase('fi');
    if (!needle) return cities;
    return cities.filter((city) => city.toLocaleUpperCase('fi').includes(needle));
  }, [cities, query]);

  useEffect(() => {
    if (!open) return;
    searchRef.current?.focus();
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const choose = (city: string) => {
    onChange(city);
    setOpen(false);
    setQuery('');
    triggerRef.current?.focus();
  };

  const onSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!visible.length) return;
      setActiveIndex((current) => {
        const next = event.key === 'ArrowDown' ? current + 1 : current - 1;
        return (next + visible.length) % visible.length;
      });
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      if (visible[activeIndex]) choose(visible[activeIndex]);
    }
  };

  return (
    <div className="form-group">
      <label id={`${id}-label`} htmlFor={`${id}-trigger`}>
        {label}{required && <span className="required-asterisk" aria-hidden="true">*</span>}
      </label>
      <div className="submit-city" ref={containerRef}>
        <button
          type="button"
          id={`${id}-trigger`}
          ref={triggerRef}
          className={`submit-city__trigger${value ? '' : ' submit-city__trigger--empty'}`}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-labelledby={`${id}-label`}
          aria-describedby={describedBy}
          onClick={() => setOpen((current) => !current)}
        >
          <span>{value || messages.cityPlaceholder}</span>
          <i className="fa-solid fa-chevron-down" aria-hidden="true" />
        </button>

        {open && (
          <div className="submit-city__panel">
            <input
              ref={searchRef}
              type="text"
              className="submit-city__search"
              value={query}
              placeholder={messages.citySearch}
              aria-label={messages.citySearch}
              aria-controls={listId}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={onSearchKeyDown}
            />
            <ul className="submit-city__list" role="listbox" id={listId} ref={listRef} aria-labelledby={`${id}-label`}>
              {visible.map((city, index) => (
                <li key={city} role="none">
                  <button
                    type="button"
                    role="option"
                    aria-selected={city === value}
                    className={`submit-city__option${index === activeIndex ? ' is-active' : ''}${city === value ? ' is-selected' : ''}`}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => choose(city)}
                  >
                    {city}
                  </button>
                </li>
              ))}
              {visible.length === 0 && <li className="submit-city__empty">{messages.cityNoMatch}</li>}
            </ul>
          </div>
        )}
      </div>
      <input
        type="hidden"
        id={`${id}-value`}
        name="city"
        value={value}
        required={required}
        aria-describedby={describedBy}
      />
    </div>
  );
}
