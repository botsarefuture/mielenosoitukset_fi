import { useEffect } from 'react';
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
import { routeMeta } from './routes';
import type { AppRoute } from './routes';
import type { SessionSummary } from './session';

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
export function App({ config, session, route, path, detail, series, home }: AppProps) {
  const text = catalog(config.locale);
  const meta = routeMeta(route, config, text);
  useEffect(() => {
    // Client navigation updates the same title the server rendered. The detail
    // title comes from the event once it loads, so it is not overwritten here.
    if (route.name === 'home') document.title = meta.title;
  }, [route.name, meta.title]);
  return <>
    <SiteHeader {...headerProps(config, session, text, path)} />
    <main className={`container-main-content ${route.name === 'home' ? 'public-layout-wide' : 'public-detail-main'}`} id="main-content">
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
