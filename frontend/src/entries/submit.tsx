import 'vite/modulepreload-polyfill';
import { mountIsland } from '../lib/mount-island';
import { SubmitBack, SubmitChoices, SubmitNavigation, SubmitProgress } from '../components/submit/SubmitFlow';

mountIsland('submit-progress', SubmitProgress);
mountIsland('submit-choice', SubmitChoices);
mountIsland('submit-navigation', SubmitNavigation);
mountIsland('submit-back', SubmitBack);
