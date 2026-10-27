import 'vite/modulepreload-polyfill';
import { ConfirmationPage } from '../pages/ConfirmationPage';
import { mountIsland } from '../lib/mount-island';

mountIsland('campaign-confirmation', ConfirmationPage);
