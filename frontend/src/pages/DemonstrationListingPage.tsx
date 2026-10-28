import { useEffect, useRef } from 'react';
import { ListingTools } from '../components/listings/ListingTools';
import { attachListing } from '../components/listings/controller';
import type { ListingProps } from '../components/listings/types';

export function DemonstrationListingPage(props: ListingProps) {
  const element = useRef<HTMLElement>(null);
  const text = props.messages;
  const EmptyHeading = props.headingLevel === 2 ? 'h3' : 'h2';
  useEffect(() => attachListing(element.current!, props), [props]);
  return <section className="public-demonstration-list" ref={element}>
    {props.cover && <img className="public-list-cover" src={props.cover} alt={props.coverAlt} />}
    <ListingTools props={props} />
    <section className="public-list-results" aria-labelledby="listing-title">
      <button id="load-previous-btn" type="button" className="button button-secondary load-more" hidden>{text.previous}</button>
      <div id="demos-grid" className="demos-grid" />
      <p id="listing-result-summary" className="public-listing-summary" role="status" aria-live="polite" aria-atomic="true" hidden data-format={text.summary} />
      <div id="listing-load-error" className="public-listing-summary" hidden>
        <p role="alert">{text.loadError}</p><button type="button" className="button button-secondary">{text.retry}</button>
      </div>
      <div id="no-results" className="no-results-card" hidden>
        <EmptyHeading className="no-results-title">{text.emptyTitle}</EmptyHeading><p className="no-results-text">{text.empty}</p>
        <div className="no-results-action">
          <button type="button" id="clear-filters-btn" className="button button-secondary" hidden>{text.clearFilters}</button>
          <a href={props.submitUrl} className="button button-primary">{text.submitEvent}</a>
        </div>
      </div>
      <button id="load-more-btn" type="button" className="button button-secondary load-more" hidden>{text.loadMore}</button>
    </section>
  </section>;
}
