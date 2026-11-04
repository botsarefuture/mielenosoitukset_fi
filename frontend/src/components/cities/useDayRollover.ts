import { useEffect } from 'react';
import { helsinkiDay } from '../../app/cities';

export function useDayRollover(day: string) {
  useEffect(() => {
    const check = () => { if (helsinkiDay() !== day) window.location.reload(); };
    const timer = window.setInterval(check, 30_000);
    window.addEventListener('pageshow', check);
    return () => { clearInterval(timer); window.removeEventListener('pageshow', check); };
  }, [day]);
}
