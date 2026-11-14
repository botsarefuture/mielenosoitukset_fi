# Finnish copy coverage and checklist

Snapshot: `050b3ed1c7ed9337a88cbfb5c5a55a857019d681`, 14 November 2026. Model: `gpt-6.1-sol`.

Inventory: **210 tracked HTML templates/pages** across the repository,
including retained Flask copies, email templates and the Apache error page;
every one is listed below. **133 React TS/TSX sources** are also listed,
including the excluded admin screen. Regenerate the file list with
`git ls-files "*.html" "frontend/src/*.ts" "frontend/src/*.tsx"` and compare
when new sources are added. Existing rows do not automatically cover new files.

The checkboxes mean **source text reviewed**, not “corrected”, “deployed” or
“visually accepted”. NO COPY records an inspected wrapper/helper, not a
language pass on its data source. REVIEWED / USAGE TODO means the text was
read but its current use must be established. UI TODO and EMAIL TODO remain
unchecked. Admin sources are listed for inventory completeness and excluded
from this task. New en/sv translations remain for humans.

## Ordered work

- [x] Inventory every tracked HTML template/page, including retained copies.
- [x] Inspect every non-admin React TS/TSX source: 74 copy owners/composers, 58 without owned Finnish prose.
- [x] Review public/shared and regular-user Flask template text; record unused/uncertain sources explicitly.
- [x] Record exact originals, replacements and reasons in [the audit](finnish-copy-audit.md).
- [x] Apply accepted text corrections and rebuild frontend assets; rejected and meaning-dependent proposals remain explicit.
- [ ] Finish partial backend/JS/documentation and runtime-context checks below.
- [ ] Obtain independent rendered acceptance for the final changed source/capture snapshot; source review alone is insufficient.
- [ ] Complete UI findings/context checks before starting user emails.
- [ ] Review user email HTML, subjects, shared macros and generated text after the UI phase.
- [ ] Implement the requested Claude → gpt-6.1-sol pre-merge Finnish review workflow (TODO FI-COPY-02).

## All tracked HTML templates/pages

Template states: EMAIL TODO: 32, EXCLUDED: 96, REVIEWED: 75, REVIEWED / USAGE TODO: 7.

| Source review | Source | State | Coverage / next action |
| --- | --- | --- | --- |
| [x] | [deploy/apache/rate-limit.html](../deploy/apache/rate-limit.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_layouts/demonstration-list.html](../mielenosoitukset_fi/templates/_layouts/demonstration-list.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_macros/_hero.html](../mielenosoitukset_fi/templates/_macros/_hero.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_macros/_pagination.html](../mielenosoitukset_fi/templates/_macros/_pagination.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_macros/_public_search.html](../mielenosoitukset_fi/templates/_macros/_public_search.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_macros/frontend.html](../mielenosoitukset_fi/templates/_macros/frontend.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_modals/past-demo-modal.html](../mielenosoitukset_fi/templates/_modals/past-demo-modal.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_modals/reminder-modal.html](../mielenosoitukset_fi/templates/_modals/reminder-modal.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_modals/report-error-modal.html](../mielenosoitukset_fi/templates/_modals/report-error-modal.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/_partials/demonstration-listing.html](../mielenosoitukset_fi/templates/_partials/demonstration-listing.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| — | [mielenosoitukset_fi/templates/admin/demonstrations/demo_diff.html](../mielenosoitukset_fi/templates/admin/demonstrations/demo_diff.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin/demonstrations/edit_history.html](../mielenosoitukset_fi/templates/admin/demonstrations/edit_history.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin/suggestion_view.html](../mielenosoitukset_fi/templates/admin/suggestion_view.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin/suggestions_list.html](../mielenosoitukset_fi/templates/admin/suggestions_list.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/_background_job_macros.html](../mielenosoitukset_fi/templates/admin_V2/_background_job_macros.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/_modals_users.html](../mielenosoitukset_fi/templates/admin_V2/_modals_users.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/_users_table.html](../mielenosoitukset_fi/templates/admin_V2/_users_table.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/analytics.html](../mielenosoitukset_fi/templates/admin_V2/analytics.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/background_job_detail.html](../mielenosoitukset_fi/templates/admin_V2/background_job_detail.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/background_jobs.html](../mielenosoitukset_fi/templates/admin_V2/background_jobs.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/cases/all.html](../mielenosoitukset_fi/templates/admin_V2/cases/all.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/cases/blocklist.html](../mielenosoitukset_fi/templates/admin_V2/cases/blocklist.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/cases/case.html](../mielenosoitukset_fi/templates/admin_V2/cases/case.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/cc/confirm_action.html](../mielenosoitukset_fi/templates/admin_V2/cc/confirm_action.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/cc/edit_link_unavailable.html](../mielenosoitukset_fi/templates/admin_V2/cc/edit_link_unavailable.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/cc/link_already_used.html](../mielenosoitukset_fi/templates/admin_V2/cc/link_already_used.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/cities/index.html](../mielenosoitukset_fi/templates/admin_V2/cities/index.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/cities/review_dashboard.html](../mielenosoitukset_fi/templates/admin_V2/cities/review_dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/dashboard.html](../mielenosoitukset_fi/templates/admin_V2/dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/_edit_link_modal.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/_edit_link_modal.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/_media_fields.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/_media_fields.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/_organizer_editor.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/_organizer_editor.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_log.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_log.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_timeline.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_timeline.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/command_center.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/command_center.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/confirm_delete.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/confirm_delete.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/form.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/form.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/magic_tokens.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/magic_tokens.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/merge.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/merge.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/review.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/review.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/submission_errors.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/submission_errors.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_dashboard.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_editor.html](../mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_editor.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/developer/requests.html](../mielenosoitukset_fi/templates/admin_V2/developer/requests.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/developer/user_apps.html](../mielenosoitukset_fi/templates/admin_V2/developer/user_apps.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/governance/_tabs.html](../mielenosoitukset_fi/templates/admin_V2/governance/_tabs.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/governance/audit.html](../mielenosoitukset_fi/templates/admin_V2/governance/audit.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/governance/clearances.html](../mielenosoitukset_fi/templates/admin_V2/governance/clearances.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/governance/dashboard.html](../mielenosoitukset_fi/templates/admin_V2/governance/dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/governance/security.html](../mielenosoitukset_fi/templates/admin_V2/governance/security.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/kampanja/list.html](../mielenosoitukset_fi/templates/admin_V2/kampanja/list.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/logs.html](../mielenosoitukset_fi/templates/admin_V2/logs.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/macros.html](../mielenosoitukset_fi/templates/admin_V2/macros.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/organizations/confirm_delete.html](../mielenosoitukset_fi/templates/admin_V2/organizations/confirm_delete.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/organizations/dashboard.html](../mielenosoitukset_fi/templates/admin_V2/organizations/dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/organizations/form.html](../mielenosoitukset_fi/templates/admin_V2/organizations/form.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/organizations/macros.html](../mielenosoitukset_fi/templates/admin_V2/organizations/macros.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/organizations/review_suggestion.html](../mielenosoitukset_fi/templates/admin_V2/organizations/review_suggestion.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/organizations/view.html](../mielenosoitukset_fi/templates/admin_V2/organizations/view.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/overall_24h_analytics.html](../mielenosoitukset_fi/templates/admin_V2/overall_24h_analytics.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/per_demo_analytics.html](../mielenosoitukset_fi/templates/admin_V2/per_demo_analytics.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form_v2.html](../mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form_v2.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/confirm_delete.html](../mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/confirm_delete.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/dashboard.html](../mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/site_analytics.html](../mielenosoitukset_fi/templates/admin_V2/site_analytics.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/site_demo_analytics.html](../mielenosoitukset_fi/templates/admin_V2/site_demo_analytics.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/stats.html](../mielenosoitukset_fi/templates/admin_V2/stats.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/status.html](../mielenosoitukset_fi/templates/admin_V2/status.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/super_audit/logs.html](../mielenosoitukset_fi/templates/admin_V2/super_audit/logs.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/tag_form.html](../mielenosoitukset_fi/templates/admin_V2/tag_form.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/ui_translations/dashboard.html](../mielenosoitukset_fi/templates/admin_V2/ui_translations/dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/ui_translations/editor.html](../mielenosoitukset_fi/templates/admin_V2/ui_translations/editor.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/ui_translations/sync_dashboard.html](../mielenosoitukset_fi/templates/admin_V2/ui_translations/sync_dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/user/_history.html](../mielenosoitukset_fi/templates/admin_V2/user/_history.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/user/account_status.html](../mielenosoitukset_fi/templates/admin_V2/user/account_status.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/user/api_tokens.html](../mielenosoitukset_fi/templates/admin_V2/user/api_tokens.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/user/confirm.html](../mielenosoitukset_fi/templates/admin_V2/user/confirm.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/user/edit.html](../mielenosoitukset_fi/templates/admin_V2/user/edit.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/user/history.html](../mielenosoitukset_fi/templates/admin_V2/user/history.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_V2/user/list.html](../mielenosoitukset_fi/templates/admin_V2/user/list.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/admin_base.html](../mielenosoitukset_fi/templates/admin_base.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| [x] | [mielenosoitukset_fi/templates/alarm.html](../mielenosoitukset_fi/templates/alarm.html) | REVIEWED / USAGE TODO | Text read; dormant, conditional or active usage unverified |
| [x] | [mielenosoitukset_fi/templates/api_docs.html](../mielenosoitukset_fi/templates/api_docs.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/base.html](../mielenosoitukset_fi/templates/base.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/cancel_demonstration.html](../mielenosoitukset_fi/templates/cancel_demonstration.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/cities.html](../mielenosoitukset_fi/templates/cities.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/city.html](../mielenosoitukset_fi/templates/city.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/contact.html](../mielenosoitukset_fi/templates/contact.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/cropper-modal.html](../mielenosoitukset_fi/templates/cropper-modal.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/demo_views/calendar_grid.html](../mielenosoitukset_fi/templates/demo_views/calendar_grid.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/demo_views/calendar_grid_old.html](../mielenosoitukset_fi/templates/demo_views/calendar_grid_old.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/demo_views/calendar_year.html](../mielenosoitukset_fi/templates/demo_views/calendar_year.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/detail.html](../mielenosoitukset_fi/templates/detail.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/detail_react.html](../mielenosoitukset_fi/templates/detail_react.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/developer/app_detail.html](../mielenosoitukset_fi/templates/developer/app_detail.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/developer/apps.html](../mielenosoitukset_fi/templates/developer/apps.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/developer/dashboard.html](../mielenosoitukset_fi/templates/developer/dashboard.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/developer/locked.html](../mielenosoitukset_fi/templates/developer/locked.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [ ] | [mielenosoitukset_fi/templates/emails/AM/cancellation_email.html](../mielenosoitukset_fi/templates/emails/AM/cancellation_email.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/AM/choose_shift.html](../mielenosoitukset_fi/templates/emails/AM/choose_shift.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/AM/confirm_participation.html](../mielenosoitukset_fi/templates/emails/AM/confirm_participation.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/AM/confirmation_email.html](../mielenosoitukset_fi/templates/emails/AM/confirmation_email.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/AM/reminder.html](../mielenosoitukset_fi/templates/emails/AM/reminder.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/AM/thank_you.html](../mielenosoitukset_fi/templates/emails/AM/thank_you.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| — | [mielenosoitukset_fi/templates/emails/admin_demo_approve_notification.html](../mielenosoitukset_fi/templates/emails/admin_demo_approve_notification.html) | EXCLUDED | Admin-recipient email |
| — | [mielenosoitukset_fi/templates/emails/admin_demo_city_assignment.html](../mielenosoitukset_fi/templates/emails/admin_demo_city_assignment.html) | EXCLUDED | Admin-recipient email |
| — | [mielenosoitukset_fi/templates/emails/admin_demo_city_escalation.html](../mielenosoitukset_fi/templates/emails/admin_demo_city_escalation.html) | EXCLUDED | Admin-recipient email |
| — | [mielenosoitukset_fi/templates/emails/admin_email_base.html](../mielenosoitukset_fi/templates/emails/admin_email_base.html) | EXCLUDED | Admin-recipient email |
| — | [mielenosoitukset_fi/templates/emails/admin_email_macros.html](../mielenosoitukset_fi/templates/emails/admin_email_macros.html) | EXCLUDED | Admin-recipient email |
| — | [mielenosoitukset_fi/templates/emails/admin_org_suggestion_notification.html](../mielenosoitukset_fi/templates/emails/admin_org_suggestion_notification.html) | EXCLUDED | Admin-recipient email |
| — | [mielenosoitukset_fi/templates/emails/admin_suggestion_notification.html](../mielenosoitukset_fi/templates/emails/admin_suggestion_notification.html) | EXCLUDED | Admin-recipient email |
| [ ] | [mielenosoitukset_fi/templates/emails/auth/identity_change_required.html](../mielenosoitukset_fi/templates/emails/auth/identity_change_required.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/auth/mfa_disabled.html](../mielenosoitukset_fi/templates/emails/auth/mfa_disabled.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/auth/mfa_enabled.html](../mielenosoitukset_fi/templates/emails/auth/mfa_enabled.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/auth/password_changed.html](../mielenosoitukset_fi/templates/emails/auth/password_changed.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/auth/settings_changed.html](../mielenosoitukset_fi/templates/emails/auth/settings_changed.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| — | [mielenosoitukset_fi/templates/emails/customer_support/new_ticket.html](../mielenosoitukset_fi/templates/emails/customer_support/new_ticket.html) | EXCLUDED | Admin-recipient email |
| [ ] | [mielenosoitukset_fi/templates/emails/customer_support/ticket_admin_reply.html](../mielenosoitukset_fi/templates/emails/customer_support/ticket_admin_reply.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/customer_support/ticket_auto_reply.html](../mielenosoitukset_fi/templates/emails/customer_support/ticket_auto_reply.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| — | [mielenosoitukset_fi/templates/emails/customer_support/ticket_urgent_alert.html](../mielenosoitukset_fi/templates/emails/customer_support/ticket_urgent_alert.html) | EXCLUDED | Admin-recipient email |
| [ ] | [mielenosoitukset_fi/templates/emails/demo_cancellation_link.html](../mielenosoitukset_fi/templates/emails/demo_cancellation_link.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/demo_cancelled_notification.html](../mielenosoitukset_fi/templates/emails/demo_cancelled_notification.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/demo_edit_link.html](../mielenosoitukset_fi/templates/emails/demo_edit_link.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/demo_reminder.html](../mielenosoitukset_fi/templates/emails/demo_reminder.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/demo_submitter_approved.html](../mielenosoitukset_fi/templates/emails/demo_submitter_approved.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/demo_submitter_confirmation.html](../mielenosoitukset_fi/templates/emails/demo_submitter_confirmation.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/demo_submitter_rejected.html](../mielenosoitukset_fi/templates/emails/demo_submitter_rejected.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/invite_to_organization.html](../mielenosoitukset_fi/templates/emails/invite_to_organization.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/kampanja/welcome.html](../mielenosoitukset_fi/templates/emails/kampanja/welcome.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/macros_new.html](../mielenosoitukset_fi/templates/emails/macros_new.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/new_demo_notification.html](../mielenosoitukset_fi/templates/emails/new_demo_notification.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/new_user_credentials.html](../mielenosoitukset_fi/templates/emails/new_user_credentials.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/newsletter.html](../mielenosoitukset_fi/templates/emails/newsletter.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/organization_access_notification.html](../mielenosoitukset_fi/templates/emails/organization_access_notification.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/password_reset_email.html](../mielenosoitukset_fi/templates/emails/password_reset_email.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/registration_confirmation_email.html](../mielenosoitukset_fi/templates/emails/registration_confirmation_email.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/translator_welcome.html](../mielenosoitukset_fi/templates/emails/translator_welcome.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [ ] | [mielenosoitukset_fi/templates/emails/user_update_notification.html](../mielenosoitukset_fi/templates/emails/user_update_notification.html) | EMAIL TODO | Review after UI; verify recipient, subject and plain-text source too |
| [x] | [mielenosoitukset_fi/templates/errors/400.html](../mielenosoitukset_fi/templates/errors/400.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/errors/401.html](../mielenosoitukset_fi/templates/errors/401.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/errors/403.html](../mielenosoitukset_fi/templates/errors/403.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/errors/404.html](../mielenosoitukset_fi/templates/errors/404.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/errors/410.html](../mielenosoitukset_fi/templates/errors/410.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/errors/429.html](../mielenosoitukset_fi/templates/errors/429.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/errors/500.html](../mielenosoitukset_fi/templates/errors/500.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/fundraising.html](../mielenosoitukset_fi/templates/fundraising.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/header.html](../mielenosoitukset_fi/templates/header.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/heavy.html](../mielenosoitukset_fi/templates/heavy.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/index.html](../mielenosoitukset_fi/templates/index.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/info.html](../mielenosoitukset_fi/templates/info.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/kampanja/_campaign_fallback.html](../mielenosoitukset_fi/templates/kampanja/_campaign_fallback.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/kampanja/_confirmation_expired_fallback.html](../mielenosoitukset_fi/templates/kampanja/_confirmation_expired_fallback.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/kampanja/_confirmation_invalid_fallback.html](../mielenosoitukset_fi/templates/kampanja/_confirmation_invalid_fallback.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/kampanja/_confirmation_success_fallback.html](../mielenosoitukset_fi/templates/kampanja/_confirmation_success_fallback.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/kampanja/confirm_success.html](../mielenosoitukset_fi/templates/kampanja/confirm_success.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/kampanja/index.html](../mielenosoitukset_fi/templates/kampanja/index.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/list.html](../mielenosoitukset_fi/templates/list.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/macros.html](../mielenosoitukset_fi/templates/macros.html) | REVIEWED / USAGE TODO | Text read; dormant, conditional or active usage unverified |
| [ ] | [mielenosoitukset_fi/templates/macros_new.html](../mielenosoitukset_fi/templates/macros_new.html) | EMAIL TODO | Email-only shared macro (newsletter); reviewed in email phase |
| — | [mielenosoitukset_fi/templates/manual_base.html](../mielenosoitukset_fi/templates/manual_base.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/dashboard.html](../mielenosoitukset_fi/templates/manuals/dashboard.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/demos.html](../mielenosoitukset_fi/templates/manuals/demos.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/faq.html](../mielenosoitukset_fi/templates/manuals/faq.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/index.html](../mielenosoitukset_fi/templates/manuals/index.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/organizations.html](../mielenosoitukset_fi/templates/manuals/organizations.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/recurring.html](../mielenosoitukset_fi/templates/manuals/recurring.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/security.html](../mielenosoitukset_fi/templates/manuals/security.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/stats.html](../mielenosoitukset_fi/templates/manuals/stats.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/support.html](../mielenosoitukset_fi/templates/manuals/support.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/users.html](../mielenosoitukset_fi/templates/manuals/users.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/users/about_roles.html](../mielenosoitukset_fi/templates/manuals/users/about_roles.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| — | [mielenosoitukset_fi/templates/manuals/users/add.html](../mielenosoitukset_fi/templates/manuals/users/add.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| [x] | [mielenosoitukset_fi/templates/notifications/all.html](../mielenosoitukset_fi/templates/notifications/all.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| — | [mielenosoitukset_fi/templates/oauth/mcp_consent.html](../mielenosoitukset_fi/templates/oauth/mcp_consent.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| [x] | [mielenosoitukset_fi/templates/ohjeet/index.html](../mielenosoitukset_fi/templates/ohjeet/index.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/organizations/details.html](../mielenosoitukset_fi/templates/organizations/details.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/organizations/fill_info.html](../mielenosoitukset_fi/templates/organizations/fill_info.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/paikkakunta-dropdown.html](../mielenosoitukset_fi/templates/paikkakunta-dropdown.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/preview.html](../mielenosoitukset_fi/templates/preview.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/pride-nakyvaksi/index.html](../mielenosoitukset_fi/templates/pride-nakyvaksi/index.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/privacy.html](../mielenosoitukset_fi/templates/privacy.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/siblings.html](../mielenosoitukset_fi/templates/siblings.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/status.html](../mielenosoitukset_fi/templates/status.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/submit.html](../mielenosoitukset_fi/templates/submit.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/submit_react.html](../mielenosoitukset_fi/templates/submit_react.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/suggest_change.html](../mielenosoitukset_fi/templates/suggest_change.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/tag_list.html](../mielenosoitukset_fi/templates/tag_list.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/terms.html](../mielenosoitukset_fi/templates/terms.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/today_demos.html](../mielenosoitukset_fi/templates/today_demos.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| — | [mielenosoitukset_fi/templates/toolbar.html](../mielenosoitukset_fi/templates/toolbar.html) | EXCLUDED | Admin-only UI or admin help/authorization |
| [x] | [mielenosoitukset_fi/templates/upcoming/translations.html](../mielenosoitukset_fi/templates/upcoming/translations.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/update_notice.html](../mielenosoitukset_fi/templates/update_notice.html) | REVIEWED / USAGE TODO | Text read; dormant, conditional or active usage unverified |
| [x] | [mielenosoitukset_fi/templates/users/auth/_popup_complete.html](../mielenosoitukset_fi/templates/users/auth/_popup_complete.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/forced_identity_change.html](../mielenosoitukset_fi/templates/users/auth/forced_identity_change.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/forced_pwd_reset.html](../mielenosoitukset_fi/templates/users/auth/forced_pwd_reset.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/login.html](../mielenosoitukset_fi/templates/users/auth/login.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/password_reset.html](../mielenosoitukset_fi/templates/users/auth/password_reset.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/password_reset_request.html](../mielenosoitukset_fi/templates/users/auth/password_reset_request.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/register.html](../mielenosoitukset_fi/templates/users/auth/register.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/register_next_steps.html](../mielenosoitukset_fi/templates/users/auth/register_next_steps.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/settings.html](../mielenosoitukset_fi/templates/users/auth/settings.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/token_ui.html](../mielenosoitukset_fi/templates/users/auth/token_ui.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/auth/verify_mfa.html](../mielenosoitukset_fi/templates/users/auth/verify_mfa.html) | REVIEWED / USAGE TODO | Text read; dormant, conditional or active usage unverified |
| [x] | [mielenosoitukset_fi/templates/users/logout_confirm.html](../mielenosoitukset_fi/templates/users/logout_confirm.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/profile/messages.html](../mielenosoitukset_fi/templates/users/profile/messages.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/templates/users/profile/profile copy.html](../mielenosoitukset_fi/templates/users/profile/profile%20copy.html) | REVIEWED / USAGE TODO | Text read; dormant, conditional or active usage unverified |
| [x] | [mielenosoitukset_fi/templates/users/profile/profile.html](../mielenosoitukset_fi/templates/users/profile/profile.html) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [mielenosoitukset_fi/users/templates/login.html](../mielenosoitukset_fi/users/templates/login.html) | REVIEWED / USAGE TODO | Text read; dormant, conditional or active usage unverified |
| [x] | [mielenosoitukset_fi/users/templates/register.html](../mielenosoitukset_fi/users/templates/register.html) | REVIEWED / USAGE TODO | Text read; dormant, conditional or active usage unverified |

## All React TS/TSX sources

Admin-only branches of shared public files are excluded even when the public
text is reviewed. Loaded user/API content is owned by its upstream source.

| Source review | Source | State | Coverage / next action |
| --- | --- | --- | --- |
| [x] | [frontend/src/app/ApiDocsScreen.tsx](../frontend/src/app/ApiDocsScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/App.tsx](../frontend/src/app/App.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/CalendarFallback.tsx](../frontend/src/app/CalendarFallback.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/CalendarGrid.tsx](../frontend/src/app/CalendarGrid.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/CalendarScope.tsx](../frontend/src/app/CalendarScope.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/CalendarScreen.tsx](../frontend/src/app/CalendarScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/CampaignScreen.tsx](../frontend/src/app/CampaignScreen.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/CancelLinkScreen.tsx](../frontend/src/app/CancelLinkScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/CityAdminApplyScreen.tsx](../frontend/src/app/CityAdminApplyScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/ContactScreen.tsx](../frontend/src/app/ContactScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/DeveloperScreen.tsx](../frontend/src/app/DeveloperScreen.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/Footer.tsx](../frontend/src/app/Footer.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/FundraisingReminder.tsx](../frontend/src/app/FundraisingReminder.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/FundraisingScreen.tsx](../frontend/src/app/FundraisingScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| — | [frontend/src/app/GodScreen.tsx](../frontend/src/app/GodScreen.tsx) | EXCLUDED | Admin-only UI or admin help/authorization |
| [x] | [frontend/src/app/InformationScreen.tsx](../frontend/src/app/InformationScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/ListingScreen.tsx](../frontend/src/app/ListingScreen.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/MaintenancePage.tsx](../frontend/src/app/MaintenancePage.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/OrganizationFillScreen.tsx](../frontend/src/app/OrganizationFillScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/OrganizationScreen.tsx](../frontend/src/app/OrganizationScreen.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/PrideCarrierLink.tsx](../frontend/src/app/PrideCarrierLink.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/PrideScreen.tsx](../frontend/src/app/PrideScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/PrideVolunteer.tsx](../frontend/src/app/PrideVolunteer.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/StatusScreen.tsx](../frontend/src/app/StatusScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/SubmitFallback.tsx](../frontend/src/app/SubmitFallback.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/SubmitScreen.tsx](../frontend/src/app/SubmitScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/SuggestChangeScreen.tsx](../frontend/src/app/SuggestChangeScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/TodayScreen.tsx](../frontend/src/app/TodayScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/YearCalendarScreen.tsx](../frontend/src/app/YearCalendarScreen.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/api-docs.d.ts](../frontend/src/app/api-docs.d.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/bridge.ts](../frontend/src/app/bridge.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/calendar.ts](../frontend/src/app/calendar.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/campaign-route.ts](../frontend/src/app/campaign-route.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/campaign-schedule.ts](../frontend/src/app/campaign-schedule.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/cancel-link.ts](../frontend/src/app/cancel-link.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/cities.ts](../frontend/src/app/cities.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/city-admin-route.ts](../frontend/src/app/city-admin-route.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/client.tsx](../frontend/src/app/client.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/config.ts](../frontend/src/app/config.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/contact-route.ts](../frontend/src/app/contact-route.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/detail-route.ts](../frontend/src/app/detail-route.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/detail.ts](../frontend/src/app/detail.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/developer-route.ts](../frontend/src/app/developer-route.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/discovery-meta.ts](../frontend/src/app/discovery-meta.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/fundraising-bar.ts](../frontend/src/app/fundraising-bar.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/fundraising-copy.ts](../frontend/src/app/fundraising-copy.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/fundraising-reminder.ts](../frontend/src/app/fundraising-reminder.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/fundraising.ts](../frontend/src/app/fundraising.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/header-props.ts](../frontend/src/app/header-props.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/i18n.ts](../frontend/src/app/i18n.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/information.ts](../frontend/src/app/information.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/information/AboutContent.tsx](../frontend/src/app/information/AboutContent.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/information/GuidesContent.tsx](../frontend/src/app/information/GuidesContent.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/information/PrivacyContent.tsx](../frontend/src/app/information/PrivacyContent.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/information/TermsContent.tsx](../frontend/src/app/information/TermsContent.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/information/TranslationContent.tsx](../frontend/src/app/information/TranslationContent.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/listing.ts](../frontend/src/app/listing.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/organization.ts](../frontend/src/app/organization.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/pride-volunteer.ts](../frontend/src/app/pride-volunteer.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/render.tsx](../frontend/src/app/render.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/routes.tsx](../frontend/src/app/routes.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/server-cache.ts](../frontend/src/app/server-cache.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/session-server.ts](../frontend/src/app/session-server.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/session.ts](../frontend/src/app/session.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/status.ts](../frontend/src/app/status.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/submit-copy.ts](../frontend/src/app/submit-copy.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/submit.ts](../frontend/src/app/submit.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/app/suggest-change.ts](../frontend/src/app/suggest-change.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/suggest-change/ListEditor.tsx](../frontend/src/app/suggest-change/ListEditor.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/suggest-change/MarkdownPreview.tsx](../frontend/src/app/suggest-change/MarkdownPreview.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/app/useSession.ts](../frontend/src/app/useSession.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/VolunteerForm.tsx](../frontend/src/components/VolunteerForm.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/cities/CityDirectory.tsx](../frontend/src/components/cities/CityDirectory.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/cities/useDayRollover.ts](../frontend/src/components/cities/useDayRollover.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/detail/DetailActions.tsx](../frontend/src/components/detail/DetailActions.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/detail/DetailGallery.tsx](../frontend/src/components/detail/DetailGallery.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/detail/DetailMap.tsx](../frontend/src/components/detail/DetailMap.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/detail/DetailScreen.tsx](../frontend/src/components/detail/DetailScreen.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/detail/FollowButton.tsx](../frontend/src/components/detail/FollowButton.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/detail/account.ts](../frontend/src/components/detail/account.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/detail/content.ts](../frontend/src/components/detail/content.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/detail/types.ts](../frontend/src/components/detail/types.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/detail/useDemonstration.ts](../frontend/src/components/detail/useDemonstration.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/fundraising/FundraisingBar.tsx](../frontend/src/components/fundraising/FundraisingBar.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/header/LanguageSwitcher.tsx](../frontend/src/components/header/LanguageSwitcher.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/header/NavigationLink.tsx](../frontend/src/components/header/NavigationLink.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/header/NotificationMenu.tsx](../frontend/src/components/header/NotificationMenu.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/header/SiteHeader.tsx](../frontend/src/components/header/SiteHeader.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/header/ThemeToggle.tsx](../frontend/src/components/header/ThemeToggle.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/header/UserMenu.tsx](../frontend/src/components/header/UserMenu.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/header/types.ts](../frontend/src/components/header/types.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/listings/DemonstrationCard.tsx](../frontend/src/components/listings/DemonstrationCard.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/listings/ListingTools.tsx](../frontend/src/components/listings/ListingTools.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/listings/ReactSearchFilters.tsx](../frontend/src/components/listings/ReactSearchFilters.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/listings/SearchFilters.tsx](../frontend/src/components/listings/SearchFilters.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/listings/controller.tsx](../frontend/src/components/listings/controller.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/listings/query.ts](../frontend/src/components/listings/query.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/listings/types.ts](../frontend/src/components/listings/types.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/organization/ChatPanel.tsx](../frontend/src/components/organization/ChatPanel.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/organization/OrganizationChat.tsx](../frontend/src/components/organization/OrganizationChat.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/organization/copy.ts](../frontend/src/components/organization/copy.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/organization/types.ts](../frontend/src/components/organization/types.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/pride/PrideMap.tsx](../frontend/src/components/pride/PrideMap.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/submit/CitySelect.tsx](../frontend/src/components/submit/CitySelect.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/submit/DateField.tsx](../frontend/src/components/submit/DateField.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/submit/DescriptionEditor.tsx](../frontend/src/components/submit/DescriptionEditor.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/submit/OrganizerList.tsx](../frontend/src/components/submit/OrganizerList.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/components/submit/SubmitFlow.tsx](../frontend/src/components/submit/SubmitFlow.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/submit/draft.ts](../frontend/src/components/submit/draft.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/components/submit/types.ts](../frontend/src/components/submit/types.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/data/campaign.ts](../frontend/src/data/campaign.ts) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/entries/campaign.tsx](../frontend/src/entries/campaign.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/confirmation.tsx](../frontend/src/entries/confirmation.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/detail.tsx](../frontend/src/entries/detail.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/header.tsx](../frontend/src/entries/header.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/home.tsx](../frontend/src/entries/home.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/listing.tsx](../frontend/src/entries/listing.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/pride.tsx](../frontend/src/entries/pride.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/submit-react.tsx](../frontend/src/entries/submit-react.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/submit.tsx](../frontend/src/entries/submit.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/entries/volunteer.tsx](../frontend/src/entries/volunteer.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/lib/event-image.ts](../frontend/src/lib/event-image.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/lib/mount-island.tsx](../frontend/src/lib/mount-island.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/lib/track-demo-view.ts](../frontend/src/lib/track-demo-view.ts) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/pages/CampaignPage.tsx](../frontend/src/pages/CampaignPage.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/pages/CitiesPage.tsx](../frontend/src/pages/CitiesPage.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/pages/ConfirmationPage.tsx](../frontend/src/pages/ConfirmationPage.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/pages/DemonstrationDetailPage.tsx](../frontend/src/pages/DemonstrationDetailPage.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |
| [x] | [frontend/src/pages/DemonstrationListingPage.tsx](../frontend/src/pages/DemonstrationListingPage.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/pages/HomePage.tsx](../frontend/src/pages/HomePage.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/pages/OrganizationPage.tsx](../frontend/src/pages/OrganizationPage.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/pages/PublicListingPage.tsx](../frontend/src/pages/PublicListingPage.tsx) | NO COPY | Inspected: copy supplied by catalog/props, identifiers only, or no prose |
| [x] | [frontend/src/pages/SubmitPage.tsx](../frontend/src/pages/SubmitPage.tsx) | REVIEWED | Source text reviewed; apply/runtime status is separate |

## Other text sources and context TODOs

These are deliberately not marked as a full pass merely because some messages
were inspected. Audit the consumer before treating a backend response as UI.

| Source / context | State | Next action |
| --- | --- | --- |
| [utils/react_detail.py](../mielenosoitukset_fi/utils/react_detail.py), `detail_messages()` | REVIEWED | Keep TypeScript catalog parity; validate 0/1/many participant labels. |
| [basic_routes.py](../mielenosoitukset_fi/basic_routes.py) | PARTIAL | Selected displayed messages reviewed/fixed; enumerate remaining public flash/API messages and generated page props. Exclude admin branches. |
| [users/BPs/auth.py](../mielenosoitukset_fi/users/BPs/auth.py), profile/chat handlers | PARTIAL | Displayed API-access/MFA messages traced; audit other actually displayed feedback, not hidden protocol errors. |
| [go-api/fundraising_reminder.go](../go-api/fundraising_reminder.go), submission/banner/city-application handlers, developer_write.go | PARTIAL | Selected Finnish feedback reviewed; enumerate all regular-user consumers/states and check English error fallbacks. |
| [utils/notifications.py](../mielenosoitukset_fi/utils/notifications.py), [notifications_bp.py](../mielenosoitukset_fi/notifications_bp.py) | REVIEWED (regular-user branches) | Serializer and list labels read; user-generated legacy messages are separate. |
| Legacy JS: webauthn.js, user-cropper.js, user-pagination.js | REVIEWED / RUNTIME TODO | Owned copy checked; browser and platform-generated errors need runtime context. |
| Legacy JS: date.js, ck.js, ckeditor-init.js, toaster.js, modal.js, submit-draft.js and other non-admin root static/js files | PARTIAL | Complete source/consumer review. Confirm short month labels such as “Hele” in an actual exposed picker before claiming a live defect. |
| [frontend/server.mjs](../frontend/server.mjs) | REVIEWED (fallback copy) | Finnish unavailable heading read; no wording finding. |
| [fundraising.json](../mielenosoitukset_fi/utils/data/fundraising.json) | REVIEWED (bundled display fields) | Do not change official collection facts as proofreading. Production configuration remains unchecked. |
| [city_catalog.json](../go-api/city_catalog.json) | UI TODO | Validate inflected city names and interpolated contexts separately; TS loader inspection does not audit the data. |
| [docs/api.md](api.md) and OpenAPI descriptions | UI TODO | Read rendered API documentation, including technical terms and examples; not covered by ApiDocsScreen shell review. |
| Flatpickr, Quill, Leaflet and browser-provided strings | RUNTIME TODO | Check exposed widget labels in Finnish; distinguish vendor defaults from owned catalog strings. |
| User/DB content, configured texts and names | OUTSIDE STATIC PASS | Do not rewrite users’ event titles, descriptions, profiles or messages as site copy. |
| Email subjects, queue/job-generated body text and recipient ownership | EMAIL TODO | Trace EmailSender, relevant user email call sites and shared macros after UI completion; never send real mail. |

- [ ] R32: optional city-selector group label rewrite is deferred. Original wording is retained because page screenshots cannot capture the native popup. Obtain suitable native-window evidence before changing it.

## Closing a row

Record reviewer/model, revision, exact scope and linked findings. After applying
text changes, verify placeholders, punctuation across inline links, 0/1/many
counts, empty/error/loading/modal states and existing localization fallback.
Record relevant technical checks and independent visual acceptance separately.
A subsequent text change reopens the affected runtime/capture check.
