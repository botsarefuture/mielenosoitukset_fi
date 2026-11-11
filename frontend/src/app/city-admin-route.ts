/** City admin applications (docs/city-admin-applications.md, phase 2). */
export const cityAdminPath = '/kaupunkiadmin';
/** Same-origin POST target that Apache routes to the Go API. */
export const cityAdminSubmitPath = '/kaupunkiadmin';
/** Same-origin GET of the signed-in user's own applications, routed to Go. */
export const cityAdminMinePath = '/kaupunkiadmin/hakemukset';

/** Cities the national admin team moderates; mirrors go-api/city_admin_status.go. */
export const nationallyManagedCities = new Set(['helsinki']);

export const cityAdminCopy = {
  title: 'Ryhdy kaupunkiadminiksi',
  description: 'Kaupunkiadminit tarkistavat oman paikkakuntansa mielenosoitusilmoitukset ja pitävät tiedot ajan tasalla.',
};

export const applicationStatusLabels: Record<string, string> = {
  received: 'Vastaanotettu', in_review: 'Käsittelyssä', approved: 'Hyväksytty',
  declined: 'Hylätty', withdrawn: 'Peruttu',
};
