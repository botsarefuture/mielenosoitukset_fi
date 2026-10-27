import 'vite/modulepreload-polyfill';
import { DemonstrationListingPage } from '../pages/DemonstrationListingPage';
import { mountIsland } from '../lib/mount-island';

mountIsland('demonstration-listing', DemonstrationListingPage);
