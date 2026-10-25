# In-conversation visual acceptance

Run `.agents/skills/moso-visual-qa/SKILL.md` for rendered UI changes. This is a
conversation workflow, **not another GitHub test job**. Existing functional and
component checks still apply; do not duplicate them or rerun the whole suite
merely to get a visual opinion.

## Review packet

The implementer supplies a compact packet with:

- Actual affected routes, roles, states and intended change; existing shared
  component/reference or before captures. Do not redefine the product's design.
- Final HEAD plus changed source files/content hashes, including uncommitted
  and untracked changes. A commit SHA alone is insufficient in a dirty worktree.
- Real rendered screenshots at 390px and 1440px, both light and dark, of the
  changed screen. Include relevant empty/error/loading/modal/focus and long or
  localized text states. Shared changes need representative consumer pages.
- Image paths/hashes, viewports, theme, locale, role/state, and missing resources.
  Use readable viewport/detail images plus full-page context as appropriate,
  not just a huge full-page image downscaled until defects disappear.

Use seeded disposable data. Do not include tokens, cookies, production contact
details or private correspondence. Render the actual application; a raw Jinja
file is not a page. Missing required fonts/styles/widgets must be disclosed and
block acceptance of affected rendering, not silently become substitutes.

## Separate reviewer

Dispatch a fresh-context reviewer agent with the packet, images and design
standard, not the implementer's desired verdict. The reviewer is read-only and
must open every supplied image with image-capable tools, inspect readable
details and compare to the reference. Check hierarchy, spacing, alignment,
typography, control consistency, text contrast/wrapping, clipping, mobile
actions and shared-component consistency. Paths existing or tests passing are
not proof that the images were reviewed or look good.

The reviewer returns **FIX**, **BLOCKED**, or **SHIP**, identifying reviewed
images/source and concrete findings/limitations. The implementer cannot supply
their own SHIP. No reviewer available means BLOCKED; no self-review fallback.
Do not certify the entire site from a few changed views.

## Every fix invalidates approval

After a UI-affecting correction: run necessary existing focused checks, take new
affected captures and obtain a fresh independent review. Do not reuse a SHIP
from earlier code/screenshots. Verify source/capture hashes have not changed
since review before saying ready. Reuse unchanged captures only when their
inputs/source are unchanged. After two unsuccessful fix/review rounds, report
remaining findings for direction instead of spending indefinitely or approving
anyway. Keep the visual gate open if blocked.

Record the outcome briefly here in the conversation:

> Visual review: SHIP / FIX / BLOCKED — independent reviewer; source snapshot;
> reviewed viewports/states/images; findings resolved; remaining limits.

There is no extra CI job, JSON approval receipt, new screenshot test suite,
automatic merge or deployment permission. GitHub checks cannot enforce whether
an agent actually looked at a picture; do not claim this conversational review
is branch protection. The goal is an honest, repeatable independent judgment.
