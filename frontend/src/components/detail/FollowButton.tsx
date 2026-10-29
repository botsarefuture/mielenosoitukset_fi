import { useActionState } from 'react';
import type { DetailProps } from './types';
import { accountEndpoint, accountRequest } from './account';

/** Account mutation adapter, separate from the open event-data API. */
export function FollowButton({ props, organizationId }: { props: DetailProps; organizationId?: string }) {
  const organization = Boolean(organizationId);
  const following = organization
    ? (props.followedOrganizations ?? []).includes(organizationId!) : Boolean(props.recurringFollowing);
  const [error, submit, pending] = useActionState(async () => {
    try {
      const template = organization
        ? (following ? props.urls.unfollowOrganization : props.urls.followOrganization)
        : (following ? props.urls.unfollowRecurring : props.urls.followRecurring);
      if (!template) throw new Error('Missing follow action');
      const endpoint = template.replace('__ORGANIZATION_ID__', encodeURIComponent(organizationId ?? ''))
        .replace('__EVENT_ID__', encodeURIComponent(props.id));
      const result = await accountRequest(accountEndpoint(endpoint, props.id), { method: 'POST' }, props.csrfToken);
      if (result.status !== 'OK' || typeof result.following !== 'boolean') throw new Error('Invalid follow response');
      if (organization) props.onOrganizationFollowChange?.(organizationId!, result.following);
      else props.onRecurringFollowChange?.(result.following);
      return '';
    } catch { return props.messages.actionError; }
  }, '');
  return <form action={submit}><button className="detail-button" type="submit" disabled={pending} aria-pressed={following}>
    {pending ? props.messages.sending : following ? props.messages.following : organization ? props.messages.follow : props.messages.followSeries}
  </button>{error && <p role="alert">{error}</p>}</form>;
}
