import type { CardProps } from '../components/listings/DemonstrationCard';
import { SiteHeader } from '../components/header/SiteHeader';
import { DetailScreen } from '../components/detail/DetailScreen';
import { HomePage } from '../pages/HomePage';
import type { HomeData } from '../pages/HomePage';
import type { AppConfig } from './config';
import { detailEndpoint, detailMessages, detailUrls } from './detail';
import type { DetailBootstrap, DetailSeries } from './detail-route';
import { SiteFooter } from './Footer';
import { headerProps } from './header-props';
import { catalog } from './i18n';
import type { AppRoute } from './routes';
import type { SessionSummary } from './session';
import { lazy, Suspense } from 'react';
import type { ListingBootstrap } from './listing';
import type { OrganizationBootstrap } from './organization';
import type { CitiesData } from './cities';
import type { SubmitBootstrap } from './submit';
import type { CalendarBootstrap } from './calendar';

const ListingScreen = lazy(() => import('./ListingScreen'));
const OrganizationScreen = lazy(() => import('./OrganizationScreen'));
const CitiesPage = lazy(() => import('../pages/CitiesPage'));
const TodayScreen = lazy(() => import('./TodayScreen'));
const SubmitScreen = lazy(() => import('./SubmitScreen'));
const CalendarScreen = lazy(() => import('./CalendarScreen'));
const YearCalendarScreen = lazy(() => import('./YearCalendarScreen'));
const GodScreen = lazy(() => import('./GodScreen'));

export type AppProps = {
  config: AppConfig;
  session: SessionSummary;
  route: AppRoute;
  path: string;
  /** Server-resolved event for the detail route; absent on other pages. */
  detail?: DetailBootstrap;
  /** Series navigation for the `/children` route. */
  series?: DetailSeries;
  /** Server-read home batch, so cards paint without a second request. */
  home?: HomeData | null;
  listing?: ListingBootstrap;
  organization?: OrganizationBootstrap;
  cities?: CitiesData | null;
  submission?: SubmitBootstrap;
  calendar?: CalendarBootstrap;
};

function cardProps(config: AppConfig, session: SessionSummary, text: ReturnType<typeof catalog>): CardProps {
  return {
    authenticated: session.authenticated,
    attendanceEndpoint: config.urls.attendance,
    detailUrl: config.urls.detail,
    seriesUrl: config.urls.series,
    tagUrl: config.urls.tag,
    messages: text.cards,
  };
}

/** One public application shell: shared header, routed page content, footer. */
export function App({ config, session, route, path, detail, series, home, listing, organization, cities, submission, calendar }: AppProps) {
  const text = catalog(config.locale);
  return <>
    <SiteHeader {...headerProps(config, session, text, path)} />
    <main className={`container-main-content ${route.name === 'submit' ? 'submit-workspace' : route.name === 'detail' || route.name === 'series' ? 'public-detail-main' : 'public-layout-wide'}`} id="main-content" tabIndex={-1}>
      {route.name === 'god-auth' && <Suspense fallback={<p role="status">Ladataan kirjautumista...</p>}><GodScreen /></Suspense>}
      {route.name === 'calendar' && calendar && <Suspense fallback={<p role="status">Ladataan kalenteria...</p>}>
        <CalendarScreen calendar={calendar} config={config} session={session} />
      </Suspense>}
      {route.name === 'calendar-year' && calendar && <Suspense fallback={<p role="status">Ladataan kalenteria...</p>}>
        <YearCalendarScreen calendar={calendar} />
      </Suspense>}
      {route.name === 'submit' && submission && <Suspense fallback={<p role="status">Ladataan lomaketta...</p>}>
        <SubmitScreen config={config} submission={submission} />
      </Suspense>}
      {route.name === 'cities' && <Suspense fallback={<p role="status">Ladataan kaupunkeja…</p>}>
        <CitiesPage initialData={cities ?? null} endpoint={`${config.apiBase}/cities`} />
      </Suspense>}
      {route.name === 'today' && <Suspense fallback={<p role="status">Ladataan mielenosoituksia…</p>}>
        <TodayScreen city={route.value} listing={listing} config={config} session={session} />
      </Suspense>}
      {route.name === 'organization' && organization && <Suspense fallback={<p role="status">Ladataan organisaatiota...</p>}>
        <OrganizationScreen key={path} organization={organization} config={config} session={session} />
      </Suspense>}
      {route.name === 'listing' && <Suspense fallback={<p role="status">Ladataan mielenosoituksia...</p>}>
        <ListingScreen key={path} route={route} config={config} session={session} listing={listing} />
      </Suspense>}
      {route.name === 'home' && <HomePage
        endpoint={config.homeApi}
        locale={config.locale}
        initialData={home ?? null}
        cards={cardProps(config, session, text)}
        urls={{
          all: config.urls.demonstrations, submit: config.urls.submit, calendar: config.urls.calendar,
          info: config.urls.info, pride: config.urls.pride,
        }}
        text={text.home}
      />}
      {(route.name === 'detail' || route.name === 'series') && (detail
        ? <DetailScreen
            base={{
              endpoint: detailEndpoint(config), locale: config.locale,
              authenticated: session.authenticated,
              urls: detailUrls(config), messages: detailMessages(config.locale),
              series,
            }}
            id={detail.id}
            canonicalUrl={detail.canonicalUrl}
          />
        : <section className="detail-error" role="alert">
            <h1>{detailMessages(config.locale).error}</h1>
            <p><a className="detail-button detail-button--primary" href={config.urls.demonstrations}>
              {detailMessages(config.locale).allEvents}
            </a></p>
          </section>)}
    </main>
    <SiteFooter config={config} session={session} text={text} />
  </>;
}
