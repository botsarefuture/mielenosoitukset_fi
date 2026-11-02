import { useEffect, useState } from 'react';
import { OrganizationPage } from '../pages/OrganizationPage';
import type { AppConfig } from './config';
import { listingProps } from './listing';
import type { OrganizationBootstrap } from './organization';
import type { SessionSummary } from './session';

export default function OrganizationScreen({ organization, config, session }: {
  organization: OrganizationBootstrap; config: AppConfig; session: SessionSummary;
}) {
  const id = organization.profile._id;
  const state = session.authenticated && session.organization?.id === id ? session.organization : null;
  const [notices, showNotices] = useState<{ category: string; message: string }[]>([]);
  useEffect(() => {
    if (!state?.hasMessages) return;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    void fetch('/get_flash_messages', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      headers: { Accept: 'application/json' } }).then(async response => {
      if (!response.ok) return;
      const value = await response.json();
      if (Array.isArray(value.messages)) showNotices(value.messages.filter((item: unknown) => item
        && typeof item === 'object' && typeof (item as { message?: unknown }).message === 'string')
        .slice(0, 10).map((item: { category?: unknown; message: string }) => ({
          category: typeof item.category === 'string' && ['success', 'error', 'warning', 'info'].includes(item.category) ? item.category : 'info',
          message: item.message,
        })));
    }).catch(() => {}).finally(() => clearTimeout(timer));
    return () => { controller.abort(); clearTimeout(timer); };
  }, [id, state?.hasMessages]);
  const path = `/organization/${id}`;
  return <>
    {notices.map((notice, index) => <div key={index} className={`flash-message flash-message--inline flash-${notice.category}`}
      role={notice.category === 'error' ? 'alert' : 'status'}><span className="flash-text">{notice.message}</span></div>)}
    <OrganizationPage organization={organization.profile} authenticated={session.authenticated} privateState={state}
      urls={{ login: `${config.urls.login}?next=${encodeURIComponent(path)}`, fill: `${path}/fill`,
        follow: `/api/follow/organization/${id}`, unfollow: `/api/unfollow/organization/${id}`,
        acceptInvite: `/users/orgs/accept_invite/${id}`, declineInvite: `/users/orgs/decline_invite?organization_id=${id}`,
        adminView: `/admin/organization/view/${id}`, adminEdit: `/admin/organization/edit/${id}`,
        adminDelete: `/admin/organization/confirm_delete/${id}` }}
      listing={{ ...listingProps({ name: 'listing', scope: 'organization', value: id }, config, session),
        initialData: organization.listing.page, initialSearch: organization.listing.query,
        onSearch: search => {
          if (!session.siteAnalyticsEnabled || navigator.doNotTrack === '1') return;
          try { navigator.sendBeacon('/api/analytics/event', new Blob([
            JSON.stringify({ event: 'demo_search', resource_id: search.slice(0, 120) }),
          ], { type: 'application/json' })); } catch { /* Optional analytics. */ }
        } }} />
  </>;
}
