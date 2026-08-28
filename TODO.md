# TODO — active task list

Consolidated list of fixes/features requested (so none are forgotten). Tick items off as they land.

## Overflow fixes

- [x] Ensure no overflow on public pages (reported for `/city/helsinki/tanaan`, cities pages)
  - [x] Header `.container` overflows viewport by 24–64px on the right (clips bell/user area)
  - [x] Header `.branding` pokes ~9px past viewport on mobile
  - [x] `.city-card` overflows ~6px past viewport on `/cities` at ~360px
- [x] Verify no horizontal page scroll / protruding elements on home, cities, city today pages at desktop + mobile widths
  - Verified via Playwright + Jinja harness at 320/360/390/768/1024/1440 (zero right-side offenders); live-site header also measured.

## Fixes
- [ ] Please ensure hero consistency between all the user facing pages!

## Features

- [x] Add an info/welcome email to people who sign up as translators
- [x] Allow all logged-in users to access the admin dashboard, but only show modules relevant to their role/job
- [x] On demo detail pages, hide the "Seuraa" (follow) button for organizations that cannot be followed
- [ ] Ensure that the user can enable 2fa in their settings!

## Process

- [x] Update CHANGELOG.md for every user-facing change