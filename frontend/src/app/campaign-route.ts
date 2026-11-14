import type { AppConfig } from './config';
import type { CampaignPageProps } from '../pages/CampaignPage';
import { campaignSchedule } from './campaign-schedule';

export const campaignPath = '/kampanja/';

export const campaignCopy = {
  title: 'Yhdessä näkyväksi – Mielenosoitukset.fi',
  description: 'Tule tekemään Mielenosoitukset.fi-palvelua tunnetuksi. Voit auttaa omalla paikkakunnallasi tai verkossa.',
  image: '/static/kampanja/og-banner.png',
};

/**
 * Props for the campaign page; writes keep their Flask endpoints. `data` is the
 * shared fundraising configuration and `today` the Helsinki date, both chosen by
 * the server so the phase cannot differ between server and client.
 */
export function campaignProps(config: AppConfig, today: string, data?: unknown): CampaignPageProps {
  return {
    today,
    schedule: campaignSchedule(data),
    shareAddress: `${config.origin.replace(/^https?:\/\//, '')}${campaignPath.replace(/\/$/, '')}`,
    urls: { home: config.urls.home, fundraising: config.urls.fundraising, privacy: config.urls.privacy, pride: config.urls.pride },
    volunteer: {
      endpoint: '/kampanja/api/volunteers',
      messages: {
        required: 'Nimi ja sähköpostiosoite ovat pakollisia.',
        invalid: 'Tarkista korostetut tiedot ja yritä uudelleen.',
        success: 'Kiitos ilmoittautumisestasi. Tarkista sähköpostisi vahvistaaksesi ilmoittautumisen.',
        failed: 'Ilmoittautuminen epäonnistui. Yritä uudelleen.',
        network: 'Yhteys palveluun epäonnistui. Yritä myöhemmin uudelleen.',
        sending: 'Lähetetään…',
      },
    },
  };
}

/**
 * Whether the campaign is public. Mirrors Flask's gate: anything but an explicit
 * `published: true` from the API, including a failed read, is private.
 */
export async function loadCampaignPublication(readBase: string): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch(`${readBase}/campaign/publication`, {
      signal: controller.signal, credentials: 'omit', headers: { Accept: 'application/json' },
    });
    if (!response.ok) return false;
    const data: unknown = await response.json();
    return Boolean(data && typeof data === 'object' && (data as { published?: unknown }).published === true);
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
