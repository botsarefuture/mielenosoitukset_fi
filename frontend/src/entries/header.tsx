import 'vite/modulepreload-polyfill';
import { SiteHeader } from '../components/header/SiteHeader';
import { mountIsland } from '../lib/mount-island';

mountIsland('site-header', SiteHeader);
