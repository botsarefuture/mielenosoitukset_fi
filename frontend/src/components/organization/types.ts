import type { PublicListingProps } from '../../pages/PublicListingPage';

export type PublicOrganization = {
  _id: string;
  name: string;
  description: string;
  email: string;
  website: string;
  logo: string | null;
  social_media_links: Record<string, string>;
  verified: boolean;
};

export type OrganizationPermissions = {
  VIEW_ORGANIZATION: boolean;
  EDIT_ORGANIZATION: boolean;
  DELETE_ORGANIZATION: boolean;
  INVITE_TO_ORGANIZATION: boolean;
};

export type OrganizationPrivateState = {
  following: boolean;
  invited: boolean;
  permissions: OrganizationPermissions;
};

export type OrganizationUrls = {
  login: string;
  fill: string;
  follow: string;
  unfollow: string;
  acceptInvite: string;
  declineInvite: string;
  adminView: string;
  adminEdit: string;
  adminDelete: string;
};

export type OrganizationPageProps = {
  organization: PublicOrganization;
  authenticated: boolean;
  privateState?: OrganizationPrivateState | null;
  urls: OrganizationUrls;
  listing: PublicListingProps;
};
