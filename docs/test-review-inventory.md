# Individual test review inventory

Baseline: `main` at `52a971e1e11c6560e1eb45393c2ef812bbadd693`, 2026-10-12.

141 Python test files; 1,011 test definitions (1,006 in 140 files under `tests/`, plus five standalone recurrence tests in one file). Twenty-nine MFA/account/passkey definitions have review records below; remaining entries are pending review. The initial inventory came from the baseline revision above; SEC-01 adds eleven net definitions on PR #901. This inventory was extracted from Python AST across tracked repository Python files, excluding fixture definitions; it does not claim parameter expansion or completed review of the whole suite. See [the repository roadmap](../roadmap.md#test-by-test-review-programme) for required evidence and priorities.
Merged #915 adds three account-access definitions; both branches' reviews are retained.

For each checked definition, add its review record under the file heading (requirement, setup/mocks, assertions, variants, reliability, disposition, revision/run/PR evidence). Parameter groups must account for every collected case. Refresh additions/removals at milestones. Include shared fixtures/configuration and standalone test scripts in the supporting audit.

Use the roadmap's P0–P3 policy and status vocabulary. Initial review status for every entry is Backlog; assign an owner and justified priority when triaging it. A discovered security/core-workflow defect can escalate immediately, regardless of its review batch.

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

## tests/test_admin_audit_indexes.py

- [ ] `test_audit_collections_index_the_deterministic_pagination_order`

## tests/test_admin_case_bp.py

- [ ] `test_accept_demo_closes_linked_support_case`
- [ ] `test_case_pages_render_clean_support_case_views`
- [ ] `test_approve_demo_token_closes_linked_support_case`
- [ ] `test_reject_demo_token_closes_linked_support_case`
- [ ] `test_deescalate_writes_case_history`
- [ ] `test_auto_close_cases_respects_approved_field`

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
- [ ] `test_every_full_admin_v2_page_uses_canonical_hero_macro`
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

## tests/test_admin_user_bp.py

- [ ] `test_user_control_paginates_results`
- [ ] `test_user_control_searches_display_names`
- [ ] `test_user_control_filters_by_city_admin_scope`
- [ ] `test_edit_user_exposes_translator_role_and_auto_assigns_permission`
- [ ] `test_create_user_can_assign_translator_role`
- [ ] `test_create_user_can_assign_city_admin_scope`
- [ ] `test_create_city_admin_requires_city_selection`
- [ ] `test_create_user_rejects_reserved_admin_identity`
- [ ] `test_create_user_persists_active_true`
- [ ] `test_user_from_db_defaults_active_true`

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

- [ ] `test_anonymous_edit_token_renders_without_city_admin_navigation`

## tests/test_api_contract.py

- [ ] `ApiContractTests::test_openapi_paths_and_methods_match_api_routes`
- [ ] `ApiContractTests::test_openapi_documents_external_non_bp_endpoints`

## tests/test_auth_login_redirects.py

- [ ] `test_login_does_not_redirect_back_to_notifications_api`
- [ ] `test_login_keeps_normal_internal_page_redirect`

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
- [ ] `test_explicit_object_id_editor_can_open_scoped_audit_views`
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

## tests/test_demo_decision_service.py

- [ ] `test_legacy_approval_is_idempotent_and_reconciles_all_side_effects`
- [ ] `test_token_rejection_consumes_used_token_and_revokes_siblings`
- [ ] `test_form_approval_uses_canonical_decision_service`
- [ ] `test_admin_api_rejection_is_idempotent`
- [ ] `test_notification_delivery_can_retry_without_repeating_decision_effects`
- [ ] `test_bulk_decision_uses_same_service_and_reports_each_result`

## tests/test_demo_edit_link_lifecycle.py

- [ ] `test_edit_link_duration_is_allowlisted_and_registry_expiry_matches`
- [ ] `test_each_edit_link_is_unique_and_revocation_blocks_anonymous_access`
- [ ] `test_anonymous_edit_token_can_save_with_session_csrf`
- [ ] `test_send_edit_link_ignores_client_url_and_does_not_use_persistent_queue`
- [ ] `test_recurring_editor_does_not_offer_regular_demo_edit_links`

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

- [ ] `test_build_sha_is_captured_from_environment`
- [ ] `test_build_sha_file_rejects_partial_or_invalid_values`
- [ ] `test_health_endpoint_publishes_uncached_worker_build`
- [ ] `test_verifier_waits_past_old_worker_for_replacement`
- [ ] `test_verifier_rejects_plain_200_without_matching_metadata`
- [ ] `test_production_deploy_contract_is_sha_bound`

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

- [ ] `test_delete_user_without_fresh_step_up_rejected`
- [ ] `test_delete_user_with_recent_sudo_session_still_requires_fresh`
- [ ] `test_delete_user_with_fresh_webauthn_step_up_succeeds`
- [ ] `test_delete_user_with_fresh_password_step_up_succeeds`
- [ ] `test_delete_user_fresh_token_cannot_be_reused`
- [ ] `test_delete_user_direct_endpoint_without_token_rejected`
- [ ] `test_delete_user_without_admin_permission_rejected`
- [ ] `test_fresh_step_up_token_expires`
- [ ] `test_fresh_step_up_token_bound_to_action_and_target`
- [ ] `test_fresh_step_up_token_not_valid_for_other_actions`
- [ ] `test_existing_admin_actions_still_use_regular_sudo`
- [ ] `test_fresh_step_up_password_requires_totp_when_mfa_enabled`
- [ ] `test_fresh_step_up_options_requires_action`
- [ ] `test_fresh_step_up_verify_without_options_fails`
- [ ] `test_fresh_step_up_options_rejects_unknown_action_and_invalid_target`
- [ ] `test_user_delete_modal_supports_real_webauthn_and_password_fallback`
- [ ] `test_rendered_user_delete_javascript_parses`

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

## tests/test_organization_fill_page.py

- [ ] `test_organization_fill_page_uses_public_org_visual_shell`
- [ ] `test_organization_fill_submission_stores_logo_suggestion`
- [ ] `test_admin_can_apply_logo_suggestion`

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

Focused run evidence is linked in the delivery PR; checked entries mean assessed definitions, not closure of all WebAuthn security requirements. Crypto-origin/RP tampering, consumed assertion replay and cross-user mutations need coverage verification in the remaining QA-01 inventory.

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

- [ ] `test_public_shell_has_language_and_semantic_footer_lists`
- [ ] `test_city_today_page_has_a_document_language`
- [ ] `test_public_chat_feedback_uses_safe_shared_toast`
- [ ] `test_api_documentation_code_blocks_are_focusable_and_links_are_distinct`

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

- [ ] `test_public_demonstrations_list_uses_summary_payload`

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

- [ ] `test_public_inline_style_debt_matches_reviewed_baseline`
- [ ] `test_public_inline_style_baseline_scope_is_documented`
- [ ] `test_style_attribute_scanner_covers_all_valid_static_forms`

## tests/test_public_listing_contract.py

- [ ] `test_public_listing_family_uses_shared_hero_and_pagination_markup`
- [ ] `test_public_listing_pagination_controller_supports_buttons_and_sentinels`
- [ ] `test_public_workspace_styles_cover_listing_end_message`
- [ ] `test_public_list_runtime_uses_defined_localized_browser_contracts`
- [ ] `test_public_list_filters_and_date_picker_follow_active_locale`

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

- [ ] `test_shared_information_cards_have_mobile_shrink_contract`
- [ ] `test_information_cards_fit_portrait_viewport`

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
- [ ] `test_organization_scope_does_not_leak_to_unrelated_demonstration`
- [ ] `test_toolbar_is_omitted_without_demo_or_organization_context`
- [ ] `test_toolbar_fits_public_detail_in_both_themes`

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

- [ ] `test_step_up_password_grants_elevation`
- [ ] `test_step_up_rejects_wrong_password`
- [ ] `test_step_up_requires_totp_when_mfa_enabled`
- [ ] `test_step_up_password_without_mfa_and_without_totp_works`
- [ ] `test_step_up_options_reflect_methods`
- [ ] `test_step_up_webauthn_flow`
- [ ] `test_elevation_times_out`
- [ ] `test_elevation_does_not_leak_across_sessions`
- [ ] `test_sudo_required_redirects_anonymous_to_login`
- [ ] `test_logout_clears_elevation`
- [ ] `test_change_password_requires_step_up`

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

- [ ] `SurfaceManifestTests::test_route_surface_manifest_matches_source`
- [ ] `SurfaceManifestTests::test_background_job_surface_manifest_matches_source`
- [ ] `SurfaceManifestTests::test_socketio_surface_manifest_matches_source`

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
