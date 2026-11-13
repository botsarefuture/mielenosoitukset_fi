import 'vite/modulepreload-polyfill';
import { CampaignPage } from '../pages/CampaignPage';
import type { CampaignPageProps } from '../pages/CampaignPage';
import { helsinkiToday } from '../app/fundraising';
import { mountIsland } from '../lib/mount-island';

/** Flask bridge: the island computes the phase from the visitor-independent Helsinki date. */
mountIsland<Omit<CampaignPageProps, 'today'>>('campaign-page', (props) => <CampaignPage {...props} today={helsinkiToday()} />);
