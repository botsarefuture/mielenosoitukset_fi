import type { ListingProps } from './types';

/** Uncontrolled inputs integrate the existing localized date/city widgets. */
export function SearchFilters({ props }: { props: ListingProps }) {
  const text = props.messages;
  return <form method="GET" className="search-form public-search-form" id="search-form"
    data-date-year-label={text.year} data-date-month-label={text.month}>
    <div className="public-search-field"><label htmlFor="demo-search">{text.search}</label>
      <input type="text" id="demo-search" name="search" placeholder={text.searchPlaceholder} />
    </div>
    {props.fixed.city ? <input type="hidden" name="city" defaultValue={props.fixed.city} /> :
      <div className="public-search-field"><label htmlFor="city_input">{text.city}</label>
        <input type="text" id="city_input" placeholder={text.city} autoComplete="off" role="combobox"
          aria-autocomplete="list" aria-expanded="false" aria-controls="city_suggestions" />
        <input type="hidden" name="city" id="city" />
        <div className="suggestions" id="city_suggestions" role="listbox" aria-label={text.city} />
      </div>}
    <div className="public-search-field"><label htmlFor="demo-location">{text.location}</label>
      <input type="text" id="demo-location" name="location" placeholder={text.location} />
    </div>
    <div className="date-range public-search-dates">
      <div className="public-search-field"><label htmlFor="date_start">{text.startDate}</label>
        <input type="text" name="display_date_start" id="date_start" aria-describedby="date-error" placeholder={text.startDate} />
      </div>
      <div className="public-search-field"><label htmlFor="date_end">{text.endDate}</label>
        <input type="text" name="display_date_end" id="date_end" aria-describedby="date-error" placeholder={text.endDate} />
      </div>
    </div>
    <div className="date-error" id="date-error" role="alert">{text.dateError}</div>
    <input type="hidden" name="date_start" id="iso_date_start" /><input type="hidden" name="date_end" id="iso_date_end" />
    <button type="submit" className="button button-primary public-search-submit">{text.submitSearch}</button>
    <div className="filters" id="filters" aria-live="polite" />
  </form>;
}
