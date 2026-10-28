export type Demonstration = {
  _id: string; title?: string; date?: string; formatted_date?: string; date_display?: string;
  start_time?: string | null; end_time?: string | null; start_time_display?: string | null; end_time_display?: string | null;
  latitude?: number | string | null; longitude?: number | string | null;
  city?: string; address?: string; tags?: string[]; cancelled?: boolean;
  cover_picture?: string; cover_image?: string; preview_image?: string; img?: string;
  detail_url?: string; slug?: string; running_number?: number; parent?: string;
};
export type Friend = { name: string; avatar?: string };
export type ListingMessages = {
  search: string; searchPlaceholder: string; city: string; location: string; startDate: string; endDate: string;
  dateError: string; year: string; month: string; submitSearch: string; removeFilter: string;
  loading: string; loadMore: string; loadingMore: string; previous: string; summary: string;
  loadError: string; retry: string; emptyTitle: string; empty: string; filteredEmpty: string;
  clearFilters: string; submitEvent: string; cancelled: string; today: string; startingFrom: string;
  loginPrompt: string; attendingSuffix: string; loadingFriends: string; invite: string; allEvents: string; endTime: string;
};
export type ListingProps = {
  title: string; headingLevel?: 1 | 2; locale: string; fixed: Record<string, string>; cities: string[]; authenticated: boolean;
  endpoint: string; attendanceEndpoint: string; allEventsUrl: string; submitUrl: string;
  detailUrl: string; seriesUrl: string; tagUrl: string;
  cover: string | null; coverAlt: string; messages: ListingMessages;
};
export type ListParams = Record<string, string | number>;
export type Page = { page: number; per_page: number; total_pages: number; total: number;
  result_start: number; result_end: number; results: Demonstration[] };
