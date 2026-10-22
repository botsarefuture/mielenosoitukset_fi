# Individual test review inventory

Baseline: `main` at `52a971e1e11c6560e1eb45393c2ef812bbadd693`, 2026-10-12.

Branch `codex/deploy-dependency-receipt` on #951 at505b5eaa, including main `a5f256b7` (#942/#946 merged), 2026-10-22: 166 Python test files; 1,213 definitions; 308 assessed definitions. All merged reviews and three #951/eight #952 definitions are retained. These are branch-tree counts, not completed review or release acceptance for the pending dependency work. Older per-branch/run counts below are historical evidence only.

For each checked definition, add its review record under the file heading (requirement, setup/mocks, assertions, variants, reliability, disposition, revision/run/PR evidence). Parameter groups must account for every collected case. Refresh additions/removals at milestones. Include shared fixtures/configuration and standalone test scripts in the supporting audit.

Use the roadmap's P0–P3 policy and status vocabulary. Initial review status for every entry is Backlog; assign an owner and justified priority when triaging it. A discovered security/core-workflow defect can escalate immediately, regardless of its review batch.

## tests/test_deploy_dependencies.py

Supporting fixture `deployment`: real isolated Git repository with serving-baseline and already-advanced target commits, real build-marker/receipt files. Installed package metadata and venv classification are simulated explicitly; no service, production interpreter, network or package mutation is implied.

- [x] `test_readonly_legacy_adopts_verified_delta_without_downgrading_drift`

OPS-04c/P1/#952 · 2026-10-22 · Codex. Actual Git lookup and0600 receipt I/O, fake metadata for newer unchanged Flask and already-correct certifi. Installer is a failing sentinel. Verifies exact manifest/managed-pin distinction, diagnostic drift, idempotent recheck and rejection when certifi regresses despite matching receipt. Keep; not approval of legacy drift or live deployment proof.

- [x] `test_failed_same_checkout_retry_requires_install_until_success`

OPS-04c/P1/#952. Actual target checkout already advanced, fake owned-venv install fails once then updates simulated metadata. No receipt after failure; same target retries all required initial pins, acknowledges only success, then skips package writes. Keep; actual pip/venv mutation is simulated and companion command test covers sequencing.

- [x] `test_failed_delta_keeps_previous_receipt_until_same_sha_retry_succeeds`

OPS-04c/P1/#952. Existing acknowledgement, next manifest delta, one injected installer failure. Asserts byte-preserved previous receipt, exact repeated changed-pin request, then accumulated managed-pin acknowledgement. Keep; complements missing-receipt retry and distinguishes checkout state from installation success. No actual subprocess failure or power-loss durability claim.

- [x] `test_dependency_gate_fails_closed`

OPS-04c/P1/#952. Seven cases: system mutation refusal, missing serving baseline, runtime mismatch, truncated JSON, unsupported manifest, successful-but-ineffective installer, and atomic replace failure. Actual Git/receipt I/O plus targeted metadata/installer/replace doubles. Asserts prior receipt unchanged/absent, no unauthorized package-write call and temporary-file cleanup. Keep; not exhaustive filesystem fault, permissions/ownership or concurrency acceptance.

- [x] `test_production_manifest_requires_unambiguous_exact_pins`

OPS-04c/P1/#952. Five pure-parser cases reject empty, range, canonical duplicate, wildcard and direct URL syntax. Keep as explicit manifest contract; this is deliberately not a general PEP508 parser or dependency resolver.

- [x] `test_production_dependency_gate_precedes_index_reload_and_health`

OPS-04c/P1/#952. Actual script source contract asserts removal of checkout-diff skip, helper before index/reload and consistent interpreter for helper/index/health. Keep as cheap ordering ratchet; no executed systemd, shell control-flow or successful worker-reload claim.

- [x] `test_repository_requirements_follow_deployment_pin_contract`

OPS-04c/P1/#952. Parses the actual checked-in runtime requirements rather than a synthetic fixture, requiring the core Flask/certifi entries to survive normalization. Keep to catch unsupported syntax before deploy. Independent manual parse of exact serving baselinea5f256b7 confirmed all26 baseline pins supported; target has27. No claim that arbitrary historical manifests or general pip syntax are supported.

- [x] `test_owned_install_bootstraps_then_installs_and_checks_without_system_bypass`

OPS-04c/P1/#952. Three command-recorder cases cover success and failures at bootstrap/install. Exact argv/check=True and ordered-prefix assertions ensure failure halts subsequent work, hash-bootstrap precedes index install and no automatic system-bypass flag is used. Keep; subprocess execution is mocked, not network/TLS/pip-check acceptance. Actual bootstrap subprocess/hash-wheel contract remains separately assessed.

## tests/test_python_trust_bootstrap.py

- [x] `test_installed_certifi_distrusts_compromised_emsign_root`

P1 trust-store advisory · Codex · 2026-10-22. Real installed certifi bundle is parsed by OpenSSL through the stdlib SSL context; nonempty trusted roots must exclude the exact SHA256 of the affected emSign ECC G3 root. Fingerprint independently extracted from the backed-up production pre-update certifi2026.2.25 bundle; old live bundle had the root, updated bundle does not. No network/mocks or version-only success assertion. Keep as a concrete trust-store regression; does not prove adversarial TLS handshakes, intermediate/cross-sign revocation or arbitrary client CA overrides.

- [x] `test_bootstrap_uses_hashed_wheel_and_propagates_failure`

P1 trust-store advisory · Codex · 2026-10-22. Two subprocess cases execute the actual Bash bootstrap with a fake interpreter whose path contains spaces. Exact argv proves the upstream wheel/version/SHA256, no-cache upgrade and preserved argument boundaries; exit17 proves installation failure is propagated. No network or pip mock internals; does not establish the remote wheel's authenticity or exercise pip's hash verifier. Separate actual local installation succeeded at pip26.2.2/certifi2026.10.19. Keep as an offline command contract, not TLS-chain or production remediation proof.

- [x] `test_dependency_entrypoints_bootstrap_before_index_install`

P1 trust-store advisory · Codex · 2026-10-22. Parses actual CI YAML and reads Docker/requirements sources. Checks bootstrap ordering before index installs, Docker copy/dependency chaining/OS CA package and exact certifi pin. No Docker, SSH, apt or live workflow execution; source-string assertions are deliberately a small ratchet, not integration evidence. Keep; pair with runtime version checks and real image rebuild/deployment acceptance.

## tests/test_profile_image_fallback.py

- [x] `test_profile_image_failure_uses_fallback_once`

DATA-05 · P1 · #581 · Codex · 2026-10-19. One definition /two browser cases. Actual public profile GET renders the main avatar and both follower-list macro instances from real seeded Mongo data. Chromium executes those handlers; controlled HTTP404 image responses exercise original failure, with successful or failed fallback. Assertions cover all three images, handler removal, completed fallback and decoded success/failure, and bounded source/fallback requests (coalescing permitted). Both cases failed before the fix; all9 combined fallback/profile-editor cases pass afterward. Local five-file review completed with one Major test-fixture finding: scrolling a closed-modal avatar may fail when modal CSS loads. Removed scrolling and use eager loading independently of visibility. App template/DOM/handlers are real, external image delivery is simulated; no production Cloudflare, network recovery/backoff, visual design or general image-surface acceptance claim. Keep; targets the current confirmed loop without retry-framework expansion.

## tests/test_ci_runtime_contract.py

- [x] `test_mongo_compatible_runner_keeps_database_and_required_suite`

OPS-04b / QA-05 · P1 · Codex · 2026-10-22. The real YAML job remains python-tests on explicit Ubuntu 22, MongoDB 8 and Python 3.12; static assertions retain all four services, Chromium, unconditional pytest and failing health/test gates. No fixtures or mocked responses. One focused case, YAML/every Bash-step syntax and diff checks pass. Six-file local review completed with zero findings (later prose formatting/evidence excluded). This cannot prove hosted kernel/service availability or successful integration tests; real CI is required. Keep as a narrow migration guard; update it only with documented compatible-runner evidence before 2027-04-17, not to erase a failed suite. No test definitions removed/skipped and no production DB/OS changes.

## Supporting audit — tests/conftest.py

These two functions are `@pytest.fixture` definitions despite their names. They require supporting review and are excluded from the 997-test total.

- [ ] `test_settings`
- [ ] `test_config_path`

## mielenosoitukset_fi/scripts/test_repeat_v2.py

Standalone unittest script; these methods are included in the test total even if the configured pytest discovery does not collect this path. Review its imports, invocation and scheduling assumptions alongside the individual records below. Source inspection shows missing `timedelta`/`relativedelta` imports and a `scripts.repeat_v2` import whose resolution needs verification; no execution or completed review is claimed here.

- [ ] `TestCalculateNextDates::test_daily_frequency`
- [ ] `TestCalculateNextDates::test_weekly_frequency`
- [ ] `TestCalculateNextDates::test_monthly_frequency`
- [ ] `TestCalculateNextDates::test_yearly_frequency`
- [ ] `TestCalculateNextDates::test_custom_interval`

Individual review records (all Backlog; owner unassigned):

| Definition | Requirement to verify | Setup / assertions to review | Variants / reliability gaps | Disposition and validation evidence |
|---|---|---|---|---|
| `test_daily_frequency` | Daily schedule dates and inclusive start. | Fixed start/schedule; asserts count 365 and first two dates. | Establish horizon policy, end boundary and date arithmetic imports. | Pending; not run. Record reviewer, revision, node/invocation and any fix PR. |
| `test_weekly_frequency` | Weekly schedule dates and inclusive start. | Fixed start/schedule; asserts count 53 and one-week spacing. | Establish horizon policy, year boundary and date arithmetic imports. | Pending; not run. Record reviewer, revision, node/invocation and any fix PR. |
| `test_monthly_frequency` | Monthly recurrence dates. | Fixed January start; asserts count 12 and next month. | Verify month-end/leap-year policy and missing date arithmetic import. | Pending; not run. Record reviewer, revision, node/invocation and any fix PR. |
| `test_yearly_frequency` | Yearly recurrence dates. | Fixed start; asserts count two and next year. | Verify inclusive end/horizon policy and leap-day behavior. | Pending; not run. Record reviewer, revision, node/invocation and any fix PR. |
| `test_custom_interval` | Two-day interval recurrence. | Fixed start/schedule; asserts count 183 and first increment. | Verify interval validation, horizon boundary and date arithmetic imports. | Pending; not run. Record reviewer, revision, node/invocation and any fix PR. |

## tests/test_account_access.py

- [x] `test_password_and_mfa_login_reject_disabled_account`
- [x] `test_existing_session_loses_access_after_account_disabled`
- [x] `test_legacy_account_without_active_field_remains_enabled`

SEC-02 / QA-01 review, 2026-10-12, Codex, P1. Real Flask clients and disposable MongoDB; real password hashing/TOTP, no mocked authorization. External mail/network side effects use the existing fixture isolation. Evidence: focused suite on this branch and final PR commit/run record.

| Definition | Requirement / assertions | Variants, reliability and limitations | Disposition |
|---|---|---|---|
| `test_password_and_mfa_login_reject_disabled_account` | Correct first/second factors cannot establish session for disabled user; preflight returns invalid. | Four status × MFA combinations; real DB update, exact redirect and absent user ID. TOTP time is real; no expiry boundary claim. | Keep. |
| `test_existing_session_loses_access_after_account_disabled` | Protected access succeeds before status update and fails afterward. | Inactive and banned independently; same client retains existing cookie; verifies loader enforcement, not permanent revocation after future reactivation or WebSocket events. | Keep. |
| `test_legacy_account_without_active_field_remains_enabled` | Missing legacy active flag defaults enabled. | Real model and successful password session; ensures no forced migration requirement. | Keep. |

## tests/test_admin_account_status.py

- [x] `test_compiled_account_status_copy_is_present_and_translated`
- [x] `test_account_status_confirmation_and_success_follow_session_locale`

I18N-01 / QA-04 follow-up, P1, reviewed 2026-10-15 by Codex. These two definitions cover nine cases and reproduced seven failures before the runtime catalogs were repaired (FI fallback masked two rendered cases). All 31 focused account-status cases pass after repair. Existing context-specific status-label coverage alone did not protect the uncontextualized confirmation copy.

| Definition | Requirement / assertions | Setup, reliability and limits | Disposition |
|---|---|---|---|
| `test_compiled_account_status_copy_is_present_and_translated` | All eight confirmation/action/help/success messages exist in the shipped MO and equal explicit FI/EN/SV expectations, not just PO source or fallback. | Direct GNUTranslations of tracked runtime artifacts, three locales; no translation mock. Does not prove all catalog strings are translated. | Keep; fails against pre-fix artifacts, including FI. |
| `test_account_status_confirmation_and_success_follow_session_locale` | Real GET renders heading/breadcrumb/action/explanation in the selected language without Finnish fallback; protected POST changes actual state and flashes localized success. | Authenticated admin with real disposable Mongo state and signed form proof, three locales × activate/disable. No permission/translation mocks or time sleeps. No visual/layout or deployment claim. | Keep; four EN/SV variants failed before repair, while FI rendering alone hid missing compiled keys. |

- [x] `test_same_status_token_has_one_winner_under_concurrent_submit`
- [x] `test_status_action_visibility_uses_shared_hierarchy`

Approved review follow-up, 2026-10-13: the synchronized race uses two independent clients with the same cookie/proof and a barrier immediately before the real conditional Mongo update, after both requests have read their snapshots. Exactly one 302, one 409, one persisted version increment and one action audit must result. The collection method wrapper adds synchronization only; it does not mock the write outcome. The visibility test covers lower/self/peer/higher targets, exact template link presence/absence and a membership-only permission denied by the shared predicate. No sleeps or production requests. Both definitions are retained; sequential disable/enable/replay coverage is not replaced. Final combined run and revision are recorded in the integration PR.
Review follow-up, 2026-10-13: real Flask/MongoDB confirmation tests prove independent target tabs survive each other's consumption, the eight-nonce bound rejects evicted forms, and a supported superuser can list/change ordinary accounts. Runtime GNUTranslations tests prove FI/EN/SV account-status contexts do not replace uncontextualized case labels. Focused result: 17 parameterized cases passed; no claim of a full-suite or production run.

- [x] `test_independent_confirmation_tabs_keep_their_nonces`
- [x] `test_confirmation_nonce_collection_is_bounded`
- [x] `test_superuser_can_list_and_change_ordinary_account_status`
- [x] `test_compiled_status_labels_have_distinct_gettext_context`

- [x] `test_admin_can_disable_and_reenable_with_audited_confirmation`
- [x] `test_admin_cannot_change_self_or_peer_or_higher_status`
- [x] `test_viewer_without_edit_permission_cannot_change_status`
- [x] `test_status_confirmation_rejects_missing_tampered_or_wrong_target_proof`
- [x] `test_saved_status_form_cannot_replay_after_disable_enable_cycle`
- [x] `test_user_list_and_editor_show_account_status`
- [x] `test_status_confirmation_expires`
- [x] `test_confirmation_is_bound_to_the_authenticated_actor`
- [x] `test_confirmation_layout_and_keyboard_actions_in_both_themes`

The original nine definitions are supplemented by six reviewed follow-up definitions. Parameter expansion is reported separately from definition counts.

SEC-02 / QA-01 review, 2026-10-12, Codex, P1; real Flask sessions, signed forms and MongoDB. No mocked permission or write path. The shared seeded identities are isolated by the test fixtures. The expiry case uses a dedicated old-timestamp signer solely for its confirmation token; the session signer and application clock remain unchanged.

| Definition | Requirement / assertion | Cases, reliability and limits | Disposition |
|---|---|---|---|
| `test_admin_can_disable_and_reenable_with_audited_confirmation` | DB state changes, activation removes ban, audit records state and excludes proof. | Actual signed confirmation and audit writes; email notification not part of this action. | Keep. |
| `test_admin_cannot_change_self_or_peer_or_higher_status` | GET and POST denied for unauthorized hierarchy. | Self, equal-level and higher-level parameter cases; preserves existing hierarchy policy. | Keep. |
| `test_viewer_without_edit_permission_cannot_change_status` | A scoped admin lacking EDIT_USER cannot read confirmation or mutate. | Explicit lower-privilege fixture, exact 403; broader scope semantics remain SEC-03. | Keep. |
| `test_status_confirmation_rejects_missing_tampered_or_wrong_target_proof` | Missing/modified proof or different target rejected. | Real signer; no cryptographic stub. | Keep. |
| `test_saved_status_form_cannot_replay_after_disable_enable_cycle` | Original cookie/proof rejected despite matching active state later. | Real saved cookie, two accepted actions, exact conflict response verifies versioning. | Keep. |
| `test_user_list_and_editor_show_account_status` | List and editor expose disabled state and status heading. | Actual rendered routes; semantic text checks, not pixel/theme validation. | Keep. |
| `test_status_confirmation_expires` | Expired signed proof rejected. | Controlled signer timestamp; no sleep or altered application clock. | Keep. |
| `test_confirmation_is_bound_to_the_authenticated_actor` | Another privileged actor cannot use leaked proof, even with copied nonce. | Distinct allowed admin, exact 400 and unchanged target state. | Keep. |
| `test_confirmation_layout_and_keyboard_actions_in_both_themes` | Hero/action visible, no horizontal body overflow, keyboard reaches submit from cancel. | Real authenticated route at 390/1440px in light/dark with local resources; verifies geometry/focus, not a full contrast or pixel-quality audit. | Keep. |

Evidence: 37 focused admin-status/user/fresh-deletion backend cases passed, followed by the focused Chromium layout/keyboard case across both widths/themes. Final commit is recorded in the delivery PR. New template uses the existing hero, form-section, buttons and sticky actions; broader contrast/visual acceptance remains QA-04.

## tests/test_admin_audit_indexes.py

- [x] `test_audit_collections_index_the_deterministic_pagination_order`

USER-01 / QA-02 review, 2026-10-18, Codex, P2: real disposable MongoDB index metadata proves both audit stores retain timestamp/_id order and admin logs additionally support entity_type/entity_id/timestamp/_id history queries. No mocked create_index; this does not establish production index creation, explain plans or large-dataset latency. Keep; focused run passes.

## tests/test_admin_case_bp.py

- [x] `test_accept_demo_closes_linked_support_case`
- [x] `test_case_pages_render_clean_support_case_views`
- [x] `test_approve_demo_token_closes_linked_support_case`
- [x] `test_reject_demo_token_closes_linked_support_case`
- [x] `test_deescalate_writes_case_history`
- [x] `test_auto_close_cases_respects_approved_field`

SEC-03 / QA-01 review, 2026-10-12, Codex, P1. Disposable MongoDB, seeded real demo/case/token registry, actual routes; external mail delivery isolated by existing fixtures. Final delivery PR records revision/run evidence. These cases do not prove approval retry idempotency or the whole token lifecycle.

| Definition | Requirement / assertions | Cases, reliability and limits | Disposition |
|---|---|---|---|
| `test_accept_demo_closes_linked_support_case` | Legacy approval closes linked case with canonical reason/action log. | Real admin POST and stored state; notification multiplicity not asserted. | Keep; broader idempotency remains SEC-04. |
| `test_case_pages_render_clean_support_case_views` | Global list/detail render expected sections/demo. | Actual routes and content; no pixel/focus proof. | Keep; scoped read denial added separately. |
| `test_approve_demo_token_closes_linked_support_case` | Registered approval token drives case closure/history. | Real token/registry and redirect; no replay or expiry variant here. | Keep. |
| `test_reject_demo_token_closes_linked_support_case` | Registered rejection token drives rejected closure/history. | Symmetric case state assertions; sibling-token policy not covered. | Keep. |
| `test_deescalate_writes_case_history` | Escalation cleared and canonical history field used. | Actual JSON route and DB state; scope denial covered below. | Keep. |
| `test_auto_close_cases_respects_approved_field` | Background resolver recognizes approved flag and closes once. | Direct real DB job; test assumes isolated seeded cases for exact closed count. | Keep; read-only UI side effect tested below. |

## tests/test_admin_case_component_contract.py

- [ ] `test_case_cards_use_shared_copy_and_title_wrappers`

## tests/test_admin_demo_merge_editor.py

- [ ] `test_global_admin_merge_editor_uses_shared_form_contract`
- [ ] `test_restricted_admin_cannot_open_merge_editor`
- [ ] `test_merge_editor_has_no_legacy_page_specific_ui_layer`

## tests/test_admin_demo_views.py

- [ ] `test_create_demo_hides_edit_only_controls`
- [ ] `test_edit_demo_shows_edit_only_controls`
- [ ] `test_demo_dashboard_has_scoped_preview_and_edit_link_quick_actions`
- [ ] `test_demo_suggestions_use_shared_collection_and_review_contract`
- [ ] `test_demo_suggestions_status_filter_counts_and_page_size_are_preserved`
- [ ] `test_demo_edit_history_uses_stable_server_pagination`
- [ ] `test_demo_diff_escapes_stored_content_and_uses_shared_workflow`
- [ ] `test_editor_without_accept_permission_cannot_forge_demo_approval`
- [ ] `test_submission_errors_require_view_logs_permission`
- [ ] `test_view_logs_permission_is_assignable`
- [ ] `test_submission_errors_use_stable_server_pagination_and_preserve_filters`
- [ ] `test_demo_audit_views_use_stable_server_pagination`
- [ ] `test_demo_dashboard_filters_year_text_and_missing_tag`
- [ ] `test_demo_dashboard_filters_by_required_tag`
- [ ] `test_edit_demo_prefills_translation_fields`
- [ ] `test_demo_dashboard_renders_numbered_pagination`
- [ ] `test_create_demo_persists_translation_payload`
- [ ] `test_create_demo_persists_normalized_slug_and_all_image_assets`
- [ ] `test_create_demo_rejects_a_duplicate_normalized_slug`

## tests/test_admin_developer_collections.py

- [ ] `test_developer_requests_use_stable_server_pagination`
- [ ] `test_developer_request_kind_and_status_filters_are_server_rendered`
- [ ] `test_user_apps_use_stable_server_pagination`
- [ ] `test_developer_templates_use_shared_collection_contract`

## tests/test_admin_flash_i18n_contract.py

- [ ] `test_admin_flash_messages_do_not_mix_known_english_source_copy`
- [ ] `test_babel_extracts_flash_message_first_arguments`
- [ ] `test_admin_flash_messages_do_not_use_unextractable_f_strings`
- [ ] `test_repository_extraction_command_includes_flash_messages`

## tests/test_admin_governance.py

- [ ] `test_governance_dashboard_collects_admin_tools`
- [ ] `test_board_clearance_is_persisted_and_audited`
- [ ] `test_legacy_board_pages_redirect_to_governance`
- [ ] `test_city_management_explains_unsaved_and_risky_changes`
- [ ] `test_admin_management_views_share_workspace_design`
- [ ] `test_clearance_collection_paginates_filtered_users`
- [ ] `test_governance_audit_collection_paginates_with_stable_tie_breaker`
- [ ] `test_governance_migration_preserves_existing_city_managers`
- [ ] `test_global_admin_promotion_requires_persistent_clearance`
- [ ] `test_city_permission_is_independent_from_user_editing`
- [ ] `test_clearance_change_rejects_missing_csrf_token`

## tests/test_admin_logs.py

- [ ] `test_admin_logs_page_is_a_linked_finnish_log_center`
- [ ] `test_admin_logs_api_supports_search_and_event_categories`
- [ ] `test_admin_logs_page_paginates_server_rendered_rows_deterministically`
- [ ] `test_admin_logs_page_escapes_server_rendered_audit_content`
- [ ] `test_admin_log_payload_redacts_credentials_for_display`

## tests/test_admin_magic_tokens.py

- [ ] `test_magic_token_collection_uses_stable_server_pagination`
- [ ] `test_magic_token_filters_preserve_truthful_counts_and_page_size`
- [ ] `test_magic_token_revocation_and_global_admin_boundary`
- [ ] `test_magic_token_template_uses_shared_collection_and_modal_contracts`

## tests/test_admin_mcp.py

- [ ] `test_admin_mcp_requires_bearer_token`
- [ ] `test_admin_mcp_lists_tools`
- [ ] `test_admin_mcp_oauth_metadata_advertises_registration_and_pkce`
- [ ] `test_admin_mcp_dynamic_client_registration_and_oauth_code_flow`
- [ ] `test_admin_mcp_accepts_oauth_bearer_tokens`
- [ ] `test_admin_mcp_accepts_existing_api_tokens`
- [ ] `test_admin_mcp_rejects_ordinary_api_token`
- [ ] `test_admin_mcp_can_search_demos`
- [ ] `test_admin_mcp_can_add_case_note`
- [ ] `test_admin_mcp_can_update_organization`
- [ ] `test_admin_mcp_can_create_demo`

## tests/test_admin_media_retirement.py

- [ ] `test_retired_media_workspace_has_no_routes_or_endpoints`

## tests/test_admin_organizer_editor.py

- [ ] `test_organization_admin_only_sees_and_links_permitted_organizations`
- [ ] `test_create_demo_accepts_linked_and_freeform_organizers_with_sparse_indexes`
- [ ] `test_city_admin_can_add_freeform_but_cannot_forge_organization_link`
- [ ] `test_edit_demo_preserves_organizer_metadata_and_updates_freeform_fields`
- [ ] `test_duplicate_organizers_are_rejected_server_side`
- [ ] `test_incomplete_freeform_organizer_rows_are_rejected`
- [ ] `test_completely_unused_organizer_row_is_ignored`

## tests/test_admin_pagination.py

- [ ] `test_parse_admin_pagination_normalizes_invalid_values`
- [ ] `test_build_admin_pagination_clamps_page_and_preserves_query_state`
- [ ] `test_build_admin_pagination_exposes_an_empty_first_page`

## tests/test_admin_recu_demo.py

- [ ] `test_recurring_runner_normalizes_frozen_child_ids`
- [ ] `test_recurring_child_slug_gets_stable_series_suffix_on_collision`
- [ ] `test_recurring_demo_from_dict_accepts_city_key`
- [ ] `test_admin_can_create_recurring_demo_with_create_form_fields`
- [ ] `test_admin_can_create_recurring_demo_with_sparse_organizer_indexes`
- [ ] `test_editor_without_accept_permission_cannot_change_recurring_approval`
- [ ] `test_admin_can_bulk_update_selected_recurring_children`
- [ ] `test_admin_can_bulk_cancel_selected_recurring_children`
- [ ] `test_admin_recurring_break_date_cancels_existing_child`
- [ ] `test_recurring_runner_skips_break_dates_and_cancels_existing_children`
- [ ] `test_background_job_repeat_main_creates_child_demos_without_stdin`
- [ ] `test_recurring_demo_no_change_save_preserves_schedule_and_nullable_values`
- [ ] `test_admin_can_create_recurring_demo_with_translations`
- [ ] `test_admin_can_create_recurring_demo_with_slug_and_all_image_assets`
- [ ] `test_recurring_demo_cover_upload_overrides_the_url`

## tests/test_admin_recu_demo_bp.py

- [ ] `test_recurring_control_paginates_with_stable_server_side_order`
- [ ] `test_recurring_control_filters_before_counting_and_pagination`
- [ ] `test_recurring_control_counts_and_lists_only_city_scoped_rows`
- [ ] `test_recu_demo_delete_accepts_json_confirmation_contract`
- [ ] `test_recu_demo_delete_rejects_unconfirmed_json`
- [ ] `test_recurring_control_excludes_unrenderable_records_from_counts`

## tests/test_admin_recu_demo_views.py

- [ ] `test_create_recu_demo_uses_shared_admin_form`
- [ ] `test_edit_recu_demo_renders_shared_admin_form_with_org_selector`
- [ ] `test_recurring_form_exposes_live_date_preview`
- [ ] `test_recurring_date_preview_uses_schedule_and_excludes_breaks`
- [ ] `test_recurring_date_preview_scans_past_long_consecutive_break`
- [ ] `test_recurring_date_preview_rejects_incomplete_monthly_schedule`
- [ ] `test_edit_recu_demo_prefills_translation_fields`
- [ ] `test_recu_demo_dashboard_lists_demos_with_migrated_city_key`
- [ ] `test_recu_demo_dashboard_renders_server_side_pagination`
- [ ] `test_recu_demo_dashboard_filters_approval_state`

## tests/test_admin_recu_organizer_editor.py

- [ ] `test_organization_admin_only_sees_and_links_permitted_recurring_organizations`
- [ ] `test_recurring_edit_preserves_organizer_metadata_without_mutating_children`

## tests/test_admin_review_followup_contract.py

- [ ] `test_warning_foregrounds_meet_normal_text_contrast_in_both_themes`
- [ ] `test_demo_review_regressions_keep_shared_interaction_contracts`

## tests/test_admin_scope_context.py

- [ ] `test_admin_actor_context_distinguishes_global_city_and_translator_roles`
- [ ] `test_admin_role_with_limited_permissions_is_not_classified_as_global`
- [ ] `test_admin_actor_context_distinguishes_organization_and_restricted_roles`
- [ ] `test_admin_shell_does_not_claim_every_actor_is_a_superuser`
- [ ] `test_public_pages_do_not_evaluate_admin_scope_context`
- [ ] `test_public_context_processor_returns_no_admin_scope_context`
- [ ] `test_admin_shell_renders_the_authenticated_scope`

## tests/test_admin_stats_collection.py

- [ ] `test_overall_24h_initial_render_matches_helsinki_api`
- [ ] `test_stats_collection_uses_deterministic_server_pagination`
- [ ] `test_scoped_analytics_viewer_only_sees_allowed_demo_counts`
- [ ] `test_demo_analytics_detail_requires_scoped_permission`

## tests/test_admin_ui_contract.py

- [ ] `test_full_admin_templates_use_the_admin_shell`
- [ ] `test_admin_inline_style_debt_cannot_grow_without_review`
- [ ] `test_admin_shell_uses_shared_css_without_inline_style_debt`
- [ ] `test_demo_organizer_editor_uses_shared_accessible_contract`
- [ ] `test_active_legacy_demo_workflows_use_shared_admin_contracts`
- [ ] `test_admin_theme_is_applied_before_styles_and_controls_color_scheme`
- [ ] `test_root_admin_dashboard_uses_shared_components_and_safe_feed_rendering`
- [ ] `test_legacy_dialog_does_not_override_bootstrap_modal`
- [ ] `test_admin_design_standard_is_documented`
- [ ] `test_admin_page_heroes_keep_copy_in_one_content_group`
- [ ] `test_admin_hero_variants_are_limited_to_the_shared_stacked_contract`
- [ ] `test_legacy_admin_hero_selectors_and_action_aliases_are_absent`
- [ ] `test_admin_hero_foreground_and_data_view_surfaces_are_shared`
- [ ] `test_user_role_forms_use_shared_admin_contract`
- [ ] `test_demo_collection_uses_server_side_filter_and_pagination_contract`
- [ ] `test_secondary_editors_use_shared_form_primitives`
- [ ] `test_submitter_modal_keeps_stable_dom_across_reopens`
- [ ] `test_organization_workflows_use_shared_admin_components`
- [ ] `test_organization_collection_uses_shared_data_view_contract`
- [ ] `test_organization_detail_uses_shared_components_and_scoped_controls`
- [ ] `test_organization_pages_use_canonical_hero_macro_and_navigation`
- [ ] `test_city_admin_operational_pages_use_canonical_hero_macro`
- [ ] `test_access_management_pages_use_canonical_hero_navigation`
- [ ] `test_governance_workspaces_use_shared_collection_components`
- [ ] `test_translation_workspaces_use_canonical_hero_navigation`
- [ ] `test_translation_collections_use_shared_filter_data_and_pagination_contracts`
- [ ] `test_system_workspaces_use_canonical_hero_navigation`
- [ ] `test_audit_and_developer_pages_use_canonical_hero_navigation`
- [ ] `test_analytics_pages_use_shared_hero_metric_slot`
- [ ] `test_analytics_pages_use_shared_theme_aware_components`
- [ ] `test_case_and_merge_pages_use_canonical_hero_navigation`
- [ ] `test_case_views_use_shared_workspace_components_without_inline_css`
- [ ] `test_demo_command_center_separates_hero_copy_from_operational_context`
- [ ] `test_destructive_confirmations_use_canonical_hero_navigation`
- [ ] `test_specialist_admin_pages_use_canonical_hero_navigation`
- [ ] `test_super_audit_uses_shared_collection_contract`
- [ ] `test_campaign_collection_uses_shared_admin_components`
- [x] `test_every_full_admin_v2_page_uses_canonical_hero_macro`
- [ ] `test_full_admin_pages_use_breadcrumbs_and_standard_back_actions`
- [ ] `test_dead_admin_template_copies_and_legacy_sync_actions_are_absent`
- [ ] `test_retired_media_workspace_is_absent`
- [ ] `test_system_status_uses_shared_theme_aware_health_components`
- [ ] `test_stats_and_demo_audits_use_shared_data_cues`
- [ ] `test_user_editor_layout_lives_in_shared_admin_components`
- [ ] `test_demo_editor_static_geometry_uses_shared_form_components`
- [ ] `test_recurring_editor_static_geometry_uses_shared_form_components`
- [ ] `test_demo_editors_share_the_canonical_media_field_contract`
- [ ] `test_recurring_collection_uses_shared_filter_data_and_modal_contracts`
- [ ] `test_recurring_collection_uses_shared_pagination_component`
- [ ] `test_background_job_detail_uses_shared_code_and_disclosure_components`
- [ ] `test_background_job_collection_uses_shared_workspace_components`
- [ ] `test_admin_boolean_controls_do_not_inherit_text_field_geometry`
- [ ] `test_demo_edit_links_use_the_shared_secure_lifecycle_contract`
- [ ] `test_retired_admin_styles_and_templates_do_not_return`
- [ ] `test_shipping_admin_styles_use_only_semantic_or_bootstrap_tokens`
- [ ] `test_admin_v2_does_not_restore_retired_layout_aliases`
- [ ] `test_demo_suggestion_workflow_uses_shared_admin_components`

USER-01 / QA-03 review follow-up, 2026-10-18, Codex, P2: `test_every_full_admin_v2_page_uses_canonical_hero_macro` is individually assessed. It inventories full admin templates, requires the canonical macro, explicitly includes account confirmation and scoped history, and preserves the structural/localized-confirmation checks. The reviewed count increases from 52 to 53 only for the new full history page; no prior page or assertion is removed. This is source-contract evidence, not visual proof; actual status/history render checks accompany it. Keep; focused run passes.

## tests/test_admin_user_history_durability.py

- [x] `test_concurrent_profile_writes_have_one_attributed_winner`
- [x] `test_event_does_not_reload_a_later_writers_profile`
- [x] `test_failed_projection_keeps_event_and_retry_is_idempotent`
- [x] `test_source_write_failure_cannot_lose_its_event`
- [x] `test_full_pending_outbox_rejects_an_unrecordable_change`
- [x] `test_scope_outbox_survives_projection_failure`
- [x] `test_creation_and_reset_outbox_survive_projection_failure`
- [x] `test_deletion_cannot_drop_pending_history_or_reuse_fresh_auth`
- [x] `test_delete_conflict_returns_matching_response_format`

USER-01 review corrections, Codex, P1 data-integrity gate, 2026-10-18. Twenty-four cases use real Flask/Mongo persistence; wrappers inject timing or explicit delivery/write failures, not fabricated success. No replica-set transactions or live provider delivery are assumed. Existing #887 tests remain intact. The first complete CI gate passed 1,362 cases /325 skips before the final Minor JSON-envelope fix; its expanded deletion/fresh-auth batch passes 47 cases locally, with the final required CI recorded in the PR.

| Definition | Requirement / assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_concurrent_profile_writes_have_one_attributed_winner` | Two distinct authorized actors read the same user; one 302/one 409, one event with winner's actor/old/new and exact persisted name. | Two edit entrypoints, two clients/thread-local contexts, Barrier before actual conditional Mongo write, ten-second failure bound; no sleeps/write-result mocks. Does not prove cross-document request atomicity. | Keep. |
| `test_event_does_not_reload_a_later_writers_profile` | An intervening later stored value cannot be attributed to the earlier request. | Actual Mongo write immediately before projection; wraps the actual registered route namespace to survive fixture module reloads. Exact original-event vs later-account-state assertions. | Keep. |
| `test_failed_projection_keeps_event_and_retry_is_idempotent` | State and original actor/before/after remain durable; authorized read recovers one admin/super-audit event and clears pending queue. | Admin-store failure, super-store failure, real successful insert followed by lost acknowledgement; retries twice, exact event ID and actor preserved. Credential omission asserted. No hard power-loss/storage-durability claim. | Keep. |
| `test_source_write_failure_cannot_lose_its_event` | Rejected source mutation cannot persist state without its event. | Profile/create/reset/grant ×4; injected atomic Mongo exception before real write; exact unchanged account/no created user/no grant/no success event. Not a transaction spanning multiple separately successful writes. | Keep. |
| `test_full_pending_outbox_rejects_an_unrecordable_change` | Saturated 100-event queue blocks further recorded mutation without dropping events. | Delivery disabled at actual route namespace; real bounded CAS, 409 and unchanged name/queue length. Does not prove document-size limits. | Keep. |
| `test_scope_outbox_survives_projection_failure` | Grant/revocation retain their exact durable event on the source grant and recover with one ID. | Two real scope transitions; admin projection failure only, then actual authorized recovery. Role changes are independently audited user writes. | Keep. |
| `test_creation_and_reset_outbox_survive_projection_failure` | Inserted/reset user contains required-reset state and its own safe event despite audit outage. | Create/reset ×2; real request/source write, unavailable projection, then history read and exact event count. Never stores/generated-password proof in history. | Keep. |
| `test_deletion_cannot_drop_pending_history_or_reuse_fresh_auth` | Failed delivery blocks deletion with pending event intact; consumed proof cannot be reused; fresh reauth allows deletion only after recovery, retaining projected history. JSON contains ERROR and translated retry/reauth guidance. | Three FI/EN/SV cases, real compiled catalogs/password step-up/options/nonce/Mongo; temporary delivery failure, exact 503/403/200 sequence. Existing WebAuthn/concurrency/expiry tests retained. | Keep. |
| `test_delete_conflict_returns_matching_response_format` | Competing recorded write blocks actual conditional delete; JSON gets ERROR plus localized reason/reauth guidance while form requests retain HTML409; consumed proof stays unusable. | Six cases: JSON/form × FI/EN/SV; real fresh proof and real Mongo interleaving before the actual conditional delete, not a fabricated deleted_count. Exact surviving name/event ID, 409 format and replay403 asserted. | Keep; covers the independently valid Minor response-format finding. |

## tests/test_admin_user_history.py

- [x] `test_admin_bootstrap_is_pinned_and_served_locally`
- [x] `test_profile_history_records_only_actual_changes_and_no_secrets`
- [x] `test_user_history_includes_city_grants_and_revocation`
- [x] `test_creation_and_reset_requirement_have_safe_history`
- [x] `test_history_adapts_status_logs_and_escapes_values`
- [x] `test_history_rejects_missing_capability_and_higher_targets`
- [x] `test_history_pagination_is_scoped_bounded_and_stable`
- [x] `test_invalid_profile_save_does_not_invent_history`
- [x] `test_user_history_and_transition_copy_follow_locale`
- [x] `test_status_and_history_share_readable_responsive_layout`

USER-01 / QA-01–QA-04, P2; individually reviewed 2026-10-18 by Codex. Real local Flask/MongoDB requests and the shipped templates/styles; shared email/network isolation is retained. No permission, persistence or status-token result mocks. Ten definitions cover 20 parameterized cases. The first complete focused run passes 215 cases across history/status/user administration, hierarchy/fresh deletion, city scope, CSS/token/inline and admin contracts. The subsequent password-reset review correction preserves action audits even without a field difference; focused follow-up evidence belongs in the PR. These are branch results, not production or full-suite review.

| Definition | Requirement / assertions | Setup, reliability and limits | Disposition |
|---|---|---|---|
| `test_admin_bootstrap_is_pinned_and_served_locally` | Admin shell loads the local existing 5.3.3 stylesheet with exact SHA-256 and MIT notice, not the external CSS URL. | Static provenance guard; hash also independently compared with upstream release. Runtime checks below load it while external requests are blocked. No Bootstrap upgrade or JS-hosting claim. | Keep. |
| `test_profile_history_records_only_actual_changes_and_no_secrets` | Both edit POST paths record old/new identity, translator role and exact resulting permissions, actor/time, no password/MFA fields; identical repeat writes no profile event. | Two route cases; legacy direct editor retains existing permissions while save_user uses submitted selection. Exact distinct behavior remains protected. Synthetic secret marker is not a real credential. Does not prove concurrent-edit attribution or transactional audit delivery. | Keep. |
| `test_user_history_includes_city_grants_and_revocation` | Grant records selected city/implied scope permissions; its separate role write records city_admin. Revocation and role restoration likewise have separate exact events. | Actual grant synchronization with real MongoDB; four events reflect four atomic source writes rather than falsely presenting two cross-document transactions. Does not prove all multi-grant/membership paths. | Keep; updated for durable per-write attribution. |
| `test_creation_and_reset_requirement_have_safe_history` | Creation history omits generated password/hash; reset action records false→true and repeated request still records an unchanged action. | Real create/reset endpoints with isolated mail sink; does not prove SMTP delivery, full credential lifecycle or privacy erasure. | Keep. |
| `test_history_adapts_status_logs_and_escapes_values` | Existing status audit plus detail diff render together; old/new emails visible, actor HTML escaped, secret fields/request payload/token absent; response is private/no-store. | Real status confirmation and allowlisted legacy-shaped fixture. Explicitly excludes arbitrary audit payloads, not all historical log schemas or external log sinks. | Keep. |
| `test_history_rejects_missing_capability_and_higher_targets` | Ordinary user and VIEW_USER-only actor denied; EDIT_USER actor cannot inspect higher account; authorized self history works; malformed/missing users 404. | Separate real sessions/roles; server checks apply before history count/query. Not a complete organization-grant/delegation matrix. | Keep with existing privileged-action suite. |
| `test_history_pagination_is_scoped_bounded_and_stable` | 41 equal-timestamp records produce exact reverse-ID pages of 20/20/1 without duplicates or unrelated target data; excessive page/page-size cannot request extra rows. | Real database sort/count and rendered content. No current-page client filtering, DB offset mock or production load claim. | Keep. |
| `test_invalid_profile_save_does_not_invent_history` | Invalid email retains old email and creates no change event. | Actual validation route; paired with unchanged-repeat and hierarchy negatives. Not every form validation combination. | Keep. |
| `test_user_history_and_transition_copy_follow_locale` | FI/EN/SV history title and current/after labels render from shipped catalogs; exact edit-user/cancel runtime labels prevent stale or incorrect navigation copy. | Three real localized session cases and actual GNU catalogs; unrelated runtime entries preserved during targeted compilation. Not complete site localization. | Keep. |
| `test_status_and_history_share_readable_responsive_layout` | Activation/ban removal and closure use readable states/actions; long identity fields fit, keyboard reaches submit/disclosure, targets ≥44px, action text contrast ≥4.5, no document overflow. | Eight real Chromium cases: two actions × light320/dark390/light1440/dark1440. Actual pinned local Bootstrap and local icon fonts; CSS transition settlement is awaited before measuring/capturing, not a fixed delay. Full-page screenshots inspected. Not every locale/browser, screen reader or all admin surface acceptance. | Keep. |

This history uses the existing audit store and its delivery/retention behavior. It is not an atomic user-state/audit transaction, immutable archive, historical backfill or full cross-source audit/GDPR implementation. Unknown legacy secret fields are filtered at presentation; new snapshots are allowlisted before logging.

## tests/test_admin_user_bp.py

- [x] `test_user_control_paginates_results`
- [x] `test_user_control_searches_display_names`
- [x] `test_user_control_filters_by_city_admin_scope`
- [x] `test_edit_user_exposes_translator_role_and_auto_assigns_permission`
- [x] `test_create_user_can_assign_translator_role`
- [x] `test_create_user_can_assign_city_admin_scope`
- [x] `test_create_city_admin_requires_city_selection`
- [x] `test_create_user_rejects_reserved_admin_identity`
- [x] `test_create_user_persists_active_true`
- [x] `test_user_from_db_defaults_active_true`

SEC-03 / QA-01 review, 2026-10-12, Codex, P1. Real admin client, disposable MongoDB and stored grant data; external delivery isolated by fixtures. None of these positive tests alone proves forbidden actions are blocked; the privileged-action tests below supply negative paths. Final run/commit evidence recorded in PR.

| Definition | Requirement / assertions | Coverage and reliability limits | Disposition |
|---|---|---|---|
| `test_user_control_paginates_results` | Expected records/pages split with per_page two. | Fixed unique usernames; not equal-sort-key or concurrent insertion proof. | Keep; deterministic tie-breaker remains data-view work. |
| `test_user_control_searches_display_names` | Display-name search returns matching identity. | Positive substring case only; no permission claim. | Keep. |
| `test_user_control_filters_by_city_admin_scope` | Grant city filter includes/excludes expected users. | Three grant cases; role/grant labeling verified via real list. | Keep. |
| `test_edit_user_exposes_translator_role_and_auto_assigns_permission` | Edit/save preserve translator role and canonical name; implied translation rights persist. | Global admin positive path; delegation refusal covered separately. | Keep. |
| `test_create_user_can_assign_translator_role` | Creation UI options and persisted implied translator capabilities. | Real POST/database; email delivery not verified. | Keep. |
| `test_create_user_can_assign_city_admin_scope` | New city grant has exactly expected cities/default capabilities. | Prevents unrequested permission expansion; #917's explicit new case choices remain separate integration. | Keep. |
| `test_create_city_admin_requires_city_selection` | Missing city prevents account creation. | Redirect plus absent DB identity; no malformed-city matrix. | Keep. |
| `test_create_user_rejects_reserved_admin_identity` | Reserved display identity rejected without persistence. | One reserved variant; validator suite covers broader names. | Keep. |
| `test_create_user_persists_active_true` | New user explicitly enabled/unbanned. | Normal creation contract. | Keep. |
| `test_user_from_db_defaults_active_true` | Legacy missing-active field defaults enabled. | Model compatibility only; runtime access checks covered by account-access tests. | Keep. |

## tests/test_analytics_rollup.py

- [ ] `test_rollup_buckets_legacy_and_modern_timestamps_into_same_counts`
- [ ] `test_rebuild_repairs_inflated_counters_and_prunes_stale_docs`
- [ ] `test_rollup_replay_does_not_double_count`
- [ ] `test_rollup_skips_pass_while_rebuild_paused`
- [ ] `test_rebuild_job_is_registered`
- [ ] `test_prep_writes_in_place_and_is_idempotent`
- [ ] `test_prep_updates_changed_counts_without_duplicating`
- [ ] `test_prep_updates_legacy_random_id_rows_in_place`
- [ ] `test_prep_removes_rows_for_demos_without_raw_events`
- [ ] `test_two_rebuilds_cannot_run_concurrently`
- [ ] `test_public_rebuild_is_skipped_while_another_rebuild_holds`
- [ ] `test_two_workers_cannot_claim_the_same_pass`
- [ ] `test_failed_pass_claim_stops_without_overwriting_pass_state`
- [ ] `test_rebuild_aborts_when_rollup_pass_does_not_settle`
- [ ] `test_stale_pass_claim_can_be_taken_over`
- [ ] `test_flag_without_timestamp_is_not_a_live_pass`
- [ ] `test_taken_over_pass_lease_aborts_without_writing`

## tests/test_anonymous_edit_token.py

- [x] `test_anonymous_edit_token_renders_without_city_admin_navigation`

QA-01d / P1, reviewed 2026-10-15 by Codex. Actual anonymous GET renders the demo form in FI/EN/SV without creating an authenticated session. Safe selected template flags prove approval, link generation and access-panel authority are false; the CSRF field exists and any preserved approved input is hidden, not an editable checkbox. Hidden fields remain part of the existing payload contract, not an authorization boundary; forged POST behavior is assessed separately below. The original label-absence check is retained but cannot alone prove navigation or permissions across locales. This is rendering/state evidence, not full light/dark/mobile or screen-reader acceptance. Real local app and seeded bearer link; no anonymous-user permission mock. Keep, strengthened.

## tests/test_api_contract.py

- [ ] `ApiContractTests::test_openapi_paths_and_methods_match_api_routes`
- [ ] `ApiContractTests::test_openapi_documents_external_non_bp_endpoints`

## tests/test_auth_login_redirects.py

- [x] `test_login_does_not_redirect_back_to_notifications_api`
- [x] `test_login_keeps_normal_internal_page_redirect`
- [x] `test_login_rejects_unsafe_or_non_page_return_targets`
- [x] `test_popup_login_return_target_is_data_not_executable_script`
- [x] `test_popup_login_still_reloads_opener_and_closes`

QA-01c / SEC-05, P1, reviewed 2026-10-15 by Codex, main 9098c02a. Initially five definitions / 45 cases passed after correction; combined with MFA, account-access, auth-page and inline-style checks, 97 passed. CodeRabbit CLI completed review of all six changed files with zero findings. On 2026-10-18, the redirect matrix added six cases for decoded double/triple-leading slashes in normal and popup completion; all five definitions / 51 cases passed. Initial 21-case baseline exposed ten failures; separate browser runs confirmed execution of a harmless injected console marker in both string-breakout and script-ending scenarios before repair. Tests use actual Flask password login and session state with disposable seeded users; HTTP/email/uploads/jobs are isolated by shared fixtures. Browser tests fulfill every request locally, including any escaped destination, with the actual login-generated HTML. No production probe, live exploitation or whole-authentication audit is claimed.

| Definition | Requirement / meaningful assertions | Fixtures, coverage and limitations | Disposition |
|---|---|---|---|
| `test_login_does_not_redirect_back_to_notifications_api` | Login returns exactly the internal root, not notifications API. | Actual successful password POST; exact Location replaces weak suffix assertion. Does not prove all API routes itself. | Strengthened; keep. |
| `test_login_keeps_normal_internal_page_redirect` | Profile and city targets retain path/query/fragment; authenticated session belongs to expected user. | Three valid root-relative URLs, real hash/session. Not every public route or primary-MFA branch. | Strengthened; keep valid-URL compatibility control. |
| `test_login_rejects_unsafe_or_non_page_return_targets` | Absolute/network/ambiguous slash/control/relative/self-loop/API spellings fall back to root in both HTTP and popup completion, without losing successful authentication. | Twenty-two adversarial inputs × two modes, including encoded double/triple-leading slashes; parsed/decoded/dot-normalized path guards are exercised, not only raw string prefixes. Does not establish safety of arbitrary later redirects implemented by destination routes. | New negative matrix; keep. |
| `test_popup_login_return_target_is_data_not_executable_script` | Actual Chromium executes completion HTML without injected console marker or errors, navigates once to same origin and preserves the target as literal URL data. | Two string/script-ending payloads, actual application response, all browser network fulfilled locally. Both executed the marker before repair. Not all browsers or all Unicode/malformed-HTML cases. | New runtime security regression; keep. |
| `test_popup_login_still_reloads_opener_and_closes` | Real browser popup reloads opener exactly once and closes rather than navigating elsewhere. | Actual window.open and reload over intercepted same-origin requests; no opener/close function mocks. No cross-origin opener or production CSP certification. | New preserved-behavior control; keep. |

## tests/test_auth_page_contract.py

- [ ] `test_login_uses_shared_layout_and_conditional_passkey_contract`
- [ ] `test_register_uses_grouped_accessible_shared_form_contract`
- [ ] `test_auth_styles_cover_theme_focus_and_responsive_states`
- [ ] `test_auth_family_uses_one_secondary_action_contract_without_mobile_autofocus`
- [ ] `test_auth_pages_render_without_horizontal_overflow`
- [ ] `test_login_starts_conditional_passkey_mediation`

## tests/test_background_job_detail.py

- [ ] `test_background_job_detail_uses_shared_server_pagination`
- [ ] `test_background_job_detail_normalizes_legacy_page_size`
- [ ] `test_background_job_detail_keeps_selected_run_visible_off_page`

## tests/test_background_jobs.py

- [ ] `test_background_job_manager_executes_prep_job_and_records_audit`
- [ ] `test_background_job_audit_records_history_for_all_demo_write_paths`
- [ ] `test_background_job_history_preserves_demo_id_on_replace_and_update`
- [ ] `test_submit_route_is_idempotent_and_does_not_create_duplicate_demo`
- [ ] `test_submit_duplicate_conflict_can_match_existing_translation_title`
- [ ] `test_conflict_api_can_match_existing_translation_title`
- [ ] `test_merge_duplicate_submissions_repoints_references_and_audits`
- [ ] `test_process_submit_notifications_sends_admin_notifications_immediately`
- [ ] `test_process_submit_notifications_marks_job_error_when_delivery_fails`
- [ ] `test_admin_pending_reminder_ignores_old_completed_notifications`
- [ ] `test_admin_pending_reminder_keeps_recent_completed_notifications_as_blockers`

## tests/test_browser_e2e.py

- [ ] `test_public_pages_render_in_real_browser`
- [ ] `test_standard_public_heroes_share_visual_foundation`
- [ ] `test_user_login_and_notifications_flow_in_real_browser`
- [ ] `test_developer_dashboard_redirects_through_login_in_real_browser`
- [ ] `test_admin_dashboard_redirects_through_login_in_real_browser`
- [ ] `test_submitter_modal_can_be_closed_and_reopened`
- [ ] `test_admin_pages_share_responsive_theme_aware_heroes`
- [ ] `test_admin_summary_cards_center_icons_and_keep_copy_separate`
- [ ] `test_admin_demo_suggestion_selection_and_reject_modal_are_accessible`
- [ ] `test_admin_demo_diff_toggle_and_rollback_modal_are_accessible`
- [ ] `test_admin_filter_toolbars_use_shared_theme_and_fit_viewport`
- [ ] `test_admin_demo_forms_use_shared_theme_and_control_contract`
- [ ] `test_admin_workspace_accessibility_matrix`
- [ ] `test_admin_organizer_editor_supports_mixed_accessible_rows`
- [ ] `test_background_job_detail_uses_shared_responsive_theme_contract`
- [ ] `test_submission_errors_use_shared_responsive_theme_contract`
- [ ] `test_magic_tokens_use_shared_responsive_theme_contract`
- [ ] `test_ui_translation_editor_uses_shared_responsive_form_contract`
- [ ] `test_demo_merge_editor_uses_shared_responsive_form_contract`
- [ ] `test_developer_collections_use_shared_responsive_contract`
- [ ] `test_demo_audit_views_use_shared_responsive_theme_contract`
- [ ] `test_report_error_modal_vertical_fit_and_scroll_contract`
- [ ] `test_report_error_modal_buttons_are_not_overridden_by_page_button_styles`

## tests/test_calendar_localization.py

- [ ] `test_calendar_routes_use_babel_locale_data_instead_of_finnish_maps`
- [ ] `test_calendar_templates_share_locale_and_fallback_contracts`
- [ ] `test_calendar_labels_have_english_and_swedish_translations`
- [ ] `test_current_and_legacy_month_views_render_active_locale`
- [ ] `test_year_view_renders_active_locale`
- [ ] `test_calendar_routes_keep_supporting_proleptic_years`

## tests/test_calendar_preview_safety.py

- [ ] `test_calendar_templates_use_shared_safe_hover_preview_renderer`
- [ ] `test_calendar_mobile_descriptions_are_not_marked_as_html`
- [ ] `test_calendar_preview_helper_only_builds_text_dom_nodes`
- [ ] `test_calendar_preview_renders_untrusted_values_as_text_in_browser`

## tests/test_calendar_year_layout_contract.py

- [ ] `test_calendar_year_uses_versioned_scoped_styles_without_inline_debt`
- [ ] `test_calendar_year_styles_follow_product_theme_and_accessibility_contract`
- [ ] `test_calendar_year_focus_indicators_contrast_with_their_surfaces`
- [ ] `test_calendar_year_keeps_behavioral_hooks_and_respects_reduced_motion`

## tests/test_campaign_admin_ui_contract.py

- [ ] `test_campaign_modal_initializes_inside_deferred_boot`

## tests/test_campaign_volunteer_feedback.py

- [ ] `test_campaign_volunteer_feedback_contract_uses_accessible_in_page_status`
- [ ] `test_campaign_volunteer_api_localizes_required_fields_error`
- [ ] `test_campaign_volunteer_api_rejects_blank_normalized_required_values`
- [ ] `test_campaign_page_embeds_localized_volunteer_feedback`
- [ ] `test_campaign_volunteer_feedback_handles_request_outcomes`
- [ ] `test_campaign_volunteer_validation_focuses_first_invalid_field`
- [ ] `test_campaign_volunteer_validation_rejects_whitespace_only_name`
- [ ] `test_campaign_volunteer_double_submit_starts_one_request`

## tests/test_cities_page_improvements.py

- [ ] `test_cities_page_renders`
- [ ] `test_cities_page_contains_cards`

## tests/test_case_city_scope.py

- [ ] `test_case_list_reuses_edit_scope_and_preserves_autoclose`
- [ ] `test_every_case_route_declares_its_permission`
- [ ] `test_undeclared_case_route_fails_closed`
- [x] `test_ordinary_user_cannot_read_cases`
- [x] `test_city_case_list_and_detail_use_same_scope`
- [x] `test_city_case_mutations_reject_foreign_targets`
- [x] `test_city_admin_can_add_note_to_own_case`
- [x] `test_case_relink_cannot_cross_city_boundary`
- [x] `test_revoked_case_grant_loses_access`
- [x] `test_view_only_case_grant_cannot_write_or_autoclose`
- [x] `test_unlinked_case_and_global_tools_remain_outside_city_scope`
- [x] `test_city_case_reply_and_close_reopen_are_scoped_and_persisted`
- [x] `test_city_key_is_authoritative_over_conflicting_city_text`

SEC-03 / QA-01 review, 2026-10-12, Codex, P1. Real grants, case/demo records and Flask clients; no mocked permission or writes. Fixtures create unique actor/demo/case IDs and reuse canonical stored `type`, not the model attribute name `case_type`. External email delivery isolated; outbound message persistence still exercised. Final commit/run evidence is in the delivery PR.

| Definition | Requirement / assertions | Cases and limitations | Disposition |
|---|---|---|---|
| `test_ordinary_user_cannot_read_cases` | Both list and direct detail deny a logged-in ordinary user. | Exact 403, closes previous login-only exposure. | Keep. |
| `test_city_case_list_and_detail_use_same_scope` | Scoped navigation permission, own row visible, foreign row absent, direct scope enforced. | Real Helsinki/Turku records; query and detail compared. | Keep. |
| `test_city_case_mutations_reject_foreign_targets` | Cross-city note/close/reopen rejected before any write. | Three endpoint parameter cases; full target document remains identical. | Keep. |
| `test_city_admin_can_add_note_to_own_case` | Permitted internal note persists. | Real form and action log. | Keep. |
| `test_case_relink_cannot_cross_city_boundary` | Known case cannot be moved to foreign demo. | Valid foreign demo ID and unchanged link. | Keep. |
| `test_revoked_case_grant_loses_access` | Fresh requests respect grant revocation. | Same cookie, DB revoked marker; no cache-invalidation assumption across requests. | Keep. |
| `test_view_only_case_grant_cannot_write_or_autoclose` | List read does not mutate approved case; POST and rendered note/close controls unavailable. | Actual stored-state equality and rendered HTML; no browser interaction proof. | Keep. |
| `test_unlinked_case_and_global_tools_remain_outside_city_scope` | Unrouted case/global blocklist unavailable to city actor. | Removes linked demo and checks exact denials. | Keep. |
| `test_city_case_reply_and_close_reopen_are_scoped_and_persisted` | Own support reply persists as outbound message; close/reopen state changes work. | Actual queue helper; does not prove external mail delivery. | Keep. |
| `test_city_key_is_authoritative_over_conflicting_city_text` | Stale display city cannot override normalized key. | Deliberately contradictory stored fields, exact denial. | Keep. |

Validation: 51 focused city/case/component/user-management cases passed, including the unchanged default city grant regression. Historical grant backfill and global case capabilities require explicit owner policy, not automatic privilege expansion.

## tests/test_city_assignment.py

- [ ] `TestActiveCityAdmins::test_returns_active_city_admins_with_accept_demo_permission`
- [ ] `TestActiveCityAdmins::test_returns_empty_when_no_admins_for_city`
- [ ] `TestActiveCityAdmins::test_ignores_revoked_grants`
- [ ] `TestActiveCityAdmins::test_ignores_inactive_users`
- [ ] `TestActiveCityAdmins::test_ignores_banned_users`
- [ ] `TestActiveCityAdmins::test_normalises_city_key`
- [ ] `TestActiveCityAdmins::test_ignores_wrong_permission`
- [ ] `TestAssignDemoToCity::test_writes_assignment_and_returns_message`
- [ ] `TestAssignDemoToCity::test_returns_none_for_empty_admins`
- [ ] `TestTouchCityAssignment::test_resets_assigned_at_when_not_escalated`
- [ ] `TestTouchCityAssignment::test_does_not_reset_when_escalated`
- [ ] `TestTouchCityAssignment::test_returns_false_when_no_assignment`
- [ ] `TestClearCityAssignment::test_removes_assignment`
- [ ] `TestClearCityAssignment::test_returns_false_when_no_assignment`
- [ ] `TestEscalateOverdue::test_finds_overdue_demo`
- [ ] `TestEscalateOverdue::test_skips_recently_assigned`
- [ ] `TestEscalateOverdue::test_skips_already_escalated`
- [ ] `TestMarkEscalated::test_flips_escalated`
- [ ] `TestMarkEscalated::test_double_escalation_returns_false`
- [ ] `TestHasLiveAssignment::test_returns_true_for_non_escalated_assignment`
- [ ] `TestHasLiveAssignment::test_returns_false_for_escalated`
- [ ] `TestHasLiveAssignment::test_returns_false_for_no_assignment`
- [ ] `TestNotEscalatedAssignmentClause::test_matches_demos_without_assignment`
- [ ] `TestNotEscalatedAssignmentClause::test_matches_escalated_assignments`
- [ ] `TestNotEscalatedAssignmentClause::test_excludes_non_escalated_assignments`
- [ ] `TestSubmitIntegration::test_city_with_admins_gets_assignment_and_skips_national_queue`
- [ ] `TestSubmitIntegration::test_city_without_admins_falls_back_to_national_queue`
- [ ] `TestDecisionClearsAssignment::test_approve_clears_assignment`
- [ ] `TestDecisionClearsAssignment::test_reject_clears_assignment`
- [ ] `TestEscalationScript::test_escalate_once_succeeds_with_no_overdue`
- [ ] `TestNationalReminderSkipsAssignments::test_enqueues_no_reminders_for_active_assignments`
- [ ] `TestNationalReminderSkipsAssignments::test_enqueues_reminders_for_escalated_assignments`

## tests/test_city_management.py

- [ ] `test_public_cities_lists_enabled_contact_cities_and_demo_cities`
- [ ] `test_admin_city_control_can_toggle_enabled_city`
- [ ] `test_admin_city_control_aggregates_counts_and_offers_bulk_tools`
- [ ] `test_admin_city_control_grant_count_links_to_filtered_user_list`
- [ ] `test_user_city_scope_picker_prioritizes_enabled_cities`
- [ ] `test_create_city_admin_auto_activates_inactive_city`
- [ ] `test_edit_user_city_grant_auto_activates_inactive_city`
- [ ] `test_edit_user_revoking_city_grant_does_not_deactivate_city`

## tests/test_city_scoped_admin.py

- [ ] `test_city_admin_can_open_command_center_and_edit_only_for_assigned_city`
- [ ] `test_city_admin_can_open_create_demo_form`
- [ ] `test_city_admin_without_scoped_permission_still_blocked_from_demo_routes`
- [ ] `test_city_scoped_admin_dashboard_only_lists_assigned_cities`
- [ ] `test_city_scoped_admin_suggestions_hide_other_city_rows_and_counts`
- [ ] `test_city_scoped_admin_audit_timeline_hides_other_city_rows_and_counts`
- [x] `test_explicit_object_id_editor_can_open_scoped_audit_views`
- [ ] `test_string_organization_id_is_included_in_scoped_audit_query`
- [ ] `test_city_scoped_admin_suggestions_show_empty_state_outside_scope`
- [ ] `test_city_scoped_admin_dashboard_shows_accept_action_for_scoped_demo`
- [ ] `test_dashboard_hides_edit_link_quick_action_without_scoped_permission`
- [ ] `test_city_scoped_admin_dashboard_shows_create_demo_action`
- [ ] `test_city_scoped_admin_can_approve_only_assigned_city`
- [ ] `test_city_scoped_permission_does_not_satisfy_unscoped_route_gate`
- [ ] `test_city_admin_gets_limited_organization_permissions`
- [ ] `test_legacy_scoped_user_is_displayed_as_city_admin`
- [ ] `test_city_admin_can_create_and_edit_but_cannot_verify_organization`
- [ ] `test_city_admin_cannot_edit_verified_organization`
- [ ] `test_city_admin_cannot_invite_to_verified_organization`
- [ ] `test_city_admin_can_invite_to_unverified_organization`
- [ ] `test_city_admin_dashboard_redirects_to_scoped_demo_view`
- [ ] `test_edit_user_revokes_object_id_backed_city_scope_grant`

SEC-04b / QA-01 supporting review, 2026-10-16, Codex, P1; only `test_explicit_object_id_editor_can_open_scoped_audit_views` is assessed in this file. Its prior final 403 assertion relied on earlier GET normalization replacing the document and erasing the explicit editor grant. Existing `has_demo_permission` explicitly grants editors access; no production permission rule is changed to make this test pass.

| Definition | Requirement / assertions | Setup, coverage and reliability limits | Disposition |
|---|---|---|---|
| `test_explicit_object_id_editor_can_open_scoped_audit_views` | ObjectId-backed explicit editor can read its scoped audit timeline/detail/command center and still open the editor afterward; persisted editor ID survives those reads. The positive command-center link is a wiring observation, not proof of complete action visibility parity. | Real local user/membership/demo records and authenticated Flask session; no authorization mocks. One explicit-editor/VIEW_DEMO membership scenario, not a full role matrix or proof that all fields remain unchanged. Observed template/server edit-action parity remains a separate UI-affordance gap. | Corrected 403 to 200 based on existing server contract and added persisted-grant assertion. Removed the old negative edit-link assertion rather than making the UI's missing authorized action a required contract; keep. |

## tests/test_config.py

- [ ] `ConfigReloadTests::test_reload_reads_config_from_env_selected_path`
- [ ] `ConfigReloadTests::test_database_manager_reset_clears_singleton`
- [ ] `ConfigReloadTests::test_reload_supports_translation_catalogs_but_publishes_finnish_only`

## tests/test_contact_security.py

- [ ] `test_contact_accepts_bounded_submission_and_adds_correlation_id`
- [ ] `test_contact_rejects_missing_and_consumed_csrf_tokens`
- [ ] `test_contact_rejects_token_replay_from_restored_session_cookie`
- [ ] `test_contact_allows_bounded_tokens_from_concurrent_forms`
- [ ] `test_contact_rejects_streamed_body_without_content_length`
- [ ] `test_contact_honeypot_silently_suppresses_submission`
- [ ] `test_contact_rejects_unapproved_subject_and_oversized_message`
- [ ] `test_contact_runtime_circuit_breaker_preserves_support_email_path`
- [ ] `test_contact_per_ip_rate_limit_is_enforced`
- [ ] `test_contact_global_rate_limit_applies_across_client_addresses`

## tests/test_css_integrity.py

- [ ] `test_brace_balance_ignores_braces_in_strings_and_comments`
- [ ] `test_brace_balance_reports_unclosed_and_extra_braces`
- [ ] `test_all_shipped_css_files_have_balanced_braces`

## tests/test_database_utils.py

- [ ] `DatabaseUtilsTests::test_stringify_object_ids_converts_nested_ids_and_dates`
- [ ] `DatabaseUtilsTests::test_stringify_object_ids_uses_to_dict_for_user_objects`
- [ ] `DatabaseUtilsTests::test_revert_stringified_object_ids_restores_nested_values`
- [ ] `DatabaseUtilsTests::test_date_helpers_round_trip_between_finnish_and_iso`

## tests/test_demo_cancellation_public.py

- [ ] `test_verified_official_contact_can_cancel_demo_immediately`
- [ ] `test_public_report_of_cancelled_demo_creates_request_but_does_not_cancel`

## tests/test_demo_card_i18n_contract.py

- [ ] `test_every_dynamic_demo_card_consumer_includes_shared_card_contract`
- [ ] `test_demo_card_i18n_is_owned_only_by_the_shared_card_partial`
- [ ] `test_demo_card_renderer_has_no_finnish_runtime_fallbacks`
- [ ] `test_demo_card_labels_have_english_and_swedish_translations`
- [ ] `test_demo_list_renders_shared_card_contract_for_active_locale`

## tests/test_demo_rollback.py

- [x] `test_rollback_preserves_current_decision_scope_and_metadata`
- [x] `test_rollback_sparse_history_and_undo_use_actual_content`
- [x] `test_rollback_checks_current_city_scope`
- [x] `test_rollback_conflict_does_not_write_or_record_success`
- [x] `test_rollback_invalid_identifiers_are_not_server_errors`
- [x] `test_rollback_keeps_concurrent_unrelated_metadata`
- [x] `test_rollback_requires_edit_permission_and_csrf`
- [x] `test_rollback_explanation_uses_compiled_locale`
- [x] `test_rollback_restores_canonical_location_and_media_content`
- [x] `test_rollback_guards_canonical_location_and_media_changes`
- [x] `test_rollback_history_failure_retains_exact_event_and_retry_is_idempotent`
- [x] `test_authorized_history_read_recovers_pending_rollback_only_after_scope_check`
- [x] `test_rollback_pipeline_preserves_literal_dollar_prefixed_content`
- [x] `test_demo_read_apis_do_not_expose_pending_rollback_receipts`
- [x] `test_destructive_admin_actions_cannot_drop_pending_rollback`
- [x] `test_recurring_cleanup_retains_pending_rollback_until_delivery`
- [x] `test_delete_conflict_does_not_record_successful_deletion`
- [x] `test_partial_merge_conflict_retains_prewrite_backup`
- [x] `test_merge_backup_failure_prevents_all_content_writes`
- [x] `test_merge_followup_failure_retains_confirmed_removed_source_phase`
- [x] `test_primary_merge_conflict_survives_backup_status_failure`
- [x] `test_merge_phase_failure_does_not_claim_completed_operation`
- [x] `test_delete_history_failure_retains_exact_durable_recovery_copy`
- [x] `test_delete_snapshot_conflict_and_retry_record_actual_latest_document`
- [x] `test_delete_backup_failure_preserves_source_and_history`
- [x] `test_demo_delete_failures_preserve_response_format_and_localized_guidance`

Current e1a003d0 GitHub review's Minor "Return JSON for the new 409 and 503 outcomes when the request is in json_mode" is independently valid: six abort sites returned HTML to dashboard JSON requests. One added definition expands to 24 cases (six failure boundaries × JSON FI/EN/SV or HTML FI). All 18 JSON cases failed before the helper fix; six HTML controls passed. After format handling plus targeted runtime translations, all 24 pass. Final combined integration passed 202 cases (rollback/merge/moderation/decisions, passkeys/fresh deletion, profile and deploy verifier). Fifteen-file bounded local review against e1a003d0 completed with zero findings across 12 source files, excluding three binary MOs; later tracker wording is not part of that review. Exactly two new messages per FI/EN/SV MO, every prior runtime value retained. Historical PO duplicates prevented direct msggrep selection; msguniq is used only in the compiler pipeline before selecting the exact two new IDs, not to rewrite source catalogs or broadly rebuild runtime translations.

| Definition | Requirement and assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_demo_delete_failures_preserve_response_format_and_localized_guidance` | Six pre/post-delete failure paths preserve409/503, JSON status/message envelope and exact localized guidance; HTML remains HTML. Before-delete source/concurrent content and post-delete recovery pre-image are checked independently of response format. | Real scoped admin HTTP/DB and three shipped runtime locales; receipt-flush boundary returnsFalse, specific backup/delete/history/phase DB calls fault-injected, actual conflict write. No auth result mocked; no SMTP/process-kill/all-sink claim. | Keep;18 intended pre-fix format failures and six unchanged HTML controls. |

Bounded follow-up review identified missing post-delete phase tracking and overlapping deletion-history failure findings. Both exception and swallowed-error/None paths are now covered. Twenty-six rollback definitions now expand to 78 cases after the complete-primary-snapshot regression additions. Earlier combined rollback/merge/moderation/decision/MCP/recurrence/user-history/fresh-reauth/passkey/status validation passed 174 cases; GitHub CI on 478cf7c1 passed 1,438 /325 skipped. Current review correction validation passed 73 rollback/merge/moderation/decision cases; diff checks pass. Swedish runtime guidance changes exactly one catalog value, with an explicit rendered cancellation-status assertion. No final zero-finding local-review claim: completed reviews produced findings corrected afterward and manually checked with focused regressions. Recovery backups are not a general automatic recovery worker or a cross-document transaction; failed related-data repointing and unknown acknowledgements still require explicit recovery. Completed/conflicting deletion backups drop their redundant pre-image, while unresolved copies require a separately defined retention/recovery policy.

| Definition | Requirement and assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_merge_followup_failure_retains_confirmed_removed_source_phase` | Recommendation, repointing, case and history failures return 503, retain exact original backup and removed-source evidence, and never mark completed. | Five real route/DB cases; exact registered-handler callback injection includes history returning None, not only raising. No external-provider or crash recovery proof. | Keep. |
| `test_primary_merge_conflict_survives_backup_status_failure` | Primary CAS conflict returns 409 even if recording its recovery phase fails; no secondary is deleted. | Three real-write variants: timestamp/title, cancellation-only and editor-access-only changes. The latter two do not update last_modified and fail before the complete-snapshot guard. Targeted backup-status failure; no fabricated mutation success. | Keep; protects ordinary reachable cancellation/access writes too. |
| `test_merge_phase_failure_does_not_claim_completed_operation` | Failure recording source removal compensates safe writes; failure recording completion preserves confirmed source-removal state and returns 503. | Two phase-boundary exceptions with actual sources/history. Does not prove transactional related-data updates. | Keep. |
| `test_delete_history_failure_retains_exact_durable_recovery_copy` | Missing history acknowledgement returns 503 after deletion while exact pre-image remains in history-pending backup. | None, raised error and real history-insert failure; three cases against disposable Mongo. No automatic replay worker or provider delivery claim. | Keep. |
| `test_delete_snapshot_conflict_and_retry_record_actual_latest_document` | Concurrent edit prevents deletion/false history; explicit retry deletes the latest snapshot and canonical history matches it. | Real interleaved write and route retry; confirmed conflict/completion removes redundant backup pre-image. Not a simultaneous-process test. | Keep. |
| `test_delete_backup_failure_preserves_source_and_history` | Backup-write failure prevents deletion and success history. | Actual admin POST; injected backup boundary only. Does not simulate uncertain acknowledgement. | Keep. |

Integrated follow-up review, 2026-10-19: the initial nine-file CodeRabbit review completed with two Minor and two overlapping Major findings. The missing changelog space is corrected. A real guarded-delete conflict now creates no false delete history/audit. Merge backup is persisted before the first write; each secondary delete returns its actual pre-image, enabling insert-only compensation. The primary is compensated only while its complete document still equals this merge's result; newer changes are preserved and failed/ambiguous recovery remains explicitly incomplete with 503, not an unqualified 409 or successful merge. Three newly assessed definitions cover four cases. Existing recurring-cleanup coverage additionally asserts no false delete runtime action on a retained child. This is compensation plus retained recovery data, not replica-set transaction/automatic recovery-worker acceptance.

| Definition | Requirement and assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_delete_conflict_does_not_record_successful_deletion` | Real delete guard loses to a newly inserted receipt marker: 409, complete source unchanged except marker, no added edit-history or deletion audit. | Mongo wrapper inserts a marker immediately before actual conditional delete, not a fake delete result or full concurrent rollback HTTP request. Existing normal deletion tests remain separate. | Keep; verifies the independently valid Minor false-success finding. |
| `test_partial_merge_conflict_retains_prewrite_backup` | Backup already exists before first/second secondary writes. A source with new receipt survives; an earlier deleted source is recreated exactly. Without newer primary, exact primary is restored and409/backup-restored; with newer primary, preserve it and503/recovery-pending backup. | Three real source docs; one real deletion before a controlled receipt/newer-title interleaving. Actual pre-images, guarded replacement and insert-only restoration. Does not prove every database interruption, source recreation race, or compensation after partial related-data repointing. | Keep; two real compensation cases for the overlapping Major findings, not just availability of an unused backup. |
| `test_merge_backup_failure_prevents_all_content_writes` | Backup insert fails: 503, complete demo collection unchanged and no backup/successful merge. | Actual admin POST; exception injected only at backup-write boundary. Does not simulate driver acknowledgement loss or disk failure. | Keep; fail closed before destructive writes. |

Durability follow-up, 2026-10-19: six definitions /nine cases use actual source-document update pipelines and history upserts against standalone disposable MongoDB. Tests inject only projection/receipt-cleanup failures, not mutation success. Exact snapshots, actor, stable event ID and one canonical history row survive failure/retry; receipt payload is never nested inside its own snapshots. Existing concurrency and metadata-preservation cases continue to exercise real conditional writes. All 69 combined rollback/merge-editor/moderation/decision/MCP/recurrence cases pass; no full-suite, production, deletion/merge cross-document atomicity, power-loss or full audit-retention claim. Requires MongoDB 4.2+ update pipelines, not replica-set transactions. Main integration and completed local review are required before push/delivery.

| Definition | Requirement and assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_rollback_history_failure_retains_exact_event_and_retry_is_idempotent` | History projection or source cleanup failure returns 503 but retains exact original before/after/actor/event ID. Repeated failure cannot overwrite receipt; recovery and repeated no-op produce one history row and remove only delivered receipt. | Two real Mongo paths with targeted write-boundary exceptions. Covers ambiguous cleanup completion after history already persisted. Not a process-kill/storage durability test. | Keep. |
| `test_authorized_history_read_recovers_pending_rollback_only_after_scope_check` | Unauthorized history request cannot deliver/clear pending data; authorized GET projects original event and clears receipt. | Real route permissions/session and standalone Mongo; recovery comes from actual read, not explicit helper mocking. Original actor retained. | Keep. |
| `test_rollback_pipeline_preserves_literal_dollar_prefixed_content` | Dollar-prefixed title, tag and nested translated title persist as literal data; history equals actual result. | Real aggregation update, no Mongo evaluator mock; guards against treating content as pipeline expressions. Not a full BSON-size/type/legacy-document audit. | Keep. |
| `test_demo_read_apis_do_not_expose_pending_rollback_receipts` | Raw admin demo API and MCP get_demo retain normal title but omit internal receipt and its private fixture text. | Actual authenticated/scoped transports; existing public listing uses an allowlisted projection and detail serializer. No policy change or all-future-sink assertion. | Keep. |
| `test_destructive_admin_actions_cannot_drop_pending_rollback` | Delete and primary/secondary merge attempts fail 503 with all demo documents unchanged while delivery fails; successful later flush yields exact original event. | Three actual admin POSTs. Does not claim concurrent multi-document merge atomicity or retention protection against direct DB administrators. | Keep. |
| `test_recurring_cleanup_retains_pending_rollback_until_delivery` | Invalid recurring child survives pending delivery failure, then normal cleanup deletes it only after exact history projection. | Real processor with disposable DB globals and dry-run disabled via fixture monkeypatch; runtime_actions reset. No production scheduler/leader or SMTP evidence. | Keep. |

Review follow-up, 2026-10-19: both new definitions add five cases each for latitude, longitude, img, cover_source and canonical event_type. All ten fail against the previous 942 head at the intended missing-restore or missing 409 assertions, then pass after including those fields in the shared update/guard set. Combined rollback/moderation/decision run:42 passed. The existing CSRF test now extracts the actual target form token with stdlib HTMLParser instead of undeclared bs4; real negative/positive authorization and persistence assertions are retained. Source, test and inventory changes remain local until the outstanding history-durability finding and current-main integration are complete; no merge/release claim.

| Definition | Requirement and assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_rollback_restores_canonical_location_and_media_content` | Field-only historical restore changes the exact canonical value, preserves every other field except timestamp, records exact before/after, and supports undo back to the value before restore. | Five fields, sparse history and actual HTTP/MongoDB. No constructor/rendering or media/network mocks; test values are stored fixture data, not remote downloads. Does not prove history-write durability (still open). | Keep; all five reproduced the omitted-field regression. |
| `test_rollback_guards_canonical_location_and_media_changes` | A concurrently added canonical field causes409, leaves precisely the competing write and creates no success history. | Five initially absent fields; a wrapper inserts a real write just before the real conditional Mongo update. No timing sleeps or fabricated write results. Covers missing→present guard boundaries, not every transition or grant revocation. | Keep; all five reproduced the missing guard. |

SEC-04c / QA-01, P1, Codex, 2026-10-18. Real Flask requests and disposable MongoDB; no authorization/write-result mocks. Sixteen parameter-expanded cases. Focused run/PR evidence is recorded in the delivery PR. Existing fixture isolates external mail/network side effects; this is not production verification or transactional audit durability.

| Definition | Requirement and assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_rollback_preserves_current_decision_scope_and_metadata` | Actual content/explicit clearing restored, every other stored field preserved; exact actual before/after and actor recorded; repeated restore adds no event. | Real approve/deny API ×2, captured mail boundary, exact unchanged case/link rows and one notification; historical foreign identity/scope/moderation/cancellation injected. Does not prove provider delivery or history-write crash recovery. | Keep. |
| `test_rollback_sparse_history_and_undo_use_actual_content` | Sparse snapshots cannot erase missing fields; the newly recorded previous content can itself be restored. | Real two POSTs and DB state; no broad unknown-field retention policy claim. | Keep. |
| `test_rollback_checks_current_city_scope` | Current own-city edit allowed; old in-scope snapshot cannot authorize foreign current target, with no content/history write. | Real scoped admin/grant, own/foreign ×2; no mocked permission predicate. Grant revocation between check and write is not proven. | Keep. |
| `test_rollback_conflict_does_not_write_or_record_success` | Interleaved content or authoritative city-key changes yield 409, preserve competing write and create no success record. | Two variants; wrapper introduces a real Mongo update immediately before real conditional update, does not fabricate result. Also exercises initially absent city_key. No sleeps; not an all-entrypoint concurrency proof. | Keep. |
| `test_rollback_invalid_identifiers_are_not_server_errors` | Malformed/missing history and malformed/missing target return 404. | Four real routes; no stacktrace/500 acceptance. | Keep. |
| `test_rollback_keeps_concurrent_unrelated_metadata` | Background metadata update does not cause a false conflict; actual atomic pre-image and restored state include the fresh value. | Real Mongo interleaving via method wrapper, no fabricated result; exact before/after assertions. Added after independently validating the review's Minor false-conflict finding. | Keep. |
| `test_rollback_requires_edit_permission_and_csrf` | Non-admin denied; absent/wrong token rejected without mutation; actual rendered session-bound proof succeeds. | Real session/form and standard-library HTMLParser extraction; project uses route-specific CSRF, not a global extension. No CSRF mock/config-only assertion. | Keep. |
| `test_rollback_explanation_uses_compiled_locale` | Actual confirmation explains content-only restoration in FI/EN/SV rather than source fallback. | Three real session-locale GETs, actual shipped MO; public locales enabled in fixture. No visual/all-copy claim. | Keep. |

## tests/test_demo_decision_ordering.py

- [x] `test_later_opposite_decision_preserves_case_and_history_consistency`
- [x] `test_current_decision_retries_case_compare_and_set_after_an_older_writer`
- [x] `test_overlapping_same_decision_keeps_one_history_and_notification`
- [x] `test_unchanged_request_retries_the_actual_newer_decision_notification`

SEC-04a / QA-01, P1; individually assessed 2026-10-15 by Codex, stacked on #938. Real domain service, local MongoDB and separate thread-local Flask app contexts; no mocked transition or case write outcomes. Collection/service wrappers add Event synchronization only, with ten-second failure guards and finally release; no sleep-based ordering. Captured enqueue is the external boundary. These tests bypass route permissions/CSRF and do not establish live multi-process operation, notification delivery order or provider acceptance/crash safety.

| Definition | Requirement / assertions | Cases, coverage and reliability limits | Disposition |
|---|---|---|---|
| `test_later_opposite_decision_preserves_case_and_history_consistency` | Later persisted decision owns final demo/case identity/outcome. Each changed result and exactly one persisted history retain their own state/identity, not a later read. | Six cases: both decision directions paused after real atomic transition, before case projection or immediately before actual conditional case write. First four baseline cases fail with contradictory case outcome. Does not enumerate every interleaving, all cases or later unrelated edits/deletions. | New real regression; keep. Removing only case CAS in a test process makes both narrow-window cases fail at final outcome. |
| `test_current_decision_retries_case_compare_and_set_after_an_older_writer` | Newer decision loses first case CAS, re-reads and succeeds on second write; final case matches newer demo and both case history entries appear once in actual write order. | Two directions; both writers pause at their real update boundary, older writer released first. Exact two newer update attempts proves retry branch exercised. No forced perpetual-contention or database interruption coverage. | New retry-path regression; keep. |
| `test_overlapping_same_decision_keeps_one_history_and_notification` | One changed/one unchanged result share decision ID, one captured email/notification record/history/decision audit, one case decision entry and canonical outcome. | Two decisions; first paused after transition while second reconciles. Real Mongo unique notification claim. Does not prove crash recovery between transition/notify flag or enqueue/provider acceptance. | New overlapping idempotency regression; keep alongside sequential #938 tests. |
| `test_unchanged_request_retries_the_actual_newer_decision_notification` | A no-op request paused before rereading a newer opposite decision retries the newer failed notification type, not its own superseded requested status; result and case share actual persisted identity/state. | Two directions with a real conditional no-op, intervening transition and deterministic pre-enqueue failure. Real registry claim removal/unique insert; captured email boundary. Does not certify provider failure-after-acceptance handling. | New mixed-status retry regression; removing current-status adoption makes both cases fail on notification type. |

Combined focused decision/edit-link/anonymous run passes 24 cases, including twelve new interleaving cases; test-only mutations dropping the case write precondition and current-status adoption detect stale overwrite/wrong notification type in both directions. Subsequent normal 24-case run passes, Python compilation/diff checks pass, and final five-file CodeRabbit review completed with zero findings (later status/evidence text updates excluded). Black is unavailable; no formatter-run claim. No transaction, lock service, new persisted fields or clock-based ordering is introduced. Case compare-and-set retries are bounded at eight; exhaustion raises a retriable failure rather than claiming successful reconciliation. Exhaustion/DB-crash recovery, external email ordering, same-demo ordinary edit/rollback metadata preservation and route-level conflict messaging remain separate SEC-04 evidence gaps, not completed acceptance.

## tests/test_demo_decision_service.py

- [x] `test_legacy_approval_is_idempotent_and_reconciles_all_side_effects`
- [x] `test_token_rejection_consumes_used_token_and_revokes_siblings`
- [x] `test_form_approval_uses_canonical_decision_service`
- [x] `test_admin_api_rejection_is_idempotent`
- [x] `test_notification_delivery_can_retry_without_repeating_decision_effects`
- [x] `test_bulk_decision_uses_same_service_and_reports_each_result`

QA-01e / SEC-04, P1; six definitions individually assessed 2026-10-15 by Codex on main 9098c02a. Real local Flask clients, signed seeded tokens, actual Mongo conditional writes and persisted cases/history/audit. Only email enqueue is captured or made to raise; this is not SMTP/worker delivery evidence. Existing dual-import email aliases are patched explicitly. Fixture-admin sessions bypass primary login; role/CSRF negatives, token expiry/IP/concurrency and privacy redaction are not established by these tests. All 12 combined decision/edit-link/anonymous cases pass; diff check and exact AST membership pass. CodeRabbit completed the four changed-file review with zero findings (later roadmap/status reconciliation excluded from that snapshot). #674 is already closed; this review does not reopen its old route-duplication report or certify crash/concurrent-decision acceptance.

| Definition | Requirement / meaningful assertions | Fixture, coverage and reliability limits | Disposition |
|---|---|---|---|
| `test_legacy_approval_is_idempotent_and_reconciles_all_side_effects` | Legacy approve then API approve preserve decision identity/source, one notification/history/decision audit, canonical booleans, exact public URL, all four token families revoked. Two linked cases with ObjectId/string IDs close once with matching actor/source/time; unrelated case remains byte-for-field equal. | Actual DB and route adapters; inserted control cases prevent one-case/vacuous isolation coverage. No opposite-decision race, missing submitter or partial crash. | Strengthened; keep. Test-process mutation removing string-ID lookup fails the new closed assertion. |
| `test_token_rejection_consumes_used_token_and_revokes_siblings` | Rejection sets canonical state, consumes chosen token, revokes nonempty preview/approve sibling set, sends one email and writes one history/audit. Replay renders existing friendly used-link page, preserves used timestamp/decision and sends nothing again. | Real signature/registry/route; HTTP 200 is intentional friendly replay policy, not fresh success. Seed has no edit sibling; four-family terminal revocation is checked in legacy-approval test. Not token race/IP/expiry proof. | Strengthened replay and non-vacuous policy assertions; keep. |
| `test_form_approval_uses_canonical_decision_service` | Form sets canonical booleans/source and linked case outcome/closed decision identity, one email/history/audit. | Real authenticated save with minimal valid data; not field/UI/browser or forged approval authority proof (separate tests). Only approval, not all form transitions. | Strengthened side-effect assertions; keep. |
| `test_admin_api_rejection_is_idempotent` | Two API denials yield changed then unchanged, stable decision metadata, canonical rejected state, closed rejected case, single email/history/decision audit. | Same sequential client, real DB, captured enqueue; does not establish simultaneous requests or opposite decisions. | Strengthened identity/state/audit assertions; keep. |
| `test_notification_delivery_can_retry_without_repeating_decision_effects` | Enqueue failure returns 500 after canonical approval, removes delivery claim; alternate-entrypoint retry keeps decision ID and queues identical content once with queued_at. Third call does not enqueue or alter case/history/audit. | Deterministic queue exception before enqueue succeeds, no timing sleep. Cannot prove crash after external acceptance/before queued_at, or actual provider exactly-once delivery. | Strengthened intermediate and final state assertions; keep; delivery crash window remains explicit. |
| `test_bulk_decision_uses_same_service_and_reports_each_result` | Duplicate selected ID collapses to one changed result, malformed ID has own exact status, retry reports unchanged with zero changes and one total email/history/audit. | Real bulk route and seeded session CSRF; authorized happy path only, no forbidden/not-found/limit/CSRF negative matrix. | Strengthened deduplication/retry assertions; keep with remaining boundary coverage tracked. |


## tests/test_demo_edit_link_lifecycle.py

- [x] `test_edit_link_duration_is_allowlisted_and_registry_expiry_matches`
- [x] `test_each_edit_link_is_unique_and_revocation_blocks_anonymous_access`
- [x] `test_anonymous_edit_token_can_save_with_session_csrf`
- [x] `test_send_edit_link_ignores_client_url_and_does_not_use_persistent_queue`
- [x] `test_edit_link_lifetime_applies_to_anonymous_get_and_post`
- [x] `test_edit_link_management_rejects_missing_or_wrong_csrf`
- [x] `test_revoke_all_edit_links_is_demo_scoped_and_blocks_existing_sessions`
- [x] `test_edit_link_requires_matching_signature_and_registry_before_get_or_post`
- [x] `test_recurring_editor_does_not_offer_regular_demo_edit_links`

QA-01d / SEC-04, P1, individually reviewed 2026-10-15 by Codex, based on main 9098c02a. Nine lifecycle definitions / 28 cases plus three anonymous-shell cases; combined with unchanged decision-service regressions, 37 cases pass. CodeRabbit CLI completed both changed test files with zero findings; diff and exact inventory checks pass. Real local Flask/MongoDB and itsdangerous signing/validation; requests/email/uploads/jobs are isolated by shared fixtures. Admin/anonymous actors are real session identities, not permission mocks. The lifetime matrix changes only the registered demo-link serializer's timestamp source and its domain UTC clock, leaving session-cookie clocks/signatures intact. #672 is already closed; this verifies/enhances coverage of existing implementation, not a new lifecycle-policy feature or release claim.

| Definition | Requirement / meaningful assertions | Setup, coverage and limits | Disposition |
|---|---|---|---|
| `test_edit_link_duration_is_allowlisted_and_registry_expiry_matches` | 1h/24h/7d map to exact registry durations/expiry and returned metadata; raw token absent from record; unsupported 30d creates no link. | Three real creation variants. Not every malformed JSON/type/duration input or entropy analysis. | Strengthened all allowed durations and no-op rejection; keep. |
| `test_each_edit_link_is_unique_and_revocation_blocks_anonymous_access` | Two links differ; revoking first blocks GET and POST from previously valid CSRF session without mutation, while second remains usable. | Real generated signatures/registry and revocation endpoint. Uniqueness sample is not a collision-probability proof or concurrent revoke/save guarantee. | Strengthened POST and sibling control; keep. |
| `test_anonymous_edit_token_can_save_with_session_csrf` | Missing/wrong CSRF cannot change title; valid session CSRF saves, but forged approval cannot flip either initial approval state; raw token absent from super-audit records. | Two initial approval states, actual form handler. The audit assertion covers this sink and token, not all logs/providers/URLs. | Strengthened CSRF negatives and server authority; keep. |
| `test_send_edit_link_ignores_client_url_and_does_not_use_persistent_queue` | Email sink receives expected recipient and server-origin edit route; generated link actually opens anonymously; queue path raises if called. | Actual server creation with captured direct-send boundary, both historical module aliases patched. Does not prove SMTP delivery or provider retention. | Strengthened exact origin/path and real resolution instead of startswith(http); keep. |
| `test_edit_link_lifetime_applies_to_anonymous_get_and_post` | Correct 1h/24h/7d behavior before/at expiry, including valid links beyond the former one-hour limit; expired GET/POST return 410 without mutation and show friendly expired state. | Seven real signed/registry age variants; initial GET supplies valid CSRF so denial is not masked by missing CSRF. Only local domain/signer clocks changed. Not every corrupted legacy timestamp or concurrent revocation interleaving. | New signature/registry lifetime integration; keep. |
| `test_edit_link_management_rejects_missing_or_wrong_csrf` | Generate/send/revoke/revoke-all each return 403 without CSRF or with mismatch; registry count/revoked flag and mail sink unchanged. | Eight authorized-admin requests so CSRF denial is meaningful. Does not establish every role/city/org scope or every audit side effect. | New management CSRF matrix; keep. |
| `test_revoke_all_edit_links_is_demo_scoped_and_blocks_existing_sessions` | Two target-demo links and existing edit session become unusable; another demo's link remains valid; non-edit registry actions retain revoked state; denied POST leaves title unchanged. | Real registry/generation/revoke-all endpoints and separate anonymous clients. Not a distributed revoke-vs-save race or case/notification decision-policy audit. | New scoped bulk regression; keep. |
| `test_edit_link_requires_matching_signature_and_registry_before_get_or_post` | Tampering, missing registry, wrong registry action or demo each reject GET and valid-CSRF POST before changing original target. | Four scenarios with initially valid bearer/session; registry mutations prepare corrupt state, not mocked resolver results. Does not cover every itsdangerous serialization/version/corrupt-payload case. | New binding negatives; keep. |
| `test_recurring_editor_does_not_offer_regular_demo_edit_links` | Recurring form omits regular edit-link controls while duplicate action remains. | Real rendered admin route, existing UI IDs. This is visibility evidence, not backend permission denial for every recurring payload. | Keep with narrow claim. |

## tests/test_demo_moderation_preservation.py

- [x] `test_mcp_creation_always_starts_pending`
- [x] `test_mcp_content_patch_cannot_change_moderation`
- [x] `test_model_content_save_preserves_moderation_state`
- [x] `test_model_creation_still_inserts_complete_content`
- [x] `test_form_content_edit_keeps_approval_identity_and_case_history`

SEC-04b / QA-01, P1; individually assessed 2026-10-16 by Codex, stacked on #939. Real Flask/Mongo/model normalization and canonical approval API; only enqueue is captured through the established dual-alias helper from #938. Three initial cases reproduced erased decision metadata and a new decision identity after an ordinary form edit. Existing-document save now sets modeled fields instead of replacing the document; unknown server-owned fields remain the owning workflow's responsibility and must be explicitly unset when retired. New-document insertion is unchanged.

| Definition | Requirement / assertions | Cases, setup and reliability limits | Disposition |
|---|---|---|---|
| `test_mcp_creation_always_starts_pending` | MCP creation does not advertise approval and persists pending state even if an approval boolean is supplied; no decision identity or notification is invented. | Two actual HTTP tools/list and tools/call cases using write-scoped credentials and MongoDB; both true and false inputs. Captured enqueue is not SMTP evidence. Unknown approval input is ignored consistently with other unknown creation fields. | Reviewed 2026-10-18; keep. |
| `test_mcp_content_patch_cannot_change_moderation` | Generic MCP approval patches fail before content writes; exact demo/case snapshots and one notification remain unchanged. | Four real HTTP cases: approved/rejected initial decisions × true/false patch, including a title change to detect partial application. Snapshot follows MCP app initialization so migrations are not confused with request writes. Enqueue captured, not SMTP delivery. | Reviewed 2026-10-18; keep. |
| `test_model_content_save_preserves_moderation_state` | After canonical approve/deny, normalization plus title edit/explicit description clearing keeps exact decision metadata and canonical booleans. Repeating the same decision reports unchanged and leaves one captured email. | Two status variants, actual constructor/save (including normalization-triggered saves), real stored decision/notification. Captured enqueue is not external delivery evidence. No concurrent stale-content/approval edit claim. | New regression; keep. |
| `test_model_creation_still_inserts_complete_content` | A new content model still persists its ID/title/city/pending approval without invented moderation metadata. | Explicit app/database fixtures; constructor may auto-save normalized time before explicit save, so this checks ordinary creation lifecycle rather than isolating one call/insert count. | New insertion-path regression; keep. |
| `test_form_content_edit_keeps_approval_identity_and_case_history` | Real approved-demo form save changes the title while retaining exact decision metadata and complete linked case document; no second notification. | Authenticated fixture admin with valid minimal form data; not browser rendering, primary login, unauthorized checkbox/CSRF or rejection-form transition coverage. | New route regression; keep alongside existing scoped negatives. |

The combined moderation/translation/organizer/city-scope run passes 57 cases after correcting the separately assessed destructive-read-dependent editor assertion. Creation also passes alone with explicit app/database fixtures. Python compilation, diff and exact AST membership checks pass. CodeRabbit completed the four implementation/test/initial-plan file review with zero findings; a follow-up covering both finalized test files also completed with zero findings. Later inventory/status text is not part of those review snapshots. Broad replacement behavior previously removed fields the model never serialized, including rejected/moderation/editor data. This correction does not change permission predicates, #887, payloads or CSS. Historical rollback authorization, ordinary stale-content writes racing a newer decision, and full server-owned-field lifecycle/retention audits remain explicit SEC-04 gaps.

## tests/test_demo_suggestion_public.py

- [ ] `test_suggest_change_get_shows_clean_route_and_markdown_description`
- [ ] `test_suggest_change_post_converts_markdown_and_normalizes_route`
- [ ] `test_suggest_change_post_does_not_add_lossy_description_when_only_other_fields_change`

## tests/test_demo_translation_cache.py

- [ ] `test_get_or_create_deepl_suggestions_for_demo_caches_result`
- [ ] `test_get_or_create_deepl_suggestions_for_demo_refreshes_when_source_changes`
- [ ] `test_get_or_create_deepl_suggestions_for_demo_skips_past_demos_by_default`

## tests/test_demo_translation_suggestions.py

- [ ] `test_build_deepl_translation_suggestions_returns_structured_proposals`
- [ ] `test_build_deepl_translation_suggestions_requires_configuration`

## tests/test_demo_translation_workflow.py

- [ ] `test_translator_can_access_translation_dashboard`
- [ ] `test_translation_dashboard_hides_past_demos_by_default`
- [ ] `test_translation_dashboard_never_includes_past_demos`
- [ ] `test_translation_dashboard_paginates_filtered_results_deterministically`
- [ ] `test_translation_dashboard_hides_unchanged_recurring_children`
- [ ] `test_translator_can_propose_translation_for_recurring_parent`
- [ ] `test_admin_can_approve_recurring_parent_translation`
- [ ] `test_translation_dashboard_shows_changed_recurring_children`
- [ ] `test_translator_can_open_translation_editor`
- [ ] `test_translation_editor_displays_descriptions_as_markdown`
- [ ] `test_translator_can_generate_cached_deepl_suggestion`
- [ ] `test_translator_can_submit_demo_translation_proposal`
- [ ] `test_translation_proposal_stores_markdown_as_safe_html`
- [ ] `test_translator_proposal_can_record_deepl_provenance`
- [ ] `test_admin_can_approve_demo_translation_proposal`
- [ ] `test_regular_user_cannot_access_translation_dashboard`

## tests/test_demonstration_translations.py

- [ ] `test_demonstration_translation_falls_back_to_base_fields`
- [ ] `test_demonstration_translation_normalizes_tags_and_roundtrips_to_dict`
- [ ] `test_demonstration_can_serialize_localized_payload`
- [ ] `test_demo_localization_helper_supports_dict_payloads`

## tests/test_dependencies.py

- [ ] `TestDependencyIntegrity::test_no_dependency_conflicts`
- [ ] `TestDependencyIntegrity::test_core_dependencies_importable`
- [ ] `TestDependencyIntegrity::test_all_declared_dependencies_importable`
- [ ] `TestDependencyIntegrity::test_requirements_file_exists_and_pinned`
- [ ] `TestDependencyIntegrity::test_dev_requirements_extends_base`

## tests/test_deploy_build_sha.py

- [x] `test_build_sha_is_captured_from_environment`
- [x] `test_build_sha_file_rejects_partial_or_invalid_values`
- [x] `test_health_endpoint_publishes_uncached_worker_build`
- [x] `test_verifier_waits_past_old_worker_for_replacement`
- [x] `test_verifier_rejects_plain_200_without_matching_metadata`
- [x] `test_production_deploy_contract_is_sha_bound`
- [x] `test_verifier_reads_origin_socket_without_proxy`
- [x] `test_verifier_reports_cloudflare_challenge_without_body_or_url`
- [x] `test_verifier_reports_missing_origin_socket`
- [x] `test_verifier_passes_socket_while_waiting_for_new_worker`
- [x] `test_verifier_rejects_unsupported_or_credentialed_socket_urls`
- [x] `test_verifier_distinguishes_empty_from_omitted_socket`
- [x] `test_public_challenge_warning_requires_verified_origin`
- [x] `test_public_origin_receipt_must_match_expected_https_build`
- [x] `test_later_challenge_cannot_hide_previous_bad_public_health`

OPS-04a · P1 · Codex · 2026-10-22, main63c85eae. Three new individually assessed definitions /sixteen cases. All40 focused deploy cases pass; YAML/every workflow run-step Bash syntax, deploy Bash syntax and diff checks pass. Seven-file local CodeRabbit review completed with zero findings (subsequent tracker/evidence text excluded). Existing SHA-bound deployment contract also verifies the output receipt is emitted after SSH succeeds and passed into the public verifier, not an unconditional success override. Transport responses are controlled urllib outcomes; these tests do not prove an actual GitHub SSH command or live Cloudflare policy. Origin socket tests continue to use a real local HTTP socket server. No deployment/browser release acceptance claim.

| Definition | Purpose / setup / assertions | Reliability / coverage / disposition |
|---|---|---|
| `test_public_challenge_warning_requires_verified_origin` | Nine CLI cases: explicit403 challenge with/without matching origin, normal403,503 with challenge header, correct/stale/unhealthy/invalid200 payload and network failure. Only proven-origin challenge warns; no URL/body leakage or false public-SHA success message. | Real CLI/parsing/retry/response handling with mocked urllib transport; no live CDN. Keep. |
| `test_public_origin_receipt_must_match_expected_https_build` | Five malformed/unsafe receipt combinations reject before probing: different/empty SHA, HTTP, URL credentials and socket mode. | Sentinel probe would fail if validation accidentally continued. Not an authentication proof: receipt comes from trusted workflow step output. Keep. |
| `test_later_challenge_cannot_hide_previous_bad_public_health` | Stale or unhealthy200 followed by explicit challenge remains failure without warning. | Two ordered transport sequences, actual parser/CLI and no sleeps. Ensures exemption cannot erase observed app failures; no general CDN diagnosis. Keep. |

OPS / QA-01 review, 2026-10-16, Codex, P1. Base `9098c02a`; passed focused validation:
`pytest -o addopts='' -q tests/test_deploy_build_sha.py` (24 cases),
plus Bash syntax and `git diff --check`. No production reload or end-to-end
deployment performed.

| Definition | Purpose / setup / assertions | Reliability / coverage / disposition |
|---|---|---|
| `test_build_sha_is_captured_from_environment` | Monkeypatched environment; exact valid SHA resolution. | Deterministic; environment precedence only. Keep. |
| `test_build_sha_file_rejects_partial_or_invalid_values` | Temporary file, unset environment; rejects partial SHA and accepts full SHA. | Real file reads; not a concurrent atomic-write test. Keep. |
| `test_health_endpoint_publishes_uncached_worker_build` | Real Flask fixture; config SHA, 200 JSON, no-store and build header. | Tests endpoint contract, not real Gunicorn reload. Keep. |
| `test_verifier_waits_past_old_worker_for_replacement` | Mocked SHA sequence/sleep; two old responses followed by expected SHA. | Deterministic retry logic; transport covered separately. Keep. |
| `test_verifier_rejects_plain_200_without_matching_metadata` | Mocked absent SHA/sleep; bounded retries cannot succeed. | Transport payload validation covered by origin tests. Keep. |
| `test_production_deploy_contract_is_sha_bound` | Reads real shell/workflow/docs; SHA verifier, socket argument, independent public HTTPS and restricted SSH contract. | Static guard, not shell execution or actual key permissions. Keep. |
| `test_verifier_reads_origin_socket_without_proxy` | Real temporary Unix HTTP server; five HTTP/body variants for both HTTP and HTTPS logical URLs; broken proxies, public transport forbidden; exact Host/path, direct fetch and CLI result. | Ten cases catch HTTPS override rejection in either validation layer; proves local transport, not production process setup. Keep. |
| `test_verifier_reports_cloudflare_challenge_without_body_or_url` | Mock urllib HTTP 403/challenge containing private URL/body; captured stderr names challenge without leaking data. | Reproduces known Cloudflare response contract; no live WAF dependency. Keep. |
| `test_verifier_reports_missing_origin_socket` | Real nonexistent short socket path; None result and safe exception class diagnostic. | Deterministic filesystem failure; no remote request. Keep. |
| `test_verifier_passes_socket_while_waiting_for_new_worker` | Mocked transport old/new sequence; exact socket passed on both probes. | Socket transport tested separately; keeps retry wiring covered. Keep. |
| `test_verifier_rejects_unsupported_or_credentialed_socket_urls` | Three CLI argument variants; argparse exit 2 for FTP or embedded HTTP/HTTPS credentials. | No real connection; local socket support does not permit unsupported schemes or URL credentials. Keep. |
| `test_verifier_distinguishes_empty_from_omitted_socket` | Two CLI variants with mocked probe; empty socket exits 2 before probing, omitted option passes None and preserves public transport selection. | Empty-path case failed before the fix; no real transport, covered separately above. Keep. |

## tests/test_detail_metadata_localization.py

- [ ] `test_detail_metadata_uses_one_localized_safe_contract`
- [ ] `test_detail_metadata_labels_have_english_and_swedish_translations`
- [ ] `test_detail_route_localizes_empty_metadata_and_emits_one_twitter_set`

## tests/test_developer_bp.py

- [ ] `test_developer_app_detail_hides_rate_limits_when_enforcement_disabled`
- [ ] `test_developer_app_detail_shows_actual_rate_limits_when_enforcement_enabled`
- [ ] `test_developer_app_detail_has_clear_permissions_sections`

## tests/test_email_templates.py

- [ ] `test_settings_changed_email_template_renders`
- [ ] `test_demo_cancellation_link_email_explains_verified_vs_reviewed_paths`
- [ ] `test_city_assignment_email_template_renders`
- [ ] `test_city_assignment_escalation_email_template_renders`

## tests/test_error_handlers.py

- [ ] `ErrorHandlerTests::test_handlers_render_expected_templates`

## tests/test_facebook_event_import.py

- [ ] `TestParseEventUrl::test_accepts_full_www_url`
- [ ] `TestParseEventUrl::test_accepts_schemaless_and_mobile_subdomain`
- [ ] `TestParseEventUrl::test_accepts_query_strings_and_trailing_parts`
- [ ] `TestParseEventUrl::test_rejects_empty_input`
- [ ] `TestParseEventUrl::test_rejects_non_event_facebook_url`
- [ ] `TestFetchEvent::test_not_configured_without_token`
- [ ] `TestFetchEvent::test_http_error_mapping`
- [ ] `TestFetchEvent::test_builds_endpoint_and_payload`
- [ ] `TestFetchEvent::test_actor_id_slash_normalized_to_tilde`
- [ ] `TestFetchEvent::test_default_actor_id_uses_tilde`
- [ ] `TestFetchEvent::test_network_error_maps_to_apify_network`
- [ ] `TestFetchEvent::test_non_json_response_maps_to_unexpected_response`
- [ ] `TestFetchEvent::test_empty_or_malformed_results`
- [ ] `TestNormalizeEvent::test_full_public_event_normalization`
- [ ] `TestNormalizeEvent::test_description_is_sanitized`
- [ ] `TestNormalizeEvent::test_unknown_city_is_not_guessed`
- [ ] `TestNormalizeEvent::test_missing_start_stamp_falls_back_to_start_time`
- [ ] `TestNormalizeEvent::test_warnings_for_problematic_events`
- [ ] `TestNormalizeEvent::test_length_caps_apply`
- [ ] `TestNormalizeEvent::test_organizer_falls_back_to_company`
- [ ] `TestNormalizeEvent::test_to_dict_contains_expected_keys`
- [ ] `TestSubmitFacebookImportRoute::test_success_response_shape`
- [ ] `TestSubmitFacebookImportRoute::test_known_error_is_mapped`
- [ ] `TestSubmitFacebookImportRoute::test_invalid_url_error`
- [ ] `TestSubmitFacebookImportRoute::test_unexpected_exception_returns_internal`
- [ ] `TestSubmitFacebookImportRoute::test_missing_url_returns_400`
- [ ] `TestSubmitStampsFacebookProvenance::test_form_submit_stores_facebook_import`
- [ ] `TestSubmitStampsFacebookProvenance::test_form_submit_without_flag_has_no_provenance`
- [ ] `TestSubmitWizardChooser::test_chooser_page_renders_first`
- [ ] `TestSubmitWizardChooser::test_import_section_is_before_title_field`
- [ ] `TestSubmitWizardChooser::test_progress_steps_count_six`

## tests/test_flashing.py

- [ ] `FlashMessageTests::test_flash_message_marks_request_and_maps_success_category`
- [ ] `FlashMessageTests::test_flash_message_falls_back_to_default_category`
- [ ] `FlashMessageTests::test_named_values_are_interpolated_after_translation`

## tests/test_forced_identity_change.py

- [ ] `test_flagged_user_is_redirected_to_identity_change`
- [ ] `test_flagged_user_can_replace_both_names`
- [ ] `test_flagged_user_cannot_choose_reserved_admin_identity`
- [ ] `test_identity_change_stays_forced_if_database_flag_was_cleared`

## tests/test_fresh_step_up_user_deletion.py

- [x] `test_delete_user_without_fresh_step_up_rejected`
- [x] `test_delete_user_with_recent_sudo_session_still_requires_fresh`
- [x] `test_delete_user_with_fresh_webauthn_step_up_succeeds`
- [x] `test_delete_user_with_fresh_password_step_up_succeeds`
- [x] `test_delete_user_fresh_token_cannot_be_reused`
- [x] `test_delete_user_direct_endpoint_without_token_rejected`
- [x] `test_delete_user_without_admin_permission_rejected`
- [x] `test_fresh_step_up_token_expires`
- [x] `test_fresh_step_up_token_bound_to_action_and_target`
- [x] `test_fresh_step_up_token_not_valid_for_other_actions`
- [x] `test_existing_admin_actions_still_use_regular_sudo`
- [x] `test_fresh_step_up_password_requires_totp_when_mfa_enabled`
- [x] `test_fresh_step_up_options_requires_action`
- [x] `test_fresh_step_up_verify_without_options_fails`
- [x] `test_fresh_step_up_options_rejects_unknown_action_and_invalid_target`
- [x] `test_fresh_deletion_token_rejects_another_authorized_actor`
- [x] `test_parallel_fresh_deletion_token_has_one_winner`
- [x] `test_user_delete_modal_supports_real_webauthn_and_password_fallback`
- [x] `test_rendered_user_delete_javascript_parses`

QA-01b / P1, individually reviewed 2026-10-15 by Codex, based on main 9098c02a. Nineteen definitions / 23 parameterized cases; combined with unchanged ordinary step-up tests, 34 cases pass. Isolated test-process mutations dropping expires_at and used predicates each fail the intended expiry/replay HTTP assertions; the subsequent normal 23-case run passes. CodeRabbit CLI completed review of the changed test file with zero findings (not a whole-repository security audit). Real Flask routes, disposable MongoDB, password/TOTP verification and cryptographically signed simulated WebAuthn assertions; external HTTP/mail/upload/screenshot/jobs are isolated by fixtures. Authenticated clients are prepared by `_client_for_user`, not primary-login ceremonies. Simulated authenticator signatures are not physical-device, browser UX or attestation evidence. Production code and #887 policy remain unchanged. Shared fixture/configuration and privacy/erasure semantics remain separate reviews.

| Definition | Requirement / meaningful assertions | Coverage, reliability and limits | Disposition |
|---|---|---|---|
| `test_delete_user_without_fresh_step_up_rejected` | Missing proof gives exact guard error and target remains. | Actual authenticated admin POST, not a mocked guard. Overlaps direct JSON case but remains readable core invariant. | Keep. |
| `test_delete_user_with_recent_sudo_session_still_requires_fresh` | Real recent elevation is true yet deletion without fresh proof is denied and target remains. | Real password step-up; differentiates ordinary sudo from per-deletion ceremony. | Keep; preserves #887. |
| `test_delete_user_with_fresh_webauthn_step_up_succeeds` | Signed fresh ceremony followed by real deletion returns OK and removes the target. | Actual registration/verification; helper creates another same-actor client/key, not browser session-binding evidence. Extra registration setup is redundant but not a verifier mock. | Keep; simplification can be separate. |
| `test_delete_user_with_fresh_password_step_up_succeeds` | Password ceremony mints scoped token and permitted deletion actually removes user. | Real password validation, seeded admin without MFA; does not prove wrong-password or expired ceremony rejection. | Keep positive fallback integration. |
| `test_delete_user_fresh_token_cannot_be_reused` | First use deletes target; same-target replay must hit fresh-proof guard; different-target attempt also denied and second user survives; record is used. | Previously only changed target, allowing target binding to mask broken replay enforcement. Sequential replay, not concurrency proof. | Strengthened same-target assertion; keep. |
| `test_delete_user_direct_endpoint_without_token_rejected` | JSON and form transports both reject missing proof and preserve target. | Two actual POST encodings; JSON overlaps core missing-proof test, form protects separate parsing branch. | Strengthened transport coverage; keep. |
| `test_delete_user_without_admin_permission_rejected` | Regular user with genuine fresh proof is forbidden; target remains and proof is not consumed. | Real account/key; proves lack-of-privilege boundary, not which of multiple admin/permission decorators denied it. | Strengthened state assertions; keep. |
| `test_fresh_step_up_token_expires` | Unused actor/action/target-correct proof works at 59.999s, fails at/after 60s, and records correct consumption/remaining target state; registry stores hash, not raw proof. | Only step-up UTC clock controlled; Mongo millisecond boundary explicit, no sleeps. Old test consumed proof and changed target, never testing time. No DB TTL-index cleanup claim. | Replaced vacuous scenario with three independent boundary cases; keep. |
| `test_fresh_step_up_token_bound_to_action_and_target` | Wrong target denied without consuming proof; intended target then succeeds, ruling out unrelated invalid-proof failure. | Separate existing users, same unexpired proof. Action isolation belongs to next test. | Strengthened positive control; keep. |
| `test_fresh_step_up_token_not_valid_for_other_actions` | Domain-created proof for another action cannot delete; target survives and proof remains unused. | Helper creates unsupported action under authenticated request context to test consume policy, not public issuance allowlist. | Strengthened state assertions; keep. |
| `test_existing_admin_actions_still_use_regular_sudo` | Ordinary elevation still unlocks passkey registration and is reported elevated. | Does not invoke MFA rename despite previous comment; comment narrowed. | Keep narrow compatibility case. |
| `test_fresh_step_up_password_requires_totp_when_mfa_enabled` | Missing TOTP issues no proof; valid real TOTP mints unused actor/action-bound proof. | Real device secret/pyotp; no replay/drift/incorrect-numeric matrix or permission-to-delete claim. | Strengthened registry outcome; keep. |
| `test_fresh_step_up_options_requires_action` | Missing action rejected with invalid_action. | Actual options endpoint; broader malformed JSON/types are not covered here. | Keep. |
| `test_fresh_step_up_verify_without_options_fails` | WebAuthn and correct-password fallback both reject absent ceremony with exact error. | Two endpoints; WebAuthn empty credential is rejected at ceremony prerequisite, not a cryptographic-negative case. | Strengthened password branch; keep. |
| `test_fresh_step_up_options_rejects_unknown_action_and_invalid_target` | Unsupported action and malformed target rejected; invalid options leave no ceremony binding. | New authenticated session, actual parser and request state; does not assess every previously valid-binding replacement scenario. | Strengthened session check; keep. |
| `test_fresh_deletion_token_rejects_another_authorized_actor` | Different admin reaches proof guard but cannot use owner's token; token stays unused and owner subsequently deletes successfully. | Exact guard JSON rules out earlier permission denial; real DB/proof, no actor-verifier mocks. Not stolen-cookie protection. | New actor-binding regression; keep. |
| `test_parallel_fresh_deletion_token_has_one_winner` | Two clients with same actor/proof/target yield exactly one OK deletion and one proof rejection; used timestamp persists. | Barrier before actual Mongo find_one_and_update, two threads, bounded waits, no mocked write result. Both worker outcomes are collected; original request errors take precedence over a peer's broken barrier. One controlled local race, not distributed load testing. | New atomic-consumption regression; keep. |
| `test_user_delete_modal_supports_real_webauthn_and_password_fallback` | Shared template wires decode/assertion functions and password/TOTP controls. | Source-string guard only; function name does not establish real browser interaction. | Keep alongside backend and parse tests; browser ceremony remains pending. |
| `test_rendered_user_delete_javascript_parses` | Actual rendered inline deletion script passes Node syntax check. | Rendering is real; Node absence explicitly skips. Syntax is not focus, visual or interaction proof. | Keep with narrow claim. |

## tests/test_geocode.py

- [ ] `TestGeocodeAddressHelper::test_query_is_sent_through_params_not_raw_url`
- [ ] `TestGeocodeAddressHelper::test_returns_coordinates_from_first_result`
- [ ] `TestGeocodeAddressHelper::test_returns_none_for_empty_results`
- [ ] `TestGeocodeAddressHelper::test_returns_none_when_lat_or_lon_missing`
- [ ] `TestGeocodeAddressHelper::test_returns_none_when_api_errors`
- [ ] `TestGeocodeAddressHelper::test_returns_none_without_making_request_for_missing_city`
- [ ] `TestGeocodeAdminEndpoint::test_returns_coordinates_for_logged_in_admin`
- [ ] `TestGeocodeAdminEndpoint::test_requires_login`
- [ ] `TestGeocodeAdminEndpoint::test_requires_address_and_city`

## tests/test_issue_858_production_errors.py

- [ ] `test_normal_user_does_not_see_admin_navigation`
- [ ] `test_admin_user_sees_admin_navigation`
- [ ] `test_translator_sees_admin_navigation`
- [ ] `test_translation_permission_sees_admin_navigation`
- [ ] `test_developer_requests_accepts_legacy_string_timestamp`
- [ ] `test_developer_requests_remain_server_side_protected`
- [ ] `test_apache_rate_limit_document_is_static_and_preserves_contract`

## tests/test_issue_861_event_detail_hierarchy.py

- [ ] `test_event_overview_labels_are_translated`
- [ ] `test_event_detail_orders_core_information_before_secondary_actions`
- [ ] `test_event_detail_hierarchy_uses_shared_responsive_workspace_styles`
- [ ] `test_event_detail_defaults_to_overview_and_exposes_layout_choice`
- [ ] `test_event_detail_layout_query_sets_scoped_cookie_and_redirects_canonically`
- [ ] `test_invalid_detail_layout_is_ignored_without_overwriting_preference`
- [ ] `test_detail_layout_cache_entries_do_not_cross_variants`
- [ ] `test_event_detail_omits_missing_optional_organizers`
- [ ] `test_long_event_description_expands_across_viewports_and_themes`
- [ ] `test_description_recomputes_when_viewport_width_changes`
- [ ] `test_detail_layout_choice_persists_across_event_pages`

## tests/test_live_http_smoke.py

- [ ] `test_public_pages_render_over_real_http`

## tests/test_manual_content.py

- [ ] `test_manual_updated_content_present`
- [ ] `test_manual_base_has_no_broken_image_refs`
- [ ] `test_manual_base_renders_mobile_toggle`

## tests/test_manual_pages.py

- [ ] `test_manual_pages_render`
- [ ] `test_manual_index_render`
- [ ] `test_manual_requires_login`

## tests/test_measure_http_latency.py

- [ ] `test_main_rejects_non_http_urls`
- [ ] `test_summarize_reports_requested_percentiles`

## tests/test_mfa_settings.py

- [x] `test_mfa_enable_flow_end_to_end`
- [x] `test_mfa_device_rename_requires_step_up_and_updates_name`
- [x] `test_mfa_login_uses_short_lived_server_side_pending_state`
- [x] `test_expired_pending_mfa_login_requires_password_again`
- [x] `test_copied_pending_cookie_cannot_replay_successful_mfa`
- [x] `test_password_change_revokes_pending_first_factor`
- [x] `test_reset_after_mfa_user_load_does_not_call_login_user`
- [x] `test_reset_between_persisted_read_and_atomic_authorization_is_rejected`
- [x] `test_reset_after_consumption_before_session_creation_is_rejected`
- [x] `test_reset_at_session_creation_revokes_the_response_cookie`
- [x] `test_parallel_pending_challenge_consumption_has_one_winner`
- [x] `test_combined_mfa_login_binds_credentials_and_rejects_password_change`
- [x] `test_reset_during_combined_mfa_verification_prevents_login`
- [x] `test_pending_mfa_attempt_limit_cannot_be_reset_by_cookie_replay`
- [x] `test_verify_mfa_route_does_not_500`
- [x] `test_password_login_without_javascript_renders_mfa_step`
- [x] `test_legacy_mfa_flag_does_not_replace_first_factor_proof`

SEC-01 / QA-01 review, 2026-10-12, Codex, P1, PR #901. The old `test_mfa_blocks_login_without_code_and_allows_with_code` used a username absent from its fixture and accepted a broad response range. It was replaced with actual identity/session and challenge assertions; it was not silently dropped.

Shared setup: disposable MongoDB and real Flask test clients/session cookies, actual password hashes and stored MFA devices. External email/network side effects are isolated by `tests/conftest.py`. No mock bypasses challenge persistence, consumption or credential revocation. TOTP uses real time; invalid-code selection excludes the accepted window with a boundary margin. These tests do not prove browser focus/layout or all inactive-account entrypoints (SEC-02).

| Definition | Requirement / assertions | Cases, isolation and limitations | Disposition |
|---|---|---|---|
| `test_mfa_enable_flow_end_to_end` | Issued setup secret only; wrong/unissued code rejected, activation/device state persists, sudo required for removal. | Real API/database state; invalid code strengthened to avoid random valid-code collisions. QR prefix is structural coverage, not scanning compatibility. | Keep; strengthened invalid-code assertion. |
| `test_mfa_device_rename_requires_step_up_and_updates_name` | Forbidden without sudo; valid rename persists; blank/missing/unknown device rejected. | Real client/DB; ownership across two users remains a separate permission-test requirement. | Keep. |
| `test_mfa_login_uses_short_lived_server_side_pending_state` | Cookie contains opaque handle, DB binds actual user, no password/raw password hash stored; completion sets exact identity and clears proof. | Real first-factor and TOTP; markup verifies removed hidden fields but does not execute browser JS. | Keep; strengthened proof assertions. |
| `test_expired_pending_mfa_login_requires_password_again` | Expired DB challenge cannot authenticate and is removed. | Database expiry moved into past; no sleeps or host-clock change. | Keep. |
| `test_copied_pending_cookie_cannot_replay_successful_mfa` | Successful identity established, then saved pre-login cookie fails with a valid code. | Separate Flask clients; proves server revocation independent of response-cookie clearing. | Keep. |
| `test_password_change_revokes_pending_first_factor` | Model password change invalidates pending proof despite valid TOTP; no user session and challenge removed. | Real password change, hash persistence and endpoint. Concurrent interleavings are covered by the four cases below. | Keep. |
| `test_reset_after_mfa_user_load_does_not_call_login_user` | A reset after initial user loading rejects authorization without calling login_user. | Real reset after actual TOTP validation; login_user spy proves no session creation call. | Keep. |
| `test_reset_between_persisted_read_and_atomic_authorization_is_rejected` | Reset winning before the user-record compare-and-set rejects authentication. | Hook schedules real reset at MongoDB update boundary; actual conditional write rejects stale hash. | Keep. |
| `test_reset_after_consumption_before_session_creation_is_rejected` | Reset before final credential read prevents login_user. | Real mutation during proof cleanup; exact empty login-call assertion. | Keep. |
| `test_reset_at_session_creation_revokes_the_response_cookie` | Reset at session creation invalidates protected access; current-password login recovers. | Real cookie/loader; controlled reset after login_user, no cryptographic bypass. | Keep. |
| `test_parallel_pending_challenge_consumption_has_one_winner` | Two simultaneous database consume attempts yield exactly one success. | Separate request contexts, two worker threads and barrier; tests atomic storage invariant, not parallel browser HTTP dispatch. | Keep. |
| `test_combined_mfa_login_binds_credentials_and_rejects_password_change` | Combined password/TOTP login sets the exact credential binding; a later reset blocks protected access. | Real factors, DB password mutation and session loader; exact cookie binding and redirect assertions. | Keep. |
| `test_reset_during_combined_mfa_verification_prevents_login` | Reset after password validation during TOTP verification prevents login_user. | Real TOTP verifier followed by deterministic reset; login_user spy confirms no session creation. | Keep. |
| `test_pending_mfa_attempt_limit_cannot_be_reset_by_cookie_replay` | Saved cookie cannot reset server attempt count; later valid code fails after exhaustion. | Only TOTP rejection mocked during failure phase; real verifier restored before final valid-code assertion. Fresh password verification can intentionally issue new proof. | Keep. |
| `test_verify_mfa_route_does_not_500` | Legacy POST forwards with 307 and preserves existing authenticated identity. | Was a loose non-500 assertion; now checks destination, status and user ID. Anonymous legacy proof is covered separately. | Keep; strengthened. |
| `test_password_login_without_javascript_renders_mfa_step` | Ordinary form POST renders visible MFA step with no password field copy; code then establishes correct session. | Server-rendered requests without browser JavaScript; client rendering/focus remains browser coverage work. | Keep. |
| `test_legacy_mfa_flag_does_not_replace_first_factor_proof` | Legacy boolean flag plus valid code cannot establish anonymous login. | Real anonymous request through forwarded legacy endpoint; exact unauthenticated session assertion. | Keep. |

Validation: focused MFA, username, passkey and fresh-deletion test files run for this PR; final counts and commit evidence are recorded in the PR. The review completion marks assessment of these definitions, not completion of the broader QA-01 programme.

## tests/test_operational_metrics.py

- [ ] `test_percentile_interpolates_and_rejects_invalid_range`
- [ ] `test_summarize_samples_ignores_non_numeric_and_non_finite_values`
- [ ] `test_collect_operational_metrics_uses_bounded_run_sample_and_queue_counts`
- [ ] `test_collect_operational_metrics_uses_effective_oldest_queue_timestamp`

## tests/test_org_logo_referrer_policy.py

- [ ] `test_organization_logo_images_do_not_send_preview_referrers`

## tests/test_org_action_validation.py

- [x] `test_org_action_rejects_malformed_json_or_identifiers`
- [x] `test_invitation_actions_reject_invalid_addresses`
- [x] `test_invite_role_normalizes_input_and_matches_legacy_address`
- [x] `test_organization_editor_cannot_mutate_another_org_invite`
- [x] `test_invite_form_rejects_invalid_object_identifier`
- [x] `test_membership_delete_requires_resolved_target_organization`

SEC-03 / QA-01 review, 2026-10-12, Codex, P1; actual Flask endpoints, roles, membership grants and disposable MongoDB. External delivery is isolated by existing fixtures; no permission/DB-write mock. Unique actor/target IDs prevent parametrized identity collisions. Error/audit assertions do not claim the full canonical audit/redaction programme is complete.

| Definition | Requirement / assertions | Cases and limits | Disposition |
|---|---|---|---|
| `test_org_action_rejects_malformed_json_or_identifiers` | Invalid payloads return JSON 400 rather than reaching unsafe ObjectId conversion. | Five APIs × list/string/invalid-ID payloads, exact status and error envelope. Empty/malformed JSON syntax uses same validator but not separately parameterized. | Keep. |
| `test_invitation_actions_reject_invalid_addresses` | Invalid or non-string email rejected before invite handling. | Three invite APIs × malformed/list/header-shaped address. Valid delivery integration not part of this test. | Keep. |
| `test_invite_role_normalizes_input_and_matches_legacy_address` | Mixed-case legacy invite updated without duplication, then cancelled. | Actual legacy string → canonical dict and persisted empty list; valid role member used. Other role policies remain #550. | Keep. |
| `test_organization_editor_cannot_mutate_another_org_invite` | Own-org rights do not authorize foreign owner invitation. | Real unrelated verified organization, exact 403 and unchanged invitations. | Keep. |
| `test_invite_form_rejects_invalid_object_identifier` | Browser form identifier checked before BSON conversion. | Exact 400; HTTP redirect/success rendering unaffected. | Keep. |
| `test_membership_delete_requires_resolved_target_organization` | Deletion only succeeds for authorized resolved organization. | Own, foreign, orphan and malformed stored ID; exact status and record existence. Revealed broad edit helper bypass, which was corrected. Owner-transfer/last-owner policy and concurrent permissions changes need separate acceptance. | Keep. |

Final focused run/revision evidence is recorded in the delivery PR. Review completion marks these definitions assessed; organization role lifecycle, destructive confirmations and audit architecture remain open.

## tests/test_organization_orphan_members.py

- [x] `test_organization_detail_renders_with_missing_member`
- [x] `test_organization_preserves_valid_members_and_permissions`
- [x] `test_organization_with_only_orphan_members_renders_empty_members`
- [x] `test_organization_does_not_suppress_other_user_loading_errors`
- [x] `test_public_organization_does_not_load_member_users`
- [x] `test_members_batch_loading_cache_and_serialization`
- [x] `test_admin_organization_view_uses_safe_batched_members`

Organization HTTP 500 regression review, 2026-10-13. Disposable database and real Flask/model lookups; no production records are changed. Four request variants reproduced the same missing-user exception before the fix. Seven new cases and 51 existing organization/deletion cases passed afterward (58 total); final commit and PR identify the delivery revision.

Member-loading follow-up: 69 focused cases passed, including 2/27-member query-count variants, public/admin rendering, organization mutations and fresh-step-up deletion tests. Full suite not run. The originally injected loader failure is now injected at batch deserialization and asserted on first member access.

| Definition | Requirement / assertions | Fixtures, coverage and limits | Disposition |
|---|---|---|---|
| `test_organization_detail_renders_with_missing_member` | Real detail GET returns 200 with organization content; no missing user invented or stored membership deleted. | ObjectId/string references × anonymous/authenticated clients; four real database/render cases. Not a production or all-browser check. | Keep. |
| `test_organization_preserves_valid_members_and_permissions` | Valid members retain roles/permissions, missing member gets no membership/access, refresh is idempotent and user records remain unchanged. | Real seeded users plus one orphan; exact member IDs and stored-user equality. Does not audit every permission policy. | Keep. |
| `test_organization_with_only_orphan_members_renders_empty_members` | No valid members is a supported empty state and still renders 200. | Separate synthetic organization, two missing users; both stored memberships remain. | Keep. |
| `test_organization_does_not_suppress_other_user_loading_errors` | Unrelated user-deserialization errors still propagate rather than disappearing as missing users. | One injected ValueError, narrowly scoped to the loader. Does not prove every upstream exception type. | Keep. |
| `test_public_organization_does_not_load_member_users` | Anonymous public GET renders without invoking the member loader. | Real Flask GET; loader raises immediately if used. Authenticated permission lookups are intentionally outside this query-free contract. | Keep. |
| `test_members_batch_loading_cache_and_serialization` | Construction/serialization are lazy, one user query hydrates members, repeated access is cached, explicit refresh re-queries, and saving excludes cached users. Approved review follow-up retains the same list object through refresh, update_member and add_member; retained aliases observe changed roles/persisted permissions and the new member. | Real database with 2/27 valid users plus a string orphan; collection-level find instrumentation and forbidden per-user loader. Checks actual IDs, unchanged input and persisted fields. Existing permission-merge policy is preserved, not redefined. Counts application queries, not cursor getMore/network packets. | Keep. |
| `test_admin_organization_view_uses_safe_batched_members` | Admin view renders despite a missing user and preserves membership IDs required by row actions. | Real authenticated route and persisted membership identities; separate action tests cover authorization. | Keep. |

## tests/test_organization_fill_page.py

- [ ] `test_organization_fill_page_uses_public_org_visual_shell`
- [ ] `test_organization_fill_submission_stores_logo_suggestion`
- [ ] `test_admin_can_apply_logo_suggestion`

## tests/test_passkey_counter_concurrency.py

- [x] `test_distinct_challenges_cannot_overwrite_newer_credential_counter`
- [x] `test_deleted_passkey_cannot_complete_previously_verified_login`

QA-01h / SEC-05 · P1 · Codex · 2026-10-19 · main3c8665ab. Two individually assessed definitions /five cases. Real Flask sessions, independent challenges, ES256 signatures and disposable MongoDB. Imported registration/app fixtures exercise actual password step-up and credential registration. Four failures reproduced before the conditional-write fix; the counterless positive control passed. Combined passkey/lifecycle/fresh-deletion validation passed56 cases. Local five-file review completed with two overlapping Minor reports of the same empty duplicate inventory heading, corrected afterward. No code findings reported; not a zero-finding review claim. No physical authenticator, browser ceremony or process-crash acceptance claim.

| Definition | Requirement and assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_distinct_challenges_cannot_overwrite_newer_credential_counter` | With distinct consumed challenges, stale positive-counter state cannot authenticate or replace newer counter; both genuine counterless logins remain valid. Checks each HTTP outcome, session identity, challenge consumption and final counter. | Four ordered real-write variants:2→1,1→1,1→2 and0→0. Barrier delegates actual crypto verification against observed0; Event orders actual DB updates, no sleeps/fabricated results. Conservative CAS rejects the stale higher-counter request too; retry needs fresh challenge. Not same-challenge replay or arbitrary multi-process/device coverage. | Keep; three stale-state failures reproduced on old code, counterless control passed. |
| `test_deleted_passkey_cannot_complete_previously_verified_login` | Removing credential before final write yields403, no authenticated session, no revived credential; challenge remains consumed. | Actual route/crypto/DB deletion at update boundary, not mocked verifier success. Does not prove deletion after successful commit invalidates an already authenticated session. | Keep; pre-fix route returned200 with missing credential. |

## tests/test_passkey_challenge_lifecycle.py

- [x] `test_login_challenge_expires_at_exact_server_deadline`
- [x] `test_challenge_purpose_is_independent_of_user_binding`
- [x] `test_simultaneous_counterless_login_has_one_challenge_winner`

QA-01g · P1 · Codex · 2026-10-19 · base #943 (`635247c9`) on main `e6383141`. Three definitions /ten cases. Imported `wapp` provides the existing localhost RP/origin app with cleanup. The `registered_key` fixture uses actual password step-up, registration options, ES256 signing and registration verification; no crypto/authorization outcomes are mocked. Real disposable MongoDB is used. Collection wrappers synchronize or fault-inject only the specific challenged write; normal assertions inspect actual records/sessions. Individual initial focused run: ten passed; final run/review evidence belongs in the delivery PR. No production authentication or #887 policy changes.

| Definition | Requirement / assertions | Cases, setup, reliability and limits | Disposition |
|---|---|---|---|
| `test_login_challenge_expires_at_exact_server_deadline` | Generated expiry is exactly300s after issuance. Signed counterless HTTP assertion succeeds at299s, fails at300s and301s; exact authenticated identity or absent identity, consumed state and unchanged credential after denial. | Three cases change only webauthn helper clock. Future2099 timestamps keep the real Mongo TTL monitor from asynchronously removing the row while simulated expiry is tested. Does not test TTL cleanup, clock-skewed hosts, registration or step-up HTTP expiry. | Keep; isolates strict server expiry independently of signature/counter/replay failures. |
| `test_challenge_purpose_is_independent_of_user_binding` | Both wrong purpose values fail without changing the complete stored challenge; original purpose succeeds afterward. | Three purposes × bound/unbound user, same request session and valid expiry. Direct helper contract rather than endpoint end-to-end: deliberately holds user/session binding fixed, including combinations not issued by current routes, so another predicate cannot mask missing purpose filtering. No sleeps or remote calls. | Keep; isolates purpose predicate, with an exact valid control. |
| `test_simultaneous_counterless_login_has_one_challenge_winner` | Same valid signed assertion produces exactly one200 with expected owner identity and one403 with no identity; stored challenge is used and counter remains0. | Two independent Flask clients share the initial challenge-session cookie, synchronized at the actual Mongo find-and-update boundary with a bounded barrier/future wait. Counter0 prevents anti-clone counter handling from masking double consumption. Real crypto/write outcomes; no response mocks or sleep-based timing. Does not prove concurrent distinct-challenge sign-counter monotonicity or replica-set failover. | Keep; verifies one-winner atomic consume, complementary to #943's sequential replay and foreign-session tests. |

Validation: all71 combined lifecycle/passkey/step-up/fresh-deletion/account-access cases pass. Isolated in-process mutations removed only expiry, purpose or used-state filtering from the real database write: both expired HTTP cases authenticated incorrectly, all six wrong-purpose cases consumed incorrectly, and both concurrent clients authenticated. All nine targeted assertions failed as intended; the299s valid control still passed. No tracked source edits were made for mutations. Exact AST/checklist set comparison reports no missing/extra entries: 1,169 definitions /160 files /264 assessed. These results are not whole-suite, browser/hardware or production acceptance.

## tests/test_passkeys_webauthn.py

- [x] `test_passkey_register_and_login_end_to_end`
- [x] `test_passkey_login_verifies_the_assertion_bound_challenge`
- [x] `test_passkey_registration_requires_step_up`
- [x] `test_passkey_register_verify_without_pending_challenge_rejected`
- [x] `test_passkey_rejects_unknown_credential_at_login`
- [x] `test_passkey_login_requires_confirmed_account`
- [x] `test_login_options_respect_username_scope`
- [x] `test_passkey_duplicate_registration_rejected`
- [x] `test_passkey_list_rename_delete`
- [x] `test_passkeys_are_isolated_between_users`
- [x] `test_passkey_rejects_disabled_accounts`

SEC-02 / QA-01 review, 2026-10-12, Codex, P1. The old `test_banned_and_inactive_users_can_log_in_with_passkey_bodies` accepted either 200 or 403 and never proved denial. Replaced with two exact-denial parameter cases and absent-session assertions.

Shared setup: simulated hardware authenticator signs real registration/assertion bodies; actual WebAuthn crypto verifier, localhost RP/origin, disposable MongoDB, real password step-up. Browser/physical hardware compatibility is not proven. Shared database identity uniqueness matters: disabled-account parameter cases now use unique usernames/emails after an initial duplicate-key failure. Each test has a fresh Flask client and stored challenge; fixtures stop app resources.

| Definition | Requirement / assertions | Cases and remaining coverage limitations | Disposition |
|---|---|---|---|
| `test_passkey_register_and_login_end_to_end` | Registration persists credential/name, excludes duplicate, anonymous valid assertion authenticates and increments counter. | Exact API/storage checks; a browser device chooser is outside scope. | Keep. |
| `test_passkey_login_verifies_the_assertion_bound_challenge` | Earlier signed challenge remains usable after second options request. | Distinct challenges; selected one consumed, other untouched. Same client sequential requests, not threaded HTTP. | Keep. |
| `test_passkey_registration_requires_step_up` | Registration options forbidden without elevation. | Exact 403/error; verify endpoint's elevation covered elsewhere. | Keep. |
| `test_passkey_register_verify_without_pending_challenge_rejected` | Used challenge cannot register credentials. | Actual signed body after used-state mutation; explicitly checks rejection. Expiry is separate coverage. | Keep. |
| `test_passkey_rejects_unknown_credential_at_login` | Unknown credential rejected. | Signed assertion with nonexistent ID, 403 and absent user ID. | Keep; strengthened session assertion. |
| `test_passkey_login_requires_confirmed_account` | Unconfirmed account denied despite valid key. | Real registration fixture; 403/reason and absent user ID; active remains true to isolate confirmation. | Keep; strengthened session assertion. |
| `test_login_options_respect_username_scope` | Known username options contain corresponding credential; unknown has no explicit list. | Preserves discoverable-key fallback, not username enumeration resistance. | Keep. |
| `test_passkey_duplicate_registration_rejected` | Reused credential ID rejected. | Fresh challenge and valid crypto; exact 400/localized reason. | Keep. |
| `test_passkey_list_rename_delete` | List reflects own key, rename requires sudo, normalization persists, unknown deletion fails and real deletion removes row. | Real DB; valid-sudo delete covered, non-sudo delete belongs to step-up tests. | Keep. |
| `test_passkeys_are_isolated_between_users` | Another user's list is empty; anonymous step-up leads to login. | Does not prove forged cross-user rename/delete denial; record as remaining QA-01 ownership gap. | Keep; schedule scoped mutation tests. |
| `test_passkey_rejects_disabled_accounts` | Valid assertion denied after account disabled, no user session created. | Active=false and banned=true separately; registers while enabled, then DB status update; unique identities prevent fixture collisions. | Keep; strengthened old weak test. |

Focused run evidence is linked in the delivery PR; checked entries mean assessed definitions, not closure of all WebAuthn security requirements. The following QA-01f batch closes the named cross-user mutation, signed origin/RP mismatch and sequential consumed-assertion gaps; concurrent counter updates and physical authenticator/browser acceptance remain separate requirements.

- [x] `test_elevated_passkey_mutations_are_owner_scoped`
- [x] `test_signed_passkey_assertion_rejects_wrong_relying_party`
- [x] `test_passkey_login_challenge_cannot_cross_browser_sessions`
- [x] `test_consumed_passkey_assertion_cannot_authenticate_again`

QA-01f · P1 · Codex · 2026-10-19 · base `e6383141`. These four definitions add six real HTTP/MongoDB/cryptographic cases, without mocking permission or verifier outcomes. The existing simulated ES256 authenticator signs the complete assertion, including the deliberately mismatched origin or RP hash. All eighteen passkey cases pass; final combined run/review evidence is recorded in the delivery PR. A separate test process replaced only the two ownership-scoped helpers with unscoped real database writes: both cases then failed specifically at expected404 versus actual200, demonstrating detection of the intended regression. No tracked production source was modified for that experiment. No production authentication policy or #887 changes.

| Definition | Requirement / assertions | Setup, variants, reliability and limits | Disposition |
|---|---|---|---|
| `test_elevated_passkey_mutations_are_owner_scoped` | An elevated foreign account gets404/error for both rename and delete; the entire target credential stays byte-for-value unchanged. The same elevated owner operation then succeeds with exact changed name or deleted document. | Registers a real credential; both clients pass actual password step-up, so missing elevation cannot mask missing ownership enforcement. Existing list isolation remains. Mutation of only the ownership predicates is checked separately; no production requests. | Keep; closes the earlier review's forged cross-user mutation gap. |
| `test_signed_passkey_assertion_rejects_wrong_relying_party` | Wrong origin and wrong RP hash independently produce403 with the crypto-verification error, no user session or credential changes; attempted challenge is consumed. Fresh correct assertion with the same key/counter then authenticates the exact owner. | Two variants signed with the real private key; not invalid-signature/missing-challenge failures. Fresh valid control avoids an always-denying verifier passing the negative cases. Does not cover registration origin policy or every supported origin configuration. | Keep; verifies actual py-webauthn RP/origin boundaries. |
| `test_passkey_login_challenge_cannot_cross_browser_sessions` | A valid assertion used from another browser session fails without consuming the original challenge or updating the credential. The originating client can still authenticate with that exact assertion. | Independent Flask clients, same signed body; asserts no foreign login session. No mocked challenge storage, time or authorization. Not a concurrent race test. | Keep; isolates browser-session binding from signature/counter validity. |
| `test_consumed_passkey_assertion_cannot_authenticate_again` | First assertion succeeds as the exact owner; identical replay fails with challenge error, absent login identity and exact unchanged credential. | Zero counter intentionally permits counterless authenticators, so counter enforcement cannot hide missing single-use consumption. Removes only authenticated user ID from the signed test session while preserving challenge binding: a test-only isolation step, not proof of real logout cleanup (covered separately). Sequential replay, not atomic two-client concurrency. | Keep; proves used-challenge enforcement independently of session rotation and sign count. |

Additional in-process mutations separately relaxed only expected origin/RP, challenge session binding or used-state filtering. All four corresponding cases failed specifically at expected403 versus actual200. These experiments retained real signatures and Mongo writes and left no tracked source changes. Normal combined passkey/step-up/fresh-deletion/account-access validation passed 61 cases. Exact AST-to-checklist comparison has no missing/extra entries (1,166 definitions /159 files /261 checked). This is not a full-suite, all-authentication, production or browser/hardware acceptance claim.

## tests/test_privileged_user_actions.py

- [x] `test_full_permission_actor_can_assign_global_role_with_legacy_base_role`
- [x] `test_clearance_check_enforces_target_hierarchy`
- [x] `test_clearance_routes_require_global_not_membership_permission`
- [x] `test_clearance_write_requires_global_permission_even_with_valid_csrf`
- [x] `test_direct_user_edit_cannot_change_higher_role_target`
- [x] `test_admin_cannot_self_promote_through_either_entrypoint`
- [x] `test_restricted_editor_cannot_delegate_unowned_global_permission`
- [x] `test_restricted_editor_cannot_edit_globally_privileged_legacy_user`
- [x] `test_organization_admin_role_does_not_grant_global_user_management`
- [x] `test_force_password_change_respects_target_hierarchy`
- [x] `test_ordinary_target_profile_edit_still_works`
- [x] `test_admin_can_edit_own_basic_profile_without_changing_authority`
- [x] `test_hard_coded_identity_has_no_hierarchy_exception`
- [x] `test_admin_user_audit_excludes_credentials_and_request_payload`
- [x] `test_create_user_cannot_bypass_superuser_promotion_process`

SEC-03 / QA-01 review, 2026-10-12, Codex, P1 review batch; corrected privilege-escalation paths are P0 code defects. Real Flask/DB/roles/grants with no authorization mocks. Synthetic payload marker is not a real credential; assertions inspect scoped audit events, not the whole service logging system. Final run and revision recorded in PR.

| Definition | Requirement / assertions | Variants and remaining limits | Disposition |
|---|---|---|---|
| `test_full_permission_actor_can_assign_global_role_with_legacy_base_role` | Full-authority legacy base role accepts a valid global-role assignment. | Direct helper with explicit SimpleNamespace capabilities; clearance and persisted promotion covered separately. | Keep; reviewed 2026-10-13. |
| `test_clearance_check_enforces_target_hierarchy` | Legacy clearance GET allows a lower target; denies self, peer and higher; missing/invalid IDs return 404. | Six real Flask/DB cases, no authorization mocks. Does not cover concurrent role changes. | Keep; reviewed 2026-10-13, #919 focused run. |
| `test_clearance_routes_require_global_not_membership_permission` | Board read/list/legacy UI and governance clearance page require global authority, not an organization grant. | Eight real membership-vs-global cases, exact 403/200/redirect outcomes; same base role isolates permission scope. | Keep; reviewed 2026-10-13, #919 focused run. |
| `test_clearance_write_requires_global_permission_even_with_valid_csrf` | A valid CSRF token cannot turn an organization permission into global write authority. | Two real POST cases; exact status and persisted approval presence/absence. Existing governance tests retain missing-CSRF coverage. | Keep; reviewed 2026-10-13, #919 focused run. |
| `test_direct_user_edit_cannot_change_higher_role_target` | Both edit and save deny higher-level target with no DB change. | Two entrypoints, exact 403 and full stored-document equality. | Keep. |
| `test_admin_cannot_self_promote_through_either_entrypoint` | Direct own-role God promotion rejected. | Both routes; real ObjectId/string distinction; stored state unchanged. | Keep. |
| `test_restricted_editor_cannot_delegate_unowned_global_permission` | Explicit EDIT_USER does not authorize granting DELETE_USER. | Real restricted actor and target, exact denial/state equality. | Keep. |
| `test_restricted_editor_cannot_edit_globally_privileged_legacy_user` | Low base-role user with global_admin flag still protected. | Real flag/role mismatch; separate from named God-role test. | Keep. |
| `test_organization_admin_role_does_not_grant_global_user_management` | Organization rights do not grant list/save/forced-reset/clearance global authority. | Four route checks; actual org membership and no global capability. | Keep. |
| `test_force_password_change_respects_target_hierarchy` | Self, peer and higher target forcing denied. | Three cases with unchanged DB flag. Lower target success exercised by audit test. | Keep. |
| `test_ordinary_target_profile_edit_still_works` | Authorized ordinary profile update persists. | Positive save POST/display name; full-field round-trip remains form tests. | Keep. |
| `test_admin_can_edit_own_basic_profile_without_changing_authority` | Own basic profile may change without a role/rights change. | Valid public username isolates authority checks from reserved-name validation; exact role/permission preservation. | Keep. |
| `test_hard_coded_identity_has_no_hierarchy_exception` | Former exception ID gains no authority and target role is not mutated. | Direct helper test, not a production identity query. | Keep. |
| `test_admin_user_audit_excludes_credentials_and_request_payload` | Actual forced reset works; synthetic secrets excluded in both audit layers; admin actor filter retrieves request events. | Real DB writes and actual `_build_logs_query` actor predicate; does not prove all audit sources/retention/redaction. | Keep; strengthened 2026-10-13. |
| `test_create_user_cannot_bypass_superuser_promotion_process` | Hidden God role/early global-admin creation rejected without persistence. | Two roles with exact expected status, existing UI notice and clearance promotion flow preserved. | Keep. |

Known remaining acceptance: dedicated full-role alias cases, concurrent authorization changes, invalid-ID matrices for every legacy form route and cross-source audit completeness. Those are not silently declared covered.

## tests/test_privacy_policy.py

- [ ] `test_privacy_policy_discloses_current_personal_data_processing`

## tests/test_process_email_queue.py

- [ ] `test_process_email_queue_rebinds_sender_to_active_database`
- [ ] `test_process_email_queue_drains_orphaned_jobs_regardless_of_instance`
- [ ] `test_process_email_queue_keeps_failed_job_for_retry`
- [ ] `test_process_email_queue_retries_failed_job_on_later_run`
- [ ] `test_process_email_queue_is_idempotent_on_empty_queue`
- [ ] `test_process_email_queue_records_delivery_status_on_case`
- [ ] `test_process_email_queue_records_failure_status_on_case`
- [ ] `test_process_email_queue_reopens_exhausted_legacy_ticket_job`
- [ ] `test_process_email_queue_does_not_reopen_real_sender_exhausted_jobs`
- [ ] `test_process_email_queue_redacts_recipients_in_delivery_errors`

## tests/test_product_design_tokens.py

- [ ] `test_public_and_admin_shells_load_product_tokens_before_components`
- [ ] `test_product_tokens_cover_shared_semantic_roles`
- [ ] `test_public_components_do_not_depend_on_admin_scoped_tokens`
- [ ] `test_admin_component_api_aliases_the_product_foundation`

## tests/test_profile_follow_lists.py

- [ ] `test_profile_follow_counts_open_public_user_lists`

## tests/test_public_accessibility_contracts.py

- [x] `test_public_shell_has_language_and_semantic_footer_lists`
- [x] `test_city_today_page_has_a_document_language`
- [x] `test_public_chat_feedback_uses_safe_shared_toast`
- [x] `test_api_documentation_code_blocks_are_focusable_and_links_are_distinct`

UI-01 / QA-04 supporting review, 2026-10-12, Codex, P1. Anonymous real Flask responses and source-string checks are wiring evidence, not complete accessibility/security acceptance. Existing external-service isolation remains in the common fixture; no mocked UI rendering or permission result.

| Definition | Purpose / assertions | Fixtures / coverage / reliability | Disposition |
|---|---|---|---|
| `test_public_shell_has_language_and_semantic_footer_lists` | Nonempty HTML language and intended footer/nav/list wiring; obsolete separator/inline auth markup absent. | Real submit GET, exact strings/regex. Does not prove complete DOM validity or footer viewport fit. | Keep with narrow claim. |
| `test_city_today_page_has_a_document_language` | Empty stored locale still renders Finnish document language. | Explicit test-session locale, real city/today response, exact lang attribute. Other locale fallback variants remain locale tests. | Keep. |
| `test_public_chat_feedback_uses_safe_shared_toast` | Chat uses shared toast; text assignment, no innerHTML/native alert, status/live hooks remain. | Static JS/template reads only, not execution of stored chat data or actual screen-reader behavior. | Keep as guard; runtime sink coverage separate. |
| `test_api_documentation_code_blocks_are_focusable_and_links_are_distinct` | Code pre blocks are tabbable; scoped focus/link tokens remain. | Real docs GET plus CSS strings. Does not prove computed contrast, keyboard behavior or every link. | Keep; broaden behavior in later QA-04. |

## tests/test_public_calendar_theme_contract.py

- [ ] `test_active_month_calendars_share_cache_keyed_static_styles`
- [ ] `test_calendar_styles_are_scoped_and_use_product_tokens`
- [ ] `test_calendar_focus_ring_meets_non_text_contrast_in_both_themes`
- [ ] `test_current_mobile_description_is_revealed_only_when_present`
- [ ] `test_legacy_view_switch_initializes_without_jquery`

## tests/test_public_chrome_contract.py

- [ ] `test_api_docs_uses_shared_page_chrome_without_template_css`
- [ ] `test_public_footer_has_one_semantic_shared_structure`
- [ ] `test_public_chrome_css_uses_product_tokens_and_namespaced_components`
- [ ] `test_public_header_uses_shared_scoped_component_css`
- [ ] `test_mobile_navigation_owns_accessibility_state_without_inline_handlers`
- [ ] `test_public_chrome_labels_are_translated`
- [ ] `test_api_docs_chrome_is_theme_aware_and_portrait_safe`
- [ ] `test_public_header_mobile_menu_and_theme_contract`
- [ ] `test_public_navigation_remains_available_without_javascript`

## tests/test_public_pagination_limits.py

- [x] `test_public_page_size_is_bounded_and_existing_defaults_survive`
- [x] `test_demo_apis_cap_the_real_query_and_return_bounded_metadata`
- [x] `test_tag_page_materializes_only_the_bounded_page`
- [x] `test_public_organization_api_cannot_bypass_page_size_limit`
- [x] `test_enormous_out_of_range_pages_never_reach_database_skip`
- [x] `test_public_cache_normalizes_page_sizes_and_excludes_old_unbounded_namespace`
- [x] `test_old_oversized_cached_response_cannot_bypass_the_new_limit`

DATA-01a / QA-02, P1; reviewed 2026-10-13 by Codex. Disposable local database and real Flask queries only; no production stress request. Together with existing public API/history/analytics coverage, 92 focused cases passed. These tests establish response/query bounds, not rate limiting or bounded browser memory.

| Definition | Requirement / assertions | Fixtures, variants and limitations | Disposition |
|---|---|---|---|
| `test_public_page_size_is_bounded_and_existing_defaults_survive` | Maximum 100, minimum 1, malformed/default handling preserved. | Nine raw variants; direct shared parser, tag default 10. | Keep; fails without the cap. |
| `test_demo_apis_cap_the_real_query_and_return_bounded_metadata` | Both APIs return 100 then 5 records with exact counts/ranges and no overlap. | 105 uniquely tagged real records; modern next URL carries bounded size. No production query-plan measurement. | Keep. |
| `test_tag_page_materializes_only_the_bounded_page` | HTML tag context contains only 100 records and two pages. | Actual render signal, disconnected in finally; does not assess visual layout. | Keep. |
| `test_public_organization_api_cannot_bypass_page_size_limit` | Organization endpoint applies the same bound, including last page. | 105 uniquely searchable local records; real database query. | Keep. |
| `test_enormous_out_of_range_pages_never_reach_database_skip` | Four endpoint variants return empty results without huge Mongo offsets. | Cursor skip wrapper raises rather than mocking returned records; 100-digit page. Count cost remains outside this guarantee. | Keep. |
| `test_public_cache_normalizes_page_sizes_and_excludes_old_unbounded_namespace` | Excessive and bounded query sizes share the new cache key; different resolved languages do not. | Real request contexts, no explicit URL language; exact new namespace. Strengthened for approved #927 review correction on 2026-10-13. | Keep. |
| `test_old_oversized_cached_response_cannot_bypass_the_new_limit` | Pre-fix cache cannot bypass handler bounds; new stored payload is bounded. A session-language change reaches a distinct route cache key without changing the URL. | Synthetic legacy cache marker, real database, handler and session locale selector. Does not prove a live Redis deployment. | Keep. |

## tests/test_public_cropper.py

- [x] `test_cropper_uses_shared_dialog_and_pinned_existing_engine`
- [x] `test_cropper_preserves_native_upload_without_file_transfer_support`
- [x] `test_actual_cropper_has_modal_focus_keyboard_geometry_and_real_upload`
- [x] `test_cropper_export_uses_source_resolution_and_bounded_zoom`
- [x] `test_cropper_locales_reopen_and_cancel_are_consistent`
- [x] `test_cropper_cancel_during_async_apply_cannot_commit_stale_file`
- [x] `test_cropper_decode_and_apply_failures_are_visible_and_recoverable`
- [x] `test_cropper_restores_committed_file_and_preview_together`

UI-01 / QA-04 review, 2026-10-13, Codex, P1. Real browser, actual shared Jinja include/CSS/controller, local pinned existing Cropper 2.1.0 runtime and synthetic 800×450 PNG. Harness isolates the dialog from unrelated wizard integrations; no whole-submission acceptance claim. No authorization or image-engine mocks in positive crop cases. Error/race tests replace only the selection canvas promise to create deterministic adverse conditions.

Integration review follow-up, 2026-10-18: `test_cropper_preserves_native_upload_without_file_transfer_support` is individually assessed across missing DataTransfer, missing File, throwing files setter and ignored files assignment. A real browser uploads image bytes through the native input and FormData; exact name/type/size/SHA-256 survive, the enhancement stays inactive, and no page errors occur. These four feature-injection cases do not certify every legacy browser. The two pending-crop cancellation tests now instrument and await settlement of the actual registered async apply handler, rather than assuming one zero-delay timer proves no stale commit; no production test hook or arbitrary delay is added.

| Definition | Requirement / assertions | Coverage, reliability and limits | Disposition |
|---|---|---|---|
| `test_cropper_uses_shared_dialog_and_pinned_existing_engine` | Named native dialog/help/keyboard contract, no inline palette or image-data innerHTML, preserved global hooks and exact vendor hash. | Source/provenance guard only, not runtime/security proof of every vendor method. | Keep alongside runtime cases. |
| `test_actual_cropper_has_modal_focus_keyboard_geometry_and_real_upload` | Inert background, internal Tab loop, ArrowRight movement, theme-safe modal/action colors and bounded geometry; actual exported file has original name/type, positive dimensions and 16:9 ratio; preview commits and focus returns. | Four light/dark × desktop/390px cases, real engine and image bytes, no page errors; screenshots inspected. Not full wizard, all browsers, pointer/touch-drag or complete contrast audit. | Keep. |
| `test_cropper_export_uses_source_resolution_and_bounded_zoom` | A 1600×900 source exports at least 1200px wide at initial crop in both viewport sizes; uniform zoom-in reduces sampled source area; zoom-out cannot exceed native width/height; aspect remains 16:9. | Six actual-engine desktop/390px × normal/in/out zoom cases; generated real PNG and decoded exported file, not mocked canvas. Five cases failed before correction (mobile initial output only 260px wide). Does not assert arbitrary rotation/skew or every source format/pixel-color mapping. | New P1 source-resolution regression; keep. |
| `test_cropper_locales_reopen_and_cancel_are_consistent` | FI/EN/SV titles/actions, three clean reopens and Escape/button/backdrop cancellation, file clearing, engine/container cleanup and focus return. | Three locale cases with actual catalogs/engine; no sleeps. Label checks do not assert every translated help/error string visually. | Keep. |
| `test_cropper_cancel_during_async_apply_cannot_commit_stale_file` | Cancelling a pending canvas promise cannot replace file/preview; next image opens normally. | Deterministic promise injection into real selection; no timer race used for ordering. Does not cover every file decode/import/blob-stage interleaving. | Keep. |
| `test_cropper_decode_and_apply_failures_are_visible_and_recoverable` | Corrupt image gives live error/disabled apply; after cancel valid image works; canvas failure shows an error, enables retry, clears the uncommitted file and leaves the preview hidden. | Actual failed decode plus one synthetic canvas rejection with no prior accepted crop. This test does not establish restoration of a previously accepted pair; the 24-case replacement test below does. Import/network/browser-unsupported matrices remain follow-up. | Keep with explicit scope. |

Historical checkpoint, 2026-10-15 at 92b4bb54: 26 cases passed across cropper, inline-style, CSS-integrity and product-token checks; six definitions accounted for sixteen cropper cases. JS syntax/diff checks passed. Those cancellation/error tests had no prior accepted crop and did not prove restoration of a previously accepted file/preview pair. That specific gap is covered by the approved 2026-10-16 follow-up below. This slice does not close UI-01's broader assistive-technology, touch/all-browser or submission integration requirements.

2026-10-16 approved replacement-crop follow-up: the user approved the file/preview restoration fix, the coverage clarification and the validated push to #929. The current failure-test row and historical checkpoint above now distinguish empty-state failures from accepted-pair restoration. Its new definition is individually assessed below.

| Definition | Requirement / assertions | Coverage, reliability and limits | Disposition |
|---|---|---|---|
| `test_cropper_restores_committed_file_and_preview_together` | Replacement cancel/error restores the exact accepted file name/type/size/SHA-256 and preview-source SHA-256/visibility together; no accepted crop leaves both empty. Button, Escape, backdrop, real decode failure, canvas rejection and cancellation during pending canvas all preserve the expected pair and focus return. | 24 cases: committed/empty × desktop/390px × six exit paths. Actual pinned engine and valid image bytes; only adverse canvas promises are injected. Corrupt bytes exercise actual decode. Per-page immutable state snapshots, no timer-based race order. Does not establish whole-wizard draft/import/removal/reset behavior, every async import/blob stage, Safari/Firefox or physical touch interaction. | Two committed/button cases fail on current #929 head before fix, then all 24 pass; keep. |

Current approved behavior also changes the existing failure-test assertion: an uncommitted original is cleared rather than retained. Existing recovery control/enabled/error assertions remain; older checkpoint descriptions above are not a claim that uncommitted bytes are retained by this follow-up. All 40 cropper cases pass, including the prior six-definition/source-resolution matrix; combined with inline/CSS/product-token checks, 50 pass. JS/Jinja syntax, diff and exact AST membership pass. A local CodeRabbit Minor about contradictory roadmap approval status was corrected; final six-file review completed with zero findings before this evidence-text addition. The controller keeps only the latest committed file/preview pair; async generation guards still reject stale completions. JS cache version is bumped; CSS, routes, field names and vendor bytes are unchanged.

## tests/test_public_city_autocomplete.py

- [x] `test_city_combobox_keyboard_selection_preserves_route_contract`
- [x] `test_city_combobox_treats_html_and_regex_as_plain_text_and_bounds_options`

UI-01 / QA-04, P1; reviewed 2026-10-15 by Codex. Two definitions / nine cases; 64 combined focused cases passed with search-field, URL/history, listing-contract, CSS-integrity and inline-style checks. Light mobile/dark desktop active-option screenshots inspected; explicit settled action-background/foreground assertions avoid mistaking intermediate CSS-transition colors for final states. No real API/load-performance or screen-reader certification claim.

Integration follow-up, 2026-10-18: both existing definitions are reassessed. Reversed 100-city input proves sorting happens before the 20-option cap; accented city names are compared with the browser's locale-aware collation. Active-descendant failures now identify the missing attribute immediately, and screenshot paths use per-case tmp_path to avoid overwriting diagnostics. Nine cases pass. No network debounce is added to local filtering; the harmless empty string in the selected-value set is not an observable selection defect.

| Definition | Requirement / meaningful assertions | Setup, reliability and limits | Disposition |
|---|---|---|---|
| `test_city_combobox_keyboard_selection_preserves_route_contract` | Active descendant/selected state, ArrowDown/Home/End/Escape/Enter/Tab; focus remains on input; selection updates hidden value and single chip; selected option excluded; search/page/fixed tag retained, tag automatically submits while general list waits. Options have 44px height and fit viewport. | Actual list/tag routes and shared controller, two themes × two widths, isolated API with deterministic empty response. Condition waits, no sleeps. Does not prove live database filtering, all browsers or audible assistive-technology output. | Keep; old pointer-only implementation fails keyboard and ARIA assertions. |
| `test_city_combobox_treats_html_and_regex_as_plain_text_and_bounds_options` | HTML/regex-looking text is rendered and selected literally, no injected image executes; pointer selection calls chip rendering; options capped at 20 and blur clears them. | Small DOM harness executes shipped controller with synthetic city data and a narrow history callback spy. Not whole-route or database evidence; bounded option DOM is not a whole-process memory guarantee. | Keep; old regex/HTML construction would fail literal-render and injection assertions. |

## tests/test_public_date_range.py

- [ ] `test_restored_historical_range_can_select_an_earlier_start`
- [x] `test_public_date_vendor_files_match_reviewed_release_hashes`
- [x] `test_actual_date_picker_locale_bounds_history_and_clear`
- [x] `test_actual_calendar_is_theme_safe_and_keyboard_reachable`
- [x] `test_public_dates_remain_manually_usable_if_picker_asset_fails`

UI-01 / QA-04, 2026-10-13, Codex, P1, stacked on #923. Tests execute the same pinned local Flatpickr JS/CSS as the product, not a stub. API results are isolated because these definitions assess widget state/URL integration rather than database search. Upstream npm tarball SHA-512 integrity and normalized JS/CSS/license members were independently checked; final revision/run/PR evidence linked at delivery.

| Definition | Purpose / assertions | Setup / coverage / reliability | Disposition |
|---|---|---|---|
| `test_public_date_vendor_files_match_reviewed_release_hashes` | Shipped JS/CSS/MIT license match reviewed version bytes. | Local SHA-256 against independently integrity-checked npm release, terminal newline normalization documented. Hash match does not prove absence of all upstream defects. | Keep. |
| `test_actual_date_picker_locale_bounds_history_and_clear` | Real picker shows FI/EN/SV names; changed range submits, Back restores coupled bounds, clear removes selections/max bound and restores current-year floor; explicit 2020 ranges survive restoration. | Three routes × three locales (nine cases), actual selectedDates/config plus DOM/URL waits. Synthetic API only; not live-data/count proof. Does not cover every unusual year/time-zone boundary. | Keep. |
| `test_actual_calendar_is_theme_safe_and_keyboard_reachable` | ArrowDown enters actual day grid, selected hover uses contrast-safe semantic colors, viewport fit/light-dark surface, Escape closes and restores field focus. | Two themes × 1440/390px (four cases), actual JS/CSS and DOM focus; selected screenshots inspected. Not a full assistive-technology or all-browser audit. | Keep. |
| `test_public_dates_remain_manually_usable_if_picker_asset_fails` | Date fields still submit ISO URL filters without picker JS and no page exception. | Three actual routes, one specific asset aborted deliberately, normal adapter/history scripts run. Dependency-failure fallback, not whole no-JavaScript listing acceptance. | Keep. |

Earlier filter/history regressions now also execute the real bundled picker and still cover invalid typed dates: the adapter retains the invalid raw entry instead of allowing vendor close/blur parsing to silently erase it. Cropper/autocomplete/full accessibility and broader DATA-01 acceptance remain separate.

## tests/test_public_demo_localization.py

- [ ] `test_demo_detail_renders_translated_fields_and_language_switcher`
- [ ] `test_demo_api_returns_translated_card_fields_for_active_locale`
- [ ] `test_demo_api_v1_search_matches_translated_fields`
- [ ] `test_demo_api_blueprint_returns_localized_results_for_requested_language`
- [ ] `test_demo_api_blueprint_uses_session_locale_when_lang_missing`
- [ ] `test_demo_api_blueprint_can_include_translation_map`
- [ ] `test_demo_api_blueprint_detail_returns_localized_payload`
- [ ] `test_demo_api_blueprint_detail_can_include_translation_map`
- [ ] `test_demo_api_blueprint_search_and_tag_filters_match_translations`
- [ ] `test_calendar_month_view_renders_translated_demo_titles`
- [ ] `test_demonstrations_list_page_renders_without_server_error`
- [ ] `test_set_language_redirects_back_to_safe_next_path`
- [ ] `test_language_switcher_keeps_current_page_and_query_string`

## tests/test_public_demonstrations_api.py

- [ ] `test_public_index_provisioning_is_not_part_of_route_import`
- [x] `test_public_demonstrations_list_uses_summary_payload`
- [x] `test_public_pages_have_chronological_tie_breaks_and_filtered_counts`
- [x] `test_public_page_metadata_handles_empty_and_out_of_range`
- [x] `test_public_pagination_normalizes_invalid_numeric_args`
- [x] `test_public_chronological_sort_has_index_backed_plan`

DATA-01 / QA-02, 2026-10-12, Codex, P1. Real Flask/public routes and MongoDB fixtures; no ordering/count/authorization mocks. Separate tag isolates fixture rows. Dates are relative to today; inserted order intentionally disagrees with time and ID. Both API shapes are parameterized; existing localization and recurring SEO regressions run alongside this slice. Final run/revision linked in PR.

| Definition | Purpose and assertion review | Setup, variants and reliability | Disposition |
|---|---|---|---|
| `test_public_demonstrations_list_uses_summary_payload` | Summary fields retained; internal payload/history/notes excluded. | Existing future-dated seeded record with exact public values and excluded keys. Does not prove every sensitive field is excluded; projection audit remains separate. | Keep. |
| `test_public_pages_have_chronological_tie_breaks_and_filtered_counts` | Exact date/time/ID sequence across three pages, no duplicate/gap, same filtered total/ranges; modern next links preserve filters and page size. | Six reverse-inserted records plus hidden matching record; both endpoints, tied time/IDs and different days. Stable-dataset contract only; concurrent inserts need separate snapshot/cursor policy. | Keep. |
| `test_public_page_metadata_handles_empty_and_out_of_range` | Empty pages have 0–0 range and correct filtered total/page count. | Both endpoints, no matches versus beyond-last page; exact empty arrays. UI handling remains next slice. | Keep. |
| `test_public_pagination_normalizes_invalid_numeric_args` | Malformed/negative args do not crash and independent valid arg survives. | Six parameter cases: two endpoints × three input variants. Huge page-size/offset bounds and legacy time normalization remain follow-up evidence. | Keep. |
| `test_public_chronological_sort_has_index_backed_plan` | Approved/date/start-time/ID index registers idempotently without removing old indexes; actual broad public query has IXSCAN and no blocking SORT, returns 12 rows. | Real disposable MongoDB, 200 synthetic future records plus seed, unhinted winning plan. Reproduced SORT before the fix; no mocked planner. Does not claim production timings, arbitrary filter plans or live index presence. | Keep; review-driven regression. |

Remaining DATA-01: browser cumulative summaries, URL/filter reset and stale-request protection across list/city/tag; representative light/dark/mobile checks. API pagination does not claim snapshot stability during concurrent insert/delete, nor canonicalization of non-normalized historical times.

## tests/test_public_detail_invite_contract.py

- [ ] `test_detail_invite_dialog_uses_safe_dom_rendering_and_app_feedback`
- [ ] `test_detail_invite_dialog_has_translated_visible_copy`

## tests/test_public_detail_like_guard.py

- [ ] `test_optional_like_controls_are_guarded_in_every_entrypoint`
- [ ] `test_cancelled_detail_omits_like_controls_without_page_errors`

## tests/test_public_follow_feedback_contract.py

- [ ] `test_public_follow_failures_use_shared_safe_feedback`

## tests/test_public_guides.py

- [ ] `test_public_guides_are_accessible_without_login`
- [ ] `test_submit_page_links_to_guides_for_submission_help`

## tests/test_public_inline_style_contract.py

- [x] `test_public_inline_style_debt_matches_reviewed_baseline`
- [x] `test_public_inline_style_baseline_scope_is_documented`
- [x] `test_style_attribute_scanner_covers_all_valid_static_forms`

UI-02b / QA-03, P2; individually reviewed 2026-10-15 by Codex. Pure repository source/JSON checks with no app, network or permission mocks. The migration removed 23 inline bytes from index and 59 from organization details; only those two residual-block hashes are updated, with unchanged block counts and no new inline declarations/attributes. This is a reviewed reduction, not a full baseline regeneration or expanded exception.

| Definition | Requirement / assertions | Coverage, reliability and limits | Disposition |
|---|---|---|---|
| `test_public_inline_style_debt_matches_reviewed_baseline` | Every in-scope style block/attribute matches its reviewed content hash/multiplicity; unexplained additions, removals or changes fail with exact path differences. | Actual tracked template source and JSON; regex-based structural scanning, not a full HTML/CSS parser or visual/security audit. Human-reviewed baseline changes remain a trust boundary. | Keep exact debt ratchet; deliberate two-block reductions reviewed here. |
| `test_public_inline_style_baseline_scope_is_documented` | Excluded directories and exact-hash policy stay explicit rather than silently widening exceptions. | Fixed metadata assertions; cannot by itself prove collector implementation or prevent a coordinated malicious test/baseline change. | Keep supporting scope guard. |
| `test_style_attribute_scanner_covers_all_valid_static_forms` | Double/single/unquoted styles and script-generated markup are counted; data-style and JS-created style elements are not misclassified as attributes. | Synthetic scanner fixture, not runtime DOM; name overstates universality—these representative forms do not prove every malformed/Jinja/escaped HTML combination. | Keep with narrowed coverage claim; further parser edge cases remain separate. |

## tests/test_public_list_filter_history.py

2026-10-13 follow-up: the existing explicit page/history lifecycle test now selects the supported data-saving manual fallback. Its page/filter/back/forward/retry assertions remain intact; automatic windowing is independently exercised below. A passing manual test is not automatic-loading evidence.

- [x] `test_public_filter_url_restores_page_and_back_forward`
- [x] `test_restored_city_chip_is_text_safe_and_removal_resets_url`
- [x] `test_tag_page_invalid_pagination_does_not_raise_500`

DATA-01 / QA-02, 2026-10-12, Codex, P1, stacked on #921. Actual routes/templates/form/history/loader/CSS; synthetic API responses isolate browser contracts; the pinned local picker now executes. Backend ordering/query plans remain #920's real-DB evidence. The tag numeric regression uses real Flask GETs. Final revision/run/PR evidence recorded at delivery.

| Definition | Purpose / assertions | Setup / coverage / reliability | Disposition |
|---|---|---|---|
| `test_public_filter_url_restores_page_and_back_forward` | URL restores page 3/size/date/search; search resets page 1, load-more updates URL, Back/Forward restore form and accurate deep-page ranges, retry updates page after 503. | Three route variants; actual browser history; API captures prove fixed city/tag overrides and preserved location/date/size. Explicit waits for state transitions; not a live-data or snapshot-pagination test. | Keep. |
| `test_restored_city_chip_is_text_safe_and_removal_resets_url` | Markup-shaped city stays text, keyboard removal clears city/reset page without dropping date; invalid calendar day shows error without mutating URL. | List/tag × light/dark × 1440/390px (eight cases), exact DOM fields/URL, chip geometry and 44px target; selected chip screenshots inspected. Does not claim whole-page overflow is fixed or complete autocomplete accessibility. | Keep. |
| `test_tag_page_invalid_pagination_does_not_raise_500` | Tag GET rejects neither malformed numeric strings nor zero/negative values with server error. | Three real route cases, exact 200; shared parser retains original tag default size. Huge integer bounds remain explicit server-pagination follow-up. | Keep. |

Deep links/history restore the latest requested page as a new window; subsequent Load more extends that window. They do not replay every previously accumulated page. Remaining acceptance includes production integration, API pagination bounds/legacy times and broader discovery/no-JS behavior.

## tests/test_public_list_request_state.py

2026-10-13 follow-up: keyboard-control geometry tests explicitly use the data-saving manual fallback so each intermediate range remains observable. Actual automatic loading, bounded DOM, focus and delayed-response behavior have separate runtime coverage below.

- [x] `test_public_retry_uses_compiled_locale_catalog`
- [x] `test_public_loader_ignores_stale_search_and_counts_appended_results`
- [x] `test_public_controller_old_finally_cannot_unlock_new_search`
- [x] `test_public_loader_http_failure_offers_retry_without_erasing_append`
- [x] `test_public_listing_summary_is_shared_responsive_and_keyboard_operable`

DATA-01 / QA-02, 2026-10-12, Codex, P1; stacked on #920. Browser harnesses use actual shipped JS with controlled deferred fetch responses (deliberately ignoring abort), safe lightweight card-render stubs and no server ordering mock claim. The template/browser matrix uses actual routes, cards, CSS and keyboard with isolated API data and actual pinned date-picker runtime; server order/count evidence belongs to #920. Final revision/run evidence linked in PR.

| Definition | Purpose / assertions | Fixtures / coverage / reliability | Disposition |
|---|---|---|---|
| `test_public_retry_uses_compiled_locale_catalog` | Runtime MO files translate the retry label in English and Swedish. | Two cases read actual compiled GNU catalogs, without Babel mocks; catches PO-only fixes that fail to ship runtime translations. Does not claim full catalog completeness. | Keep; reviewed 2026-10-13; focused run linked in #921. |
| `test_public_loader_ignores_stale_search_and_counts_appended_results` | New search wins; aborted older response cannot repaint; append counts accumulate and empty append does not erase cards. | Actual loader, deferred response order, exact DOM/count/abort state. Card/friend/navigation rendering isolated; not a backend snapshot test. | Keep. |
| `test_public_controller_old_finally_cannot_unlock_new_search` | Old load-next completion cannot unlock or alter newer reset state. | Actual controller, exact lock/page/page-count/request assertions with manual resolvers; no timing sleeps. | Keep. |
| `test_public_loader_http_failure_offers_retry_without_erasing_append` | HTTP failure preserves prior cards and offers successful retry; overlapping retry/append is suppressed. | Actual loader and 503 mock, exact DOM/count/request count; replacement-failure and malformed payload matrices remain follow-up. | Keep. |
| `test_public_listing_summary_is_shared_responsive_and_keyboard_operable` | Three list families share live summary, keyboard load-more, final hidden control and viewport-fitting summary in both themes/sizes. | Twelve cases: list/city/tag × light/dark × 1440/390px. Actual UI, synthetic API and actual pinned date picker; page errors asserted, summary geometry checked. Does not prove whole-page overflow, all date-picker behavior or live data. | Keep. |

Screenshots of representative list states are inspected separately. Existing page/footer overflow and full URL/history behavior remain explicit follow-up work; this review does not silently declare broad UI acceptance.

## tests/test_public_attendance_window.py

- [x] `test_slow_attendance_survives_append_and_cancels_only_eviction_or_search`

DATA-01b review correction, 2026-10-13, Codex, P2: actual shipped attendance updater, loader and bounded window with controlled delayed fetch responses and lightweight card rendering. Six pages leave at most five pending page requests; the removed page is aborted while all retained-page requests survive. Completing a retained request clears its actual loading element. Replacement search aborts remaining old requests and leaves one new active request/page. No live friends API, real-user graph, or delivery-timing guarantee. Keep: catches the former unconditional append cancellation; final combined focused run passed 76 cases.

## tests/test_public_windowed_loading.py

- [x] `test_successful_retry_resumes_automatic_loading_without_another_scroll`

Approved #928 review correction, 2026-10-13: this shared-controller runtime regression uses deferred page callbacks, fails an automatic request, proves no retry loop, then simulates the retry loader's successful state/resume callback without a scroll event. The next nearby page must load automatically with unchanged scroll position; final-page state prevents further requests. It fails without scheduleAuto in resumeAuto. Explicit state/frame waits, no arbitrary sleep. Synthetic loader data isolates scheduling; not a live API retry test. Keep.

- [x] `test_automatic_public_lists_bound_dom_and_restore_discarded_pages`
- [x] `test_delayed_append_preserves_new_focus_and_cannot_restore_old_filter_pages`
- [x] `test_window_does_not_discard_keyboard_focus_and_preserves_scroll_anchor`
- [x] `test_automatic_requests_are_single_flight_and_failure_never_loops`

DATA-01b / QA-02 / QA-04, P2; reviewed 2026-10-13 by Codex. Ten parameterized cases; final combined review-correction run passed 77 focused cases with attendance, request/history/listing/inline-style/CSS and server-resource-limit checks. API responses are isolated for browser behavior; this does not prove live database performance or a numerical heap ceiling. Five retained pages are a constant bound on mounted cards and page references, not a claim that the entire browser uses constant RAM. Final PR records revision/run evidence.

| Definition | Requirement / assertions | Fixtures, mocks, reliability and limits | Disposition |
|---|---|---|---|
| `test_automatic_public_lists_bound_dom_and_restore_discarded_pages` | Scroll through ten pages without clicking Load more; at most five mounted pages / 60 default-size cards; discarded prior page re-fetched, contiguous range restored. | Six actual list/city/tag × light desktop/dark mobile cases with real renderer/controller/CSS. Synthetic 30-page API isolates UI; exact bounds, captured requests and page errors. Representative screenshots inspected. No real-API load benchmark or screen-reader claim. | Keep. |
| `test_delayed_append_preserves_new_focus_and_cannot_restore_old_filter_pages` | Focus gained during an in-flight request prevents eviction; replacement search aborts old request and stale response cannot repopulate old pages. | Shipped loader/window with deferred responses deliberately ignoring abort; lightweight render/friends stubs isolate state. Exact focus/connectivity, single new page, text and aria-busy assertions. | Keep. |
| `test_window_does_not_discard_keyboard_focus_and_preserves_scroll_anchor` | Offscreen focused page cannot be pruned, even manually; removing it after blur retains surviving page position within one pixel. Explicit manual advance can replace a visible unfocused edge to avoid a small-page/large-viewport dead end. | Real shared window and browser geometry; fixed 600px fixture pages isolate anchor correction. Does not prove every image/font layout-shift case. | Keep. |
| `test_automatic_requests_are_single_flight_and_failure_never_loops` | Repeated scroll/manual events cannot overlap page requests; failure stops automatic retries; explicit manual retry works; destroyed controller ignores late state. | Real shared controller, deferred load callback, explicit frame/state waits; no arbitrary sleep. Does not prove server cancellation after an aborted HTTP request. | Keep. |

## tests/test_public_listing_contract.py

- [x] `test_public_listing_family_uses_shared_hero_and_pagination_markup`
- [x] `test_public_listing_pagination_controller_supports_buttons_and_sentinels`
- [x] `test_public_workspace_styles_cover_listing_end_message`
- [x] `test_public_list_runtime_uses_defined_localized_browser_contracts`
- [x] `test_public_list_filters_and_date_picker_follow_active_locale`

DATA-01 / QA-02 supporting review, 2026-10-12, Codex, P1. Source-only assertions retained as wiring guards, not treated as runtime or visual proof; meaningful browser behavior is covered in request-state regressions above.

| Definition | Purpose and assertion review | Fixtures / coverage / reliability | Disposition |
|---|---|---|---|
| `test_public_listing_family_uses_shared_hero_and_pagination_markup` | Three templates import shared hero and render load-more macro. | Exact source strings only; does not prove runtime geometry or semantics. | Keep as wiring guard alongside browser matrix. |
| `test_public_listing_pagination_controller_supports_buttons_and_sentinels` | Controller retains button/sentinel/reload hooks. | Source strings cannot prove concurrency; new deferred-controller regression supplies behavioral evidence. Intersection-observer triggering remains unreviewed runtime gap. | Keep. |
| `test_public_workspace_styles_cover_listing_end_message` | End-message selectors remain in shared CSS. | String presence, not light/dark/hidden computed-style proof. | Keep with narrow claim. |
| `test_public_list_runtime_uses_defined_localized_browser_contracts` | Removed undefined view/translation/jQuery contracts stay removed; locale-derived picker wiring remains. | Exact obsolete/required strings; cannot prove translation completeness or runtime. | Keep alongside locale/browser tests. |
| `test_public_list_filters_and_date_picker_follow_active_locale` | FI/EN/SV city chip labels, January names, summary formats and retry text follow selected locale without page errors. | Actual page/autocomplete, compiled catalogs, Intl formatter and pinned picker locale config; three parameter cases. Does not test date-picker library internals, chip URL reset or complete keyboard selection. | Keep; strengthened localization evidence; remaining gaps tracked. |

## tests/test_public_locales.py

- [ ] `test_unpublished_language_cannot_be_selected`
- [ ] `test_stale_unpublished_locale_is_removed`
- [ ] `test_browser_language_cannot_enable_unpublished_locale`
- [ ] `test_single_public_language_hides_selector`
- [ ] `test_sitemap_does_not_advertise_unpublished_language`
- [ ] `test_maintenance_page_hides_unpublished_english`
- [ ] `test_submission_pages_offer_translation_help`

## tests/test_public_message_localization.py

- [ ] `test_reminder_api_localizes_required_email`
- [ ] `test_suggestion_flash_localizes_empty_submission`
- [ ] `test_reminder_modal_uses_shared_safe_feedback_contract`

## tests/test_public_mobile_overflow.py

- [x] `test_shared_information_cards_have_mobile_shrink_contract`
- [x] `test_information_cards_fit_portrait_viewport`
- [x] `test_public_collection_page_fits_viewport_without_clipping`
- [x] `test_home_and_organization_layout_preserves_content`

UI-02 / QA-03/QA-04, P2, reviewed 2026-10-15 by Codex, based on main 9098c02a. The shared footer used 100% content-box width plus 32px horizontal padding: actual 390px list page had 422px body width. Empty-state geometry alone then missed a long title clipped inside its card. Component-scoped box sizing, shrinkable footer grid and card text wrapping fix these independent causes without adding global overflow suppression or a new palette. All 93 combined width/search/listing/CSS/inline cases pass. CodeRabbit's two Minor test findings (overwritten screenshot artifacts and first-locator-only count) were corrected; final changed-test-file review completed with zero findings. Representative light/dark 390px footer screenshots inspected; whole-body screenshot capture is not relied on for body-scroll-host content outside the viewport.

| Definition | Requirement / meaningful assertions | Setup, coverage and reliability limits | Disposition |
|---|---|---|---|
| `test_shared_information_cards_have_mobile_shrink_contract` | Border-box belongs to the container selector, grid children explicitly shrink and information text can wrap. | Source regex now scopes declarations instead of accepting an unrelated global reset. No runtime or visual proof by itself; benign selector regrouping may require maintenance. | Strengthened source guard; keep with runtime cases. |
| `test_information_cards_fit_portrait_viewport` | Actual information page root width and every section-card bound/content width fit at 320/360/390px. | Real route with fixture-isolated external assets; default theme only, no all-page/localization claim. Card presence prevents vacuous empty selection. | Keep existing three runtime cases. |
| `test_public_collection_page_fits_viewport_without_clipping` | List/city/tag root and body fit, exact card count/full long title/address/tag text is present and fits its own box, footer links stay inside viewport with visible keyboard focus; footer content is not hidden by overflow clipping and requested theme is actually applied. | 48 actual-route cases: light/dark × 320/360/390/1440px × empty/populated API. API is deterministic synthetic data, renderer/chrome are real. Diagnostic widths identify culprits; real focus/Shift+Tab and case-specific tmp_path screenshots. Not live API data, browser/locale exhaustive testing, production widget interaction, image/media/table or zoom acceptance. | New whole-page and component clipping regression; keep. |
| `test_home_and_organization_layout_preserves_content` | Home/normal-org/long-org root and complete hero/title/action boxes fit and center; exact long name/description remain, home retains three actions, heading stays white and requested theme is applied. Computed mobile font size must follow the shared responsive scale, not a legacy container reset. | 24 real SSR route cases: two themes × 320/360/390/1440px × three views. Real synthetic seeded organization, isolated API/external assets; no CSS/image-engine mocks. Unique 320/390px tmp_path captures with finite animations fast-forwarded. Explicit 16px-root design-scale assertion needs maintenance if typography changes. Does not prove every locale/font/provider, media variant, dynamic widget, animation state or full keyboard/screen-reader interaction. | New UI-02b regression; original home title and later nowrap action clipping reproduced separately; keep. |

UI-02b follow-up is stacked on #936's shared shell/width-test foundation, not a duplicate footer fix. Public hero content/action shrink and mobile title sizing live in the existing shared stylesheet. The two page-local organization flex/min-width and home nowrap rules were removed; no new inline palette or broad override added. Visual inspection exposed a legacy mobile container `font-size: revert !important` despite passing overflow guards; removing it restores the shared scale (24px rather than 32px at 320px) and an explicit computed-size assertion guards this regression. Both the imported container URL and parent stylesheet URL are cache-versioned. All 117 combined width/listing/search/CSS/inline cases pass; three changed templates parse with Jinja and diff check passes. CodeRabbit completed review of the ten implementation/inventory files with zero findings (roadmap status edits excluded). Screenshot collection additionally includes 1440px desktop. Broader page-owned style migration and non-geometry UI acceptance remain open.

## tests/test_public_native_dialog_contract.py

- [ ] `test_public_templates_do_not_use_native_browser_dialogs`
- [ ] `test_shared_public_javascript_does_not_use_native_browser_dialogs`
- [ ] `test_removed_legacy_scripts_cannot_be_reintroduced_or_referenced`

## tests/test_public_notification_contract.py

- [ ] `test_notification_popover_uses_accessible_shared_markup`
- [ ] `test_notification_payload_is_rendered_without_html_interpolation`
- [ ] `test_notification_states_use_shared_product_tokens`

## tests/test_public_performance_contract.py

- [ ] `test_base_does_not_load_unused_jquery_ui_on_every_public_page`
- [ ] `test_bootstrap_is_versioned_on_the_first_party_cdn`
- [ ] `test_high_traffic_pages_do_not_duplicate_font_awesome`
- [ ] `test_detail_map_is_lazy_loaded_below_the_fold`

## tests/test_public_profile_editor.py

- [ ] `test_profile_editor_uses_shared_optional_field_contract`
- [ ] `test_legacy_profile_editor_redirects_to_canonical_settings`
- [ ] `test_profile_api_requires_authentication`
- [ ] `test_profile_api_preserves_picture_when_only_bio_changes`
- [ ] `test_saved_bio_is_safely_rendered_on_public_profile`
- [ ] `test_profile_api_returns_safe_localized_validation_errors`
- [ ] `test_profile_editor_uses_safe_dom_and_shared_css`

## tests/test_public_search_fields.py

- [ ] `test_city_suggestions_stay_within_their_search_field`
- [x] `test_public_search_labels_are_explicit_and_unique`
- [x] `test_public_search_fields_are_visible_aligned_and_focusable`

UI-01 / QA-04, 2026-10-12, Codex, P1, stacked on #922. Actual shared macro and compiled catalogs; browser uses actual product styles, with synthetic API and actual pinned date picker. Final run/revision/PR evidence linked at delivery.

| Definition | Purpose / assertions | Fixtures / coverage / reliability | Disposition |
|---|---|---|---|
| `test_public_search_labels_are_explicit_and_unique` | Every text field has a unique explicit label/target; exact FI/EN/SV search/start/end copy; hidden backend names and fixed city preserved; error linkage present. | Three routes × three locales (nine cases), real Flask/Jinja/catalog rendering. Regex limited to controlled form structure; full DOM/accessibility audits remain separate. | Keep. |
| `test_public_search_fields_are_visible_aligned_and_focusable` | Label click focuses correct input; label/input left edges align; 44px controls fit viewport; logical first Tab target. | Three routes × two themes × 1440/390px (twelve cases). Actual DOM/style/focus, actual pinned picker/synthetic API; representative form screenshots inspected. Does not verify actual picker popup, autocomplete keyboard behavior or whole-page overflow. | Keep; remaining UI-01/UI-02 items explicit. |

## tests/test_public_token_manager.py

- [ ] `test_token_manager_requires_authentication`
- [ ] `test_token_manager_renders_shared_accessible_contract`
- [ ] `test_token_manager_uses_safe_dom_and_shared_styles`
- [ ] `test_token_manager_rendered_javascript_parses`
- [ ] `test_token_creation_rejects_malformed_scopes_with_localized_error`
- [ ] `test_token_revoke_rejects_invalid_and_foreign_ids`
- [ ] `test_token_revoke_deletes_only_the_current_users_token`

## tests/test_public_toolbar_contract.py

- [ ] `test_toolbar_uses_safe_management_links_instead_of_duplicate_handlers`
- [ ] `test_toolbar_uses_clear_action_hierarchy_without_current_page_links`
- [ ] `test_toolbar_collapse_control_exposes_state_and_relationship`
- [ ] `test_toolbar_styles_are_scoped_and_use_product_tokens`
- [ ] `test_toolbar_inline_style_debt_was_removed_from_baseline`
- [ ] `test_toolbar_stylesheet_cache_key_is_versioned`
- [ ] `test_toolbar_renders_for_authenticated_admin_demo_context`
- [ ] `test_toolbar_hides_javascript_only_controls_until_enhanced`
- [ ] `test_toolbar_renders_organization_management_links`
- [ ] `test_toolbar_is_omitted_when_role_has_no_contextual_actions`
- [ ] `test_organization_admin_with_regular_user_role_gets_scoped_toolbox`
- [x] `test_organization_scope_does_not_leak_to_unrelated_demonstration`
- [x] `test_explicit_editor_keeps_contextual_toolbox_after_content_normalization`
- [ ] `test_toolbar_is_omitted_without_demo_or_organization_context`
- [ ] `test_toolbar_fits_public_detail_in_both_themes`

Review follow-up, 2026-10-18: the unrelated-organization negative explicitly clears the fixture's separate editor grant before a real public GET; absence of the toolbox proves membership alone does not leak actions. The new positive keeps the explicit editor grant and asserts both toolbox presence and exact persisted editors after GET normalization. These are authorization-context regressions, not browser layout or primary authentication evidence. Permission predicates and reauthentication are unchanged. All 33 focused moderation-preservation, MCP and non-browser toolbar cases pass locally; full CI remains the integration gate.

## tests/test_recurrence_dates.py

- [ ] `test_recurrence_dates_align_weekly_schedule_and_limit_output`
- [ ] `test_recurrence_dates_honor_selected_day_of_month`
- [ ] `test_recurrence_preview_script_uses_safe_dom_rendering`
- [ ] `test_recurrence_preview_aborts_stale_request_before_empty_date_return`

## tests/test_recurring_public_seo.py

- [ ] `test_recurring_series_has_one_sitemap_url_and_no_child_urls`
- [ ] `test_series_page_selects_next_occurrence_and_aligns_seo_metadata`
- [ ] `test_old_child_url_redirects_to_current_series_page`
- [ ] `test_authenticated_old_child_url_also_redirects_to_series`
- [ ] `test_explicit_occurrence_keeps_clean_series_canonical`
- [ ] `test_all_past_series_selects_latest_and_explains_state`
- [ ] `test_selection_skips_cancelled_future_occurrence`
- [ ] `test_selection_returns_none_when_every_occurrence_is_cancelled`
- [ ] `test_all_cancelled_series_is_noindex_and_omitted_from_sitemap`
- [ ] `test_selection_orders_start_times_with_midnight_fallback`
- [ ] `test_same_day_occurrence_remains_current_until_its_end_time`
- [ ] `test_invalid_recurring_parent_is_404`
- [ ] `test_empty_recurring_series_is_noindex_in_html_and_response_header`
- [ ] `test_public_api_and_today_page_link_recurring_occurrences_to_series`
- [ ] `test_api_cards_use_standalone_url_when_parent_series_is_invisible`
- [ ] `test_series_page_stays_indexable_when_selected_occurrence_is_beyond_horizon`
- [ ] `test_series_page_is_noindex_when_no_occurrence_is_in_discovery_window`
- [ ] `test_recurring_series_chooser_is_theme_aware_and_portrait_safe`
- [ ] `test_requested_occurrence_is_independent_of_chooser_limits`
- [ ] `test_occurrence_without_hide_field_remains_visible`
- [ ] `test_requested_occurrence_obeys_series_visibility`
- [ ] `test_cancelled_rows_do_not_consume_active_limit_and_remain_linked`
- [ ] `test_all_cancelled_series_exposes_working_occurrence_links`

## tests/test_recurring_siblings_regression.py

- [ ] `test_recurring_siblings_does_not_dump_pathological_series`

## tests/test_register_next_steps.py

- [ ] `test_next_steps_without_session_email_is_safe`
- [ ] `test_next_steps_uses_session_email_and_safe_json`
- [ ] `test_next_steps_uses_shared_components_without_page_owned_css`
- [ ] `test_resend_confirmation_does_not_expose_delivery_exception`

## tests/test_registration_validation_contract.py

- [ ] `test_password_helper_ignores_empty_identity_fragments`
- [ ] `test_password_helper_rejects_username_and_email_identity`
- [ ] `test_registration_rejects_weak_and_identity_based_passwords`
- [ ] `test_register_form_uses_safe_localized_shared_status_contract`
- [ ] `test_register_form_matches_server_three_of_four_category_policy`
- [ ] `test_auth_routes_unpack_password_validation_result`

## tests/test_request_ip.py

- [ ] `test_client_ip_uses_socket_address_without_proxy_header`
- [ ] `test_client_ip_accepts_cloudflare_header_from_cloudflare_proxy`
- [ ] `test_client_ip_rejects_spoofed_cloudflare_header_from_direct_request`
- [ ] `test_client_ip_rejects_invalid_cloudflare_header`
- [ ] `test_client_ip_prefers_real_ipv6_when_cloudflare_pseudo_ipv4_is_enabled`

## tests/test_robots_txt.py

- [ ] `test_robots_txt_advertises_canonical_sitemap`
- [ ] `test_robots_txt_keeps_existing_directives_and_single_sitemap`

## tests/test_route_smoke.py

- [ ] `test_all_registered_http_routes_respond_without_server_errors`
- [ ] `test_reset_client_session_restores_authentication_after_logout`

## tests/test_security_regressions.py

- [ ] `test_legacy_settings_rejects_privilege_fields`
- [ ] `test_legacy_settings_still_updates_allowed_fields`
- [ ] `test_ordinary_user_cannot_issue_mcp_admin_token`
- [ ] `test_api_token_rejects_unknown_scopes`
- [ ] `test_api_token_rejects_malformed_scope_payload`
- [ ] `test_global_admin_can_issue_mcp_admin_token`
- [ ] `test_privileged_token_without_step_up_is_rejected`
- [ ] `test_auth_security_routes_ignore_stale_module_database_handle`

## tests/test_service_integrations.py

- [ ] `test_redis_service_responds_to_ping`
- [ ] `test_smtp_service_accepts_messages`
- [ ] `test_s3_service_round_trips_objects`

## tests/test_settings_credential_dialogs.py

- [ ] `test_credential_actions_use_shared_accessible_modals`
- [ ] `test_settings_has_no_native_credential_dialogs_and_preserves_api_contracts`
- [ ] `test_rendered_settings_inline_javascript_parses`
- [ ] `test_credential_dialog_copy_is_translated_in_supported_catalogs`

## tests/test_settings_layout_contract.py

- [ ] `test_settings_route_uses_shared_workspace_components`
- [ ] `test_settings_template_has_no_page_owned_presentation_or_jquery_tabs`
- [ ] `test_settings_fields_and_city_picker_follow_accessible_contract`
- [ ] `test_settings_api_data_is_rendered_with_dom_nodes_and_active_locale`
- [ ] `test_settings_shared_css_uses_product_tokens_and_cache_is_bumped`
- [ ] `test_new_settings_copy_is_translated_in_supported_catalogs`

## tests/test_settings_page_smoke.py

- [ ] `test_settings_page_renders_after_stepup_rewrite`

## tests/test_site_analytics.py

- [ ] `test_demo_search_history_restoration_does_not_count_as_new_search`
- [ ] `test_static_assets_are_not_counted`
- [ ] `test_admin_and_account_pages_are_not_counted`
- [ ] `test_health_checks_and_status_are_not_counted`
- [ ] `test_api_and_analytics_endpoints_are_not_counted`
- [ ] `test_demonstration_page_is_classified`
- [ ] `test_demonstration_subresources_are_not_pageviews`
- [ ] `test_organization_page_is_classified`
- [ ] `test_index_and_generic_pages_are_classified`
- [ ] `test_devices_are_bucketed_coarsely`
- [ ] `test_referrers_are_categorized_not_stored_raw`
- [ ] `test_multiple_requests_aggregate_into_single_counters`
- [ ] `test_language_is_recorded`
- [ ] `test_device_and_referrer_are_recorded`
- [ ] `test_increment_counter_buckets_by_helsinki_local_hour`
- [ ] `test_health_endpoint_does_not_record`
- [ ] `test_admin_pages_do_not_record`
- [ ] `test_static_assets_do_not_record`
- [ ] `test_api_requests_do_not_record`
- [ ] `test_bot_user_agents_do_not_record`
- [ ] `test_404_and_errors_are_not_recorded`
- [ ] `test_non_html_responses_are_not_recorded`
- [ ] `test_analytics_failure_does_not_break_page`
- [ ] `test_analytics_can_be_disabled`
- [ ] `test_admin_overview_returns_200_and_numbers`
- [ ] `test_admin_overview_labels_resourceless_page_types`
- [ ] `test_admin_overview_documents_limits`
- [ ] `test_overview_period_math`
- [ ] `test_demo_analytics_numbers`
- [ ] `test_demo_analytics_resolves_slug_and_id`
- [ ] `test_admin_demo_analytics_page`
- [ ] `test_admin_demo_analytics_unknown_demo_404`
- [ ] `test_analytics_requires_login`
- [ ] `test_analytics_requires_permission`
- [ ] `test_top_pages_ranks_demos_and_titles`
- [ ] `test_demo_search_event_recorded_once_per_search`
- [ ] `test_demo_search_pagination_does_not_record`
- [ ] `test_plain_list_loads_do_not_record_search`
- [ ] `test_language_change_event`
- [ ] `test_beacon_records_allowlisted_events`
- [ ] `test_beacon_rejects_unknown_events`
- [ ] `test_beacon_rejects_cross_origin_referrer`
- [ ] `test_beacon_external_link_uses_hostname_only`
- [ ] `test_event_totals_and_top_search_terms`
- [ ] `test_resource_id_is_length_capped`
- [ ] `test_dashboard_shows_events`

## tests/test_site_analytics_visitors.py

- [ ] `test_hash_same_ip_device_same_week_is_stable`
- [ ] `test_hash_rotates_after_one_week`
- [ ] `test_hash_depends_on_device`
- [ ] `test_hash_depends_on_address`
- [ ] `test_hash_depends_on_secret`
- [ ] `test_invalid_or_unparsable_address_yields_no_hash`
- [ ] `test_hash_length_is_configured`
- [ ] `test_hash_ignores_ipv4_mapped_ipv6_form`
- [ ] `test_record_visitor_creates_document`
- [ ] `test_record_visitor_same_ip_same_day_increments_pageviews`
- [ ] `test_record_visitor_different_ips_are_distinct`
- [ ] `test_record_visitor_different_device_buckets_are_distinct`
- [ ] `test_record_visitor_unknown_addresses_ignored`
- [ ] `test_record_visitor_disabled_flag`
- [ ] `test_visitor_total_counts_distinct_hashes`
- [ ] `test_visitor_total_zero_when_no_docs`
- [ ] `test_get_visitor_overview_structure`
- [ ] `test_no_data_reports_unavailable_not_zero`
- [ ] `test_period_fully_before_tracking_is_unavailable`
- [ ] `test_visitor_series_marks_pre_tracking_days_as_none`
- [ ] `test_tracking_start_note_present_in_overview`
- [ ] `test_visitor_series_shape_matches_traffic_series`
- [ ] `test_salt_rotation_dedupes_only_within_a_week`
- [ ] `test_visitor_migration_is_registered`
- [ ] `test_visitor_migration_creates_indexes`

## tests/test_sitemap_and_today_pages.py

- [ ] `test_sitemap_includes_public_city_org_tag_and_today_pages`
- [ ] `test_sitemap_demo_priority_is_highest_for_date_closest_to_today`
- [ ] `test_demo_after_sitemap_horizon_is_noindex_and_excluded`
- [ ] `test_demo_at_sitemap_horizon_remains_indexable`
- [ ] `test_historical_demo_outside_sitemap_remains_indexable`
- [ ] `test_invalid_demo_date_is_never_emitted_in_sitemap`
- [ ] `test_detail_cache_varies_when_date_crosses_noindex_boundary`
- [ ] `test_cities_page_links_to_today_and_future_city_views`
- [ ] `test_today_pages_render_finland_and_city_specific_demos`

## tests/test_status_pages.py

- [ ] `test_status_returns_200`
- [ ] `test_status_contains_heading`
- [ ] `test_status_shows_overall_banner`
- [ ] `test_status_shows_db_service`
- [ ] `test_status_shows_cache_service`
- [ ] `test_status_shows_s3_service`
- [ ] `test_status_shows_latency`
- [ ] `test_status_shows_error_when_db_fails`
- [ ] `test_status_uses_no_context_processor`
- [ ] `test_admin_status_returns_200`
- [ ] `test_admin_status_contains_heading`
- [ ] `test_admin_status_shows_mongodb`
- [ ] `test_admin_status_shows_redis`
- [ ] `test_admin_status_shows_s3`
- [ ] `test_admin_status_shows_collection_counts`
- [ ] `test_admin_status_shows_overview`
- [ ] `test_admin_status_shows_recent_errors`
- [ ] `test_admin_status_shows_operational_percentiles`
- [ ] `test_admin_status_shows_email_delivery_errors`
- [ ] `test_admin_status_requires_auth`
- [ ] `test_admin_status_forbids_normal_user`
- [ ] `test_admin_status_shows_server_uptime`
- [ ] `test_admin_status_shows_disk_info`

## tests/test_step_up_authentication.py

- [x] `test_step_up_password_grants_elevation`
- [x] `test_step_up_rejects_wrong_password`
- [x] `test_step_up_requires_totp_when_mfa_enabled`
- [x] `test_step_up_password_without_mfa_and_without_totp_works`
- [x] `test_step_up_options_reflect_methods`
- [x] `test_step_up_webauthn_flow`
- [x] `test_elevation_times_out`
- [x] `test_elevation_does_not_leak_across_sessions`
- [x] `test_sudo_required_redirects_anonymous_to_login`
- [x] `test_logout_clears_elevation`
- [x] `test_change_password_requires_step_up`

QA-01a / P1, reviewed 2026-10-15 by Codex on a branch based on main 9098c02a. Eleven definitions / thirteen cases pass; combined with unchanged fresh-deletion regression coverage, 30 cases pass. The latter file was run for compatibility, not individually assessed in this batch. `wapp` uses the real application with explicit localhost RP/origin and cleanup; `_client_for_user` prepares authenticated sessions, so these are elevation tests, not primary-login coverage. Disposable MongoDB and actual password hashing/TOTP/WebAuthn verification are exercised. External HTTP/email/uploads/screenshots/background jobs are isolated by shared fixtures; the simulated authenticator creates real signed assertions but is not hardware-attestation/browser evidence. Shared fixture/configuration audit remains separately pending; this review does not certify the entire conftest lifecycle or parallel-process cleanup.

| Definition | Requirement / assertions | Setup, reliability and limits | Disposition |
|---|---|---|---|
| `test_step_up_password_grants_elevation` | Registration options denied before correct password, allowed afterward. | Actual guard and password check, not mocked elevation. Does not prove fresh single-action deletion authorization. | Keep as protected-route integration. |
| `test_step_up_rejects_wrong_password` | Wrong password denied; status false, sudo key absent and protected registration still denied. | Real hash; negative state checked beyond response alone. Existing elevation before a failed retry is outside this case. | Strengthened; keep. |
| `test_step_up_requires_totp_when_mfa_enabled` | Password alone gives totp_required; malformed TOTP denied without opening guard; real current TOTP grants elevation. | Actual MFA secret/device in DB and pyotp, no verifier mock. Numeric incorrect codes, replay, TOTP drift/window policy and multiple-device behavior remain outside this definition. | Strengthened; keep with explicit limits. |
| `test_step_up_password_without_mfa_and_without_totp_works` | No-MFA fallback returns success, records correct actor/method and reports elevated. | Real no-device account. Overlaps first test but explicitly protects method/session payload; not a reason to remove route-level guard case. | Strengthened; keep. |
| `test_step_up_options_reflect_methods` | Password-only method initially; real registered key makes WebAuthn preferred. | Signed simulated registration, explicit option response statuses; no hardware/browser claim. | Keep; status assertions strengthened. |
| `test_step_up_webauthn_flow` | Fresh session initially denied; real signed step-up grants actor-bound WebAuthn elevation and unlocks guard; password fallback remains. | Real registration/assertion verification through API using generated key. Challenge replay/origin/counter negative matrices are assessed in separate WebAuthn tests, not proved here. | Strengthened recorded method/actor; keep. |
| `test_elevation_times_out` | Configured 10/900-second windows allow exact boundary, reject just after, clear sudo while retaining login. | Only step-up module clock replaced, not cookie/signing/TOTP clocks; no sleep and no production clock change. Invalid configuration and future timestamps remain follow-up cases. | Strengthened deterministic boundary integration; keep. |
| `test_elevation_does_not_leak_across_sessions` | Separate client for same/different account starts denied; copied sudo bound to a different actor is rejected/cleared; original session stays elevated. | Distinct cookie jars and real guard. Deliberate wrong-actor state is fixture preparation, not a claim that stolen same-actor session cookies are safe. | Strengthened same-account and ownership boundaries; keep. |
| `test_sudo_required_redirects_anonymous_to_login` | Anonymous registration attempt redirects to login. | Actual outer login_required decorator returns 302; this does not test direct sudo_required's standalone 401 branch. | Keep with narrowed claim. |
| `test_logout_clears_elevation` | Original session loses sudo/login, protected route redirects, and real re-login on same cookie jar remains unelevated. | Replaces vacuous fresh-client-only assertion. An isolated runtime mutation making logout clear_elevation a no-op is detected by this test; no production file was mutated. Does not prove copied-cookie invalidation. | Strengthened; mutation confirmed. |
| `test_change_password_requires_step_up` | No elevation and weak password leave stored hash unchanged; successful strong update verifies new password and rejects old one. | Real DB/hash and policy route; no success-status-only claim. Broader existing-session revocation/MFA-reset lifecycle remains separate. | Strengthened; keep. |

## tests/test_submit_draft_reliability.py

- [ ] `test_submit_draft_contract_is_scoped_versioned_and_exactly_cleared`
- [ ] `test_sparse_organizer_indexes_are_collected_in_numeric_order`
- [ ] `test_submit_draft_notice_is_localized_in_english_and_swedish`
- [ ] `test_clean_submit_page_preserves_server_defaults`
- [ ] `test_submit_draft_restores_fields_quill_city_and_organizers`
- [ ] `test_submit_draft_flushes_pending_edits_on_pagehide`
- [ ] `test_invalid_submit_draft_fails_open_without_clearing_server_defaults`

## tests/test_submit_feedback_contract.py

- [ ] `test_submit_form_uses_accessible_feedback_and_product_modal`
- [ ] `test_submit_feedback_replaces_native_dialogs_and_marks_invalid_fields`
- [ ] `test_submit_conflict_modal_renders_server_data_as_text_and_keeps_retry_contract`
- [ ] `test_submit_feedback_has_shared_light_dark_component_and_cache_bump`
- [ ] `test_submit_new_feedback_copy_is_localized_in_english_and_swedish`
- [ ] `test_submit_validation_and_conflict_modal_work_in_browser`

## tests/test_submit_multilinguality.py

- [ ] `test_submit_form_exposes_default_language_selector`

## tests/test_submit_organization_search_security.py

- [ ] `test_organization_search_treats_query_as_bounded_literal_text`
- [ ] `test_organization_search_normalizes_public_result_fields`
- [ ] `test_submit_autocomplete_uses_shared_safe_native_controls`
- [ ] `test_submit_autocomplete_feedback_is_localized_in_english_and_swedish`
- [ ] `test_submit_autocomplete_renders_and_selects_untrusted_values_safely`
- [ ] `test_submit_autocomplete_ignores_an_older_delayed_failure`

## tests/test_super_admin_permissions.py

- [ ] `test_global_admin_flag_grants_every_permission_scope`
- [ ] `test_super_admin_roles_grant_every_permission`
- [ ] `test_god_role_also_enables_legacy_global_admin_checks_when_loaded`
- [ ] `test_regular_user_still_needs_an_explicit_permission`

## tests/test_super_audit_collection.py

- [ ] `test_super_audit_collection_paginates_with_stable_filter_state`
- [ ] `test_super_audit_collection_uses_shared_empty_state`

## tests/test_support_ticket_email_sender.py

- [ ] `test_ticket_sender_profile_does_not_persist_smtp_credentials`
- [ ] `test_ticket_sender_reads_flask_mapping_without_attribute_access`
- [ ] `test_ticket_profile_resolves_delivery_settings_from_server_config`
- [ ] `test_legacy_empty_ticket_sender_is_recovered_from_server_config`
- [ ] `test_null_ticket_smtp_overrides_use_safe_defaults`
- [ ] `test_delivery_error_sanitizer_redacts_recipient_addresses`
- [ ] `test_email_templates_autoescape_untrusted_contact_fields`
- [ ] `test_support_ingress_preserves_valid_contact_request_id`
- [ ] `test_support_auto_reply_is_disabled_by_default`
- [ ] `test_support_auto_reply_requires_explicit_opt_in`
- [ ] `test_support_auto_reply_respects_explicit_disable`
- [ ] `test_wrapper_ticket_does_not_queue_external_acknowledgement`
- [ ] `test_direct_mail_does_not_queue_external_acknowledgement`

## tests/test_support_ticket_markdown.py

- [ ] `test_support_reply_markdown_formats_html_and_plain_text`
- [ ] `test_support_reply_markdown_blocks_active_content_and_unsafe_links`
- [ ] `test_admin_reply_keeps_existing_template_and_has_distinct_multipart_bodies`
- [ ] `test_email_sender_uses_plain_override_only_when_explicitly_requested`
- [ ] `test_support_reply_delivery_is_multipart_plain_and_html`

## tests/test_surface_manifest.py

- [x] `SurfaceManifestTests::test_route_surface_manifest_matches_source`
- [ ] `SurfaceManifestTests::test_background_job_surface_manifest_matches_source`
- [ ] `SurfaceManifestTests::test_socketio_surface_manifest_matches_source`

QA-01 / USER-01, Codex, 2026-10-18: route-surface definition individually reviewed. AST-derived route/decorator signatures are compared to a checked-in inventory with explicit coverage anchors for every route module. Adding the user-history route produced the CI count mismatch (10 vs 9); only that module's count/hash/coverage was updated, not the test or other surfaces. Keep: detects route drift, not runtime authorization or coverage quality by itself; real new-route tests remain required. Background/socket definitions remain unassessed.

## tests/test_tag_list_localization_contract.py

- [ ] `test_tag_list_uses_localized_stable_empty_state_markup`
- [ ] `test_tag_list_labels_have_english_and_swedish_translations`
- [ ] `test_tag_route_renders_localized_empty_state_contract`

## tests/test_terms_page_contract.py

- [ ] `test_terms_uses_shared_semantic_page_contract_without_local_styles`
- [ ] `test_terms_shared_prose_component_uses_product_tokens_and_focus_state`
- [ ] `test_terms_route_follows_active_locale`
- [ ] `test_terms_catalog_has_complete_nonempty_translations`
- [ ] `test_terms_is_theme_aware_and_portrait_safe`

## tests/test_time_utils.py

- [ ] `test_utcnow_preserves_legacy_naive_utc_contract`

## tests/test_today_page_design_contract.py

- [ ] `test_today_page_uses_shared_header_and_scoped_stylesheet`
- [ ] `test_today_component_uses_product_tokens_for_all_states`
- [ ] `test_empty_state_secondary_action_outweighs_shared_button_rules`
- [ ] `test_today_page_is_theme_aware_and_portrait_safe`

## tests/test_translations_join.py

- [ ] `test_guest_cannot_join`
- [ ] `test_logged_in_user_gains_translation_permissions`
- [ ] `test_join_is_idempotent`
- [ ] `test_join_grants_no_review_permission`
- [ ] `test_translator_page_shows_joined_state`
- [ ] `test_guest_page_shows_login_cta`
- [ ] `test_unjoined_user_page_shows_join_form`

## tests/test_ui_translation_workflow.py

- [ ] `test_translator_can_access_ui_translation_dashboard`
- [ ] `test_admin_dashboard_shows_untranslated_rows_by_default`
- [ ] `test_ui_translation_dashboard_paginates_and_preserves_filters`
- [ ] `test_admin_can_access_ui_translation_sync_dashboard`
- [ ] `test_ui_translation_sync_dashboard_paginates_stably`
- [ ] `test_admin_get_to_approve_route_redirects_instead_of_error`
- [ ] `test_translator_can_open_ui_translation_editor`
- [ ] `test_ui_translation_editor_uses_shared_form_contract`
- [ ] `test_admin_can_open_real_catalog_ui_translation_editor`
- [ ] `test_translator_can_submit_ui_translation_proposal`
- [ ] `test_admin_can_approve_ui_translation_proposal`
- [ ] `test_admin_can_approve_ui_translation_proposal_with_local_write`
- [ ] `test_admin_can_bulk_requeue_ui_translation_sync`
- [ ] `test_background_sync_can_push_approved_ui_translation_to_git`
- [ ] `test_sync_rebases_stale_branch_when_main_has_advanced`
- [ ] `test_sync_skips_pushing_when_branch_is_already_current`
- [ ] `test_sync_can_open_pr_and_attempt_auto_merge`

## tests/test_upload_vendor_assets.py

- [ ] `test_existing_object_without_matching_hash_is_never_overwritten`
- [ ] `test_prefix_validation_finishes_before_any_missing_asset_is_uploaded`
- [ ] `test_untrusted_vendor_content_is_rejected_before_s3_lookup`
- [ ] `test_only_explicit_versioned_manifests_are_accepted`

## tests/test_uptimerobot_exempt.py

- [ ] `TestIsUptimerobotIp::test_known_ipv4_returns_true`
- [ ] `TestIsUptimerobotIp::test_known_ipv6_returns_true`
- [ ] `TestIsUptimerobotIp::test_random_ip_returns_false`
- [ ] `TestIsUptimerobotIp::test_none_returns_false`
- [ ] `TestIsUptimerobotIp::test_empty_string_returns_false`
- [ ] `TestIsUptimerobotIp::test_invalid_ip_returns_false`
- [ ] `TestGetClientIpIpResolution::test_direct_connection_uses_remote_addr`
- [ ] `TestGetClientIpIpResolution::test_spoofed_cf_header_from_non_cloudflare_ignored`
- [ ] `TestGetClientIpIpResolution::test_legitimate_cloudflare_header_accepted`
- [ ] `TestGetClientIpIpResolution::test_spoofed_cf_header_with_normal_ip_uses_real_ip`
- [ ] `TestGetClientIpIpResolution::test_x_forwarded_for_from_non_cloudflare_ignored`
- [ ] `TestRateLimitExemptionCannotBeSpoofed::test_direct_attacker_not_exempt`
- [ ] `TestRateLimitExemptionCannotBeSpoofed::test_spoofed_cf_with_ur_ip_attacker_not_exempt`
- [ ] `TestRateLimitExemptionCannotBeSpoofed::test_legitimate_cf_proxied_ur_ip_gets_exempt`
- [ ] `TestRateLimitExemptionCannotBeSpoofed::test_direct_ur_ip_gets_exempt`

## tests/test_username_validation.py

- [ ] `test_reserved_admin_identity_is_case_and_prefix_insensitive`
- [ ] `test_non_reserved_identity_names_are_allowed`
- [ ] `test_normalize_username`
- [ ] `test_normalize_username_rejects_non_string_values`
- [ ] `test_normalize_email_is_case_and_whitespace_insensitive`
- [ ] `test_validate_username_accepts_supported_usernames`
- [ ] `test_validate_username_rejects_unsupported_usernames`
- [ ] `test_valid_username_provides_boolean_validator_api`
- [ ] `test_username_availability_rejects_invalid_username`
- [ ] `test_username_availability_is_case_insensitive_for_existing_users`
- [ ] `test_registration_normalizes_username`
- [ ] `test_registration_normalizes_email`
- [ ] `test_registration_rejects_email_with_different_casing`
- [ ] `test_database_enforces_canonical_identity_uniqueness`
- [ ] `test_login_normalizes_username`
- [ ] `test_mfa_check_normalizes_username`
- [ ] `test_login_supports_legacy_mixed_case_username`
- [ ] `test_mfa_check_supports_legacy_mixed_case_username`

## tests/test_web_vitals.py

- [ ] `test_vitals_endpoint_stores_only_coarse_aggregate_dimensions`
- [ ] `test_vitals_endpoint_rejects_cross_origin_invalid_and_bot_input`
- [ ] `test_vitals_endpoint_rejects_oversized_bodies_before_parsing`
- [ ] `test_vitals_endpoint_accepts_bounded_chunked_body_without_content_length`
- [ ] `test_vitals_endpoint_bounds_chunked_body_without_content_length`
- [ ] `test_vitals_summary_reports_bounded_histogram_percentiles`
- [ ] `test_web_vitals_migration_is_registered_and_bounded`
- [ ] `test_public_pages_load_pinned_first_party_vitals_without_identifiers`
- [ ] `test_pagehide_flushes_vitals_once_and_restoration_starts_a_new_visit`
- [ ] `test_admin_overview_reads_vitals_once_and_preserves_devices`

## tests/test_websocket_smoke.py

- [ ] `test_chat_socketio_events_cover_friend_listing_history_send_and_read`

## tests/test_wrappers.py

- [ ] `HasDemoPermissionTests::test_normalize_object_id_accepts_object_id_dict`
- [ ] `HasDemoPermissionTests::test_normalize_object_id_returns_none_for_unsupported_value`
- [ ] `HasDemoPermissionTests::test_denies_for_unauthenticated_user`
- [ ] `HasDemoPermissionTests::test_allows_global_admin_without_db_lookup`
- [ ] `HasDemoPermissionTests::test_denies_for_invalid_demo_id`
- [ ] `HasDemoPermissionTests::test_denies_when_demo_missing`
- [ ] `HasDemoPermissionTests::test_allows_user_listed_as_editor`
- [ ] `HasDemoPermissionTests::test_allows_user_listed_as_editor_with_oid_dict`
- [ ] `HasDemoPermissionTests::test_allows_permission_via_organizer_membership`
- [ ] `HasDemoPermissionTests::test_allows_permission_via_organizer_oid_dict`
- [ ] `HasDemoPermissionTests::test_denies_without_matching_permissions`
- [ ] `HasDemoPermissionTests::test_allows_permission_via_city_scope`
- [ ] `HasDemoPermissionTests::test_denies_city_scope_for_other_city`

## tests/test_wrappers_decorators.py

- [ ] `WrapperDecoratorTests::test_permission_required_redirects_unauthenticated_users`
- [ ] `WrapperDecoratorTests::test_permission_required_allows_users_with_permission`
- [ ] `WrapperDecoratorTests::test_permission_required_aborts_when_demo_permission_is_missing`
- [ ] `WrapperDecoratorTests::test_permission_required_allows_demonstration_access_when_granted`
- [ ] `WrapperDecoratorTests::test_deprecated_endpoint_aborts_with_gone`
