/**
 * Portable contracts for the demonstration submission page.
 *
 * Flask supplies URLs, the submission token, the city list and translated
 * strings as escaped JSON props. Everything else (validation, drafts, request
 * building) lives here so the page can move to another host unchanged.
 */

/** One organizer row. `key` is React-local and never submitted. */
export type Organizer = {
  key: string;
  name: string;
  email: string;
  website: string;
  isPrivate: boolean;
  showName: boolean;
  showEmail: boolean;
};

/** Wizard steps. Step 6 is the delivered/success step. */
export const STEP_COUNT = 6;
export const LAST_INPUT_STEP = 5;

/** Editable values of the form, independent of DOM node ids. */
export type SubmitFields = {
  title: string;
  tags: string;
  defaultLanguage: string;
  descriptionHtml: string;
  date: string;
  startTime: string;
  endTime: string;
  eventType: string;
  route: string;
  city: string;
  address: string;
  submitterRole: string;
  submitterName: string;
  submitterEmail: string;
  acceptTerms: boolean;
  facebook: string;
  facebookImported: boolean;
  facebookImageUrl: string;
};

/** Translated copy the component renders. Supplied by the host application. */
export type SubmitMessages = {
  steps: string[];
  previous: string;
  next: string;
  submit: string;
  sending: string;

  introTitle: string;
  introLead: string;
  helpLink: string;
  draftNotice: string;
  draftReset: string;
  beforeSubmitTitle: string;
  beforeSubmitBody: string[];
  beforeSubmitGuides: string;

  choiceTitle: string;
  choiceLead: string;
  importTitle: string;
  importDescription: string;
  manualTitle: string;
  manualDescription: string;

  basicsTitle: string;
  basicsLead: string;
  facebookLabel: string;
  facebookPlaceholder: string;
  facebookHelper: string;
  importButton: string;
  importHelper: string;
  importEmptyUrl: string;
  importLoading: string;
  importFailed: string;
  importImported: string;
  importMissing: string;
  titleLabel: string;
  titlePlaceholder: string;
  titleHelper: string;
  tagsLabel: string;
  tagsPlaceholder: string;
  tagsHelper: string;
  languageLabel: string;
  languageHelper: string;
  descriptionLabel: string;
  descriptionHelper: string;
  imageLabel: string;
  imageHelper: string;
  removeImage: string;

  timePlaceTitle: string;
  timePlaceLead: string;
  dateLabel: string;
  datePlaceholder: string;
  dateFormatHelper: string;
  startTimeLabel: string;
  endTimeLabel: string;
  endTimeHelper: string;
  typeLabel: string;
  typePlaceholder: string;
  typeOption: Record<string, string>;
  routeLabel: string;
  routePlaceholder: string;
  routeHelper: string;
  routePreviewLabel: string;
  routePreviewEmpty: string;
  routePreviewHelper: string;
  cityLabel: string;
  cityPlaceholder: string;
  citySearch: string;
  cityNoMatch: string;
  addressLabel: string;
  addressPlaceholder: string;
  addressHelper: string;

  organizersTitle: string;
  organizersLead: string;
  organizerLabel: string;
  addOrganizer: string;
  organizerHelper: string;
  organizerSearchLabel: string;
  organizerSearchPlaceholder: string;
  organizerSearchHelp: string;
  organizerSearchEmpty: string;
  organizerSearchError: string;
  organizerName: string;
  organizerWebsite: string;
  organizerEmail: string;
  organizerPrivate: string;
  organizerShowName: string;
  organizerShowEmail: string;
  organizerPrivacyHint: string;
  removeOrganizer: string;

  contactTitle: string;
  contactLead: string;
  roleLabel: string;
  rolePlaceholder: string;
  roleHelper: string;
  nameLabel: string;
  namePlaceholder: string;
  emailLabel: string;
  emailPlaceholder: string;
  contactHelper: string;
  acceptTermsPrefix: string;
  termsLink: string;
  acceptTermsAnd: string;
  privacyLink: string;

  successTitle: string;
  successBody: string;
  backHome: string;
  newEvent: string;

  supportTitle: string;
  supportLead: string;
  supportContact: string;
  supportInfo: string;

  conflictTitle: string;
  conflictLead: string;
  conflictMatches: string;
  conflictCancel: string;
  conflictConfirm: string;

  errorGeneric: string;
  errorRateLimited: string;
  errorRequired: string;
  errorTerms: string;
  errorConflictCancelled: string;
  errorConflictForceFailed: string;
  errorCodeLabel: string;
};

/** Everything the page needs from Flask. */
export type SubmitPageProps = {
  action: string;
  importUrl: string;
  orgSearchUrl: string;
  termsUrl: string;
  privacyUrl: string;
  homeUrl: string;
  guidesUrl: string;
  contactUrl: string;
  infoUrl: string;
  token: string;
  cities: string[];
  locales: string[];
  localeNames: Record<string, string>;
  defaultLanguage: string;
  canEditDemo: boolean;
  messages: SubmitMessages;
};

/** A duplicate warning returned with HTTP 409. */
export type ConflictMatch = { title?: string; date?: string; address?: string };

export type ConflictData = {
  message?: string;
  demos?: ConflictMatch[];
};

/** A validation failure the page can focus. */
export type InvalidField = { name: keyof SubmitFields | 'organizers'; message: string };
