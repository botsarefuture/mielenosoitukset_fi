import { useEffect, useRef } from 'react';
import flatpickr from 'flatpickr';
import type { Instance } from 'flatpickr/dist/types/instance';
import type { Options } from 'flatpickr/dist/types/options';
import 'flatpickr/dist/flatpickr.min.css';

/**
 * Calendar/time picker.
 *
 * Uses Flatpickr for a calendar that opens on click in every browser, but
 * deliberately *without* `altInput`. That option left the source input visible
 * beside a second, unlabelled control, so every field rendered twice and the
 * required attribute lived on the hidden copy. Here the visible text input is
 * owned by Flatpickr and a separate hidden input carries the ISO value the
 * server expects, so there is exactly one control per field.
 */
type SevenDays = [string, string, string, string, string, string, string];
type TwelveMonths = [string, string, string, string, string, string, string, string, string, string, string, string];

const FINNISH_LOCALE = {
  firstDayOfWeek: 1,
  weekdays: {
    shorthand: ['Su', 'Ma', 'Ti', 'Ke', 'To', 'Pe', 'La'] as SevenDays,
    longhand: ['Sunnuntai', 'Maanantai', 'Tiistai', 'Keskiviikko', 'Torstai', 'Perjantai', 'Lauantai'] as SevenDays,
  },
  months: {
    shorthand: ['Tam', 'Hel', 'Mar', 'Huht', 'Tou', 'Kes', 'Hele', 'Elo', 'Syys', 'Lok', 'Marr', 'Jou'] as TwelveMonths,
    longhand: [
      'Tammikuu', 'Helmikuu', 'Maaliskuu', 'Huhtikuu', 'Toukokuu', 'Kesäkuu',
      'Heinäkuu', 'Elokuu', 'Syyskuu', 'Lokakuu', 'Marraskuu', 'Joulukuu',
    ] as TwelveMonths,
  },
};

/** `2026-12-24` -> `24.12.2026` for the visible Finnish field. */
export function isoToDisplay(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso.trim());
  return match ? `${match[3]}.${match[2]}.${match[1]}` : '';
}

/** `24.12.2026` or `24.12.26` -> `2026-12-24`; anything else becomes empty. */
export function displayToIso(display: string): string {
  const match = /^(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})$/.exec(display.trim());
  if (!match) return '';
  const [, day, month, rawYear] = match;
  const year = rawYear.length === 2 ? `20${rawYear}` : rawYear;
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
}

type DateFieldProps = {
  id: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  mode?: 'date' | 'time';
  describedBy?: string;
  labelledBy?: string;
  label?: string;
};

export function DateField({
  id, name, value, onChange, required, mode = 'date', describedBy, labelledBy, label,
}: DateFieldProps) {
  const displayRef = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<Instance | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const input = displayRef.current;
    if (!input) return;
    const config: Partial<Options> = mode === 'date'
      ? {
          dateFormat: 'd.m.Y',
          allowInput: true,
          locale: FINNISH_LOCALE,
          onChange: (_dates: Date[], text: string) => onChangeRef.current(displayToIso(text ?? '')),
        }
      : {
          enableTime: true,
          noCalendar: true,
          dateFormat: 'H:i',
          allowInput: true,
          time_24hr: true,
          onChange: (_dates: Date[], text: string) => onChangeRef.current(text ?? ''),
        };

    const picker = flatpickr(input, config) as unknown as Instance;
    picker.calendarContainer?.classList.add('public-date-calendar');
    pickerRef.current = picker;
    return () => {
      picker.destroy();
      pickerRef.current = null;
    };
  }, [mode]);

  // Draft restore and Facebook import set state directly; push it to the widget.
  useEffect(() => {
    const picker = pickerRef.current;
    if (!picker) return;
    const next = mode === 'date' ? isoToDisplay(value) : value;
    if ((picker.input.value ?? '') !== next) picker.setDate(next || '', false);
  }, [value, mode]);

  return (
    <>
      <input
        ref={displayRef}
        type="text"
        id={`${id}-display`}
        className="submit-date-display"
        defaultValue={mode === 'date' ? isoToDisplay(value) : value}
        placeholder={mode === 'date' ? 'pp.kk.vvvv' : 'hh:mm'}
        autoComplete="off"
        required={required}
        aria-describedby={describedBy}
        aria-labelledby={labelledBy}
        aria-label={labelledBy ? undefined : label}
      />
      <input type="hidden" id={id} name={name} value={value} />
    </>
  );
}
