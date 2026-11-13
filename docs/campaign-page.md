# Campaign page (`/kampanja/`)

The page follows the maintainer-approved mockup v2.2 (13 November 2026). Copy, order and
states were reviewed there; change them only with the maintainer.

## Order

Hero (Tule mukaan, Tule avajaisiin, donate slot), Näin voit auttaa, Mistä on kyse (one
sticker image), Tietoa keräyksestä, Aikataulu, Tule mukaan (volunteer form), Avajaiset,
Pride näkyväksi, Usein kysyttyä, closing line. From the collection's opening day
"Tietoa keräyksestä" moves above "Mistä on kyse".

## One configuration

All dates and facts come from `mielenosoitukset_fi/utils/data/fundraising.json`, the file
the Go API serves as `GET /api/fundraising/details` (the host falls back to the bundled
copy when the API is down). The keys read by `frontend/src/app/campaign-schedule.ts`:

| Key | Meaning |
| --- | --- |
| `start_date`, `end_date` | collection period (planned dates when unset) |
| `campaign_start_date` | campaign starts |
| `opening_date`, `opening_time`, `opening_city`, `opening_city_in` | opening event (`opening_city_in` is the adessive, "Tampereella") |
| `marketing_week_start`, `marketing_week_end` | marketing week |
| `collection_number`, `area` | collection permit number and area |

A bad value falls back to the bundled default field by field. No component hardcodes a date.

## Phase

The host computes the Helsinki date per request (`private, no-store`, so nothing is cached
across a boundary) and passes it, with the configuration, to the page and the browser
bootstrap, so server and client render the same markup. The bootstrap never carries account
or payment fields. A milestone is reached on its first day: 16.11.2026, 16.2.2027 (the day
after the last collection day), 1.3.2027, 6.3.2027 and 3.5.2027. The latest reached one is
"Tässä ollaan nyt"; before the first one the next is labelled "Seuraavaksi"; after
9.5.2027 every milestone is done. Before opening the donate slot is the reminder
("Pienkeräys aukeaa 16.11." and "Tilaa muistutus" to `/keräys`); from the opening day it is
"Lahjoita keräykseen"; after the closing day it is gone.

## Publication gate

Unchanged: anonymous visitors are redirected to login until the campaign is published
(`GET /api/campaign/publication`); signed-in preview is `noindex`. This PR does not publish
anything.

## Opening interest form

Off until its UI and backend ship. Without it the opening cards link to the facts instead of
a form, and the timeline shows no sign-up link.

## Checks

`node --experimental-strip-types scripts/verify_campaign_schedule.mjs` covers every phase
boundary; `scripts/verify_public_host.mjs` covers the rendered sections, order swap and the
gate.
