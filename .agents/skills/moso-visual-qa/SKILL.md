---
name: moso-visual-qa
description: Verify rendered mielenosoitukset.fi UI changes with screenshots and independent visual acceptance. Use for changes to templates, styles, browser behavior, translations or backend data affecting a screen; not for backend-only work with no rendered impact.
---

# Moso visual acceptance

Read `docs/ADMIN_UI_STANDARD.md` and `docs/visual-qa.md`. Run this workflow in the
current conversation, not as an additional GitHub test suite or model API job.
Preserve the existing product language, roles, routes and security. This is a
quality gate, not permission to redesign a page or import Hallmark's aesthetic.

## Implementer

- Identify the affected routes, roles and states before changing code. Capture
  the existing version for comparison; never reset another person's checkout.
  For a new screen use an approved comparable component/reference. If neither
  exists, disclose that and have the independent reviewer assess the new design.
- Render the real Flask application with seeded, non-sensitive data and actual
  styles/assets. Do not use `file://` templates, mock HTML or substitute fonts
  while claiming production fidelity. Record unavailable resources.
- After each UI-affecting fix recapture the affected states. Use existing
  relevant tests when needed, not a second suite/full CI rerun for screenshot
  review. At minimum check 390px and 1440px in BOTH themes. Add affected error,
  empty/loading, modal, focus, long-text/localized and permission-specific states.
  Capture the actual changed screen, not a fixed unrelated page matrix. Reuse
  unchanged evidence only when its rendered inputs/source really did not change;
  shared-style changes require representative consumer checks too.
- Inspect viewport-sized captures plus readable crops/full-page context where
  needed. A giant downscaled full-page image alone is insufficient. Check
  spacing/alignment, hierarchy, typography, contrast, control consistency,
  clipping, wrapping, mobile actions and visual similarity to shared components.
- Record final HEAD, changed files/content hashes and screenshot paths/hashes
  in a compact review packet in this conversation. Include role/state/viewport/
  theme/locale and missing assets. Include uncommitted/untracked source, not just
  the last commit SHA; changed working-tree code can invalidate the evidence.
- Give a **separate reviewer agent** the packet/images, before/reference
  images, affected scope and design standard. Use fresh context, not your own
  verdict. Do not ask it to approve, supply a desired score or hide limitations.
  It may inspect but must not edit implementation, approve a different snapshot,
  regenerate captures or write to the implementation worktree.

## Independent reviewer

Open every submitted screenshot using image-capable tools. Checking paths or
reading test results is not visual review. Compare before/reference and final
images at readable scale. Review the actual changed states and relevant shared
consumers. Return one verdict: **FIX**, **BLOCKED**, or **SHIP**, with specific
findings, reviewed image paths/digests, scope, limitations and source snapshot.
Reject a self-review request. Missing/illegible captures, missing necessary
states/assets or unavailable image tools require BLOCKED. Existing unrelated
defects may be recorded separately; new/worsened visual defects require FIX.
Do not certify the whole product from a few representative pages.

## Final gate

Only the independent reviewer can issue SHIP. Record its actual verdict in this
conversation, with the exact reviewed source/images and remaining limitations.
Do not invent a reviewer, self-approve, or relabel a technical pass as SHIP.
Any rendering-affecting source change after review invalidates it;
fix → relevant checks → fresh captures → independent review repeats until SHIP.
No JSON receipt, PR approval bot, extra CI workflow or paid API is required.
If reviewer tools/capacity are unavailable, report BLOCKED and leave visual
acceptance open.
Do not keep spending on unbounded cosmetic revisions: after two unsuccessful
review/fix rounds, report the remaining findings for direction. Do not bypass
the gate, rewrite the user's goal, merge or deploy merely to finish the loop.
