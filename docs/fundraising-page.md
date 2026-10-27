# Fill in the fundraising page

The default is a Finnish **preparation page behind login** at `/keräys`. Empty official
fields have explicit public placeholders. No invented organizer, collection
number, payment details, amount raised or endorsements are published. The
€2,500 amount is a target. The supplied 15.11.2026–15.2.2027 period remains
proposed; the planned 10.11 notification is not a completed filing.

## One file to complete

Edit `mielenosoitukset_fi/utils/data/fundraising.json`:

| Field | Fill with |
| --- | --- |
| `organizer` | Confirmed official organizer's full published name |
| `collection_number` | Confirmed collection number |
| `start_date`, `end_date` | Confirmed dates as `YYYY-MM-DD`; empty by default |
| `planned_start_date`, `planned_end_date` | Proposed dates for preparation copy only; never enable payments |
| `recipient`, `iban` | Verified recipient and IBAN; required together for bank transfers |
| `reference` | Optional bank reference; leave empty if none is provided |
| `payment_url` | Optional verified HTTPS donation page; can replace bank instructions |
| `mobilepay_links` | Two ready entries with `label` and empty `url`; fill each with a confirmed, appropriate MobilePay payment link. Add more entries if needed. |
| `details_confirmed` | Set to `true` only after the information is verified |
| `publication_state` | Keep `"preparation"`; explicitly change to `"active"` when opening is authorized |
| `show_header_link` | Set to `true` to display “Tutustu pienkeräykseen” in the public header |

The header link points to the information page, not directly to payment.
Before public release it is visible only to authenticated users.
`/kampanja/` links to the page and has updated preparation copy. Existing
volunteer/newsletter fields and handlers remain. No event/supporter commitments
are invented. Service copy follows the existing `/info` page.

Internal campaign planning goals (not public campaign-page copy): 25,000 stickers, 8 Pride and 4 other banners, posters
without an invented count. The supplied sticker/banner estimate is €1,889.94,
not a final whole-campaign budget or proof of purchase. The source city's
distribution list and total disagree (the 100-sticker list names 11 cities while
its summary counts 10); detailed city allocations are deliberately unpublished
pending reconciliation. Targets are explicitly distinguished from delivery.

Donation instructions require confirmed complete details, explicit active state,
valid ordered dates and today's Helsinki date inside the collection period
(inclusive). With incomplete details or a closed period they remain hidden.
Unsafe payment URL schemes/credentials are discarded. These checks do not
verify registration, bank ownership or payment-provider legitimacy; the owner
must confirm those. No payment is processed by this app. Preparation never
changes itself into active state merely because a date arrives.

MobilePay links are ordinary anchors and can be the only payment method. Empty
entries are clearly marked as pending during preparation; no blank links are
rendered. Confirm suitability of the actual MobilePay product before publishing:
[MobilePay's current support guidance](https://help.vippsmobilepay.com/fi-FI/articles/how-much-does-it-cost-to-use-box)
restricts personal boxes to private purposes and excludes organizational fundraising.
The older linked PDF returned 404 during verification. Choose an appropriate
provider-approved product before publishing either slot; do not use personal boxes
for this campaign on the strength of this implementation.
The configurable slots do not establish provider approval or create any boxes.

Keep primary campaign costs (materials, implementation and travel) and secondary
service upkeep/continuity purposes distinct. The page is marked `lang="fi"`;
English/Swedish translations are not claimed. Navigation keeps its normal locale.

## Static fallback compatibility

The inspected implementation is in the separate recovery toolkit:
`scripts/dr/prepare_snapshot.py` and `scripts/dr/polish_snapshot.py` in
`mielenosoitukset-fi/recovery`, using the security console's `snapshot_site.py`.
It was inspected locally, not changed or deployed by this feature.

- After publication, `/keräys` is in the public sitemap even with header promotion off.
  Before publication, campaign/fundraising pages are omitted and anonymous access
  requires login. Never use an authenticated session to generate a public snapshot.
- All copy/bank instructions are server-rendered HTML; no donation widget, API,
  login, database write, JavaScript or QR generator is required. Payment uses an
  ordinary external HTTPS link.
- The introduction uses `section`, because the mirror polisher removes headers.
  Shared local CSS/product tokens use the toolkit's existing asset collector.
- A direct support email remains available without the contact form. The mirror
  strips campaign signup forms; they cannot accept entries while the app is down.
- A snapshot retains capture-time information and cannot reevaluate dates or
  revocations. Donation instructions state the exact permitted period and warn
  against donating after it. Refresh/replace the snapshot after status/payment
  changes and at closure. Live date gating is not static automatic closure.

The export/polish pipeline needs verification with the new page before claiming
deployed DR acceptance. No production/recovery-server deployment is included.

## Focused validation

From the repository root run:

```sh
python -m pytest tests/test_fundraising_page.py tests/test_campaign_volunteer_feedback.py -o addopts='' -q
```

Cases cover preview, activation, required fields, date boundaries, escaped
output, safe links, closure and opt-in header promotion. Existing volunteer
feedback cases protect preserved signup behavior. Real Flask browser captures
cover 390/1440px, both themes and JavaScript-disabled content; final evidence
and independent visual verdict belong in the PR. These are not provider-payment
tests or a production deployment check.

## Volunteer participation

The existing campaign section presents materials, social media, events and local
cooperation as ways to help, with tasks/timing still subject to planning. Existing
field names, JSON endpoint and one-day email-token confirmation remain unchanged.
The form explains required versus optional information and preserves accessible
validation, error text and retry data. Submission disables the button and exposes
busy state, then restores it after the response. Confirmation success is shown
only after an HTTP success with `success: true`.

Both JS-only signup fieldsets start disabled and are enabled only after their
handlers exist. Without JavaScript they cannot submit personal details through
an accidental GET. Explicit notices explain that nothing was submitted, with a
direct support email for volunteer questions. Newsletter integration is unchanged.
The DR pipeline removes forms; supporting copy/email stays available.

## Local verification on 26 October 2026

The focused fundraising/volunteer set passes 45 cases, including browser feedback,
validation, duplicate submission, no-JavaScript behavior and the unchanged
newsletter request contract. No real signup, mail or donation was sent.

The current recovery toolkit's `StaticHTML` and `polish()` are exercised against
synthetic active Flask HTML: intro, exact dates, recipient/IBAN, two payment links
and support email survive while scripts/forms are removed. This is an HTML-only
compatibility check; its asset hook deliberately skips retrieval. The complete
crawler/asset export, static HTTP delivery and deployed recovery remain unverified.
The toolkit source and servers are unchanged.

At closure or any change to official/payment information:

1. Set `publication_state` to `closed` (or return to `preparation`), deploy through
   the normal separately authorized release and check the public page.
2. Re-run the existing snapshot crawl → prepare → polish workflow in the recovery
   repository against that release. Replace every served/cached old snapshot.
3. Check the served snapshot at `/keräys`: old payment links/bank instructions
   must be gone; keep the historical period and support contact understandable.
4. Until replacement is verified, withdraw stale snapshot payment instructions.
   A live date check alone cannot close an already exported static copy.

Real Flask screenshot evidence is retained locally in
`/Users/emiliavuorenmaa/.codex/visualizations/2026/10/26/01a17871-2046-7f82-9665-7cc2acb6be9a/fundraising-final/`.
The review packet identifies the exact source/image digests, roles, locales,
viewports, states and excluded analytics requests. Independent visual acceptance
is recorded in the conversation and PR after reviewing this final snapshot.

## Admin-controlled publication

Both `/keräys` and `/kampanja/` (including the volunteer section) start behind
login. Any authenticated user can preview them. Missing, malformed or unreadable
publication state defaults to private. No deployment/migration automatically
publishes these pages. Existing volunteer email-confirmation tokens keep their
original validation/expiry behavior even while pages are private.

In **Hallintapaneeli → Kampanjan hallinta**, an administrator with global
`KAMPANJA` permission can press **Julkaise sivut kaikille**. This is a native POST
form with session-bound CSRF proof; no JavaScript is needed. The shared state is
persisted in MongoDB `campaign_settings`, `_id: public_pages`, with the boolean
`published`, actor and UTC timestamp. Request/session/CSRF material is excluded
from this action's audit entry. A scope-limited grant cannot publish globally.
The action reports write uncertainty without claiming success.

**Palauta kirjautumisen taakse** withdraws anonymous page/API access. Page and
admin responses use `private, no-store`, and preview responses are `noindex`.
The volunteer JSON endpoint returns 401 without writing a signup when a private
campaign is accessed anonymously. Publication also controls sitemap discovery
and anonymous header promotion, independently of the configured header flag.

This button controls visibility only. `fundraising.json` confirmation, explicit
payment activation and date checks remain necessary before any payment method is
shown. Republishing never fills official details or opens donations by itself.

A static copy already exported while public cannot re-check this database state.
Withdrawing pages must also withdraw/replace existing public snapshots and any
previously cached copies through the separately authorized recovery workflow.
The login gate does not establish authentication for an already exported mirror.


The campaign refresh deliberately removes public procurement quantities and cost
breakdowns from `/kampanja/`. The above planning figures are maintainer context,
not content to reinsert into that page. The fundraising information page keeps
its separate official details and target. The publication and donation gates
are unchanged by the React/page presentation work.
