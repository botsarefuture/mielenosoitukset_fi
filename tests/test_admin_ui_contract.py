from pathlib import Path
from html.parser import HTMLParser


ADMIN_TEMPLATE_ROOTS = (
    Path("mielenosoitukset_fi/templates/admin"),
    Path("mielenosoitukset_fi/templates/admin_V2"),
)


def _admin_templates():
    for root in ADMIN_TEMPLATE_ROOTS:
        yield from root.rglob("*.html")


class _AdminHeroContractParser(HTMLParser):
    """Collect structural hero violations without rendering Jinja templates."""

    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
    _ALLOWED_CHILDREN = {
        "admin-page-hero__content",
        "admin-page-hero__actions",
        "admin-page-hero__metric",
        "admin-page-hero__nav",
    }

    def __init__(self):
        super().__init__()
        self.stack = []
        self.violations = []

    def handle_starttag(self, tag, attrs):
        classes = set(dict(attrs).get("class", "").split())
        if self.stack and self.stack[-1]["is_hero"]:
            if not classes.intersection(self._ALLOWED_CHILDREN):
                self.violations.append(
                    f"unexpected direct <{tag}> child of admin-page-hero"
                )
            if "admin-page-hero__content" in classes:
                self.stack[-1]["has_content"] = True

        node = {
            "tag": tag,
            "is_hero": "admin-page-hero" in classes,
            "has_content": False,
        }
        if tag not in self._VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] != tag:
                continue
            closing = self.stack[index:]
            del self.stack[index:]
            for node in reversed(closing):
                if node["is_hero"] and not node["has_content"]:
                    self.violations.append(
                        "admin-page-hero is missing admin-page-hero__content"
                    )
            return


def test_full_admin_templates_use_the_admin_shell():
    violations = []

    for template in _admin_templates():
        source = template.read_text(encoding="utf-8")
        if "{% extends" not in source:
            continue
        if "admin_base.html" not in source or "{% block content %}" in source:
            violations.append(str(template))

    assert violations == []


def test_admin_theme_is_applied_before_styles_and_controls_color_scheme():
    base = Path("mielenosoitukset_fi/templates/admin_base.html").read_text(
        encoding="utf-8"
    )
    workspace = Path("mielenosoitukset_fi/static/css/admin/workspace.css").read_text(
        encoding="utf-8"
    )

    assert base.index("localStorage.getItem('theme')") < base.index("variables.css")
    assert "html.light" in workspace and "color-scheme: light" in workspace
    assert "html.dark" in workspace and "color-scheme: dark" in workspace
    assert "modal-content, .modal-header, .modal-body, .modal-footer" not in base


def test_legacy_dialog_does_not_override_bootstrap_modal():
    modal_css = Path("mielenosoitukset_fi/static/css/admin/modal.css").read_text(
        encoding="utf-8"
    )

    selectors = {
        line.strip().removesuffix("{").strip()
        for line in modal_css.splitlines()
        if line.strip().endswith("{")
    }
    assert ".modal" not in selectors
    assert ".modal-header" not in selectors
    assert ".modal-body" not in selectors
    assert ".modal-footer" not in selectors


def test_admin_design_standard_is_documented():
    standard = Path("docs/ADMIN_UI_STANDARD.md").read_text(encoding="utf-8")

    assert "## Lists and tables" in standard
    assert "## Modals" in standard
    assert "--admin-workspace-surface" in standard


def test_admin_page_heroes_keep_copy_in_one_content_group():
    violations = []

    for template in Path("mielenosoitukset_fi/templates/admin_V2").rglob("*.html"):
        parser = _AdminHeroContractParser()
        parser.feed(template.read_text(encoding="utf-8"))
        violations.extend(f"{template}: {message}" for message in parser.violations)

    assert violations == []


def test_admin_hero_foreground_and_data_view_surfaces_are_shared():
    workspace = Path("mielenosoitukset_fi/static/css/admin/workspace.css").read_text(
        encoding="utf-8"
    )
    users = Path(
        "mielenosoitukset_fi/templates/admin_V2/_users_table.html"
    ).read_text(encoding="utf-8")

    assert "color: var(--admin-heading-color, var(--admin-workspace-text));" in workspace
    assert "--admin-heading-color: var(--admin-hero-foreground);" in workspace
    assert "--admin-hero-muted-foreground:" in workspace
    assert "admin-data-view__header admin-result-summary" in users
    assert "admin-data-view__viewport users-table-scroll" in users
    assert "admin-data-view__footer admin-pagination" in users
    assert ".users-results-heading" not in users


def test_user_role_forms_use_shared_admin_contract():
    edit = Path(
        "mielenosoitukset_fi/templates/admin_V2/user/edit.html"
    ).read_text(encoding="utf-8")
    modals = Path(
        "mielenosoitukset_fi/templates/admin_V2/_modals_users.html"
    ).read_text(encoding="utf-8")

    assert "admin_page_hero(" in edit
    assert 'class="admin-form admin-user-form"' in edit
    assert "admin-form-section" in edit
    assert "admin-sticky-actions" in edit
    assert "modal fade admin-modal" in modals


def test_demo_collection_uses_server_side_filter_and_pagination_contract():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html"
    ).read_text(encoding="utf-8")
    route = Path(
        "mielenosoitukset_fi/admin/admin_demo_bp.py"
    ).read_text(encoding="utf-8")

    for contract in (
        "admin-filter-bar",
        "admin-advanced-filters",
        "admin-active-filters",
        "admin-result-summary",
        "admin-pagination",
        "admin-page-size",
    ):
        assert contract in template
    assert "filterRows" not in template
    assert '"priority": {"_sort_priority": 1, "date": 1, "_id": 1}' in route
    assert '"date_desc": {"date": -1, "_id": -1}' in route
    assert "filtered_count = mongo.demonstrations.count_documents(filter_query)" in route


def test_secondary_editors_use_shared_form_primitives():
    merge = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/merge.html"
    ).read_text(encoding="utf-8")
    ui_editor = Path(
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/editor.html"
    ).read_text(encoding="utf-8")

    assert "{% block styles %}" not in merge
    assert "admin-form admin-merge-form" in merge
    assert "admin-sticky-actions" in merge
    assert "admin-code-block" in ui_editor
    assert "admin-panel-inset" in ui_editor
    assert 'class="admin-form"' in ui_editor


def test_organization_workflows_use_shared_admin_components():
    form = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/form.html"
    ).read_text(encoding="utf-8")
    review = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/review_suggestion.html"
    ).read_text(encoding="utf-8")
    macros = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/macros.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    for template in (form, review, macros):
        assert "<style" not in template
        assert "style=" not in template
    assert "admin-form-layout" in form
    assert "admin-form-section__header" in form
    assert "admin-sticky-actions__buttons" in form
    assert "{{ invite_modal(organization) }}" in form
    assert "organization and can_invite_members" in form
    assert "admin-data-view__viewport" in review
    assert "admin-selection-checkbox field-checkbox" in review
    assert "applyBtn.style" not in review
    assert "--admin-workspace-on-primary: #ffffff;" in workspace
    assert "background: var(--admin-workspace-primary-bg);" in workspace
    assert "background: var(--admin-workspace-primary-hover);" in workspace


def test_organization_collection_uses_shared_data_view_contract():
    dashboard = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/dashboard.html"
    ).read_text(encoding="utf-8")

    assert "<style" not in dashboard
    assert "style=" not in dashboard
    assert 'class="admin-page admin-workspace"' in dashboard
    assert "admin-workspace-summary-card" in dashboard
    assert "admin-filter-bar__primary--search" in dashboard
    assert "admin-data-view__viewport" in dashboard
    assert "admin-data-view__footer admin-pagination" in dashboard
    assert "admin-pagination__info" in dashboard
    assert "admin-entity-identity" in dashboard
    assert "aria-selected" in dashboard


def test_organization_detail_uses_shared_components_and_scoped_controls():
    detail = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/view.html"
    ).read_text(encoding="utf-8")

    assert "<style" not in detail
    assert "style=" not in detail
    assert "admin-detail-layout" in detail
    assert detail.count("admin-data-view") >= 2
    assert "admin-section-card" in detail
    assert "admin-modal admin-workflow-modal" in detail
    assert "admin-toast" in detail
    assert "{% if can_edit_organization %}" in detail
    assert "{% if can_invite_members %}" in detail
    assert "bootstrap.Modal.getOrCreateInstance" in detail
    assert "org-button" not in detail
    assert "org-role-select" not in detail


def test_organization_pages_use_canonical_hero_macro_and_navigation():
    macro = Path("mielenosoitukset_fi/templates/admin_V2/macros.html").read_text(
        encoding="utf-8"
    )
    pages = (
        "dashboard.html",
        "form.html",
        "review_suggestion.html",
        "view.html",
    )

    assert "macro admin_page_hero" in macro
    assert 'class="admin-breadcrumbs"' in macro
    assert 'class="admin-page-hero__content"' in macro
    assert 'class="admin-page-hero__actions"' in macro
    assert "admin-page-hero__back" in macro
    assert macro.index("back_url") < macro.index("caller()")
    for name in pages:
        source = Path(
            "mielenosoitukset_fi/templates/admin_V2/organizations", name
        ).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source


def test_city_admin_operational_pages_use_canonical_hero_macro():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/cities/index.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/form.html",
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form_v2.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[2:]:
        source = Path(name).read_text(encoding="utf-8")
        assert source.lstrip().startswith("{% extends")
        assert "float:right" not in source


def test_access_management_pages_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/user/list.html",
        "mielenosoitukset_fi/templates/admin_V2/user/edit.html",
        "mielenosoitukset_fi/templates/admin_V2/governance/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/governance/clearances.html",
        "mielenosoitukset_fi/templates/admin_V2/governance/audit.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[1:2] + pages[3:]:
        assert "back_url=" in Path(name).read_text(encoding="utf-8")


def test_translation_workspaces_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_editor.html",
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/editor.html",
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/sync_dashboard.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[:2] + pages[3:]:
        assert "back_url=" in Path(name).read_text(encoding="utf-8")


def test_system_workspaces_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/background_jobs.html",
        "mielenosoitukset_fi/templates/admin_V2/background_job_detail.html",
        "mielenosoitukset_fi/templates/admin_V2/status.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
    for name in pages[1:]:
        source = Path(name).read_text(encoding="utf-8")
        assert "admin.admin_dashboard" in source
    assert "back_url=" in Path(pages[2]).read_text(encoding="utf-8")


def test_audit_and_developer_pages_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/logs.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_log.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_timeline.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/magic_tokens.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/submission_errors.html",
        "mielenosoitukset_fi/templates/admin_V2/developer/requests.html",
        "mielenosoitukset_fi/templates/admin_V2/developer/user_apps.html",
        "mielenosoitukset_fi/templates/admin_V2/user/api_tokens.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[1:4] + pages[6:]:
        assert "back_url=" in Path(name).read_text(encoding="utf-8")


def test_analytics_pages_use_shared_hero_metric_slot():
    macro = Path(
        "mielenosoitukset_fi/templates/admin_V2/macros.html"
    ).read_text(encoding="utf-8")
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/analytics.html",
        "mielenosoitukset_fi/templates/admin_V2/stats.html",
    )

    assert "metric_value=none" in macro
    assert 'class="admin-page-hero__metric"' in macro
    assert "metric_id" in macro
    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "metric_value=" in source
        assert "admin.admin_dashboard" in source
    assert "analytics-hero" not in Path(pages[0]).read_text(encoding="utf-8")
    stats_css = Path(
        "mielenosoitukset_fi/static/css/admin/stats.css"
    ).read_text(encoding="utf-8")
    assert ".stats-hero" not in stats_css


def test_admin_boolean_controls_do_not_inherit_text_field_geometry():
    workspace = Path("mielenosoitukset_fi/static/css/admin/workspace.css").read_text(
        encoding="utf-8"
    )
    demo_form = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/form.html"
    ).read_text(encoding="utf-8")
    recurring_form = Path(
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form_v2.html"
    ).read_text(encoding="utf-8")

    assert ":is(.form-control, .form-select, .form-check-input)" not in workspace
    assert 'input[type="checkbox"].form-check-input' in workspace
    assert 'input[type="radio"].form-check-input' in workspace
    assert ".form-check-input:indeterminate" in workspace
    assert ".form-check-input:focus-visible" in workspace
    for template in (demo_form, recurring_form):
        assert "{% if can_approve_demo|default(false) %}" in template
        assert 'class="admin-check-row"' in template
        assert "data-admin-boolean" in template
        assert 'aria-live="polite"' in template
