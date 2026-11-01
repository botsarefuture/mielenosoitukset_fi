import 'vite/modulepreload-polyfill';
import { mountIsland } from '../lib/mount-island';
import { SubmitPage } from '../pages/SubmitPage';

mountIsland('submit-page', SubmitPage);
