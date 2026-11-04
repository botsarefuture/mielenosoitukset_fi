import 'vite/modulepreload-polyfill';
import { HomePage } from '../pages/HomePage';
import { mountIsland } from '../lib/mount-island';

mountIsland('home', HomePage);
