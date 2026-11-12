import 'vite/modulepreload-polyfill';
import { CampaignPage } from '../pages/CampaignPage';
import { mountIsland } from '../lib/mount-island';

mountIsland('campaign-page', CampaignPage);
