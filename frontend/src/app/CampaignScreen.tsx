import { CampaignPage } from '../pages/CampaignPage';
import { campaignProps } from './campaign-route';
import type { AppConfig } from './config';

export default function CampaignScreen({ config, today, data }: { config: AppConfig; today: string; data?: unknown }) {
  return <CampaignPage {...campaignProps(config, today, data)} />;
}
