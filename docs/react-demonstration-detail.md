# Client-side demonstration detail migration

The maintainer selected direct browser-to-Go reads on29October2026. Flask must
not wait for the Go event request before its first byte. This supersedes the
server-side API-primary proposal. This phase adds no new routing framework,
authentication system, database schema or dependency stack.

## Ownership and portable contracts

- `frontend/src/pages/DemonstrationDetailPage.tsx` receives typed API/route/text
  props. It renders a page, not mutations of the previous Jinja DOM.
- `components/detail/useDemonstration.ts` owns validated event reads, request
  cancellation, deadline, retry and distinct404/error/loading states. Credentials
  are omitted. Changed routes never display another event's stale response.
- `components/detail/types.ts` separates the API DTO, host routes/text and screen
  props. It can move to a full React application without changing the Go contract.
- Gallery, sanitized rich text, route/facts/organizers and on-demand map use
  component state. Map code splits through React.lazy/Suspense and loads only
  after activation. Browser routing lives in the entry adapter, so a future
  router can replace it without rewriting the page. No React Router/Next setup
  or second global data/state library is introduced for this slice.
- `entries/detail.tsx` adapts the current browser/history and resource URLs. A
  series change also changes action targets, login return path, document title
  and back/forward state. It never embeds Flask authorization in the component.
- Public URLs from API content cross a protocol boundary before use; rich HTML
  is rebuilt from a small allowlist. Event content cannot contribute executable
  attributes, scripts, SVG, styles, forms or arbitrary iframes.

## Thin Flask shell and scope

Enable `PUBLIC_DETAIL_REACT_ENABLED: true`. Browser API base is configurable as
`PUBLIC_DEMONSTRATION_API_URL` and defaults to
https://api.mielenosoitukset.fi/api/demonstrations. This is a public address, not
a MongoDB URI. Development/capture sets it to the actual local Go server.

Public routes use one projected metadata read for normal identifiers,
with the existing alias/number/slug priority. No Demonstration constructor,
normalization writes, geocoding, organizer enrichment, similar-events queries,
server-to-Go HTTP or full old detail-template rendering happens on this path.
Public visibility is checked before metadata, including malformed flags.
Cancellation notices remain accessible. Canonical series redirects and selected
occurrence URLs continue to use the current parent/chooser logic.

Title, description, canonical, OpenGraph, Twitter, Event JSON-LD and noindex rules
are present in the HTML before JavaScript. This is metadata SSR, not duplicate
SSR of the page body. No-JS visitors receive a readable summary and a a link to the listing and calendar; network failures offer same-view retry. An API404 is
shown as unavailable, not replaced with stale metadata. Search indexing of a
client-rendered body still depends on crawler JavaScript support; no equivalence
to full SSR indexing is claimed.

There is one public detail view for both authenticated and anonymous users.
Classic/overview cookies and old public layout parameters do not select another
view when this migration is enabled. Only authorized nonpublic internal previews
retain their separate privileged view.

Reminder, report and friend invitation forms use React dialogs and useActionState,
with explicit submission, pending/error feedback and retained field values. They
call existing same-origin Flask workflows; success requires a JSON acknowledgement,
not a followed redirect. The report route adds a validated JSON acknowledgement
while preserving native form redirects. Attendance and following stay on existing
account endpoints; the open Go API receives no account cookies. Login intent and
selected-occurrence action targets are preserved. Administrative toolbox permissions
are still computed on the host, never inferred by React.

The organizer DTO preserves anonymous private-organizer placeholders. It includes
an email only when the stored public-email consent flag is exactly booleantrue;
unconsented contact data is stripped by Mongo projection and payload validation.
The selected occurrence's cover_source comes from its API data, not stale shell
metadata. The read screen and account adapters remain separate, portable modules.

## Verification and rollback

Focused route tests cover metadata-only rendering, public/nonpublic boundaries,
identifier compatibility, cancellation, series selection and account workflows. Browser checks must use the real Flask and Go services with isolated
synthetic data. Existing visual acceptance remains mandatory at390/1440px in
both themes, including affected error/loading/modal/focus states. No new visual
CI suite and no bulk latency reruns are part of this migration.

Rollback by disabling PUBLIC_DETAIL_REACT_ENABLED; public URLs and original
workflows remain present. Go deployment is independent. This opt-in feature is
not a claim that every detail flow, role or the whole frontend has migrated.
