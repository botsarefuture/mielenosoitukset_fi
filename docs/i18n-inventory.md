# Translation inventory (I18N-01)

Snapshot: 11 November 2026. The public site is Finnish-only. English and Swedish
copy belongs to human translators; this task changes no translations or runtime
behaviour. Do not enable another public language just because a catalog exists.

## Reproduce the inventory

Run from the repository root with Python 3; no installed packages are needed:

```sh
python3 scripts/i18n_inventory.py
python3 scripts/i18n_inventory.py --json > /tmp/i18n-inventory.json
python3 scripts/i18n_inventory.py --check
python3 -m unittest tests.test_i18n_inventory
```

The first command regenerates the tables between the markers below. Replace that
section after source changes, then run `--check`. JSON contains every counted
candidate's file, line, source text, family and placement/scope, plus all PO
entries, their flags, translations and line numbers. It is the detailed translator
worklist; search it by family, then read the surrounding source before translating.
The script reads files only and works from any working directory.

### Counting rules and limits

- **PO counts are exact physical entries**, excluding the empty-msgid metadata
  header. Total includes obsolete entries; active excludes them. Unique active
  keys use `(msgctxt, msgid)`. Empty means every `msgstr`/plural form is empty;
  a partly filled plural is separate. Fuzzy and empty can overlap. Duplicate
  definitions include obsolete/live collisions because GNU `msgfmt` rejects
  those too. The duplicate table gives **msgid lines**, not msgstr diagnostics.
- **UI counts are static candidates, not a complete linguistic audit.** React
  counts Finnish-looking quoted/template literals, JSX text and accessible
  labels using Finnish characters and a small Finnish word list. Comments,
  tests, declarations (`.d.ts`), URLs and obvious language-neutral identifiers
  are excluded. Nested template expressions use `${…}` placeholders. Some short
  ASCII-only Finnish, generated strings and unusual syntax can be missed.
- Template candidates include visible text, title/description blocks, accessible
  attributes and Finnish string literals in Jinja expressions and inline scripts outside `_()`,
  `gettext()`, `ngettext()` and `{% trans %}`. English unwrapped HTML text is also
  included: it bypasses localization just like Finnish. Comments, style contents
  and obvious technical values are excluded. External JavaScript files are
  **not** inventoried here; inline script candidates have their own JSON kind.
- An occurrence is a source location, not a word or rendered repetition. Unique
  text collapses whitespace and HTML entities; a paragraph counts once. Family
  unique counts overlap, so do not add them to get the global unique total.
  Dynamic fragments, abbreviations and placeholders still need human triage.
- Grouping follows file ownership, not an import graph or production traffic.
  Shared shell/other includes cross-route metadata and fallbacks in `render.tsx`
  and `routes.tsx`, plus authentication and maintenance. No strings are moved
  into a second route total just because that route imports a shared component.
- “Copy module” means a named TypeScript copy/data object, **not** gettext
  integration. “Absent PO” counts distinct candidate texts missing as exact
  active, context-free msgids in that locale; it does not mean the other texts
  are translated, correct, compiled or actually used by React.
- Public rollback means the root migrated-page templates plus `kampanja/`,
  `pride-nakyvaksi/`, `ohjeet/`, `upcoming/` and `organizations/`. Other
  Flask/shared includes accounts, developer pages, errors, shared layouts and
  old manuals; these must not be mistaken for retired public rollback pages.
  Admin directories and emails are separate. This is an ownership inventory,
  not proof that a particular template is currently served in production.

## Catalogs and compilation

Gettext source catalogs are
`mielenosoitukset_fi/translations/{fi,en,sv}/LC_MESSAGES/messages.po`; sibling
`messages.mo` files are committed runtime catalogs. `messages.pot` is the source
message template. `babel.cfg` extracts Python, Jinja HTML and
`static/js/**/*.js`, **not `frontend/src` TypeScript/TSX**.

Existing extraction and compilation instructions are in `TRANSLATING.md`:

```sh
bash scripts/extract_translations.sh /tmp/messages.pot
# After humans reconcile the source catalogs and review their translations:
pybabel compile -d mielenosoitukset_fi/translations
```

Extraction alone does not update PO/MO files. The normal compile command writes
MO files; do not run it as part of this documentation task. Fuzzy entries need
review and are not normally compiled. An edited PO is not evidence that the
committed MO contains its latest translations.

Read-only compilation checks performed for this inventory:

```sh
msgfmt --check -o /dev/null mielenosoitukset_fi/translations/en/LC_MESSAGES/messages.po
msgfmt --check -o /dev/null mielenosoitukset_fi/translations/sv/LC_MESSAGES/messages.po
```

Both fail: English has 14 duplicate-definition errors and Swedish has 17.
English's duplicates are live/obsolete collisions. Swedish also has the live/live
`tapahtuma` duplicate. Humans should reconcile definitions without discarding
useful translations; do not blindly delete matching source text or obsolete
history. These failures were observed with GNU `msgfmt`, not inferred only from
the Python parser. No catalog was changed or recompiled.

## Regenerated numbers

<!-- i18n-inventory:start -->

### Gettext totals

| Locale | Total msgids | Active entries | Unique active keys | Empty | Fuzzy | Obsolete | Partial plurals | Duplicate keys |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| en | 3188 | 3104 | 3104 | 2167 | 185 | 84 | 0 | 14 |
| sv | 3202 | 3105 | 3104 | 2456 | 0 | 97 | 0 | 17 |

### Duplicate definitions

| Locale | msgid | PO lines |
| --- | --- | --- |
| en | `Ei saatavilla` | 1944, 13216 (obsolete) |
| en | `Kieli` | 3054, 13210 (obsolete) |
| en | `Käyttäjien hallinta` | 126, 13198 (obsolete) |
| en | `Mielenosoituksen tunniste puuttuu.` | 2245, 13186 (obsolete) |
| en | `Mielenosoitus luotu onnistuneesti.` | 4624, 13183 (obsolete) |
| en | `Mielenosoitus päivitetty onnistuneesti.` | 4611, 13180 (obsolete) |
| en | `Mielenosoitusta ei löytynyt.` | 44, 13177 (obsolete) |
| en | `Mielenosoitusten hallinta` | 136, 13204 (obsolete) |
| en | `Organisaatio luotu onnistuneesti.` | 4771, 13192 (obsolete) |
| en | `Organisaatioiden hallinta` | 131, 13201 (obsolete) |
| en | `Päivämäärä:` | 5184, 13252 (obsolete) |
| en | `Seuraa` | 5512, 13418 (obsolete) |
| en | `Superkäyttäjän käsikirja` | 121, 13195 (obsolete) |
| en | `Toistuvien mielenosoitusten hallinta` | 141, 13207 (obsolete) |
| sv | `Ei saatavilla` | 1976, 3575 (obsolete) |
| sv | `Kieli` | 3036, 3569 (obsolete) |
| sv | `Käyttäjien hallinta` | 119, 3557 (obsolete) |
| sv | `Mielenosoituksen tunniste puuttuu.` | 2257, 3545 (obsolete) |
| sv | `Mielenosoitus luotu onnistuneesti.` | 3542 (obsolete), 4981 |
| sv | `Mielenosoitus päivitetty onnistuneesti.` | 3539 (obsolete), 4969 |
| sv | `Mielenosoitusta ei löytynyt.` | 40, 3536 (obsolete) |
| sv | `Mielenosoitusten hallinta` | 127, 3563 (obsolete) |
| sv | `Organisaatio luotu onnistuneesti.` | 3551 (obsolete), 5125 |
| sv | `Organisaatioiden hallinta` | 123, 3560 (obsolete) |
| sv | `Päivämäärä:` | 3623 (obsolete), 5571 |
| sv | `Seuraa` | 3830 (obsolete), 5914 |
| sv | `Superkäyttäjän käsikirja` | 115, 3554 (obsolete) |
| sv | `Toistuvien mielenosoitusten hallinta` | 131, 3566 (obsolete) |
| sv | `Virhe: ` | 3735 (obsolete), 12379 |
| sv | `Virheen kuvaus` | 3614 (obsolete), 6855 |
| sv | `tapahtuma` | 13128, 13158 |

### Main TypeScript catalog

| Locale | Finnish keys | Explicit overrides | Missing overrides | Identical to Finnish |
| --- | --- | --- | --- | --- |
| en | 70 | 70 | 0 | meta.title |
| sv | 70 | 70 | 0 | meta.title |

### Finnish-only typed message objects

| File | Finnish keys | Missing en overrides | Missing sv overrides |
| --- | --- | --- | --- |
| `frontend/src/app/detail.ts` | 70 | 70 | 70 |
| `frontend/src/app/submit-copy.ts` | 122 | 122 | 122 |

### React Finnish candidates

| Family | Occurrences | Unique text | Copy module | Inline | Absent en PO | Absent sv PO |
| --- | --- | --- | --- | --- | --- | --- |
| API docs | 7 | 6 | 0 | 7 | 2 | 2 |
| Campaign and fundraising | 97 | 88 | 23 | 74 | 76 | 76 |
| Cities and calendar | 83 | 64 | 0 | 83 | 48 | 48 |
| Contact | 22 | 20 | 2 | 20 | 5 | 5 |
| Detail | 74 | 73 | 70 | 4 | 2 | 2 |
| Home and listings | 69 | 53 | 68 | 1 | 10 | 10 |
| Information pages | 205 | 202 | 9 | 196 | 140 | 140 |
| Organizations | 54 | 51 | 28 | 26 | 26 | 26 |
| Pride | 24 | 24 | 0 | 24 | 2 | 2 |
| Shared shell and other | 141 | 119 | 37 | 104 | 74 | 74 |
| Status | 12 | 10 | 0 | 12 | 9 | 9 |
| Submit | 159 | 149 | 124 | 35 | 52 | 52 |
| Suggestion forms | 76 | 70 | 0 | 76 | 18 | 18 |

### Template unwrapped copy candidates

| Scope | Family | Occurrences | Unique text |
| --- | --- | --- | --- |
| Public rollback | API docs | 0 | 0 |
| Public rollback | Campaign and fundraising | 104 | 97 |
| Public rollback | Cities and calendar | 0 | 0 |
| Public rollback | Contact | 1 | 1 |
| Public rollback | Detail | 0 | 0 |
| Public rollback | Home and listings | 21 | 21 |
| Public rollback | Information pages | 116 | 113 |
| Public rollback | Organizations | 0 | 0 |
| Public rollback | Pride | 2 | 2 |
| Public rollback | Shared shell and other | 0 | 0 |
| Public rollback | Status | 8 | 7 |
| Public rollback | Submit | 11 | 10 |
| Public rollback | Suggestion forms | 1 | 1 |
| Other Flask/shared | Detail | 45 | 39 |
| Other Flask/shared | Home and listings | 2 | 2 |
| Other Flask/shared | Information pages | 499 | 403 |
| Other Flask/shared | Shared shell and other | 219 | 166 |
| Email | Campaign and fundraising | 37 | 33 |
| Email | Organizations | 21 | 21 |
| Email | Shared shell and other | 294 | 191 |
| Email | Submit | 30 | 23 |
| Email | Suggestion forms | 29 | 28 |
| Admin | Campaign and fundraising | 23 | 19 |
| Admin | Shared shell and other | 118 | 107 |
| Admin | Status | 35 | 35 |

React total: **1023 occurrences / 842 unique texts**. Templates: **1616 occurrences / 1249 unique texts**.

<!-- i18n-inventory:end -->

## Clearly wrong existing translations

These are findings, not replacement translations. All five English entries are
already marked fuzzy. Leave the correction and approval to human translators.
Paths below are relative to `mielenosoitukset_fi/translations/`.

| Catalog location | msgid | Existing msgstr | Why it needs review |
| --- | --- | --- | --- |
| `en/LC_MESSAGES/messages.po:1339` | `Takaisin` | `Starts at ` | A navigation action is paired with event start-time wording. |
| `en/LC_MESSAGES/messages.po:25` | `Virheellinen päivämäärän muoto. Ole hyvä ja käytä muotoa vvvv-kk-pp.` | `Incorrect date format. Please use the format dd.mm.yyyy.` | The instructed date format contradicts the source format. |
| `en/LC_MESSAGES/messages.po:34` | `Esikatselukuva ei löytynyt.` | `Demonstration not found.` | The missing object is a preview image, not the event. |
| `en/LC_MESSAGES/messages.po:39` | `Vain ylläpitäjät voivat suositella mielenosoituksia.` | `No demonstrations found` | A permission restriction is replaced by an empty search result. |
| `en/LC_MESSAGES/messages.po:49` | `Mielenosoituksen päivämäärä puuttuu.` | `Title of the demonstration` | A missing-date error is replaced by a title field label. |

No comparably obvious Swedish mismatch was established in this focused review.
That is not a Swedish quality approval; empty entries and all existing copy still
need human review. Fuzzy text may differ from what the current MO actually shows.

## React route worklists

Paths in this section are relative to `frontend/src/`. The generated table gives
occurrences, distinct candidate texts and PO gaps for each family. Existing
TypeScript translations do not come from PO/MO files.

| Family and routes | Copy ownership and representative source strings |
| --- | --- |
| Home and listings: `/`, `/demonstrations`, `/city/:city`, `/tag/:tag`, event series | `app/i18n.ts` owns home/card copy: `Tulevat mielenosoitukset`, `Hae`, `Peruttu`. `app/listing.ts` owns Finnish-only listing messages; `pages/PublicListingPage.tsx` still has inline copy. `components/listings/` mostly consumes message props; Flask islands can receive gettext-backed props, while the standalone host supplies its own copy. |
| Detail: `/demonstration/:identifier` | `app/detail.ts` has a typed Finnish catalog, but **both en and sv alias fi**, so all its keys lack locale overrides. Examples: `Seuraa`, `Kopioi linkki`, `Kerro virheestä`. Inline errors/metadata also occur in `app/detail-route.ts` and `components/detail/useDemonstration.ts`; `content.ts` is a helper, not a translation catalog. |
| Cities and calendar: `/cities`, `/calendar/...`, `/city/:city/calendar/...`, today routes | Inline in `pages/CitiesPage.tsx`, `components/cities/CityDirectory.tsx`, `app/Calendar*.tsx`, `app/YearCalendarScreen.tsx`, `app/TodayScreen.tsx`, and `app/calendar.ts`. Examples: `Edellinen vuosi`, `Edellinen kuukausi`, `Suomessa`. No locale message catalog; `app/cities.ts` is a city-data helper. `Intl` calls hard-code `fi-FI`; city names/inflected phrases come from shared city data outside this scan. |
| Submit: `/submit` | `app/submit-copy.ts` has typed Finnish messages, but `translations` is empty. Examples: `Aika ja paikka`, `Järjestäjät`, `Kiitos ilmoituksestasi!`. Inline labels also occur in `components/submit/` and `app/SubmitFallback.tsx`. The exact key count includes neutral placeholders that translators should preserve. |
| Information: `/info`, `/ohjeet`, `/privacy`, `/terms`, `/upcoming/translations/` | `app/information.ts` is a Finnish metadata catalog only. Most body copy is inline in `app/information/*Content.tsx`. Examples: `Tietosuojaseloste`, `Käyttöehdot`, `Ohjeet järjestäjille`. Translate full paragraphs, not isolated words from legal or privacy sentences. |
| Campaign and fundraising: `/kampanja`, `/keräys`, confirmation/island views | `app/campaign-route.ts` and `data/campaign.ts` contain Finnish copy/data objects. Inline copy in `pages/CampaignPage.tsx`, `pages/ConfirmationPage.tsx`, `components/VolunteerForm.tsx` and `app/FundraisingScreen.tsx`. Examples: `Keräys avoinna`, `Jotta mielenosoitukset löytyvät`, `Mihin varat käytetään?`. No en/sv route catalog. Preserve payment identifiers and placeholders; translating copy does not authorize donations or change collection status. |
| Contact: `/contact` | `app/contact-route.ts` has a small Finnish copy object; `app/ContactScreen.tsx` has inline labels, categories, errors and confirmation text. Examples: `Ota yhteyttä`, `Tukipyyntö`, `Muu`. No en/sv message catalog. |
| Status: `/status` | Inline in `app/StatusScreen.tsx` and constants in `app/status.ts`; no locale catalog. Examples: `Kaikki palvelut toimivat`, `Jokin palvelu ei vastaa`, `Päivitetty:`. Include failure states and check descriptions. |
| API docs: `/api-docs/` | Inline shell in `app/ApiDocsScreen.tsx`: `API-dokumentaatio`, `API:n perustiedot`, `Sisältö`. **Body copy is outside frontend/src**: `frontend/render-api-docs.py` renders `docs/api.md` at build time. The React count covers only the shell, not the Markdown documentation. Do not translate API paths, code samples or field identifiers. |
| Suggestion forms: `/suggest_change/:id`, `/organization/:id/fill` | Inline in `app/SuggestChangeScreen.tsx`, `app/OrganizationFillScreen.tsx`, `app/suggest-change.ts` and `app/suggest-change/*.tsx`. Examples: `Verkkosivusto puuttuu`, `Sähköposti puuttuu`, `Logo lisätty`. No locale catalog. Preserve Markdown and form field contracts. |
| Organizations: `/organization/:id` | `components/organization/copy.ts` is Finnish-only. `app/OrganizationScreen.tsx` and chat components also have inline strings. Examples: `Vahvistettu organisaatio`, `Täydennä tiedot`, `Pysy ajan tasalla`. |
| Pride: `/pride-nakyvaksi` and aliases | Inline in `app/PrideScreen.tsx` and `components/pride/PrideMap.tsx`; no locale catalog. Examples: `Pride näkyväksi`, `Ilmoita Pride-mielenosoitus`, `Avaa mielenosoitus`. |
| Shared shell/other: every route, login, maintenance | `app/i18n.ts` has existing en/sv overrides for every Finnish key; the only identical value is the site brand at `meta.title`, not an error. Home/card source copy in that file is counted under home/listings. Inline copy remains in `app/App.tsx`, `app/render.tsx`, `app/routes.tsx`, `app/discovery-meta.ts`, `app/GodScreen.tsx`, `app/MaintenancePage.tsx`, header components and session helpers. Examples: `Ladataan kirjautumista...`, `Palvelu ei ole juuri nyt käytettävissä`, `Sivu toimii parhaiten, kun JavaScript on käytössä.` |

No other `messages`/catalog file bridges the standalone React copy to gettext.
The main TypeScript catalog's existing translations should be reviewed/reused,
not commissioned a second time. A developer must later wire approved human
copy into the responsible TypeScript objects/components; editing PO alone cannot
localize these screens. Keep current URLs, interpolation values, account flows
and Finnish fallback behaviour unchanged during that later work.

## Flask templates

All paths here are under `mielenosoitukset_fi/templates/`. The generated table
separates rollback pages, other Flask/shared surfaces, emails and admin. Zero
means no candidate was found by these rules, **not** a promise of full coverage.
Strings already inside `_()` are excluded even when their PO entry is empty.

- **Public rollback:** the largest unwrapped families are information
  (`ohjeet/index.html`, e.g. `Ohjekeskus`, `Ohjeet järjestäjille`) and campaign/
  fundraising (`fundraising.html`, `kampanja/_campaign_fallback.html` and
  confirmation fallbacks). Status titles and descriptions are unwrapped in
  `status.html`. `contact.html:58` contains `Täytä alla oleva lomake ja lähetä,
  niin olemme sinuun yhteydessä!`; submit retains `Poista kuva` and string
  literals in `submit_react.html`. `list_legacy.html` retains Finnish metadata and script-generated labels.
  Pride's page title is also literal. See the table for every family's count.
- **Mostly wrapped rollback families:** API docs, city/calendar templates,
  detail and suggestion forms have no counted unwrapped copy. Organization
  completion retains the inline-script label `Valitse alusta`.
  Their `_()` calls can still resolve to untranslated/fuzzy PO entries. Keep
  them compatible for rollback; do not build a second localization system there.
- **Other Flask/shared:** `manuals/` and `manual_base.html` retain extensive
  literal instructions; this is not the React `/ohjeet` page. Shared layouts,
  error pages, account/auth and developer templates also need review. Treat
  `demo_views/` and preview/cancellation views separately from the React detail
  screen. External static JavaScript still needs a separate extraction pass.
- **Email:** literal subjects/bodies exist under `emails/`, including auth,
  moderation, contact/support and campaign messages. These counts are separated
  from screen copy; coordinate the actual message work with I18N-02.
- **Admin, lower priority:** `admin/`, `admin_V2/` and `admin_base.html` are not
  public rollback templates. The biggest counted files are
  `admin_V2/governance/security.html`, `admin_V2/status.html` and
  `admin_V2/kampanja/list.html`; recurrence-form scripts also contain literals. Examples include
  `VAHVISTA`, `Infrastruktuuri`, `Kaikki järjestelmät toimivat` and English
  `Cover Photo`. Preserve identifiers, abbreviations and format specifiers
  when deciding which candidates actually need translation.

## Recommended translation order

Counts below are **distinct source candidates per family, for each target
language**, not additive estimates of new catalog keys. Deduplicate shared labels,
reuse correct existing translations and inspect JSON locations before assigning
work. Long information paragraphs cost more than one-word buttons.

1. Reconcile the duplicate definitions, then review the English fuzzy entries
   and the five obvious mismatches. Compilation is a prerequisite to shipping
   any gettext update. Review existing main TypeScript translations in parallel.
2. Core discovery: home/listings (53), detail (73), cities/calendar (64).
   Prioritize navigation, filters, empty/loading/error states and accessibility
   labels; include shared shell/metadata (119 candidates, some already covered).
3. Submission and corrections: submit (149), suggestion forms (70), contact
   (20), organizations (51). The typed detail and submit catalogs are ready for
   human copy but need en/sv wiring; never translate form field names or API data.
4. Information pages (202), then campaign/fundraising (88) and Pride (24).
   Keep privacy/terms meaning intact and involve the responsible human owners.
5. Status (10) and API-docs shell (6); schedule the separate `docs/api.md` body
   as a prose translation job, not as six UI messages.
6. Keep public rollback templates compatible using their separate table; then
   tackle other live Flask/shared pages and emails. Admin is last unless an
   operational need changes that priority. Existing PO empty totals are a
   whole-repository backlog, not extra strings to add to every route estimate.

This completes the inventory stage only. No catalog cleanup, translation,
extraction update, runtime wiring, route migration or language activation is part
of I18N-01. No rendered files changed, so screenshots and visual SHIP do not apply.
