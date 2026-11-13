import type { PublicOrganization } from '../components/organization/types';
import type { SuggestionDemo } from './suggest-change';
import type { ServiceStatus } from './status';
import type { CancelLinkState } from './cancel-link';
import type { CardProps } from '../components/listings/DemonstrationCard';
import { SiteHeader } from '../components/header/SiteHeader';
import { DetailScreen } from '../components/detail/DetailScreen';
import { HomePage } from '../pages/HomePage';
import type { HomeData } from '../pages/HomePage';
import type { AppConfig } from './config';
import { detailEndpoint, detailMessages, detailUrls } from './detail';
import type { DetailBootstrap, DetailSeries } from './detail-route';
import { SiteFooter } from './Footer';
import { useSession } from './useSession';
import { headerProps } from './header-props';
import { catalog } from './i18n';
import type { AppRoute } from './routes';
import type { SessionSummary } from './session';
import { lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
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
const PrideScreen = lazy(() => import('./PrideScreen'));

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
  /** A page rendered on the server and hydrated, such as the information pages. */
  serverPage?: ReactNode;
  /** Helsinki date the server used for the fundraising page, so hydration matches. */
  today?: string;
  fundraising?: Record<string, unknown> | null;
  /** Whether the /info page may promote the campaign: published, or the visitor can preview it. */
  campaignVisible?: boolean;
  /** The organization whose details the fill-in page suggests changes to. */
  organizationFill?: PublicOrganization;
  suggestionDemo?: SuggestionDemo;
  serviceStatus?: ServiceStatus | null;
  cancelLink?: CancelLinkState;
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
export function App({ config, session, route, path, detail, series, home, listing, organization, cities, submission, calendar, serverPage }: AppProps) {
  const text = catalog(config.locale);
  // Only after a failed server session read: ask the bridge once so the shell does not show guest buttons to a signed-in visitor.
  const shell = useSession(session, { endpoint: config.urls.authMe, refreshOnMount: Boolean(session.unverified) }).session;
  return <>
    <SiteHeader {...headerProps(config, shell, text, path)} hydrating={route.name === 'api-docs' || route.name === 'status' || route.name === 'information' || route.name === 'campaign' || route.name === 'fundraising' || route.name === 'contact' || route.name === 'city-admin' || route.name === 'organization-fill' || route.name === 'suggest-change' || route.name === 'cancel-link' || route.name === 'developer'} />
    <main className={`container-main-content ${route.name === 'submit' ? 'submit-workspace' : route.name === 'detail' || route.name === 'series' ? 'public-detail-main' : 'public-layout-wide'}`} id="main-content" tabIndex={-1}>
      {serverPage}
      {route.name === 'god-auth' && <Suspense fallback={<p role="status">Ladataan kirjautumista…</p>}><GodScreen /></Suspense>}
      {route.name === 'calendar' && calendar && <Suspense fallback={<p role="status">Ladataan kalenteria…</p>}>
        <CalendarScreen calendar={calendar} config={config} session={session} />
      </Suspense>}
      {route.name === 'calendar-year' && calendar && <Suspense fallback={<p role="status">Ladataan kalenteria…</p>}>
        <YearCalendarScreen calendar={calendar} />
      </Suspense>}
      {route.name === 'submit' && submission && <Suspense fallback={<p role="status">Ladataan lomaketta…</p>}>
        <SubmitScreen config={config} submission={submission} />
      </Suspense>}
      {route.name === 'cities' && <Suspense fallback={<p role="status">Ladataan kaupunkeja…</p>}>
        <CitiesPage initialData={cities ?? null} endpoint={`${config.apiBase}/cities`} />
      </Suspense>}
      {route.name === 'today' && <Suspense fallback={<p role="status">Ladataan mielenosoituksia…</p>}>
        <TodayScreen city={route.value} listing={listing} config={config} session={session} />
      </Suspense>}
      {route.name === 'organization' && organization && <Suspense fallback={<p role="status">Ladataan organisaatiota…</p>}>
        <OrganizationScreen key={path} organization={organization} config={config} session={session} />
      </Suspense>}
      {route.name === 'pride' && <Suspense fallback={<p role="status">Ladataan mielenosoituksia…</p>}>
        <PrideScreen config={config} session={session} listing={listing} />
      </Suspense>}
      {route.name === 'listing' && <Suspense fallback={<p role="status">Ladataan mielenosoituksia…</p>}>
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
        quick={{ todayUrl: config.urls.today, text: text.homeQuick }}
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
    <SiteFooter config={config} session={shell} text={text} />
  </>;
}
