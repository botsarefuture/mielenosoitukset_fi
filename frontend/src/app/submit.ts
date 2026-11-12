import type { AppConfig, AppLocale } from './config';
import { LOCALE_NAMES } from './config';
import { cityCatalog } from './cities';
import { submitMessages } from './submit-copy';
import type { SubmitPageProps } from '../components/submit/types';

export type SubmitBootstrap = { token: string; locales: AppLocale[]; defaultLanguage: AppLocale; canEditDemo: boolean; sent: boolean; conflict: boolean };

export function submitProps(config: AppConfig, data: SubmitBootstrap): SubmitPageProps {
  return {
    action: config.urls.submit, importUrl: '/submit/facebook_import', orgSearchUrl: '/api/v1/search_organizations',
    termsUrl: '/terms', privacyUrl: config.urls.privacy, homeUrl: config.urls.home,
    guidesUrl: config.urls.guides, contactUrl: config.urls.contact, infoUrl: config.urls.info,
    token: data.token, cities: cityCatalog.map(city => city.name), locales: data.locales,
    localeNames: LOCALE_NAMES, defaultLanguage: data.defaultLanguage, canEditDemo: data.canEditDemo,
    messages: submitMessages(config.locale),
  };
}
