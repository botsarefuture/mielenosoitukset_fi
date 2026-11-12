import 'vite/modulepreload-polyfill';
import { DetailScreen } from '../components/detail/DetailScreen';
import type { DetailProps } from '../components/detail/types';
import { mountIsland } from '../lib/mount-island';

/**
 * Flask island mount. The screen and its browser adapter are shared with the
 * React host; only the props source differs while this page still renders here.
 */
function IslandDetail(props: DetailProps) {
  const { id, canonicalUrl: _canonicalUrl, ...base } = props;
  // The island shares the URL it was opened with, exactly as before.
  return <DetailScreen base={base} id={id} canonicalUrl={window.location.href} />;
}

mountIsland('demonstration-detail', IslandDetail);
