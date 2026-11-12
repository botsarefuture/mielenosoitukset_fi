import { CampaignPage } from '../pages/CampaignPage';
import { campaignProps } from './campaign-route';
import type { AppConfig } from './config';

export default function CampaignScreen({ config }: { config: AppConfig }) {
  return <CampaignPage {...campaignProps(config)} />;
}
