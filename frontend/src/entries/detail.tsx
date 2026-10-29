import 'vite/modulepreload-polyfill';
import { useCallback, useEffect, useRef, useState } from 'react';
import { DemonstrationDetailPage } from '../pages/DemonstrationDetailPage';
import type { DetailProps } from '../pages/DemonstrationDetailPage';
import type { DetailEvent } from '../components/detail/types';
import { mountIsland } from '../lib/mount-island';
import { trackDemoView } from '../lib/track-demo-view';

type Route = { id: string; href: string };
/** Browser host adapter. Components receive routes and account configuration as data. */
function DetailRoute(props: DetailProps) {
  const [followedOrganizations, setFollowedOrganizations] = useState(props.followedOrganizations ?? []);
  const [recurringFollowing, setRecurringFollowing] = useState(Boolean(props.recurringFollowing));
  function organizationChanged(id: string, following: boolean) {
    setFollowedOrganizations(current => following ? [...new Set([...current, id])] : current.filter(value => value !== id));
  }

  const [route, setRoute] = useState<Route>({ id: props.id, href: window.location.href });
  const trackedView = useRef<string | null>(null);
  useEffect(() => { trackedView.current = null; }, [route.id]);
  const loaded = useCallback((event: DetailEvent) => {
    if (event._id !== route.id) return;
    document.title = `${event.title} | Mielenosoitukset.fi`;
    if (trackedView.current === event._id) return;
    trackedView.current = event._id;
    trackDemoView(props.urls.trackView, event._id);
  }, [route.id, props.urls.trackView]);
  const [intent, setIntent] = useState<'attend' | 'invite' | null>(() => {
    const action = new URL(window.location.href).searchParams.get('action');
    return action === 'like' ? 'attend' : action === 'inviteFriends' ? 'invite' : null;
  });
  const consumeIntent = useCallback(() => {
    setIntent(null);
    setRoute(previous => {
      const url = new URL(previous.href); url.searchParams.delete('action');
      window.history.replaceState({ ...window.history.state, detailId: previous.id, detailUrl: url.href }, '', url);
      return { ...previous, href: url.href };
    });
  }, []);
  useEffect(() => {
    window.history.replaceState({ ...window.history.state, detailId: props.id, detailUrl: window.location.href }, '', window.location.href);
    function restore(event: PopStateEvent) {
      if (typeof event.state?.detailId !== 'string' || !/^[a-f\d]{24}$/i.test(event.state.detailId)) return;
      const url = new URL(event.state.detailUrl ?? window.location.href, window.location.origin);
      if (url.origin === window.location.origin) { setIntent(null); setRoute({ id: event.state.detailId, href: url.href }); }
    }
    window.addEventListener('popstate', restore);
    return () => window.removeEventListener('popstate', restore);
  }, [props.id]);
  function select(id: string, href: string) {
    const url = new URL(href, window.location.origin);
    if (url.origin !== window.location.origin || !/^[a-f\d]{24}$/i.test(id)) return;
    window.history.pushState({ ...window.history.state, detailId: id, detailUrl: url.href }, '', url);
    setIntent(null); setRoute({ id, href: url.href });
  }
  function loginHref(action: string) {
    const login = new URL(props.urls.login, window.location.origin);
    const selected = new URL(route.href); selected.searchParams.set('action', action);
    login.searchParams.set('next', selected.pathname + selected.search);
    return login.pathname + login.search;
  }
  const urls = { ...props.urls,
    calendar: props.urls.calendar.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    reminder: props.urls.reminder.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    report: props.urls.report.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    invite: props.urls.invite.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    like: props.urls.like.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    unlike: props.urls.unlike.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    attendance: props.urls.attendance.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    login: loginHref('like'), loginInvite: loginHref('inviteFriends'),
  };
  return <DemonstrationDetailPage {...props} id={route.id} canonicalUrl={route.href} urls={urls}
    initialAction={intent} onIntentConsumed={consumeIntent} onSelect={select} onLoaded={loaded} followedOrganizations={followedOrganizations} recurringFollowing={recurringFollowing}
    onOrganizationFollowChange={organizationChanged} onRecurringFollowChange={setRecurringFollowing} />;
}
mountIsland('demonstration-detail', DetailRoute);
