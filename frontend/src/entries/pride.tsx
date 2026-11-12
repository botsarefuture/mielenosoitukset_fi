import 'vite/modulepreload-polyfill';
import { PrideMap } from '../components/pride/PrideMap';
import { mountIsland } from '../lib/mount-island';

mountIsland('pride-map', PrideMap);
