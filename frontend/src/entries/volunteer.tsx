import 'vite/modulepreload-polyfill';
import { VolunteerForm } from '../components/VolunteerForm';
import { mountIsland } from '../lib/mount-island';

mountIsland('volunteer-form', VolunteerForm);
