import type { AppConfig } from './config';
import type { CampaignPageProps } from '../pages/CampaignPage';

export const campaignPath = '/kampanja/';

export const campaignCopy = {
  title: 'Yhdessä näkyväksi – Mielenosoitukset.fi',
  description: 'Tule tekemään mielenosoitukset.fi-palvelua tunnetuksi. Voit auttaa omalla paikkakunnallasi tai verkossa.',
  image: '/static/kampanja/og-banner.png',
};

/** Props for the existing campaign page; writes keep their Flask and newsletter endpoints. */
export function campaignProps(config: AppConfig): CampaignPageProps {
  return {
    urls: { home: config.urls.home, fundraising: config.urls.fundraising, privacy: config.urls.privacy },
    volunteer: {
      endpoint: '/kampanja/api/volunteers',
      messages: {
        required: 'Nimi ja sähköpostiosoite ovat pakollisia.',
        invalid: 'Tarkista korostetut tiedot ja yritä uudelleen.',
        success: 'Kiitos ilmoittautumisestasi! Tarkista sähköpostisi vahvistaaksesi ilmoittautumisen.',
        failed: 'Ilmoittautuminen epäonnistui. Yritä uudelleen.',
        network: 'Yhteys palveluun epäonnistui. Yritä myöhemmin uudelleen.',
        sending: 'Lähetetään…',
      },
    },
    newsletter: { endpoint: 'https://mailist.luova.club/signup', listId: '68d26ca27f8e9dee7c846a22' },
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
