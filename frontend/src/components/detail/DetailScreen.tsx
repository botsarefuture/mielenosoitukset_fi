import { useCallback, useEffect, useRef, useState } from 'react';
import { DemonstrationDetailPage } from '../../pages/DemonstrationDetailPage';
import { trackDemoView } from '../../lib/track-demo-view';
import type { DetailEvent, DetailProps } from './types';

/**
 * Browser host adapter for the portable detail screen.
 *
 * The screen itself receives routes and account configuration as data. This
 * adapter owns the URL, in-page navigation between occurrences, the `action`
 * intent, login links and the single view-tracking call, so both the Flask
 * island and the React host behave the same way.
 */

type Route = { id: string; href: string };

export type DetailScreenProps = {
  /** Everything the screen needs except the per-route fields this adapter owns. */
  base: Omit<DetailProps, 'id' | 'canonicalUrl'>;
  /** Resolved public id of the event the server rendered. */
  id: string;
  /** Canonical public URL to share for the first loaded event. */
  canonicalUrl: string;
  /** Start URL; the current location when the page was rendered. */
  initialHref?: string;
};

export function DetailScreen({ base, id, canonicalUrl, initialHref }: DetailScreenProps) {
  const [followedOrganizations, setFollowedOrganizations] = useState(base.followedOrganizations ?? []);
  const [recurringFollowing, setRecurringFollowing] = useState(Boolean(base.recurringFollowing));
  function organizationChanged(organizationId: string, following: boolean) {
    setFollowedOrganizations(current => following
      ? [...new Set([...current, organizationId])]
      : current.filter(value => value !== organizationId));
  }

  const [route, setRoute] = useState<Route>(() => ({ id, href: initialHref ?? window.location.href }));
  const trackedView = useRef<string | null>(null);
  useEffect(() => { trackedView.current = null; }, [route.id]);
  const loaded = useCallback((event: DetailEvent) => {
    if (event._id !== route.id) return;
    document.title = `${event.title} | Mielenosoitukset.fi`;
    if (trackedView.current === event._id) return;
    trackedView.current = event._id;
    trackDemoView(base.urls.trackView, event._id);
  }, [route.id, base.urls.trackView]);
  const [intent, setIntent] = useState<'attend' | 'invite' | null>(() => {
    const action = new URL(window.location.href).searchParams.get('action');
    return action === 'like' ? 'attend' : action === 'inviteFriends' ? 'invite' : null;
  });
  const consumeIntent = useCallback(() => {
    setIntent(null);
    setRoute(previous => {
      const url = new URL(previous.href);
      url.searchParams.delete('action');
      window.history.replaceState({ ...window.history.state, detailId: previous.id, detailUrl: url.href }, '', url);
      return { ...previous, href: url.href };
    });
  }, []);
  useEffect(() => {
    window.history.replaceState({ ...window.history.state, detailId: id, detailUrl: window.location.href }, '', window.location.href);
    function restore(event: PopStateEvent) {
      if (typeof event.state?.detailId !== 'string' || !/^[a-f\d]{24}$/i.test(event.state.detailId)) return;
      const url = new URL(event.state.detailUrl ?? window.location.href, window.location.origin);
      if (url.origin === window.location.origin) {
        setIntent(null);
        setRoute({ id: event.state.detailId, href: url.href });
      }
    }
    window.addEventListener('popstate', restore);
    return () => window.removeEventListener('popstate', restore);
  }, [id]);
  function select(nextId: string, href: string) {
    const url = new URL(href, window.location.origin);
    if (url.origin !== window.location.origin || !/^[a-f\d]{24}$/i.test(nextId)) return;
    window.history.pushState({ ...window.history.state, detailId: nextId, detailUrl: url.href }, '', url);
    setIntent(null);
    setRoute({ id: nextId, href: url.href });
  }
  function loginHref(action: string) {
    const login = new URL(base.urls.login, window.location.origin);
    const selected = new URL(route.href);
    selected.searchParams.set('action', action);
    login.searchParams.set('next', selected.pathname + selected.search);
    return login.pathname + login.search;
  }
  const urls: DetailProps['urls'] = {
    ...base.urls,
    calendar: base.urls.calendar.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    reminder: base.urls.reminder.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    report: base.urls.report.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    invite: base.urls.invite.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    like: base.urls.like.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    unlike: base.urls.unlike.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    attendance: base.urls.attendance.replaceAll('__EVENT_ID__', encodeURIComponent(route.id)),
    login: loginHref('like'), loginInvite: loginHref('inviteFriends'),
  };
  return <DemonstrationDetailPage {...base} id={route.id}
    canonicalUrl={route.id === id ? canonicalUrl : route.href} urls={urls}
    initialAction={intent} onIntentConsumed={consumeIntent} onSelect={select} onLoaded={loaded}
    followedOrganizations={followedOrganizations} recurringFollowing={recurringFollowing}
    onOrganizationFollowChange={organizationChanged} onRecurringFollowChange={setRecurringFollowing} />;
}
