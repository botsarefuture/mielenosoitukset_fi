export type DetailEvent = {
  _id: string; title: string; description: string; date: string | null;
  start_time: string | null; end_time: string | null; city: string | null; address: string | null;
  latitude: number | null; longitude: number | null; tags: string[]; route: string[];
  cancelled: boolean; event_type: string | null; facebook: string | null;
  img: string | null; cover_picture: string | null; preview_image: string | null; gallery_images: string[];
  cover_source?: string | null;
  organizers: { name: string | null; email: string | null; logo: string | null; is_private: boolean; website: string | null; organization_id: string | null }[];
};
export type DetailMessages = {
  follow: string; following: string; followSeries: string;
  loading: string; error: string; retry: string; notFound: string; allEvents: string;
  date: string; location: string; startingFrom: string; cancelled: string; description: string;
  organizers: string; noOrganizers: string; organizerProfile: string; website: string;
  route: string; map: string; showMap: string; mapLoading: string; directions: string;
  gallery: string; openImage: string; close: string; previous: string; next: string; imageUnavailable: string;
  calendar: string; reminder: string; report: string; invite: string; attend: string;
  loginRequired: string; share: string; copyLink: string; shareCopied: string; copyFailed: string;
  login: string; email: string; emailOptional: string; reportDescription: string; markCancelled: string; sendReport: string; sendInvites: string; chooseFriends: string; noFriends: string; friendsError: string; inviteSent: string; actionError: string; sending: string; saved: string; cancelAttendance: string; anonymousOrganizer: string; noDescription: string; facebook: string; shareFacebook: string; unknownTime: string;
};
export type Occurrence = {
  id: string; url: string; date: string; start_time?: string | null; end_time?: string | null;
  cancelled?: boolean; selected?: boolean;
};
export type DetailProps = {
  id: string; endpoint: string; locale: string; canonicalUrl: string; authenticated: boolean; csrfToken?: string;
  initialAction?: 'attend' | 'invite' | null; onIntentConsumed?: () => void;
  coverSource?: string | null;
  urls: { listing: string; login: string; loginInvite?: string; calendar: string; reminder: string; report: string;
    invite: string; friends: string; like: string; unlike: string; attendance: string; followOrganization?: string; unfollowOrganization?: string; followRecurring?: string; unfollowRecurring?: string; organizationPrefix: string; tagPrefix: string };
  messages: DetailMessages;
  series?: { title: string; occurrences: Occurrence[] };
  onSelect?: (id: string, url: string) => void;
  onLoaded?: (event: DetailEvent) => void;
  followedOrganizations?: string[]; followableOrganizations?: string[];
  recurringTargetId?: string | null; recurringFollowing?: boolean;
  onOrganizationFollowChange?: (id: string, following: boolean) => void;
  onRecurringFollowChange?: (following: boolean) => void;
};
