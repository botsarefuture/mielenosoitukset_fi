import type { HeaderMessages } from '../components/header/types';
import type { CardProps } from '../components/listings/DemonstrationCard';
import type { HomeProps } from '../pages/HomePage';
import type { AppLocale } from './config';

/**
 * Public application copy.
 *
 * The React host replaces Flask's template-provided strings, so the strings it
 * needs live here. Finnish is the source catalog; English and Swedish override
 * it. This is presentation copy only: permissions, routes and validation are
 * never decided here.
 */

type CardMessages = CardProps['messages'];

export type Catalog = {
  meta: { title: string; description: string };
  nav: { home: string; demonstrations: string; cities: string; submit: string };
  account: { profile: string; settings: string; admin: string; logout: string; login: string; register: string };
  header: HeaderMessages;
  footer: {
    rights: string; navigation: string; info: string; privacy: string; contact: string;
    guides: string; developer: string; social: string; account: string;
  };
  fundraising: string;
  home: HomeProps['text'];
  cards: CardMessages;
};

const fi: Catalog = {
  meta: {
    title: 'Mielenosoitukset.fi',
    description: 'Mielenosoitukset.fi - Tietoa mielenosoituksista ja aktivismista Suomessa.',
  },
  nav: { home: 'Etusivu', demonstrations: 'Mielenosoitukset', cities: 'Kaupungit', submit: 'Ilmoita mielenosoituksesta' },
  account: { profile: 'Profiili', settings: 'Asetukset', admin: 'Hallintapaneeli', logout: 'Kirjaudu ulos',
    login: 'Kirjaudu sisään', register: 'Rekisteröidy' },
  header: {
    skip: 'Siirry sisältöön', home: 'Mielenosoitukset.fi - Etusivu', navigation: 'Päävalikko',
    languages: 'Kielivalinta', changeLanguage: 'Vaihda kieleksi', menu: 'Valikko',
    openMenu: 'Avaa navigaatiovalikko', closeMenu: 'Sulje navigaatiovalikko', close: 'Sulje valikko',
    userMenu: 'Käyttäjävalikko', theme: 'Vaihda teemaa', lightTheme: 'Vaihda vaaleaan teemaan',
    darkTheme: 'Vaihda tummaan teemaan',
    adminWarning: 'Olet mobiililaitteella. Siirry PC:lle admintoimintojen käyttöä varten',
    notifications: 'Ilmoitukset', markRead: 'Merkitse luetuiksi', all: 'Näytä kaikki',
    empty: 'Ei ilmoituksia', loading: 'Ladataan…', loadError: 'Virhe ladattaessa',
    markError: 'Ilmoituksia ei voitu merkitä luetuiksi.',
  },
  footer: {
    rights: 'Kaikki oikeudet pidätetään.', navigation: 'Sivuston alatunniste',
    info: 'Tietoa sivustosta', privacy: 'Tietosuojaseloste', contact: 'Ota yhteyttä',
    guides: 'Ohjeet', developer: 'Kehittäjille', social: 'Mielenosoitukset.fi sosiaalisessa mediassa',
    account: 'Käyttäjätili',
  },
  fundraising: 'Tutustu pienkeräykseen',
  home: {
    title: 'Tulevat mielenosoitukset',
    intro: 'Mielenosoitukset.fi tarjoaa ajankohtaiset tiedot mielenosoituksista ympäri Suomen.',
    search: 'Hae mielenosoituksia', searchPlaceholder: 'Hae mielenosoituksia...', submitSearch: 'Hae',
    all: 'Kaikki mielenosoitukset', submit: 'Ilmoita mielenosoituksesta',
    calendar: 'Kalenterinäkymä', info: 'Tietoa sivustosta',
    eventsTitle: 'Poimintoja ajankohtaisista mielenosoituksista.', recommendedTitle: 'Suosittelemme',
    emptyTitle: 'Ei mielenosoituksia näytettäväksi',
    empty: 'Uusia mielenosoituksia lisätään jatkuvasti. Tarkista myöhemmin uudelleen!',
    prideTitle: 'Pride näkyväksi koko Suomessa',
    prideIntro: 'Tutustu Pride näkyväksi -sivuun, katso Pride-mielenosoitukset kartalla ja lisää myös oma tapahtumasi mukaan.',
    prideLink: 'Avaa Pride näkyväksi',
    loading: 'Ladataan mielenosoituksia...',
    loadError: 'Mielenosoitusten lataaminen epäonnistui. Yritä uudelleen.',
    retry: 'Yritä uudelleen',
  },
  cards: {
    startingFrom: 'alkaen', endTime: 'Päättymisaika', cancelled: 'Peruttu', today: 'Tänään',
    loginPrompt: 'Kirjaudu sisään käyttääksesi sosiaalisia toimintoja',
    loadingFriends: 'Ladataan kavereita...', attendingSuffix: 'osallistuu', invite: 'Kutsu kavereita',
  },
};

const en: Catalog = {
  ...fi,
  meta: {
    title: 'Mielenosoitukset.fi',
    description: 'Mielenosoitukset.fi - Information about demonstrations and activism in Finland.',
  },
  nav: { home: 'Home', demonstrations: 'Demonstrations', cities: 'Cities', submit: 'Submit a demonstration' },
  account: { profile: 'Profile', settings: 'Settings', admin: 'Admin panel', logout: 'Sign out',
    login: 'Sign in', register: 'Register' },
  header: {
    ...fi.header,
    skip: 'Skip to content', home: 'Mielenosoitukset.fi - Home', navigation: 'Main menu',
    languages: 'Language selection', changeLanguage: 'Change language to', menu: 'Menu',
    openMenu: 'Open navigation menu', closeMenu: 'Close navigation menu', close: 'Close menu',
    userMenu: 'User menu', theme: 'Change theme', lightTheme: 'Switch to light theme',
    darkTheme: 'Switch to dark theme',
    adminWarning: 'You are on a mobile device. Use a PC for administrative features',
    notifications: 'Notifications', markRead: 'Mark as read', all: 'Show all',
    empty: 'No notifications', loading: 'Loading…', loadError: 'Could not load',
    markError: 'Notifications could not be marked as read.',
  },
  footer: {
    rights: 'All rights reserved.', navigation: 'Site footer', info: 'About the site',
    privacy: 'Privacy policy', contact: 'Contact us', guides: 'Guides', developer: 'For developers',
    social: 'Mielenosoitukset.fi on social media', account: 'User account',
  },
  fundraising: 'Read about the fundraiser',
  home: {
    title: 'Upcoming demonstrations',
    intro: 'Mielenosoitukset.fi lists current demonstrations around Finland.',
    search: 'Search for demonstrations', searchPlaceholder: 'Search for demonstrations...', submitSearch: 'Search',
    all: 'All demonstrations', submit: 'Submit a demonstration',
    calendar: 'Calendar view', info: 'About the site',
    eventsTitle: 'Highlights from current demonstrations', recommendedTitle: 'We recommend',
    emptyTitle: 'No demonstrations to show',
    empty: 'New demonstrations are added continuously. Check again later!',
    prideTitle: 'Pride visibility across Finland',
    prideIntro: 'Visit the Pride visibility page, view Pride demonstrations on the map and add your own event.',
    prideLink: 'Open Pride visibility',
    loading: 'Loading demonstrations...',
    loadError: 'Could not load demonstrations. Please try again.',
    retry: 'Try again',
  },
  cards: {
    startingFrom: 'onwards', endTime: 'Ends at', cancelled: 'Cancelled', today: 'Today',
    loginPrompt: 'Sign in to use social features', loadingFriends: 'Loading friends...',
    attendingSuffix: 'is attending', invite: 'Invite friends',
  },
};

const sv: Catalog = {
  ...fi,
  meta: {
    title: 'Mielenosoitukset.fi',
    description: 'Mielenosoitukset.fi - Information om demonstrationer och aktivism i Finland.',
  },
  nav: { home: 'Framsidan', demonstrations: 'Demonstrationer', cities: 'Städer', submit: 'Anmäl en demonstration' },
  account: { profile: 'Profil', settings: 'Inställningar', admin: 'Administrationspanel', logout: 'Logga ut',
    login: 'Logga in', register: 'Registrera dig' },
  header: {
    ...fi.header,
    skip: 'Gå till innehållet', home: 'Mielenosoitukset.fi - Framsidan', navigation: 'Huvudmeny',
    languages: 'Språkval', changeLanguage: 'Byt språk till', menu: 'Meny',
    openMenu: 'Öppna navigationsmenyn', closeMenu: 'Stäng navigationsmenyn', close: 'Stäng menyn',
    userMenu: 'Användarmenyn', theme: 'Byt tema', lightTheme: 'Byt till ljust tema',
    darkTheme: 'Byt till mörkt tema',
    adminWarning: 'Du använder en mobil enhet. Gå till en dator för administrativa funktioner',
    notifications: 'Aviseringar', markRead: 'Markera som lästa', all: 'Visa alla',
    empty: 'Inga aviseringar', loading: 'Laddar…', loadError: 'Det gick inte att ladda',
    markError: 'Aviseringarna kunde inte markeras som lästa.',
  },
  footer: {
    rights: 'Alla rättigheter förbehållna.', navigation: 'Sidfot', info: 'Om webbplatsen',
    privacy: 'Dataskyddsbeskrivning', contact: 'Kontakta oss', guides: 'Anvisningar',
    developer: 'För utvecklare', social: 'Mielenosoitukset.fi i sociala medier', account: 'Användarkonto',
  },
  fundraising: 'Läs om insamlingen',
  home: {
    title: 'Kommande demonstrationer',
    intro: 'Mielenosoitukset.fi samlar aktuella demonstrationer runt om i Finland.',
    search: 'Sök demonstrationer', searchPlaceholder: 'Sök demonstrationer...', submitSearch: 'Sök',
    all: 'Alla demonstrationer', submit: 'Anmäl en demonstration',
    calendar: 'Kalendervy', info: 'Om webbplatsen',
    eventsTitle: 'Urval av aktuella demonstrationer', recommendedTitle: 'Vi rekommenderar',
    emptyTitle: 'Inga demonstrationer att visa',
    empty: 'Nya demonstrationer läggs till hela tiden. Kontrollera igen senare!',
    prideTitle: 'Pride synligt i hela Finland',
    prideIntro: 'Besök sidan Pride synligt, se Pride-demonstrationer på kartan och lägg till ditt eget evenemang.',
    prideLink: 'Öppna Pride synligt',
    loading: 'Laddar demonstrationer...',
    loadError: 'Det gick inte att ladda demonstrationer. Försök igen.',
    retry: 'Försök igen',
  },
  cards: {
    startingFrom: 'och framåt', endTime: 'Sluttid', cancelled: 'Inställd', today: 'Idag',
    loginPrompt: 'Logga in för att använda sociala funktioner', loadingFriends: 'Laddar vänner...',
    attendingSuffix: 'deltar', invite: 'Bjud in vänner',
  },
};

const catalogs: Record<AppLocale, Catalog> = { fi, en, sv };

export function catalog(locale: AppLocale): Catalog {
  return catalogs[locale] ?? fi;
}
