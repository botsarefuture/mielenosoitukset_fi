import type { DetailMessages, DetailProps } from '../components/detail/types';
import type { AppConfig, AppLocale } from './config';

/**
 * Portable copy and endpoints for the demonstration detail screen.
 *
 * The detail screen renders in the React host, so its strings live here instead
 * of in Flask's translation catalogs. Finnish is the source catalog; `en` and
 * `sv` reuse it until a human translator supplies those strings, the same rule
 * the Flask catalogs follow.
 *
 * Account actions still post to the existing same-origin Flask routes. They are
 * declared here so the host owns its URLs, not read from a Flask template.
 */

/** Existing public account routes. Changing one here must change the route too. */
const ROUTES = {
  trackView: '/api/analytics/track_view',
  report: '/report',
  calendar: '/demonstration/__EVENT_ID__/ics',
  reminder: '/subscribe_reminder/__EVENT_ID__',
  invite: '/api/demonstrations/__EVENT_ID__/invite',
  like: '/api/demonstrations/__EVENT_ID__/like',
  unlike: '/api/demonstrations/__EVENT_ID__/unlike',
  attendance: '/api/demonstrations/__EVENT_ID__/attending',
  friends: '/users/profile/api/friends_list/',
  suggestChange: '/suggest_change/__EVENT_ID__',
  followOrganization: '/api/follow/organization/__ORGANIZATION_ID__',
  unfollowOrganization: '/api/unfollow/organization/__ORGANIZATION_ID__',
  followRecurring: '/api/follow/recurring/__EVENT_ID__',
  unfollowRecurring: '/api/unfollow/recurring/__EVENT_ID__',
  organizationPrefix: '/organization/',
  tagPrefix: '/tag/',
} as const;

const fi: DetailMessages = {
  follow: 'Seuraa', following: 'Seurataan', followSeries: 'Seuraa sarjaa',
  followDisabled: 'Seuraaminen on teknisten muutosten vuoksi tilapäisesti pois käytöstä tässä näkymässä. Voit siirtyä organisaation sivulle organisaation napista ja seurata sieltä.',
  loading: 'Ladataan tapahtuman tietoja...', error: 'Tapahtuman tietoja ei voitu ladata.',
  retry: 'Yritä uudelleen', notFound: 'Tapahtumaa ei löydy tai se ei ole julkinen.',
  allEvents: 'Kaikki mielenosoitukset',
  date: 'Ajankohta', location: 'Sijainti', startingFrom: 'alkaen',
  cancelled: 'Tämä mielenosoitus on peruttu.', description: 'Kuvaus',
  organizers: 'Järjestäjät', noOrganizers: 'Järjestäjätietoja ei ole ilmoitettu',
  organizerProfile: 'Organisaation profiili', website: 'Verkkosivusto',
  route: 'Reitti', map: 'Kartta', showMap: 'Näytä kartta', mapLoading: 'Ladataan karttaa...',
  directions: 'Avaa reittiohjeet', series: 'Kaikki tapahtuman ajankohdat',
  gallery: 'Tapahtuman kuvat', openImage: 'Avaa kuva', close: 'Sulje',
  previous: 'Edellinen kuva', next: 'Seuraava kuva', imageUnavailable: 'Kuvaa ei voitu ladata.',
  calendar: 'Lisää kalenteriin (.ics)', reminder: 'Tilaa muistutus',
  report: 'Ilmoita virheestä', invite: 'Kutsu kavereita', attend: 'Osallistun',
  suggestEditTitle: 'Korjaa tiedot muokkauslomakkeella',
  suggestEdit: 'Siirry ehdottamaan muokkauksia',
  reportOnlyTitle: 'Ilmoita ongelmasta ylläpidolle',
  reportOnly: 'Haluan vain ilmoittaa virheen',
  loginRequired: 'Kirjaudu sisään ilmoittaaksesi osallistumisestasi.',
  share: 'Jaa tapahtuma', copyLink: 'Kopioi linkki', shareCopied: 'Linkki kopioitu',
  copyFailed: 'Linkkiä ei voitu kopioida.', login: 'Kirjaudu sisään',
  email: 'Sähköpostiosoite', emailOptional: 'Sähköposti (valinnainen)',
  reportDescription: 'Kerro virheestä', markCancelled: 'Tapahtuma on peruttu',
  sendReport: 'Lähetä ilmoitus', sendInvites: 'Lähetä kutsut',
  chooseFriends: 'Valitse ainakin yksi kaveri.',
  noFriends: 'Sinulla ei ole vielä kutsuttavia kavereita.',
  friendsError: 'Kaverien lataaminen epäonnistui.', inviteSent: 'Kutsut lähetetty!',
  actionError: 'Toiminto epäonnistui. Yritä uudelleen.', sending: 'Lähetetään...',
  saved: 'Tallennettu', cancelAttendance: 'Peru osallistuminen',
  anonymousOrganizer: 'Yksityishenkilö (nimi piilotettu)',
  noDescription: 'Tapahtumalle ei ole lisätty kuvausta.', facebook: 'Facebook-tapahtuma',
  shareFacebook: 'Jaa Facebookissa', shareMastodon: 'Jaa Mastodonissa',
  shareX: 'Jaa X:ssä', shareLinkedIn: 'Jaa LinkedInissä',
  unknownTime: 'Kellonaikaa ei ole ilmoitettu',
};

const catalogs: Record<AppLocale, DetailMessages> = {
  fi,
  en: fi,
  sv: fi,
};

export function detailMessages(locale: AppLocale): DetailMessages {
  return catalogs[locale] ?? fi;
}

/** The existing public event API; the host adds the identifier and language. */
export function detailEndpoint(config: AppConfig): string {
  return `${config.apiBase}/demonstrations`;
}

/** Account and navigation endpoints the detail screen posts to or links. */
export function detailUrls(config: AppConfig): DetailProps['urls'] {
  return {
    ...ROUTES,
    listing: config.urls.demonstrations,
    login: config.urls.login,
  };
}

/** Canonical public path for one event, matching the site's existing URLs. */
export function detailPath(config: AppConfig, identifier: string): string {
  return config.urls.detail.replace('__ID__', encodeURIComponent(identifier));
}
