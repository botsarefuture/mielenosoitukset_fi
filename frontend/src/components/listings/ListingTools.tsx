import { SearchFilters } from './SearchFilters';
import type { ListingProps } from './types';

export function ListingTools({ props }: { props: ListingProps }) {
  const Heading = props.headingLevel === 2 ? 'h2' : 'h1';
  return <section className="public-list-tools" aria-labelledby="listing-title">
    <header className="public-list-heading">
      <Heading id="listing-title">{props.title}</Heading>
      <div className="public-list-actions">
        {props.rssUrl && <a className="public-list-feed" href={props.rssUrl}><i className="fa-solid fa-rss" aria-hidden="true" />RSS</a>}
        {Object.keys(props.fixed).length > 0 && <a className="public-list-all" href={props.allEventsUrl}><i className="fa-solid fa-arrow-left" aria-hidden="true" />{props.messages.allEvents}</a>}
      </div>
    </header>
    <SearchFilters props={props} />
  </section>;
}
